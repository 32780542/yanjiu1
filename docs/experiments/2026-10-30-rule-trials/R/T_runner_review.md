# T候选与试验入口独立只读审查

审查时间：2026-10-30。T源码SHA256：`046f00aa397b7f4ff306f3fbb796c97565b743550a9dae608572e88f5a8cc02b`。审查时 `run_trials.py` SHA256：`e7e8d3f1271ba37eee3e03128f53cd8768fc327315a7babdf23e77475425550b`。本次未修改候选或运行入口，未启动交通仿真。

发现一项P2：`run_trials.py:61–64` 在存在 `result.json` 时无条件读取 `requested/completed/mean_travel_time_s/fuel_g_per_km`。实际worker在进入SUMO前先写入只含 `status="starting"` 等启动字段的文件；若随后超时或进程提前退出，`run_one` 会抛出 `KeyError`，主循环的 `future.result()` 随之中止收集，无法把该失败正常写入批次manifest。使用隔离临时目录、构造真实启动文件结构并令 `subprocess.run` 抛出 `TimeoutExpired` 的静态探针，实际复现 `KeyError('requested')`。应保存失败/不完整摘要并使其他case继续收集；当前已完成case的既有证据不因该失败路径缺陷而失效。

T控制规则未发现其他实质问题：目标为 `4+1.5+h*v_ego`，`h=(30−5.5)/28.8`，28.8m/s时与原30米平衡点一致；只使用当前物理近前车，局部200/100米过滤保留。NOA确实改用了同一时距跟驰，协议已明确登记，并在命令输出前将其状态强制归零。`safe_speed`、真实占道几何、必要合流优先权及通用请求函数的源码均保留；外层安全裁剪仍覆盖所有命令。执行T的7项行为测试，7/7通过；这些是静态行为证据。

冻结入口从固定Git基线提取所需源码，仅替换候选规则；动态源码快照读取同一冻结目录。检查运行中 `20261030T003244862597Z_screen` 的base/T各10个冻结文件，全部匹配协议哈希；审查时已有9份case输入/源码快照也全部匹配。原生道路和路由由同一固定源码生成，没有发现缺失的静态路网或配置资产。当前环境已有实际case产物；`configs/tools.json` 的相对来源文档字段不参与该运行路径。外部SUMO由原有环境/PATH定位，版本与解释器由case证据记录。

各case采用独立Python进程、独立输出目录和独立TraCI连接。此次批次外层确为 `run_logged.py` 的Windows私有Job，整个进程树有最终清理边界。单worker超时分支没有额外的子树清理确认；不能把外层最终清理解释为逐case超时清理已独立验证。未发现正常完成case间共享控制状态。

以上审查不证明串稳定性、普遍安全或交通收益；这些结论须另据规定的真实配对试验和独立种子结果。

按主代理要求增加隔离回归测试 `test_trial_runner_timeout.py`。唯一测试模拟超时及原生启动摘要，要求保留 `returncode=124`、失败或启动状态、原case路径；捕获旧解析器的 `KeyError` 并给出明确失败断言。RED日志为 `results/operations/20261030T003722131300Z_literature_R_runner_timeout_red_232a7125/`，1项测试、1个预期失败、0错误，未运行SUMO。运行入口由主代理修复，本审查未改动。
