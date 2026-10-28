"""Read-only installed MCP tool, isolated from all parent research modules."""
import json
import os
from pathlib import Path
import runpy
import sys
import sysconfig

root=Path(__file__).resolve().parents[1]
config=json.loads((root/'configs/tools.json').read_text(encoding='utf-8'))
server=Path(config['mcp_server'])
sys.path[:0]=[str(server.parent),str(Path(config['sumo_home'])/'tools')]
sys.path.append(sysconfig.get_path('purelib'))
site_packages=Path(sysconfig.get_path('purelib'))
sys.path.extend(str(site_packages/p) for p in ('win32','win32/lib'))
DLL_HANDLES=[os.add_dll_directory(str(site_packages/'pywin32_system32'))]
os.chdir(root)
os.environ['SUMO_HOME']=config['sumo_home']
os.environ['PYTHONDONTWRITEBYTECODE']='1'
for key in ('TEMP','TMP','TMPDIR'):
    os.environ[key]=str(root/'tmp')
runpy.run_path(str(server),run_name='__main__')
