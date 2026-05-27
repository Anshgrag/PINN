import json
import sys
import math

def get_centroid(coords):
    """Calculates the mean of all [lon, lat] pairs in a ring."""
    if not coords:
        return None
    sum_lon = sum(p[0] for p in coords)
    sum_lat = sum(p[1] for p in coords)
    count = len(coords)
    return [sum_lon / count, sum_lat / count]

def convert_v2(input_path, output_path):
    GRID_SIZE = 64
    
    try:
        with open(input_path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"ERROR: Could not read GeoJSON file: {e}")
        sys.exit(1)

    features = data.get('features', [])
    if not features:
        print("WARNING: No features found in GeoJSON")
        sys.exit(0)

    # 1. BOUNDING BOX EXTRACTION
    all_lons = []
    all_lats = []
    for feature in features:
        geom = feature.get('geometry')
        if not geom: continue
        g_type = geom.get('type')
        coords = geom.get('coordinates', [])
        
        if g_type == 'Polygon' and coords:
            for lon, lat in coords[0]:
                all_lons.append(lon)
                all_lats.append(lat)
        elif g_type == 'MultiPolygon' and coords:
            for poly in coords:
                if poly:
                    for lon, lat in poly[0]:
                        all_lons.append(lon)
                        all_lats.append(lat)

    if not all_lons or not all_lats:
        print("ERROR: No valid coordinates extracted.")
        sys.exit(1)

    min_lon, max_lon = min(all_lons), max(all_lons)
    min_lat, max_lat = min(all_lats), max(all_lats)

    print(f"Total features found in GeoJSON: {len(features)}")
    print(f"Computed Bounding Box:")
    print(f"  Min Lon: {min_lon}, Max Lon: {max_lon}")
    print(f"  Min Lat: {min_lat}, Max Lat: {max_lat}")

    # 2. EDGE CASE GUARDS
    if max_lon == min_lon or max_lat == min_lat:
        print("ERROR: Degenerate bounding box detected. Cannot normalize.")
        sys.exit(1)

    # 3. NORMALIZATION & MAPPING
    grid = [[0 for _ in range(GRID_SIZE)] for _ in range(GRID_SIZE)]
    mapped_count = 0
    
    for feature in features:
        geom = feature.get('geometry')
        if not geom: continue
        g_type = geom.get('type')
        coords = geom.get('coordinates', [])

        props = feature.get('properties', {})
        h_val = props.get('height')
        levels = props.get('building:levels')
        
        height_m = 12.0 # Default
        if h_val:
            try:
                if isinstance(h_val, str):
                    height_m = float(''.join(c for c in h_val if c.isdigit() or c == '.'))
                else:
                    height_m = float(h_val)
            except: pass
        elif levels:
            try:
                if isinstance(levels, str):
                    num_levels = float(''.join(c for c in levels if c.isdigit() or c == '.'))
                else:
                    num_levels = float(levels)
                height_m = num_levels * 3.5
            except: pass

        # Get outer ring for mapping
        if g_type == 'Polygon' and coords:
            outer_ring = coords[0]
        elif g_type == 'MultiPolygon' and coords:
            outer_ring = coords[0][0]
        else:
            continue

        centroid = get_centroid(outer_ring)
        if not centroid: continue
        
        lon, lat = centroid
        col = int((lon - min_lon) / (max_lon - min_lon) * (GRID_SIZE - 1))
        row = int((lat - min_lat) / (max_lat - min_lat) * (GRID_SIZE - 1))
        
        col = max(0, min(GRID_SIZE - 1, col))
        row = max(0, min(GRID_SIZE - 1, row))
        
        grid[row][col] = int(height_m)
        mapped_count += 1

    print(f"Buildings successfully placed on grid: {mapped_count}")

    # 4. OUTPUT FORMAT & EXPORT
    try:
        with open(output_path, 'w') as f:
            for r in range(GRID_SIZE):
                f.write(" ".join(map(str, grid[r])) + "\n")
        print(f"Successfully wrote grid to {output_path}")
    except Exception as e:
        print(f"ERROR: Could not write output file: {e}")
        sys.exit(1)

    # 5. ASCII PREVIEW
    print("\nASCII PREVIEW (Row 0 at top = South):")
    for r in range(GRID_SIZE - 1, -1, -1):
        line = "".join('█' if val > 0 else '.' for val in grid[r])
        print(line)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python convert_v2.py <input.geojson> <output.txt>")
        sys.exit(1)
    
    convert_v2(sys.argv[1], sys.argv[2])
