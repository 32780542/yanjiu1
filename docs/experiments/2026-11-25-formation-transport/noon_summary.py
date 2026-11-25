"""Compare the same two sets of 192 closed-loop cohorts, preserving failed formations."""
import csv
from pathlib import Path
from statistics import median

from noon_cases import read

HERE = Path(__file__).resolve().parent
DATA = HERE.parents[2] / "tmp"
BATCHES = {
    "morning": ("reference-fresh", "final-reference"),
    "join_one_hop": ("combined-fresh", "combined-final192"),
    "follow_slot": ("receive-fresh192", "receive-final192"),
    "start_on_sight_only": ("compact-receive", "compact-last"),
    "joint_join": ("joint-fresh", "joint-final"),
    "instant_conflict": ("conflict-matched", "conflict-confirm"),
    "target_conflict": ("target-first", "target-last"),
    "hold_conflict": ("hold-first", "hold-last"),
    "minimum_reuse": ("reuse-first", "reuse-last"),
}


def write(name, rows):
    with (HERE / name).open("w", encoding="utf8", newline="") as output:
        writer = csv.DictWriter(output, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run(name):
    folder = DATA / ("nov25-noon-" + name)
    return read([folder]) if (folder / "summary.csv").is_file() else {}


def summarize(base, group):
    def optimal(row, stage):
        return row[stage + "_excess_total"] == row[stage + "_excess_max"] == 0
    def best_tail(row, stage):
        return (row[stage + "_actual_total"] is not None
                and row[stage + "_actual_total"] == row[stage + "_best_legal_total"]
                and row[stage + "_actual_max"] == row[stage + "_best_legal_max"])
    return dict(cases=len(group), cars=sum(r["n"] for r in group),
                completed=sum(r["completed"] for r in group),
                collisions=sum(r["collisions"] for r in group), teleports=sum(r["teleports"] for r in group),
                both=sum(r["whole_both"] for r in group),
                gained=sum(r["whole_both"] and not b["whole_both"] for r,b in zip(group,base)),
                lost=sum(b["whole_both"] and not r["whole_both"] for r,b in zip(group,base)),
                upstream_optimal=sum(optimal(r,"formation") for r in group),
                downstream_optimal=sum(optimal(r,"transform") for r in group),
                upstream_best_legal_tail=sum(best_tail(r,"formation") for r in group),
                downstream_best_legal_tail=sum(best_tail(r,"transform") for r in group),
                both_hold_at_least_10s=sum(min(r["upstream_whole_hold_s"], r["downstream_whole_hold_s"]) >= 10
                                            for r in group),
                median_upstream_hold_s=median(r["upstream_whole_hold_s"] for r in group),
                median_downstream_hold_s=median(r["downstream_whole_hold_s"] for r in group))


def main():
    records, exceptions = [], []
    for method, pair in BATCHES.items():
        for cohort, (old, new) in enumerate(zip(BATCHES["morning"], pair), 1):
            a, b = run(old), run(new)
            if not b:
                print("pending", method, cohort)
                continue
            assert set(a) == set(b) and len(a) == 192
            for k, row in b.items():
                before = a[k]
                assert all(row[t] == before[t] for t in ("first_frame_sha256", "tape_sha256", "n", "completed"))
                assert row["completed"] == row["n"] and row["status"] == before["status"] == "drained"
                if row["whole_both"] != before["whole_both"]:
                    exceptions.append(dict(method=method, cohort=cohort, road=k[0], n=k[1], spacing=k[2],
                                           seed=k[3], before=before["whole_both"], after=row["whole_both"],
                                           upstream_s=row["upstream_whole_hold_s"], downstream_s=row["downstream_whole_hold_s"]))
            for road in ("all", "3to2", "4to3", "2to3", "3to4"):
                keys = sorted(k for k in b if road == "all" or k[0] == road)
                records.append(dict(method=method, cohort=cohort, road=road,
                                    **summarize([a[k] for k in keys], [b[k] for k in keys])))
    write("noon_comparison.csv", records)
    if exceptions:
        write("noon_changed_cases.csv", exceptions)


if __name__ == "__main__":
    main()
