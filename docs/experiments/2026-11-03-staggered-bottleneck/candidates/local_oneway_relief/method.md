# F：本车单向疏解未来负荷

在固定E（direct_gap，SHA256 `04d739353f73ba2b309d18047baacb2abf6e362356f6b1b25865a1c62cf60274`）上，只给 `_decide` 增10行：准备区transform的中道本车在自己[-60,+30]实车窗口计算 `P=n1+n2−n0`；P≥2且本车左道clear时立即1→0，否则保持E的following，不预先追gap、不减速开隙。准备区存续道直接返回，阻止自由fill把左道车辆搬回中道；必要2→1和已有横移优先保留。

规则无新阈值、Memory或邻车flags。既有同道CTH、无前车相位、安全执行和gap速度法均不变；未叠加A/C/D。F不是MOBIL移植，8m可行不等于目标道后车没有额外制动，后者需由交通结果检验。

构建源454行，SHA256 `f3a7acba6a812196d357cdccefb707ffec88df1e744d6f4dfc77ce26d916464d`。生产和E字节未改；build从固定SHA校验的E重建，若E缺失才调用其既有build。

冻结E的12项测试出现4个预期断言失败，operation `20261103T032745401825Z_local-oneway-relief-red_b897549c`；F通过12/12，operation `20261103T032820832559Z_local-oneway-relief-green_1086b6cb`，含600个随机未受影响分支与E等价检查。构建operation `20261103T032813646744Z_local-oneway-relief-build_16faeda9`退出0。没有在本子任务中运行交通仿真。

完整机制反例、必要条件、原文证据与局限见[method_next.md](../../methods/method_next.md)。
