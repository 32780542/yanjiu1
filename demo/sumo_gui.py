"""SUMO GUI demonstration helpers, isolated from the research entry point."""
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import traceback
import uuid
import xml.etree.ElementTree as ET
from collections.abc import Iterator, Mapping
from itertools import chain


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALGORITHM_RUN_REL = Path(
    'variants/phase5f_adaptive_duration/results/phase5_r5/runs/'
    '20260913T162400652574Z_9f6cc9d8'
)
EVIDENCE_MANIFEST_SHA256 = (
    'da5f87a7abb899fa8c92aaf32696d9f2b275452452703e4e6c3ed70208a23e03'
)
SIMPLE_VARIANT_REL = Path('variants/phase5g_pure_formation')
SIMPLE_OUTPUT_BASE = Path('results/phase5g/simple_gui_sources')


@dataclass(frozen=True, slots=True)
class DemoConfig:
    vehicle_count: int = 30
    depart_interval_s: float = 0.8
    vehicle_speed_mps: float = 12.0
    simulation_duration_s: float = 120.0
    gui_delay_ms: int = 40
    auto_zoom: bool = True
    wait_before_close: bool = True
    algorithm_case: str = 'r5c_gradual_three_r5_on'


@dataclass(frozen=True, slots=True)
class SimpleFormationDemoConfig:
    vehicle_count: int = 6
    target_speed_mps: float = 10.0
    random_seed: int = 1
    simulation_duration_s: float = 45.0
    show_gui: bool = True
    gui_delay_ms: int = 40
    auto_zoom: bool = True
    wait_before_close: bool = True
    local_formation_range_m: float = 90.0
    adjacent_lane_gap_m: float = 15.0
    same_lane_gap_m: float = 30.0
    position_tolerance_m: float = 2.0
    formation_accel_limit_mps2: float = 0.5
    max_formation_lane_changes: int = 1


@dataclass(frozen=True, slots=True)
class CheckedPaths:
    root: Path
    sumo_gui: Path
    network: Path
    algorithm_run: Path
    sumo_home: Path


@dataclass(frozen=True, slots=True)
class SimpleCheckedPaths:
    root: Path
    variant_root: Path
    variant_run: Path
    variant_results: Path
    sumo_home: Path
    sumo_gui: Path
    network: Path
    traci_python: Path


@dataclass(frozen=True, slots=True)
class TraceSource:
    case_name: str
    case_dir: Path
    trace_path: Path
    metadata: Mapping
    validation: Mapping
    evidence_status: str
    actors: tuple[str, ...]
    verified_trace_bytes: bytes | None = None
    trace_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class GeneratedSimpleTrace:
    outer_path: Path
    source: TraceSource


@dataclass(frozen=True, slots=True)
class TraceFrame:
    time_s: float
    states: Mapping[str, Mapping[str, float]]


@dataclass(frozen=True, slots=True)
class PlaybackStats:
    frames_played: int
    final_time_s: float
    colliding_vehicle_reports: int
    teleport_starts: int
    end_reason: str


def _finite_number(name, value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f'{name} 必须是数字，允许范围 {minimum}–{maximum}')
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError(f'{name} 必须是有限数字，允许范围 {minimum}–{maximum}')


def validate_config(config: DemoConfig, root: Path = PROJECT_ROOT) -> CheckedPaths:
    """Validate editable settings and resolve every required external path."""
    root = Path(root).resolve()
    if isinstance(config.vehicle_count, bool) or not isinstance(config.vehicle_count, int):
        raise ValueError('VEHICLE_COUNT 必须是整数，允许范围 1–5000')
    if not 1 <= config.vehicle_count <= 5000:
        raise ValueError('VEHICLE_COUNT 必须在 1–5000 之间')
    _finite_number('DEPART_INTERVAL_S', config.depart_interval_s, 0.1, 60.0)
    _finite_number('VEHICLE_SPEED_MPS', config.vehicle_speed_mps, 0.1, 33.3)
    _finite_number('SIMULATION_DURATION_S', config.simulation_duration_s, 1.0, 3600.0)
    if isinstance(config.gui_delay_ms, bool) or not isinstance(config.gui_delay_ms, int):
        raise ValueError('GUI_DELAY_MS 必须是整数，允许范围 0–1000')
    if not 0 <= config.gui_delay_ms <= 1000:
        raise ValueError('GUI_DELAY_MS 必须在 0–1000 之间')
    if not isinstance(config.auto_zoom, bool):
        raise ValueError('AUTO_ZOOM 必须是 True 或 False')
    if not isinstance(config.wait_before_close, bool):
        raise ValueError('WAIT_BEFORE_CLOSE 必须是 True 或 False')
    if not isinstance(config.algorithm_case, str) or not config.algorithm_case.strip():
        raise ValueError('ALGORITHM_CASE 必须是非空案例名')
    last_departure = (config.vehicle_count - 1) * config.depart_interval_s
    if last_departure >= config.simulation_duration_s:
        raise ValueError(
            'SIMULATION_DURATION_S 必须大于最后一辆车的发车时刻 '
            f'{last_departure:g} 秒'
        )

    tools_path = root / 'configs' / 'tools.json'
    if not tools_path.is_file():
        raise FileNotFoundError(f'缺少SUMO登记文件: {tools_path}')
    try:
        tools = json.loads(tools_path.read_text(encoding='utf-8-sig'))
        sumo_home = Path(tools['sumo_home']).resolve()
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f'无法读取 {tools_path} 中的 sumo_home: {error}') from error
    sumo_gui = sumo_home / 'bin' / 'sumo-gui.exe'
    if not sumo_gui.is_file():
        raise FileNotFoundError(f'缺少登记的SUMO界面程序: {sumo_gui}')
    network = root / 'scenarios' / 'cai2024' / 'bottleneck.net.xml'
    if not network.is_file():
        raise FileNotFoundError(f'缺少瓶颈路网: {network}')
    algorithm_run = root / ALGORITHM_RUN_REL
    if not algorithm_run.is_dir():
        raise FileNotFoundError(f'缺少阶段5F正式运行目录: {algorithm_run}')
    return CheckedPaths(root, sumo_gui, network, algorithm_run, sumo_home)


def validate_simple_config(
        config: SimpleFormationDemoConfig,
        root: Path = PROJECT_ROOT) -> SimpleCheckedPaths:
    """Validate simple-formation settings without opening legacy results."""
    if type(config.vehicle_count) is not int or config.vehicle_count not in (3, 6, 12):
        raise ValueError('VEHICLE_COUNT 必须是整数 3、6 或 12')
    _finite_number('TARGET_SPEED_MPS', config.target_speed_mps, 0.0, math.inf)
    if config.target_speed_mps <= 0:
        raise ValueError('TARGET_SPEED_MPS 必须是正的有限数字')
    if type(config.random_seed) is not int or not 0 <= config.random_seed < 2**64:
        raise ValueError('RANDOM_SEED 必须是精确的 uint64 整数（不接受 bool）')
    _finite_number(
        'SIMULATION_DURATION_S', config.simulation_duration_s, 0.0, math.inf)
    if config.simulation_duration_s <= 0:
        raise ValueError('SIMULATION_DURATION_S 必须是正的有限数字')
    intervals = round(config.simulation_duration_s / 0.1)
    if not math.isclose(intervals * 0.1, config.simulation_duration_s,
                        abs_tol=1e-9, rel_tol=0.0):
        raise ValueError('SIMULATION_DURATION_S 必须是 0.1 秒的完整倍数')
    if type(config.show_gui) is not bool:
        raise ValueError('SHOW_GUI 必须是 True 或 False')
    if type(config.gui_delay_ms) is not int or not 0 <= config.gui_delay_ms <= 1000:
        raise ValueError('GUI_DELAY_MS 必须是 0–1000 的整数（不接受 bool）')
    if type(config.auto_zoom) is not bool:
        raise ValueError('AUTO_ZOOM 必须是 True 或 False')
    if type(config.wait_before_close) is not bool:
        raise ValueError('WAIT_BEFORE_CLOSE 必须是 True 或 False')
    for name, value in (
            ('LOCAL_FORMATION_RANGE_M', config.local_formation_range_m),
            ('ADJACENT_LANE_GAP_M', config.adjacent_lane_gap_m),
            ('SAME_LANE_GAP_M', config.same_lane_gap_m),
            ('POSITION_TOLERANCE_M', config.position_tolerance_m),
            ('FORMATION_ACCEL_LIMIT_MPS2', config.formation_accel_limit_mps2)):
        _finite_number(name, value, 0.0, math.inf)
        if value <= 0:
            raise ValueError(f'{name} 必须是正的有限数字')
    if type(config.max_formation_lane_changes) is not int \
            or config.max_formation_lane_changes != 1:
        raise ValueError('MAX_FORMATION_LANE_CHANGES 必须是整数 1（不接受 bool）')

    root = Path(root).resolve()
    tools_path = root / 'configs' / 'tools.json'
    if not tools_path.is_file():
        raise FileNotFoundError(f'缺少SUMO登记文件: {tools_path}')
    try:
        tools = json.loads(tools_path.read_text(encoding='utf-8-sig'))
        sumo_home = Path(tools['sumo_home']).resolve()
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f'无法读取 {tools_path} 中的 sumo_home: {error}') from error
    sumo_gui = sumo_home / 'bin' / 'sumo-gui.exe'
    traci_python = sumo_home / 'tools' / 'traci' / '__init__.py'
    network = root / 'scenarios' / 'cai2024' / 'bottleneck.net.xml'
    variant_root = root / SIMPLE_VARIANT_REL
    variant_run = variant_root / 'run.py'
    variant_results = variant_root / 'results'
    for label, path, kind in (
            ('登记的SUMO界面程序', sumo_gui, 'file'),
            ('SUMO TraCI入口', traci_python, 'file'),
            ('瓶颈路网', network, 'file'),
            ('Phase5G入口', variant_run, 'file'),
            ('Phase5G结果根目录', variant_results, 'dir')):
        exists = path.is_file() if kind == 'file' else path.is_dir()
        if not exists:
            raise FileNotFoundError(f'缺少{label}: {path}')
    return SimpleCheckedPaths(
        root=root, variant_root=variant_root.resolve(),
        variant_run=variant_run.resolve(), variant_results=variant_results.resolve(),
        sumo_home=sumo_home, sumo_gui=sumo_gui.resolve(),
        network=network.resolve(), traci_python=traci_python.resolve())


def format_number(value: float) -> str:
    return format(value, '.12g')


def native_routes_tree(config: DemoConfig) -> ET.Element:
    """Build deterministic native SUMO demand from the editable settings."""
    routes = ET.Element('routes')
    ET.SubElement(
        routes, 'vType', id='native_demo', vClass='passenger', guiShape='passenger',
        carFollowModel='IDM', laneChangeModel='LC2013', length='4', width='1.8',
        maxSpeed='33.3', accel='2.6', decel='4.5', emergencyDecel='9',
        tau='1', minGap='2.5', speedFactor='1', speedDev='0')
    ET.SubElement(routes, 'route', id='through', edges='upstream downstream')
    for index in range(config.vehicle_count):
        ET.SubElement(
            routes, 'vehicle', id=f'demo_{index:04d}', type='native_demo',
            route='through', depart=format_number(index * config.depart_interval_s),
            departLane=str(index % 3), departPos='base',
            departSpeed=format_number(config.vehicle_speed_mps))
    return routes


def sumo_config_tree(network: Path, route_name: str, output_dir: Path,
                     end_s: float) -> ET.Element:
    """Build a GUI-ready configuration whose outputs stay in one attempt."""
    network = Path(network).resolve()
    output_dir = Path(output_dir).resolve()
    tree = ET.Element('configuration')
    inputs = ET.SubElement(tree, 'input')
    ET.SubElement(inputs, 'net-file', value=str(network))
    ET.SubElement(inputs, 'route-files', value=route_name)
    times = ET.SubElement(tree, 'time')
    ET.SubElement(times, 'begin', value='0')
    ET.SubElement(times, 'end', value=format_number(end_s))
    ET.SubElement(times, 'step-length', value='0.1')
    processing = ET.SubElement(tree, 'processing')
    ET.SubElement(processing, 'lanechange.duration', value='3')
    ET.SubElement(processing, 'time-to-teleport', value='-1')
    ET.SubElement(processing, 'max-depart-delay', value='-1')
    ET.SubElement(processing, 'collision.action', value='warn')
    ET.SubElement(processing, 'collision.check-junctions', value='true')
    random_number = ET.SubElement(tree, 'random_number')
    ET.SubElement(random_number, 'seed', value='20260914')
    outputs = ET.SubElement(tree, 'output')
    for key, filename in (
            ('tripinfo-output', 'tripinfo.xml'),
            ('summary-output', 'summary.xml'),
            ('lanechange-output', 'lanechanges.xml')):
        ET.SubElement(outputs, key, value=str(output_dir / filename))
    ET.SubElement(outputs, 'tripinfo-output.write-unfinished', value='true')
    report = ET.SubElement(tree, 'report')
    ET.SubElement(report, 'no-step-log', value='true')
    ET.SubElement(report, 'log', value=str(output_dir / 'sumo.log'))
    return tree


def create_run_directory(root: Path, mode: str, *, stamp: str | None = None,
                         token: str | None = None) -> Path:
    """Allocate one append-only demonstration attempt directory."""
    if mode not in {'algorithm', 'native', 'simple_formation'}:
        raise ValueError(f'未知演示模式: {mode}')
    stamp = stamp or datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    token = token or uuid.uuid4().hex[:8]
    path = Path(root).resolve() / 'results' / 'demo_runs' / f'{stamp}_{mode}_{token}'
    path.mkdir(parents=True, exist_ok=False)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f'无法读取JSON文件 {path}: {error}') from error


def verify_relative_hash(base: Path, hashes: Mapping[str, str], relative: str) -> Path:
    """Verify one evidence file without permitting a path outside its run."""
    base = Path(base).resolve()
    path = (base / Path(relative)).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f'证据路径越界: {relative}')
    expected = hashes.get(relative)
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError(f'证据清单缺少有效SHA-256: {relative}')
    if not path.is_file():
        raise FileNotFoundError(f'证据文件缺失: {path}')
    actual = sha256_file(path)
    if actual != expected.lower():
        raise ValueError(
            f'证据SHA-256不一致: {relative}; expected={expected}; actual={actual}')
    return path


def load_trace_source(root: Path, case_name: str) -> TraceSource:
    """Open one finalized Phase5F case only after verifying sealed hashes."""
    if not isinstance(case_name, str) or not case_name.strip() \
            or Path(case_name).name != case_name \
            or any(separator in case_name for separator in ('/', '\\')):
        raise ValueError(f'ALGORITHM_CASE 不是安全的案例名: {case_name!r}')
    root = Path(root).resolve()
    run = root / ALGORITHM_RUN_REL
    manifest_path = run / 'evidence_hashes.json'
    if not manifest_path.is_file():
        raise FileNotFoundError(f'阶段5F证据清单缺失: {manifest_path}')
    manifest_actual = sha256_file(manifest_path)
    if manifest_actual != EVIDENCE_MANIFEST_SHA256:
        raise ValueError(
            '阶段5F evidence_hashes.json SHA-256不一致; '
            f'expected={EVIDENCE_MANIFEST_SHA256}; actual={manifest_actual}')
    hashes = _read_json(manifest_path)
    case_index_path = verify_relative_hash(run, hashes, 'case_index.json')
    case_index = _read_json(case_index_path)
    expected_cases = case_index.get('expected_variants', {})
    if case_name not in expected_cases:
        available = ', '.join(sorted(expected_cases))
        raise ValueError(f'ALGORITHM_CASE 不存在: {case_name!r}; 可选: {available}')
    if case_name not in case_index.get('finalized_variants', []):
        raise ValueError(f'ALGORITHM_CASE 尚未封存完成: {case_name}')

    prefix = f'cases/{case_name}'
    metadata_path = verify_relative_hash(run, hashes, f'{prefix}/metadata.json')
    trace_path = verify_relative_hash(run, hashes, f'{prefix}/trace.jsonl')
    validation_path = verify_relative_hash(run, hashes, f'{prefix}/validation.json')
    metadata = _read_json(metadata_path)
    validation = _read_json(validation_path)
    try:
        with trace_path.open(encoding='utf-8') as stream:
            first = json.loads(next(stream))
        initial = first['initial']
        actors = tuple(sorted(initial))
        if not actors:
            raise ValueError('initial车辆集合为空')
    except (OSError, StopIteration, json.JSONDecodeError, KeyError, TypeError) as error:
        raise ValueError(f'阶段5F trace首行无效: {trace_path}: {error}') from error
    evidence_status = metadata.get('execution_status')
    if not isinstance(evidence_status, str):
        value = validation.get('status')
        evidence_status = value if isinstance(value, str) else 'unknown'
    return TraceSource(case_name, metadata_path.parent, trace_path, metadata,
                       validation, evidence_status, actors)


def _frame_time(states: Mapping[str, Mapping[str, float]]) -> float:
    times = []
    for actor, state in states.items():
        try:
            value = float(state['time_s'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f'{actor} 缺少有效time_s') from error
        if not math.isfinite(value):
            raise ValueError(f'{actor} 的time_s不是有限数')
        times.append(value)
    if not times or any(not math.isclose(value, times[0], abs_tol=1e-9)
                        for value in times[1:]):
        raise ValueError('同一轨迹帧的车辆时间不一致')
    return times[0]


def iter_trace_frames(source: TraceSource) -> Iterator[TraceFrame]:
    """Yield initial and completed control-frame states, preserving failed tails."""
    expected_actors = set(source.actors)
    saw_initial = False
    previous_time = -math.inf
    if source.verified_trace_bytes is None:
        stream = source.trace_path.open(encoding='utf-8')
    else:
        actual_digest = hashlib.sha256(source.verified_trace_bytes).hexdigest()
        if source.trace_sha256 != actual_digest:
            raise RuntimeError('不可变trace字节与保存的SHA-256不一致')
        stream = io.StringIO(source.verified_trace_bytes.decode('utf-8'))
    with stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise ValueError(f'trace.jsonl 第{line_number}行为空')
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f'trace.jsonl 第{line_number}行不是有效JSON') from error
            if not saw_initial:
                initial = record.get('initial')
                if not isinstance(initial, dict) or set(initial) != expected_actors:
                    raise ValueError('trace初始车辆集合与metadata不一致')
                previous_time = _frame_time(initial)
                yield TraceFrame(previous_time, initial)
                saw_initial = True
            status = record.get('status')
            if status != 'completed':
                if status in {'running', 'initializing'} and not record.get('steps'):
                    continue
                break
            steps = record.get('steps')
            if not isinstance(steps, dict) or set(steps) != expected_actors:
                raise ValueError(f'trace第{line_number}行车辆集合不一致')
            try:
                states = {actor: steps[actor]['final'] for actor in source.actors}
            except (KeyError, TypeError) as error:
                raise ValueError(f'trace第{line_number}行缺少final状态') from error
            time_s = _frame_time(states)
            if time_s <= previous_time:
                raise ValueError(f'trace第{line_number}行时间未严格递增')
            yield TraceFrame(time_s, states)
            previous_time = time_s
    if not saw_initial:
        raise ValueError('trace.jsonl 没有轨迹记录')


_SOURCE_ANCHOR_FIELDS = frozenset({
    'schema', 'run_id', 'source_manifest_sha256', 'input_manifest_sha256',
    'source_hashes', 'input_hashes', 'code_snapshot_manifest',
    'input_snapshot_manifest', 'case_file_sha256', 'mode_registry_sha256',
})
_COMPLETION_ANCHOR_FIELDS = frozenset({
    'schema', 'run_id', 'outer_schema', 'source_anchor_schema',
    'source_anchor_sha256', 'source_manifest_sha256', 'input_manifest_sha256',
    'child_directory', 'child_manifest', 'child_manifest_sha256',
    'outer_evidence_hashes', 'outer_evidence_manifest_sha256',
    'outer_evidence_file_sha256',
})
_HEX_DIGITS = frozenset('0123456789abcdef')


def _json_digest(value) -> str:
    try:
        payload = (json.dumps(
            value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
            allow_nan=False) + '\n').encode('utf-8')
    except (TypeError, ValueError) as error:
        raise RuntimeError(f'信任材料不能规范化为JSON: {error}') from error
    return hashlib.sha256(payload).hexdigest()


def _reject_json_constant(value):
    raise ValueError(f'禁止非有限JSON常量 {value}')


def _read_strict_object(path: Path, label: str, fields=None) -> dict:
    try:
        value = json.loads(
            Path(path).read_text(encoding='utf-8-sig'),
            parse_constant=_reject_json_constant)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(f'{label}不是有效JSON对象: {error}') from error
    if not isinstance(value, dict):
        raise RuntimeError(f'{label}必须是JSON对象')
    if fields is not None:
        missing = sorted(set(fields) - set(value))
        extra = sorted(set(value) - set(fields))
        if missing:
            raise RuntimeError(f'{label}缺少字段: {missing}')
        if extra:
            raise RuntimeError(f'{label}存在额外字段: {extra}')
    return value


def _is_reparse(info) -> bool:
    return bool(getattr(info, 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))


def _lstat_no_reparse(path: Path, boundary: Path, label: str):
    """Inspect one lexical path under a boundary before any resolving occurs."""
    target = Path(os.path.abspath(path))
    base = Path(os.path.abspath(boundary))
    try:
        relative = target.relative_to(base)
    except ValueError as error:
        raise RuntimeError(f'{label}越界: {target}') from error
    current = base
    for part in (Path('.'), *relative.parts):
        if part != Path('.'):
            current /= part
        try:
            info = os.lstat(current)
        except OSError as error:
            raise RuntimeError(f'{label}缺失: {target}') from error
        if current.is_symlink() or _is_reparse(info):
            raise RuntimeError(f'{label}禁止符号链接、junction或reparse point: {current}')
    return target, base, info


def _require_regular_file(path: Path, boundary: Path, label: str) -> Path:
    """Require a real regular file and reject reparse points in its path."""
    target, _, info = _lstat_no_reparse(path, boundary, label)
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError(f'{label}不是普通文件: {target}')
    return target


def _resolve_result_directory(path: Path, boundary: Path, label: str) -> Path:
    """Reject lexical reparse paths, then resolve a result directory in bounds."""
    target, base, info = _lstat_no_reparse(path, boundary, label)
    if not stat.S_ISDIR(info.st_mode):
        raise RuntimeError(f'{label}不是目录: {target}')
    resolved = target.resolve(strict=True)
    resolved_base = base.resolve(strict=True)
    if resolved == resolved_base or not resolved.is_relative_to(resolved_base):
        raise RuntimeError(f'{label}越界: {resolved}')
    return resolved


def _regular_file_manifest(path: Path, label: str) -> dict[str, dict[str, str]]:
    """Describe one exact regular-file tree without following reparse points."""
    root = Path(os.path.abspath(path))
    try:
        root_info = os.lstat(root)
    except OSError as error:
        raise RuntimeError(f'{label}目录缺失: {root}') from error
    if root.is_symlink() or _is_reparse(root_info):
        raise RuntimeError(f'{label}根目录禁止符号链接、junction或reparse point')
    if not stat.S_ISDIR(root_info.st_mode):
        raise RuntimeError(f'{label}不是目录: {root}')
    files = {}
    folded = {}

    def visit(folder: Path):
        try:
            entries = sorted(os.scandir(folder), key=lambda item: item.name)
        except OSError as error:
            raise RuntimeError(f'{label}无法枚举目录: {folder}') from error
        for entry in entries:
            candidate = Path(os.path.abspath(entry.path))
            try:
                relative = candidate.relative_to(root).as_posix()
            except ValueError as error:
                raise RuntimeError(f'{label}路径越界: {candidate}') from error
            try:
                info = entry.stat(follow_symlinks=False)
            except OSError as error:
                raise RuntimeError(f'{label}.{relative}无法读取属性') from error
            if entry.is_symlink() or _is_reparse(info):
                raise RuntimeError(
                    f'{label}.{relative}禁止符号链接、junction或reparse point')
            if stat.S_ISDIR(info.st_mode):
                visit(candidate)
            elif stat.S_ISREG(info.st_mode):
                collision = folded.get(relative.casefold())
                if collision is not None and collision != relative:
                    raise RuntimeError(
                        f'{label}存在大小写路径冲突: {collision}, {relative}')
                folded[relative.casefold()] = relative
                files[relative] = {
                    'sha256': sha256_file(candidate), 'type': 'regular'}
            else:
                raise RuntimeError(f'{label}.{relative}不是普通文件')

    visit(root)
    return files


def _valid_digest(value) -> bool:
    return (type(value) is str and len(value) == 64
            and set(value).issubset(_HEX_DIGITS))


def _safe_relative_name(name, label: str) -> str:
    if type(name) is not str or not name or '\\' in name:
        raise RuntimeError(f'{label}含无效相对路径: {name!r}')
    path = Path(name)
    if path.is_absolute() or path.as_posix() != name \
            or any(part in ('', '.', '..') for part in path.parts):
        raise RuntimeError(f'{label}含越界或非规范路径: {name!r}')
    return name


def _validate_snapshot_manifest(value, label: str) -> dict:
    if not isinstance(value, dict) or not value:
        raise RuntimeError(f'{label}必须是非空JSON对象')
    folded = {}
    for name, entry in value.items():
        _safe_relative_name(name, label)
        collision = folded.get(name.casefold())
        if collision is not None and collision != name:
            raise RuntimeError(f'{label}存在大小写路径冲突: {collision}, {name}')
        folded[name.casefold()] = name
        if not isinstance(entry, dict):
            raise RuntimeError(f'{label}.{name}必须是JSON对象')
        missing = sorted({'sha256', 'type'} - set(entry))
        extra = sorted(set(entry) - {'sha256', 'type'})
        if missing or extra:
            raise RuntimeError(
                f'{label}.{name}字段不精确: missing={missing}; extra={extra}')
        if entry['type'] != 'regular' or not _valid_digest(entry['sha256']):
            raise RuntimeError(f'{label}.{name}必须绑定普通文件和小写SHA-256')
    return value


def _validate_hash_map(value, label: str) -> dict:
    if not isinstance(value, dict) or not value:
        raise RuntimeError(f'{label}必须是非空JSON对象')
    for name, digest in value.items():
        _safe_relative_name(name, label)
        if not _valid_digest(digest):
            raise RuntimeError(f'{label}.{name}不是小写SHA-256')
    return value


def _bind_hash_map(hashes: dict, manifest: dict, label: str) -> None:
    for name, digest in hashes.items():
        entry = manifest.get(name)
        if not isinstance(entry, dict) or entry.get('sha256') != digest \
                or entry.get('type') != 'regular':
            raise RuntimeError(f'{label}.{name}与snapshot manifest不一致')


def _verify_sealed_directory(path: Path) -> Mapping[str, str]:
    """Verify one exact regular-file tree against its local evidence seal."""
    root = Path(os.path.abspath(path))
    manifest_path = root / 'evidence_hashes.json'
    actual = _regular_file_manifest(root, '证据目录')
    if 'evidence_hashes.json' not in actual:
        raise RuntimeError('证据目录缺少 evidence_hashes.json')
    hashes = _read_strict_object(manifest_path, 'evidence_hashes.json')
    expected = {
        name: entry['sha256'] for name, entry in actual.items()
        if name != 'evidence_hashes.json'
    }
    if hashes != expected:
        missing = sorted(set(expected) - set(hashes))
        extra = sorted(set(hashes) - set(expected))
        changed = sorted(
            name for name in set(expected) & set(hashes)
            if expected[name] != hashes[name])
        raise RuntimeError(
            '证据清单不一致: '
            f'missing={missing}; extra={extra}; changed={changed}')
    return hashes


def _verify_simple_trust(
        outer: Path, paths: SimpleCheckedPaths) -> tuple[dict, str]:
    """Verify sibling content-integrity anchors, not signatures, before child parsing."""
    trust = outer.parent / '.phase5g-trust'
    source_path = _require_regular_file(
        trust / f'{outer.name}.json', paths.variant_results,
        'source anchor')
    completion_path = _require_regular_file(
        trust / f'{outer.name}.completion.json', paths.variant_results,
        'completion anchor')
    source = _read_strict_object(
        source_path, 'source anchor', _SOURCE_ANCHOR_FIELDS)
    completion = _read_strict_object(
        completion_path, 'completion anchor', _COMPLETION_ANCHOR_FIELDS)
    if source['schema'] != 'phase5g_external_trust_anchor_v2' \
            or source['run_id'] != outer.name:
        raise RuntimeError('source anchor的schema或run_id不一致')
    if completion['schema'] != 'phase5g_simple_demo_completion_anchor_v1' \
            or completion['run_id'] != outer.name \
            or completion['outer_schema'] != 'phase5g_simple_demo_v1' \
            or completion['source_anchor_schema'] != source['schema'] \
            or completion['child_directory'] != 'case':
        raise RuntimeError('completion anchor的schema、run_id或child_directory不一致')
    if completion['source_anchor_sha256'] != sha256_file(source_path):
        raise RuntimeError('completion anchor的source anchor SHA-256不一致')
    for name in ('source_manifest_sha256', 'input_manifest_sha256'):
        if completion[name] != source[name] or not _valid_digest(source[name]):
            raise RuntimeError(f'completion anchor与source anchor的{name}不一致')

    code_manifest = _validate_snapshot_manifest(
        _read_strict_object(
            outer / 'code_snapshot_manifest.json',
            'code snapshot manifest'),
        'code snapshot manifest')
    input_manifest = _validate_snapshot_manifest(
        _read_strict_object(
            outer / 'input_snapshot_manifest.json',
            'input snapshot manifest'),
        'input snapshot manifest')
    anchored_code_manifest = _validate_snapshot_manifest(
        source['code_snapshot_manifest'], 'source anchor.code snapshot manifest')
    anchored_input_manifest = _validate_snapshot_manifest(
        source['input_snapshot_manifest'], 'source anchor.input snapshot manifest')
    if code_manifest != anchored_code_manifest:
        raise RuntimeError('code snapshot manifest与source anchor不一致')
    if input_manifest != anchored_input_manifest:
        raise RuntimeError('input snapshot manifest与source anchor不一致')
    if _json_digest(code_manifest) != source['source_manifest_sha256']:
        raise RuntimeError('code snapshot manifest根SHA-256不一致')
    if _json_digest(input_manifest) != source['input_manifest_sha256']:
        raise RuntimeError('input snapshot manifest根SHA-256不一致')
    if code_manifest != _regular_file_manifest(
            outer / 'code_snapshot', 'code snapshot'):
        raise RuntimeError('code snapshot完整文件manifest不一致')
    if input_manifest != _regular_file_manifest(
            outer / 'input_snapshot', 'input snapshot'):
        raise RuntimeError('input snapshot完整文件manifest不一致')

    code_hashes = _validate_hash_map(
        _read_strict_object(outer / 'code_hashes.json', 'code_hashes.json'),
        'code_hashes.json')
    input_hashes = _validate_hash_map(
        _read_strict_object(outer / 'input_hashes.json', 'input_hashes.json'),
        'input_hashes.json')
    anchored_code = _validate_hash_map(source['source_hashes'],
                                       'source anchor.source_hashes')
    anchored_inputs = _validate_hash_map(source['input_hashes'],
                                         'source anchor.input_hashes')
    if code_hashes != anchored_code:
        raise RuntimeError('code_hashes.json与source anchor不一致')
    if input_hashes != anchored_inputs:
        raise RuntimeError('input_hashes.json与source anchor不一致')
    _bind_hash_map(code_hashes, code_manifest, 'code_hashes.json')
    _bind_hash_map(input_hashes, input_manifest, 'input_hashes.json')
    if input_hashes.get('phase5g_cases.json') != source['case_file_sha256'] \
            or not _valid_digest(source['case_file_sha256']) \
            or not _valid_digest(source['mode_registry_sha256']):
        raise RuntimeError('source anchor的case或mode registry SHA-256不一致')

    child_manifest = _validate_snapshot_manifest(
        completion['child_manifest'], 'completion anchor.child manifest')
    if _json_digest(child_manifest) != completion['child_manifest_sha256']:
        raise RuntimeError('completion anchor的child manifest根SHA-256不一致')
    actual_child = _regular_file_manifest(outer / 'case', 'case child manifest')
    if child_manifest != actual_child:
        raise RuntimeError('completion anchor的child manifest与实际case不一致')
    evidence = _verify_sealed_directory(outer)
    anchored_evidence = completion['outer_evidence_hashes']
    if not isinstance(anchored_evidence, dict) or evidence != anchored_evidence:
        raise RuntimeError('completion anchor的outer evidence清单不一致')
    if _json_digest(evidence) != completion['outer_evidence_manifest_sha256']:
        raise RuntimeError('completion anchor的outer evidence根SHA-256不一致')
    if sha256_file(outer / 'evidence_hashes.json') \
            != completion['outer_evidence_file_sha256']:
        raise RuntimeError('completion anchor的outer evidence文件SHA-256不一致')
    trace_entry = child_manifest.get('trace.jsonl')
    if not isinstance(trace_entry, dict) or not _valid_digest(
            trace_entry.get('sha256')):
        raise RuntimeError('completion anchor的child manifest缺少trace.jsonl')
    return source, trace_entry['sha256']


_TRACE_STATE_FIELDS = frozenset({
    'time_s', 'x_m', 'y_m', 'heading_rad', 'vx_mps', 'vy_mps',
    'yaw_rate_radps', 'a_drive_mps2', 'steering_rad',
})
_TRACE_STEP_FIELDS = frozenset({
    'initial', 'final', 'command', 'samples', 'dt_s',
})
_TRACE_COMMAND_FIELDS = frozenset({'acceleration_mps2', 'steering_rad'})
_TRACE_RECORD_CONTAINERS = (
    'inputs', 'decisions', 'actions', 'diagnostics')


def _trace_number(value, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise RuntimeError(f'{label}必须是exact int/float有限数字（不接受bool）')
    return float(value)


def _trace_state_time(state, label: str) -> float:
    if not isinstance(state, dict):
        raise RuntimeError(f'{label}必须是JSON对象')
    missing = sorted(_TRACE_STATE_FIELDS - set(state))
    extra = sorted(set(state) - _TRACE_STATE_FIELDS)
    if missing or extra:
        raise RuntimeError(
            f'{label}的VehicleState字段必须精确: '
            f'missing={missing}; extra={extra}')
    for field in sorted(_TRACE_STATE_FIELDS):
        _trace_number(state[field], f'{label}.{field}')
    return float(state['time_s'])


def _validate_trace_command(command, label: str) -> None:
    if not isinstance(command, dict):
        raise RuntimeError(f'{label}必须是JSON对象')
    missing = sorted(_TRACE_COMMAND_FIELDS - set(command))
    extra = sorted(set(command) - _TRACE_COMMAND_FIELDS)
    if missing or extra:
        raise RuntimeError(
            f'{label}的command字段必须精确: '
            f'missing={missing}; extra={extra}')
    for field in sorted(_TRACE_COMMAND_FIELDS):
        _trace_number(command[field], f'{label}.{field}')


def _trace_frame_time(states, actors: tuple[str, ...], label: str) -> float:
    if not isinstance(states, dict) or set(states) != set(actors):
        raise RuntimeError(f'{label}车辆集合与controlled不一致')
    times = [
        _trace_state_time(states[actor], f'{label}.{actor}') for actor in actors
    ]
    if any(not math.isclose(value, times[0], abs_tol=1e-9, rel_tol=0.0)
           for value in times[1:]):
        raise RuntimeError(f'{label}各车辆时间不一致')
    return times[0]


def _preflight_simple_trace(
        trace_path: Path, metadata: Mapping, actors: tuple[str, ...],
        expected_sha256: str) -> bytes:
    """Parse and validate the complete replay stream before a GUI run exists."""
    case = metadata.get('case')
    parameters = metadata.get('parameters')
    if not isinstance(case, dict) or not isinstance(parameters, dict):
        raise RuntimeError('case metadata缺少case或parameters对象')
    duration = _trace_number(case.get('duration_s'), 'case.duration_s')
    control_dt = _trace_number(
        parameters.get('control_sync_dt_s'), 'parameters.control_sync_dt_s')
    dynamics_dt = _trace_number(
        parameters.get('dynamics_dt_s'), 'parameters.dynamics_dt_s')
    if duration <= 0:
        raise RuntimeError('case.duration_s必须为正数')
    if control_dt <= 0:
        raise RuntimeError('parameters.control_sync_dt_s必须为正数')
    if dynamics_dt <= 0:
        raise RuntimeError('parameters.dynamics_dt_s必须为正数')
    expected_samples = round(control_dt / dynamics_dt)
    if expected_samples < 1 or not math.isclose(
            expected_samples * dynamics_dt, control_dt,
            abs_tol=1e-9, rel_tol=0.0):
        raise RuntimeError('control dt不包含完整dynamics dt周期')
    expected_intervals = round(duration / control_dt)
    if expected_intervals < 1 or not math.isclose(
            expected_intervals * control_dt, duration,
            abs_tol=1e-9, rel_tol=0.0):
        raise RuntimeError('case duration不包含完整control dt周期')
    if type(metadata.get('intervals')) is not int \
            or metadata['intervals'] != expected_intervals \
            or type(metadata.get('trace_intervals')) is not int \
            or metadata['trace_intervals'] != expected_intervals:
        raise RuntimeError('case metadata的intervals/trace_intervals与duration不一致')
    case_initial = case.get('initial')
    _trace_frame_time(case_initial, actors, 'case.initial')

    count = 0
    first_time = None
    previous_final = None
    previous_final_states = None
    try:
        trace_bytes = Path(trace_path).read_bytes()
        trace_text = trace_bytes.decode('utf-8')
    except (OSError, UnicodeError) as error:
        raise RuntimeError(f'无法打开新轨迹trace: {trace_path}') from error
    if hashlib.sha256(trace_bytes).hexdigest() != expected_sha256:
        raise RuntimeError('trace字节与completion anchor绑定的SHA-256不一致')
    stream = io.StringIO(trace_text)
    with stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                raise RuntimeError(f'trace第{line_number}行为空')
            try:
                record = json.loads(line, parse_constant=_reject_json_constant)
            except json.JSONDecodeError as error:
                raise RuntimeError(f'trace第{line_number}行不是有效JSON对象') from error
            except ValueError as error:
                raise RuntimeError(
                    f'trace第{line_number}行含禁止的非有限JSON常量') from error
            if not isinstance(record, dict):
                raise RuntimeError(f'trace第{line_number}行必须是JSON对象')
            if record.get('status') != 'completed':
                raise RuntimeError(f'trace第{line_number}行状态必须是completed')
            for field in _TRACE_RECORD_CONTAINERS:
                if not isinstance(record.get(field), dict):
                    raise RuntimeError(
                        f'trace第{line_number}行.{field}必须存在且是JSON对象')
            if 'readback' not in record or record['readback'] is not None \
                    and not isinstance(record['readback'], dict):
                raise RuntimeError(
                    f'trace第{line_number}行.readback必须存在且为null/JSON对象')
            initial_states = record.get('initial')
            initial_time = _trace_frame_time(
                initial_states, actors, f'trace第{line_number}行initial')
            if first_time is None:
                first_time = initial_time
                if initial_states != case_initial:
                    raise RuntimeError('trace首行initial与case.initial不连续')
            elif not math.isclose(
                    initial_time, previous_final, abs_tol=1e-9, rel_tol=0.0) \
                    or initial_states != previous_final_states:
                raise RuntimeError(f'trace第{line_number}行initial状态/时间不连续')
            steps = record.get('steps')
            if not isinstance(steps, dict) or set(steps) != set(actors):
                raise RuntimeError(f'trace第{line_number}行steps车辆集合不一致')
            final_states = {}
            sample_times_by_actor = {}
            for actor in actors:
                step = steps[actor]
                if not isinstance(step, dict):
                    raise RuntimeError(
                        f'trace第{line_number}行steps.{actor}结构无效')
                missing = sorted(_TRACE_STEP_FIELDS - set(step))
                extra = sorted(set(step) - _TRACE_STEP_FIELDS)
                if missing or extra:
                    raise RuntimeError(
                        f'trace第{line_number}行steps.{actor}.step字段'
                        f'必须精确: missing={missing}; extra={extra}')
                step_initial = step.get('initial')
                _trace_state_time(
                    step_initial, f'trace第{line_number}行steps.{actor}.initial')
                if step_initial != initial_states[actor]:
                    raise RuntimeError(
                        f'trace第{line_number}行steps.{actor}.initial'
                        '与record initial不一致')
                _validate_trace_command(
                    step['command'], f'trace第{line_number}行steps.{actor}.command')
                step_dt = _trace_number(
                    step.get('dt_s'), f'trace第{line_number}行steps.{actor}.dt_s')
                if not math.isclose(
                        step_dt, dynamics_dt, abs_tol=1e-9, rel_tol=0.0):
                    raise RuntimeError(
                        f'trace第{line_number}行steps.{actor}.dt_s'
                        '与dynamics dt不一致')
                samples = step.get('samples')
                if not isinstance(samples, list) \
                        or len(samples) != expected_samples:
                    raise RuntimeError(
                        f'trace第{line_number}行steps.{actor}样本不完整：'
                        f'{len(samples) if isinstance(samples, list) else "非数组"}'
                        f'/{expected_samples}个dynamics样本')
                actor_sample_times = []
                for sample_index, sample in enumerate(samples):
                    next_time = _trace_state_time(
                        sample,
                        f'trace第{line_number}行steps.{actor}'
                        f'.samples[{sample_index}]')
                    expected_sample_time = (
                        initial_time + (sample_index + 1) * dynamics_dt)
                    if not math.isclose(
                            next_time, expected_sample_time,
                            abs_tol=1e-9, rel_tol=0.0):
                        raise RuntimeError(
                            f'trace第{line_number}行steps.{actor}样本时间'
                            '不符合dynamics dt间隔')
                    actor_sample_times.append(next_time)
                sample_times_by_actor[actor] = actor_sample_times
                final_state = step.get('final')
                _trace_state_time(
                    final_state, f'trace第{line_number}行steps.{actor}.final')
                final_states[actor] = final_state
                if final_state != samples[-1]:
                    raise RuntimeError(
                        f'trace第{line_number}行steps.{actor}.final'
                        '状态/时间与最后样本不一致')
            reference_sample_times = sample_times_by_actor[actors[0]]
            for actor in actors[1:]:
                candidate_times = sample_times_by_actor[actor]
                if len(candidate_times) != len(reference_sample_times) or any(
                        not math.isclose(left, right, abs_tol=1e-9, rel_tol=0.0)
                        for left, right in zip(
                            candidate_times, reference_sample_times)):
                    raise RuntimeError(
                        f'trace第{line_number}行样本车辆帧时间不一致')
            final_time = _trace_frame_time(
                final_states, actors, f'trace第{line_number}行final')
            if final_time <= initial_time or not math.isclose(
                    final_time, initial_time + control_dt,
                    abs_tol=1e-9, rel_tol=0.0):
                raise RuntimeError(
                    f'trace第{line_number}行时间未严格递增或不符合控制周期')
            previous_final = final_time
            previous_final_states = final_states
            count += 1
    if count != expected_intervals:
        raise RuntimeError(f'trace区间数不完整: {count}/{expected_intervals}')
    if first_time is None or not math.isclose(
            previous_final - first_time, duration,
            abs_tol=1e-9, rel_tol=0.0):
        raise RuntimeError('trace总时长与保存duration/control dt契约不一致')
    return trace_bytes


def _require_exact_field(document: Mapping, name: str, expected, label: str):
    value = document.get(name)
    valid = type(value) is type(expected) and value == expected
    if not valid:
        raise RuntimeError(
            f'{label}.{name}必须是精确{type(expected).__name__}'
            f' {expected!r}，实际为{value!r}')
    return value


def _require_exact_int_field(
        document: Mapping, name: str, label: str, *, minimum: int = 0,
        maximum: int | None = None) -> int:
    value = document.get(name)
    if type(value) is not int or value < minimum \
            or maximum is not None and value > maximum:
        raise RuntimeError(
            f'{label}.{name}必须是exact int（不接受bool）')
    return value


def _require_positive_number_field(
        document: Mapping, name: str, label: str) -> float:
    value = _trace_number(document.get(name), f'{label}.{name}')
    if value <= 0:
        raise RuntimeError(f'{label}.{name}必须为正数')
    return value


def _require_object_field(document: Mapping, name: str, label: str) -> dict:
    value = document.get(name)
    if not isinstance(value, dict):
        raise RuntimeError(f'{label}.{name}必须是JSON对象')
    return value


def _validate_outer_simple_documents(
        outer: Path, metadata: Mapping, validation: Mapping,
        config: SimpleFormationDemoConfig | None) -> None:
    label = '新轨迹metadata'
    _require_exact_field(metadata, 'schema', 'phase5g_simple_demo_v1', label)
    _require_exact_field(metadata, 'run_id', outer.name, label)
    _require_exact_field(metadata, 'formal', False, label)
    _require_exact_field(metadata, 'mode', 'lane_priority', label)
    _require_exact_field(metadata, 'simple_formation_enabled', True, label)
    count = _require_exact_int_field(metadata, 'vehicle_count', label, minimum=1)
    if count not in (3, 6, 12):
        raise RuntimeError(f'{label}.vehicle_count必须是3、6或12')
    seed = _require_exact_int_field(
        metadata, 'seed', label, maximum=2**64 - 1)
    target_speed = _require_positive_number_field(
        metadata, 'target_speed_mps', label)
    duration = _require_positive_number_field(metadata, 'duration_s', label)
    simple = _require_object_field(metadata, 'simple_parameters', label)
    expected_simple_names = {
        'simple_formation_local_range_m',
        'simple_formation_adjacent_gap_m',
        'simple_formation_same_gap_m',
        'simple_formation_position_tolerance_m',
        'simple_formation_accel_limit_mps2',
        'simple_formation_max_lane_changes',
    }
    if set(simple) != expected_simple_names:
        raise RuntimeError(f'{label}.simple_parameters字段集不一致')
    for name in expected_simple_names - {'simple_formation_max_lane_changes'}:
        _require_positive_number_field(simple, name, f'{label}.simple_parameters')
    if _require_exact_int_field(
            simple, 'simple_formation_max_lane_changes',
            f'{label}.simple_parameters', minimum=1) != 1:
        raise RuntimeError(
            f'{label}.simple_parameters.simple_formation_max_lane_changes必须为1')
    if not _valid_digest(metadata.get('case_file_sha256')):
        raise RuntimeError(f'{label}.case_file_sha256必须是小写SHA-256')
    _require_object_field(metadata, 'mode_registry', label)

    validation_label = '新轨迹validation'
    _require_exact_field(validation, 'run_id', outer.name, validation_label)
    _require_exact_field(validation, 'status', 'completed', validation_label)
    _require_exact_field(validation, 'passed', True, validation_label)
    _require_exact_field(
        validation, 'complete_execution', True, validation_label)
    _require_exact_field(
        validation, 'engineering_passed', True, validation_label)
    _require_exact_field(validation, 'formal', False, validation_label)
    _require_exact_field(validation, 'mode', 'lane_priority', validation_label)
    _require_exact_field(validation, 'case_directory', 'case', validation_label)

    if config is None:
        return
    expected = {
        'vehicle_count': config.vehicle_count,
        'seed': config.random_seed,
        'target_speed_mps': config.target_speed_mps,
        'duration_s': config.simulation_duration_s,
    }
    actual = {
        'vehicle_count': count, 'seed': seed,
        'target_speed_mps': target_speed, 'duration_s': duration,
    }
    for name, value in expected.items():
        if actual[name] != value:
            raise RuntimeError(f'{label}.{name}与顶部配置不一致')
    expected_simple = {
        'simple_formation_local_range_m': config.local_formation_range_m,
        'simple_formation_adjacent_gap_m': config.adjacent_lane_gap_m,
        'simple_formation_same_gap_m': config.same_lane_gap_m,
        'simple_formation_position_tolerance_m': config.position_tolerance_m,
        'simple_formation_accel_limit_mps2':
            config.formation_accel_limit_mps2,
        'simple_formation_max_lane_changes':
            config.max_formation_lane_changes,
    }
    for name, value in expected_simple.items():
        if simple[name] != value:
            raise RuntimeError(
                f'{label}.simple_parameters.{name}与顶部配置不一致')


def _validate_child_simple_documents(
        outer: Path, metadata: Mapping, validation: Mapping) -> None:
    label = 'case metadata'
    _require_exact_field(metadata, 'schema', 'phase5g_variant_v1', label)
    _require_exact_field(metadata, 'mode', 'lane_priority', label)
    _require_exact_field(metadata, 'formal', False, label)
    _require_exact_field(metadata, 'live', False, label)
    _require_exact_field(metadata, 'execution_status', 'completed', label)
    _require_exact_field(metadata, 'lifecycle_status', 'finalized', label)
    _require_exact_field(metadata, 'parent_run_id', outer.name, label)
    _require_object_field(metadata, 'case', label)
    _require_object_field(metadata, 'parameters', label)
    _require_object_field(metadata, 'initial', label)
    _require_exact_int_field(metadata, 'intervals', label, minimum=1)
    _require_exact_int_field(metadata, 'trace_intervals', label, minimum=1)

    validation_label = 'case validation'
    _require_exact_field(validation, 'status', 'completed', validation_label)
    if type(validation.get('passed')) is not bool:
        raise RuntimeError(f'{validation_label}.passed必须是exact bool')
    _require_exact_field(validation, 'sealed', True, validation_label)
    _require_exact_field(
        validation, 'recording_passed', True, validation_label)


def load_simple_trace_source(
        outer_path: Path, paths: SimpleCheckedPaths,
        config: SimpleFormationDemoConfig | None = None) -> TraceSource:
    """Load only a newly generated, sealed Phase5G simple-formation trace."""
    outer = _resolve_result_directory(
        outer_path, paths.variant_results, '结果路径')
    source_anchor, expected_trace_sha256 = _verify_simple_trust(outer, paths)
    metadata = _read_strict_object(
        outer / 'metadata.json', '新轨迹metadata')
    validation = _read_strict_object(
        outer / 'validation.json', '新轨迹validation')
    _validate_outer_simple_documents(outer, metadata, validation, config)
    if metadata.get('case_file_sha256') != source_anchor['case_file_sha256']:
        raise RuntimeError('新轨迹metadata.case_file_sha256与source anchor不一致')
    if _json_digest(metadata.get('mode_registry')) \
            != source_anchor['mode_registry_sha256']:
        raise RuntimeError('新轨迹metadata.mode_registry与source anchor不一致')

    case_dir = _resolve_result_directory(outer / 'case', outer, 'case目录')
    _verify_sealed_directory(case_dir)
    child_metadata = _read_strict_object(
        case_dir / 'metadata.json', 'case metadata')
    child_validation = _read_strict_object(
        case_dir / 'validation.json', 'case validation')
    _validate_child_simple_documents(
        outer, child_metadata, child_validation)
    case = child_metadata['case']
    controlled = case.get('controlled')
    if not isinstance(controlled, list) or not controlled \
            or any(type(actor) is not str or not actor for actor in controlled) \
            or len(set(controlled)) != len(controlled):
        raise RuntimeError('新轨迹case.metadata.case.controlled无效')
    actors = tuple(controlled)
    if len(actors) != metadata['vehicle_count']:
        raise RuntimeError('新轨迹controlled车辆数与outer metadata不一致')
    initial = case.get('initial')
    if not isinstance(initial, dict) or set(initial) != set(actors) \
            or case.get('scripts') != {}:
        raise RuntimeError('新轨迹case必须全量受控且不得包含背景或脚本车辆')
    if child_metadata['initial'] != initial:
        raise RuntimeError('case metadata.initial与case.initial不一致')
    if type(case.get('name')) is not str or not case['name']:
        raise RuntimeError('case metadata.case.name必须是非空字符串')
    case_duration = _require_positive_number_field(
        case, 'duration_s', 'case metadata.case')
    if case_duration != metadata['duration_s']:
        raise RuntimeError('case metadata.case.duration_s与outer metadata不一致')
    parameters = child_metadata['parameters']
    _require_positive_number_field(parameters, 'length_m', 'case metadata.parameters')
    _require_positive_number_field(
        parameters, 'control_sync_dt_s', 'case metadata.parameters')
    trace_path = case_dir / 'trace.jsonl'
    if not trace_path.is_file():
        raise FileNotFoundError(f'新轨迹trace缺失: {trace_path}')
    verified_trace_bytes = _preflight_simple_trace(
        trace_path, child_metadata, actors, expected_trace_sha256)
    trace_sha256 = hashlib.sha256(verified_trace_bytes).hexdigest()
    source = TraceSource(
        case_name=case['name'],
        case_dir=case_dir, trace_path=trace_path,
        metadata=child_metadata, validation=child_validation,
        evidence_status='completed', actors=actors,
        verified_trace_bytes=verified_trace_bytes,
        trace_sha256=trace_sha256)
    return source


def _subprocess_diagnostic(text: str | None) -> str:
    cleaned = (text or '').replace('\x00', '').strip().replace('\r', ' ')
    return cleaned[-2000:].replace('\n', ' | ') or '(无stderr)'


def generate_fresh_simple_trace(
        config: SimpleFormationDemoConfig, paths: SimpleCheckedPaths, *,
        process_runner=None) -> GeneratedSimpleTrace:
    """Generate an isolated fresh trace and reject any unsealed/escaped result."""
    command = [
        sys.executable, '-I', '-B', '-S', str(paths.variant_run),
        'phase5g-demo', '--offline',
        '--vehicle-count', str(config.vehicle_count),
        '--seed', str(config.random_seed),
        '--target-speed-mps', format_number(config.target_speed_mps),
        '--duration-s', format_number(config.simulation_duration_s),
        '--output-base', SIMPLE_OUTPUT_BASE.as_posix(),
        '--local-formation-range-m', format_number(config.local_formation_range_m),
        '--adjacent-lane-gap-m', format_number(config.adjacent_lane_gap_m),
        '--same-lane-gap-m', format_number(config.same_lane_gap_m),
        '--position-tolerance-m', format_number(config.position_tolerance_m),
        '--formation-accel-limit-mps2',
        format_number(config.formation_accel_limit_mps2),
        '--max-formation-lane-changes', str(config.max_formation_lane_changes),
    ]
    runner = subprocess.run if process_runner is None else process_runner
    try:
        completed = runner(
            command, cwd=paths.variant_root, capture_output=True, text=True,
            encoding='utf-8', timeout=180, check=False, shell=False)
    except subprocess.TimeoutExpired as error:
        raise RuntimeError('生成simple formation轨迹超时（180秒）') from error
    except OSError as error:
        raise RuntimeError(f'无法启动Phase5G轨迹生成进程: {error}') from error
    if completed.returncode != 0:
        raise RuntimeError(
            f'Phase5G轨迹生成失败，exit code {completed.returncode}；'
            f'stderr: {_subprocess_diagnostic(completed.stderr)}')
    lines = [line for line in (completed.stdout or '').splitlines() if line.strip()]
    if not lines:
        raise RuntimeError('Phase5G轨迹生成成功退出，但stdout没有结果JSON')
    try:
        payload = json.loads(lines[-1])
    except json.JSONDecodeError as error:
        raise RuntimeError('Phase5G轨迹生成stdout最后一行不是有效JSON') from error
    raw_path = payload.get('path') if isinstance(payload, dict) else None
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise RuntimeError('Phase5G轨迹生成结果JSON缺少有效path')
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = paths.variant_root / candidate
    resolved = _resolve_result_directory(
        candidate, paths.variant_results, 'Phase5G结果路径')
    try:
        source = load_simple_trace_source(resolved, paths, config)
    except (OSError, ValueError) as error:
        raise RuntimeError(f'Phase5G新轨迹证据无效: {error}') from error
    return GeneratedSimpleTrace(resolved, source)


def write_xml(path: Path, root: ET.Element) -> None:
    path = Path(path)
    if not path.parent.is_dir():
        raise FileNotFoundError(f'XML目标目录不存在: {path.parent}')
    ET.indent(root, space='  ')
    ET.ElementTree(root).write(path, encoding='utf-8', xml_declaration=True)


def write_json_atomic(path: Path, data: Mapping) -> None:
    path = Path(path)
    if not path.parent.is_dir():
        raise FileNotFoundError(f'JSON目标目录不存在: {path.parent}')
    temporary = path.with_suffix(path.suffix + '.writing')
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
        encoding='utf-8')
    os.replace(temporary, path)


def algorithm_routes_tree() -> ET.Element:
    routes = ET.Element('routes')
    ET.SubElement(
        routes, 'vType', id='external_demo', vClass='passenger', guiShape='passenger',
        length='4', width='1.8', maxSpeed='33.3', accel='5', decel='10',
        emergencyDecel='10', minGap='0', speedFactor='1', speedDev='0')
    ET.SubElement(routes, 'route', id='demo_full', edges='upstream downstream')
    ET.SubElement(routes, 'route', id='demo_remaining', edges='downstream')
    return routes


def gui_command(paths: CheckedPaths, sumocfg: Path, delay_ms: int, port: int) -> list[str]:
    return [
        str(paths.sumo_gui), '-c', str(Path(sumocfg).resolve()),
        '--remote-port', str(port), '--start', '--delay', str(delay_ms),
        '--window-size', '1500,750', '--no-step-log', 'true',
    ]


def to_sumo_pose(state: Mapping[str, float], length_m: float = 4.0):
    heading = float(state['heading_rad'])
    return (
        float(state['x_m']) + length_m / 2 * math.cos(heading),
        float(state['y_m']) + length_m / 2 * math.sin(heading),
        (90 - math.degrees(heading)) % 360,
    )


def _view_id(connection):
    views = connection.gui.getIDList()
    return views[0] if views else None


def _event_counts(connection):
    return (connection.simulation.getCollidingVehiclesNumber(),
            connection.simulation.getStartingTeleportNumber())


def _initial_route_and_lane(state):
    x_m = float(state['x_m'])
    y_m = float(state['y_m'])
    downstream = x_m >= 1000.0
    lane = round((y_m - 1.65) / 3.3)
    lane = max(0, min(1 if downstream else 2, lane))
    return ('demo_remaining' if downstream else 'demo_full', lane,
            x_m - 1000.0 if downstream else x_m)


def play_algorithm(connection, source: TraceSource, auto_zoom: bool) -> PlaybackStats:
    """Display exact recorded control-frame states without recomputing decisions."""
    frames = iter_trace_frames(source)
    first = next(frames)
    length_m = float(source.metadata.get('parameters', {}).get('length_m', 4.0))
    controlled = set(source.metadata.get('case', {}).get('controlled', []))
    for actor in source.actors:
        state = first.states[actor]
        route_id, lane, position = _initial_route_and_lane(state)
        connection.vehicle.add(
            actor, route_id, typeID='external_demo', depart='now',
            departLane=str(lane), departPos=format_number(max(0.0, position + length_m / 2)),
            departSpeed=format_number(max(0.0, float(state['vx_mps']))))
    connection.simulationStep()
    present = set(connection.vehicle.getIDList())
    missing = set(source.actors) - present
    if missing:
        raise RuntimeError(f'SUMO未能装载算法演示车辆: {sorted(missing)}')
    for actor in source.actors:
        connection.vehicle.setSpeedMode(actor, 0)
        connection.vehicle.setLaneChangeMode(actor, 0)
        color = (0, 160, 255, 255) if actor in controlled else (255, 150, 40, 255)
        connection.vehicle.setColor(actor, color)
    if auto_zoom:
        view = _view_id(connection)
        if view is not None:
            xs = [float(state['x_m']) for state in first.states.values()]
            connection.gui.setBoundary(view, min(xs) - 35, -8, max(xs) + 75, 18)

    collisions = teleports = frames_played = 0
    final_time = first.time_s
    for frame in chain((first,), frames):
        for actor in source.actors:
            state = frame.states[actor]
            front_x, front_y, angle = to_sumo_pose(state, length_m)
            speed = math.hypot(float(state['vx_mps']), float(state.get('vy_mps', 0.0)))
            connection.vehicle.setSpeed(actor, speed)
            connection.vehicle.moveToXY(
                actor, '', -1, front_x, front_y, angle=angle, keepRoute=3)
        connection.simulationStep()
        collided, teleported = _event_counts(connection)
        collisions += collided
        teleports += teleported
        frames_played += 1
        final_time = frame.time_s
    end_reason = ('trace_completed' if source.evidence_status == 'completed'
                  else f'trace_{source.evidence_status}_prefix')
    return PlaybackStats(frames_played, final_time, collisions, teleports, end_reason)


def play_native(connection, duration_s: float, auto_zoom: bool) -> PlaybackStats:
    if auto_zoom:
        view = _view_id(connection)
        if view is not None:
            connection.gui.setBoundary(view, -20, -25, 1220, 25)
    collisions = teleports = frames = 0
    final_time = 0.0
    end_reason = 'duration_reached'
    while True:
        current_time = float(connection.simulation.getTime())
        if current_time >= duration_s:
            final_time = current_time
            break
        connection.simulationStep()
        frames += 1
        final_time = min(duration_s, current_time + 0.1)
        collided, teleported = _event_counts(connection)
        collisions += collided
        teleports += teleported
        if connection.simulation.getMinExpectedNumber() == 0:
            end_reason = 'demand_drained'
            break
    return PlaybackStats(frames, final_time, collisions, teleports, end_reason)


class OwnedGuiSession:
    """Own and reliably close one TraCI connection, process and combined log."""

    def __init__(self, connection, process, log):
        self.connection = connection
        self.process = process
        self.log = log

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc, tb):
        cleanup_errors = []
        try:
            self.connection.close(False)
        except Exception as error:
            cleanup_errors.append(f'close: {type(error).__name__}: {error}')
        try:
            if self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=10)
        except Exception as error:
            cleanup_errors.append(f'process: {type(error).__name__}: {error}')
        try:
            self.log.close()
        except Exception as error:
            cleanup_errors.append(f'log: {type(error).__name__}: {error}')
        if cleanup_errors and exc_type is None:
            raise RuntimeError('; '.join(cleanup_errors))
        return False


def _load_traci(paths: CheckedPaths):
    tool_root = (paths.sumo_home / 'tools').resolve()
    if not tool_root.is_dir():
        raise FileNotFoundError(f'缺少SUMO TraCI工具目录: {tool_root}')
    if str(tool_root) not in sys.path:
        sys.path.insert(0, str(tool_root))
    os.environ['SUMO_HOME'] = str(paths.sumo_home)
    os.environ['PATH'] = str(paths.sumo_home / 'bin') + os.pathsep + os.environ.get('PATH', '')
    import traci
    origin = Path(traci.__file__).resolve()
    if not origin.is_relative_to(tool_root):
        raise RuntimeError(f'加载了错误来源的TraCI: {origin}')
    return traci


def start_gui_session(paths: CheckedPaths, sumocfg: Path, delay_ms: int,
                      log_path: Path) -> OwnedGuiSession:
    with socket.socket() as port_socket:
        port_socket.bind(('127.0.0.1', 0))
        port = port_socket.getsockname()[1]
    command = gui_command(paths, sumocfg, delay_ms, port)
    environment = os.environ.copy()
    environment['SUMO_HOME'] = str(paths.sumo_home)
    environment['PATH'] = str(paths.sumo_home / 'bin') + os.pathsep + environment.get('PATH', '')
    log = Path(log_path).open('w', encoding='utf-8')
    process = None
    try:
        process = subprocess.Popen(
            command, cwd=paths.root, env=environment, stdout=log,
            stderr=subprocess.STDOUT)
        traci = _load_traci(paths)
        connection = traci.connect(
            port=port, numRetries=50, waitBetweenRetries=0.1, proc=process)
        return OwnedGuiSession(connection, process, log)
    except BaseException:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log.close()
        raise


def _base_metadata(mode: str, config: DemoConfig, run_dir: Path, purpose: str):
    return {
        'run_id': run_dir.name,
        'mode': mode,
        'purpose': purpose,
        'status': 'starting',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'configuration': asdict(config),
    }


def _finish_metadata(path: Path, metadata: dict, status: str, **fields):
    metadata.update(status=status, ended_utc=datetime.now(timezone.utc).isoformat(), **fields)
    write_json_atomic(path, metadata)


def _is_user_closed(error: BaseException) -> bool:
    text = str(error).lower()
    return type(error).__name__ == 'FatalTraCIError' and any(
        marker in text for marker in ('connection closed', 'peer shutdown', 'tcpip'))


def _wait_if_requested(config: DemoConfig, input_fn, output_fn):
    if config.wait_before_close:
        try:
            input_fn('仿真已结束。按 Enter 关闭 SUMO 窗口...')
        except EOFError:
            output_fn('当前控制台不能读取Enter，SUMO窗口将自动关闭。')


def run_algorithm_demo(config: DemoConfig, root: Path = PROJECT_ROOT, *,
                       runtime=start_gui_session, input_fn=input,
                       output_fn=print) -> Path:
    paths = validate_config(config, root)
    source = load_trace_source(paths.root, config.algorithm_case)
    run_dir = create_run_directory(paths.root, 'algorithm')
    route_path = run_dir / 'algorithm.rou.xml'
    config_path = run_dir / 'algorithm.sumocfg'
    metadata_path = run_dir / 'run_metadata.json'
    write_xml(route_path, algorithm_routes_tree())
    duration = float(source.metadata.get('case', {}).get('duration_s', 60.0)) + 5.0
    write_xml(config_path, sumo_config_tree(paths.network, route_path.name, run_dir, duration))
    write_json_atomic(run_dir / 'config_snapshot.json', asdict(config))
    metadata = _base_metadata(
        'algorithm', config, run_dir,
        '阶段5F封存轨迹可视化；不重新计算控制决策，不是新的科研实验')
    metadata.update(
        source_case=source.case_name, source_status=source.evidence_status,
        source_trace=str(source.trace_path.relative_to(paths.root)),
        source_trace_sha256=sha256_file(source.trace_path),
        network=str(paths.network.relative_to(paths.root)),
        network_sha256=sha256_file(paths.network),
        sumocfg=config_path.name, route_file=route_path.name)
    write_json_atomic(metadata_path, metadata)
    output_fn('模式1：播放阶段5F封存轨迹；这不是一次新的实时科研实验。')
    try:
        metadata['status'] = 'running'
        write_json_atomic(metadata_path, metadata)
        with runtime(paths, config_path, config.gui_delay_ms,
                     run_dir / 'stdout_stderr.log') as connection:
            stats = play_algorithm(connection, source, config.auto_zoom)
            _wait_if_requested(config, input_fn, output_fn)
        _finish_metadata(metadata_path, metadata, 'completed', **asdict(stats))
    except KeyboardInterrupt:
        _finish_metadata(metadata_path, metadata, 'interrupted', end_reason='interrupted')
        output_fn(f'已中断并清理SUMO。本次记录: {run_dir}')
    except BaseException as error:
        if _is_user_closed(error):
            _finish_metadata(metadata_path, metadata, 'user_closed', end_reason='user_closed')
            output_fn(f'检测到用户关闭SUMO窗口。本次记录: {run_dir}')
        else:
            _finish_metadata(
                metadata_path, metadata, 'failed', end_reason='exception',
                error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
            raise
    output_fn(f'算法轨迹演示记录已保存: {run_dir}')
    return run_dir


def run_native_demo(config: DemoConfig, root: Path = PROJECT_ROOT, *,
                    runtime=start_gui_session, input_fn=input,
                    output_fn=print) -> Path:
    paths = validate_config(config, root)
    run_dir = create_run_directory(paths.root, 'native')
    route_path = run_dir / 'native.rou.xml'
    config_path = run_dir / 'native.sumocfg'
    metadata_path = run_dir / 'run_metadata.json'
    write_xml(route_path, native_routes_tree(config))
    write_xml(config_path, sumo_config_tree(
        paths.network, route_path.name, run_dir, config.simulation_duration_s))
    write_json_atomic(run_dir / 'config_snapshot.json', asdict(config))
    metadata = _base_metadata(
        'native', config, run_dir,
        'SUMO原生IDM/LC2013交通流演示；不调用NOA或阶段5F控制器')
    metadata.update(
        planned_vehicles=config.vehicle_count,
        network=str(paths.network.relative_to(paths.root)),
        network_sha256=sha256_file(paths.network),
        sumocfg=config_path.name, route_file=route_path.name)
    write_json_atomic(metadata_path, metadata)
    output_fn('模式2：SUMO原生交通流演示；本模式不使用NOA/阶段5F控制器。')
    try:
        metadata['status'] = 'running'
        write_json_atomic(metadata_path, metadata)
        with runtime(paths, config_path, config.gui_delay_ms,
                     run_dir / 'stdout_stderr.log') as connection:
            stats = play_native(
                connection, config.simulation_duration_s, config.auto_zoom)
            _wait_if_requested(config, input_fn, output_fn)
        _finish_metadata(metadata_path, metadata, 'completed', **asdict(stats))
    except KeyboardInterrupt:
        _finish_metadata(metadata_path, metadata, 'interrupted', end_reason='interrupted')
        output_fn(f'已中断并清理SUMO。本次记录: {run_dir}')
    except BaseException as error:
        if _is_user_closed(error):
            _finish_metadata(metadata_path, metadata, 'user_closed', end_reason='user_closed')
            output_fn(f'检测到用户关闭SUMO窗口。本次记录: {run_dir}')
        else:
            _finish_metadata(
                metadata_path, metadata, 'failed', end_reason='exception',
                error=f'{type(error).__name__}: {error}', traceback=traceback.format_exc())
            raise
    output_fn(f'原生交通流演示记录已保存: {run_dir}')
    return run_dir


def run_simple_formation_demo(
        config: SimpleFormationDemoConfig, root: Path = PROJECT_ROOT, *,
        generator=None, runtime=start_gui_session, input_fn=input,
        output_fn=print) -> Path:
    """Generate a fresh simple trace and optionally replay it in SUMO-GUI."""
    paths = validate_simple_config(config, root)
    output_fn(
        f'当前simple formation配置：车辆={config.vehicle_count}，'
        f'目标速度={format_number(config.target_speed_mps)}m/s，'
        f'seed={config.random_seed}，时长={format_number(config.simulation_duration_s)}s，'
        f'显示GUI={config.show_gui}')
    generate = generate_fresh_simple_trace if generator is None else generator
    generated = generate(config, paths)
    if not config.show_gui:
        output_fn(f'轨迹已生成：{generated.outer_path}')
        return generated.outer_path

    source = generated.source
    if source.verified_trace_bytes is None or source.trace_sha256 \
            != hashlib.sha256(source.verified_trace_bytes).hexdigest():
        raise RuntimeError('simple formation缺少已验证的不可变trace字节')
    run_dir = create_run_directory(paths.root, 'simple_formation')
    route_path = run_dir / 'simple_formation.rou.xml'
    config_path = run_dir / 'simple_formation.sumocfg'
    metadata_path = run_dir / 'run_metadata.json'
    write_xml(route_path, algorithm_routes_tree())
    write_xml(config_path, sumo_config_tree(
        paths.network, route_path.name, run_dir,
        config.simulation_duration_s + 5.0))
    write_json_atomic(run_dir / 'config_snapshot.json', asdict(config))
    metadata = _base_metadata(
        'simple_formation', config, run_dir,
        '新生成的Phase5G无通信、局部自组织、简单if/else交错编队轨迹回放')
    metadata.update(
        generation_source=str(generated.outer_path),
        source_case=source.case_name,
        source_status=source.evidence_status,
        source_trace=str(source.trace_path),
        source_trace_sha256=source.trace_sha256,
        controlled_actors=list(source.actors),
        network=str(paths.network),
        network_sha256=sha256_file(paths.network),
        sumocfg=config_path.name,
        route_file=route_path.name,
    )
    write_json_atomic(metadata_path, metadata)
    output_fn('正在播放本次新生成的局部自组织交错编队轨迹。')
    try:
        metadata['status'] = 'running'
        write_json_atomic(metadata_path, metadata)
        with runtime(paths, config_path, config.gui_delay_ms,
                     run_dir / 'stdout_stderr.log') as connection:
            stats = play_algorithm(connection, source, config.auto_zoom)
            _wait_if_requested(config, input_fn, output_fn)
        _finish_metadata(
            metadata_path, metadata, 'completed', terminal_status='completed',
            **asdict(stats))
    except KeyboardInterrupt:
        _finish_metadata(
            metadata_path, metadata, 'interrupted',
            terminal_status='interrupted', end_reason='interrupted')
        output_fn(f'已中断并清理SUMO。本次记录: {run_dir}')
    except BaseException as error:
        if _is_user_closed(error):
            _finish_metadata(
                metadata_path, metadata, 'user_closed',
                terminal_status='user_closed', end_reason='user_closed')
            output_fn(f'检测到用户关闭SUMO窗口。本次记录: {run_dir}')
        else:
            _finish_metadata(
                metadata_path, metadata, 'failed', terminal_status='failed',
                end_reason='exception', error=f'{type(error).__name__}: {error}',
                traceback=traceback.format_exc())
            raise
    output_fn(f'simple formation演示记录已保存: {run_dir}')
    return run_dir


def check_environment(config: DemoConfig, root: Path = PROJECT_ROOT) -> dict:
    """Run all non-GUI checks used by runrun.py --check."""
    paths = validate_config(config, root)
    source = load_trace_source(paths.root, config.algorithm_case)
    traci = _load_traci(paths)
    return {
        'sumo_gui': str(paths.sumo_gui),
        'network': str(paths.network),
        'network_sha256': sha256_file(paths.network),
        'algorithm_case': source.case_name,
        'source_status': source.evidence_status,
        'source_trace': str(source.trace_path),
        'source_trace_sha256': sha256_file(source.trace_path),
        'evidence_manifest_sha256': EVIDENCE_MANIFEST_SHA256,
        'traci': str(Path(traci.__file__).resolve()),
    }


def check_simple_environment(
        config: SimpleFormationDemoConfig,
        root: Path = PROJECT_ROOT) -> dict:
    """Validate simple-demo inputs without spawning or creating any run."""
    paths = validate_simple_config(config, root)
    return {
        'sumo_gui': str(paths.sumo_gui),
        'network': str(paths.network),
        'variant_root': str(paths.variant_root),
        'variant_run': str(paths.variant_run),
        'variant_results': str(paths.variant_results),
        'traci': str(paths.traci_python),
        'configuration': asdict(config),
    }
