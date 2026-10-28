"""Install prescribed initial states before physical t=0, without a traffic policy.

Native insertion occurs at each state's mapped lane position, avoiding stale
lane order from large remote relocations. The external carrier's minGap is
explicit; physical SUMO collisions and all independent geometry audits remain.
This initializer does not run during any physical control interval.
"""
import traceback
import xml.etree.ElementTree as ET
from uuid import uuid4

from experiments.records import atomic_json
from models.geometry import to_sumo_pose
from research.common import ROOT, binary, lock_traci, write_xml
from simulation.multi_vehicle import FleetBridge

NET = ROOT/'scenarios/cai2024/bottleneck.net.xml'


def bootstrap(path, initial, model, p, stdout):
    routes = ET.Element('routes')
    ET.SubElement(routes, 'vType', id='external_noa', length=str(model.p['length_m']),
                  width=str(model.p['width_m']), maxSpeed=str(model.p['max_speed_mps']),
                  accel=str(model.p['max_accel_mps2']), decel='10', emergencyDecel='10',
                  speedFactor='1', speedDev='0', minGap=str(p['sumo_external_min_gap_m']))
    ET.SubElement(routes, 'route', id='full', edges='upstream downstream')
    ET.SubElement(routes, 'route', id='remaining', edges='downstream')
    write_xml(path/'routes.rou.xml', routes)
    cmd = [binary('sumo'), '-n', str(NET), '-r', str(path/'routes.rou.xml'),
           '--step-length', str(p['control_sync_dt_s']), '--seed', str(p['phase4_seed']),
           '--no-step-log', 'true', '--time-to-teleport', '-1', '--collision.action', 'warn',
           '--log', str(path/'sumo.log')]
    atomic_json(path/'command.json', {'command':cmd, 'cwd':str(ROOT), 'seed':p['phase4_seed']})
    progress = {'status':'running', 'initial_readbacks':{}, 'completed_initialization_steps':0,
                'phase':'load_traci', 'insertion':{}, 'external_min_gap_m':p['sumo_external_min_gap_m']}
    atomic_json(path/'bootstrap.json', progress)
    conn = None
    try:
        traci = lock_traci()
        progress['phase'] = 'start_sumo'
        label = 'phase4_bootstrap_' + uuid4().hex
        traci.start(cmd, label=label, stdout=stdout)
        conn = traci.getConnection(label)
        progress.update(phase='insert_prescribed_positions', sumo_version=conn.getVersion())
        for key, state in sorted(initial.items()):
            x, y, angle = to_sumo_pose(state, model.p['length_m'])
            edge, position, lane = conn.simulation.convertRoad(x, y)
            if edge not in ('upstream', 'downstream'):
                raise ValueError(f'Initial state maps outside supported road: {edge}')
            route = 'full' if edge == 'upstream' else 'remaining'
            conn.vehicle.add(key, route, typeID='external_noa', departLane=str(lane),
                             departPos=str(position), departSpeed='0')
            progress['insertion'][key] = {'edge':edge, 'lane':lane, 'position_m':position, 'speed_mps':0}
        conn.simulationStep()
        progress.update(phase='install_initial_states', completed_initialization_steps=1)
        if set(conn.vehicle.getIDList()) != set(initial):
            progress['inserted_ids'] = list(conn.vehicle.getIDList())
            raise RuntimeError('Not all prescribed vehicles inserted during bootstrap')
        for key, state in sorted(initial.items()):
            conn.vehicle.setSpeedMode(key, model.p['sumo_speed_mode'])
            conn.vehicle.setLaneChangeMode(key, model.p['sumo_lane_change_mode'])
            x, y, angle = to_sumo_pose(state, model.p['length_m'])
            conn.vehicle.setSpeed(key, model.observe(state)['speed_mps'])
            conn.vehicle.moveToXY(key, '', -1, x, y, angle=angle, keepRoute=model.p['sumo_move_keep_route'])
        conn.simulationStep()
        progress.update(phase='initial_readback', completed_initialization_steps=2,
                        sumo_time_s=conn.simulation.getTime())
        bridge = FleetBridge(conn, initial, model, p['control_sync_dt_s'])
        progress.update(status='completed', initial_readbacks=bridge.initial_reports,
                        excluded_initialization_steps=2, time_offset_s=bridge.time_offset,
                        purpose='Install frozen CG states; no physical-time scheduling or control intervention')
        atomic_json(path/'bootstrap.json', progress)
        return conn, bridge
    except BaseException as exc:
        progress.update(status='failed', error=f'{type(exc).__name__}: {exc}',
                        traceback=traceback.format_exc(), initial_readbacks=getattr(exc, 'fleet_initial_reports', {}))
        atomic_json(path/'bootstrap.json', progress)
        if conn is not None:
            conn.close()
        raise
