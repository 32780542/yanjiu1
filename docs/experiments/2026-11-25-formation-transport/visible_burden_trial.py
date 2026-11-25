"""Reproduce visible-history experiments on top of the reviewed frozen controller."""
import argparse
from pathlib import Path
import subprocess
from private_burden_trial import BASE, VARIANT
from run_study import ROOT, REQUIRED, OPTIONAL

MASK = """
@lru_cache(maxsize=256)
def _burden_mask(source, target, history, squared):
    radius,total,forbidden = _lane_constraints(source,target)
    if not any(history):
        return forbidden
    n = len(source)
    burden = [[h+abs(a-b) for b in target] for a,h in zip(source,history)]
    if not squared:
        lo,hi = max(radius,max(history)), radius+max(history)
        while lo < hi:
            mid = (lo+hi)//2
            mask = [[f or z>mid for f,z in zip(row,vals)] for row,vals in zip(forbidden,burden)]
            matched = linear_sum_assignment(mask)[1]
            if any(mask[i][j] for i,j in enumerate(matched)):
                lo = mid+1
            else:
                hi = mid
        return [[f or z>lo for f,z in zip(row,vals)] for row,vals in zip(forbidden,burden)]
    penalty = n * (max(history)+radius)**2 + 1
    weight = [[penalty if f else z*z for f,z in zip(row,vals)] for row,vals in zip(forbidden,burden)]
    cols = _assignment(weight, penalty)
    # Every optimal permutation uses only tight exchange edges for an optimal dual.
    dist = [0]*n
    for _ in range(n):
        old = dist.copy()
        for i,j in enumerate(cols):
            for k,l in enumerate(cols):
                if not forbidden[i][l]:
                    dist[k] = min(dist[k],old[i]+weight[i][l]-weight[i][j])
        if dist==old:
            break
    mask = [row.copy() for row in forbidden]
    for i,j in enumerate(cols):
        for k,l in enumerate(cols):
            mask[i][l] |= dist[k] != dist[i]+weight[i][l]-weight[i][j]
    return mask

"""


def prepare(out,scope,objective):
    out.mkdir(parents=True,exist_ok=False)
    for name in (*REQUIRED,*OPTIONAL):
        dst=out/name
        dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(subprocess.check_output(["git","show",f"{BASE}:{VARIANT}/{name}"],cwd=ROOT))
    (out/"tmp").mkdir()
    def replace(name, a,b):
        dst=out/"noa"/name
        s=dst.read_text(encoding="utf8")
        assert s.count(a)==1,a
        dst.write_text(s.replace(a,b),encoding="utf8")
    replace("native_rules.py","    proposal_since: float = 0.","""    proposal_since: float = 0.
    observed_steps: tuple = ()
    transition: bool = False""")
    gate={"formation":"not transforming","transform":"transforming","both":"True"}[scope]
    replace("native_rules.py","    if len(group) == 1:\n        if ego.lane >= lanes:",
            f"""    observed = ()
    if {gate}:
        prev = {{t:(lane,h) for t,lane,h in memory.observed_steps}} if memory.transition == transforming else {{}}
        observed = tuple((c.track,c.lane,h+abs(c.lane-last)) for c in group
                         for last,h in [prev.get(c.track,(c.lane,0))])
    if len(group) == 1:
        if ego.lane >= lanes:""")
    replace("native_rules.py","        return command, memory\n\n    rank = group.index(ego)",
            "        return command, replace(memory, observed_steps=observed, transition=transforming)\n\n    rank = group.index(ego)")
    replace("native_rules.py","                           forward_anchor=forward_anchor, opened_lanes=",
            "                           history=tuple(h for _,_,h in observed),\n                           forward_anchor=forward_anchor, opened_lanes=")
    replace("native_rules.py","proposed_step=step, proposal_since=since))",
            "proposed_step=step, proposal_since=since, observed_steps=observed, transition=transforming))")
    replace("staggered.py","forward_anchor=None, opened_lanes=None):","forward_anchor=None, opened_lanes=None, history=()):")
    replace("staggered.py","position_error=POSITION_ERROR_M)","position_error=POSITION_ERROR_M, history=history)")
    replace("transport.py","def _integer_positions(values):",MASK+"\ndef _integer_positions(values):")
    replace("transport.py","ego_index=None, action=None, position_error=None):","ego_index=None, action=None, position_error=None, history=()):")
    replace("transport.py","    # In a bijection,",f"""    if any(history):
        forbidden = _burden_mask(source,target,tuple(history[i] for i in car_order),{objective=="square"})
    # In a bijection,""")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("out",type=Path)
    p.add_argument("--scope",required=True,choices=("formation","transform","both"))
    p.add_argument("--objective",required=True,choices=("max","square"))
    a=p.parse_args();prepare(a.out,a.scope,a.objective)
