"""前向虚拟合流跟驰与真实编队空位接续。"""
from dataclasses import dataclass, replace
from math import sqrt

CRUISE, MAX_SPEED = 28.8, 33.3
POSITION_GAIN, SPEED_RELAXATION = .3, .2
WIDTH, LANE_WIDTH, CLEARANCE = 1.8, 3.3, 8.
LENGTH, STANDSTILL, BRAKING, RESPONSE = 4., 1.5, 10., .2
HEADWAY = .85
ROAD_PREVIEW = 300.


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


def _phase(lane, speed=CRUISE):
    return 0.


def _physical_phase(car, lanes, speed=None):
    speed = car.speed if speed is None else speed
    lateral = max(0., min(lanes - 1, car.y / LANE_WIDTH - .5))
    lower = int(lateral)
    upper = min(lower + 1, lanes - 1)
    return _phase(lower, speed) + (lateral - lower) * (
        _phase(upper, speed) - _phase(lower, speed))


def _pair_error(car, peer, lanes):
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


def _following(ego, rows, lanes=3):
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


def _actual_front(ego, rows, lane):
    return min((c for c in rows if 0. < c.x - ego.x <= 200.
                and _occupies(c, lane, 0.)),
               key=lambda c: (c.x, c.y, c.speed), default=None)


def _entry_spacing(speed):
    # Two staggered half-pitches must each fit the unchanged 8 m corridor.
    return max(desired_spacing(speed), 2 * CLEARANCE)


def _queue_front(ego, rows, known):
    """All references are strictly ahead; virtual insertion must be executable now."""
    actual = _actual_front(ego, rows, ego.lane)
    choices = [actual] if actual is not None else []
    if ego.lane in (0, 1):
        snapshot = (ego, *rows)
        for peer in rows:
            if not 0. < peer.x - ego.x <= 200.:
                continue
            direct = ego.lane == 1 and peer.lane == 2 and (known or peer.vy < -.1)
            cascade = (known and ego.lane == 0 and peer.lane == 1 and any(
                ending.lane == 2 and 0. < ending.x - peer.x <= desired_spacing(peer.speed)
                and _clear(ending, snapshot, 1) for ending in rows))
            observed = ego.lane == 0 and peer.lane == 1 and peer.vy < -.1
            if (direct or cascade or observed) and _clear(peer, snapshot, ego.lane):
                choices.append(peer)
    return min(choices, key=lambda c: (c.x, c.y, c.speed), default=None)


def _vacancy(ego, rows, lane, held=None):
    """An actual front minus one entry pitch, with another full pitch behind."""
    front = _actual_front(ego, rows, lane)
    if front is None or held is not None and front.track != held:
        return None
    d = _entry_spacing(ego.speed)
    target = front.x - d
    current = _actual_front(ego, rows, ego.lane)
    if current is not None:
        q = current.x
        if abs(target - q) > abs(ego.x - q) + 1e-9:
            return None
    for other in rows:
        if other.track == ego.track or not _occupies(other, lane):
            continue
        offset = other.x - target
        predicted = offset + other.speed - front.speed
        if offset * predicted <= 0. or min(abs(offset), abs(predicted)) < d - 1e-9:
            return None
        # A stopped adjacent front/rear inside 8 m cannot be yielded to by reversing.
        if abs(other.x - ego.x) < CLEARANCE:
            return None
    return front, target


def _decide(ego, neighbors, memory, mode, drop_x=1000.):
    if mode not in ('noa', 'formation', 'transform'):
        raise ValueError('Unknown driving mode: ' + mode)
    rows = tuple(c for c in neighbors if -100. <= c.x - ego.x <= 200.)
    known = drop_x if drop_x is not None and drop_x - ego.x <= ROAD_PREVIEW else None
    if mode == 'noa':
        return _reactive(ego, rows, memory, known)
    moving = abs(ego.vy) > .1 or abs(ego.y - (ego.lane + .5) * LANE_WIDTH) > .15
    current = _actual_front(ego, rows, ego.lane)
    guided = (mode == 'transform' and ego.lane == 2
              and current is not None and current.vy < -.1)
    mandatory = ego.lane == 2 and (known is not None or guided or memory.lane_target == 1)
    front = _queue_front(ego, rows, known is not None) if mode == 'transform' else current
    physical = _front_following(ego, rows, 200.)
    access = ((known is not None and any(c.lane == 2 for c in (ego, *rows)))
              or mandatory or front is not None and front.track != physical[2]
              or moving or ego.pending_lane is not None)
    d = _entry_spacing(ego.speed) if access else desired_spacing(ego.speed)
    target = front.x - d if front is not None else None
    speed = _request(ego, target, front.speed) if front is not None else CRUISE
    reference = front.track if front is not None else None
    formed = _following(ego, rows)
    transition = access or front is not None and front.track != physical[2]
    if not transition:
        speed, target, reference, linked = formed
        local = _front_following(ego, rows)
        if local[2] is None and physical[2] is not None and memory.front is not None:
            # Close the visible 50-200 m hole without cancelling soft phase again.
            speed = max(0., min(MAX_SPEED, physical[0] + formed[0] - _request(ego, ego.x, CRUISE)))
            target, reference = physical[1], physical[2]
    else:
        linked = int(front is not None or formed[3])

    lane = ego.pending_lane
    plan = memory.lane_target
    anchor = None
    if lane is None and moving:
        lane = plan
    if not moving and ego.pending_lane is None and plan == ego.lane:
        plan = None
    if lane is not None:
        plan = lane
        anchor = _actual_front(ego, rows, lane)
    elif mandatory:
        plan = 1
        anchor = _actual_front(ego, rows, 1)
        if _clear(ego, rows, 1):
            lane = 1
    elif (mode == 'transform' and ego.lane == 1
          and (known is not None or any(c.vy < -.1 for c in rows) or plan is not None)):
        vacancy = _vacancy(ego, rows, plan, memory.front) if plan is not None else None
        if vacancy is None:
            plan = None
            crowded = front is not None and (front.x - ego.x <= _entry_spacing(ego.speed)
                                             or speed < CRUISE)
            if crowded:
                vacancy = _vacancy(ego, rows, 0)
                if vacancy is not None:
                    point = vacancy[1]
                    useful = (current is not None or target is None or point > target + 1e-9
                              or ego.lane == 1 and front.lane == 2 and point >= target - 1e-9)
                    if useful:
                        plan = 0
        if plan is not None and vacancy is not None:
            anchor = vacancy[0]
            if _clear(ego, rows, plan):
                lane = plan
    else:
        plan = None

    if plan is not None and anchor is not None:
        target = anchor.x - _entry_spacing(ego.speed)
        speed, reference = _request(ego, target, anchor.speed), anchor.track
    if physical[2] is not None and (transition or plan is not None):
        speed = min(speed, physical[0])
    own = Memory(lane_target=plan, front=anchor.track if anchor is not None else reference)
    reason = ('forward_change' if lane is not None else 'forward_approach' if plan is not None
              else 'forward_follow')
    return Command(speed, lane, reason, target, reference, int(linked or reference is not None)), own


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
