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
    from_ending: frozenset[int] = frozenset()


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


def _formation_fill(ego, group, rows, lanes):
    """从队首往后找能补前方缺位的车；每辆车只执行自己的决定。"""
    sizes = [sum(c.lane == lane for c in group) for lane in range(lanes)]
    balanced = max(sizes) - min(sizes) <= 1
    if balanced and (lanes != 3 or sizes[1] <= min(sizes[0], sizes[2])):
        return None
    if any(abs(c.vy) > .05 or abs(c.y - (c.lane + .5) * LANE_WIDTH) > .05 for c in group):
        return None
    if balanced:
        # 末层还没有填齐时，让中道最后一辆车补到较空的一侧。
        if ego.lane != 1 or next(c for c in group if c.lane == 1) is not ego:
            return None
        return next((lane for lane in (0, 2) if sizes[lane] < sizes[1] and _clear(ego, rows, lane)), None)
    # 从前向后读取实际占道。每辆车只在自己这一层能往前补一个位置时考虑换道。
    counts = [0] * lanes
    tails = [None] * lanes
    for car in reversed(group):
        source = car.lane
        dest = min(range(lanes), key=lambda lane: (counts[lane], abs(lane - source), lane))
        if counts[source] > counts[dest]:
            step = source + (1 if dest > source else -1)
            front = tails[dest]
            gap = desired_spacing(car.speed)
            slot = (front.x - gap if front is not None else
                    group[-1].x + _phase(group[-1].lane, car.speed) - _phase(dest, car.speed))
            vacant = all(c.lane != dest or abs(c.x - slot) >= gap / 2 for c in group)
            if vacant and counts[step] <= counts[source] and _clear(car, group, step):
                # 先让前面的候选车补，一次只跨相邻一道。
                return step if car is ego and _clear(ego, rows, step) else None
        if car is ego:
            break
        counts[source] += 1
        tails[source] = car
    return None


def _layer_target(ego, group, lanes):
    """把各道实车位置按同道层距和邻道半层错位换算到本车所在层。"""
    spacing = desired_spacing(ego.speed)
    rank = [0] * lanes
    origin = 0.
    for car in reversed(group):
        lane = car.lane
        offset = rank[lane] * spacing + _phase(lane, ego.speed)
        origin += car.x + offset
        if car is ego:
            own_offset = offset
        rank[lane] += 1
    return origin / len(group) - own_offset


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


def _two_lane_slot(group, rank, first_lane, seen_ending):
    """在连续六个可见位置内，就近分道；同一目标道保持纵向顺序。"""
    start = rank - rank % 6
    indices = range(start, min(start + 6, len(group)))
    slots = [[j for j in indices if (first_lane + j) % 2 == lane] for lane in (0, 1)]

    def cost_to_lane_zero(j):
        car = group[j]
        return (car.track in seen_ending, j not in slots[0], car.lane != 0, j)

    assigned_zero = set(sorted(indices, key=cost_to_lane_zero)[:len(slots[0])])
    on_zero = rank in assigned_zero
    lane = 0 if on_zero else 1
    earlier = sum((j in assigned_zero) == on_zero for j in range(start, rank))
    return lane, slots[lane][earlier]


def _three_lane_position(group, rank, spacing):
    """每三辆组成一层。两侧同相，中道落后半个同道间距。"""
    start = rank - rank % 3
    layer = group[start:start + 3]
    if len(layer) == 1:
        source = min(layer[0].lane, 2)
        lane = source if len(group) == 1 else min((0, 2), key=lambda edge: abs(edge - source))
    else:
        lanes = (0, 2) if len(layer) == 2 else (0, 1, 2)
        lane = lanes[sorted(layer, key=lambda car: car.lane).index(group[rank])]
    own_offset = rank // 3 + (0.5 if lane == 1 and len(layer) == 3 else 0.)
    target = sum(car.x + spacing * (j // 3 + (0.5 if j % 3 == 2 else 0.) - own_offset)
                 for j, car in enumerate(group)) / len(group)
    return lane, target


def _fold(ego, rows, memory, lanes):
    """按缩道后的可用车道数，在本车可见段内拟合交错队形。"""
    group = list(reversed(_local_group(ego, rows)))
    # 落单车可接到最近的可见队尾，两辆车须在彼此前后视距以内。
    if lanes == 2 and len(group) == 1:
        front = min((c for c in rows if 0 < c.x - ego.x <= REAR_VIEW),
                    key=lambda c: (c.x, c.lane), default=None)
        if front is not None:
            group = [front, ego]
    rank = group.index(ego)
    mean_speed = sum(car.speed for car in group) / len(group)
    spacing = desired_spacing(mean_speed)
    seen_ending = frozenset()
    if lanes == 2:
        first_lane = min(group[0].lane, 1)
        seen_ending = frozenset(car.track for car in group if car.lane == 2 or car.track in memory.from_ending)
        target_lane, slot = _two_lane_slot(group, rank, first_lane, seen_ending)
        target_x = sum(car.x + (j - slot) * (spacing / 2) for j, car in enumerate(group)) / len(group)
    else:
        target_lane, target_x = _three_lane_position(group, rank, spacing)

    acceleration = (SHAPE_FREQUENCY ** 2 * (target_x - ego.x)
                    + 2 * SHAPE_FREQUENCY * (CRUISE - ego.speed))
    acceleration = max(-SHAPE_ACCEL_LIMIT, min(SHAPE_ACCEL_LIMIT, acceleration))
    speed = max(0., min(MAX_SPEED, ego.speed + CONTROL_STEP * acceleration))
    lane = ego.pending_lane
    if lane is None and ego.lane != target_lane:
        adjacent = ego.lane + (1 if target_lane > ego.lane else -1)
        if _clear(ego, rows, adjacent):
            lane = adjacent
    predecessor = group[rank - 1].track if rank else None
    reason = 'two_lane_shape' if lanes == 2 else 'three_lane_shape'
    return Command(speed, lane, reason, target_x, predecessor, int(len(group) > 1)), Memory(lane, predecessor, seen_ending)


def _layered_formation(ego, rows, memory, lanes):
    """在可见车群内补缺，再按当前车道数和交错相位调距。"""
    speed, target, reference, linked = _following(ego, rows)
    physical = _front_following(ego, rows, FRONT_VIEW)
    if reference is None and physical[2] is not None and memory.front is not None:
        local_speed = _request(ego, ego.x, CRUISE)
        speed = max(0., min(MAX_SPEED, physical[0] + speed - local_speed))
        target, reference, linked = physical[1:4]
    group = _local_group(ego, rows)
    if ego.pending_lane is not None:
        participating = int(linked or len(group) > 1)
        return Command(physical[0], ego.pending_lane, 'executing', physical[1], physical[2], participating), memory
    # 一端外侧还有一个完整连接距离可看，才从这段车群数层补位。
    end_visible = (group[-1].x - ego.x <= FRONT_VIEW - GROUP_GAP
                   or ego.x - group[0].x <= REAR_VIEW - GROUP_GAP)
    if len(group) >= 2 and end_visible:
        lane = _formation_fill(ego, group, rows, lanes)
        if lane is not None:
            return Command(speed, lane, 'formation_fill', target, reference, 1), Memory(lane, reference)
        target = _layer_target(ego, group, lanes)
        speed = _request(ego, target, CRUISE)
        if physical[1] is not None and physical[1] < ego.x:
            speed = min(speed, physical[0])
        return Command(speed, None, 'formation_align', target, reference, 1), Memory(front=reference)

    return Command(speed, None, 'formation_follow', target, reference, linked), Memory(front=reference)


def _decide(ego, neighbors, memory, mode, lanes, at_drop):
    rows = tuple(c for c in neighbors if -REAR_VIEW <= c.x - ego.x <= FRONT_VIEW)
    if mode == 'noa':
        return _reactive(ego, rows, memory, lanes)
    if mode not in ('formation', 'transform'):
        raise ValueError('Unknown driving mode: ' + mode)
    if mode == 'transform' and at_drop:
        return _fold(ego, rows, memory, lanes)
    if ego.lane >= lanes or (at_drop and mode == 'formation' and ego.pending_lane is not None):
        command, own = _reactive(ego, rows, memory, lanes)
        return replace(command, formation_state=_following(ego, rows)[3]), own
    if at_drop and mode == 'formation':
        speed, target, ref, linked = _following(ego, rows)
        return Command(speed, None, 'formation_follow', target, ref, linked), Memory(front=ref)
    return _layered_formation(ego, rows, memory, lanes)


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


def decide(ego, neighbors, memory, mode, drop_x=1000., *, lane_count=3, downstream=False):
    """下游只需本地车道数。旧调用传入缩道位置时，仍按本车位置判断两道接续。"""
    distance_to_end = drop_x - ego.x if drop_x is not None else float('inf')
    # 旧调用可在驶过缩道后继续传缩道坐标。
    approaching = drop_x is not None and distance_to_end <= ROAD_PREVIEW and not downstream
    lanes = lane_count - 1 if approaching and lane_count > 2 else lane_count
    command, memory = _decide(ego, neighbors, memory, mode, lanes, approaching or downstream or lanes == 2)
    limit = safe_speed(ego, neighbors)
    if distance_to_end <= ROAD_PREVIEW and ego.lane >= lanes:
        distance = max(0., distance_to_end - STANDSTILL)
        limit = min(limit, sqrt((BRAKING * RESPONSE) ** 2 + 2 * BRAKING * distance) - BRAKING * RESPONSE)
    return replace(command, speed=min(command.speed, limit)), memory
