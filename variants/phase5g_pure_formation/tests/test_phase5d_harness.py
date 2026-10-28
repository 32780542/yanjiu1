"""Mode binding and semantic replay; short fixtures are not research results."""
import copy
import inspect
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from experiments import phase5_r5 as harness
from experiments import phase5c_cases as extension
from research.common import ROOT, read_json, sha256


class GameHarnessTests(unittest.TestCase):
    def require_api(self):
        self.assertIn('waiting_policy', inspect.signature(harness.parameters).parameters,
                      'The experiment must bind a declared waiting policy')

    def test_explicit_modes_and_fixed_parent_parameter_compatibility(self):
        self.require_api()
        model, old_p, old_policy = harness.parameters(True)
        for mode in ('minimax', 'stackelberg'):
            _, p, policy = harness.parameters(True, waiting_policy=mode)
            new = {k:v for k,v in p.items() if k not in old_p}
            self.assertEqual(new, dict(r5_waiting_policy=mode, r5_game_horizon_s=5.,
                r5_game_peer_accel_mps2=.5, r5_game_gap_weight=1.,
                r5_game_speed_weight=1., r5_game_effort_weight=.05))
            self.assertEqual({k:p[k] for k in old_p}, old_p)
            self.assertEqual({k:policy[k] for k in old_policy}, old_policy)
            self.assertEqual({k:policy[k] for k in new}, new)
        fixed_model,fixed_p,fixed_policy=harness.parameters(True, waiting_policy='fixed')
        self.assertEqual(dict(fixed_model.p),dict(model.p))
        self.assertEqual((fixed_p,fixed_policy),(old_p,old_policy))

    def test_off_and_waiting_baseline_never_receive_new_policy(self):
        self.require_api()
        for enabled, lane in ((False, True), (False, False), (True, False)):
            old = harness.parameters(enabled, lane_priority=lane)[1:]
            for mode in ('minimax', 'stackelberg'):
                self.assertEqual(harness.parameters(enabled, lane_priority=lane, waiting_policy=mode)[1:], old)

    def test_bad_modes_rejected_even_if_disabled(self):
        self.require_api()
        for bad in (None, True, 1, '', 'Stackelberg', [], {}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                harness.parameters(False, waiting_policy=bad)

    def test_exact_extension_matrix_preserves_non_target_variants(self):
        self.require_api()
        cases=extension.build_cases(dict(harness.parameters(False)[0].p))
        old=harness.expected_variants(cases, True)
        self.assertEqual(len(old), 6)
        for mode in ('minimax', 'stackelberg'):
            actual=harness.expected_variants(cases, True, waiting_policy=mode)
            self.assertEqual(list(actual), list(old))
            for name,spec in old.items():
                wanted={**spec}
                if spec['r5_enabled'] and spec.get('lane_priority_enabled', True):
                    wanted['waiting_policy']=mode
                self.assertEqual(actual[name], wanted)

    def test_plan_is_a_frozen_input(self):
        self.assertIn('docs/phase5d_local_game_plan.md', harness.INPUTS)

    def test_game_replay_rejects_numeric_type_substitution_and_missing_game(self):
        from experiments.phase5_r5_replay import compare_private_record
        memory=dict(r5_rng_state=1,r5_draw_count=0,r5_phase='YIELD',r5_deadline_s=None,
                    r5_clear_since_s=None,r5_last_time_s=0.)
        game=dict(solver_mode='stackelberg',ego_costs=[[0.,1.]],executed=True)
        row=dict(inputs={},decisions={'ego':dict(memory=memory,diagnostics={'r5':{'waiting_game':game}})})
        compare_private_record(row,copy.deepcopy(row))
        for mutation in ('bool_for_float','missing'):
            changed=copy.deepcopy(row)
            if mutation=='bool_for_float':changed['decisions']['ego']['diagnostics']['r5']['waiting_game']['ego_costs'][0][0]=False
            else:del changed['decisions']['ego']['diagnostics']['r5']['waiting_game']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                compare_private_record(row,changed)

    def test_six_case_roundtrip_and_resealed_mode_or_payoff_mutations_rejected(self):
        self.require_api()
        from experiments.phase5 import _seal
        from experiments.phase5_r5_replay import replay_run
        from experiments.records import atomic_json
        model_p=dict(harness.parameters(False)[0].p)
        cases=[{**case,'duration_s':.2} for case in extension.build_cases(model_p)]
        (ROOT/'tmp').mkdir(exist_ok=True)
        folder=Path(tempfile.mkdtemp(prefix='phase5d_mode_unit_',dir=ROOT/'tmp'))
        with patch.object(extension,'build_cases',side_effect=lambda *args:copy.deepcopy(cases)):
            frozen=folder/'unit_cases.json'
            extension.freeze_cases(frozen,model_p)
            source=harness.run_phase5_r5(frozen,base=folder/'runs',live=False,sampling=True,
                                       waiting_policy='stackelberg')
            replay=replay_run(source,base=folder/'replays')
            self.assertTrue(replay['passed'], replay)
            self.assertEqual(len(replay['cases']), 6)
            self.assertEqual(read_json(source/'metadata.json')['waiting_policy'], 'stackelberg')
            index=read_json(source/'case_index.json')['expected_variants']
            active='r5c_gradual_three_r5_on'
            for name,spec in index.items():
                meta=read_json(source/'cases'/name/'metadata.json')
                self.assertEqual(meta['policy_parameters'].get('r5_waiting_policy','fixed'),
                                 spec.get('waiting_policy','fixed'))
            for mutation in ('declared_mode','missing_mode','index_mode','policy_mode','payoff'):
                with self.subTest(mutation=mutation):
                    altered=folder/('mutated_'+mutation)/source.name
                    shutil.copytree(source,altered)
                    if mutation in ('declared_mode','missing_mode'):
                        target=altered/'metadata.json'; data=read_json(target)
                        if mutation=='declared_mode':data['waiting_policy']='minimax'
                        else:data.pop('waiting_policy')
                        atomic_json(target,data)
                    elif mutation=='index_mode':
                        target=altered/'case_index.json';data=read_json(target)
                        data['expected_variants'][active]['waiting_policy']='minimax'
                        atomic_json(target,data)
                    elif mutation=='policy_mode':
                        target=altered/'cases'/active/'metadata.json';data=read_json(target)
                        data['policy_parameters']['r5_waiting_policy']='minimax'
                        atomic_json(target,data)
                    else:
                        target=altered/'cases'/active/'trace.jsonl'
                        rows=[json.loads(line) for line in target.read_text().splitlines()]
                        # Add a forged game diagnostic to the actual completed decision.
                        # Full deterministic replay must reject extra fields, even resealed.
                        self.assertEqual(rows[0]['status'],'completed')
                        rows[0]['decisions']['lower']['diagnostics']['forged_game_payoff']=0.
                        target.write_text(''.join(json.dumps(row)+'\n' for row in rows),encoding='utf-8')
                    _seal(altered)
                    self.assertFalse(replay_run(altered,base=folder/'replays')['passed'], mutation)

if __name__=='__main__':unittest.main()
