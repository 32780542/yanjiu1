"""Shared Bernoulli arrival tape; hidden types are offline initialization data."""
import csv
import hashlib
import math
import random
import xml.etree.ElementTree as ET
from research.common import ROOT, output_path, settings, write_json, write_xml, sha256
from research.network import SCENARIO


def probability(q_per_lane_hour, dt_s):
    if not all(math.isfinite(x) for x in (q_per_lane_hour, dt_s)) or q_per_lane_hour < 0 or dt_s <= 0:
        raise ValueError('Finite nonnegative per-lane demand and positive dt required')
    p = q_per_lane_hour * dt_s / 3600
    if p > 1:
        raise ValueError('Bernoulli probability exceeds 1')
    return p


def stream(seed, label):
    # Standard-library MT19937; domain-separated streams, seed independent of MPR.
    derived = int.from_bytes(hashlib.sha256(f'keyan1:v1:{seed}:{label}'.encode()).digest(), 'big')
    return random.Random(derived)


def generate(q_per_lane_hour, seed, duration_s, dt_s=.1):
    p = probability(q_per_lane_hour, dt_s)
    steps = round(duration_s / dt_s)
    if duration_s <= 0 or not math.isclose(steps * dt_s, duration_s, abs_tol=1e-9):
        raise ValueError('Duration must be a positive integer multiple of demand dt')
    arrivals = [stream(seed, f'arrival-lane-{i}') for i in range(3)]
    types = [stream(seed, f'type-lane-{i}') for i in range(3)]
    rows=[]
    for step in range(steps):
        for lane in range(3):
            u_arrival, u_type = arrivals[lane].random(), types[lane].random()
            if u_arrival < p:
                rows.append({'vehicle_id':f'veh_{lane}_{step:06d}', 'planned_depart_s':round(step*dt_s,9),
                             'depart_lane':lane, 'type_uniform':u_type})
    return rows


def assign_types(records, noa_fraction):
    if not math.isfinite(noa_fraction) or not 0 <= noa_fraction <= 1:
        raise ValueError('NOA fraction must lie in [0,1]')
    return [{**row, 'hidden_type':'NOA' if row['type_uniform'] < noa_fraction else 'HDV'} for row in records]


def write_csv(path, rows, fields):
    p=output_path(path)
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def routes_tree(rows, add_probe=False):
    main, paper, smoke = [settings(x) for x in ('no_comm_main','paper_reference','topology_smoke')]
    tree=ET.Element('routes')
    attrs={'id':'native_probe','vClass':smoke['vehicle_class'],'guiShape':smoke['gui_shape'],'carFollowModel':smoke['car_follow_model'],
           'laneChangeModel':smoke['lane_change_model'],'length':main['length_m'],'width':main['width_m'],'mass':main['mass_kg'],
           'maxSpeed':paper['max_speed_mps'],'accel':smoke['accel_mps2'],'decel':smoke['decel_mps2'],
           'emergencyDecel':smoke['emergency_decel_mps2'],'tau':smoke['tau_s'],'minGap':smoke['min_gap_m'],
           'delta':smoke['idm_delta'],'stepping':smoke['idm_stepping_s'],'speedFactor':smoke['speed_factor'],
           'speedDev':smoke['speed_deviation'],'lcStrategic':smoke['lc_strategic'],
           'lcCooperative':smoke['lc_cooperative'],'lcSpeedGain':smoke['lc_speed_gain'],
           'lcKeepRight':smoke['lc_keep_right'],'emissionClass':main['candidate_emission_class']}
    ET.SubElement(tree,'vType',**{k:str(v) for k,v in attrs.items()})
    ET.SubElement(tree,'route',id='through',edges='upstream downstream')
    for row in rows:
        ET.SubElement(tree,'vehicle',id=row['vehicle_id'],type='native_probe',route='through',
                      depart=f"{row['planned_depart_s']:.1f}",departLane=str(row['depart_lane']),
                      departPos=str(smoke['departure_position_m']),departSpeed=str(smoke['departure_speed_mps']))
    if add_probe:
        ET.SubElement(tree,'vehicle',id='termination_probe',type='native_probe',route='through',
                      depart=str(smoke['probe_time_s']),departLane='2',departPos=str(smoke['probe_position_m']),
                      departSpeed=str(smoke['probe_speed_mps']),color='1,0.3,0.1')
    return tree


def config_tree(route_name, output_dir, end_s):
    smoke=settings('topology_smoke')
    tree=ET.Element('configuration')
    inp=ET.SubElement(tree,'input')
    ET.SubElement(inp,'net-file',value='bottleneck.net.xml')
    ET.SubElement(inp,'route-files',value=route_name)
    time=ET.SubElement(tree,'time')
    for key,value in [('begin',0),('end',end_s),('step-length',smoke['sumo_dt_s'])]:
        ET.SubElement(time,key,value=str(value))
    proc=ET.SubElement(tree,'processing')
    for key,value in [('lanechange.duration',smoke['lanechange_duration_s']),('time-to-teleport',smoke['time_to_teleport_s']),
                      ('max-depart-delay',smoke['max_depart_delay_s']),('collision.action',smoke['collision_action']),
                      ('collision.check-junctions',str(smoke['collision_check_junctions']).lower())]:
        ET.SubElement(proc,key,value=str(value))
    rand=ET.SubElement(tree,'random_number')
    ET.SubElement(rand,'seed',value=str(smoke['seed']))
    out=ET.SubElement(tree,'output')
    for key,name in [('tripinfo-output','tripinfo.xml'),('summary-output','summary.xml'),('fcd-output','fcd.xml'),
                     ('lanechange-output','lanechanges.xml')]:
        ET.SubElement(out,key,value=str(output_path(output_dir)/name))
    ET.SubElement(out,'tripinfo-output.write-unfinished',value='true')
    report=ET.SubElement(tree,'report')
    ET.SubElement(report,'no-step-log',value='true')
    ET.SubElement(report,'log',value=str(output_path(output_dir)/'sumo.log'))
    return tree


def build_all():
    smoke,paper=settings('topology_smoke'),settings('paper_reference')
    summaries=[]
    for q in paper['flow_levels_per_lane_hour']:
        rows=generate(q,smoke['seed'],smoke['demand_duration_s'],smoke['demand_dt_s'])
        fields=['vehicle_id','planned_depart_s','depart_lane','type_uniform']
        base=SCENARIO/'demand'/f'q{q}_seed{smoke["seed"]}'
        write_csv(base.with_suffix('.csv'),rows,fields)
        write_csv(base.with_suffix('.types.csv'),assign_types(rows,smoke['hidden_noa_fraction']),fields+['hidden_type'])
        write_xml(base.with_suffix('.rou.xml'),routes_tree(rows))
        per_lane=[sum(r['depart_lane']==i for r in rows) for i in range(3)]
        summaries.append({'q_per_lane_hour':q,'q_total_hour':q*3,'probability_per_lane_step':probability(q,smoke['demand_dt_s']),
                          'duration_s':smoke['demand_duration_s'],'expected_per_lane':q*smoke['demand_duration_s']/3600,
                          'realized_per_lane':per_lane,'realized_total':len(rows),
                          'csv_sha256':sha256(base.with_suffix('.csv')),'routes_sha256':sha256(base.with_suffix('.rou.xml'))})
    q=smoke['smoke_q_per_lane_hour']
    rows=generate(q,smoke['seed'],smoke['smoke_demand_duration_s'],smoke['demand_dt_s'])
    write_csv(SCENARIO/'smoke_demand.csv',rows,['vehicle_id','planned_depart_s','depart_lane','type_uniform'])
    write_xml(SCENARIO/'smoke.rou.xml',routes_tree(rows,add_probe=True))
    (ROOT/'results/phase1/smoke').mkdir(parents=True,exist_ok=True)
    write_xml(SCENARIO/'smoke.sumocfg',config_tree('smoke.rou.xml','results/phase1/smoke',smoke['smoke_end_s']))
    write_xml(SCENARIO/'empty.rou.xml',ET.Element('routes'))
    (ROOT/'results/phase0/mcp_sim').mkdir(parents=True,exist_ok=True)
    write_xml(SCENARIO/'mcp_probe.sumocfg',config_tree('empty.rou.xml','results/phase0/mcp_sim',1))
    write_json('results/phase1/demand_manifest.json',{'mechanism':'independent per-lane Bernoulli per 0.1 s',
               'rng':'Python random.Random MT19937; SHA256 domain-separated seed; version pinned',
               'seed':smoke['seed'],'horizon':'[0,600) s; finite demand, not a fixed simulation cutoff',
               'coupling':'same seed uses nested arrivals across q; types independent of arrivals and MPR',
               'purpose':'Common input artifacts; only 60 s lowest-flow smoke executed', 'scenarios':summaries})
    print('Four fixed-seed demand tapes written; smoke demand is only the first 60 s at 1250 veh/(lane*h).')
