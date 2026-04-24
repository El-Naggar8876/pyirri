"""
Home Module - Project Setup and Overview
Enhanced with Field Layout Workflow for multi-block crop management.
"""

import streamlit as st
from datetime import datetime
import json
import pandas as pd

# Module-level placeholders - will be set by _init_lazy_imports()
auth = None
show_project_manager_ui = None
get_gee_manager = None
flm = None
folium = None
Draw = None
st_folium = None
Nominatim = None
Polygon = None
np = None
dwg_handler = None

# Flags for availability
AUTH_AVAILABLE = False
GEE_AVAILABLE = False
FIELD_LAYOUT_AVAILABLE = False
MAP_AVAILABLE = False
DWG_HANDLER_AVAILABLE = False

_lazy_imports_done = False

def _init_lazy_imports():
    """Initialize all lazy imports - call at start of show()"""
    global _lazy_imports_done, AUTH_AVAILABLE, GEE_AVAILABLE, FIELD_LAYOUT_AVAILABLE, MAP_AVAILABLE, DWG_HANDLER_AVAILABLE
    global auth, show_project_manager_ui, get_gee_manager, flm
    global folium, Draw, st_folium, Nominatim, Polygon, np, dwg_handler
    
    if _lazy_imports_done:
        return
    
    # Import auth
    try:
        from modules import auth as _auth
        auth = _auth
        AUTH_AVAILABLE = True
    except Exception as e:
        auth = None
        AUTH_AVAILABLE = False
        print(f"Failed to import auth in home.py: {e}")
    
    # Import GEE
    try:
        from modules.gee_project_manager import show_project_manager_ui as _show_pm, get_gee_manager as _get_gee
        show_project_manager_ui = _show_pm
        get_gee_manager = _get_gee
        GEE_AVAILABLE = True
    except Exception as e:
        show_project_manager_ui = None
        get_gee_manager = None
        GEE_AVAILABLE = False
        print(f"Failed to import GEE in home.py: {e}")
    
    # Import field layout manager
    try:
        from modules import field_layout_manager as _flm
        flm = _flm
        FIELD_LAYOUT_AVAILABLE = True
    except Exception as e:
        flm = None
        FIELD_LAYOUT_AVAILABLE = False
        print(f"Failed to import flm in home.py: {e}")
    
    # Import map libraries
    try:
        import folium as _folium
        from folium.plugins import Draw as _Draw
        from streamlit_folium import st_folium as _st_folium
        from geopy.geocoders import Nominatim as _Nominatim
        from shapely.geometry import Polygon as _Polygon
        import numpy as _np
        folium = _folium
        Draw = _Draw
        st_folium = _st_folium
        Nominatim = _Nominatim
        Polygon = _Polygon
        np = _np
        MAP_AVAILABLE = True
    except Exception as e:
        folium = None
        Draw = None
        st_folium = None
        Nominatim = None
        Polygon = None
        np = None
        MAP_AVAILABLE = False
        print(f"Failed to import map libraries in home.py: {e}")
    
    # Import DWG/CAD handler
    try:
        from components import dwg_handler as _dwg_handler
        dwg_handler = _dwg_handler
        DWG_HANDLER_AVAILABLE = True
    except Exception as e:
        dwg_handler = None
        DWG_HANDLER_AVAILABLE = False
        print(f"Failed to import dwg_handler in home.py: {e}")
    
    _lazy_imports_done = True

def _get_auth():
    """Get the auth module"""
    _init_lazy_imports()
    return auth

def _get_gee_funcs():
    """Get GEE functions"""
    _init_lazy_imports()
    return show_project_manager_ui, get_gee_manager

def _get_flm():
    """Get field layout manager"""
    _init_lazy_imports()
    return flm

def _get_map_libs():
    """Get map libraries"""
    _init_lazy_imports()
    return (folium, Draw, st_folium, Nominatim, Polygon, np)

def show():
    # Initialize lazy imports first
    _init_lazy_imports()
    
    st.markdown('<h1 class="main-header">Irrigation System Design</h1>', unsafe_allow_html=True)
    
    # Welcome message with user info - get name directly from session state
    username = st.session_state.get('username')
    user_name = st.session_state.get('name') or username or 'User'
    
    st.markdown(f"""
    <div class="info-box">
    <h3>Welcome, {user_name}! 👋</h3>
    <p>This comprehensive tool helps you design complete sprinkler and drip irrigation systems based on 
    FAO standards and best practices. Start by setting up your project and defining your field layout.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # =========================================================================
    # MAIN TABS - Project Setup vs Field Layout Workflow
    # =========================================================================
    main_tabs = st.tabs([
        "📋 Project Setup",
        "🗺️ Field Layout & Blocks",
        "📊 Design Workflow"
    ])
    
    # =========================================================================
    # TAB 1: PROJECT SETUP (existing functionality)
    # =========================================================================
    with main_tabs[0]:
        show_project_setup_tab(username)
    
    # =========================================================================
    # TAB 2: FIELD LAYOUT WORKFLOW (NEW)
    # =========================================================================
    with main_tabs[1]:
        show_field_layout_workflow_tab()
    
    # =========================================================================
    # TAB 3: DESIGN WORKFLOW GUIDE
    # =========================================================================
    with main_tabs[2]:
        show_design_workflow_tab()


def show_project_setup_tab(username):
    """Original project setup functionality."""
    
    # Project Setup
    st.markdown('<h2 class="sub-header">Project Setup</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        project_name = st.text_input(
            "Project Name",
            value=st.session_state.project_data.get('project_name', ''),
            help="Enter a unique name for your irrigation project"
        )
        
        location = st.text_input(
            "Location",
            value=st.session_state.project_data.get('location', ''),
            help="Project location (City, Region, Country)"
        )
        
        area = st.number_input(
            "Total Area (hectares)",
            min_value=0.0,
            value=float(st.session_state.project_data.get('area', 0.0)),
            step=0.1,
            help="Total irrigable area in hectares"
        )
        
        altitude = st.number_input(
            "Altitude (m above sea level)",
            min_value=0.0,
            value=float(st.session_state.project_data.get('altitude', 0.0)),
            step=10.0,
            help="Altitude affects atmospheric pressure and sprinkler performance"
        )
    
    with col2:
        crop_type = st.selectbox(
            "Primary Crop Type",
            options=['', 'Wheat', 'Maize', 'Barley', 'Potatoes', 'Vegetables', 
                    'Citrus', 'Grapes', 'Apples', 'Alfalfa', 'Grass/Pasture', 'Other'],
            index=0 if not st.session_state.project_data.get('crop_type') else 
                  ['', 'Wheat', 'Maize', 'Barley', 'Potatoes', 'Vegetables', 
                   'Citrus', 'Grapes', 'Apples', 'Alfalfa', 'Grass/Pasture', 'Other'].index(
                       st.session_state.project_data.get('crop_type', '')
                   )
        )
        
        soil_type = st.selectbox(
            "Soil Type",
            options=['', 'Sandy', 'Loamy Sand', 'Sandy Loam', 'Loam', 
                    'Silty Loam', 'Silt', 'Clay Loam', 'Clay'],
            index=0 if not st.session_state.project_data.get('soil_type') else
                  ['', 'Sandy', 'Loamy Sand', 'Sandy Loam', 'Loam', 
                   'Silty Loam', 'Silt', 'Clay Loam', 'Clay'].index(
                       st.session_state.project_data.get('soil_type', '')
                   )
        )
        
        water_source = st.selectbox(
            "Water Source",
            options=['', 'River', 'Lake', 'Reservoir', 'Well', 'Borehole', 
                    'Municipal Supply', 'Canal'],
            index=0 if not st.session_state.project_data.get('water_source') else
                  ['', 'River', 'Lake', 'Reservoir', 'Well', 'Borehole', 
                   'Municipal Supply', 'Canal'].index(
                       st.session_state.project_data.get('water_source', '')
                   )
        )
        
        water_quality = st.selectbox(
            "Water Quality",
            options=['Good', 'Moderate', 'Poor'],
            index=['Good', 'Moderate', 'Poor'].index(
                st.session_state.project_data.get('water_quality', 'Good')
            )
        )
    
    # Save project data
    col_save1, col_save2 = st.columns(2)
    
    with col_save1:
        if st.button("💾 Save Project Information", type="primary"):
            st.session_state.project_data.update({
                'project_name': project_name,
                'location': location,
                'area': area,
                'altitude': altitude,
                'crop_type': crop_type,
                'soil_type': soil_type,
                'water_source': water_source,
                'water_quality': water_quality,
                'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            st.success("✅ Project information saved to current session!")
            st.rerun()
    
    with col_save2:
        # Save to user account (persistent storage)
        current_user = auth.get_current_user() if AUTH_AVAILABLE and auth else None
        
        if AUTH_AVAILABLE and current_user and project_name:
            if st.button("☁️ Save to My Account", type="secondary", 
                        help="Save this project to your account for future access"):
                # Update session first
                st.session_state.project_data.update({
                    'project_name': project_name,
                    'location': location,
                    'area': area,
                    'altitude': altitude,
                    'crop_type': crop_type,
                    'soil_type': soil_type,
                    'water_source': water_source,
                    'water_quality': water_quality,
                    'last_updated': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })
                
                # Debug: Check climate data before saving
                climate_data = st.session_state.project_data.get('climate_data', {})
                has_monthly = climate_data.get('monthly_data') is not None
                monthly_type = type(climate_data.get('monthly_data')).__name__ if has_monthly else 'None'
                
                st.info(f"Saving as user: **{current_user}** | Climate data type: {monthly_type}")
                
                # Save to persistent storage (auth already retrieved above)
                success = auth.save_user_project(project_name, st.session_state.project_data) if auth else False
                if success:
                    if has_monthly:
                        st.success(f"✅ Project '{project_name}' saved! Climate data type: {monthly_type}")
                    else:
                        st.success(f"✅ Project '{project_name}' saved (no climate data found)")
                    st.balloons()
                else:
                    st.error(f"❌ Failed to save project. User: {current_user}")
        elif AUTH_AVAILABLE and not current_user:
            st.warning("⚠️ Please login to save to your account")
        elif not project_name:
            st.info("💡 Enter a project name to enable saving to your account")
    
    # Cloud Project Manager Section
    st.markdown("---")
    if GEE_AVAILABLE and show_project_manager_ui:
        show_project_manager_ui()
    else:
        st.markdown("### ☁️ Cloud Project Manager")
        st.warning("""
        ⚠️ **Google Earth Engine integration not available.**
        
        To enable cloud storage, install the earthengine-api package:
        ```
        pip install earthengine-api
        ```
        """)
    
    # Interactive Field Mapping
    st.markdown("---")
    st.markdown('<h2 class="sub-header">📍 Field Mapping & Delineation</h2>', unsafe_allow_html=True)
    
    # Tabs for different input methods
    field_input_tabs = st.tabs(["🗺️ Draw on Map", "📁 Upload AutoCAD File", "📝 Manual Entry"])
    
    with field_input_tabs[0]:
        if MAP_AVAILABLE:
            show_interactive_map()
        else:
            st.warning("""
            ⚠️ **Interactive mapping not available.**
            
            To enable interactive field delineation, install required packages:
            ```
            pip install folium streamlit-folium geopy shapely
            ```
            
            Use the "Upload AutoCAD File" or "Manual Entry" tab instead.
            """)
    
    with field_input_tabs[1]:
        if DWG_HANDLER_AVAILABLE and dwg_handler:
            result = dwg_handler.show_dwg_upload_section(key_prefix="project_setup")
            if result:
                st.success("✅ Field boundary imported from CAD file!")
                st.rerun()
        else:
            st.warning("""
            ⚠️ **AutoCAD file support requires the `ezdxf` library.**
            
            To enable CAD file import, install the library:
            ```bash
            pip install ezdxf
            ```
            
            **Supported formats:**
            - **.DXF** - Direct support (recommended)
            - **.DWG** - Requires conversion to DXF first (use AutoCAD "Save As" or free ODA File Converter)
            """)
    
    with field_input_tabs[2]:
        show_manual_field_input()


def show_design_workflow_tab():
    """Design workflow guide and project status."""
    st.markdown('<h2 class="sub-header">Design Workflow</h2>', unsafe_allow_html=True)
    
    # Check field layout status
    if FIELD_LAYOUT_AVAILABLE:
        summary = flm.get_field_layout_summary()
        if summary['total_blocks'] > 0:
            st.success(f"""
            ✅ **Field Layout Complete!** 
            - {summary['total_blocks']} crop block(s) defined
            - Drip blocks: {summary['drip_blocks_count']} ({summary['drip_area_ha']:.2f} ha)
            - Sprinkler blocks: {summary['sprinkler_blocks_count']} ({summary['sprinkler_area_ha']:.2f} ha)
            
            You can now proceed with the appropriate design workflow based on your irrigation selections.
            """)
            
            if summary['drip_blocks_count'] > 0:
                st.info("💧 **Drip Irrigation blocks detected** → Use the Drip Irrigation menu for design")
            if summary['sprinkler_blocks_count'] > 0:
                st.info("🌧️ **Sprinkler blocks detected** → Use the Sprinkler Irrigation menu for design")
        else:
            st.warning("⚠️ Please complete the **Field Layout & Blocks** tab to define your crop blocks before starting design.")
    
    workflow_steps = [
        ("1️⃣", "Field Layout", "Draw field boundary and create crop/tree blocks"),
        ("2️⃣", "Crop Water Requirements", "Calculate ET₀, crop coefficients, and irrigation needs"),
        ("3️⃣", "Equipment Selection", "Choose sprinklers or emitters based on irrigation type"),
        ("4️⃣", "Hydraulic Design", "Design system hydraulics and pressure requirements"),
        ("5️⃣", "Pipe Network Design", "Size laterals, mainlines, and submains"),
        ("6️⃣", "Pump Selection", "Select appropriate pump based on system requirements"),
        ("7️⃣", "Cost Estimation", "Calculate material costs and bill of quantities"),
        ("8️⃣", "Reports & Export", "Generate comprehensive design reports")
    ]
    
    cols = st.columns(2)
    for i, (icon, title, description) in enumerate(workflow_steps):
        with cols[i % 2]:
            st.markdown(f"""
            <div class="info-box">
            <h4>{icon} {title}</h4>
            <p>{description}</p>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
    
    # Quick stats
    if st.session_state.project_data['project_name']:
        st.markdown("---")
        st.markdown('<h2 class="sub-header">Project Status</h2>', unsafe_allow_html=True)
        
        progress_data = calculate_completion_status()
        area = st.session_state.project_data.get('area', 0)
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Overall Progress", f"{progress_data['overall']}%")
        with col2:
            st.metric("Modules Completed", f"{progress_data['completed']}/8")
        with col3:
            st.metric("Project Area", f"{area:.2f} ha")
        with col4:
            if 'last_updated' in st.session_state.project_data:
                st.metric("Last Updated", st.session_state.project_data['last_updated'].split()[0])
        
        # Progress bar
        st.progress(progress_data['overall'] / 100)


# =============================================================================
# FIELD LAYOUT WORKFLOW TAB (NEW FEATURE)
# =============================================================================

def show_field_layout_workflow_tab():
    """
    Field Layout Workflow - Draw field boundary, create crop blocks, assign irrigation.
    This is the main new feature for multi-block crop management.
    """
    st.markdown('<h2 class="sub-header">🗺️ Field Layout Workflow</h2>', unsafe_allow_html=True)
    
    if not FIELD_LAYOUT_AVAILABLE:
        st.error("Field Layout Manager module not available. Please check installation.")
        return
    
    # Initialize field layout state
    field_layout = flm.initialize_field_layout_state()
    workflow_step = flm.get_workflow_step()
    
    # =========================================================================
    # WORKFLOW PROGRESS INDICATOR
    # =========================================================================
    show_workflow_progress(workflow_step)
    
    st.markdown("---")
    
    # =========================================================================
    # WORKFLOW STEPS - Sub-tabs for each step
    # =========================================================================
    step_tabs = st.tabs([
        "1️⃣ Draw Field Boundary",
        "2️⃣ Mark Water Source",
        "3️⃣ Create Crop Blocks",
        "4️⃣ Assign Irrigation",
        "5️⃣ Review & Continue"
    ])
    
    with step_tabs[0]:
        show_draw_boundary_step()
    
    with step_tabs[1]:
        show_water_source_step()
    
    with step_tabs[2]:
        show_create_blocks_step()
    
    with step_tabs[3]:
        show_assign_irrigation_step()
    
    with step_tabs[4]:
        show_review_step()


def show_workflow_progress(current_step: str):
    """Display workflow progress indicator."""
    steps = [
        ('draw_boundary', 'Draw Boundary', '📐'),
        ('mark_water_source', 'Water Source', '💧'),
        ('create_blocks', 'Create Blocks', '🌱'),
        ('assign_irrigation', 'Assign Irrigation', '🚿'),
        ('ready_for_design', 'Ready', '✅')
    ]
    
    step_index = next((i for i, s in enumerate(steps) if s[0] == current_step), 0)
    
    cols = st.columns(5)
    for i, (step_id, step_name, icon) in enumerate(steps):
        with cols[i]:
            if i < step_index:
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; background: #28a745; border-radius: 8px; color: white;">
                    <div style="font-size: 1.5em;">✓</div>
                    <div style="font-size: 0.8em;">{step_name}</div>
                </div>
                """, unsafe_allow_html=True)
            elif i == step_index:
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; background: #007bff; border-radius: 8px; color: white;">
                    <div style="font-size: 1.5em;">{icon}</div>
                    <div style="font-size: 0.8em; font-weight: bold;">{step_name}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="text-align: center; padding: 10px; background: #6c757d; border-radius: 8px; color: white; opacity: 0.5;">
                    <div style="font-size: 1.5em;">{icon}</div>
                    <div style="font-size: 0.8em;">{step_name}</div>
                </div>
                """, unsafe_allow_html=True)


def show_draw_boundary_step():
    """Step 1: Draw main field boundary."""
    st.markdown("### 📐 Draw Main Field Boundary")
    
    field_layout = flm.get_field_layout()
    
    # Show existing boundary info at the top if already defined
    if field_layout.get('main_boundary') or field_layout.get('main_boundary_local'):
        st.success("✅ **Field Boundary Already Defined**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Area", f"{field_layout.get('total_area_ha', 0):.2f} ha")
        with col2:
            bbox = flm.calculate_bounding_box(field_layout.get('main_boundary_local', []))
            st.metric("Length (N-S)", f"{bbox.get('height', 0):.1f} m")
        with col3:
            st.metric("Width (E-W)", f"{bbox.get('width', 0):.1f} m")
        
        # Show source info if from CAD
        field_geometry = st.session_state.project_data.get('field_geometry', {})
        if field_geometry.get('source') == 'cad_file':
            st.info(f"📁 Imported from: **{field_geometry.get('source_file', 'CAD file')}** (Layer: {field_geometry.get('source_layer', 'unknown')})")
        
        if st.button("🗑️ Clear Boundary & Start Over", key="clear_boundary_top"):
            field_layout['main_boundary'] = None
            field_layout['main_boundary_local'] = None
            field_layout['total_area_ha'] = 0
            if 'field_geometry' in st.session_state.project_data:
                del st.session_state.project_data['field_geometry']
            flm.set_workflow_step('draw_boundary')
            st.rerun()
        
        st.markdown("---")
    
    # Choose input method - Tabs for Draw vs Upload
    input_method_tabs = st.tabs(["🗺️ Draw on Map", "📁 Upload AutoCAD File"])
    
    # TAB 1: Draw on Map
    with input_method_tabs[0]:
        st.markdown("""
        <div style="background-color: #e8f4f8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB;">
        <b>Instructions:</b>
        <ol>
            <li>Search for your location or navigate to your field area</li>
            <li>Use the polygon draw tool to outline your main field boundary</li>
            <li>Click to place points, double-click to complete the polygon</li>
            <li>The system will calculate the field area automatically</li>
        </ol>
        </div>
        """, unsafe_allow_html=True)
        
        if MAP_AVAILABLE:
            col1, col2 = st.columns([2, 1])
            
            with col2:
                st.markdown("#### Map Settings")
                
                search_location = st.text_input(
                    "Search Location",
                    value=st.session_state.project_data.get('location', 'Pretoria, South Africa'),
                    help="Enter city, region, or coordinates",
                    key="boundary_location_search"
                )
                
                if st.button("🔍 Find Location", key="find_boundary_location"):
                    coords = geocode_location(search_location)
                    if coords:
                        st.session_state.project_data['map_center'] = coords
                        st.session_state.project_data['map_zoom'] = 15
                        st.success(f"✅ Location found!")
                        st.rerun()
                
                # Show current boundary info in sidebar
                if field_layout.get('main_boundary') and not field_layout.get('main_boundary_local'):
                    st.markdown("#### ✅ Boundary Defined")
                    st.metric("Total Area", f"{field_layout.get('total_area_ha', 0):.2f} ha")
                    
                    bbox = flm.calculate_bounding_box(field_layout.get('main_boundary_local', []))
                    st.metric("Length (N-S)", f"{bbox.get('height', 0):.1f} m")
                    st.metric("Width (E-W)", f"{bbox.get('width', 0):.1f} m")
                    
                    if st.button("🗑️ Clear Boundary & Redraw", key="clear_boundary"):
                        field_layout['main_boundary'] = None
                        field_layout['main_boundary_local'] = None
                        field_layout['total_area_ha'] = 0
                        flm.set_workflow_step('draw_boundary')
                        st.rerun()
                elif not field_layout.get('main_boundary'):
                    st.info("Draw a polygon on the map to define your field boundary.")
            
            with col1:
                show_boundary_drawing_map()
        else:
            st.warning("Interactive map not available. Using manual input.")
            show_manual_boundary_input()
    
    # TAB 2: Upload CAD File
    with input_method_tabs[1]:
        if DWG_HANDLER_AVAILABLE and dwg_handler:
            result = dwg_handler.show_dwg_upload_section(key_prefix="field_layout")
            if result:
                # Update field_layout from the imported CAD data
                field_layout['main_boundary'] = result.get('boundary')
                field_layout['main_boundary_local'] = result.get('local_polygon')
                field_layout['total_area_ha'] = result.get('area_ha', 0)
                field_layout['workflow_step'] = 'mark_water_source'
                field_layout['updated_at'] = result.get('imported_at')
                st.rerun()
        else:
            st.warning("""
            ⚠️ **AutoCAD file support requires the `ezdxf` library.**
            
            To enable CAD file import, install the library:
            ```bash
            pip install ezdxf
            ```
            
            **Supported formats:**
            - **.DXF** - Direct support (recommended)
            - **.DWG** - Requires conversion to DXF first
            """)
            
            # Still show manual input as fallback
            st.markdown("---")
            st.markdown("### 📝 Or enter coordinates manually")
            show_manual_boundary_input()
    
    # Navigation
    can_proceed, reason = flm.can_proceed_to_next_step() if flm.get_workflow_step() == 'draw_boundary' else (field_layout.get('main_boundary') is not None or field_layout.get('main_boundary_local') is not None, "")
    
    if field_layout.get('main_boundary') or field_layout.get('main_boundary_local'):
        if st.button("✅ Boundary Complete → Next Step", type="primary", key="boundary_next"):
            flm.set_workflow_step('mark_water_source')
            st.success("Boundary saved! Proceed to mark water source.")
            st.rerun()


def show_water_source_step():
    """Step 2: Mark water source location."""
    st.markdown("### 💧 Mark Water Source Location")
    
    field_layout = flm.get_field_layout()
    
    # Check for either GPS or local boundary (CAD imports may only have local coords)
    has_boundary = field_layout.get('main_boundary') or field_layout.get('main_boundary_local')
    
    if not has_boundary:
        st.warning("⚠️ Please complete Step 1 (Draw Field Boundary) first.")
        return
    
    # Check if this is a CAD import without GPS coordinates
    is_cad_import_without_gps = field_layout.get('main_boundary_local') and not field_layout.get('main_boundary')
    
    if is_cad_import_without_gps:
        st.info("""
        📁 **Field imported from CAD file (local coordinates)**
        
        Since the CAD file uses local coordinates, you can specify the water source position in meters 
        relative to the field origin (bottom-left corner).
        """)
        
        show_manual_water_source_for_cad(field_layout)
    else:
        st.markdown("""
        <div style="background-color: #e8f4f8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB;">
        <b>Instructions:</b>
        <ol>
            <li>Click the marker tool on the map</li>
            <li>Place a marker at your water source location (well, pump, reservoir, etc.)</li>
            <li>The water source can be inside or outside the field boundary</li>
        </ol>
        </div>
        """, unsafe_allow_html=True)
        
        if MAP_AVAILABLE:
            col1, col2 = st.columns([2, 1])
            
            with col2:
                st.markdown("#### Water Source Info")
                
                water_source_type = st.selectbox(
                    "Water Source Type",
                    options=['Well', 'Borehole', 'Reservoir', 'River', 'Canal', 'Municipal', 'Other'],
                    index=0,
                    key="water_source_type"
                )
                
                if field_layout.get('water_source'):
                    st.success("✅ Water source marked!")
                    ws = field_layout['water_source']
                    st.caption(f"📍 {ws[0]:.6f}, {ws[1]:.6f}")
                    
                    if st.button("🗑️ Remove Water Source", key="clear_water_source"):
                        field_layout['water_source'] = None
                        field_layout['water_source_local'] = None
                        st.rerun()
                else:
                    st.info("Click on the map to mark your water source location.")
            
            with col1:
                show_water_source_map()
        else:
            show_manual_water_source_input()
    
    # Navigation
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← Back to Boundary", key="ws_back"):
            flm.set_workflow_step('draw_boundary')
            st.rerun()
    
    with col_nav2:
        # Allow proceeding with or without water source (for CAD imports, water_source_local suffices)
        has_water_source = field_layout.get('water_source') or field_layout.get('water_source_local')
        if has_water_source:
            if st.button("✅ Water Source Complete → Next", type="primary", key="ws_next"):
                flm.set_workflow_step('create_blocks')
                st.success("Water source saved! Proceed to create crop blocks.")
                st.rerun()
        else:
            st.button("Skip (optional)", key="ws_skip", on_click=lambda: flm.set_workflow_step('create_blocks'))


def show_manual_water_source_for_cad(field_layout):
    """
    Manual water source input for CAD-imported fields without GPS coordinates.
    Allows specifying water source in local meter coordinates.
    """
    st.markdown("#### Water Source Location (Local Coordinates)")
    
    # Get field bounding box for reference
    local_polygon = field_layout.get('main_boundary_local', [])
    if local_polygon:
        xs = [p[0] for p in local_polygon]
        ys = [p[1] for p in local_polygon]
        max_x = max(xs) if xs else 500
        max_y = max(ys) if ys else 500
    else:
        max_x, max_y = 500, 500
    
    col1, col2 = st.columns(2)
    
    with col1:
        water_source_type = st.selectbox(
            "Water Source Type",
            options=['Well', 'Borehole', 'Reservoir', 'River', 'Canal', 'Municipal', 'Other'],
            index=0,
            key="water_source_type_cad"
        )
    
    with col2:
        st.info(f"Field dimensions: {max_x:.0f}m × {max_y:.0f}m")
    
    col1, col2 = st.columns(2)
    
    # Current water source values
    current_ws = field_layout.get('water_source_local', [0, 0])
    
    with col1:
        ws_x = st.number_input(
            "X Position (meters from left edge)",
            min_value=-100.0,
            max_value=max_x + 100,
            value=float(current_ws[0] if current_ws else 0),
            step=1.0,
            key="ws_x_local"
        )
    
    with col2:
        ws_y = st.number_input(
            "Y Position (meters from bottom edge)",
            min_value=-100.0,
            max_value=max_y + 100,
            value=float(current_ws[1] if current_ws else 0),
            step=1.0,
            key="ws_y_local"
        )
    
    if st.button("💾 Set Water Source Location", key="set_ws_local"):
        field_layout['water_source_local'] = [ws_x, ws_y]
        # Also update in field_geometry
        if 'field_geometry' in st.session_state.project_data:
            st.session_state.project_data['field_geometry']['water_source_local'] = [ws_x, ws_y]
        st.success(f"✅ Water source set at ({ws_x:.1f}m, {ws_y:.1f}m)")
        st.rerun()
    
    if field_layout.get('water_source_local'):
        ws = field_layout['water_source_local']
        st.success(f"✅ Current water source: ({ws[0]:.1f}m, {ws[1]:.1f}m)")


def show_create_blocks_step():
    """Step 3: Create internal crop/tree blocks."""
    st.markdown("### 🌱 Create Crop/Tree Blocks")
    
    field_layout = flm.get_field_layout()
    
    # Check for either GPS or local boundary (CAD imports may only have local coords)
    has_boundary = field_layout.get('main_boundary') or field_layout.get('main_boundary_local')
    
    if not has_boundary:
        st.warning("⚠️ Please complete Step 1 (Draw Field Boundary) first.")
        return
    
    st.markdown("""
    <div style="background-color: #e8f4f8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB;">
    <b>Create Internal Crop Blocks:</b>
    <ul>
        <li>Each block represents a distinct crop or tree zone within your field</li>
        <li>Draw polygons inside the main field boundary</li>
        <li>Assign crop type and optional name to each block</li>
        <li>Different blocks can have different irrigation systems</li>
    </ul>
    <b>Example:</b> A farm might have Mango trees (8 ha), Apple orchard (6 ha), and Vegetable plots (10 ha).
    </div>
    """, unsafe_allow_html=True)
    
    # Existing blocks summary
    blocks = field_layout.get('crop_blocks', [])
    if blocks:
        st.markdown("#### 📊 Existing Blocks")
        
        block_data = []
        for block in blocks:
            block_data.append({
                'ID': block['id'],
                'Name': block['name'],
                'Crop': block['crop_name'],
                'Area (ha)': f"{block.get('area_ha', 0):.2f}",
                'Irrigation': block.get('irrigation_system', 'Not assigned'),
                'Color': block['color']
            })
        
        # Display as colored cards
        cols = st.columns(min(3, len(blocks)))
        for i, block in enumerate(blocks):
            with cols[i % 3]:
                irrigation_icon = '💧' if block.get('irrigation_system') == 'drip' else '🌧️' if block.get('irrigation_system') == 'sprinkler' else '❓'
                st.markdown(f"""
                <div style="background: {block['color']}33; border: 2px solid {block['color']}; padding: 15px; border-radius: 10px; margin-bottom: 10px;">
                    <h4 style="margin: 0; color: {block['color']};">{block['name']}</h4>
                    <p style="margin: 5px 0;">🌱 {block['crop_name']}</p>
                    <p style="margin: 5px 0;">📐 {block.get('area_ha', 0):.2f} ha</p>
                    <p style="margin: 5px 0;">{irrigation_icon} {block.get('irrigation_system', 'Not assigned')}</p>
                </div>
                """, unsafe_allow_html=True)
        
        total_block_area = sum(b.get('area_ha', 0) for b in blocks)
        st.metric("Total Block Area", f"{total_block_area:.2f} ha", 
                  delta=f"{total_block_area - field_layout.get('total_area_ha', 0):.2f} ha" if field_layout.get('total_area_ha') else None)
    
    st.markdown("---")
    
    # Add new block interface
    st.markdown("#### ➕ Add New Block")
    
    add_block_method = st.radio(
        "How would you like to add a block?",
        ["🗺️ Draw on Map", "📝 Manual Entry"],
        horizontal=True,
        key="add_block_method"
    )
    
    if add_block_method == "🗺️ Draw on Map" and MAP_AVAILABLE:
        show_block_drawing_interface()
    else:
        show_manual_block_entry()
    
    # Block management
    if blocks:
        st.markdown("---")
        st.markdown("#### 🔧 Manage Blocks")
        
        col1, col2 = st.columns(2)
        with col1:
            block_to_delete = st.selectbox(
                "Select block to delete",
                options=[f"{b['id']}: {b['name']}" for b in blocks],
                key="delete_block_select"
            )
        with col2:
            if st.button("🗑️ Delete Selected Block", type="secondary", key="delete_block_btn"):
                block_id = int(block_to_delete.split(':')[0])
                flm.delete_crop_block(block_id)
                st.success(f"Block deleted!")
                st.rerun()
    
    # Navigation
    st.markdown("---")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← Back to Water Source", key="blocks_back"):
            flm.set_workflow_step('mark_water_source')
            st.rerun()
    
    with col_nav2:
        if blocks:
            if st.button("✅ Blocks Complete → Assign Irrigation", type="primary", key="blocks_next"):
                flm.set_workflow_step('assign_irrigation')
                st.rerun()
        else:
            st.info("Add at least one crop block to continue.")


def show_assign_irrigation_step():
    """Step 4: Assign irrigation system type to each block."""
    st.markdown("### 🚿 Assign Irrigation System Type")
    
    field_layout = flm.get_field_layout()
    blocks = field_layout.get('crop_blocks', [])
    
    if not blocks:
        st.warning("⚠️ Please create crop blocks in Step 3 first.")
        return
    
    st.markdown("""
    <div style="background-color: #e8f4f8; padding: 15px; border-radius: 8px; border-left: 4px solid #2E86AB;">
    <b>Choose Irrigation System for Each Block:</b>
    <ul>
        <li><b>💧 Drip Irrigation:</b> Best for trees, orchards, vineyards, vegetables. High efficiency (90%)</li>
        <li><b>🌧️ Sprinkler Irrigation:</b> Best for field crops, grass, large uniform areas. Efficiency (75%)</li>
    </ul>
    The system will recommend the best option based on crop type.
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Quick assign options
    st.markdown("#### Quick Assign")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("💧 All Drip", width="stretch", key="all_drip"):
            for block in blocks:
                flm.update_crop_block(block['id'], {'irrigation_system': 'drip'})
            st.success("All blocks set to Drip Irrigation")
            st.rerun()
    
    with col2:
        if st.button("🌧️ All Sprinkler", width="stretch", key="all_sprinkler"):
            for block in blocks:
                flm.update_crop_block(block['id'], {'irrigation_system': 'sprinkler'})
            st.success("All blocks set to Sprinkler Irrigation")
            st.rerun()
    
    with col3:
        if st.button("🎯 Auto (Recommended)", width="stretch", key="auto_assign"):
            for block in blocks:
                recommended = block.get('recommended_irrigation', ['drip'])
                flm.update_crop_block(block['id'], {'irrigation_system': recommended[0]})
            st.success("Irrigation assigned based on crop recommendations")
            st.rerun()
    
    st.markdown("---")
    st.markdown("#### Individual Block Assignment")
    
    # Individual assignment for each block
    for block in blocks:
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            st.markdown(f"""
            <div style="background: {block['color']}33; padding: 10px; border-radius: 8px; border-left: 4px solid {block['color']};">
                <b>{block['name']}</b><br>
                🌱 {block['crop_name']} | 📐 {block.get('area_ha', 0):.2f} ha
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            # Show recommendation
            recommended = block.get('recommended_irrigation', ['drip', 'sprinkler'])
            rec_text = f"Recommended: {', '.join(recommended)}"
            
            current_system = block.get('irrigation_system', recommended[0] if recommended else 'drip')
            irrigation_options = ['drip', 'sprinkler']
            current_index = irrigation_options.index(current_system) if current_system in irrigation_options else 0
            
            new_system = st.selectbox(
                f"Irrigation for {block['name']}",
                options=['💧 Drip', '🌧️ Sprinkler'],
                index=current_index,
                key=f"irrigation_{block['id']}",
                help=rec_text,
                label_visibility="collapsed"
            )
        
        with col3:
            # Save button
            system_value = 'drip' if 'Drip' in new_system else 'sprinkler'
            if system_value != block.get('irrigation_system'):
                if st.button("💾", key=f"save_irr_{block['id']}", help="Save selection"):
                    flm.update_crop_block(block['id'], {'irrigation_system': system_value})
                    st.rerun()
            else:
                st.markdown("✓")
    
    # Summary
    st.markdown("---")
    st.markdown("#### 📊 Assignment Summary")
    
    drip_blocks = [b for b in blocks if b.get('irrigation_system') == 'drip']
    sprinkler_blocks = [b for b in blocks if b.get('irrigation_system') == 'sprinkler']
    unassigned_blocks = [b for b in blocks if not b.get('irrigation_system')]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        drip_area = sum(b.get('area_ha', 0) for b in drip_blocks)
        st.metric("💧 Drip Irrigation", f"{len(drip_blocks)} blocks", f"{drip_area:.2f} ha")
    with col2:
        sprinkler_area = sum(b.get('area_ha', 0) for b in sprinkler_blocks)
        st.metric("🌧️ Sprinkler Irrigation", f"{len(sprinkler_blocks)} blocks", f"{sprinkler_area:.2f} ha")
    with col3:
        unassigned_area = sum(b.get('area_ha', 0) for b in unassigned_blocks)
        st.metric("❓ Unassigned", f"{len(unassigned_blocks)} blocks", f"{unassigned_area:.2f} ha")
    
    # Navigation
    st.markdown("---")
    col_nav1, col_nav2 = st.columns(2)
    with col_nav1:
        if st.button("← Back to Blocks", key="irr_back"):
            flm.set_workflow_step('create_blocks')
            st.rerun()
    
    with col_nav2:
        if not unassigned_blocks:
            if st.button("✅ Complete → Review & Continue", type="primary", key="irr_next"):
                flm.set_workflow_step('ready_for_design')
                # Sync data to project
                flm.sync_to_project_data()
                st.success("Field layout complete! Review and proceed to design.")
                st.rerun()
        else:
            st.warning(f"Please assign irrigation to all {len(unassigned_blocks)} unassigned block(s).")


def show_review_step():
    """Step 5: Review field layout and proceed to design."""
    st.markdown("### ✅ Review Field Layout")
    
    field_layout = flm.get_field_layout()
    summary = flm.get_field_layout_summary()
    
    if not summary['total_blocks']:
        st.warning("⚠️ Please complete the previous steps to create your field layout.")
        return
    
    # Success banner
    st.success(f"""
    🎉 **Field Layout Complete!**
    
    Your field is ready for irrigation design. The system has captured:
    - **Total Field Area:** {summary['total_field_area_ha']:.2f} ha
    - **Crop Blocks:** {summary['total_blocks']} blocks covering {summary['total_block_area_ha']:.2f} ha
    - **Crops:** {', '.join(summary['crops'])}
    """)
    
    # Visual summary
    st.markdown("---")
    st.markdown("#### 📊 Layout Summary")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 💧 Drip Irrigation Blocks")
        if summary['drip_blocks_count'] > 0:
            drip_blocks = flm.get_blocks_by_irrigation_type('drip')
            for block in drip_blocks:
                st.markdown(f"""
                <div style="background: {block['color']}33; padding: 10px; border-radius: 8px; margin: 5px 0; border-left: 4px solid {block['color']};">
                    <b>{block['name']}</b> - {block['crop_name']}<br>
                    📐 {block.get('area_ha', 0):.2f} ha | 💧 {block.get('emitter_type', 'TBD')}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No drip irrigation blocks defined.")
    
    with col2:
        st.markdown("##### 🌧️ Sprinkler Irrigation Blocks")
        if summary['sprinkler_blocks_count'] > 0:
            sprinkler_blocks = flm.get_blocks_by_irrigation_type('sprinkler')
            for block in sprinkler_blocks:
                st.markdown(f"""
                <div style="background: {block['color']}33; padding: 10px; border-radius: 8px; margin: 5px 0; border-left: 4px solid {block['color']};">
                    <b>{block['name']}</b> - {block['crop_name']}<br>
                    📐 {block.get('area_ha', 0):.2f} ha
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("No sprinkler irrigation blocks defined.")
    
    # Field visualization
    st.markdown("---")
    st.markdown("#### 🗺️ Field Layout Visualization")
    show_field_layout_visualization()
    
    # Next steps
    st.markdown("---")
    st.markdown("#### 🚀 Next Steps")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if summary['drip_blocks_count'] > 0:
            st.markdown("""
            <div style="background: #d4edda; padding: 15px; border-radius: 10px; border-left: 4px solid #28a745;">
                <h4 style="color: #155724; margin: 0;">💧 Drip Irrigation Design</h4>
                <p style="color: #155724;">
                    Go to <b>Drip Irrigation</b> menu to:
                    <ul>
                        <li>Calculate water requirements</li>
                        <li>Select emitters</li>
                        <li>Design pipe network</li>
                        <li>Generate BOQ</li>
                    </ul>
                </p>
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        if summary['sprinkler_blocks_count'] > 0:
            st.markdown("""
            <div style="background: #cce5ff; padding: 15px; border-radius: 10px; border-left: 4px solid #004085;">
                <h4 style="color: #004085; margin: 0;">🌧️ Sprinkler Irrigation Design</h4>
                <p style="color: #004085;">
                    Go to <b>Sprinkler Irrigation</b> menu to:
                    <ul>
                        <li>Calculate crop water needs</li>
                        <li>Select sprinklers</li>
                        <li>Design hydraulics</li>
                        <li>Generate reports</li>
                    </ul>
                </p>
            </div>
            """, unsafe_allow_html=True)
    
    # Edit option
    st.markdown("---")
    if st.button("✏️ Edit Field Layout", key="edit_layout"):
        flm.set_workflow_step('draw_boundary')
        st.rerun()
    
    # Export option
    with st.expander("📥 Export Field Layout Data"):
        json_data = flm.export_field_layout_to_json()
        st.download_button(
            label="Download JSON",
            data=json_data,
            file_name="field_layout.json",
            mime="application/json"
        )


# =============================================================================
# MAP DRAWING FUNCTIONS
# =============================================================================

def safe_st_folium(m, width=700, height=500, returned_objects=None, key=None):
    """
    Wrapper for st_folium with error handling for Streamlit Cloud compatibility.
    Returns map_data or None if component fails to load.
    """
    if returned_objects is None:
        returned_objects = ["all_drawings"]
    
    # Check if st_folium is available
    if st_folium is None:
        st.error("""
        ⚠️ **Map component not available**
        
        The map library (streamlit-folium) is not loaded. This can happen on cloud deployments.
        
        **Workarounds:**
        1. **Refresh the page** multiple times
        2. Use **Manual Coordinate Input** below
        3. Contact your administrator to check server configuration
        """)
        
        # Show manual input alternative
        with st.expander("📝 Manual Coordinate Input (Alternative)", expanded=True):
            st.info("Enter coordinates manually if the map is unavailable:")
            col1, col2 = st.columns(2)
            with col1:
                manual_lat = st.number_input("Latitude", value=0.0, format="%.6f", key=f"{key}_manual_lat")
            with col2:
                manual_lon = st.number_input("Longitude", value=0.0, format="%.6f", key=f"{key}_manual_lon")
            st.caption("Example: Cairo (30.0444, 31.2357), Rome (41.9028, 12.4964)")
        return None
    
    try:
        map_data = st_folium(m, width=width, height=height, returned_objects=returned_objects, key=key)
        return map_data
    except Exception as e:
        error_msg = str(e)
        st.error(f"""
        ⚠️ **Map component failed to load**
        
        This is a known issue with cloud deployments due to network latency or proxy settings.
        
        **Please try:**
        1. **Refresh the page** (F5 or Ctrl+R)
        2. **Wait 10-15 seconds** and try again
        3. **Clear browser cache** and reload
        4. Use **Manual Input** mode below as an alternative
        
        *Technical: {error_msg[:150]}*
        """)
        
        # Show manual input alternative
        with st.expander("📝 Manual Coordinate Input (Alternative)", expanded=True):
            st.info("Enter coordinates manually while the map loads:")
            col1, col2 = st.columns(2)
            with col1:
                manual_lat = st.number_input("Latitude", value=0.0, format="%.6f", key=f"{key}_err_lat")
            with col2:
                manual_lon = st.number_input("Longitude", value=0.0, format="%.6f", key=f"{key}_err_lon")
        return None


def show_boundary_drawing_map():
    """Display map for drawing field boundary."""
    center = st.session_state.project_data.get('map_center', [-25.7479, 28.2293])
    zoom = st.session_state.project_data.get('map_zoom', 15)
    
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri WorldImagery'
    )
    
    # Add drawing tools for boundary
    draw = Draw(
        export=True,
        draw_options={
            'polyline': False,
            'rectangle': True,
            'polygon': True,
            'circle': False,
            'marker': False,
            'circlemarker': False
        },
        edit_options={'edit': True}
    )
    draw.add_to(m)
    
    # Show existing boundary
    field_layout = flm.get_field_layout()
    if field_layout.get('main_boundary'):
        folium.Polygon(
            locations=field_layout['main_boundary'],
            color='yellow',
            fill=True,
            fill_color='yellow',
            fill_opacity=0.3,
            popup='Main Field Boundary'
        ).add_to(m)
    
    # Display map with error handling for Streamlit Cloud
    map_data = safe_st_folium(m, width=700, height=500, returned_objects=["all_drawings"], key="boundary_map")
    
    # Process drawings
    if map_data and map_data.get('all_drawings'):
        process_boundary_drawing(map_data['all_drawings'])


def show_water_source_map():
    """Display map for marking water source."""
    field_layout = flm.get_field_layout()
    
    # Center on field if available
    if field_layout.get('main_boundary'):
        lats = [c[0] for c in field_layout['main_boundary']]
        lons = [c[1] for c in field_layout['main_boundary']]
        center = [(max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2]
    else:
        center = st.session_state.project_data.get('map_center', [-25.7479, 28.2293])
    
    m = folium.Map(
        location=center,
        zoom_start=16,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri WorldImagery'
    )
    
    # Draw field boundary
    if field_layout.get('main_boundary'):
        folium.Polygon(
            locations=field_layout['main_boundary'],
            color='yellow',
            fill=True,
            fill_color='yellow',
            fill_opacity=0.2,
            popup='Field Boundary'
        ).add_to(m)
    
    # Add marker drawing tool
    draw = Draw(
        export=False,
        draw_options={
            'polyline': False,
            'rectangle': False,
            'polygon': False,
            'circle': False,
            'marker': True,
            'circlemarker': False
        }
    )
    draw.add_to(m)
    
    # Show existing water source
    if field_layout.get('water_source'):
        folium.Marker(
            location=field_layout['water_source'],
            popup='<b>Water Source</b>',
            tooltip='Water Source',
            icon=folium.Icon(color='blue', icon='tint', prefix='fa')
        ).add_to(m)
    
    # Display map with error handling for Streamlit Cloud
    map_data = safe_st_folium(m, width=700, height=500, returned_objects=["all_drawings"], key="water_source_map")
    
    # Process drawings
    if map_data and map_data.get('all_drawings'):
        for drawing in map_data['all_drawings']:
            if drawing.get('geometry', {}).get('type') == 'Point':
                coords = drawing['geometry']['coordinates']
                water_source = [coords[1], coords[0]]  # [lat, lon]
                
                field_layout['water_source'] = water_source
                if field_layout.get('main_boundary'):
                    field_layout['water_source_local'] = flm.convert_point_gps_to_local(
                        water_source, field_layout['main_boundary']
                    )
                st.rerun()


def show_block_drawing_interface():
    """Interface for drawing crop blocks on map."""
    field_layout = flm.get_field_layout()
    
    if not field_layout.get('main_boundary'):
        st.warning("Please draw the main field boundary first.")
        return
    
    # Block details form
    col1, col2 = st.columns(2)
    
    with col1:
        block_name = st.text_input(
            "Block Name",
            value=f"Block {flm.get_next_block_id()}",
            key="new_block_name"
        )
        
        crop_options = list(flm.CROP_DATABASE.keys())
        crop_names = [flm.CROP_DATABASE[c]['name'] for c in crop_options]
        
        selected_crop_name = st.selectbox(
            "Crop Type",
            options=crop_names,
            key="new_block_crop"
        )
        selected_crop = crop_options[crop_names.index(selected_crop_name)]
    
    with col2:
        st.markdown("#### Crop Info")
        crop_info = flm.CROP_DATABASE[selected_crop]
        st.write(f"**Category:** {crop_info['category']}")
        st.write(f"**Recommended Irrigation:** {', '.join(crop_info['recommended_irrigation'])}")
        if crop_info.get('typical_spacing_m'):
            st.write(f"**Typical Spacing:** {crop_info['typical_spacing_m'][0]}m × {crop_info['typical_spacing_m'][1]}m")
    
    st.markdown("---")
    st.markdown("#### Draw Block on Map")
    st.info("Draw a polygon inside the field boundary to define this crop block.")
    
    # Map for drawing blocks
    lats = [c[0] for c in field_layout['main_boundary']]
    lons = [c[1] for c in field_layout['main_boundary']]
    center = [(max(lats) + min(lats)) / 2, (max(lons) + min(lons)) / 2]
    
    m = folium.Map(
        location=center,
        zoom_start=16,
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri WorldImagery'
    )
    
    # Draw field boundary
    folium.Polygon(
        locations=field_layout['main_boundary'],
        color='yellow',
        fill=True,
        fill_color='yellow',
        fill_opacity=0.1,
        popup='Field Boundary'
    ).add_to(m)
    
    # Draw existing blocks
    for block in field_layout.get('crop_blocks', []):
        if block.get('polygon_gps'):
            folium.Polygon(
                locations=block['polygon_gps'],
                color=block['color'],
                fill=True,
                fill_color=block['color'],
                fill_opacity=0.4,
                popup=f"{block['name']}: {block['crop_name']}"
            ).add_to(m)
    
    # Draw water source
    if field_layout.get('water_source'):
        folium.Marker(
            location=field_layout['water_source'],
            popup='Water Source',
            icon=folium.Icon(color='blue', icon='tint', prefix='fa')
        ).add_to(m)
    
    # Add drawing tools
    draw = Draw(
        export=True,
        draw_options={
            'polyline': False,
            'rectangle': True,
            'polygon': True,
            'circle': False,
            'marker': False,
            'circlemarker': False
        }
    )
    draw.add_to(m)
    
    # Display map with error handling for Streamlit Cloud
    map_data = safe_st_folium(m, width=700, height=500, returned_objects=["all_drawings"], key="block_drawing_map")
    
    # Process new block drawing
    if map_data and map_data.get('all_drawings'):
        for drawing in map_data['all_drawings']:
            geom_type = drawing.get('geometry', {}).get('type')
            if geom_type in ['Polygon', 'Rectangle']:
                coords = drawing['geometry']['coordinates'][0]
                polygon_gps = [[lat, lon] for lon, lat in coords]
                
                # Convert to local coordinates
                polygon_local = flm.convert_gps_to_local(polygon_gps, 
                    reference_point=[min(lats), min(lons)])
                
                # Create and add block
                new_block = flm.create_crop_block(
                    block_id=flm.get_next_block_id(),
                    name=block_name,
                    crop_type=selected_crop,
                    polygon_gps=polygon_gps,
                    polygon_local=polygon_local
                )
                
                if flm.add_crop_block(new_block):
                    st.success(f"✅ Block '{block_name}' added! Area: {new_block['area_ha']:.2f} ha")
                    st.rerun()


def show_manual_block_entry():
    """Manual entry form for crop blocks (when map not available)."""
    field_layout = flm.get_field_layout()
    
    st.markdown("#### Manual Block Entry")
    
    col1, col2 = st.columns(2)
    
    with col1:
        block_name = st.text_input(
            "Block Name",
            value=f"Block {flm.get_next_block_id()}",
            key="manual_block_name"
        )
        
        crop_options = list(flm.CROP_DATABASE.keys())
        crop_names = [flm.CROP_DATABASE[c]['name'] for c in crop_options]
        
        selected_crop_name = st.selectbox(
            "Crop Type",
            options=crop_names,
            key="manual_block_crop"
        )
        selected_crop = crop_options[crop_names.index(selected_crop_name)]
    
    with col2:
        block_area = st.number_input(
            "Block Area (ha)",
            min_value=0.1,
            max_value=1000.0,
            value=1.0,
            step=0.1,
            key="manual_block_area"
        )
        
        block_notes = st.text_area(
            "Notes (optional)",
            key="manual_block_notes",
            height=68
        )
    
    # Create simple rectangular polygon based on area
    # Assume field origin at (0,0) and stack blocks vertically
    existing_blocks = field_layout.get('crop_blocks', [])
    y_offset = sum(b.get('area_ha', 0) * 100 for b in existing_blocks)  # Simple stacking
    
    # Estimate dimensions (square root approach)
    side = (block_area * 10000) ** 0.5  # Convert ha to m²
    
    polygon_local = [
        [0, y_offset],
        [side, y_offset],
        [side, y_offset + side],
        [0, y_offset + side],
        [0, y_offset]
    ]
    
    if st.button("➕ Add Block", type="primary", key="add_manual_block"):
        new_block = flm.create_crop_block(
            block_id=flm.get_next_block_id(),
            name=block_name,
            crop_type=selected_crop,
            polygon_gps=[],  # No GPS for manual entry
            polygon_local=polygon_local,
            notes=block_notes
        )
        new_block['area_ha'] = block_area  # Override calculated area
        
        if flm.add_crop_block(new_block):
            st.success(f"✅ Block '{block_name}' added!")
            st.rerun()


def show_manual_boundary_input():
    """Manual boundary input when map not available."""
    st.markdown("#### Manual Field Dimensions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        field_length = st.number_input(
            "Field Length (m)",
            min_value=10.0,
            max_value=5000.0,
            value=500.0,
            step=10.0,
            key="manual_field_length"
        )
    
    with col2:
        field_width = st.number_input(
            "Field Width (m)",
            min_value=10.0,
            max_value=5000.0,
            value=400.0,
            step=10.0,
            key="manual_field_width"
        )
    
    area_ha = (field_length * field_width) / 10000
    st.metric("Calculated Area", f"{area_ha:.2f} ha")
    
    if st.button("💾 Save Field Dimensions", type="primary", key="save_manual_boundary"):
        field_layout = flm.get_field_layout()
        
        # Create rectangular boundary in local coordinates
        polygon_local = [
            [0, 0],
            [field_width, 0],
            [field_width, field_length],
            [0, field_length],
            [0, 0]
        ]
        
        field_layout['main_boundary_local'] = polygon_local
        field_layout['total_area_ha'] = area_ha
        
        # Update project data
        st.session_state.project_data['field_geometry'] = {
            'length_m': field_length,
            'width_m': field_width,
            'area_ha': area_ha,
            'area_m2': field_length * field_width,
            'local_polygon': polygon_local
        }
        st.session_state.project_data['area'] = area_ha
        
        flm.set_workflow_step('mark_water_source')
        st.success("✅ Field dimensions saved!")
        st.rerun()


def show_manual_water_source_input():
    """Manual water source input when map not available."""
    st.markdown("#### Water Source Location")
    
    water_source_position = st.selectbox(
        "Water Source Position",
        options=['Corner (SW)', 'Corner (SE)', 'Corner (NW)', 'Corner (NE)', 
                 'Side (South)', 'Side (North)', 'Side (East)', 'Side (West)',
                 'Center', 'Outside Field'],
        key="manual_ws_position"
    )
    
    if st.button("💾 Save Water Source", type="primary", key="save_manual_ws"):
        field_layout = flm.get_field_layout()
        field_layout['water_source_position'] = water_source_position
        flm.set_workflow_step('create_blocks')
        st.success("✅ Water source position saved!")
        st.rerun()


def process_boundary_drawing(drawings):
    """Process boundary polygon from map drawings."""
    for drawing in drawings:
        geom_type = drawing.get('geometry', {}).get('type')
        if geom_type in ['Polygon', 'Rectangle']:
            coords = drawing['geometry']['coordinates'][0]
            boundary_gps = [[lat, lon] for lon, lat in coords]
            
            # Calculate dimensions
            field_layout = flm.get_field_layout()
            
            # Convert to local coordinates
            boundary_local = flm.convert_gps_to_local(boundary_gps)
            
            # Calculate area
            area_ha = flm.calculate_polygon_area(boundary_local)
            
            # Store in field layout
            field_layout['main_boundary'] = boundary_gps
            field_layout['main_boundary_local'] = boundary_local
            field_layout['total_area_ha'] = area_ha
            field_layout['created_at'] = datetime.now().isoformat()
            
            # Also update project data
            bbox = flm.calculate_bounding_box(boundary_local)
            st.session_state.project_data['field_geometry'] = {
                'boundary': boundary_gps,
                'local_polygon': boundary_local,
                'area_ha': area_ha,
                'length_m': bbox['height'],
                'width_m': bbox['width']
            }
            st.session_state.project_data['area'] = area_ha
            
            st.rerun()


def show_field_layout_visualization():
    """Display visualization of field layout with blocks."""
    field_layout = flm.get_field_layout()
    
    if not field_layout.get('crop_blocks'):
        st.info("No blocks to visualize yet.")
        return
    
    def hex_to_rgba(hex_color, alpha=0.25):
        """Convert hex color to rgba string for Plotly."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
            return f'rgba({r}, {g}, {b}, {alpha})'
        return f'rgba(100, 100, 100, {alpha})'
    
    try:
        import plotly.graph_objects as go
        
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
        for block in field_layout.get('crop_blocks', []):
            if block.get('polygon_local'):
                polygon = block['polygon_local']
                xs = [p[0] for p in polygon]
                ys = [p[1] for p in polygon]
                
                # Convert hex color to rgba for fill
                fill_color = hex_to_rgba(block['color'], 0.25)
                
                fig.add_trace(go.Scatter(
                    x=xs + [xs[0]],
                    y=ys + [ys[0]],
                    mode='lines',
                    line=dict(color=block['color'], width=2),
                    name=f"{block['name']} ({block['crop_name']})",
                    fill='toself',
                    fillcolor=fill_color
                ))
                
                # Add label
                centroid = flm.get_polygon_centroid(polygon)
                irr_icon = '💧' if block.get('irrigation_system') == 'drip' else '🌧️'
                fig.add_annotation(
                    x=centroid[0],
                    y=centroid[1],
                    text=f"<b>{block['name']}</b><br>{block['crop_name']}<br>{irr_icon}",
                    showarrow=False,
                    font=dict(size=10)
                )
        
        # Draw water source
        if field_layout.get('water_source_local'):
            ws = field_layout['water_source_local']
            fig.add_trace(go.Scatter(
                x=[ws[0]],
                y=[ws[1]],
                mode='markers',
                marker=dict(size=15, color='blue', symbol='diamond'),
                name='Water Source'
            ))
        
        fig.update_layout(
            title='Field Layout',
            xaxis_title='Width (m)',
            yaxis_title='Length (m)',
            showlegend=True,
            height=500,
            yaxis_scaleanchor="x",
            yaxis_scaleratio=1
        )
        
        st.plotly_chart(fig, width="stretch")
        
    except ImportError:
        st.warning("Plotly not available for visualization.")


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def calculate_completion_status():
    """Calculate project completion status"""
    completed = 0
    total_modules = 8
    
    # Check each module for data
    checks = [
        bool(st.session_state.project_data.get('project_name')),
        bool(st.session_state.project_data.get('irrigation_requirements')),
        bool(st.session_state.project_data.get('sprinkler_data')),
        bool(st.session_state.project_data.get('hydraulic_design')),
        bool(st.session_state.project_data.get('pipe_network')),
        bool(st.session_state.project_data.get('pump_data')),
        bool(st.session_state.project_data.get('layout_data')),
        bool(st.session_state.project_data.get('cost_data'))
    ]
    
    completed = sum(checks)
    overall = int((completed / total_modules) * 100)
    
    return {
        'overall': overall,
        'completed': completed,
        'total': total_modules
    }


def show_interactive_map():
    """Interactive map for field delineation"""
    st.markdown("""
    <div class="info-box">
    <strong>Instructions:</strong>
    <ol>
        <li>Enter your location or use the map to navigate</li>
        <li>Click "Draw Field" and click points on the map to draw your field boundary</li>
        <li>Mark your water source location</li>
        <li>System will automatically calculate field dimensions</li>
    </ol>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.markdown("#### Map Settings")
        
        # Location search
        search_location = st.text_input(
            "Search Location",
            value=st.session_state.project_data.get('location', 'Pretoria, South Africa'),
            help="Enter city, region, or coordinates"
        )
        
        if st.button("🔍 Find Location"):
            coords = geocode_location(search_location)
            if coords:
                st.session_state.project_data['map_center'] = coords
                st.session_state.project_data['map_zoom'] = 15
                st.success(f"✅ Location found: {coords[0]:.4f}, {coords[1]:.4f}")
                st.rerun()
        
        # Get saved field data
        field_data = st.session_state.project_data.get('field_geometry', {})
        
        # Zoom to field button
        if field_data.get('boundary'):
            if st.button("🎯 Zoom to Field"):
                # Calculate field center
                lats = [coord[0] for coord in field_data['boundary']]
                lons = [coord[1] for coord in field_data['boundary']]
                center_lat = (max(lats) + min(lats)) / 2
                center_lon = (max(lons) + min(lons)) / 2
                st.session_state.project_data['map_center'] = [center_lat, center_lon]
                st.session_state.project_data['map_zoom'] = 16
                st.rerun()
        
        if field_data:
            st.markdown("#### Field Information")
            st.metric("Field Area", f"{field_data.get('area_ha', 0):.2f} ha")
            
            # Show dimensions with orientation
            length = field_data.get('length_m', 0)
            width = field_data.get('width_m', 0)
            st.metric("Field Length (N-S)", f"{length:.1f} m", help="North-South dimension (vertical on map)")
            st.metric("Field Width (E-W)", f"{width:.1f} m", help="East-West dimension (horizontal on map)")
            
            if field_data.get('water_source'):
                st.success("✅ Water source marked")
                ws = field_data['water_source']
                st.caption(f"📍 {ws[0]:.6f}, {ws[1]:.6f}")
            
            # Clear field button
            if st.button("🗑️ Clear Field & Redraw"):
                if 'field_geometry' in st.session_state.project_data:
                    del st.session_state.project_data['field_geometry']
                st.rerun()
    
    with col1:
        # Get map center and zoom
        center = st.session_state.project_data.get('map_center', [-25.7479, 28.2293])  # Default: Pretoria
        zoom = st.session_state.project_data.get('map_zoom', 15)
        
        # Create map
        m = folium.Map(
            location=center,
            zoom_start=zoom,
            tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
            attr='Esri WorldImagery'
        )
        
        # Add drawing tools
        draw = folium.plugins.Draw(
            export=True,
            draw_options={
                'polyline': False,
                'rectangle': True,
                'polygon': True,
                'circle': False,
                'marker': True,
                'circlemarker': False
            },
            edit_options={'edit': True}
        )
        draw.add_to(m)
        
        # Add existing field boundary if available
        if field_data.get('boundary'):
            folium.Polygon(
                locations=field_data['boundary'],
                color='yellow',
                fill=True,
                fill_color='yellow',
                fill_opacity=0.3,
                popup='Field Boundary'
            ).add_to(m)
        
        # Add water source marker if available
        if field_data.get('water_source'):
            folium.Marker(
                location=field_data['water_source'],
                popup='<b>Water Source</b><br>Click to edit',
                tooltip='Water Source Location',
                icon=folium.Icon(color='blue', icon='info-sign', prefix='glyphicon')
            ).add_to(m)
            
            # Add a circle to make it more visible
            folium.CircleMarker(
                location=field_data['water_source'],
                radius=15,
                color='blue',
                fill=True,
                fillColor='lightblue',
                fillOpacity=0.7,
                popup='<b>Water Source</b>'
            ).add_to(m)
        
        # Display map with error handling for Streamlit Cloud
        map_data = safe_st_folium(m, width=700, height=500, returned_objects=["all_drawings"], key="interactive_map")
        
        # Process drawn shapes
        if map_data and map_data.get('all_drawings'):
            process_map_drawings(map_data['all_drawings'])

def geocode_location(location_str):
    """Convert location string to coordinates"""
    try:
        geolocator = Nominatim(user_agent="irrigation_design_app")
        location = geolocator.geocode(location_str)
        if location:
            return [location.latitude, location.longitude]
    except:
        pass
    return None

def process_map_drawings(drawings):
    """Process user drawings from the map"""
    if not drawings:
        return
    
    field_boundary = None
    water_source = None
    
    for drawing in drawings:
        geometry_type = drawing.get('geometry', {}).get('type')
        
        if geometry_type in ['Polygon', 'Rectangle']:
            # Extract boundary coordinates
            coords = drawing['geometry']['coordinates'][0]
            field_boundary = [[lat, lon] for lon, lat in coords]
            
        elif geometry_type == 'Point':
            # Water source marker
            coords = drawing['geometry']['coordinates']
            water_source = [coords[1], coords[0]]  # [lat, lon]
    
    # Save field boundary if drawn
    if field_boundary:
        # Calculate field dimensions
        field_info = calculate_field_dimensions(field_boundary)
        
        # Convert GPS polygon to local coordinate system (meters from bottom-left)
        local_polygon = convert_gps_to_local(field_boundary)
        
        # Get existing water source if already saved
        existing_water_source_gps = st.session_state.project_data.get('field_geometry', {}).get('water_source')
        current_water_source = water_source if water_source else existing_water_source_gps
        
        # Convert water source to local coordinates if available
        water_source_local = None
        if current_water_source:
            water_source_local = convert_gps_point_to_local(current_water_source, field_boundary)
        
        st.session_state.project_data['field_geometry'] = {
            'boundary': field_boundary,
            'water_source': current_water_source,
            'local_polygon': local_polygon,
            'water_source_local': water_source_local,
            'gps_polygon': field_boundary,  # Keep for reference
            **field_info
        }
        
        # Update area in main project data
        st.session_state.project_data['area'] = field_info['area_ha']
        
        msg = f"""
        ✅ **Field Delineated!**
        - Area: {field_info['area_ha']:.2f} ha
        - Length: {field_info['length_m']:.1f} m
        - Width: {field_info['width_m']:.1f} m
        """
        if current_water_source:
            msg += "\n- Water source marked ✓"
        
        st.success(msg)
        st.rerun()
    
    # Save water source independently if marked
    elif water_source:
        # Preserve existing field geometry
        existing_geometry = st.session_state.project_data.get('field_geometry', {})
        existing_geometry['water_source'] = water_source
        
        # Convert to local coordinates if boundary exists
        if existing_geometry.get('boundary'):
            water_source_local = convert_gps_point_to_local(water_source, existing_geometry['boundary'])
            existing_geometry['water_source_local'] = water_source_local
        
        st.session_state.project_data['field_geometry'] = existing_geometry
        
        st.success(f"""
        ✅ **Water Source Marked!**
        - Location: {water_source[0]:.6f}, {water_source[1]:.6f}
        """)
        st.rerun()

def calculate_field_dimensions(boundary_coords):
    """Calculate area and dimensions from boundary coordinates"""
    # Convert to Shapely polygon for accurate calculations
    # Coordinates are [lat, lon], need to convert to projected system for meters
    polygon = Polygon([(lon, lat) for lat, lon in boundary_coords])
    
    # Approximate area calculation (simple method)
    # For more accuracy, should use proper projection
    area_deg2 = polygon.area
    
    # Rough conversion: 1 degree ≈ 111 km at equator
    # This is approximate and varies with latitude
    lat_avg = np.mean([coord[0] for coord in boundary_coords])
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * np.cos(np.radians(lat_avg))
    
    area_m2 = area_deg2 * meters_per_deg_lat * meters_per_deg_lon
    area_ha = area_m2 / 10000
    
    # Calculate bounding box dimensions
    lats = [coord[0] for coord in boundary_coords]
    lons = [coord[1] for coord in boundary_coords]
    
    # Width is east-west (longitude span), Length is north-south (latitude span)
    width_m = (max(lons) - min(lons)) * meters_per_deg_lon
    length_m = (max(lats) - min(lats)) * meters_per_deg_lat
    
    return {
        'area_ha': area_ha,
        'area_m2': area_m2,
        'length_m': length_m,
        'width_m': width_m,
        'perimeter_m': length_m * 2 + width_m * 2
    }


def convert_gps_to_local(boundary_coords):
    """Convert GPS coordinates to local meters from bottom-left origin"""
    if not boundary_coords:
        return []
    
    # Get bounding box
    lats = [coord[0] for coord in boundary_coords]
    lons = [coord[1] for coord in boundary_coords]
    
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    
    # Conversion factors
    lat_avg = np.mean(lats)
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * np.cos(np.radians(lat_avg))
    
    # Convert to local coordinates (meters from min_lon, min_lat as origin)
    local_polygon = []
    for lat, lon in boundary_coords:
        x = (lon - min_lon) * meters_per_deg_lon
        y = (lat - min_lat) * meters_per_deg_lat
        local_polygon.append([x, y])
    
    return local_polygon


def convert_gps_point_to_local(gps_point, boundary_coords):
    """Convert a single GPS point to local coordinates"""
    if not gps_point or not boundary_coords:
        return None
    
    # Get bounding box origin
    lats = [coord[0] for coord in boundary_coords]
    lons = [coord[1] for coord in boundary_coords]
    
    min_lat = min(lats)
    min_lon = min(lons)
    
    # Conversion factors
    lat_avg = np.mean(lats)
    meters_per_deg_lat = 111320
    meters_per_deg_lon = 111320 * np.cos(np.radians(lat_avg))
    
    # Convert point
    lat, lon = gps_point
    x = (lon - min_lon) * meters_per_deg_lon
    y = (lat - min_lat) * meters_per_deg_lat
    
    return [x, y]


def show_manual_field_input():
    """Manual field dimension input (fallback when map not available)"""
    st.markdown("#### Manual Field Dimensions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        field_length = st.number_input(
            "Field Length (m)",
            min_value=10.0,
            max_value=5000.0,
            value=float(st.session_state.project_data.get('field_geometry', {}).get('length_m', 500.0)),
            step=10.0
        )
        
        field_shape = st.selectbox(
            "Field Shape",
            options=['Rectangular', 'Square', 'Irregular'],
            index=0
        )
    
    with col2:
        field_width = st.number_input(
            "Field Width (m)",
            min_value=10.0,
            max_value=5000.0,
            value=float(st.session_state.project_data.get('field_geometry', {}).get('width_m', 400.0)),
            step=10.0
        )
        
        water_source_location = st.selectbox(
            "Water Source Location",
            options=['Corner', 'Side', 'Center', 'Outside Field']
        )
    
    calculated_area = (field_length * field_width) / 10000  # ha
    
    st.info(f"**Calculated Area:** {calculated_area:.2f} ha")
    
    if st.button("💾 Save Field Dimensions", type="primary"):
        st.session_state.project_data['field_geometry'] = {
            'length_m': field_length,
            'width_m': field_width,
            'area_ha': calculated_area,
            'area_m2': field_length * field_width,
            'shape': field_shape,
            'water_source_location': water_source_location
        }
        st.session_state.project_data['area'] = calculated_area
        st.success("✅ Field dimensions saved!")
        st.rerun()


# Note: My Projects section removed - use Cloud Project Manager instead
