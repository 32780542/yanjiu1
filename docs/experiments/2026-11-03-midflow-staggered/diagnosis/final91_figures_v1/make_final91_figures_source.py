"""All-seed final91 figures from the completed independent original audit only."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
from statistics import mean
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image
from audit_raw_midflow import read, sha, write_csv

ENGINE=Path("C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py")
FLOWS=(1500,1750,2000)
SEEDS=tuple(range(91,96))


def csvrows(path):
    with path.open(encoding="utf-8-sig",newline="") as stream:
        return list(csv.DictReader(stream))


def run(audit,output):
    verification=read(audit/"verification.json")
    assert verification["cases_n"]==verification["eligible_cases_n"]==90 and verification["raw_reconstructed"]
    pairs,did,cases=(csvrows(audit/name) for name in ("paired_seeds.csv","road_did_seeds.csv","per_case.csv"))
    assert len(pairs)==60 and len(did)==30 and len(cases)==90
    assert all(r["eligible"]=="True" for r in pairs+did+cases)
    output.mkdir(parents=True,exist_ok=False)
    spec=importlib.util.spec_from_file_location("academic_final91_style",ENGINE)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    theme=engine.THEMES["nature"]
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"svg.fonttype":"none","axes.axisbelow":True})
    colors=("#3C5488","#E64B35","#00A087","#8491B4","#F39B7F")
    offsets=np.linspace(-.16,.16,5)
    panels,figures=[],[]
    for metric,unit,title,basename in (
        ("mean_system_time_s","s","Full-request system-time effects","final91_system_time_effects"),
        ("fuel_g_per_km","g/km","Fuel effects on the same complete cohort","final91_fuel_effects")):
        figure,axes=plt.subplots(2,3,figsize=(12.4,7.2),sharex=True,sharey="row",constrained_layout=True)
        for row,reference in enumerate(("NOA","S")):
            rowvalues=[0.]
            selected_panels=[]
            for col,flow in enumerate(FLOWS):
                ax=axes[row,col]
                values=[]
                for seed in SEEDS:
                    roads={r["scenario"]:r for r in pairs if r["reference"]==reference and float(r["flow"])==flow and int(r["seed"])==seed}
                    difference=next(r for r in did if r["reference"]==reference and float(r["flow"])==flow and int(r["seed"])==seed)
                    assert set(roads)=={"straight3","lane_drop"}
                    triple=[float(roads[r][metric+"_delta"]) for r in ("straight3","lane_drop")]+[float(difference[metric+"_did"])]
                    assert abs(triple[2]-(triple[1]-triple[0]))<1e-10 and np.isfinite(triple).all()
                    values.append(triple)
                values=np.array(values)
                rowvalues.extend(values.ravel())
                means=values.mean(axis=0)
                assert abs(means[2]-(means[1]-means[0]))<1e-10
                for i,seed in enumerate(SEEDS):
                    ax.plot([0+offsets[i],1+offsets[i]],values[i,:2],color=colors[i],lw=.7,alpha=.45,zorder=2)
                    ax.scatter(np.arange(3)+offsets[i],values[i],color=colors[i],s=30,edgecolor="white",linewidth=.4,zorder=3)
                for x,y in enumerate(means):
                    ax.plot([x-.26,x+.26],[y,y],color="black",lw=2.5,zorder=4)
                ax.axvline(1.5,color="0.82",lw=.8,ls=":")
                ax.axhline(0,color="0.35",lw=1,ls="--",zorder=1)
                ax.set_xticks(range(3),["Straight delta","Lane-drop delta","Road DID"])
                ax.set_xlim(-.5,2.5)
                ax.set_title(f"{'ABCDEF'[row*3+col]}   {flow} veh/h/lane",loc="left",fontsize=11,pad=8)
                engine.apply_base_style(ax,theme)
                panel=dict(metric=metric,unit=unit,reference=reference,flow=flow,seeds=list(SEEDS),
                           categories=["straight_delta","lane_drop_delta","absolute_road_DID"],
                           seed_values=values.tolist(),equal_seed_means=means.tolist(),points_n=int(values.size))
                panels.append(panel)
                selected_panels.append((ax,means))
            lo,hi=min(rowvalues),max(rowvalues)
            span=max(hi-lo,.02 if unit=="s" else .1)
            for ax,means in selected_panels:
                ax.set_ylim(lo-.18*span,hi+.25*span)
                for x,y in enumerate(means):
                    ax.text(x,y+.045*span,f"{y:+.3f}",ha="center",va="bottom",fontsize=8,color="black",zorder=5,
                            bbox=dict(facecolor="white",edgecolor="none",alpha=.7,pad=.5))
            axes[row,0].set_ylabel(f"D1 minus {reference}\nDelta ({unit}); negative = lower",fontsize=10)
        figure.suptitle(title+" | locked seeds 91–95",fontsize=13)
        handles=[Line2D([],[],color=c,marker="o",ls="none",markersize=5,label=str(s)) for s,c in zip(SEEDS,colors)]
        handles.append(Line2D([],[],color="black",lw=2.5,label="Five-seed mean"))
        figure.legend(handles=handles,loc="outside lower center",ncol=6,frameon=False,title="All seeds shown; same-seed road effects linked",fontsize=8,title_fontsize=8)
        figure.supxlabel("600 s demand, all requests drained within the common 1200 s limit. Road DID = lane-drop delta − straight delta.\nAxis scale shared within each row; dots are observations, with no confidence interval or significance annotation.",fontsize=8)
        for extension in ("png","svg"):
            figure.savefig(output/(basename+"."+extension),dpi=300,bbox_inches="tight",facecolor="white")
        plt.close(figure)
        with Image.open(output/(basename+".png")) as im:
            figures.append(dict(file=basename+".png",pixels=list(im.size),dpi=list(im.info.get("dpi",())),sha256=sha(output/(basename+".png")),visually_reviewed=False))
    assert len(panels)==12 and all(p["points_n"]==15 for p in panels)
    absolute=[]
    for flow in FLOWS:
        for road in ("straight3","lane_drop"):
            for label in ("NOA","D1","S"):
                values={int(r["seed"]):float(r["mean_system_time_s"]) for r in cases if r["label"]==label and float(r["flow"])==flow and r["scenario"]==road}
                assert set(values)==set(SEEDS)
                absolute.append(dict(flow=flow,scenario=road,label=label,seeds_n=5,mean_system_time_s=mean(values.values()),**{f"seed{s}_system_time_s":values[s] for s in SEEDS}))
    write_csv(output/"absolute_system_time.csv",absolute)
    lines=["|Flow (veh/h/lane)|Road|NOA system time (s)|D1 system time (s)|S system time (s)|","|---:|---|---:|---:|---:|"]
    for flow in FLOWS:
        for road in ("straight3","lane_drop"):
            values={r["label"]:r["mean_system_time_s"] for r in absolute if r["flow"]==flow and r["scenario"]==road}
            lines.append(f"|{flow}|{road}|{values['NOA']:.6f}|{values['D1']:.6f}|{values['S']:.6f}|")
    (output/"absolute_system_time.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    (output/"plot_data.json").write_text(json.dumps(dict(panels=panels,absolute_system=absolute,
          statistic="Equal means of five per-seed paired complete-request effects; no pooling by requested count.",
          negative="Lower metric; DID is an absolute effect difference across roads, never a percentage difference."),indent=2)+"\n",encoding="utf-8")
    sources=[audit/n for n in ("paired_seeds.csv","road_did_seeds.csv","per_case.csv","verification.json")]+[ENGINE,Path(__file__)]
    (output/"source_sha256.json").write_text(json.dumps({str(p.resolve()):sha(p) for p in sources},indent=2)+"\n",encoding="utf-8")
    (output/"make_final91_figures_source.py").write_bytes(Path(__file__).read_bytes())
    (output/"visual_qa.json").write_text(json.dumps(dict(figures=figures,panels_n=len(panels),all_points_per_figure=90,source_hashes_verified=True,visual_review_pending=True),indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(output=str(output.resolve()),figures=figures,points_per_figure=90)))


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    run(args.audit,args.output)
