"""Cai-style centralized assignment reference, not a full Cai2024 reproduction.

Retains staggered targets and squared normalized longitudinal/lane assignment
costs from formationControlNormal.m/getRelativeDistance.m. MATLAB's foremost
target at front-30m is shifted to front, the current group head; lanes use the common
highest-lane phase convention. Same-source-lane assignments are sorted by x:
the convex squared longitudinal cost cannot increase under this uncrossing.

No A*/CBS/Bezier/GPOPS/SNOPT is reproduced. Shared feedback and 8m/1s clearance
produce adjacent lane requests; SUMO alone executes motion and vehicle safety.
The complete true-state map is intentionally privileged, solely for this reference.
"""

from dataclasses import replace

from scipy.optimize import linear_sum_assignment

from noa.native_rules import CRUISE, LANE_WIDTH, Command, Vehicle, _clear, _request


class GlobalPlanner:
    """Reassign every 5s; expose plan origins and groups for experiment records.

    ``assignments[id]`` is ``(origin_x, final_lane)`` at ``planned_at``. Live
    commands advance origin_x at 28.8m/s. New arrivals cruise until the next
    structural plan; departed IDs are removed without resetting existing targets.
    """

    def __init__(self):
        self.assignments: dict[str, tuple[float, int]] = {}
        self.groups: tuple[tuple[str, ...], ...] = ()
        self.planned_at: float | None = None
        self._changing: dict[str, int] = {}

    @staticmethod
    def _order(states):
        # IDs break only physically indistinguishable ties, never lane priority.
        return sorted(states, key=lambda k: (-states[k].x, -states[k].lane, states[k].y, states[k].speed, k))

    @staticmethod
    def _targets(count, front, lanes):
        slots = [
            (front - 30.0 * layer - 15.0 * ((lanes - 1 - lane) % 2), lane)
            for layer in range((count + lanes - 1) // lanes)
            for lane in reversed(range(lanes))
        ]
        return sorted(slots, key=lambda p: (-p[0], -p[1]))[:count]

    def _plan(self, states, now, drop_x):
        groups = []
        for key in self._order(states):
            if not groups or states[groups[-1][-1]].x - states[key].x > 50.0:
                groups.append([])
            groups[-1].append(key)
        self.groups = tuple(tuple(group) for group in groups)
        self.assignments = {}
        for group in groups:
            front = states[group[0]].x
            lanes = 2 if drop_x is not None and front >= drop_x - 360.0 else 3
            slots = self._targets(len(group), front, lanes)
            costs = [
                [((x - states[key].x) / 15.0) ** 2 + (lane - states[key].lane) ** 2 for x, lane in slots]
                for key in group
            ]
            rows, columns = linear_sum_assignment(costs)
            matched = {group[i]: slots[j] for i, j in zip(rows, columns)}
            # All rows with the same source lane have identical lateral costs.
            # Sorting their allocated slots preserves the optimum and FIFO order.
            for lane in range(3):
                members = [key for key in group if states[key].lane == lane]
                ordered = sorted((matched[key] for key in members), key=lambda p: (-p[0], -p[1]))
                self.assignments.update(zip(members, ordered))
        self.planned_at = now

    def commands(
        self, states: dict[str, Vehicle], now: float, drop_x: float | None = 1000.0
    ) -> dict[str, Command]:
        if not states:
            self.assignments.clear()
            self._changing.clear()
            self.groups, self.planned_at = (), None
            return {}
        if self.planned_at is None or now < self.planned_at or now - self.planned_at >= 5.0 - 1e-9:
            self._plan(states, now, drop_x)
        self.assignments = {k: p for k, p in self.assignments.items() if k in states}
        self._changing = {k: lane for k, lane in self._changing.items() if k in states}
        order = self._order(states)
        # Common clearance uses track for self exclusion; normalize the central
        # frame so local/private track labels need not be globally unique.
        cars = {key: replace(states[key], track=i) for i, key in enumerate(order)}
        occupied = list(cars.values())
        result = {}
        for key in order:
            ego, slot = cars[key], self.assignments.get(key)
            target = None if slot is None else slot[0] + CRUISE * (now - self.planned_at)
            speed = CRUISE if target is None else _request(ego, target, CRUISE)
            lane, reason = None, "global_unplanned" if slot is None else "global_track"
            changing = self._changing.get(key)
            if changing is not None:
                center = (changing + 0.5) * LANE_WIDTH
                if abs(ego.y - center) <= 0.15 and abs(ego.vy) <= 0.1:
                    del self._changing[key]
                else:
                    lane, reason = changing, "global_executing"
            if lane is None and slot is not None and slot[1] != ego.lane:
                step = ego.lane + (1 if slot[1] > ego.lane else -1)
                ending = drop_x is not None and ego.x >= drop_x - 360.0 and step == 2
                if not ending and _clear(ego, occupied, step):
                    lane, reason = step, "global_change"
                    self._changing[key] = lane
                else:
                    reason = "global_wait_clearance"
            if lane is not None:
                # Reserve this adjacent corridor for later simultaneous requests.
                occupied.append(replace(ego, lane=lane, y=(lane + 0.5) * LANE_WIDTH, vy=0.0))
            result[key] = Command(speed, lane, reason, target)
        return result
