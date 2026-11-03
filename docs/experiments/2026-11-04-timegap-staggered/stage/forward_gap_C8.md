# C8：纵向形成，单向收缩重排

候选`20261104_forward_gap_C8_200/300/native_rules.py`，位于`tmp/staggered_bottleneck/candidates/`，各317行。独立从C7只收窄一般补位的用途和方向，旧源不改。

## 使用范围与方向

普通三道formation只做真实CTH、200 m闭孔及原mutual软相位，不为形成一般横移。已知道路上的必要2→1仍保留。

一般横向重排只在transform、本车处于道1，且本车known道路、实际看见向内横移，或已有自身计划时发生；目标固定为道0。道0没有0→1回流，道2先沿用C7的必要/实际前驱跟随2→1，进入道1后可按同一真实slot再去0，不保留原ending角色。

目标仍是实际前车P后P−D_entry的位置，保留C7目标道前后D、当前真实同道前车半D误差不增、当前/外推8 m走廊、低速entry尺度及远孔松弛基准修复。已有本车已提交动作继续，不增加冷却、人数、名单或私有阶段。触发动作不成为永久道路知识。

由C8从空自身记忆产生的新横移动作只有2→1和1→0。实际完成后道序严格递减，因此每车最多初始道序（≤2）次实际横移；同一次执行的持续请求不计作新完成。NoA基线保持原有普通行为。

## 定向红绿测试

`stage/test_forward_C8.py`新增3组：

1. 有真实slot时，普通formation和没有触发的transform都不绕行。
2. 道0不因临时slot回到1。
3. known、实际向内运动或已有本车计划均可触发合法1→0；原ending实际2→1后也能再1→0。

冻结C7先出现前两组共3个失败子例，第三组保持绿。复用C7仍适用的7组，总计10组；两候选均通过。旧“未知路时可以一般补位进2道”的动作期望被单向重排规格替换，不将政策禁止回流误记成道路知识latch。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C8.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C8_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C8.py -v
```

源码仅`_decide`的一般补位范围/方向改变，其余定义与C7相同；200/300只差ROAD_PREVIEW。本子任务未运行仿真，交错形成与交通效果由root独立筛选；冻结后不修改同名源。
