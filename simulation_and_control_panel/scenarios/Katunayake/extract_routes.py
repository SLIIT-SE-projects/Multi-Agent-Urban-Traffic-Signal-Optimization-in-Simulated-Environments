import xml.etree.ElementTree as ET
from collections import Counter

tree = ET.parse('katunayake.routes_temp.xml')
root = tree.getroot()

# Find all route edges
routes = []
for vehicle in root.findall('vehicle'):
    # In rou.alt.xml, routes are inside routeDistribution/route
    route_dist = vehicle.find('routeDistribution')
    route = vehicle.find('route')
    if route_dist is not None:
        route = route_dist.find('route')
    if route is not None:
        edges = route.get('edges')
        if edges:
            routes.append(edges)

# Count and get the 20 most common routes
route_counts = Counter(routes)
most_common = route_counts.most_common(20)

# Create a new XML file for the routes
new_root = ET.Element('routes')

for i, (edges, count) in enumerate(most_common):
    route_elem = ET.SubElement(new_root, 'route')
    route_elem.set('id', f'route_{i}')
    route_elem.set('edges', edges)

# Write to file
tree_out = ET.ElementTree(new_root)
ET.indent(tree_out, space="    ", level=0)
tree_out.write('katunayake.routes.xml', encoding='utf-8', xml_declaration=True)

print(f"Extracted {len(most_common)} explicit routes and saved to katunayake.routes.xml")
