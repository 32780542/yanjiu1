"""Build and run separate upstream anchor hypotheses over the frozen subflow controller."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
import zipfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
from run_study import REQUIRED, OPTIONAL


def edit(text,old,new):
    if text.count(old)!=1:
        raise ValueError(f"Expected one matching frozen fragment: {old!r}")
    return text.replace(old,new)


COMMON_HELPER='''
def _shared_anchor_speed(rank, group, base_positions, shift):
    """Preserve every clipped pairwise acceleration difference in this view."""
    omega = SHAPE_FREQUENCY
    headroom = float("inf")
    own = 0.
    for j, (car, slot_x) in enumerate(zip(group, base_positions)):
        lower = max(-SHAPE_ACCEL_LIMIT, -car.speed / CONTROL_STEP)
        upper = min(SHAPE_ACCEL_LIMIT, (MAX_SPEED - car.speed) / CONTROL_STEP)
        raw = omega ** 2 * (slot_x - car.x) + 2 * omega * (CRUISE - car.speed)
        base = min(upper, max(lower, raw))
        headroom = min(headroom, upper - base)
        if j == rank:
            own = base
    common = min(omega ** 2 * shift, headroom)
    speed = max(0., min(MAX_SPEED, group[rank].speed + CONTROL_STEP * (own + common)))
    return speed, common / omega ** 2

'''

FORMED_HELPER='''
def _inside_formed_pair(rank, group, lanes, spacing):
    """Does a closed pair of full layers in this physical view contain ego?"""
    size = 2 * lanes
    first = max(0, rank - size + 1)
    last = min(rank, len(group) - size)
    for start in range(first, last + 1):
        end = start + size
        if start and group[start-1].x == group[start].x:
            continue
        if end < len(group) and group[end-1].x == group[end].x:
            continue
        window = group[start:end]
        if max(c.speed for c in window) - min(c.speed for c in window) > .5 + 1e-9:
            continue
        columns = [[] for _ in range(lanes)]
        for c in window:
            if 0 <= c.lane < lanes and abs(c.y - (c.lane + .5) * 3.3) <= .3 + 1e-9:
                columns[c.lane].append(c.x)
        if any(len(col) != 2 or abs(col[0] - col[1] - spacing) > 2. + 1e-9
               for col in columns):
            continue
        for phase in ((0, 1) if lanes == 2 else (0,)):
            for row in range(2):
                origins = [col[row] + spacing * .5 * ((j + phase) % 2)
                           for j, col in enumerate(columns)]
                if max(origins) - min(origins) > 2. + 1e-9:
                    break
            else:
                return True
    return False

'''


def prepare(out,modes,archive):
    out.mkdir(parents=True,exist_ok=False)
    frozen=out/"frozen"
    base=ROOT/"tmp/nov25-open-subflow/frozen/subflow"
    manifest={}
    z=zipfile.ZipFile(archive) if archive else None
    for mode in modes:
        dst=frozen/mode
        for name in (*REQUIRED,*OPTIONAL):
            f=dst/name;f.parent.mkdir(parents=True,exist_ok=True)
            f.write_bytes(z.read("base/"+name) if z else (base/name).read_bytes())
        (dst/"tmp").mkdir()
        slots=dst/"noa/staggered.py";rules=dst/"noa/native_rules.py"
        s=slots.read_text(encoding="utf8");r=rules.read_text(encoding="utf8")
        assert hashlib.sha256(slots.read_bytes()).hexdigest()=="6697aea07a4395c669e4cbccddf467c2f94effcb3ced877ea0a611118956c604"
        if mode=="common":
            s=edit(s,"    step_ready: bool = True","    step_ready: bool = True\n    base_positions: tuple | None = None\n    requested_shift: float = 0.")
            old="    if forward_anchor is not None:\n        x = anchored_x(x, origin - front_offset, spacing, forward_anchor)"
            s=edit(s,old,"    base_positions = None\n    shift = 0.\n    if forward_anchor is not None:\n        shift = anchored_x(0., origin - front_offset, spacing, forward_anchor)\n        if shift > 0.:\n            base_positions = tuple(slots[j][1] for j in fit.assignment)")
            s=edit(s,"_open_subflow(rank, group, slots, fit, opened_lanes))","_open_subflow(rank, group, slots, fit, opened_lanes), base_positions, shift)")
            r=edit(r,"def _transport(ego, rows, memory, lanes, opened, transforming):",COMMON_HELPER+"\ndef _transport(ego, rows, memory, lanes, opened, transforming):")
            old="            x = anchored_x(ego.x, ego.x, desired_spacing(ego.speed), forward_anchor)\n            command = replace(command, speed=_shape_speed(ego, x), target_x=x)"
            r=edit(r,old,"            shift = anchored_x(0., ego.x, desired_spacing(ego.speed), forward_anchor)\n            speed, applied = _shared_anchor_speed(0, group, (ego.x,), shift)\n            command = replace(command, speed=speed, target_x=ego.x + applied)")
            r=edit(r,"    speed = _shape_speed(ego, target.x)","    target_x = target.x\n    if target.base_positions is None:\n        speed = _shape_speed(ego, target_x)\n    else:\n        speed, applied = _shared_anchor_speed(rank, group, target.base_positions, target.requested_shift)\n        target_x += applied")
            r=edit(r,"Command(speed, lane, reason, target.x, predecessor","Command(speed, lane, reason, target_x, predecessor")
            slots.write_text(s,encoding="utf8");rules.write_text(r,encoding="utf8")
        elif mode=="visible":
            old="        x = anchored_x(x, origin - front_offset, spacing, forward_anchor)"
            s=edit(s,old,"        from noa.native_rules import FRONT_VIEW, REAR_VIEW\n        m = sum(-REAR_VIEW <= forward_anchor - car.x <= FRONT_VIEW for car in group)\n        x += m / (len(group) + m) * max(0., forward_anchor - spacing - (origin - front_offset))")
            slots.write_text(s,encoding="utf8")
        elif mode=="shared_view":
            old="    if forward_anchor is not None:\n        x = anchored_x(x, origin - front_offset, spacing, forward_anchor)"
            s=edit(s,old,"    if forward_anchor is not None:\n        from noa.native_rules import FRONT_VIEW\n        if forward_anchor - min(c.x for c in group) <= FRONT_VIEW:\n            x = anchored_x(x, origin - front_offset, spacing, forward_anchor)")
            slots.write_text(s,encoding="utf8")
        elif mode=="formed_pair":
            s=edit(s,"def anchored_x(",FORMED_HELPER+"\ndef anchored_x(")
            s=edit(s,"    if forward_anchor is not None:\n        x = anchored_x(",
                   "    if forward_anchor is not None and not _inside_formed_pair(rank, group, lanes, spacing):\n        x = anchored_x(")
            slots.write_text(s,encoding="utf8")
        elif mode=="unanchored":
            old="    if not transforming:\n        forward_anchor = min((c.x for c in rows if c.x > group[0].x), default=None)\n"
            r=edit(r,old,"")
            rules.write_text(r,encoding="utf8")
        manifest[mode]={name:hashlib.sha256((dst/name).read_bytes()).hexdigest() for name in (*REQUIRED,*OPTIONAL)}
    (frozen/"measure.py").write_bytes(z.read("measure.py") if z else
                                    (ROOT/"tmp/nov25-open-subflow/frozen/measure.py").read_bytes())
    if z:
        z.close()
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2))


def run(out,workers,modes):
    jobs=[]
    for road,n,seed in itertools.product(("2to3","3to2","3to4","4to3"),(12,24),(8721,8722,8723)):
        jobs.extend((mode,road,str(n),"long",str(seed),"2800") for mode in modes)
    for road in ("2to3","3to2","3to4","4to3"):
        jobs.extend((mode,road,"12","demo12","20","1600") for mode in modes)
    def one(cell):
        name="_".join(cell)
        with (out/(name+".log")).open("xb") as log:
            subprocess.run([sys.executable,"-B",str(HERE/"splice/probe.py"),"--out",str(out),
                            "--cell",*cell],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=650)
        print(name,flush=True)
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(one,jobs))


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True);p.add_argument("--prepare",action="store_true")
    p.add_argument("--workers",type=int,default=5)
    p.add_argument("--shared-view",action="store_true",help="Separate geometric gate hypothesis only")
    p.add_argument("--formed-pair",action="store_true",help="Protect actual dynamic-spacing complete layer pairs only")
    p.add_argument("--unanchored",action="store_true",help="Identical subflow with its upstream external anchor disabled")
    p.add_argument("--base-archive",type=Path,help="Restore a self-contained original runner and evaluator")
    p.add_argument("--pack-base",type=Path,help="Archive an already prepared subflow and its evaluator")
    a=p.parse_args()
    assert sum((a.shared_view,a.formed_pair,a.unanchored))<=1
    modes=("formed_pair",) if a.formed_pair else ("shared_view",) if a.shared_view else ("unanchored",) if a.unanchored else ("subflow","common","visible")
    if a.pack_base:
        with zipfile.ZipFile(a.pack_base,"x",compression=zipfile.ZIP_DEFLATED) as z:
            for name in (*REQUIRED,*OPTIONAL):
                z.write(a.out/"frozen/subflow"/name,"base/"+name)
            z.write(a.out/"frozen/measure.py","measure.py")
    elif a.prepare:
        prepare(a.out.resolve(),modes,a.base_archive)
    else:
        run(a.out.resolve(),a.workers,modes)
