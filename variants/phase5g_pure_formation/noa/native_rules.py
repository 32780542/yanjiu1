"""单车根据局部观测计算跟驰速度和相邻车道换道请求。"""
from dataclasses import dataclass, replace
from math import sqrt

CRUISE, MAX_SPEED = 28.8, 33.3
POSITION_GAIN, SPEED_RELAXATION = .3, .2
WIDTH, LANE_WIDTH, CLEARANCE = 1.8, 3.3, 8.
LENGTH, STANDSTILL, BRAKING, RESPONSE = 4., 1.5, 10., .2
HEADWAY = .85
ROAD_PREVIEW = 200.
CONTROL_STEP, SHAPE_FREQUENCY, SHAPE_ACCEL_LIMIT = .1, 2., 5.
FRONT_VIEW, REAR_VIEW, GROUP_GAP = 200., 100., 50.
LANE_CHANGE_TIME = 1.0


@dataclass(frozen=True, slots=True)
class Vehicle:
    track: int
    x: float
    y: float
    speed: float
    lane: int
    vy: float = 0.
    acceleration: float = 0.
    time: float = 0.
    pending_lane: int | None = None


@dataclass(frozen=True, slots=True)
class Command:
    speed: float
    lane: int | None = None
    reason: str = ''
    target_x: float | None = None
    reference: int | None = None
    formation_state: int = 0
    assignment_gap: float | None = None
    certified: bool | None = None
    proposal_lane: int | None = None
    step_gap: float | None = None
    step_certified: bool | None = None
    refined: bool = False


@dataclass(frozen=True, slots=True)
class Memory:
    lane_target: int | None = None
    front: int | None = None
    proposed_step: int | None = None
    proposal_since: float = 0.
    # (local track, last lane, longitudinal position of last observed crossing)
    crossings: tuple[tuple[int, int, float], ...] = ()
    preview_start: float | None = None
    receiving_track: int | None = None


def desired_spacing(speed):
    return LENGTH + STANDSTILL + HEADWAY * speed


def _occupies(car, lane, horizon=1.):
    center = (lane + .5) * LANE_WIDTH
    end_y = car.y + horizon * car.vy
    return (min(car.y, end_y) - WIDTH / 2 < center + LANE_WIDTH / 2
            and max(car.y, end_y) + WIDTH / 2 > center - LANE_WIDTH / 2)


def _clear(ego, rows, lane):
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
    return max(0., min(MAX_SPEED, ego.speed + SPEED_RELAXATION * (desired - ego.speed)))


def _phase(lane, speed):
    return desired_spacing(speed) / 2 if lane % 2 else 0.


def _physical_phase(car, speed):
    """横移途中，按车辆实际横向位置在两个车道的交错目标之间插值。"""
    lateral = max(0., car.y / LANE_WIDTH - .5)
    lower = int(lateral)
    upper = lower + 1
    return _phase(lower, speed) + (lateral - lower) * (
        _phase(upper, speed) - _phase(lower, speed))


def _pair_error(car, peer):
    speed = (car.speed + peer.speed) / 2
    return peer.x - car.x + _physical_phase(peer, speed) - _physical_phase(car, speed)


def _front_following(ego, rows, distance=50.):
    front = min((c for c in rows if 0. < c.x - ego.x <= distance
                 and _occupies(c, ego.lane, 0.)),
                key=lambda c: (c.x, c.y, c.speed), default=None)
    if front is None:
        return CRUISE, None, None, 0
    target = front.x - desired_spacing(ego.speed)
    return _request(ego, target, front.speed), target, front.track, 1


def _local_group(ego, rows):
    """只取本车视野内、相邻纵向间隔至多 50 米的车群。"""
    cars = sorted((ego, *rows), key=lambda c: (c.x, c.lane))
    first = last = cars.index(ego)
    while first and cars[first].x - cars[first - 1].x <= GROUP_GAP:
        first -= 1
    while last + 1 < len(cars) and cars[last + 1].x - cars[last].x <= GROUP_GAP:
        last += 1
    return cars[first:last + 1]


def _following(ego, rows):
    """本车在同一帧观测中双向匹配邻车，再微调速度形成半个车头间距的错位。"""
    following = _front_following(ego, rows)
    cars = (ego, *rows)

    def nearest(car, lane):
        return min((c for c in cars if c.lane == lane and abs(c.x - car.x) <= 50.),
                   key=lambda c: (abs(_pair_error(car, c)),
                                  abs(c.x - car.x), c.x, c.y, c.speed, c.vy), default=None)

    linked = bool(following[3]) or any(-50. <= c.x - ego.x < 0.
             and _occupies(c, ego.lane, 0.) for c in rows)
    error = 0.
    for lane in (ego.lane - 1, ego.lane + 1):
        if lane >= 0:
            peer = nearest(ego, lane)
            if peer is not None and nearest(peer, ego.lane) is ego:
                linked = True
                error += _pair_error(ego, peer) / 2
    phase_speed = max(-2., min(2., POSITION_GAIN * error))
    if following[2] is not None:
        if phase_speed * (following[0] - ego.speed) < 0.:
            phase_speed = 0.
        return (max(0., min(MAX_SPEED, following[0] + SPEED_RELAXATION * phase_speed)),
                following[1], following[2], int(linked))
    target = ego.x + phase_speed / POSITION_GAIN
    return _request(ego, target, CRUISE), target, None, int(linked)


def _reactive(ego, rows, memory, lanes):
    """纯 NOA 跟随实际前车，受阻时可超车，见到缩道后寻找安全并入机会。"""
    speed, target, reference, _ = _front_following(ego, rows)
    lane = ego.pending_lane
    moving = abs(ego.vy) > .1 or abs(ego.y - (ego.lane + .5) * LANE_WIDTH) > .15
    if lane is None and moving:
        lane = memory.lane_target
    if lane is not None:
        return Command(speed, lane, 'executing', target, reference), Memory(lane_target=lane)
    if ego.lane >= lanes:
        if _clear(ego, rows, lanes - 1):
            return Command(speed, lanes - 1, 'merge', target, reference), Memory(lane_target=lanes - 1)
        anchor = _actual_front(ego, rows, lanes - 1)
        if anchor is not None:
            approach_x = anchor.x - _entry_spacing(ego.speed)
            approach_speed = _request(ego, approach_x, anchor.speed)
            if approach_speed < speed:
                speed, target, reference = approach_speed, approach_x, anchor.track
        return Command(speed, None, 'merge_wait', target, reference), Memory()
    front = min((c for c in rows if c.lane == ego.lane and c.x > ego.x),
                key=lambda c: c.x, default=None)
    if front is not None and ego.speed < CRUISE - 2 and front.speed < CRUISE - 2:
        options = [lane for lane in (ego.lane - 1, ego.lane + 1)
                   if 0 <= lane < lanes and _clear(ego, rows, lane)]

        def free_distance(lane):
            return min((c.x - ego.x for c in rows if c.lane == lane and c.x > ego.x),
                       default=200.)

        if options:
            lane = max(options, key=free_distance)
            if free_distance(lane) > front.x - ego.x + 15.:
                return Command(speed, lane, 'normal_overtake', target, reference), Memory(lane_target=lane)
    return Command(speed, None, 'normal_follow', target, reference), Memory()


def _actual_front(ego, rows, lane):
    return min((c for c in rows if 0. < c.x - ego.x <= 200.
                and _occupies(c, lane, 0.)),
               key=lambda c: (c.x, c.y, c.speed), default=None)


def _entry_spacing(speed):
    # 车并入交错中点后，前后两个半间距都要容得下 8 米换道净空。
    return max(desired_spacing(speed), 2 * CLEARANCE)


def _solo_follow(ego, rows, memory):
    """落单车保留实际前车约束与本车已经发起的横移。"""
    speed, target, reference, linked = _following(ego, rows)
    physical = _front_following(ego, rows, FRONT_VIEW)
    if reference is None and physical[2] is not None and memory.front is not None:
        local_speed = _request(ego, ego.x, CRUISE)
        speed = max(0., min(MAX_SPEED, physical[0] + speed - local_speed))
        target, reference, linked = physical[1:4]
    if ego.pending_lane is not None:
        return Command(physical[0], ego.pending_lane, 'executing', physical[1], physical[2], linked), memory
    return Command(speed, None, 'formation_follow', target, reference, linked), Memory(front=reference)


def safe_speed(ego, neighbors):
    limit = MAX_SPEED
    response_speed = BRAKING * RESPONSE
    occupied = tuple(lane for lane in range(max(0, ego.lane - 2), ego.lane + 3) if _occupies(ego, lane))
    for front in neighbors:
        if not 0. < front.x - ego.x <= 200.:
            continue
        if any(_occupies(front, lane) for lane in occupied):
            free = max(0., front.x - ego.x - LENGTH - STANDSTILL)
            stopping = sqrt(response_speed ** 2 + front.speed ** 2 + 2 * BRAKING * free) - response_speed
            limit = min(limit, stopping)
    return limit


def _shape_speed(ego, target_x):
    acceleration = (SHAPE_FREQUENCY ** 2 * (target_x - ego.x)
                    + 2 * SHAPE_FREQUENCY * (CRUISE - ego.speed))
    accel = max(-SHAPE_ACCEL_LIMIT, min(SHAPE_ACCEL_LIMIT, acceleration))
    return max(0., min(MAX_SPEED, ego.speed + CONTROL_STEP * accel))


def _observed_crossings(group, memory):
    previous = {track: (lane, x) for track, lane, x in memory.crossings}
    observed = []
    for car in group:
        lane, x = previous.get(car.track, (car.lane, float("-inf")))
        observed.append((car.track, car.lane, car.x if car.lane != lane else x))
    return tuple(observed)


def _transport(ego, rows, memory, lanes, opened, transforming, preview_start):
    from noa.staggered import anchored_x, choose_target
    from noa.transport import compatible_join_step

    group = list(reversed(_local_group(ego, rows)))
    forward_anchor = None
    if not transforming:
        forward_anchor = min((c.x for c in rows if c.x > group[0].x), default=None)
    if len(group) == 1 and transforming and lanes == 2:
        front = min((c for c in rows if 0 < c.x - ego.x <= REAR_VIEW),
                    key=lambda c: (c.x, c.lane), default=None)
        if front is not None:
            group = [front, ego]
    crossings = _observed_crossings(group, memory)
    if len(group) == 1:
        if ego.lane >= lanes:
            return _reactive(ego, rows, memory, lanes)
        command, memory = _solo_follow(ego, rows, memory)
        if forward_anchor is not None and command.reference is None and command.lane is None:
            x = anchored_x(ego.x, ego.x, desired_spacing(ego.speed), forward_anchor)
            command = replace(command, speed=_shape_speed(ego, x), target_x=x)
        return command, replace(memory, crossings=crossings)

    rank = group.index(ego)
    spacing = desired_spacing(sum(c.speed for c in group) / len(group))
    head_clipped = group[0].x - ego.x > FRONT_VIEW - GROUP_GAP
    tail_clipped = ego.x - group[-1].x > REAR_VIEW - GROUP_GAP
    moved = (tuple(x >= preview_start for _, _, x in crossings)
             if transforming and preview_start is not None else ())
    target = choose_target(rank, group, lanes, spacing, moved=moved, receiving=transforming,
                           head_clipped=head_clipped, tail_clipped=tail_clipped,
                           sensor_bounds=(ego.x - REAR_VIEW, ego.x + FRONT_VIEW),
                           forward_anchor=forward_anchor, opened_lanes=opened if opened < lanes else None)
    target_x = target.x
    receiving_track = None
    if target.incoming_front is not None:
        incoming = group[target.incoming_front]
        if incoming.track == memory.receiving_track or not _clear(incoming, (ego,), ego.lane):
            target_x = min(target_x, incoming.x - spacing)
            receiving_track = incoming.track
    speed = _shape_speed(ego, target_x)

    predecessor = group[rank - 1].track if rank else None
    front_speed, front_x, front, _ = _front_following(ego, rows, FRONT_VIEW)
    if front is not None and not transforming:
        retained_front = memory.front == front and all(c.track != front for c in group)
        if retained_front or all(c.lane == ego.lane for c in group):
            # A side-by-side neighbour does not erase a previously followed
            # car across a long gap. A single file also follows its real front.
            speed, predecessor = front_speed, front
        elif front_x < ego.x:
            speed = min(speed, front_speed)

    lane = ego.pending_lane
    step = None
    if target.lane != ego.lane and target.step_certified and target.released:
        step = ego.lane + (1 if target.lane > ego.lane else -1)
    if not transforming and step is not None and len(group) < 1 + len(rows):
        counts = tuple(sum(car.lane == lane for car in (ego, *rows)) for lane in range(lanes))
        if not compatible_join_step(counts, ego.lane, step):
            step = None
    since = memory.proposal_since if step == memory.proposed_step else ego.time
    persistent = transforming or ego.time - since >= LANE_CHANGE_TIME - 1e-8
    if lane is None and step is not None and step < opened and persistent and _clear(ego, rows, step):
        lane = step
    reason = 'transform_transport' if transforming else 'formation_transport'
    return (Command(speed, lane, reason, target_x, predecessor, 1,
                    target.gap, target.certified, target.lane, target.step_gap, target.step_certified,
                    target.refined),
            Memory(lane, predecessor, proposed_step=step, proposal_since=since,
                   crossings=crossings, receiving_track=receiving_track))


def decide(ego, neighbors, memory, mode, drop_x=1000., *, lane_count=3, downstream=False,
           upcoming_lanes=None, visible_boundary_x=None):
    """Use the downstream template once visible, crossing only into an open lane."""
    distance_to_end = drop_x - ego.x if drop_x is not None else float('inf')
    approaching = drop_x is not None and distance_to_end <= ROAD_PREVIEW and not downstream
    lanes = (upcoming_lanes if upcoming_lanes is not None else
             lane_count - 1 if approaching and lane_count > 2 else lane_count)
    transition = approaching or downstream or upcoming_lanes is not None
    rows = tuple(c for c in neighbors if -REAR_VIEW <= c.x - ego.x <= FRONT_VIEW)
    usable = min(lanes, lane_count)
    if mode == 'noa':
        command, memory = _reactive(ego, rows, memory, usable)
    elif mode == 'transform' or mode == 'formation' and not transition:
        preview_start = memory.preview_start if visible_boundary_x is None else visible_boundary_x - ROAD_PREVIEW
        command, memory = _transport(ego, rows, memory, lanes, lane_count, transition, preview_start)
        memory = replace(memory, preview_start=preview_start)
    elif mode == 'formation':
        speed, target, reference, linked = _following(ego, rows)
        if ego.lane >= usable or ego.pending_lane is not None:
            command, memory = _reactive(ego, rows, memory, usable)
            command = replace(command, formation_state=linked)
        else:
            command = Command(speed, None, 'formation_follow', target, reference, linked)
            memory = Memory(front=reference)
    else:
        raise ValueError('Unknown driving mode: ' + mode)
    limit = safe_speed(ego, neighbors)
    if distance_to_end <= ROAD_PREVIEW and ego.lane >= lanes:
        distance = max(0., distance_to_end - STANDSTILL)
        limit = min(limit, sqrt((BRAKING * RESPONSE) ** 2 + 2 * BRAKING * distance) - BRAKING * RESPONSE)
    return replace(command, speed=min(command.speed, limit)), memory
