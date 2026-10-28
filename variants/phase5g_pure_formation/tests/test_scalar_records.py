"""不可变数值记录的读取顺序；用于避免仿真中的递归复制。"""

import unittest
from models.vehicle import VehicleState, Actuation


class ScalarRecordTests(unittest.TestCase):
    def test_state_and_action_values_preserve_all_fields(self):
        from models.records import scalar_values
        state = VehicleState(1.,2.,3.,4.,5.,6.,7.,8.,9.)
        self.assertEqual(scalar_values(state),(1.,2.,3.,4.,5.,6.,7.,8.,9.))
        self.assertEqual(scalar_values(Actuation(-3.,.1)),(-3.,.1))


if __name__=="__main__":
    unittest.main()
