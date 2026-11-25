"""Count one-hop capacities on the actual per-car solves without changing any command."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
import runrun
sys.path.insert(0, str(ROOT / "variants/phase5g_pure_formation"))
from noa import staggered


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("rest", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    regular = staggered.solve_transport
    counts = Counter()
    def observed(vehicles, slots, **options):
        fit = regular(vehicles, slots, **options)
        flags = options.get("moved", ())
        if not flags or fit.max_crossings != 1:
            return fit
        counts["one_hop_transform_decisions"] += 1
        if any(flags):
            counts["with_observed_crossing"] += 1
        pop = Counter(s for s, _ in vehicles)
        goal = Counter(s for s, _ in slots)
        fresh = Counter(s for (s,_), moved in zip(vehicles, flags) if not moved)
        left = minimum = 0
        for lane in sorted(pop.keys() | goal.keys()):
            right = left + pop[lane] - goal[lane]
            out = max(0,-left) + max(0,right)
            minimum += max(0,out - fresh[lane])
            left = right
        repeated = sum(used and row[0] != slots[j][0] for used,row,j in zip(flags, vehicles,fit.assignment))
        assert repeated >= minimum
        if not minimum:
            assert not repeated
        counts["forced_reuse"] += minimum > 0
        counts["above_minimum"] += repeated > minimum
        counts["unavoidable_assignments"] += minimum
        counts["repeated_assignments"] += repeated
        return fit
    staggered.solve_transport = observed
    args.out.mkdir(parents=True, exist_ok=False)
    rc = runrun.main(["--headless", "--output-base", str(args.out), *args.rest])
    (args.out/"decisions.json").write_text(json.dumps(counts, indent=2), encoding="utf8")
    return rc


if __name__ == "__main__":
    sys.exit(main())
