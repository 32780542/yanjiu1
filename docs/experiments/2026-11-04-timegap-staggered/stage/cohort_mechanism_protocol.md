# 已成形45车群的局部控制机制探针

本探针在同一个1000 m缩道点比较三种已准备好的车群，检查交错结构是否提供即时可用的合流间隔，以及实际动作能否引导局部接续。它补充连续流中相位尚未充分成熟的观察，不用于修改C12、重选正式结果或估计全局容量。正式效率试验的出口仍为1200 m；这里统一延至3600 m，只为继续观察全部45辆车。

## 三组与初态

| 组 | 冻结规则与运行mode | 初态 |
|---|---|---|
| C12 / S | `20261104_C12_200/native_rules.py`，`transform` | 原`formed45_initial.json`，已有演示保留 |
| NOA / S | 同一C12冻结文件，`noa` | 与C12 / S逐车完全相同的原初态 |
| P12 / P | `20261104_P12_200/native_rules.py`，`transform` | 新并排初态，保持同车群中心 |

三组都是45车、三道各15车、速度28.8 m/s、同道纵距30 m、depart=0。NOA / S称为**已给定交错初态上的单车对照**：NOA自身状态始终0，不能据该初态称NOA形成了编队。它使用主NOA的50 m普通跟驰，不使用另一项远前车补充基线。

原交错输入为[formed45_initial.json](D:/yanjiu1/keyan1/docs/experiments/2026-11-03-staggered-bottleneck/formation_demo_D1/formed45_initial.json)：道0／2为`35+30i`，道1为`20+30i`，i=0…14。新[cohort_parallel45_initial.json](D:/yanjiu1/keyan1/docs/experiments/2026-11-04-timegap-staggered/stage/cohort_parallel45_initial.json)仅将原道1各车x加10 m，道0／2各车x减5 m，使所有道均为`30+30i`。IDs、车道、速度、出发时间和记录顺序均不变；IDs只用于关联输出。

两种初态的全车纵向均值都是240 m。它们仍保留实际几何差异：交错组的纵向范围为20–455 m，并排组为30–450 m；各车的起始位置也不同。P12 / P与C12 / S比较的是各自已成形结构下的完整控制行为，不把这项初态几何差异隐去。原同道30 m与h=.85时目标29.98 m相差.02 m，两组保持相同名义同道距。

本小探针使用200 m直接道路感知情景；车辆感知、1000 m瓶颈、执行物理和观察出口对三组相同。仅新增下面两次运行，不重跑已有C12 / S，不启动其他流量或种子。

## 入口与待运行命令

[geometry_trial.py](D:/yanjiu1/keyan1/docs/experiments/2026-11-04-timegap-staggered/geometry_trial.py)新增`--mode {noa,formation,transform}`和`--initial PATH`。未传时仍是原`transform`与原demo tape；协议会记录实际mode、initial及完整命令。道路构造和控制器源没有改动。

以下命令从`D:/yanjiu1/keyan1`运行；由root在当前单槽任务结束后执行。输出目录若已存在，应另取新目录保留旧尝试。

```powershell
$cohortDoc = 'D:/yanjiu1/keyan1/docs/experiments/2026-11-04-timegap-staggered'
$cohortCandidates = 'D:/yanjiu1/keyan1/tmp/staggered_bottleneck/candidates'
$cohortOriginal = 'D:/yanjiu1/keyan1/docs/experiments/2026-11-03-staggered-bottleneck/formation_demo_D1/formed45_initial.json'

python scripts/run_logged.py --label cohort_NOA_S --timeout 900 -- python "$cohortDoc/geometry_trial.py" --rules "$cohortCandidates/20261104_C12_200/native_rules.py" --output tmp/staggered_bottleneck/20261104_cohort_NOA_S_3600_r01 --demo formed45 --mode noa --initial $cohortOriginal --scenario lane_drop --exit-m 3600

python scripts/run_logged.py --label cohort_P12_P --timeout 900 -- python "$cohortDoc/geometry_trial.py" --rules "$cohortCandidates/20261104_P12_200/native_rules.py" --output tmp/staggered_bottleneck/20261104_cohort_P12_P_3600_r01 --demo formed45 --mode transform --initial "$cohortDoc/stage/cohort_parallel45_initial.json" --scenario lane_drop --exit-m 3600
```

## 按实际轨迹读取1000 m通过

只读工具为[cohort_probe.py](D:/yanjiu1/keyan1/docs/experiments/2026-11-04-timegap-staggered/tools/cohort_probe.py)。逐车在实际`positions.jsonl.gz`中找相邻实测位置`x_a<1000≤x_b`，用相应时间做线性内插：

\[
t_{1000}=t_a+(t_b-t_a)\frac{1000-x_a}{x_b-x_a}.
\]

每车自由行驶基准来自它自己的第一帧实际时间与位置，而非输入文件的depart或tripinfo：

\[
t_{free}=t_0+\frac{1000-x_0}{28.8},\qquad delay=t_{1000}-t_{free}.
\]

这样保留并排／交错的实际初始几何，同时不把每车起始位置差直接当作额外延误。提前通过导致的负延误照实保留。没有实际跨越括号的车保留缺失，不用出口时刻代替；全45车平均与最后通过仅在45车都有实际通过记录时给出。

汇总列出45车平均通过时刻、平均瓶颈延误、最后通过时刻、末道停止暴露和实际完成横移数；逐车表保留x0、t0、首帧速度、自由基准与实际通过时刻。末道停止暴露沿用既有描述口径：`900≤x<1000`、`|y−8.25|≤.15 m`、`v<.1 m/s`，按0.1 s实测帧计vehicle-s，不作为达标门。横移读取`trips.json`中的实际`lane_completion_events`，分别列完成位置不超过1000 m的次数与整个观察段的次数，不把请求次数算成完成次数。

待两组完成后运行：

```powershell
python "$cohortDoc/tools/cohort_probe.py" --case C12_S=tmp/staggered_bottleneck/20261104_C12_45_drop_long3600 --case NOA_S=tmp/staggered_bottleneck/20261104_cohort_NOA_S_3600_r01 --case P12_P=tmp/staggered_bottleneck/20261104_cohort_P12_P_3600_r01 --output docs/experiments/2026-11-04-timegap-staggered/stage/cohort_mechanism_report
```

输出为`summary.csv`、`per_vehicle.csv`和`summary.json`。C12 / S与NOA / S是同初态控制机制对照；P12 / P保留并排结构的初态差异。结果只解释本45车群在原瓶颈的行为，不替代正式连续流效率比较。

同一汇总还直接读取各run的`result.json`，保留`status`、`safe`、`all_completed`、`requested`、`completed`、`collisions`、`teleports`原字段。1000 m通过记录与全段运行结果同时展示，使通过瓶颈后出现的异常或未完成情况也可见；逐车内插与全45车均值的计算条件不变。

## 已做的入口验证

[test_cohort_mechanism.py](D:/yanjiu1/keyan1/docs/experiments/2026-11-04-timegap-staggered/stage/test_cohort_mechanism.py)的4项无SUMO测试已通过：旧默认不变；mode／initial覆盖写入协议并进入实际命令；并排输入逐车属性、同道距与中心守恒；人工三帧轨迹的通过内插、首实测帧自由基准、停止暴露与实际横移计数正确。覆盖参数测试先在旧入口上按预期失败。测试中的外部调用全部替换，没有运行Git或SUMO。
