"""持续交通效率、燃油与Cai式时空速度图，300DPI PNG与SVG。"""

import argparse
import gzip
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def speed_grid(path):
    total, count = np.zeros((48,120)), np.zeros((48,120))
    with gzip.open(path,"rt",encoding="utf-8") as stream:
        for line in stream:
            frame = json.loads(line)
            t = frame["time_s"]
            if t >= 600:
                continue
            for x, _, speed, _ in frame["states"].values():
                if 0 <= x < 1200:
                    i, j = int(x/25), int(t/5)
                    total[i,j] += speed
                    count[i,j] += 1
    return np.divide(total,count,out=np.full_like(total,np.nan),where=count>0)


def plot(directory):
    directory = Path(directory)
    groups = json.loads((directory/"groups.json").read_text(encoding="utf-8"))
    rows = json.loads((directory/"results.json").read_text(encoding="utf-8"))
    sources = json.loads((directory/"verification.json").read_text(encoding="utf-8"))["case_sources"]
    plt.rcParams.update({"font.sans-serif":["Microsoft YaHei","SimHei","DejaVu Sans"],
        "font.size":10,"axes.unicode_minus":False,"svg.fonttype":"none"})
    colors = {False:"#3C5488",True:"#E64B35"}
    labels = {False:"常规跟驰",True:"纯规则编队"}
    flows = (1250,1500,1750,2000)
    lookup = {(r["flow_veh_h_lane"],r["formation"]):r for r in groups if r["kind"]=="demand"}
    def save(fig,name):
        for extension in ("png","svg"):
            path = directory/f"{name}.{extension}"
            fig.savefig(path,dpi=300,bbox_inches="tight",facecolor="white")
            if extension=="svg":
                path.write_text("\n".join(s.rstrip() for s in path.read_text(encoding="utf-8").splitlines())+"\n",encoding="utf-8")
        plt.close(fig)
    def curve(ax,metric,ylabel):
        for on in (False,True):
            means = np.array([lookup[(q,on)][metric+"_mean"] for q in flows],dtype=float)
            errors = np.array([lookup[(q,on)][metric+"_sd"] for q in flows],dtype=float)
            ax.plot(flows,means,color=colors[on],marker="o",linewidth=1.5,label=labels[on],markersize=4)
            measured = np.isfinite(means) & np.isfinite(errors)
            ax.errorbar(np.array(flows)[measured],means[measured],yerr=errors[measured],
                color=colors[on],fmt="none",capsize=3)
        ax.set_xlabel("每车道需求率（辆/小时）")
        ax.set_ylabel(ylabel)
        ax.set_xticks(flows)
        ax.grid(axis="y",alpha=.17)
        ax.spines[["top","right"]].set_visible(False)

    fig, axes = plt.subplots(1,3,figsize=(12,3.5))
    for ax,metric,label in zip(axes,("mean_system_time_s","mean_travel_time_s","exit_flow_veh_h"),
            ("平均系统时间（s，含入口等待）","平均在网行程时间（s）","0–600 s实际出口流量（辆/小时）")):
        curve(ax,metric,label)
    axes[0].legend(frameon=False)
    fig.suptitle("三车道持续交通效率（3个种子，均值±样本标准差）",y=1.03,fontsize=12)
    fig.tight_layout()
    save(fig,"traffic_efficiency")

    fig, axes = plt.subplots(1,2,figsize=(8.5,3.6))
    curve(axes[0],"fuel_g_per_km","距离归一化油耗（g/km）")
    curve(axes[1],"mean_fuel_rate_mg_s","每车平均燃油流率（mg/s）")
    axes[0].legend(frameon=False)
    fig.suptitle("HBEFA3油耗比较（相同请求、相同车辆与在网区间）",y=1.03,fontsize=11)
    fig.tight_layout()
    save(fig,"traffic_fuel")

    fig, axes = plt.subplots(2,4,figsize=(12.8,5.7),sharex=True,sharey=True,
                              layout="constrained")
    cmap = plt.get_cmap("turbo").copy()
    cmap.set_bad("white")
    for i,on in enumerate((False,True)):
        for j,q in enumerate(flows):
            row = next(r for r in rows if r["kind"]=="demand" and r["seed"]==1
                       and r["formation"]==on and r["flow_veh_h_lane"]==q)
            grid = speed_grid(Path(sources[row["name"]])/"positions.jsonl.gz")
            image = axes[i,j].imshow(grid,origin="lower",extent=(0,600,0,1200),
                aspect="auto",cmap=cmap,vmin=0,vmax=33.3,interpolation="none")
            axes[i,j].set_title(f"{q} 辆/小时/车道",fontsize=10)
            axes[i,j].set_xticks((0,200,400,600))
            if j==0:
                axes[i,j].set_ylabel(labels[on]+"\n纵向位置（m）")
            if i==1:
                axes[i,j].set_xlabel("时间（s）")
    fig.colorbar(image,ax=axes,label="速度（m/s）",shrink=.85,pad=.02)
    fig.suptitle("连续600 s时空速度图（seed 1；5 s×25 m网格，空单元留白）",fontsize=12)
    save(fig,"traffic_speed_maps")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    plot(parser.parse_args().directory)
