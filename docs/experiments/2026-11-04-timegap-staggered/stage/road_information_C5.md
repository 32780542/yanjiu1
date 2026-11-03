# C5：道路知识与本帧物理接收分开

两组独立候选，各含200/300 m版本：

- `20261104_forward_gap_C5R_200/300/native_rules.py`：基于C2，各314行。
- `20261104_forward_gap_C5G_200/300/native_rules.py`：基于C4，各317行。

路径均在`tmp/staggered_bottleneck/candidates/`。R/G唯一差别是原C4半entry-D空位上界；同组200/300只差道路警示距离。旧源不改，不含C6几何进步判据。

## 核心规则

1. 只有本车`known`道路信息可把可用道数约束为2；未知时允许三道几何选位。
2. 删除`Memory.transforming`及其永久latch，不以新flag替代；自身记忆仅剩目标道与空位前车关联。
3. 未知道路的接收车，仅将**该peer自己正在实际向内横移**的严格前方实车作为虚拟前驱，并验证原8 m走廊；远处另一车的动作不授权静止peer。
4. 已知道路时可提前接收尚未横移的ending车，原两层公开几何接收保留；未知时不根据静止中道车和别的ending车推定未来动作。
5. 未知道路的lane2本车，若最近严格前方真实同道车实际向1道横移，可以跟随向1移动；只用现有`lane_target=1`保持本车动作，直到实际完成。
6. 已有本车pending/实际横移继续执行；已完成横移不转化为道路知识。接收产生的实际减速与占道变化可经真实跟驰/编队空位关系继续传播。
7. 临时接入由当前虚拟关系、已启动本车合流/横移决定；关系结束后恢复原CTH和三道选位。已知道路的几何约束仍由`known`持续施加。

这里传播的是物理动作及形成关系，不能由一次普通2→1运动证明道路缩减。用户情形1通过已观察编队前车的实际路径引导后车，不共享道路flag或邻车私有stage。

## 三组行为反例

`stage/test_road_information_C5.py`：

- 直路drop=None，1道接收车x880、实际2→1前车x895、真实1道前车x930：本帧可接收。前车已稳定1道后，本车x900、真实前车x929，2道有F=x939/R=x800的有效空位，必须重新具备使用2道的资格，不能被旧cue永久禁止。
- 未知道路，近处静止横向的2道车x895、远处另一2→1车x1020、本车x880及真实前车x930：远处动作不能把895车变成虚拟前驱。
- 已知drop1000、x900时禁止新进2道；未知时已有pending=1仍继续。另验证lane2跟随严格前方实际横移车向1移动，cue消失后仅用本车lane_target继续至完成。

冻结C2/C4先各出现前两组失败；C5R/G四份候选各3组通过。NOA、物理安全、h及公共相位定义保持；形成空位规则按各自R/G基底保留。

```powershell
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C5R_200\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_road_information_C5.py -v
```

将路径分别替换为C5R_300、C5G_200、C5G_300可运行相同测试。本子任务未运行仿真；直路三道占用、缩道收益及交错几何由root比较。冻结交付后不修改同名源。
