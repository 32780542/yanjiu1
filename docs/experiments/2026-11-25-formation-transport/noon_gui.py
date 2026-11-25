"""Confirm real, free-camera SUMO runs and export concise evidence for the seven-car example."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
import measure

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
original_shape = measure.whole_shape


def strict_shape(states, lanes):
    if lanes == 2:
        ordered = sorted(states.values(), key=lambda s:-s[0])
        if any(measure.lane_of(a[1]) == measure.lane_of(b[1]) for a,b in zip(ordered,ordered[1:])):
            return False
    return original_shape(states,lanes)


def main():
    measure.whole_shape = strict_shape
    rows=[]
    for case in ("3to2","4to3","2to3","3to4","7car_4to3_11254","24car_4to3_10153","11car_3to2_9901"):
        [folder] = (ROOT/"tmp/nov25-noon-exact-live"/case).glob("*/result.json")
        run=folder.parent
        result=json.loads(folder.read_bytes())
        cmd=json.loads((run/"sumo_command.json").read_bytes())
        assert Path(cmd[0]).stem == "sumo-gui" and result["gui"] and result["gui_auto_zoom"] is False
        stat=measure.measure(run,True)
        assert stat["safe"] and stat["status"]=="drained" and stat["completed"]==stat["requested"]
        formation,transform=stat["formation_moves"],stat["transform_moves"]
        assert formation and transform
        with gzip.open(run/"positions.jsonl.gz","rb") as stream:
            trace=hashlib.file_digest(stream,"sha256").hexdigest()
        rows.append(dict(case=case,cars=stat["completed"],gui=True,auto_zoom=False,
                         upstream="/".join(map(str,formation["end_counts"][:stat["upstream_lanes"]])),
                         downstream="/".join(map(str,transform["end_counts"][:stat["downstream_lanes"]])),
                         upstream_s=stat["upstream"]["whole_hold_s"],
                         downstream_s=stat["downstream"]["whole_hold_s"],
                         trace_sha256=trace,run=str(run.relative_to(ROOT))))
        if case=="7car_4to3_11254":
            with ZipFile(HERE/"figures/receiving7_gui.zip","w",compression=ZIP_DEFLATED) as z:
                for name in ("input.json","result.json","positions.jsonl.gz","trips.json","sumo_command.json",
                             "native.net.xml","native.rou.xml"):
                    z.write(run/name,name)
    with (HERE/"noon_live_runs.csv").open("w",encoding="utf8",newline="") as out:
        w=csv.DictWriter(out,list(rows[0]));w.writeheader();w.writerows(rows)
    print(len(rows),"real SUMO-GUI runs")


if __name__=="__main__":
    main()
