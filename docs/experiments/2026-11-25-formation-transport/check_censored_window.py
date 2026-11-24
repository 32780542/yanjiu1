"""Exact half-layer audit of finite observation windows on legal staggered columns.

A longitudinal interval includes every car at an identical coordinate. Lane l
has points a-D*(r+I[l%2!=p]/2) at consecutive nonnegative ranks r. Complete
layers precede an optional final subset. Three lanes require that an extra
middle-lane vehicle has both extra outer-lane partners, following whole_shape.
The count mask below concerns geometrical equilibrium, before safety/road caps.
"""
from collections import Counter
from functools import lru_cache
import json
import math
import subprocess
import tempfile
from pathlib import Path
from random import Random
import sys
from types import SimpleNamespace
from unittest.mock import patch

# This audit uses the original tail convention of the first research
# revision. The newer two-lane controller intentionally fills every half-slot.
root = Path(__file__).resolve().parents[3]
snapshot = tempfile.TemporaryDirectory(prefix="formation-crop-audit-")
package = Path(snapshot.name) / "noa"
package.mkdir()
for name in ("__init__.py", "transport.py", "staggered.py"):
    tracked = "variants/phase5g_pure_formation/noa/" + name
    data = subprocess.check_output(["git", "show", "e186b8a:" + tracked], cwd=root)
    (package / name).write_bytes(data)
sys.path.insert(0, snapshot.name)
from noa import staggered
from noa.staggered import choose_target
from noa.transport import solve_transport


def legal_tail(lanes, tail):
    return lanes != 3 or 1 not in tail or {0,2}.issubset(tail)


def lane_mask(lanes, parity):
    return sum(1 << k for k in range(parity,lanes,2))


@lru_cache(maxsize=16384)
def compatible_extension(lanes, parity_at_lo, masks, possible=None):
    """Whether a complete finite staggered cohort can have exactly these visible bands.

    'masks' covers *all* lattice coordinates inside the closed viewing range,
    including observed empty bands. Extra complete layers outside this range
    can be removed without changing the observation. Two candidate head or
    tail bands beyond it suffice to try both parities. No count of hidden
    cars or global head index is assumed.
    """
    occupied = [j for j,m in enumerate(masks) if m]
    if not occupied:
        return True
    band = [lane_mask(lanes,(j+parity_at_lo)%2) for j in range(len(masks))]
    if possible is None:
        possible = masks
    if any(m & ~expected for m,expected in zip(masks,band)):
        return False
    for head in range(-2,occupied[0]+1):
        if lanes != 2 and (head+parity_at_lo)%2:
            continue
        for last in range(max(head,occupied[-1]-1), len(masks)+2):
            if (last-head)%2:
                continue
            if any(possible[j] != band[j] for j in range(max(0,head),min(last,len(masks)))):
                continue
            # Occupied bands are already inside [head,last+1]. Either of the
            # last two half-layers may be unobserved; only visible lanes bind.
            if lanes == 3:
                middle_required = 0 <= last+1 < len(masks) and masks[last+1] & 2
                outer_possible = possible[last] if 0 <= last < len(masks) else 5
                if middle_required and outer_possible != 5:
                    continue
            return True
    return False


def noisy_extension(scene, ego, lanes, spacing, front, rear, eps=.05):
    """Independent existence test for a legal measured slice with errors <=eps.

    Use the ego's lattice slice as band zero and a single scalar origin A.
    Each detected row constrains A. For a fixed A, a cell is compulsory in
    the sensor if its entire position-error interval lies in the closed FOV.
    Other cells may escape the FOV, even while a parallel companion remains
    visible. Try all origin intervals on which these finite masks are constant.
    """
    h = spacing/2
    cells = {}
    low,high = -math.inf,math.inf
    for car in scene:
        parity = (car.lane-ego.lane)%2
        b = 2*round(((ego.x-car.x)/h-parity)/2)+parity
        if cells.get(b,0) & (1<<car.lane):
            return False
        cells[b] = cells.get(b,0) | (1<<car.lane)
        origin = car.x+b*h
        low,high = max(low,origin-eps),min(high,origin+eps)
    if low>high:
        return False
    back,ahead = ego.x-rear,ego.x+front
    first = math.floor((low-ahead-eps)/h)-1
    last = math.ceil((high-back+eps)/h)+1
    bands = range(first,last+1)
    masks = tuple(cells.get(b,0) for b in bands)
    breaks = sorted({low,high} | {t for b in bands for t in (back+eps+b*h,ahead-eps+b*h)
                                 if low < t < high})
    for origin in breaks+[(a+b)/2 for a,b in zip(breaks,breaks[1:])]:
        possible = tuple(cells.get(b,0) if back+eps<=origin-b*h<=ahead-eps
                         else lane_mask(lanes,(ego.lane+b)%2) for b in bands)
        if compatible_extension(lanes,(ego.lane+first)%2,masks,possible):
            return True
    return False


@lru_cache(maxsize=16384)
def fitted(lanes, top_parity, masks, head_clipped, tail_clipped, back_mm, ahead_mm):
    """Compare the old balanced crop and current omitted-band crop with observed bands."""
    counts = [sum((m>>lane)&1 for m in masks) for lane in range(lanes)]
    lead = top_parity if head_clipped or lanes==2 else 0
    source = tuple(lane for lane,n in enumerate(counts) for _ in range(n))
    layers, extra = divmod(len(source),lanes)
    whole = not (head_clipped or tail_clipped)
    observed = {(k,b) for b,m in enumerate(masks) for k in range(lanes) if (m>>k)&1}
    origins = []
    consecutive = True
    for k in range(lanes):
        seq = sorted(b for lane,b in observed if lane==k)
        if seq:
            origins.append(seq[0]-(k%2!=lead))
            consecutive &= all(a+2==b for a,b in zip(seq,seq[1:]))
    profile_ok = max(counts)-min(counts)<=1 and (
        not whole or lanes!=3 or sum(k%2==lead for k,n in enumerate(counts) if n>layers)
        == min(extra,len(range(lead,lanes,2))))
    old = profile_ok and consecutive and len(set(origins))==1
    # Call the production planner on every distinct normalized window. Tap its
    # real matching result to verify every car at once. The primary assignment
    # precedes the ego-specific forbidden-edge re-solve, so it is rank invariant.
    group = [SimpleNamespace(lane=k,x=-14.99*b) for k,b in sorted(observed,key=lambda p:(p[1],-p[0]))]
    state = []
    def audit(vehicles,slots,**kwargs):
        match = solve_transport(vehicles,slots,**kwargs)
        state.append(all(vehicles[i][0]==slots[j][0] and abs(vehicles[i][1]-slots[j][1])<1e-8
                         for i,j in enumerate(match.assignment)))
        return match
    with patch("noa.staggered.solve_transport",audit):
        first = choose_target(0,group,lanes,29.98,head_clipped=head_clipped,tail_clipped=tail_clipped,
                              sensor_bounds=(back_mm/1000,ahead_mm/1000))
    assert len(state)==1
    if state[0]:
        assert first.lane==group[0].lane and abs(first.x-group[0].x)<1e-8
    return old,state[0]


def enumerate_windows():
    # D=29.980 m, all sensor arithmetic in integer millimetres. Lattice-aligned
    # and very narrow windows supplement the native 200/100 m configuration.
    half, layers, component_gap = 14990,18,50000
    ranges = [(200000,100000),(8*half,4*half),(5*half,3*half),(2*half,half)]
    result = []
    for lanes in range(2,9):
        counts = Counter()
        for phase in ((0,1) if lanes==2 else (0,)):
            classes = [lane_mask(lanes,(phase+b)%2) for b in range(2)]
            for tail in range(2**lanes-1):
                extra = [k for k in range(lanes) if (tail>>k)&1]
                if not legal_tail(lanes,extra):
                    continue
                bands = classes*layers+[classes[0]&tail,classes[1]&tail]
                for ego,mask in enumerate(bands):
                    if not mask:
                        continue
                    for idx,(front,rear) in enumerate(ranges):
                        lo,hi = ego-front//half,ego+rear//half
                        observed = tuple(bands[b] if 0<=b<len(bands) else 0 for b in range(lo,hi+1))
                        assert compatible_extension(lanes,(phase+lo)%2,observed)
                        start = next(b for b,m in enumerate(observed) if m)
                        end = max(b for b,m in enumerate(observed) if m)
                        h = (ego-lo-start)*half > front-component_gap
                        t = (lo+end-ego)*half > rear-component_gap
                        xego = -(ego-lo-start)*half
                        old,same = fitted(lanes,(lo+start+phase)%2,observed[start:end+1],h,t,xego-rear,xego+front)
                        counts["windows"] += mask.bit_count()
                        counts["unrepresentable"] += int(not same)*mask.bit_count()
                        counts["old_unrepresentable"] += int(not old)*mask.bit_count()
                        if idx==0:
                            counts["native_windows"] += mask.bit_count()
                            counts["native_unrepresentable"] += int(not same)*mask.bit_count()
        result.append(dict(lanes=lanes,**counts))
    return result


def targets(cars, ego, lanes, spacing, front, rear):
    rows = sorted([v for v in cars if -rear <= v.x-ego.x <= front],key=lambda v:(-v.x,-v.lane))
    fit = choose_target(rows.index(ego),rows,lanes,spacing,head_clipped=rows[0].x-ego.x>front-50,
                        tail_clipped=ego.x-rows[-1].x>rear-50,sensor_bounds=(ego.x-rear,ego.x+front))
    return dict(lane=ego.lane, proposed=fit.lane, dx_m=round(fit.x-ego.x,9),
                counts=[sum(v.lane==k for v in rows) for k in range(lanes)])


def production_examples():
    def field(x,k):
        return SimpleNamespace(x=x,lane=k)
    D = 29.98
    cars = [field(900-D*(row+.5*(k%2)),k) for row in range(18) for k in range(4)]
    cars.append(field(900-D*18.5,1))
    example = targets(cars,cars[16*4+2],4,D,200,100)
    assert example["counts"] == [8,10,8,9] and abs(example["dx_m"])<1e-8
    # Same nominal geometry, all lanes complete; a one-ulp measurement change
    # can remove just one of two parallel cars lying on the exact range edge.
    clean = [field(400-20*(row+.5*(k%2)),k) for row in range(30) for k in range(4)]
    ego = clean[16*4+2]
    before = targets(clean,ego,4,20,200,100)
    edge = next(v for v in clean if v.lane==2 and v.x-ego.x==200)
    edge.x = math.nextafter(edge.x,math.inf)
    after = targets(clean,ego,4,20,200,100)
    assert before["dx_m"]==0 and before["counts"]!=after["counts"] and abs(after["dx_m"])<1e-8
    # Any farther complete layers have identical observations. The same sensor
    # view can occur with the first observed band truly at the head or clipped.
    a = [field(-15*b,k) for b in range(20) for k in range(b%2,4,2)]
    b = a+[field(15,k) for k in (1,3)]
    observer = a[18]
    visible = lambda world: {(v.lane,v.x) for v in world if -100<=v.x-observer.x<=140}
    # Use complete even/odd layers at the invisible front so both worlds have
    # the canonical global even leading phase.
    b.extend(field(30,k) for k in (0,2))
    assert visible(a)==visible(b) and len(a)!=len(b)
    return dict(incomplete_tail=example,exact_edge=before,edge_after_one_ulp=after)


def noisy_hard_crops():
    """Independent position perturbations precede inclusive sensing, grouping and optimization."""
    rng = Random(1125)
    counts = {}
    for lanes in range(2,9):
        for spacing in (20.,29.98):
            for name,front,rear in (("native",200.,100.),("aligned",6*spacing,3*spacing),
                                    ("short",spacing,spacing/2)):
                stats = counts.setdefault(name,Counter())
                for trial in range(30):
                    phase = rng.randrange(2) if lanes==2 else 0
                    legal = [s for s in range(2**lanes-1)
                             if legal_tail(lanes,[k for k in range(lanes) if (s>>k)&1])]
                    tail = rng.choice(legal)
                    all_cars = []
                    for row in range(19):
                        for k in range(lanes):
                            if row==18 and not (tail>>k)&1:
                                continue
                            ideal = 900-spacing*(row+.5*(k%2!=phase))
                            all_cars.append(SimpleNamespace(lane=k,ideal=ideal,x=ideal+rng.uniform(-.05,.05)))
                    chunk = (all_cars[:lanes*3],all_cars[lanes*7:lanes*12],all_cars[-lanes*3:])[trial%3]
                    ego = rng.choice(chunk)
                    scene = sorted((c for c in all_cars if -rear<=c.x-ego.x<=front),
                                   key=lambda c:(-c.x,-c.lane))
                    ideal_scene = [c for c in all_cars if -rear<=c.ideal-ego.ideal<=front]
                    membership_changed = {id(c) for c in scene}!={id(c) for c in ideal_scene}
                    h,t = scene[0].x-ego.x>front-50,ego.x-scene[-1].x>rear-50
                    assert noisy_extension(scene,ego,lanes,spacing,front,rear)
                    target = choose_target(scene.index(ego),scene,lanes,spacing,head_clipped=h,tail_clipped=t,
                                           sensor_bounds=(ego.x-rear,ego.x+front))
                    stats["windows"] += 1
                    stats["membership_changed"] += membership_changed
                    stats["wrong_lane"] += target.lane!=ego.lane
                    err = abs(target.x-ego.x)
                    nominal_error = abs(target.x-ego.ideal)
                    stats["exceeds_10cm"] += err>.10000001
                    stats["exceeds_5cm_from_ideal"] += nominal_error>.05000001
                    stats["max_position_correction_m"] = max(stats["max_position_correction_m"],round(err,6))
    return counts


def hole_controls():
    """Separate detectable interior gaps, visible three-lane tail and field-edge holes."""
    cases = {}
    for lanes in range(2,9):
        d = 30.
        rows = [SimpleNamespace(lane=k,x=-d*(r+.5*(k%2))) for r in range(25) for k in range(lanes)]
        ego = rows[13*lanes]
        scene = sorted([c for c in rows if -100<=c.x-ego.x<=200],key=lambda c:(-c.x,-c.lane))
        for lane in range(lanes):
            missing = next(c for c in scene if c.lane==lane and 10<c.x-ego.x<=45)
            defect = [c for c in scene if c is not missing]
            assert staggered._observed_offsets(defect,lanes,d,0,(ego.x-100,ego.x+200)) is None
            assert not noisy_extension(defect,ego,lanes,d,200,100)
            cases["genuine_interior_holes_rejected"] = cases.get("genuine_interior_holes_rejected",0)+1
        if lanes==4:
            # At +195 m both odd lanes are certainly inside +200 m even with
            # 5 cm errors. A deleted companion is a real vacancy, despite the
            # coarse <50 m endpoint flag also being true.
            boundary = [c for c in scene if c.x==scene[0].x]
            assert len(boundary)==2 and boundary[0].x-ego.x==195
            defect = [c for c in scene if c is not boundary[0]]
            cases["missing_companion_5m_inside_sensor_accepted"] = (
                staggered._observed_offsets(defect,lanes,d,0,(ego.x-100,ego.x+200)) is not None)
            assert not noisy_extension(defect,ego,lanes,d,200,100)
        if lanes==3:
            tail = [SimpleNamespace(lane=k,x=-d*(25+.5*(k%2))) for k in (0,1)]
            visible = sorted((c for c in rows+tail if abs(c.x-tail[0].x)<=190),key=lambda c:(-c.x,-c.lane))
            bounds = (tail[0].x-190,tail[0].x+190)
            assert staggered._observed_offsets(visible,3,d,0,bounds) is None
            assert not noisy_extension(visible,tail[0],3,d,190,190)
            witness = choose_target(visible.index(tail[-1]),visible,3,d,head_clipped=True,tail_clipped=False,
                                    sensor_bounds=bounds)
            cases["middle_tail_without_both_outer_rejected"] = True
            cases["illegal_middle_tail_target_lane"] = witness.lane
    return cases


if __name__=="__main__":
    results = dict(production=production_examples(), exhaustive=enumerate_windows())
    results["distinct_production_windows"] = fitted.cache_info().misses
    results["perturbed_hard_crops"] = noisy_hard_crops()
    results["previous_coarse_edge_test_exceeding_10cm"] = dict(native=3,aligned=27,short=138)
    results["genuine_hole_controls"] = hole_controls()
    print(json.dumps(results,indent=2))
