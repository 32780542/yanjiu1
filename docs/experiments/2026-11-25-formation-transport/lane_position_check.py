"""Independently check lane-position costs using assignment and perfect matching."""
from itertools import permutations
from math import lcm

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching


def assignment(old, new, expected_radius, expected_total, rng, brute=False):
    """Unit vehicle copies and unit target copies in independently shuffled order."""
    old = rng.permutation(old)
    new = rng.permutation(new)
    cost = np.abs(old[:, None] - new[None, :])
    n = len(old)
    radius = next(
        r for r in range(int(cost.max()) + 1)
        if (maximum_bipartite_matching(csr_matrix(cost <= r), perm_type="column") >= 0).all()
    )
    a, b = linear_sum_assignment(cost)
    unrestricted = int(cost[a, b].sum())
    permitted = np.where(cost <= radius, cost, np.inf)
    a, b = linear_sum_assignment(permitted)
    joint = int(cost[a, b].sum())
    assert (radius, unrestricted, joint) == (expected_radius, expected_total, expected_total)
    if brute:
        possible = []
        for target in permutations(new.tolist()):
            moves = [abs(int(x)-y) for x,y in zip(old,target)]
            possible.append((max(moves),sum(moves)))
        assert min(possible) == (expected_radius, expected_total)
        assert min(v for _,v in possible) == expected_total
    assert len(a) == n


def main():
    rng = np.random.default_rng(251126)
    deletions = brute = offsets = 0
    for k in range(2,10):
        unit = []
        for j in range(k):
            triangle = lambda a: a*(a+1)//2
            unit_cost = triangle(j) + triangle(k-1-j)
            unit.append(unit_cost)
            for t in (1,2):
                old = np.repeat(np.arange(k),(k-1)*t)
                new = np.repeat([i for i in range(k) if i!=j],k*t)
                for src,dst in ((old,new),(new,old)):
                    exhaustive = len(src) <= 6
                    assignment(src,dst,1,t*unit_cost,rng,exhaustive)
                    brute += int(exhaustive)
                    deletions += 1
        print(f"K={k}, total for each removed coordinate (t=1): {unit}")

    # Translated contiguous roadway footprints. Use the generic prefix formula
    # for the total and the extreme sorted displacements for the bottleneck.
    for k in range(2,10):
        for ell in range(1,10):
            n = lcm(k,ell)
            old = np.repeat(np.arange(k),n//k)
            for d in range(-3,4):
                new = np.repeat(d+np.arange(ell),n//ell)
                cuts = range(min(0,d),max(k-1,d+ell-1))
                total = sum(abs(int((old<=i).sum())-int((new<=i).sum())) for i in cuts)
                radius = max(abs(d),abs(d+ell-k))
                assignment(old,new,radius,total,rng)
                if ell == k-1:
                    assert 2*total == n*(abs(d-1)+abs(d))
                offsets += 1

    # Five cars on a four-to-three road; both occupancies are as even as possible.
    src, dst = [0,0,1,2,3], [1,2,2,3,3]
    assignment(src,dst,2,5,rng,True)
    assignment(src,[1,1,2,2,3],1,3,rng,True)
    print(f"{deletions} deletion/insertion cases; {brute} also exhausted permutation by permutation")
    print(f"{offsets} translated-footprint cases; 2 extra rounded-population counterexamples")


if __name__ == "__main__":
    main()
