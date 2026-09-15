"""Portable SUMO discovery contracts for the root research runtime."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def _root_common_module():
    common_path = ROOT / "research" / "common.py"
    spec = importlib.util.spec_from_file_location("phase5g_root_common", common_path)
    if spec is None or spec.loader is None:
        raise AssertionError("unable to load root research.common")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RootToolDiscoveryTests(unittest.TestCase):
    def test_uses_sumo_home_with_empty_portable_config(self):
        common = _root_common_module()
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw).resolve()
            (home / "bin").mkdir()
            executable = home / "bin" / "sumo.exe"
            executable.write_bytes(b"")
            with patch.object(common, "read_json", return_value={"sumo_home": ""}), \
                    patch.dict(os.environ, {"SUMO_HOME": str(home)}, clear=False):
                self.assertEqual(home, common.sumo_home())
                self.assertEqual(str(home), common.tool_env()["SUMO_HOME"])
                self.assertEqual(str(executable), common.binary("sumo"))

    def test_falls_back_to_sumo_on_path_with_empty_config(self):
        common = _root_common_module()
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw).resolve()
            executable = home / "bin" / "sumo-gui.exe"
            executable.parent.mkdir()
            executable.write_bytes(b"")
            with patch.object(common, "read_json", return_value={"sumo_home": ""}), \
                    patch.dict(os.environ, {"SUMO_HOME": ""}, clear=False), \
                    patch.object(common.shutil, "which", side_effect=lambda name: str(executable) if name == "sumo-gui.exe" else None):
                self.assertEqual(home, common.sumo_home())

    def test_lock_traci_rejects_cached_wrong_origins_without_leaking_environment(self):
        common = _root_common_module()
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw).resolve()
            (home / "tools").mkdir()
            wrong = types.SimpleNamespace(__file__=str(home.parent / "wrong.py"))
            with patch.object(common, "sumo_home", return_value=home), \
                    patch.dict(os.environ, {}, clear=False), \
                    patch.object(sys, "path", list(sys.path)), \
                    patch.dict(sys.modules, {"traci": wrong, "sumolib": wrong}):
                with self.assertRaisesRegex(RuntimeError, "Wrong tool module origin"):
                    common.lock_traci()


if __name__ == "__main__":
    unittest.main()
