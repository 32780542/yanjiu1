"""Stream fixed seed91 original speeds into the predeclared common spacetime bins."""
import argparse
from collections import defaultdict
import csv
import gzip
import importlib.util
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.patheffects as pe
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image
from audit_raw_midflow import read,sha,write_csv

HERE=Path(__file__).resolve().parent
REPO=Path(__file__).resolve().parents[4]
BATCH=REPO/"tmp/staggered_bottleneck/20261103_midflow_final91_D1_NOA60"
ENGINE=Path("C:/Users/84335/.codex/skills/academic-figures/scripts/gen_figure.py")
RULES="2be889140b497b763818a35814b0f34815c7cccd309dd5007ebaddca8a91f35a"
TE=np.arange(100.,600.1,10.)
XE=np.arange(0.,1200.1,25.)


def extract(record,previous_audit,output,sources):
    wrapper=Path(record["case_output"])
    state=read(wrapper/"case_record.json")
    assert state["seal_status"]=="verified" and state["safe"] and state["all_completed"]
    run=Path(state["run_dir"])
    seal=read(wrapper/"evidence/seal.json")
    label="NOA" if state["mode"]=="noa" else "D1"
    key=(label,float(state["flow"]),91,"lane_drop")
    audited=previous_audit[key]
    assert Path(audited["case_dir"]).resolve()==run.resolve()
    local={}
    for name in ("positions.jsonl.gz","events.jsonl.gz"):
        path=run/name
        digest=sha(path)
        assert digest==seal["originals"][name]["sha256"] and path.stat().st_size==seal["originals"][name]["bytes"]
        local[str(path.resolve())]=digest
    assert local[str((run/"positions.jsonl.gz").resolve())]==audited["positions_sha256"]
    for name,field in (("input.json","input_sha256"),("result.json","result_sha256"),("trips.json","trips_sha256")):
        path=run/name
        digest=sha(path)
        assert digest==audited[field]
        local[str(path.resolve())]=digest
    original,result,trips=read(run/"input.json"),read(run/"result.json"),read(run/"trips.json")
    assert result["seed"]==91 and result["scenario"]=="lane_drop" and result["mode"]==state["mode"]
    assert result["source_sha256"]["noa/native_rules.py"]==RULES and result["step_s"]==.1
    assert original["positions_step_s"]==.1 and result["all_completed"] and result["safe"]
    for name,digest in result["source_sha256"].items():
        path=run/"source"/name
        assert sha(path)==digest
        local[str(path.resolve())]=digest
    for path in (wrapper/"case_record.json",wrapper/"evidence/seal.json"):
        local[str(path.resolve())]=sha(path)
    counts=np.zeros((50,48),dtype=np.int64)
    sums=np.zeros((50,48),dtype=np.float64)
    lane2counts=np.zeros_like(counts)
    lane2sums=np.zeros_like(sums)
    lanes={t["vehicle_id"]:t["lane"] for t in trips}
    events=defaultdict(list)
    if state["flow"]==2000:
        for t in trips:
            for event in t["lane_events"]:
                events[round(event["time_s"]*10)].append((t["vehicle_id"],event["to_lane"]))
    nframes,nsamples,total_speed,outside=0,0,0.,0
    speed_sum_correction=0.
    previous_time,first_time,last_time,end_seen=None,None,None,False
    with gzip.open(run/"positions.jsonl.gz","rt",encoding="utf-8") as stream:
        for line in stream:
            frame=json.loads(line)
            time,vehicles=frame["time_s"],frame["states"]
            tick=round(time*10)
            if previous_time is not None:
                assert 0<time-previous_time<.100001
            previous_time=time
            for vehicle,lane in events.get(tick,()):
                lanes[vehicle]=lane
            if time>=600:
                end_seen=True
                break
            if time<100:
                continue
            nframes+=1
            first_time=time if first_time is None else first_time
            last_time=time
            ti=(tick-1000)//100
            assert 0<=ti<50 and abs(time-tick/10)<1e-7
            for vehicle,s in vehicles.items():
                x,speed=s[0],s[2]
                assert -1e-7<=speed<=33.3+1e-7
                if not 0<=x<1200:
                    outside+=1
                    continue
                xi=int(x//25)
                counts[ti,xi]+=1
                sums[ti,xi]+=speed
                nsamples+=1
                corrected=speed-speed_sum_correction
                updated=total_speed+corrected
                speed_sum_correction=(updated-total_speed)-corrected
                total_speed=updated
                if state["flow"]==2000 and lanes[vehicle]==2:
                    lane2counts[ti,xi]+=1
                    lane2sums[ti,xi]+=speed
    assert end_seen and nframes==5000 and first_time==100 and abs(last_time-599.9)<1e-7
    assert int(counts.sum())==nsamples and abs(float(sums.sum())-total_speed)<1e-5
    def save_bins(name,n,v,scope):
        path=output/name
        with path.open("x",encoding="utf-8-sig",newline="") as target:
            writer=csv.DictWriter(target,fieldnames=["flow_veh_h_lane","seed","policy","scope","time_start_s","time_end_s","position_start_m","position_end_m","samples_n","speed_sum_mps","mean_speed_mps"])
            writer.writeheader()
            for ti in range(50):
                for xi in range(48):
                    count=int(n[ti,xi])
                    writer.writerow(dict(flow_veh_h_lane=state["flow"],seed=91,policy=label,scope=scope,
                        time_start_s=TE[ti],time_end_s=TE[ti+1],position_start_m=XE[xi],position_end_m=XE[xi+1],
                        samples_n=count,speed_sum_mps=float(v[ti,xi]),mean_speed_mps=float(v[ti,xi])/count if count else ""))
        return dict(file=name,sha256=sha(path),bins_n=2400,nonempty_bins_n=int((n>0).sum()),samples_n=int(n.sum()))
    csvfiles=[save_bins(f"flow{int(state['flow'])}_{label}_all_lanes_bins.csv",counts,sums,"all_actual_physical_vehicles")]
    if state["flow"]==2000:
        csvfiles.append(save_bins(f"flow2000_{label}_lane2_bins.csv",lane2counts,lane2sums,"actual_SUMO_lane_index_2_replayed_from_original_lane_events"))
    sources.update(local)
    info=dict(flow=state["flow"],seed=91,scenario="lane_drop",policy=label,mode=state["mode"],candidate=state["candidate"],
              wrapper=str(wrapper.resolve()),run_dir=str(run.resolve()),case_record_seal_status=state["seal_status"],rules_sha256=RULES,
              source_sha256=result["source_sha256"],original_file_sha256=local,window_frames=nframes,
              first_window_sample_s=first_time,last_window_sample_s=last_time,physical_vehicle_samples=nsamples,
              outside_0_1200_samples=outside,speed_sum_mps=total_speed,csv=csvfiles)
    return info,counts,sums,lane2counts,lane2sums


def run(output):
    assert output.resolve().is_relative_to(HERE)
    manifest=read(BATCH/"manifest.json")
    selected=[r for r in manifest if r["seed"]==91 and r["scenario"]=="lane_drop"]
    assert len(selected)==6 and {(r["flow"],r["mode"]) for r in selected}=={(f,m) for f in (1500,1750,2000) for m in ("noa","transform")}
    audited_path=HERE/"final91_independent_v1/per_case.csv"
    with audited_path.open(encoding="utf-8-sig",newline="") as stream:
        audited={(r["label"],float(r["flow"]),int(r["seed"]),r["scenario"]):r for r in csv.DictReader(stream)}
    output.mkdir(parents=True,exist_ok=False)
    sources={str(p.resolve()):sha(p) for p in (BATCH/"manifest.json",audited_path,Path(__file__),ENGINE)}
    data,runmap={},[]
    for record in sorted(selected,key=lambda r:(r["flow"],r["mode"])):
        info,*arrays=extract(record,audited,output,sources)
        data[(int(info["flow"]),info["policy"])]=arrays
        runmap.append(info)
        print(json.dumps(dict(flow=info["flow"],policy=info["policy"],samples=info["physical_vehicle_samples"])),flush=True)
    spec=importlib.util.spec_from_file_location("academic_spacetime_style",ENGINE)
    engine=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    theme=engine.THEMES["nature"]
    plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"svg.fonttype":"none"})
    cmap=plt.colormaps["viridis"].copy()
    cmap.set_bad("white")
    norm=colors.Normalize(vmin=0,vmax=33.3)
    figures=[]
    def panel(ax,n,v,title):
        avg=np.divide(v,n,out=np.zeros_like(v),where=n>0)
        mesh=ax.pcolormesh(TE,XE,np.ma.masked_where(n.T==0,avg.T),cmap=cmap,norm=norm,shading="flat",antialiased=False)
        engine.apply_base_style(ax,theme)
        ax.grid(False)
        for position,ls in ((640,"--"),(1000,"-")):
            line=ax.axhline(position,color="black",lw=.9,ls=ls)
            line.set_path_effects([pe.Stroke(linewidth=1.7,foreground="white"),pe.Normal()])
        ax.set(title=title,xlim=(100,600),ylim=(0,1200),xticks=[100,200,300,400,500,600],yticks=[0,400,640,1000,1200])
        ax.tick_params(labelsize=8)
        return mesh
    def save(fig,name):
        for ext in ("png","svg"):
            fig.savefig(output/(name+"."+ext),dpi=300,bbox_inches="tight",facecolor="white")
        plt.close(fig)
        with Image.open(output/(name+".png")) as image:
            figures.append(dict(file=name+".png",pixels=list(image.size),dpi=list(image.info.get("dpi",())),png_sha256=sha(output/(name+".png")),svg_sha256=sha(output/(name+".svg")),visually_reviewed=False))
    legend=[Line2D([],[],color="black",ls="--",lw=1,label="Preparation starts: 640 m"),Line2D([],[],color="black",ls="-",lw=1,label="Lane end: 1000 m")]
    fig,axes=plt.subplots(3,2,figsize=(10.8,10.1),sharex=True,sharey=True)
    fig.subplots_adjust(left=.08,right=.865,top=.90,bottom=.12,wspace=.08,hspace=.27)
    for row,flow in enumerate((1500,1750,2000)):
        for col,label in enumerate(("NOA","D1")):
            n,v,_,_=data[(flow,label)]
            mesh=panel(axes[row,col],n,v,f"{'ABCDEF'[row*2+col]}   {flow} veh/h/lane | {label}")
            if col==0:axes[row,col].set_ylabel("Position (m)")
            if row==2:axes[row,col].set_xlabel("Simulation time (s)")
    cax=fig.add_axes([.895,.12,.022,.78])
    bar=fig.colorbar(mesh,cax=cax,ticks=[0,10,20,28.8,33.3])
    bar.set_label("Mean measured speed (m/s)")
    fig.suptitle("Fixed seed 91: measured speeds across all physical lanes",y=.985,fontsize=13)
    fig.legend(handles=legend,loc="upper center",bbox_to_anchor=(.48,.957),ncol=2,frameon=False,fontsize=9)
    fig.text(.49,.022,"25 m × 10 s bins; actual-vehicle sample mean; empty bins are white; common 0–33.3 m/s scale.\nRepresentative seed fixed before viewing: all five seeds determine the reported effects; seed 91 includes reversed low-flow road DIDs.",ha="center",va="bottom",fontsize=8)
    save(fig,"seed91_all_lanes_speed_spacetime")
    # The ending-lane subset is streamed at the same time, with original actual
    # SUMO lane-index flips; it is a declared supplement, not a new seed search.
    fig,axes=plt.subplots(1,2,figsize=(10.8,4.7),sharex=True,sharey=True)
    fig.subplots_adjust(left=.08,right=.865,top=.81,bottom=.22,wspace=.08)
    for col,label in enumerate(("NOA","D1")):
        _,_,n,v=data[(2000,label)]
        mesh=panel(axes[col],n,v,f"{label} | 2000 veh/h/lane | seed 91")
        axes[col].set_xlabel("Simulation time (s)")
    axes[0].set_ylabel("Position (m)")
    cax=fig.add_axes([.895,.22,.022,.59])
    fig.colorbar(mesh,cax=cax,ticks=[0,10,20,28.8,33.3],label="Mean measured speed (m/s)")
    fig.suptitle("Supplement: original actual lane index 2",y=.99,fontsize=13)
    fig.legend(handles=legend,loc="upper center",bbox_to_anchor=(.48,.93),ncol=2,frameon=False,fontsize=9)
    fig.text(.49,.025,"Same 25 m × 10 s bins and 0–33.3 m/s scale. Actual SUMO lane index is replayed from original lane midpoint events.\nEmpty bins are white; the lane ends at 1000 m. This fixed-seed subset does not replace the full five-seed effects.",ha="center",va="bottom",fontsize=8)
    save(fig,"seed91_2000_actual_lane2_speed_spacetime")
    (output/"runmap.json").write_text(json.dumps(runmap,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"source_sha256.json").write_text(json.dumps(sources,indent=2)+"\n",encoding="utf-8")
    (output/"binning_protocol.json").write_text(json.dumps(dict(seed=91,flows=[1500,1750,2000],policies=["NOA","D1"],window_s=[100,600],position_m=[0,1200],time_bin_s=10,position_bin_m=25,
        time_edges_s=TE.tolist(),position_edges_m=XE.tolist(),intervals="Left inclusive, right exclusive",statistic="sum of recorded actual-vehicle sample speeds / number of samples in each bin; no interpolation, no virtual vehicles, no frame or lane equalization",empty_bin="CSV mean blank and image white",color_scale_mps=[0,33.3],rows="Flow",columns="NOA / D1",axes="Time horizontally, road position vertically",supplement="Only the originally specified 2000/91 actual lane2; original lane midpoint flips, not intent",limitations="Fixed seed91 representative display, not five-seed primary effects. Both low-flow seed91 reversed main road DID contexts are retained. No new simulation, controller changes or parameter tuning."),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (output/"make_final91_spacetime_source.py").write_bytes(Path(__file__).read_bytes())
    (output/"visual_qa.json").write_text(json.dumps(dict(figures=figures,visual_review_pending=True,bin_rows_all_lanes=14400,bin_rows_lane2=4800,runmap_cases=6),indent=2)+"\n",encoding="utf-8")
    print(json.dumps(dict(output=str(output.resolve()),figures=figures)),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    run(parser.parse_args().output)
