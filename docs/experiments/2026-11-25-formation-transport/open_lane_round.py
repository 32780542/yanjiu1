"""Verify the largest simultaneous subset of a fixed one-hop optimal lane assignment."""
from collections import Counter
from dataclasses import dataclass
from itertools import product
import random
from time import perf_counter

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True)
class Car:
    source: int
    dest: int
    x: float
    slot_x: float
    available: bool = True

    @property
    def residual(self):
        return (self.x - self.slot_x) ** 2


def signed_flow(before, goal):
    """Net flow to the right on each cut. Check realizability in one step."""
    if len(before)!=len(goal) or not before or sum(before)!=sum(goal):
        raise ValueError("Expected equal-size populations on the same nonempty path")
    if any(not isinstance(n,int) or n<0 for n in (*before,*goal)):
        raise ValueError("Lane populations must be nonnegative integers")
    flow=[]; imbalance=0
    for n,q in zip(before[:-1],goal[:-1]):
        imbalance+=n-q
        flow.append(imbalance)
    at_path_edges=[0,*flow,0]
    if any(max(0,-at_path_edges[i])+max(0,at_path_edges[i+1])>n for i,n in enumerate(before)):
        raise ValueError("A vehicle would need more than one hop")
    return tuple(flow)


def largest_counts(before,goal,limit):
    """Signed counts in the componentwise greatest feasible subset."""
    flow=signed_flow(before,goal)
    if len(limit)!=len(flow) or any(not isinstance(u,int) or not 0<=u<=abs(f)
                                   for u,f in zip(limit,flow)):
        raise ValueError("Each availability count must lie between zero and the planned edge count")
    take=list(limit)
    # At a through node there is one incoming and one outgoing edge. All
    # outgoing moves use cars already present at the beginning of the round.
    for k in reversed(range(len(flow)-1)):
        if flow[k]>0 and flow[k+1]>0:
            slack=max(0,goal[k+1]-before[k+1])
            take[k]=min(take[k],slack+take[k+1])
    for k in range(1,len(flow)):
        if flow[k]<0 and flow[k-1]<0:
            slack=max(0,goal[k]-before[k])
            take[k]=min(take[k],slack+take[k-1])
    return tuple(-n if f<0 else n for f,n in zip(flow,take))


def select_round(cars,lanes):
    """Choose only original role holders. Residual ties prefer the front car."""
    before=[0]*lanes; goal=[0]*lanes
    planned=[0]*(lanes-1)
    pools=[[] for _ in planned]
    for car in cars:
        if not (0<=car.source<lanes and 0<=car.dest<lanes) or abs(car.source-car.dest)>1:
            raise ValueError("Expected specified one-hop physical roles")
        before[car.source]+=1; goal[car.dest]+=1
        if car.source!=car.dest:
            edge=min(car.source,car.dest)
            planned[edge]+=1
            if car.available:
                pools[edge].append(car)
    flow=signed_flow(before,goal)
    if planned!=list(map(abs,flow)):
        raise ValueError("Opposite moves on the same cut are not total-optimal")
    counts=largest_counts(before,goal,[len(p) for p in pools])
    selected=[]
    for count,pool in zip(counts,pools):
        n=abs(count)
        pool.sort(key=lambda car:(car.residual,-car.x))
        if 0<n<len(pool) and (pool[n-1].residual,pool[n-1].x)==(pool[n].residual,pool[n].x):
            raise ValueError("The boundary vehicles have indistinguishable physical tie-breaks")
        selected.extend(pool[:n])
    return counts,tuple(selected)


def populations(n,k):
    if k==1:
        yield (n,)
    else:
        for i in range(n+1):
            for tail in populations(n-i,k-1):
                yield (i,*tail)


def physical_key(subset,lanes):
    # Independent ordinal convention for comparing tied summed residuals.
    return tuple(tuple(sorted(-c.x for c in subset if min(c.source,c.dest)==k))
                 for k in range(lanes-1))


def check_case(cars,before,goal,stats):
    edges=len(before)-1
    chosen,materialized=select_round(cars,len(before))
    # Input ordering and temporary tracking numbers are irrelevant to selection.
    assert select_round(tuple(reversed(cars)),len(before))==(chosen,materialized)
    movers=[c for c in cars if c.source!=c.dest]
    max_edge=[0]*edges
    best=None
    for bits in product((0,1),repeat=len(movers)):
        accepted=[c for b,c in zip(bits,movers) if b]
        stats["subsets"]+=1
        if any(not c.available for c in accepted):
            continue
        end=list(before);cross=[0]*edges
        for c in accepted:
            end[c.source]-=1;end[c.dest]+=1
            cross[min(c.source,c.dest)]+=1
        if any(v>max(n,q) for v,n,q in zip(end,before,goal)):
            continue
        max_edge=[max(a,b) for a,b in zip(max_edge,cross)]
        cost=(-len(accepted),sum(c.residual for c in accepted),physical_key(accepted,len(before)))
        if best is None or cost<best[0]:
            best=(cost,set(accepted))
    assert tuple(max_edge)==tuple(map(abs,chosen)) and set(materialized)==best[1]
    stats["cases"]+=1
    if any(not c.available and c.dest!=c.source for c in cars):
        stats["some_move_unavailable"]+=1
    if len(materialized)<sum(c.available and c.dest!=c.source for c in cars):
        stats["further_throttled"]+=1
    if materialized:
        stats["nonempty"]+=1
    if not movers:
        return
    # A separate continuous LP has one decision per physical car. It receives
    # neither the net cut flows nor the formula for the optimal edge counts.
    incidence=np.zeros((len(before),len(movers)))
    edge_matrix=np.zeros((edges,len(movers)))
    for i,c in enumerate(movers):
        incidence[c.source,i]=-1
        incidence[c.dest,i]=1
        edge_matrix[min(c.source,c.dest),i]=1
    bounds=[(0,float(c.available)) for c in movers]
    cap=np.maximum(before,goal)-before
    ones=np.ones(len(movers))
    lp=linprog(-ones,A_ub=incidence,b_ub=cap,bounds=bounds,method="highs")
    assert lp.success and np.allclose(edge_matrix@lp.x,max_edge)
    stats["lps"]+=1
    for edge,row in enumerate(edge_matrix):
        if row.any():
            lp=linprog(-row,A_ub=incidence,b_ub=cap,bounds=bounds,method="highs")
            assert lp.success and abs(-lp.fun-max_edge[edge])<1e-7
            stats["lps"]+=1
    lp=linprog([c.residual for c in movers],A_ub=incidence,b_ub=cap,A_eq=[ones],
               b_eq=[len(materialized)],bounds=bounds,method="highs")
    assert lp.success and abs(lp.fun-sum(c.residual for c in materialized))<1e-7
    stats["lps"]+=1


def verify():
    stats=Counter()
    for lanes in range(2,6):
        for n in range(6):
            for before in (p for p in populations(n,lanes) if p[-1]==0):
                source=[j for j,v in enumerate(before) for _ in range(v)]
                for goal in populations(n,lanes):
                    dest=[j for j,v in enumerate(goal) for _ in range(v)]
                    if any(abs(a-b)>1 for a,b in zip(source,dest)):
                        continue
                    cars=[]
                    for i,(a,b) in enumerate(zip(source,dest)):
                        x=600.-7*i
                        cars.append(Car(a,b,x,x+(i%3)-1,b!=lanes-1))
                    check_case(cars,before,goal,stats)
    print("All one-new-outer-lane exhaustive cases:",dict(stats),flush=True)
    rng=random.Random(981316)
    more=Counter()
    for _ in range(512):
        lanes=rng.randint(2,11)
        orientation=rng.choices((-1,1),k=lanes-1)
        before=[0]*lanes;goal=[0]*lanes;cars=[]
        for i in range(rng.randint(1,10)):
            a=rng.randrange(lanes)
            dest=[a]
            if a and orientation[a-1]<0:
                dest.append(a-1)
            if a<lanes-1 and orientation[a]>0:
                dest.append(a+1)
            b=rng.choice(dest)
            before[a]+=1;goal[b]+=1
            x=100.-5*i
            cars.append(Car(a,b,x,x+rng.choice((-3,-1,0,1,3)),rng.choice((True,True,False))))
        check_case(cars,before,goal,more)
    print("Arbitrary feasible directions and individual availability:",dict(more))
    before=(0,3,1,2,0);goal=(1,0,2,1,2)
    assert signed_flow(before,goal)==(-1,2,1,2)
    assert largest_counts(before,goal,[1,2,1,0])==(-1,1,0,0)
    assert largest_counts((1,1,0),(0,1,1),[1,1])==(1,1)
    assert largest_counts((1,1,0),(0,1,1),[1,0])==(0,0)
    # Identical longitudinal position and residual at the selection boundary
    # cannot elect one car without more physical information.
    tied=[Car(0,1,0,1),Car(0,1,0,1),Car(1,2,10,10,False)]
    try:
        select_round(tied,3)
    except ValueError as err:
        assert "indistinguishable" in str(err)
    else:
        raise AssertionError("A symmetric physical tie should remain unresolved")


if __name__=="__main__":
    start=perf_counter()
    verify()
    print(f"Elapsed {perf_counter()-start:.2f} s")
