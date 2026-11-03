# C3：当前真实前车横移时，不新发起形成绕行

候选：`tmp/staggered_bottleneck/candidates/20261104_forward_gap_C3_200/native_rules.py`及`C3_300`，各319行，仅`ROAD_PREVIEW`不同。C/C2原件不变。

C2实际重复横移证据见`C2_repeated_lane_changes.csv`：37次非必要重复中28次发生在当前真实CTH前车正在横移时，目标空位前车则稳定。C3只在**新选形成空位**入口增加一个判断：本车道最近真实前车若`abs(vy)>0.1 m/s`，或其位置距当前道中心超过0.15 m，则不另选相邻道形成空位，继续既有真实跟驰。前车实际完成横移后，每步重新检查原几何空位；不保留额外等待状态。

0.1/0.15沿用本控制器原有自身横移判断标准；不读前车pending或计划。已有合法本车空位计划和已执行横移继续按C2处理；必要2→1分支位于该门之前，不受影响。没有冷却、车名单、人数目标、完成期或新增记忆字段；相位反馈、200 m闭孔、虚拟接收和真实F−D空位规则均保持C2。

新增3项行为测试：横向速度/未回中心两类前车均阻止新绕行、前车回中后原空位重新可选；已有本车计划继续；必要2→1继续。先在冻结C2观察到第一项的两个子例失败，再实现C3。复用C2的17项行为，共20项，两候选均通过。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C3.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C3_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C3.py -v
```

本轮仅这一处方法更新。真实重复横移是否减少、两道交错是否保持，交由root复验；本子任务未运行仿真。冻结交付后不修改同名源。
