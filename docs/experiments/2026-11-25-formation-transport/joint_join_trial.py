"""Largest simultaneous one-hop batch shared by a local group and its larger observed population."""
import argparse
from pathlib import Path
from slot_predecessor_trial import build

HELPER="""
@lru_cache(maxsize=512)
def _shared_quota(counts, local_flow):
    from noa.transport import lane_bounds
    width = len(counts)
    origin = [k for k,n in enumerate(counts) for _ in range(n)]
    layers, rem = divmod(len(origin),width)
    best_key = None
    answer = None
    for extra in combinations(range(width),rem):
        if width==3 and 1 in extra and not {0,2}.issubset(extra):
            continue
        goal=[layers+(k in extra) for k in range(width)]
        target=[k for k,n in enumerate(goal) for _ in range(n)]
        radius,total=lane_bounds(origin,target)
        flows=tuple(accumulate(a-b for a,b in zip(counts,goal)))[:-1]
        shared=tuple(min(abs(a),abs(b)) if a*b>0 else 0 for a,b in zip(local_flow,flows))
        key=(radius,total,-sum(shared),extra)
        if best_key is None or key < best_key:
            best_key=key
            answer=shared
    return answer if best_key[0]<=1 else None


def _shared_move(group, slots, fit, rank, wider):
    if fit.max_crossings!=1:
        return True
    here=group[rank].lane
    there=slots[fit.assignment[rank]][0]
    if here==there:
        return True
    width=len(wider)
    n=[0]*width
    q=[0]*width
    for car,(lane,_) in zip(group,slots):
        n[car.lane]+=1
        q[lane]+=1
    net=tuple(accumulate(a-b for a,b in zip(n,q)))[:-1]
    quota=_shared_quota(wider,net)
    if quota is None:
        return True
    edge=min(here,there)
    if quota[edge]==abs(net[edge]):
        return True
    ordered=sorted((abs(group[i].x-slots[j][1]), -group[i].x, i)
                   for i,j in enumerate(fit.assignment) if group[i].lane==here and slots[j][0]==there)
    return rank in [i for _,_,i in ordered[:quota[edge]]]

"""


def prepare(out):
    build(out,"order","combined")
    f=out/"noa/native_rules.py";s=f.read_text(encoding="utf8")
    a=s.index("@lru_cache(maxsize=512)\ndef _extendible");b=s.index("def _transport(",a)
    s=s[:a]+s[b:]
    a=s.index("    if not transforming and step is not None and len(group) < len(rows)+1:")
    b=s.index("    since =",a)
    s=s[:a]+s[b:]
    a="                           receiving=transforming,"
    s=s.replace(a,"                           wider=(tuple(sum(c.lane == k for c in (ego,*rows)) for k in range(lanes))\n                                  if not transforming and len(group)<len(rows)+1 else ()),\n"+a)
    f.write_text(s,encoding="utf8")
    f=out/"noa/staggered.py";s=f.read_text(encoding="utf8")
    anchor="def choose_target("
    s=s.replace(anchor,HELPER+anchor)
    s=s.replace("receiving=False):","receiving=False, wider=()):")
    mark="_open_road_allows(rank, group, slots, fit, opened_lanes, lanes))"
    assert s.count(mark)==1
    s=s.replace(mark,"_open_road_allows(rank, group, slots, fit, opened_lanes, lanes)\n                  and (not wider or _shared_move(group, slots, fit, rank, wider)))")
    f.write_text(s,encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);prepare(p.parse_args().out)
