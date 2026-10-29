from noa import native_rules as r

def car(track,x,lane):
    return r.Vehicle(track,x,(lane+.5)*3.3,28.8,lane)

def test_actual_ending_lane_keeps_three_lane_pair_geometry():
    a,b=car(0,700,2),car(1,700,1)
    forward,count=r._pair_error(a,b,3,640)
    backward,reverse_count=r._pair_error(b,a,2,640)
    assert count==reverse_count==3
    assert forward==15 and backward==-15

def test_separate_ending_unit_waits_using_its_actual_three_lane_phase():
    ego,front,middle=car(0,700,2),car(1,770,2),car(2,700,1)
    command,_=r.decide(ego,[front,middle],r.Memory(),'transform',1000)
    assert command.reason=='ending_follower'
    assert command.lane is None
    assert command.speed>r.CRUISE
