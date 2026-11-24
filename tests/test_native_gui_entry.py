"""The default entry computes native SUMO steps while its GUI is open."""

import gzip
import io
import inspect
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import runrun

VARIANT = Path(__file__).resolve().parents[1] / "variants/phase5g_pure_formation"
if str(VARIANT) not in sys.path:
    sys.path.insert(0, str(VARIANT))
from experiments import native_sumo as native
from experiments.complete_layers import groups_at
import run_native_flow


def shape_assessment():
    report = VARIANT.parents[1] / "docs/experiments/2026-11-19-staggered-reconfiguration"
    spec = importlib.util.spec_from_file_location("shape_assessment", report / "assess.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeEntrypointTests(unittest.TestCase):
    def test_initial_demo_reads_an_experiment_departure_table(self):
        with TemporaryDirectory() as tmp, patch.object(runrun, "_check"):
            tape = Path(tmp) / "cohort.json"
            tape.write_text(json.dumps([{"lane": 0, "x": 80, "speed": 28.8}]))
            output = []
            result = runrun.main(["--layout", "3to2", "--initial-demo", str(tape), "--check"],
                                 output_fn=output.append)
            self.assertEqual(result, 0)
            self.assertTrue(any("cohort.json" in line and "1 辆车" in line for line in output))

    def test_each_model_runs_the_same_demand_on_each_selected_road(self):
        with TemporaryDirectory() as tmp, patch.object(runrun, "RANDOM_SEED", 20), patch.object(runrun, "FLOW_VEH_H_LANE", 1750):
            for selector, lanes, outgoing, scenario in (
                (["--lanes", "3"], 3, 2, "lane_drop"), (["--lanes", "4"], 4, 3, "four_to_three"),
                (["--layout", "2to3"], 2, 3, "two_to_three"), (["--layout", "3to4"], 3, 4, "three_to_four"),
            ):
                demand = None
                for model, mode in (("hdv", "hdv"), ("noa", "noa"), ("formation", "transform")):
                    with self.subTest(model=model, scenario=scenario):
                        base = Path(tmp) / f"{scenario}_{model}"
                        args = ["--model", model, *selector, "--duration", "12",
                                "--headless", "--output-base", str(base)]
                        self.assertEqual(runrun.main(args, output_fn=lambda _: None), 0)
                        run, = base.iterdir()
                        result = json.loads((run / "result.json").read_bytes())
                        self.assertEqual((result["mode"], result["scenario"]), (mode, scenario))
                        self.assertGreater(result["completed"], 0)
                        self.assertEqual(result["completed"], result["requested"])
                        net = ET.parse(next(run.glob("*.net.xml")))
                        for edge, count in (("upstream", lanes), ("downstream", outgoing)):
                            self.assertEqual(len(net.findall(f"./edge[@id='{edge}']/lane")), count)
                        routes = ET.parse(next(run.glob("*.rou.xml")))
                        tape = [v.attrib for v in routes.findall("vehicle")]
                        self.assertEqual({int(v["departLane"]) for v in tape}, set(range(lanes)))
                        if demand is None:
                            demand = tape
                        self.assertEqual(tape, demand)
                        if model == "hdv":
                            self.assertEqual(result["idm_tau_s"], .85)

    def test_file_settings_apply_on_run_and_explicit_cli_flags_override_them(self):
        with patch.object(runrun, "MODEL", "HDV"), patch.object(runrun, "LANE_COUNT", 4):
            for options, model, lanes in (([], "HDV", "4 道缩至 3"), (["--model", "NOA", "--lanes", "3"], "NOA", "3 道缩至 2")):
                output = []
                self.assertEqual(runrun.main(["--check", *options], output_fn=output.append), 0)
                self.assertIn(model, output[0])
                self.assertIn(lanes, output[1])

    def test_formation_demo_uses_an_unbalanced_stream_on_a_three_lane_road(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            result = dict(status="drained", requested=12, departed=12, completed=12, collisions=0, teleports=0)
            (directory / "result.json").write_text(json.dumps(result))
            with patch.object(runrun, "run_case", return_value=directory) as run:
                runrun.main(["--formation-demo"], output_fn=lambda _: None)
        args = run.call_args.kwargs
        self.assertEqual(args["scenario"], "straight3")
        self.assertTrue(args["gui"])
        self.assertFalse(args["auto_zoom"])
        vehicles = args["initial"]
        self.assertEqual([sum(v["lane"] == lane for v in vehicles) for lane in range(3)], [6, 4, 2])
        self.assertEqual({v["x"] for v in vehicles}, {0})
        self.assertEqual(len({v["depart"] for v in vehicles}), 12)

    def test_native_formation_demo_reaches_four_physical_staggered_layers(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(runrun.main(["--formation-demo", "--headless", "--output-base", tmp],
                                         output_fn=lambda _: None), 0)
            run, = Path(tmp).iterdir()
            result = json.loads((run / "result.json").read_bytes())
            self.assertEqual((result["completed"], result["collisions"], result["teleports"]), (12, 0, 0))
            self.assertGreater(result["transport_certificates"]["formation_transport"]["accepted_requests"], 0)
            longest = consecutive = 0
            with gzip.open(run / "positions.jsonl.gz", "rt", encoding="utf-8") as stream:
                for line in stream:
                    states = json.loads(line)["states"]
                    formed = any(group["size"] == 12 for group in groups_at(states, 3))
                    consecutive = consecutive + 1 if formed else 0
                    longest = max(consecutive, longest)
            self.assertGreaterEqual(longest * native.STEP, 1.)

    def test_transform_demo_retains_the_same_twelve_in_both_physical_shapes(self):
        with TemporaryDirectory() as tmp:
            self.assertEqual(runrun.main(["--transform-demo", "--headless", "--output-base", tmp],
                                         output_fn=lambda _: None), 0)
            run, = Path(tmp).iterdir()
            row = shape_assessment().measure(run, cohort=True)
        self.assertEqual((row["completed"], row["collisions"], row["teleports"]), (12, 0, 0))
        self.assertEqual((row["crossing0"], row["crossing1"], row["peak_down"]), (6, 6, 12))
        self.assertGreater(row["three_longest_s"], 20.)
        self.assertGreater(row["two_longest_s"], 25.)

    def test_geometric_audit_accepts_slow_mirror_shapes_and_counts_every_intervening_car(self):
        measure = shape_assessment().alternating_windows
        speed = 12.
        half_gap = (5.5 + .85 * speed) / 2
        for first in (0, 1):
            states = {i: (200. - i * half_gap, (.5 + (first + i) % 2) * 3.3, speed)
                      for i in range(5)}
            windows, peak = measure(states)
            self.assertEqual((len(windows), peak), (2, 5))
            states["crossing"] = (200. - 1.5 * half_gap, 3.3, speed)
            self.assertEqual(measure(states), (set(), 3))

    def test_four_to_three_demo_forms_both_shapes_from_physical_positions(self):
        report = VARIANT.parents[1] / "docs/experiments/2026-11-20-lane-drop/measure.py"
        spec = importlib.util.spec_from_file_location("lane_drop_measure", report)
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        with TemporaryDirectory() as tmp:
            self.assertEqual(runrun.main(["--four-to-three-demo", "--headless", "--output-base", tmp],
                                         output_fn=lambda _: None), 0)
            run, = Path(tmp).iterdir()
            row = audit.measure(run, cohort=True)
        self.assertEqual((row["completed"], row["collisions"], row["teleports"]), (12, 0, 0))
        self.assertEqual(row["crossing"], "4/4/4")
        self.assertGreater(row["up_s"], 15.)
        self.assertGreater(row["down_s"], 10.)

    def test_mode_comparison_gui_keeps_camera_under_user_control(self):
        with TemporaryDirectory() as tmp:
            folder = Path(tmp)
            result = dict(status="drained", requested=0, departed=0, completed=0, pending_final=0,
                          onroad_final=0, collisions=0, teleports=0, mean_travel_time_s=None, formation_state=None)
            (folder / "result.json").write_text(json.dumps(result), encoding="utf-8")
            with patch.object(run_native_flow, "run_case", return_value=folder) as run:
                run_native_flow.main(["--gui", "--mode", "noa"])
        self.assertTrue(run.call_args.kwargs["gui"])
        self.assertFalse(run.call_args.kwargs["auto_zoom"])

    def test_main_runs_directly_with_native_gui_and_manual_camera(self):
        self.assertTrue(hasattr(runrun, "run_case"), "the entry must call native run_case")
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "result.json").write_text(
                json.dumps(
                    dict(status="drained", requested=1, departed=1, completed=1, collisions=0, teleports=0)
                ),
                encoding="utf-8",
            )
            with patch.object(runrun, "run_case", return_value=directory) as run:
                self.assertEqual(
                    runrun.main([], input_fn=lambda _: self.fail("no menu"), output_fn=lambda _: None), 0
                )
            self.assertEqual(run.call_args.kwargs["mode"], "transform")
            self.assertEqual(run.call_args.kwargs["scenario"], "lane_drop")
            self.assertEqual(run.call_args.kwargs["flow"], runrun.FLOW_VEH_H_LANE)
            self.assertEqual(run.call_args.kwargs["duration"], 600.0)
            self.assertEqual(run.call_args.kwargs["seed"], runrun.RANDOM_SEED)
            self.assertTrue(run.call_args.kwargs["gui"])
            self.assertEqual(run.call_args.kwargs["gui_delay_ms"], runrun.GUI_DELAY_MS)
            self.assertFalse(run.call_args.kwargs["auto_zoom"])
            self.assertTrue(run.call_args.kwargs["wait_before_close"])

    def test_short_headless_command_disables_gui_and_wait(self):
        self.assertTrue(hasattr(runrun, "run_case"), "the entry must call native run_case")
        with TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "result.json").write_text(
                json.dumps(
                    dict(status="time_limit", requested=1, departed=1, completed=0, collisions=0, teleports=0)
                ),
                encoding="utf-8",
            )
            with patch.object(runrun, "run_case", return_value=directory) as run:
                self.assertEqual(
                    runrun.main(
                        ["--headless", "--duration", "2", "--max-time", "3", "--gui-delay-ms", "5"],
                        output_fn=lambda _: None,
                    ),
                    0,
                )
            self.assertFalse(run.call_args.kwargs["gui"])
            self.assertFalse(run.call_args.kwargs["wait_before_close"])
            self.assertEqual(run.call_args.kwargs["duration"], 2.0)
            self.assertEqual(run.call_args.kwargs["gui_delay_ms"], 5)
            self.assertEqual(run.call_args.kwargs["max_time"], 3.0)

    def test_check_reports_native_dependencies_without_launching_sumo(self):
        self.assertTrue(hasattr(runrun, "run_case"), "the entry must call native run_case")
        output = []
        with patch.object(runrun, "run_case") as run:
            self.assertEqual(runrun.main(["--check"], output_fn=output.append), 0)
        run.assert_not_called()
        self.assertTrue(any("自检通过" in line for line in output))
        self.assertTrue(any("28.8" in line and "33.3" in line for line in output))
        self.assertTrue(any("native_sumo.py" in line for line in output))

    def test_direct_process_check_works_from_another_directory(self):
        process = subprocess.run(
            [sys.executable, str(runrun.PROJECT_ROOT / "runrun.py"), "--check"],
            cwd=runrun.PROJECT_ROOT.parent,
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(process.returncode, 0, process.stderr.decode("utf-8", errors="replace"))
        self.assertIn("自检通过", process.stdout.decode("utf-8"))

    def test_invalid_delay_is_reported_without_traceback(self):
        output, errors = io.StringIO(), io.StringIO()
        with (
            patch.object(runrun, "GUI_DELAY_MS", -1),
            patch.object(runrun.sys, "argv", ["runrun.py", "--check"]),
            patch.object(runrun.sys, "stdin", io.StringIO()),
            patch.object(runrun.sys, "stdout", output),
            patch.object(runrun.sys, "stderr", errors),
        ):
            self.assertEqual(runrun._debug_friendly_entry(), 1)
        self.assertIn("GUI_DELAY_MS", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue() + errors.getvalue())


class NativeGUIExecutionTests(unittest.TestCase):
    def test_camera_starts_at_entry_and_stops_at_the_bottleneck_view(self):
        self.assertTrue(hasattr(native, "gui_view_boundary"))
        self.assertEqual(native.gui_view_boundary(0.0), (0.0, -20.0, 600.0, 40.0))
        self.assertEqual(native.gui_view_boundary(600.0), (300.0, -20.0, 900.0, 40.0))
        self.assertEqual(native.gui_view_boundary(1200.0), (600.0, -20.0, 1200.0, 40.0))

    def test_gui_opens_before_step_and_waits_before_closing(self):
        self.assertIn("gui_delay_ms", inspect.signature(native.run_case).parameters)
        order, command = [], []
        tc = native.lock_traci().constants

        class Connection:
            def __init__(self):
                self.gui = SimpleNamespace(
                    getIDList=lambda: ["View #0"], setBoundary=lambda *args: order.append("view")
                )
                self.simulation = SimpleNamespace(
                    getTime=lambda: 0.1,
                    getDepartedIDList=lambda: (),
                    getArrivedIDList=lambda: (),
                    getCollisions=lambda: (),
                    getStartingTeleportIDList=lambda: (),
                    getMinExpectedNumber=lambda: 0,
                )
                self.vehicle = SimpleNamespace(getAllSubscriptionResults=lambda: {})

            def getVersion(self):
                return 0, "test native GUI"

            def simulationStep(self):
                order.append("step")

            def close(self):
                order.append("close")

        connection = Connection()

        class TraCI:
            constants = tc

            def start(self, args, **kwargs):
                command.extend(args)
                order.append("start")
                Path(args[args.index("--tripinfo-output") + 1]).write_text("<tripinfos/>")

            def getConnection(self, label):
                return connection

        def inspect_last_frame(prompt):
            self.assertIn("Enter", prompt)
            order.append("inspect")

        with (
            TemporaryDirectory() as tmp,
            patch.object(native, "lock_traci", return_value=TraCI()),
            patch.object(native, "build_network", return_value=Path(tmp) / "unused.net.xml"),
            patch.object(native.time, "sleep", side_effect=lambda _: order.append("delay")) as delay,
            patch.object(sys, "stdin", SimpleNamespace(isatty=lambda: True)),
        ):
            native.run_case(
                flow=0.0,
                duration=0.1,
                max_time=0.1,
                output_base=tmp,
                gui=True,
                gui_delay_ms=17,
                wait_before_close=True,
                input_fn=inspect_last_frame,
                output_fn=lambda _: None,
            )
        self.assertEqual(order, ["start", "view", "step", "delay", "inspect", "close"])
        delay.assert_called_once_with(0.017)
        self.assertEqual(command[command.index("--delay") + 1], "17")
        self.assertEqual(command[command.index("--quit-on-end") + 1], "true")

    def test_result_captures_complete_layer_source_and_runtime_versions(self):
        with TemporaryDirectory() as tmp:
            directory = native.run_case(flow=0.0, duration=0.1, max_time=0.1, output_base=tmp)
            result = json.loads((directory / "result.json").read_text(encoding="utf-8"))
            self.assertIn("experiments/complete_layers.py", result["source_sha256"])
            self.assertEqual(
                (directory / "source/experiments/complete_layers.py").read_bytes(),
                (VARIANT / "experiments/complete_layers.py").read_bytes(),
            )
            self.assertEqual(result["runtime"]["python_version"], sys.version.split()[0])
            self.assertEqual(result["runtime"]["scipy_version"], "1.18.1")
            inputs = json.loads((directory / "input.json").read_text(encoding="utf-8"))
            self.assertEqual(inputs["case"]["runtime"], result["runtime"])


if __name__ == "__main__":
    unittest.main()
