"""Join the separately audited panels, checking native requests and physical entries."""
from concurrent.futures import ProcessPoolExecutor
import csv
import gzip
import hashlib
import json
from pathlib import Path
from pose_anchor_phase import BATCHES,HERE,ROOT,STUDY

OUTPUTS={
    "traffic":("history_flow","subflow_visible","common_flow","shared_flow","last_flow"),
    "phase":("history_phase","subflow_visible_phase","common_phase","shared_phase","last_phase"),
    "finite":("finite_base","finite_last"),
    "gap_phase":("closing_phase_initial","closing_phase_last")}


def read_traffic(r):
    folder=STUDY/BATCHES[r["model"]]/f"3to2_s6_q{int(float(r['flow']))}"
    path=next(folder.glob("*/positions.jsonl.gz"));first={};trace=hashlib.sha256()
    with gzip.open(path,"rb") as f:
        for line in f:
            trace.update(line)
            frame=json.loads(line)
            for k,state in frame["states"].items():
                if k not in first:first[k]=(frame["time_s"],*state[:3])
    r["trace_sha"]=trace.hexdigest()
    assert r["first_states_sha"]==hashlib.sha256(json.dumps(first,sort_keys=True).encode()).hexdigest()
    return r,first


def main():
    home=ROOT/"tmp/nov25-pose-anchor"
    for panel,inputs in OUTPUTS.items():
        rows=[]
        for source in inputs:
            with (home/(source+".csv")).open(encoding="utf8",newline="") as f:
                rows.extend(csv.DictReader(f))
        if panel=="traffic":
            with ProcessPoolExecutor(3) as pool:
                compared=list(pool.map(read_traffic,rows))
            for r,first in compared:
                base,ref=next((s,v) for s,v in compared if s["flow"]==r["flow"] and s["model"]=="subflow")
                assert (ref.keys()==first.keys() and r["route_sha"]==base["route_sha"] and r["tape_sha"]==base["tape_sha"])
                r["different_first_times_vs_subflow"]=sum(first[k][0]!=ref[k][0] for k in first)
                r["different_first_position_speed_vs_subflow"]=sum(first[k][1:]!=ref[k][1:] for k in first)
            rows=[r for r,v in compared]
        assert len(rows)=={"traffic":24,"phase":24,"finite":144,"gap_phase":8}[panel]
        with (HERE/f"pose_anchor_{panel}.csv").open("x",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,rows[0]);writer.writeheader();writer.writerows(rows)
        print(panel,len(rows))


if __name__=="__main__":main()
