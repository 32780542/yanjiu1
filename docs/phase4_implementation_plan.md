# 阶段4实施计划：独立NOA基线

2026-09-11执行状态：本计划的实现、测试、实验、审查与交付工作已完成。复选框表示任务已执行，不代表驾驶条件全部通过；普通案例综合9/14通过，M1未通过，阶段5不放行。最终固定运行20260910T185443571873Z_3776ab63，结论与失败入口见phase4_acceptance.md及phase4_next_entry.md。

> 按已授权研究规格第六版、§6–8和阶段4执行。使用 subagent-driven-development 与 test-driven-development；所有实现、测试和日志留在keyan1，保持既有未提交phase01工作区，不复制废案、不改写冻结证据。

**目标：** 实现局部独立NOA的CRUISE/FOLLOW/PREPARE_LC/EXECUTE_LC/MERGE/EMERGENCY，并以真实SUMO小案例、信息隔离审计、独立数值重放评估驾驶能力与失败边界。

**架构：** 感知层保持现有接口，NOA本地记忆扩展只包含本车行为与自行生成的短期参考。纯函数 `decide(control, parameters)` 返回动作、本车新记忆及仅供日志的诊断；无TraCI、文件或全局状态访问。专用阶段4时钟先冻结/观测，再逐车独立控制、积分和批量SUMO同步，离线真值仅审计不干预动作。

**工具：** 登记Python3.12、标准库unittest、SUMO1.27.1与现有运动学/贝塞尔/几何接口，不增加依赖。

## 1. 前置核验

- [x] 读取阶段3验收、当前模型、观测与时钟代码及规格§6–8。执行 `python -I -B -S run.py verify`、`test`、`phase3-replay --run-dir results/phase3/runs/20260910T163533938451Z_2dcd59f7`，stdout/stderr写入 `results/phase4/preflight/`；确认原始证据无变化。
- [x] 保存本阶段入口、模型限制与参数来源。旧模型仅保留重放；不新增质量、惯量、轮胎力或非理想感知条件。

## 2. 纯局部NOA控制器

创建 `noa/contracts.py`、`noa/road.py`、`noa/controller.py` 和必要的候选安全检查模块；创建 `configs/phase4.json`；测试为 `tests/test_phase4_controller.py`。每项先写行为测试、保存失败证据，再实现并运行受影响测试。

```python
@dataclass(frozen=True, slots=True)
class NoaMemory(LocalMemory):
    # 仅本车计划与行为；其余具体字段随实现登记，不包含真值ID或其他车计划。
    plan: object = None

def decide(control: ControlInput, parameters) -> NoaDecision:
    # 返回 .action (Actuation)、.memory (NoaMemory)、.diagnostics (可JSON编码)
    ...
```

- [x] 同车道巡航、慢前车跟驰、减速/急刹/停车与再起步；对比可见前车变化的动作正例。
- [x] 从当前或有来源的本地道路观测推导当前/邻接车道及终止边界；道路整体平移不改变相对决策，禁止固定1000/640坐标触发。
- [x] 按局部几何生成两段二次贝塞尔候选，跟踪输出加速度及等效转向。候选检查预测期间车身与道路占用、前后车预测包络；无安全空隙则延后、减速或停止。
- [x] 实现换道准备、执行、完成/连续换道、强制并道和紧急状态；短期计划仅属于本车，保留几何来源和时刻。记录实际jerk与执行器jerk的差别，不用实际状态跳变补救。
- [x] 不变性测试涵盖邻车局部编号、邻车顺序、相同输入/本地记忆，以及纯局部信息入口；精确对称条件下不得用ID裁决。
- [x] 所有新增活动参数带值、单位、来源、状态和理由；沿用主运动/感知/安全硬边界。测试策略不冒称品牌或论文NOA标定。

## 3. 阶段4时钟与实验记录

创建 `simulation/noa_clock.py`、`experiments/phase4_cases.py`、`experiments/phase4.py`、`experiments/phase4_replay.py`、`experiments/phase4_audit.py`；测试为 `tests/test_phase4_records.py`。复用FleetBridge和RunRecord，不改写阶段3probe语义。

```python
sample = sensor.sample(ego_key, frozen_frame)
control = replace(sample, memory=replace(previous_own_memory,
                  observation_history=sample.memory.observation_history))
decision = decide(control, immutable_parameters)
step = model.advance(initial, decision.action, sync_dt, integration_dt)
```

- [x] 测试所有动作取自同刻快照、逆序执行不变、任何漏车/重复推进或读回失败均保留并终止。脚本干扰车只读取自身状态及预先登记的外部工况，不读取NOA动作来让行。
- [x] 小案例覆盖速度阶跃、慢前车、减速/急刹、切入、高速后车、普通换道、连续两次换道、终止车道有空隙/无空隙、停车起步、跨edge、参考对象越界；保留不可避免碰撞或停车舒适性失败的压力案例。
- [x] 每次真实SUMO尝试独立RunRecord：冻结初始条件、模型/NOA/工况参数、源代码与配置、路网和输入快照、命令/版本、全区间控制输入、动作、本车记忆、全部积分子步、读回及诊断；提前失败也完整保存已获得证据。
- [x] 独立真值审计计算碰撞、道路越界、横向跟踪、完成换道/并道、速度/加速度/转向/jerk、终止原因。失败不计为正常驾驶成功；分别报告数值可重放和驾驶门槛。
- [x] 重放从初态、冻结配置与局部观测链复算每次动作和记忆，验证全部子步、SUMO读回与哈希；拒绝动作/记忆/观测/时刻/子步/截断篡改，保留故障注入证据。
- [x] 固定物理工况下至少运行一次积分减半及控制/感知同步减半对照；保留状态切换差异和未改善结果，不称完整收敛证明。

## 4. 集成、审查与交付

修改 `run.py` 接入 `phase4` 和 `phase4-replay`，更新 `research/common.py` 的代码清单以覆盖noa，更新 `research/registry.py` 收录phase4层。先以缺少子命令或遗漏代码快照的测试确认失败，再接入。

- [x] 运行全部测试、真实SUMO案例与固定运行独立重放；原阶段3仍可重放，当前源码差异如实报告。
- [x] 由独立子代理先按规格审查局部信息、安全与失败记录，再审查重放/哈希/时钟代码质量；修复确认的问题并重跑受影响检查。
- [x] 保存 `docs/phase4_acceptance.md`、`docs/phase4_model.md`、下一阶段入口、README、参数登记表及交付哈希。若部分驾驶门槛失败，明确M1未通过，下一入口先补齐阶段4，不放行阶段5或正式实验。

复跑命令统一为 `python -I -B -S run.py test`、`phase4`、`phase4-replay --run-dir results/phase4/runs/<run_id>`。运行或验收失败退出非零；所有失败目录保留。
