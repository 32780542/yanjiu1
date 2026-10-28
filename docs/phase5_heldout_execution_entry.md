# 阶段 5 heldout 执行入口核对

2026-09-12 19:47 UTC，只读核对通过。现有 `variants/phase5_cost_holdout` 的 94 个源码文件、5 个输入文件仍等于初态冻结时的哈希；新隔离进程重新生成的六个完整 case 与 `heldout_frozen_cases.json` 逐字段相等，包括采样拒绝次数。40 个已加载项目模块均来自该副本，工作目录和五个临时目录变量均指向该副本。此次未启动车辆，也未读取 heldout 结果；检查时该副本尚无 `results/phase5/runs`。

证据：`tmp/phase5_comparison_design/heldout_entry_check_20260912T1946Z.json`；日志 `results/operations/20260912T194715672530Z_heldout_execution_entry_audit_026e75d9`。模块检查日志为 `20260912T194352756616Z_heldout_entry_module_origins_4a5f95f0`，独立初态生成日志为 `20260912T194451495347Z_heldout_entry_initial_generation_ad98cf33`。三个固定分析入口的哈希也已再次核对，均未改变。

## 执行顺序

1. 等 A、B1、B2 开发包及各自绑定重放全部完成，再用固定 `phase5_select_v1.py` 写正式选择记录。
2. 现有 A heldout 已完成准备。B 选定后，从选择记录 `input_bindings[selection.selected].run` 指向的已封存开发包复制到一个新副本，再执行现有 `tmp/phase5_prepare_holdout.py`。只准备选中的一个 B。
3. 对新 B 重做模块来源检查，并用固定分析脚本的 `generate-initials --variant <副本>` 只读生成 case 数据。取六个固定随机 case，要求其完整对象与已冻结六 case 相等；生成器同时构造的四个事件不进入本轮车辆命令。
4. A/B 各运行下表 13 个变体，分别保留新目录和外部日志。完成后分别用固定 `phase5_bind_v1.py` 调用标准整包重放，再用固定 `phase5_heldout_v1.py heldout-summary` 汇总。

准备 B 的实际工具是 `tmp/phase5_clone_workspace.py`，它直接接受已封存 run 和新目的目录；不需要另一个“clone_current”脚本。后续命令模板如下，尖括号参数须取自正式选择记录：

```powershell
$entryPython = 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe'
$entryWorkspace = 'D:/yanjiu1/keyan1'
& $entryPython -I -B -S "$entryWorkspace/tmp/phase5_clone_workspace.py" '<选中B的已封存开发run>' '<新Bheldout绝对目录>'
& $entryPython -I -B -S "$entryWorkspace/tmp/phase5_prepare_holdout.py" '<新Bheldout绝对目录>'
& $entryPython -I -B -S "$entryWorkspace/tmp/phase5_comparison_design/check_module_origins.py" '<新Bheldout绝对目录>' --output '<副本外的新来源审计JSON>'
```

## 确定的 13 个变体

普通组均为 45 s、控制/感知 0.1 s、积分 0.01 s，每组 450 个控制区间。顺序为每个 case 先 OFF 后 on，六 case 结束后运行半控制采样。

| 次序 | 变体 |
|---:|---|
| 1–2 | `random_3_seed6111_off`, `random_3_seed6111_on` |
| 3–4 | `random_3_seed6112_off`, `random_3_seed6112_on` |
| 5–6 | `random_6_seed6211_off`, `random_6_seed6211_on` |
| 7–8 | `random_6_seed6212_off`, `random_6_seed6212_on` |
| 9–10 | `random_12_seed6311_off`, `random_12_seed6311_on` |
| 11–12 | `random_12_seed6312_off`, `random_12_seed6312_on` |
| 13 | `random_3_seed6111_on_half_control`：控制/感知 0.05 s，共 900 区间，积分仍 0.01 s |

同一首 case 的固定已保存命令积分细化另写 `integration_half`，积分 0.005 s；它不是额外独立 seed。`case_index.expected_variants` 必须正好是上述 13 项。

## 已核对的车辆命令

`run.py` 的真实参数是重复六次 `--case`，不是 `--cases`、CSV 字符串或 `--case-names`。以下是选择完成后才执行的 A 模板；B 使用其新副本路径和独立 label。保留默认实时 SUMO 和默认采样即可得到 13 项。

```powershell
$entryPython = 'C:/Users/84335/AppData/Local/Programs/Python/Python312/python.exe'
$entryWorkspace = 'D:/yanjiu1/keyan1'
$heldoutVariant = "$entryWorkspace/variants/phase5_cost_holdout"
$heldoutCases = @(
  '--case', 'random_3_seed6111',
  '--case', 'random_3_seed6112',
  '--case', 'random_6_seed6211',
  '--case', 'random_6_seed6212',
  '--case', 'random_12_seed6311',
  '--case', 'random_12_seed6312'
)
& $entryPython -I -B -S "$entryWorkspace/scripts/run_logged.py" --label phase5_cost_heldout --timeout 7200 -- $entryPython -I -B -S "$heldoutVariant/run.py" phase5 @heldoutCases
```

共享外层 logger 的日志归入根工作区 `results/operations`；子 `run.py` 根据自身文件位置切换 cwd、模块路径和临时目录，科学结果归入对应副本。13 项的选择必须显式传入：生成器本身仍返回六随机加四事件，不传 `--case` 会运行 21 项。

heldout 只取原生成器的六个随机 case，因此顶层 `complete_suite=false` 是该子集的正常事实。用 13 项索引、保存区间、实时读回、独立重放和 `full_matrix_observed` 核对本轮完成度，不能把这个布尔值当作工具失败后反复重跑。

## 准备文件与结果门槛

- A 的六初态文件 SHA256 为 `f0055edf2b68485c435b6c25ca2cc2efe2da0f393370d41faf2d7952578d7133`；B 必须使用逐字段相等的完整六 case。
- 准备脚本只按已审计规则改种子条目的 value/rationale，并同步 CSV 同行 value/rationale/status=`predeclared_heldout_unvalidated`，再在原计划末尾追加固定“用户授权追加：独立验证子集”全文。固定 heldout 分析器已逐字校验这一合法追加，不要求删除它。准备脚本已完成所需 CSV 同步。
- 新 B 的源码/输入差异必须通过固定分析器的 `compare_seed_transition` 和 `compare_seed_inputs` 规则；原基础模型、控制、守卫、检测器与数字边界继续与选中的开发来源相等。原 A 已通过该检查，证据在 `results/phase5/comparison_20260912T192359379811Z_heldout_preparation_probe_ecaf03e8`。
- 普通车辆包外层 timeout 为预登记 7200 s；绑定重放可采用已确定的内部 6600 s、外层 7200 s。记录源 run 的明确路径，分析始终不使用 `latest`。硬杀后未封存的目录不能自动当作有效绑定。
- 运行、重放和比较工具完成不等于形成成功。六 seed 的失败和未开始项仍保留；连续指标的配对需要两侧完整 45 s 窗口，安全失败二值照实记录。只有两个完整 OFF 轨迹严格相等时，才合并基线。

当前等待项是正式 B 选择及其唯一 heldout 副本的上述准备/来源检查。此次没有克隆任何 B heldout，也没有打开其不存在的验证结果。
