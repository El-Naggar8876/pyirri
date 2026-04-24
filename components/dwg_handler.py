"""
AutoCAD DWG File Handler Module
Provides functionality to parse and convert AutoCAD DWG files 
to field boundary polygons for use in irrigation design workflows.

Note: DWG is a proprietary format. This module uses ezdxf for DXF support
and provides a fallback workflow for DWG conversion.
"""

import streamlit as st
import json
import math
from typing import List, Dict, Tuple, Optional, Any
from datetime import datetime
import io
import tempfile
import os

# Try to import ezdxf for DXF/DWG handling
try:
    import ezdxf
    from ezdxf.entities import LWPolyline, Polyline, Line, Circle, Arc, Spline
    EZDXF_AVAILABLE = True
except ImportError:
    EZDXF_AVAILABLE = False

# Try to import ODA File Converter wrapper (for DWG to DXF conversion)
# This is optional - DWG files can also be converted externally
ODA_CONVERTER_AVAILABLE = False


# =============================================================================
# CONSTANTS
# =============================================================================

SUPPORTED_EXTENSIONS = ['.dwg', '.dxf']
DEFAULT_COORDINATE_SYSTEM = 'local'  # 'local' or 'gps'

# Layer name patterns that typically contain field boundaries
BOUNDARY_LAYER_PATTERNS = [
    'boundary', 'field', 'parcel', 'plot', 'area', 
    'perimeter', 'outline', 'site', 'property',
    'border', 'limit', 'extent', 'cadastral'
]

# Common scales for CAD drawings
CAD_SCALES = {
    'meters': 1.0,
    'centimeters': 0.01,
    'millimeters': 0.001,
    'feet': 0.3048,
    'inches': 0.0254,
    'yards': 0.9144,
}


# =============================================================================
# DWG/DXF PARSING FUNCTIONS
# =============================================================================

def parse_dxf_file(file_content: bytes, layer_filter: str = None) -> Dict:
    """
    Parse a DXF file and extract geometry entities.
    
    Args:
        file_content: Raw bytes of the DXF file
        layer_filter: Optional layer name to filter (case-insensitive)
    
    Returns:
        Dictionary containing extracted geometries and metadata
    """
    if not EZDXF_AVAILABLE:
        return {
            'success': False,
            'error': 'ezdxf library not installed. Please install with: pip install ezdxf',
            'polygons': [],
            'polylines': [],
            'lines': [],
            'points': [],
            'layers': []
        }
    
    try:
        # Create temporary file for ezdxf to read
        with tempfile.NamedTemporaryFile(suffix='.dxf', delete=False) as tmp:
            tmp.write(file_content)
            tmp_path = tmp.name
        
        # Read the DXF file
        doc = ezdxf.readfile(tmp_path)
        msp = doc.modelspace()
        
        # Clean up temp file
        os.unlink(tmp_path)
        
        # Get all layers
        layers = [layer.dxf.name for layer in doc.layers]
        
        # Extract entities
        polygons = []
        polylines = []
        lines = []
        points = []
        circles = []
        
        for entity in msp:
            # Filter by layer if specified
            if layer_filter:
                if layer_filter.lower() not in entity.dxf.layer.lower():
                    continue
            
            layer_name = entity.dxf.layer
            
            if entity.dxftype() == 'LWPOLYLINE':
                coords = [(p[0], p[1]) for p in entity.get_points('xy')]
                is_closed = entity.closed
                
                poly_data = {
                    'layer': layer_name,
                    'coordinates': coords,
                    'is_closed': is_closed,
                    'entity_type': 'LWPOLYLINE'
                }
                
                if is_closed:
                    polygons.append(poly_data)
                else:
                    polylines.append(poly_data)
                    
            elif entity.dxftype() == 'POLYLINE':
                coords = [(v.dxf.location.x, v.dxf.location.y) for v in entity.vertices]
                is_closed = entity.is_closed
                
                poly_data = {
                    'layer': layer_name,
                    'coordinates': coords,
                    'is_closed': is_closed,
                    'entity_type': 'POLYLINE'
                }
                
                if is_closed:
                    polygons.append(poly_data)
                else:
                    polylines.append(poly_data)
                    
            elif entity.dxftype() == 'LINE':
                start = (entity.dxf.start.x, entity.dxf.start.y)
                end = (entity.dxf.end.x, entity.dxf.end.y)
                
                lines.append({
                    'layer': layer_name,
                    'start': start,
                    'end': end,
                    'entity_type': 'LINE'
                })
                
            elif entity.dxftype() == 'CIRCLE':
                center = (entity.dxf.center.x, entity.dxf.center.y)
                radius = entity.dxf.radius
                
                circles.append({
                    'layer': layer_name,
                    'center': center,
                    'radius': radius,
                    'entity_type': 'CIRCLE'
                })
                
            elif entity.dxftype() == 'POINT':
                location = (entity.dxf.location.x, entity.dxf.location.y)
                points.append({
                    'layer': layer_name,
                    'location': location,
                    'entity_type': 'POINT'
                })
        
        # Calculate bounding box
        all_coords = []
        for poly in polygons + polylines:
            all_coords.extend(poly['coordinates'])
        for line in lines:
            all_coords.extend([line['start'], line['end']])
        
        if all_coords:
            min_x = min(c[0] for c in all_coords)
            max_x = max(c[0] for c in all_coords)
            min_y = min(c[1] for c in all_coords)
            max_y = max(c[1] for c in all_coords)
            bounding_box = {
                'min_x': min_x, 'max_x': max_x,
                'min_y': min_y, 'max_y': max_y,
                'width': max_x - min_x,
                'height': max_y - min_y
            }
        else:
            bounding_box = None
        
        return {
            'success': True,
            'error': None,
            'polygons': polygons,
            'polylines': polylines,
            'lines': lines,
            'points': points,
            'circles': circles,
            'layers': layers,
            'bounding_box': bounding_box,
            'entity_count': len(polygons) + len(polylines) + len(lines) + len(points) + len(circles)
        }
        
    except Exception as e:
        return {
            'success': False,
            'error': f'Error parsing DXF file: {str(e)}',
            'polygons': [],
            'polylines': [],
            'lines': [],
            'points': [],
            'layers': []
        }


def identify_field_boundary(parsed_data: Dict) -> Optional[Dict]:
    """
    Attempt to identify the main field boundary from parsed CAD data.
    Uses heuristics: largest closed polygon, or polygon on boundary-named layer.
    
    Args:
        parsed_data: Output from parse_dxf_file
        
    Returns:
        The polygon most likely to be the field boundary, or None
    """
    if not parsed_data['success'] or not parsed_data['polygons']:
        return None
    
    polygons = parsed_data['polygons']
    
    # First, check for polygons on boundary-named layers
    for poly in polygons:
        layer_lower = poly['layer'].lower()
        for pattern in BOUNDARY_LAYER_PATTERNS:
            if pattern in layer_lower:
                return poly
    
    # Otherwise, return the polygon with the largest area
    def calculate_polygon_area(coords):
        """Shoelace formula for polygon area"""
        n = len(coords)
        if n < 3:
            return 0
        area = 0
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        return abs(area) / 2
    
    largest_poly = max(polygons, key=lambda p: calculate_polygon_area(p['coordinates']))
    return largest_poly


def convert_to_local_coordinates(polygon_coords: List[Tuple[float, float]], 
                                  scale: float = 1.0,
                                  offset: Tuple[float, float] = None) -> List[List[float]]:
    """
    Convert CAD coordinates to local meter coordinates.
    Normalizes to origin at bottom-left corner.
    
    Args:
        polygon_coords: List of (x, y) tuples from CAD file
        scale: Conversion factor to meters (e.g., 0.001 for mm)
        offset: Optional (x, y) offset to apply
    
    Returns:
        List of [x, y] coordinates in meters
    """
    if not polygon_coords:
        return []
    
    # Apply scale
    scaled = [(x * scale, y * scale) for x, y in polygon_coords]
    
    # Calculate offset to normalize (origin at bottom-left)
    min_x = min(p[0] for p in scaled)
    min_y = min(p[1] for p in scaled)
    
    if offset:
        min_x = offset[0]
        min_y = offset[1]
    
    # Normalize to origin
    normalized = [[p[0] - min_x, p[1] - min_y] for p in scaled]
    
    return normalized


def convert_local_to_gps(local_coords: List[List[float]], 
                         reference_point: Tuple[float, float],
                         bearing: float = 0) -> List[List[float]]:
    """
    Convert local meter coordinates to GPS coordinates.
    
    Args:
        local_coords: List of [x, y] in meters
        reference_point: (latitude, longitude) of the origin point
        bearing: Rotation angle in degrees (0 = north)
        
    Returns:
        List of [lat, lon] GPS coordinates
    """
    if not local_coords:
        return []
    
    ref_lat, ref_lon = reference_point
    
    # Earth radius in meters
    R = 6371000
    
    # Convert bearing to radians
    bearing_rad = math.radians(bearing)
    
    gps_coords = []
    for x, y in local_coords:
        # Rotate coordinates based on bearing
        x_rot = x * math.cos(bearing_rad) - y * math.sin(bearing_rad)
        y_rot = x * math.sin(bearing_rad) + y * math.cos(bearing_rad)
        
        # Convert meters to degrees
        # Latitude: y direction (north)
        delta_lat = y_rot / R * (180 / math.pi)
        # Longitude: x direction (east), adjusted for latitude
        delta_lon = x_rot / (R * math.cos(math.radians(ref_lat))) * (180 / math.pi)
        
        new_lat = ref_lat + delta_lat
        new_lon = ref_lon + delta_lon
        
        gps_coords.append([new_lat, new_lon])
    
    return gps_coords


def calculate_field_info_from_polygon(local_coords: List[List[float]]) -> Dict:
    """
    Calculate field information from local coordinates.
    
    Args:
        local_coords: List of [x, y] in meters
        
    Returns:
        Dictionary with area_ha, length_m, width_m, perimeter_m
    """
    if len(local_coords) < 3:
        return {
            'area_ha': 0,
            'length_m': 0,
            'width_m': 0,
            'perimeter_m': 0
        }
    
    # Calculate area using shoelace formula
    n = len(local_coords)
    area = 0
    for i in range(n):
        j = (i + 1) % n
        area += local_coords[i][0] * local_coords[j][1]
        area -= local_coords[j][0] * local_coords[i][1]
    area_m2 = abs(area) / 2
    area_ha = area_m2 / 10000
    
    # Calculate bounding box dimensions
    xs = [p[0] for p in local_coords]
    ys = [p[1] for p in local_coords]
    width_m = max(xs) - min(xs)  # E-W
    length_m = max(ys) - min(ys)  # N-S
    
    # Calculate perimeter
    perimeter = 0
    for i in range(n):
        j = (i + 1) % n
        dx = local_coords[j][0] - local_coords[i][0]
        dy = local_coords[j][1] - local_coords[i][1]
        perimeter += math.sqrt(dx**2 + dy**2)
    
    return {
        'area_ha': area_ha,
        'area_m2': area_m2,
        'length_m': length_m,
        'width_m': width_m,
        'perimeter_m': perimeter
    }


# =============================================================================
# STREAMLIT UI COMPONENTS
# =============================================================================

def show_dwg_upload_section(key_prefix: str = "default"):
    """
    Display the DWG/DXF file upload section in the Streamlit UI.
    Returns the processed field geometry data if successful.
    
    Args:
        key_prefix: Unique prefix for widget keys to avoid duplicates when
                   this function is called from multiple places.
    """
    st.markdown("### 📁 Upload AutoCAD File")
    
    st.markdown("""
    <div style="background-color: #fff3cd; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107;">
    <b>Supported Formats:</b>
    <ul>
        <li><b>.DXF</b> - Direct support (recommended)</li>
        <li><b>.DWG</b> - Requires conversion to DXF first (use AutoCAD, ODA File Converter, or online tools)</li>
    </ul>
    <p>💡 <b>Tip:</b> Export your field boundary as a DXF file from AutoCAD for best compatibility.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # File uploader with unique key
    uploaded_file = st.file_uploader(
        "Upload AutoCAD File",
        type=['dxf', 'dwg'],
        help="Upload a DXF or DWG file containing your field boundary",
        key=f"cad_file_uploader_{key_prefix}"
    )
    
    if not uploaded_file:
        return None
    
    file_ext = uploaded_file.name.split('.')[-1].lower()
    
    # Handle DWG files
    if file_ext == 'dwg':
        st.warning("""
        ⚠️ **DWG files require conversion to DXF format.**
        
        Please convert your DWG file using one of these methods:
        1. **AutoCAD**: Save As → DXF format
        2. **Free ODA File Converter**: [Download here](https://www.opendesign.com/guestfiles/oda_file_converter)
        3. **Online converters**: Various free online DWG to DXF converters available
        
        Then upload the converted DXF file.
        """)
        return None
    
    # Parse DXF file
    if file_ext == 'dxf':
        return show_dxf_processing_ui(uploaded_file, key_prefix)
    
    return None


def show_dxf_processing_ui(uploaded_file, key_prefix: str = "default") -> Optional[Dict]:
    """
    Process an uploaded DXF file and show configuration options.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        key_prefix: Unique prefix for widget keys
        
    Returns:
        Processed field geometry data or None
    """
    if not EZDXF_AVAILABLE:
        st.error("""
        ❌ The `ezdxf` library is required to process DXF files.
        
        Install it with: `pip install ezdxf`
        """)
        return None
    
    # Read file content
    file_content = uploaded_file.read()
    
    # Parse the file
    with st.spinner("Parsing DXF file..."):
        parsed_data = parse_dxf_file(file_content)
    
    if not parsed_data['success']:
        st.error(f"❌ Error parsing file: {parsed_data['error']}")
        return None
    
    # Show file info
    st.success(f"✅ File parsed successfully!")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Closed Polygons", len(parsed_data['polygons']))
    with col2:
        st.metric("Open Polylines", len(parsed_data['polylines']))
    with col3:
        st.metric("Total Entities", parsed_data['entity_count'])
    
    # Show layers
    if parsed_data['layers']:
        with st.expander("📋 Layers in File", expanded=False):
            for layer in parsed_data['layers']:
                st.write(f"• {layer}")
    
    # Configuration options
    st.markdown("---")
    st.markdown("#### Configuration")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Layer filter
        layer_options = ['All Layers'] + parsed_data['layers']
        selected_layer = st.selectbox(
            "Select Layer (for boundary)",
            options=layer_options,
            help="Choose which layer contains your field boundary",
            key=f"layer_select_{key_prefix}"
        )
        
        # Scale/units
        scale_unit = st.selectbox(
            "Drawing Units",
            options=list(CAD_SCALES.keys()),
            index=0,  # Default to meters
            help="What units is your drawing in?",
            key=f"scale_unit_{key_prefix}"
        )
        scale_factor = CAD_SCALES[scale_unit]
    
    with col2:
        # Polygon selection if multiple
        if len(parsed_data['polygons']) > 1:
            polygon_options = [
                f"Polygon {i+1} ({p['layer']}, {len(p['coordinates'])} pts)" 
                for i, p in enumerate(parsed_data['polygons'])
            ]
            polygon_options.insert(0, "Auto-detect (largest)")
            
            selected_polygon_idx = st.selectbox(
                "Select Field Boundary Polygon",
                options=range(len(polygon_options)),
                format_func=lambda x: polygon_options[x],
                help="Choose which polygon represents your field boundary",
                key=f"polygon_select_{key_prefix}"
            )
        else:
            selected_polygon_idx = 0
    
    # GPS Reference Point (for geo-referencing)
    st.markdown("---")
    st.markdown("#### Geo-referencing (Optional)")
    
    use_gps_reference = st.checkbox(
        "Set GPS Reference Point",
        help="If you know the GPS coordinates of a reference point in your drawing, enter them here",
        key=f"use_gps_ref_{key_prefix}"
    )
    
    reference_lat = None
    reference_lon = None
    bearing = 0
    
    if use_gps_reference:
        col1, col2, col3 = st.columns(3)
        with col1:
            reference_lat = st.number_input(
                "Reference Latitude",
                value=-25.7479,
                format="%.6f",
                help="Latitude of the origin/reference point",
                key=f"ref_lat_{key_prefix}"
            )
        with col2:
            reference_lon = st.number_input(
                "Reference Longitude", 
                value=28.2293,
                format="%.6f",
                help="Longitude of the origin/reference point",
                key=f"ref_lon_{key_prefix}"
            )
        with col3:
            bearing = st.number_input(
                "Bearing (degrees)",
                value=0.0,
                min_value=0.0,
                max_value=360.0,
                help="Rotation angle from north (0° = north up)",
                key=f"bearing_{key_prefix}"
            )
    
    # Process button
    st.markdown("---")
    if st.button("🔄 Process and Import Field Boundary", type="primary", key=f"process_cad_{key_prefix}"):
        # Re-parse with layer filter if needed
        layer_filter = None if selected_layer == 'All Layers' else selected_layer
        
        if layer_filter:
            parsed_data = parse_dxf_file(file_content, layer_filter)
        
        # Select polygon
        if selected_polygon_idx == 0 or len(parsed_data['polygons']) == 1:
            # Auto-detect
            boundary_poly = identify_field_boundary(parsed_data)
        else:
            boundary_poly = parsed_data['polygons'][selected_polygon_idx - 1]
        
        if not boundary_poly:
            st.error("❌ No valid field boundary polygon found. Please check your layer selection.")
            return None
        
        # Convert to local coordinates (meters)
        local_coords = convert_to_local_coordinates(
            boundary_poly['coordinates'],
            scale=scale_factor
        )
        
        # Calculate field info
        field_info = calculate_field_info_from_polygon(local_coords)
        
        # Convert to GPS if reference provided
        gps_coords = None
        if use_gps_reference and reference_lat and reference_lon:
            gps_coords = convert_local_to_gps(
                local_coords,
                (reference_lat, reference_lon),
                bearing
            )
        
        # Create field geometry data in the same format as the interactive map
        field_geometry = {
            'local_polygon': local_coords,
            'boundary': gps_coords,  # GPS coordinates (if available)
            'gps_polygon': gps_coords,
            'water_source': None,  # To be set separately
            'water_source_local': None,
            'source': 'cad_file',
            'source_file': uploaded_file.name,
            'source_layer': boundary_poly['layer'],
            'scale_unit': scale_unit,
            'imported_at': datetime.now().isoformat(),
            **field_info
        }
        
        # Store in session state
        st.session_state.project_data['field_geometry'] = field_geometry
        st.session_state.project_data['area'] = field_info['area_ha']
        
        # Also update field_layout for the workflow
        if 'field_layout' in st.session_state.project_data:
            st.session_state.project_data['field_layout']['main_boundary'] = gps_coords
            st.session_state.project_data['field_layout']['main_boundary_local'] = local_coords
            st.session_state.project_data['field_layout']['total_area_ha'] = field_info['area_ha']
            st.session_state.project_data['field_layout']['updated_at'] = datetime.now().isoformat()
            if gps_coords:
                st.session_state.project_data['field_layout']['workflow_step'] = 'mark_water_source'
        
        # Show success message
        st.success(f"""
        ✅ **Field Boundary Imported Successfully!**
        
        📊 **Field Information:**
        - **Area:** {field_info['area_ha']:.2f} ha ({field_info['area_m2']:,.0f} m²)
        - **Length (N-S):** {field_info['length_m']:.1f} m
        - **Width (E-W):** {field_info['width_m']:.1f} m
        - **Perimeter:** {field_info['perimeter_m']:.1f} m
        - **Source:** {uploaded_file.name} (Layer: {boundary_poly['layer']})
        """)
        
        # Show preview of polygon
        with st.expander("🔍 Preview Imported Boundary", expanded=True):
            show_polygon_preview(local_coords, field_info)
        
        return field_geometry
    
    return None


def show_polygon_preview(local_coords: List[List[float]], field_info: Dict):
    """
    Display a simple preview of the imported polygon.
    """
    try:
        import plotly.graph_objects as go
        
        xs = [p[0] for p in local_coords] + [local_coords[0][0]]
        ys = [p[1] for p in local_coords] + [local_coords[0][1]]
        
        fig = go.Figure()
        
        # Add polygon
        fig.add_trace(go.Scatter(
            x=xs, y=ys,
            mode='lines+markers',
            fill='toself',
            fillcolor='rgba(46, 134, 171, 0.3)',
            line=dict(color='#2E86AB', width=2),
            marker=dict(size=6),
            name='Field Boundary'
        ))
        
        fig.update_layout(
            title=f"Field Boundary Preview ({field_info['area_ha']:.2f} ha)",
            xaxis_title="East-West (m)",
            yaxis_title="North-South (m)",
            yaxis_scaleanchor="x",
            yaxis_scaleratio=1,
            height=400,
            showlegend=False
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
    except ImportError:
        # Fallback without plotly
        st.write("Polygon vertices (meters from origin):")
        for i, (x, y) in enumerate(local_coords):
            st.write(f"  Point {i+1}: ({x:.1f}, {y:.1f})")


def show_cad_upload_alternative():
    """
    Alternative UI section for CAD upload that appears alongside 
    the interactive map drawing option.
    """
    st.markdown("---")
    st.markdown("### 📁 Or Upload from CAD File")
    
    with st.expander("📐 Import from AutoCAD (DXF/DWG)", expanded=False):
        result = show_dwg_upload_section()
        if result:
            st.rerun()


# =============================================================================
# INTEGRATION HELPERS
# =============================================================================

def get_cad_field_data() -> Optional[Dict]:
    """
    Get field geometry data if it was imported from CAD file.
    
    Returns:
        Field geometry dict if sourced from CAD, None otherwise
    """
    field_geometry = st.session_state.get('project_data', {}).get('field_geometry', {})
    if field_geometry.get('source') == 'cad_file':
        return field_geometry
    return None


def is_field_from_cad() -> bool:
    """Check if current field data was imported from CAD file."""
    field_geometry = st.session_state.get('project_data', {}).get('field_geometry', {})
    return field_geometry.get('source') == 'cad_file'


def merge_cad_with_blocks(cad_geometry: Dict, crop_blocks: List[Dict]) -> Dict:
    """
    Merge CAD-imported field boundary with manually-created crop blocks.
    This allows using CAD for the main boundary while defining
    internal zones/blocks through the UI.
    
    Args:
        cad_geometry: Field geometry from CAD import
        crop_blocks: List of crop block definitions
        
    Returns:
        Combined field data structure
    """
    merged = cad_geometry.copy()
    merged['crop_blocks'] = crop_blocks
    merged['has_internal_blocks'] = len(crop_blocks) > 0
    return merged
