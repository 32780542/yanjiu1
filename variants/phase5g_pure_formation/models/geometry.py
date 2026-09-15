from dataclasses import dataclass
import math


@dataclass(frozen=True,slots=True)
class BodyPose:
    x: float
    y: float
    heading: float
    length: float
    width: float

    def corners(self):
        c,s=math.cos(self.heading),math.sin(self.heading)
        return tuple((self.x+c*x-s*y,self.y+s*x+c*y) for x,y in
                     ((self.length/2,self.width/2),(-self.length/2,self.width/2),
                      (-self.length/2,-self.width/2),(self.length/2,-self.width/2)))


def body_from_state(state,parameters):
    return BodyPose(state.x_m,state.y_m,state.heading_rad,parameters['length_m'],parameters['width_m'])


def to_sumo_pose(state,length):
    return (state.x_m+length/2*math.cos(state.heading_rad),
            state.y_m+length/2*math.sin(state.heading_rad),(90-math.degrees(state.heading_rad))%360)


def from_sumo_pose(front_x,front_y,angle_deg,length):
    psi=math.radians(90-angle_deg)
    return front_x-length/2*math.cos(psi),front_y-length/2*math.sin(psi),psi


def interpolate(a,b,fraction):
    if (a.length,a.width)!=(b.length,b.width):
        raise ValueError('Body dimensions cannot change inside a swept interval')
    return BodyPose(a.x+(b.x-a.x)*fraction,a.y+(b.y-a.y)*fraction,
                    a.heading+(b.heading-a.heading)*fraction,a.length,a.width)


def vertex_motion_bound(a,b):
    return math.hypot(a.x-b.x,a.y-b.y)+math.hypot(a.length/2,a.width/2)*abs(b.heading-a.heading)
