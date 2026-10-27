"""MATLAB 式随机到达的纯规则编队实验，保存紧凑物理轨迹。"""

from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, replace
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import random
import time
from types import MappingProxyType

from experiments import phase5g
from experiments.formation_metrics import evaluate_run
from models.geometry import BodyPose
from models.kinematic import kinematic_state
from models.vehicle import VehicleState
from perception.ideal import IdealSensor
from perception.road import VisibleRoad
from research.common import ROOT, read_json
from safety.geometry import collide
from simulation.phase5g_clock import CLOCK_SCHEMA, Phase5GClock, initial_memory_hash


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                  allow_nan=False)+"\n", encoding="utf-8")


def bernoulli_requests(count, lanes, flow, seed):
    """每拍、每车道独立来车；保留 MATLAB 的 p=q·0.1/3600 语义。"""
    probability = flow * 0.1 / 3600
    if count < 1 or lanes not in (2, 3, 4) or not 0 < probability <= 1:
        raise ValueError("需要正车辆数、2/3/4 车道以及 (0,36000] 的每车道流量")
    arrivals = [random.Random(f"arrival:{seed}:{lane}") for lane in range(lanes)]
    speeds = random.Random(f"speed:{seed}")
    rows, tick = [], 0
    while len(rows) < count:
        tick += 1
        for lane in range(lanes-1, -1, -1):
            if arrivals[lane].random() < probability:
                rows.append((round(tick*.1, 1), lane, speeds.uniform(8., 12.)))
                if len(rows) == count:
                    break
    return rows


def study_parameters(speed, gap):
    registered = read_json("configs/phase5g.json")
    simple = {key: registered[key] for key in phase5g.simple_formation.PARAMETERS}
    simple["simple_formation_same_lane_gap_m"] = gap
    return phase5g.parameters("lane_priority", speed, simple_rules=True,
                             simple_overrides=simple)


def entry_is_clear(entry, states, physical):
    """入口使用已有静止间距与时距；相交于入口车道的车辆均参与检查。"""
    required = (physical["length_m"] + 2*physical["noa_body_margin_m"]
                + physical["noa_standstill_gap_m"]
                + physical["noa_headway_s"] * entry.vx_mps)
    for state in states.values():
        half_y = (physical["length_m"]*abs(math.sin(state.heading_rad))
                  + physical["width_m"]*abs(math.cos(state.heading_rad)))/2
        if abs(state.y_m-entry.y_m) <= half_y + physical["width_m"]/2:
            if state.x_m - entry.x_m < required:
                return False
    return True


class StudyClock(Phase5GClock):
    """沿用感知、决策和积分，仅省去完整诊断树的重复序列化。"""

    def _admit_queued(self):
        now = round(self._current_time(), 10)
        states, sensors, memories = dict(self.states), dict(self.sensors), dict(self.memories)
        states = {key: replace(state, time_s=now) for key, state in states.items()}
        blocked_lanes = set()
        for key in self._all_controlled:
            row = self._departures[key]
            if row["actual_departure_s"] is not None or row["scheduled_departure_s"] > now+1e-9:
                continue
            entry = replace(VehicleState(**row["state"]), time_s=now)
            lane = round((entry.y_m-1.65)/3.3)
            if lane in blocked_lanes or not entry_is_clear(entry, states, self.p):
                blocked_lanes.add(lane)
                continue
            states[key] = entry
            sensors[key] = IdealSensor(self.p, self._road)
            memories[key] = self._restored_memories[key]
            row["actual_departure_s"] = now
        self.states, self.sensors, self.memories = MappingProxyType(states), sensors, memories
        self._rebuild_active_state()

    def tick_compact(self, *, queue_entries=True):
        if queue_entries:
            self._admit_queued()
        else:
            self._activate_due()
        frame = self._frame()
        decisions = {}
        for key in sorted(self.states):
            sample = self.sensors[key].sample(key, frame)
            memory = replace(self.memories[key], observation_history=sample.memory.observation_history)
            decisions[key] = self._decide(replace(sample, memory=memory))
        steps = {key: self.model.advance(self.states[key], decision.action,
                                        self.dt, self.integration_dt)
                 for key, decision in decisions.items()}
        self.states = MappingProxyType({key: step.final for key, step in steps.items()})
        self.memories = {key: decision.memory for key, decision in decisions.items()}
        return steps, decisions


def make_clock(case):
    model, physical, policy = study_parameters(case["target_speed_mps"], case["same_lane_gap_m"])
    requests = bernoulli_requests(case["vehicle_count"], case["lane_count"],
                                  case["flow_veh_h_lane"], case["seed"])
    origin = requests[0][0]
    departures = {}
    for ordinal, (requested, lane, speed) in enumerate(requests):
        state = kinematic_state(physical, x_m=100., y_m=3.3*(lane+.5), vx_mps=speed)
        departures[f"v{ordinal:02d}"] = dict(scheduled_departure_s=round(requested-origin, 1),
            actual_departure_s=None, state=asdict(state), physical_ordinal=ordinal)
    initial = {key: VehicleState(**row["state"]) for key, row in departures.items()
               if row["scheduled_departure_s"] == 0}
    memories = {key: asdict(phase5g.simple_formation.SimpleFormationMemory((), "CRUISE"))
                for key in departures}
    width = case["lane_count"]*3.3
    road = VisibleRoad((((0., 0.), (10000., 0.)), ((0., width), (10000., width))),
                       tuple(((0., 3.3*lane), (10000., 3.3*lane))
                             for lane in range(1, case["lane_count"])))
    clock = StudyClock(initial, model, road, physical, policy, tuple(departures), {},
        memories, clock_schema=CLOCK_SCHEMA,
        initial_memories_sha256=initial_memory_hash(memories), departures=departures)
    return clock, origin


def physical_frame(clock, decisions=None, initial_steps=None):
    states = (clock.states if initial_steps is None else
              {key: step.initial for key, step in initial_steps.items()})
    return {"time_s": round(next(iter(states.values())).time_s, 10),
            "states": {key: asdict(state) for key, state in states.items()},
            "join_diagnostics": {} if decisions is None else {
                key: {name: decision.diagnostics.get("simple_formation", {}).get(name)
                      for name in ("join_phase", "lane_reason")}
                for key, decision in decisions.items()}}


def substep_incidents(steps, lane_count, incidents, seen):
    """在原模型全部积分子步检查车体，避免只查控制拍遗漏接触。"""
    for index in range(len(next(iter(steps.values())).samples)):
        states = {key: step.samples[index] for key, step in steps.items()}
        bodies = {key: BodyPose(s.x_m, s.y_m, s.heading_rad, 4., 1.8)
                  for key, s in states.items()}
        keys = sorted(states, key=lambda key: states[key].x_m)
        for i, left in enumerate(keys):
            state = states[left]
            half_y = (4*abs(math.sin(state.heading_rad))+1.8*abs(math.cos(state.heading_rad)))/2
            if (state.y_m-half_y < -1e-8 or state.y_m+half_y > 3.3*lane_count+1e-8) and left not in seen["road"]:
                incidents["road_departure_events"].append(dict(time_s=state.time_s, actor=left))
                seen["road"].add(left)
            for right in keys[i+1:]:
                if states[right].x_m-state.x_m > 4.4:
                    break
                pair = tuple(sorted((left, right)))
                if pair not in seen["collision"] and collide(bodies[left], bodies[right]):
                    incidents["collision_events"].append(dict(time_s=state.time_s, actors=list(pair)))
                    seen["collision"].add(pair)


def planned_cases():
    def case(name, kind, lanes, flow, seed, speed=10., gap=30.):
        return dict(name=name, kind=kind, lane_count=lanes, flow_veh_h_lane=flow,
            seed=seed, vehicle_count=4*lanes, target_speed_mps=speed,
            same_lane_gap_m=gap, observation_after_entry_s=200.)
    cases = [case(f"L{lanes}_q{flow}_s{seed}", "lane_flow", lanes, flow, seed)
             for lanes in (2, 3, 4) for flow in (252, 756, 1512) for seed in range(1, 6)]
    cases += [case(f"{name}_s{seed}", "parameter", 3, 756, seed, speed, gap)
              for name, speed, gap in (("speed8", 8., 30.), ("speed12", 12., 30.),
                                       ("gap24", 10., 24.), ("gap36", 10., 36.))
              for seed in range(1, 6)]
    return cases


def run_case(case, root):
    start = time.perf_counter()
    directory = Path(root) / case["name"]
    directory.mkdir()
    clock, origin = make_clock(case)
    inputs = dict(case=case, first_request_absolute_s=origin,
                  physical_parameters=dict(clock.p), policy_parameters=dict(clock.policy),
                  departures=clock._departures)
    write_json(directory / "input.json", inputs)
    incidents = {"collision_events": [], "road_departure_events": []}
    seen = {"collision": set(), "road": set()}
    with gzip.open(directory / "trajectory.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as stream:
        def save(decisions=None, initial_steps=None):
            stream.write(json.dumps(physical_frame(clock, decisions, initial_steps), separators=(",", ":"),
                                    allow_nan=False)+"\n")
        last = None
        while last is None or clock._current_time() < last+case["observation_after_entry_s"]-1e-8:
            if clock._current_time() > 1200:
                raise RuntimeError("入口未在 1200 s 数值预算内完成")
            steps, decisions = clock.tick_compact()
            substep_incidents(steps, case["lane_count"], incidents, seen)
            save(decisions, steps)
            actuals = [row["actual_departure_s"] for row in clock._departures.values()]
            if all(value is not None for value in actuals):
                last = max(actuals)
        save(decisions)
    inputs.update(departures=clock._departures,
                  completed_lane_changes=sum(m.completed_lane_changes for m in clock.memories.values()))
    write_json(directory / "input.json", inputs)
    write_json(directory / "incidents.json", incidents)
    result = evaluate_run(directory)
    result["elapsed_wall_s"] = time.perf_counter()-start
    write_json(directory / "result.json", result)
    write_json(directory / "hashes.json", {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in directory.iterdir() if p.is_file()})
    return result


def run_study(*, workers=6, cases=None, output_base=None):
    cases = planned_cases() if cases is None else cases
    base = ROOT / "results" / "formation_study" if output_base is None else Path(output_base)
    root = base / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root.mkdir(parents=True)
    sources = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for folder in ("noa", "models", "perception", "simulation", "experiments", "configs", "safety")
               for p in (ROOT/folder).glob("*") if p.suffix in (".py", ".json")}
    write_json(root / "protocol.json", dict(schema="formation_study_v1", cases=cases,
        generation="independent per-lane Bernoulli p=q*0.1/3600; shift first request to t=0",
        entry="lane FIFO, inherited standstill gap + time headway",
        position_tolerance_m=2., speed_tolerance_mps=1., confirmation_s=1.,
        formation_deadline_s=None, hold_s=None, road_length_m=10000.,
        source_sha256=sources))
    print(json.dumps({"study_root": str(root), "cases": len(cases)}, ensure_ascii=False), flush=True)
    rows = []
    with ProcessPoolExecutor(max_workers=workers) as pool, (root / "results.jsonl").open("w", encoding="utf-8") as stream:
        futures = {pool.submit(run_case, case, root): case for case in cases}
        for future in as_completed(futures):
            case = futures[future]
            try:
                row = future.result()
            except Exception as error:
                row = {**case, "status": "error", "error": f"{type(error).__name__}: {error}"}
            rows.append(row)
            stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+"\n")
            stream.flush()
            print(json.dumps({"done": len(rows), "case": case["name"], "status": row["status"],
                "formed": row.get("formation_success"), "delay_s": row.get("formation_delay_s")}, ensure_ascii=False), flush=True)
    write_json(root / "summary.json", dict(case_count=len(cases),
        completed=sum(r["status"] == "completed" for r in rows),
        formed=sum(r.get("formation_success") is True for r in rows), results=sorted(rows, key=lambda r: r["name"])))
    return root
