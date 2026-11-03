# C4：形成空位还需保持当前前车后的半D错位

候选：`tmp/staggered_bottleneck/candidates/20261104_forward_gap_C4_200/native_rules.py`及`C4_300`，各318行，仅`ROAD_PREVIEW`不同。直接从C2新增三行几何判断，不包含C3瞬时横移门；C2/C3原件不改。

设目标道实际前车为P，当前本车道最近真实前车为F，接入pitch为d=max(D(v),16 m)。目标点仍为p=P.x−d，并保持目标道前后各d空间；C4同时要求

\[
p\le F.x-d/2.
\]

本车横移后，原当前前车F成为相邻道前车，交错结构本就需要至少半pitch纵距。若目标点将F逼近到只差1–2 m，则拒绝该形成空位，即使F刚完成横移、当前已回中。该关系直接由半D交错几何给出，没有冷却、完成期或新经验阈值。

约束放在真实空位函数内，所以新选择与尚未提交的准备计划都重新检查。已有pending/实际执行横移沿用C2，不撤销已发动作；必要2→1分支不调用此形成空位门，保持不变。实际同道前车不存在时不虚构一个F。NOA、物理安全、相位恢复、200 m闭孔和其余C2机制均不变。folding是否被误当永久道路知识，留给下一独立单元。

## 行为证据

`stage/test_forward_C4.py`新增3项行为，复用13项仍适用的前版测试，共16项。

- 前车刚回中但slot向前跳15.02 m：新选择和未提交旧计划均拒绝。冻结C2、C3各先出现两个失败子例。
- 目标仅修正0.10 m（巡航）或0.20 m（低速接入），且与当前F保留半d：均仍可横移，目标严格为P−d。低速正例明确处于接入状态，不把16 m当永久CTH。
- 已提交执行与必要2→1继续原动作。

旧四个slot正例因目标追近当前前车、不满足新半D关系，按规格迁移为上述有效正例；没有为旧期望加例外。两候选各16项通过。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C4.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C4_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C4.py -v
```

本子任务未运行仿真。由root验证重复横移、45车完整交错与交通表现；冻结交付后不修改同名源。
