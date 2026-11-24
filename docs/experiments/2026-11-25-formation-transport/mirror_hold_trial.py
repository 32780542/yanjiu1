"""Build the two-lane fixed-population mirror trial from the frozen selected source."""
import argparse
import hashlib
from pathlib import Path
import shutil
import random
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = ROOT / "tmp/nov25study/selected_holdout_900/source"
DIGEST = "c0b2c15fc13ee893814d5f6929a0184f108ec3ce1701f0806a663e0e46634562"

MIRROR = '''
def _holding_offsets(group, spacing, head_clipped, tail_clipped, primary):
    """Compare both legal phases if both keep every car in its current lane."""
    lanes = sorted(car.lane for car in group)
    if lanes[0] < 0 or lanes[-1] > 1 or sorted(j for j, _ in primary) != lanes:
        return primary
    alternate = _balanced_offsets(group, 2, spacing, head_clipped, tail_clipped, mirror=True)
    if sorted(j for j, _ in alternate) != lanes:
        return primary

    # Within each actual lane the monotone matching minimizes square distance.
    # A free common origin puts mean target x at mean observed x in both phases.
    def offsets_by_car(profile):
        return [d for _, d in sorted(profile, key=lambda pair: (pair[0], pair[1]))]

    first = offsets_by_car(primary)
    other = offsets_by_car(alternate)
    n = len(first)
    shift = (sum(other) - sum(first)) / n
    changes = [shift + a - b for a, b in zip(first, other)]
    if all(abs(change) < 1e-9 for change in changes):
        return primary
    ordered = sorted(group, key=lambda car: (car.lane, -car.x))
    anchor = ordered[0].x
    center = (sum(car.x - anchor for car in ordered) + sum(first)) / n
    gain = sum(change * (2 * (car.x - anchor - center + d) - change)
               for car, d, change in zip(ordered, first, changes))
    uncertainty = 2 * POSITION_ERROR_M * sum(abs(change) for change in changes)
    return alternate if gain > uncertainty + 1e-8 else primary

'''


def build(out):
    out = out.resolve()
    shutil.copytree(BASE, out, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "tmp"))
    (out / "tmp").mkdir(exist_ok=True)
    path = out / "noa/staggered.py"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == DIGEST
    data = path.read_text(encoding="utf-8")
    data = data.replace("def _balanced_offsets(group, lanes, spacing, head_clipped, tail_clipped):",
                        "def _balanced_offsets(group, lanes, spacing, head_clipped, tail_clipped, mirror=False):")
    data = data.replace("    # A sensor may first", "    if mirror:\n        lead_phase = 1 - lead_phase\n    # A sensor may first")
    data = data.replace("def choose_target(", MIRROR + "\ndef choose_target(")
    fallback = "        offsets = _balanced_offsets(group, lanes, spacing, head_clipped, tail_clipped)"
    assert data.count(fallback) == 1
    data = data.replace(fallback, fallback + "\n        if lanes == 2:\n            offsets = _holding_offsets(group, spacing, head_clipped, tail_clipped, offsets)")
    path.write_text(data, encoding="utf-8")
    print(out, hashlib.sha256(path.read_bytes()).hexdigest())


def verify(out):
    sys.path.insert(0, str(out.resolve()))
    from noa import staggered as st
    from noa.native_rules import Vehicle
    assert Path(st.__file__).resolve().is_relative_to(out.resolve())
    rng = random.Random(73451)
    compared = changed = 0
    for _ in range(2000):
        n = rng.randrange(2, 13)
        group = sorted([Vehicle(i, rng.uniform(0, 180), (j+.5)*3.3,28.8,j)
                        for i,j in enumerate(rng.choices((0,1), k=n))],key=lambda c:-c.x)
        h,t = rng.choice((True,False)),rng.choice((True,False))
        primary = st._balanced_offsets(group,2,29.98,h,t)
        other = st._balanced_offsets(group,2,29.98,h,t,mirror=True)
        result = st._holding_offsets(group,29.98,h,t,primary)
        inputs=[(c.lane,c.x) for c in group]
        profiles=[]
        for offsets in (primary,other):
            origin=(sum(c.x for c in group)+sum(d for _,d in offsets))/n
            slots=[(j,origin-d) for j,d in offsets]
            fit=st.solve_transport(inputs,slots)
            profiles.append((fit,[slots[k][1] for k in fit.assignment]))
        a,b=profiles
        expected=False
        if a[0].max_crossings==b[0].max_crossings==0:
            compared+=1
            margin=.1*sum(abs(x-y) for x,y in zip(a[1],b[1]))
            expected=a[0].squared_displacement-b[0].squared_displacement>margin+1e-8
        assert (result is not primary)==expected
        changed+=expected
    print(f"2000 independent full assignment comparisons, {compared} eligible, {changed} strict switches")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("--verify", action="store_true")
    args=parser.parse_args()
    (verify if args.verify else build)(args.out)
