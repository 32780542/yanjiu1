import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def output_path(path):
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT):
        raise ValueError(f'Output outside research root: {p}')
    return p


def read_json(path):
    return json.loads((ROOT / path).read_text(encoding='utf-8-sig'))


def write_json(path, data):
    p = output_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def settings(layer):
    return {x['name']: x['value'] for x in read_json(f'configs/{layer}.json')['parameters']}


def write_xml(path, root):
    p = output_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(p, encoding='utf-8', xml_declaration=True)


def tool_env():
    env = os.environ.copy()
    config = read_json('configs/tools.json')
    env.update(SUMO_HOME=config['sumo_home'], PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    env['PATH'] = str(Path(config['sumo_home']) / 'bin') + os.pathsep + env.get('PATH', '')
    for key in ('TEMP', 'TMP', 'TMPDIR', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'):
        env[key] = str(ROOT / 'tmp')
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    return env


def binary(name):
    return str(Path(read_json('configs/tools.json')['sumo_home']) / 'bin' / f'{name}.exe')


def command(cmd, log, timeout=60):
    result = subprocess.run(cmd, cwd=ROOT, env=tool_env(), capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout)
    write_json(log, {'command':cmd, 'cwd':str(ROOT), 'returncode':result.returncode,
                     'stdout':result.stdout, 'stderr':result.stderr})
    if result.returncode:
        raise RuntimeError(f'Command failed; see {log}: {result.stderr[-1500:]}')
    return result


def lock_traci():
    tool_root = Path(read_json('configs/tools.json')['sumo_home']) / 'tools'
    sys.path.insert(0, str(tool_root))
    os.environ.update({k:v for k,v in tool_env().items() if k in ('SUMO_HOME', 'PATH')})
    import traci
    import sumolib
    for module in (traci, sumolib):
        if not Path(module.__file__).resolve().is_relative_to(tool_root.resolve()):
            raise RuntimeError(f'Wrong tool module origin: {module.__file__}')
    return traci


def code_manifest():
    paths = [ROOT / 'run.py']
    for folder in ('research', 'perception', 'noa', 'models', 'safety', 'simulation', 'experiments', 'tests', 'scripts', 'configs'):
        paths.extend(p for p in (ROOT / folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    return {p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(paths)}
