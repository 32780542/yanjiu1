"""Physical small cases fixed before the first stage4 run; no actor coordination."""
from dataclasses import asdict
from models.kinematic import kinematic_state


def cases(p):
    def state(x,y,v,**kwargs):
        return asdict(kinematic_state(p,x_m=x,y_m=y,vx_mps=v,**kwargs))
    def case(name,duration,ego,others=(),requirements=None,purpose='',stress=False):
        initial={'ego':state(*ego)}
        scripts={}
        for key,position,script in others:
            initial[key]=state(*position)
            scripts[key]=script
        return {'name':name,'duration_s':duration,'controlled':['ego'],'initial':initial,'scripts':scripts,
                'requirements':requirements or {},'purpose':purpose,'stress':stress}
    return [
        case('cruise_speed_step',12,(100,1.65,10),requirements={'min_final_speed_mps':19,'final_y_m':1.65},purpose='Accelerate toward generic 20m/s cruise target'),
        {**case('lane_keep',6,(250,4.95,20),requirements={'final_y_m':4.95},purpose='Recover small own lateral/heading error'),
         'initial':{'ego':state(250,4.8,20,heading_rad=.02)}},
        case('slow_following',14,(250,1.65,18),[
            ('lead',(325,1.65,12),{'speed_steps':[[0,12]]}),
            ('adjacent',(255,4.95,18),{'speed_steps':[[0,18]]})],
            {'max_final_speed_mps':14,'modes_any':['FOLLOW']},'Slow front vehicle with adjacent gap occupied'),
        case('stop_restart',30,(200,1.65,12),[
            ('lead',(280,1.65,12),{'speed_steps':[[0,12],[3,0],[20,15]]}),
            ('block',(205,4.95,12),{'speed_steps':[[0,12],[3,0],[20,15]]})],
            {'minimum_speed_below_mps':1,'min_final_speed_mps':2},'Lead stops and restarts on its own frozen schedule'),
        case('normal_lane_change',15,(250,1.65,20),[
            ('lead',(340,1.65,10),{'speed_steps':[[0,10]]})],
            {'min_lane_changes':1,'modes_any':['EXECUTE_LC']},'Local overtake of slow lead with clear adjacent lane'),
        case('two_lane_changes',24,(100,1.65,20),[
            ('lead',(190,1.65,10),{'speed_steps':[[0,10]]}),
            ('second',(330,4.95,10),{'speed_steps':[[0,10]]})],
            {'min_lane_changes':2},'Sequential locally justified changes; no destination lane injected'),
        case('fast_rear_gap',6,(250,1.65,18),[
            ('lead',(335,1.65,10),{'speed_steps':[[0,10]]}),
            ('rear',(210,4.95,30),{'speed_steps':[[0,30]]})],
            {'no_lane_change_before_s':2},'Do not enter an adjacent lane ahead of a fast approaching rear car'),
        case('observed_cut_in',15,(250,1.65,18),[
            ('cutin',(315,4.95,12),{'speed_steps':[[0,12]],'lane_change':{'start_s':1,'y_start_m':4.95,'y_target_m':1.65,'duration_s':5,'speed_mps':12}})],
            {},'Exogenous neighbor cuts in using own preset curve; controller cannot read that plan'),
        case('merge_clear',16,(850,8.25,18),requirements={'min_final_x_m':1010,'max_final_y_m':5.4,'modes_any':['MERGE']},purpose='Observed terminating lane, empty adjacent lane, cross into downstream'),
        case('merge_gap_after_queue',12,(875,8.25,15),[
            ('front_block',(930,4.95,0),{'speed_steps':[[0,0]]}),
            ('rear_block',(865,4.95,0),{'speed_steps':[[0,0]]})],
            {'min_final_x_m':1010,'max_final_y_m':5.4},'First development run showed these two stopped cars leave a legal path after the queue; retained as a distinct gap-selection case'),
        case('merge_no_gap',16,(875,8.25,15),[
            ('queued_'+str(i),(865+6*i,4.95,0),{'speed_steps':[[0,0]]}) for i in range(28)],
            {'max_final_x_m':997,'max_final_speed_mps':.1},'Stationary target-lane queue extends beyond the lane end; each 2m inter-body gap is shorter than the4m ego body, forcing stop/wait'),
        {'name':'independent_noa_pair','duration_s':10,'controlled':['ego','other'],
         'initial':{'ego':state(250,1.65,18),'other':state(300,4.95,15)},'scripts':{},
         'requirements':{'min_final_speed_mps':19},'purpose':'Two independent NOA policies with separate own memory and common physics time, formation off','stress':False},
        case('cross_edge',9,(950,1.65,20),[
            ('neighbor',(1030,4.95,18),{'speed_steps':[[0,18]]})],
            {'min_final_x_m':1010,'final_y_m':1.65},'Continuous local sensing and motion across edge boundary'),
        case('reference_exits_range',5,(250,1.65,20),[
            ('departing',(430,4.95,33.3),{'speed_steps':[[0,33.3]]})],
            {'neighbor_count_decreases':True},'Neighbor leaves finite forward observation range'),
        case('urgent_braking_stress',8,(200,1.65,20),[
            ('lead',(225,1.65,10),{'speed_steps':[[0,10]],'acceleration_steps':[[0,-6]]}),
            ('block',(202,4.95,20),{'speed_steps':[[0,20]]})],
            {'modes_any':['EMERGENCY']},'Predeclared severe closing/braking stress; collision or comfort failure retained',True),
    ]
