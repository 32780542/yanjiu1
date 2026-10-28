# runrun.py SUMO GUI 演示入口设计

## 目标

在不修改现有科研 `run.py`、控制器或封存结果的前提下，新增项目根目录 `runrun.py`。用户既可以在PowerShell中执行 `python runrun.py`，也可以在编辑器中打开该文件后直接点击“运行”或“调试”。程序启动后显示三个选项：

1. 播放阶段5F已封存的算法轨迹；
2. 运行车辆数量等参数可调的SUMO原生瓶颈交通流；
3. 退出。

该入口是演示工具，不新增科研证据，也不改变阶段5科学结论。

## 用户可编辑配置

`runrun.py` 顶部设置清晰、带中文注释的配置区。至少包含：

```python
VEHICLE_COUNT = 30
DEPART_INTERVAL_S = 0.8
VEHICLE_SPEED_MPS = 12.0
SIMULATION_DURATION_S = 120.0
GUI_DELAY_MS = 40
AUTO_ZOOM = True
WAIT_BEFORE_CLOSE = True
ALGORITHM_CASE = "r5c_gradual_three_r5_on"
```

车辆数量、发车间隔和车辆速度主要控制模式2；算法案例、GUI延迟、自动缩放和结束等待控制模式1。程序在启动SUMO前验证类型、有限性、取值范围、案例存在性、SUMO安装与路网文件，错误信息必须指出具体参数或路径。

## 模式1：阶段5F算法轨迹演示

模式1读取阶段5F正式自适应运行：

`variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400652574Z_9f6cc9d8`

默认案例为 `r5c_gradual_three_r5_on`。程序读取其 `metadata.json` 和 `trace.jsonl`，创建只供演示使用的SUMO route/config，在可见 `sumo-gui` 中生成同一组车辆，并按封存轨迹逐拍设置车辆位置、角度和速度。画面重现当前项目已有结果，不重新计算控制决策。

控制台必须明确显示：这是封存轨迹可视化，不是一次新的实时科研实验。若案例是失败前缀，仍只播放保存的前缀并显示其失败状态；不得补齐、平滑或隐藏碰撞结果。

允许用户通过 `ALGORITHM_CASE` 切换同一正式包内的案例。案例名必须存在于 `case_index.json`，且必须有可读的metadata和trace。默认案例展示多车低速换道效果。

## 模式2：可调SUMO原生交通流

模式2根据顶部配置生成新的route XML和sumocfg，使用既有3车道收缩为2车道的 `bottleneck.net.xml`。车辆轮流分配到上游三条车道，按固定发车间隔进入，采用SUMO原生跟驰与换道模型。车辆数、速度和仿真时长可调。

此模式不调用NOA/阶段5F控制器。控制台和运行元数据必须标注“SUMO原生交通流演示”，避免将其结果误认为算法性能。

## 文件、进程与数据流

脚本用 `Path(__file__).resolve().parent` 确定项目根目录，因此编辑器调试时的工作目录不会影响运行。SUMO位置从 `configs/tools.json` 读取，不依赖系统PATH中的其他版本。

每次启动模式1或2，都在 `results/demo_runs/<timestamp>_<mode>/` 创建独立目录，保存：

- 生成的 `.rou.xml` 和 `.sumocfg`；
- SUMO stdout/stderr日志；
- 本次顶部配置快照；
- 模式、来源轨迹或路网哈希、开始/结束状态和异常信息。

程序通过TraCI启动可见 `sumo-gui`。连接、窗口和子进程由本次脚本拥有；正常结束、用户关闭窗口或 `Ctrl+C` 时都尝试关闭连接并回收子进程。不得写入或覆盖 `results/phase*`、`variants/*/results/phase*` 中的科研包。

## GUI行为

- 默认自动开始播放；`GUI_DELAY_MS` 控制视觉播放速度。
- `AUTO_ZOOM=True` 时设置适合完整瓶颈路段或算法车辆局部区域的视口。
- 仿真结束且 `WAIT_BEFORE_CLOSE=True` 时，控制台提示按Enter关闭，使用户在调试模式下有时间观察最终画面。
- 用户提前关闭SUMO GUI时，脚本以正常的“用户关闭”状态收尾，而不是输出难懂的TraCI堆栈。
- 菜单输入无效时重新提示，不启动任何进程。

## 代码边界

`runrun.py` 负责用户入口和配置。可复用逻辑放入 `demo/sumo_gui.py`，包括参数验证、XML生成、封存轨迹读取、TraCI启动和资源清理；`demo/__init__.py` 只声明包。这样可独立测试生成与验证逻辑，不要求测试进程打开GUI。

现有 `run.py`、阶段5F版本、实验运行器、安全守卫与封存结果保持不变。模式1读取正式轨迹时先校验其manifest、固定run路径和案例索引；若来源不完整或被修改，拒绝播放并提示用户。

## 错误处理

- 配置错误：启动GUI前失败，中文指出变量名和允许范围。
- SUMO或路网缺失：指出配置文件和期望路径。
- 正式轨迹manifest、案例索引或trace不一致：拒绝模式1，不降级到未校验数据。
- TraCI连接失败：保存失败状态与日志，关闭已启动进程。
- 用户关闭窗口或按 `Ctrl+C`：保存 `user_closed` / `interrupted` 状态并清理。
- 模式2出现SUMO碰撞或teleport：保留计数并在结束摘要中显示，不将其隐藏或自动修复。

## 测试与验收

实现前先写失败测试，至少覆盖：

- 顶部默认配置与参数边界；
- 任意工作目录下解析项目根和SUMO路径；
- 模式1正式manifest、案例名、失败前缀和轨迹读取；
- 模式2精确车辆数、ID唯一、三车道轮转、发车时间与速度；
- 生成XML可被标准库解析且引用正确路网；
- 菜单1/2/3和无效输入；
- GUI启动命令必须使用登记的 `sumo-gui.exe`；
- mock TraCI下自动缩放、逐拍播放、结束等待和清理；
- 用户关闭窗口、连接失败和 `Ctrl+C` 的状态保存。

完成后运行新增测试与受影响回归。再执行不启动GUI的 `--check` 自检，验证SUMO、路网和默认轨迹来源。最后由用户运行 `python runrun.py` 或直接点击调试进行可见验收；自动化测试不伪造“已看到GUI”的结论。

## 明确不做

- 不让任意车辆数进入阶段5F实时控制器；
- 不把封存轨迹播放称为新的闭环实验；
- 不改科研 `run.py`；
- 不覆盖旧结果或失败证据；
- 不添加通信、全局调度、车型真值或邻车私有意图；
- 不把演示模式的顺畅画面解释为阶段5科学通过。
