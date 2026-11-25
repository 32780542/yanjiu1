"""Use the observed direction of a physical lane change to account for occupied target slots."""
import argparse
from pathlib import Path
import subprocess
from private_burden_trial import BASE, VARIANT
from run_study import ROOT, REQUIRED, OPTIONAL


def prepare(out, scope):
    out.mkdir(parents=True,exist_ok=False)
    for name in (*REQUIRED,*OPTIONAL):
        dst=out/name;dst.parent.mkdir(parents=True,exist_ok=True)
        dst.write_bytes(subprocess.check_output(["git","show",f"{BASE}:{VARIANT}/{name}"],cwd=ROOT))
    (out/"tmp").mkdir()
    dst=out/"noa/native_rules.py"
    code=dst.read_text(encoding="utf8").replace("from math import sqrt","from math import ceil, floor, sqrt")
    anchor="def _transport(ego, rows, memory, lanes, opened, transforming):"
    helper="""def _observed_destination(car, opened):
    lateral = car.y / LANE_WIDTH - .5
    # The adjacent centre in the direction of the observed motion.
    if car.vy > 0:
        lane = ceil(lateral - 1e-8)
    elif car.vy < 0:
        lane = floor(lateral + 1e-8)
    else:
        return car
    return replace(car, lane=lane) if 0 <= lane < opened and lane != car.lane else car


"""
    code=code.replace(anchor,helper+anchor)
    gate={"both":"True","formation":"not transforming","transform":"transforming"}[scope]
    old="    target = choose_target(rank, group, lanes, spacing,"
    assert code.count(old)==1
    dst.write_text(code.replace(old,"    planned_group = [_observed_destination(c, opened) for c in group] if "+gate+" else group\n    target = choose_target(rank, planned_group, lanes, spacing,"),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);p.add_argument("--scope",required=True,choices=("both","formation","transform"))
    a=p.parse_args();prepare(a.out,a.scope)
