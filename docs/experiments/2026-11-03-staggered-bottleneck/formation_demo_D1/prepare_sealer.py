"""Reuse the prior complete raw/figure/source archive with D1 operation labels."""
from pathlib import Path
OUT=Path(__file__).resolve().parent
source=(OUT.parent/'formation_demo_S_long/seal_long_demo.py').read_text(encoding='utf-8')
source=source.replace("['S2400-demo-', 'S-long-']","['D1-geometry-']")
(OUT/'seal_long_demo.py').write_text(source,encoding='utf-8')
print('D1 complete evidence sealer prepared; no raw is pruned')
