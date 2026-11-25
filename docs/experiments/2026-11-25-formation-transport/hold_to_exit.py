"""For complete fixed cohorts, check formation until the last frame all cars are still on the road."""
from collections import Counter
from pathlib import Path
import json
from noon_summary import HERE, write


def main():
    batches = [("development","exact", "nov25-noon-exact-dev64", "candidate"),
               ("paired384","morning","nov25-noon-reference-fresh","candidate"),
               ("paired384","morning","nov25-noon-final-reference","candidate"),
               ("paired384","exact","nov25-noon-reuse-first","candidate"),
               ("paired384","exact","nov25-noon-reuse-last","candidate"),
               ("prospective96","morning","nov25-noon-prospective96","baseline"),
               ("prospective96","exact","nov25-noon-prospective96","candidate")]
    totals={}
    for sample,method,dirname,source in batches:
        folder=HERE.parents[2]/"tmp"/dirname
        for report in sorted(folder.glob(source+"_*/measure.json")):
            case=json.loads((report.parent/"row.json").read_bytes())
            counts=totals.setdefault((sample,method),Counter())
            counts["cases"]+=1
            if not case["whole_both"]:
                continue
            counts["both"]+=1
            down=json.loads(report.read_bytes())["downstream"]
            last_all=down["all_present_intervals_s"][-1][1]
            episodes=down["whole_episodes"]
            assert down["last_whole_s"]==episodes[-1]["end_s"]<=last_all
            full_at_exit=down["last_whole_s"]==last_all
            counts["complete_at_last_shared_frame"]+=full_at_exit
            counts["unbroken_from_first_whole_to_exit"]+=full_at_exit and len(episodes)==1
            trips=json.loads((folder/case["run"]/"trips.json").read_bytes())
            for trip in trips:
                for ev in trip["lane_events"]:
                    if ev["time_s"]>down["last_whole_s"]:
                        key="crossings_before_first_exit" if ev["time_s"]<=last_all else "crossings_after_last_shared_frame"
                        counts[key]+=abs(ev["to_lane"]-ev["from_lane"])
    keys=("cases","both","complete_at_last_shared_frame","unbroken_from_first_whole_to_exit",
          "crossings_before_first_exit","crossings_after_last_shared_frame")
    rows=[dict(sample=s,method=m,**{key:c[key] for key in keys}) for (s,m),c in totals.items()]
    write("noon_hold_to_exit.csv",rows)
    for row in rows:
        print(row)


if __name__=="__main__":
    main()
