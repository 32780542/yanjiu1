"""Build/verify deduplicated, offline native-SUMO evidence using only Python stdlib."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
from statistics import mean
import tarfile
import tempfile

SOURCES = ("experiments/native_sumo.py", "experiments/global_reference.py",
           "experiments/complete_layers.py", "noa/native_rules.py",
           "run_native_flow.py", "research/common.py")
THRESHOLDS = (100, 600, 640, 1100)
SEGMENTS = {"upstream": (100, 600), "bottleneck": (640, 1100)}
FLAGS = ("vehicle_seconds", "participating_vehicle_seconds", "participation_rate",
         "mean_participants", "peak_participants", "episodes", "mean_episode_s", "max_episode_s")
SCOPE = "selected raw fields, full original positions local hash+rerunnable Git source"
README = """Compact native-SUMO evidence; Python standard library only.

Scope: selected raw fields, full original positions local hash+rerunnable Git source.
Original input/result/trips/sumo_command JSON and all six frozen sources are
byte-exact SHA256 blobs. Complete-layer source is preserved but never executed.
flags contains ALL original frames: time_s, active_ids, aligned integer flags.
crossings contains first observed equality or consecutive-frame crossing brackets
for each vehicle at x=100,600,640,1100, linked to entire original positions.gz SHA.
Original positions/events.gz are NOT included; their full-file SHA256 and bytes
are in index.json. Offline verification checks the selected fields and recomputes
metrics. With local originals, --check-originals additionally checks full hashes
and re-extracts every selected field. Hash linkage alone cannot prove a selected
field's origin when the complete original is unavailable.

Extract compact_evidence.py from this archive and run:
python -B compact_evidence.py verify bundle.tar.gz --report verification.json
Add --check-originals only where the indexed original run directories still exist.
The script does not import project controllers, detectors, SUMO, or third parties.
"""


def encode(value):
    return (json.dumps(value, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode()


def sha_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def raw_info(path):
    path = Path(path)
    return {"sha256": sha_file(path), "bytes": path.stat().st_size} if path.is_file() else {"missing": True}


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("non-finite or nonnumeric observation")
    return value


def equal(left, right):
    if isinstance(left, (float, int)) and not isinstance(left, bool):
        return (isinstance(right, (float, int)) and not isinstance(right, bool)
                and math.isfinite(left) and math.isfinite(right)
                and math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-7))
    return left == right


def compare(actual, expected, context):
    if not equal(actual, expected):
        raise ValueError(f"{context} mismatch: recomputed={actual!r}, saved={expected!r}")


def extract_positions(path, flags_path, original, vehicle_ids):
    """Select original fields without extrapolating across a missing frame."""
    crossings = {key: {} for key in vehicle_ids}
    previous, old_time, frames = {}, None, 0
    with gzip.open(path, "rt", encoding="utf-8") as source, Path(flags_path).open("wb") as target:
        for line in source:
            if not line.strip():
                continue
            frame = json.loads(line)
            time = number(frame["time_s"])
            if old_time is not None and time < old_time:
                raise ValueError("position frame time decreases")
            states, flags = frame["states"], frame.get("formation_states")
            if (not isinstance(flags, dict) or set(flags) != set(states)
                    or any(type(value) is not int or value not in (0, 1) for value in flags.values())):
                raise ValueError("invalid original formation flag data")
            ids = list(states)
            target.write(encode({"time_s": time, "active_ids": ids, "flags": [flags[key] for key in ids]}))
            current = {}
            for key, state in states.items():
                if key not in crossings:
                    raise ValueError("position vehicle not present in trips")
                point = [frames, time, number(state[0])]
                current[key] = point
                found = crossings[key]
                for threshold in THRESHOLDS:
                    name = str(threshold)
                    if name in found:
                        continue
                    if point[2] == threshold:
                        found[name] = {"samples": [point]}
                    elif key in previous and previous[key][2] < threshold < point[2] and time > previous[key][1]:
                        found[name] = {"samples": [previous[key], point]}
            previous, old_time, frames = current, time, frames + 1
    if not frames:
        raise ValueError("empty original positions")
    return {"positions_sha256": original["sha256"], "positions_bytes": original["bytes"],
            "frames": frames, "vehicles": crossings}


def build(manifests, output, analyzer_csvs=(), source_git=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    index = {"format": "native-compact-evidence-v1", "scope": SCOPE, "source_git": source_git,
             "blobs": {}, "manifests": [], "analyzers": [], "cases": []}
    expectations = {}
    for path in map(Path, analyzer_csvs):
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                expectations[str(Path(row["run_dir"]).resolve())] = row
    with tempfile.TemporaryDirectory(prefix="compact-build-", dir=output.parent) as temporary:
        store = Path(temporary)

        def add(data):
            digest = hashlib.sha256(data).hexdigest()
            if digest not in index["blobs"]:
                (store / digest).write_bytes(data)
                index["blobs"][digest] = {"bytes": len(data)}
            return digest

        for path in map(Path, analyzer_csvs):
            index["analyzers"].append({"path": str(path.resolve()), "blob": add(path.read_bytes())})
        seen = set()
        for manifest_path in map(Path, manifests):
            raw = manifest_path.read_bytes()
            records = json.loads(raw)
            if not isinstance(records, list):
                raise ValueError("manifest must be a JSON list")
            index["manifests"].append({"path": str(manifest_path.resolve()), "blob": add(raw)})
            for record in records:
                run = Path(record["run_dir"])
                run = (run if run.is_absolute() else manifest_path.parent / run).resolve()
                if str(run) in seen:
                    raise ValueError("duplicate case run_dir")
                seen.add(str(run))
                case = {"record": record, "run_dir": str(run), "files": {}, "originals": {}, "compact": {}}
                for name in ("input.json", "result.json", "trips.json", "sumo_command.json"):
                    case["files"][name] = add((run / name).read_bytes())
                inp = json.loads((run / "input.json").read_bytes())
                result = json.loads((run / "result.json").read_bytes())
                if set(inp.get("source_sha256", {})) != set(SOURCES):
                    raise ValueError("six-source manifest mismatch")
                if inp["source_sha256"] != result.get("source_sha256"):
                    raise ValueError("input/result source hash mismatch")
                for name in SOURCES:
                    digest = add((run / "source" / name).read_bytes())
                    compare(digest, inp["source_sha256"][name], "source hash " + name)
                    case["files"]["source/" + name] = digest
                for name in ("positions.jsonl.gz", "events.jsonl.gz"):
                    case["originals"][name] = raw_info(run / name)
                if case["originals"]["positions.jsonl.gz"].get("missing"):
                    raise ValueError("missing original positions")
                trips = json.loads((run / "trips.json").read_bytes())
                flag_path = store / "flags-current.jsonl"
                crossings = extract_positions(run / "positions.jsonl.gz", flag_path,
                                              case["originals"]["positions.jsonl.gz"],
                                              [trip["vehicle_id"] for trip in trips])
                case["compact"]["flags"] = add(flag_path.read_bytes())
                case["compact"]["crossings"] = add(encode(crossings))
                if str(run) in expectations:
                    case["analyzer_expected"] = expectations[str(run)]
                index["cases"].append(case)
                print(json.dumps({"packed_case": len(index["cases"]), "run_dir": str(run)}), flush=True)
        tool = Path(__file__).read_bytes()
        index["tool_sha256"] = hashlib.sha256(tool).hexdigest()
        index["readme_sha256"] = hashlib.sha256(README.encode()).hexdigest()
        archive = output / "bundle.tar.gz"
        with archive.open("wb") as raw_tar, gzip.GzipFile(filename="", mode="wb", fileobj=raw_tar,
                                                          compresslevel=6, mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode="w") as tar:
                def member(name, data):
                    info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o644
                    tar.addfile(info, io.BytesIO(data))
                member("index.json", encode(index))
                member("compact_evidence.py", tool)
                member("README.md", README.encode())
                for digest in sorted(index["blobs"]):
                    member("blobs/" + digest, (store / digest).read_bytes())
        (output / "bundle.json").write_bytes(encode({"archive": archive.name, **raw_info(archive),
            "case_count": len(index["cases"]), "unique_blobs": len(index["blobs"]), "scope": SCOPE,
            "index_sha256": hashlib.sha256(encode(index)).hexdigest()}))
    return archive


def traffic(trips, result, inp):
    entered = [row for row in trips if row["entered_s"] is not None]
    completed = [row for row in entered if row["exited_s"] is not None]
    for row in trips:
        if (row["entered_s"] is not None and row["entered_s"] < row["requested_s"]
                or row["exited_s"] is not None and (row["entered_s"] is None or row["exited_s"] < row["entered_s"])):
            raise ValueError("invalid trip time ordering")
    avg = lambda values: mean(values) if values else None
    wait = avg([row["entered_s"] - row["requested_s"] for row in entered])
    travel = avg([row["exited_s"] - row["entered_s"] for row in completed])
    system = avg([row["exited_s"] - row["requested_s"] for row in completed])
    distance = sum(row["distance_m"] for row in completed)
    fuel = sum(row["fuel_mg"] for row in completed)
    ratio = fuel / distance if distance else None
    all_completed = len(completed) == len(trips)
    safe = not result.get("collisions") and not result.get("teleports") and result.get("error") is None
    eligible = bool(trips) and all_completed and safe
    duration = inp["case"]["demand_duration_s"]
    return {"requested": len(trips), "departed": len(entered), "completed": len(completed),
        "all_completed": all_completed, "performance_comparison_eligible": eligible,
        "mean_entry_wait_s": wait if eligible else None,
        "mean_travel_time_s": travel if eligible else None,
        "mean_system_time_s": system if eligible else None,
        "fuel_g_per_km": ratio if eligible else None,
        "completed_subset_mean_travel_time_s": travel, "completed_subset_mean_system_time_s": system,
        "departed_subset_mean_entry_wait_s": wait, "completed_subset_fuel_g_per_km": ratio,
        "completed_fuel_mg": fuel, "all_fuel_mg": sum(row["fuel_mg"] for row in trips),
        "exit_flow_veh_h": (sum(row["exited_s"] <= duration for row in completed) * 3600 / duration
                            if result["actual_end_s"] >= duration - 1e-8 else None),
        "clearance_after_demand_s": max(0, max((row["exited_s"] for row in completed), default=duration) - duration)
                                    if all_completed else None,
        "lane_changes": sum(row.get("lane_changes", 0) for row in trips),
        "lane_change_completions": sum(len(row.get("lane_completion_events", [])) for row in trips)}


def audit_selected(flag_path, crossings, trips, step):
    wanted = {}
    times = {}
    ids = {row["vehicle_id"] for row in trips}
    if set(crossings["vehicles"]) != ids:
        raise ValueError("crossing/trip vehicle identity mismatch")
    for key, entries in crossings["vehicles"].items():
        times[key] = {}
        if not set(entries).issubset(map(str, THRESHOLDS)):
            raise ValueError("unknown crossing threshold")
        for threshold, entry in entries.items():
            samples = entry["samples"]
            if len(samples) not in (1, 2) or any(len(sample) != 3 for sample in samples):
                raise ValueError("invalid crossing bracket samples")
            for frame, time, x in samples:
                if type(frame) is not int or frame < 0:
                    raise ValueError("invalid bracket frame index")
                number(time); number(x)
                wanted.setdefault(frame, []).append((key, time))
            if len(samples) == 1:
                if samples[0][2] != int(threshold):
                    raise ValueError("single crossing bracket must equal threshold")
                crossing_time = samples[0][1]
            else:
                (f0, t0, x0), (f1, t1, x1) = samples
                if f1 != f0 + 1 or not t1 > t0 or not x0 < int(threshold) < x1:
                    raise ValueError("invalid crossing bracket order")
                crossing_time = t0 + (t1 - t0) * (int(threshold) - x0) / (x1 - x0)
            times[key][int(threshold)] = crossing_time
    old_time = first = None
    previous, active, episodes = {}, {}, []
    vehicle_seconds = participating = peak = count = 0
    with Path(flag_path).open("rb") as stream:
        for raw in stream:
            frame = json.loads(raw)
            time = number(frame["time_s"])
            names, values = frame["active_ids"], frame["flags"]
            if (not isinstance(names, list) or len(set(names)) != len(names) or not set(names).issubset(ids)
                    or len(values) != len(names) or any(type(v) is not int or v not in (0, 1) for v in values)):
                raise ValueError("invalid compact flag frame")
            flags = dict(zip(names, values))
            if old_time is None:
                first = time
            else:
                dt = time - old_time
                if dt < 0 or not equal(dt, step):
                    raise ValueError("flag frame time/step mismatch")
                vehicle_seconds += dt * len(previous)
                participating += dt * sum(previous.values())
                for key in active:
                    active[key] += dt
            for key in tuple(active):
                if not flags.get(key):
                    episodes.append(active.pop(key))
            for key, value in flags.items():
                if value:
                    active.setdefault(key, 0.0)
            for key, expected_time in wanted.pop(count, []):
                if key not in flags or time != expected_time:
                    raise ValueError("bracket sample not in its active flag frame")
            peak = max(peak, sum(values))
            previous, old_time, count = flags, time, count + 1
    if not count or wanted or count != crossings["frames"]:
        raise ValueError("flag frame count/bracket mismatch")
    episodes.extend(active.values())
    duration = old_time - first
    summary = {"vehicle_seconds": vehicle_seconds, "participating_vehicle_seconds": participating,
        "participation_rate": participating / vehicle_seconds if vehicle_seconds else None,
        "mean_participants": participating / duration if duration else None, "peak_participants": peak,
        "episodes": len(episodes), "mean_episode_s": mean(episodes) if episodes else None,
        "max_episode_s": max(episodes) if episodes else None}
    segments = {}
    for name, (x0, x1) in SEGMENTS.items():
        vehicles = {row["vehicle_id"]: times[row["vehicle_id"]][x1] - times[row["vehicle_id"]][x0]
                    for row in trips if row["entered_s"] is not None
                    and x0 in times[row["vehicle_id"]] and x1 in times[row["vehicle_id"]]
                    and times[row["vehicle_id"]][x1] >= times[row["vehicle_id"]][x0]}
        segments[name] = {"eligible_vehicles": len(vehicles), "total_vehicles": len(trips),
                          "mean_time_s": mean(vehicles.values()) if vehicles else None, "vehicles": vehicles}
    return summary, segments, count, old_time


def verify(archive, check_originals=False):
    archive = Path(archive)
    with tempfile.TemporaryDirectory(prefix="compact-verify-") as temporary:
        store = Path(temporary)
        found, index = set(), None
        with tarfile.open(archive, "r|gz") as tar:
            for member in tar:
                if not member.isfile() or member.name in found:
                    raise ValueError("invalid or duplicate archive member")
                found.add(member.name)
                stream = tar.extractfile(member)
                if member.name == "index.json":
                    index = json.load(stream)
                    if index.get("format") != "native-compact-evidence-v1":
                        raise ValueError("unsupported evidence format")
                elif index is None:
                    raise ValueError("index must be first archive member")
                elif member.name in ("compact_evidence.py", "README.md"):
                    field = "tool_sha256" if member.name.endswith(".py") else "readme_sha256"
                    compare(hashlib.sha256(stream.read()).hexdigest(), index[field], member.name + " hash")
                elif re.fullmatch(r"blobs/[0-9a-f]{64}", member.name):
                    digest = member.name[6:]
                    if digest not in index["blobs"]:
                        raise ValueError("unindexed blob")
                    hasher, size = hashlib.sha256(), 0
                    with (store / digest).open("wb") as target:
                        while chunk := stream.read(1024 * 1024):
                            hasher.update(chunk); size += len(chunk); target.write(chunk)
                    compare(hasher.hexdigest(), digest, "blob hash")
                    compare(size, index["blobs"][digest]["bytes"], "blob bytes")
                else:
                    raise ValueError("unexpected archive member")
        if index is None or not {"blobs/" + sha for sha in index["blobs"]}.issubset(found):
            raise ValueError("missing indexed blobs")

        def data(digest):
            if digest not in index["blobs"]:
                raise ValueError("unindexed reference")
            return json.loads((store / digest).read_bytes())

        cases = []
        for case in index["cases"]:
            files = case["files"]
            required = {"input.json", "result.json", "trips.json", "sumo_command.json"} | {"source/" + n for n in SOURCES}
            if set(files) != required:
                raise ValueError("missing required original JSON/source files")
            inp, result, trips = (data(files[n]) for n in ("input.json", "result.json", "trips.json"))
            if len({t["vehicle_id"] for t in trips}) != len(trips) or {t["vehicle_id"] for t in trips} != {a["vehicle_id"] for a in inp["arrivals"]}:
                raise ValueError("trip/input identity mismatch")
            if set(inp["source_sha256"]) != set(SOURCES) or inp["source_sha256"] != result["source_sha256"]:
                raise ValueError("source manifest mismatch")
            for name in SOURCES:
                compare(files["source/" + name], inp["source_sha256"][name], "source hash " + name)
            crossings = data(case["compact"]["crossings"])
            original = case["originals"]["positions.jsonl.gz"]
            compare(crossings["positions_sha256"], original["sha256"], "crossing original positions hash")
            compare(crossings["positions_bytes"], original["bytes"], "crossing original positions bytes")
            flags, segments, count, end = audit_selected(store / case["compact"]["flags"], crossings,
                                                        trips, inp["positions_step_s"])
            for key in FLAGS:
                compare(flags[key], result["formation_state"][key], "formation_state." + key)
            compare(end, result["actual_end_s"], "positions end")
            metrics = traffic(trips, result, inp)
            for key, value in metrics.items():
                if key in result:
                    compare(value, result[key], "result." + key)
            expected = case.get("analyzer_expected", {})
            available = {**metrics, "positions_frames": count,
                         **{"flag_" + key: value for key, value in flags.items()},
                         **{"flag_recomputed_" + key: value for key, value in flags.items()},
                         **{name + "_" + key: value for name, segment in segments.items()
                            for key, value in segment.items() if key != "vehicles"}}
            for key, value in available.items():
                if key in expected:
                    saved = expected[key]
                    parsed = None if saved == "" else saved == "True" if saved in ("True", "False") else float(saved)
                    compare(value, parsed, "analyzer." + key)
            if check_originals:
                run = Path(case["run_dir"])
                for name, info in case["originals"].items():
                    observed = raw_info(run / name)
                    if observed != info:
                        raise ValueError("original full-file hash/bytes mismatch: " + str(run / name))
                for name, digest in files.items():
                    compare(sha_file(run / name), digest, "original file hash " + name)
                audit_flags = store / "audit-current.jsonl"
                audit_crossings = extract_positions(run / "positions.jsonl.gz", audit_flags, original,
                                                    [row["vehicle_id"] for row in trips])
                compare(sha_file(audit_flags), case["compact"]["flags"], "original selected flags hash")
                compare(hashlib.sha256(encode(audit_crossings)).hexdigest(), case["compact"]["crossings"], "original selected crossings hash")
            cases.append({"record": case["record"], "positions_sha256": original["sha256"],
                          "traffic": metrics, "formation_state": flags, "segments": segments,
                          "frames": count, "analyzer_compared": bool(expected)})
        return {"cases_verified": len(cases), "unique_blobs": len(index["blobs"]),
                "archive": {**raw_info(archive), "path": str(archive)}, "scope": SCOPE,
                "local_originals_checked": check_originals, "cases": cases}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--manifest", action="append", required=True, type=Path)
    make.add_argument("--output", required=True, type=Path)
    make.add_argument("--analyzer-csv", action="append", default=[], type=Path)
    make.add_argument("--source-git")
    check = commands.add_parser("verify")
    check.add_argument("archive", type=Path)
    check.add_argument("--check-originals", action="store_true")
    check.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        archive = build(args.manifest, args.output, args.analyzer_csv, args.source_git)
        print(json.dumps({"archive": str(archive), **raw_info(archive)}), flush=True)
    else:
        report = verify(args.archive, args.check_originals)
        if args.report:
            args.report.write_bytes(encode(report))
        print(json.dumps({key: value for key, value in report.items() if key != "cases"}), flush=True)


if __name__ == "__main__":
    main()
