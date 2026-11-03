# joint03：纵向跟驰与有界错位修正同时作用

独立候选`20261104_C8_joint03_200/300/native_rules.py`位于`tmp/staggered_bottleneck/candidates/`，各315行。从C8_state父本只删除`_following`内两行“相位与真实CTH本步调速方向相反就归零”的判断，生产不动。

比例增益仍为0.3，没有采用phase06增益，也没有新增参数。相位中间速度仍限±2 m/s，松弛系数0.2及共用`safe_speed/decide`物理上限不变；CTH、几何、接收、单向横移和状态标记均沿用父本。

变化只在存在50 m内真实前车的形成分支：CTH纵向调速与有界相位修正同时相加，正负方向不再互斥。没有此前车的分支原来不经过该门，计算保持不变。这是用于观察几何调整过程的独立假设，不声明更稳定或交通更优。

## 三项行为红绿

`stage/test_joint03.py`先在C8_state父本出现两项失败：

1. 本车20 m/s、前车30 m处22 m/s时，CTH请求20.85；负相位应修正到20.73，父本归零后仍为20.85。
2. 本车制动时，正相位应使原始形成请求增加0.12；父本取消了它。joint03允许该项，同时实际`decide`仍被共用停止距离上限裁剪。
3. 零错位平衡和NOA受阻超车保持原结果。

两个新候选各3项通过。精确文本比较确认只删除上述两行，200/300只差ROAD_PREVIEW。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_joint03.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_C8_joint03_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_joint03.py -v
```

本子任务未运行仿真/Git。root按开发短筛决定是否继续，冻结后不修改同名源。
