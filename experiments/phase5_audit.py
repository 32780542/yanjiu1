"""Read-only local-information counterfactuals; never imported by controllers."""
from dataclasses import asdict, replace
import json
from models.vehicle import VehicleState
from perception.ideal import IdealSensor, TruthVehicle, WorldFrame
from perception.road import ego_point, in_box
from experiments.phase3_replay import compare_tree


def isolation_rows(records, model, parameters, policy, road, controlled):
    """Rebuild every sensor history, then compare sampled same-memory decisions.

    The own memory comes from the independently replayed trace. This asks a
    controlled causal question at each sampled frame; it is not a claim that
    four unobserved counterfactual driving trajectories have been simulated.
    """
    if parameters['formation_enabled']:
        from noa.formation import memory_from_dict, decide
    else:
        from noa.contracts import memory_from_dict
        from noa.controller import decide
    kinds = ('identity_order', 'hidden_type', 'future_plan', 'outside_state')
    sensors = {(key, kind): IdealSensor(parameters, road) for key in controlled for kind in kinds}
    stride = parameters['phase5_isolation_stride']
    if type(stride) is not int or stride < 1:
        raise ValueError('Isolation audit stride must be a positive integer')
    for index, record in enumerate(records):
        cars = tuple(TruthVehicle(key, VehicleState(**state), model.p['length_m'], model.p['width_m'],
                    model.observe(VehicleState(**state))['a_long_mps2']) for key, state in record['initial'].items())
        for key in controlled:
            own = next(vehicle for vehicle in cars if vehicle.key == key)
            for kind in kinds:
                ego_key = key
                if kind == 'identity_order':
                    rename = lambda name: 'counterfactual_' + name[::-1]
                    ego_key = rename(key)
                    changed = tuple(replace(vehicle, key=rename(vehicle.key)) for vehicle in reversed(cars))
                elif kind == 'hidden_type':
                    changed = tuple(replace(vehicle, hidden_type='NOA' if i % 2 else 'HDV') for i, vehicle in enumerate(cars))
                elif kind == 'future_plan':
                    changed = tuple(replace(vehicle, future_plan=('unavailable', index, i, 'merge_then_brake')) for i, vehicle in enumerate(cars))
                else:
                    changed = tuple(vehicle for vehicle in cars if in_box(ego_point(vehicle.state.x_m, vehicle.state.y_m, own.state), parameters))
                    changed += (TruthVehicle('unobservable_counterfactual', replace(own.state, x_m=own.state.x_m + 10000 + index),
                                            10., 2.5, hidden_type='HDV'),)
                observed = sensors[key, kind].sample(ego_key, WorldFrame(changed))
                if index % stride and index != len(records) - 1:
                    continue
                memory = memory_from_dict(record['inputs'][key]['memory'])
                control = replace(observed, memory=replace(memory, observation_history=observed.memory.observation_history))
                decision = decide(control, policy)
                identical = True
                try:
                    compare_tree(record['inputs'][key], asdict(control), model.p['replay_absolute_tolerance'])
                    compare_tree(record['decisions'][key], asdict(decision), model.p['replay_absolute_tolerance'])
                except ValueError:
                    identical = False
                removal_changes = False
                if kind == 'hidden_type':
                    empty = replace(control, observation=replace(control.observation, neighbors=()))
                    removal_changes = decide(empty, policy).action != decision.action
                yield {'interval': index, 'ego': key, 'mutation': kind,
                       'mutated_frame': [asdict(vehicle) for vehicle in changed], 'input': asdict(control),
                       'decision': asdict(decision), 'identical': identical,
                       'visible_removal_changes_action': removal_changes}


def isolation_audit(records, model, p, policy, road, controlled, path):
    comparisons, sensitive, errors = 0, 0, []
    with path.open('w', encoding='utf-8') as handle:
        for row in isolation_rows(records, model, p, policy, road, controlled):
            handle.write(json.dumps(row, allow_nan=False) + '\n')
            comparisons += 1
            sensitive += row['visible_removal_changes_action']
            if not row['identical']:
                errors.append({name: row[name] for name in ('interval', 'ego', 'mutation')})
    return {'passed': comparisons > 0 and not errors, 'comparisons': comparisons, 'mismatches': errors,
            'visible_neighbor_removal_changes_action': sensitive,
            'sample_stride_intervals': p['phase5_isolation_stride'],
            'scope': 'Every sensor history rebuilt; sampled same-own-memory counterfactual decisions. Own memory separately validated by full trace replay.'}
