import json,re,hashlib
from pathlib import Path
from collections import Counter
from urllib.parse import urlparse
P=Path(__file__).parent
data=json.loads((P/'papers.json').read_text('utf8'))
required='local_id title authors year doi primary_url abstract_url access_level verified_utc topic abstract_summary_zh information_requirement relevance transfer_idea_zh limitation_zh evidence_locator'.split()
errors=[]
for i,d in enumerate(data,1):
    if d.get('local_id')!=f'A{i:03d}': errors.append(f'Bad ID at {i}')
    for k in required:
        if k not in d:errors.append(f'{i}: missing {k}')
        elif k!='doi' and (d[k] is None or d[k]==''): errors.append(f'{i}: empty {k}')
    if d.get('access_level') not in {'metadata','abstract','full_text'}:errors.append(f'{i}: invalid reading depth')
    if d.get('information_requirement') not in {'sensing_only','v2v','global','mixed','unclear'}:errors.append(f'{i}: invalid information requirement')
    if d.get('relevance') not in {'current_fit','adaptable','background'}:errors.append(f'{i}: invalid relevance')
    if not 1900<=d.get('year',0)<=2026:errors.append(f'{i}: invalid year')
    for k in ['primary_url','abstract_url']:
        if urlparse(d.get(k,'')).scheme not in {'http','https'}: errors.append(f'{i}: invalid {k}')
    if d.get('doi') and not re.fullmatch(r'10\.\d{4,9}/\S+',d['doi'],re.I):errors.append(f'{i}: invalid DOI shape')
for key in ['local_id','doi']:
    values=[str(d[key]).casefold() for d in data if d[key] is not None]
    if len(values)!=len(set(values)):errors.append(f'duplicate {key}')
titles=[re.sub(r'\W','',d['title']).casefold() for d in data]
if len(titles)!=len(set(titles)):errors.append('duplicate normalized titles')
manifest={}
for f in sorted(P.glob('*.txt')):
    b=f.read_bytes();manifest[f.name]={'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}
report={'records':len(data),'reading_depth':dict(Counter(d['access_level'] for d in data)),'information_requirements':dict(Counter(d['information_requirement'] for d in data)),'unique_normalized_titles':len(set(titles)),'nonempty_unique_dois':len({d['doi'].casefold() for d in data if d['doi']}),'errors':errors,'text_snapshot_manifest':manifest,'scope':'Only A_acc research outputs written; no production/test/old research files intentionally modified; no Git or simulation run.'}
(P/'validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
lines=['# 主题A书目速览','','详尽摘要、迁移条件和一手入口见papers.json；正文限定条件见synthesis.md。','','| ID | 年 | 题名 | 阅读深度 |','|---|---:|---|---|']
for d in data:lines.append(f"| {d['local_id']} | {d['year']} | [{d['title']}]({d['primary_url']}) | {d['access_level']} |")
(P/'bibliography.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
print(json.dumps({k:v for k,v in report.items() if k!='text_snapshot_manifest'},ensure_ascii=False,indent=2))
print('Text snapshots:',len(manifest),'bytes:',sum(x['bytes'] for x in manifest.values()))
assert not errors,errors
