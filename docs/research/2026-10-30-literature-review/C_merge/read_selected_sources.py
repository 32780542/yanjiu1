from pathlib import Path
import requests
from pypdf import PdfReader

root = Path(__file__).parent
sources = {
    'MOBIL': 'https://www.mtreiber.de/publications/MOBIL_TRB.pdf',
    'LMRS': 'https://opentrafficsim.org/old/images/pdf/TRR_LMRS.pdf',
    'CoopMA2017': 'https://discovery.ucl.ac.uk/id/eprint/1561171/1/Heydecker_TranspResearchC.pdf',
}
for name, url in sources.items():
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        path = root / (name + '.pdf')
        path.write_bytes(response.content)
        pdf = PdfReader(path)
        text = '\n'.join(f'\n--- PDF PAGE {i+1} ---\n' + (p.extract_text() or '') for i,p in enumerate(pdf.pages))
        (root / (name + '_text.txt')).write_text(text, encoding='utf-8')
        print(name, 'pages', len(pdf.pages), 'bytes', len(response.content))
    except Exception as exc:
        print(name, type(exc).__name__, str(exc))
