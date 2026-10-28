"""R5 private state, visible geometry and candidate-gate contracts."""
from dataclasses import asdict, replace
import importlib.util
import json
import math
from pathlib import Path
import unittest
from unittest.mock import patch

from models.bezier import QuadraticLaneChange
from models.kinematic import KinematicModel
from models.vehicle import VehicleState
from noa.contracts import NoaMemory, memory_from_dict
from noa.controller import decide
from noa.road import reconstruct
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import VisibleRoad
from research.common import settings


def road():
    return VisibleRoad((((-300.,0.),(2000.,0.)),((-300.,9.9),(2000.,9.9))),
                       (((-300.,3.3),(2000.,3.3)),((-300.,6.6),(2000.,6.6))))


class R5Tests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('noa.r5'), 'Missing R5 implementation')
        from noa import r5
        self.r5 = r5
        self.model = KinematicModel.from_config()
        self.p = {**self.model.p, **settings('phase4'), **settings('phase5'),
                  **settings('phase5_r5'), 'formation_enabled':True,'noa_target_speed_mps':5.}

    def memory(self, state=1, **kw):
        return NoaMemory((), 'CRUISE', r5_rng_state=state, **kw)

    def control(self, t=0., memory=None, neighbors=((0.,8.25,8.,0.),), speed=8., y=1.65, x=100.):
        own = VehicleState(time_s=t,x_m=x+speed*t,y_m=y,vx_mps=speed)
        targets=[]
        for index,(dx,ny,v,vy) in enumerate(neighbors):
            heading=math.asin(vy/v) if v else 0.
            targets.append(TruthVehicle('alias'+str(index),VehicleState(time_s=t,x_m=own.x_m+dx,
                 y_m=ny,heading_rad=heading,vx_mps=v),4.,1.8))
        c=IdealSensor({**self.model.p,**settings('phase3')},road()).sample('ego',WorldFrame(
            (TruthVehicle('ego',own,4.,1.8),)+tuple(targets)))
        return replace(c,memory=memory or self.memory())

    def assess(self,c,target=4.95):
        r=reconstruct(c.ego,c.observation.road,self.p)
        plan=QuadraticLaneChange(c.ego.time_s,r.current_center_m,target,5.,max(5.,c.ego.vx_mps))
        return self.r5.assess_candidate(c,r,plan,c.memory,self.p)

    def advance(self,c,allow_draw=True):
        return self.r5.advance_backoff(self.assess(c),c.memory,c.ego.time_s,self.p,allow_draw=allow_draw)

    def test_splitmix_vector_pure_and_private(self):
        state,word,u=self.r5.draw_uniform(0)
        self.assertEqual(state,0x9E3779B97F4A7C15)
        self.assertEqual(word,0xE220A8397B1DCDAF)
        self.assertEqual((state,word,u),self.r5.draw_uniform(0))
        other=self.r5.draw_uniform(991)
        self.r5.draw_uniform(state)
        self.assertEqual(other,self.r5.draw_uniform(991))
        for invalid in (None,True,-1,2**64,1.5):
            with self.assertRaises(ValueError):self.r5.draw_uniform(invalid)

    def test_near_simultaneous_uses_one_private_draw_fixed_deadline(self):
        c=self.control()
        self.assertEqual(self.assess(c)['reason'],'ambiguous')
        m,d=self.advance(c)
        deadline=m.r5_deadline_s
        self.assertEqual(m.r5_draw_count,1)
        self.assertEqual(d['draws_this_tick'],1)
        self.assertGreaterEqual(deadline,.5)
        self.assertLess(deadline,2.)
        for index in range(1,101):
            m,d=self.advance(self.control(t=index*.1,memory=m))
            self.assertEqual(m.r5_deadline_s,deadline)
            self.assertEqual(m.r5_draw_count,1)
        self.assertEqual(m.r5_phase,'YIELD')
        self.assertTrue(d['blocking'])
        self.assertEqual(d['reason'],'expired_ambiguous_wait')

    def test_entered_precedes_gap_front_rear_and_overlap(self):
        for dx in (-5.,0.,5.):
            with self.subTest(dx=dx):
                a=self.assess(self.control(neighbors=((dx,7.4,8.,0.),)))
                self.assertEqual(a['reason'],'yield_entered')

    def test_contact_and_inward_units_and_false_positive_release(self):
        self.assertNotEqual(self.assess(self.control(neighbors=((0.,7.5,8.,0.),)))['reason'],'yield_entered')
        for vy,expected in ((-.051,'yield_visible_inward_motion'),(-.05,'ambiguous'),(-.049,'ambiguous')):
            with self.subTest(vy=vy):
                self.assertEqual(self.assess(self.control(neighbors=((0.,8.25,8.,vy),)))['reason'],expected)

    def test_front_priority_tolerance_is_geometric_and_not_alias(self):
        for dx,expected in ((2.0001,'yield_visible_front'),(2.,'ambiguous'),(-2.0001,'ego_visible_front')):
            self.assertEqual(self.assess(self.control(neighbors=((dx,8.25,8.,0.),)))['reason'],expected)
        self.assertEqual(self.assess(self.control(neighbors=((7.3001,8.25,8.,0.),)))['reason'],'no_potential_competition')

    def test_json_roundtrip_and_invalid_private_schema(self):
        m,_=self.advance(self.control())
        restored=memory_from_dict(json.loads(json.dumps(asdict(m))))
        self.assertEqual(m,restored)
        self.assertEqual(self.advance(self.control(t=.1,memory=m)),self.advance(self.control(t=.1,memory=restored)))
        for field,value in (('r5_rng_state',True),('r5_rng_state',2**64),('r5_draw_count',-1),
                            ('r5_deadline_s',float('nan')),('r5_phase','SECRET'),('r5_last_time_s',100.)):
            with self.subTest(field=field),self.assertRaises(ValueError):
                decide(self.control(memory=replace(m,**{field:value})),self.p)

    def test_yield_overlay_preserves_deadline_and_draw_latch(self):
        m,_=self.advance(self.control())
        deadline=m.r5_deadline_s
        m,_=self.advance(self.control(t=.1,memory=m,neighbors=((0.,8.245,8.,-.06),)))
        self.assertEqual(m.r5_phase,'YIELD')
        self.assertEqual(m.r5_deadline_s,deadline)
        m,_=self.advance(self.control(t=.2,memory=m))
        self.assertEqual(m.r5_draw_count,1)
        self.assertEqual(m.r5_deadline_s,deadline)

    def test_only_yield_updates_without_consuming_random(self):
        m,d=self.advance(self.control(neighbors=((5.,8.25,8.,0.),)))
        self.assertEqual(m.r5_phase,'YIELD')
        self.assertEqual(m.r5_draw_count,0)
        self.assertIsNone(m.r5_deadline_s)
        self.assertEqual(d['draws_this_tick'],0)

    def test_clear_then_reentry_draws_once_more(self):
        m,_=self.advance(self.control())
        for index in range(1,13):
            m,_=self.advance(self.control(t=index*.1,memory=m,neighbors=()))
        self.assertEqual(m.r5_phase,'IDLE')
        m,_=self.advance(self.control(t=1.3,memory=m))
        self.assertEqual(m.r5_draw_count,2)

    def test_missing_frame_and_duplicate_physical_matching_are_unknown(self):
        m,_=self.advance(self.control())
        deadline=m.r5_deadline_s
        m,_=self.advance(self.control(t=.5,memory=m))
        self.assertEqual(m.r5_phase,'UNKNOWN')
        self.assertEqual(m.r5_deadline_s,deadline)
        fresh,_=self.advance(self.control())
        m,_=self.advance(self.control(t=.1,memory=fresh,neighbors=((0.,8.25,8.,0.),(.1,8.25,8.,0.))))
        self.assertEqual(m.r5_phase,'UNKNOWN')
        self.assertEqual(m.r5_draw_count,1)

    def test_label_order_translation_and_hidden_plan_indifference(self):
        c=self.control(neighbors=((0.,8.25,8.,0.),(40.,4.95,8.,0.)))
        a=self.assess(c)
        n=tuple(replace(v,track_id='renamed'+str(i)) for i,v in enumerate(reversed(c.observation.neighbors)))
        changed=replace(c,observation=replace(c.observation,neighbors=n))
        self.assertEqual(a,self.assess(changed))
        shifted=self.assess(self.control(x=200.,neighbors=((0.,8.25,8.,0.),(40.,4.95,8.,0.))))
        self.assertEqual(a['reason'],shifted['reason'])
        self.assertEqual(self.advance(c)[0].r5_deadline_s,self.advance(self.control(x=200.,neighbors=((0.,8.25,8.,0.),(40.,4.95,8.,0.))))[0].r5_deadline_s)

    def test_decide_off_retains_old_actions_and_rng(self):
        c=self.control(neighbors=())
        d=decide(c,{**self.p,'r5_enabled':False})
        old=decide(replace(c,memory=NoaMemory((),'CRUISE')),{**self.p,'r5_enabled':False})
        self.assertEqual(d.action,old.action)
        self.assertEqual(d.memory.r5_rng_state,1)
        self.assertEqual(d.memory.r5_draw_count,0)

    def test_candidate_gate_yield_guard_and_formation_cannot_add_back(self):
        # Own slow lead supplies genuine NOA motivation; opposite outer car is
        # only a potential competitor, not a supplied hidden intent.
        c=self.control(neighbors=((35.,1.65,3.,0.),(0.,8.25,8.,0.)))
        checks=[]
        def guard(control,plan,road,accel,p):
            checks.append((plan.y_start_m,plan.y_target_m,accel))
            return dict(safe=True,reason='unit_gate_stub',at_s=None,checked_s=5.5)
        with patch('noa.controller.verify_candidate',side_effect=guard):
            d=decide(c,self.p)
        self.assertIsNone(d.memory.plan)
        self.assertEqual(d.memory.r5_phase,'BACKOFF')
        self.assertLessEqual(d.action.acceleration_mps2,-.5)
        self.assertTrue(checks)
        self.assertTrue(all(a==b for a,b,_ in checks))
        from noa.formation import FormationMemory,decide as formation
        fm=FormationMemory(**asdict(c.memory))
        with patch('noa.controller.verify_candidate',side_effect=guard):
            result=formation(replace(c,memory=fm),self.p)
        self.assertEqual(result.diagnostics['formation']['applied_increment_mps2'],0.)

    def test_deadline_expires_while_clear_is_still_being_confirmed(self):
        m,_=self.advance(self.control())
        for index in range(1,14):m,_=self.advance(self.control(t=index*.1,memory=m))
        self.assertLess(1.3,m.r5_deadline_s)
        m,d=self.advance(self.control(t=1.4,memory=m,neighbors=()))
        self.assertEqual(m.r5_phase,'ELIGIBLE')
        self.assertEqual(m.r5_draw_count,1)
        self.assertIsNotNone(m.r5_clear_since_s)

    def test_backoff_ego_front_ambiguous_preserves_promised_wait(self):
        m,_=self.advance(self.control(neighbors=((-1.99,8.25,8.,0.),)))
        deadline=m.r5_deadline_s
        m,d=self.advance(self.control(t=.1,memory=m,neighbors=((-2.01,8.25,8.,0.),)))
        self.assertEqual(m.r5_phase,'BACKOFF')
        self.assertTrue(d['blocking'])
        m,d=self.advance(self.control(t=.2,memory=m,neighbors=((-1.99,8.25,8.,0.),)))
        self.assertEqual((m.r5_deadline_s,m.r5_draw_count),(deadline,1))

    def test_expiry_below_minimum_speed_is_not_plan_eligibility(self):
        m,_=self.advance(self.control(neighbors=((-1.99,8.25,8.,0.),)))
        deadline=m.r5_deadline_s
        for index in range(1,31):
            c=self.control(t=index*.1,memory=m,speed=4.9,neighbors=((-2.01,8.25,4.9,0.),))
            with patch('noa.controller.verify_candidate',return_value=dict(safe=False,reason='unit_declined',at_s=0.,checked_s=0.)):
                d=decide(c,self.p)
            m=d.memory
        self.assertEqual(m.r5_phase,'ELIGIBLE')
        self.assertEqual(d.diagnostics['r5']['assessment']['reason'],'ego_visible_front')
        self.assertEqual((m.r5_deadline_s,m.r5_draw_count),(deadline,1))
        self.assertIsNone(m.plan)
        self.assertGreater(d.action.acceleration_mps2,0.)

    def test_rejected_yield_keeps_original_fallback_and_failure_evidence(self):
        c=self.control(neighbors=((35.,1.65,3.,0.),(0.,8.25,8.,0.)))
        reject=dict(safe=False,reason='neighbor_reachable_occupancy',at_s=.01,checked_s=.01)
        with patch('noa.controller.verify_candidate',return_value=reject):
            old=decide(c,{**self.p,'r5_enabled':False})
            d=decide(c,self.p)
        self.assertEqual(d.action,old.action)
        self.assertIsNone(d.memory.plan)
        self.assertEqual(d.diagnostics['r5']['reason'],'yield_not_certified')
        self.assertEqual(d.diagnostics['r5']['guard'],reject)

    def test_active_plan_is_not_cleared_or_steering_zeroed(self):
        plan=QuadraticLaneChange(0.,1.65,4.95,5.,8.)
        c=self.control(t=1.,y=plan.at(1.)['y_m'],memory=self.memory(plan=plan,target_y_m=plan.y_target_m))
        reject=dict(safe=False,reason='unit_active_blockage',at_s=.01,checked_s=.01)
        with patch('noa.controller.verify_candidate',return_value=reject):
            d=decide(c,self.p)
            old=decide(c,{**self.p,'r5_enabled':False})
        self.assertEqual(d.action,old.action)
        self.assertEqual(d.memory.plan,plan)
        self.assertNotEqual(d.action.steering_rad,0.)
        self.assertEqual(d.diagnostics['r5']['reason'],'active_plan_bypass')
        self.assertEqual(d.memory.r5_draw_count,0)

    def test_expired_guard_blockage_does_not_restart_timer(self):
        m=self.memory()
        reject=dict(safe=False,reason='unit_declined',at_s=.01,checked_s=.01)
        deadline=None
        with patch('noa.controller.verify_candidate',return_value=reject):
            for index in range(31):
                dx=-1.99 if index==0 else -2.01
                d=decide(self.control(t=index*.1,memory=m,neighbors=((35.,1.65,3.,0.),(dx,8.25,8.,0.))),self.p)
                m=d.memory
                deadline=m.r5_deadline_s if deadline is None else deadline
                self.assertEqual(m.r5_deadline_s,deadline)
        self.assertEqual(d.diagnostics['r5']['reason'],'expired_but_guard_blocked')
        self.assertEqual(d.diagnostics['r5']['assessment']['reason'],'ego_visible_front')
        self.assertEqual(d.diagnostics['r5']['candidate_guard'],reject)
        self.assertEqual(m.r5_draw_count,1)
        self.assertIsNone(m.plan)

    def test_visible_front_release_retains_prepare_and_behavior_tick_requirements(self):
        # Inherited private states; now release also requires visible ego-front.
        started=[]
        deadlines=[]
        accept=dict(safe=True,reason='unit_gate_stub',at_s=None,checked_s=5.5)
        for seed in (1,2):
            m=self.memory(seed)
            with patch('noa.controller.verify_candidate',return_value=accept):
                for index in range(41):
                    dx=-1.99 if index==0 else -2.01
                    d=decide(self.control(t=index*.1,memory=m,neighbors=((35.,1.65,3.,0.),(dx,8.25,8.,0.))),self.p)
                    m=d.memory
                    if m.plan is not None:
                        self.assertEqual(d.diagnostics['r5']['assessment']['reason'],'ego_visible_front')
                        self.assertGreaterEqual(m.prepare_since_s,m.r5_deadline_s-1e-9)
                        self.assertGreaterEqual(m.plan.start_s-m.prepare_since_s,self.p['noa_prepare_duration_s']-1e-9)
                        self.assertAlmostEqual(m.plan.start_s/self.p['behavior_dt_s'],round(m.plan.start_s/self.p['behavior_dt_s']))
                        deadlines.append(m.r5_deadline_s)
                        started.append(m.plan.start_s)
                        break
        self.assertEqual(len(started),2)
        self.assertNotEqual(deadlines[0],deadlines[1])
        self.assertEqual(started[0],started[1])

    def test_emergency_braking_is_not_clipped_back_to_comfort(self):
        c=self.control(neighbors=((5.,1.65,0.,0.),(0.,8.25,8.,0.)))
        d=decide(c,self.p)
        self.assertEqual(d.memory.own_behavior,'EMERGENCY')
        self.assertEqual(d.action.acceleration_mps2,self.p['min_accel_mps2'])

    def test_unknown_does_not_revive_stale_signature_as_previous_frame(self):
        m,_=self.advance(self.control())
        deadline=m.r5_deadline_s
        m,_=self.advance(self.control(t=.5,memory=m))
        self.assertEqual(m.r5_phase,'UNKNOWN')
        # A near-old position can be compatible with one short interval even
        # though the retained signature actually precedes the missing frames.
        m,d=self.advance(self.control(t=.6,memory=m,x=96.))
        self.assertEqual(m.r5_phase,'UNKNOWN')
        self.assertEqual((m.r5_deadline_s,m.r5_draw_count),(deadline,1))
        self.assertTrue(d['blocking'])

    def test_unique_gap_anchor_role_change_creates_new_episode(self):
        # This is the association/state contract, not a physical traffic case.
        c=self.control()
        a=self.assess(c)
        anchor=(130.,4.95,0.,0.,0.,4.,1.8)
        old={**a,'episode_signature':(a['target_y_m'],None,anchor,a['participant_signatures'])}
        m,_=self.r5.advance_backoff(old,c.memory,0.,self.p)
        fresh=self.assess(self.control(t=.1,memory=m))
        swapped={**fresh,'episode_signature':(fresh['target_y_m'],anchor,None,fresh['participant_signatures'])}
        m,d=self.r5.advance_backoff(swapped,m,.1,self.p)
        self.assertEqual(m.r5_phase,'BACKOFF')
        self.assertEqual(m.r5_draw_count,2)
        self.assertEqual(d['draws_this_tick'],1)

    def test_waiting_target_does_not_block_another_clear_safe_candidate(self):
        neighbors=((35.,4.95,3.,0.),(0.,8.25,8.,0.))
        reject=dict(safe=False,reason='unit_first_blocked',at_s=0.,checked_s=0.)
        with patch('noa.controller.verify_candidate',return_value=reject):
            first=decide(self.control(y=4.95,neighbors=neighbors),self.p)
        self.assertEqual(first.memory.r5_phase,'YIELD')
        self.assertAlmostEqual(first.memory.r5_episode_signature[0],8.25)
        calls=[]
        def accepting(control,plan,road,accel,p):
            calls.append(plan.y_target_m)
            return dict(safe=True,reason='unit_second_clear',at_s=None,checked_s=5.5)
        with patch('noa.controller.verify_candidate',side_effect=accepting):
            second=decide(self.control(t=.1,y=4.95,memory=first.memory,neighbors=neighbors),self.p)
        self.assertTrue(any(abs(y-1.65)<1e-7 for y in calls))
        self.assertEqual(second.memory.own_behavior,'PREPARE_LC')
        self.assertAlmostEqual(second.memory.target_y_m,1.65)
        self.assertEqual(second.memory.r5_phase,'IDLE')
        self.assertEqual(second.memory.r5_draw_count,0)

    def test_phase_deadline_is_consistent_at_its_stored_memory_time(self):
        m,_=self.advance(self.control())
        invalid=(replace(m,r5_deadline_s=-1.),
                 replace(m,r5_last_time_s=.1,r5_deadline_s=.05),
                 replace(m,r5_phase='ELIGIBLE',r5_last_time_s=0.,r5_deadline_s=.05),
                 replace(m,r5_last_time_s=None),
                 replace(m,r5_clear_since_s=.2,r5_last_time_s=.1),
                 self.memory(r5_clear_since_s=0.))
        for memory in invalid:
            with self.subTest(memory=memory),self.assertRaises(ValueError):
                memory_from_dict(json.loads(json.dumps(asdict(memory))))
        # Valid previous BACKOFF is allowed to cross its deadline at the next
        # input; consistency is checked at stored time, not at current now.
        last=replace(m,r5_last_time_s=1.3,r5_deadline_s=1.35,
            r5_episode_signature=self.assess(self.control(t=1.3))['episode_signature'])
        restored=memory_from_dict(json.loads(json.dumps(asdict(last))))
        ended,diagnostic=self.advance(self.control(t=1.4,memory=restored))
        self.assertEqual(ended.r5_phase,'YIELD')
        self.assertTrue(diagnostic['blocking'])
        self.assertEqual(diagnostic['reason'],'expired_ambiguous_wait')


if __name__=='__main__':
    unittest.main()
