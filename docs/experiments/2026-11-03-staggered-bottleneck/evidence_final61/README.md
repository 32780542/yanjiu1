# 锁定 S 的61–65独立确认：紧凑证据

8 个独立可核验包完整覆盖原 NOA80 + S80，160例，无重复、无遗漏。每方法按两种原道路，再按全部低流量<=1500（每道路25例）/全部高流量>=2000（每道路15例）分区；不依表现或完成结果选择。每包保留全批80例原 protocol/manifest 字节及明确分区映射。

| 包 | 例数 | 字节 |
|---|---:|---:|
| 20261103_final61_NOA80_lane_drop_high15.tar.gz | 15 | 11844081 |
| 20261103_final61_NOA80_lane_drop_low25.tar.gz | 25 | 8902731 |
| 20261103_final61_NOA80_straight3_high15.tar.gz | 15 | 9564299 |
| 20261103_final61_NOA80_straight3_low25.tar.gz | 25 | 7463708 |
| 20261103_final61_S80_lane_drop_high15.tar.gz | 15 | 12679786 |
| 20261103_final61_S80_lane_drop_low25.tar.gz | 25 | 10780846 |
| 20261103_final61_S80_straight3_high15.tar.gz | 15 | 11940455 |
| 20261103_final61_S80_straight3_low25.tar.gz | 25 | 10034033 |

归档总字节 83,209,939；每包严格小于20,000,000字节。

每个case保留原input/result/trips、六源和选定flags/gate brackets/region ledgers，以及case_record、worker和必要operation日志。大runner snapshot按批去重。index.json逐成员记录SHA/字节及原路径映射；工具先核对原件字节，再临时解包于独立Python -I中核验全部病例，禁止读取原仓库。

按仓库命令可复核任一包：`python -B tools/package_stage.py verify ARCHIVE --check-originals --report NEW.json`（从本实验目录运行）。离线使用时先安全解包，调用包内repo/docs/experiments/2026-11-03-staggered-bottleneck/tools/package_stage.py verify；完整依赖已内置，无须原tmpcase。原件路径是可选的额外字节比对条件；异机离线验证请省略--check-originals。

单包只有一个方法，原generic配对可能缺参考而不eligible；这不等同于正式配对失败。正式80配对、16组来自../final61_S160，并经../review_final61_S160.{json,md}逐原件复算。archive_report_crosscheck.json另将8包160个离线核验case的15指标和input/result/trips/源码/需求/参数SHA逐例绑定正式表，并重新核对80对的15指标差。

正式160例全部safe/drained、80对有效。2250/2500缩道系统时间改善15.8138%/14.3397%，均5/5种子；同种子道路额外节省8.929788/11.583358秒，均5/5。500缩道仅2/5改善，三例未改善完整保留。80/80配对燃油增加，16组均值也全部增加，不能省略代价。

完整positions/events已按原政策清理，原全文件仅留SHA/字节索引；这些包不能重建完整轨迹或追加未保留指标。现有选定字段可独立复核，交通成功不能单独证明完整形成几何。全矩阵、source lock、输入和失败资格均不由返回码替代。

S31/G0匹配归因及S-phase子系统关闭证明另见../matched_nonformation31_and_S170；不把原NOA总差当成单纯交错或P参数作用。

冻结package_stage/report_paired/旧road工具均未修改，旧证据包未移动或重写；此工具不仿真、不改生产或候选、不删除原件。
