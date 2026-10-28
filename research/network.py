"""Build plain XML from paper dimensions. Never import a reference net.xml."""
import math
import xml.etree.ElementTree as ET
from research.common import ROOT, binary, command, settings, write_xml, write_json, sha256

SCENARIO = ROOT / 'scenarios/cai2024'


def build():
    paper, main = settings('paper_reference'), settings('no_comm_main')
    upstream, downstream = paper['upstream_length_m'], paper['downstream_length_m']
    nodes = ET.Element('nodes')
    for name, x in [('entry', 0), ('bottleneck', upstream), ('exit', upstream+downstream)]:
        ET.SubElement(nodes, 'node', id=name, x=str(x), y='0', type='priority', radius='0')
    edges = ET.Element('edges')
    for name, a, b, lanes, start, end in [
        ('upstream', 'entry', 'bottleneck', paper['upstream_lanes'], 0, upstream),
        ('downstream', 'bottleneck', 'exit', paper['downstream_lanes'], upstream, upstream+downstream)]:
        edge = ET.SubElement(edges, 'edge', id=name, attrib={'from':a, 'to':b}, numLanes=str(lanes),
                             speed=str(paper['max_speed_mps']), width=str(main['lane_width_m']),
                             length=str(end-start), spreadType='center')
        for lane in range(lanes):
            y = main['lane_width_m'] * (lane + .5)
            ET.SubElement(edge, 'lane', index=str(lane), width=str(main['lane_width_m']),
                          shape=f'{start},{y} {end},{y}')
    connections = ET.Element('connections')
    for lane in (0, 1):
        ET.SubElement(connections, 'connection', attrib={'from':'upstream', 'to':'downstream'},
                      fromLane=str(lane), toLane=str(lane))
    for suffix, tree in [('nod', nodes), ('edg', edges), ('con', connections)]:
        write_xml(SCENARIO / f'bottleneck.{suffix}.xml', tree)
    cmd = [binary('netconvert'), '--node-files', str(SCENARIO/'bottleneck.nod.xml'),
           '--edge-files', str(SCENARIO/'bottleneck.edg.xml'), '--connection-files', str(SCENARIO/'bottleneck.con.xml'),
           '--output-file', str(SCENARIO/'bottleneck.net.xml'), '--no-internal-links', 'true',
           '--offset.disable-normalization', 'true', '--junctions.corner-detail', '0']
    command(cmd, 'results/phase1/netconvert.json')
    result = validate_tree(ET.parse(SCENARIO/'bottleneck.net.xml').getroot())
    result['net_sha256'] = sha256(SCENARIO/'bottleneck.net.xml')
    write_json('results/phase1/network_validation.json', result)
    if not result['passed']:
        raise RuntimeError(f'Network invalid: {result["errors"]}')
    draw_topology()
    print('Network generated and independently checked: 1000 m x 3 lanes + 200 m x 2 lanes.')


def validate_tree(root):
    errors, lanes = [], []
    edge_specs = {'upstream':(3, 0., 1000.), 'downstream':(2, 1000., 1200.)}
    actual_edges = {e.get('id'):e for e in root.findall('edge')}
    if set(actual_edges) != set(edge_specs):
        errors.append('Unexpected or missing physical/internal edges')
    def check(condition, message):
        if not condition:
            errors.append(message)
    def close(a, b):
        return math.isfinite(a) and math.isclose(a, b, abs_tol=1e-6, rel_tol=0)
    for name, (n, x0, x1) in edge_specs.items():
        edge = actual_edges.get(name)
        if edge is None:
            errors.append(f'Missing edge {name}')
            continue
        lane_nodes = edge.findall('lane')
        check(len(lane_nodes) == n, f'{name} lane count')
        check({x.get('index') for x in lane_nodes} == {str(i) for i in range(n)}, f'{name} lane indexes')
        for lane in lane_nodes:
            try:
                index = int(lane.get('index'))
                shape = [tuple(map(float, p.split(','))) for p in lane.get('shape').split()]
                width, speed, length = [float(lane.get(k)) for k in ('width', 'speed', 'length')]
                expected_y = 1.65 + 3.3 * index
                check(close(width, 3.3), f'{lane.get("id")} explicit width')
                check(close(speed, 33.3), f'{lane.get("id")} road speed')
                check(close(length, x1-x0), f'{lane.get("id")} physical length')
                check(len(shape) >= 2 and close(shape[0][0], x0) and close(shape[-1][0], x1), f'{lane.get("id")} endpoints')
                check(all(close(p[1], expected_y) for p in shape), f'{lane.get("id")} straight continuous centerline')
                geometric_length = sum(math.dist(a[:2], b[:2]) for a,b in zip(shape, shape[1:]))
                check(close(geometric_length, x1-x0), f'{lane.get("id")} geometric length')
                lanes.append(dict(id=lane.get('id'), index=index, width_m=width, speed_mps=speed,
                                  length_m=length, geometric_length_m=geometric_length, shape=shape))
            except (TypeError, ValueError, AttributeError):
                errors.append(f'Missing or malformed physical attributes: {lane.get("id")}')
    links = [(x.get('from'), x.get('to'), x.get('fromLane'), x.get('toLane')) for x in root.findall('connection')]
    check(sorted(links) == [('upstream','downstream','0','0'), ('upstream','downstream','1','1')],
          'Only 0->0 and 1->1 allowed; lane 2 must merge upstream')
    return {'passed':not errors, 'errors':errors, 'lanes':lanes, 'connections':links,
            'source':'independent parsing of generated net.xml', 'controller_access':False}


def draw_topology():
    from PIL import Image, ImageDraw, ImageFont
    root = ET.parse(SCENARIO/'bottleneck.net.xml').getroot()
    report = validate_tree(root)
    im = Image.new('RGB', (1600, 760), '#f5f7fa')
    d = ImageDraw.Draw(im)
    font_path = 'C:/Windows/Fonts/arial.ttf'
    font = ImageFont.truetype(font_path, 24)
    small = ImageFont.truetype(font_path, 18)
    title = ImageFont.truetype(font_path, 34)
    d.text((60,25), 'Cai 2024 | generated 3-to-2 network', fill='#182c44', font=title)
    d.text((60,75), 'Read from bottleneck.net.xml | x=0 -> 1000 -> 1200 m | all widths explicitly 3.3 m', fill='#48586b', font=font)
    for ymin,ymax,xend in [(0,3.3,1200),(3.3,6.6,1200),(6.6,9.9,1000)]:
        d.rectangle((80,350-ymax*18,80+xend*1.2,350-ymin*18), fill='#485462', outline='white', width=2)
    for lane in report['lanes']:
        a,b=lane['shape'][0],lane['shape'][-1]
        y=350-a[1]*18
        d.line((80+a[0]*1.2,y,80+b[0]*1.2,y),fill='#6ae0bf',width=3)
        d.text((105+a[0]*1.2,y-21),lane['id']+f'  y={a[1]:.2f} m',fill='white',font=small)
    for x in [0,1000,1200]:
        px=80+1.2*x
        d.line((px,145,px,370),fill='#af6374',width=2)
        d.text((px-30,382),str(x)+' m',fill='#182c44',font=small)
    d.text((70,438),'Bottleneck detail: only retained lanes connect; terminated lane has NO outgoing connection.',fill='#182c44',font=font)
    xbase,ybase=300,665
    for lane in (0,1,2):
        y=ybase-lane*48
        d.line((xbase-150,y,xbase+550 if lane<2 else xbase+300,y),fill='#485462',width=32)
        d.text((70,y-12),f'Lane {lane}',fill='#182c44',font=font)
        if lane<2:
            d.line((xbase+220,y,xbase+480,y),fill='#32be98',width=4)
            d.polygon([(xbase+480,y),(xbase+464,y-8),(xbase+464,y+8)],fill='#32be98')
        else:
            d.line((xbase+300,y-18,xbase+300,y+18),fill='#ce4755',width=7)
            d.text((xbase+330,y-15),'Merge into lane 1 before x=1000',fill='#a33443',font=font)
    d.text((70,710),'Diagram axes have different scales. Native SUMO motion is for topology testing only.',fill='#48586b',font=small)
    target=ROOT/'results/phase1/topology.png'
    im.save(target)
