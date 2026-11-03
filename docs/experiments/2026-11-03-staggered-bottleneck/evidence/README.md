# 114 例短批自包含紧凑证据

七个包完整覆盖原批计划，共 114 例；没有按表现、完成状态或 eligible 挑选案例。
所有包小于 20,000,000 字节，总计 **29,906,505 字节**。

| 原批 / 包 | 例数 | 字节 |
|---|---:|---:|
| `20261103_TM_load180_32.tar.gz` | 32 | 8,092,441 |
| `20261103_TM1250_180_8.tar.gz` | 8 | 1,337,987 |
| `20261103_A_screen180_20.tar.gz` | 20 | 5,262,557 |
| `20261103_D_screen180_10.tar.gz` | 10 | 2,697,876 |
| `20261103_C_screen180_10.tar.gz` | 10 | 2,687,968 |
| `20261103_ablation180_24.tar.gz` | 24 | 7,189,855 |
| `20261103_F_screen180_10.tar.gz` | 10 | 2,637,821 |

## 验证结果与读取入口

每包先对原 evidence 和 protocol/input/request/source 逐案复核，再逐成员 SHA/字节数建索引。
解包时与每个原文件逐字节比较；随后在临时目录用包内方法源码、新 Python `-I` 进程重新离线核验。
该进程禁止读取原仓库文件，所有包均记录原仓库读取尝试为零。没有执行 SUMO。

联合七包的独立离线核验为 `verification_all114.json`：

- 114/114 case 和协议对应核验通过，114 例记录为物理 safe，112 例完成。
- NH 的 2500 流量、seed1/4 两例保留原 `time_limit`、`all_completed=false`，不进入有效性能比较。
- 原始配对 94 项，92 项 eligible；这些数不是“所有策略通过”。
- 114 例正式完整 `[100,600)` 区域窗口均不足；正式窗指标保持 null。

`per_case.csv`、`paired.csv`、`summary.json` 仅由这次**归档中原件**的重新核验结果导出。
`case_locator` / `reference_evidence` / `candidate_evidence` 使用 `包名#包内相对evidence目录`。
原运行路径仍保留为 provenance，不需要访问该路径。`PUBLIC_MANIFEST.json` 给出所有公开文件 SHA 和大小；
每包另有 `.tar.manifest.json`、`.tar.verification.json`。

联合核验 operation：
`results/operations/20261103T035031682648Z_staggered-public114-offline-verify_75bb224a`，退出 0，41.610 s。
由该报告导出 CSV 的 operation：
`results/operations/20261103T035243354765Z_staggered-public114-tables_27ab0153`，退出 0。

## 包内结构与离线使用

- `index.json`：逐成员 SHA/字节数、原路径与包内相对 case/operation 映射。
- `stage/protocol.json` / `manifest.json`：原始字节，不改写原记录。
- `stage/runner.py` / `seal_case.py`：该批原冻结驱动。
- `stage/sources/*/`：各候选原冻结十文件及 freeze hash，六源也在逐例 compact 中保留原字节。
- `stage/cases/*/evidence/`：完整原 evidence 目录；case_record、worker/error log 同包保存。
- `stage/operations/*/`：必要仿真 operation 的 started/result/stdout/stderr；run_logged snapshot 按 SHA 去重保存。
- `repo/`：当前打包/核验工具、旧 compact/traffic 方法及导入所需最小依赖，均被成员索引固定。

从仓库工具验证一个或多个包：

```powershell
python -B docs/experiments/2026-11-03-staggered-bottleneck/tools/package_stage.py verify PACKAGE.tar.gz --report offline.json
```

没有原仓库时，可先把任意包解到新目录，然后从该目录运行其自带
`repo/docs/experiments/2026-11-03-staggered-bottleneck/tools/package_stage.py`，用同一 verify 命令指向下载的包。
验证不依赖原 tmp case、SUMO 或第三方 Python 库。本次验证环境为 Windows / Python 3.12。

## 证据范围

保存原 input/result/trips/源码字节、所有 active-id/0/1 帧、观测到的越线相邻括号，
以及原区域人数/低速人数/速度和账本。可离线复算这些字段对应的统计。
**完整 positions/events 不在本次七包中。** 它们只有原全文件 SHA/字节数；hash 本身不能在原件缺席时证明选出字段来源，也不能还原完整轨迹。
本包不能重新审计全时空车辆几何、连续碰撞/换道走廊、区域外速度、所有事件顺序或任意新轨迹指标。
碰撞/瞬移数是保存的原 SUMO 结果，不把紧凑核验称为独立全轨迹物理安全证明。

## 后续未封口 worker 失败兼容需求

本批 114 例均有已封口、可复核紧凑证据；后续 long600 尚未完成/未封口的案例不在这七包中。
worker 实际计算超时 `returncode=124`、原 result 仍 `starting` 的情况，不能称为物理 `time_limit`，也不证明不能排空。
下一版打包工具需原样保留该类 case_record/worker/operation 日志、原 input/result/source/trips（如存在）及 partial raw，
明确标记 unverified/ineligible/hash-only，不伪造最终统计、不过滤整批；必要时按失败 profile 的完整计划分包。
该兼容修改尚未进入本次已冻结包和打包工具 SHA，后续应另版实现，不重写这七包。
