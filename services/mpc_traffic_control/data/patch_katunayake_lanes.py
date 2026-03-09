import os
import sys
import json
import xml.etree.ElementTree as ET

# Paths
dir_path = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(dir_path, "lane_ids_katunayake.json")
map_path = os.path.abspath(os.path.join(dir_path, "../../../simulation_and_control_panel/scenarios/katunayake/katunayake.net.xml"))

def main():
    print(f"Reading Katunayake map: {map_path}")
    if not os.path.exists(map_path):
        print(f"Error: map not found at {map_path}")
        sys.exit(1)
        
    tree = ET.parse(map_path)
    root = tree.getroot()
    
    # Collect all valid lanes
    valid_lanes = []
    for edge in root.findall('edge'):
        # skip internal edges
        if edge.get('function') == 'internal': continue
        
        for lane in edge.findall('lane'):
            valid_lanes.append(lane.get('id'))
            
    print(f"Found {len(valid_lanes)} valid lanes in the map.")
    
    # Read existing 64 lanes
    if not os.path.exists(json_path):
        print(f"Error: {json_path} not found")
        sys.exit(1)
        
    with open(json_path, 'r') as f:
        target_lanes = json.load(f)
        
    print(f"Loaded {len(target_lanes)} target lanes from json.")
    
    # Patch invalid lanes
    patched = 0
    for i, lane in enumerate(target_lanes):
        if lane not in valid_lanes:
            # Replace it with the very first valid lane just as a dummy
            replaced_with = valid_lanes[0]
            print(f"Lane {lane} is MISSING. Replacing with dummy: {replaced_with}")
            target_lanes[i] = replaced_with
            patched += 1
            
    print(f"Patched {patched} missing lanes.")
    
    # Save back to json
    with open(json_path, 'w') as f:
        json.dump(target_lanes, f)
        
    print(f"Successfully saved {len(target_lanes)} lanes back to {json_path}.")

if __name__ == "__main__":
    main()
