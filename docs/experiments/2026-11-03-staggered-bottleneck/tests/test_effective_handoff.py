"""Narrow effective-handoff contracts; default target is the frozen TM baseline."""
from dataclasses import asdict
import importlib.util
import os
from pathlib import Path
import random
import subprocess
import sys
import types
import unittest


REPO = Path(__file__).resolve().parents[4]
BASE = "177f7a32088fb69efcc94d9acb72863e7e00e787"
NAME = "variants/phase5g_pure_formation/noa/native_rules.py"
baseline = types.ModuleType("handoff_frozen_tm")
sys.modules[baseline.__name__] = baseline
exec(compile(subprocess.check_output(["git", "show", BASE + ":" + NAME], cwd=REPO),
             BASE + ":" + NAME, "exec"), baseline.__dict__)
rules = baseline
if os.environ.get("RULES_PATH"):
    spec = importlib.util.spec_from_file_location("effective_handoff_rules", os.environ["RULES_PATH"])
    rules = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = rules
    spec.loader.exec_module(rules)


class EffectiveHandoffTests(unittest.TestCase):
    def car(self, track, x, lane, speed=28.8, module=rules):
        return module.Vehicle(track, x, (lane + .5) * module.LANE_WIDTH, speed, lane)

    def scene(self, helper_x=700.0):
        head = self.car(1, 700, 2)
        return head, (self.car(2, helper_x, 1), self.car(3, 730, 1), self.car(4, 750, 0))

    def test_do_not_move_a_helper_when_head_already_has_a_clear_gap(self):
        head, rows = self.scene(710)
        self.assertTrue(rules._clear(head, rows, 1))
        self.assertIsNone(rules._make_room(head, rows)[1])

    def test_helper_must_have_an_immediately_clear_left_corridor(self):
        head, rows = self.scene()
        rows += (self.car(5, 700, 0), self.car(6, 670, 2))
        self.assertFalse(rules._clear(rows[0], (head, *rows), 0))
        self.assertIsNone(rules._make_room(head, rows)[1])

    def test_vacating_the_helper_must_actually_release_head_corridor(self):
        head, rows = self.scene()
        rows += (self.car(5, 694, 1),)
        self.assertFalse(rules._clear(head, tuple(c for c in rows if c.track != 2), 1))
        self.assertIsNone(rules._make_room(head, rows)[1])

    def test_skip_a_more_forward_helper_whose_departure_would_not_help(self):
        head, rows = self.scene()
        rows += (self.car(5, 710, 1),)
        helper = rules._make_room(head, rows)[1]
        self.assertIsNotNone(helper)
        self.assertEqual(helper.track, 2)

    def test_keep_an_effective_vacancy_handoff(self):
        head, rows = self.scene()
        self.assertFalse(rules._clear(head, rows, 1))
        helper = rules._make_room(head, rows)[1]
        self.assertEqual(helper.track, 2)
        self.assertTrue(rules._clear(helper, (head, *rows), 0))
        self.assertTrue(rules._clear(head, tuple(c for c in rows if c.track != helper.track), 1))

    def test_handoff_waits_for_observed_vacancy(self):
        head, rows = self.scene()
        command, _ = rules.decide(head, rows, rules.Memory(), "transform")
        self.assertIsNone(command.lane)
        released = tuple(c for c in rows if c.track != 2)
        command, _ = rules.decide(head, released, rules.Memory(), "transform")
        self.assertEqual(command.lane, 1)

    def test_track_relabeling_order_and_remote_cars_do_not_change_helper_position(self):
        head, rows = self.scene()
        rows += (self.car(5, 710, 1),)
        expected = rules._make_room(head, rows)[1]
        relabeled = tuple(self.car(1009 - 17 * i, c.x, c.lane, c.speed)
                          for i, c in enumerate((head, *rows)))
        remote = (self.car(8008, 1600, 0), self.car(9011, 1700, 2))
        actual = rules._make_room(relabeled[0], (*remote, *reversed(relabeled[1:])))[1]
        self.assertEqual((actual.x, actual.lane), (expected.x, expected.lane))

    def test_noa_commands_and_private_memory_equal_frozen_tm(self):
        rng = random.Random(20261103)
        for _ in range(300):
            lane = rng.randrange(3)
            x = rng.uniform(630, 1010)
            values = [(0, x, lane, rng.uniform(0, 33.3))]
            values += [(i, x + rng.uniform(-130, 230), rng.randrange(3), rng.uniform(0, 33.3))
                       for i in range(1, 10)]
            observations = [[self.car(*v, module=m) for v in values] for m in (rules, baseline)]
            actual = rules.decide(observations[0][0], observations[0][1:], rules.Memory(), "noa")
            expected = baseline.decide(observations[1][0], observations[1][1:], baseline.Memory(), "noa")
            self.assertEqual(tuple(map(asdict, actual)), tuple(map(asdict, expected)))


if __name__ == "__main__":
    unittest.main()
