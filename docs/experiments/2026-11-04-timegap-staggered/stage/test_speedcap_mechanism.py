"""Only the controller's shared MAX_SPEED changes; no SUMO run."""
from pathlib import Path
import importlib.util
import os
import sys
import unittest

BASE = Path(__file__).resolve().parents[4] / 'tmp/staggered_bottleneck/candidates'


class SharedSpeedCap(unittest.TestCase):
    def test_shared_cap_and_noa_zero(self):
        for preview in (200, 300):
            family = 'C12' if os.environ.get('SPEEDCAP_PARENT_ONLY') == '1' else 'speedcap288'
            path = BASE / f'20261104_{family}_{preview}/native_rules.py'
            spec = importlib.util.spec_from_file_location(f'cap_{preview}', path)
            r = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = r
            spec.loader.exec_module(r)
            # A clear, distant target genuinely requests above cruise in the parent.
            ego = r.Vehicle(0, 0., 1.65, 28.8, 0)
            self.assertLessEqual(r._request(ego, 100., 28.8), 28.8)
            for speed in (0., 28.8, 33.3):
                ego = r.Vehicle(0, 0., 1.65, speed, 0)
                for rows in ((), (r.Vehicle(1, 40., 1.65, 28.8, 0),),
                             (r.Vehicle(1, 0., 4.95, 28.8, 1),)):
                    for mode in ('noa', 'formation', 'transform'):
                        command, _ = r.decide(ego, rows, r.Memory(), mode, None)
                        self.assertLessEqual(command.speed, 28.8)
                        if mode == 'noa':
                            self.assertEqual(command.formation_state, 0)
            parent = (BASE / f'20261104_C12_{preview}/native_rules.py').read_bytes()
            old = b'CRUISE, MAX_SPEED = 28.8, 33.3'
            self.assertEqual(parent.count(old), 1)
            self.assertEqual(path.read_bytes(), parent.replace(old, b'CRUISE, MAX_SPEED = 28.8, 28.8'))


if __name__ == '__main__':
    unittest.main()
