# 初版J：局部全体相位耦合，已知准备区单边图

该目录保持原J identity，SHA `dd0b7f466de943976af8fe44e1f5b89dfbafe5ea8e86f6f242fcea7a22f75e53`，441行。正文解释中称J0以区分物理邻接版，但原protocol的J名称与hash不改。

原12合同通过后发现 `_following` 仍按desired lanes枚举邻道，准备区lane1/2使用2/3不同参数，使1↔2边单边。该源及旧build/patch/meta保留为诊断，不通过覆盖旧目录来修复。

完整公式、Meere/Zheng原文边界、反例与新旧身份见[共同方法记录](../../methods/J_JT_local_coupling.md)。物理邻接修正在独立 `local_phase_coupling_physical`，只差一行。
