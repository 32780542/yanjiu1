# 固定 LP0 严格等价于所采用 S 关闭纵向相位

**结论：S 把纵向 `phase_speed` 置零后，与现成 LP0 的完整控制输出和自身 Memory 严格等价。** 因此控制层面允许复用既有 LP0 十例作为 S 关闭纵向相位的消融；实际配对仍必须逐例保持同 arrival tape、道路、seed、物理参数及非控制源码，保留 LP0 的真实源码身份，不重写旧 protocol 或结果。本核验没有运行交通仿真、修改控制器或使用 Git。

固定 S（生产及候选）SHA256 为 `8bdaa210e7aa7e72e8ae5e6b4a6642e38adc80b2a3416653624752fbf685d12f`；固定 LP0 为 `64a134fee75ae628779b81e497fca1de6b095a2f1828493c573ee2dacc455eb4`。虚拟 S0 仅在内存把 S 的相位限幅赋值替换为 LP0 原有的 `phase_speed = 0.0`，保留 S 的 CTH 门禁，源码 SHA 为 `b3b7fa3c363cb19826904e54a146b4e9bfea4e79040d9844208d4bd882648057`，未写出新候选文件。

## AST 与常量传播证明

[独立核验脚本](verify_LP0_S_phase_zero.py)先核验固定源 SHA，并硬断言虚拟 S0 删除以下精确两行之后，**源码字节直接等于 LP0**。与旧 M 证明不同，本证明不需要删除任何 `error` 累加或其他死变量。

```python
if phase_speed * (following[0] - ego.speed) < 0.0:
    phase_speed = 0.0
```

1. AST 精确检查 `_following` 中只有两个 `phase_speed` 写入：外层无条件的浮点正零赋值，以及该门禁内部的零赋值。正零赋值之后紧接实际 front 分支，门禁为其中第一条语句，二者之间没有其他写入；初始化严格支配门禁。
2. AST 精确检查门禁只有上述比较、一次零赋值且无 else；比较表达式没有函数调用、赋值表达式或额外状态读写。对项目有效 Vehicle 状态，`ego.speed` 和 `_front_following` 经夹紧的 `following[0]` 均有限且处于 `[0,33.3]`，所以速度差有限。二进制浮点 `0.0 * 有限差值` 只得到 `+0.0` 或 `-0.0`，两者严格小于 `0.0` 都为假。因此门禁不会执行，也不改变可见状态。
3. 只移除这一个已证明恒假的 If 后，**整模块 AST 与 LP0 完全相同**。常量、Vehicle/Command/Memory、最近真实 front、L 的实测 witness、互选图与 linked、几何 fill、实际 gap、横移优先级及硬安全全部保留。没有通过关闭图或全部移除 body 逻辑取得等价。
4. 该证明适用于项目有效物理状态下的控制输出和 Memory，不要求计算次数或墙钟一致；不宣称动态系统全局收敛。

## 6000 个有效状态的独立精确比较

使用与旧 M 证明相同且未改的 oracle，SHA256 `a24adc6bee09319fd1d71eb05c468be76bed54b41d9dd8e55caa43731fbe91f6`。读取前 6000 个状态，通过各自 Vehicle 默认值还原省略字段，并逐车验证数值有限、速度在 `[0,33.3]`、车道合法和本地 track 唯一。数值执行的虚拟 S0 **保留未经化简的门禁**，不是只运行已删门禁的 AST。

- `noa`、`formation`、`transform` 三模式共 **18000 次完整 Command/Memory 比较按 `float.hex` 精确相同**，包含 speed、lane、reason、target、reference、formation_state 和全部记忆字段。
- 另外 **6000 次 safe_speed 按 hex 精确相同**。
- 其中 10006 个命令的 formation_state 为 1，4111 个命令具有真实 reference；样本包含 approach_gap、approach_join、executing、fill_layer、merge 和正常跟驰/超车等实际分支。
- S 候选与生产、LP0、L、M、两份 source.json、旧 M 的脚本/说明/JSON及其完整 operation 文件，在本次运行前后逐字不变；各 SHA 见[结果 JSON](LP0_S_phase_zero_equivalence.json)。Oracle 前后 SHA 也相同。

成功 operation：`20261103T080925054846Z_LP0-S-phase-zero-AST-and-6000-equivalence-valid-defaults_f78d20f6`，exit 0，4.172 秒，stderr 为空。脚本 SHA256 为 `9c6d410726666a47664e380c2881b024af7614acdb4017b0120fceee66778694`。

首次 operation `20261103T080849594003Z_LP0-S-phase-zero-AST-and-6000-equivalence_b2f0c0f2` 因新核验脚本直接读取 oracle 第 407 个状态省略的 `vy` 字段而退出 1。其失败日志保留；修正仅使核验使用 Vehicle 自带默认值，不改输入或控制器。它不是不等价反例。

## 归因口径

S 与同输入 LP0 的差异应解释为：**“所采用的、带真实前车 CTH 优先门禁的纵向相位子系统，相对于关闭纵向相位的贡献。”** 它包含该相位子系统在 head/body 及 CTH 冲突时的整体行为，不能称为纯 body P 参数的单独作用。LP0 仍保留交错 fill 几何、L 单格衔接、关系输出及合流规则，因此也不是关闭全部编队的对照。

此前以“多出门禁，所以 LP0 不是严格 S-phase0”为由限制归因的表述，已被此证明排除；门禁是所采用相位子系统的一部分，归零后没有额外控制效应。该控制等价结论不提供新的交通效果数字，也不能替代具体十例的输入与非控制源码配对核对。
