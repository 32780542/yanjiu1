import json
from datetime import datetime, timezone
from pathlib import Path

root = Path(__file__).parent
path = root / 'papers.json'
papers = json.loads(path.read_text(encoding='utf-8'))
by_id = {p['local_id']: p for p in papers}

p = by_id['C006']
p.update(doi='10.1016/j.trb.2007.10.004', primary_url='https://www.sciencedirect.com/science/article/abs/pii/S0191261507001312', abstract_url='https://www.sciencedirect.com/science/article/abs/pii/S0191261507001312')
p['limitation_zh'] = '宏观量驱动的换道概率不是严格局部感知控制；本轮只读摘要及出版社预览。'
p['evidence_locator'] = 'Elsevier出版社摘要与Introduction预览；TRID最初许可转载摘要；42(6):511–522。'
p = by_id['C008']
p.update(year=2021, doi='10.1016/j.trc.2021.103081')
p['limitation_zh'] = '这是模型增强而非安全证书；虚拟输入不能用于真实距离安全判断；发表年为2021，关键正文读取2023修订预印本v3，非对最终版逐式核对。'
p['evidence_locator'] += ' 最终出版题名与DOI经Crossref注册元数据核实，TRC125:103081。'
p = by_id['C012']
p.update(doi='10.3141/2188-12', primary_url='https://journals.sagepub.com/doi/10.3141/2188-12', abstract_url='https://journals.sagepub.com/doi/10.3141/2188-12')
p['limitation_zh'] = '实测短间隙不能直接移用为安全阈值；本轮摘要级，未阅读全文。'
p['evidence_locator'] = 'Sage出版社完整摘要及作者题录，TRR2188:108–118；最初TRID官方摘要。'
p = by_id['C019']
p.update(doi='10.1109/ITSC.2017.8317887', abstract_url='https://publications.ri.cmu.edu/interactive-ramp-merging-planning-in-autonomous-driving-multi-merging-leading-pgm')
p['evidence_locator'] += ' DOI与题名经Crossref注册元数据核实。'
by_id['C033']['year'] = 2015
by_id['C033']['evidence_locator'] = '出版社摘要与scope说明；online2014，正式卷期TransportReviews35(6):775–797（2015）。'

stamp = datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')
for p in papers:
    p['verified_utc'] = stamp

required = ['local_id','title','authors','year','doi','primary_url','abstract_url','access_level','verified_utc','topic','abstract_summary_zh','information_requirement','relevance','transfer_idea_zh','limitation_zh','evidence_locator']
assert len(papers) == 50
assert len({p['title'].casefold() for p in papers}) == 50
dois = [p['doi'].casefold() for p in papers if p['doi']]
assert len(dois) == len(set(dois))
assert all(all(k in p for k in required) for p in papers)
assert all(p['local_id'] == f'C{i:03d}' for i,p in enumerate(papers,1))
assert all(p['information_requirement'] in ['sensing_only','v2v','global','mixed','unclear'] for p in papers)
assert all(p['relevance'] in ['current_fit','adaptable','background'] for p in papers)
path.write_text(json.dumps(papers, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
report = {
    'count': len(papers), 'full_text_key_sections': sum(p['access_level']=='full_text' for p in papers),
    'abstract': sum(p['access_level']=='abstract' for p in papers),
    'doi_verified': len(dois), 'doi_null': [p['local_id'] for p in papers if not p['doi']],
    'title_duplicates': 0, 'doi_duplicates': 0, 'verified_utc': stamp,
    'scope': 'new bibliography files only; no controller edits, traffic experiments, or Git operations',
    'full_text_definition': 'Key relevant body sections accessed and read, not a claim of reading every page.'
}
(root/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False))
