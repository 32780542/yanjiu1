# 规则试验的紧凑离线证据

[compact_evidence.py](compact_evidence.py) 仅用 Python 标准库，提供 `build` / `verify` 两个子命令。[audit_publication.py](audit_publication.py) 独立核对合并清单和分析 CSV。工具不调用 SUMO、项目控制器、完整层检测器、网络接口或 Git 写操作。

**范围：selected raw fields, full original positions local hash+rerunnable Git source。** 完整 positions/events 原件留在本地；压缩包只保留其全文件 SHA256、字节数和原目录。没有把选出的字段冒称为完整原始轨迹。没有原件时可复核包内数据与统计的一致性；全文件哈希本身不能证明每个选出字段确实来自该原件。`--check-originals` 可在原件仍可用时完整核验哈希，并重新提取所有选出字段进行逐字节比对。

每个 `bundle.tar.gz` 自包含：

- 原始 `input.json`、`result.json`、`trips.json`、`sumo_command.json` 和每例六份 source，均按原字节保存，SHA256 相同的文件只存一份。完整层检测器源码仅为原始源码证据，不参与任何计算。
- 所有原始物理帧的 `time_s`、`active_ids` 和按相同顺序排列的 0/1 flags；没有抽帧，也没有做状态1的额外门槛。
- 每辆车在 x=100/600/640/1100 米的首次实测等值点，或连续两帧的实际穿越样本 `[frame_index,time_s,x_m]`。车辆缺帧后不会跨缺口插值。每例 crossing 数据直接携带完整原 positions 文件 SHA256/字节数；原始穿越时间由这些样本线性插值得到，上游用100→600，瓶颈用640→1100。
- 原始清单和可选分析 CSV、`index.json`、当次完整校验脚本及范围说明。

校验器逐数据块重算 SHA256/字节数；从 trips 重算全程时间、系统时间、进入等待、燃油及完成数；从所有 flags 帧重算车辆秒、参与车辆秒、参与率、平均/峰值人数、连续1段数和时长；从实际穿越样本重算逐车分段时间、可用数和均值，再与每例原始 result、可选分析 CSV 比较。临时解包仅包含选出字段及小文件，核验完自动清理。输出报告还保留分段逐车值，可复核共同车辆集合的配对比较。

## 已冻结 screen48

[bundle.tar.gz](screen48/bundle.tar.gz)：**48 例，8,802,762 字节（8.40 MiB），300 个去重数据块**。SHA256：

`347fb732be6cc0d8c28056ddf4a0400ff209f039d83512d4ffc80e1027c97d02`

本包先由原32例和16例清单生成；完成后父任务的合并48例清单与完整分析 CSV 到达。保留包字节不变，另存[合并清单原字节](screen48/analysis_manifest.json)与[完整分析 CSV 原字节](screen48/analysis_per_case.csv)，经独立[出版审计](screen48/publication_audit.json)核对：48例记录逐项一致，**307,843 帧、31,956 次车辆运行、1,920 项分析数值/计数比较通过**。六源每例共288份逻辑文件去重为9份源码字节。完整原 positions 共363,351,149字节、events共2,057,116字节仅作哈希索引，未发布这些大原件。

[verification.json](screen48/verification.json) 是全部48例的离线重算结果；`bundle.json` 记录包和索引摘要。还已从压缩包提取其自带脚本，在 `python -I -B` 隔离模式下独立复核通过。随后对全部48例完成本地原件全文件哈希和所有选出字段的重新提取逐字节核验，见[原件核验摘要](screen48/originals_verification_summary.json)。TDD先确认8个缺实现失败，再有8个实际夹具测试通过，涵盖原字节/去重、错误哈希、无效flag、重新哈希后的flag与统计矛盾、坏穿越样本、trip/result矛盾和本地原件变化。运行证据索引见 [runs.json](runs.json)，不重复保存 runner 源码快照。

## extensions32 与完整 heldout 分组

以下新包均由同一已测试标准库工具构建，记录源码基线 `8ed11d90ac457269b2175e20aec5ba1bbba8a318`。每例四份原始 JSON、六份源码、全部 flags 帧、首次实际穿越样本以及完整 positions/events 的全文件哈希索引均保留。每份包都已从包内提取工具，以 `python -I -B` 完成独立离线复算；也已对全部本地原件完成哈希及选出字段逐字节重提取核验。

| 阶段 | 例数 | 包字节数 | SHA256 |
| --- | ---: | ---: | --- |
| [extensions32](extensions32/stage_summary.json) | 32 | 6,092,912 | `05e2e7c9840fb733bfe1a356daf0df35c54153b3264c1ff1857505f7094e24df` |
| [heldout base/noa](heldout_base_noa50_retry1/stage_summary.json) | 50 | 4,785,291 | `419a233f82e5f946375e8d0b28b7e2c0bdc872db3938011700cc6dd393f31e92` |
| [heldout base/transform](heldout_base_transform50/stage_summary.json) | 50 | 7,610,947 | `c88ae37b29164f81c4f767f1bba242431ed87ad839c3edbc08df0468e1e336cc` |
| [heldout T/transform](heldout_t_transform50/stage_summary.json) | 50 | 7,504,025 | `a631cdb154eadf3bbded0dc5f16b35aa4c0dc2da47d51a40e8ed120546006aa9` |

extensions32 使用 T2/noa、T2/transform、TM/transform、TR/transform 各8例。其分析表从原80行 CSV 按完整32例清单的 `run_dir` 精确选取，选择过程、原表 SHA256 及子表 SHA256 见 [selection_provenance.json](extensions32/selection_provenance.json)。独立[出版审计](extensions32/publication_audit.json)确认32例记录精确一致、205,202帧、21,304次车辆运行与1,280项分析数值/计数比较通过；未按状态、改善或缺失情况筛例。

每份 heldout 包覆盖整个指定 profile 的50例：流量500/750/1000/1250/1500、随机种子11–15、straight3/lane_drop 两场景。三个分组的最终分析 CSV 审计尚待父任务提供最终 CSV，现有包已经保留精确 profile 清单及原始证据；后续追加分析子表与独立出版审计即可，归档字节保持不变。尚未完整的 TM/noa、TM/transform 分组没有封存。

base/noa 首次构建在第14例后打开临时 `flags-current.jsonl` 时出现 Windows `OSError: [Errno 22] Invalid argument`；失败输出目录保留为空，日志保存在成功阶段的 `logs/` 中。相同工具和输入在新目录 `heldout_base_noa50_retry1` 成功，随后原件与离线校验均通过。失败和成功尝试均纳入 [runs.json](runs.json)，工具与模拟数据未改变。

## CLI

从仓库根目录运行；长命令按仓库要求加 `python -B scripts/run_logged.py --label <唯一名称> --timeout <秒> --`。`--output` 必须是新目录，失败或旧试验目录均不覆盖。

```text
python -B docs/experiments/2026-10-30-rule-trials/evidence/compact_evidence.py build --manifest <JSON清单> --output <新阶段目录> --analyzer-csv <可选per_case.csv> --source-git <基线Git提交>
python -B docs/experiments/2026-10-30-rule-trials/evidence/compact_evidence.py verify <新阶段目录>/bundle.tar.gz --report <校验报告.json>
python -B docs/experiments/2026-10-30-rule-trials/evidence/compact_evidence.py verify <新阶段目录>/bundle.tar.gz --check-originals --report <本地原件校验.json>
```

`--manifest` 和 `--analyzer-csv` 均可重复。后续 T2/TM/TR 或 heldout 使用新的阶段目录；不要重建 screen48。若一次清单约200例，建议父任务先按阶段/候选划分为各自的完整子清单，每包约50–100例，以便每份压缩档保持约20MB以内。划分后的所有子清单应与最终总清单逐项对齐；工具不会静默过滤或漏掉清单案例。

只拿到压缩包时，可提取包内 `compact_evidence.py` 后运行其 `verify`，不需要本项目、SUMO、第三方库或原始大轨迹。包内 README 给出了该入口。要核对后来合并的清单/CSV，运行 `audit_publication.py --bundle ... --manifest ... --analyzer-csv ... --verification ... --report ...`。
