"""Small offline fixtures for hashes, direct flags, crossing brackets and mismatches."""
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
TOOL = HERE / "compact_evidence.py"
tool = None
if TOOL.exists():
    spec = importlib.util.spec_from_file_location("compact_fixture_tool", TOOL)
    tool = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = tool
    spec.loader.exec_module(tool)


def encoded(value):
    return (json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n").encode()


class CompactEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(tool, "compact evidence implementation is missing")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = self.root / "case"
        self.case.mkdir()
        sources = {name: hashlib.sha256(b"# fixture source\n").hexdigest() for name in tool.SOURCES}
        for name in sources:
            path = self.case / "source" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# fixture source\n")
        self.input = {"case": {"demand_duration_s": 4}, "arrivals": [{"vehicle_id": "a"}],
                      "source_sha256": sources, "positions_step_s": 1.0}
        self.result = {"requested": 1, "departed": 1, "completed": 1,
                       "all_completed": True, "performance_comparison_eligible": True,
                       "safe": True, "collisions": 0, "teleports": 0, "error": None,
                       "actual_end_s": 5, "mean_travel_time_s": 5.0, "mean_system_time_s": 5.0,
                       "mean_entry_wait_s": 0.0, "fuel_g_per_km": 1.0,
                       "completed_subset_mean_travel_time_s": 5.0,
                       "completed_subset_mean_system_time_s": 5.0,
                       "departed_subset_mean_entry_wait_s": 0.0,
                       "completed_subset_fuel_g_per_km": 1.0,
                       "source_sha256": sources,
                       "formation_state": {"vehicle_seconds": 5.0,
                           "participating_vehicle_seconds": 2.0, "participation_rate": 0.4,
                           "mean_participants": 0.4, "peak_participants": 1, "episodes": 1,
                           "mean_episode_s": 2.0, "max_episode_s": 2.0}}
        trips = [{"vehicle_id": "a", "requested_s": 0, "entered_s": 0,
                  "exited_s": 5, "distance_m": 1200, "fuel_mg": 1200}]
        self.frames = [{"time_s": t, "states": {"a": [x, 0, 20, 0]},
                        "formation_states": {"a": flag}}
                       for t, x, flag in ((0, 90, 0), (1, 100, 1), (2, 610, 1),
                                          (3, 650, 0), (4, 1110, 0))]
        self.frames.append({"time_s": 5, "states": {}, "formation_states": {}})
        for name, value in (("input.json", self.input), ("result.json", self.result),
                            ("trips.json", trips), ("sumo_command.json", ["sumo", "--fixture"])):
            (self.case / name).write_bytes(encoded(value))
        self.write_positions()
        with gzip.open(self.case / "events.jsonl.gz", "wb") as stream:
            stream.write(b'{"event":"fixture"}\n')
        self.manifest = self.root / "manifest.json"
        self.manifest.write_bytes(encoded([{"candidate": "fixture", "stage": "fixture",
                                            "run_dir": str(self.case)}]))

    def write_positions(self):
        with gzip.open(self.case / "positions.jsonl.gz", "wb") as stream:
            stream.writelines(encoded(frame) for frame in self.frames)

    def build(self):
        return tool.build([self.manifest], self.root / "output")

    def mutate_blob(self, archive, kind, mutate):
        with tarfile.open(archive, "r:gz") as tar:
            files = {member.name: tar.extractfile(member).read() for member in tar if member.isfile()}
        index = json.loads(files["index.json"])
        old = index["cases"][0]["compact"][kind]
        data = mutate(files["blobs/" + old])
        sha = hashlib.sha256(data).hexdigest()
        files["blobs/" + sha] = data
        index["blobs"][sha] = {"bytes": len(data)}
        index["cases"][0]["compact"][kind] = sha
        files["index.json"] = encoded(index)
        target = self.root / "mutated.tar.gz"
        with tarfile.open(target, "w:gz") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        return target

    def test_round_trip_recomputes_exact_flags_trips_and_crossings(self):
        archive = self.build()
        report = tool.verify(archive, check_originals=True)
        self.assertEqual(report["cases_verified"], 1)
        case = report["cases"][0]
        self.assertEqual(case["formation_state"], self.result["formation_state"])
        self.assertEqual(case["traffic"]["mean_travel_time_s"], 5.0)
        self.assertAlmostEqual(case["segments"]["upstream"]["mean_time_s"], 500 / 510)
        self.assertAlmostEqual(case["segments"]["bottleneck"]["mean_time_s"], 3 + 450 / 460 - 2.75)
        with tarfile.open(archive) as tar:
            index = json.load(tar.extractfile("index.json"))
            for name, sha in index["cases"][0]["files"].items():
                self.assertEqual(tar.extractfile("blobs/" + sha).read(), (self.case / name).read_bytes())
            self.assertEqual(len(set(index["cases"][0]["files"]["source/" + n] for n in tool.SOURCES)), 1)
            self.assertFalse(any("positions.jsonl" in m.name for m in tar))

    def test_invalid_original_flag_is_rejected(self):
        self.frames[1]["formation_states"]["a"] = 2
        self.write_positions()
        with self.assertRaisesRegex(ValueError, "flag"):
            self.build()

    def test_bad_blob_hash_is_rejected(self):
        archive = self.build()
        with tarfile.open(archive) as tar:
            files = {m.name: tar.extractfile(m).read() for m in tar if m.isfile()}
        name = next(n for n in files if n.startswith("blobs/"))
        files[name] += b"bad"
        target = self.root / "bad-hash.tar.gz"
        with tarfile.open(target, "w:gz") as tar:
            for name, data in files.items():
                info = tarfile.TarInfo(name); info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
        with self.assertRaisesRegex(ValueError, "hash|bytes"):
            tool.verify(target)

    def test_rehashed_invalid_flag_is_rejected_semantically(self):
        def change(data):
            frames = [json.loads(line) for line in data.splitlines()]
            frames[1]["flags"][0] = 2
            return b"".join(encoded(frame) for frame in frames)
        with self.assertRaisesRegex(ValueError, "flag"):
            tool.verify(self.mutate_blob(self.build(), "flags", change))

    def test_rehashed_valid_flag_with_wrong_result_summary_is_rejected(self):
        def change(data):
            frames = [json.loads(line) for line in data.splitlines()]
            frames[1]["flags"][0] = 0
            return b"".join(encoded(frame) for frame in frames)
        with self.assertRaisesRegex(ValueError, "formation_state"):
            tool.verify(self.mutate_blob(self.build(), "flags", change))

    def test_rehashed_invalid_crossing_bracket_is_rejected(self):
        def change(data):
            value = json.loads(data)
            value["vehicles"]["a"]["600"]["samples"][0][2] = 700
            return encoded(value)
        with self.assertRaisesRegex(ValueError, "bracket"):
            tool.verify(self.mutate_blob(self.build(), "crossings", change))

    def test_wrong_trip_summary_is_rejected(self):
        self.result["mean_travel_time_s"] = 999
        (self.case / "result.json").write_bytes(encoded(self.result))
        with self.assertRaisesRegex(ValueError, "mean_travel_time_s"):
            tool.verify(self.build())

    def test_changed_local_original_positions_is_detected(self):
        archive = self.build()
        with (self.case / "positions.jsonl.gz").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "original.*hash|original.*bytes"):
            tool.verify(archive, check_originals=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
