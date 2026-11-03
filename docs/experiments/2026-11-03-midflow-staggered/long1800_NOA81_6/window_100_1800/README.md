# 延长窗口：复用封存账本

区域积分窗口[100,1800)；1000m首次越线沿原定义含两端。区域仍800≤x<1000、三道长度0.6车道公里，低速v<5m/s。TT/系统时间/燃油/分段时间/旗标沿用原全需求或全轨迹值，仅region和越线流量延长。缺样/不完整不补值；全部计划样本均列出，种子等权，target−NOA。

| 方法/流量 | eligible seeds | 系统时间NOA/候选(s) | 全窗区均速NOA/候选(m/s) | 全窗低速车辆秒NOA/候选 | 全窗越线流量NOA/候选(veh/h) |
|---|---:|---|---|---|---|

执行状态逐例保留case_analysis_status、原native status与worker operation路径。worker墙钟timeout/124与仿真max_time结束分开，native残留starting不表示仍在运行，也不推断物理已完成或算法未排空；未封存者不产生窗口指标。

全部案例、逐种子配对、均值与逐文件来源hash见同目录CSV/ledger_index.json/summary.json。原[100,600)数值另存original_100_600_metrics并逐项重建核对，不覆盖原工具或封包。
