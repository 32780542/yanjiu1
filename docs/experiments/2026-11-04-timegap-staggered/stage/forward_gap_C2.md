# C2：恢复完整相位反馈，统一真实空位接续

候选：`tmp/staggered_bottleneck/candidates/20261104_forward_gap_C2_200/native_rules.py`与`C2_300`，各315行；二者只差`ROAD_PREVIEW`。C旧版311行源保持原样。C2同时改以下两项，运行结果按C2整体解释。

## 1. 形成反馈恢复A语义

C直路24车也有相位残差，原因可由行为状态复现：在本车CTH已经平衡时，公共`_following`要求+0.15 m/s的相位修正，C最后的`min(speed, physical[0])`将其全部抹去。80 m前孔时，负相位又被外层反向门取消，正相位被同一个CTH请求上限裁掉。

C2在没有接入/准备横移时直接使用公共`_following`的速度、目标及参考，不再另加一次反向取消或以基础CTH请求整段限速。原函数内部的相位门与±0.4 m/s反馈全部保留。纯形成的CTH请求是跟踪反馈；真正的停止距离安全界仍由原`safe_speed/decide`最终限制。

200 m闭孔单独处理：只有50 m内没有真实前车、200 m内仍有真实前车时，以该车的整D跟驰请求替换自由巡航部分，同时保留公共形成函数原有的软相位增量。不会将新的远孔加速方向再用作相位取消门。NOA仍为原50 m普通跟驰。接入、可执行虚拟合流及准备/执行横移期间，保留C的实际前车CTH速度约束和原8 m走廊，不把这部分速度约束误用于普通形成。

## 2. 删除永久ending角色

删除`Memory.merged_from_ending`及对应永久禁止补位分支。道2上的本车先执行必要2→1；实际进入存续道后，与所有其他车辆使用同一真实编队空位规则。只有相邻道实际前车F后F−D_entry的位置前后均留D_entry、当前位置/1 s外推走廊成立，且满足原有位置进展条件时才准备/执行换道。

这不按前驱道色决定目的道，也不生成目标人数。C原45车t60的道1后端多为原ending车辆，原角色锁使其无法接续道0尾部真实空位；C2让这些实车在同一几何条件下具备接续资格。实际21/24人数本身不能构成完整45车交替链，但C2不把人数差作为控制输入。是否形成完整交错，仍以全部45车的实际位置、道色和间距判断。

接入尺度仍为D_entry=max(5.5+0.85v,16 m)，16只来自两段8 m横移走廊；局部接入结束后恢复原D。没有新增阈值、三车组、解锁门或邻车状态。`Memory`恢复为A的三个字段：本车目标道、空位前车关联及本车变换历史。

## 验证

`stage/test_forward_C2.py`包含5项新增行为测试，复用12项仍适用的C行为测试，共17项。旧“原ending永远不能再换道”测试由“真实空位成立才可接续、后界不足D仍拒绝”两项新规格替换，C原测试文件未改。

旧C上先观察到相位与永久角色的失败，再实现C2。新增测试涵盖20/28.8 m/s本地正相位、80 m远孔的正负相位，以及原ending车辆有/无真实后向D空间的动作。两候选均17项通过；15个公共定义（包含Memory、NOA、真实跟驰、原mutual相位及安全包装）与冻结A一致。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C2.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_forward_gap_C2_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_forward_C2.py -v
```

本子任务未运行仿真。C2的交通收益、额外横移次数和45车几何需root实测，候选不保证完整形成。冻结交付后不修改同名文件。
