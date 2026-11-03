# 最终91–95只读独立审计方法

在最终90例完整矩阵封口前准备；不参与控制、不调源、不启动仿真、不按部分结果改口径。原正式评价方法保持原样，本审计不导入原traffic evaluator，仅直接复算原件。

矩阵为3流量×5种子×2道路=30个共同道路输入；每组D1、NOA、S三例，共90。D1−NOA主30对、D1−S次30对；每一比较3流量×5种子=15个道路DID。DID定义`(D1_drop−ref_drop)−(D1_straight−ref_straight)`，小于0表示额外缩道节省，不相减百分比。

`audit_final91_independent.py`要求两个manifest恰为60和30、完整预定笛卡尔矩阵唯一、全部case_record seal verified后才创建结果目录。逐例核对：

- sealed evidence文件SHA、原positions/events SHA和字节数、compact index中原JSON及源码SHA；不触碰运行中gzip。
- D1规则2be...1f35a、S规则8bdaa...d12f及五份原非规则SHA逐字固定；实际source_sha256记录6个源码文件。仅使用每例冻结快照，不读取安装后的生产规则。
- 全部原input arrivals及原trips一一对应；同流量/种子两道路三方法的需求相同。核共同物理、速度/换道模式、600s需求/1200s排空上限、.1s步长。
- 原trips直接计算`mean(exit−request)`、`mean(exit−entry)`、`mean(entry−request)`、`sum(fuel_mg)/sum(distance_m)`，逐项核原result，并核系统=旅行+入口。保留不安全、不排空或不eligible计数，不换种子。
- 每例全部gate brackets插值与原vehicles ledger核对；启用默认raw重建时，每个双端点与原positions逐一核对，并重算[100,600)内800≤x<1000的车辆秒、速度积分、低速车辆秒，与region_steps独立账本比较。固定窗口不外推，终止道恰在1000的停留不被冒充800–1000内部暴露。
- 原轨迹formation states只允许0/1，NOA须全0；这些flag校验不替代真实交错几何。

最终逐例、逐种子配对、逐种子DID和流量等权均值分文件输出，记录来源SHA与源码快照。系统改善百分比逐种子按原参考均值归一，主结论同时保留绝对时间。原正式表若用S−D1方向，独立结果直接D1−S，不依赖符号转换代码；随后逐列对照原正式转换表并记录最大误差。

开发验证仅使用已封口D1开发例，完整原raw8616个gate端点、300394个0/1状态和region积分通过；没有读取最终部分性能作选择。完整最终结果就绪后运行此脚本一次，新目录保存。任何来源或原件矛盾均停止并记录，不将其当作效果阴性或静默删除。

区域和越线量只解释机制，不称饱和容量，不回流控制。真实几何、固定初态24/45恢复、普通交通效率和receiver后窗扰动各自报告；post5事件窗口可能重叠，不能相加为全路唯一暴露。
