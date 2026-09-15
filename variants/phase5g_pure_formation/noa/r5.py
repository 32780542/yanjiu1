"""Pure visible-geometry contention gate and own sealed SplitMix64 state.

No peer intent, sensor label, shared stream, clock entropy or external source.
Physical association is compatibility, not a true identity certificate.
"""
from dataclasses import astuple, replace
import math

from noa.contracts import validate_r5_memory
from noa.prediction import measured_bodies
from noa.road import world_point

PRNG_VERSION='splitmix64_high53_v1'
HARD_YIELD=('yield_entered','yield_visible_inward_motion','yield_visible_front','yield_occupied_corridor',
            'yield_visible_upper_lane')


def _lane_priority_enabled(p):
    enabled=p.get('r5_lane_priority_enabled',False)
    if type(enabled) is not bool:
        raise ValueError('r5_lane_priority_enabled must be an exact bool')
    return enabled


def draw_uniform(state):
    if type(state) is not int or not 0 <= state < 2**64:
        raise ValueError('Private PRNG state must be an exact uint64')
    mask=2**64-1
    state=(state+0x9E3779B97F4A7C15)&mask
    word=state
    word=((word^(word>>30))*0xBF58476D1CE4E5B9)&mask
    word=((word^(word>>27))*0x94D049BB133111EB)&mask
    word^=word>>31
    return state,word,(word>>11)/float(1<<53)


def validate(memory,now,p):
    _lane_priority_enabled(p)
    validate_r5_memory(memory)
    if p.get('r5_enabled',False) is not True or memory.r5_rng_state is None:
        raise ValueError('Enabled R5 requires its sealed private initial state')
    for name in ('r5_front_margin_m','r5_visible_inward_speed_mps','r5_yield_deceleration_mps2',
                 'r5_backoff_min_s','r5_backoff_max_s','r5_clear_stable_s'):
        value=p[name]
        if type(value) not in (float,int) or not math.isfinite(value) or value<=0:
            raise ValueError('Invalid positive R5 parameter: '+name)
    if p['r5_backoff_max_s']<=p['r5_backoff_min_s']:
        raise ValueError('Invalid R5 backoff interval')
    for value in (memory.r5_last_time_s,memory.r5_clear_since_s):
        if value is not None and value>now+1e-9:
            raise ValueError('R5 memory timestamp is from the future')
    if memory.r5_phase=='ELIGIBLE' and memory.r5_deadline_s>now+1e-9:
        raise ValueError('Eligible R5 deadline is in the future')


def _half(body):
    c,s=abs(math.cos(body.heading)),abs(math.sin(body.heading))
    return (body.length*c+body.width*s)/2,(body.length*s+body.width*c)/2


def _strip(control,road,target,p):
    e=control.ego
    tol=p['noa_geometry_tolerance_m']
    heights=[]
    for line in control.observation.road.boundary_polylines_m+control.observation.road.marking_polylines_m:
        points=tuple(world_point(point,e) for point in line)
        for a,b in zip(points,points[1:]):
            if abs(a[1]-b[1])<=tol and min(a[0],b[0])-tol<=e.x_m<=max(a[0],b[0])+tol:
                heights.append((a[1]+b[1])/2)
    unique=[]
    for y in sorted(heights):
        if not unique or y-unique[-1]>tol:unique.append(y)
    pairs=[(a,b) for a,b in zip(unique,unique[1:]) if abs((a+b)/2-target)<=tol]
    if len(pairs)!=1 or not any(abs(target-y)<=tol for y in road.centers_m):
        raise ValueError('R5 target strip must come from current visible geometry')
    return pairs[0]


def _visible_lane(control,road,x,y,hx,hy,p):
    """Certify one observed strip over the whole body's conservative rectangle.

    Each segment endpoint splits the rectangle's x extent. Checking every
    section and interval detects clipped ends and interior visibility gaps;
    boundaries are never extended from ego's section to a peer's position.
    Return a shared geometric center, not a nearest-center or label fallback.
    """
    tol=p['noa_geometry_tolerance_m']
    segments=[]
    for physical,lines in ((True,control.observation.road.boundary_polylines_m),
                           (False,control.observation.road.marking_polylines_m)):
        for line in lines:
            points=tuple(world_point(point,control.ego) for point in line)
            for a,b in zip(points,points[1:]):
                if abs(a[1]-b[1])<=tol and abs(a[0]-b[0])>tol:
                    segments.append((min(a[0],b[0]),max(a[0],b[0]),(a[1]+b[1])/2,physical))
    cuts=sorted({x-hx,x+hx}|{v for a,b,_,_ in segments for v in (a,b) if x-hx<v<x+hx})
    sections=cuts+[(a+b)/2 for a,b in zip(cuts,cuts[1:])]
    lane=None
    for at in sections:
        visible=[(height,physical) for a,b,height,physical in segments if a<=at<=b]
        edges=[height for height,physical in visible if physical]
        if not edges or max(edges)-min(edges)<=tol:
            return None
        heights=[]
        for height in sorted(height for height,_ in visible if min(edges)<=height<=max(edges)):
            if not heights or height-heights[-1]>tol:heights.append(height)
        strips=list(zip(heights,heights[1:]))
        distances=[abs((a+b)/2-y) for a,b in strips]
        if sum(distance<=min(distances)+tol for distance in distances)!=1:
            return None
        fits=[(a+b)/2 for a,b in strips if a+tol<=y-hy and y+hy<=b-tol]
        if len(fits)!=1:
            return None
        shared=[center for center in road.centers_m if abs(center-fits[0])<=tol]
        if len(shared)!=1 or (lane is not None and lane!=shared[0]):
            return None
        lane=shared[0]
    return lane


def _lane_relation(ego_lane,peer_lane,dx,margin):
    """1: peer higher; -1: ego higher; 0: incomparable. Never a sort key."""
    if ego_lane is None or peer_lane is None:return 0
    if peer_lane>ego_lane:return 1
    if peer_lane<ego_lane:return -1
    if dx>margin:return 1
    if dx < -margin:return -1
    return 0


def assess_candidate(control,road,candidate,memory,p):
    """Side-effect-free assessment; all signatures contain permitted physics."""
    lane_priority=_lane_priority_enabled(p)
    e=control.ego
    target=min(road.centers_m,key=lambda y:abs(y-candidate.y_target_m))
    if abs(target-candidate.y_target_m)>p['noa_geometry_tolerance_m']:
        raise ValueError('R5 candidate target is not a visible center')
    lower,upper=_strip(control,road,target,p)
    tol=p['noa_geometry_tolerance_m']
    c,s=abs(math.cos(e.heading_rad)),abs(math.sin(e.heading_rad))
    ego_half=(p['length_m']*c+p['width_m']*s)/2
    evx=e.vx_mps*math.cos(e.heading_rad)-e.vy_mps*math.sin(e.heading_rad)
    centers=road.centers_m
    target_index=centers.index(target)
    bodies=measured_bodies(control)
    near=[]
    for b in bodies:
        index=min(range(len(centers)),key=lambda i:(abs(centers[i]-b.y),centers[i]))
        hx,hy=_half(b)
        radius=ego_half+hx+2*p['noa_body_margin_m']+p['noa_standstill_gap_m']+abs(b.vx-evx)*candidate.duration_s
        if abs(index-target_index)<=1 and abs(b.x-e.x_m)<=radius:
            near.append(b)
    near_signatures=tuple(astuple(b) for b in near)
    occupied=[]
    for b in bodies:
        hx,hy=_half(b)
        if b.y+hy>lower+tol and b.y-hy<upper-tol:
            occupied.append((b.x-hx-p['noa_body_margin_m'],b.x+hx+p['noa_body_margin_m'],b))
    # Entered peers stay participants before they become a gap boundary. Gap
    # anchors exclude these participants so their crossing does not erase a latch.
    anchors=[row for row in occupied if astuple(row[2]) not in near_signatures]
    behind=[row for row in anchors if row[1]<e.x_m-ego_half]
    ahead=[row for row in anchors if row[0]>e.x_m+ego_half]
    rear=max(behind,key=lambda row:row[1]) if behind else None
    front=min(ahead,key=lambda row:row[0]) if ahead else None
    rear_signature=astuple(rear[2]) if rear else None
    front_signature=astuple(front[2]) if front else None
    entered=[b for b in near if b.y+_half(b)[1]>lower+tol and b.y-_half(b)[1]<upper-tol]
    inward=[b for b in near if ((b.y>upper and b.vy < -p['r5_visible_inward_speed_mps']) or
                              (b.y<lower and b.vy > p['r5_visible_inward_speed_mps']))]
    reason='no_potential_competition'
    participants=near
    if entered:reason='yield_entered'
    elif inward:reason='yield_visible_inward_motion'
    elif any(a<=e.x_m+ego_half and z>=e.x_m-ego_half for a,z,_ in occupied):
        reason='yield_occupied_corridor'
    else:
        left=max((z for a,z,_ in occupied if z<e.x_m-ego_half),default=-math.inf)
        right=min((a for a,z,_ in occupied if a>e.x_m+ego_half),default=math.inf)
        participants=[b for b in near if b.x-_half(b)[0]>left and b.x+_half(b)[0]<right]
        if participants:
            if lane_priority:
                ego_hy=(p['length_m']*s+p['width_m']*c)/2
                ego_lane=_visible_lane(control,road,e.x_m,e.y_m,ego_half,ego_hy,p)
                lanes=[_visible_lane(control,road,b.x,b.y,*_half(b),p) for b in participants]
                pairs=[_lane_relation(ego_lane,lane,b.x-e.x_m,p['r5_front_margin_m'])
                       for b,lane in zip(participants,lanes)]
                if any(value==1 for value in pairs):
                    upper_peer=any(value==1 and lane>ego_lane for value,lane in zip(pairs,lanes))
                    reason='yield_visible_upper_lane' if upper_peer else 'yield_visible_front'
                elif all(value==-1 for value in pairs):
                    reason='ego_visible_upper_lane' if any(lane<ego_lane for lane in lanes) else 'ego_visible_front'
                else:reason='ambiguous'
            else:
                dx=[b.x-e.x_m for b in participants]
                if any(x>p['r5_front_margin_m'] for x in dx):reason='yield_visible_front'
                elif all(x < -p['r5_front_margin_m'] for x in dx):reason='ego_visible_front'
                else:reason='ambiguous'
    signatures=tuple(astuple(b) for b in participants)
    return {'reason':reason,'target_y_m':target,'target_strip_m':(lower,upper),
            'participant_signatures':signatures,'entered_signatures':tuple(astuple(b) for b in entered),
            'inward_signatures':tuple(astuple(b) for b in inward),
            'episode_signature':(target,rear_signature,front_signature,signatures)}


def _compatible(old,new,dt,p):
    if dt==0:return old==new
    tol=p['noa_geometry_tolerance_m']
    omega=p['max_speed_mps']*abs(math.tan(p['max_steering_rad']))/p['wheelbase_m']
    bound=max(abs(p['min_accel_mps2']),p['max_accel_mps2'])+p['max_speed_mps']*omega
    heading=abs(math.atan2(math.sin(new[4]-old[4]),math.cos(new[4]-old[4])))
    return (all(abs(new[i]-old[i]-old[i+2]*dt)<=.5*bound*dt*dt+tol for i in (0,1)) and
            all(abs(new[i]-old[i])<=bound*dt+2*tol/dt for i in (2,3)) and
            heading<=omega*dt+tol/max(old[5:]) and
            all(abs(new[i]-old[i])<=tol for i in (5,6)))


def _unique(old,new,dt,p):
    if len(old)!=len(new):return False
    edges=[tuple(j for j,b in enumerate(new) if _compatible(a,b,dt,p)) for a in old]
    solutions=0
    def visit(index,used):
        nonlocal solutions
        if solutions>1:return
        if index==len(edges):
            solutions+=1
            return
        for j in edges[index]:
            if j not in used:visit(index+1,used|{j})
    visit(0,set())
    return solutions==1


def _same_episode(old,new,dt,p):
    if abs(old[0]-new[0])>p['noa_geometry_tolerance_m']:return 'new'
    if not _unique(old[3],new[3],dt,p):return 'unknown'
    old_anchors=tuple(v for v in old[1:3] if v is not None)
    new_anchors=tuple(v for v in new[1:3] if v is not None)
    roles_same=all((a is None and b is None) or
                   (a is not None and b is not None and _compatible(a,b,dt,p))
                   for a,b in zip(old[1:3],new[1:3]))
    if not roles_same and old_anchors and _unique(old_anchors,new_anchors,dt,p):
        return 'new'
    for a,b in zip(old[1:3],new[1:3]):
        if a is None and b is None:continue
        if a is None or b is None:return 'unknown'
        if not _compatible(a,b,dt,p):return 'unknown'
    return 'same'


def advance_backoff(assessment,memory,now,p,allow_draw=True):
    """Commit at most one own episode draw; no candidate traversal side effect."""
    validate(memory,now,p)
    reason=assessment['reason']
    current=assessment['episode_signature']
    old=memory.r5_episode_signature
    dt=0. if memory.r5_last_time_s is None else now-memory.r5_last_time_s
    m=replace(memory,r5_last_time_s=now)
    drawn=[]
    relation='same'
    if reason=='no_potential_competition':
        if old is not None and abs(old[0]-current[0])>p['noa_geometry_tolerance_m']:
            # This is only a candidate preview until its own original guard
            # accepts and NOA selects it. A different clear target inherits no
            # other target's private waiting or clearing clock.
            m=replace(m,r5_phase='IDLE',r5_deadline_s=None,r5_episode_signature=None,r5_clear_since_s=None)
            return m,diagnostic(m,assessment,drawn,False,'different_clear_target')
        if old is not None:
            if m.r5_phase=='BACKOFF' and now>=m.r5_deadline_s-1e-9:
                m=replace(m,r5_phase='ELIGIBLE')
            since=now if memory.r5_clear_since_s is None or dt>p['control_sync_dt_s']+1e-9 else memory.r5_clear_since_s
            if now-since>=p['r5_clear_stable_s']-1e-9:
                m=replace(m,r5_phase='IDLE',r5_deadline_s=None,r5_episode_signature=None,r5_clear_since_s=None)
            else:m=replace(m,r5_clear_since_s=since)
        return m,diagnostic(m,assessment,drawn,blocking=m.r5_phase!='IDLE',reason=reason)
    m=replace(m,r5_clear_since_s=None)
    if old is not None:
        if abs(old[0]-current[0])>p['noa_geometry_tolerance_m']:
            relation='new'
        elif memory.r5_phase=='UNKNOWN' or dt>p['control_sync_dt_s']+1e-9:
            # UNKNOWN retains a deadline, never a fresh visible signature.
            # It can clear from current observations or a new visible target,
            # but cannot revive an old position using the latest tick's dt.
            relation='unknown'
        else:
            relation=_same_episode(old,current,max(0.,dt),p)
    if relation=='unknown':
        m=replace(m,r5_phase='UNKNOWN')
        return m,diagnostic(m,assessment,drawn,True,'episode_association_unknown')
    if old is None or relation=='new':
        m=replace(m,r5_episode_signature=current,r5_deadline_s=None)
    else:m=replace(m,r5_episode_signature=current)
    if reason in HARD_YIELD:
        m=replace(m,r5_phase='YIELD')
        return m,diagnostic(m,assessment,drawn,True,reason)
    if reason=='ambiguous' and m.r5_deadline_s is None:
        if not allow_draw:
            m=replace(m,r5_phase='YIELD')
            return m,diagnostic(m,assessment,drawn,True,'ambiguous_requires_private_draw')
        state,word,u=draw_uniform(m.r5_rng_state)
        delay=p['r5_backoff_min_s']+u*(p['r5_backoff_max_s']-p['r5_backoff_min_s'])
        m=replace(m,r5_rng_state=state,r5_draw_count=m.r5_draw_count+1,r5_deadline_s=now+delay)
        drawn=[{'word_u64':word,'unit_interval':u,'delay_s':delay}]
    if m.r5_deadline_s is not None:
        blocked=now<m.r5_deadline_s-1e-9
        if not blocked and reason=='ambiguous':
            m=replace(m,r5_phase='YIELD')
            return m,diagnostic(m,assessment,drawn,True,'expired_ambiguous_wait')
        m=replace(m,r5_phase='BACKOFF' if blocked else 'ELIGIBLE')
        return m,diagnostic(m,assessment,drawn,blocked,'private_backoff_wait' if blocked else 'private_backoff_expired')
    # A newly unambiguous ego-front candidate needs no random episode.
    m=replace(m,r5_phase='IDLE',r5_episode_signature=None,r5_deadline_s=None)
    return m,diagnostic(m,assessment,drawn,False,reason)


def diagnostic(memory,assessment,drawn,blocking,reason):
    return {'phase':memory.r5_phase,'reason':reason,'assessment':assessment,'blocking':blocking,
            'deadline_s':memory.r5_deadline_s,'draw_count':memory.r5_draw_count,'draws_this_tick':len(drawn),
            'draws':drawn,'proposed_yield_mps2':None,'guard':None,
            'association_scope':'current visible physics compatibility only; no true identity guarantee'}
