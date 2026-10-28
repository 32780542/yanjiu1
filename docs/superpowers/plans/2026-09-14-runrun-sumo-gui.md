# runrun.py SUMO GUI 演示入口实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增可从命令行或编辑器“运行/调试”直接启动的 `runrun.py`，提供阶段5F封存轨迹可视化、车辆数可调的SUMO原生交通流和退出三个选项。

**Architecture:** `runrun.py` 只保存用户可编辑配置和交互入口；`demo/sumo_gui.py` 负责配置验证、证据校验、XML/元数据生成、TraCI GUI运行与清理。所有可见运行写入新的 `results/demo_runs/` 子目录，不修改科研入口或封存结果；测试通过依赖注入和临时目录覆盖行为，不启动GUI。

**Tech Stack:** Python 3.12标准库、`unittest`、SUMO 1.27.1、TraCI 1.27.1、XML ElementTree。

---

## 文件结构

- 创建 `runrun.py`：顶部配置区、三项菜单、`--check`入口。
- 创建 `demo/__init__.py`：演示包边界说明。
- 创建 `demo/sumo_gui.py`：配置、证据、工件、GUI会话和两种运行模式。
- 创建 `tests/test_runrun_demo.py`：无需打开GUI的回归测试。
- 修改 `README.md`：增加面向用户的GUI演示运行说明和科学语义边界。
- 不修改 `run.py`、`experiments/`、`models/`、`noa/`、`simulation/`、阶段5F源码或任何封存结果。

### Task 1: 配置对象、项目路径与环境自检

**Files:**
- Create: `tests/test_runrun_demo.py`
- Create: `demo/__init__.py`
- Create: `demo/sumo_gui.py`

- [x] **Step 1: 写配置与路径失败测试**

```python
class DemoConfigurationTests(unittest.TestCase):
    def test_project_root_is_independent_of_current_directory(self):
        self.assertEqual(gui.PROJECT_ROOT, Path(__file__).resolve().parents[1])

    def test_default_config_is_valid(self):
        result = gui.validate_config(gui.DemoConfig(), gui.PROJECT_ROOT)
        self.assertTrue(result.sumo_gui.name == "sumo-gui.exe")

    def test_invalid_numeric_and_boolean_values_name_the_variable(self):
        bad = [
            (replace(gui.DemoConfig(), vehicle_count=0), "VEHICLE_COUNT"),
            (replace(gui.DemoConfig(), depart_interval_s=float("nan")), "DEPART_INTERVAL_S"),
            (replace(gui.DemoConfig(), vehicle_speed_mps=40), "VEHICLE_SPEED_MPS"),
            (replace(gui.DemoConfig(), simulation_duration_s=0), "SIMULATION_DURATION_S"),
            (replace(gui.DemoConfig(), gui_delay_ms=-1), "GUI_DELAY_MS"),
            (replace(gui.DemoConfig(), auto_zoom=1), "AUTO_ZOOM"),
        ]
        for config, name in bad:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, name):
                gui.validate_config(config, gui.PROJECT_ROOT)
```

- [x] **Step 2: 运行测试并确认RED**

Run: `python -B -m unittest tests.test_runrun_demo.DemoConfigurationTests -v`

Expected: FAIL，原因是 `demo.sumo_gui` 尚不存在。

- [x] **Step 3: 实现最小配置和路径解析**

```python
@dataclass(frozen=True, slots=True)
class DemoConfig:
    vehicle_count: int = 30
    depart_interval_s: float = 0.8
    vehicle_speed_mps: float = 12.0
    simulation_duration_s: float = 120.0
    gui_delay_ms: int = 40
    auto_zoom: bool = True
    wait_before_close: bool = True
    algorithm_case: str = "r5c_gradual_three_r5_on"

@dataclass(frozen=True, slots=True)
class CheckedPaths:
    root: Path
    sumo_gui: Path
    network: Path
    algorithm_run: Path

def validate_config(config: DemoConfig, root: Path = PROJECT_ROOT) -> CheckedPaths:
    # 严格拒绝bool冒充int、NaN/Inf、超范围值、发车计划超出仿真时长、
    # 缺失tools.json/SUMO GUI/路网/阶段5F正式运行目录。
```

数值范围固定为：车辆数1–5000、发车间隔0.1–60秒、速度0.1–33.3 m/s、仿真时长1–3600秒、GUI延迟0–1000 ms；并要求最后一辆车的计划发车时刻小于仿真时长。

- [x] **Step 4: 运行配置测试并确认GREEN**

Run: `python -B -m unittest tests.test_runrun_demo.DemoConfigurationTests -v`

Expected: PASS。

### Task 2: 原生交通流工件生成

**Files:**
- Modify: `tests/test_runrun_demo.py`
- Modify: `demo/sumo_gui.py`

- [x] **Step 1: 写route、sumocfg和运行目录失败测试**

```python
class NativeArtifactTests(unittest.TestCase):
    def test_native_route_has_exact_unique_vehicles_and_round_robin_lanes(self):
        root = gui.native_routes_tree(gui.DemoConfig(vehicle_count=7))
        vehicles = root.findall("vehicle")
        self.assertEqual([v.get("id") for v in vehicles], [f"demo_{i:04d}" for i in range(7)])
        self.assertEqual([v.get("departLane") for v in vehicles], ["0", "1", "2", "0", "1", "2", "0"])
        self.assertEqual([float(v.get("depart")) for v in vehicles], [0, .8, 1.6, 2.4, 3.2, 4, 4.8])
        self.assertTrue(all(v.get("departSpeed") == "12" for v in vehicles))

    def test_sumocfg_references_absolute_network_and_local_route(self):
        tree = gui.sumo_config_tree(self.root / "bottleneck.net.xml", "native.rou.xml", self.out, 120)
        self.assertEqual(tree.find("input/net-file").get("value"), str(self.root / "bottleneck.net.xml"))
        self.assertEqual(tree.find("input/route-files").get("value"), "native.rou.xml")

    def test_new_run_directory_never_reuses_an_old_attempt(self):
        first = gui.create_run_directory(self.root, "native", stamp="20260914T010203000000Z", token="deadbeef")
        with self.assertRaises(FileExistsError):
            gui.create_run_directory(self.root, "native", stamp="20260914T010203000000Z", token="deadbeef")
```

- [x] **Step 2: 运行测试并确认RED**

Run: `python -B -m unittest tests.test_runrun_demo.NativeArtifactTests -v`

Expected: FAIL，缺少 `native_routes_tree`、`sumo_config_tree` 和 `create_run_directory`。

- [x] **Step 3: 实现XML与独立运行目录**

```python
def native_routes_tree(config: DemoConfig) -> ET.Element:
    routes = ET.Element("routes")
    ET.SubElement(routes, "vType", id="native_demo", carFollowModel="IDM",
                  laneChangeModel="LC2013", length="4", width="1.8",
                  maxSpeed="33.3", accel="2.6", decel="4.5", minGap="2.5")
    ET.SubElement(routes, "route", id="through", edges="upstream downstream")
    for index in range(config.vehicle_count):
        ET.SubElement(routes, "vehicle", id=f"demo_{index:04d}", type="native_demo",
                      route="through", depart=format_number(index * config.depart_interval_s),
                      departLane=str(index % 3), departPos="base",
                      departSpeed=format_number(config.vehicle_speed_mps))
    return routes
```

`sumo_config_tree` 写入0.1秒步长、无强制teleport、碰撞警告，以及运行目录内的 `tripinfo.xml`、`summary.xml`、`lanechanges.xml` 和 `sumo.log`。`write_xml` 与 `write_json_atomic` 只接受已经由 `create_run_directory` 创建的目标。

- [x] **Step 4: 运行工件测试并确认GREEN**

Run: `python -B -m unittest tests.test_runrun_demo.NativeArtifactTests -v`

Expected: PASS。

### Task 3: 阶段5F证据校验与流式轨迹读取

**Files:**
- Modify: `tests/test_runrun_demo.py`
- Modify: `demo/sumo_gui.py`

- [x] **Step 1: 写正式证据与失败前缀测试**

```python
class AlgorithmTraceTests(unittest.TestCase):
    def test_default_formal_case_hashes_and_frames_are_readable(self):
        source = gui.load_trace_source(gui.PROJECT_ROOT, "r5c_gradual_three_r5_on")
        frames = gui.iter_trace_frames(source)
        first, second = next(frames), next(frames)
        self.assertEqual(set(first.states), {"lead_lower", "lead_upper", "lower", "middle_front", "upper"})
        self.assertGreater(second.time_s, first.time_s)
        self.assertEqual(source.evidence_status, "completed")

    def test_unknown_case_and_tampered_trace_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "ALGORITHM_CASE"):
            gui.load_trace_source(gui.PROJECT_ROOT, "missing")
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            gui.verify_relative_hash(self.root, {"trace.jsonl": "0" * 64}, "trace.jsonl")

    def test_failed_record_yields_only_preserved_completed_prefix(self):
        source = self.make_source([initial_record, completed_record, failed_record])
        frames = list(gui.iter_trace_frames(source))
        self.assertEqual([f.time_s for f in frames], [0.0, 0.1])
        self.assertEqual(source.evidence_status, "failed")
```

- [x] **Step 2: 运行测试并确认RED**

Run: `python -B -m unittest tests.test_runrun_demo.AlgorithmTraceTests -v`

Expected: FAIL，缺少正式包校验和轨迹迭代器。

- [x] **Step 3: 实现锚定manifest与逐行读取**

```python
ALGORITHM_RUN_REL = Path("variants/phase5f_adaptive_duration/results/phase5_r5/runs/20260913T162400652574Z_9f6cc9d8")
EVIDENCE_MANIFEST_SHA256 = "da5f87a7abb899fa8c92aaf32696d9f2b275452452703e4e6c3ed70208a23e03"

def load_trace_source(root: Path, case_name: str) -> TraceSource:
    # 先校验evidence_hashes.json自身的固定摘要；再校验case_index.json、
    # cases/<case>/metadata.json、trace.jsonl和validation.json。
    # case必须存在于expected_variants且已经finalized。

def iter_trace_frames(source: TraceSource) -> Iterator[TraceFrame]:
    # 第一行产生initial帧；后续只对status==completed的记录产生每个actor的final状态；
    # 首个失败/不完整记录立即停止，既不插值也不补齐。
```

哈希采用1 MiB块流式计算，禁止一次把约80 MiB的 `trace.jsonl` 读入内存。`TraceSource` 保存案例目录、metadata、validation、状态与trace路径；`TraceFrame` 保存时间和不可变语义的状态映射。

- [x] **Step 4: 运行轨迹测试并确认GREEN**

Run: `python -B -m unittest tests.test_runrun_demo.AlgorithmTraceTests -v`

Expected: PASS，且默认正式trace摘要与固定manifest一致。

### Task 4: TraCI GUI会话、轨迹播放与原生仿真

**Files:**
- Modify: `tests/test_runrun_demo.py`
- Modify: `demo/sumo_gui.py`

- [x] **Step 1: 写GUI命令、视口、逐帧和清理失败测试**

```python
class GuiRuntimeTests(unittest.TestCase):
    def test_gui_command_uses_registered_binary_and_delay(self):
        command = gui.gui_command(self.paths, self.sumocfg, 40, 8813)
        self.assertEqual(Path(command[0]), self.paths.sumo_gui)
        self.assertIn("--remote-port", command)
        self.assertEqual(command[command.index("--delay") + 1], "40")

    def test_algorithm_playback_moves_every_actor_and_sets_zoom(self):
        status = gui.play_algorithm(self.connection, self.source, auto_zoom=True)
        self.assertEqual(self.connection.gui.setBoundary.call_count, 1)
        self.assertEqual(self.connection.vehicle.moveToXY.call_count, 10)
        self.assertEqual(status.frames_played, 2)

    def test_owned_session_closes_connection_process_and_log_on_error(self):
        with self.assertRaises(RuntimeError):
            with gui.OwnedGuiSession(self.connection, self.process, self.log):
                raise RuntimeError("injected")
        self.connection.close.assert_called_once()
        self.process.terminate.assert_called_once()
        self.log.close.assert_called_once()
```

- [x] **Step 2: 运行测试并确认RED**

Run: `python -B -m unittest tests.test_runrun_demo.GuiRuntimeTests -v`

Expected: FAIL，缺少GUI命令、播放和拥有型清理。

- [x] **Step 3: 实现GUI启动和播放核心**

```python
def to_sumo_pose(state: Mapping[str, float], length_m: float = 4.0) -> tuple[float, float, float]:
    heading = state["heading_rad"]
    return (state["x_m"] + length_m / 2 * math.cos(heading),
            state["y_m"] + length_m / 2 * math.sin(heading),
            (90 - math.degrees(heading)) % 360)

def play_algorithm(connection, source: TraceSource, auto_zoom: bool) -> PlaybackStats:
    # 用第一帧位置通过TraCI添加车辆；关闭SUMO自身速度/换道决策；
    # 每个记录控制拍设置速度和moveToXY后simulationStep；返回播放帧数和末时刻。

class OwnedGuiSession:
    # __exit__依次尝试connection.close、等待进程、必要时terminate/kill，并关闭日志；
    # 即使前一步失败，也继续完成后续清理。
```

`start_gui_session` 使用临时本机端口、显式 `sumo-gui.exe`、`--start`、`--delay`、`--no-step-log true`，将stdout/stderr合并写入本次 `stdout_stderr.log`。用户关闭窗口导致的TraCI连接异常转换为 `user_closed`，`KeyboardInterrupt`转换为 `interrupted`；其他异常保留类型、消息和traceback。

- [x] **Step 4: 实现两种模式的运行元数据生命周期**

```python
def run_algorithm_demo(config: DemoConfig, root: Path = PROJECT_ROOT, *, runtime=start_gui_session,
                       input_fn=input, output_fn=print) -> Path:
    # 新建目录，先写status=starting；生成algorithm.rou.xml和algorithm.sumocfg；
    # 启动前再次校验证据；播放；可选等待Enter；最终原子更新run_metadata.json。

def run_native_demo(config: DemoConfig, root: Path = PROJECT_ROOT, *, runtime=start_gui_session,
                    input_fn=input, output_fn=print) -> Path:
    # 新建目录并写配置快照；生成native.rou.xml/native.sumocfg；
    # 循环simulationStep直到时长或需求排空，累计碰撞/teleport并保存最终统计。
```

- [x] **Step 5: 运行GUI mock测试并确认GREEN**

Run: `python -B -m unittest tests.test_runrun_demo.GuiRuntimeTests -v`

Expected: PASS，不出现真实SUMO窗口或残留进程。

### Task 5: `runrun.py` 顶部配置、菜单与直接调试

**Files:**
- Modify: `tests/test_runrun_demo.py`
- Create: `runrun.py`

- [x] **Step 1: 写入口配置、菜单和`--check`失败测试**

```python
class EntrypointTests(unittest.TestCase):
    def test_top_level_defaults_build_expected_config(self):
        self.assertEqual(runrun.build_config(), gui.DemoConfig())

    def test_menu_dispatches_one_two_and_three_and_retries_invalid_input(self):
        for answers, expected in [(["1"], "algorithm"), (["2"], "native"), (["3"], "exit"), (["x", "2"], "native")]:
            with self.subTest(answers=answers):
                self.assertEqual(runrun.choose_mode(input_fn=answerer(answers), output_fn=lambda _: None), expected)

    def test_check_does_not_start_gui(self):
        with patch.object(runrun, "run_algorithm_demo") as algorithm, patch.object(runrun, "run_native_demo") as native:
            self.assertEqual(runrun.main(["--check"]), 0)
        algorithm.assert_not_called()
        native.assert_not_called()
```

- [x] **Step 2: 运行测试并确认RED**

Run: `python -B -m unittest tests.test_runrun_demo.EntrypointTests -v`

Expected: FAIL，`runrun.py` 尚不存在。

- [x] **Step 3: 实现可直接编辑的入口**

```python
# ===================== 用户配置区：直接修改下面这些值 =====================
VEHICLE_COUNT = 30
DEPART_INTERVAL_S = 0.8
VEHICLE_SPEED_MPS = 12.0
SIMULATION_DURATION_S = 120.0
GUI_DELAY_MS = 40
AUTO_ZOOM = True
WAIT_BEFORE_CLOSE = True
ALGORITHM_CASE = "r5c_gradual_three_r5_on"
# ========================== 配置区结束 ================================

def main(argv=None) -> int:
    config = build_config()
    if list(sys.argv[1:] if argv is None else argv) == ["--check"]:
        print_check_report(config)
        return 0
    mode = choose_mode()
    if mode == "algorithm":
        run_algorithm_demo(config)
    elif mode == "native":
        run_native_demo(config)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

入口在导入后用 `Path(__file__)` 确定根目录，并把项目根和登记SUMO tools路径加入运行环境，所以编辑器工作目录可以任意。错误在控制台显示中文摘要；调试时不要求添加参数。

- [x] **Step 4: 运行入口测试并确认GREEN**

Run: `python -B -m unittest tests.test_runrun_demo.EntrypointTests -v`

Expected: PASS。

### Task 6: 用户文档、整体自检与回归

**Files:**
- Modify: `README.md`
- Modify: `docs/superpowers/plans/2026-09-14-runrun-sumo-gui.md`

- [x] **Step 1: 更新README运行说明**

在“运行”章节前增加：

```markdown
## 可视化演示入口

打开项目根目录 `runrun.py`，修改顶部配置区后，可直接点击编辑器的“运行”或“调试”；也可执行 `python runrun.py`。菜单1播放阶段5F封存轨迹，菜单2运行参数可调的SUMO原生交通流，菜单3退出。菜单1不是新实验，菜单2不使用NOA控制器，两者输出均保存到 `results/demo_runs/`。

不打开GUI的环境自检：`python runrun.py --check`。
```

- [x] **Step 2: 运行新增测试全集**

Run: `python -B -m unittest tests.test_runrun_demo -v`

Expected: 全部PASS，无warning/error。

- [x] **Step 3: 运行不打开GUI的真实自检**

Run: `python runrun.py --check`

Expected: 退出码0；输出登记的SUMO 1.27.1路径、瓶颈路网、默认案例和证据SHA-256均通过；不生成SUMO进程。

- [x] **Step 4: 运行受影响完整回归并封存日志**

Run: `python -I -B -S scripts/run_logged.py --label runrun-final --timeout 900 -- python -I -B -S run.py test`

Expected: 原213项加新增测试全部PASS，退出码0，日志位于新的 `results/operations/<timestamp>_runrun-final_<token>/`。

- [x] **Step 5: 检查产物边界、语法和Git远端**

Run: `python -m py_compile runrun.py demo/sumo_gui.py tests/test_runrun_demo.py`

Expected: 退出码0。

Run: `git diff --check`

Expected: 退出码0，无空白错误。

Run: `git remote get-url origin`

Expected: `https://github.com/32780542/biyesheji1`。

Run: `git status --short`

Expected: 新增演示文件、测试、设计/计划文档及README修改可见；科研入口和封存结果无修改。由于仓库尚无HEAD，本计划不自动提交或推送。
