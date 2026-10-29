import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import stat
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def native_io_path(path):
    """Return a Windows extended-length spelling for filesystem I/O only."""
    absolute = os.path.abspath(path)
    if os.name != 'nt' or absolute.startswith('\\\\?\\'):
        return absolute
    if absolute.startswith('\\\\'):
        return '\\\\?\\UNC\\' + absolute[2:]
    return '\\\\?\\' + absolute


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
    digest = hashlib.sha256()
    with open(native_io_path(path), 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def regular_file(path):
    """Check a regular file without Windows MAX_PATH truncation."""
    try:
        return stat.S_ISREG(os.lstat(native_io_path(path)).st_mode)
    except OSError:
        return False


def settings(layer):
    return {x['name']: x['value'] for x in read_json(f'configs/{layer}.json')['parameters']}


def write_xml(path, root):
    p = output_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(p, encoding='utf-8', xml_declaration=True)


def sumo_home():
    """Resolve SUMO from SUMO_HOME, a variant-relative config, or PATH."""
    configured = read_json('configs/tools.json').get('sumo_home', '')
    if configured is None:
        configured = ''
    if not isinstance(configured, str):
        raise ValueError('configs/tools.json sumo_home must be a string')
    selected = os.environ.get('SUMO_HOME', '').strip() or configured.strip()
    if selected:
        candidate = Path(selected).expanduser()
        if not candidate.is_absolute():
            candidate = ROOT / candidate
        return candidate.resolve()
    executable = shutil.which('sumo-gui.exe') or shutil.which('sumo-gui') \
        or shutil.which('sumo.exe') or shutil.which('sumo')
    if executable:
        return Path(executable).resolve().parent.parent
    raise FileNotFoundError(
        'SUMO not found; set SUMO_HOME, configure a variant-relative '
        'configs/tools.json sumo_home, or add SUMO to PATH')


def tool_env():
    env = os.environ.copy()
    home = sumo_home()
    env.update(SUMO_HOME=str(home), PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    env['PATH'] = str(home / 'bin') + os.pathsep + env.get('PATH', '')
    for key in ('TEMP', 'TMP', 'TMPDIR', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'):
        env[key] = str(ROOT / 'tmp')
    env.pop('PYTHONPATH', None)
    env.pop('PYTHONHOME', None)
    return env


def binary(name):
    home = sumo_home()
    windows = home / 'bin' / f'{name}.exe'
    return str(windows if windows.is_file() else home / 'bin' / name)


def command(cmd, log, timeout=60):
    result = subprocess.run(cmd, cwd=ROOT, env=tool_env(), capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=timeout)
    write_json(log, {'command':cmd, 'cwd':str(ROOT), 'returncode':result.returncode,
                     'stdout':result.stdout, 'stderr':result.stderr})
    if result.returncode:
        raise RuntimeError(f'Command failed; see {log}: {result.stderr[-1500:]}')
    return result


def lock_traci():
    tool_root = sumo_home() / 'tools'
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
