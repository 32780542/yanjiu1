# Codex流式中断：定位、处理与复验

2026-09-13。已把当前代理组 `SELECT` 从 `⚡️台湾HINET-1` 切换到 `🇺🇸美国西雅图-ChatGPT优化`，API读回确认生效；切换后通过桌面实际使用的10997端口重新完成短响应和长响应测试。证据指向原节点或其上游到OpenAI的连接不稳定；客户端证据不能确定具体哪一跳关闭TLS。

## 复现与对照

测试使用同一Codex 0.153.4、gpt-6-astra、xhigh，以及相同“输出1–1000并以TRANSPORT_OK结束”提示，不读取项目文件、不执行工具。代理内核均为Clash 2020.10.09。成功要求退出0、收到turn.completed、1000行逐行匹配且结束标记存在。

| 路径 | 结果 | 耗时 |
|---|---|---:|
| 原HINET-1，实际10997端口 | 多次TLS异常关闭，外部超时 | 100.1 s |
| 原HINET-1，独立本机代理实例 | 同样TLS异常关闭，外部超时 | 100.8 s |
| 西雅图，独立实例第一次 | 完整通过，无重试 | 75.0 s |
| 西雅图，独立实例第二次 | 完整通过，无重试 | 70.8 s |
| 切换后西雅图，实际10997端口 | 完整通过，无重试 | 70.5 s |

原节点错误为 `peer closed connection without sending TLS close_notify`。原桌面失败日志则是HTTP200之后chunked响应体解码失败，并已自动重试5次。因此，没有依据把135秒解释为一个已确认的单连接超时，也不能把问题仅归因于研究任务上下文过大。原节点普通HTTPS成功、46.5秒公开连续流也成功，说明这是有条件的长模型响应故障，不是所有联网均失效。

另发现CLI探针默认不会沿用桌面系统代理；直接连接会超时。复验明确在子进程指定HTTP_PROXY/HTTPS_PROXY，并移除工具环境中的API-key变量，使用已有ChatGPT登录，才与桌面路由/认证相符。这个修正只作用于诊断子进程。早期无效探针、超时及配置拒绝记录保留，未冒充有效A/B结果。

## 实际修改与恢复保护

1. 修改现有代理组SELECT的运行时节点选择。作用于使用该组的新连接，不只Codex。没有强制关闭已有连接；代理客户端重启后是否保持选择未在本轮测试。
2. 新增 `scripts/run_logged.py`：命令固定在研究根目录执行，独立目录保存完整stdout/stderr、开始/结束状态、退出码、执行器源码快照和哈希；输出给模型的只有摘要。Windows创建暂停进程、绑定私有Job后恢复，普通退出与超时均清理所属后代。
3. 新增 `docs/phase5_checkpoint.md` 与工作区 `AGENTS.md`，要求小单元接续、限制工具输出、避免重复整套已通过前置检查。

运行器的8项针对性测试通过，覆盖普通成功、非零退出、超时、大日志分块哈希、封存异常、父进程提前退出后的后代清理、无关进程保留以及Job绑定失败时目标未执行。原审查指出的两项问题及红绿测试均保留；主任务再次以运行器执行完整8项短测试，退出0。Windows要求CPython；运行器在“创建暂停进程到绑定Job”之间被OS强杀仍可能留下暂停进程，外部服务代启动的进程不属于该Job。不能将这些边界写成任何情况下无孤儿进程。

示例：

```powershell
Set-Location -LiteralPath 'D:\yanjiu1\keyan1'
& 'C:\Users\84335\AppData\Local\Programs\Python\Python312\python.exe' -I -B -S scripts/run_logged.py --label controller_tests --timeout 120 -- <可执行程序> <参数>
```

开始记录存在而结束记录缺失时，先核对PID/日志；不能自动重试可能有副作用的操作。

## 证据与回退

- [汇总与逐项结果](D:/yanjiu1/keyan1/results/codex_transport/20260913_005335/summary.json)
- [诊断过程与失败说明](D:/yanjiu1/keyan1/results/codex_transport/20260913_005335/README.md)
- [节点修改回执](D:/yanjiu1/keyan1/results/codex_transport/20260913_005335/proxy_change.json)
- [最终8项测试](D:/yanjiu1/keyan1/results/operations/20260912T171849182744Z_transport_final_test_02505c30/stderr.log)
- [阶段5恢复入口](D:/yanjiu1/keyan1/docs/phase5_checkpoint.md)

如需恢复原节点，运行本地 `results/codex_transport/20260913_005335/switch_proxy.py rollback`。它先检查当前选择，若已被外部改为其他节点便拒绝覆盖；新建回退回执，不改原切换证据。

正式Codex配置文件哈希保持一致，没有添加内置openai重试配置或改模型。当前版本拒绝覆盖内置提供方ID，与[官方配置参考](https://learn.chatgpt.com/docs/config-file/config-reference)一致。任务拆小与保存会话日志也符合[官方故障恢复建议](https://learn.chatgpt.com/docs/reference/troubleshooting)。

这次已消除可复现问题在当前路径上的触发，并获得3次长响应成功；不保证网络今后永不掉线。若再次发生，应先对照当前节点、错误时间及Cloudflare请求标识，而不是重跑研究前置阶段。阶段5固定前置审查64份文件复核无差异；本轮没有实现编队控制器、改变算法/模型参数或运行新的研究实验。
