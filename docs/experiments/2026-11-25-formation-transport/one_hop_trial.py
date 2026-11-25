"""A local one-hop reconfiguration records only the last observed crossing of each member."""
import argparse
from pathlib import Path
from crossing_memory_trial import build


def create(out):
    build(out,"max")
    p=out/"noa/native_rules.py";s=p.read_text(encoding="utf8")
    a=s.index("    threshold = memory.preview_x");b=s.index("    if len(group) == 1:\n",a)
    s=s[:a]+"""    previous = {track:(lane,x) for track,lane,x in memory.observed_steps}
    observed = []
    for car in group:
        lane, last_x = previous.get(car.track, (car.lane,float("-inf")))
        observed.append((car.track,car.lane,car.x if lane!=car.lane else last_x))
    observed = tuple(observed)
"""+s[b:]
    s=s.replace("history=tuple(len(events) for _,_,events in observed) if transforming else ()",
                "history=tuple(x >= memory.preview_x for _,_,x in observed) if transforming and memory.preview_x is not None else ()")
    p.write_text(s,encoding="utf8")
    p=out/"noa/transport.py";s=p.read_text(encoding="utf8")
    a=s.index("@lru_cache(maxsize=256)\ndef _burden_mask");b=s.index("def _integer_positions",a)
    s=s[:a]+"""@lru_cache(maxsize=256)
def _one_hop_mask(source, target, moved):
    radius, _, ordinary = _lane_constraints(source, target)
    if radius != 1:
        return ordinary
    blocked = [[f or (used and a!=b) for f,b in zip(row,target)]
               for a,used,row in zip(source,moved,ordinary)]
    cols = linear_sum_assignment(blocked)[1]
    return ordinary if any(blocked[i][j] for i,j in enumerate(cols)) else blocked


"""+s[b:]
    s=s.replace("_burden_mask(source,target,tuple(history[i] for i in car_order),False)",
                "_one_hop_mask(source,target,tuple(history[i] for i in car_order))")
    assert "_burden_mask" not in s;p.write_text(s,encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("out",type=Path)
    create(p.parse_args().out)
