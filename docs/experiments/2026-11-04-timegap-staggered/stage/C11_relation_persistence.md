# C11/P11：普通主前驱的局部建立与持续维护

从C8_relations与parallel_relations独立派生四源，生产不动：

- `20261104_C11_200/300/native_rules.py`：交错几何。
- `20261104_P11_200/300/native_rules.py`：并排几何。

路径均在`tmp/staggered_bottleneck/candidates/`，各317行。增益0.3、原始相位限幅±2、CF反向优先门均保留。

## 两处关系规则

普通跟驰仍由现有50 m范围建立。50–200 m主动闭孔只针对本车已建立的主前驱：当前200 m最近真实前车的reference必须等于`memory.front`。fresh车辆不会自动追赶80/150 m外的陌生前车；已经在40 m建立的同一关系拉开到80 m后，仍可维护CTH与原相位反馈。

返回自身记忆时，`front`优先保存本车slot anchor；没有anchor则保存本帧选中的reference。沿用原字段，不新增flag。前驱离开视野、落到本车后方或不再被选择时，该关系随当前reference释放；新前车进入50 m时可重新建立。

感知、公共safe_speed仍为200 m。真实接入、虚拟CTH和本车pending目标道引用仍沿用原200 m分支，保持严格前向。收缩、NOA、相位、时距、物理参数和已有关系状态合同不改。

这是形成关系选择与持续性规则，不按道路位置激活，也没有队伍规模上限；不预先给出成熟速度或交通收益结论。

## 行为红绿

`stage/test_C11_relations.py`四组：

1. fresh80 m不自动加速入队，也不保存尚未建立的前驱。
2. 40 m关系保存后，拉开80 m仍按同一CTH闭孔并保留关联。
3. 换成未建立的远前车、前驱失见或落后时释放；新的40 m前车可重新建立。
4. 80 m虚拟接入保持原行为，slot anchor及pending不被普通前驱字段覆盖，目标道80 m引用继续。

两个父本先各出现4个失败记录；四份新源各4组通过。精确文本比较确认只增加远孔前驱匹配条件、改变同一Memory.front的返回来源。交错/并排仍仅两行几何差，同组200/300只差ROAD_PREVIEW。

```powershell
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_C11_200\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_C11_relations.py -v
```

替换为C11_300、P11_200或P11_300可运行相同测试。未运行仿真/Git；冻结后同名源不再改，由root完成短筛及最终冻结。
