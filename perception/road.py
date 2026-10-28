"""Sensor-side road geometry. No complete map is passed to a controller.

Only the validated, adjoining, straight, eastbound lane geometry is supported.
Lines describe physical boundaries/markings without lane, edge or slot labels.
"""
from dataclasses import dataclass
import math
import xml.etree.ElementTree as ET
from perception.contracts import RoadObservation


def ego_point(x, y, ego):
    dx, dy = x-ego.x_m, y-ego.y_m
    c, s = math.cos(ego.heading_rad), math.sin(ego.heading_rad)
    return (c*dx+s*dy, -s*dx+c*dy)


def snap_box_point(point, rear, front, side, tolerance):
    values = []
    for value,lower,upper in ((point[0],-rear,front),(point[1],-side,side)):
        if abs(value-lower) <= tolerance:
            value = lower
        elif abs(value-upper) <= tolerance:
            value = upper
        values.append(value)
    return tuple(values)


def box_tolerance(parameters):
    return parameters['sensor_roundoff_ulps']*math.ulp(max(parameters[k] for k in ('rear_range_m','front_range_m','side_range_m')))


def in_box(point, parameters):
    x,y = snap_box_point(point,parameters['rear_range_m'],parameters['front_range_m'],
                         parameters['side_range_m'],box_tolerance(parameters))
    return -parameters['rear_range_m'] <= x <= parameters['front_range_m'] and abs(y) <= parameters['side_range_m']


def clip_segment(a, b, rear, front, side, tolerance=0.):
    """Slab clipping, inclusive boundary; retain point intersections as points."""
    a,b = (snap_box_point(p,rear,front,side,tolerance) for p in (a,b))
    lo, hi = 0., 1.
    for start, end, lower, upper in ((a[0], b[0], -rear, front), (a[1], b[1], -side, side)):
        delta = end-start
        if delta == 0:
            if not lower <= start <= upper:
                return None
        else:
            u, v = (lower-start)/delta, (upper-start)/delta
            lo, hi = max(lo, min(u, v)), min(hi, max(u, v))
            if lo > hi:
                if (lo-hi)*max(abs(b[0]-a[0]),abs(b[1]-a[1])) > tolerance:
                    return None
                lo = hi = (lo+hi)/2
    # Clamp only floating point clipping roundoff, never expand the sensor box.
    def point(t):
        return (max(-rear, min(front, a[0]+t*(b[0]-a[0]))),
                max(-side, min(side, a[1]+t*(b[1]-a[1]))))
    return (point(lo), point(hi))


def merge_horizontal(lines):
    """Remove artificial edge segmentation of the same physical line."""
    groups, rest = {}, []
    for a, b in lines:
        if a[1] == b[1]:
            groups.setdefault(a[1], []).append(tuple(sorted((a[0], b[0]))))
        else:
            rest.append((a, b))
    for y, intervals in groups.items():
        merged = []
        for start, end in sorted(intervals):
            if merged and start <= merged[-1][1]:
                merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
            else:
                merged.append((start, end))
        rest.extend(((a, y), (b, y)) for a, b in merged)
    return tuple(sorted(rest))


@dataclass(frozen=True, slots=True)
class VisibleRoad:
    boundaries: tuple
    markings: tuple

    @classmethod
    def from_net(cls, path):
        from research.common import ROOT
        from safety.geometry import RoadEnvelope
        path = ROOT / path
        envelope = RoadEnvelope.from_net(path)
        boundaries, markings = [], []
        for x0, x1, y0, y1 in envelope.regions:
            boundaries.extend((((x0, y0), (x1, y0)), ((x0, y1), (x1, y1))))
        for a, b in zip(envelope.regions, envelope.regions[1:]):
            for y1, y2 in ((a[2], b[2]), (a[3], b[3])):
                if y1 != y2:
                    boundaries.append(((a[1], min(y1, y2)), (a[1], max(y1, y2))))
        for e in ET.parse(path).getroot().findall('edge'):
            if e.get('function') == 'internal':
                continue
            lanes = sorted(e.findall('lane'), key=lambda lane: int(lane.get('index')))
            for lane in lanes[:-1]:
                shape = [tuple(map(float, p.split(','))) for p in lane.get('shape').split()]
                y = shape[0][1]+float(lane.get('width'))/2
                markings.append(((shape[0][0], y), (shape[-1][0], y)))
        return cls(merge_horizontal(boundaries), merge_horizontal(markings))

    def observe(self, ego, parameters):
        def crop(lines):
            found = []
            for a, b in lines:
                segment = clip_segment(ego_point(*a, ego), ego_point(*b, ego),
                                       parameters['rear_range_m'], parameters['front_range_m'],
                                       parameters['side_range_m'],box_tolerance(parameters))
                if segment is not None:
                    found.append(segment)
            return tuple(sorted(set(found)))
        return RoadObservation(ego.time_s, crop(self.boundaries), crop(self.markings))
