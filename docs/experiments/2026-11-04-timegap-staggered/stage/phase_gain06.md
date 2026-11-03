# 跨道相位增益0.6：独立参数试验

从新状态合同的C8S与P8S各派生200/300 m候选，生产源保持原样：

- `20261104_C8_phase06_200/300/native_rules.py`
- `20261104_parallel_phase06_200/300/native_rules.py`

均位于`tmp/staggered_bottleneck/candidates/`，各318行。它们保留各自原有交错/并排几何。

## 唯一参数变化

增加独立常量`PHASE_GAIN=.6`，仅在`_following`的跨道误差反馈中代替原来的0.3：

\[
phase\_speed=\operatorname{clip}(0.6\,error,-2,2).
\]

真实CTH及`_request`的`POSITION_GAIN`仍为0.3。无本车道前车时，软位置目标仍用`phase_speed/POSITION_GAIN`转换，使放大的相位修正不会被换用0.6作除数抵销。相位中间速度限幅仍为±2 m/s，松弛系数仍为0.2；其余方向判断、安全限制、D(v)、entry-D和横移规则不变。状态1沿用新的已有关系合同。

参数假设仅为：提高未限幅小误差的跨道反馈强度，可能缩短几何调整过程。它不改变目标几何，实际24/45及流量试验将判断调整过程和交通表现，不据此声明稳定性或收益。

## 三项行为验证

`stage/test_phase_gain06.py`适用于两种几何：

1. 单条边小相位误差±2 m时，未被其他条件屏蔽的本步速度修正从±0.06增至±0.12 m/s。
2. 零错位和真实CTH平衡速度保持不变。
3. 大错位仍限为±2的相位中间速度，最终软修正仍至多约±0.4 m/s；NOA的受阻超车与真实CTH请求保持原值。

旧C8S、P8S先各出现小误差两个失败子例，零误差及限幅/NOA项保持绿；四个新候选各3项全部通过。精确文本比较确认每份只新增PHASE_GAIN并替换相位乘数，未改变`_request`或物理参数。同几何200/300只差ROAD_PREVIEW；交错/并排之间仍仅差两行目标几何。

```powershell
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_C8_phase06_200\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_phase_gain06.py -v
```

替换为其余三份源路径可运行相同测试。本子任务未运行仿真/Git，冻结后不修改同名源。
