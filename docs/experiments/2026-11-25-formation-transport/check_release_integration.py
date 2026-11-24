"""Check the production road-opening decisions against an independent subset-flow solver."""
from pathlib import Path
import random
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[3]/"variants/phase5g_pure_formation"))
from noa.staggered import _open_road_allows
from noa.transport import solve_transport
from open_lane_round import Car, select_round


def main():
    rng=random.Random(25110427)
    eligible = proposed = withheld_inside = 0
    for trial in range(2000):
        lanes=rng.randrange(2,7)
        opened=rng.randrange(1,lanes)
        size=rng.randrange(2,16)
        source=[rng.randrange(lanes) for _ in range(size)]
        targets=[rng.randrange(lanes) for _ in range(size)]
        cars=[(lane,3*i+rng.random()) for i,lane in enumerate(source)]
        slots=[(lane,rng.random()*40) for lane in targets]
        fit=solve_transport(cars,slots)
        if fit.max_crossings!=1:
            continue
        relation=[Car(a,slots[j][0],x,slots[j][1],a<opened and slots[j][0]<opened)
                  for (a,x),j in zip(cars,fit.assignment)]
        edges,selected=select_round(relation,lanes)
        group=[SimpleNamespace(lane=lane,x=x) for lane,x in cars]
        for i,c in enumerate(relation):
            if c.source>=opened:
                continue
            ready=_open_road_allows(i,group,slots,fit,opened,lanes)
            assert ready == (c.source==c.dest or c in selected), (group,slots,fit,opened,edges,i)
            proposed+=c.source!=c.dest
            withheld_inside+=c.source!=c.dest and c.dest<opened and not ready
        eligible+=1
    print(f"{eligible} one-hop problems, {proposed} physical proposals, "
          f"{withheld_inside} moves to already-open lanes withheld by the capacity constraints")


if __name__=="__main__":
    main()
