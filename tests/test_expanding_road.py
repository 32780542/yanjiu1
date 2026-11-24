"""Real network topology, local road observations and the public layout selector."""

import gzip
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import runrun
import run_native_flow
from experiments import native_sumo as native
from noa import native_rules as rules


class ExpandingRoadTests(unittest.TestCase):
    def test_sparse_demo_starts_with_visible_separated_groups(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "result.json").write_text(json.dumps(dict(
                status="drained", requested=24, departed=24, completed=24, collisions=0, teleports=0)))
            for layout in ("3to2", "4to3", "2to3", "3to4"):
                with self.subTest(layout=layout), patch.object(runrun, "run_case", return_value=folder) as run:
                    runrun.main(["--layout", layout, "--sparse-platoon-demo"], output_fn=lambda _: None)
                    case = run.call_args.kwargs
                    tape = case["initial"]
                    xs = sorted(c["x"] for c in tape)
                    self.assertEqual((len(tape), xs[0], xs[-1]), (24, 70., 650.))
                    biggest_gap = max(b-a for a,b in zip(xs, xs[1:]))
                    self.assertGreater(biggest_gap, 50.)
                    self.assertLessEqual(biggest_gap, 200.)
                    self.assertEqual(native.ROAD_LAYOUT[case["scenario"]], (2800, 1000, int(layout[-1])))
                    self.assertTrue(case["gui"])
                    self.assertFalse(case["auto_zoom"])

    def test_long_demo_uses_chain24_and_2800_metres_on_every_layout(self):
        for layout in ("3to2", "4to3", "2to3", "3to4"):
            with self.subTest(layout=layout), TemporaryDirectory() as tmp:
                folder = Path(tmp)
                (folder / "result.json").write_text(json.dumps(dict(
                    status="drained", requested=24, departed=24, completed=24, collisions=0, teleports=0)))
                with patch.object(runrun, "run_case", return_value=folder) as run:
                    runrun.main(["--layout", layout, "--long-platoon-demo"], output_fn=lambda _: None)
                case = run.call_args.kwargs
                self.assertTrue(case["gui"])
                self.assertFalse(case["auto_zoom"])
                self.assertEqual(native.ROAD_LAYOUT[case["scenario"]], (2800, 1000, int(layout[-1])))
                self.assertEqual(native.upstream_lanes(case["scenario"]), int(layout[0]))
                lanes = runrun.DEMO_ENTRY_LANES[int(layout[0])]
                self.assertEqual(case["initial"], [
                    dict(x=526-22*i, lane=lanes[i % len(lanes)], speed=28.8) for i in range(24)])

    def test_transport_certificates_count_matches_separately_from_submitted_requests(self):
        samples = iter([
            ("formation_transport", False, 0., 1, None),
            ("formation_transport", True, .125, 0, None),
            ("transform_transport", True, float("inf"), 1, 1),
            ("transform_transport", True, float("inf"), 1, 1),
            ("transform_transport", False, None, None, None),
            ("transform_transport", None, None, None, None),
        ])

        def scripted(ego, neighbors, memory, **road):
            reason, certified, gap, proposal, requested = next(samples)
            return SimpleNamespace(speed=10., lane=requested, reason=reason, formation_state=0,
                                   certified=certified, assignment_gap=gap, proposal_lane=proposal,
                                   step_certified=gap is not None, refined=gap == 0), memory

        with TemporaryDirectory() as tmp, patch.object(rules, "decide", side_effect=scripted):
            path = native.run_case(initial=[dict(x=100, lane=0, speed=10)], duration=.1, max_time=.6,
                                   output_base=tmp)
            result = json.loads((path / "result.json").read_bytes())
        self.assertEqual(result["status"], "time_limit", result.get("error"))
        totals = result["transport_certificates"]
        self.assertEqual(totals["formation_transport"], dict(
            matched_ticks=2, certified_ticks=1, zero_gap_ticks=1, positive_gap_ticks=1,
            no_alternative_ticks=0, unevaluated_gap_ticks=0, different_lane_ticks=1, accepted_requests=0,
            step_certified_ticks=2, step_only_certified_ticks=1, step_only_requests=0,
            refined_ticks=1, refined_requests=0))
        self.assertEqual(totals["transform_transport"], dict(
            matched_ticks=3, certified_ticks=2, zero_gap_ticks=0, positive_gap_ticks=0,
            no_alternative_ticks=2, unevaluated_gap_ticks=1, different_lane_ticks=2, accepted_requests=1,
            step_certified_ticks=2, step_only_certified_ticks=0, step_only_requests=0,
            refined_ticks=0, refined_requests=0))

    def test_source_snapshot_reproduces_the_formation_controller_dependencies(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            hashes = native._source_snapshot(directory)
            for name in ("noa/staggered.py", "noa/transport.py"):
                self.assertIn(name, hashes)
                source = (native.ROOT / name).read_bytes()
                self.assertEqual(source, (directory / "source" / name).read_bytes())
                self.assertEqual(hashes[name], hashlib.sha256(source).hexdigest())

    def test_constructed_network_preserves_existing_lane_centers_and_connections(self):
        for scenario, incoming, outgoing in (
            ("two_to_three", 2, 3), ("two_to_three_demo", 2, 3),
            ("three_to_four", 3, 4), ("three_to_four_demo", 3, 4),
            ("formation_demo", 3, 2), ("four_to_three_demo", 4, 3),
        ):
            with self.subTest(scenario=scenario), TemporaryDirectory() as tmp:
                root = ET.parse(native.build_network(Path(tmp), scenario))
                for edge, lanes in (("upstream", incoming), ("downstream", outgoing)):
                    lines = root.findall(f"./edge[@id='{edge}']/lane")
                    self.assertEqual(len(lines), lanes)
                    for lane, line in enumerate(lines):
                        for point in line.attrib["shape"].split():
                            self.assertAlmostEqual(float(point.split(",")[1]), (lane + .5) * 3.3)
                links = root.findall("./connection[@from='upstream'][@to='downstream']")
                self.assertEqual({(int(x.get("fromLane")), int(x.get("toLane"))) for x in links},
                                 {(i, i) for i in range(min(incoming, outgoing))})

    def test_layout_selector_routes_the_twelve_car_demo_and_checks_without_launch(self):
        for layout, scenario, lanes in (
            ("3to2", "formation_demo", 3), ("4to3", "four_to_three_demo", 4),
            ("2to3", "two_to_three_demo", 2), ("3to4", "three_to_four_demo", 3),
        ):
            with self.subTest(layout=layout), TemporaryDirectory() as tmp:
                path = Path(tmp)
                (path / "result.json").write_text(json.dumps(dict(
                    status="drained", requested=12, departed=12, completed=12, collisions=0, teleports=0)))
                options = ["--layout", layout, "--transform-demo"]
                with patch.object(runrun, "run_case", return_value=path) as run:
                    self.assertEqual(runrun.main([*options, "--check"], output_fn=lambda _: None), 0)
                    run.assert_not_called()
                    self.assertEqual(runrun.main(options, output_fn=lambda _: None), 0)
                case = run.call_args.kwargs
                self.assertEqual((case["scenario"], case["gui"], case["gui_delay_ms"]), (scenario, True, 40))
                self.assertEqual(sorted(row["depart"] for row in case["initial"]), [round(.7*i, 1) for i in range(12)])
                self.assertEqual({row["lane"] for row in case["initial"]}, set(range(lanes)))

    def test_explicit_straight_demo_overrides_file_transform_demo(self):
        output = []
        with patch.object(runrun, "TRANSFORM_DEMO", True):
            self.assertEqual(runrun.main(["--formation-demo", "--check"], output_fn=output.append), 0)
        self.assertIn("直路", output[1])

    def test_expansion_preview_is_local_and_native_execution_waits_for_the_opening(self):
        seen = []

        def request_new_lane(ego, neighbors, memory, **road):
            seen.append((ego.x, road))
            return rules.Command(speed=28.8, lane=2, reason="test_opening"), memory

        with TemporaryDirectory() as tmp, patch.object(rules, "decide", side_effect=request_new_lane):
            path = native.run_case(scenario="two_to_three", initial=[dict(x=790, lane=1)], duration=.1,
                                   diagnostic=True, output_base=tmp)
            result = json.loads((path / "result.json").read_bytes())
            self.assertEqual(result["status"], "drained", result.get("error"))
            with gzip.open(path / "diagnostic.jsonl.gz", "rt") as stream:
                frames = [json.loads(line) for line in stream]
        self.assertTrue(any(x < 800 for x, _ in seen))
        self.assertTrue(any(800 <= x < 1000 for x, _ in seen))
        self.assertTrue(any(x > 1000 for x, _ in seen))
        for x, road in seen:
            self.assertEqual(road["lane_count"], 2 if x < 1000 else 3)
            self.assertEqual(road.get("upcoming_lanes"), 3 if 800 <= x < 1000 else None)
            self.assertIsNone(road["drop_x"])
            self.assertEqual(road["downstream"], x >= 1000)
        accepted = [frame["states"][key]["x"] for frame in frames
                    for key, action in frame["actions"].items() if action["accepted"]]
        self.assertTrue(accepted)
        self.assertGreaterEqual(min(accepted), 1000.)

    def test_global_reference_matrix_skips_unsupported_expansions(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "result.json").write_text(json.dumps(dict(
                status="drained", requested=0, departed=0, completed=0, pending_final=0,
                onroad_final=0, collisions=0, teleports=0, mean_travel_time_s=None, formation_state=None)))
            with patch.object(run_native_flow, "run_case", return_value=path) as run:
                run_native_flow.main(["--matrix", "--scenarios", "three_to_four", "two_to_three", "--seeds", "1"])
            self.assertEqual([call.kwargs["mode"] for call in run.call_args_list],
                             ["noa", "formation", "transform"] * 2)
