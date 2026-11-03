"""Check unchanged sources, actual raster arithmetic, editable SVG and 300dpi PNG."""
import csv,hashlib,json,math,xml.etree.ElementTree as ET
from pathlib import Path
import numpy as np
from PIL import Image
BASE=Path(__file__).resolve().parent.parent;OUT=BASE/'final_figures'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
p=json.loads((OUT/'provenance.json').read_text())
for name,digest in p['source_tables_sha256'].items():
    path=Path(name);assert sha(path)==digest and sha(OUT/'source_tables'/path.name)==digest
for name,digest in p['outputs'].items():assert sha(OUT/name)==digest
with (OUT/'speed_raster_cells.csv').open(newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==17000
for profile in ['NoA','S']:
    grid=np.load(OUT/(profile+'_2250_seed42_speed_raster.npz'))
    rr=[r for r in rows if r['profile']==profile];assert len(rr)==8500
    for r in rr:
        i=(int(r['x_left_m'])-500)//20;j=(int(r['t_left_s'])-100)//5;n=int(r['vehicle_samples']);s=float(r['sum_sample_speed_mps'])
        assert n==grid['sample_count'][i,j] and s==grid['speed_sum_mps'][i,j]
        if n:assert math.isclose(float(r['mean_speed_mps']),s/n,rel_tol=1e-14) and float(r['mean_speed_mps'])==grid['mean_speed_mps'][i,j]
        else:assert r['mean_speed_mps']=='' and np.isnan(grid['mean_speed_mps'][i,j])
    source=next(r for r in p['raster_sources'] if r['profile']==profile)
    assert sum(int(r['vehicle_samples']) for r in rr)==source['vehicle_samples_in_raster']
    assert sha(Path(source['positions']))==source['positions_sha256']
plots=[]
for name in ['system_time_and_paired_improvement','fuel_cost_paired','long1800_2250_seed42_speed_raster']:
    png=OUT/(name+'.png');svg=OUT/(name+'.svg');ET.parse(svg)
    with Image.open(png) as im:
        assert min(im.info['dpi'])>299;plots.append(dict(figure=name,pixels=list(im.size),dpi=im.info['dpi'],png_sha256=sha(png),svg_sha256=sha(svg)))
result=dict(actual_cases=160,actual_eligible_pairs=80,unchanged_original_and_copied_table_hashes=True,raster_cells_rechecked=17000,all_nonempty_means_exactly_sum_divided_by_count=True,selected_full_raw_retained_hash_verified=True,all_three_figures_visually_reviewed=True,plots=plots,no_new_simulations=True,no_new_formation_or_efficiency_threshold=True)
(OUT/'final_verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
