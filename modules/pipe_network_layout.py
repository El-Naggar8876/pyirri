"""
Pipe Network Layout Module - Professional CAD-Style Drawing Interface

Features:
---------
1. Drawing Modes:
   - Click-to-Click: Traditional mode - click each point to build polyline
   - Click-and-Drag: CAD mode - click start, drag to preview, click to finish line
   
2. Grid Snapping:
   - Adjustable grid sizes: 5m, 10m, 25m, 50m
   - Automatic coordinate snapping for precise alignment
   
3. Angle Constraints:
   - Snap to specific angles: 15°, 30°, 45°, 90°
   - Ensures perfectly horizontal, vertical, or diagonal lines
   - Great for orthogonal and structured layouts
   
4. Length Constraints:
   - Fix line length to exact measurement
   - Useful for standardized pipe sections
   
5. Real-Time Measurements:
   - Length display on each segment
   - Angle indication for non-horizontal lines
   - Live annotations during drawing
   
6. Alignment Guides:
   - Horizontal and vertical guides from last point
   - Visual feedback for alignment
   - Cyan dashed lines for reference
   
7. Manual Coordinate Entry:
   - Precise X,Y input via number fields
   - Perfect for known coordinates
   
8. Professional Visualization:
   - Color-coded pipe types (Mainline=Red, Submain=Orange, Lateral=Green)
   - Grid overlay when snapping enabled
   - Clear visual feedback during drawing
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.graph_objects import Scattergl  # For high-performance rendering
import numpy as np
from streamlit_plotly_events import plotly_events
from math import atan2, sqrt

# Import DevLogger for toggleable debug output
from components.logger import DevLogger, log_debug, log_info, log_warning


def apply_cad_constraints(start_x, start_y, end_x, end_y, 
                          enable_angle_snap, angle_increment,
                          enable_length_constraint, target_length):
    """
    Apply CAD-style constraints to line drawing
    
    Args:
        start_x, start_y: Starting point coordinates
        end_x, end_y: Desired end point coordinates
        enable_angle_snap: Whether to snap to specific angles
        angle_increment: Angle snap increment in degrees
        enable_length_constraint: Whether to constrain to specific length
        target_length: Target length in meters
    
    Returns:
        constrained_x, constrained_y: Constrained end point coordinates
    """
    # Calculate current vector
    dx = end_x - start_x
    dy = end_y - start_y
    current_length = np.sqrt(dx**2 + dy**2)
    
    if current_length < 0.1:  # Avoid division by zero
        return end_x, end_y
    
    # Calculate current angle
    current_angle = np.degrees(np.arctan2(dy, dx))
    
    # Apply angle snapping
    if enable_angle_snap:
        # Snap to nearest increment
        snapped_angle = round(current_angle / angle_increment) * angle_increment
        angle_rad = np.radians(snapped_angle)
    else:
        angle_rad = np.radians(current_angle)
    
    # Apply length constraint
    if enable_length_constraint:
        length = target_length
    else:
        length = current_length
    
    # Calculate constrained endpoint
    constrained_x = start_x + length * np.cos(angle_rad)
    constrained_y = start_y + length * np.sin(angle_rad)
    
    return constrained_x, constrained_y


def calculate_line_info(start_x, start_y, end_x, end_y):
    """Calculate length and angle for a line segment"""
    dx = end_x - start_x
    dy = end_y - start_y
    length = np.sqrt(dx**2 + dy**2)
    angle = np.degrees(np.arctan2(dy, dx))
    return length, angle


def find_grid_intersections(field_geometry, n_rows, n_cols, network=None, snap_to_submain=True, submain_threshold=15.0, skip_interval=1):
    """
    SMART GRID INTERSECTION FINDER - Places valves ONLY on submain lines
    
    This function extracts valve positions at internal grid intersections,
    but ONLY keeps intersections that are on or near a submain line.
    
    Valves control water flow from submains to laterals, so they should
    be positioned ON the submain network, not randomly at grid corners.
    
    Supported Field Types:
    - Regular quadrilaterals (rectangles, parallelograms, trapezoids)
    - Irregular polygons (5+ sides)
    - Any field area (small plots to large farms)
    - Rotated fields at any angle
    
    Algorithm:
    1. Get subplot_polygons from operational_data (the source of truth)
    2. Collect ALL corner vertices from ALL subplots
    3. Find vertices that appear 4 times (internal corners where 4 subplots meet)
    4. Filter to keep only INTERNAL points (not on field boundary)
    5. **SMART FILTER**: Only keep intersections within threshold distance of a submain line
    6. Snap valve position to the nearest point on the submain
    
    Args:
        field_geometry: Field boundary with 'local_polygon' vertices
        n_rows: Number of subplot rows
        n_cols: Number of subplot columns
        network: Pipe network containing submains (if None, returns all intersections)
        snap_to_submain: If True, only return intersections near submains
        submain_threshold: Maximum distance (meters) from submain to place valve
        skip_interval: Place valve every N intersections (1=every intersection, 2=every other)
    
    Returns:
        List of (x, y) tuples - valve positions on submain lines at grid intersections
    """
    from shapely.geometry import Polygon, Point, LineString
    from collections import Counter
    import streamlit as st
    
    # Get subplot_polygons from operational_data - this is the SOURCE OF TRUTH
    operational_data = st.session_state.project_data.get('operational_data', {})
    subplot_polygons = operational_data.get('subplot_polygons', {})
    
    local_polygon = field_geometry.get('local_polygon')
    if not local_polygon:
        st.warning("No field polygon found")
        return []
    
    field_poly = Polygon(local_polygon)
    field_area = field_poly.area
    num_vertices = len(local_polygon)
    
    # Get submains from network
    submains = []
    submain_lines = []
    if network:
        submains = network.get('submains', [])
        for submain in submains:
            if len(submain) >= 2:
                submain_lines.append(LineString(submain))
    
    # DevLogger: Smart Valve Placement diagnostics (only shown in Dev Mode)
    DevLogger.section("SMART VALVE PLACEMENT")
    log_debug("Field Properties", shape=f"{num_vertices}-sided", area=f"{field_area/10000:.2f} ha", 
              grid=f"{n_rows}×{n_cols}")
    log_debug("Submain Network", lines=len(submain_lines), threshold=f"{submain_threshold}m")
    
    if len(submain_lines) == 0 and snap_to_submain:
        st.error("❌ **No submain lines found!** Please draw submain lines first, then auto-place valves.")
        st.info("💡 **Tip:** Draw your submain lines using the 🟠 Submain tool, then click 'Auto-place at Grid Intersections'")
        return []
    
    # =========================================================================
    # STEP 1: Extract all internal grid intersections
    # =========================================================================
    internal_corners = []
    
    if subplot_polygons and len(subplot_polygons) > 0:
        log_info("STEP 1: Extracting grid intersections from subplot polygons...")
        
        # Collect ALL vertices from ALL subplot polygons
        all_vertices = []
        for subplot_num, polygon_coords in subplot_polygons.items():
            for coord in polygon_coords:
                rounded = (round(coord[0], 1), round(coord[1], 1))
                all_vertices.append(rounded)
        
        # Count vertex frequency
        vertex_counts = Counter(all_vertices)
        
        # Extract internal corners (vertices shared by 4 subplots)
        boundary_line = field_poly.exterior
        field_diagonal = ((field_poly.bounds[2] - field_poly.bounds[0])**2 + 
                         (field_poly.bounds[3] - field_poly.bounds[1])**2)**0.5
        boundary_threshold = max(0.5, min(5.0, field_diagonal / 500))
        
        for vertex, count in vertex_counts.items():
            if count >= 4:
                x, y = vertex
                point = Point(x, y)
                dist_to_boundary = boundary_line.distance(point)
                
                if dist_to_boundary > boundary_threshold:
                    internal_corners.append((float(x), float(y)))
        
        log_debug(f"Found {len(internal_corners)} internal grid intersections")
    else:
        # Fallback to geometric calculation
        internal_corners = find_grid_intersections_geometric(field_geometry, n_rows, n_cols)
        log_debug(f"Generated {len(internal_corners)} intersections geometrically")
    
    if len(internal_corners) == 0:
        st.warning("⚠️ No internal grid intersections found")
        return []
    
    # =========================================================================
    # STEP 2: Filter to keep ONLY intersections near submain lines
    # =========================================================================
    if not snap_to_submain or len(submain_lines) == 0:
        log_info(f"Returning all {len(internal_corners)} intersections (no submain filtering)")
        return internal_corners
    
    log_info("STEP 2: Filtering intersections near submain lines...")
    
    # --- Place valves at grid intersections on submains, EXCLUDING mainline intersections ---
    valve_positions = []
    skipped_count = 0
    mainline_skipped = 0
    if not submain_lines:
        log_warning("No submain lines found for smart valve grouping.")
        return []

    # Find all mainline points and create mainline geometry for distance calculation
    mainline_points = []
    mainline_lines = []
    if network and 'mainlines' in network:
        for mainline in network['mainlines']:
            mainline_points.extend(mainline)
            if len(mainline) >= 2:
                mainline_lines.append(LineString(mainline))
    
    # Minimum distance from mainline to place a valve
    # This prevents valves at the submain-mainline junction
    MIN_DISTANCE_FROM_MAINLINE = 10.0  # meters - skip intersections within 10m of mainline

    # For each submain, collect eligible intersections (snapped to submain)
    for submain_idx, submain_line in enumerate(submain_lines):
        # Gather all intersections near this submain
        submain_intersections = []
        for corner_x, corner_y in internal_corners:
            corner_point = Point(corner_x, corner_y)
            nearest_on_line = submain_line.interpolate(submain_line.project(corner_point))
            distance = corner_point.distance(nearest_on_line)
            if distance <= submain_threshold:
                # Calculate distance from mainline
                if mainline_lines:
                    min_dist_to_main = min(ml.distance(Point(nearest_on_line.x, nearest_on_line.y)) for ml in mainline_lines)
                elif mainline_points:
                    min_dist_to_main = min(Point(p).distance(nearest_on_line) for p in mainline_points)
                else:
                    min_dist_to_main = 999  # No mainline, assume far enough
                
                # SKIP intersections too close to mainline (these are at the junction)
                if min_dist_to_main < MIN_DISTANCE_FROM_MAINLINE:
                    mainline_skipped += 1
                    if mainline_skipped <= 3:
                        log_debug(f"Skipping intersection at ({nearest_on_line.x:.1f}, {nearest_on_line.y:.1f}) - too close to mainline ({min_dist_to_main:.1f}m)")
                    continue
                
                submain_intersections.append({
                    'grid': (corner_x, corner_y),
                    'snapped': (nearest_on_line.x, nearest_on_line.y),
                    'dist_to_main': min_dist_to_main
                })
        if not submain_intersections:
            continue
        # Sort intersections by distance from mainline (descending: farthest first)
        submain_intersections.sort(key=lambda d: -d['dist_to_main'])
        
        # Place valves based on skip_interval:
        # skip_interval=1: place at EVERY intersection (1-2 plots per valve)
        # skip_interval=2: place every other (3-4 plots per valve)
        for idx, intersection in enumerate(submain_intersections):
            if idx % skip_interval == 0:
                valve_positions.append(intersection['snapped'])
                if len(valve_positions) <= 15:
                    log_debug(f"Submain {submain_idx+1}: Valve at ({intersection['snapped'][0]:.1f}, {intersection['snapped'][1]:.1f})")
            else:
                skipped_count += 1
                if skipped_count <= 5:
                    log_debug(f"Submain {submain_idx+1}: Skipped at ({intersection['snapped'][0]:.1f}, {intersection['snapped'][1]:.1f})")

    if mainline_skipped > 3:
        log_debug(f"... and {mainline_skipped - 3} more intersections skipped (too close to mainline)")
    if len(valve_positions) > 15:
        log_debug(f"... and {len(valve_positions) - 15} more valves placed on submains")
    if skipped_count > 5:
        log_debug(f"... and {skipped_count - 5} more intersections skipped")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    DevLogger.section("VALVE PLACEMENT COMPLETE")
    if skip_interval == 1:
        log_info(f"Valves placed: {len(valve_positions)} (at every intersection - 1-2 plots/valve)")
    else:
        log_info(f"Valves placed: {len(valve_positions)} (grouped - {skip_interval*2} plots/valve)")
    log_info(f"Intersections skipped: {skipped_count}")

    if len(valve_positions) == 0:
        st.warning("⚠️ No grid intersections are near your submain lines!")
        st.info("💡 **Suggestions:**\n"
                "   1. Draw submains that pass through grid intersections\n"
                f"   2. Increase the snap threshold (currently {submain_threshold}m)\n"
                "   3. Or place valves manually by clicking on the map")
    else:
        if skip_interval == 1:
            log_info(f"Placed {len(valve_positions)} valves at ALL intersections! Each valve serves 1-2 plots for accurate pipe sizing.")
        else:
            log_info(f"Placed {len(valve_positions)} grouped valves on submain lines!")

    return valve_positions


def find_grid_intersections_geometric(field_geometry, n_rows, n_cols):
    """
    Geometric fallback for calculating grid intersections.
    Works with quadrilateral fields using edge-parallel interpolation.
    For irregular polygons, uses bounding box grid clipped to field.
    
    Args:
        field_geometry: Field boundary with 'local_polygon' vertices
        n_rows: Number of subplot rows
        n_cols: Number of subplot columns
    
    Returns:
        List of (x, y) tuples - intersection coordinates
    """
    from shapely.geometry import LineString, Polygon, Point, MultiPoint
    import streamlit as st
    
    local_polygon = field_geometry.get('local_polygon')
    if not local_polygon or n_rows <= 0 or n_cols <= 0:
        return []
    
    field_poly = Polygon(local_polygon)
    num_vertices = len(local_polygon)
    
    log_info("Geometric Fallback Method")
    log_debug(f"Field vertices: {num_vertices}")
    
    valve_positions = []
    
    # =========================================================================
    # QUADRILATERAL FIELDS: Edge-parallel interpolation (most accurate)
    # =========================================================================
    if num_vertices == 4:
        log_debug("Using edge-parallel interpolation for quadrilateral")
        
        # Identify corners geometrically using convex hull
        corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
        
        if len(corners) != 4:
            log_warning("Could not identify 4 corners - field may be degenerate")
            return []
        
        # Sort corners: bottom-left, bottom-right, top-left, top-right
        corners_sorted = sorted(corners, key=lambda p: (p[1], p[0]))
        
        bottom_points = corners_sorted[:2]
        bottom_left = min(bottom_points, key=lambda p: p[0])
        bottom_right = max(bottom_points, key=lambda p: p[0])
        
        top_points = corners_sorted[2:4]
        top_left = min(top_points, key=lambda p: p[0])
        top_right = max(top_points, key=lambda p: p[0])
        
        # Define edges
        left_edge = (bottom_left, top_left)
        right_edge = (bottom_right, top_right)
        bottom_edge = (bottom_left, bottom_right)
        top_edge = (top_left, top_right)
        
        # Generate all internal intersections
        for col in range(1, n_cols):
            col_fraction = col / n_cols
            
            for row in range(1, n_rows):
                row_fraction = row / n_rows
                
                # Interpolate vertical line endpoints
                bottom_x = bottom_edge[0][0] + col_fraction * (bottom_edge[1][0] - bottom_edge[0][0])
                bottom_y = bottom_edge[0][1] + col_fraction * (bottom_edge[1][1] - bottom_edge[0][1])
                top_x = top_edge[0][0] + col_fraction * (top_edge[1][0] - top_edge[0][0])
                top_y = top_edge[0][1] + col_fraction * (top_edge[1][1] - top_edge[0][1])
                
                # Interpolate horizontal line endpoints
                left_x = left_edge[0][0] + row_fraction * (left_edge[1][0] - left_edge[0][0])
                left_y = left_edge[0][1] + row_fraction * (left_edge[1][1] - left_edge[0][1])
                right_x = right_edge[0][0] + row_fraction * (right_edge[1][0] - right_edge[0][0])
                right_y = right_edge[0][1] + row_fraction * (right_edge[1][1] - right_edge[0][1])
                
                # Create lines and find intersection
                v_line = LineString([(bottom_x, bottom_y), (top_x, top_y)])
                h_line = LineString([(left_x, left_y), (right_x, right_y)])
                
                intersection = v_line.intersection(h_line)
                
                if not intersection.is_empty and intersection.geom_type == 'Point':
                    x, y = intersection.x, intersection.y
                    valve_positions.append((x, y))
    
    # =========================================================================
    # IRREGULAR POLYGONS: Bounding box grid clipped to field
    # =========================================================================
    else:
        log_debug(f"Using bounding box grid for {num_vertices}-sided polygon")
        
        minx, miny, maxx, maxy = field_poly.bounds
        width = maxx - minx
        height = maxy - miny
        
        log_debug(f"Bounding box: {width:.1f}m × {height:.1f}m")
        
        # Generate grid intersections within bounding box
        for col in range(1, n_cols):
            col_fraction = col / n_cols
            x = minx + col_fraction * width
            
            for row in range(1, n_rows):
                row_fraction = row / n_rows
                y = miny + row_fraction * height
                
                point = Point(x, y)
                
                # Only include points inside the field polygon
                if field_poly.contains(point):
                    valve_positions.append((x, y))
    
    log_info(f"Generated {len(valve_positions)} intersection points")
    
    return valve_positions


def find_line_intersections(network):
    """
    Find all intersection points between network lines
    
    Returns:
        List of (x, y) intersection points
    """
    from shapely.geometry import LineString
    
    intersections = []
    all_network_lines = []
    
    # Collect all network lines as LineString objects
    for mainline in network.get('mainlines', []):
        if len(mainline) >= 2:
            for i in range(len(mainline) - 1):
                all_network_lines.append(LineString([mainline[i], mainline[i+1]]))
    
    for submain in network.get('submains', []):
        if len(submain) >= 2:
            for i in range(len(submain) - 1):
                all_network_lines.append(LineString([submain[i], submain[i+1]]))
    
    for lateral in network.get('laterals', []):
        if len(lateral) >= 2:
            for i in range(len(lateral) - 1):
                all_network_lines.append(LineString([lateral[i], lateral[i+1]]))
    
    # Find all intersection points between lines
    for i, line1 in enumerate(all_network_lines):
        for j, line2 in enumerate(all_network_lines):
            if i >= j:  # Avoid duplicate checks
                continue
            
            try:
                intersection = line1.intersection(line2)
                if not intersection.is_empty:
                    if intersection.geom_type == 'Point':
                        intersections.append((intersection.x, intersection.y))
                    elif intersection.geom_type == 'MultiPoint':
                        for pt in intersection.geoms:
                            intersections.append((pt.x, pt.y))
            except:
                pass
    
    return intersections


def snap_to_network_lines(click_x, click_y, network, snap_threshold=5.0):
    """
    Snap a clicked point to the nearest existing pipe network line (Nearest Snap)
    
    Args:
        click_x, click_y: Clicked coordinates
        network: Pipe network data
        snap_threshold: Maximum distance to snap
    
    Returns:
        snapped_x, snapped_y: Coordinates snapped to nearest line
    """
    min_distance = float('inf')
    snapped_x, snapped_y = click_x, click_y
    
    # Collect all network lines
    all_lines = []
    for mainline in network.get('mainlines', []):
        if len(mainline) >= 2:
            for i in range(len(mainline) - 1):
                all_lines.append((mainline[i], mainline[i+1]))
                
    for submain in network.get('submains', []):
        if len(submain) >= 2:
            for i in range(len(submain) - 1):
                all_lines.append((submain[i], submain[i+1]))
                
    for lateral in network.get('laterals', []):
        if len(lateral) >= 2:
            for i in range(len(lateral) - 1):
                all_lines.append((lateral[i], lateral[i+1]))
    
    for p1, p2 in all_lines:
        x1, y1 = p1
        x2, y2 = p2
        
        # Calculate closest point on line segment
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            continue
        
        t = ((click_x - x1) * dx + (click_y - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))  # Clamp to segment
        
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        dist = np.sqrt((click_x - closest_x)**2 + (click_y - closest_y)**2)
        
        if dist < min_distance:
            min_distance = dist
            snapped_x = closest_x
            snapped_y = closest_y
            
    if min_distance <= snap_threshold:
        return snapped_x, snapped_y
    
    return click_x, click_y


def snap_to_field_lines(click_x, click_y, field_geometry, operational_data, snap_threshold=15):
    """
    Snap a clicked point to the nearest field boundary or subplot division line
    
    Args:
        click_x, click_y: Clicked coordinates
        field_geometry: Field geometry data with boundary and dimensions
        operational_data: Operational design data with subplot grid info
        snap_threshold: Maximum distance (in meters) to snap to a line
    
    Returns:
        snapped_x, snapped_y: Coordinates snapped to nearest line
    """
    # Get field data - use 'local_polygon' which is the correct key
    local_polygon = field_geometry.get('local_polygon')
    n_rows = operational_data.get('n_rows', 0)
    n_cols = operational_data.get('n_cols', 0)
    
    if not local_polygon:
        return click_x, click_y
    
    # Collect all grid lines (as (x1, y1, x2, y2) tuples)
    all_lines = []
    
    # Add field boundary lines
    for i in range(len(local_polygon)):
        x1, y1 = local_polygon[i]
        x2, y2 = local_polygon[(i + 1) % len(local_polygon)]
        all_lines.append((x1, y1, x2, y2))
    
    # Add subplot division lines if available
    if n_rows > 0 and n_cols > 0 and len(local_polygon) >= 4:
        try:
            from shapely.geometry import Polygon, MultiPoint
            
            poly = Polygon(local_polygon)
            
            # Detect if this is a regular quadrilateral (4 well-defined corners)
            corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
            is_regular_quad = len(corners) == 4
            
            if is_regular_quad:
                # REGULAR QUADRILATERAL: Use edge-parallel interpolation (same as operational_design)
                corners_sorted = sorted(corners, key=lambda p: (p[1], p[0]))
                
                bottom_points = corners_sorted[:2]
                bottom_left = min(bottom_points, key=lambda p: p[0])
                bottom_right = max(bottom_points, key=lambda p: p[0])
                
                top_points = corners_sorted[2:4]
                top_left = min(top_points, key=lambda p: p[0])
                top_right = max(top_points, key=lambda p: p[0])
                
                left_edge = (bottom_left, top_left)
                right_edge = (bottom_right, top_right)
                bottom_edge = (bottom_left, bottom_right)
                top_edge = (top_left, top_right)
                
                # Horizontal lines (parallel to edges)
                for i in range(1, n_rows):
                    fraction = i / n_rows
                    left_point = (
                        left_edge[0][0] + fraction * (left_edge[1][0] - left_edge[0][0]),
                        left_edge[0][1] + fraction * (left_edge[1][1] - left_edge[0][1])
                    )
                    right_point = (
                        right_edge[0][0] + fraction * (right_edge[1][0] - right_edge[0][0]),
                        right_edge[0][1] + fraction * (right_edge[1][1] - right_edge[0][1])
                    )
                    all_lines.append((left_point[0], left_point[1], right_point[0], right_point[1]))
                
                # Vertical lines (parallel to edges)
                for i in range(1, n_cols):
                    fraction = i / n_cols
                    bottom_point = (
                        bottom_edge[0][0] + fraction * (bottom_edge[1][0] - bottom_edge[0][0]),
                        bottom_edge[0][1] + fraction * (bottom_edge[1][1] - bottom_edge[0][1])
                    )
                    top_point = (
                        top_edge[0][0] + fraction * (top_edge[1][0] - top_edge[0][0]),
                        top_edge[0][1] + fraction * (top_edge[1][1] - top_edge[0][1])
                    )
                    all_lines.append((bottom_point[0], bottom_point[1], top_point[0], top_point[1]))
            else:
                # IRREGULAR POLYGON: Use bounding box grid
                minx, miny, maxx, maxy = poly.bounds
                
                # Horizontal subdivision lines
                for i in range(1, n_rows):
                    y_pos = miny + (i * (maxy - miny) / n_rows)
                    all_lines.append((minx, y_pos, maxx, y_pos))
                
                # Vertical subdivision lines
                for i in range(1, n_cols):
                    x_pos = minx + (i * (maxx - minx) / n_cols)
                    all_lines.append((x_pos, miny, x_pos, maxy))
        except:
            pass
    
    if not all_lines:
        return click_x, click_y
    
    # STEP 1: Find all intersection points between lines
    intersections = []
    for i in range(len(all_lines)):
        for j in range(i + 1, len(all_lines)):
            x1, y1, x2, y2 = all_lines[i]
            x3, y3, x4, y4 = all_lines[j]
            
            # Calculate intersection using line equation
            denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if abs(denom) < 1e-10:  # Lines are parallel
                continue
            
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denom
            u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denom
            
            # Check if intersection is within both line segments
            if 0 <= t <= 1 and 0 <= u <= 1:
                int_x = x1 + t * (x2 - x1)
                int_y = y1 + t * (y2 - y1)
                intersections.append((int_x, int_y))
    
    # STEP 2: Find closest point on any line
    min_distance = float('inf')
    snapped_x, snapped_y = click_x, click_y
    
    for x1, y1, x2, y2 in all_lines:
        # Calculate closest point on line segment
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            continue
        
        t = ((click_x - x1) * dx + (click_y - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))  # Clamp to segment
        
        closest_x = x1 + t * dx
        closest_y = y1 + t * dy
        dist = np.sqrt((click_x - closest_x)**2 + (click_y - closest_y)**2)
        
        if dist < min_distance:
            min_distance = dist
            snapped_x = closest_x
            snapped_y = closest_y
    
    # If we didn't snap to any line within threshold, return original click
    if min_distance > snap_threshold:
        return click_x, click_y
    
    # STEP 3: Check if the snapped point is very close to an intersection
    # Only override with intersection if we're within a very tight threshold
    intersection_threshold = 8  # meters - threshold for intersection priority
    
    closest_int = None
    closest_int_dist = float('inf')
    
    for int_x, int_y in intersections:
        # Check if our click was near this intersection
        dist_click_to_int = np.sqrt((click_x - int_x)**2 + (click_y - int_y)**2)
        # Also check if the line-snapped point ended up near this intersection
        dist_snap_to_int = np.sqrt((snapped_x - int_x)**2 + (snapped_y - int_y)**2)
        
        # If we clicked near an intersection OR the snap put us near one, track it
        if dist_click_to_int <= intersection_threshold or dist_snap_to_int <= 8:
            if dist_click_to_int < closest_int_dist:
                closest_int_dist = dist_click_to_int
                closest_int = (int_x, int_y)
    
    if closest_int:
        return closest_int[0], closest_int[1]
    
    # Return the line snap point
    return snapped_x, snapped_y


def snap_to_midpoint(click_x, click_y, network, snap_threshold=10.0):
    """Snap to midpoint of existing network lines"""
    min_distance = float('inf')
    snapped_x, snapped_y = click_x, click_y
    
    all_lines = []
    for mainline in network.get('mainlines', []):
        if len(mainline) >= 2:
            for i in range(len(mainline) - 1):
                all_lines.append((mainline[i], mainline[i+1]))
    for submain in network.get('submains', []):
        if len(submain) >= 2:
            for i in range(len(submain) - 1):
                all_lines.append((submain[i], submain[i+1]))
    for lateral in network.get('laterals', []):
        if len(lateral) >= 2:
            for i in range(len(lateral) - 1):
                all_lines.append((lateral[i], lateral[i+1]))
    
    for p1, p2 in all_lines:
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2
        dist = np.sqrt((click_x - mid_x)**2 + (click_y - mid_y)**2)
        
        if dist < min_distance:
            min_distance = dist
            snapped_x = mid_x
            snapped_y = mid_y
    
    if min_distance <= snap_threshold:
        return snapped_x, snapped_y
    return click_x, click_y


def snap_to_perpendicular(click_x, click_y, last_point, network, snap_threshold=5.0):
    """Snap to perpendicular point on existing network lines from last point"""
    if not last_point:
        return click_x, click_y
    
    min_distance = float('inf')
    snapped_x, snapped_y = click_x, click_y
    
    all_lines = []
    for mainline in network.get('mainlines', []):
        if len(mainline) >= 2:
            for i in range(len(mainline) - 1):
                all_lines.append((mainline[i], mainline[i+1]))
    for submain in network.get('submains', []):
        if len(submain) >= 2:
            for i in range(len(submain) - 1):
                all_lines.append((submain[i], submain[i+1]))
    for lateral in network.get('laterals', []):
        if len(lateral) >= 2:
            for i in range(len(lateral) - 1):
                all_lines.append((lateral[i], lateral[i+1]))
    
    for p1, p2 in all_lines:
        x1, y1 = p1
        x2, y2 = p2
        
        # Calculate perpendicular foot from last_point to this line
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            continue
        
        t = ((last_point[0] - x1) * dx + (last_point[1] - y1) * dy) / (dx * dx + dy * dy)
        t = max(0, min(1, t))
        
        perp_x = x1 + t * dx
        perp_y = y1 + t * dy
        
        # Check if click is near this perpendicular point
        dist = np.sqrt((click_x - perp_x)**2 + (click_y - perp_y)**2)
        
        if dist < min_distance:
            min_distance = dist
            snapped_x = perp_x
            snapped_y = perp_y
    
    if min_distance <= snap_threshold:
        return snapped_x, snapped_y
    return click_x, click_y


def snap_to_polar_grid(click_x, click_y, origin, distance_increment=10, angle_increment=15):
    """Snap to polar grid (radial distance and angular increments from origin)"""
    if not origin:
        return click_x, click_y
    
    # Calculate polar coordinates from origin
    dx = click_x - origin[0]
    dy = click_y - origin[1]
    distance = np.sqrt(dx**2 + dy**2)
    angle = np.degrees(np.arctan2(dy, dx))
    
    # Snap to nearest distance increment
    snapped_distance = round(distance / distance_increment) * distance_increment
    
    # Snap to nearest angle increment
    snapped_angle = round(angle / angle_increment) * angle_increment
    
    # Convert back to Cartesian
    angle_rad = np.radians(snapped_angle)
    snapped_x = origin[0] + snapped_distance * np.cos(angle_rad)
    snapped_y = origin[1] + snapped_distance * np.sin(angle_rad)
    
    return snapped_x, snapped_y


def snap_to_cartesian_grid(click_x, click_y, grid_size=5):
    """Snap to Cartesian grid"""
    snapped_x = round(click_x / grid_size) * grid_size
    snapped_y = round(click_y / grid_size) * grid_size
    return snapped_x, snapped_y


def calculate_valve_position_on_submain(subplot_list, operational_data, network):
    """
    Calculate optimal valve position on submain line for given subplots.
    
    Strategy:
    1. Find the common boundary point where adjacent selected subplots meet
    2. If no common boundary, find the geometric median of subplot centers
    3. Project this point onto the nearest submain line
    
    Args:
        subplot_list: List of subplot numbers
        operational_data: Operational design data with subplot centers and polygons
        network: Pipe network with submain lines
    
    Returns:
        (x, y): Valve position on submain, or (None, None) if no submains exist
    """
    from shapely.geometry import Point, LineString, Polygon, MultiPoint
    from shapely.ops import unary_union
    import numpy as np
    import streamlit as st
    
    # Get subplot geometries
    subplot_polygons = operational_data.get('subplot_polygons', {})
    subplot_centers = operational_data.get('subplot_centers', {})
    
    if not subplot_polygons or not subplot_centers:
        return None, None
    
    # Get polygons and centers for selected subplots
    selected_polygons = []
    selected_centers = []
    
    for subplot_num in subplot_list:
        if subplot_num in subplot_polygons:
            poly_coords = subplot_polygons[subplot_num]
            selected_polygons.append(Polygon(poly_coords))
        if subplot_num in subplot_centers:
            selected_centers.append(subplot_centers[subplot_num])
    
    if not selected_polygons or not selected_centers:
        return None, None
    
    # STRATEGY 1: Find common corner/vertex point (where adjacent subplots meet)
    all_vertices = []
    for poly in selected_polygons:
        vertices = list(poly.exterior.coords)[:-1]  # Exclude duplicate last point
        all_vertices.extend(vertices)
    
    # Find vertices shared by multiple subplots
    from collections import Counter
    vertex_counts = Counter(all_vertices)
    
    # Common vertices (shared by 2+ subplots) - sorted by frequency
    common_vertices = [(v, count) for v, count in vertex_counts.items() if count >= 2]
    
    # DEBUG: Log what we found
    DevLogger.section(f"Valve Position for subplots {subplot_list}")
    log_debug(f"Total vertices: {len(all_vertices)}")
    log_debug(f"Common vertices found: {len(common_vertices)}")
    if common_vertices:
        common_vertices.sort(key=lambda x: x[1], reverse=True)
        log_debug(f"Most common vertex: {common_vertices[0][0]} (shared by {common_vertices[0][1]} subplots)")
    
    reference_point = None
    
    if common_vertices:
        # Found shared corners - use the most common one (where most subplots meet)
        common_vertices.sort(key=lambda x: x[1], reverse=True)
        best_vertex = common_vertices[0][0]
        reference_point = Point(best_vertex)
        log_debug(f"Using common corner at: ({best_vertex[0]:.1f}, {best_vertex[1]:.1f})")
    else:
        # STRATEGY 2: No common vertices (subplots not adjacent)
        # Use the centroid of all selected subplot centers as reference
        centroid_x = sum(c[0] for c in selected_centers) / len(selected_centers)
        centroid_y = sum(c[1] for c in selected_centers) / len(selected_centers)
        reference_point = Point(centroid_x, centroid_y)
        log_debug(f"No common corner, using centroid at: ({centroid_x:.1f}, {centroid_y:.1f})")
    
    # Now project the reference point onto the nearest submain line
    # BUT: Only consider submains that are reasonably close to the subplot group
    submains = network.get('submains', [])
    
    if not submains:
        # No submains - return the reference point itself
        log_debug("No submains found, using reference point directly")
        return reference_point.x, reference_point.y
    
    log_debug(f"Found {len(submains)} submain lines")
    
    # Calculate bounding box of selected subplots to filter relevant submains
    all_x = [c[0] for c in selected_centers]
    all_y = [c[1] for c in selected_centers]
    bbox_min_x = min(all_x) - 50  # Add 50m buffer
    bbox_max_x = max(all_x) + 50
    bbox_min_y = min(all_y) - 50
    bbox_max_y = max(all_y) + 50
    
    log_debug(f"Subplot bounding box: X=[{bbox_min_x:.1f}, {bbox_max_x:.1f}], Y=[{bbox_min_y:.1f}, {bbox_max_y:.1f}]")
    
    # Find the closest point on submains that intersect or are near the subplot bounding box
    min_distance = float('inf')
    best_valve_point = None
    best_submain_idx = None
    
    for idx, submain in enumerate(submains):
        if len(submain) < 2:
            continue
        
        # Check if this submain passes through or near the subplot bounding box
        submain_in_bbox = False
        for point in submain:
            if (bbox_min_x <= point[0] <= bbox_max_x and 
                bbox_min_y <= point[1] <= bbox_max_y):
                submain_in_bbox = True
                break
        
        if not submain_in_bbox:
            log_debug(f"Skipping Submain {idx + 1} (outside subplot area)")
            continue
        
        line = LineString(submain)
        nearest_on_submain = line.interpolate(line.project(reference_point))
        distance = reference_point.distance(nearest_on_submain)
        
        log_debug(f"Submain {idx + 1}: distance = {distance:.1f}m, position = ({nearest_on_submain.x:.1f}, {nearest_on_submain.y:.1f})")
        
        if distance < min_distance:
            min_distance = distance
            best_valve_point = nearest_on_submain
            best_submain_idx = idx
    
    if best_valve_point:
        log_info(f"SELECTED: Submain {best_submain_idx + 1} at: ({best_valve_point.x:.1f}, {best_valve_point.y:.1f})")
        log_debug(f"Distance from reference: {min_distance:.1f}m")
        return best_valve_point.x, best_valve_point.y
    
    # Fallback: No submain in subplot area - use reference point directly
    log_warning("No submain found in subplot area, using reference point directly")
    return reference_point.x, reference_point.y


def show():
    """Interactive pipe network design with full-screen map and toolbar controls"""
    
    # Custom CSS for AutoCAD-style layout - IMPROVED
    st.markdown("""
        <style>
        .stButton button {
            width: 100%;
            border-radius: 4px;
            height: 3em;
            font-weight: 600;
        }
        .tool-active button {
            background-color: #0078d4 !important;
            border: 2px solid #004578 !important;
            color: white !important;
            box-shadow: 0 0 10px rgba(0, 120, 212, 0.5);
        }
        .block-container {
            padding-top: 0.5rem;
            padding-bottom: 0rem;
            max-width: 100%;
        }
        div[data-testid="stHorizontalBlock"] {
            gap: 0.3rem;
        }
        </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<h2 class="sub-header">🔧 CAD - Pipe Network Layout</h2>', unsafe_allow_html=True)
    
    # Get required data
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    operational_data = st.session_state.project_data.get('operational_data', {})
    
    if not field_geometry:
        st.warning("⚠️ Please complete field mapping and operational design first.")
        return
    
    # Show Operational Design info if available
    if operational_data:
        st.info("""
        💡 **Operational Design Overlay Active**: The map below shows colored subplots based on your irrigation schedule.
        - **Day 1 (Red)**: Farthest plots from water source
        - **Day 2-5**: Progressively closer to water source
        - **Toggle overlay** using the checkbox in the sidebar
        - Each day irrigates approximately the same **area** (~19 ha)
        """)
    
    # Initialize pipe network in session state
    if 'pipe_network_design' not in st.session_state.project_data:
        st.session_state.project_data['pipe_network_design'] = {
            'mainlines': [], 'submains': [], 'laterals': [], 'sprinklers': [], 'valves': []
        }
    
    network_temp = st.session_state.project_data['pipe_network_design']
    
    # Restore saved valve tables from project_data on page load
    # Priority: 1) project_data['valve_table'], 2) network['valves'], 3) existing session state
    if 'valve_table' in st.session_state.project_data and st.session_state.project_data['valve_table']:
        # Restore from saved valve_table in project_data (cloud save)
        st.session_state.valve_table = st.session_state.project_data['valve_table']
    elif network_temp.get('valves') and ('valve_table' not in st.session_state or not st.session_state.valve_table):
        # Fallback: reconstruct valve_table from network valves array
        st.session_state.valve_table = [
            {
                'name': v.get('name', f'V{i+1}'),
                'subplots': v.get('selected_subplots', []),
                'irrigation_day': v.get('irrigation_day', 'Not assigned'),
                'x': v.get('x', 0),
                'y': v.get('y', 0),
                'auto_positioned': v.get('auto_positioned', False)
            }
            for i, v in enumerate(network_temp['valves'])
        ]
    elif 'valve_table' not in st.session_state:
        st.session_state.valve_table = []
    
    # Same for mainline valve table
    if 'mainline_valve_table' in st.session_state.project_data and st.session_state.project_data['mainline_valve_table']:
        st.session_state.mainline_valve_table = st.session_state.project_data['mainline_valve_table']
    elif network_temp.get('mainline_valves') and ('mainline_valve_table' not in st.session_state or not st.session_state.mainline_valve_table):
        st.session_state.mainline_valve_table = network_temp['mainline_valves']
    elif 'mainline_valve_table' not in st.session_state:
        st.session_state.mainline_valve_table = []
    
    # CRITICAL: Auto-rebuild network['valves'] from valve_table on page load
    # This ensures valves are displayed in pipe_network_design.py even after refresh
    if st.session_state.valve_table and not network_temp.get('valves'):
        network_temp['valves'] = []
        for valve_config in st.session_state.valve_table:
            valve_data = {
                'name': valve_config.get('name', ''),
                'x': float(valve_config.get('x', 0)),
                'y': float(valve_config.get('y', 0)),
                'subplots_served': len(valve_config.get('subplots', [])),
                'selected_subplots': valve_config.get('subplots', []),
                'irrigation_day': valve_config.get('irrigation_day', 'Not assigned'),
                'subplot_id': valve_config.get('subplots', ['Not selected'])[0] if valve_config.get('subplots') else 'Not selected',
                'is_valid': valve_config.get('irrigation_day', '') not in ['Mixed', 'Invalid', 'N/A', 'Not assigned']
            }
            network_temp['valves'].append(valve_data)
    
    # Also rebuild mainline valves if needed
    if st.session_state.mainline_valve_table and not network_temp.get('mainline_valves'):
        network_temp['mainline_valves'] = st.session_state.mainline_valve_table
    
    # Initialize drawing state
    if 'current_drawing' not in st.session_state:
        st.session_state.current_drawing = {
            'mode': 'Mainline',
            'points': [],
            'is_drawing': False,
            'draw_method': 'Click-to-Click',
            'enable_angle_snap': False,
            'angle_snap_increment': 45,
            'enable_length_constraint': False,
            'target_length': 50.0,
            'show_measurements': True,
            'show_alignment_guides': True,
            'enable_snap': True,
            'snap_size': 25.0,
            'enable_intersection_snap': True,
            'enable_line_snap': True,
            'valve_coverage': 'full',  # full, three-quarter, half, quarter
            'valve_direction': 0,  # 0, 90, 180, 270 degrees for orientation
            'show_operational_overlay': True  # NEW: Show operational design colors
        }
    
    # Initialize selection state
    if 'selected_line' not in st.session_state:
        st.session_state.selected_line = {'type': None, 'index': None}
    
    network = st.session_state.project_data['pipe_network_design']
    drawing = st.session_state.current_drawing
    selected = st.session_state.selected_line
    
    # --- TOP TOOLBAR (AutoCAD Style) ---
    
    # Row 1: Drawing Tools
    col1, col2, col3, col4, col5, col6, col7, col8 = st.columns([1, 1, 1, 1, 1, 1, 1, 2])
    
    with col1:
        # Mainline Tool
        is_active = drawing['is_drawing'] and drawing['mode'] == 'Mainline'
        if is_active:
            st.markdown('<div class="tool-active">', unsafe_allow_html=True)
        if st.button("🔴 Mainline", key="tool_mainline", help="Draw Mainline Pipe"):
            drawing['mode'] = 'Mainline'
            drawing['is_drawing'] = True
            drawing['points'] = []
            selected['type'] = None
            st.rerun()
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col2:
        # Submain Tool
        is_active = drawing['is_drawing'] and drawing['mode'] == 'Submain'
        if is_active:
            st.markdown('<div class="tool-active">', unsafe_allow_html=True)
        if st.button("🟠 Submain", key="tool_submain", help="Draw Submain Pipe"):
            drawing['mode'] = 'Submain'
            drawing['is_drawing'] = True
            drawing['points'] = []
            selected['type'] = None
            st.rerun()
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col3:
        # Lateral Tool
        is_active = drawing['is_drawing'] and drawing['mode'] == 'Lateral'
        if is_active:
            st.markdown('<div class="tool-active">', unsafe_allow_html=True)
        if st.button("🟢 Lateral", key="tool_lateral", help="Draw Lateral Pipe"):
            drawing['mode'] = 'Lateral'
            drawing['is_drawing'] = True
            drawing['points'] = []
            selected['type'] = None
            st.rerun()
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col4:
        # Valve Tool
        is_active = drawing['is_drawing'] and drawing['mode'] == 'Valve'
        if is_active:
            st.markdown('<div class="tool-active">', unsafe_allow_html=True)
        if st.button("🔵 Valve", key="tool_valve", help="Place Valve on Submain/Lateral"):
            drawing['mode'] = 'Valve'
            drawing['is_drawing'] = True
            drawing['points'] = []
            selected['type'] = None
            st.rerun()
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col5:
        # Mainline Valve Tool (for placing valves at submain-mainline junctions)
        is_active = drawing['is_drawing'] and drawing['mode'] == 'MainlineValve'
        if is_active:
            st.markdown('<div class="tool-active">', unsafe_allow_html=True)
        if st.button("🟣 Main Valve", key="tool_mainline_valve", help="Place Valve at Mainline-Submain junction"):
            drawing['mode'] = 'MainlineValve'
            drawing['is_drawing'] = True
            drawing['points'] = []
            selected['type'] = None
            st.rerun()
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)
    
    with col6:
        # Measure Tool (NEW)
        is_active = drawing['is_drawing'] and drawing['mode'] == 'Measure'
        if is_active:
            st.markdown('<div class="tool-active">', unsafe_allow_html=True)
        if st.button("📏 Measure", key="tool_measure", help="Measure distance between two points"):
            drawing['mode'] = 'Measure'
            drawing['is_drawing'] = True
            drawing['points'] = []
            selected['type'] = None
            # Initialize measurement result
            if 'measurement' not in st.session_state:
                st.session_state.measurement = None
            st.rerun()
        if is_active:
            st.markdown('</div>', unsafe_allow_html=True)
            
    with col6:
        # Finish Tool
        if st.button("✅ Finish", key="tool_finish", disabled=not (drawing['is_drawing'] and len(drawing['points']) >= 2)):
            if drawing['mode'] == 'Mainline':
                network['mainlines'].append(drawing['points'].copy())
            elif drawing['mode'] == 'Submain':
                network['submains'].append(drawing['points'].copy())
            elif drawing['mode'] == 'Lateral':
                network['laterals'].append(drawing['points'].copy())
            elif drawing['mode'] == 'Measure':
                # Calculate and store measurement
                if len(drawing['points']) == 2:
                    p1, p2 = drawing['points']
                    distance = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                    st.session_state.measurement = {
                        'point1': p1,
                        'point2': p2,
                        'distance': distance
                    }
            drawing['points'] = []
            drawing['is_drawing'] = False
            st.rerun()
            
    with col7:
        # Cancel/Clear Tool
        if st.button("❌ Cancel", key="tool_cancel"):
            drawing['points'] = []
            drawing['is_drawing'] = False
            if 'measurement' in st.session_state:
                st.session_state.measurement = None
            st.rerun()
            
    with col8:
        # Save
        if st.button("💾 Save Network", key="tool_save", type="primary"):
            # Save network to pipe_network_design (the key used throughout the module)
            st.session_state.project_data['pipe_network_design'] = network
            # Also save valve tables if they exist
            if 'valve_table' in st.session_state:
                st.session_state.project_data['valve_table'] = st.session_state.valve_table
            if 'mainline_valve_table' in st.session_state:
                st.session_state.project_data['mainline_valve_table'] = st.session_state.mainline_valve_table
            st.success("✅ Network saved!")
    
    # Display measurement result if available
    if 'measurement' in st.session_state and st.session_state.measurement:
        meas = st.session_state.measurement
        st.success(f"📏 **Measurement**: {meas['distance']:.2f} m | From ({meas['point1'][0]:.1f}, {meas['point1'][1]:.1f}) to ({meas['point2'][0]:.1f}, {meas['point2'][1]:.1f})")
    
    # Row 2: SIMPLE SNAP OPTIONS
    with st.expander("⚙️ Drawing Options", expanded=False):
        tool_col1, tool_col2, tool_col3 = st.columns(3)
        with tool_col1:
            enable_snap = st.checkbox("🧲 Snap to Intersections/Endpoints", value=False, 
                                     help="Enable to snap to existing line intersections and endpoints")
            drawing['enable_snap'] = enable_snap
        with tool_col2:
            drawing['show_measurements'] = st.checkbox("📏 Show Dimensions", value=drawing.get('show_measurements', True))
        with tool_col3:
            if st.button("🗑️ Clear All", key="clear_all_btn"):
                network['mainlines'] = []
                network['submains'] = []
                network['laterals'] = []
                network['valves'] = []
                if 'measurement' in st.session_state:
                    st.session_state.measurement = None
                st.rerun()
    
    # Valve Quick Actions Bar (show when in Valve mode)
    if drawing.get('mode') == 'Valve':
        st.markdown("### 🔵 Valve Placement Mode")
        st.markdown("**Click on the map to place valves manually, or use auto-place below**")
        
        # Get operational data
        operational_data = st.session_state.project_data.get('operational_data', {})
        actual_total_subplots = operational_data.get('total_subplots', 0)
        subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
        
        if actual_total_subplots == 0:
            st.warning("⚠️ No subplots defined in Operational Design. Please configure irrigation schedule first.")
        else:
            # Initialize valve table in session state if not exists
            if 'valve_table' not in st.session_state:
                st.session_state.valve_table = []
            
            # Quick Actions Row
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # Option to place valves at every intersection or grouped
                valve_density = st.radio(
                    "Valve density",
                    ["Every intersection (1-2 plots/valve)", "Grouped (3-4 plots/valve)"],
                    index=0,
                    horizontal=True,
                    key="valve_density_option",
                    help="Choose 'Every intersection' for more accurate pipe sizing"
                )
                
                if st.button("📍 Auto-place at Grid Intersections", key="auto_place_grid_intersections"):
                    # Get field geometry and grid dimensions
                    field_geometry = st.session_state.project_data.get('field_geometry', {})
                    n_rows = operational_data.get('n_rows', 0)
                    n_cols = operational_data.get('n_cols', 0)
                    
                    # Determine skip interval based on density selection
                    skip_interval = 1 if "Every" in valve_density else 2
                    
                    # Find grid intersections ON SUBMAIN LINES ONLY
                    intersections = find_grid_intersections(
                        field_geometry, n_rows, n_cols, 
                        network=network,
                        snap_to_submain=True,
                        submain_threshold=15.0,
                        skip_interval=skip_interval  # Pass the skip interval
                    )
                    
                    if intersections:
                        st.session_state.valve_table = []
                        network['valves'] = []
                        
                        for idx, (x, y) in enumerate(intersections):
                            valve_entry = {
                                'name': f'V{idx + 1}',
                                'subplots': [],
                                'irrigation_day': 'Not assigned',
                                'x': x,
                                'y': y,
                                'auto_positioned': True,
                                'adjacent': False
                            }
                            st.session_state.valve_table.append(valve_entry)
                            
                            valve_data = {
                                'name': f'V{idx + 1}',
                                'x': float(x),
                                'y': float(y),
                                'subplots_served': 0,
                                'selected_subplots': [],
                                'irrigation_day': 'Not assigned',
                                'subplot_id': 'Not selected',
                                'is_valid': True
                            }
                            network['valves'].append(valve_data)
                        
                        st.success(f"✅ Placed {len(intersections)} valves!")
                        st.rerun()
                    else:
                        st.warning("⚠️ No suitable positions found.")
            
            with col2:
                if st.button("🗑️ Clear All Valves", key="clear_all_valves_quick"):
                    st.session_state.valve_table = []
                    network['valves'] = []
                    st.success("✅ Cleared all valves")
                    st.rerun()
            
            with col3:
                # Reset subplot assignments button (keeps valve positions, clears subplot assignments)
                if st.button("🔄 Reset Subplot Assignments", key="reset_subplot_assignments"):
                    # Clear subplot assignments but keep valve positions
                    for valve in network.get('valves', []):
                        valve['selected_subplots'] = []
                        valve['subplots_served'] = 0
                        valve['irrigation_day'] = 'Not assigned'
                        valve['subplot_id'] = 'Not selected'
                    for idx, valve_entry in enumerate(st.session_state.get('valve_table', [])):
                        valve_entry['subplots'] = []
                        valve_entry['irrigation_day'] = 'Not assigned'
                        # Clear the text input widget values in session state
                        input_key = f"valve_subplots_{idx}"
                        if input_key in st.session_state:
                            del st.session_state[input_key]
                    st.success("✅ Reset all valve subplot assignments. Please re-assign subplots to valves.")
                    st.rerun()
            
            col4, _ = st.columns([1, 2])
            with col4:
                st.success(f"✅ {actual_total_subplots} subplots | {len(st.session_state.get('valve_table', []))} valves")

    # Mainline Valve Quick Actions Bar (show when in MainlineValve mode)
    if drawing.get('mode') == 'MainlineValve':
        st.markdown("### 🟣 Mainline Valve Placement Mode")
        
        # Initialize mainline valve table in session state if not exists
        if 'mainline_valve_table' not in st.session_state:
            st.session_state.mainline_valve_table = []
        
        # Initialize mainline_valves in network if not exists
        if 'mainline_valves' not in network:
            network['mainline_valves'] = []
        
        # Get list of submains for assignment
        submains = network.get('submains', [])
        num_submains = len(submains)
        
        # Check if this is a no-submain system
        is_no_submain_system = num_submains == 0
        
        if is_no_submain_system:
            st.markdown("**Place valves at mainline-lateral junctions for mainline pipe sizing**")
            st.info("""
            ℹ️ **No-Submain System Detected**
            
            Your system has no submain lines - the mainline connects directly to laterals.
            Place valves along the mainline where lateral connections occur.
            
            **Click on the mainline** at each point where laterals connect.
            """)
            
            # Quick Actions Row for no-submain systems
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📍 Auto-place at Lateral Intersections", key="auto_place_mainline_valves_no_sub"):
                    # Find intersections between mainlines and laterals
                    from shapely.geometry import LineString, Point
                    
                    mainline_valves = []
                    mainlines = network.get('mainlines', [])
                    laterals = network.get('laterals', [])
                    
                    # Create LineString objects for mainlines
                    mainline_lines = []
                    for ml in mainlines:
                        if len(ml) >= 2:
                            mainline_lines.append(LineString(ml))
                    
                    if not mainline_lines:
                        st.warning("⚠️ No mainlines drawn. Please draw mainlines first.")
                    elif not laterals:
                        st.warning("⚠️ No laterals drawn. Please draw laterals first, or manually place valves on the mainline.")
                    else:
                        for lateral_idx, lateral in enumerate(laterals):
                            if len(lateral) >= 2:
                                lateral_line = LineString(lateral)
                                
                                # Find closest point on mainline to lateral start/end
                                for ml_line in mainline_lines:
                                    # Check start point of lateral
                                    start_pt = Point(lateral[0])
                                    end_pt = Point(lateral[-1])
                                    
                                    dist_start = ml_line.distance(start_pt)
                                    dist_end = ml_line.distance(end_pt)
                                    
                                    # Use whichever end is closer to mainline
                                    if dist_start < dist_end and dist_start < 20:
                                        junction_x, junction_y = lateral[0]
                                    elif dist_end < 20:
                                        junction_x, junction_y = lateral[-1]
                                    else:
                                        continue  # No junction found
                                    
                                    # Check if valve already exists at this position
                                    exists = False
                                    for existing in mainline_valves:
                                        if abs(existing['x'] - junction_x) < 5 and abs(existing['y'] - junction_y) < 5:
                                            exists = True
                                            break
                                    
                                    if not exists:
                                        mainline_valves.append({
                                            'name': f'MV{len(mainline_valves) + 1}',
                                            'x': junction_x,
                                            'y': junction_y,
                                            'submain_indices': [],
                                            'submain_names': [],
                                            'submain_reference': f'Lateral Connection {len(mainline_valves) + 1}',
                                            'lateral_connection': True
                                        })
                        
                        if mainline_valves:
                            st.session_state.mainline_valve_table = mainline_valves
                            network['mainline_valves'] = mainline_valves
                            st.success(f"✅ Placed {len(mainline_valves)} mainline valve(s) at lateral junctions!")
                            st.rerun()
                        else:
                            st.warning("⚠️ No junctions found. Make sure laterals connect to mainlines, or place valves manually.")
            
            with col2:
                if st.button("🗑️ Clear Mainline Valves", key="clear_mainline_valves_no_sub"):
                    st.session_state.mainline_valve_table = []
                    network['mainline_valves'] = []
                    st.success("✅ Cleared all mainline valves")
                    st.rerun()
            
            with col3:
                mlv_count = len(st.session_state.get('mainline_valve_table', []))
                st.success(f"✅ {mlv_count} mainline valve(s)")
            
            # Display mainline valve table if valves exist
            if st.session_state.get('mainline_valve_table'):
                st.markdown("---")
                st.markdown("#### 📊 Mainline Valve Configuration")
                st.info("💡 These valves mark lateral connection points on the mainline for pipe sizing.")
                
                for idx, mv in enumerate(st.session_state.mainline_valve_table):
                    with st.container():
                        col_name, col_pos, col_info = st.columns([1, 1, 2])
                        
                        with col_name:
                            st.markdown(f"**🟣 {mv['name']}**")
                        
                        with col_pos:
                            st.caption(f"Position: ({mv['x']:.1f}, {mv['y']:.1f})")
                        
                        with col_info:
                            st.caption(f"Lateral Connection Point")
                        
                        st.markdown("---")
                
                # Save button
                if st.button("💾 Save Mainline Valves", key="save_mainline_valves_no_sub", type="primary"):
                    network['mainline_valves'] = st.session_state.mainline_valve_table
                    st.session_state.project_data['pipe_network_design'] = network
                    st.session_state.project_data['mainline_valve_table'] = st.session_state.mainline_valve_table
                    st.success("✅ Mainline valves saved!")
                    st.rerun()
        
        else:
            # STANDARD CASE: System has submains
            st.markdown("**Place valves at mainline-submain junctions for mainline pipe sizing**")
            st.info(f"📊 Found {num_submains} submain(s). Place a valve at each mainline-submain junction.")
            
            # Quick Actions Row
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("📍 Auto-place at Mainline-Submain Junctions", key="auto_place_mainline_valves"):
                    # Find intersections between mainlines and submains
                    from shapely.geometry import LineString, Point
                    
                    mainline_valves = []
                    mainlines = network.get('mainlines', [])
                    
                    # Create LineString objects for mainlines
                    mainline_lines = []
                    for ml in mainlines:
                        if len(ml) >= 2:
                            mainline_lines.append(LineString(ml))
                    
                    if not mainline_lines:
                        st.warning("⚠️ No mainlines drawn. Please draw mainlines first.")
                    else:
                        for submain_idx, submain in enumerate(submains):
                            if len(submain) >= 2:
                                submain_line = LineString(submain)
                                
                                # Find closest point on mainline to submain start/end
                                for ml_line in mainline_lines:
                                    # Check start point of submain
                                    start_pt = Point(submain[0])
                                    end_pt = Point(submain[-1])
                                    
                                    dist_start = ml_line.distance(start_pt)
                                    dist_end = ml_line.distance(end_pt)
                                    
                                    # Use whichever end is closer to mainline
                                    if dist_start < dist_end and dist_start < 20:
                                        junction_x, junction_y = submain[0]
                                    elif dist_end < 20:
                                        junction_x, junction_y = submain[-1]
                                    else:
                                        continue  # No junction found
                                    
                                    # Check if valve already exists at this position
                                    exists = False
                                    for existing in mainline_valves:
                                        if abs(existing['x'] - junction_x) < 5 and abs(existing['y'] - junction_y) < 5:
                                            # Add this submain to existing valve
                                            if submain_idx not in existing['submain_indices']:
                                                existing['submain_indices'].append(submain_idx)
                                            exists = True
                                            break
                                    
                                    if not exists:
                                        mainline_valves.append({
                                            'name': f'MV{len(mainline_valves) + 1}',
                                            'x': junction_x,
                                            'y': junction_y,
                                            'submain_indices': [submain_idx],
                                            'submain_names': [f'Submain {submain_idx + 1}']
                                        })
                        
                        if mainline_valves:
                            st.session_state.mainline_valve_table = mainline_valves
                            network['mainline_valves'] = mainline_valves
                            st.success(f"✅ Placed {len(mainline_valves)} mainline valve(s) at junctions!")
                            st.rerun()
                        else:
                            st.warning("⚠️ No junctions found. Make sure submains connect to mainlines.")
            
            with col2:
                if st.button("🗑️ Clear Mainline Valves", key="clear_mainline_valves"):
                    st.session_state.mainline_valve_table = []
                    network['mainline_valves'] = []
                    st.success("✅ Cleared all mainline valves")
                    st.rerun()
            
            with col3:
                mlv_count = len(st.session_state.get('mainline_valve_table', []))
                st.success(f"✅ {mlv_count} mainline valve(s) | {num_submains} submain(s)")
            
            # Display mainline valve table if valves exist
            if st.session_state.get('mainline_valve_table'):
                st.markdown("---")
                st.markdown("#### 📊 Mainline Valve Configuration")
                st.info("💡 Assign which submain(s) each mainline valve feeds. This is used for mainline pipe sizing.")
                
                for idx, mv in enumerate(st.session_state.mainline_valve_table):
                    with st.container():
                        col_name, col_pos, col_submain = st.columns([1, 1, 2])
                        
                        with col_name:
                            st.markdown(f"**🟣 {mv['name']}**")
                        
                        with col_pos:
                            st.caption(f"Position: ({mv['x']:.1f}, {mv['y']:.1f})")
                        
                        with col_submain:
                            # Multi-select for submains this valve feeds
                            submain_options = [f"Submain {i+1}" for i in range(num_submains)]
                            current_selection = mv.get('submain_names', [])
                            
                            selected_submains = st.multiselect(
                                "Feeds Submain(s)",
                                submain_options,
                                default=current_selection,
                                key=f"mv_submain_{idx}",
                                label_visibility="collapsed"
                            )
                            
                            # Update the valve data - both formats for compatibility
                            mv['submain_names'] = selected_submains
                            mv['submain_indices'] = [int(s.split()[-1]) - 1 for s in selected_submains]
                            # For mainline design compatibility
                            if selected_submains:
                                mv['submain_reference'] = ', '.join(selected_submains)
                                mv['submain_idx'] = mv['submain_indices'][0] if mv['submain_indices'] else None
                            else:
                                mv['submain_reference'] = 'Not assigned'
                                mv['submain_idx'] = None
                        
                        st.markdown("---")
                
                # Save button
                if st.button("💾 Save Mainline Valves", key="save_mainline_valves", type="primary"):
                    network['mainline_valves'] = st.session_state.mainline_valve_table
                    st.session_state.project_data['pipe_network_design'] = network
                    st.session_state.project_data['mainline_valve_table'] = st.session_state.mainline_valve_table
                    st.success("✅ Mainline valves saved!")
                    st.rerun()

    # --- MAIN MAP AREA WITH SIDE PANEL ---
    
    # Status Bar - SIMPLE with DEBUG INFO
    if drawing['is_drawing']:
        if len(drawing['points']) > 0:
            last_pt = drawing['points'][-1]
            st.info(f"✏️ **DRAWING {drawing['mode'].upper()}** | **Points: {len(drawing['points'])}** | Last: ({last_pt[0]:.1f}, {last_pt[1]:.1f}) | **Click anywhere for next point** or click 'Finish'")
        else:
            st.info(f"✏️ **DRAWING {drawing['mode'].upper()}** | **Click anywhere on the map** to place first point - Full freedom!")
    else:
        st.success(f"✅ Ready | Select Mainline/Submain/Lateral above to start drawing | Click anywhere to place points freely!")

    # Create and display the interactive plot
    fig = create_interactive_plot(field_geometry, operational_data, network, drawing)
    
    # Show helpful message for Measure mode
    if drawing.get('is_drawing') and drawing.get('mode') == 'Measure':
        if len(drawing.get('points', [])) == 0:
            st.info("📏 **MEASUREMENT MODE:** Click on a gray grid point to select your first measurement point.")
        elif len(drawing.get('points', [])) == 1:
            st.info("📏 **First point recorded!** Click on another gray grid point to complete the measurement.")
    
    # Sidebar: Operational Design Overlay Toggle
    if operational_data:
        st.sidebar.markdown("### 🎨 Operational Design Overlay")
        drawing['show_operational_overlay'] = st.sidebar.checkbox(
            "Show Irrigation Schedule Colors",
            value=drawing.get('show_operational_overlay', True),
            help="Display colored subplots based on irrigation schedule (Day 1 = Farthest from water source)"
        )
        
        if drawing['show_operational_overlay']:
            st.sidebar.markdown("**Color Legend:**")
            st.sidebar.markdown("- 🔴 Day 1 (Farthest)")
            st.sidebar.markdown("- 🩵 Day 2")
            st.sidebar.markdown("- 🔵 Day 3")
            st.sidebar.markdown("- 🟠 Day 4")
            st.sidebar.markdown("- 🟢 Day 5")
        
        st.sidebar.markdown("---")
    
    # DEBUG: Show drawing state
    st.sidebar.write("### 🐛 Debug Info")
    st.sidebar.write(f"**Drawing Mode:** {drawing.get('mode', 'None')}")
    st.sidebar.write(f"**Is Drawing:** {drawing.get('is_drawing', False)}")
    st.sidebar.write(f"**Points Count:** {len(drawing.get('points', []))}")
    st.sidebar.write(f"**Click Counter:** {st.session_state.get('click_counter', 0)}")
    
    # Show field rotation if field exists
    if field_geometry and field_geometry.get('polygon'):
        try:
            from shapely.geometry import Polygon
            poly = Polygon(field_geometry['polygon'])
            corners = list(poly.convex_hull.exterior.coords)[:-1]
            if len(corners) == 4:
                max_length = 0
                best_angle = 0
                for j in range(4):
                    p1 = corners[j]
                    p2 = corners[(j + 1) % 4]
                    edge_length = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                    if edge_length > max_length:
                        max_length = edge_length
                        dx = p2[0] - p1[0]
                        dy = p2[1] - p1[1]
                        best_angle = np.degrees(np.arctan2(dy, dx))
                st.sidebar.write(f"**🔄 Field Rotation:** {best_angle:.1f}°")
        except:
            pass
    
    # SWITCH TO st.plotly_chart with on_select to capture clicks
    # Store selection in session state with unique key
    selection_key = f"map_selection_{st.session_state.get('click_counter', 0)}"
    
    # Create two-column layout: Map (left, larger) and Valve Table (right)
    if drawing.get('mode') == 'Valve' and st.session_state.get('valve_table'):
        map_col, table_col = st.columns([3, 2])
    else:
        map_col = st.container()
        table_col = None
    
    with map_col:
        # Display chart and capture click/selection events
        event = st.plotly_chart(
            fig,
            width="stretch",
            on_select="rerun",
            selection_mode="points",
            key=selection_key
        )
    
    # =============================================================================
    # HELPER: Build a map of which subplots are assigned to which valves
    # Used for duplicate detection
    # =============================================================================
    def get_subplot_valve_assignments():
        """Returns dict: {subplot_num: valve_name} for all assigned subplots"""
        assignments = {}
        for valve in st.session_state.get('valve_table', []):
            for subplot in valve.get('subplots', []):
                assignments[subplot] = valve.get('name', 'Unknown')
        return assignments
    
    # Display Valve Management Table beside the map (only in Valve mode with valves)
    if table_col is not None:
        with table_col:
            st.markdown("### 📊 Valve Management")
            
            operational_data = st.session_state.project_data.get('operational_data', {})
            subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
            total_subplots = operational_data.get('total_subplots', 0)
            
            # =============================================================================
            # UNASSIGNED PLOTS DISPLAY
            # =============================================================================
            all_subplots = set(range(1, total_subplots + 1))
            assigned_subplots = set()
            for valve in st.session_state.valve_table:
                assigned_subplots.update(valve.get('subplots', []))
            unassigned_subplots = sorted(all_subplots - assigned_subplots)
            
            if unassigned_subplots:
                unassigned_str = ', '.join(map(str, unassigned_subplots))
                st.warning(f"📋 **Unassigned plots ({len(unassigned_subplots)}):** {unassigned_str}")
            else:
                st.success(f"✅ All {total_subplots} plots assigned!")
            
            st.markdown("**Assign subplots to valves:**")
            
            # Scrollable container for valve table
            valve_container = st.container(height=450)
            with valve_container:
                for idx, valve in enumerate(st.session_state.valve_table):
                    with st.container():
                        st.markdown(f"**{valve['name']}** `({valve['x']:.0f}, {valve['y']:.0f})`")
                        
                        # Subplots input
                        current_subplots = ','.join(map(str, valve['subplots'])) if valve['subplots'] else ''
                        new_subplots = st.text_input(
                            "Subplots",
                            value=current_subplots,
                            key=f"valve_subplots_{idx}",
                            placeholder="e.g., 1,2,3,4",
                            label_visibility="collapsed"
                        )
                        
                        # Parse subplots with DUPLICATE VALIDATION
                        if new_subplots:
                            try:
                                subplot_list = [int(s.strip()) for s in new_subplots.split(',') if s.strip()]
                                
                                # ==============================================
                                # CHECK FOR DUPLICATE SUBPLOT ASSIGNMENTS
                                # ==============================================
                                duplicate_errors = []
                                valid_subplots = []
                                
                                for subplot in subplot_list:
                                    # Check if this subplot is assigned to another valve
                                    is_duplicate = False
                                    for other_idx, other_valve in enumerate(st.session_state.valve_table):
                                        if other_idx != idx:  # Don't check current valve
                                            if subplot in other_valve.get('subplots', []):
                                                duplicate_errors.append(f"Plot {subplot} → {other_valve['name']}")
                                                is_duplicate = True
                                                break
                                    
                                    if not is_duplicate:
                                        valid_subplots.append(subplot)
                                
                                # Show warning for duplicates
                                if duplicate_errors:
                                    st.warning(f"⚠️ Already assigned: {', '.join(duplicate_errors)}")
                                
                                # Only keep valid (non-duplicate) subplots
                                valve['subplots'] = sorted(valid_subplots)
                                
                                # Calculate irrigation day based on valid subplots only
                                unique_days = set()
                                for subplot in valid_subplots:
                                    if subplot in subplot_day_assignments:
                                        unique_days.add(subplot_day_assignments[subplot])
                                
                                if len(unique_days) == 1:
                                    valve['irrigation_day'] = list(unique_days)[0]
                                elif len(unique_days) > 1:
                                    valve['irrigation_day'] = f"Mixed"
                                else:
                                    valve['irrigation_day'] = 'N/A'
                            except:
                                valve['subplots'] = []
                                valve['irrigation_day'] = 'Invalid'
                        else:
                            valve['subplots'] = []
                            valve['irrigation_day'] = 'N/A'
                        
                        # Day indicator
                        day_color = "🟢" if valve['irrigation_day'] not in ['N/A', 'Invalid', 'Mixed'] else "🔴"
                        if valve['irrigation_day'] == 'Mixed':
                            day_color = "⚠️"
                        st.caption(f"{day_color} Day {valve['irrigation_day']}")
                        
                        # Move to position and delete - single row
                        total_valves = len(st.session_state.valve_table)
                        col_pos, col_go, col_del = st.columns([2, 1, 1])
                        
                        with col_pos:
                            # Number input for target position
                            target_pos = st.number_input(
                                "Move to V#",
                                min_value=1,
                                max_value=total_valves,
                                value=idx + 1,  # Current position (1-indexed)
                                step=1,
                                key=f"target_pos_{idx}",
                                label_visibility="collapsed"
                            )
                        
                        with col_go:
                            # Move button - only enabled if position is different
                            target_idx = int(target_pos) - 1  # Convert to 0-indexed
                            if target_idx != idx:
                                if st.button("📍", key=f"move_btn_{idx}", help=f"Move to position V{target_pos}"):
                                    # Remove valve from current position
                                    valve_to_move = st.session_state.valve_table.pop(idx)
                                    # Insert at new position
                                    st.session_state.valve_table.insert(target_idx, valve_to_move)
                                    # Renumber all valves
                                    for i, v in enumerate(st.session_state.valve_table):
                                        v['name'] = f'V{i+1}'
                                    # Clear number input keys to avoid stale state
                                    keys_to_clear = [k for k in st.session_state.keys() if k.startswith('target_pos_') or k.startswith('move_btn_')]
                                    for k in keys_to_clear:
                                        del st.session_state[k]
                                    st.toast(f"✅ Moved to V{target_pos}")
                                    st.rerun()
                            else:
                                st.button("📍", key=f"move_btn_{idx}", disabled=True, help="Change number to move")
                        
                        with col_del:
                            if st.button("🗑️", key=f"del_v_{idx}", help="Delete valve"):
                                st.session_state.valve_table.pop(idx)
                                # Renumber remaining valves
                                for i, v in enumerate(st.session_state.valve_table):
                                    v['name'] = f'V{i+1}'
                                st.rerun()
                        
                        st.markdown("---")
            
            # Save button
            if st.button("💾 Save & Apply", key="apply_valves_btn", type="primary", width="stretch"):
                network['valves'] = []
                for valve_config in st.session_state.valve_table:
                    valve_data = {
                        'name': valve_config['name'],
                        'x': float(valve_config['x']),
                        'y': float(valve_config['y']),
                        'subplots_served': len(valve_config['subplots']),
                        'selected_subplots': valve_config['subplots'],
                        'irrigation_day': valve_config['irrigation_day'],
                        'subplot_id': valve_config['subplots'][0] if valve_config['subplots'] else 'Not selected',
                        'is_valid': valve_config['irrigation_day'] not in ['Mixed', 'Invalid', 'N/A']
                    }
                    network['valves'].append(valve_data)
                st.success(f"✅ Applied {len(st.session_state.valve_table)} valves!")
                st.rerun()
    
    # DEBUG: Show event data
    st.sidebar.write(f"**Selection Event:** {event}")
    
    # Extract click coordinates from selection event
    click_x, click_y = None, None
    if event and 'selection' in event:
        selection = event['selection']
        st.sidebar.write(f"**Selection Details:** {selection}")
        
        if 'points' in selection and len(selection['points']) > 0:
            # Get first selected point
            point = selection['points'][0]
            st.sidebar.write(f"**Point Data:** {point}")
            
            click_x = point.get('x')
            click_y = point.get('y')
            
            st.sidebar.write(f"**Extracted X:** {click_x}")
            st.sidebar.write(f"**Extracted Y:** {click_y}")
    
    if drawing['is_drawing'] and click_x is not None and click_y is not None:
            # Handle Measurement mode (two clicks)
            if drawing['mode'] == 'Measure':
                if len(drawing['points']) == 0:
                    # First click - record first point
                    drawing['points'].append([click_x, click_y])
                    st.info(f"✅ First point recorded at ({click_x:.1f}, {click_y:.1f}). Click second point.")
                    st.rerun()
                elif len(drawing['points']) == 1:
                    # Second click - record second point and calculate
                    drawing['points'].append([click_x, click_y])
                    p1, p2 = drawing['points']
                    distance = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                    st.session_state.measurement = {
                        'point1': p1,
                        'point2': p2,
                        'distance': distance
                    }
                    # Reset drawing mode
                    drawing['points'] = []
                    drawing['is_drawing'] = False
                    drawing['mode'] = None
                    st.success(f"📏 Measurement complete: {distance:.2f} m")
                    st.rerun()
            # Handle Valve placement (single click)
            elif drawing['mode'] == 'Valve':
                # Default: Use exact click position
                snapped_x, snapped_y = click_x, click_y
                snap_type = "freehand"
                
                # OPTIONAL: Snap to submain/lateral intersections or points
                if drawing.get('enable_snap', False):
                    # Check for intersection snap
                    intersections = find_line_intersections(network)
                    min_dist = 15.0
                    for ix, iy in intersections:
                        dist = np.sqrt((click_x - ix)**2 + (click_y - iy)**2)
                        if dist < min_dist:
                            snapped_x, snapped_y = ix, iy
                            snap_type = "intersection"
                            min_dist = dist
                    
                    # Check for endpoint snap
                    if snap_type == "freehand":
                        all_endpoints = []
                        for line in network.get('submains', []) + network.get('laterals', []):
                            if line and len(line) >= 1:
                                all_endpoints.extend([line[0], line[-1]])
                        
                        min_dist = 15.0
                        for ex, ey in all_endpoints:
                            dist = np.sqrt((click_x - ex)**2 + (click_y - ey)**2)
                            if dist < min_dist:
                                snapped_x, snapped_y = ex, ey
                                snap_type = "endpoint"
                                min_dist = dist
                
                # Create valve data structure
                selected_subplots = drawing.get('valve_selected_subplots', [])
                subplots_served = drawing.get('subplots_served', len(selected_subplots))
                
                # Validate: Check if all subplots operate on the same day
                operational_data = st.session_state.project_data.get('operational_data', {})
                subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
                
                # Check for mixed irrigation days
                is_valid = True
                unique_days = set()
                if selected_subplots and subplot_day_assignments:
                    for subplot in selected_subplots:
                        if subplot in subplot_day_assignments:
                            day = subplot_day_assignments[subplot]
                            unique_days.add(day)
                    
                    if len(unique_days) > 1:
                        is_valid = False
                        st.error(f"""
                        ❌ **VALVE NOT PLACED - INVALID CONFIGURATION**
                        
                        Selected subplots operate on **{len(unique_days)} different days**: {sorted(unique_days)}
                        
                        A single valve cannot irrigate subplots on different days!
                        
                        Please reconfigure the valve to serve only subplots on the same irrigation day.
                        """)
                        # Don't create the valve - exit early
                        drawing['is_drawing'] = False
                        drawing['points'] = []
                        st.rerun()
                
                valve_data = {
                    'x': float(snapped_x),
                    'y': float(snapped_y),
                    'subplots_served': subplots_served,
                    'selected_subplots': selected_subplots,
                    'is_valid': is_valid  # Track validity
                }
                
                # Assign subplot_id and irrigation days based on selected subplots
                operational_data = st.session_state.project_data.get('operational_data', {})
                subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
                
                if selected_subplots and len(selected_subplots) > 0:
                    # Use first selected subplot as primary subplot_id
                    valve_data['subplot_id'] = selected_subplots[0]
                    
                    # Get irrigation days for all selected subplots
                    irrigation_days = []
                    for subplot in selected_subplots:
                        if subplot in subplot_day_assignments:
                            day = subplot_day_assignments[subplot]
                            if day not in irrigation_days:
                                irrigation_days.append(day)
                    
                    # Store irrigation days (could be multiple if valve serves subplots on different days)
                    if len(irrigation_days) == 1:
                        valve_data['irrigation_day'] = irrigation_days[0]
                    elif len(irrigation_days) > 1:
                        # Valve serves multiple days - store all days
                        valve_data['irrigation_day'] = f"{len(irrigation_days)} days: {irrigation_days}"
                        valve_data['irrigation_days_list'] = irrigation_days
                    else:
                        valve_data['irrigation_day'] = 'Not assigned'
                else:
                    valve_data['subplot_id'] = 'Not selected'
                    valve_data['irrigation_day'] = 'Not assigned'
                
                # Ensure valves list exists
                if 'valves' not in network:
                    network['valves'] = []
                
                # Add valve to network
                network['valves'].append(valve_data)
                
                # ALSO add to valve_table for management UI
                if 'valve_table' not in st.session_state:
                    st.session_state.valve_table = []
                
                # Get next valve number
                valve_num = len(st.session_state.valve_table) + 1
                valve_entry = {
                    'name': f'V{valve_num}',
                    'subplots': valve_data.get('selected_subplots', []),
                    'irrigation_day': valve_data.get('irrigation_day', 'Not assigned'),
                    'x': float(snapped_x),
                    'y': float(snapped_y),
                    'auto_positioned': False,  # Manually placed
                    'adjacent': False
                }
                st.session_state.valve_table.append(valve_entry)
                
                # Show confirmation with subplot info
                selected_subplots = valve_data.get('selected_subplots', [])
                irrigation_day = valve_data.get('irrigation_day', 'Not assigned')
                
                if selected_subplots:
                    subplots_str = ', '.join(map(str, selected_subplots))
                    st.toast(f"✅ Valve {valve_entry['name']} placed manually: Subplot(s) {subplots_str} | Day {irrigation_day}", icon="🔵")
                else:
                    st.toast(f"✅ Valve {valve_entry['name']} placed manually (click to assign subplots in table)", icon="🔵")
                
                # Reset drawing mode
                drawing['is_drawing'] = False
                drawing['points'] = []
                
                if 'click_counter' not in st.session_state:
                    st.session_state.click_counter = 0
                st.session_state.click_counter += 1
                st.rerun()
            
            # Handle Mainline Valve placement (single click)
            elif drawing['mode'] == 'MainlineValve':
                # Snap to nearest mainline-submain junction OR mainline-lateral junction (for no-submain systems)
                snapped_x, snapped_y = click_x, click_y
                snap_type = "freehand"
                
                # Find closest junction point
                mainlines = network.get('mainlines', [])
                submains = network.get('submains', [])
                laterals = network.get('laterals', [])
                
                from shapely.geometry import LineString, Point
                
                # Create LineString objects for mainlines
                mainline_lines = []
                for ml in mainlines:
                    if len(ml) >= 2:
                        mainline_lines.append(LineString(ml))
                
                # Determine if this is a no-submain system
                is_no_submain_system = len(submains) == 0
                
                best_junction = None
                min_dist = 30.0  # 30m snap distance
                junction_type = None
                
                if not is_no_submain_system:
                    # STANDARD: Find closest submain endpoint that's near a mainline
                    for submain_idx, submain in enumerate(submains):
                        if len(submain) >= 2:
                            for endpoint in [submain[0], submain[-1]]:
                                pt = Point(endpoint)
                                click_pt = Point(click_x, click_y)
                                
                                # Check if this endpoint is near clicked position
                                dist_to_click = click_pt.distance(pt)
                                
                                if dist_to_click < min_dist:
                                    # Verify it's also near a mainline
                                    for ml_line in mainline_lines:
                                        if ml_line.distance(pt) < 15:  # Within 15m of mainline
                                            snapped_x, snapped_y = endpoint
                                            min_dist = dist_to_click
                                            snap_type = "junction"
                                            junction_type = "submain"
                                            best_junction = submain_idx
                                            break
                else:
                    # NO-SUBMAIN: Find closest lateral endpoint or mainline point
                    # First try lateral endpoints
                    for lateral_idx, lateral in enumerate(laterals):
                        if len(lateral) >= 2:
                            for endpoint in [lateral[0], lateral[-1]]:
                                pt = Point(endpoint)
                                click_pt = Point(click_x, click_y)
                                
                                dist_to_click = click_pt.distance(pt)
                                
                                if dist_to_click < min_dist:
                                    # Verify it's also near a mainline
                                    for ml_line in mainline_lines:
                                        if ml_line.distance(pt) < 15:
                                            snapped_x, snapped_y = endpoint
                                            min_dist = dist_to_click
                                            snap_type = "junction"
                                            junction_type = "lateral"
                                            best_junction = lateral_idx
                                            break
                    
                    # If no lateral junction found, snap to nearest point on mainline
                    if snap_type == "freehand" and mainline_lines:
                        click_pt = Point(click_x, click_y)
                        for ml_line in mainline_lines:
                            # Project click point onto mainline
                            nearest_point = ml_line.interpolate(ml_line.project(click_pt))
                            dist_to_mainline = click_pt.distance(nearest_point)
                            
                            if dist_to_mainline < 25:  # Within 25m of mainline
                                snapped_x, snapped_y = nearest_point.x, nearest_point.y
                                snap_type = "mainline"
                                junction_type = "mainline_point"
                                break
                
                # Initialize mainline_valve_table if not exists
                if 'mainline_valve_table' not in st.session_state:
                    st.session_state.mainline_valve_table = []
                
                if 'mainline_valves' not in network:
                    network['mainline_valves'] = []
                
                # Check if valve already exists at this position
                exists = False
                for existing in st.session_state.mainline_valve_table:
                    if abs(existing['x'] - snapped_x) < 5 and abs(existing['y'] - snapped_y) < 5:
                        st.warning(f"⚠️ A mainline valve already exists near this position")
                        exists = True
                        break
                
                if snap_type in ["junction", "mainline"] and not exists:
                    valve_num = len(st.session_state.mainline_valve_table) + 1
                    
                    if junction_type == "submain":
                        ref_name = f'Submain {best_junction + 1}' if best_junction is not None else 'Not assigned'
                        mv_data = {
                            'name': f'MV{valve_num}',
                            'x': snapped_x,
                            'y': snapped_y,
                            'submain_reference': ref_name,
                            'submain_idx': best_junction,
                            'submain_indices': [best_junction] if best_junction is not None else [],
                            'submain_names': [ref_name] if best_junction is not None else [],
                            'lateral_connection': False
                        }
                        toast_msg = f"✅ Mainline Valve {mv_data['name']} placed at junction with {ref_name}"
                    else:
                        # Lateral or mainline point (no-submain system)
                        ref_name = f'Lateral Connection {valve_num}'
                        mv_data = {
                            'name': f'MV{valve_num}',
                            'x': snapped_x,
                            'y': snapped_y,
                            'submain_reference': ref_name,
                            'submain_idx': None,
                            'submain_indices': [],
                            'submain_names': [],
                            'lateral_connection': True
                        }
                        toast_msg = f"✅ Mainline Valve {mv_data['name']} placed at {ref_name}"
                    
                    st.session_state.mainline_valve_table.append(mv_data)
                    network['mainline_valves'].append(mv_data)
                    
                    st.toast(toast_msg, icon="🟣")
                elif not exists:
                    if is_no_submain_system:
                        st.warning("⚠️ Please click on or near the mainline. The valve will be placed at the clicked position on the mainline.")
                    else:
                        st.warning("⚠️ Please click near a mainline-submain junction. The valve should be placed where a submain connects to the mainline.")
                
                # Reset drawing mode
                drawing['is_drawing'] = False
                drawing['points'] = []
                st.rerun()
            
            # Handle Line drawing (mainline, submain, lateral)
            else:
                # Default: Use exact click position (FREEHAND - FULL FREEDOM)
                snapped_x, snapped_y = click_x, click_y
                snap_type = "freehand"
                
                # OPTIONAL: Only snap if user enabled it
                if drawing.get('enable_snap', False):
                    # Check for intersection snap
                    intersections = find_line_intersections(network)
                    min_dist = 15.0
                    for ix, iy in intersections:
                        dist = np.sqrt((click_x - ix)**2 + (click_y - iy)**2)
                        if dist < min_dist:
                            snapped_x, snapped_y = ix, iy
                            snap_type = "intersection"
                            min_dist = dist
                    
                    # Check for endpoint snap
                    if snap_type == "freehand":
                        all_endpoints = []
                        for line in network.get('mainlines', []) + network.get('submains', []) + network.get('laterals', []):
                            if line and len(line) >= 1:
                                all_endpoints.extend([line[0], line[-1]])
                        
                        min_dist = 15.0
                        for ex, ey in all_endpoints:
                            dist = np.sqrt((click_x - ex)**2 + (click_y - ey)**2)
                            if dist < min_dist:
                                snapped_x, snapped_y = ex, ey
                                snap_type = "endpoint"
                                min_dist = dist
                
                # Create new point at exact clicked location (or snapped if enabled)
                new_point = [float(snapped_x), float(snapped_y)]
                
                # Add point (avoid exact duplicates)
                if not drawing['points'] or drawing['points'][-1] != new_point:
                    drawing['points'].append(new_point)
                    if 'click_counter' not in st.session_state:
                        st.session_state.click_counter = 0
                    st.session_state.click_counter += 1
                    st.rerun()

    # Show network summary table below map
    # Show if ANY network elements exist (mainlines, submains, laterals, or valves)
    if network.get('mainlines') or network.get('submains') or network.get('laterals') or network.get('valves'):
        show_network_summary(network)

# ... (rest of file) ...


def create_interactive_plot(field_geometry, operational_data, network, drawing):
    """Create interactive Plotly figure with field and network"""
    
    # Initialize selected_line if not present (may be called before Layout page is visited)
    if 'selected_line' not in st.session_state:
        st.session_state.selected_line = {'type': None, 'index': None}
    
    fig = go.Figure()
    
    field_length = field_geometry.get('length_m', 850)
    field_width = field_geometry.get('width_m', 688)
    water_source = field_geometry.get('water_source')
    water_source_local = field_geometry.get('water_source_local')
    num_main_fields = operational_data.get('num_main_fields', 2)
    
    # Draw field boundary - use local polygon if available
    local_polygon = field_geometry.get('local_polygon')
    
    if local_polygon and len(local_polygon) > 0:
        # Use local coordinate polygon (already in meters)
        poly_x = [p[0] for p in local_polygon] + [local_polygon[0][0]]
        poly_y = [p[1] for p in local_polygon] + [local_polygon[0][1]]
        
        fig.add_trace(go.Scatter(
            x=poly_x, y=poly_y,
            mode='lines',
            line=dict(color='#424242', width=2),
            fill='toself',
            fillcolor='rgba(200, 200, 200, 0.2)',
            name='Field Boundary',
            hoverinfo='skip'
        ))
        
        # Calculate bounds
        min_x, max_x = min(poly_x), max(poly_x)
        min_y, max_y = min(poly_y), max(poly_y)
    else:
        # Use rectangle
        fig.add_trace(go.Scatter(
            x=[0, field_width, field_width, 0, 0],
            y=[0, 0, field_length, field_length, 0],
            mode='lines',
            line=dict(color='#424242', width=2),
            fill='toself',
            fillcolor='rgba(200, 200, 200, 0.2)',
            name='Field Boundary',
            hoverinfo='skip'
        ))
        min_x, max_x = 0, field_width
        min_y, max_y = 0, field_length
    
    # Add operational design colored subplots overlay if enabled
    # =============================================================================
    # USE SAVED DATA FROM OPERATIONAL DESIGN - DO NOT REGENERATE
    # This ensures subplot numbers and day assignments match exactly
    # =============================================================================
    if drawing.get('show_operational_overlay', True) and operational_data and local_polygon:
        try:
            # Day colors (same as operational_design.py)
            day_colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', 
                         '#F7DC6F', '#BB8FCE', '#85C1E2', '#F8B88B', '#A9DFBF']
            
            # Get saved data from operational design - THIS IS THE SOURCE OF TRUTH
            subplot_polygons = operational_data.get('subplot_polygons', {})
            subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
            subplot_centers = operational_data.get('subplot_centers', {})
            actual_total_days = int(operational_data.get('actual_total_days', 5))
            
            # Check if we have saved subplot data from operational design
            if subplot_polygons and len(subplot_polygons) > 0:
                # =============================================================================
                # USE SAVED SUBPLOT DATA DIRECTLY - NO REGENERATION NEEDED
                # This ensures numbering and day assignments match operational design exactly
                # =============================================================================
                
                day_legend_added = set()
                subplot_positions = {}
                
                # Iterate through saved subplots in order (keys are 1-indexed subplot numbers)
                for subplot_num in sorted(subplot_polygons.keys()):
                    polygon_coords = subplot_polygons[subplot_num]
                    
                    # Get polygon coordinates
                    x_coords = [c[0] for c in polygon_coords]
                    y_coords = [c[1] for c in polygon_coords]
                    # Close the polygon
                    x_coords.append(x_coords[0])
                    y_coords.append(y_coords[0])
                    
                    # Calculate center
                    center_x = sum(x_coords[:-1]) / len(x_coords[:-1]) if len(x_coords) > 1 else 0
                    center_y = sum(y_coords[:-1]) / len(y_coords[:-1]) if len(y_coords) > 1 else 0
                    
                    # Use saved center if available
                    if subplot_centers and subplot_num in subplot_centers:
                        center_x, center_y = subplot_centers[subplot_num]
                    
                    # Store position for valve placement
                    subplot_positions[subplot_num] = (center_x, center_y)
                    
                    # Get day assignment from saved data
                    day_num = subplot_day_assignments.get(subplot_num, 1)
                    if day_num > actual_total_days:
                        day_num = actual_total_days
                    
                    color_idx = (day_num - 1) % len(day_colors)
                    color = day_colors[color_idx]
                    
                    show_in_legend = day_num not in day_legend_added
                    if show_in_legend:
                        day_legend_added.add(day_num)
                    
                    # Draw colored subplot
                    fig.add_trace(go.Scatter(
                        x=x_coords,
                        y=y_coords,
                        fill='toself',
                        fillcolor=color,
                        opacity=0.3,
                        line=dict(color=color, width=0.5),
                        name=f'Day {day_num}',
                        showlegend=show_in_legend,
                        hovertemplate=f'<b>Subplot {subplot_num}</b><br>Irrigation Day {day_num}<extra></extra>'
                    ))
                    
                    # Add subplot number label
                    fig.add_trace(go.Scatter(
                        x=[center_x],
                        y=[center_y],
                        mode='text',
                        text=f'<b>{subplot_num}</b>',
                        textfont=dict(size=12, color='black', family='Arial Black, Arial, sans-serif'),
                        showlegend=False,
                        hoverinfo='skip'
                    ))
                
                # Save subplot positions to session state for valve placement
                if 'subplot_positions' not in st.session_state:
                    st.session_state.subplot_positions = {}
                st.session_state.subplot_positions = subplot_positions
        
        except Exception as e:
            pass  # Silently fail if overlay cannot be generated
    
    # Add subplot division lines from operational design
    op_data = st.session_state.project_data.get('operational_data', {})
    total_subplots = op_data.get('total_subplots', 0)
    n_rows_saved = op_data.get('n_rows', 0)
    n_cols_saved = op_data.get('n_cols', 0)
    
    # Draw subdivision grid if we have subplots and polygon data
    if local_polygon and total_subplots > 1 and n_rows_saved > 0 and n_cols_saved > 0:
        try:
            from shapely.geometry import Polygon, LineString, MultiPoint
            
            # Use the saved n_rows and n_cols from operational design
            n_rows = n_rows_saved
            n_cols = n_cols_saved
            
            # Create polygon
            poly = Polygon(local_polygon)
            
            # Detect if this is a regular quadrilateral (4 well-defined corners)
            corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
            is_regular_quad = len(corners) == 4
            
            if is_regular_quad:
                # REGULAR QUADRILATERAL: Use edge-parallel interpolation
                corners_sorted = sorted(corners, key=lambda p: (p[1], p[0]))
                
                bottom_points = corners_sorted[:2]
                bottom_left = min(bottom_points, key=lambda p: p[0])
                bottom_right = max(bottom_points, key=lambda p: p[0])
                
                top_points = corners_sorted[2:4]
                top_left = min(top_points, key=lambda p: p[0])
                top_right = max(top_points, key=lambda p: p[0])
                
                left_edge = (bottom_left, top_left)
                right_edge = (bottom_right, top_right)
                bottom_edge = (bottom_left, bottom_right)
                top_edge = (top_left, top_right)
                
                # Horizontal lines (gold)
                for i in range(1, n_rows):
                    fraction = i / n_rows
                    left_point = (
                        left_edge[0][0] + fraction * (left_edge[1][0] - left_edge[0][0]),
                        left_edge[0][1] + fraction * (left_edge[1][1] - left_edge[0][1])
                    )
                    right_point = (
                        right_edge[0][0] + fraction * (right_edge[1][0] - right_edge[0][0]),
                        right_edge[0][1] + fraction * (right_edge[1][1] - right_edge[0][1])
                    )
                    
                    test_line = LineString([left_point, right_point])
                    intersection = test_line.intersection(poly)
                    
                    if not intersection.is_empty:
                        if intersection.geom_type == 'LineString':
                            coords = list(intersection.coords)
                            fig.add_trace(go.Scatter(
                                x=[c[0] for c in coords],
                                y=[c[1] for c in coords],
                                mode='lines',
                                line=dict(color='black', width=1.5, dash='dash'),
                                name='Length Divisions' if i == 1 else None,
                                showlegend=(i == 1),
                                hoverinfo='skip',
                                opacity=0.8
                            ))
                        elif intersection.geom_type == 'MultiLineString':
                            for line in intersection.geoms:
                                coords = list(line.coords)
                                fig.add_trace(go.Scatter(
                                    x=[c[0] for c in coords],
                                    y=[c[1] for c in coords],
                                    mode='lines',
                                    line=dict(color='black', width=1.5, dash='dash'),
                                    name='Length Divisions' if i == 1 else None,
                                    showlegend=(i == 1),
                                    hoverinfo='skip',
                                    opacity=0.8
                                ))
                
                # Vertical lines (red)
                for i in range(1, n_cols):
                    fraction = i / n_cols
                    bottom_point = (
                        bottom_edge[0][0] + fraction * (bottom_edge[1][0] - bottom_edge[0][0]),
                        bottom_edge[0][1] + fraction * (bottom_edge[1][1] - bottom_edge[0][1])
                    )
                    top_point = (
                        top_edge[0][0] + fraction * (top_edge[1][0] - top_edge[0][0]),
                        top_edge[0][1] + fraction * (top_edge[1][1] - top_edge[0][1])
                    )
                    
                    test_line = LineString([bottom_point, top_point])
                    intersection = test_line.intersection(poly)
                    
                    if not intersection.is_empty:
                        if intersection.geom_type == 'LineString':
                            coords = list(intersection.coords)
                            fig.add_trace(go.Scatter(
                                x=[c[0] for c in coords],
                                y=[c[1] for c in coords],
                                mode='lines',
                                line=dict(color='black', width=1.5, dash='dash'),
                                name='Subplot Divisions' if i == 1 else None,
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
                        elif intersection.geom_type == 'MultiLineString':
                            for line in intersection.geoms:
                                coords = list(line.coords)
                                fig.add_trace(go.Scatter(
                                    x=[c[0] for c in coords],
                                    y=[c[1] for c in coords],
                                    mode='lines',
                                    line=dict(color='black', width=1.5, dash='dash'),
                                    name='Subplot Divisions' if i == 1 else None,
                                    showlegend=False,
                                    hoverinfo='skip',
                                    opacity=0.8
                                ))
            else:
                # IRREGULAR POLYGON: Use bounding box method
                minx, miny, maxx, maxy = poly.bounds
                
                # Horizontal lines (black dashed)
                for i in range(1, n_rows):
                    y_pos = miny + (i * (maxy - miny) / n_rows)
                    test_line = LineString([(minx - 100, y_pos), (maxx + 100, y_pos)])
                    intersection = test_line.intersection(poly)
                    
                    if not intersection.is_empty:
                        if intersection.geom_type == 'LineString':
                            coords = list(intersection.coords)
                            fig.add_trace(go.Scatter(
                                x=[c[0] for c in coords],
                                y=[c[1] for c in coords],
                                mode='lines',
                                line=dict(color='black', width=1.5, dash='dash'),
                                name='Subplot Divisions' if i == 1 else None,
                                showlegend=(i == 1),
                                hoverinfo='skip',
                                opacity=0.8
                            ))
                        elif intersection.geom_type == 'MultiLineString':
                            for line in intersection.geoms:
                                coords = list(line.coords)
                                fig.add_trace(go.Scatter(
                                    x=[c[0] for c in coords],
                                    y=[c[1] for c in coords],
                                    mode='lines',
                                    line=dict(color='black', width=1.5, dash='dash'),
                                    name='Subplot Divisions' if i == 1 else None,
                                    showlegend=(i == 1),
                                    hoverinfo='skip',
                                    opacity=0.8
                                ))
                
                # Vertical lines (red)
                for i in range(1, n_cols):
                    x_pos = minx + (i * (maxx - minx) / n_cols)
                    test_line = LineString([(x_pos, miny - 100), (x_pos, maxy + 100)])
                    intersection = test_line.intersection(poly)
                    
                    if not intersection.is_empty:
                        if intersection.geom_type == 'LineString':
                            coords = list(intersection.coords)
                            fig.add_trace(go.Scatter(
                                x=[c[0] for c in coords],
                                y=[c[1] for c in coords],
                                mode='lines',
                                line=dict(color='black', width=1.5, dash='dash'),
                                name='Subplot Divisions' if i == 1 else None,
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
                        elif intersection.geom_type == 'MultiLineString':
                            for line in intersection.geoms:
                                coords = list(line.coords)
                                fig.add_trace(go.Scatter(
                                    x=[c[0] for c in coords],
                                    y=[c[1] for c in coords],
                                    mode='lines',
                                    line=dict(color='black', width=1.5, dash='dash'),
                                    name='Subplot Divisions' if i == 1 else None,
                                    showlegend=False,
                                    hoverinfo='skip',
                                    opacity=0.8
                                ))
        except Exception as e:
            # Silently ignore errors in subdivision drawing
            pass
    
    # AUTO-GENERATE SPRINKLER LINES FOR FARTHEST SUBPLOT (or entire field if only 1 subplot)
    # Get sprinkler configuration from operational design
    
    if local_polygon and total_subplots >= 1 and water_source_local:
        try:
            from shapely.geometry import Polygon, LineString, MultiPoint, Point
            import math
            
            # Get sprinkler configuration from saved operational data
            n_lines = op_data.get('n_lines_per_subplot', 0)
            n_sprinklers = op_data.get('n_sprinklers_per_line', 0)
            spacing_along = op_data.get('spacing_along', 0)
            spacing_between = op_data.get('spacing_between', 0)
            
            # If not available, calculate from field dimensions
            if n_lines == 0 or n_sprinklers == 0:
                field_length_calc = field_geometry.get('length_m', 850)
                field_width_calc = field_geometry.get('width_m', 688)
                subplot_length = field_length_calc / n_rows_saved
                subplot_width = field_width_calc / n_cols_saved
                
                # Use default sprinkler spacing
                if spacing_along == 0:
                    spacing_along = 15  # Default 15m
                if spacing_between == 0:
                    spacing_between = 15  # Default 15m
                
                n_sprinklers = max(1, int(subplot_length / spacing_along))
                n_lines = max(1, int(subplot_width / spacing_between))
            
            poly = Polygon(local_polygon)
            
            # Detect if regular quadrilateral
            corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
            is_regular_quad = len(corners) == 4
            
            if is_regular_quad:
                # REGULAR QUADRILATERAL: Use edge-parallel sprinkler lines (EXACT COPY from operational_design.py)
                # Sprinkler lines run parallel to LENGTH (from bottom edge to top edge)
                
                # Sort corners: bottom-left, bottom-right, top-left, top-right
                corners_sorted = sorted(corners, key=lambda p: (p[1], p[0]))
                
                # Bottom two points (lower y values)
                bottom_points = corners_sorted[:2]
                bottom_left = min(bottom_points, key=lambda p: p[0])
                bottom_right = max(bottom_points, key=lambda p: p[0])
                
                # Top two points (higher y values)
                top_points = corners_sorted[2:4]
                top_left = min(top_points, key=lambda p: p[0])
                top_right = max(top_points, key=lambda p: p[0])
                
                # Define field edges for interpolation
                left_edge = (bottom_left, top_left)
                right_edge = (bottom_right, top_right)
                bottom_edge = (bottom_left, bottom_right)
                top_edge = (top_left, top_right)
                
                # Find farthest subplot from water source
                max_distance = 0
                farthest_subplot = (0, 0)
                
                for row in range(n_rows_saved):
                    for col in range(n_cols_saved):
                        # Calculate subplot center
                        row_frac = (row + 0.5) / n_rows_saved
                        col_frac = (col + 0.5) / n_cols_saved
                        
                        # Interpolate center point
                        left_center = (
                            left_edge[0][0] + row_frac * (left_edge[1][0] - left_edge[0][0]),
                            left_edge[0][1] + row_frac * (left_edge[1][1] - left_edge[0][1])
                        )
                        right_center = (
                            right_edge[0][0] + row_frac * (right_edge[1][0] - right_edge[0][0]),
                            right_edge[0][1] + row_frac * (right_edge[1][1] - right_edge[0][1])
                        )
                        center = (
                            left_center[0] + col_frac * (right_center[0] - left_center[0]),
                            left_center[1] + col_frac * (right_center[1] - left_center[1])
                        )
                        
                        # Check if subplot center is inside field polygon
                        from shapely.geometry import Point
                        subplot_center_point = Point(center[0], center[1])
                        if not poly.contains(subplot_center_point):
                            continue  # Skip subplots outside the field
                        
                        # Calculate distance from water source
                        distance = math.sqrt((center[0] - water_source_local[0])**2 + 
                                           (center[1] - water_source_local[1])**2)
                        
                        if distance > max_distance:
                            max_distance = distance
                            farthest_subplot = (row, col)
                
                # Generate sprinkler lines for farthest subplot ONLY
                row, col = farthest_subplot
                row_frac_bottom = row / n_rows_saved
                row_frac_top = (row + 1) / n_rows_saved
                col_frac_left = col / n_cols_saved
                col_frac_right = (col + 1) / n_cols_saved
                
                # Calculate this subplot's four corners by interpolating on the field edges
                # Bottom-left corner of subplot
                subplot_bl_left = (
                    left_edge[0][0] + row_frac_bottom * (left_edge[1][0] - left_edge[0][0]),
                    left_edge[0][1] + row_frac_bottom * (left_edge[1][1] - left_edge[0][1])
                )
                subplot_bl_right = (
                    right_edge[0][0] + row_frac_bottom * (right_edge[1][0] - right_edge[0][0]),
                    right_edge[0][1] + row_frac_bottom * (right_edge[1][1] - right_edge[0][1])
                )
                subplot_bl = (
                    subplot_bl_left[0] + col_frac_left * (subplot_bl_right[0] - subplot_bl_left[0]),
                    subplot_bl_left[1] + col_frac_left * (subplot_bl_right[1] - subplot_bl_left[1])
                )
                
                # Top-left corner of subplot
                subplot_tl_left = (
                    left_edge[0][0] + row_frac_top * (left_edge[1][0] - left_edge[0][0]),
                    left_edge[0][1] + row_frac_top * (left_edge[1][1] - left_edge[0][1])
                )
                subplot_tl_right = (
                    right_edge[0][0] + row_frac_top * (right_edge[1][0] - right_edge[0][0]),
                    right_edge[0][1] + row_frac_top * (right_edge[1][1] - right_edge[0][1])
                )
                subplot_tl = (
                    subplot_tl_left[0] + col_frac_left * (subplot_tl_right[0] - subplot_tl_left[0]),
                    subplot_tl_left[1] + col_frac_left * (subplot_tl_right[1] - subplot_tl_left[1])
                )
                
                # Bottom-right corner of subplot
                subplot_br = (
                    subplot_bl_left[0] + col_frac_right * (subplot_bl_right[0] - subplot_bl_left[0]),
                    subplot_bl_left[1] + col_frac_right * (subplot_bl_right[1] - subplot_bl_left[1])
                )
                
                # Top-right corner of subplot
                subplot_tr = (
                    subplot_tl_left[0] + col_frac_right * (subplot_tl_right[0] - subplot_tl_left[0]),
                    subplot_tl_left[1] + col_frac_right * (subplot_tl_right[1] - subplot_tl_left[1])
                )
                
                # Create subplot polygon to clip sprinklers
                subplot_poly = Polygon([subplot_bl, subplot_br, subplot_tr, subplot_tl])
                
                # For each sprinkler line within this subplot
                # Sprinkler lines run from bottom edge to top edge of THIS subplot
                for line_idx in range(n_lines):
                    # Position of this line within the subplot WIDTH (as a fraction from 0 to 1)
                    line_fraction_in_subplot = (line_idx + 0.5) / n_lines
                    
                    # Interpolate along bottom and top edges of THIS SUBPLOT
                    line_start = (
                        subplot_bl[0] + line_fraction_in_subplot * (subplot_br[0] - subplot_bl[0]),
                        subplot_bl[1] + line_fraction_in_subplot * (subplot_br[1] - subplot_bl[1])
                    )
                    line_end = (
                        subplot_tl[0] + line_fraction_in_subplot * (subplot_tr[0] - subplot_tl[0]),
                        subplot_tl[1] + line_fraction_in_subplot * (subplot_tr[1] - subplot_tl[1])
                    )
                    
                    # Create line and intersect with field polygon
                    test_line = LineString([line_start, line_end])
                    intersection = test_line.intersection(poly)
                    
                    if intersection.is_empty:
                        continue
                    
                    # Handle different intersection types
                    line_segments = []
                    if intersection.geom_type == 'LineString':
                        line_segments = [intersection]
                    elif intersection.geom_type == 'MultiLineString':
                        line_segments = list(intersection.geoms)
                    else:
                        continue
                    
                    # Draw line segments and place sprinklers
                    for segment in line_segments:
                        coords = list(segment.coords)
                        
                        # Draw the line
                        fig.add_trace(go.Scatter(
                            x=[coords[0][0], coords[-1][0]],
                            y=[coords[0][1], coords[-1][1]],
                            mode='lines',
                            line=dict(color='blue', width=1.5),
                            name='Sprinkler Line',
                            showlegend=(line_idx == 0),
                            legendgroup='auto_sprinklers',
                            hoverinfo='skip'
                        ))
                        
                        # Place sprinklers along this line segment
                        segment_length = segment.length
                        
                        sprinkler_x_list = []
                        sprinkler_y_list = []
                        
                        # Calculate number of sprinklers based on ACTUAL segment length
                        # Use ceiling to match operational design calculation
                        import math
                        if segment_length >= spacing_along * 0.5:
                            actual_n_sprinklers = max(1, math.ceil(segment_length / spacing_along))
                        else:
                            actual_n_sprinklers = 0
                        
                        # Place sprinklers at regular spacing intervals
                        for spr_idx in range(actual_n_sprinklers):
                            # Start at half spacing from start, then every spacing_along meters
                            distance_along = (spr_idx + 0.5) * spacing_along
                            
                            if distance_along > segment_length:
                                break
                            
                            # Calculate position as fraction along the line
                            t = distance_along / segment_length
                            
                            # Interpolate point along the line segment
                            sprinkler_x = coords[0][0] + t * (coords[-1][0] - coords[0][0])
                            sprinkler_y = coords[0][1] + t * (coords[-1][1] - coords[0][1])
                            
                            # Add sprinkler (line is already inside subplot and field, so all points are valid)
                            sprinkler_x_list.append(sprinkler_x)
                            sprinkler_y_list.append(sprinkler_y)
                        
                        if sprinkler_x_list:
                            fig.add_trace(go.Scatter(
                                x=sprinkler_x_list,
                                y=sprinkler_y_list,
                                mode='markers',
                                marker=dict(size=5, color='green', symbol='circle'),
                                name='Sprinkler',
                                showlegend=(line_idx == 0),
                                legendgroup='auto_sprinklers',
                                hovertemplate='Sprinkler<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
                            ))
                        else:
                            # Debug: log when no sprinklers are placed
                            log_warning(f"No sprinklers placed on line {line_idx}, segment length: {segment.length:.1f}m")
                
                # Highlight farthest subplot boundary
                fig.add_trace(go.Scatter(
                    x=[subplot_bl[0], subplot_br[0], subplot_tr[0], subplot_tl[0], subplot_bl[0]],
                    y=[subplot_bl[1], subplot_br[1], subplot_tr[1], subplot_tl[1], subplot_bl[1]],
                    mode='lines',
                    line=dict(color='red', width=2, dash='dot'),
                    name='Farthest Subplot',
                    showlegend=True,
                    hoverinfo='skip'
                ))
            
            else:
                # IRREGULAR POLYGON: Use VERTICAL bounding box approach (EXACT from operational_design.py)
                # But only for the farthest subplot
                coords = list(poly.exterior.coords)[:-1]
                
                if len(coords) >= 4:
                    # Get bounding box
                    bounds = poly.bounds
                    min_x_field, min_y_field = bounds[0], bounds[1]
                    max_x_field, max_y_field = bounds[2], bounds[3]
                    
                    # Find farthest subplot from water source (using bounding box grid)
                    max_distance = 0
                    farthest_subplot = (0, 0)
                    
                    for row in range(n_rows_saved):
                        for col in range(n_cols_saved):
                            # Calculate subplot center
                            subplot_min_x = min_x_field + col * (max_x_field - min_x_field) / n_cols_saved
                            subplot_max_x = min_x_field + (col + 1) * (max_x_field - min_x_field) / n_cols_saved
                            subplot_min_y = min_y_field + row * (max_y_field - min_y_field) / n_rows_saved
                            subplot_max_y = min_y_field + (row + 1) * (max_y_field - min_y_field) / n_rows_saved
                            
                            subplot_center_x = (subplot_min_x + subplot_max_x) / 2
                            subplot_center_y = (subplot_min_y + subplot_max_y) / 2
                            
                            # Check if subplot center is inside field polygon
                            from shapely.geometry import Point
                            subplot_center_point = Point(subplot_center_x, subplot_center_y)
                            if not poly.contains(subplot_center_point):
                                continue  # Skip subplots outside the field
                            
                            # Calculate distance from water source
                            distance = math.sqrt((subplot_center_x - water_source_local[0])**2 + 
                                               (subplot_center_y - water_source_local[1])**2)
                            
                            if distance > max_distance:
                                max_distance = distance
                                farthest_subplot = (row, col)
                    
                    # Generate VERTICAL sprinkler lines for farthest subplot ONLY
                    row, col = farthest_subplot
                    
                    # Calculate this subplot's bounding box
                    subplot_min_x = min_x_field + col * (max_x_field - min_x_field) / n_cols_saved
                    subplot_max_x = min_x_field + (col + 1) * (max_x_field - min_x_field) / n_cols_saved
                    subplot_min_y = min_y_field + row * (max_y_field - min_y_field) / n_rows_saved
                    subplot_max_y = min_y_field + (row + 1) * (max_y_field - min_y_field) / n_rows_saved
                    
                    subplot_actual_width = subplot_max_x - subplot_min_x
                    
                    # For each VERTICAL sprinkler line within this subplot
                    for line_idx in range(n_lines):
                        # Position of this vertical line within the subplot
                        # Lines are evenly distributed across the subplot width
                        line_x = subplot_min_x + (line_idx + 0.5) * (subplot_actual_width / n_lines)
                        
                        if line_x > subplot_max_x:
                            continue
                        
                        # Create a vertical line from subplot bottom to top
                        test_line = LineString([(line_x, subplot_min_y - 10), (line_x, subplot_max_y + 10)])
                        
                        # Intersect with field boundary to get only the parts inside
                        intersection = test_line.intersection(poly)
                        
                        if intersection.is_empty:
                            continue
                        
                        # Handle different intersection types
                        line_segments = []
                        if intersection.geom_type == 'LineString':
                            line_segments = [intersection]
                        elif intersection.geom_type == 'MultiLineString':
                            line_segments = list(intersection.geoms)
                        else:
                            continue
                        
                        # Draw line segments and place sprinklers
                        for segment in line_segments:
                            coords = list(segment.coords)
                            
                            # Draw the vertical line segment
                            fig.add_trace(go.Scatter(
                                x=[coords[0][0], coords[-1][0]],
                                y=[coords[0][1], coords[-1][1]],
                                mode='lines',
                                line=dict(color='blue', width=1.5),
                                name='Sprinkler Line',
                                showlegend=(line_idx == 0),
                                legendgroup='auto_sprinklers',
                                hoverinfo='skip'
                            ))
                            
                            # Place sprinklers along this line segment
                            segment_length = segment.length
                            
                            sprinkler_x_list = []
                            sprinkler_y_list = []
                            
                            # Calculate number of sprinklers based on ACTUAL segment length
                            # Use ceiling to match operational design calculation
                            import math
                            if segment_length >= spacing_along * 0.5:
                                actual_n_sprinklers = max(1, math.ceil(segment_length / spacing_along))
                            else:
                                actual_n_sprinklers = 0
                            
                            # Place sprinklers at regular spacing intervals
                            for spr_idx in range(actual_n_sprinklers):
                                # Start at half spacing from start, then every spacing_along meters
                                distance_along = (spr_idx + 0.5) * spacing_along
                                
                                if distance_along > segment_length:
                                    break
                                
                                # Calculate position as fraction along the line
                                t = distance_along / segment_length
                                
                                # Calculate sprinkler position
                                sprinkler_x = coords[0][0] + t * (coords[-1][0] - coords[0][0])
                                sprinkler_y = coords[0][1] + t * (coords[-1][1] - coords[0][1])
                                
                                # Add sprinkler (line is already inside field, so all points are valid)
                                sprinkler_x_list.append(sprinkler_x)
                                sprinkler_y_list.append(sprinkler_y)
                            
                            if sprinkler_x_list:
                                fig.add_trace(go.Scatter(
                                    x=sprinkler_x_list,
                                    y=sprinkler_y_list,
                                    mode='markers',
                                    marker=dict(size=5, color='green', symbol='circle'),
                                    name='Sprinkler',
                                    showlegend=(line_idx == 0),
                                    legendgroup='auto_sprinklers',
                                    hovertemplate='Sprinkler<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
                                ))
                            else:
                                # Debug: log when no sprinklers are placed
                                log_warning(f"No sprinklers placed on line {line_idx}, segment length: {segment.length:.1f}m")
                    
                    # Highlight farthest subplot boundary (rectangle)
                    fig.add_trace(go.Scatter(
                        x=[subplot_min_x, subplot_max_x, subplot_max_x, subplot_min_x, subplot_min_x],
                        y=[subplot_min_y, subplot_min_y, subplot_max_y, subplot_max_y, subplot_min_y],
                        mode='lines',
                        line=dict(color='red', width=2, dash='dot'),
                        name='Farthest Subplot',
                        showlegend=True,
                        hoverinfo='skip'
                    ))
                else:
                    st.warning("⚠️ Could not generate sprinklers: Insufficient polygon points")
                
        except Exception as e:
            st.error(f"❌ Error generating sprinklers: {str(e)}")
            import traceback
            st.code(traceback.format_exc())
    else:
        if not local_polygon:
            st.warning("⚠️ Cannot auto-generate sprinklers: Field polygon not available")
        elif not water_source_local:
            st.warning("⚠️ Cannot auto-generate sprinklers: Water source not placed yet")
    
    # Add visible fine grid lines for drawing guidance (lighter and finer than division lines)
    # Create finer grid (every 50m or field_dimension/40, whichever is smaller)
    fine_grid_spacing_x = min(50, (max_x - min_x) / 40)
    fine_grid_spacing_y = min(50, (max_y - min_y) / 40)
    
    # Vertical grid lines
    x_grid = min_x
    while x_grid <= max_x:
        fig.add_trace(go.Scatter(
            x=[x_grid, x_grid],
            y=[min_y, max_y],
            mode='lines',
            line=dict(color='lightgray', width=0.3, dash='dot'),
            showlegend=False,
            hoverinfo='skip'
        ))
        x_grid += fine_grid_spacing_x
    
    # Horizontal grid lines
    y_grid = min_y
    while y_grid <= max_y:
        fig.add_trace(go.Scatter(
            x=[min_x, max_x],
            y=[y_grid, y_grid],
            mode='lines',
            line=dict(color='lightgray', width=0.5, dash='dot'),
            showlegend=False,
            hoverinfo='skip'
        ))
        y_grid += fine_grid_spacing_y
    
    # Draw subdivision lines
    if num_main_fields > 1:
        field_height = field_length / num_main_fields
        for i in range(1, num_main_fields):
            y_pos = i * field_height
            fig.add_trace(go.Scatter(
                x=[0, field_width],
                y=[y_pos, y_pos],
                mode='lines',
                line=dict(color='gray', width=1, dash='dot'),
                name=f'Subdivision {i}',
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Draw intersection points with special markers (AutoCAD-style)
    intersections = find_line_intersections(network)
    if intersections:
        int_x = [pt[0] for pt in intersections]
        int_y = [pt[1] for pt in intersections]
        fig.add_trace(go.Scatter(
            x=int_x,
            y=int_y,
            mode='markers',
            marker=dict(
                size=12,
                color='red',
                symbol='x',
                line=dict(width=2, color='darkred')
            ),
            name='Intersections',
            hovertemplate='Intersection<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>',
            showlegend=True
        ))
    
    # Draw endpoint markers for all network lines
    all_endpoints = []
    for mainline in network.get('mainlines', []):
        if mainline:
            all_endpoints.extend([mainline[0], mainline[-1]])
    for submain in network.get('submains', []):
        if submain:
            all_endpoints.extend([submain[0], submain[-1]])
    for lateral in network.get('laterals', []):
        if lateral:
            all_endpoints.extend([lateral[0], lateral[-1]])
    
    if all_endpoints:
        ep_x = [pt[0] for pt in all_endpoints]
        ep_y = [pt[1] for pt in all_endpoints]
        fig.add_trace(go.Scatter(
            x=ep_x,
            y=ep_y,
            mode='markers',
            marker=dict(
                size=10,
                color='blue',
                symbol='square',
                line=dict(width=1, color='darkblue')
            ),
            name='Endpoints',
            hovertemplate='Endpoint<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>',
            showlegend=True,
            opacity=0.7
        ))
    
    # Highlight last snapped point with LARGE visual feedback (AutoCAD-style)
    if drawing.get('last_snap_point'):
        snap_x, snap_y = drawing['last_snap_point']
        snap_type = drawing.get('last_snap_type', 'none')
        
        # Color and symbol based on snap type
        if snap_type == 'intersection':
            snap_color = 'red'
            snap_symbol = 'x'
            snap_size = 25
            snap_label = '⨯ INTERSECTION'
        elif snap_type == 'endpoint':
            snap_color = 'blue'
            snap_symbol = 'square'
            snap_size = 22
            snap_label = '■ ENDPOINT'
        else:
            snap_color = 'yellow'
            snap_symbol = 'circle'
            snap_size = 18
            snap_label = 'Click'
        
        # Large, highly visible snap indicator
        fig.add_trace(go.Scatter(
            x=[snap_x],
            y=[snap_y],
            mode='markers+text',
            marker=dict(
                size=snap_size,
                color=snap_color,
                symbol=snap_symbol,
                line=dict(width=3, color='white'),
                opacity=0.9
            ),
            text=[snap_label],
            textposition='top center',
            textfont=dict(size=12, color=snap_color, family='Arial Black'),
            name=f'Snap: {snap_type}',
            hovertemplate=f'<b>{snap_type.upper()} SNAP</b><br>X: {snap_x:.1f}m<br>Y: {snap_y:.1f}m<extra></extra>',
            showlegend=False
        ))
    
    # Draw water source - use local coordinates if available
    if water_source_local:
        fig.add_trace(go.Scatter(
            x=[water_source_local[0]],
            y=[water_source_local[1]],
            mode='markers+text',
            marker=dict(size=20, color='#1E88E5', symbol='circle'),
            text=['💧'],
            textposition='middle center',
            textfont=dict(size=16),
            name='Water Source',
            hovertemplate='Water Source<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
        ))
    elif water_source:
        # Fallback to GPS coordinates (for backward compatibility)
        fig.add_trace(go.Scatter(
            x=[water_source[0]],
            y=[water_source[1]],
            mode='markers+text',
            marker=dict(size=20, color='#1E88E5', symbol='circle'),
            text=['💧'],
            textposition='middle center',
            textfont=dict(size=16),
            name='Water Source',
            hovertemplate='Water Source<br>Lat: %{y:.6f}<br>Lon: %{x:.6f}<extra></extra>'
        ))
    
    # Draw existing mainlines (Red)
    selected_line = st.session_state.selected_line
    for i, line in enumerate(network.get('mainlines', [])):
        if len(line) >= 2:
            xs = [p[0] for p in line]
            ys = [p[1] for p in line]
            
            # Check if this line is selected
            is_selected = (selected_line.get('type') == 'mainlines' and selected_line.get('index') == i)
            
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode='lines+markers',
                line=dict(
                    color='#FFD700' if is_selected else '#d32f2f',  # Gold if selected
                    width=6 if is_selected else 4
                ),
                marker=dict(size=10 if is_selected else 8, color='#FFD700' if is_selected else '#d32f2f'),
                name=f'Mainline {i+1}' + (' [SELECTED]' if is_selected else ''),
                hovertemplate='Mainline<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
            ))
    
    # Draw existing submains (Orange)
    for i, line in enumerate(network.get('submains', [])):
        if len(line) >= 2:
            xs = [p[0] for p in line]
            ys = [p[1] for p in line]
            
            # Check if this line is selected
            is_selected = (selected_line.get('type') == 'submains' and selected_line.get('index') == i)
            
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode='lines+markers',
                line=dict(
                    color='#FFD700' if is_selected else '#ff9800',  # Gold if selected
                    width=5 if is_selected else 3
                ),
                marker=dict(size=9 if is_selected else 7, color='#FFD700' if is_selected else '#ff9800'),
                name=f'Submain {i+1}' + (' [SELECTED]' if is_selected else ''),
                hovertemplate='Submain<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
            ))
    
    # Draw existing laterals (Green)
    for i, line in enumerate(network.get('laterals', [])):
        if len(line) >= 2:
            xs = [p[0] for p in line]
            ys = [p[1] for p in line]
            
            # Check if this line is selected
            is_selected = (selected_line.get('type') == 'laterals' and selected_line.get('index') == i)
            
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode='lines+markers',
                line=dict(
                    color='#FFD700' if is_selected else '#4caf50',  # Gold if selected
                    width=4 if is_selected else 2
                ),
                marker=dict(size=8 if is_selected else 6, color='#FFD700' if is_selected else '#4caf50'),
                name=f'Lateral {i+1}' + (' [SELECTED]' if is_selected else ''),
                hovertemplate='Lateral<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
            ))
    
    # Draw existing sprinklers (Blue)
    if network.get('sprinklers'):
        xs = [p[0] for p in network['sprinklers']]
        ys = [p[1] for p in network['sprinklers']]
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode='markers',
            marker=dict(size=10, color='#2196f3', symbol='circle'),
            name='Sprinklers',
            hovertemplate='Sprinkler<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
        ))
    
    # Draw valves with coverage visualization
    if network.get('valves'):
        # Calculate field rotation angle to align valve orientations with subplot grid
        field_rotation_angle = 0  # Default: no rotation
        if local_polygon and len(local_polygon) >= 4:
            try:
                from shapely.geometry import Polygon
                poly = Polygon(local_polygon)
                corners = list(poly.convex_hull.exterior.coords)[:-1]
                
                if len(corners) == 4:
                    # Find the longest edge - this typically represents the subplot row direction
                    max_length = 0
                    best_edge = None
                    for j in range(4):
                        p1 = corners[j]
                        p2 = corners[(j + 1) % 4]
                        edge_length = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                        if edge_length > max_length:
                            max_length = edge_length
                            best_edge = (p1, p2)
                    
                    if best_edge:
                        dx = best_edge[1][0] - best_edge[0][0]
                        dy = best_edge[1][1] - best_edge[0][1]
                        # Calculate angle in degrees
                        field_rotation_angle = np.degrees(np.arctan2(dy, dx))
            except:
                field_rotation_angle = 0
        
        # =========================================================================
        # SMART VALVE OFFSET: Pre-calculate offsets for overlapping valves
        # Groups nearby valves and spreads them out for visibility
        # =========================================================================
        valve_display_offsets = {}  # {valve_index: (offset_x, offset_y)}
        overlap_threshold = 10  # meters - valves within this distance get offset
        offset_distance = 12  # meters - how far to spread overlapping valves
        
        # Find clusters of overlapping valves
        processed = set()
        for i, valve in enumerate(network['valves']):
            if i in processed:
                continue
            
            vx = valve.get('x', 0)
            vy = valve.get('y', 0)
            if isinstance(vx, dict): vx = 0
            if isinstance(vy, dict): vy = 0
            
            # Find all valves close to this one (including itself)
            cluster = [i]
            cluster_coords = [(vx, vy)]
            
            for j, other_valve in enumerate(network['valves']):
                if j != i and j not in processed:
                    ox = other_valve.get('x', 0)
                    oy = other_valve.get('y', 0)
                    if isinstance(ox, dict): ox = 0
                    if isinstance(oy, dict): oy = 0
                    
                    distance = np.sqrt((vx - ox)**2 + (vy - oy)**2)
                    if distance < overlap_threshold:
                        cluster.append(j)
                        cluster_coords.append((ox, oy))
            
            # If cluster has more than 1 valve, apply offsets
            if len(cluster) > 1:
                # Calculate centroid of cluster
                centroid_x = sum(c[0] for c in cluster_coords) / len(cluster_coords)
                centroid_y = sum(c[1] for c in cluster_coords) / len(cluster_coords)
                
                # Spread valves in a circle around the centroid
                for k, valve_idx in enumerate(cluster):
                    angle = (k * 360 / len(cluster)) + 45  # Start at 45° for better visibility
                    offset_x = offset_distance * np.cos(np.radians(angle))
                    offset_y = offset_distance * np.sin(np.radians(angle))
                    valve_display_offsets[valve_idx] = (offset_x, offset_y)
                    processed.add(valve_idx)
            else:
                # Single valve, no offset needed
                valve_display_offsets[i] = (0, 0)
                processed.add(i)
        
        # Now render each valve with its calculated offset
        # Get subplot day assignments for recalculating irrigation days
        subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
        
        for i, valve in enumerate(network['valves']):
            # Get valve coordinates with safety checks
            vx = valve.get('x', 0)
            vy = valve.get('y', 0)
            
            # Handle case where x or y might be stored as a dict
            if isinstance(vx, dict):
                vx = 0
            if isinstance(vy, dict):
                vy = 0
            
            # Get pre-calculated offset
            offset_x, offset_y = valve_display_offsets.get(i, (0, 0))
            
            # Check if this valve is part of an overlap cluster
            overlap_count = 1 if (offset_x != 0 or offset_y != 0) else 0
            
            # Apply offset to display position
            display_x = vx + offset_x
            display_y = vy + offset_y
            
            subplots_served = valve.get('subplots_served', 0)
            selected_subplots = valve.get('selected_subplots', [])
            subplot_id = valve.get('subplot_id', None)
            
            # RECALCULATE irrigation day from current subplot_day_assignments
            # This ensures it's always up-to-date, not stale from when valve was created
            irrigation_day = None
            irrigation_days_list = []
            
            if selected_subplots and subplot_day_assignments:
                for subplot in selected_subplots:
                    day = subplot_day_assignments.get(subplot)
                    if day is not None and day not in irrigation_days_list:
                        irrigation_days_list.append(day)
                
                if len(irrigation_days_list) == 1:
                    irrigation_day = irrigation_days_list[0]
                elif len(irrigation_days_list) > 1:
                    irrigation_day = f"Mixed: {irrigation_days_list}"
                else:
                    irrigation_day = valve.get('irrigation_day', None)  # Fallback to stored
            else:
                irrigation_day = valve.get('irrigation_day', None)  # Fallback to stored
            
            # Determine color and shape based on irrigation day (for overlapping) or number of subplots
            # Use same colors as subplot day colors for consistency
            day_colors_map = {
                1: '#FF6B6B',  # Red/Coral - Day 1 (matches subplot overlay)
                2: '#4ECDC4',  # Teal - Day 2
                3: '#45B7D1',  # Light Blue - Day 3
                4: '#FFA07A',  # Light Salmon - Day 4
                5: '#98D8C8',  # Mint - Day 5
                6: '#F7DC6F',  # Yellow - Day 6
                7: '#BB8FCE',  # Purple - Day 7
                8: '#85C1E2',  # Sky Blue - Day 8
                9: '#F8B88B',  # Peach - Day 9
                10: '#A9DFBF'  # Light Green - Day 10
            }
            
            if irrigation_day and isinstance(irrigation_day, int):
                # Use day color - same as the subplot overlay color
                valve_color = day_colors_map.get(irrigation_day, '#607D8B')  # Gray default
                valve_symbol = 'diamond' if overlap_count > 0 else 'circle'
            elif irrigation_days_list and len(irrigation_days_list) == 1:
                # Single day from recalculation
                valve_color = day_colors_map.get(irrigation_days_list[0], '#607D8B')
                valve_symbol = 'diamond' if overlap_count > 0 else 'circle'
                irrigation_day = irrigation_days_list[0]  # Update for display
            elif irrigation_days_list and len(irrigation_days_list) > 1:
                # Mixed days - use first day's color but indicate mixed
                valve_color = '#FFA500'  # Orange for mixed days
                valve_symbol = 'square'  # Square to indicate mixed
            else:
                # Fallback: Color by number of subplots if no day assigned
                valve_colors = {
                    1: '#2196F3',  # Blue - 1 subplot
                    2: '#3F51B5',  # Indigo - 2 subplots
                    3: '#673AB7',  # Deep purple - 3 subplots
                    4: '#9C27B0'   # Purple - 4 subplots
                }
                valve_color = valve_colors.get(subplots_served, '#9C27B0')
                valve_symbol = 'circle'
            
            # Build hover template with all selected subplots
            hover_text = f'<b>Valve {i+1}</b><br>'
            hover_text += f'Serves: {subplots_served} subplot(s)<br>'
            
            if selected_subplots:
                subplots_str = ', '.join(map(str, selected_subplots))
                hover_text += f'<b>Subplots: {subplots_str}</b><br>'
            
            # Show irrigation day info - with per-subplot breakdown if available
            if irrigation_days_list and len(irrigation_days_list) > 1:
                hover_text += f'<b>⚠️ Mixed Days: {irrigation_days_list}</b><br>'
                # Show each subplot with its day
                for sp in selected_subplots:
                    sp_day = subplot_day_assignments.get(sp, 'N/A')
                    hover_text += f'  Plot {sp}: Day {sp_day}<br>'
            elif irrigation_day and irrigation_day != 'Not assigned':
                hover_text += f'<b>Irrigation Day: {irrigation_day}</b><br>'
            else:
                hover_text += f'<b>Irrigation Day: N/A</b><br>'
            
            if overlap_count > 0:
                hover_text += f'<i>⚠️ {overlap_count} other valve(s) at same location</i><br>'
                hover_text += f'<i>Display offset applied for visibility</i><br>'
            
            hover_text += f'Actual Position: ({vx:.1f}, {vy:.1f})<extra></extra>'
            
            # Build legend name with valve number, day, subplot count, and subplot numbers
            if selected_subplots:
                subplots_str = ', '.join(map(str, selected_subplots))
                subplot_info = f'{subplots_served} subplot{"s" if subplots_served != 1 else ""}: {subplots_str}'
            else:
                subplot_info = f'{subplots_served} subplot{"s" if subplots_served != 1 else ""}'
            
            # Use recalculated day for legend
            if irrigation_days_list and len(irrigation_days_list) == 1:
                legend_name = f'Valve {i+1} - Day {irrigation_days_list[0]} ({subplot_info})'
            elif irrigation_days_list and len(irrigation_days_list) > 1:
                legend_name = f'Valve {i+1} - Mixed Days ({subplot_info})'
            elif irrigation_day and isinstance(irrigation_day, int):
                legend_name = f'Valve {i+1} - Day {irrigation_day} ({subplot_info})'
            else:
                legend_name = f'Valve {i+1} - Day N/A ({subplot_info})'
            
            # Main valve marker - show VALVE NUMBER on the map (not subplot count)
            fig.add_trace(go.Scatter(
                x=[display_x],
                y=[display_y],
                mode='markers+text',
                marker=dict(
                    size=22 if overlap_count > 0 else 20,
                    color=valve_color,
                    symbol=valve_symbol,
                    line=dict(width=3, color='white')
                ),
                text=[f'{i+1}'],  # Show valve number (1, 2, 3...) instead of subplot count
                textfont=dict(size=10, color='white', family='Arial Black'),
                textposition='middle center',
                name=legend_name,
                legendgroup='valves',
                showlegend=True,
                hovertemplate=hover_text
            ))
            
            # Add a dotted line connecting display position to actual position if offset applied
            if offset_x != 0 or offset_y != 0:
                fig.add_trace(go.Scatter(
                    x=[vx, display_x],
                    y=[vy, display_y],
                    mode='lines',
                    line=dict(color=valve_color, width=1, dash='dot'),
                    showlegend=False,
                    hoverinfo='skip'
                ))
    
    # Draw mainline valves (purple markers at mainline-submain intersections)
    mainline_valves = network.get('mainline_valves', [])
    for i, mv in enumerate(mainline_valves):
        mv_x = mv.get('x', 0)
        mv_y = mv.get('y', 0)
        
        # Get submain reference - try multiple formats for compatibility
        submain_ref = mv.get('submain_reference', None)
        if not submain_ref or submain_ref == 'Not assigned':
            # Try getting from submain_names list
            submain_names = mv.get('submain_names', [])
            if submain_names:
                submain_ref = ', '.join(submain_names)
            else:
                submain_ref = 'Not assigned'
        
        # Create hover text
        hover_text = f"<b>Mainline Valve {i+1}</b><br>"
        hover_text += f"Submain: {submain_ref}<br>"
        hover_text += f"Position: ({mv_x:.1f}, {mv_y:.1f})"
        
        # Purple diamond marker for mainline valves
        fig.add_trace(go.Scatter(
            x=[mv_x],
            y=[mv_y],
            mode='markers+text',
            marker=dict(
                size=24,
                color='#9c27b0',  # Purple
                symbol='diamond',
                line=dict(width=3, color='white')
            ),
            text=[f'M{i+1}'],  # Show M1, M2, M3... for mainline valves
            textfont=dict(size=9, color='white', family='Arial Black'),
            textposition='middle center',
            name=f'MainValve {i+1} → {submain_ref}',
            legendgroup='mainline_valves',
            showlegend=True,
            hovertemplate=hover_text
        ))
    
    # Draw current line being drawn with CAD-style enhancements
    if drawing['is_drawing'] and len(drawing['points']) > 0:
        xs = [p[0] for p in drawing['points']]
        ys = [p[1] for p in drawing['points']]
        
        # Color based on mode
        color_map = {
            'Mainline': '#d32f2f',
            'Submain': '#ff9800',
            'Lateral': '#4caf50',
            'Sprinkler': '#2196f3'
        }
        color = color_map.get(drawing['mode'], '#000000')
        
        if drawing['mode'] == 'Sprinkler':
            # Show as individual markers
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode='markers',
                marker=dict(size=15, color=color, symbol='circle', line=dict(width=3, color='white')),
                name='Preview',
                showlegend=False,
                hoverinfo='skip'
            ))
        else:
            # Show as dotted line with enhanced preview - LARGE VISIBLE MARKERS
            fig.add_trace(go.Scatter(
                x=xs, y=ys,
                mode='lines+markers',
                line=dict(color=color, width=4, dash='dot'),
                marker=dict(size=15, color=color, symbol='circle', line=dict(width=3, color='white')),
                name='Current Line (Preview)',
                showlegend=False,
                hovertext=[f'Point {i+1}: ({p[0]:.1f}, {p[1]:.1f})' for i, p in enumerate(drawing['points'])],
                hoverinfo='text'
            ))
            
            # Add alignment guides if enabled
            if drawing.get('show_alignment_guides', True) and len(drawing['points']) > 0:
                last_point = drawing['points'][-1]
                
                # Horizontal alignment guide
                fig.add_trace(go.Scatter(
                    x=[min_x, max_x],
                    y=[last_point[1], last_point[1]],
                    mode='lines',
                    line=dict(color='cyan', width=1, dash='dashdot'),
                    opacity=0.3,
                    name='H-Guide',
                    showlegend=False,
                    hoverinfo='skip'
                ))
                
                # Vertical alignment guide
                fig.add_trace(go.Scatter(
                    x=[last_point[0], last_point[0]],
                    y=[min_y, max_y],
                    mode='lines',
                    line=dict(color='cyan', width=1, dash='dashdot'),
                    opacity=0.3,
                    name='V-Guide',
                    showlegend=False,
                    hoverinfo='skip'
                ))
            
            # Add measurement annotations if enabled
            if drawing.get('show_measurements', True) and len(drawing['points']) >= 2:
                for i in range(len(drawing['points']) - 1):
                    p1 = drawing['points'][i]
                    p2 = drawing['points'][i + 1]
                    
                    # Calculate length and angle
                    length, angle = calculate_line_info(p1[0], p1[1], p2[0], p2[1])
                    
                    # Mid point for annotation
                    mid_x = (p1[0] + p2[0]) / 2
                    mid_y = (p1[1] + p2[1]) / 2
                    
                    # Create annotation text
                    annotation_text = f"L={length:.1f}m"
                    if abs(angle) > 0.1:  # Only show angle if not horizontal
                        annotation_text += f"<br>∠={angle:.0f}°"
                    
                    fig.add_annotation(
                        x=mid_x,
                        y=mid_y,
                        text=annotation_text,
                        showarrow=False,
                        bgcolor='rgba(255, 255, 255, 0.8)',
                        bordercolor=color,
                        borderwidth=1,
                        borderpad=4,
                        font=dict(size=10, color=color, family='Arial Black')
                    )
    
    # Draw completed measurement line if exists
    if 'measurement' in st.session_state and st.session_state.measurement:
        meas = st.session_state.measurement
        p1, p2 = meas['point1'], meas['point2']
        
        # Draw measurement line
        fig.add_trace(go.Scatter(
            x=[p1[0], p2[0]],
            y=[p1[1], p2[1]],
            mode='lines+markers',
            line=dict(color='magenta', width=3, dash='dash'),
            marker=dict(size=12, color='magenta', symbol='diamond', line=dict(width=2, color='white')),
            name='Measurement',
            showlegend=True,
            hovertext=f"Measurement: {meas['distance']:.2f} m",
            hoverinfo='text'
        ))
        
        # Add measurement annotation
        mid_x = (p1[0] + p2[0]) / 2
        mid_y = (p1[1] + p2[1]) / 2
        fig.add_annotation(
            x=mid_x,
            y=mid_y,
            text=f"📏 {meas['distance']:.2f} m",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor='magenta',
            ax=0,
            ay=-40,
            bgcolor='rgba(255, 0, 255, 0.9)',
            bordercolor='white',
            borderwidth=2,
            borderpad=6,
            font=dict(size=14, color='white', family='Arial Black')
        )
    
    # Layout with scroll zoom enabled
    snap_enabled = drawing.get('enable_snap', False)
    snap_size = drawing.get('snap_size', 25.0)
    
    # Calculate appropriate tick spacing based on field size
    field_range_x = max_x - min_x
    field_range_y = max_y - min_y
    tick_spacing_x = 50 if field_range_x < 500 else 100
    tick_spacing_y = 50 if field_range_y < 500 else 100
    
    fig.update_layout(
        xaxis=dict(
            title="Width (m)",
            range=[min_x - 20, max_x + 20],
            scaleanchor="y",
            scaleratio=1,
            constrain="domain",
            showgrid=snap_enabled,
            gridwidth=1,
            gridcolor='rgba(128, 128, 128, 0.3)',
            dtick=snap_size if snap_enabled else tick_spacing_x,
            tickmode='linear',
            tick0=0
        ),
        yaxis=dict(
            title="Length (m)",
            range=[min_y - 20, max_y + 20],
            constrain="domain",
            showgrid=snap_enabled,
            gridwidth=1,
            gridcolor='rgba(128, 128, 128, 0.3)',
            dtick=snap_size if snap_enabled else tick_spacing_y,
            tickmode='linear',
            tick0=0
        ),
        height=850,  # Taller for full-screen
        hovermode='closest',
        showlegend=True,
        legend=dict(x=1.02, y=1),
        plot_bgcolor='white',
        paper_bgcolor='white',
        margin=dict(l=60, r=150, t=40, b=60),
        clickmode='event+select',
        dragmode=False,  # CRITICAL: Disable drag modes to allow clicks
        modebar_add=['zoom2d', 'pan2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d']
    )
    
    # Enable scroll zoom
    fig.update_xaxes(fixedrange=False)
    fig.update_yaxes(fixedrange=False)
    
    # CRITICAL FIX: Add clickable grid ALIGNED WITH FIELD EDGES
    # Generate grid following field border directions
    grid_x = []
    grid_y = []
    
    grid_spacing = 5.0  # 5 meter spacing
    
    # Try edge-aligned grid for quadrilaterals, fallback to rectangular
    if local_polygon and len(local_polygon) >= 4:
        try:
            from shapely.geometry import Polygon, Point
            poly = Polygon(local_polygon)
            corners = list(poly.convex_hull.exterior.coords)[:-1]
            
            if len(corners) == 4:
                # Sort corners to get field orientation
                centroid = poly.centroid
                angles = [atan2(c[1] - centroid.y, c[0] - centroid.x) for c in corners]
                sorted_corners = [c for _, c in sorted(zip(angles, corners))]
                
                # Identify field edges (4 corners → 4 edges)
                bottom_left = sorted_corners[0]
                bottom_right = sorted_corners[1]
                top_right = sorted_corners[2]
                top_left = sorted_corners[3]
                
                # Calculate field dimensions along edges
                bottom_edge_length = sqrt((bottom_right[0] - bottom_left[0])**2 + (bottom_right[1] - bottom_left[1])**2)
                left_edge_length = sqrt((top_left[0] - bottom_left[0])**2 + (top_left[1] - bottom_left[1])**2)
                
                # Number of grid lines
                n_horizontal = max(2, int(left_edge_length / grid_spacing) + 1)
                n_vertical = max(2, int(bottom_edge_length / grid_spacing) + 1)
                
                # Generate grid aligned with field edges
                for i in range(n_horizontal):
                    t_vertical = i / max(n_horizontal - 1, 1)  # 0 to 1 along left edge
                    
                    # Interpolate along left and right edges
                    left_point = (
                        bottom_left[0] + t_vertical * (top_left[0] - bottom_left[0]),
                        bottom_left[1] + t_vertical * (top_left[1] - bottom_left[1])
                    )
                    right_point = (
                        bottom_right[0] + t_vertical * (top_right[0] - bottom_right[0]),
                        bottom_right[1] + t_vertical * (top_right[1] - bottom_right[1])
                    )
                    
                    # Generate points along this horizontal line
                    for j in range(n_vertical):
                        t_horizontal = j / max(n_vertical - 1, 1)  # 0 to 1 along bottom edge
                        
                        # Interpolate between left and right points
                        x = left_point[0] + t_horizontal * (right_point[0] - left_point[0])
                        y = left_point[1] + t_horizontal * (right_point[1] - left_point[1])
                        
                        # Add all points (no polygon filtering for better coverage)
                        grid_x.append(x)
                        grid_y.append(y)
                
                # If grid is still empty, force fallback
                if len(grid_x) == 0:
                    raise ValueError("Grid generation failed")
            else:
                raise ValueError("Not a quadrilateral")
                
        except Exception as e:
            # Fallback to rectangular grid
            grid_x = []
            grid_y = []
            x_range = np.arange(min_x - 20, max_x + 20, grid_spacing)
            y_range = np.arange(min_y - 20, max_y + 20, grid_spacing)
            xx, yy = np.meshgrid(x_range, y_range)
            grid_x = xx.flatten().tolist()
            grid_y = yy.flatten().tolist()
    else:
        # Rectangular grid fallback
        x_range = np.arange(min_x - 20, max_x + 20, grid_spacing)
        y_range = np.arange(min_y - 20, max_y + 20, grid_spacing)
        xx, yy = np.meshgrid(x_range, y_range)
        grid_x = xx.flatten().tolist()
        grid_y = yy.flatten().tolist()
    
    # FINAL SAFEGUARD: If grid is still empty, create emergency grid
    if len(grid_x) == 0:
        st.sidebar.error("🚨 Primary grid failed - using emergency rectangular grid")
        x_range = np.arange(min_x - 50, max_x + 50, grid_spacing)
        y_range = np.arange(min_y - 50, max_y + 50, grid_spacing)
        xx, yy = np.meshgrid(x_range, y_range)
        grid_x = xx.flatten().tolist()
        grid_y = yy.flatten().tolist()
    
    # Add clickable grid trace - Semi-visible for easier clicking
    if len(grid_x) > 0:
        # Add grid as FIRST trace (before moving it to back)
        fig.add_trace(go.Scatter(
            x=grid_x,
            y=grid_y,
            mode='markers',
            marker=dict(
                size=15,  # Larger for easier clicking (especially for Measure mode)
                color='lightgray',
                opacity=0.3,  # More visible when in Measure mode
                symbol='circle'
            ),
            name='Click Grid',
            showlegend=False,
            hoverinfo='x+y',  # Show coordinates on hover
            hovertemplate='X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
        ))
        
        # Debug: Show grid info
        st.sidebar.write(f"**Grid Status:** ✅ {len(grid_x)} points generated")
    else:
        # This should NEVER happen now
        st.sidebar.error("⛔ CRITICAL: Grid generation completely failed!")
    
    # Move grid trace to the BACK (z-order 0) so other elements draw on top
    if len(fig.data) > 0:
        fig.data = [fig.data[-1]] + list(fig.data[:-1])
    
    return fig


def show_network_summary(network):
    """Display detailed network summary with statistics"""
    
    st.markdown("---")
    st.markdown("### 📊 Network Summary")
    
    def calculate_line_length(points):
        """Calculate total length of a polyline"""
        if len(points) < 2:
            return 0
        total = 0
        for i in range(len(points) - 1):
            dx = points[i+1][0] - points[i][0]
            dy = points[i+1][1] - points[i][1]
            total += np.sqrt(dx**2 + dy**2)
        return total
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown("**🔴 Mainlines**")
        total_main_length = sum(calculate_line_length(line) for line in network.get('mainlines', []))
        st.write(f"- Count: {len(network.get('mainlines', []))}")
        st.write(f"- Total Length: {total_main_length:.1f} m")
    
    with col2:
        st.markdown("**🟠 Submains**")
        total_sub_length = sum(calculate_line_length(line) for line in network.get('submains', []))
        st.write(f"- Count: {len(network.get('submains', []))}")
        st.write(f"- Total Length: {total_sub_length:.1f} m")
    
    with col3:
        st.markdown("**🟢 Laterals**")
        total_lat_length = sum(calculate_line_length(line) for line in network.get('laterals', []))
        st.write(f"- Count: {len(network.get('laterals', []))}")
        st.write(f"- Total Length: {total_lat_length:.1f} m")
    
    with col4:
        st.markdown("**🔵 Valves**")
        valves = network.get('valves', [])
        total_subplots_served = sum(v.get('subplots_served', 0) for v in valves)
        st.write(f"- Count: {len(valves)}")
        st.write(f"- Total Subplots: {total_subplots_served}")
    
    # Get operational data for sprinkler counts
    operational_data = st.session_state.project_data.get('operational_data', {})
    N_sprinkler_lines = operational_data.get('N_sprinkler_lines', 0)
    N_sprinklers_line = operational_data.get('N_sprinklers_line', 0)
    total_sprinklers = operational_data.get('total_sprinklers', 0)
    
    st.markdown("**📊 Totals**")
    total_pipe = total_main_length + total_sub_length + total_lat_length
    st.write(f"- Total Pipe Length: **{total_pipe:.1f} m** ({total_pipe/1000:.2f} km)")
    
    # Show sprinkler information from operational design
    if total_sprinklers > 0:
        st.write(f"- Number of Sprinkler Lines: **{N_sprinkler_lines}**")
        st.write(f"- Sprinklers per Line: **{N_sprinklers_line}**")
        st.write(f"- Total Sprinklers: **{total_sprinklers:,}**")
    else:
        st.write(f"- Total Sprinklers: **{len(network.get('sprinklers', []))}** (from manual placement)")
        st.info("💡 Complete Operational Design to see calculated sprinkler counts")
    
    # Detailed item management with delete options
    st.markdown("---")
    st.markdown("### 🗑️ Manage Network Elements")
    
    # Mainlines
    if network.get('mainlines'):
        with st.expander(f"🔴 Mainlines ({len(network['mainlines'])})"):
            # Clear All button at top
            if st.button("🗑️ Clear All Mainlines", key="clear_all_mainlines_btn", help="Delete all mainlines"):
                network['mainlines'] = []
                st.success("✅ Cleared all mainlines")
                st.rerun()
            
            st.markdown("---")
            
            for i, line in enumerate(network['mainlines']):
                col1, col2 = st.columns([4, 1])
                with col1:
                    length = calculate_line_length(line)
                    st.write(f"**Mainline {i+1}:** {length:.1f} m ({len(line)} points)")
                with col2:
                    if st.button("🗑️", key=f"del_main_{i}", help="Delete this mainline"):
                        network['mainlines'].pop(i)
                        st.rerun()
    
    # Submains
    if network.get('submains'):
        with st.expander(f"🟠 Submains ({len(network['submains'])})"):
            # Clear All button at top
            if st.button("🗑️ Clear All Submains", key="clear_all_submains_btn", help="Delete all submains"):
                network['submains'] = []
                st.success("✅ Cleared all submains")
                st.rerun()
            
            st.markdown("---")
            
            for i, line in enumerate(network['submains']):
                col1, col2 = st.columns([4, 1])
                with col1:
                    length = calculate_line_length(line)
                    st.write(f"**Submain {i+1}:** {length:.1f} m ({len(line)} points)")
                with col2:
                    if st.button("🗑️", key=f"del_sub_{i}", help="Delete this submain"):
                        network['submains'].pop(i)
                        st.rerun()
    
    # Laterals
    if network.get('laterals'):
        with st.expander(f"🟢 Laterals ({len(network['laterals'])})"):
            # Clear All button at top
            if st.button("🗑️ Clear All Laterals", key="clear_all_laterals_btn", help="Delete all laterals"):
                network['laterals'] = []
                st.success("✅ Cleared all laterals")
                st.rerun()
            
            st.markdown("---")
            
            for i, line in enumerate(network['laterals']):
                col1, col2 = st.columns([4, 1])
                with col1:
                    length = calculate_line_length(line)
                    st.write(f"**Lateral {i+1}:** {length:.1f} m ({len(line)} points)")
                with col2:
                    if st.button("🗑️", key=f"del_lat_{i}", help="Delete this lateral"):
                        network['laterals'].pop(i)
                        st.rerun()
    
    # Mainline Valves
    if network.get('mainline_valves'):
        with st.expander(f"🟣 Mainline Valves ({len(network['mainline_valves'])})"):
            # Clear All button at top
            if st.button("🗑️ Clear All Mainline Valves", key="clear_all_mainline_valves_manage_btn", help="Delete all mainline valves"):
                network['mainline_valves'] = []
                if 'mainline_valve_table' in st.session_state:
                    st.session_state.mainline_valve_table = []
                st.success("✅ Cleared all mainline valves")
                st.rerun()
            
            st.markdown("---")
            
            for i, mv in enumerate(network['mainline_valves']):
                col1, col2 = st.columns([4, 1])
                with col1:
                    submain_ref = mv.get('submain_reference', 'Not assigned')
                    x, y = mv.get('x', 0), mv.get('y', 0)
                    st.write(f"**MainValve {i+1}:** {submain_ref} @ ({x:.1f}, {y:.1f})")
                with col2:
                    if st.button("🗑️", key=f"del_mainvalve_{i}", help="Delete this mainline valve"):
                        network['mainline_valves'].pop(i)
                        if 'mainline_valve_table' in st.session_state and len(st.session_state.mainline_valve_table) > i:
                            st.session_state.mainline_valve_table.pop(i)
                        st.rerun()
    
    # Valves
    if network.get('valves'):
        with st.expander(f"🔵 Valves ({len(network['valves'])})"):
            # Clear All button at top
            if st.button("🗑️ Clear All Valves", key="clear_all_valves_manage_btn", help="Delete all valves"):
                network['valves'] = []
                st.success("✅ Cleared all valves")
                st.rerun()
            
            st.markdown("---")
            
            for i, valve in enumerate(network['valves']):
                col1, col2 = st.columns([4, 1])
                with col1:
                    subplots_count = valve.get('subplots_served', 0)
                    selected_subplots = valve.get('selected_subplots', [])
                    x, y = valve.get('x', 0), valve.get('y', 0)
                    irrigation_day = valve.get('irrigation_day', None)
                    is_valid = valve.get('is_valid', True)
                    
                    # Format subplot list
                    if selected_subplots:
                        subplots_str = ', '.join(map(str, selected_subplots))
                        subplot_display = f"Subplot(s) {subplots_str}"
                    else:
                        subplot_display = f"{subplots_count} subplot(s)"
                    
                    # Build display string
                    valve_info = f"**Valve {i+1}:** {subplot_display} @ ({x:.1f}, {y:.1f})"
                    
                    if irrigation_day:
                        valve_info += f" → **Day {irrigation_day}**"
                    
                    # Show validity warning
                    if not is_valid:
                        st.error(f"{valve_info} ⚠️ **INVALID - Multiple irrigation days**")
                    else:
                        st.write(valve_info)
                with col2:
                    if st.button("🗑️", key=f"del_valve_{i}", help="Delete this valve"):
                        network['valves'].pop(i)
                        st.rerun()
