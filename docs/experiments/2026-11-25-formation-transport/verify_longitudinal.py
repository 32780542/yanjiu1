"""Independent local-spacing analysis on an unchanged staggered lane graph.

Each retained pair connects mutually selected physical neighbors within 50 m.
Use at most one front and one rear vehicle per relevant lane. The sign is the
observed longitudinal order; skip aligned/ambiguous pairs. A same-lane pair
aims for alpha=1 spacing D, an adjacent-lane pair for alpha=1/2. In this
maintenance experiment a pair must already be within D/4 of that branch.

For an edge from i to its physical front j, define
    r_ij = x_j - x_i - alpha*(5.5 + T*(v_i+v_j)/2).
Add +k*w*r_ij to i's acceleration and -k*w*r_ij to j's, on top of
b*(V-v). Each car reconstructs the pair from its own observations. Assume
fixed lanes, reciprocal edges, connectedness, additive-consistent edge offsets,
constant V and inactive speed/acceleration/safety limits. Write q for position
relative to a compatible shape traveling at V, u for speed relative to V:
    q'=u; u'=-Kq-Cu, K=kL.
An edge adds (k*T*w*alpha/2)*[[1,1],[-1,-1]] to C on [rear,front].
Hence sym(C) is diagonal. With the weights below, weighted degree <=1,
alpha-weighted degree <=.75, lambda_max(K)<=8, sym(C) in [2.725,5.275],
and ||skew(C)||_2<=1.275. E=(q'Kq+u'u)/2 has derivative -u'sym(C)u.
Only common translation is neutral. An incompatible loop instead minimizes
the weighted sum of squared edge errors and can retain nonzero residuals.

For semi-implicit Euler, first update u, then q using the new u. A root z
satisfies [(z-1)^2 I + h(z-1)C + h^2 z K]d=0. On the unit circle z!=1,
left-multiply by d*, divide by z*d*d, write a+ib=d*Cd/(d*d), l=d*Kd/(d*d).
The imaginary part gives b=-a*cot(theta/2), the real part gives
4*sin(theta/2)^2=2*h*a+h^2*l. So no such crossing can occur if
    (2*h*a_max+h^2*l_max)*(1+(b_max/a_min)^2) < 4.
This holds along the full step homotopy (0, .1]. Continuous-time stability
places the non-neutral roots inside the disk for small positive h. The
translation root stays simple since the graph is connected and 1'C1=n*b>0.

A single fixed physical front yields C=b+k*w*T*alpha/2, K=k*w. Its two
sampled poles have polynomial z²-(2-h*C-h²*K)z+(1-h*C). For an externally
perturbed front and fixed V, the continuous position transfer is
K*(1-alpha*T*s/2)/(s²+C*s+K); gain <=1 iff C²>=2*K+(K*alpha*T/2)².
This single-edge statement does not cover arbitrary switched traffic strings.
"""
import argparse
from collections import Counter
import gzip
import json
from math import isclose, log
from pathlib import Path
from random import Random
import xml.etree.ElementTree as ET

import numpy as np


V, T, K, B, DT, R = 28.8, .85, 4., 4., .1, 50.
D = 5.5 + T*V


def proposals(i, rows, visible):
    lane, x, v = rows[i]
    best = {}
    for j in visible:
        other_lane, y, speed = rows[j]
        if abs(other_lane-lane) > 1 or not 0 < abs(y-x) <= R:
            continue
        alpha = 1 if lane == other_lane else .5
        gap = 5.5 + T*(v+speed)/2
        residual = abs(abs(y-x)-alpha*gap)
        if residual >= gap/4:
            continue
        key = (other_lane, y > x)
        # The strictly closest eligible vehicle on that side; no ID tie-break.
        distance = abs(y-x)
        if key not in best or distance < best[key][0]:
            best[key] = (distance,j)
        elif distance == best[key][0]:
            best[key] = (distance,None)
    return {j for _,j in best.values() if j is not None}


def edges(rows):
    indices = tuple(range(len(rows)))
    out = [proposals(i,rows,indices) for i in indices]
    links = []
    for i in indices:
        full = {j for j in out[i] if i in out[j]}
        visible = [j for j in indices if -100 <= rows[j][1]-rows[i][1] <= 200]
        local = {j for j in proposals(i,rows,visible) if i in proposals(j,rows,visible)}
        assert local == full
        links.extend((i,j) for j in local if rows[j][1] > rows[i][1])
    return sorted(links)


def graph_matrices(rows, links):
    n = len(rows)
    stiff, damping = np.zeros((n,n)), np.eye(n)*B
    for i,j in links:
        same = rows[i][0] == rows[j][0]
        w, alpha = (.25,1) if same else (.125,.5)
        ij = np.ix_([i,j],[i,j])
        stiff[ij] += K*w*np.array([[1,-1],[-1,1]])
        damping[ij] += K*T*w*alpha/2*np.array([[1,1],[-1,-1]])
    return stiff, damping


def shape(lanes, layers):
    return [(lane,-D*(layer+(lane%2)/2),V) for layer in range(layers) for lane in range(lanes)]


def check_graph(lanes, layers, rng):
    rows = shape(lanes,layers)
    links = edges(rows)
    stiff, damping = graph_matrices(rows,links)
    n, eye = len(rows), np.eye(len(rows))
    eigen = np.linalg.eigvalsh(stiff)
    assert eigen[1] > 0 and eigen[-1] <= 8+1e-10
    assert np.linalg.eigvalsh((damping+damping.T)/2)[0] >= 2.725-1e-10
    assert np.linalg.norm((damping-damping.T)/2,2) <= 1.275+1e-10
    A = np.block([[eye-DT**2*stiff, DT*(eye-DT*damping)],[-DT*stiff, eye-DT*damping]])
    poles = np.sort(abs(np.linalg.eigvals(A)))
    assert isclose(poles[-1],1,abs_tol=1e-10) and poles[-2] < 1

    # Compare edge forces computed from physical distances with matrix dynamics.
    q = np.array([rng.uniform(-.8,.8) for _ in rows])
    u = np.array([rng.uniform(-.12,.12) for _ in rows])
    observed = [(k,x+q[i],v+u[i]) for i,(k,x,v) in enumerate(rows)]
    assert edges(observed) == links
    acceleration = -B*u.copy()
    for i,j in links:
        lane_i,x,v = observed[i]
        lane_j,y,s = observed[j]
        w,alpha = (.25,1) if lane_i == lane_j else (.125,.5)
        correction = K*w*(y-x-alpha*(5.5+T*(v+s)/2))
        acceleration[i] += correction
        acceleration[j] -= correction
    assert np.allclose(acceleration, -stiff@q-damping@u)
    u_new = u+DT*acceleration
    assert np.allclose(A@np.r_[q,u], np.r_[q+DT*u_new,u_new])
    return dict(lanes=lanes,cars=n,links=len(links),relative_spectral_radius=round(poles[-2],7),
                slow_mode_efold_s=round(-DT/log(poles[-2]),2))


def topology(rows, links):
    """Count components and detect nonzero cycle sum in integer half periods."""
    adjacency = [[] for _ in rows]
    for i,j in links:
        half = 2 if rows[i][0] == rows[j][0] else 1
        adjacency[i].append((j,half))
        adjacency[j].append((i,-half))
    levels, components, compatible = {}, 0, True
    for i in range(len(rows)):
        if i in levels:
            continue
        components += 1
        levels[i] = 0
        todo = [i]
        while todo:
            k = todo.pop()
            for neighbor, shift in adjacency[k]:
                proposed = levels[k]+shift
                if neighbor in levels:
                    compatible &= levels[neighbor] == proposed
                else:
                    levels[neighbor] = proposed
                    todo.append(neighbor)
    return components, compatible, sum(not peers for peers in adjacency)


def trace_check(trace):
    """Geometric prerequisite coverage in archived SUMO traffic, sampled at 1 Hz."""
    cut = float(ET.parse(trace.parent/"native.net.xml").find("./edge[@id='upstream']/lane").get("length"))
    counts = Counter(dict.fromkeys(("long_group_snapshots","centered","connected","compatible",
                                    "connected_compatible","car_snapshots","isolated_cars"),0))
    with gzip.open(trace,"rt") as stream:
        for line in stream:
            f = json.loads(line)
            if abs(f["time_s"]-round(f["time_s"])) > 1e-6:
                continue
            groups = []
            for s in sorted(f["states"].values(),key=lambda v:v[0]):
                if not groups or s[0]-groups[-1][-1][0] > 50:
                    groups.append([])
                groups[-1].append(s)
            for group in groups:
                low,high = group[0][0],group[-1][0]
                if high-low <= 300 or not (high < cut-200 or low >= cut):
                    continue
                counts["long_group_snapshots"] += 1
                if any(abs(s[1]-(round(s[1]/3.3-.5)+.5)*3.3) > .3 for s in group):
                    continue
                counts["centered"] += 1
                rows = [(round(y/3.3-.5),x,v) for x,y,v,*_ in group]
                components,compatible,isolated = topology(rows,edges(rows))
                counts["connected"] += components == 1
                counts["compatible"] += compatible
                counts["connected_compatible"] += components == 1 and compatible
                counts["car_snapshots"] += len(rows)
                counts["isolated_cars"] += isolated
    return dict(trace=str(trace),**counts)


def main():
    bound = (2*DT*5.275+DT**2*8)*(1+(1.275/2.725)**2)
    assert bound < 4
    followers = []
    for kind, w, alpha in (("same_lane",.25,1),("adjacent_lane",.125,.5)):
        k, c = K*w, B + K*w*alpha*T/2
        poles = np.roots([1,-(2-DT*c-DT**2*k),1-DT*c])
        assert max(abs(poles)) < 1 and c*c >= 2*k+(k*alpha*T/2)**2
        followers.append(dict(edge=kind,poles=list(np.round(poles,7))))
    rng = Random(1125)
    graphs = [check_graph(lanes,layers,rng) for lanes in (2,3,4) for layers in (3,6,12)]
    # A new vehicle just outside sight can change a window mean but cannot
    # alter the selected local edges. A half-period adjacent tie has no
    # sign/phase information and correctly creates no maintenance edge.
    assert edges([(0,0.,V),(1,0.,V)]) == []
    leader_gap = 3.
    front_only = [(0,0.,V),(1,-D/2,V),(2,leader_gap,V)]
    assert not any(i in (0,2) for i,j in edges(front_only))
    assert {j for i,j in edges(front_only) if i==1} == {0,2}
    block = shape(2,3)
    offset = min(s[1] for s in block)-40
    split = block+[(l,x+offset,v) for l,x,v in block]
    assert topology(split,edges(split)) == (2,True,0)
    # Same local view, extra complete layer in front changes the global rank.
    platoon = shape(3,20)
    ego = 30
    enlarged = platoon+[(l,x+D,v) for l,x,v in shape(3,1)]
    before = edges(platoon)
    after = edges(enlarged)
    assert [e for e in before if ego in e] == [e for e in after if ego in e]
    return dict(semi_implicit_bound=round(bound,6),threshold=4,followers=followers,graphs=graphs,
                split_group_gap_m=40,split_graph_components=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--trace",type=Path,nargs="+")
    args = parser.parse_args()
    print(json.dumps([trace_check(path) for path in args.trace] if args.trace else main(),indent=2))
