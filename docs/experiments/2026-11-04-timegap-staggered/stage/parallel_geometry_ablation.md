# parallel：无交错的并行编队消融

这是用于检验交错几何效率贡献的独立对照，不作为用户最终目标方法。候选`20261104_parallel_200/300/native_rules.py`位于`tmp/staggered_bottleneck/candidates/`，各317行；从选定的C8主法派生，C8原件不改。

只改变两行几何定义：

- `_phase`对所有车道返回0，各道期望同x并排。
- `_vacancy`中相邻道目标由q=F.x−D_entry/2改为q=F.x，候选按零错位位置误差判断。

其他D(v)、接收提案、单向动作、NOA、物理安全、entry尺度、速度及数值参数全部沿用C8。入口D_entry保持max(D(v),16 m)，不另调参数。200/300只差原道路警示距离。

`stage/test_parallel_ablation.py`两项行为：同x跨道的相位误差为0；候选按q=当前真实前车x的零错位几何进步选择。先在C8看到两项均失败，再在parallel两源均通过；精确文本比较确认只有上述两行改变。

```powershell
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_parallel_ablation.py -v
$env:FORWARD_RULES='D:\yanjiu1\keyan1\tmp\staggered_bottleneck\candidates\20261104_parallel_300\native_rules.py'
python -m unittest discover -s docs/experiments/2026-11-04-timegap-staggered/stage -p test_parallel_ablation.py -v
```

本子任务未运行仿真或Git。冻结后不修改同名源，由root作为几何消融独立实测。
