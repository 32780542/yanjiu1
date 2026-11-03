# G0N：保留N真实释放的匹配非形成对照

新源SHA `d4124d14568b282585395efd118a9ea434adcd1f73b40ae08159d97184b6302f`，345行，固定父N `5d21af5456e816c927116a66895db29d03fada7b28057ecef266b60a0d92a0d6`。仅_following换成原50m真实front CTH/状态0，_fill换成原NoA慢前车超车提案；整个_decide逐字保持N，包括八行本车唯一阻挡释放和实际gap执行。

它是 **matched-nonformation control，使用transform以匹配gap/Memory流程**，不是原纯NoA。与G0的全部源码差异已经证明恰好是N八行；NoA模式不变。联合12项/28子测试通过，无仿真/生产或Git修改。

共同build、mandatory_priority匹配证明、归因读法、日志标签及完整TDD记录见[共同方法](../matched_nonformation/method.md)和[共同构建](../matched_nonformation/build.py)。
