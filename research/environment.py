import asyncio
from datetime import timedelta
import importlib.metadata
from pathlib import Path
import platform
import socket
import subprocess
import sys
from research.common import ROOT, read_json, write_json, binary, command, lock_traci, tool_env, sha256
from research.network import SCENARIO


def probe_environment():
    traci=lock_traci()
    versions={name:importlib.metadata.version(name) for name in ('traci','sumolib','mcp','Pillow','pywin32')}
    expected={'traci':'1.27.1','sumolib':'1.27.1','mcp':'1.27.0','Pillow':'11.0.0','pywin32':'311'}
    if versions!=expected:
        raise RuntimeError(f'Tooling versions changed: {versions}; expected {expected}')
    binaries={}
    for name in ('sumo','sumo-gui','netconvert'):
        result=command([binary(name),'--version'],f'results/phase0/{name}_version.json')
        binaries[name]={'path':binary(name),'sha256':sha256(binary(name)),'version_line':result.stdout.splitlines()[0]}
        if '1.27.1' not in result.stdout.splitlines()[0]:
            raise RuntimeError(f'Unexpected SUMO version {name}')
    cfg=SCENARIO/'mcp_probe.sumocfg'
    cmd=[binary('sumo'),'-c',str(cfg),'--no-step-log','true']
    with (ROOT/'results/phase0/traci_probe.stdout.log').open('w',encoding='utf-8') as log:
        traci.start(cmd,label='environment',stdout=log)
        conn=traci.getConnection('environment')
        try:
            server_version=conn.getVersion()
            before=conn.simulation.getTime()
            dt=conn.simulation.getDeltaT()
            conn.simulationStep()
            after=conn.simulation.getTime()
            lane_widths={i:conn.lane.getWidth(i) for i in conn.lane.getIDList()}
            assert abs(dt-.1)<1e-12 and abs(after-before-.1)<1e-12
            assert all(abs(x-3.3)<1e-12 for x in lane_widths.values())
        finally:
            conn.close()
    import sumolib
    config=read_json('configs/tools.json')
    mcp_src=Path(config['mcp_server']).parent
    result={'passed':True,'python_version':sys.version,'python_executable':sys.executable,
            'isolated':bool(sys.flags.isolated),'dont_write_bytecode':sys.dont_write_bytecode,'no_site':bool(sys.flags.no_site),
            'platform':platform.platform(),'package_versions':versions,'binaries':binaries,
            'traci_module':traci.__file__,'sumolib_module':sumolib.__file__,
            'server_version':server_version,'getDeltaT_s':dt,'observed_step_s':after-before,'lane_widths_m':lane_widths,
            'SUMO_HOME':config['sumo_home'],'command':cmd,'cwd':str(ROOT),'output_temp_dir':str(ROOT/'tmp'),
            'mcp_tool_version':'0.1.0','mcp_source_hashes':{str(p):sha256(p) for p in sorted(mcp_src.rglob('*.py'))},
            'path_hazard':'Bare sumo/netconvert resolved to old 0.32.0; all new commands pin explicit 1.27.1 binaries.',
            'matlab':'Reference source unchanged; no MATLAB traffic simulation executed; GPOPS/SNOPT not required for stage 0-1.'}
    write_json('results/phase0/environment.json',result)
    print('Environment verified: SUMO/TraCI 1.27.1; getDeltaT=0.1 seconds; all lane widths=3.3 m.')


async def probe_mcp():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params=StdioServerParameters(command=sys.executable,args=['-I','-B','-S',str(ROOT/'scripts/mcp_server_entry.py')],
                                 cwd=str(ROOT),env=tool_env())
    result={'transport':'stdio','cwd':str(ROOT),'server':read_json('configs/tools.json')['mcp_server'],
            'client_args':params.args,'actions':[],'passed':False}
    with (ROOT/'results/phase0/mcp.stderr.log').open('w',encoding='utf-8') as errlog:
        try:
            async with asyncio.timeout(50):
                async with stdio_client(params,errlog=errlog) as (read,write):
                    async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=12)) as session:
                        init=await session.initialize()
                        result['initialize']=init.model_dump(mode='json')
                        listing=await session.list_tools()
                        result['tool_names']=[x.name for x in listing.tools]
                        async def call(name,args):
                            response=await session.call_tool(name,args)
                            item=response.model_dump(mode='json')
                            result['actions'].append({'name':name,'arguments':args,'response':item})
                            text='\n'.join(x.get('text','') for x in item['content'])
                            if item.get('isError') or 'Error:' in text or text.startswith('Error'):
                                raise RuntimeError(text)
                            return text
                        info=await call('get_sumo_info',{})
                        if '1.27.1' not in info or 'yanjiu1' not in info:
                            raise RuntimeError('MCP resolved wrong SUMO')
                        with socket.socket() as sock:
                            sock.bind(('127.0.0.1',0))
                            port=sock.getsockname()[1]
                        connected=False
                        try:
                            await call('control_simulation',{'action':'connect','params':{
                                'config_file':str(SCENARIO/'mcp_probe.sumocfg'),'gui':False,'port':port,'timeout_s':8}})
                            connected=True
                            await call('control_simulation',{'action':'step','params':{'step':0.1}})
                            await call('query_simulation_state',{'target':'simulation'})
                        finally:
                            if connected:
                                await call('control_simulation',{'action':'disconnect'})
                        result['passed']=True
        except Exception as exc:
            result['error']=repr(exc)
        finally:
            write_json('results/phase0/mcp_probe.json',result)
    if not result['passed']:
        raise RuntimeError('MCP verification failed; inspect results/phase0/mcp_probe.json and mcp.stderr.log')
    print('MCP verified: initialize, list_tools, SUMO 1.27.1 info, connect, step, state, disconnect.')
