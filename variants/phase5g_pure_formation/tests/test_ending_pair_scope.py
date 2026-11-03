from noa import native_rules as r

def car(track,x,lane):
    return r.Vehicle(track,x,(lane+.5)*3.3,28.8,lane)

def test_actual_ending_lane_keeps_three_lane_pair_geometry():
    a,b=car(0,700,2),car(1,700,1)
    forward,count=r._pair_error(a,b,3,640)
    backward,reverse_count=r._pair_error(b,a,2,640)
    assert count==reverse_count==3
    assert (r._phase(1,3),r._phase(2,3))==(15.0,0.0)
    # y=4.949999999999999 is continuously interpolated, not rounded to lane centre.
    physical_phase=r._physical_phase(b,3)-r._physical_phase(a,3)
    assert forward==physical_phase and backward==-physical_phase
    assert forward==-backward

def test_ending_unit_approaches_its_actual_gap_without_a_distant_head_wait():
    ego,front,middle=car(0,700,2),car(1,770,2),car(2,700,1)
    command,memory=r.decide(ego,[front,middle],r.Memory(),'transform',1000)
    assert command.reason=='approach_gap'
    assert command.lane is None
    assert memory.gap==(None,middle.track)
    assert command.target_x==715.0
    assert command.speed>r.CRUISE
