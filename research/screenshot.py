"""Capture the actual SUMO GUI through TraCI, with an owned hidden process."""
import socket
import subprocess
import time
from research.common import ROOT, binary, lock_traci, tool_env, write_json, sha256
from research.network import SCENARIO
from research.demand import config_tree
from research.common import write_xml


def capture():
    traci=lock_traci()
    out=ROOT/'results/phase1/gui'
    out.mkdir(parents=True,exist_ok=True)
    write_xml(SCENARIO/'gui_probe.sumocfg',config_tree('empty.rou.xml','results/phase1/gui',2))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    cmd=[binary('sumo-gui'),'-c',str(SCENARIO/'gui_probe.sumocfg'),'--remote-port',str(port),
         '--start','--quit-on-end','--window-size','1600,700','--no-step-log','true']
    startup=subprocess.STARTUPINFO()
    startup.dwFlags|=subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow=subprocess.SW_HIDE
    conn=None
    files=[]
    with (out/'stdout.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen(cmd,cwd=ROOT,env=tool_env(),stdout=log,stderr=log,startupinfo=startup)
        try:
            conn=traci.connect(port=port,numRetries=20,waitBetweenRetries=.2,proc=proc)
            view=conn.gui.getIDList()[0]
            for filename,bounds in [('sumo_topology_full.png',(-20,-60,1220,80)),
                                    ('sumo_bottleneck_zoom.png',(910,-20,1080,35))]:
                target=out/filename
                target.unlink(missing_ok=True)
                conn.gui.setBoundary(view,*bounds)
                time.sleep(.2)
                conn.gui.screenshot(view,str(target),width=1600,height=700)
                conn.simulationStep()
                # SUMO renders queued screenshots before processing the next step.
                conn.simulationStep()
                files.append(target)
                # Rendering is asynchronous on Windows; do not move the viewport
                # or close the owned process before the requested PNG is complete.
                from PIL import Image
                deadline=time.monotonic()+6
                ready=False
                while time.monotonic()<deadline:
                    try:
                        with Image.open(target) as im:
                            im.verify()
                        ready=True
                        break
                    except (OSError, SyntaxError):
                        time.sleep(.1)
                if not ready:
                    raise RuntimeError(f'Timed out waiting for GUI render: {target}')
        finally:
            if conn:
                conn.close()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.terminate()
                proc.wait(timeout=10)
    report={'command':cmd,'passed':all(p.exists() for p in files),
            'files':{str(p.relative_to(ROOT)):sha256(p) if p.exists() else None for p in files},
            'purpose':'Actual SUMO GUI topology screenshots; hidden subprocess owned and closed by capture'}
    write_json(out/'capture.json',report)
    if not report['passed']:
        raise RuntimeError('SUMO screenshot missing; see GUI stdout log')
    print('Actual SUMO topology and bottleneck screenshots saved.')
