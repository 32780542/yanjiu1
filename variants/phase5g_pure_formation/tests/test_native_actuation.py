"""Shared normal acceleration shaping never delays an active safety brake."""

import unittest

from experiments import native_sumo as native


class NativeActuationTests(unittest.TestCase):
    def test_normal_acceleration_request_is_limited_per_physical_step(self):
        self.assertAlmostEqual(
            native.execution_speed(20.0, 33.3, 33.3),
            20.0 + native.REQUEST_ACCELERATION * native.STEP,
        )

    def test_a_lower_safety_speed_is_applied_without_smoothing(self):
        self.assertAlmostEqual(native.execution_speed(20.0, 28.8, 5.0), 5.0)

    def test_a_normal_deceleration_is_shaped_but_safety_can_override_it(self):
        self.assertAlmostEqual(
            native.execution_speed(20.0, 12.0, 33.3),
            20.0 - native.REQUEST_DECELERATION * native.STEP,
        )

    def test_the_vehicle_capability_remains_the_matlab_value(self):
        self.assertEqual(native.PHYSICAL["accel"], 5.0)


if __name__ == "__main__":
    unittest.main()
