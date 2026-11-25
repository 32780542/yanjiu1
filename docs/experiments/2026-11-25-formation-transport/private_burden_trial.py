"""Build an isolated ego-history experiment from the reviewed Git snapshot."""
import argparse
from pathlib import Path
import subprocess
from run_study import ROOT, REQUIRED, OPTIONAL

BASE = "7c3771e4eb7e43a4e8ab28000d6ae3bf1508d747"
VARIANT = "variants/phase5g_pure_formation"


def build(out, scope):
    out.mkdir(parents=True, exist_ok=False)
    for name in (*REQUIRED, *OPTIONAL):
        src = subprocess.check_output(["git", "show", f"{BASE}:{VARIANT}/{name}"], cwd=ROOT)
        f = out / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(src)
    (out / "tmp").mkdir()
    def edit(name, before, after):
        path = out / "noa" / name
        code = path.read_text(encoding="utf8")
        assert code.count(before) == 1, before
        path.write_text(code.replace(before, after), encoding="utf8")
    edit("native_rules.py", "    proposal_since: float = 0.", """    proposal_since: float = 0.
    stage_lane: int | None = None
    stage_changes: int = 0
    transition: bool = False""")
    edit("native_rules.py", "    rows = tuple(c for c in neighbors", """    same_stage = transition == memory.transition and memory.stage_lane is not None
    observed_changes = (memory.stage_changes + abs(ego.lane - memory.stage_lane)) if same_stage else 0
    memory = replace(memory, stage_changes=observed_changes)
    rows = tuple(c for c in neighbors""")
    edit("native_rules.py", "    return replace(command, speed=min(command.speed, limit)), memory",
         """    memory = replace(memory, stage_lane=ego.lane, stage_changes=observed_changes, transition=transition)
    return replace(command, speed=min(command.speed, limit)), memory""")
    active = {"transform":"transforming", "formation":"not transforming", "both":"True"}[scope]
    edit("native_rules.py","                           forward_anchor=forward_anchor, opened_lanes=",
         "                           ego_history=memory.stage_changes if "+active+" else 0,\n                           forward_anchor=forward_anchor, opened_lanes=")
    edit("staggered.py","sensor_bounds=None, forward_anchor=None, opened_lanes=None):",
         "sensor_bounds=None, forward_anchor=None, opened_lanes=None, ego_history=0):")
    edit("staggered.py",'ego_index=rank, action="next_lane", position_error=POSITION_ERROR_M)',
         'ego_index=rank, action="next_lane", position_error=POSITION_ERROR_M, ego_history=ego_history)')
    edit("transport.py","ego_index=None, action=None, position_error=None):",
         "ego_index=None, action=None, position_error=None, ego_history=0):")
    edit("transport.py","    chosen = _assignment(costs, penalty)\n    assignment = [0] * n", """    chosen = _assignment(costs, penalty)
    if ego_history:
        ego_row = car_order.index(ego_index)
        burden = [max(bottleneck, ego_history + abs(source[ego_row]-lane)) for lane in target]
        for limit in sorted(set(burden)):
            blocked = [ban or h > limit for ban,h in zip(forbidden[ego_row],burden)]
            if blocked[chosen[ego_row]]:
                trial = costs.copy()
                trial[ego_row] = [penalty if ban else c for ban,c in zip(blocked,costs[ego_row])]
                candidate = _assignment(trial, penalty)
                if any(trial[i][j] == penalty for i,j in enumerate(candidate)):
                    continue
                chosen = candidate
            forbidden = list(forbidden)
            forbidden[ego_row] = blocked
            costs[ego_row] = [penalty if ban else c for ban,c in zip(blocked,costs[ego_row])]
            break
    assignment = [0] * n""")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("out", type=Path)
    p.add_argument("--scope", choices=("formation","transform","both"), required=True)
    args = p.parse_args()
    build(args.out, args.scope)
