"""每车独立的跟驰、形成与车道减少规则；输入仅为本车及可见邻车。"""

from dataclasses import dataclass, replace
from math import sqrt


CRUISE, MAX_SPEED, GAP = 28.8, 33.3, 30.0
POSITION_GAIN = 0.3
SPEED_RELAXATION = 0.2  # 0.1 s step / 0.5 s following response
WIDTH, LANE_WIDTH, CLEARANCE = 1.8, 3.3, 8.0
LENGTH, STANDSTILL, BRAKING, RESPONSE = 4.0, 1.5, 10.0, 0.2


@dataclass(frozen=True, slots=True)
class Vehicle:
    track: int
    x: float
    y: float
    speed: float
    lane: int
    vy: float = 0.0
    acceleration: float = 0.0
    time: float = 0.0
    pending_lane: int | None = None


@dataclass(frozen=True, slots=True)
class Command:
    speed: float
    lane: int | None = None
    reason: str = ""
    target_x: float | None = None
    reference: int | None = None


@dataclass(frozen=True, slots=True)
class Memory:
    lane_target: int | None = None
    gap: tuple[int | None, int | None] | None = None
    joining: bool = False


def _occupies(car, lane, horizon=1.0):
    center = (lane + 0.5) * LANE_WIDTH
    end_y = car.y + horizon * car.vy
    return (
        min(car.y, end_y) - WIDTH / 2 < center + LANE_WIDTH / 2
        and max(car.y, end_y) + WIDTH / 2 > center - LANE_WIDTH / 2
    )


def _clear(ego, rows, lane):
    """当前及1s外推的目标走廊满足MATLAB的8m车头位置差。"""
    for other in rows:
        if other.track == ego.track or not _occupies(other, lane):
            continue
        gap = other.x - ego.x
        predicted = gap + other.speed - ego.speed
        if gap * predicted <= 0 or min(abs(gap), abs(predicted)) < CLEARANCE:
            return False
    return True


def _request(ego, target, reference_speed):
    desired = reference_speed + POSITION_GAIN * (target - ego.x)
    return max(0.0, min(MAX_SPEED, ego.speed + SPEED_RELAXATION * (desired - ego.speed)))


def _phase(lane, lanes):
    return GAP / 2 if (lanes - 1 - min(lane, lanes - 1)) % 2 else 0.0


def _physical_phase(car, lanes):
    lateral = max(0.0, min(lanes - 1, car.y / LANE_WIDTH - 0.5))
    lower = int(lateral)
    upper = min(lower + 1, lanes - 1)
    return _phase(lower, lanes) + (lateral - lower) * (_phase(upper, lanes) - _phase(lower, lanes))


def _component(ego, rows):
    """纵向相邻不超过50m的可见车群；其余车辆仍参与安全判断。"""
    cars = sorted((ego, *rows), key=lambda c: (c.x, c.lane, c.y))
    index = next(i for i, c in enumerate(cars) if c.track == ego.track)
    low = high = index
    while low and cars[low].x - cars[low - 1].x <= 50.0:
        low -= 1
    while high + 1 < len(cars) and cars[high + 1].x - cars[high].x <= 50.0:
        high += 1
    return tuple(cars[low : high + 1])


def _following(ego, rows, lanes):
    """跟车仅沿真实前车链；跨道相位仅由互选的实际局部队首分担。"""
    fronts = [c for c in rows if 0.0 < c.x - ego.x <= 50.0 and _occupies(c, ego.lane, 0.0)]
    front = min(fronts, key=lambda c: (c.x, c.y, c.speed), default=None)
    if front is not None:
        target = front.x - GAP
        return _request(ego, target, front.speed), target, front.track
    cars = (ego, *rows)

    def is_head(car):
        return not any(
            0.0 < other.x - car.x <= 50.0 and _occupies(other, car.lane, 0.0) for other in cars
        )

    def nearest(car, lane):
        q = car.x + _physical_phase(car, lanes)
        candidates = [c for c in cars if c.lane == lane and abs(c.x - car.x) <= 50.0 and is_head(c)]

        def order(c):
            difference = c.x + _physical_phase(c, lanes) - q
            return abs(difference), difference, c.x, c.y, c.speed, c.vy

        return min(candidates, key=order, default=None)

    error = 0.0
    for lane in (ego.lane - 1, ego.lane + 1):
        if 0 <= lane < lanes:
            peer = nearest(ego, lane)
            if peer is not None and nearest(peer, ego.lane) is ego:
                error += peer.x + _physical_phase(peer, lanes) - ego.x - _physical_phase(ego, lanes)
    error /= max(1, lanes - 1)
    phase_speed = max(-2.0, min(2.0, POSITION_GAIN * error))
    target = ego.x + phase_speed / POSITION_GAIN
    return _request(ego, target, CRUISE), target, None


def _merge_target(ego, rows, lane, held=None):
    """跟踪本车旁边的真实空隙；可用性由共同物理走廊判断。"""
    ordered = sorted(
        (c for c in rows if _occupies(c, lane)), key=lambda c: (c.x, c.y, c.speed, c.vy)
    )
    if not ordered:
        return ego.x, CRUISE, (None, None)
    by_track = {c.track: c for c in ordered}
    if held and all(key is None or key in by_track for key in held):
        front, rear = (by_track.get(key) for key in held)
        low, high = (rear.x if rear else -float("inf")), (front.x if front else float("inf"))
        if not low <= ego.x <= high or any(
            low < c.x < high for c in ordered if c.track not in held
        ):
            held = None
    else:
        held = None
    if held is None:
        front = min((c for c in ordered if c.x > ego.x), key=lambda c: c.x, default=None)
        rear = max((c for c in ordered if c.x <= ego.x), key=lambda c: c.x, default=None)
    gap = (front.track if front else None, rear.track if rear else None)
    if front is not None and rear is not None:
        return (front.x + rear.x) / 2, (front.speed + rear.speed) / 2, gap
    distance = max(15.0, LENGTH + STANDSTILL + RESPONSE * ego.speed)
    reference = front if front is not None else rear
    target = reference.x - distance if front is not None else reference.x + distance
    if front is None and ego.x >= target:
        return ego.x, CRUISE, gap
    return target, reference.speed, gap


def _join_speed(ego, rows, memory, lane):
    target, speed, gap = _merge_target(ego, rows, lane, memory.gap)
    return _request(ego, target, speed), target, replace(memory, gap=gap)


def _make_room(ego, rows):
    """只用当前终止车道前车及其90m窗口选择一个实际可行的中道车。"""
    all_rows = (ego, *rows)
    ending = [c for c in all_rows if c.lane == 2 and abs(c.x - ego.x) <= 90.0]
    if not ending:
        return None, None
    head = max(ending, key=lambda c: c.x)
    anchor = max(
        (c for c in all_rows if c.lane >= 1 and abs(c.x - head.x) <= 90.0),
        key=lambda c: (c.x, c.lane),
    )
    window = [c for c in all_rows if anchor.x - 60.0 <= c.x <= anchor.x + 30.0]
    counts = [sum(c.lane == lane for c in window) for lane in range(3)]
    if counts[1] + counts[2] - counts[0] < 2:
        return head, None
    options = [
        c
        for c in window
        if c.lane == 1 and c.track != anchor.track and anchor.x - 30.0 <= c.x <= anchor.x + 15.0
    ]
    helper = max(options, key=lambda c: c.x) if options else None
    return head, helper


def _fill(ego, rows, lanes):
    """将局部未成层的余车补入前方空位；已经完整的层不被拆散。"""
    component = _component(ego, rows)
    cars = tuple(c for c in component if abs(c.x - ego.x) <= 90.0)
    if len(cars) < lanes:
        return None
    members = tuple(c for c in cars if c.lane < lanes)

    def phase(lane):
        return 15.0 if (lanes - 1 - lane) % 2 else 0.0

    anchor = max(
        (c for c in component if c.lane < lanes), key=lambda c: (c.x + phase(c.lane), c.lane, c.x)
    )
    base = anchor.x + phase(anchor.lane)
    near = base - round((base - ego.x - phase(ego.lane)) / GAP) * GAP
    centers = [near + k * GAP for k in range(-3, 4)]

    def matches(center, lane):
        return [c for c in cars if c.lane == lane and abs(c.x - (center - phase(lane))) <= 2.0]

    full = [
        center
        for center in centers
        if all(len(matches(center, lane)) == 1 for lane in range(lanes))
    ]
    candidates = [
        c
        for c in members
        if c.track != anchor.track
        and abs(c.vy) < 0.1
        and not any(abs(c.x - (center - phase(c.lane))) <= 2.0 for center in full)
    ]
    choices = []
    for center in centers:
        window = [c for c in component if c.lane < lanes and center - 60.0 <= c.x <= center + 30.0]
        counts = [sum(c.lane == lane for c in window) for lane in range(lanes)]
        if not any(matches(center, lane) for lane in range(lanes)):
            continue
        for lane in range(lanes):
            target = center - phase(lane)
            if any(_occupies(c, lane) and abs(c.x - target) < CLEARANCE for c in cars):
                continue
            for car in candidates:
                if car not in window:
                    continue
                boundary = min(car.lane, lane)
                imbalance = sum(counts[: boundary + 1]) - (boundary + 1) * len(window) / lanes
                after = imbalance + (1 if lane <= boundary else -1)
                balances = abs(after) < abs(imbalance) - 1e-9
                references = [
                    c
                    for c in members
                    if c.track != car.track and abs(c.x - (center - phase(c.lane))) <= 2.0
                ]
                if (
                    abs(car.lane - lane) == 1
                    and balances
                    and abs(car.x - target) <= GAP
                    and references
                    and _clear(car, cars, lane)
                ):
                    reference = max(references, key=lambda c: (c.lane, c.x))
                    target = reference.x + phase(reference.lane) - phase(lane)
                    score = (-center, abs(target - car.x), -car.x, -car.lane, -lane)
                    choices.append((score, car, lane))
    if not choices:
        return None
    _, car, lane = min(choices, key=lambda item: item[0])
    return lane if car.track == ego.track else None


def _receiving_distance(ego, incoming):
    return max(
        CLEARANCE,
        LENGTH
        + STANDSTILL
        + RESPONSE * ego.speed
        + max(ego.speed**2 - incoming.speed**2, 0.0) / (2 * BRAKING),
    )


def _receiving(ego, rows, helper):
    front = min((c.x for c in rows if c.lane == ego.lane and c.x > ego.x), default=float("inf"))
    candidates = [c for c in rows if c.lane == 2 and ego.lane == 1 and ego.x <= c.x < front]
    if ego.lane == 0 and helper is not None and ego.x <= helper.x < front:
        candidates.append(helper)
    if not candidates:
        return None
    reference = max(candidates, key=lambda c: c.x)
    return reference


def _mandatory_priority(ego, rows, lane, drop_x):
    """必要合流车与本车即将占用同一走廊时，自由补位让行。"""
    if drop_x is None or ego.lane != 0 or lane != 1:
        return False
    for car in rows:
        if car.lane == 2 and drop_x - 360.0 <= car.x <= drop_x:
            gap = car.x - ego.x
            predicted = gap + car.speed - ego.speed
            if gap * predicted <= 0 or min(abs(gap), abs(predicted)) < CLEARANCE:
                return True
    return False


def _decide(ego, neighbors, memory, mode, drop_x=1000.0):
    """所有分支只输出本车动作，横移前后沿用目标车道实际跟驰。"""
    if mode not in ("noa", "formation", "transform", "cooperative"):
        raise ValueError("Unknown driving mode: " + mode)
    if mode == "cooperative" and drop_x is None:
        return _decide(ego, neighbors, memory, "noa", drop_x)
    rows = tuple(c for c in neighbors if -100.0 <= c.x - ego.x <= 200.0)
    preparing = drop_x is not None and ego.x >= drop_x - 360.0 and (ego.x < drop_x or ego.lane == 2)
    lanes = 2 if drop_x is not None and ego.x >= drop_x else 3
    organized = mode != "noa"
    forming = mode != "cooperative"
    future_lanes = 2 if preparing and mode in ("transform", "cooperative") else lanes
    moving = abs(ego.vy) > 0.1 or abs(ego.y - (ego.lane + 0.5) * LANE_WIDTH) > 0.15
    # Own submitted actuation can precede measured lateral motion by one frame.
    if ego.pending_lane is not None and memory.lane_target != ego.pending_lane:
        memory = replace(memory, lane_target=ego.pending_lane, gap=None)
    if (
        ego.pending_lane is None
        and not moving
        and memory.lane_target is not None
        and abs(memory.lane_target - ego.lane) > 1
    ):
        memory = Memory()
    if (
        not moving
        and ego.pending_lane is None
        and (
            (preparing and memory.lane_target == 2)
            or _mandatory_priority(ego, rows, memory.lane_target, drop_x)
        )
    ):
        memory = Memory()
    if memory.lane_target is not None:
        target_center = (memory.lane_target + 0.5) * LANE_WIDTH
        arrived = (
            ego.pending_lane is None and abs(ego.y - target_center) <= 0.15 and abs(ego.vy) <= 0.1
        )
        if arrived or (not moving and not organized and ego.pending_lane is None):
            memory = replace(memory, lane_target=None, gap=None)
        else:
            speed, target, memory = (
                _join_speed(ego, rows, memory, memory.lane_target)
                if organized
                else (CRUISE, None, memory)
            )
            if moving or _clear(ego, rows, memory.lane_target):
                return Command(speed, memory.lane_target, "executing", target), memory
            return Command(speed, None, "approach_join", target), memory
    following_lanes = lanes if ego.lane == 2 else future_lanes
    speed, target, reference = (
        _following(ego, rows, following_lanes) if organized and forming else (CRUISE, None, None)
    )
    if memory.joining and (
        not organized
        or (target is None or abs(target - ego.x) <= 2.0)
        and abs(speed - ego.speed) <= 0.5
    ):
        memory = replace(memory, joining=False)

    if preparing and mode in ("transform", "cooperative"):
        head, helper = _make_room(ego, rows)
        if helper is not None and helper.track == ego.track:
            memory = Memory(lane_target=0, joining=True)
            speed, target, memory = _join_speed(ego, rows, memory, 0)
            lane = 0 if _clear(ego, rows, 0) else None
            return (
                Command(speed, lane, "make_room" if lane is not None else "prepare_room", target),
                memory,
            )
        receiving = _receiving(ego, rows, helper)
        if receiving is not None:
            target = receiving.x - _receiving_distance(ego, receiving)
            speed = min(speed, _request(ego, target, receiving.speed))
            return Command(speed, None, "open_gap", target, receiving.track), memory
        if (
            ego.lane == 2
            and head is not None
            and head.track != ego.track
            and not _clear(ego, rows, 1)
        ):
            return Command(speed, None, "ending_follower", target, reference), memory

    if preparing and ego.lane == 2:
        target, gap_speed, gap = _merge_target(ego, rows, 1, memory.gap)
        memory = replace(memory, gap=gap)
        speed = _request(ego, target, gap_speed)
        if _clear(ego, rows, 1):
            return Command(speed, 1, "merge", target), replace(
                memory, lane_target=1, joining=organized
            )
        return Command(speed, None, "approach_gap", target), memory

    if organized and forming and not memory.joining:
        lane = _fill(ego, rows, 2 if preparing else lanes)
        if lane is not None:
            if not _mandatory_priority(ego, rows, lane, drop_x):
                memory = Memory(lane_target=lane, joining=True)
                speed, target, memory = _join_speed(ego, rows, memory, lane)
                return Command(speed, lane, "fill_layer", target), memory

    if mode in ("noa", "cooperative"):
        front = min(
            (c for c in rows if c.lane == ego.lane and c.x > ego.x), key=lambda c: c.x, default=None
        )
        if front is not None and ego.speed < CRUISE - 2 and front.speed < CRUISE - 2:
            options = [
                lane
                for lane in (ego.lane - 1, ego.lane + 1)
                if 0 <= lane < lanes
                and not (preparing and lane == 2)
                and not _mandatory_priority(ego, rows, lane, drop_x)
                and _clear(ego, rows, lane)
            ]

            def free_distance(lane):
                return min(
                    (c.x - ego.x for c in rows if c.lane == lane and c.x > ego.x), default=200.0
                )

            if options:
                lane = max(options, key=free_distance)
                if free_distance(lane) > front.x - ego.x + 15.0:
                    return Command(speed, lane, "normal_overtake"), Memory(lane_target=lane)
    reason = (
        "cooperative_follow" if mode == "cooperative"
        else "join_follow" if memory.joining else "formation_follow" if organized else "normal_follow"
    )
    return Command(speed, None, reason, target, reference), memory


def safe_speed(ego, neighbors):
    """按前车继续制动后的停止位置，保留0.2s响应和车身净距。"""
    limit = MAX_SPEED
    response_speed = BRAKING * RESPONSE
    for front in neighbors:
        shared = any(_occupies(ego, lane) and _occupies(front, lane) for lane in range(3))
        if 0.0 < front.x - ego.x <= 200.0 and shared:
            free = max(0.0, front.x - ego.x - LENGTH - STANDSTILL)
            stopping = (
                sqrt(response_speed**2 + front.speed**2 + 2 * BRAKING * free) - response_speed
            )
            limit = min(limit, stopping)
    return limit


def decide(ego, neighbors, memory, mode, drop_x=1000.0):
    command, memory = _decide(ego, neighbors, memory, mode, drop_x)
    return replace(command, speed=min(command.speed, safe_speed(ego, neighbors))), memory
