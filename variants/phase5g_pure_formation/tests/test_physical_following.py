"""以真实前车构建跟驰链，跨道对齐不复制邻车的速度。"""

from dataclasses import replace
import unittest

from noa.native_rules import Memory, Vehicle, decide


def car(track, x, lane, speed=28.8):
    return Vehicle(track, x, (lane + 0.5) * 3.3, speed, lane)


class PhysicalFollowingTests(unittest.TestCase):
    def test_nearest_real_front_defines_the_same_lane_distance(self):
        ego = car(0, 100.0, 0)
        rows = [car(1, 145.0, 0), car(2, 190.0, 2), car(3, 130.0, 1), car(4, 175.0, 1)]
        command, _ = decide(ego, rows, Memory(), "formation", None)
        self.assertAlmostEqual(command.target_x, 115.0)

    def test_a_head_does_not_copy_a_stopped_adjacent_cars_speed(self):
        ego = car(0, 100.0, 0)
        command, _ = decide(ego, [car(1, 100.0, 1, 0.0)], Memory(), "formation", None)
        self.assertGreaterEqual(command.speed, 26.8)
        self.assertLessEqual(command.speed, 30.8)

    def test_real_negative_reference_cycle_has_no_cross_lane_speed_feedback(self):
        a = car(0, 682.365, 1, 0.0)
        b = car(1, 655.258, 0, 0.0)
        for ego, other in ((a, b), (replace(b, track=0), replace(a, track=1))):
            command, _ = decide(ego, [other], Memory(), "transform")
            self.assertGreaterEqual(command.speed, 26.8)

    def test_a_join_is_finished_longitudinally_before_another_free_fill(self):
        ego = car(0, 154.827, 0)
        rows = [car(1, 329.59, 0), car(2, 106.27, 0), car(3, 147.81, 2), car(4, 190.27, 2)]
        memory = Memory(joining=True)
        command, memory = decide(ego, rows, memory, "formation", None)
        self.assertIsNone(command.lane)
        self.assertTrue(memory.joining)

    def test_heads_align_the_first_row_instead_of_accepting_a_one_row_offset(self):
        ego = car(0, 700.0, 1)
        rows = [car(1, 715.0, 0), car(2, 685.0, 0), car(3, 655.0, 0)]
        command, _ = decide(ego, rows, Memory(), "transform")
        self.assertAlmostEqual(command.target_x, 730.0)
        self.assertAlmostEqual(command.speed, 30.8)

    def test_entering_a_real_gap_does_not_target_its_rear_car_position(self):
        ego = car(0, 700.0, 0)
        rows = [car(1, 715.0, 1), car(2, 685.0, 1)]
        memory = Memory(lane_target=1, joining=True)
        command, _ = decide(ego, rows, memory, "formation", None)
        self.assertAlmostEqual(command.target_x, 700.0)
        self.assertAlmostEqual(command.speed, 28.8)

    def test_an_ending_follower_can_use_its_own_safe_nonconflicting_gap(self):
        ego = car(0, 670.0, 2)
        rows = [car(1, 700.0, 2), car(2, 685.0, 1), car(3, 655.0, 1), car(4, 700.0, 0), car(5, 670.0, 0)]
        command, _ = decide(ego, rows, Memory(), "transform")
        self.assertEqual(command.lane, 1)

    def test_free_fill_yields_to_a_visible_necessary_merge_in_the_same_corridor(self):
        # 六车19.9s的原生状态：C2仍在640m后，A2已需要合流。
        ego = car(0, 638.1680428294391, 0, 24.706310124799895)
        rows = [
            Vehicle(i + 1, x, y, v, lane, vy)
            for i, (x, y, v, lane, vy) in enumerate(
                (
                    (670.2407335937487, 4.95, 28.8, 1, -3.3),
                    (640.301311460154, 8.25, 29.20071420948352, 2, 0.0),
                    (653.7268887439401, 3.3, 25.9832397458757, 0, -3.3),
                    (623.9575306373935, 4.95, 26.383560086641776, 1, 0.0),
                    (668.3399999999987, 1.65, 26.8, 0, 0.0),
                )
            )
        ]
        command, _ = decide(ego, rows, Memory(), "transform")
        self.assertIsNone(command.lane)
        self.assertNotEqual(command.reason, "fill_layer")

    def test_an_unstarted_free_request_yields_when_a_necessary_merge_arrives(self):
        ego = car(0, 638.0, 0)
        rows = [car(1, 640.0, 2), car(2, 670.0, 1), car(3, 610.0, 1)]
        command, memory = decide(ego, rows, Memory(lane_target=1, joining=True), "transform")
        self.assertIsNone(command.lane)
        self.assertIsNone(memory.lane_target)

    def test_normal_overtaking_also_yields_the_conflicting_mandatory_corridor(self):
        ego = car(0, 638.0, 0, 20.0)
        rows = [car(1, 660.0, 0, 20.0), car(2, 640.0, 2, 20.0)]
        command, _ = decide(ego, rows, Memory(), "noa")
        self.assertIsNone(command.lane)

    def test_a_gap_passed_by_the_car_is_replaced_before_lateral_entry(self):
        # v19原生88.5s：原F/R都已在本车后，不能仍追其后方中点。
        ego = car(0, 684.284, 2, 8.0)
        rows = [car(1, 660.209, 1, 2.0), car(2, 643.585, 1, 0.0), car(3, 703.546, 1, 22.03)]
        memory = Memory(lane_target=1, gap=(1, 2), joining=True)
        command, memory = decide(ego, rows, memory, "transform")
        self.assertGreater(command.target_x, 660.209)
        self.assertGreater(command.speed, 0.0)
        self.assertEqual(memory.gap, (3, 1))

    def test_ordinary_merge_keeps_its_underlying_formation_following(self):
        ego = car(0, 700.0, 0)
        rows = [car(1, 745.0, 0), car(2, 730.0, 1), car(3, 760.0, 2)]
        command, _ = decide(ego, rows, Memory(), "formation")
        self.assertAlmostEqual(command.target_x, 715.0)
        self.assertGreater(command.speed, 28.8)

    def test_ordinary_formation_does_not_fill_an_announced_ending_lane(self):
        ego = car(0, 700.0, 1)
        rows = [
            car(i + 1, x, lane)
            for i, (x, lane) in enumerate(((715.0, 2), (715.0, 1), (685.0, 1), (670.0, 0), (655.0, 0)))
        ]
        command, _ = decide(ego, rows, Memory(), "formation")
        self.assertNotEqual(command.lane, 2)


if __name__ == "__main__":
    unittest.main()
