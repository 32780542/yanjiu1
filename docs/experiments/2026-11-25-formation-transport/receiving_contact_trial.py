"""Keep a receiving link until its observed occupant changes, or test the slot's longitudinal conflict."""
import argparse
from pathlib import Path

from slot_predecessor_trial import build as predecessor


def build(out, mode):
    predecessor(out, "order", "combined")
    p = out / "noa/staggered.py"
    s = p.read_text(encoding="utf8")
    trigger = "abs(ahead.lane-lane) == 1 and ahead.x >= group[rank].x"
    if mode == "target":
        s = s.replace(trigger, trigger + " and ahead.x - x < CLEARANCE")
        s = s.replace("            if abs(ahead.lane", "            from noa.native_rules import CLEARANCE\n            if abs(ahead.lane")
    else:
        s = s.replace("    released: bool = True", "    released: bool = True\n    receiving_track: int | None = None")
        s = s.replace("history=(), receiving=False):", "history=(), receiving=False, previous_receiver=None):")
        s = s.replace("    if receiving and lane", "    receiving_track = None\n    if receiving and lane")
        s = s.replace("            if "+trigger+":", "            from noa.native_rules import _clear\n            if ("+trigger+"\n                    and (ahead.track == previous_receiver or not _clear(ahead, (group[rank],), lane))):\n                receiving_track = ahead.track")
        s = s.replace("fit, opened_lanes, lanes))","fit, opened_lanes, lanes), receiving_track)")
        q = out / "noa/native_rules.py"
        a = q.read_text(encoding="utf8")
        a = a.replace("    preview_x: float | None = None", "    preview_x: float | None = None\n    receiving_track: int | None = None")
        assert "receiving_track: int" in a
        a = a.replace("receiving=transforming,", "receiving=transforming, previous_receiver=memory.receiving_track,")
        a = a.replace("Memory(lane, predecessor, proposed_step=step,", "Memory(lane, predecessor, receiving_track=target.receiving_track, proposed_step=step,")
        q.write_text(a, encoding="utf8")
    p.write_text(s, encoding="utf8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path)
    parser.add_argument("mode", choices=("hold", "target"))
    args = parser.parse_args()
    build(args.out, args.mode)
