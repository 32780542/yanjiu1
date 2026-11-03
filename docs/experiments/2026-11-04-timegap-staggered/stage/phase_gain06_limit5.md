# 相位增益0.6、原始限幅5：独立幅值参数试验

从完整关系出口的C8_relations与parallel_relations派生四份候选，生产保持原样：

- `20261104_C8_phase06_limit5_200/300/native_rules.py`
- `20261104_parallel_phase06_limit5_200/300/native_rules.py`

均位于`tmp/staggered_bottleneck/candidates/`，各318行。两种几何分别保留交错或并排目标；相位增益为PHASE_GAIN=0.6，原始相位速度限幅由±2改为±5。

## 参数含义

松弛系数仍为0.2，所以有界软速度修正预算由约±0.4增至±1 m/s；小误差处响应与已测gain06相同。真实CTH和`_request`的POSITION_GAIN仍为0.3，原CF反向优先门保留，共用停止距离安全上限、时距、entry尺度及全部横移动作不变。

这项试验只检验几何调整过程是否受到原±0.4 m/s预算限制，不声称更稳定或交通更优。它不叠加joint03，也不引入接收、头车或完成期新规则。

完整关系出口统一按`linked or reference is not None`报告状态1。此前phase06/joint03父本的状态报告作为开发历史保留；不按flag比例选择参数。

## 三项行为验证

`stage/test_phase_gain06_limit5.py`：

1. 小错位仍与gain06一致，单边误差±2 m对应本步±0.12 m/s修正。
2. 较大错位的预算提高：例中±10 m给出±0.6、±30 m给出±1 m/s，绝对值不超过1。
3. NOA原超车/跟驰不变；制动时原CF方向门仍有效，实际输出仍由相同safe cap裁剪。

旧gain06交错/并排源先各出现四个较大幅值失败子例，小错位与NOA/安全项保持绿。四个新候选各3项通过。精确文本比较确认从各自relations父本只增加PHASE_GAIN并替换相位增益/限幅表达式；同几何200/300只差ROAD_PREVIEW，两种几何仍仅差相位定义和q目标两行。

```powershell
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_C8_phase06_limit5_200\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_phase_gain06_limit5.py -v
```

替换为其余三份路径可运行相同测试。本子任务未运行仿真/Git。四源冻结后交由root短筛，按本轮截止时间停止调参并据实际结果冻结正式方案；同名候选不再修改。
