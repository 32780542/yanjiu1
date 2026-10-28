"""开放路段的持续随机交通：原规则决策、原积分、独立油耗评价。"""

from bisect import bisect_left, bisect_right
from collections import deque
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import time
import traceback
from types import SimpleNamespace
import zipfile

from experiments import phase5g
from experiments.formation_study import entry_is_clear as headway_entry_clear
from experiments.formation_study import study_parameters, write_json, substep_incidents
from experiments.traffic_metrics import summarize_trips
from models.fuel import fuel_rate_mg_s
from models.kinematic import kinematic_state
from noa.contracts import NoaMemory
from noa.driving import stop_distance
from noa.controller import decide
from noa.simple_formation import SimpleFormationMemory
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import VisibleRoad
from research.common import ROOT


def arrival_tape(lanes, flow, seed, duration_s):
    """固定时间窗内逐车道独立来车，无车辆数上限，无首车强制入场。"""
    probability = flow*.1/3600
    if lanes not in (2, 3, 4) or not 0 < probability <= 1:
        raise ValueError("需要2/3/4车道及有效每车道需求率")
    ticks = round(duration_s*10)
    if ticks <= 0 or abs(ticks/10-duration_s) > 1e-9:
        raise ValueError("持续发车时长必须为正的0.1s整数倍")
    streams = [random.Random(f"continuous-arrival:{seed}:{lane}") for lane in range(lanes)]
    return [dict(vehicle_id=f"v{lane}_{tick:05d}", requested_s=tick/10, lane=lane)
            for tick in range(ticks) for lane in range(lanes)
            if streams[lane].random() < probability]


def entry_is_clear(entry, states, p):
    """安全插入同时满足时距与原模型含执行滞后的紧急制动距离。"""
    if not headway_entry_clear(entry, states, p):
        return False
    own_stop = stop_distance(entry.vx_mps, 0., abs(p["min_accel_mps2"]), p)
    for state in states.values():
        half_y = (p["length_m"]*abs(math.sin(state.heading_rad))
                  + p["width_m"]*abs(math.cos(state.heading_rad)))/2
        if abs(state.y_m-entry.y_m) > half_y+p["width_m"]/2:
            continue
        front_stop = state.vx_mps**2/(2*abs(p["min_accel_mps2"]))
        required = p["length_m"]+2*p["noa_body_margin_m"]+p["noa_standstill_gap_m"]+own_stop-front_stop
        if state.x_m-entry.x_m < required:
            return False
    return True


@dataclass(frozen=True, slots=True)
class CandidateFrame:
    vehicles: tuple


class FrameIndex:
    """对已校验世界快照作保守空间裁剪，再由原传感器精确判断可见性。"""
    def __init__(self, frame):
        self.vehicles = tuple(sorted(frame.vehicles, key=lambda v: v.state.x_m))
        self.xs = tuple(v.state.x_m for v in self.vehicles)
        self.by_key = {v.key: v for v in self.vehicles}

    def around(self, key):
        x = self.by_key[key].state.x_m
        # sqrt(200²+50²)<207，覆盖任意朝向的当前传感矩形。
        lo, hi = bisect_left(self.xs, x-207), bisect_right(self.xs, x+207)
        return CandidateFrame(self.vehicles[lo:hi])


def audit_open_steps(steps, trips, lanes, incidents, seen):
    """车体只在测量路段内参与审计，出口跨越点也纳入检查。"""
    exits = {key:trips[key]["exited_s"] for key in steps
             if trips[key]["exited_s"] is not None}
    if not exits:
        substep_incidents(steps, lanes, incidents, seen)
        return
    sample_times = {s.time_s for s in next(iter(steps.values())).samples}
    for at in sorted(sample_times | set(exits.values())):
        active = {}
        for key, step in steps.items():
            if key in exits and at > exits[key]+1e-10:
                continue
            index = min(len(step.samples)-1, max(0, int((at-step.initial.time_s)/.01-1e-8)))
            before = step.initial if index == 0 else step.samples[index-1]
            after = step.samples[index]
            fraction = (at-before.time_s)/(after.time_s-before.time_s)
            state = replace(before, time_s=at,
                x_m=before.x_m+(after.x_m-before.x_m)*fraction,
                y_m=before.y_m+(after.y_m-before.y_m)*fraction,
                heading_rad=before.heading_rad+(after.heading_rad-before.heading_rad)*fraction)
            active[key] = SimpleNamespace(samples=(state,))
        if active:
            substep_incidents(active, lanes, incidents, seen)


class OpenTraffic:
    def __init__(self, case, tape):
        self.case, self.tape = case, tape
        if case["formation"]:
            self.model, self.p, self.policy = study_parameters(case["target_speed_mps"], case["same_lane_gap_m"])
        else:
            self.model, self.p, self.policy = phase5g.parameters("off", case["target_speed_mps"])
        # 两组共同采用常规跟驰/车道保持；横向差异仅来自当前编队补位。
        self.p["noa_overtake_speed_deficit_mps"] = 2*self.p["max_speed_mps"]+1
        self.policy["noa_overtake_speed_deficit_mps"] = self.p["noa_overtake_speed_deficit_mps"]
        width = case["lane_count"]*3.3
        # 1200m为测量出口，路面继续延伸，车辆不会把出口误当停车墙。
        self.road = VisibleRoad((((-300., 0.), (2000., 0.)), ((-300., width), (2000., width))),
            tuple(((-300., lane*3.3), (2000., lane*3.3)) for lane in range(1, case["lane_count"])))
        self.tick_index, self.cursor = 0, 0
        self.entered_count, self.exited_count = 0, 0
        self.states, self.sensors, self.memories = {}, {}, {}
        self.queues = [deque() for _ in range(case["lane_count"])]
        self.trips = {r["vehicle_id"]: dict(r, entered_s=None, exited_s=None,
            distance_m=0., onroad_s=0., fuel_mg=0., lane_changes=0) for r in tape}
        self.incidents = {"collision_events": [], "road_departure_events": []}
        self.seen = {"collision": set(), "road": set()}
        self.digest = hashlib.sha256()

    @property
    def now(self):
        return self.tick_index/10

    def _admit(self):
        while self.cursor < len(self.tape) and self.tape[self.cursor]["requested_s"] <= self.now+1e-9:
            row = self.tape[self.cursor]
            self.queues[row["lane"]].append(row["vehicle_id"])
            self.cursor += 1
        for lane, queue in enumerate(self.queues):
            if not queue:
                continue
            key = queue[0]
            entry = kinematic_state(self.p, time_s=self.now, x_m=0., y_m=3.3*(lane+.5), vx_mps=28.8)
            if not entry_is_clear(entry, self.states, self.p):
                continue
            queue.popleft()
            self.states[key] = entry
            self.sensors[key] = IdealSensor(self.p, self.road)
            self.memories[key] = (SimpleFormationMemory((), "CRUISE") if self.case["formation"]
                                  else NoaMemory((), "CRUISE"))
            self.trips[key]["entered_s"] = self.now
            self.entered_count += 1

    def tick(self):
        self._admit()
        if not self.states:
            self.tick_index += 1
            return dict(time_s=self.now, distance_m=0., fuel_mg=0., vehicle_seconds=0., active=0,
                        pending=sum(map(len, self.queues)), entered=self.entered_count, exited=self.exited_count)
        frame = WorldFrame(tuple(TruthVehicle(key, state, 4., 1.8,
            self.model.observe(state)["a_long_mps2"]) for key, state in self.states.items()))
        index = FrameIndex(frame)
        decisions = {}
        for key in sorted(self.states):
            sample = self.sensors[key].sample(key, index.around(key))
            memory = replace(self.memories[key], observation_history=sample.memory.observation_history)
            decisions[key] = decide(replace(sample, memory=memory), self.policy)
        steps = {key: self.model.advance(self.states[key], decision.action, .1, .01)
                 for key, decision in decisions.items()}
        distance, fuel, vehicle_seconds, exited = 0., 0., 0., 0
        next_states, next_memories = {}, {}
        for key, step in steps.items():
            row, before = self.trips[key], step.initial
            for after in step.samples:
                fraction = min(1., (1200-before.x_m)/(after.x_m-before.x_m)) if after.x_m >= 1200 else 1.
                dt = (after.time_s-before.time_s)*fraction
                end_speed = before.vx_mps+(after.vx_mps-before.vx_mps)*fraction
                speed = (before.vx_mps+end_speed)/2
                acceleration = (after.vx_mps-before.vx_mps)/(after.time_s-before.time_s)
                consumption = fuel_rate_mg_s(speed, acceleration)*dt
                row["distance_m"] += speed*dt
                row["onroad_s"] += dt
                row["fuel_mg"] += consumption
                distance, fuel, vehicle_seconds = distance+speed*dt, fuel+consumption, vehicle_seconds+dt
                if after.x_m >= 1200:
                    row["exited_s"] = before.time_s+dt
                    exited += 1
                    break
                before = after
            row["lane_changes"] = decisions[key].memory.completed_lane_changes
            if row["exited_s"] is None:
                next_states[key] = replace(step.final, time_s=(self.tick_index+1)/10)
                next_memories[key] = decisions[key].memory
            else:
                del self.sensors[key]
        audit_open_steps(steps, self.trips, self.case["lane_count"], self.incidents, self.seen)
        self.states, self.memories = next_states, next_memories
        # 摘要覆盖每拍实际状态与命令；仅保存1s物理样本，减少长期流量存储。
        self.digest.update(json.dumps({key: (asdict(steps[key].final), asdict(decisions[key].action))
            for key in sorted(steps)}, separators=(",", ":"), allow_nan=False).encode())
        self.tick_index += 1
        self.exited_count += exited
        entered, completed = self.entered_count, self.exited_count
        pending = sum(map(len, self.queues))
        if self.cursor != entered+pending or entered != completed+len(self.states):
            raise RuntimeError("持续交通车辆守恒失败")
        return dict(time_s=self.now, distance_m=distance, fuel_mg=fuel,
            vehicle_seconds=vehicle_seconds, active=len(self.states), pending=pending,
            entered=entered, exited=completed)


def planned_cases():
    def case(kind, lanes, flow, seed, on, speed=28.8, gap=30.):
        name = f"{kind}_L{lanes}_q{flow}_v{speed:g}_d{gap:g}_s{seed}_{'on' if on else 'off'}"
        return dict(name=name, kind=kind, lane_count=lanes, flow_veh_h_lane=flow,
            seed=seed, formation=on, target_speed_mps=speed, same_lane_gap_m=gap,
            demand_duration_s=600., max_time_s=2400.)
    cases = [case("demand", 3, flow, seed, on)
             for flow in (1250,1500,1750,2000) for seed in (1,2,3) for on in (False,True)]
    cases += [case("lanes", lanes, 1500, seed, on)
              for lanes in (2,4) for seed in (1,2,3) for on in (False,True)]
    cases += [case("speed", 3, 1500, seed, on, speed=speed)
              for speed in (24.,32.) for seed in (1,2,3) for on in (False,True)]
    cases += [case("gap", 3, 1500, seed, True, gap=gap)
              for gap in (24.,36.) for seed in (1,2,3)]
    return cases


def run_case(case, root):
    started = time.perf_counter()
    directory = Path(root)/case["name"]
    directory.mkdir()
    tape = arrival_tape(case["lane_count"], case["flow_veh_h_lane"], case["seed"], case["demand_duration_s"])
    clock = OpenTraffic(case, tape)
    write_json(directory/"input.json", dict(case=case, arrivals=tape, parameters=clock.p,
        policy=clock.policy, fuel_class="HBEFA3/PC_G_EU4", fuel_mass_kg=1500., slope_deg=0.))
    with gzip.open(directory/"network.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as network, \
         gzip.open(directory/"positions.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as positions:
        while clock.now < case["max_time_s"] and (clock.now < case["demand_duration_s"]
                or clock.states or clock.cursor < len(tape) or any(clock.queues)):
            event = clock.tick()
            network.write(json.dumps(event, separators=(",", ":"))+"\n")
            if clock.tick_index % 10 == 0:
                positions.write(json.dumps(dict(time_s=clock.now,
                    states={key: [s.x_m,s.y_m,s.vx_mps,s.a_drive_mps2] for key,s in clock.states.items()}),
                    separators=(",", ":"))+"\n")
            if clock.tick_index % 100 == 0:
                network.flush()
                positions.flush()
            if clock.tick_index % 1000 == 0:
                print(json.dumps(dict(case=case["name"], simulation_s=clock.now,
                    active=len(clock.states), pending=sum(map(len, clock.queues)))), flush=True)
            if clock.seen["collision"] or clock.seen["road"]:
                break
    trips = list(clock.trips.values())
    write_json(directory/"trips.json", trips)
    write_json(directory/"incidents.json", clock.incidents)
    result = {**case, **summarize_trips(trips, case["demand_duration_s"], clock.now),
        "status": "completed", "collision_pairs":len(clock.seen["collision"]),
        "road_departure_vehicles":len(clock.seen["road"]),
        "trajectory_digest":clock.digest.hexdigest(), "wall_s":time.perf_counter()-started}
    result["termination_reason"] = ("collision" if clock.seen["collision"] else
        "road_departure" if clock.seen["road"] else "drained" if result["all_completed"] else "time_limit")
    write_json(directory/"result.json", result)
    write_json(directory/"hashes.json", {p.name:hashlib.sha256(p.read_bytes()).hexdigest()
               for p in directory.iterdir() if p.is_file()})
    return result


def run_study(*, cases=None, workers=8, output_base=None):
    cases = planned_cases() if cases is None else cases
    base = ROOT/"results/continuous_traffic" if output_base is None else Path(output_base)
    root = base/datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root.mkdir(parents=True)
    sources = [p for folder in ("noa","models","perception","simulation","experiments","configs","safety","research")
               for p in (ROOT/folder).glob("*") if p.suffix in (".py",".json")]
    with zipfile.ZipFile(root/"source_snapshot.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for p in sources:
            archive.write(p, p.relative_to(ROOT).as_posix())
    write_json(root/"protocol.json", dict(schema="continuous_traffic_v2", cases=cases,
        user_selected_road="MATLAB constant-lane straight road", road_length_m=1200.,
        dt_control_s=.1, dt_physics_s=.01, fuel_model="HBEFA3/PC_G_EU4",
        workers=workers, entry="lane FIFO; time headway and model emergency stopping distance",
        stop_on_first_safety_incident=True,
        baseline="ordinary car following and lane keeping; spontaneous overtaking disabled in both modes",
        source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}))
    print(json.dumps(dict(study_root=str(root), cases=len(cases))), flush=True)
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool, (root/"results.jsonl").open("w", encoding="utf-8") as stream:
        futures = {pool.submit(run_case, case, root):case for case in cases}
        for future in as_completed(futures):
            case = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {**case, "status":"error", "error":str(error), "traceback":traceback.format_exc()}
                write_json(root/case["name"]/"error.json", result)
            results.append(result)
            stream.write(json.dumps(result, ensure_ascii=False, allow_nan=False)+"\n")
            stream.flush()
            print(json.dumps(dict(done=len(results), case=case["name"], status=result["status"],
                completed=result.get("completed"), requested=result.get("requested"))), flush=True)
    write_json(root/"summary.json", dict(case_count=len(cases), results=sorted(results,key=lambda r:r["name"])))
    return root
