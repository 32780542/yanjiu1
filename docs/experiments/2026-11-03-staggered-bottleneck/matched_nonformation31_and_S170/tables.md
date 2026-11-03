# 显式同输入配对归因

G0/G0N are explicitly transform-mode nonformation controls, not original NOA. S versus LP0 changes the extra gate as well as longitudinal phase; not strict S-phase0 equivalence. Traffic success does not prove formation geometry.

| 比较(target=reference) | 流量 | 道路 | 系统参考/候选(s) | 改善(%) | 改善种子 | 燃油差(g/km) | 瓶颈差(s) | 低速差(车辆秒) |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| G0/transform=TM/noa | 2250.0 | lane_drop | 53.9137/50.8461 | 5.6898 | 5/5 | -1.7169 | -2.7481 | -1136.8400 |
| G0/transform=TM/noa | 2500.0 | lane_drop | 77.7275/73.3499 | 5.6320 | 5/5 | -0.8851 | -1.4283 | -542.5200 |
| G0N/transform=G0/transform | 2250.0 | lane_drop | 50.8461/50.7705 | 0.1488 | 3/5 | -1.1470 | -0.3460 | -1248.6200 |
| G0N/transform=G0/transform | 2500.0 | lane_drop | 73.3499/72.7786 | 0.7788 | 3/5 | -2.5451 | -0.1285 | -3283.7400 |
| G0N/transform=TM/noa | 2250.0 | lane_drop | 53.9137/50.7705 | 5.8301 | 4/5 | -2.8639 | -3.0941 | -2385.4600 |
| G0N/transform=TM/noa | 2500.0 | lane_drop | 77.7275/72.7786 | 6.3669 | 5/5 | -3.4302 | -1.5568 | -3826.2600 |
| L/transform=G0/transform | 2250.0 | lane_drop | 50.8461/50.5529 | 0.5767 | 3/5 | 9.4178 | -0.8615 | -1149.6200 |
| L/transform=G0/transform | 2500.0 | lane_drop | 73.3499/73.9921 | -0.8756 | 1/5 | 10.1616 | -1.0568 | -1793.2200 |
| L/transform=G0N/transform | 2250.0 | lane_drop | 50.7705/50.5529 | 0.4285 | 4/5 | 10.5649 | -0.5155 | 99.0000 |
| L/transform=G0N/transform | 2500.0 | lane_drop | 72.7786/73.9921 | -1.6674 | 2/5 | 12.7066 | -0.9283 | 1490.5200 |
| M/transform=G0/transform | 2250.0 | lane_drop | 50.8461/49.9124 | 1.8364 | 4/5 | 1.2625 | -1.4572 | -1359.5000 |
| M/transform=G0/transform | 2500.0 | lane_drop | 73.3499/77.5684 | -5.7512 | 1/5 | 2.9008 | -1.0790 | -3598.1800 |
| N/transform=G0N/transform | 2250.0 | lane_drop | 50.7705/52.3651 | -3.1408 | 2/5 | 8.8235 | 1.2293 | -125.8000 |
| N/transform=G0N/transform | 2500.0 | lane_drop | 72.7786/77.9580 | -7.1166 | 1/5 | 11.4792 | 1.8184 | -46.4600 |
| S/transform=G0/transform | 2250.0 | lane_drop | 50.8461/48.5624 | 4.4914 | 5/5 | 8.0463 | -2.4902 | -1034.4400 |
| S/transform=G0/transform | 2500.0 | lane_drop | 73.3499/67.4847 | 7.9962 | 5/5 | 6.8706 | -3.7706 | -1306.9600 |
| S/transform=G0N/transform | 2250.0 | lane_drop | 50.7705/48.5624 | 4.3491 | 5/5 | 9.1933 | -2.1442 | 214.1800 |
| S/transform=G0N/transform | 2500.0 | lane_drop | 72.7786/67.4847 | 7.2740 | 5/5 | 9.4156 | -3.6422 | 1976.7800 |
| S/transform=L/transform | 2250.0 | lane_drop | 50.5529/48.5624 | 3.9375 | 5/5 | -1.3716 | -1.6287 | 115.1800 |
| S/transform=L/transform | 2500.0 | lane_drop | 73.9921/67.4847 | 8.7948 | 5/5 | -3.2910 | -2.7139 | 486.2600 |
| S/transform=LP0/transform | 2250.0 | lane_drop | 49.6565/48.5624 | 2.2034 | 5/5 | 4.9284 | -1.2347 | -553.8600 |
| S/transform=LP0/transform | 2500.0 | lane_drop | 69.6095/67.4847 | 3.0524 | 5/5 | 5.4605 | -0.9815 | 226.7400 |
| S/transform=TM/noa | 2250.0 | lane_drop | 53.9137/48.5624 | 9.9257 | 5/5 | 6.3294 | -5.2383 | -2171.2800 |
| S/transform=TM/noa | 2500.0 | lane_drop | 77.7275/67.4847 | 13.1778 | 5/5 | 5.9854 | -5.1990 | -1849.4800 |
