# F：未来资源指导选道原型

从锁定S独立构建，未叠加V。源码：`tmp/staggered_bottleneck/candidates/midflow_future_resources/native_rules.py`，SHA256 `e4b18ac1a61970b9f45e6815725b036a35e91e6773dc6afdcd2032b64daba7e7`。

见[method.md](method.md)、[构建脚本](build.py)、[源码差异](native_rules.patch)、[来源记录](source.json)。F的初始6项物理合同通过，但后续审计发现未来资源距目标3–7m时，±2m的matches不够用于判空。该F源保持不动；[F2修订](../future_resources_v2/README.md)采用已有CLEARANCE=8m排除未来占用机会，并通过合并8项合同。

两版都只把未来资源用于选道；实际执行始终追踪本车旁边的真实间隙，不承诺追踪评分的未来slot。没有运行交通仿真，尚未采纳进生产。后续是否有益需要同条件交通结果及24/45辆真实几何验收。
