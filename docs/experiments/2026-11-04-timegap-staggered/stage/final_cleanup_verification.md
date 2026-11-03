# C8最终可读性清理与等价交付

最终fallback为C8_relations及matched parallel的隔离清理源，四份各316行，旧冻结源与生产未改。

仅删除未使用的GAP常量、`_phase`的lanes参数、`_pair_error/_following`的phase_boundary参数，并更新`_physical_phase`内部的三个_phase调用。没有删除其他API或重构控制分支。

## 消费者边界

正式运行链`native_sumo.py/global_reference.py`只导入状态类、CRUISE/LANE_WIDTH、decide/safe_speed/_clear/_request；当前variant测试也不读取GAP、不调用_phase旧签名、不传phase_boundary。实际规则中的对应项均未参与运算。

旧B及phase06开发测试直接使用旧GAP或_phase签名，但它们默认绑定各自历史冻结候选；旧源和这些历史测试保留，不把它们迁移到final。正式运行接口保持原样。

## 等价验证

入口：`stage/verify_final_cleanup.py`，只读重算。

- 对四对父本/清理源精确验证只有授权删除与内部调用适配。
- 每对500个构造局部观测帧，总计2000帧，逐字段比较实际decide的完整Command与Memory，包含speed/lane/target/reference/reason/flag及NOA行为，全部相同。
- matched parallel只差phase=0、q=current.x两行；同几何200/300只差ROAD_PREVIEW。

这些是纯控制函数配对验证，不是交通仿真或正式样本。清理行为等价同时由未用项删除的精确源码差异支持。

| 候选目录（均位于tmp/staggered_bottleneck/candidates，文件native_rules.py） | SHA256 |
|---|---|
| 20261104_final_200 | 12022d1e0c430f6d677ceb4856d2e95d945acb333c45ff1dcd40af9de3506ce5 |
| 20261104_final_300 | 6295e391e08ff36e6986d5fd09c420a21c33c531baade5a9eceb410d150c444f |
| 20261104_final_parallel_200 | 37339c71fa81f4ce9f979e4d2ac752b7260d16022a8880927a9f965e9e663090 |
| 20261104_final_parallel_300 | 736564d4f92d53ea8eea84e302641e19465244bbe8bbed053f9c813ae1a1ac81 |

四源04:25冻结后不再修改。中文规则说明改为指向316行final_200，并更新全部22个源码锚点，删除未用兼容项说明。
