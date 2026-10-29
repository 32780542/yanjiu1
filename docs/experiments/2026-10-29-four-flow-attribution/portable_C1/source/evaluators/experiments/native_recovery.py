"""Offline first-adjustment to confirmed two-lane physical membership times.

t_adjust is first measured x>=640 (no interpolated crossing). Two-lane groups use
[640,1200), upstream three-lane groups [0,640). We call the frozen groups_at and
locally reproduce only its row/adjacent-row confirmation clock. For each adjacent
pair the confirmation time is max(birth(row1), birth(row2), birth(edge))+1s;
membership needs any confirmed adjacent pair. This is equivalent to _mature's
>=2-row membership and preserves old members when a new tail joins.

Like complete_layers, states are left-held between samples; a threshold may fall
inside an interval. Endpoint confirmation requires a still-valid observed group.
These are sampled estimates, not proof against unrecorded short disruptions.
Unobserved recovery is censored at road/track/recording end, never delay=0. Delay
mean/median/p95 condition on observed events; upstream_formed separates recovery
of previously confirmed three-lane members from newly detected formation.
"""

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
from statistics import median

from experiments.complete_layers import groups_at


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relation_keys(groups):
    keys = set()
    for group in groups:
        rows = group["layers"]
        keys.update(("row", row) for row in rows)
        keys.update(("edge", a, b) for a, b in zip(rows, rows[1:]))
    return keys


def _membership_times(groups, born, hold):
    times = {}
    for group in groups:
        for a, b in zip(group["layers"], group["layers"][1:]):
            confirmed = max(born[("row", a)], born[("row", b)], born[("edge", a, b)]) + hold
            for vehicle in a + b:
                times[vehicle] = min(times.get(vehicle, confirmed), confirmed)
    return times


def _statistics(rows):
    delays = sorted(r["delay_s"] for r in rows if r["delay_s"] is not None)
    rank = (len(delays) - 1) * 0.95
    lower = int(rank) if delays else 0
    p95 = (
        (delays[lower] + (delays[min(lower + 1, len(delays) - 1)] - delays[lower]) * (rank - lower))
        if delays
        else None
    )
    return dict(
        subjects=len(rows),
        recovered=len(delays),
        censored=len(rows) - len(delays),
        observed_recovery_fraction=len(delays) / len(rows) if rows else None,
        conditional_mean_delay_s=sum(delays) / len(delays) if delays else None,
        conditional_median_delay_s=median(delays) if delays else None,
        conditional_p95_delay_s=p95,
    )


def evaluate_recovery(
    case_dir,
    *,
    adjustment_x=640.0,
    exit_x=1200.0,
    confirm_s=1.0,
    gap=30.0,
    position_tolerance=2.0,
    speed_tolerance=0.5,
    center_tolerance=0.3,
):
    """Return per-vehicle events plus conditional summaries, independent of mode.

    A subject must actually be observed at/after adjustment_x. upstream_formed
    means a three-lane confirmation strictly before its t_adjust. Starting already
    beyond the threshold is marked; the reported start is an observation, not an
    assumed exact crossing. Censoring is descriptive, not a structural-break count.
    """
    if not 0 < adjustment_x < exit_x or confirm_s < 0:
        raise ValueError("Require 0 < adjustment_x < exit_x and confirm_s >= 0")
    case_dir = Path(case_dir).resolve()
    positions = case_dir / "positions.jsonl.gz"
    trips_path = case_dir / "trips.json"
    if trips_path.is_file():
        trip_rows = _read(trips_path)
    else:
        trips_path = case_dir / "trips.jsonl.gz"
        with gzip.open(trips_path, "rt", encoding="utf-8") as stream:
            trip_rows = [json.loads(line) for line in stream]
    trips = {r["vehicle_id"]: r for r in trip_rows}
    config = _read(case_dir / "input.json").get("case", {}) if (case_dir / "input.json").is_file() else {}
    result = _read(case_dir / "result.json") if (case_dir / "result.json").is_file() else {}
    mode = config.get("mode", result.get("mode", "unknown"))
    applicable = config.get("scenario", "lane_drop") == "lane_drop"
    subjects, first_seen, last_seen, first_out = {}, {}, {}, {}
    upstream_first, recovered = {}, {}
    born, previous, last_time, max_step = {3: {}, 2: {}}, None, None, None
    parameters = dict(
        adjustment_x=adjustment_x,
        exit_x=exit_x,
        confirm_s=confirm_s,
        gap=gap,
        position_tolerance=position_tolerance,
        speed_tolerance=speed_tolerance,
        center_tolerance=center_tolerance,
    )

    def emit(zone_groups, clocks, start, end=None):
        for lanes in (3, 2):
            for vehicle, threshold in _membership_times(zone_groups[lanes], clocks[lanes], confirm_s).items():
                when = max(start, threshold)
                if lanes == 2:
                    if vehicle not in subjects:
                        continue
                    when = max(when, subjects[vehicle])
                    exited = trips.get(vehicle, {}).get("exited_s")
                    if exited is not None and when >= exited - 1e-9:
                        continue
                if (end is None and when > start + 1e-9) or (end is not None and when >= end - 1e-9):
                    continue
                target = upstream_first if lanes == 3 else recovered
                target[vehicle] = min(target.get(vehicle, when), when)

    with gzip.open(positions, "rt", encoding="utf-8") as stream:
        for line in stream if applicable else ():
            frame = json.loads(line)
            time_s, states = float(frame["time_s"]), frame["states"]
            if last_time is not None:
                if time_s <= last_time:
                    raise ValueError("Position timestamps must strictly increase")
                max_step = max(max_step or 0.0, time_s - last_time)
            for vehicle, state in states.items():
                first_seen.setdefault(vehicle, time_s)
                last_seen[vehicle] = time_s
                if state[0] >= adjustment_x:
                    subjects.setdefault(vehicle, time_s)
                if state[0] >= exit_x:
                    first_out.setdefault(vehicle, time_s)
            if previous is not None:
                emit(previous, born, last_time, time_s)
            zones = {
                lanes: groups_at(
                    {v: s for v, s in states.items() if low <= s[0] < high},
                    lanes,
                    gap=gap,
                    position_tolerance=position_tolerance,
                    speed_tolerance=speed_tolerance,
                    center_tolerance=center_tolerance,
                )
                for lanes, low, high in ((3, 0.0, adjustment_x), (2, adjustment_x, exit_x))
            }
            born = {
                lanes: {key: born[lanes].get(key, time_s) for key in _relation_keys(zones[lanes])}
                for lanes in (3, 2)
            }
            emit(zones, born, time_s)
            previous, last_time = zones, time_s

    rows = []
    for vehicle, adjustment in subjects.items():
        two_time = recovered.get(vehicle)
        upstream = upstream_first.get(vehicle)
        prior = upstream is not None and upstream < adjustment - 1e-9
        reason = censor_time = None
        if two_time is None:
            exited = trips.get(vehicle, {}).get("exited_s")
            if exited is not None and exited <= last_time + 1e-9:
                reason, censor_time = "road_exit", exited
            elif vehicle in first_out:
                reason, censor_time = "road_exit", first_out[vehicle]
            else:
                reason = "recording_end" if last_seen[vehicle] == last_time else "track_end"
                censor_time = last_seen[vehicle]
        rows.append(
            dict(
                vehicle_id=vehicle,
                t_adjust_s=adjustment,
                t_two_lane_s=two_time,
                delay_s=two_time - adjustment if two_time is not None else None,
                upstream_formed=prior,
                upstream_first_confirmed_s=upstream if prior else None,
                censored=two_time is None,
                censor_reason=reason,
                censored_at_s=censor_time,
                first_observation_s=first_seen[vehicle],
                last_observation_s=last_seen[vehicle],
                adjust_start_is_first_observation=adjustment == first_seen[vehicle],
            )
        )
    return dict(
        case_dir=str(case_dir),
        mode=mode,
        seed=config.get("seed"),
        scenario=config.get("scenario"),
        case_safe=result.get("safe"),
        case_all_completed=result.get("all_completed"),
        applicable=applicable,
        event_interpretation=(
            "Not applicable: no lane drop"
            if not applicable
            else (
                "Detected two-lane geometry events; NOA is not controlled formation"
                if mode == "noa"
                else "Physical two-lane membership; upstream_formed identifies prior formation recovery"
            )
        ),
        **_statistics(rows),
        upstream_formed=_statistics([r for r in rows if r["upstream_formed"]]),
        not_upstream_formed=_statistics([r for r in rows if not r["upstream_formed"]]),
        vehicles_seen=len(first_seen),
        trip_requests=len(trips),
        not_observed_adjusting=len(set(trips) - set(subjects)),
        max_position_sample_step_s=max_step,
        recording_end_s=last_time,
        conditional_statistics_note="Delay statistics include observed recoveries only; censored delays are undefined",
        parameters=parameters,
        positions_sha256=_sha(positions),
        trips_sha256=_sha(trips_path),
        evaluator_source_sha256=_sha(__file__),
        layer_evaluator_source_sha256=_sha(Path(__file__).with_name("complete_layers.py")),
        per_vehicle=rows,
    )


def summarize_manifest(manifest_path, output_dir):
    """Evaluate a JSON path array or {cases:[paths]} into a fresh JSON/CSV folder."""
    manifest_path, output_dir = Path(manifest_path).resolve(), Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(output_dir)
    manifest = _read(manifest_path)
    cases = manifest["cases"] if isinstance(manifest, dict) else manifest
    runs = [evaluate_recovery(manifest_path.parent / case) for case in cases]
    report = dict(manifest_sha256=_sha(manifest_path), runs=runs)
    run_rows, vehicle_rows = [], []
    for run in runs:
        row = {k: v for k, v in run.items() if not isinstance(v, (dict, list))}
        for group in ("upstream_formed", "not_upstream_formed"):
            row.update({group + "_" + k: v for k, v in run[group].items()})
        run_rows.append(row)
        vehicle_rows += [
            dict(case_dir=run["case_dir"], mode=run["mode"], seed=run["seed"], **v)
            for v in run["per_vehicle"]
        ]
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    for name, rows in (("runs", run_rows), ("per_vehicle", vehicle_rows)):
        with (output_dir / (name + ".csv")).open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, list(dict.fromkeys(k for row in rows for k in row)))
            writer.writeheader()
            writer.writerows(rows)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    report = summarize_manifest(args.manifest, args.output)
    print(
        json.dumps(
            dict(
                output=str(args.output.resolve()),
                runs=len(report["runs"]),
                subjects=sum(r["subjects"] for r in report["runs"]),
                recovered=sum(r["recovered"] for r in report["runs"]),
            )
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
