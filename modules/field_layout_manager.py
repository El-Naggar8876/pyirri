"""
Field Layout Manager Module
Manages field boundaries, crop blocks (internal polygons), and irrigation system assignments.

This module provides:
1. Main field boundary polygon drawing and management
2. Internal crop/tree block (zone) polygon creation
3. Crop type and irrigation system assignment per block
4. Data structures for linking blocks to design workflows
5. Integration with sprinkler and drip irrigation design pipelines
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Any

# Try to import mapping libraries
try:
    import folium
    from folium.plugins import Draw
    from streamlit_folium import st_folium
    from shapely.geometry import Polygon, Point, shape
    from shapely.ops import unary_union
    MAP_AVAILABLE = True
except ImportError:
    MAP_AVAILABLE = False

# =============================================================================
# CONSTANTS AND DATA
# =============================================================================

# Crop Types with recommended irrigation systems
CROP_DATABASE = {
    # Fruit Trees
    'mango': {
        'name': 'Mango',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'bubbler',
        'typical_spacing_m': (8, 8),
        'water_demand_L_day': 300,
        'root_depth_m': 2.0
    },
    'apple': {
        'name': 'Apple',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'inline_dripper',
        'typical_spacing_m': (5, 3),
        'water_demand_L_day': 100,
        'root_depth_m': 1.5
    },
    'citrus': {
        'name': 'Citrus (Orange, Lemon)',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'bubbler',
        'typical_spacing_m': (6, 5),
        'water_demand_L_day': 150,
        'root_depth_m': 1.5
    },
    'peach': {
        'name': 'Peach / Stone Fruits',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'micro_sprinkler',
        'typical_spacing_m': (5, 5),
        'water_demand_L_day': 140,
        'root_depth_m': 1.2
    },
    'grapes': {
        'name': 'Grapes / Vineyard',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'pressure_compensating',
        'typical_spacing_m': (3, 2),
        'water_demand_L_day': 40,
        'root_depth_m': 1.0
    },
    'date_palm': {
        'name': 'Date Palm',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'bubbler',
        'typical_spacing_m': (10, 8),
        'water_demand_L_day': 400,
        'root_depth_m': 3.0
    },
    'olives': {
        'name': 'Olives',
        'category': 'fruit_tree',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'bubbler',
        'typical_spacing_m': (7, 7),
        'water_demand_L_day': 180,
        'root_depth_m': 1.5
    },
    
    # Row Crops & Vegetables
    'vegetables': {
        'name': 'Vegetables (General)',
        'category': 'row_crop',
        'recommended_irrigation': ['drip', 'sprinkler'],
        'emitter_type': 'inline_dripper_tube',
        'typical_spacing_m': (2.0, 0.5),
        'water_demand_mm_day': 5,
        'root_depth_m': 0.5
    },
    'tomatoes': {
        'name': 'Tomatoes',
        'category': 'row_crop',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'inline_dripper',
        'typical_spacing_m': (1.5, 0.5),
        'water_demand_mm_day': 6,
        'root_depth_m': 0.6
    },
    'peppers': {
        'name': 'Peppers',
        'category': 'row_crop',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'inline_dripper',
        'typical_spacing_m': (1.5, 0.5),
        'water_demand_mm_day': 5.5,
        'root_depth_m': 0.5
    },
    'watermelon': {
        'name': 'Watermelon / Melon',
        'category': 'row_crop',
        'recommended_irrigation': ['drip'],
        'emitter_type': 'pressure_compensating',
        'typical_spacing_m': (1.5, 0.6),
        'water_demand_mm_day': 13,
        'root_depth_m': 0.8
    },
    
    # Field Crops (typically sprinkler)
    'wheat': {
        'name': 'Wheat',
        'category': 'field_crop',
        'recommended_irrigation': ['sprinkler'],
        'typical_spacing_m': None,
        'water_demand_mm_day': 5,
        'root_depth_m': 1.0
    },
    'maize': {
        'name': 'Maize / Corn',
        'category': 'field_crop',
        'recommended_irrigation': ['sprinkler'],
        'typical_spacing_m': (0.75, 0.25),
        'water_demand_mm_day': 6,
        'root_depth_m': 1.2
    },
    'alfalfa': {
        'name': 'Alfalfa / Lucerne',
        'category': 'field_crop',
        'recommended_irrigation': ['sprinkler'],
        'typical_spacing_m': None,
        'water_demand_mm_day': 7,
        'root_depth_m': 2.0
    },
    'grass': {
        'name': 'Grass / Pasture / Turf',
        'category': 'field_crop',
        'recommended_irrigation': ['sprinkler'],
        'typical_spacing_m': None,
        'water_demand_mm_day': 5,
        'root_depth_m': 0.5
    },
    'potatoes': {
        'name': 'Potatoes',
        'category': 'field_crop',
        'recommended_irrigation': ['sprinkler', 'drip'],
        'typical_spacing_m': (0.9, 0.3),
        'water_demand_mm_day': 5.5,
        'root_depth_m': 0.5
    },
    
    # Other
    'other': {
        'name': 'Other Crop',
        'category': 'other',
        'recommended_irrigation': ['sprinkler', 'drip'],
        'typical_spacing_m': None,
        'water_demand_mm_day': 5,
        'root_depth_m': 0.6
    }
}

# Irrigation System Types
IRRIGATION_SYSTEMS = {
    'drip': {
        'name': 'Drip Irrigation',
        'icon': '💧',
        'description': 'Precise water delivery directly to plant roots. Best for trees, orchards, vegetables.',
        'efficiency': 0.90,
        'suitable_crops': ['fruit_tree', 'row_crop'],
        'components': ['emitters', 'laterals', 'manifolds', 'mainline', 'filter', 'fertigation']
    },
    'sprinkler': {
        'name': 'Sprinkler Irrigation',
        'icon': '🌧️',
        'description': 'Overhead water application simulating rainfall. Best for field crops, grass, large areas.',
        'efficiency': 0.75,
        'suitable_crops': ['field_crop', 'row_crop'],
        'components': ['sprinklers', 'laterals', 'mainline', 'risers', 'pump']
    }
}

# Block colors for visualization
BLOCK_COLORS = [
    '#2ecc71',  # Green
    '#3498db',  # Blue
    '#e74c3c',  # Red
    '#f39c12',  # Orange
    '#9b59b6',  # Purple
    '#1abc9c',  # Teal
    '#e67e22',  # Dark Orange
    '#34495e',  # Dark Gray
    '#16a085',  # Sea Green
    '#c0392b',  # Dark Red
    '#8e44ad',  # Dark Purple
    '#27ae60',  # Emerald
]


# =============================================================================
# DATA STRUCTURES
# =============================================================================

def initialize_field_layout_state():
    """Initialize session state for field layout management."""
    if 'field_layout' not in st.session_state.project_data:
        st.session_state.project_data['field_layout'] = {
            'main_boundary': None,          # Main field polygon (GPS coordinates)
            'main_boundary_local': None,    # Main field polygon (local meters)
            'water_source': None,           # Water source location (GPS)
            'water_source_local': None,     # Water source location (local meters)
            'crop_blocks': [],              # List of internal crop blocks
            'irrigation_assignment': {},    # Block ID -> irrigation system type
            'workflow_step': 'draw_boundary',  # Current workflow step
            'total_area_ha': 0,
            'created_at': None,
            'updated_at': None
        }
    
    return st.session_state.project_data['field_layout']


def get_field_layout():
    """Get current field layout data."""
    return initialize_field_layout_state()


def create_crop_block(
    block_id: int,
    name: str,
    crop_type: str,
    polygon_gps: List[List[float]],
    polygon_local: List[List[float]],
    irrigation_system: str = None,
    notes: str = ""
) -> Dict:
    """
    Create a new crop block data structure.
    
    Args:
        block_id: Unique identifier for the block
        name: User-defined block name
        crop_type: Key from CROP_DATABASE
        polygon_gps: List of [lat, lon] coordinates
        polygon_local: List of [x, y] coordinates in meters
        irrigation_system: 'drip' or 'sprinkler' or None
        notes: Optional user notes
        
    Returns:
        Dictionary representing the crop block
    """
    crop_info = CROP_DATABASE.get(crop_type, CROP_DATABASE['other'])
    
    # Calculate area from polygon
    area_ha = calculate_polygon_area(polygon_local)
    
    # Auto-recommend irrigation if not specified
    if irrigation_system is None and crop_info['recommended_irrigation']:
        irrigation_system = crop_info['recommended_irrigation'][0]
    
    return {
        'id': block_id,
        'name': name,
        'crop_type': crop_type,
        'crop_name': crop_info['name'],
        'category': crop_info['category'],
        'polygon_gps': polygon_gps,
        'polygon_local': polygon_local,
        'area_ha': area_ha,
        'irrigation_system': irrigation_system,
        'recommended_irrigation': crop_info['recommended_irrigation'],
        'emitter_type': crop_info.get('emitter_type'),
        'typical_spacing_m': crop_info.get('typical_spacing_m'),
        'water_demand': crop_info.get('water_demand_L_day') or crop_info.get('water_demand_mm_day'),
        'water_demand_unit': 'L/day/plant' if crop_info.get('water_demand_L_day') else 'mm/day',
        'root_depth_m': crop_info['root_depth_m'],
        'color': BLOCK_COLORS[block_id % len(BLOCK_COLORS)],
        'notes': notes,
        'created_at': datetime.now().isoformat()
    }


def add_crop_block(block: Dict) -> bool:
    """Add a crop block to the field layout."""
    field_layout = get_field_layout()
    
    # Validate block doesn't overlap excessively with existing blocks
    # (allow some overlap for practical purposes)
    
    field_layout['crop_blocks'].append(block)
    field_layout['irrigation_assignment'][str(block['id'])] = block['irrigation_system']
    field_layout['updated_at'] = datetime.now().isoformat()
    
    return True


def update_crop_block(block_id: int, updates: Dict) -> bool:
    """Update an existing crop block."""
    field_layout = get_field_layout()
    
    for block in field_layout['crop_blocks']:
        if block['id'] == block_id:
            block.update(updates)
            block['updated_at'] = datetime.now().isoformat()
            
            # Update irrigation assignment if changed
            if 'irrigation_system' in updates:
                field_layout['irrigation_assignment'][str(block_id)] = updates['irrigation_system']
            
            return True
    
    return False


def delete_crop_block(block_id: int) -> bool:
    """Delete a crop block from the field layout."""
    field_layout = get_field_layout()
    
    field_layout['crop_blocks'] = [
        b for b in field_layout['crop_blocks'] if b['id'] != block_id
    ]
    
    if str(block_id) in field_layout['irrigation_assignment']:
        del field_layout['irrigation_assignment'][str(block_id)]
    
    field_layout['updated_at'] = datetime.now().isoformat()
    return True


def get_blocks_by_irrigation_type(irrigation_type: str) -> List[Dict]:
    """Get all blocks assigned to a specific irrigation system type."""
    field_layout = get_field_layout()
    return [
        block for block in field_layout['crop_blocks']
        if block.get('irrigation_system') == irrigation_type
    ]


def get_next_block_id() -> int:
    """Get the next available block ID."""
    field_layout = get_field_layout()
    if not field_layout['crop_blocks']:
        return 1
    return max(b['id'] for b in field_layout['crop_blocks']) + 1


# =============================================================================
# GEOMETRY CALCULATIONS
# =============================================================================

def calculate_polygon_area(polygon_local: List[List[float]]) -> float:
    """
    Calculate area of polygon in hectares.
    
    Args:
        polygon_local: List of [x, y] coordinates in meters
        
    Returns:
        Area in hectares
    """
    if not polygon_local or len(polygon_local) < 3:
        return 0.0
    
    try:
        if MAP_AVAILABLE:
            poly = Polygon(polygon_local)
            area_m2 = poly.area
        else:
            # Shoelace formula
            n = len(polygon_local)
            area_m2 = 0.0
            for i in range(n):
                j = (i + 1) % n
                area_m2 += polygon_local[i][0] * polygon_local[j][1]
                area_m2 -= polygon_local[j][0] * polygon_local[i][1]
            area_m2 = abs(area_m2) / 2.0
        
        return area_m2 / 10000  # Convert to hectares
    except:
        return 0.0


def convert_gps_to_local(boundary_coords: List[List[float]], 
                         reference_point: List[float] = None) -> List[List[float]]:
    """
    Convert GPS coordinates to local coordinates (meters).
    
    Args:
        boundary_coords: List of [lat, lon] coordinates
        reference_point: [lat, lon] to use as origin, defaults to min lat/lon
        
    Returns:
        List of [x, y] coordinates in meters
    """
    if not boundary_coords:
        return []
    
    lats = [coord[0] for coord in boundary_coords]
    lons = [coord[1] for coord in boundary_coords]
    
    if reference_point:
        min_lat, min_lon = reference_point
    else:
        min_lat = min(lats)
        min_lon = min(lons)
    
    lat_avg = np.mean(lats)
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * np.cos(np.radians(lat_avg))
    
    local_coords = []
    for lat, lon in boundary_coords:
        x = (lon - min_lon) * meters_per_deg_lon
        y = (lat - min_lat) * meters_per_deg_lat
        local_coords.append([x, y])
    
    return local_coords


def convert_point_gps_to_local(point_gps: List[float],
                               boundary_coords: List[List[float]]) -> List[float]:
    """Convert a single GPS point to local coordinates."""
    if not point_gps or not boundary_coords:
        return None
    
    lats = [coord[0] for coord in boundary_coords]
    lons = [coord[1] for coord in boundary_coords]
    
    min_lat = min(lats)
    min_lon = min(lons)
    lat_avg = np.mean(lats)
    
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * np.cos(np.radians(lat_avg))
    
    x = (point_gps[1] - min_lon) * meters_per_deg_lon
    y = (point_gps[0] - min_lat) * meters_per_deg_lat
    
    return [x, y]


def check_polygon_inside_boundary(inner_polygon: List[List[float]], 
                                   outer_polygon: List[List[float]]) -> bool:
    """Check if inner polygon is inside outer polygon."""
    if not MAP_AVAILABLE:
        return True  # Skip validation if shapely not available
    
    try:
        inner = Polygon(inner_polygon)
        outer = Polygon(outer_polygon)
        return outer.contains(inner) or outer.intersects(inner)
    except:
        return True


def get_polygon_centroid(polygon: List[List[float]]) -> List[float]:
    """Get the centroid of a polygon."""
    if not polygon:
        return [0, 0]
    
    try:
        if MAP_AVAILABLE:
            poly = Polygon(polygon)
            centroid = poly.centroid
            return [centroid.x, centroid.y]
        else:
            x_sum = sum(p[0] for p in polygon)
            y_sum = sum(p[1] for p in polygon)
            n = len(polygon)
            return [x_sum / n, y_sum / n]
    except:
        return [0, 0]


def calculate_bounding_box(polygon: List[List[float]]) -> Dict:
    """Calculate bounding box of polygon."""
    if not polygon:
        return {'min_x': 0, 'max_x': 0, 'min_y': 0, 'max_y': 0, 'width': 0, 'height': 0}
    
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    
    return {
        'min_x': min_x,
        'max_x': max_x,
        'min_y': min_y,
        'max_y': max_y,
        'width': max_x - min_x,
        'height': max_y - min_y
    }


# =============================================================================
# WORKFLOW STATE MANAGEMENT
# =============================================================================

def get_workflow_step() -> str:
    """Get current workflow step."""
    field_layout = get_field_layout()
    return field_layout.get('workflow_step', 'draw_boundary')


def set_workflow_step(step: str):
    """Set current workflow step."""
    valid_steps = [
        'draw_boundary',      # Step 1: Draw main field boundary
        'mark_water_source',  # Step 2: Mark water source
        'create_blocks',      # Step 3: Create internal crop blocks
        'assign_irrigation',  # Step 4: Assign irrigation system types
        'ready_for_design'    # Step 5: Ready to proceed to design workflows
    ]
    
    if step in valid_steps:
        field_layout = get_field_layout()
        field_layout['workflow_step'] = step
        field_layout['updated_at'] = datetime.now().isoformat()


def can_proceed_to_next_step() -> Tuple[bool, str]:
    """
    Check if user can proceed to next workflow step.
    
    Returns:
        Tuple of (can_proceed: bool, reason: str)
    """
    field_layout = get_field_layout()
    step = field_layout.get('workflow_step', 'draw_boundary')
    
    if step == 'draw_boundary':
        if field_layout.get('main_boundary'):
            return True, "Field boundary defined"
        return False, "Please draw the main field boundary first"
    
    elif step == 'mark_water_source':
        if field_layout.get('water_source'):
            return True, "Water source marked"
        return False, "Please mark the water source location"
    
    elif step == 'create_blocks':
        if field_layout.get('crop_blocks'):
            return True, f"{len(field_layout['crop_blocks'])} block(s) created"
        return False, "Please create at least one crop block"
    
    elif step == 'assign_irrigation':
        blocks = field_layout.get('crop_blocks', [])
        if all(b.get('irrigation_system') for b in blocks):
            return True, "All blocks have irrigation systems assigned"
        return False, "Please assign irrigation system to all blocks"
    
    return True, "Ready to proceed"


def advance_workflow():
    """Advance to next workflow step if possible."""
    can_proceed, _ = can_proceed_to_next_step()
    if not can_proceed:
        return False
    
    step_order = [
        'draw_boundary',
        'mark_water_source', 
        'create_blocks',
        'assign_irrigation',
        'ready_for_design'
    ]
    
    current = get_workflow_step()
    current_idx = step_order.index(current) if current in step_order else 0
    
    if current_idx < len(step_order) - 1:
        set_workflow_step(step_order[current_idx + 1])
        return True
    
    return False


# =============================================================================
# SUMMARY AND REPORTING
# =============================================================================

def get_field_layout_summary() -> Dict:
    """Get summary of field layout for reports and display."""
    field_layout = get_field_layout()
    
    blocks = field_layout.get('crop_blocks', [])
    
    # Calculate totals
    total_block_area = sum(b.get('area_ha', 0) for b in blocks)
    
    drip_blocks = [b for b in blocks if b.get('irrigation_system') == 'drip']
    sprinkler_blocks = [b for b in blocks if b.get('irrigation_system') == 'sprinkler']
    
    drip_area = sum(b.get('area_ha', 0) for b in drip_blocks)
    sprinkler_area = sum(b.get('area_ha', 0) for b in sprinkler_blocks)
    
    # Get unique crops
    crops = list(set(b.get('crop_name') for b in blocks if b.get('crop_name')))
    
    # Check for boundary - either GPS or local coordinates (for CAD imports)
    has_boundary = field_layout.get('main_boundary') is not None or field_layout.get('main_boundary_local') is not None
    has_water_source = field_layout.get('water_source') is not None or field_layout.get('water_source_local') is not None
    
    return {
        'has_boundary': has_boundary,
        'has_water_source': has_water_source,
        'total_field_area_ha': field_layout.get('total_area_ha', 0),
        'total_blocks': len(blocks),
        'total_block_area_ha': total_block_area,
        'drip_blocks_count': len(drip_blocks),
        'drip_area_ha': drip_area,
        'sprinkler_blocks_count': len(sprinkler_blocks),
        'sprinkler_area_ha': sprinkler_area,
        'crops': crops,
        'workflow_step': field_layout.get('workflow_step', 'draw_boundary'),
        'blocks': blocks
    }


def export_field_layout_to_json() -> str:
    """Export field layout data as JSON string."""
    field_layout = get_field_layout()
    return json.dumps(field_layout, indent=2, default=str)


def import_field_layout_from_json(json_str: str) -> bool:
    """Import field layout from JSON string."""
    try:
        data = json.loads(json_str)
        st.session_state.project_data['field_layout'] = data
        return True
    except:
        return False


# =============================================================================
# DESIGN WORKFLOW INTEGRATION
# =============================================================================

def get_drip_design_data() -> Dict:
    """
    Prepare data for drip irrigation design workflow.
    Returns crop zones formatted for the drip_irrigation module.
    """
    blocks = get_blocks_by_irrigation_type('drip')
    
    crop_zones = []
    for block in blocks:
        spacing = block.get('typical_spacing_m')
        row_spacing = spacing[0] if spacing else 5.0
        plant_spacing = spacing[1] if spacing else 3.0
        
        # Calculate plants per hectare and total
        plants_per_ha = 10000 / (row_spacing * plant_spacing) if spacing else 400
        total_plants = int(plants_per_ha * block.get('area_ha', 0))
        
        water_req = block.get('water_demand', 100)
        daily_volume_m3 = (total_plants * water_req) / 1000 if block.get('water_demand_unit') == 'L/day/plant' else 0
        
        crop_zones.append({
            'id': block['id'],
            'name': block['name'],
            'crop': block['crop_name'],
            'area_ha': block['area_ha'],
            'row_spacing_m': row_spacing,
            'plant_spacing_m': plant_spacing,
            'emitter_type': block.get('emitter_type', 'inline_dripper'),
            'water_req_L_day': water_req,
            'plants_per_ha': plants_per_ha,
            'total_plants': total_plants,
            'daily_volume_m3': daily_volume_m3,
            'polygon_local': block.get('polygon_local', []),
            'color': block['color']
        })
    
    return {
        'crop_zones': crop_zones,
        'total_area_ha': sum(b.get('area_ha', 0) for b in blocks),
        'total_daily_volume_m3': sum(z['daily_volume_m3'] for z in crop_zones)
    }


def get_sprinkler_design_data() -> Dict:
    """
    Prepare data for sprinkler irrigation design workflow.
    Returns data formatted for the sprinkler modules.
    """
    blocks = get_blocks_by_irrigation_type('sprinkler')
    
    sprinkler_zones = []
    for block in blocks:
        sprinkler_zones.append({
            'id': block['id'],
            'name': block['name'],
            'crop': block['crop_name'],
            'area_ha': block['area_ha'],
            'water_demand_mm_day': block.get('water_demand', 5),
            'root_depth_m': block.get('root_depth_m', 0.6),
            'polygon_local': block.get('polygon_local', []),
            'color': block['color']
        })
    
    return {
        'sprinkler_zones': sprinkler_zones,
        'total_area_ha': sum(b.get('area_ha', 0) for b in blocks)
    }


def sync_to_project_data():
    """
    Sync field layout data to project_data structure for use by design modules.
    Call this after field layout workflow is complete.
    """
    field_layout = get_field_layout()
    project_data = st.session_state.project_data
    
    # Update total area
    if field_layout.get('total_area_ha'):
        project_data['area'] = field_layout['total_area_ha']
    
    # Update field geometry
    if field_layout.get('main_boundary'):
        project_data['field_geometry'] = {
            'boundary': field_layout['main_boundary'],
            'local_polygon': field_layout.get('main_boundary_local', []),
            'water_source': field_layout.get('water_source'),
            'water_source_local': field_layout.get('water_source_local'),
            'area_ha': field_layout.get('total_area_ha', 0),
            **calculate_bounding_box(field_layout.get('main_boundary_local', []))
        }
        project_data['field_geometry']['length_m'] = project_data['field_geometry'].get('height', 0)
        project_data['field_geometry']['width_m'] = project_data['field_geometry'].get('width', 0)
    
    # Update drip operational data
    drip_data = get_drip_design_data()
    if drip_data['crop_zones']:
        if 'drip_operational' not in project_data:
            project_data['drip_operational'] = {}
        project_data['drip_operational']['crop_zones'] = drip_data['crop_zones']
    
    # Mark as synced
    field_layout['synced_at'] = datetime.now().isoformat()


# =============================================================================
# VISUALIZATION FUNCTIONS (Reusable across modules)
# =============================================================================

def hex_to_rgba(hex_color: str, alpha: float = 0.25) -> str:
    """Convert hex color to rgba string for Plotly."""
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f'rgba({r}, {g}, {b}, {alpha})'
    return f'rgba(100, 100, 100, {alpha})'


def render_field_layout_visualization(
    irrigation_filter: str = None,
    title: str = "Field Layout",
    show_water_source: bool = True,
    height: int = 450,
    show_legend: bool = True
) -> bool:
    """
    Render field layout visualization with Plotly.
    
    This function can be called from any module to display the field layout.
    
    Args:
        irrigation_filter: 'drip', 'sprinkler', or None for all blocks
        title: Chart title
        show_water_source: Whether to show water source marker
        height: Chart height in pixels
        show_legend: Whether to show legend
        
    Returns:
        True if visualization was rendered, False if no data available
    """
    try:
        import streamlit as st
        import plotly.graph_objects as go
    except ImportError:
        return False
    
    field_layout = get_field_layout()
    
    # Check if we have data to visualize
    if not field_layout.get('crop_blocks') and not field_layout.get('main_boundary_local'):
        return False
    
    # Filter blocks by irrigation type if specified
    all_blocks = field_layout.get('crop_blocks', [])
    if irrigation_filter:
        blocks = [b for b in all_blocks if b.get('irrigation_system') == irrigation_filter]
    else:
        blocks = all_blocks
    
    # If filtering and no blocks match, check if there's at least a boundary to show
    if irrigation_filter and not blocks and not field_layout.get('main_boundary_local'):
        return False
    
    fig = go.Figure()
    
    # Draw main boundary
    if field_layout.get('main_boundary_local'):
        boundary = field_layout['main_boundary_local']
        xs = [p[0] for p in boundary]
        ys = [p[1] for p in boundary]
        fig.add_trace(go.Scatter(
            x=xs + [xs[0]],
            y=ys + [ys[0]],
            mode='lines',
            line=dict(color='gold', width=3),
            name='Field Boundary',
            fill='toself',
            fillcolor='rgba(255, 215, 0, 0.1)'
        ))
    
    # Draw each block
    for block in blocks:
        if block.get('polygon_local'):
            polygon = block['polygon_local']
            xs = [p[0] for p in polygon]
            ys = [p[1] for p in polygon]
            
            # Convert hex color to rgba for fill
            fill_color = hex_to_rgba(block['color'], 0.3)
            
            # Determine irrigation icon
            irr_system = block.get('irrigation_system', '')
            irr_icon = '💧' if irr_system == 'drip' else '🌧️' if irr_system == 'sprinkler' else ''
            
            fig.add_trace(go.Scatter(
                x=xs + [xs[0]],
                y=ys + [ys[0]],
                mode='lines',
                line=dict(color=block['color'], width=2),
                name=f"{block['name']} ({block.get('crop_name', 'Unknown')})",
                fill='toself',
                fillcolor=fill_color
            ))
            
            # Add label at centroid
            centroid = get_polygon_centroid(polygon)
            fig.add_annotation(
                x=centroid[0],
                y=centroid[1],
                text=f"<b>{block['name']}</b><br>{block.get('crop_name', '')}<br>{block.get('area_ha', 0):.2f} ha {irr_icon}",
                showarrow=False,
                font=dict(size=10, color='black'),
                bgcolor='rgba(255,255,255,0.7)',
                bordercolor=block['color'],
                borderwidth=1,
                borderpad=3
            )
    
    # Draw water source
    if show_water_source and field_layout.get('water_source_local'):
        ws = field_layout['water_source_local']
        fig.add_trace(go.Scatter(
            x=[ws[0]],
            y=[ws[1]],
            mode='markers+text',
            marker=dict(size=15, color='blue', symbol='diamond'),
            name='Water Source',
            text=['💧 Water'],
            textposition='top center'
        ))
    
    # Layout configuration
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)),
        xaxis_title='Width (m)',
        yaxis_title='Length (m)',
        showlegend=show_legend,
        height=height,
        yaxis_scaleanchor="x",
        yaxis_scaleratio=1,
        margin=dict(l=50, r=50, t=50, b=50),
        plot_bgcolor='rgba(240, 248, 255, 0.5)'
    )
    
    st.plotly_chart(fig, width="stretch")
    return True


def render_field_layout_summary(irrigation_filter: str = None) -> bool:
    """
    Render a summary card of field layout blocks.
    
    Args:
        irrigation_filter: 'drip', 'sprinkler', or None for all blocks
        
    Returns:
        True if summary was rendered, False if no data
    """
    try:
        import streamlit as st
    except ImportError:
        return False
    
    field_layout = get_field_layout()
    all_blocks = field_layout.get('crop_blocks', [])
    
    if not all_blocks:
        return False
    
    # Filter blocks
    if irrigation_filter:
        blocks = [b for b in all_blocks if b.get('irrigation_system') == irrigation_filter]
    else:
        blocks = all_blocks
    
    if not blocks:
        return False
    
    # Calculate totals
    total_area = sum(b.get('area_ha', 0) for b in blocks)
    
    # Display summary
    irr_name = "Drip Irrigation" if irrigation_filter == 'drip' else "Sprinkler Irrigation" if irrigation_filter == 'sprinkler' else "All"
    irr_icon = "💧" if irrigation_filter == 'drip' else "🌧️" if irrigation_filter == 'sprinkler' else "🌱"
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                padding: 15px; border-radius: 10px; margin-bottom: 15px;">
        <h4 style="color: white; margin: 0 0 10px 0;">{irr_icon} {irr_name} Blocks from Field Layout</h4>
        <div style="display: flex; gap: 20px; flex-wrap: wrap;">
            <div style="color: white;">
                <span style="font-size: 1.5em; font-weight: bold;">{len(blocks)}</span><br>
                <span style="font-size: 0.85em;">Block(s)</span>
            </div>
            <div style="color: white;">
                <span style="font-size: 1.5em; font-weight: bold;">{total_area:.2f}</span><br>
                <span style="font-size: 0.85em;">Hectares</span>
            </div>
            <div style="color: white;">
                <span style="font-size: 1.5em; font-weight: bold;">{len(set(b.get('crop_name') for b in blocks))}</span><br>
                <span style="font-size: 0.85em;">Crop Type(s)</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Show block details in columns
    cols = st.columns(min(4, len(blocks)))
    for i, block in enumerate(blocks):
        with cols[i % 4]:
            st.markdown(f"""
            <div style="background: {block['color']}22; border: 2px solid {block['color']}; 
                        padding: 10px; border-radius: 8px; margin-bottom: 10px; text-align: center;">
                <b style="color: {block['color']};">{block['name']}</b><br>
                <span style="font-size: 0.9em;">🌱 {block.get('crop_name', 'Unknown')}</span><br>
                <span style="font-size: 0.85em;">📐 {block.get('area_ha', 0):.2f} ha</span>
            </div>
            """, unsafe_allow_html=True)
    
    return True
