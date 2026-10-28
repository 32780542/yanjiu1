"""Reconstruct only currently observed straight road cross sections.

World alignment uses own pose, not a map. Clipped observation ends are unknown
space, never asserted to be physical lane ends. No lane IDs or widths are used.
"""
from dataclasses import dataclass
import math

from safety.geometry import RoadEnvelope


@dataclass(frozen=True, slots=True)
class LocalRoad:
    envelope: object
    centers_m: tuple[float, ...]
    current_center_m: float

    def lane_end(self, center_y, width, tolerance):
        regions = self.envelope.regions
        for before, after in zip(regions, regions[1:]):
            fits_before = before[2]+width/2 <= center_y <= before[3]-width/2
            fits_after = after[2]+width/2 <= center_y <= after[3]-width/2
            if fits_before and not fits_after and abs(before[1]-after[0]) <= tolerance:
                return before[1]
        return None


def world_point(point, ego):
    c, s = math.cos(ego.heading_rad), math.sin(ego.heading_rad)
    return (ego.x_m+c*point[0]-s*point[1], ego.y_m+s*point[0]+c*point[1])


def reconstruct(ego, observation, parameters):
    tolerance = parameters['noa_geometry_tolerance_m']
    boundary, markings = [], []
    for lines, target in ((observation.boundary_polylines_m, boundary),
                          (observation.marking_polylines_m, markings)):
        for line in lines:
            points = tuple(world_point(point, ego) for point in line)
            for a, b in zip(points, points[1:]):
                if abs(a[1]-b[1]) <= tolerance:
                    if abs(a[0]-b[0]) > tolerance:
                        target.append((min(a[0], b[0]), max(a[0], b[0]), (a[1]+b[1])/2))
                elif abs(a[0]-b[0]) > tolerance:
                    raise ValueError('NOA supports observed straight world-x-aligned road only')
    breaks = sorted({v for a, b, _ in boundary for v in (a, b)})
    regions = []
    for a, b in zip(breaks, breaks[1:]):
        if b-a <= tolerance:
            continue
        heights = [y for x0, x1, y in boundary if x0-tolerance <= (a+b)/2 <= x1+tolerance]
        if len(heights) >= 2 and max(heights)-min(heights) > tolerance:
            regions.append((a, b, min(heights), max(heights)))
    if not regions:
        raise ValueError('Insufficient observed physical road boundaries')
    section = next((r for r in regions if r[0]-tolerance <= ego.x_m <= r[1]+tolerance), None)
    if section is None:
        raise ValueError('Ego outside observed road extent')
    values = sorted([section[2], section[3]] + [y for a, b, y in markings
                    if a-tolerance <= ego.x_m <= b+tolerance and section[2] < y < section[3]])
    heights = []
    for value in values:
        if not heights or value-heights[-1] > tolerance:
            heights.append(value)
    centers = tuple((a+b)/2 for a, b in zip(heights, heights[1:])
                    if b-a >= parameters['width_m']+2*parameters['noa_body_margin_m'])
    if not centers:
        raise ValueError('No body-width traversable observed lane')
    return LocalRoad(RoadEnvelope(regions), centers, min(centers, key=lambda y: (abs(y-ego.y_m), y)))
