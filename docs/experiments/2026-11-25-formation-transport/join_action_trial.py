"""Check whether a proposed formation move also belongs to a least-crossing placement after a visible join."""
import argparse
from pathlib import Path
import subprocess

from private_burden_trial import BASE,VARIANT
from run_study import REQUIRED,OPTIONAL,ROOT


HELPER = """
@lru_cache(maxsize=512)
def _extendible(counts, origin, step):
    from noa.transport import lane_bounds
    lanes = len(counts)
    source = [l for l,n in enumerate(counts) for _ in range(n)]
    layers, tail = divmod(len(source),lanes)
    targets = []
    for extra in combinations(range(lanes),tail):
        if lanes == 3 and 1 in extra and (0 not in extra or 2 not in extra):
            continue
        target = list(range(lanes))*layers + list(extra)
        targets.append((lane_bounds(source,target),target))
    best = min(cost for cost, _ in targets)
    remaining = source.copy()
    remaining.remove(origin)
    for cost,target in targets:
        if cost != best:
            continue
        for lane in set(target):
            if origin+(lane>origin)-(lane<origin) != step or abs(origin-lane) > best[0]:
                continue
            rest = target.copy()
            rest.remove(lane)
            radius, total = lane_bounds(remaining,rest)
            if radius <= best[0] and total + abs(lane-origin) == best[1]:
                return True
    return False


def _allows_join(ego, rows, group, lanes, step):
    segments = []
    for car in sorted((ego,*rows),key=lambda c:(c.x,c.lane)):
        if not segments or car.x-segments[-1][-1].x > GROUP_GAP:
            segments.append([])
        segments[-1].append(car)
    own = next(i for i,g in enumerate(segments) if ego in g)
    considered = __SETS__
    for expanded in considered:
        counts = tuple(sum(c.lane==lane for c in expanded) for lane in range(lanes))
        if not _extendible(counts,ego.lane,step):
            return False
    return True

"""


def build(out, mode):
    out.mkdir(parents=True,exist_ok=False)
    for name in (*REQUIRED,*OPTIONAL):
        dest=out/name;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(subprocess.check_output(["git","show",f"{BASE}:{VARIANT}/{name}"],cwd=ROOT))
    (out/"tmp").mkdir()
    dest=out/"noa/native_rules.py";code=dest.read_text(encoding="utf8")
    sets={"front":"[list(group)+segments[own+1]] if own+1 < len(segments) else []",
          "either":"[list(group)+segments[i] for i in (own-1,own+1) if 0 <= i < len(segments)]",
          "all":"[[c for segment in segments for c in segment]] if len(segments)>1 else []"}
    mark="def _transport(ego, rows, memory, lanes, opened, transforming):"
    code=code.replace("from math import sqrt","from math import sqrt\nfrom functools import lru_cache\nfrom itertools import combinations")
    code=code.replace(mark,HELPER.replace("__SETS__",sets[mode])+mark)
    marker="    since = memory.proposal_since if step == memory.proposed_step else ego.time"
    assert code.count(marker)==1
    code=code.replace(marker,"""    if not transforming and step is not None and not _allows_join(ego, rows, group, lanes, step):
        step = None
"""+marker)
    dest.write_text(code,encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);p.add_argument("--mode",required=True,choices=("front","either","all"))
    a=p.parse_args();build(a.out,a.mode)
