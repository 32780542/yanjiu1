"""Eight visible regions and two predeclared if/else reference orders.

Lanes are reconstructed from current visible road geometry. Side/rear regions
are occupancy diagnostics, never target references or hidden scheduling input.
"""
import math
from noa.prediction import measured_bodies


def classify(control, road, p):
    ego = control.ego
    centers = road.centers_m
    current = centers.index(road.current_center_m)
    own_projection = p['length_m']*abs(math.cos(ego.heading_rad))+p['width_m']*abs(math.sin(ego.heading_rad))
    counts = {name:0 for name in ('F', 'B', 'L', 'R', 'FL', 'FR', 'BL', 'BR', 'X')}
    items, overlap = [], False
    for body in measured_bodies(control):
        lane = min(range(len(centers)), key=lambda i:(abs(centers[i]-body.y), centers[i]))
        offset, dx = lane-current, body.x-ego.x_m
        stable = abs(body.y-centers[lane]) <= p['noa_completion_lateral_error_m']
        projection = body.length*abs(math.cos(body.heading))+body.width*abs(math.sin(body.heading))
        band = (own_projection+projection)/2+2*p['noa_body_margin_m']
        if not stable or abs(offset) > 1:
            region = 'X'
        elif offset == 0:
            region = 'F' if dx > 0 else 'B'
            overlap |= abs(dx) <= band+p['noa_geometry_tolerance_m']
        elif abs(dx) <= band+p['noa_geometry_tolerance_m']:
            region = 'L' if offset > 0 else 'R'
        elif dx > 0:
            region = 'FL' if offset > 0 else 'FR'
        else:
            region = 'BL' if offset > 0 else 'BR'
        counts[region] += 1
        items.append({'body':body, 'lane_offset':offset, 'region':region,
                      'side_band_half_length_m':band})
    return {'items':items, 'region_counts':counts, 'ego_lane_overlap':overlap}


def rank(candidates, held, p):
    """No weighted search: hold, then nearest member of the first usable group."""
    if held is not None:
        return [held]+[candidate for candidate in candidates if candidate is not held], 'hold_visible_forward_reference'
    groups = ((('F',), 'front'), (('FL', 'FR'), 'forward_corner'))
    if p['formation_reference_rule'] == 'corner_first':
        groups = tuple(reversed(groups))
    for regions, label in groups:
        group = [candidate for candidate in candidates if candidate['region'] in regions]
        if not group:
            continue
        nearest = min(candidate['dx_m'] for candidate in group)
        close = [candidate for candidate in group if candidate['dx_m']-nearest <= p['noa_geometry_tolerance_m']]
        speed_cost = min(abs(candidate['relative_speed_mps']) for candidate in close)
        tied = [candidate for candidate in close if abs(candidate['relative_speed_mps']) == speed_cost]
        if len(tied) != 1:
            return [], 'ambiguous_'+label
        chosen = tied[0]
        return [chosen]+[candidate for candidate in candidates if candidate is not chosen], 'nearest_'+label
    return [], 'no_forward_reference'
