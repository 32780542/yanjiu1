"""Report the two-seed paired test specified after the controller was frozen."""
from collections import defaultdict
from itertools import product
import json
from pathlib import Path

from noon_summary import HERE, summarize, write


def main():
    folder = HERE.parents[2]/"tmp/nov25-noon-prospective96"
    expected = list(product(("3to2","4to3","2to3","3to4"),(7,11,12,13,17,24),
                            ("compact","long"),(11781,11782)))
    pairs = defaultdict(list)
    records = []
    for road,n,profile,seed in expected:
        key = f"{road}_{n}_{profile}_{seed}"
        a,b = (json.loads((folder/f"{method}_{key}"/"row.json").read_bytes())
               for method in ("baseline","candidate"))
        assert all(a[k]==b[k] for k in ("road","n","spacing","seed","tape_sha256","first_frame_sha256"))
        assert all(r["status"]=="drained" and r["completed"]==n and r["initial_matches_request"]
                   for r in (a,b))
        for label,row in (("morning",a),("noon",b)):
            pairs[road,label].append(row)
            pairs["all",label].append(row)
            records.append({k:row[k] for k in
                            ("road","n","spacing","seed","completed","collisions","teleports",
                             "whole_both","upstream_whole_hold_s","downstream_whole_hold_s",
                             "formation_actual_total","formation_actual_max","formation_bound_total","formation_bound_max",
                             "formation_best_legal_total","formation_best_legal_max","transform_actual_total",
                             "transform_actual_max","transform_bound_total","transform_bound_max",
                             "transform_best_legal_total","transform_best_legal_max","first_frame_sha256")} | {"method":label})
    summary=[dict(road=road,method=label,**summarize(pairs[road,"morning"],rows))
             for (road,label),rows in pairs.items()]
    write("noon_prospective_cases.csv",records)
    write("noon_prospective_summary.csv",summary)
    for row in summary:
        if row["road"]=="all":
            print(row)


if __name__=="__main__":
    main()
