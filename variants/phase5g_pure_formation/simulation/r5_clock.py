"""Restore sealed per-instance private state before the first frozen observation."""
from dataclasses import fields
import hashlib
import json
import math

from noa.contracts import NoaMemory, memory_from_dict as noa_memory
from noa.formation import FormationMemory, memory_from_dict as formation_memory
from simulation.formation_clock import FormationClock

CLOCK_SCHEMA = 'phase5_r5_v1'
PRNG_ALGORITHM = 'SplitMix64'
PRNG_VERSION = 1
PRIVATE_FIELDS = {'r5_rng_state', 'r5_draw_count', 'r5_phase', 'r5_deadline_s',
                  'r5_episode_signature', 'r5_clear_since_s', 'r5_last_time_s'}


def initial_memory_hash(memories):
    raw = json.dumps(memories, sort_keys=True, separators=(',', ':'),
                     ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def restore_initial_memories(raw, controlled, enabled, formation_enabled):
    if not isinstance(raw, dict) or set(raw) != set(controlled):
        raise ValueError('Private initial memory keys must exactly match controlled instances')
    memory_type = FormationMemory if formation_enabled else NoaMemory
    codec = formation_memory if formation_enabled else noa_memory
    expected = {field.name for field in fields(memory_type)}
    if not PRIVATE_FIELDS <= expected:
        raise ValueError('R5 memory schema is unavailable in the current controller')
    restored = {}
    for key in controlled:
        value = raw[key]
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError(f'{key}: full private initial memory schema required')
        state = value['r5_rng_state']
        if state is not None and (type(state) is not int or not 0 <= state < (1 << 64)):
            raise ValueError(f'{key}: private PRNG state must be an exact unsigned 64-bit integer')
        if enabled and state is None:
            raise ValueError(f'{key}: enabled R5 requires a sealed private PRNG state')
        if type(value['r5_draw_count']) is not int or value['r5_draw_count'] < 0:
            raise ValueError(f'{key}: draw count must be a nonnegative integer')
        if value['r5_phase'] not in ('IDLE', 'YIELD', 'BACKOFF', 'ELIGIBLE', 'UNKNOWN'):
            raise ValueError(f'{key}: invalid R5 phase')
        for name in ('r5_deadline_s', 'r5_clear_since_s', 'r5_last_time_s'):
            number = value[name]
            if number is not None and (type(number) not in (float, int) or not math.isfinite(number)):
                raise ValueError(f'{key}: invalid R5 time {name}')
        # A separate JSON copy and immutable codec per actor prevent shared mutable input.
        restored[key] = codec(json.loads(json.dumps(value, allow_nan=False)))
        if type(restored[key]) is not memory_type:
            raise ValueError(f'{key}: controller memory subtype differs from formation switch')
    return restored


def validate_metadata(metadata):
    if metadata.get('clock_schema') != CLOCK_SCHEMA:
        raise ValueError('An explicit supported R5 clock schema is required')
    raw = metadata['initial_memories']
    if metadata.get('initial_memories_sha256') != initial_memory_hash(raw):
        raise ValueError('Initial private memory digest differs')
    case = metadata['case']
    if initial_memory_hash(raw) != initial_memory_hash(case['initial_memories']):
        raise ValueError('Metadata private state differs from the frozen case')
    provenance = metadata['private_rng_provenance']
    if provenance != case['private_rng_provenance']:
        raise ValueError('Private state provenance differs from the frozen case')
    if (provenance.get('algorithm') != PRNG_ALGORITHM or
            type(provenance.get('version')) is not int or provenance['version'] != PRNG_VERSION):
        raise ValueError('Unsupported sealed private PRNG algorithm/version')
    if not isinstance(provenance.get('source'), str) or not provenance['source']:
        raise ValueError('Private PRNG state generation source is required')
    return raw


class R5Clock(FormationClock):
    def __init__(self, initial, model, road, parameters, policy_parameters, controlled, scripts,
                 initial_memories):
        super().__init__(initial, model, road, parameters, policy_parameters, controlled, scripts)
        self.memories = restore_initial_memories(initial_memories, self.controlled,
                                                self.p['r5_enabled'], self.p['formation_enabled'])

    def _check_features(self):
        super()._check_features()
        if any(type(values.get('r5_enabled')) is not bool for values in (self.p, self.policy)):
            raise ValueError('R5 clock and policy switches must be explicit booleans')
        if self.p['r5_enabled'] != self.policy['r5_enabled']:
            raise ValueError('R5 clock and policy switches must agree')
