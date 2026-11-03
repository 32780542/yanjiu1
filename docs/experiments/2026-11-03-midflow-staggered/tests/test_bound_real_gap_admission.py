"""CTH-compatible admission inside a bound real gap; no traffic simulation."""
from dataclasses import asdict, replace
import importlib.util
import itertools
import os
from pathlib import Path
import random
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[4]
GP = ROOT / "tmp/staggered_bottleneck/candidates/midflow_bound_real_gap/native_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


gp = load("admission_frozen_GP", GP)
r = load("admission_candidate", os.environ.get("RULES_GP2", GP))


def car(track, x, lane, speed=28.8):
    return r.Vehicle(track, x, (lane+.5)*r.LANE_WIDTH, speed, lane)


def exact(value):
    if hasattr(value, "__dataclass_fields__"):
        return exact(asdict(value))
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {k: exact(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [exact(v) for v in value]
    return value


class BoundGapAdmissionTests(unittest.TestCase):
    def test_Cai_stage_horizon_reaches_positive_phase_gap_but_does_not_admit_early(self):
        ego, rows = car(0, 705., 2), (car(1, 690., 1), car(2, 770., 1))
        self.assertIsNone(gp._gap_plan(ego, rows, 1, None, 1000.))
        plan = r._gap_plan(ego, rows, 1, None, 1000.)
        self.assertIsNotNone(plan)
        self.assertEqual(plan[3], 5.)
        self.assertTrue(r._clear(ego, rows, 1))
        original, _ = gp.decide(ego, rows, gp.Memory(), "transform")
        self.assertEqual(original.lane, 1, "The GP premature-admission witness disappeared")
        command, memory = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(memory.gap, (2, 1))
        self.assertIsNone(command.lane)
        self.assertGreater(command.speed, ego.speed)  # approach, not a new stopping stage

    def test_existing_GP_plan_with_front_deficit_is_not_current_CTH_admission(self):
        ego, rows = car(0,755.,2),(car(1,690.,1),car(2,770.,1))
        self.assertIsNotNone(gp._gap_plan(ego,rows,1,None,1000.))
        self.assertTrue(r._clear(ego,rows,1))
        self.assertEqual(gp.decide(ego,rows,gp.Memory(),"transform")[0].lane,1)
        command,_=r.decide(ego,rows,r.Memory(),"transform")
        self.assertIsNone(command.lane)

    def test_current_CTH_window_allows_original_clear_lane_change(self):
        ego, rows = car(0, 730., 2), (car(1, 690., 1), car(2, 770., 1))
        command, memory = r.decide(ego, rows, r.Memory(), "transform")
        self.assertEqual(command.lane, 1)
        self.assertEqual(memory.gap, (2, 1))

    def test_existing_two_metre_tracking_tolerance_has_explicit_boundaries(self):
        rows=(car(1,690.,1),car(2,770.,1))
        for x,allowed in ((717.9,False),(718.,True),(719.,True),(721.,True),(742.,True),(742.1,False)):
            with self.subTest(x=x):
                ego=car(0,x,2)
                self.assertIsNotNone(r._gap_plan(ego,rows,1,None,1000.))
                command,_=r.decide(ego,rows,r.Memory(),"transform")
                self.assertEqual(command.lane,1 if allowed else None)

    def test_front_CTH_uses_current_ego_speed_not_gap_average(self):
        ego, rows = car(0, 739., 2, 33.3), (car(1, 690., 1), car(2, 770., 1))
        self.assertIsNotNone(r._gap_plan(ego, rows, 1, None, 1000.))
        self.assertTrue(r._clear(ego, rows, 1))
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertIsNone(command.lane)

    def test_rear_CTH_uses_current_rear_speed_not_gap_average(self):
        ego, rows = car(0, 718.5, 2), (car(1, 690., 1, 30.), car(2, 790., 1, 27.6))
        self.assertIsNotNone(r._gap_plan(ego, rows, 1, None, 1000.))
        self.assertTrue(r._clear(ego, rows, 1))
        command, _ = r.decide(ego, rows, r.Memory(), "transform")
        self.assertIsNone(command.lane)

    def test_moving_or_own_pending_does_not_get_cancelled_by_new_admission(self):
        rows = (car(1, 690., 1), car(2, 770., 1))
        for vy, pending in ((-.2, None), (0., 1)):
            ego = replace(car(0, 705., 2), vy=vy, pending_lane=pending)
            command, memory = r.decide(ego, rows, r.Memory(lane_target=1, gap=(2, 1), joining=True), "transform")
            self.assertEqual(command.lane, 1)
            self.assertEqual(command.reason, "executing")

    def test_no_resource_scope_and_target0_preserve_GP_exactly(self):
        rng = random.Random(202611032210)
        for _ in range(450):
            x = rng.uniform(100., 1100.)
            ego = car(0, x, rng.randrange(3), rng.uniform(0., 33.3))
            rows = tuple(car(i+1, x+dx, lane, rng.uniform(0., 33.3)) for i, (lane, dx)
                         in enumerate(itertools.product(range(3), (-80., -40., 20., 55., 100.))))
            for mode, drop in (("noa",1000.),("noa",None),("formation",1000.),("formation",None),("transform",None)):
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(), mode, drop)),
                                 exact(gp.decide(ego, rows, gp.Memory(), mode, drop)))
            if ego.lane == 1:
                self.assertEqual(exact(r.decide(ego, rows, r.Memory(lane_target=0), "transform")),
                                 exact(gp.decide(ego, rows, gp.Memory(lane_target=0), "transform")))
        for vy, pending in ((0.,None),(-.2,None),(0.,1)):
            ego = replace(car(0, 700., 2), vy=vy, pending_lane=pending)
            rows = (car(1,680.,1),car(2,704.,1))
            self.assertIsNone(r._gap_plan(ego, rows, 1, (2,1), 1000.))
            self.assertEqual(exact(r.decide(ego, rows, r.Memory(lane_target=1,gap=(2,1),joining=True), "transform")),
                             exact(gp.decide(ego, rows, gp.Memory(lane_target=1,gap=(2,1),joining=True), "transform")))

    def test_labels_permutation_invisible_and_physical_safety_preserved(self):
        ego, rows = car(0,705.,2),(car(1,690.,1),car(2,770.,1))
        command, memory = r.decide(ego,rows,r.Memory(),"transform")
        label=lambda c:replace(c,track=700-23*c.track)
        for order in itertools.permutations(rows):
            changed, held=r.decide(label(ego),tuple(label(c) for c in order),r.Memory(),"transform")
            self.assertEqual(exact(changed),exact(command))
            self.assertEqual(held.gap,tuple(700-23*t for t in memory.gap))
        self.assertEqual(exact(r.decide(ego,(*rows,car(88,906.,1,0.)),r.Memory(),"transform")),exact((command,memory)))
        blocked=(*rows,car(3,708.,2,0.))
        safe_command,_=r.decide(ego,blocked,r.Memory(),"transform")
        self.assertEqual(r.safe_speed(ego,blocked),gp.safe_speed(ego,blocked))
        self.assertLessEqual(safe_command.speed,r.safe_speed(ego,blocked))


if __name__ == "__main__":
    unittest.main()
