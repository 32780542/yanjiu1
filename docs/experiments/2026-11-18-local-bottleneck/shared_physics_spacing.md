# 同道跟驰和接入间距

原 C12 进入接入阶段时，把本车用于同道跟驰的目标间距也抬高到至少 16 m。只在虚拟前车来自邻道时应用 16 m 下限，可以让低速同道队列沿固定时距恢复速度。实际前车按车头间距 `5.5+0.85v` 跟驰。横移目标、接入空位和安全检查采用原有间距与走廊。变动发生在原目标间距低于 16 m 时，即 `v<12.353 m/s`。单步速度指令改变量至多 0.63 m/s，实际速度还受公共与原生执行边界约束。 [纯间距冻结规则](../../../tmp/staggered_bottleneck/n18_spacing_c12_r01/src/transfer/noa/native_rules.py) · [共同物理参数](shared_physics.md)

## 开发种子 211、212

固定 2000 辆/h/道、600 s 请求时长、200 m 直接感知。检验在 C12 和 KeepFront 基础上分别修改同道间距，两处补丁逐字节相同。复合规则是在 KeepFront 上改间距。四个新增案例全部排空，零碰撞与瞬移。表中是请求至驶出的系统时间，单位秒。NOA 使用本轮共同物理最早冻结的规则。 [新增案例逐例](stage/shared_physics/spacing_factorial_comparison.json) · [KeepFront 对照](stage/shared_physics/candidate_comparison.json)

| 种子 | 原冻结 NOA | C12 | KeepFront | 纯间距规则 | 复合规则 |
|---:|---:|---:|---:|---:|---:|
| 211 | 90.419 | 93.431 | 94.748 | 73.511 | 76.181 |
| 212 | 102.936 | 101.338 | 111.060 | 75.672 | 80.993 |

相对 C12，纯间距规则少用 19.920 和 25.667 s。相对 KeepFront，复合规则少用 18.567 和 30.067 s。复合规则在两个种子都比纯间距规则耗时更长。纯间距对中道出流的影响如下，差值按纯间距减 C12。

| 种子 | 入口等待（s） | x=100–600 m 行程（s） | x=800–1100 m 行程（s） | x=1000 m 总出流（辆/h） | 末道停车（辆·s） | 燃油（g/km） |
|---:|---:|---:|---:|---:|---:|---:|
| 211 | −0.886 | −13.231 | +3.044 | +432.0 | +855.6 | −11.461 |
| 212 | −9.162 | −13.237 | +2.727 | +518.4 | +494.5 | −12.006 |

中道 x=1000 m 出流从 2498.4 和 2455.2 增至 2800.8 和 2786.4 辆/h。x=600–800 m 中道低速暴露从 4098.0 和 2836.1 降至 195.1 和 45.7 辆·s。按至少三车低于 5 m/s 连续三秒的定义，两个种子的持续低速都推迟。相对原冻结 NOA，纯间距减少瓶颈行程 6.708 和 9.115 s，减少终止道停车 5740.9 和 6849.4 辆·s。 [分道轨迹审计](stage/shared_physics/spacing_factorial_queue.json)

## 原冻结 NOA 的独立种子 213–215

复用上一节的纯间距冻结规则，同一共同物理、直接感知、路网和 600 s 需求。三个种子的六个案例均排空，累计完成 6010 个请求，零碰撞和瞬移。以下差值为纯间距规则减原冻结 NOA。 [独立种子双基准审计](stage/shared_physics/spacing_holdout_old_noa.json)

| 种子 | 原冻结 NOA（s） | 纯间距编队（s） | 系统时间差（s） | 燃油差（g/km） |
|---:|---:|---:|---:|---:|
| 213 | 102.199 | 74.572 | −27.627 | −12.256 |
| 214 | 109.365 | 69.341 | −40.024 | −18.196 |
| 215 | 97.873 | 81.403 | −16.470 | −8.887 |

三种子等权，系统时间少 28.040 s，其中行程少 27.946 s，入口等待少 0.094 s。上游 100–600 m 行程少 13.462 s，瓶颈 800–1100 m 行程少 7.412 s，x=1000 m 断面多通过 331.2 辆/h，末道停车少 6235.567 辆·s。燃油少 13.113 g/km。 [原冻结 NOA 批次](../../../tmp/staggered_bottleneck/n18_shared_hold_noa_r01/protocol.json) · [纯间距批次](../../../tmp/staggered_bottleneck/n18_shared_hold_spacing_r01/protocol.json) · [独立配对审计入口](tools/compare_shared_holdout.py)

## 复现与现场查看

从项目根目录执行以下 PowerShell 命令。两个入口用各自冻结源码生成同一 2000 辆/h/道、种子 213 的 600 s 请求带。均使用共同 IDM 参数并允许 1200 s 排空。去掉 `--gui` 可用同一无界面入口。窗口运行和正式计算都在独立目录保存输入、行程和逐步记录。 [纯间距原生入口](../../../tmp/staggered_bottleneck/n18_spacing_c12_r01/src/transfer/run_native_flow.py) · [VisibleGapNOA 原生入口](../../../tmp/staggered_bottleneck/n18_visible_gap_noa_r01/src/transfer/run_native_flow.py)

```powershell
python -B scripts/run_logged.py --label shared-spacing-view --timeout 1800 -- python -X utf8 -B tmp/staggered_bottleneck/n18_spacing_c12_r01/src/transfer/run_native_flow.py --mode transform --scenario lane_drop --flow 2000 --seed 213 --duration 600 --max-time 1200 --gui --output-base tmp/staggered_bottleneck/n18_view_spacing
python -B scripts/run_logged.py --label shared-NOA-view --timeout 1800 -- python -X utf8 -B tmp/staggered_bottleneck/n18_visible_gap_noa_r01/src/transfer/run_native_flow.py --mode noa --scenario lane_drop --flow 2000 --seed 213 --duration 600 --max-time 1200 --gui --output-base tmp/staggered_bottleneck/n18_view_noa
```
