"""Fixed before heldout execution: C1_P must match old C1_H active local behavior."""
import ast
from dataclasses import asdict, fields
import importlib.util
from pathlib import Path
import sys
import unittest

from noa import native_rules as c
from experiments.native_sumo import MODES

ROOT = Path(__file__).resolve().parents[2]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module
old = load("old_C1_H", ROOT / "tmp/H_strict_formation_ablation/noa/native_rules.py")
p = load("frozen_P", ROOT / "tmp/common_pair_P_release/noa/native_rules.py")

STATES = (
    ((700,2,28.8,None),(670,2,28.8,None),(685,1,28.8,None),(655,1,28.8,None),(700,0,28.8,None),(670,0,28.8,None)),
    ((639.9,0,20,None),(659.9,0,20,None)),
    ((640.0,0,20,None),(660.0,0,20,None)),
    ((640.1,0,20,None),(660.1,0,20,None)),
    ((999.9,2,0,None),(980,1,20,None),(1010,1,28.8,None)),
    ((1000.0,2,5,None),(990,1,28.8,None),(1030,1,20,None)),
    ((1000.1,1,20,None),(1020,1,20,None),(990,0,28.8,None)),
    ((700,1,28.8,0),(715,0,20,None),(680,0,28.8,None)),
)

def make(mod, values, index):
    cars = [mod.Vehicle(i,x,(lane+.5)*3.3,speed,lane,pending_lane=pending) for i,(x,lane,speed,pending) in enumerate(values)]
    return cars[index], tuple(car for i,car in enumerate(cars) if i != index)

def action(mod, values, index, memory=None, mode="cooperative", drop=1000.0):
    ego, rows = make(mod, values, index)
    command, saved = mod._decide(ego, rows, memory if memory is not None else mod.Memory(), mode, drop)
    return asdict(command), asdict(saved)


class C1PTests(unittest.TestCase):
    def ready(self): self.assertIn("cooperative", MODES, "C1_P explicit engine mode is not yet added")

    def test_actual_mode_is_explicit(self): self.ready()

    def test_all_fixed_local_actions_and_memories_match_old_C1_H(self):
        self.ready()
        for values in STATES:
            for index in range(len(values)):
                with self.subTest(values=values,index=index):
                    self.assertEqual(action(c,values,index),action(old,values,index))

    def test_held_gap_and_pending_memory_match_old_C1_H(self):
        self.ready()
        values=STATES[0]
        for index in range(len(values)):
            for target in (0,1,2):
                cm=c.Memory(lane_target=target,gap=(None,None),joining=True)
                om=old.Memory(lane_target=target,gap=(None,None),joining=True)
                self.assertEqual(action(c,values,index,cm),action(old,values,index,om))

    def test_new_pair_follow_and_fill_are_never_executed(self):
        self.ready()
        calls=[]
        def profile(frame,event,arg):
            if event=="call" and frame.f_code.co_filename==c.__file__ and frame.f_code.co_name in ("_following","_pair_error","_fill"):
                calls.append(frame.f_code.co_name)
        before=sys.getprofile();sys.setprofile(profile)
        try:
            for values in STATES:
                for index in range(len(values)): action(c,values,index)
        finally:sys.setprofile(before)
        self.assertEqual(calls,[])

    def test_NOA_overtake_preserved_cooperative_overtake_disabled(self):
        self.ready();values=((700,0,20,None),(720,0,20,None))
        self.assertEqual(action(c,values,0,mode="noa"),action(old,values,0,mode="noa"))
        self.assertEqual(action(c,values,0,mode="noa")[0]["reason"],"normal_overtake")
        self.assertEqual(action(c,values,0)[0]["reason"],"cooperative_follow")

    def test_complete_straight_delegation_is_the_same_NOA_decision(self):
        self.ready()
        for values in STATES:
            for index in range(len(values)):
                self.assertEqual(action(c,values,index,drop=None),action(old,values,index,drop=None))
                self.assertEqual(action(c,values,index,drop=None),action(p,values,index,mode="noa",drop=None))

    def test_no_Memory_or_parameter_addition(self):
        self.assertEqual([(f.name,str(f.type)) for f in fields(c.Memory)],[(f.name,str(f.type)) for f in fields(old.Memory)])
        names=("CRUISE","MAX_SPEED","GAP","POSITION_GAIN","BRAKING","RESPONSE","CLEARANCE","LANE_WIDTH")
        self.assertEqual({n:getattr(c,n) for n in names},{n:getattr(old,n) for n in names})

    def test_helpers_safety_and_common_guards_are_byte_AST_identical(self):
        def nodes(mod):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(Path(mod.__file__).read_text(encoding="utf-8")).body if isinstance(n,ast.FunctionDef)}
        cn,pn,on=nodes(c),nodes(p),nodes(old)
        for name in ("_make_room","_receiving","_receiving_distance","_merge_target","_join_speed","_mandatory_priority","_clear","safe_speed","_occupies"):
            self.assertEqual(cn[name],pn[name]);self.assertEqual(cn[name],on[name])


if __name__=="__main__":unittest.main(verbosity=2)
