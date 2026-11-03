"""Instrument real calls to check scoring/execution with a lateral offset."""
from dataclasses import replace
import os
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode=True
if 'RULES_D_SELF' in os.environ:os.environ['RULES_D']=os.environ['RULES_D_SELF']
else:os.environ['RULES_D']=str(Path(__file__).resolve().parents[4]/'tmp/staggered_bottleneck/candidates/midflow_real_gap_balance/native_rules.py')
from test_real_gap_balance import r,receiving_scene


class SelfExclusionTests(unittest.TestCase):
    def test_real_gap_scoring_excludes_the_candidate_itself_even_with_lateral_offset(self):
        ego,rows=receiving_scene()
        ego=replace(ego,y=3.3,vy=0.)
        self.assertTrue(r._occupies(ego,0))
        original=r._merge_target
        calls=[]
        def observed_call(car,visible,lane,held=None):
            result=original(car,visible,lane,held)
            if car.track==ego.track and lane==0:calls.append(result)
            return result
        r._merge_target=observed_call
        try:command,memory=r.decide(ego,rows,r.Memory(),'transform')
        finally:r._merge_target=original
        self.assertEqual(command.lane,0)
        self.assertGreaterEqual(len(calls),2)
        self.assertEqual(calls[0][0],command.target_x)
        self.assertEqual(calls[0][2],memory.gap)
        self.assertEqual(calls[-1][0],command.target_x)


if __name__=='__main__':unittest.main()
