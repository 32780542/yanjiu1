"""Declared small physical initial conditions; no traffic optimizer or arrivals."""
from dataclasses import asdict
from models.vehicle import VehicleState


def cases(p):
    def state(x,y,v,**kw):
        if p.get('motion_model') == 'kinematic_bicycle':
            from models.kinematic import kinematic_state
            kw = {k:value for k,value in kw.items() if k not in ('vy_mps','yaw_rate_radps')}
            return asdict(kinematic_state(p,x_m=x,y_m=y,vx_mps=v,**kw))
        return asdict(VehicleState(x_m=x,y_m=y,vx_mps=v,**kw))
    return [
        {'name':'local_following','duration_s':p['phase3_duration_s'],
         'initial':{'a':state(300,1.65,20),'b':state(330,1.65,16),
                    'c':state(330,4.95,20),'d':state(300,8.25,20),'e':state(450,8.25,20)},
         'purpose':'Five independent probes; front car, parallel neighbors, and an unoccluded farther target'},
        {'name':'cross_edge','duration_s':p['phase3_crossing_duration_s'],
         'initial':{'a':state(950,1.65,20),'b':state(1010,1.65,18),'c':state(960,4.95,20)},
         'purpose':'Observe across upstream/downstream from t=0 and preserve physical state through edge crossing'},
        {'name':'range_entry','duration_s':p['phase3_duration_s'],
         'initial':{'a':state(300,1.65,20),'b':state(501,4.95,15),'c':state(199,8.25,25)},
         'purpose':'Initially just beyond front/rear bounds; relative motion brings both into view'},
        {'name':'mid_lane_motion','duration_s':p['phase3_drift_duration_s'],
         'initial':{'a':state(600,1.65,20),'b':state(630,3.217,20,vy_mps=.4,heading_rad=.02,yaw_rate_radps=.01),
                    'c':state(660,8.25,20)},
         'purpose':'Continuous initial lateral motion between lanes; not a full autonomous lane-change maneuver'}]
