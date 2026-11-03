# 完整车群轨迹

这里保存四个固定车群试验的完整输入、冻结源码、SUMO结果、positions、events及diagnostic，不采用连续大流量试验的紧凑裁剪。四包共17,096,725字节；压缩后每个成员已与原文件逐字节核对。[index.json](index.json)列出实际文件数与包大小。

| 包 | 初态和目的 | 结果入口 |
| --- | --- | --- |
| 20261104_C12_24_straight_geometry.tar.gz | 24辆不整齐初态，在三道直路形成 | [形成与成熟度](../../stage/C12_geometry_and_maturity.md) |
| 20261104_C12_45_drop_long3600.tar.gz | 45辆交错初态，1000米处三道收为两道，出口3600米 | [恢复过程](../../figures/cohort45/caption.md)、[实际运动引导](../../stage/C12_motion_guidance.md) |
| 20261104_cohort_NOA_S_3600_r01.tar.gz | 同一45辆交错初态，单车NOA，状态始终0 | [同初态探针](../../stage/cohort_mechanism_report/report.md) |
| 20261104_cohort_P12_P_3600_r01.tar.gz | 同中心45辆并排初态，匹配并排控制 | [几何探针](../../stage/cohort_mechanism_report/report.md) |

解压任一包后可直接读取相应run的result.json、输入及逐步轨迹。各包保存实际目录结构，原绝对路径只是运行来源记录。几何观察出口延长用于在所有车辆仍在场时检查队形恢复；正式交通比较仍采用1200米道路，时间结果分别报告。
