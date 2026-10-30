"""Package existing verified traffic caches, preserving every compressed byte."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import shutil
import tarfile

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=ROOT / "tmp/literature_trials/bottleneck_analysis")
    args = parser.parse_args()
    report_dir = args.cache / "reports/all250"
    report = json.loads((report_dir / "report.json").read_text(encoding="utf-8"))
    assert len(report["runs"]) == 250 and all(r["attribution_eligible"] for r in report["runs"])
    for source in sorted(report_dir.iterdir()):
        if source.is_file():
            shutil.copyfile(source, HERE / source.name)
    for name in ("FINAL_INTERPRETATION.md", "METHOD.md", "ledger_index_all250.csv", "verification_summary_all250.json"):
        shutil.copyfile(args.cache / name, HERE / name)
    sources = HERE / "method_sources"
    sources.mkdir(exist_ok=True)
    method_paths = {"bottleneck_trials.py": ROOT / "docs/experiments/2026-10-30-rule-trials/analysis/bottleneck_trials.py"}
    for name in ("bottleneck_attribution", "native_comparison", "complete_layers"):
        method_paths[name + ".py"] = ROOT / "variants/phase5g_pure_formation/experiments" / (name + ".py")
    for name, path in method_paths.items():
        shutil.copyfile(path, sources / name)
    case_index, bundles = [], []
    for profile in ("base_noa", "base_transform", "T_transform", "TM_noa", "TM_transform"):
        runs = [r for r in report["runs"] if r["profile"] == profile]
        assert len(runs) == 50
        name = "traffic_" + profile + ".tar.gz"
        target = HERE / name
        if target.exists():
            raise FileExistsError(target)
        members, cases = {}, []
        with target.open("wb") as raw, gzip.GzipFile(filename="", fileobj=raw, mode="wb", compresslevel=9, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for run in sorted(runs, key=lambda r: (r["flow_veh_h_lane"], r["seed"], r["scenario"])):
                    folder = Path(run["ledger_dir"])
                    metadata = json.loads((folder / "case.json").read_text(encoding="utf-8"))
                    assert metadata["run"] == run
                    case = dict(profile=profile, case_id=folder.name, flow=run["flow_veh_h_lane"],
                                seed=run["seed"], scenario=run["scenario"], case_dir=run["case_dir"],
                                metadata_member="cases/" + folder.name + "/case.json")
                    cases.append(case)
                    case_index.append(dict(case, bundle=name))
                    for filename in ("case.json", "region_steps.jsonl.gz", "gate_brackets.jsonl.gz", "vehicles.json.gz"):
                        payload = (folder / filename).read_bytes()
                        if filename != "case.json":
                            assert sha(payload) == metadata["ledger_sha256"][filename]
                        member_name = "cases/" + folder.name + "/" + filename
                        info = tarfile.TarInfo(member_name)
                        info.size, info.mtime, info.mode = len(payload), 0, 0o644
                        archive.addfile(info, io.BytesIO(payload))
                        members[member_name] = dict(sha256=sha(payload), bytes=len(payload))
        size = target.stat().st_size
        assert size < 50_000_000
        manifest_name = "traffic_" + profile + ".manifest.json"
        write(HERE / manifest_name, dict(profile=profile, archive=name, archive_sha256=sha(target.read_bytes()),
                                       archive_bytes=size, cases=cases, members=members))
        bundles.append(dict(profile=profile, archive=name, manifest=manifest_name, bytes=size))
        print(json.dumps(dict(profile=profile, cases=len(cases), members=len(members), bytes=size)), flush=True)
    write(HERE / "case_index.json", case_index)
    files = {}
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name not in ("PUBLIC_MANIFEST.json", "verification.json") and "__pycache__" not in path.parts:
            files[path.relative_to(HERE).as_posix()] = dict(sha256=sha(path.read_bytes()), bytes=path.stat().st_size)
    write(HERE / "PUBLIC_MANIFEST.json", dict(cases=250, profiles=5, compressed_ledgers=750,
          bundles=bundles, files=files, method_source_hashes=report["metadata"]["evaluator_hashes"],
          original_json_ties="case.json and report runs retain input/result/trips/source/positions hashes; original JSON records are in the companion case evidence bundles",
          raw_positions_copied=False, compressed_ledger_bytes_preserved=True))


if __name__ == "__main__":
    main()
