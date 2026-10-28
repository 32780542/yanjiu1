"""Initial conditions are fixed before physics, including adversarial streams."""
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from experiments.phase5_r5_cases import physical_cases, freeze_cases, load_frozen_cases, _digest
from models.kinematic import KinematicModel
from noa.formation import memory_from_dict


class R5CaseTests(unittest.TestCase):
    def setUp(self):
        self.p = dict(KinematicModel.from_config().p)

    def test_fixed_matrix_and_independent_actors(self):
        matrix = physical_cases(self.p)
        self.assertEqual(matrix, physical_cases(self.p))
        self.assertEqual(len(matrix), 8)
        self.assertEqual([c['duration_s'] for c in matrix], [20.,30.,30.,20.,20.,40.,20.,20.])
        for case in matrix:
            self.assertFalse(set(case['controlled']) & set(case['scripts']))
            self.assertEqual(set(case['initial']), set(case['controlled']) | set(case['scripts']))
            self.assertEqual(case['requirements'], {})
            self.assertNotIn('initial_memories', case)
            states = list(case['initial'].values())
            for i, a in enumerate(states):
                self.assertEqual(a['heading_rad'], 0.)
                self.assertGreaterEqual(a['y_m']-.9, 0.)
                self.assertLessEqual(a['y_m']+.9, 9.9)
                for b in states[i+1:]:
                    self.assertTrue(abs(a['x_m']-b['x_m']) > 4. or abs(a['y_m']-b['y_m']) > 1.8)
        floor = matrix[2]
        self.assertEqual(floor['initial']['left']['vx_mps'], 5.)
        self.assertEqual(floor['initial']['lead_left']['x_m']-floor['initial']['left']['x_m'],35.)

    def test_freeze_exactly_once_each_ordinary_actor_duplicates_allowed(self):
        calls=[]
        def draw():
            calls.append(1)
            return 7
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cases.json'
            frozen=freeze_cases(path,self.p,entropy_draw=draw)
            self.assertEqual(len(calls),9)
            self.assertEqual(frozen,load_frozen_cases(path,self.p))
            for case in frozen:
                self.assertEqual(set(case['initial_memories']),set(case['controlled']))
                for memory in case['initial_memories'].values():
                    self.assertEqual(json.loads(json.dumps(asdict(memory_from_dict(memory)))),memory)
                    self.assertEqual(memory['r5_draw_count'],0)
            self.assertEqual([m['r5_rng_state'] for m in frozen[-2]['initial_memories'].values()],[1,1])
            self.assertEqual([m['r5_rng_state'] for m in frozen[-1]['initial_memories'].values()],[1,2])
            self.assertEqual(frozen[-1]['private_rng_provenance']['source'],'adversarial_fixed_private_state')
            before=path.read_bytes()
            with self.assertRaises(FileExistsError):
                freeze_cases(path,self.p,entropy_draw=draw)
            self.assertEqual(before,path.read_bytes())
            self.assertEqual(len(calls),9)

    def test_invalid_private_state_rejected_before_file_created(self):
        for bad in (True,-1,2**64,1.25,None):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'cases.json'
                with self.assertRaises(ValueError):
                    freeze_cases(path,self.p,entropy_draw=lambda:bad)
                self.assertFalse(path.exists())

    def test_load_rejects_private_physical_or_source_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cases.json'
            freeze_cases(path,self.p,entropy_draw=lambda:0)
            original=json.loads(path.read_text(encoding='utf-8'))
            for field in ('private','physical','source'):
                data=json.loads(json.dumps(original))
                if field=='private': data['cases'][0]['initial_memories']['ego']['r5_rng_state']=2
                elif field=='physical': data['cases'][0]['initial']['ego']['x_m']+=1
                else: data['generator_sha256']='0'*64
                path.write_text(json.dumps(data),encoding='utf-8')
                with self.assertRaises(ValueError): load_frozen_cases(path,self.p)

    def test_rehashed_partial_memory_is_not_a_complete_initial_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cases.json'
            freeze_cases(path,self.p,entropy_draw=lambda:0)
            original=json.loads(path.read_text(encoding='utf-8'))
            for field in ('r5_phase','r5_draw_count','r5_deadline_s','plan','formation_weight'):
                with self.subTest(field=field):
                    data=json.loads(json.dumps(original))
                    del data['cases'][0]['initial_memories']['ego'][field]
                    data['initial_state_sha256']=_digest(data['cases'])
                    path.write_text(json.dumps(data),encoding='utf-8')
                    with self.assertRaises(ValueError): load_frozen_cases(path,self.p)

    def test_rehashed_wrong_entropy_provenance_boolean_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cases.json'
            freeze_cases(path,self.p,entropy_draw=lambda:0)
            original=json.loads(path.read_text(encoding='utf-8'))
            for bad in (None,0,1,False,'true'):
                with self.subTest(bad=bad):
                    data=json.loads(json.dumps(original))
                    data['cases'][0]['private_rng_provenance']['independent_draws_requested']=bad
                    data['initial_state_sha256']=_digest(data['cases'])
                    path.write_text(json.dumps(data),encoding='utf-8')
                    with self.assertRaises(ValueError): load_frozen_cases(path,self.p)

    def test_provenance_version_requires_integer_not_boolean(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'cases.json'
            freeze_cases(path,self.p,entropy_draw=lambda:0)
            data=json.loads(path.read_text(encoding='utf-8'))
            data['cases'][0]['private_rng_provenance']['version']=True
            data['initial_state_sha256']=_digest(data['cases'])
            path.write_text(json.dumps(data),encoding='utf-8')
            with self.assertRaises(ValueError): load_frozen_cases(path,self.p)


if __name__=='__main__': unittest.main()
