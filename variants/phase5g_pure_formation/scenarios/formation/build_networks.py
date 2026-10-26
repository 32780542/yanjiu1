"""Build constant-width SUMO roads for the 2/3/4-lane formation matrix."""

from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parent


def build(lane_count: int, netconvert: str = 'netconvert') -> Path:
    if lane_count not in (2, 3, 4):
        raise ValueError('lane_count must be 2, 3, or 4')
    nodes = ET.Element('nodes')
    ET.SubElement(nodes, 'node', id='entry', x='0', y='0', type='priority')
    ET.SubElement(nodes, 'node', id='exit', x='3000', y='0', type='priority')
    edges = ET.Element('edges')
    edge = ET.SubElement(edges, 'edge', id='upstream', **{
        'from': 'entry', 'to': 'exit', 'numLanes': str(lane_count),
        'speed': '33.3', 'width': '3.3', 'length': '3000',
        'spreadType': 'center'})
    for lane in range(lane_count):
        y = 3.3 * (lane + 0.5)
        ET.SubElement(edge, 'lane', index=str(lane), width='3.3',
                      shape=f'0,{y:g} 3000,{y:g}')
    stem = ROOT / f'straight_{lane_count}'
    node_path = stem.with_suffix('.nod.xml')
    edge_path = stem.with_suffix('.edg.xml')
    network_path = stem.with_suffix('.net.xml')
    for path, tree in ((node_path, nodes), (edge_path, edges)):
        ET.indent(tree, space='  ')
        ET.ElementTree(tree).write(path, encoding='utf-8', xml_declaration=True)
    subprocess.run([netconvert, '--node-files', str(node_path),
                    '--edge-files', str(edge_path), '--output-file',
                    str(network_path), '--no-turnarounds', 'true'], check=True)
    return network_path


if __name__ == '__main__':
    for lanes in (2, 3, 4):
        print(build(lanes))
