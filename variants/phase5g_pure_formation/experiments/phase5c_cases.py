"""Deterministic phase 5C extension; original R5 schema remains delegated.

The parent file is the preregistered eight-case file, including its private
states. No extension path draws entropy or reselects a case after execution.
This registry is an offline runner input, never an observation for controllers.
"""
import copy
from dataclasses import asdict
import json
from pathlib import Path

from experiments import phase5_r5_cases as parent_cases
from models.kinematic import KinematicModel, kinematic_state
from noa.formation import FormationMemory
from research.common import ROOT, sha256


SCHEMA = 'phase5c_lane_priority_cases_v1'
PARENT_FILE_SHA256 = '46cff8d466753a50a45e82675bc1a73eedf6e060e50002b9260a985f24aaaf20'


def _parent_path(parent_file):
    path = ROOT/'parent_frozen_r5_cases.json' if parent_file is None else Path(parent_file)
    if sha256(path) != PARENT_FILE_SHA256:
        raise ValueError('Phase 5C parent bytes differ from preregistered SHA256')
    return path


def build_cases(p=None, parent_file=None):
    """Return the exact parent first case and one fixed 60 s three-actor case."""
    p = dict(KinematicModel.from_config().p) if p is None else p
    parent = parent_cases.load_frozen_cases(_parent_path(parent_file), p)
    placements = {'lower': (250., 1.65, 8.), 'upper': (250., 8.25, 8.),
                  'middle_front': (280., 4.95, 8.), 'lead_lower': (310., 1.65, 2.),
                  'lead_upper': (310., 8.25, 2.)}
    controlled = ['lower', 'upper', 'middle_front']
    states = {actor: 1 for actor in controlled}
    gradual = dict(name='r5c_gradual_three', kind='r5_mechanism', duration_s=60.,
        initial={actor: asdict(kinematic_state(p, x_m=x, y_m=y, vx_mps=speed))
                 for actor, (x, y, speed) in placements.items()},
        controlled=controlled,
        scripts={actor: {'speed_steps': [[0., 2.]]} for actor in ('lead_lower', 'lead_upper')},
        requirements={}, r5_requirements=['visible_lane_priority', 'gradual_release_observation'],
        purpose='Fixed three controlled actors with duplicate private states and slow outer-lane leads; '
                'waiting and visible lane priority are compared without promising completion or formation.',
        illustrative_initial_condition=True, priority_waiting_baseline=True,
        initial_memories={actor: asdict(FormationMemory((), 'CRUISE', r5_rng_state=1))
                          for actor in controlled},
        private_rng_provenance={'algorithm': 'SplitMix64', 'version': 1,
            'source': 'adversarial_fixed_private_state', 'states_by_actor': states,
            'independent_draws_requested': False, 'uniqueness_enforced': False,
            'online_initialization': False})
    # Compare the persisted JSON representation, including every memory field.
    return json.loads(json.dumps([copy.deepcopy(parent[0]), gradual], allow_nan=False))


def _bundle(p, parent_file):
    parent = _parent_path(parent_file)
    cases = build_cases(p, parent)
    return dict(schema=SCHEMA, generator_sha256=sha256(Path(__file__)),
        parent_file_sha256=sha256(parent), model_parameters_sha256=parent_cases._digest(p),
        physical_sha256=parent_cases._digest([parent_cases._physical(case) for case in cases]),
        initial_state_sha256=parent_cases._digest(cases), cases=cases)


def freeze_cases(path, p=None, parent_file=None):
    """Exclusively create a deterministic extension; existing paths are rejected first."""
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    p = dict(KinematicModel.from_config().p) if p is None else p
    data = _bundle(p, parent_file)
    serialized = json.dumps(data, sort_keys=True, indent=2, allow_nan=False)+'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(serialized)
    return load_frozen_cases(path, p, parent_file)


def load_frozen_cases(path, p=None, parent_file=None):
    """Validate both schemas against current source and fixed generating inputs.

    The extension's complete envelope is rebuilt, so updating self-reported
    hashes cannot legitimize a changed matrix, script, private state or parent.
    The original eight-case loader and its source bytes are unchanged.
    """
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    if data.get('schema') == parent_cases.SCHEMA:
        return parent_cases.load_frozen_cases(path, p)
    if data.get('schema') != SCHEMA:
        raise ValueError('Wrong R5/phase 5C case schema')
    p = dict(KinematicModel.from_config().p) if p is None else p
    expected = _bundle(p, parent_file)
    # Canonical JSON keeps bool/int distinctions that Python dict equality loses.
    if parent_cases._digest(data) != parent_cases._digest(expected):
        raise ValueError('Phase 5C source, model, parent or fixed initial case binding changed')
    return data['cases']
