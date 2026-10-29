"""Archive existing R/S evidence only; never runs simulation or edits originals."""
import ast
import difflib
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

DEST=Path(__file__).resolve().parent
ROOT=DEST.parents[3]
METHODS={'R':'R_leader_following','S':'S_layer_anchor'}
read=lambda p:json.loads(p.read_text(encoding='utf-8'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()


def write(name,data):
    target=DEST/name;target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as stream:stream.write(data)


def json_file(name,data):
    write(name,(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))


archives={}
originals={}


def origin(path):
    path=path.resolve();assert path.is_relative_to(ROOT)
    key=str(path)
    originals.setdefault(key,dict(path=key,size=path.stat().st_size,sha256=sha(path)))
    return originals[key]


def archive(name,members):
    expected=[]
    with (DEST/name).open('xb') as raw:
        with gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0,compresslevel=9) as gz:
            with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as bundle:
                for member,path in members:
                    assert not member.startswith('/') and '..' not in Path(member).parts
                    data=path.read_bytes();record=origin(path)
                    assert digest(data)==record['sha256']
                    info=tarfile.TarInfo(member);info.size=len(data);info.mode=0o644;info.mtime=0
                    bundle.addfile(info,io.BytesIO(data))
                    expected.append(dict(path=member,size=len(data),sha256=digest(data),original=record['path']))
    archives[name]=dict(size=(DEST/name).stat().st_size,sha256=sha(DEST/name),members=expected)


parent=ROOT/'tmp/common_pair_P_release'
freeze=read(parent/'freeze.json')
assert freeze['source_sha256']['noa/native_rules.py']=='8d112d79dce42b68fc4aba986aa52b5241c3ee4e8b6d8061cd04b80bcdb75864'
write('P_parent/freeze.json',(parent/'freeze.json').read_bytes())
write('P_parent/native_rules.py',(parent/'noa/native_rules.py').read_bytes())
origin(parent/'freeze.json');origin(parent/'noa/native_rules.py')
source_views={'P_parent':dict(source_sha256=freeze['source_sha256'],files={})}
for name,value in freeze['source_sha256'].items():
    assert sha(parent/name)==value
    source_views['P_parent']['files'][name]=dict(file='P_parent/native_rules.py') if name=='noa/native_rules.py' else dict(archive='R_sources.tar.gz',member=name)

case_members=[];cases=[];traces=[];diagnostic_baselines={};summaries={}
for label,folder in METHODS.items():
    package=ROOT/'tmp'/folder
    report=read(package/'report.json');candidate=read(package/'candidate_manifest.json')
    summaries[label]=report
    for name,value in candidate['source_sha256'].items():assert sha(package/name)==value
    archive(label+'_sources.tar.gz',[(name,package/name) for name in candidate['source_sha256']])
    source_views[label]=dict(source_sha256=candidate['source_sha256'],files={name:dict(archive=label+'_sources.tar.gz',member=name) for name in candidate['source_sha256']})
    for name in ['report.json','candidate_manifest.json','six_summary.json']:
        write(label+'/'+name,(package/name).read_bytes());origin(package/name)
    for test in sorted((package/'tests').glob('*.py')):
        write(label+'/tests/'+test.name,test.read_bytes());origin(test)
    for stage in ['red','green']:
        operation=Path(report['static_tests'][stage])
        for name in ['started.json','result.json','stdout.log','stderr.log']:
            write(label+'/static_'+stage+'/'+name,(operation/name).read_bytes());origin(operation/name)
    for stage in ['full_run_operation','analysis_operation']:
        operation=Path(report[stage]) if stage in report else ROOT/'results/operations/20261029T051149102769Z_S-layer-formation-physical-summary_89ef8c10'
        for name in ['started.json','result.json','stdout.log','stderr.log']:
            write(label+'/'+stage+'/'+name,(operation/name).read_bytes());origin(operation/name)
    selected=[(name,Path(data['case']),True) for name,data in report['six']['six'].items()]
    rows=report.get('pairs',report.get('cases'))
    for row in rows:
        selected.append((f"q1500_seed{row['seed']}_{row['scenario']}",Path(row[label]['path']),False))
        for control in ['H','NOA']:
            control_path=Path(row[control]['path'])
            if str(control_path) not in diagnostic_baselines:
                config=read(control_path/'input.json');result=read(control_path/'result.json')
                diagnostic_baselines[str(control_path)]=dict(role=control,path=str(control_path),
                    source_sha256=config['source_sha256'],mode=result['mode'],seed=result['seed'],scenario=result['scenario'],
                    input=origin(control_path/'input.json'),result=origin(control_path/'result.json'),
                    positions=origin(control_path/'positions.jsonl.gz'),
                    status='Equal-demand H-freeze diagnostic only; not formal same-source R/S pairing and not P100.')
    for case_label,path,small_trace in selected:
        assert path.resolve().is_relative_to(package.resolve())
        config=read(path/'input.json');result=read(path/'result.json')
        assert config['source_sha256']==result['source_sha256']==candidate['source_sha256']
        for name,value in candidate['source_sha256'].items():assert sha(path/'source'/name)==value
        prefix=f'{label}/{case_label}'
        files=['input.json','result.json','trips.json']+(['positions.jsonl.gz'] if small_trace else [])
        for name in files:case_members.append((prefix+'/'+name,path/name))
        trace=origin(path/'positions.jsonl.gz')
        traces.append(dict(method=label,case=case_label,archived=small_trace,
                           archive_member=prefix+'/positions.jsonl.gz' if small_trace else None,**trace))
        cases.append(dict(method=label,label=case_label,path=str(path),archive='case_evidence.tar.gz',prefix=prefix,
                          requested=result['requested'],completed=result['completed'],status=result['status'],safe=result['safe'],
                          source_sha256=candidate['source_sha256'],files=files))
archive('case_evidence.tar.gz',case_members)

config_files=sorted(p for p in (ROOT/'tmp/R_leader_following/configs').rglob('*') if p.is_file())
for path in config_files:
    relative=path.relative_to(ROOT/'tmp/R_leader_following')
    assert path.read_bytes()==(ROOT/'tmp/S_layer_anchor'/relative).read_bytes()
archive('shared_configs.tar.gz',[(str(p.relative_to(ROOT/'tmp/R_leader_following')).replace('\\','/'),p) for p in config_files])
json_file('case_index.json',cases)
json_file('positions_references.json',traces)
json_file('diagnostic_baselines.json',list(diagnostic_baselines.values()))

def definitions(data):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(data).body if isinstance(n,(ast.ClassDef,ast.FunctionDef))}
rules={key:(ROOT/'tmp'/folder/'noa/native_rules.py').read_text(encoding='utf-8') for key,folder in METHODS.items()}
rules['P_parent']=(parent/'noa/native_rules.py').read_text(encoding='utf-8')
comparison={}
for old,new in [('P_parent','R'),('R','S'),('P_parent','S')]:
    a,b=definitions(rules[old]),definitions(rules[new]);changed=[k for k in b if b[k]!=a.get(k)]
    comparison[old+'_to_'+new]=dict(changed_definitions=changed,unchanged_definitions=[k for k in a if a[k]==b.get(k)])
    write(old+'_to_'+new+'.patch',''.join(difflib.unified_diff(rules[old].splitlines(True),rules[new].splitlines(True),fromfile=old+'/noa/native_rules.py',tofile=new+'/noa/native_rules.py')).encode('utf-8'))
assert comparison['P_parent_to_R']['changed_definitions']==['_front','_settled','_following','_fill']
assert comparison['R_to_S']['changed_definitions']==['_following']
for name in ['Vehicle','Memory','_pair_error','_decide','safe_speed']:
    assert definitions(rules['P_parent'])[name]==definitions(rules['R'])[name]==definitions(rules['S'])[name]
json_file('source_comparison.json',dict(parent_rule_sha256=freeze['source_sha256']['noa/native_rules.py'],comparisons=comparison,
    new_parameters=0,new_memory_fields=0,common_five_source_files_identical=True))

brief='''# R/S 诊断封存：形成目标仍未达到

本目录只封存校准性尝试，不替代或并入 P100、C1_P 的独立阴性结果。当前方法尚未同时满足“大规模物理编队 + 整体效率”目标；不能用交通快但未形成来掩盖这一点。

R 从最终 P 父规则 `8d112d79…` 出发，只用正投影的稳定局部队首作领航参照，并禁止自由补位移动队首。S 从 R 出发，增加实际根车道同层实车的位置参照。二者均无新增控制参数或 Memory 字段；各自8项静态 R/G 和两组六车门通过，不代表真实随机流已经成功形成。

1500 veh/h/lane、seed1/4 的四个600s需求案例均安全排空。R 的直路物理参与率只有1.845%/1.966%，车道减少上游0.123%/0.0036%、下游8.647%/10.399%；S 的直路1.696%/3.419%，上游0%/0.0275%、下游10.423%/8.336%。上游稳定参与几乎为零，偶发峰值6/10辆不能代表大规模编队。S 的可选500流量两例未启动，未继续候选或扫参。

R 虽在这两个校准种子相对既有 NOA 诊断基线缩短旅行时间，但其形成假设仍不成立；S 也没有解决低形成率。完整 PP、稳定参与、平均/峰值规模、关系断裂、旅行及分段时间都保留在各自 `report.json`，不只挑选有利指标。

## 内容及版本边界

- `R_sources.tar.gz`、`S_sources.tar.gz`：每个候选仅一份六核心源码，不复制12个案例中的重复 source 快照。公共五源码与 P 父版本逐字节一致；同一配置集合只保留在 `shared_configs.tar.gz` 一份。
- `P_parent/`、三个补丁及 `source_comparison.json`：给出 P 父8d规则与 R/S 的实际源码对照。P 的其它五核心文件复用 R 源码归档即可重建其六文件逻辑视图。
- `case_evidence.tar.gz`：R/S 各两组六车及四个高流量案例的原始 input/result/trips；四组六车另含小 positions.gz。完整大流量 positions 未复制，原机绝对路径、大小和 SHA256 见 `positions_references.json`。缺少这些原始大轨迹时，不能从本轻量包独立重算高流量 PP。
- `R/`、`S/`：完整报告、候选 manifest、静态测试源码及原 R/G/运行日志。测试源码按原字节保留，重放需恢复其源码/历史参照布局和 SUMO1.27.1 环境。
- `diagnostic_baselines.json`：H 冻结版本的同需求 NOA/H 诊断参照。NOA 行为等价验证不等于正式同源码版本配对；不可把这些校准对比标成新的正式 R/S 矩阵，更不可混入 P100。

运行 `python -B verify_bundle.py --originals` 可独立核对归档逐成员、P/R/S 六文件视图、原文件及大轨迹引用；在其它机器不带 `--originals` 仍可核验本包完整性。核验不运行仿真，不修改控制器或旧材料。
'''
write('README.md',brief.encode('utf-8'))
json_file('original_file_references.json',list(originals.values()))
loose={str(p.relative_to(DEST)).replace('\\','/'):dict(size=p.stat().st_size,sha256=sha(p)) for p in sorted(DEST.rglob('*')) if p.is_file() and p.name not in ['bundle_manifest.json','bundle_manifest.sha256','verification.json']}
bundle=dict(format_version=1,scope='R/S diagnostic archive only; no simulations, Git, controller or prior-data changes.',
    archives=archives,files=loose,source_views=source_views,case_count=len(cases),six_case_count=4,high_case_count=8,
    large_positions_copied=False,original_reference_count=len(originals),baseline_status='H equal-demand diagnostics, not same-source formal pairing; P100/C1_P separate.')
json_file('bundle_manifest.json',bundle)
write('bundle_manifest.sha256',(sha(DEST/'bundle_manifest.json')+'  bundle_manifest.json\n').encode())
total=sum(p.stat().st_size for p in DEST.rglob('*') if p.is_file())
assert total<3*1024*1024,total
print(json.dumps(dict(directory=str(DEST),bytes=total,case_count=len(cases),archive_count=len(archives),large_positions_copied=False)))
