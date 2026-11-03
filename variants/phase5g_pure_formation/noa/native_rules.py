"""局部时距交错编队：真实跟驰、前驱串接与逐步横移。"""
from dataclasses import dataclass, replace
from math import sqrt

CRUISE, MAX_SPEED = 28.8, 33.3
POSITION_GAIN, SPEED_RELAXATION = .3, .2
WIDTH, LANE_WIDTH, CLEARANCE = 1.8, 3.3, 8.
LENGTH, STANDSTILL, BRAKING, RESPONSE = 4., 1.5, 10., .2
HEADWAY = .85
ROAD_PREVIEW = 200.
GAP = LENGTH + STANDSTILL + HEADWAY * CRUISE


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


@dataclass(frozen=True, slots=True)
class Memory:
    lane_target: int | None = None
    front: int | None = None
    transforming: bool = False


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


def _phase(lane, lanes, speed=CRUISE):
    return desired_spacing(speed) / 2 if lane % 2 else 0.


def _physical_phase(car, lanes, speed=None):
    speed = car.speed if speed is None else speed
    lateral = max(0., min(lanes - 1, car.y / LANE_WIDTH - .5))
    lower = int(lateral)
    upper = min(lower + 1, lanes - 1)
    return _phase(lower, lanes, speed) + (lateral - lower) * (
        _phase(upper, lanes, speed) - _phase(lower, lanes, speed))


def _pair_error(car, peer, lanes, phase_boundary=None):
    speed = (car.speed + peer.speed) / 2
    return (peer.x - car.x + _physical_phase(peer, 3, speed)
            - _physical_phase(car, 3, speed)), lanes


def _front_following(ego, rows, distance=50.):
    front = min((c for c in rows if 0. < c.x - ego.x <= distance
                 and _occupies(c, ego.lane, 0.)),
                key=lambda c: (c.x, c.y, c.speed), default=None)
    if front is None:
        return CRUISE, None, None, 0
    target = front.x - desired_spacing(ego.speed)
    return _request(ego, target, front.speed), target, front.track, 1


def _following(ego, rows, lanes=3, phase_boundary=None):
    """在真实前车跟驰上，用实车互选形成半时距错位。"""
    following = _front_following(ego, rows)
    cars = (ego, *rows)

    def nearest(car, lane):
        return min((c for c in cars if c.lane == lane and abs(c.x - car.x) <= 50.),
                   key=lambda c: (abs(_pair_error(car, c, lanes)[0]),
                                  abs(c.x - car.x), c.x, c.y, c.speed, c.vy), default=None)

    linked = bool(following[3]) or any(-50. <= c.x - ego.x < 0.
             and _occupies(c, ego.lane, 0.) for c in rows)
    error = 0.
    for lane in (ego.lane - 1, ego.lane + 1):
        if 0 <= lane < 3:
            peer = nearest(ego, lane)
            if peer is not None and nearest(peer, ego.lane) is ego:
                linked = True
                error += _pair_error(ego, peer, lanes)[0] / max(1, lanes - 1)
    phase_speed = max(-2., min(2., POSITION_GAIN * error))
    if following[2] is not None:
        if phase_speed * (following[0] - ego.speed) < 0.:
            phase_speed = 0.
        return (max(0., min(MAX_SPEED, following[0] + SPEED_RELAXATION * phase_speed)),
                following[1], following[2], int(linked))
    target = ego.x + phase_speed / POSITION_GAIN
    return _request(ego, target, CRUISE), target, None, int(linked)


def _reactive(ego, rows, memory, drop_x, overtake=True):
    """普通跟驰、当前间隙接受和受阻超车；不追踪合流间隙中点。"""
    speed, target, reference, _ = _front_following(ego, rows)
    lane = ego.pending_lane
    moving = abs(ego.vy) > .1 or abs(ego.y - (ego.lane + .5) * LANE_WIDTH) > .15
    if lane is None and moving:
        lane = memory.lane_target
    if lane is not None:
        return Command(speed, lane, 'executing', target, reference), Memory(lane_target=lane)
    if drop_x is not None and ego.lane == 2:
        if _clear(ego, rows, 1):
            return Command(speed, 1, 'merge', target, reference), Memory(lane_target=1)
        return Command(speed, None, 'merge_wait', target, reference), Memory()
    if overtake:
        front = min((c for c in rows if c.lane == ego.lane and c.x > ego.x),
                    key=lambda c: c.x, default=None)
        if front is not None and ego.speed < CRUISE - 2 and front.speed < CRUISE - 2:
            lanes = 2 if drop_x is not None and ego.x >= drop_x else 3
            options = [lane for lane in (ego.lane - 1, ego.lane + 1)
                       if 0 <= lane < lanes and not (drop_x is not None and lane == 2)
                       and _clear(ego, rows, lane)]

            def free_distance(lane):
                return min((c.x - ego.x for c in rows if c.lane == lane and c.x > ego.x),
                           default=200.)

            if options:
                lane = max(options, key=free_distance)
                if free_distance(lane) > front.x - ego.x + 15.:
                    return Command(speed, lane, 'normal_overtake', target, reference), Memory(lane_target=lane)
    return Command(speed, None, 'normal_follow', target, reference), Memory()


def _chain_front(ego, rows, held=None):
    front = next((c for c in rows if c.track == held), None)
    if front is not None:
        return front
    return min((c for c in rows if (c.x, c.y) > (ego.x, ego.y)),
               key=lambda c: (c.x, c.y, c.speed, c.vy), default=None)


def _decide(ego, neighbors, memory, mode, drop_x=1000.):
    if mode not in ('noa', 'formation', 'transform'):
        raise ValueError('Unknown driving mode: ' + mode)
    rows = tuple(c for c in neighbors if -100. <= c.x - ego.x <= 200.)
    known = drop_x if drop_x is not None and drop_x - ego.x <= ROAD_PREVIEW else None
    if mode == 'noa':
        return _reactive(ego, rows, memory, known)
    speed, target, reference, linked = _following(ego, rows)
    folding = any(c.lane == 2 and c.vy < -.1 for c in rows)
    active = mode == 'transform' and (memory.transforming or known is not None or folding)
    if not active:
        if known is not None and ego.lane == 2 or ego.pending_lane is not None:
            command, memory = _reactive(ego, rows, memory, known, overtake=False)
            return replace(command, formation_state=linked), memory
        return Command(speed, None, 'formation_follow', target, reference, linked), Memory(front=reference)

    front = _chain_front(ego, rows, memory.front if memory.transforming else None)
    reference = front.track if front is not None else None
    if front is not None:
        target = front.x - desired_spacing((ego.speed + front.speed) / 2) / 2
        speed = _request(ego, target, front.speed)
        following = _front_following(ego, rows)
        if following[2] is not None:
            speed = min(speed, following[0])
        destination = 1 - min(front.lane, 1)
        linked = 1
    else:
        speed, target, destination = CRUISE, None, min(ego.lane, 1)
    lane = ego.pending_lane
    moving = abs(ego.vy) > .1 or abs(ego.y - (ego.lane + .5) * LANE_WIDTH) > .15
    if lane is None and moving:
        lane = memory.lane_target
    if lane is None and destination != ego.lane:
        step = ego.lane + (1 if destination > ego.lane else -1)
        if _clear(ego, rows, step):
            lane = step
    memory = Memory(lane_target=lane, front=reference, transforming=True)
    reason = 'transform_change' if lane is not None else 'transform_follow'
    return Command(speed, lane, reason, target, reference, linked), memory


def safe_speed(ego, neighbors):
    limit = MAX_SPEED
    response_speed = BRAKING * RESPONSE
    occupied = tuple(lane for lane in range(3) if _occupies(ego, lane))
    for front in neighbors:
        if not 0. < front.x - ego.x <= 200.:
            continue
        if any(_occupies(front, lane) for lane in occupied):
            free = max(0., front.x - ego.x - LENGTH - STANDSTILL)
            stopping = sqrt(response_speed ** 2 + front.speed ** 2 + 2 * BRAKING * free) - response_speed
            limit = min(limit, stopping)
    return limit


def decide(ego, neighbors, memory, mode, drop_x=1000.):
    command, memory = _decide(ego, neighbors, memory, mode, drop_x)
    limit = safe_speed(ego, neighbors)
    if drop_x is not None and drop_x - ego.x <= ROAD_PREVIEW and ego.lane == 2:
        distance = max(0., drop_x - ego.x - STANDSTILL)
        limit = min(limit, sqrt((BRAKING * RESPONSE) ** 2 + 2 * BRAKING * distance) - BRAKING * RESPONSE)
    return replace(command, speed=min(command.speed, limit)), memory
