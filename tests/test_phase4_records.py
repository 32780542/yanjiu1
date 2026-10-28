import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class Phase4RecordsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('simulation.noa_clock'), 'Phase4 clock absent')
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase4'), 'Phase4 runner absent')
        from research.common import ROOT, settings
        from models.kinematic import KinematicModel, kinematic_state
        from dataclasses import asdict
        self.root, self.model = ROOT, KinematicModel.from_config()
        self.p = {**dict(self.model.p), **settings('phase3'), **settings('phase4_experiments')}
        self.policy = {**dict(self.model.p), **settings('phase4')}
        self.case = {'name':'fixture','duration_s':.3,'controlled':['ego'],
                     'initial':{key:asdict(kinematic_state(self.model.p,x_m=x,y_m=1.65,vx_mps=v))
                                for key,x,v in [('ego',300,15),('front',370,13)]},
                     'scripts':{'front':{'speed_steps':[[0,13]]}},
                     'requirements':{},'purpose':'Short replay regression', 'stress':False}

    def fixture(self,path,case=None,live=False):
        from experiments.phase4 import run_case
        result = run_case(path,self.model,self.p,self.policy,case or self.case,live=live)
        self.assertEqual(result['status'],'completed',result)
        self.assertTrue(result['recording_passed'],result)
        meta=json.loads((path/'metadata.json').read_text())
        self.assertEqual(meta['completed_intervals'],meta['intervals'])
        self.assertEqual(meta['physical_intervals'],meta['intervals'])
        self.assertFalse(meta['partial_tail'])
        return meta, [json.loads(line) for line in (path/'trace.jsonl').read_text().splitlines()]

    def test_same_clock_and_reverse_call_order_produce_identical_trace(self):
        from simulation.noa_clock import NoaClock
        from models.vehicle import VehicleState
        from perception.road import VisibleRoad
        from dataclasses import asdict
        road = VisibleRoad.from_net('scenarios/cai2024/bottleneck.net.xml')
        initial = {key:VehicleState(**s) for key,s in self.case['initial'].items()}
        clocks = [NoaClock(initial,self.model,road,self.p,self.policy,['ego'],self.case['scripts']) for _ in range(2)]
        for _ in range(3):
            normal=clocks[0].tick()
            reverse=clocks[1].tick(order=['front','ego'])
            self.assertEqual(normal,reverse)
            self.assertEqual(set(normal['inputs']),{'ego'})
            self.assertEqual(set(normal['actions']),set(initial))
            self.assertTrue(all(s['time_s']==normal['inputs']['ego']['ego']['time_s'] for s in normal['initial'].values()))

    def test_missing_vehicle_order_fails_and_instance_cannot_resume(self):
        from simulation.noa_clock import NoaClock
        from models.vehicle import VehicleState
        from perception.road import VisibleRoad
        clock=NoaClock({k:VehicleState(**v) for k,v in self.case['initial'].items()},self.model,
                       VisibleRoad.from_net('scenarios/cai2024/bottleneck.net.xml'),self.p,self.policy,['ego'],self.case['scripts'])
        with self.assertRaises(ValueError):
            clock.tick(order=['ego'])
        self.assertEqual(clock.last_record['status'],'failed')
        with self.assertRaises(RuntimeError):
            clock.tick()

    def test_saved_substep_diagnostics_are_calculated_once_and_sorted_without_recomputation(self):
        from simulation.noa_clock import NoaClock
        from models.vehicle import VehicleState
        from perception.road import VisibleRoad
        initial={key:VehicleState(**state) for key,state in self.case['initial'].items()}
        clock=NoaClock(initial,self.model,VisibleRoad.from_net('scenarios/cai2024/bottleneck.net.xml'),
                       self.p,self.policy,['ego'],self.case['scripts'])
        advance,observe=self.model.advance,self.model.observe
        samples,counts,captured={},{},{}
        def record_returned_samples(state,*args):
            step=advance(state,*args)
            key=next(key for key,value in initial.items() if value is state)
            for index,sample in enumerate(step.samples):
                samples[id(sample)]=(key,index)
                counts[key,index]=0
            return step
        def count_diagnostics(state):
            report=observe(state)
            if id(state) in samples:
                key=samples[id(state)]
                counts[key]+=1
                captured[key]=report
            return report
        with patch.object(self.model,'advance',side_effect=record_returned_samples),patch.object(self.model,'observe',side_effect=count_diagnostics):
            row=clock.tick(order=['front','ego'])
        self.assertEqual(len(counts),len(initial)*round(self.p['control_sync_dt_s']/self.p['dynamics_dt_s']))
        self.assertTrue(all(count==1 for count in counts.values()),counts)
        self.assertEqual(list(row['diagnostics']),sorted(initial))
        for (key,index),report in captured.items():
            self.assertIs(row['diagnostics'][key][index],report)

    def test_real_diagnostics_interrupt_retains_steps_and_replays_the_partial_tail(self):
        from experiments.phase4 import run_case
        from experiments.phase4_replay import replay_case,replay_isolation
        advance,observe=self.model.advance,self.model.observe
        pending,triggered=[None],[0]
        def track_diagnostic_boundary(state,*args):
            step=advance(state,*args)
            if state.time_s>=.099 and state.x_m>350:
                pending[0]=step.samples[1]
            return step
        def interrupt_diagnostics(state):
            if state is pending[0] and not triggered[0]:
                triggered[0]+=1
                raise KeyboardInterrupt('real returned-step diagnostic interruption')
            return observe(state)
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path=Path(tmp)/'diagnostics'
            with patch.object(self.model,'advance',side_effect=track_diagnostic_boundary),patch.object(self.model,'observe',side_effect=interrupt_diagnostics):
                with self.assertRaisesRegex(KeyboardInterrupt,'returned-step diagnostic'):
                    run_case(path,self.model,self.p,self.policy,self.case,live=False)
            self.assertEqual(triggered[0],1)
            meta=json.loads((path/'metadata.json').read_text())
            rows=[json.loads(line) for line in (path/'trace.jsonl').read_text().splitlines()]
            result=json.loads((path/'validation.json').read_text())
            self.assertEqual(len(rows),2)
            self.assertEqual(set(rows[-1]['steps']),{'ego','front'})
            self.assertEqual(set(rows[-1]['diagnostics']),{'ego'})
            self.assertEqual(meta['failure_stage'],'diagnostics')
            self.assertEqual(meta['failure_actor'],'front')
            self.assertEqual(meta['physical_intervals'],1)
            self.assertTrue(meta['partial_tail'])
            self.assertTrue(result['recording_passed'],result)
            self.assertFalse(result['driving_passed'])
            self.assertTrue(replay_case(meta,path/'trace.jsonl')['passed'])
            self.assertTrue(replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')['passed'])

    def test_later_actor_exception_preserves_earlier_computed_decision(self):
        from simulation.noa_clock import NoaClock
        from noa.controller import decide
        from models.vehicle import VehicleState
        from perception.road import VisibleRoad
        clock=NoaClock({k:VehicleState(**v) for k,v in self.case['initial'].items()},self.model,
                       VisibleRoad.from_net('scenarios/cai2024/bottleneck.net.xml'),self.p,self.policy,['ego','front'],{})
        def injected(control,parameters):
            if control.ego.x_m==self.case['initial']['front']['x_m']:
                raise RuntimeError('second actor fault')
            return decide(control,parameters)
        with patch('simulation.noa_clock.decide',side_effect=injected):
            with self.assertRaisesRegex(RuntimeError,'second actor'):
                clock.tick()
        self.assertEqual(set(clock.last_record['inputs']),{'ego','front'})
        self.assertIn('ego',clock.last_record.get('decisions',{}))
        self.assertNotIn('front',clock.last_record.get('decisions',{}))

    def partial_failure(self,path,stage,error=RuntimeError):
        from experiments.phase4 import run_case
        from noa.controller import decide
        case=copy.deepcopy(self.case)
        case.update(controlled=['ego','front'],scripts={})
        case['initial']['front']['y_m']=4.95
        advance=self.model.advance
        def decision(control,parameters):
            if control.ego.time_s>=.099 and control.ego.x_m>350:
                raise error('second actor decision fault')
            return decide(control,parameters)
        def integration(state,*args):
            if state.time_s>=.099 and state.x_m>350:
                raise error('second actor integration fault')
            return advance(state,*args)
        target=patch('simulation.noa_clock.decide',side_effect=decision) if stage=='decision' else patch.object(self.model,'advance',side_effect=integration)
        with target:
            result=run_case(path,self.model,self.p,self.policy,case,live=False)
        return result,json.loads((path/'metadata.json').read_text()),[json.loads(line) for line in (path/'trace.jsonl').read_text().splitlines()]

    def test_partial_decision_and_integration_tails_replay_only_produced_evidence(self):
        from experiments.phase4_replay import replay_case,replay_isolation
        for stage in ('decision','integration'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
                path=Path(tmp)/stage
                result,meta,rows=self.partial_failure(path,stage)
                replay=replay_case(meta,path/'trace.jsonl')
                self.assertTrue(replay['passed'],replay)
                self.assertEqual(meta['trace_intervals'],2)
                self.assertEqual(meta['completed_intervals'],1)
                self.assertEqual(meta['physical_intervals'],1)
                self.assertEqual(meta['isolation_intervals'],1)
                self.assertTrue(meta['partial_tail'])
                self.assertEqual(meta['failure_stage'],stage)
                self.assertEqual(meta['failure_actor'],'front')
                self.assertEqual(rows[-1]['failure_stage'],stage)
                self.assertEqual(len(rows),2)
                self.assertTrue(result['recording_passed'],result)
                self.assertFalse(result['driving_passed'])
                self.assertTrue(replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')['passed'])

    def test_partial_tail_deletion_and_field_tampering_are_rejected(self):
        from experiments.phase4_replay import replay_case,replay_isolation
        for stage in ('decision','integration'):
            with self.subTest(stage=stage),tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
                path=Path(tmp)/stage
                result,meta,original=self.partial_failure(path,stage)
                self.assertTrue(replay_case(meta,path/'trace.jsonl')['passed'])
                for kind in ('tail','decision','failure_stage','failure_actor','initial','input','action','substep'):
                    if stage=='decision' and kind in ('action','substep'):
                        continue
                    rows=copy.deepcopy(original)
                    if kind=='tail': rows.pop()
                    elif kind=='decision': rows[-1]['decisions'].pop('ego')
                    elif kind=='failure_stage': rows[-1]['failure_stage']='action'
                    elif kind=='failure_actor': rows[-1]['failure_actor']='ego'
                    elif kind=='initial': rows[-1]['initial']['ego']['x_m']+=.01
                    elif kind=='input': rows[-1]['inputs']['front']['memory']['observation_history']=[]
                    elif kind=='action': rows[-1]['actions']['ego']['acceleration_mps2']+=.01
                    elif kind=='substep': rows[-1]['steps']['ego']['samples'][0]['x_m']+=.01
                    (path/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
                    self.assertFalse(replay_case(meta,path/'trace.jsonl')['passed'],kind)
                    self.assertFalse(replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')['passed'],kind)

    def check_keyboard_interrupt_finalization(self,stage):
        from experiments.phase4 import run_phase4
        from experiments.phase4_replay import replay_run
        from noa.controller import decide
        from models.kinematic import KinematicModel
        from research.common import sha256
        case=copy.deepcopy(self.case)
        case.update(controlled=['ego','front'],scripts={})
        case['initial']['front']['y_m']=4.95
        def interrupted(control,parameters):
            if control.ego.time_s>=.099 and control.ego.x_m>350:
                raise KeyboardInterrupt('preserve completed prefix and partial tail')
            return decide(control,parameters)
        advance=KinematicModel.advance
        def interrupted_integration(model,state,*args):
            if state.time_s>=.099 and state.x_m>350:
                raise KeyboardInterrupt('preserve integration tail')
            return advance(model,state,*args)
        target=patch('simulation.noa_clock.decide',side_effect=interrupted) if stage=='decision' else patch.object(KinematicModel,'advance',interrupted_integration)
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            base=Path(tmp)/'runs'
            with patch('experiments.phase4.cases',return_value=[case]),patch('experiments.phase4.command'),target:
                with self.assertRaises(KeyboardInterrupt):
                    run_phase4(base=base,live=False)
            path=Path(json.loads((base/'latest.json').read_text())['path'])
            meta=json.loads((path/'metadata.json').read_text())
            self.assertEqual(meta['case_trace_directories'],['fixture/base'])
            self.assertTrue((path/'evidence_hashes.json').is_file())
            hashes=json.loads((path/'evidence_hashes.json').read_text())
            expected={f.relative_to(path).as_posix() for f in path.rglob('*') if f.is_file() and f.name!='evidence_hashes.json'}
            self.assertEqual(set(hashes),expected)
            self.assertTrue(all(sha256(path/name)==digest for name,digest in hashes.items()))
            result=json.loads((path/'fixture/base/validation.json').read_text())
            self.assertEqual(result['status'],'failed')
            self.assertEqual(result['recorded_intervals'],1)
            self.assertTrue(result['recording_passed'],result)
            self.assertEqual(len((path/'fixture/base/trace.jsonl').read_text().splitlines()),2)
            replay=replay_run(path,base=Path(tmp)/'replays')
            self.assertTrue(replay['passed'],replay)
            self.assertFalse(replay['source_driving_gate_passed'])
            self.assertFalse(replay['fault_injection_performed'])

    def test_keyboard_interrupt_finalizes_registered_case_hashes_and_replay(self):
        for stage in ('decision','integration'):
            with self.subTest(stage=stage):
                self.check_keyboard_interrupt_finalization(stage)

    def test_first_interval_failure_keeps_partial_evidence_without_driving_coverage(self):
        from experiments.phase4 import run_case
        from experiments.phase4_replay import replay_case,replay_isolation
        from noa.controller import decide
        case=copy.deepcopy(self.case)
        case.update(controlled=['ego','front'],scripts={})
        def injected(control,parameters):
            if control.ego.x_m>350:
                raise RuntimeError('first interval second actor fault')
            return decide(control,parameters)
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path=Path(tmp)/'partial'
            with patch('simulation.noa_clock.decide',side_effect=injected):
                result=run_case(path,self.model,self.p,self.policy,case,live=False)
            meta=json.loads((path/'metadata.json').read_text())
            self.assertEqual(meta['trace_intervals'],1)
            self.assertEqual(meta['physical_intervals'],0)
            self.assertEqual(meta['isolation_intervals'],0)
            self.assertTrue(result['recording_passed'],result)
            self.assertFalse(result['driving_passed'])
            self.assertNotIn('metrics',result)
            self.assertTrue(replay_case(meta,path/'trace.jsonl')['passed'])
            isolation=replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')
            self.assertTrue(isolation['passed'],isolation)
            self.assertEqual(isolation['comparisons'],0)

    def test_replay_rebuilds_local_memories_and_rejects_tampering(self):
        from experiments.phase4_replay import replay_case
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path=Path(tmp)/'case'
            meta,original=self.fixture(path)
            self.assertTrue(replay_case(meta,path/'trace.jsonl')['passed'])
            for kind in ('observation','memory','action','initial','substep','decision','truncate','readback'):
                rows=copy.deepcopy(original)
                if kind=='observation': rows[0]['inputs']['ego']['observation']['neighbors'][0]['relative_x_m'] += .01
                elif kind=='memory': rows[1]['inputs']['ego']['memory']['observation_history']=[]
                elif kind=='action': rows[0]['actions']['ego']['acceleration_mps2'] += .01
                elif kind=='initial': rows[1]['initial']['ego']['x_m'] += .01
                elif kind=='substep': rows[0]['steps']['ego']['samples'][1]['y_m'] += .01
                elif kind=='decision': rows[0]['decisions']['ego']['memory']['own_behavior']='CORRUPTED'
                elif kind=='readback': rows[0]['readback']={}
                else: rows.pop()
                (path/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
                self.assertFalse(replay_case(meta,path/'trace.jsonl')['passed'],kind)

    def test_geometry_failure_is_driving_failure_but_remains_replayable(self):
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            case=copy.deepcopy(self.case)
            case['initial']['front']=dict(case['initial']['ego'])
            path=Path(tmp)/'overlap'
            meta,rows=self.fixture(path,case)
            result=json.loads((path/'validation.json').read_text())
            self.assertFalse(result['driving_passed'])
            self.assertGreater(result['geometry']['collision_substeps'],0)
            self.assertEqual(len(rows),3)

    def test_config_failure_retains_snapshot_in_unique_failed_run(self):
        from experiments.phase4 import run_phase4
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            base=Path(tmp)/'runs'
            with patch('experiments.phase4.KinematicModel.from_config',side_effect=RuntimeError('injected config failure')):
                with self.assertRaisesRegex(RuntimeError,'injected'):
                    run_phase4(base=base)
            latest=json.loads((base/'latest.json').read_text())
            path=Path(latest['path'])
            self.assertEqual(json.loads((path/'validation.json').read_text())['status'],'failed')
            self.assertTrue((path/'source_snapshot/noa/controller.py').is_file())
            self.assertTrue((path/'source_snapshot/configs/phase4.json').is_file())

    def test_source_manifest_covers_noa_policy(self):
        from research.common import code_manifest
        self.assertIn('noa/controller.py',code_manifest())

    def test_isolation_audit_rejects_tampered_frame_and_truncation(self):
        from experiments.phase4_replay import replay_isolation
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path=Path(tmp)/'case'
            meta,records=self.fixture(path)
            audit=path/'isolation.jsonl'
            self.assertTrue(replay_isolation(meta,path/'trace.jsonl',audit)['passed'])
            lines=audit.read_text().splitlines()
            first=json.loads(lines[0])
            first['mutated_frame'][0]['state']['x_m']+=.01
            audit.write_text(json.dumps(first)+'\n'+'\n'.join(lines[1:])+'\n',encoding='utf-8')
            self.assertFalse(replay_isolation(meta,path/'trace.jsonl',audit)['passed'])
            audit.write_text('\n'.join(lines[:-1])+'\n',encoding='utf-8')
            self.assertFalse(replay_isolation(meta,path/'trace.jsonl',audit)['passed'])

    def test_live_sumo_readback_is_replayed_and_corrupt_time_rejected(self):
        from experiments.phase4_replay import replay_case
        with tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
            path=Path(tmp)/'live'
            meta,rows=self.fixture(path,live=True)
            self.assertTrue(meta['live'])
            self.assertGreater(meta['sumo_time_offset_s'],0)
            self.assertTrue(replay_case(meta,path/'trace.jsonl')['passed'])
            rows[0]['readback']['ego']['sumo_time_s']+=.01
            (path/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
            self.assertFalse(replay_case(meta,path/'trace.jsonl')['passed'])

    def test_live_partial_precommit_and_postcommit_readbacks_replay_and_reject_tampering(self):
        from experiments.phase4 import run_case
        from experiments.phase4_replay import replay_case,replay_isolation
        from simulation.external_bridge import ExternalBridge
        case=copy.deepcopy(self.case)
        case['initial']['rear']={**case['initial']['front'],'x_m':230.,'y_m':4.95}
        case['scripts']['rear']={'speed_steps':[[0,13]]}
        original_readback=ExternalBridge.readback
        for phase in ('precommit','postcommit'):
            def injected(bridge,state=None,expected_interval_acceleration=None):
                second_interval=bridge.current.time_s>=.099
                if bridge.vehicle_id=='front' and second_interval and ((phase=='precommit' and state is None) or (phase=='postcommit' and state is not None)):
                    raise RuntimeError('retained later actor readback fault')
                return original_readback(bridge,state,expected_interval_acceleration)
            with self.subTest(phase=phase),tempfile.TemporaryDirectory(dir=self.root/'tmp') as tmp:
                path=Path(tmp)/phase
                with patch.object(ExternalBridge,'readback',injected):
                    result=run_case(path,self.model,self.p,self.policy,case,live=True)
                meta=json.loads((path/'metadata.json').read_text())
                rows=[json.loads(line) for line in (path/'trace.jsonl').read_text().splitlines()]
                replay=replay_case(meta,path/'trace.jsonl')
                self.assertTrue(replay['passed'],replay)
                self.assertTrue(result['recording_passed'],result)
                self.assertFalse(result['driving_passed'])
                self.assertEqual(meta['failure_readback_phase'],phase)
                self.assertEqual(meta['completed_intervals'],1)
                self.assertEqual(meta['physical_intervals'],2)
                self.assertEqual(meta['failure_readback_states'],{'ego':'recorded','front':'readback_exception','rear':'not_read'})
                self.assertEqual(rows[-1]['readback']['rear']['status'],'not_read')
                self.assertTrue(replay_isolation(meta,path/'trace.jsonl',path/'isolation.jsonl')['passed'])
                for kind in ('drop_actor','hide_readback','invent_readback','error','phase'):
                    changed=copy.deepcopy(rows)
                    last=changed[-1]
                    if kind=='drop_actor': last['readback'].pop('rear')
                    elif kind=='hide_readback': last['readback']['ego']=dict(last['readback']['rear'])
                    elif kind=='invent_readback': last['readback']['rear']=dict(last['readback']['ego'])
                    elif kind=='error': last['readback']['front']['errors']=['different error']
                    elif kind=='phase': last['readback_phase']='commit'
                    (path/'trace.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in changed),encoding='utf-8')
                    self.assertFalse(replay_case(meta,path/'trace.jsonl')['passed'],kind)


if __name__=='__main__':
    unittest.main()
