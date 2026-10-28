# R5 独立整合工具审查

2026-09-13。作者为 root，审查者为 formation_control。只读审查 [tmp/phase5_integrate_r5.py](D:/yanjiu1/keyan1/tmp/phase5_integrate_r5.py)、[作者测试](D:/yanjiu1/keyan1/tmp/test_phase5_integrate_r5.py) 和其调用的克隆/选择来源接口；没有调用 main，没有创建最终副本，没有读取 heldout 性能。

**当前工具审查通过，无剩余 P1/P2。** 被审版本 SHA256 `aa1db509e921bb8e1b440e6392e8e459d037fae5aefd2d434ad58bd9f663ab84`。这只允许在控制、记录独立审查及实际来源不变的前提下执行整合；不等同实际整合成功或车辆实验通过。

## 发现及闭环

初读版本有三项来源校验缺口，已通知作者并修复。旧发现留在本报告，不能用后来通过抹除：

1. registry 只检查 A 字节前缀和非空追加，任意附加 CSV 行也能通过。现 [validate_registry_append](D:/yanjiu1/keyan1/tmp/phase5_integrate_r5.py:24) 要求七个唯一名称，逐行绑定值、单位、状态、rationale、实际 config 来源行和 SHA；额外列、重复/缺失行也拒绝。此检查促成仅新 common 七行 source/page_or_url 元数据纠正，参数没有变化。
2. 整合后只核对未改 parent 文件，未逐项核对实际复制的 changed 文件，也未验证最终源文件全集。现 [validate_overlay_files](D:/yanjiu1/keyan1/tmp/phase5_integrate_r5.py:63) 要求 exact file set 为 parent∪changed，每一项为预期 parent/common 字节，formation 为实际 B1 最小补丁字节。
3. 选择验证器检查运行包 input_snapshot 和当前代码，但不检查当前工作区五输入。现 [validate_input_maps](D:/yanjiu1/keyan1/tmp/phase5_integrate_r5.py:55) 补齐 parent 五输入与其封存运行一致；common 除合法 registry 追加外四输入与 A 一致。整合前后重复核验两个源工作区五输入、设计文档及其目标副本，目标 registry 与每个继承输入也逐字节/哈希核验。

作者先保留缺 helper 的 RED；最初新 validator 正确拒绝旧来源不一致的七行。来源修正后，本次独立重跑作者三项测试通过：`results/operations/20260912T213657030223Z_phase5_r5_integration_independent_tests_1ce04d4a`，退出 0。测试涵盖 registry 重复/缺行与来源/值篡改、parent/common 输入偏移、复制内容与额外/缺失源文件、A formation 错误替代 B formation。

## 关键语义核对

工具通过正式冻结开发选择器验证指定 selection 包，只接受 `B1_same_front`；不重新选择方法。parent 当前源文件全集须与其已封存运行一致。common 相对冻结 A 只能改明确 17 个白名单文件，不允许删去 A 文件；本工具不替代这些文件各自的独立代码审查。

[formation 补丁](D:/yanjiu1/keyan1/tmp/phase5_integrate_r5.py:107) 从 A→common 提取唯一一行 insert，要求插入位置恰在唯一 `risk =` 行后，并验证它能精确重建 common；随后把这一行插入 B1 相同唯一锚点。末尾反向去除插入后必须与完整 B1 文本相同。B1 的 `noa/formation_rules.py` 和 `configs/phase5.json` 最终哈希还单独与 parent 相等。因此没有把 common 的 A 参考选择整文件覆盖到 B1。

最终目标存在时 main 在复制之前拒绝。被调用 [phase5_clone_workspace.py](D:/yanjiu1/keyan1/tmp/phase5_clone_workspace.py:30) 再次拒绝既有目标，并验证解析后的目标位于 workspace/variants 内、每个 snapshot 成员路径不越界；失败保留不完整新目录，不递归删除或自动覆盖重试。复制前后核源字节，整合结束再核全部源集和五输入。复制所需设计列表包括控制与记录独立审查报告，缺失就拒绝执行。

## 独立探针及限制

[探针](D:/yanjiu1/keyan1/tmp/phase5_r5_development/probe_integration_review.py) 只导入定义，不执行 main。它对 registry 十个字段各改一个值，十次都被拒绝；以当前实际 parent/common 五输入验证正例；实读 A/common/B1 的 formation，证明准确去掉唯一插入即完整 B1，而最终文本确实不同于 common A 文本。探针还在前后核对工具 SHA，未更改任何生产、配置、冻结输入或结果。

日志 `results/operations/20260912T213917759063Z_phase5_r5_integration_independent_probe_6d8c2159` 退出 0；独立产物 [result.json](D:/yanjiu1/keyan1/results/phase5/r5_integration_review_20260912T213917954593Z_d26ebf37/result.json) 保存脚本、被审工具和作者测试快照及 hashes.json。审查时最终目标不存在。B1 formation SHA `179a118d43ed66c1ca50ae39718fd2f6f5bc95ec945f7b6ee493fa24f9146ece`，common formation SHA `ac0165d2cb5d5ddc80e8164994e390e07a589cd37ec92c1f8ae3f7d37fd8fae7`；修正 registry SHA `5403de7ecc24f2c518e87ac1c019e4b9b90e89a1949caa72fd24648a834c900d`。

未运行 main，因而实际复制、实际新目录来源报告与随后新副本回归仍由执行单元验收。工具的哈希校验约束字节来源，不能证明新算法安全或科学改善；所有旧开发与 heldout 结果仍属于旧版本。若被审工具/17 文件范围/来源契约再变，需明确新修订后重新核对。
