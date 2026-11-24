"""Render two observed chain24 frames. --from-run exports the exact plotting data."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path

from plot_trajectories import COLORS, lane_of, plt, reference_slots, representative, road_layout


def extract(run):
    (incoming, cut), (outgoing, length) = road_layout(run)
    trace = run / "positions.jsonl.gz"
    config = json.loads((run/"input.json").read_bytes())
    ids = {car["vehicle_id"] for car in config["arrivals"]}
    if len(ids) != 24:
        raise ValueError("Expected the 24-vehicle cohort")
    with gzip.open(trace, "rt") as stream:
        frames = [(obj["time_s"], obj["states"]) for obj in map(json.loads, stream)]
    shots = []
    for label, lanes, lo, hi in (("Upstream", incoming, 0, cut-config["case"]["road_observation_m"]),
                                  ("Downstream", outgoing, cut, cut+length)):
        at, states = representative(frames, ids, lanes, lo, hi)
        shots.append(dict(label=label, lanes=lanes, time_s=at, states=states))
    return dict(run=run.name, cut_m=cut, step_s=config["positions_step_s"],
                trace_sha256=hashlib.sha256(trace.read_bytes()).hexdigest(), frames=shots)


def render(data, output):
    plt.rcParams.update({"svg.fonttype":"none","svg.hashsalt":"chain24-snapshots","font.size":9,
                         "axes.spines.top":False,"axes.spines.right":False,"axes.edgecolor":"#8C969A"})
    fig, axes = plt.subplots(2,1,figsize=(7.9,4.4),sharex=True)
    fig.subplots_adjust(left=.075,right=.975,top=.80,bottom=.23,hspace=.66)
    extent = max(max(s[0] for s in f["states"].values())-min(s[0] for s in f["states"].values())
                 for f in data["frames"])
    for ax, frame in zip(axes,data["frames"]):
        states, lanes = frame["states"], frame["lanes"]
        front = max(s[0] for s in states.values())
        slots = reference_slots(states,lanes)
        ticks = [(i+.5)*3.3 for i in range(lanes)]
        for y in ticks:
            ax.axhline(y,color="#DFE4E7",lw=.7,zorder=0)
        ax.scatter(slots[:,0]-front,slots[:,1],marker="s",s=154,facecolor="none",edgecolor="#58636A",lw=.8)
        for key,(x,y,*_) in states.items():
            ax.scatter(x-front,y,s=99,color=COLORS[lane_of(y)])
            ax.text(x-front,y,key.removeprefix("initial_"),fontsize=6.3,ha="center",va="center",color="white")
        ax.set(xlim=(-extent-11,11),ylim=(-.1,lanes*3.3+.1),yticks=ticks,yticklabels=[f"L{i+1}" for i in range(lanes)])
        ax.set_title(f"{frame['label']}    ·    {frame['time_s']:.1f} s",loc="left",fontsize=10,fontweight="bold")
        ax.set_title(f"Front at {front:.0f} m",loc="right",fontsize=8)
    axes[-1].set_xlabel("Distance from cohort front  (m)")
    fig.suptitle("3 to 2 lanes    |    The same 24 vehicles",x=.075,y=.95,ha="left",fontsize=14,fontweight="bold")
    fig.text(.075,.082,"Numbers track measured vehicle fronts. Squares mark fitted staggered slots. Lane centers are 3.3 m apart.",fontsize=7.7)
    fig.text(.075,.035,f"SUMO   /   boundary {data['cut_m']:.0f} m   /   sample {data['step_s']:.1f} s   /   trace SHA-256 {data['trace_sha256'][:16]}",fontsize=7,color="#495761")
    fig.savefig(output,metadata={"Date":None})
    plt.close(fig)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data",type=Path)
    parser.add_argument("svg",type=Path)
    parser.add_argument("--from-run",type=Path)
    args=parser.parse_args()
    if args.from_run:
        args.data.write_text(json.dumps(extract(args.from_run),indent=2)+"\n",encoding="utf-8")
    render(json.loads(args.data.read_bytes()),args.svg)
