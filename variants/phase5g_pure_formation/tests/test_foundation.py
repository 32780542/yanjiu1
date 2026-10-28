import importlib.util
import unittest
from pathlib import Path


class FoundationTests(unittest.TestCase):
    def test_bootstrap_does_not_load_editable_parent_paths(self):
        import sys
        from research.common import ROOT
        self.assertTrue(sys.flags.no_site, 'Disable .pth processing with -S')
        self.assertTrue(sys.flags.isolated)
        self.assertTrue(sys.dont_write_bytecode)
        paths=[Path(p).resolve() for p in sys.path]
        self.assertFalse(any(p.is_relative_to(ROOT.parent) and not p.is_relative_to(ROOT) for p in paths))

    def test_implementation_exists(self):
        self.assertIsNotNone(importlib.util.find_spec('research'), 'New research implementation is missing')

    def test_output_cannot_escape_workspace(self):
        from research.common import output_path, ROOT
        self.assertEqual(output_path('tmp/test'), ROOT / 'tmp/test')
        for path in ('../escape.json', 'D:/outside.json'):
            with self.assertRaises(ValueError):
                output_path(path)

    def test_probability_uses_per_lane_hour(self):
        from research.demand import probability
        for q in (1250, 1500, 1750, 2000):
            self.assertAlmostEqual(probability(q, .1) * 3600 / .1, q)
        for q in (-1, float('nan'), 40000):
            with self.assertRaises(ValueError):
                probability(q, .1)

    def test_demand_replay_and_hidden_types_do_not_change_arrivals(self):
        from research.demand import generate, assign_types
        a = generate(1250, seed=7, duration_s=60)
        self.assertEqual(a, generate(1250, seed=7, duration_s=60))
        self.assertNotEqual(a, generate(1250, seed=8, duration_s=60))
        none = assign_types(a, 0)
        all_noa = assign_types(a, 1)
        half = assign_types(a, .5)
        self.assertTrue(all(x['hidden_type'] == 'HDV' for x in none))
        self.assertTrue(all(x['hidden_type'] == 'NOA' for x in all_noa))
        for records in (none, half, all_noa):
            self.assertEqual([{k: v for k, v in x.items() if k != 'hidden_type'} for x in records], a)
        high = generate(2000, seed=7, duration_s=60)
        self.assertTrue({x['vehicle_id'] for x in a} <= {x['vehicle_id'] for x in high})

    def test_observation_contract_has_no_hidden_channel(self):
        from dataclasses import fields, FrozenInstanceError
        from perception.contracts import LocalObservation, NeighborDetection, EgoState, LocalMemory, ControlInput
        self.assertEqual({f.name for f in fields(ControlInput)}, {'ego', 'observation', 'memory'})
        self.assertEqual({f.name for f in fields(NeighborDetection)}, {
            'track_id', 'relative_x_m', 'relative_y_m', 'relative_vx_mps', 'relative_vy_mps',
            'relative_heading_rad', 'length_m', 'width_m', 'measurement_time_s'})
        forbidden = {'type', 'hidden_type', 'sumo_id', 'plan', 'global_vehicles', 'leader_id', 'slot'}
        for cls in (LocalObservation, NeighborDetection, EgoState, LocalMemory):
            self.assertTrue({f.name for f in fields(cls)}.isdisjoint(forbidden))
            self.assertIn('__slots__', cls.__dict__)
        d = NeighborDetection(1, 10., 0., 0., 0., 0., 4., 1.8, 0.)
        with self.assertRaises((FrozenInstanceError, AttributeError, TypeError)):
            d.hidden_type = 'NOA'

    def test_network_rejects_wrong_mapping_width_and_shift(self):
        from research.network import validate_tree
        import xml.etree.ElementTree as ET
        def fixture():
            root = ET.Element('net')
            for edge_id, n, start, end in [('upstream', 3, 0, 1000), ('downstream', 2, 1000, 1200)]:
                e = ET.SubElement(root, 'edge', id=edge_id)
                for lane in range(n):
                    y = 1.65 + lane * 3.3
                    ET.SubElement(e, 'lane', id=f'{edge_id}_{lane}', index=str(lane), width='3.3',
                                  speed='33.3', length=str(end-start), shape=f'{start},{y} {end},{y}')
            for lane in range(2):
                ET.SubElement(root, 'connection', attrib={'from':'upstream', 'to':'downstream',
                             'fromLane':str(lane), 'toLane':str(lane)})
            return root
        self.assertTrue(validate_tree(fixture())['passed'])
        for change in ('illegal_link', 'width', 'shift', 'missing_link', 'length'):
            root = fixture()
            if change == 'illegal_link':
                ET.SubElement(root, 'connection', attrib={'from':'upstream', 'to':'downstream', 'fromLane':'2','toLane':'1'})
            elif change == 'width':
                root.find('edge/lane').set('width', '3.2')
            elif change == 'shift':
                root.find("edge[@id='downstream']/lane").set('shape', '1000,0 1200,0')
            elif change == 'length':
                root.find('edge/lane').set('length', '999')
            else:
                root.remove(root.findall('connection')[0])
            self.assertFalse(validate_tree(root)['passed'], change)


if __name__ == '__main__':
    unittest.main()
