"""Test a least-squares same-column spacing term during upstream formation."""
import argparse
from pathlib import Path
from minimum_reuse_trial import create as base


def build(out):
    base(out)
    path = out / "noa/staggered.py"
    source = path.read_text(encoding="utf8")
    marker = "    if receiving and lane == group[rank].lane:"
    addition = '''    if not receiving and lane == group[rank].lane:
        # Each retained neighbour contributes one physical spacing equation.
        column = [(slots[j][1], car) for car,j in zip(group,fit.assignment)
                  if slots[j][0] == car.lane == lane]
        front = min((p for p in column if p[0] > x), key=lambda p:p[0], default=None)
        rear = max((p for p in column if p[0] < x), key=lambda p:p[0], default=None)
        estimates = [x]
        if front is not None and abs(front[0] - x - spacing) < 1e-8:
            estimates.append(front[1].x - spacing)
        if rear is not None and abs(x - rear[0] - spacing) < 1e-8:
            estimates.append(rear[1].x + spacing)
        x = sum(estimates) / len(estimates)
'''
    assert source.count(marker)==1
    path.write_text(source.replace(marker, addition+marker), encoding="utf8")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out",type=Path)
    build(parser.parse_args().out)
