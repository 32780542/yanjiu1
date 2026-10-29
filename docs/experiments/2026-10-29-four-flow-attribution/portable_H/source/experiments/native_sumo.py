"""Real SUMO insertion and motion; pure per-vehicle rules receive local tracks only.

The recorder may see true IDs and the full physical frame. Neither is passed to
``noa.native_rules.decide``. No Python entry gate or externally imposed motion is
used. Every case creates a fresh directory, including unsuccessful cases.
"""

from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
import gzip
import hashlib
from importlib import metadata as import_metadata
import json
import math
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
from uuid import uuid4
import xml.etree.ElementTree as ET

from research.common import ROOT, binary, lock_traci, tool_env

STEP = 0.1
LANE_WIDTH = 3.3
MODES = ("noa", "formation", "transform", "global")
SCENARIOS = ("lane_drop", "straight3")
PHYSICAL = dict(
    length=4.0,
    width=1.8,
    minGap=1.5,
    tau=0.2,
    accel=5.0,
    decel=10.0,
    emergencyDecel=30.0,
    maxSpeed=33.3,
    speedFactor=1.0,
    speedDev=0.0,
    sigma=0.0,
    carFollowModel="IDM",
    emissionClass="HBEFA3/PC_G_EU4",
)


def write_json(path, value):
    Path(path).write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


def _ticks(duration):
    ticks = round(duration / STEP)
    if not math.isfinite(duration) or ticks <= 0 or abs(ticks * STEP - duration) > 1e-8:
        raise ValueError("duration must be a positive multiple of 0.1 seconds")
    return ticks


def arrival_tape(seed=1, flow=1250.0, duration=600.0):
    """Independent per-lane Bernoulli draws, shared unchanged across all modes."""
    ticks = _ticks(duration)
    probability = flow * STEP / 3600
    if not 0 <= probability <= 1:
        raise ValueError("per-lane flow must be in [0, 36000] vehicles/hour")
    streams = [random.Random(f"continuous-arrival:{seed}:{lane}") for lane in range(3)]
    return [
        dict(vehicle_id=f"v{lane}_{tick:05d}", requested_s=tick / 10.0, lane=lane, x=0.0, speed=28.8)
        for tick in range(ticks)
        for lane in range(3)
        if streams[lane].random() < probability
    ]


def initial_tape(initial):
    rows = []
    for index, row in enumerate(initial):
        request = dict(
            vehicle_id=str(row.get("id", row.get("vehicle_id", f"initial_{index}"))),
            requested_s=float(row.get("depart", row.get("requested_s", 0.0))),
            lane=int(row["lane"]),
            x=float(row.get("x", 0.0)),
            speed=float(row.get("speed", 28.8)),
        )
        if (
            request["lane"] not in (0, 1, 2)
            or not 0 <= request["x"] < 1000
            or not 0 <= request["speed"] <= 33.3
            or request["requested_s"] < 0
            or not all(math.isfinite(request[k]) for k in ("x", "speed", "requested_s"))
        ):
            raise ValueError(f"invalid native initial request: {request}")
        rows.append(request)
    if len({r["vehicle_id"] for r in rows}) != len(rows):
        raise ValueError("vehicle IDs must be unique")
    return sorted(rows, key=lambda row: row["requested_s"])


def _write_xml(path, root):
    ET.indent(root, space="  ")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return path


def build_network(directory, scenario="lane_drop"):
    """Generate two real edges, with zero internal length and fixed lane centers."""
    if scenario not in SCENARIOS:
        raise ValueError(f"unknown scenario: {scenario}")
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    nodes, edges, connections = ET.Element("nodes"), ET.Element("edges"), ET.Element("connections")
    for name, x in (("entry", 0), ("bottleneck", 1000), ("exit", 1200)):
        ET.SubElement(nodes, "node", id=name, x=str(x), y="0", type="priority", radius="0")
    retained = 2 if scenario == "lane_drop" else 3
    for name, source, target, count, x0, x1 in (
        ("upstream", "entry", "bottleneck", 3, 0, 1000),
        ("downstream", "bottleneck", "exit", retained, 1000, 1200),
    ):
        edge = ET.SubElement(
            edges,
            "edge",
            id=name,
            attrib={"from": source, "to": target},
            numLanes=str(count),
            speed="33.3",
            width="3.3",
            length=str(x1 - x0),
            spreadType="center",
        )
        for lane in range(count):
            center = LANE_WIDTH * (lane + 0.5)
            ET.SubElement(edge, "lane", index=str(lane), width="3.3", shape=f"{x0},{center} {x1},{center}")
    for lane in range(retained):
        ET.SubElement(
            connections,
            "connection",
            attrib={"from": "upstream", "to": "downstream"},
            fromLane=str(lane),
            toLane=str(lane),
        )
    source_paths = [
        _write_xml(directory / f"native.{suffix}.xml", tree)
        for suffix, tree in (("nod", nodes), ("edg", edges), ("con", connections))
    ]
    net = directory / "native.net.xml"
    command = [
        binary("netconvert"),
        "--node-files",
        str(source_paths[0]),
        "--edge-files",
        str(source_paths[1]),
        "--connection-files",
        str(source_paths[2]),
        "--output-file",
        str(net),
        "--no-internal-links",
        "true",
        "--offset.disable-normalization",
        "true",
        "--junctions.corner-detail",
        "0",
    ]
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=tool_env(),
        timeout=60,
    )
    write_json(
        directory / "netconvert.json",
        dict(
            command=command, returncode=completed.returncode, stdout=completed.stdout, stderr=completed.stderr
        ),
    )
    if completed.returncode:
        raise RuntimeError(f"native netconvert failed: {completed.stderr[-1500:]}")
    return net


def write_routes(directory, requests):
    root = ET.Element("routes")
    ET.SubElement(root, "vType", id="CAV_ICV", **{key: str(value) for key, value in PHYSICAL.items()})
    ET.SubElement(root, "route", id="through", edges="upstream downstream")
    for row in requests:
        ET.SubElement(
            root,
            "vehicle",
            id=row["vehicle_id"],
            type="CAV_ICV",
            route="through",
            depart=str(row["requested_s"]),
            departLane=str(row["lane"]),
            departPos=str(row["x"]),
            departSpeed=str(row["speed"]),
            arrivalPos="max",
        )
    return _write_xml(Path(directory) / "native.rou.xml", root)


@dataclass(frozen=True, slots=True)
class PhysicalState:
    x: float
    y: float
    speed: float
    lane: int
    vy: float = 0.0
    acceleration: float = 0.0
    time: float = 0.0


class LocalTracks:
    """Separate private track dictionaries; true identity remains in this adapter."""

    def __init__(self, vehicle_type=None):
        if vehicle_type is None:
            from noa.native_rules import Vehicle

            vehicle_type = Vehicle
        self.vehicle_type = vehicle_type
        self.tracks = {}
        self.next_tracks = {}

    def observe(self, ego_id, states, ordered=None, xs=None):
        ego = states[ego_id]
        if ordered is None:
            ordered = sorted(states, key=lambda key: (states[key].x, states[key].y, states[key].speed))
            xs = [states[key].x for key in ordered]
        candidates = ordered[bisect_left(xs, ego.x - 100.0) : bisect_right(xs, ego.x + 200.0)]
        private = self.tracks.setdefault(ego_id, {})
        next_track = self.next_tracks.setdefault(ego_id, 1)
        neighbors = []
        for key in candidates:
            if key == ego_id:
                continue
            if key not in private:
                private[key], next_track = next_track, next_track + 1
            state = states[key]
            neighbors.append(
                self.vehicle_type(
                    private[key],
                    state.x,
                    state.y,
                    state.speed,
                    state.lane,
                    state.vy,
                    state.acceleration,
                    state.time,
                )
            )
        self.next_tracks[ego_id] = next_track
        local_ego = self.vehicle_type(
            0, ego.x, ego.y, ego.speed, ego.lane, ego.vy, ego.acceleration, ego.time
        )
        return local_ego, tuple(neighbors)

    def discard(self, ego_id):
        self.tracks.pop(ego_id, None)
        self.next_tracks.pop(ego_id, None)


def lane_request_is_safe(ego, neighbors, target_lane):
    """Common physical 8 m target clearance, followed by native SUMO gap checks."""
    if target_lane not in (0, 1, 2) or abs(target_lane - ego.lane) != 1:
        return False
    target_y = LANE_WIDTH * (target_lane + 0.5)
    for other in neighbors:
        # Includes a vehicle already straddling a lane boundary.
        occupies_target = abs(other.y - target_y) < LANE_WIDTH / 2 + PHYSICAL["width"] / 2
        if occupies_target and abs(other.x - ego.x) < 8.0 - 1e-9:
            return False
    return True


def lane_change_is_complete(state, target_lane):
    """Lane index flips halfway across; completion requires lateral rest at center."""
    return (
        state.lane == target_lane
        and abs(state.vy) < 0.05
        and abs(state.y - (1.65 + LANE_WIDTH * target_lane)) < 0.05
    )


def active_lane_request(state, attempt, now):
    """Release own request on strict completion; retain real motion past expiry."""
    if attempt is None or lane_change_is_complete(state, attempt[0]):
        return None
    moving = (
        abs(state.vy) > 0.05
        or abs(state.y - (state.lane + 0.5) * LANE_WIDTH) > 0.05
    )
    return attempt[0] if now - attempt[1] <= 1.2 or moving else None


def _source_snapshot(directory):
    sources = (
        ROOT / "experiments/native_sumo.py",
        ROOT / "experiments/global_reference.py",
        ROOT / "experiments/complete_layers.py",
        ROOT / "noa/native_rules.py",
        ROOT / "run_native_flow.py",
        ROOT / "research/common.py",
    )
    result = {}
    for path in sources:
        content = path.read_bytes()
        relative = path.relative_to(ROOT)
        destination = directory / "source" / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        result[relative.as_posix()] = hashlib.sha256(content).hexdigest()
    return result


def runtime_metadata():
    """Record the interpreter and optional centralized-reference dependency."""
    try:
        scipy_version = import_metadata.version("scipy")
    except import_metadata.PackageNotFoundError:
        scipy_version = None
    return dict(
        python_version=platform.python_version(),
        python_executable=sys.executable,
        scipy_version=scipy_version,
    )


def gui_view_boundary(front_x):
    """Follow the visible front with 600 m, then retain the drop and exit."""
    center = min(900.0, max(300.0, front_x))
    return center - 300.0, -20.0, center + 300.0, 40.0


def _summary(trips, now, duration, *, collisions=0, teleports=0, error=None):
    requested = [row for row in trips if row["requested_s"] < now + 1e-8]
    departed = [row for row in trips if row["entered_s"] is not None]
    completed = [row for row in trips if row["exited_s"] is not None]
    average = lambda values: sum(values) / len(values) if values else None
    distance = sum(row["distance_m"] for row in completed)
    fuel = sum(row["fuel_mg"] for row in completed)
    all_completed = len(completed) == len(trips)
    safe = not collisions and not teleports and error is None
    status = (
        "error"
        if error is not None
        else "unsafe" if not safe else "drained" if all_completed else "time_limit"
    )
    eligible = safe and all_completed and bool(trips)
    entry_wait = average([row["entered_s"] - row["requested_s"] for row in departed])
    travel = average([row["exited_s"] - row["entered_s"] for row in completed])
    system = average([row["exited_s"] - row["requested_s"] for row in completed])
    fuel_per_km = fuel / distance if distance else None
    return dict(
        status=status,
        all_completed=all_completed,
        safe=safe,
        performance_comparison_eligible=eligible,
        requested=len(trips),
        requested_until_end=len(requested),
        departed=len(departed),
        completed=len(completed),
        pending_final=sum(row["entered_s"] is None for row in requested),
        not_yet_requested_final=len(trips) - len(requested),
        onroad_final=len(departed) - len(completed),
        completion_fraction=len(completed) / len(trips) if trips else None,
        mean_entry_wait_s=entry_wait if eligible else None,
        mean_travel_time_s=travel if eligible else None,
        mean_system_time_s=system if eligible else None,
        completed_subset_mean_travel_time_s=travel,
        completed_subset_mean_system_time_s=system,
        departed_subset_mean_entry_wait_s=entry_wait,
        completed_subset_fuel_g_per_km=fuel_per_km,
        exit_flow_veh_h=(
            sum(row["exited_s"] <= duration for row in completed) * 3600 / duration
            if now >= duration - 1e-8
            else None
        ),
        completed_fuel_mg=fuel,
        all_fuel_mg=sum(row["fuel_mg"] for row in trips),
        fuel_g_per_km=fuel_per_km if eligible else None,
        clearance_after_demand_s=(
            max(0.0, max((row["exited_s"] for row in completed), default=duration) - duration)
            if len(completed) == len(trips)
            else None
        ),
    )


def _read_tripinfo(path, trips):
    """SUMO's emissions device integrates all steps, including final exit steps."""
    if not path.is_file():
        return
    for row in ET.parse(path).getroot().findall("tripinfo"):
        trip = trips.get(row.get("id"))
        if trip is None or float(row.get("depart", "-1")) < 0:
            continue
        trip["entered_s"] = float(row.get("depart"))
        arrival = float(row.get("arrival", "-1"))
        trip["exited_s"] = arrival if arrival >= 0 else None
        trip["distance_m"] = float(row.get("routeLength"))
        trip["onroad_s"] = float(row.get("duration"))
        trip["waiting_s"] = float(row.get("waitingTime"))
        trip["time_loss_s"] = float(row.get("timeLoss"))
        if row.get("speedFactor") is not None:
            trip["speed_factor_tripinfo"] = float(row.get("speedFactor"))
        emissions = row.find("emissions")
        if emissions is not None:
            trip["fuel_mg"] = float(emissions.get("fuel_abs"))


def run_case(
    mode="transform",
    seed=1,
    flow=1250.0,
    duration=600.0,
    scenario="lane_drop",
    output_base=None,
    gui=False,
    initial=None,
    max_time=None,
    diagnostic=False,
    gui_delay_ms=40,
    auto_zoom=True,
    wait_before_close=False,
    input_fn=input,
    output_fn=print,
):
    """Run a paired native request tape. Return the unique evidence directory.

    ``initial`` overrides stochastic demand with native requests of the form
    ``{depart, lane, x, speed, id?}``; it does not place vehicles by force.
    ``max_time`` is absolute simulation time; the default allows 300 s clearance.
    GUI displays this first calculation. Interactive callers may inspect its
    final frame before pressing Enter; final tripinfo is sealed after closing.
    """
    from noa.native_rules import Memory, Vehicle, decide, safe_speed

    if mode not in MODES or scenario not in SCENARIOS:
        raise ValueError("unknown mode or scenario")
    _ticks(duration)
    max_time = duration + 300.0 if max_time is None else float(max_time)
    _ticks(max_time)
    if type(gui_delay_ms) is not int or gui_delay_ms < 0:
        raise ValueError("gui_delay_ms must be a non-negative integer")
    requests = arrival_tape(seed, flow, duration) if initial is None else initial_tape(initial)
    base = Path(output_base) if output_base is not None else ROOT / "results/native_flow"
    name = (
        datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + f"_{scenario}_{mode}_s{seed}_{uuid4().hex[:6]}"
    )
    directory = base.resolve() / name
    directory.mkdir(parents=True, exist_ok=False)
    source_sha = _source_snapshot(directory)
    started = time.perf_counter()
    config = dict(
        mode=mode,
        seed=seed,
        flow_veh_h_lane=flow,
        demand_duration_s=duration,
        scenario=scenario,
        max_time_s=max_time,
        step_s=STEP,
        lane_change_duration_s=1.0,
        gui=gui,
        diagnostic=diagnostic,
        gui_delay_ms=gui_delay_ms if gui else None,
        gui_auto_zoom=auto_zoom if gui else None,
        gui_wait_before_close=bool(gui and wait_before_close),
        runtime=runtime_metadata(),
        observation_scope=(
            "privileged full physical state"
            if mode == "global"
            else "private local tracks: 200m ahead, 100m behind"
        ),
        reference_is_full_paper_reproduction=False if mode == "global" else None,
        reference_description=(
            "Cai-style centralized assignment reference; not a full Cai2024 reproduction"
            if mode == "global"
            else None
        ),
    )
    trips = {
        row["vehicle_id"]: dict(
            **row,
            entered_s=None,
            exited_s=None,
            distance_m=0.0,
            onroad_s=0.0,
            fuel_mg=0.0,
            lane_changes=0,
            lane_events=[],
            lane_completion_events=[],
            speed_factor=None,
            speed_factor_tripinfo=None,
        )
        for row in requests
    }
    write_json(
        directory / "input.json",
        dict(
            case=config,
            arrivals=requests,
            physical=PHYSICAL,
            speed_mode=31,
            lane_change_mode=512,
            source_sha256=source_sha,
            positions_step_s=STEP,
            insertion="SUMO native route departures; no Python entry gate",
            positions_schema="time_s, states[id]=[x,y,speed,acceleration]",
            longitudinal_coordinate="SUMO lane position + upstream edge offset; vehicle front",
            lateral_coordinate="1.65 + 3.3*lane + measured lane offset",
        ),
    )
    write_json(directory / "result.json", dict(status="starting", **config, source_sha256=source_sha))
    conn = None
    now, states, memories = 0.0, {}, {}
    reasons, execution, lane_transitions = Counter(), Counter(), Counter()
    collision_events, teleports, error = [], [], None
    version = "unavailable"
    gui_views, gui_front_x = (), 0.0
    lane_attempts, lane_motions, previous_lanes = {}, {}, {}
    ending_lane_seen = set()
    local = LocalTracks()
    try:
        planner = None
        if mode == "global":
            from experiments.global_reference import GlobalPlanner

            planner = GlobalPlanner()
        net = build_network(directory, scenario)
        routes = write_routes(directory, requests)
        traci = lock_traci()
        tc = traci.constants
        variables = (
            tc.VAR_LANEPOSITION,
            tc.VAR_LANEPOSITION_LAT,
            tc.VAR_SPEED,
            tc.VAR_SPEED_LAT,
            tc.VAR_ACCELERATION,
            tc.VAR_LANE_INDEX,
            tc.VAR_ROAD_ID,
            tc.VAR_FUELCONSUMPTION,
            tc.VAR_DISTANCE,
        )
        command = [
            binary("sumo-gui" if gui else "sumo"),
            "--net-file",
            str(net),
            "--route-files",
            str(routes),
            "--step-length",
            ".1",
            "--lanechange.duration",
            "1",
            "--time-to-teleport",
            "-1",
            "--collision.action",
            "warn",
            "--collision.mingap-factor",
            "0",
            "--collision.check-junctions",
            "true",
            "--no-step-log",
            "true",
            "--duration-log.disable",
            "true",
            "--seed",
            str(seed),
            "--route-steps",
            "0",
            "--tripinfo-output",
            str(directory / "sumo_tripinfo.xml"),
            "--tripinfo-output.write-unfinished",
            "true",
            "--device.emissions.probability",
            "1",
            "--error-log",
            str(directory / "sumo_warnings.log"),
        ]
        if gui:
            command += ["--start", "true", "--quit-on-end", "true", "--delay", str(gui_delay_ms)]
        write_json(directory / "sumo_command.json", command)
        with (
            (directory / "sumo_stdout.log").open("w", encoding="utf-8") as stdout,
            gzip.open(directory / "positions.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as positions,
            gzip.open(directory / "events.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as events,
        ):
            diagnostic_stream = (
                gzip.open(directory / "diagnostic.jsonl.gz", "wt", encoding="utf-8", compresslevel=3)
                if diagnostic
                else None
            )
            try:
                label = "native_" + uuid4().hex
                traci.start(command, label=label, stdout=stdout, doSwitch=False)
                conn = traci.getConnection(label)
                version = conn.getVersion()[1]
                if gui and auto_zoom:
                    gui_views = tuple(conn.gui.getIDList())
                    for view in gui_views:
                        conn.gui.setBoundary(view, *gui_view_boundary(0.0))
                for tick in range(1, round(max_time / STEP) + 1):
                    conn.simulationStep()
                    now = conn.simulation.getTime()
                    if gui and gui_delay_ms:
                        # TraCI-driven steps bypass SUMO's normal GUI delay.
                        # Pace only this live view; simulation time stays 0.1 s.
                        time.sleep(gui_delay_ms / 1000.0)
                    departed = tuple(conn.simulation.getDepartedIDList())
                    arrived = tuple(conn.simulation.getArrivedIDList())
                    for key in departed:
                        conn.vehicle.setSpeedMode(key, 31)
                        conn.vehicle.setLaneChangeMode(key, 512)
                        conn.vehicle.subscribe(key, variables)
                        trips[key]["entered_s"] = conn.vehicle.getDeparture(key)
                        trips[key]["speed_factor"] = conn.vehicle.getSpeedFactor(key)
                        memories[key] = Memory()
                        events.write(
                            json.dumps(
                                dict(
                                    time_s=now,
                                    kind="departed",
                                    vehicle_id=key,
                                    requested_s=trips[key]["requested_s"],
                                    entered_s=trips[key]["entered_s"],
                                )
                            )
                            + "\n"
                        )
                    for key in arrived:
                        trips[key]["exited_s"] = now
                        memories.pop(key, None)
                        local.discard(key)
                        lane_attempts.pop(key, None)
                        lane_motions.pop(key, None)
                        previous_lanes.pop(key, None)
                        events.write(json.dumps(dict(time_s=now, kind="arrived", vehicle_id=key)) + "\n")
                    states = {}
                    for key, data in conn.vehicle.getAllSubscriptionResults().items():
                        if key in arrived:
                            continue
                        lane = int(data[tc.VAR_LANE_INDEX])
                        x = data[tc.VAR_LANEPOSITION] + (
                            1000.0 if data[tc.VAR_ROAD_ID] == "downstream" else 0.0
                        )
                        states[key] = PhysicalState(
                            x,
                            1.65 + LANE_WIDTH * lane + data[tc.VAR_LANEPOSITION_LAT],
                            data[tc.VAR_SPEED],
                            lane,
                            data[tc.VAR_SPEED_LAT],
                            data[tc.VAR_ACCELERATION],
                            now,
                        )
                        if scenario == "lane_drop" and lane == 2:
                            ending_lane_seen.add(key)
                        motion = lane_motions.get(key)
                        if motion is not None and lane_change_is_complete(states[key], motion[0]):
                            complete = dict(
                                time_s=now,
                                x=x,
                                y=states[key].y,
                                vy=states[key].vy,
                                from_lane=motion[1],
                                to_lane=motion[0],
                                requested_s=motion[2],
                            )
                            trips[key]["lane_completion_events"].append(complete)
                            events.write(
                                json.dumps(dict(kind="lane_completion", vehicle_id=key, **complete)) + "\n"
                            )
                            lane_motions.pop(key)
                        trips[key]["distance_m"] = data[tc.VAR_DISTANCE]
                        trips[key]["onroad_s"] = now - trips[key]["entered_s"]
                        trips[key]["fuel_mg"] += max(0.0, data[tc.VAR_FUELCONSUMPTION]) * STEP
                        if key in previous_lanes and lane != previous_lanes[key]:
                            old = previous_lanes[key]
                            trips[key]["lane_changes"] += 1
                            transition = dict(time_s=now, x=x, from_lane=old, to_lane=lane)
                            trips[key]["lane_events"].append(transition)
                            lane_transitions[f"{old}->{lane}"] += 1
                            events.write(
                                json.dumps(dict(kind="lane_change", vehicle_id=key, **transition)) + "\n"
                            )
                        previous_lanes[key] = lane
                    if gui_views and states:
                        gui_front_x = max(gui_front_x, max(state.x for state in states.values()))
                        if tick % 10 == 0:
                            for view in gui_views:
                                conn.gui.setBoundary(view, *gui_view_boundary(gui_front_x))
                    for collision in conn.simulation.getCollisions():
                        record = dict(
                            time_s=now,
                            collider=collision.collider,
                            victim=collision.victim,
                            collider_speed=collision.colliderSpeed,
                            victim_speed=collision.victimSpeed,
                            type=collision.type,
                            lane=collision.lane,
                            position=collision.pos,
                        )
                        collision_events.append(record)
                        events.write(json.dumps(dict(kind="collision", **record)) + "\n")
                    for key in conn.simulation.getStartingTeleportIDList():
                        record = dict(time_s=now, vehicle_id=key)
                        teleports.append(record)
                        events.write(json.dumps(dict(kind="teleport", **record)) + "\n")
                    if collision_events or teleports:
                        # Retain the first unsafe physical frame even between
                        # regular 1 s samples, then stop before further control.
                        positions.write(
                            json.dumps(
                                dict(
                                    time_s=now,
                                    states={
                                        key: [s.x, s.y, s.speed, s.acceleration] for key, s in states.items()
                                    },
                                    unsafe=True,
                                ),
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                        if diagnostic_stream is not None:
                            diagnostic_stream.write(
                                json.dumps(
                                    dict(
                                        time_s=now,
                                        states={key: asdict(s) for key, s in states.items()},
                                        actions={},
                                        unsafe=True,
                                    ),
                                    separators=(",", ":"),
                                )
                                + "\n"
                            )
                        break
                    ordered = sorted(
                        states, key=lambda key: (states[key].x, states[key].y, states[key].speed)
                    )
                    xs = [states[key].x for key in ordered]
                    actions = {}
                    global_states, global_commands = {}, {}
                    if planner is not None:
                        global_states = {
                            key: Vehicle(
                                index,
                                state.x,
                                state.y,
                                state.speed,
                                state.lane,
                                state.vy,
                                state.acceleration,
                                state.time,
                            )
                            for index, (key, state) in enumerate(states.items())
                        }
                        global_commands = planner.commands(
                            global_states, now, 1000.0 if scenario == "lane_drop" else None
                        )
                    for key in ordered:
                        # This view is used by the common execution guard in all
                        # modes. Only distributed strategies receive it as input.
                        physical = states[key]
                        pending = active_lane_request(physical, lane_attempts.get(key), now)
                        if pending is None:
                            lane_attempts.pop(key, None)
                        ego, neighbors = local.observe(key, states, ordered, xs)
                        # Only ego receives its own submitted request feedback.
                        ego = replace(ego, pending_lane=pending)
                        if planner is not None:
                            command = global_commands[key]
                        else:
                            command, memories[key] = decide(
                                ego,
                                neighbors,
                                memories[key],
                                mode=mode,
                                drop_x=1000.0 if scenario == "lane_drop" else None,
                            )
                        if not math.isfinite(command.speed):
                            raise ValueError("non-finite controller speed")
                        safety_cap = safe_speed(ego, neighbors)
                        if not math.isfinite(safety_cap):
                            raise ValueError("non-finite common safe speed")
                        executed_speed = min(33.3, max(0.0, min(command.speed, safety_cap)))
                        conn.vehicle.setSpeed(key, executed_speed)
                        if command.speed > safety_cap + 1e-9:
                            execution["safe_speed_limited_ticks"] += 1
                        reasons[command.reason or "unspecified"] += 1
                        requested_lane, accepted = command.lane, False
                        if requested_lane is not None and requested_lane != ego.lane:
                            execution["lane_requested_ticks"] += 1
                            if key in lane_attempts or abs(physical.vy) > 0.05:
                                execution["lane_motion_in_progress"] += 1
                            elif requested_lane >= (
                                2 if scenario == "lane_drop" and ego.x >= 1000 else 3
                            ) or not lane_request_is_safe(ego, neighbors, requested_lane):
                                execution["local_lane_guard_rejected"] += 1
                            else:
                                conn.vehicle.changeLane(key, requested_lane, 1.0)
                                lane_attempts[key] = (requested_lane, now)
                                lane_motions[key] = (requested_lane, ego.lane, now)
                                execution["native_lane_requests"] += 1
                                accepted = True
                        if diagnostic:
                            actions[key] = dict(
                                speed=executed_speed,
                                requested_speed=command.speed,
                                pending_lane=ego.pending_lane,
                                safe_speed_cap_mps=safety_cap,
                                lane=requested_lane,
                                accepted=accepted,
                                reason=command.reason,
                                target_x=command.target_x,
                                reference=command.reference,
                            )
                    positions.write(
                        json.dumps(
                            dict(
                                time_s=now,
                                states={
                                    key: [s.x, s.y, s.speed, s.acceleration] for key, s in states.items()
                                },
                            ),
                            separators=(",", ":"),
                        )
                        + "\n"
                    )
                    if diagnostic_stream is not None:
                        diagnostic_stream.write(
                            json.dumps(
                                dict(
                                    time_s=now,
                                    states={key: asdict(s) for key, s in states.items()},
                                    actions=actions,
                                ),
                                separators=(",", ":"),
                            )
                            + "\n"
                        )
                    if tick % 1000 == 0:
                        positions.flush()
                        events.flush()
                        print(
                            json.dumps(
                                dict(
                                    run_dir=str(directory),
                                    simulation_s=now,
                                    active=len(states),
                                    departed=sum(t["entered_s"] is not None for t in trips.values()),
                                    completed=sum(t["exited_s"] is not None for t in trips.values()),
                                )
                            ),
                            flush=True,
                        )
                    if now >= duration - 1e-8 and conn.simulation.getMinExpectedNumber() == 0:
                        break
            finally:
                if diagnostic_stream is not None:
                    diagnostic_stream.close()
        if gui and wait_before_close and sys.stdin.isatty():
            output_fn(f"仿真已停止在 {now:.1f}s；可在 SUMO 窗口缩放检查最后画面。")
            output_fn(f"逐步记录已保存到 {directory}；关闭后封存最终行程指标。")
            try:
                input_fn("检查完毕后按 Enter 关闭 SUMO 并封存结果...")
            except (EOFError, KeyboardInterrupt):
                pass
    except BaseException as exc:
        error = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        primary_failure = error is not None
        cleanup_error = tripinfo_error = None
        finalization_exception = None
        try:
            if conn is not None:
                conn.close()
        except Exception as exc:
            cleanup_error = f"{type(exc).__name__}: {exc}"
            error = error or cleanup_error
            finalization_exception = exc
        try:
            _read_tripinfo(directory / "sumo_tripinfo.xml", trips)
        except (ET.ParseError, OSError, ValueError) as exc:
            tripinfo_error = f"{type(exc).__name__}: {exc}"
            error = error or tripinfo_error
            finalization_exception = finalization_exception or exc
        trip_rows = list(trips.values())
        lane_completions = [
            dict(vehicle_id=row["vehicle_id"], **event)
            for row in trip_rows
            for event in row["lane_completion_events"]
        ]
        ending_completed = {
            event["vehicle_id"]
            for event in lane_completions
            if event["from_lane"] == 2 and event["to_lane"] == 1 and event["x"] < 1000.0
        }
        write_json(directory / "trips.json", trip_rows)
        with gzip.open(directory / "trips.jsonl.gz", "wt", encoding="utf-8", compresslevel=3) as stream:
            for trip in trip_rows:
                stream.write(json.dumps(trip, separators=(",", ":")) + "\n")
        result = dict(
            error=error,
            cleanup_error=cleanup_error,
            tripinfo_error=tripinfo_error,
            **config,
            actual_end_s=now,
            wall_time_s=round(time.perf_counter() - started, 3),
            **_summary(
                trip_rows,
                now,
                duration,
                collisions=len(collision_events),
                teleports=len(teleports),
                error=error,
            ),
            collisions=len(collision_events),
            collision_events=collision_events,
            teleports=len(teleports),
            teleport_events=teleports,
            lane_changes=sum(row["lane_changes"] for row in trip_rows),
            lane_transitions=dict(lane_transitions),
            lane_index_events_are_lateral_midpoints=True,
            lane_change_completions=len(lane_completions),
            lane_completion_events=lane_completions,
            ending_lane_observed_vehicles=len(ending_lane_seen),
            ending_lane_completed_before_drop=len(ending_completed & ending_lane_seen),
            ending_lane_completion_before_drop_rate=(
                len(ending_completed & ending_lane_seen) / len(ending_lane_seen) if ending_lane_seen else None
            ),
            action_reasons=dict(reasons),
            execution=dict(execution),
            sumo_version=version,
            source_sha256=source_sha,
            fuel_source=(
                "SUMO emissions-device fuel_abs, mg"
                if (directory / "sumo_tripinfo.xml").is_file() and tripinfo_error is None
                else "TraCI last-step sample integral, mg; output interrupted"
            ),
            last_states={key: asdict(state) for key, state in states.items()},
        )
        write_json(directory / "result.json", result)
        if finalization_exception is not None and not primary_failure:
            raise finalization_exception
    return directory
