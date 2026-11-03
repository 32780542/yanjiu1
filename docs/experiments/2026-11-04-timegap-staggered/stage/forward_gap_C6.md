# C6：明确模式与形成几何进步

从冻结C5R独立建立`20261104_forward_gap_C6_200/300/native_rules.py`，位于`tmp/staggered_bottleneck/candidates/`。两份各320行，仅`ROAD_PREVIEW`不同；不含C3横移门或C4硬上界。

## 两项方法变化

**模式恢复。** 只有transform调用主动虚拟接收，以及根据未知路的实际前车2→1动作新发起跟随。formation使用真实前车、普通相位形成和编队空位，已知道路时仍执行必要2→1；不由邻车动作新启用变换接收。已有本车计划/pending动作仍继续。NOA和物理安全共用定义不改。C5 mode别名另存`C5_mode_alias.md`，不覆盖原件或既有transform结果。

**形成进步替换交通进度。** 设当前最近真实同道前车为F，entry pitch为d，目标道实际前车为P，slot仍取point=P.x−d，且目标道前后各保留d。若F存在，令q=F.x−d/2，只接受

\[
|point-q|\le|x_{ego}-q|.
\]

这表示横移之后，原前车成为相邻道前车，本车更接近半D交错位置。原“slot比当前CTH目标更前”的交通进度条件在此情况下删除；不把它与新条件叠加。无真实F时才保留原目标前移判据。

该检查位于`_vacancy`内，所有新slot及未实际提交的准备计划都逐帧重验；已pending/实际横移才绕过重新选择，必要2→1同样不受形成门限制。没有额外保持期、人数、成本或状态位，只沿用已有浮点容差。

## 行为证据

`stage/test_forward_C6.py`新增3组，复用C5道路信息3组，共6组：

- formation/transform在虚拟接收、未知guided上行为不同；formation已知路必要2→1仍保留。冻结C5R先有两个mode红例。
- 拒绝将半D位置误差增大的大绕行，同时允许ego1496、q1513、slot1519的真实改进（17→6 m）。后者越过q，故不能被C4瞬时硬上界取代。
- 接受slot909低于旧CTH目标910.02、但形成误差减小的情形，证明新判据替换了旧交通进度条件。
- 准备计划不能绕过新几何检查；已提交动作不撤销。该准备计划子例先红后绿。

两候选各6组通过。与C5R相比仅`_vacancy`、`_decide`改变，其余定义和常量不变；200/300只差道路警示距离。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C6.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C6_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C6.py -v
```

未运行仿真。几何保持、重复横移和交通代价由root复验；冻结交付后不修改同名源。
