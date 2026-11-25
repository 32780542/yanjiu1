"""Combine the two independently tested local decisions, one for each formation stage."""
import argparse
from pathlib import Path
from one_hop_trial import create
from join_action_trial import HELPER


def build(out):
    create(out)
    p=out/"noa/native_rules.py";s=p.read_text(encoding="utf8")
    s=s.replace("from math import sqrt","from math import sqrt\nfrom functools import lru_cache\nfrom itertools import combinations")
    marker="def _transport(ego, rows, memory, lanes, opened, transforming):"
    helper=HELPER[:HELPER.index("def _allows_join")]
    s=s.replace(marker,helper+marker)
    anchor="    since = memory.proposal_since if step == memory.proposed_step else ego.time"
    assert s.count(anchor)==1
    s=s.replace(anchor,"""    if not transforming and step is not None and len(group) < len(rows)+1:
        counts = tuple(sum(c.lane==lane for c in (ego,*rows)) for lane in range(lanes))
        if not _extendible(counts,ego.lane,step):
            step = None
"""+anchor)
    p.write_text(s,encoding="utf8")


if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("out",type=Path)
    build(p.parse_args().out)
