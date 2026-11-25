"""A receiving vehicle follows the observed predecessor of its assigned final column."""
import argparse
from pathlib import Path
from combined_trial import build as combined
from one_hop_trial import create as transition


def build(out,mode,base):
    (combined if base=="combined" else transition)(out)
    p=out/"noa/native_rules.py";s=p.read_text(encoding="utf8");mark="                           head_clipped=head_clipped, tail_clipped=tail_clipped,"
    assert s.count(mark)==1
    p.write_text(s.replace(mark,"                           receiving=transforming,\n"+mark),encoding="utf8")
    p=out/"noa/staggered.py";s=p.read_text(encoding="utf8")
    s=s.replace("opened_lanes=None, history=()):","opened_lanes=None, history=(), receiving=False):")
    marker="    front_offset = min(d for _, d in offsets)"
    section="""    if receiving and lane == group[rank].lane:
        # The immediately preceding target in this column can be held by a car
        # still in an adjacent lane. Link only the receiving car's own target.
        front = None
        for j, slot in enumerate(fit.assignment):
            target_lane, slot_x = slots[slot]
            if target_lane == lane and slot_x > x and (front is None or slot_x < front[0]):
                front = (slot_x,group[j])
        if front is not None:
            ahead = front[1]
            if abs(ahead.lane-lane) == 1:
                x = min(x, ahead.x - spacing)
"""
    if mode=="weighted":
        section=section.replace("x = min(x, ahead.x - spacing)","x = .5 * (x + min(x, ahead.x - spacing))")
    elif mode=="clearance":
        section=section.replace("x = min(x, ahead.x - spacing)","from noa.native_rules import CLEARANCE\n                x = min(x, ahead.x - CLEARANCE)")
    elif mode=="order":
        section=section.replace("if abs(ahead.lane-lane) == 1:", "if abs(ahead.lane-lane) == 1 and ahead.x >= group[rank].x:")
    assert s.count(marker)==1
    p.write_text(s.replace(marker,section+marker),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path);p.add_argument("--mode",choices=("full","weighted","clearance","order"),required=True)
    p.add_argument("--base",choices=("combined","transition"),default="combined")
    a=p.parse_args();build(a.out,a.mode,a.base)
