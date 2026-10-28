"""Fixed-reference analysis checked independently against the actual integrator."""
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest


class Phase5TheoryTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('experiments.phase5_theory'),
                             'Stage 5 fixed-reference analysis is missing')
        from experiments import phase5_theory
        self.theory = phase5_theory

    def test_characteristic_includes_noa_and_sample_midpoint_acceleration(self):
        self.assertEqual(self.theory.continuous_characteristic(.08, .4, .6, .2, 1., .1),
                         [.2, 1.03, 1., .08])
        self.assertEqual(self.theory.continuous_characteristic(.08, .4, .6, .2, 0., .1),
                         [.2, 1.03, .6, 0.])

    def test_eigenvalues_cover_real_and_complex_spectra_with_small_residual(self):
        roots = self.theory.eigenvalues3([[.99, 2, 1], [0, .8, 3], [0, 0, .6]])
        for got, expected in zip(sorted(roots, key=lambda z:z.real), [.6, .8, .99]):
            self.assertLess(abs(got-expected), 1e-10)
        roots = self.theory.eigenvalues3([[0, -1, 0], [1, 0, 0], [0, 0, .5]])
        self.assertTrue(all(min(abs(z-v) for v in roots)<1e-10 for z in [1j, -1j, .5]))

    def test_exact_zoh_matches_actual_rk4_longitudinal_linearization(self):
        from models.kinematic import KinematicModel
        model = KinematicModel.from_config()
        for h, dt in [(.1, .01), (.1, .005), (.05, .005)]:
            exact = self.theory.zoh_matrix(.08, .4, .6, .2, 1., h)
            actual = self.theory.kinematic_jacobian(model, .08, .4, .6, 1., h, dt)
            difference = max(abs(a-b) for row_a,row_b in zip(exact,actual)
                             for a,b in zip(row_a,row_b))
            self.assertLess(difference, 3e-8)
            self.assertLess(max(abs(z) for z in self.theory.eigenvalues3(actual)), 1.)

    def test_disabled_formation_leaves_neutral_position_mode(self):
        matrix = self.theory.zoh_matrix(.08, .4, .6, .2, 0., .1)
        self.assertLess(min(abs(z-1) for z in self.theory.eigenvalues3(matrix)), 1e-10)

    def test_individual_stability_does_not_imply_frequency_nonamplification(self):
        # Same formation gains without absolute cruise feedback: locally stable,
        # but this explicitly analytical counterfactual amplifies a low frequency.
        c = self.theory.continuous_characteristic(.08, .4, 0., .2, 1., 0.)
        self.assertGreater(c[1]*c[2], c[0]*c[3])
        self.assertGreater(abs(self.theory.reference_speed_response(.1, .08, .4, 0., .2)), 1.)
        self.assertLessEqual(abs(self.theory.reference_speed_response(.1, .08, .4, .6, .2)), 1.)

    def test_report_archives_computation_and_replay_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = self.theory.archive_analysis(Path(temp))
            report = json.loads((folder/'analysis.json').read_text(encoding='utf-8'))
            self.assertEqual(report['scope']['claim'], 'fixed_reference_cruise_branch_only')
            self.assertEqual(len(report['sampled']), 3)
            result = self.theory.verify_archive(folder)
            self.assertTrue(result['exact_report_match'])
            (folder/'analysis.json').write_text('{}\n', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'hash'):
                self.theory.verify_archive(folder)


if __name__ == '__main__':
    unittest.main()
