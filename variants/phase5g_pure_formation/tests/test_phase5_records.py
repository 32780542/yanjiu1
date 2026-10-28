import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json


class Phase5CasesTests(unittest.TestCase):
    def test_frozen_random_cases_are_repeatable_continuous_and_feasible(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5_cases'))
        from experiments.phase5_cases import cases
        from models.kinematic import KinematicModel
        p = KinematicModel.from_config().p
        first, second = cases(p), cases(p)
        self.assertEqual(first, second)
        random = [c for c in first if c['kind'] == 'random']
        self.assertEqual([len(c['initial']) for c in random], [3,3,6,6,12,12])
        self.assertEqual(len({c['seed'] for c in random}), 6)
        for c in random:
            self.assertEqual(set(c['controlled']), set(c['initial']))
            self.assertFalse(c['scripts'])
            states = list(c['initial'].values())
            self.assertGreater(len({s['y_m'] for s in states}), 1)
            self.assertTrue(any(abs(s['x_m']/15-round(s['x_m']/15)) > .01 for s in states))
            for i,a in enumerate(states):
                for b in states[i+1:]:
                    if a['y_m']==b['y_m']:
                        self.assertGreaterEqual(abs(a['x_m']-b['x_m']), 30.)

    def test_events_act_on_own_speed_schedule_only(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5_cases'))
        from experiments.phase5_cases import cases
        from models.kinematic import KinematicModel
        events = [c for c in cases(KinematicModel.from_config().p) if c['kind']!='random']
        self.assertEqual({c['kind'] for c in events}, {'disturbance','disturbance_control','visibility','nonrecovery'})
        for c in events:
            self.assertEqual(set(c['initial']),set(c['controlled']) | set(c['scripts']))
            for script in c['scripts'].values():
                self.assertEqual(set(script), {'speed_steps'})
                self.assertGreater(len(script['speed_steps']),1)

    def test_disturbance_has_matched_no_pulse_control(self):
        from experiments.phase5_cases import cases
        from models.kinematic import KinematicModel
        selected={c['name']:c for c in cases(KinematicModel.from_config().p)}
        self.assertIn('disturbance_control',selected)
        perturbed,control=selected['disturbance'],selected['disturbance_control']
        self.assertEqual(perturbed['initial'],control['initial'])
        self.assertEqual(perturbed['duration_s'],control['duration_s'])
        self.assertEqual(perturbed['controlled'],control['controlled'])
        self.assertTrue(all(v==5 for _,v in control['scripts']['event']['speed_steps']))


class Phase5RunnerTests(unittest.TestCase):
    def test_visible_count_is_not_reference_return_evidence(self):
        from experiments.phase5 import run_case,parameters
        from experiments.phase5_cases import cases
        from research.common import ROOT
        model,p,policy=parameters(True)
        case={**next(c for c in cases(model.p) if c['name']=='visibility'),'duration_s':3.}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            path=Path(tmp)/'visibility'
            result=run_case(path,model,p,policy,case,live=False)
            self.assertTrue(result['recording_passed'],result)
            event=json.loads((path/'events.json').read_text())['reference_visibility']
            self.assertFalse(event['passed'])
            self.assertTrue(all(a['range_observation_consistent'] for a in event['actors'].values()))
            self.assertTrue(event['actors']['middle']['chains'])
            self.assertTrue(event['actors']['middle']['chains'][0]['reference_released'])
            self.assertIsNone(event['actors']['middle']['chains'][0]['reselected_time_s'])

    def test_interruption_retains_completed_and_failed_case_index(self):
        from experiments import phase5
        from experiments.phase5_cases import cases
        from research.common import ROOT
        model,_,_=phase5.parameters(False)
        case={**cases(model.p)[0],'duration_s':.2}
        original=phase5.run_case
        def interrupted(path,model,p,policy,case,live=True):
            if p['formation_enabled']:
                with patch.object(model,'advance',side_effect=KeyboardInterrupt('injected physical integration interruption')):
                    return original(path,model,p,policy,case,live=live)
            return original(path,model,p,policy,case,live=live)
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp, patch('experiments.phase5.cases',return_value=[case]), patch('experiments.phase5.run_case',side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                phase5.run_phase5(base=Path(tmp)/'runs',live=False,sampling=False)
            paths=[p for p in (Path(tmp)/'runs').iterdir() if p.is_dir()]
            self.assertEqual(len(paths),1)
            result=json.loads((paths[0]/'validation.json').read_text())
            self.assertEqual(result['status'],'failed')
            self.assertTrue(result['retained_partial_package'])
            self.assertEqual(len(result['variants']),2)
            self.assertEqual(result['variants'][case['name']+'_on']['status'],'failed')
            index=json.loads((paths[0]/'case_index.json').read_text())
            self.assertEqual(len(index['completed_variants']),1)
            self.assertEqual(len(index['started_variants']),2)
            self.assertTrue((paths[0]/'evidence_hashes.json').is_file())

    def test_recovery_requires_prior_formation_loss_and_new_hold(self):
        from experiments.phase5 import recovery_report
        interval=lambda a,b:{'whole_cohort':True,'start_time_s':a,'end_time_s':b,'formed_time_s':a+5,'held_time_s':a+15 if b-a>=15 else None}
        first=interval(0,20.)
        recovered=interval(30,50)
        detection={'intervals':[first,recovered],'frames':[{'time_s':20.1,'fleet_failure_reasons':['lost']}]}
        result=recovery_report(detection,{'event_start_s':20.,'event_release_s':27.})
        self.assertTrue(result['recovered_and_held'])
        self.assertEqual(result['loss_time_s'],20.1)
        self.assertEqual(result['recovery_formed_time_s'],35.)
        no_prior={**detection,'intervals':[recovered]}
        self.assertFalse(recovery_report(no_prior,{'event_start_s':20.})['recovered_and_held'])
        unchanged={'intervals':[interval(0,50)],'frames':[]}
        self.assertFalse(recovery_report(unchanged,{'event_start_s':20.})['recovered_and_held'])

    def test_short_offline_case_preserves_nonformation_and_replay(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5'))
        from experiments.phase5 import run_case, parameters
        from experiments.phase5_cases import cases
        from research.common import ROOT
        model,p,policy=parameters(False)
        c={**cases(model.p)[0], 'duration_s':.2}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp:
            result=run_case(Path(tmp)/'case',model,p,policy,c,live=False)
            self.assertTrue(result['recording_passed'],result)
            self.assertFalse(result['formation_success'])
            self.assertFalse(result['live'])
            self.assertEqual(result['recorded_intervals'],2)
            self.assertTrue((Path(tmp)/'case'/'trace.jsonl').is_file())

    def test_full_recording_pipeline_keeps_false_science_and_sampling(self):
        from experiments.phase5 import run_phase5, parameters
        from experiments.phase5_cases import cases
        from research.common import ROOT
        model,_,_=parameters(False)
        case={**cases(model.p)[0],'duration_s':.2}
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as tmp, patch('experiments.phase5.cases',return_value=[case]):
            path=run_phase5(base=Path(tmp)/'runs',live=False)
            result=json.loads((path/'validation.json').read_text())
            self.assertTrue(result['recording_passed'],result)
            self.assertFalse(result['passed'])
            self.assertEqual(len(result['variants']),3)
            self.assertTrue(result['sampling']['control_half']['passed'])
            self.assertTrue(result['sampling']['integration_half']['passed'])
            hashes=json.loads((path/'evidence_hashes.json').read_text())
            self.assertIn('validation.json',hashes)
            self.assertIn('cases/'+case['name']+'_on/detection.json',hashes)
            self.assertTrue((path/'code_snapshot'/'noa'/'formation.py').is_file())


if __name__=='__main__':
    unittest.main()
