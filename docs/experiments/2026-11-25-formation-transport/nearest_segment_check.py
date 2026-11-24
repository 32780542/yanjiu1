"""Compare local anchor choices with explicit segment choices and path matching."""
import argparse
import itertools
from pathlib import Path
import random
from endpoint_reciprocity_check import load


def oracle(cars):
    segments=[]
    for c in sorted(cars,key=lambda c:c.x):
        if not segments or c.x-segments[-1][-1].x>50:
            segments.append([])
        segments[-1].append(c)
    choices=[]
    for i,s in enumerate(segments):
        options=[]
        if i:options.append((s[0].x-segments[i-1][-1].x,1,i-1))
        if i+1<len(segments):options.append((segments[i+1][0].x-s[-1].x,0,i+1))
        choices.append(min(options)[2] if options else None)
    assignments={c:None for c in cars}
    edges=[]
    for i in range(len(segments)-1):
        if choices[i]==i+1 and choices[i+1]==i:
            edges.append(i)
            for c in segments[i]:assignments[c]=segments[i+1][0].x
    assert len(segments)<2 or edges
    assert all(b-a>=2 for a,b in zip(edges,edges[1:]))
    return assignments


def run(source):
    native=load(source)
    choose=native._nearest_segment_anchor
    rng=random.Random(5508721);paths=requests=0
    for n in range(1,8):
        for gaps in itertools.product((55.,80.,110.),repeat=n-1):
            xs=[0.]
            for gap in gaps:xs.append(xs[-1]+gap)
            cs=[native.Vehicle(j,x,1.65,28.8,j%3) for j,x in enumerate(xs)]
            expected=oracle(cs)
            for ego in cs:
                rows=[c for c in cs if c is not ego];rng.shuffle(rows)
                group=list(reversed(native._local_group(ego,rows)))
                assert choose(group,rows)==expected[ego];requests+=1
            paths+=1
    for _ in range(850):
        x=rng.uniform(-200,200);cs=[]
        for j in range(rng.randint(2,25)):
            x+=rng.choice((0.,11.,50.,51.,60.,80.,100.,125.,175.))
            cs.append(native.Vehicle(j,x,1.65,28.8,j%3))
        for ego in cs:
            rows=[c for c in cs if c is not ego and -100<=c.x-ego.x<=200];rng.shuffle(rows)
            group=list(reversed(native._local_group(ego,rows)))
            assert choose(group,rows)==oracle([ego,*rows])[ego];requests+=1
    print(paths,"complete abstract paths; 850 cut physical scenes;",requests,"ego comparisons")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("source",type=Path)
    run(p.parse_args().source)
