import xml.etree.ElementTree as ET
import os

def clean_routes(file_path, deleted_edges):
    # Register the default namespace if any, SUMO usually uses xsi
    ET.register_namespace('xsi', 'http://www.w3.org/2001/XMLSchema-instance')
    
    # Parse the XML
    tree = ET.parse(file_path)
    root = tree.getroot()

    deleted_edges_set = set(deleted_edges)
    
    # Map from child to parent to easily remove items
    parent_map = {c: p for p in tree.iter() for c in p}
    
    elements_to_remove = []

    # Let's collect predefined routes first
    predefined_routes = {}
    for elem in root.findall('route'):
        if 'id' in elem.attrib and 'edges' in elem.attrib:
            predefined_routes[elem.get('id')] = elem.get('edges').split()

    # Now find all vehicle, flow, trip
    for elem in root.iter():
        if elem.tag in ['vehicle', 'flow', 'trip']:
            remove_this = False
            
            # check predefined route
            route_id = elem.get('route')
            if route_id and route_id in predefined_routes:
                route_edges = predefined_routes[route_id]
                if any(e in deleted_edges_set for e in route_edges):
                    remove_this = True
                    
            # check child route tags
            for child in elem.findall('route'):
                if 'edges' in child.attrib:
                    child_edges = child.get('edges').split()
                    if any(e in deleted_edges_set for e in child_edges):
                        remove_this = True
                        
            # check edges attribute directly on trip (just in case)
            if elem.tag == 'trip' and 'edges' in elem.attrib:
                trip_edges = elem.get('edges').split()
                if any(e in deleted_edges_set for e in trip_edges):
                    remove_this = True
            
            if remove_this:
                elements_to_remove.append(elem)

    # Remove the elements
    removed_count = 0
    for elem in elements_to_remove:
        if elem in parent_map:
            parent = parent_map[elem]
            if elem in list(parent):
                parent.remove(elem)
                removed_count += 1
                
    # Standard XML formatting
    if hasattr(ET, 'indent'):
        ET.indent(tree, space="    ", level=0)
        
    output_path = os.path.join(os.path.dirname(file_path), "katunayake_cleaned.rou.xml")
    
    with open(output_path, 'wb') as f:
        # SUMO route files usually start with XML declaration
        tree.write(f, encoding='UTF-8', xml_declaration=True)
        
    print(f"Removed {removed_count} elements. Saved to {output_path}")

if __name__ == '__main__':
    deleted = [
        "-415680722#0",
        "415680725",
        "415680722#1",
        "-435181003",
        "415680722#2",
        "-435181002",
        "-415680722#3",
        "435180997",
        "415680722#4"
    ]
    file_path = r"f:\Repositories\temp\research-temp-3\multi-agent-urban-traffic-signal-optimization-in-simulated-environments\simulation_and_control_panel\scenarios\Katunayake\katunayake.rou.xml"
    clean_routes(file_path, deleted)
