"""Verify public traffic archives offline, without original case paths or SUMO."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import tarfile
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def close(actual, expected, tolerance):
    assert actual is not None and expected is not None
    assert math.isclose(actual, expected, rel_tol=1e-9, abs_tol=tolerance), (actual, expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=HERE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    public, report = read(root / "PUBLIC_MANIFEST.json"), read(root / "report.json")
    for name, expected in public["files"].items():
        relative = Path(name)
        assert not relative.is_absolute() and ".." not in relative.parts
        payload = (root / relative).read_bytes()
        assert len(payload) == expected["bytes"] and sha(payload) == expected["sha256"], name
    # The frozen wrapper reuses the existing evaluator's pure _region function.
    # Its imports need the repository modules, but never call load_case/SUMO.
    sys.path.insert(0, str(ROOT / "variants/phase5g_pure_formation"))
    wrapper_path = root / "method_sources/bottleneck_trials.py"
    spec = importlib.util.spec_from_file_location("public_traffic_reconstruction", wrapper_path)
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    assert sha(wrapper_path.read_bytes()) == public["method_source_hashes"]["wrapper"]
    for name in ("bottleneck_attribution", "native_comparison", "complete_layers"):
        expected = public["method_source_hashes"][name]
        assert sha((root / "method_sources" / (name + ".py")).read_bytes()) == expected
        assert sha(Path(wrapper.existing.__file__).with_name(name + ".py").read_bytes()) == expected
    tolerance = wrapper.existing.TOLERANCE
    runs = {r["case_dir"]: r for r in report["runs"]}
    verified, ledger_files = {}, 0
    for bundle in public["bundles"]:
        manifest = read(root / bundle["manifest"])
        archive_path = root / bundle["archive"]
        assert sha(archive_path.read_bytes()) == manifest["archive_sha256"]
        assert archive_path.stat().st_size == manifest["archive_bytes"]
        with tarfile.open(archive_path, "r:gz") as archive:
            members = archive.getmembers()
            assert len(members) == len(manifest["members"])
            assert {m.name for m in members} == set(manifest["members"])
            for member in members:
                assert member.isfile()
                payload = archive.extractfile(member).read()
                expected = manifest["members"][member.name]
                assert len(payload) == expected["bytes"] and sha(payload) == expected["sha256"]
            for case in manifest["cases"]:
                metadata = json.loads(archive.extractfile(case["metadata_member"]).read())
                run = metadata["run"]
                assert run == runs[case["case_dir"]]
                assert run["profile"] == bundle["profile"] and run["attribution_eligible"]
                with TemporaryDirectory(prefix="public-traffic-") as directory:
                    folder = Path(directory)
                    for filename in ("region_steps.jsonl.gz", "gate_brackets.jsonl.gz", "vehicles.json.gz"):
                        name = "cases/" + case["case_id"] + "/" + filename
                        payload = archive.extractfile(name).read()
                        assert sha(payload) == metadata["ledger_sha256"][filename]
                        (folder / filename).write_bytes(payload)
                        ledger_files += 1
                    with gzip.open(folder / "vehicles.json.gz", "rt", encoding="utf-8") as stream:
                        vehicles = json.load(stream)
                    checks = wrapper.verify_ledgers(folder, run, vehicles)
                    assert checks == metadata["ledger_verification"]
                    # Reconstruct the same existing route/segment time formulas.
                    assert len(vehicles) == run["requested"] and vehicles
                    for metric, end, start in (("mean_travel_time_s", "exited_s", "entered_s"),
                                                ("mean_system_time_s", "exited_s", "requested_s"),
                                                ("mean_entry_wait_s", "entered_s", "requested_s")):
                        close(sum(v[end] - v[start] for v in vehicles) / len(vehicles), run[metric], tolerance)
                    for a, b in wrapper.existing.SEGMENTS:
                        metric = f"mean_segment_{a}_{b}_s"
                        close(sum(v["segments_s"][f"{a}_{b}"] for v in vehicles) / len(vehicles), run[metric], tolerance)
                    close(checks["first_crossings_reconstructed"] * 3600 / 500, run["flow_1000m_veh_h"], tolerance)
                assert run["case_dir"] not in verified
                verified[run["case_dir"]] = run
        print(json.dumps(dict(profile=bundle["profile"], verified_cases=len(manifest["cases"]))), flush=True)
    assert len(verified) == public["cases"] == 250 and ledger_files == 750
    for row in report["pairs"]:
        expected = wrapper.pair(verified[row["reference_case_dir"]], verified[row["candidate_case_dir"]],
                                row["comparison"], row["interpretation"])
        assert expected == row
    deltas = ["delta_" + metric for metric in wrapper.METRICS]
    assert wrapper.existing._means(report["pairs"], ("comparison", "flow", "scenario"), deltas) == report["paired_means"]
    assert wrapper.existing._means(report["pairs"], ("comparison", "scenario"), deltas) == report["overall_paired_means"]
    result = dict(verified_cases=250, verified_pairs=len(report["pairs"]), verified_compressed_ledgers=ledger_files,
                  original_case_paths_read=False, simulations_run=False, raw_positions_required=False,
                  reconstruction="existing verify_ledgers plus unchanged route/segment/crossing formulas; paired differences/means verified",
                  fuel_lane_count_proof="hash-bound original JSON identifiers retained; companion case evidence contains originals")
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
