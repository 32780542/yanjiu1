"""Align observed lateral history to the physical location where the road change becomes visible."""
import argparse
from pathlib import Path
from visible_burden_trial import prepare


def build(out, objective):
    prepare(out,"transform",objective)
    path=out/"noa/native_rules.py"
    code=path.read_text(encoding="utf8")
    code=code.replace("    transition: bool = False","    transition: bool = False\n    preview_x: float | None = None")
    start=code.index("    observed = ()\n")
    end=code.index("    if len(group) == 1:\n",start)
    code=code[:start]+"""    threshold = memory.preview_x if memory.preview_x is not None else ego.x
    previous = {track: (lane, events) for track, lane, events in memory.observed_steps}
    observed = []
    for car in group:
        old, past = previous.get(car.track, (car.lane, ()))
        events = tuple(x for x in past if x >= threshold)
        if car.lane != old and car.x >= threshold:
            events += (car.x,) * abs(car.lane-old)
        observed.append((car.track,car.lane,events))
    observed = tuple(observed)
"""+code[end:]
    code=code.replace("history=tuple(h for _,_,h in observed)", "history=tuple(len(events) for _,_,events in observed) if transforming else ()")
    code=code.replace("           upcoming_lanes=None):","           upcoming_lanes=None, visible_boundary_x=None):")
    marker="    usable = min(lanes, lane_count)"
    code=code.replace(marker,"""    preview_x = memory.preview_x if visible_boundary_x is None else visible_boundary_x - ROAD_PREVIEW
    memory = replace(memory, preview_x=preview_x)
"""+marker)
    code=code.replace("return replace(command, speed=min(command.speed, limit)), memory",
                      "return replace(command, speed=min(command.speed, limit)), replace(memory, preview_x=preview_x)")
    assert "visible_boundary_x=None" in code
    path.write_text(code,encoding="utf8")
    path=out/"experiments/native_sumo.py";code=path.read_text(encoding="utf8")
    mark="                                upcoming_lanes=retained if visible else None,"
    assert code.count(mark)==1
    path.write_text(code.replace(mark,mark+"\n                                visible_boundary_x=approach if visible else None,"),encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("out",type=Path);p.add_argument("--objective",required=True,choices=("max","square"))
    a=p.parse_args();build(a.out,a.objective)
