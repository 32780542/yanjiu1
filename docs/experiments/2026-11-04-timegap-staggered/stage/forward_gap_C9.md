# C9：以前侧真实空间建立可接入关系

候选`20261104_forward_gap_C9_200/300/native_rules.py`，位于`tmp/staggered_bottleneck/candidates/`，各320行。仅替换C8的旧ending-cascade接收条件，其余规则不变。

已知道路的道0车，可把严格在前的道1 peer作为虚拟前驱，条件为：

1. peer前方道0最近真实车与peer已有至少D_entry(peer.speed)纵距。
2. 若没有观察到这辆前车，必须确认peer.x+D_entry仍位于本车前200 m车辆视野内，不能把视野外当空；300 m道路警示不扩大车辆视野。
3. peer进入道0的当前及1 s预测走廊仍满足原8 m前后间距。

这替代“peer前方另有ending同伴且其可入1”的两跳条件。前侧空间已经存在时，接收车按真实peer建立CTH，补足后侧时距；普通半D交错中peer前侧仅约半D，不会据此让整道均匀减速。未知路时仍只接收已经实际向0横移的peer，既有实际横移接收不改。

C8的单向2→1/1→0、真实F−D slot、半D几何误差进步、相位反馈和低速远孔修复均保留。没有邻车意图、人数或额外记忆。

## 行为红绿

`stage/test_forward_C9.py`新增3组，复用C8的10组，共13组。

- peer前侧已有32 m、后侧仅22 m且无ending同伴：已知路接收车可跟peer打开后侧；后侧3.5 m时仍拒绝。
- peer前侧只有半D时，原ending-cascade不能授权接收；低速以前侧16 m entry尺度判断。
- 未知路仍要求peer实际横移；无前车时，仅完整前侧D可见才确认空段。

冻结C8先有3个失败记录，C9两候选各13组通过。精确定义比较只有`_queue_front`改变；200/300只差ROAD_PREVIEW。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C9.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C9_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C9.py -v
```

未运行仿真。是否补齐完整45车交错及交通效果，由root独立复验；冻结后不修改同名源。
