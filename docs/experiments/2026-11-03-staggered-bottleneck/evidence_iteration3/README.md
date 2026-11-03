# 后续正常批与1800秒未封口试验：完整矩阵封存

18包覆盖16个完整原始批计划、186例：178例已封口并通过协议/紧凑证据核验，8例为真实计算超时，物理完成情况未知。没有按完成或表现筛选；旧M8/N8等已发布批不复制。M40/Q40按预定完整道路20例分包，其他本轮批保留完整原计划。

| 包 | 计划 | 已核验封口 | 未封口 | 字节 |
|---|---:|---:|---:|---:|
| 20261103_long1800_L4_unfinished.tar.gz | 4 | 2 | 2 | 7150172 |
| 20261103_long1800_M4_unfinished.tar.gz | 4 | 2 | 2 | 6977199 |
| 20261103_long1800_N4_unfinished.tar.gz | 4 | 2 | 2 | 7302081 |
| 20261103_long1800_NOA4.tar.gz | 4 | 4 | 0 | 9605992 |
| 20261103_long1800_Q4_unfinished.tar.gz | 4 | 2 | 2 | 6954007 |
| 20261103_long1800_S4.tar.gz | 4 | 4 | 0 | 10059923 |
| 20261103_LT_screen180_8.tar.gz | 8 | 8 | 0 | 2137552 |
| 20261103_matched_nonformation31_20.tar.gz | 20 | 20 | 0 | 16697975 |
| 20261103_MN_screen180_8.tar.gz | 8 | 8 | 0 | 2143094 |
| 20261103_Q_screen180_8.tar.gz | 8 | 8 | 0 | 2131776 |
| 20261103_S_screen180_8.tar.gz | 8 | 8 | 0 | 2134593 |
| 20261103_validation31_LT10.tar.gz | 10 | 10 | 0 | 8904713 |
| 20261103_validation31_M40_lane_drop_20.tar.gz | 20 | 20 | 0 | 15196086 |
| 20261103_validation31_M40_straight3_20.tar.gz | 20 | 20 | 0 | 14175741 |
| 20261103_validation31_N10.tar.gz | 10 | 10 | 0 | 8996579 |
| 20261103_validation31_Q40_lane_drop_20.tar.gz | 20 | 20 | 0 | 15162558 |
| 20261103_validation31_Q40_straight3_20.tar.gz | 20 | 20 | 0 | 14130781 |
| 20261103_validation31_S10.tar.gz | 10 | 10 | 0 | 8826236 |

全部包共158,687,058字节；最大16,697,975字节，均严格小于20,000,000。

正常案例保留原input/result/trips、六源、全部选定flags/gate brackets/region ledgers、case_record/worker与必要run_logged日志；批冻结runner/seal及旧方法依赖一并内置。每包逐成员SHA/字节索引，先对原件字节，再临时解包由独立Python -I核验全部病例，禁止读取原仓库。单方法包generic配对缺reference不代表物理/协议失败；正式对照表另行引用。

L/M/N/Q的每个1800秒4例包保留原protocol/manifest全字节，以及两例成功的完整evidence、两例未封口的全部原有小文件和操作日志；没有把成功子集当完整物理对照。8个未封口案例均为2500、种子41/42缩道，原result仍starting，实际outer/case returncode均124；child_returncode和实际耗时3000.06–3000.11秒见索引及原操作日志。trips不存在时保持不存在，不补造字段或性能。

8例physical completion=undetermined，eligible=false；计算超时不能证明物理上限达到或道路不能排空。root报告约15:20对当时活动的M/Q进程临时设置BelowNormal，L保持正常priority；N优先级不推断。物理输入不变，**不得比较wall-clock耗时作为方法性能**。

原位置仍有32个大raw文件、1,291,519,466字节，全部重新核对存在/字节/SHA；其中未封口8例对应16个、813,903,124字节。这里只保存索引，不上传大raw，不删除原件，不声称能从云端包重建/解析partial raw。其余正常案例已清理的完整轨迹也不能由哈希重建。

现有选定字段可离线复核既定指标，不能替代完整轨迹、独立形成几何或新增未保留指标。包内工具复核入口为repo/docs/experiments/2026-11-03-staggered-bottleneck/tools/package_stage.py verify ARCHIVE --report NEW.json，异机离线省略--check-originals；在原机可加该参数额外核对原件。

S对NOA60的同输入敏感性见../S_NOA60_sensitivity，原件独立复算10对全部有效，采用实际NOA60分母，不机械减去另一表改善率。M/Q未采用结果及所有L/M/N/Q超时均保留。正式final61数值和旧封包不改。
