"""SAT and conservative adaptive sweeps of linearly interpolated substep poses.

An unresolved adaptive leaf is reported as a potential violation. This is not
a continuous-time proof for arbitrary unsampled nonlinear paths.
"""
from dataclasses import replace
import math
import xml.etree.ElementTree as ET
from models.geometry import interpolate,vertex_motion_bound


def separation_gap(a,b):
    pa,pb=a.corners(),b.corners()
    gaps=[]
    for body in (a,b):
        for theta in (body.heading,body.heading+math.pi/2):
            axis=(math.cos(theta),math.sin(theta))
            aa=[x*axis[0]+y*axis[1] for x,y in pa]
            bb=[x*axis[0]+y*axis[1] for x,y in pb]
            gaps.append(max(min(bb)-max(aa),min(aa)-max(bb)))
    return max(gaps)


def collide(a,b):
    return separation_gap(a,b)<=1e-10


def swept_collision(a0,a1,b0,b1,max_depth=12):
    am,bm=interpolate(a0,a1,.5),interpolate(b0,b1,.5)
    if any(collide(a,b) for a,b in ((a0,b0),(a1,b1),(am,bm))):
        return True
    bound=(vertex_motion_bound(a0,a1)+vertex_motion_bound(b0,b1))/2
    if separation_gap(am,bm)>bound+1e-10:
        return False
    if max_depth<=0:
        return True
    return swept_collision(a0,am,b0,bm,max_depth-1) or swept_collision(am,a1,bm,b1,max_depth-1)


def clip_x(poly,x_boundary,keep_greater):
    out=[]
    def inside(p):
        return p[0]>=x_boundary if keep_greater else p[0]<=x_boundary
    for a,b in zip(poly,poly[1:]+poly[:1]):
        ia,ib=inside(a),inside(b)
        if ia:
            out.append(a)
        if ia!=ib:
            f=(x_boundary-a[0])/(b[0]-a[0])
            out.append((x_boundary,a[1]+f*(b[1]-a[1])))
    return out


class RoadEnvelope:
    def __init__(self,regions):
        self.regions=tuple(sorted(regions))
        if not self.regions or any(abs(a[1]-b[0])>1e-7 for a,b in zip(self.regions,self.regions[1:])):
            raise ValueError('Road auditor requires adjoining straight x-aligned segments')

    @classmethod
    def from_net(cls,path):
        regions=[]
        for e in ET.parse(path).getroot().findall('edge'):
            if e.get('function')=='internal':
                continue
            points=[]
            lows,highs=[],[]
            for lane in e.findall('lane'):
                shape=[tuple(map(float,p.split(','))) for p in lane.get('shape').split()]
                if max(p[1] for p in shape)-min(p[1] for p in shape)>1e-7:
                    raise ValueError('Only the validated straight road is supported by this envelope')
                points.extend(shape)
                lows.append(shape[0][1]-float(lane.get('width'))/2)
                highs.append(shape[0][1]+float(lane.get('width'))/2)
            regions.append((min(p[0] for p in points),max(p[0] for p in points),min(lows),max(highs)))
        return cls(regions)

    def contains(self,body,padding=0):
        poly=list(replace(body,length=body.length+2*padding,width=body.width+2*padding).corners())
        if min(x for x,y in poly)<self.regions[0][0]-1e-9 or max(x for x,y in poly)>self.regions[-1][1]+1e-9:
            return False
        for x0,x1,y0,y1 in self.regions:
            piece=clip_x(clip_x(poly,x0,True),x1,False)
            if not piece or max(x for x,y in piece)-min(x for x,y in piece)<1e-10:
                continue
            if min(y for x,y in piece)<y0-1e-9 or max(y for x,y in piece)>y1+1e-9:
                return False
        return True


def swept_outside(road,a,b,max_depth=12):
    mid=interpolate(a,b,.5)
    if not all(road.contains(p) for p in (a,mid,b)):
        return True
    if road.contains(mid,padding=vertex_motion_bound(a,b)/2):
        return False
    if max_depth<=0:
        return True
    return swept_outside(road,a,mid,max_depth-1) or swept_outside(road,mid,b,max_depth-1)
