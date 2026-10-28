"""The default entry computes native SUMO steps while its GUI is open."""

import io
import inspect
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import runrun

VARIANT = Path(__file__).resolve().parents[1] / "variants/phase5g_pure_formation"
if str(VARIANT) not in sys.path:
    sys.path.insert(0, str(VARIANT))
from experiments import native_sumo as native


class NativeEntrypointTests(unittest.TestCase):
    def test_defaults_select_real_1250_lane_drop_transform(self):
        config = runrun.build_config()
        self.assertTrue(hasattr(config, "mode"), "the entry still builds the historical demo")
        self.assertEqual(config.mode, "transform")
        self.assertEqual(config.scenario, "lane_drop")
        self.assertEqual(config.flow_veh_h_lane, 1250.0)
        self.assertEqual(config.demand_duration_s, 600.0)
        self.assertEqual(config.seed, 1)
        self.assertTrue(config.show_gui)
        self.assertEqual(config.gui_delay_ms, 40)
        self.assertTrue(config.wait_before_close)

    def test_main_runs_directly_with_native_gui_without_a_menu(self):
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
            self.assertEqual(run.call_args.kwargs["duration"], 600.0)
            self.assertTrue(run.call_args.kwargs["gui"])
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
