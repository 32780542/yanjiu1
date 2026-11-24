from pathlib import Path
import requests,io,concurrent.futures
from pypdf import PdfReader
P=Path(__file__).parent
URLS={
'gunter21':'https://lab-work.github.io/download/gunter2020commercially.pdf',
'gunter19':'https://arxiv.org/pdf/1902.04983',
'li_fd21':'https://arxiv.org/pdf/2105.05380',
'hdm06':'https://www.akesting.de/download/HDM.pdf',
'trr07':'https://www.akesting.de/download/Timedelay_TRR_2007.pdf',
'liang00':'https://www.jstage.jst.go.jp/article/jsmec1997/43/3/43_3_671/_pdf',
'cui17':'https://lab-work.github.io/download/Cui2017.pdf',
'idm10':'https://arxiv.org/pdf/0912.3613',
}
def get(kv):
 k,u=kv
 try:
  r=requests.get(u,timeout=45);r.raise_for_status()
  reader=PdfReader(io.BytesIO(r.content))
  s='\n\n'.join('=== PDF PAGE '+str(i+1)+' ===\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages))
  (P/(k+'.txt')).write_text(s,encoding='utf8')
  return k,len(reader.pages),len(s),u
 except Exception as e:return k,str(e),u
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:
 for r in ex.map(get,URLS.items()):print(r)
