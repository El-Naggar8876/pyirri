"""
Hydraulic Design Module
Calculate pressure requirements, friction losses, and system hydraulics
Based on formula: Pr = Ps – (Po + Pls)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

def show():
    st.markdown('<h1 class="main-header">Hydraulic Design</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    Design system hydraulics including pressure requirements based on the formula:<br>
    <b>Pr = Ps – (Po + Pls)</b><br>
    Where Pr = Pressure remaining, Ps = Static pressure, Po = Operating pressure, Pls = System pressure losses
    </div>
    """, unsafe_allow_html=True)
    
    tabs = st.tabs(["Pressure Requirements", "System Head"])
    
    with tabs[0]:
        show_pressure_requirements()
    
    with tabs[1]:
        show_system_head()


def get_pipe_network_data():
    """
    Get pipe network design data from saved designs.
    Returns dictionary with friction losses for each line type.
    
    PRIORITY: temp state (most recent calculations) > saved project_data
    """
    data = {
        'sprinkler_line': {'flow': 0, 'friction_loss': 0, 'pipe_sizes': [], 'segments': []},
        'lateral_line': {'flow': 0, 'friction_loss': 0, 'pipe_sizes': [], 'segments': []},
        'submain': {'flow': 0, 'friction_loss': 0, 'pipe_sizes': [], 'segments': []},
        'mainline': {'flow': 0, 'friction_loss': 0, 'pipe_sizes': [], 'segments': []}
    }
    
    # Helper to get design data - TEMP FIRST (most current), then saved
    def get_design(saved_key, temp_key):
        # Check temp state first (most recent calculations)
        if temp_key in st.session_state:
            return st.session_state[temp_key], 'temp'
        elif saved_key in st.session_state.project_data:
            return st.session_state.project_data[saved_key], 'saved'
        return None, None
    
    # Sprinkler Line
    sprinkler_design, source = get_design('sprinkler_line_design', 'temp_sprinkler_line_design')
    if sprinkler_design and 'segments' in sprinkler_design:
        segments = sprinkler_design['segments']
        data['sprinkler_line']['flow'] = max(seg.get('flow_m3h', 0) for seg in segments) if segments else 0
        data['sprinkler_line']['friction_loss'] = sum(seg.get('friction_loss_m', 0) for seg in segments)
        data['sprinkler_line']['pipe_sizes'] = list(set(seg.get('pipe_nominal_mm', '') for seg in segments))
        data['sprinkler_line']['segments'] = segments
    
    # Lateral Line
    lateral_design, source = get_design('lateral_design', 'temp_lateral_design')
    if lateral_design and 'segments' in lateral_design:
        segments = lateral_design['segments']
        data['lateral_line']['flow'] = max(seg.get('flow_m3h', 0) for seg in segments) if segments else 0
        data['lateral_line']['friction_loss'] = sum(seg.get('friction_loss_m', 0) for seg in segments)
        data['lateral_line']['pipe_sizes'] = list(set(seg.get('pipe_nominal_mm', '') for seg in segments))
        data['lateral_line']['segments'] = segments
    
    # Submain (farthest - index 0) - check TEMP first
    submain_design = None
    
    # Try temp state first (most recent)
    for idx in range(10):  # Check first 10 possible indices
        temp_key = f'temp_submain_{idx}_design'
        if temp_key in st.session_state:
            if idx == 0:  # Farthest submain
                submain_design = st.session_state[temp_key]
                break
    
    # If not in temp, try saved
    if not submain_design:
        for key in st.session_state.project_data.keys():
            if key.startswith('submain_') and key.endswith('_design') and not key.startswith('temp_'):
                try:
                    idx = int(key.split('_')[1])
                    if idx == 0:  # Farthest submain
                        submain_design = st.session_state.project_data[key]
                        break
                except:
                    pass
    
    if submain_design and 'segments' in submain_design:
        segments = submain_design['segments']
        # Use full_flow_m3h if available (for mainline consistency)
        data['submain']['flow'] = max(seg.get('full_flow_m3h', seg.get('flow_m3h', 0)) for seg in segments) if segments else 0
        data['submain']['friction_loss'] = submain_design.get('total_friction_loss_m', sum(seg.get('friction_loss_m', 0) for seg in segments))
        data['submain']['pipe_sizes'] = list(set(seg.get('pipe_nominal_mm', '') for seg in segments))
        data['submain']['segments'] = segments
    
    # Mainline - check TEMP first, then saved
    mainline_design = None
    mainline_segments = []
    
    # Try temp state first for all mainlines
    for idx in range(10):  # Check first 10 possible mainline indices
        temp_key = f'temp_mainline_{idx}_design'
        if temp_key in st.session_state:
            design = st.session_state[temp_key]
            if design and 'segments' in design:
                mainline_segments.extend(design['segments'])
    
    # If no temp data, try saved
    if not mainline_segments:
        for key in st.session_state.project_data.keys():
            if key.startswith('mainline_') and key.endswith('_design') and not key.startswith('temp_'):
                design = st.session_state.project_data[key]
                if design and 'segments' in design:
                    mainline_segments.extend(design['segments'])
    
    if mainline_segments:
        # Get max flow from segments (this should already be the correct V3 max daily flow)
        data['mainline']['flow'] = max(seg.get('flow_m3h', 0) for seg in mainline_segments)
        data['mainline']['friction_loss'] = sum(seg.get('head_loss_m', seg.get('friction_loss_m', 0)) for seg in mainline_segments)
        data['mainline']['pipe_sizes'] = list(set(seg.get('pipe_nominal_mm', '') for seg in mainline_segments))
        data['mainline']['segments'] = mainline_segments
    
    return data


def get_sprinkler_data():
    """
    Get sprinkler data from sprinkler selection module.
    Returns dictionary with sprinkler specifications.
    
    Note: Flow in sprinkler_data is stored in l/h, converted to m³/h here
    """
    # First check if there's saved sprinkler selection data
    sprinkler_selection = st.session_state.project_data.get('sprinkler_selection', {})
    
    # Get selected sprinkler info
    selected_sprinkler = sprinkler_selection.get('selected_sprinkler', {})
    
    if selected_sprinkler:
        # Use actual selected sprinkler data
        flow_lh = selected_sprinkler.get('flow', 3000)  # l/h
        flow_m3h = flow_lh / 1000  # Convert to m³/h
        return {
            'name': selected_sprinkler.get('model', selected_sprinkler.get('name', 'Unknown')),
            'pressure': selected_sprinkler.get('pressure', 
                        selected_sprinkler.get('recommended_pressure_kpa', 300)),  # kPa
            'flow': flow_m3h,  # m³/h
            'flow_lh': flow_lh,  # Keep original l/h
            'radius': selected_sprinkler.get('diameter', 30) / 2,  # m (diameter/2)
            'type': selected_sprinkler.get('type', 'Impact')
        }
    
    # Fallback to older sprinkler_data format (from sprinkler_selection module)
    sprinkler_data = st.session_state.project_data.get('sprinkler_data', {})
    if sprinkler_data:
        flow_lh = sprinkler_data.get('flow', 3000)  # l/h
        flow_m3h = flow_lh / 1000  # Convert to m³/h
        return {
            'name': sprinkler_data.get('model', 'Unknown'),
            'pressure': sprinkler_data.get('pressure', 300),  # kPa
            'flow': flow_m3h,  # m³/h
            'flow_lh': flow_lh,  # Keep original l/h
            'radius': sprinkler_data.get('diameter', 30) / 2,  # m
            'type': sprinkler_data.get('sprinkler_type', 'Impact'),
            'nozzle': sprinkler_data.get('nozzle', '')
        }
    
    # Default values if nothing found
    return {
        'name': 'Not Selected',
        'pressure': 300,
        'flow': 3.0,  # m³/h default
        'flow_lh': 3000,  # l/h
        'radius': 15,
        'type': 'Impact'
    }


def show_pressure_requirements():
    """Calculate and display pressure requirements with detailed breakdown table"""
    st.markdown('<h2 class="sub-header">Pressure Requirements</h2>', unsafe_allow_html=True)
    
    # Formula explanation
    st.markdown("""
    ### Pressure Balance Formula
    
    **Pr = Ps – (Po + Pls)**
    
    Where:
    - **Ps** = Static pressure available at the site
    - **Po** = Operating pressure for "worst case" sprinkler
    - **Pls** = Pressure loss throughout system (mainline and "worst case" lateral circuit)
    - **Pr** = Pressure remaining after satisfying the total system requirement
    """)
    
    st.markdown("---")
    
    # Get sprinkler data from Sprinkler Selection module
    sprinkler_info = get_sprinkler_data()
    sprinkler_pressure_kpa = sprinkler_info.get('pressure', 300)  # kPa
    sprinkler_flow = sprinkler_info.get('flow', 3.0)  # m³/h per sprinkler
    sprinkler_name = sprinkler_info.get('name', 'Not Selected')
    
    # Get pipe network data (includes mainline with correct V3 max daily flow)
    pipe_data = get_pipe_network_data()
    
    # Show data linkage status
    with st.expander("📊 Data Source Status", expanded=False):
        st.markdown("**Data is automatically linked from:**")
        
        # Sprinkler status
        if sprinkler_name != 'Not Selected':
            st.success(f"✅ **Sprinkler**: {sprinkler_name} @ {sprinkler_pressure_kpa} kPa, {sprinkler_flow} m³/h")
        else:
            st.warning("⚠️ **Sprinkler**: Not selected - using defaults")
        
        # Sprinkler Line status
        if pipe_data['sprinkler_line']['segments']:
            flow = pipe_data['sprinkler_line']['flow']
            loss = pipe_data['sprinkler_line']['friction_loss']
            st.success(f"✅ **Sprinkler Line**: {flow:.2f} m³/h, {loss:.3f} m friction loss")
        else:
            st.info("📝 **Sprinkler Line**: Not designed yet")
        
        # Lateral status
        if pipe_data['lateral_line']['segments']:
            flow = pipe_data['lateral_line']['flow']
            loss = pipe_data['lateral_line']['friction_loss']
            st.success(f"✅ **Lateral Line**: {flow:.2f} m³/h, {loss:.3f} m friction loss")
        else:
            st.info("📝 **Lateral Line**: Not designed yet")
        
        # Submain status
        if pipe_data['submain']['segments']:
            flow = pipe_data['submain']['flow']
            loss = pipe_data['submain']['friction_loss']
            st.success(f"✅ **Submain (Farthest)**: {flow:.2f} m³/h, {loss:.3f} m friction loss")
        else:
            st.info("📝 **Submain**: Not designed yet")
        
        # Mainline status
        if pipe_data['mainline']['segments']:
            flow = pipe_data['mainline']['flow']
            loss = pipe_data['mainline']['friction_loss']
            # Check for V3 flow method
            flow_method = pipe_data['mainline']['segments'][0].get('flow_method', '')
            method_note = " (Max Daily Flow)" if 'Max Daily' in flow_method else ""
            st.success(f"✅ **Mainline**: {flow:.2f} m³/h{method_note}, {loss:.3f} m friction loss")
        else:
            st.info("📝 **Mainline**: Not designed yet")
        
        st.caption("💡 Data updates automatically when you recalculate designs in Pipe Network Design")
    
    # Calculate pipe losses (in meters)
    sprinkler_line_loss = pipe_data['sprinkler_line']['friction_loss']
    lateral_loss = pipe_data['lateral_line']['friction_loss']
    submain_loss = pipe_data['submain']['friction_loss']
    mainline_loss = pipe_data['mainline']['friction_loss']
    
    total_pipe_loss = sprinkler_line_loss + lateral_loss + submain_loss + mainline_loss
    
    # Convert pressure to bar (1 bar = 100 kPa = 10.197 m head)
    sprinkler_pressure_bar = sprinkler_pressure_kpa / 100
    
    st.markdown("### System Pressure Requirements Table")
    
    # ============ SPRINKLER SECTION ============
    st.markdown("---")
    st.markdown("#### 🔵 Sprinkler")
    
    if sprinkler_name != 'Not Selected':
        # Get flow in both units
        flow_lh = sprinkler_info.get('flow_lh', sprinkler_flow * 1000)
        sprinkler_table = pd.DataFrame([{
            'Description': f"Operating Pressure ({sprinkler_name})",
            'Flow (m³/h)': f"{sprinkler_flow:.3f} ({flow_lh:.0f} l/h)",
            'Size (mm)': '-',
            'Pressure Loss (bar)': f"- {sprinkler_pressure_bar:.2f}"
        }])
        st.dataframe(sprinkler_table, width="stretch", hide_index=True)
    else:
        st.warning("⚠️ Please select a sprinkler first in Sprinkler Selection module")
    
    # ============ SPRINKLER LINE SECTION ============
    st.markdown("---")
    st.markdown("#### 🌊 Sprinkler Line")
    
    if pipe_data['sprinkler_line']['segments']:
        segments = pipe_data['sprinkler_line']['segments']
        rows = []
        for seg in segments:
            loss_bar = seg.get('friction_loss_m', 0) / 10.197
            rows.append({
                'Section': seg.get('position', f"Section {seg.get('segment', '')}"),
                'Flow (m³/h)': round(seg.get('flow_m3h', 0), 2),
                'Size (mm)': seg.get('pipe_nominal_mm', ''),
                'Pressure Loss (bar)': f"- {loss_bar:.2f}"
            })
        df_sprinkler_line = pd.DataFrame(rows)
        st.dataframe(df_sprinkler_line, width="stretch", hide_index=True)
    else:
        st.info("📝 Complete Sprinkler Line design in Pipe Network Design")
    
    # ============ LATERAL LINE SECTION ============
    st.markdown("---")
    st.markdown("#### 📏 Lateral Line")
    
    if pipe_data['lateral_line']['segments']:
        segments = pipe_data['lateral_line']['segments']
        rows = []
        for seg in segments:
            loss_bar = seg.get('friction_loss_m', 0) / 10.197
            rows.append({
                'Section': seg.get('position', f"Section {seg.get('segment', '')}"),
                'Flow (m³/h)': round(seg.get('flow_m3h', 0), 2),
                'Size (mm)': seg.get('pipe_nominal_mm', ''),
                'Pressure Loss (bar)': f"- {loss_bar:.2f}"
            })
        df_lateral = pd.DataFrame(rows)
        st.dataframe(df_lateral, width="stretch", hide_index=True)
    else:
        st.info("📝 Complete Lateral Line design in Pipe Network Design")
    
    # ============ SUBMAIN SECTION ============
    st.markdown("---")
    st.markdown("#### 🔀 Submain (Farthest)")
    
    if pipe_data['submain']['segments']:
        segments = pipe_data['submain']['segments']
        rows = []
        for seg in segments:
            loss_bar = seg.get('friction_loss_m', 0) / 10.197
            rows.append({
                'Section': seg.get('position', f"Section {seg.get('segment', '')}"),
                'Flow (m³/h)': round(seg.get('flow_m3h', 0), 2),
                'Size (mm)': seg.get('pipe_nominal_mm', ''),
                'Pressure Loss (bar)': f"- {loss_bar:.2f}"
            })
        df_submain = pd.DataFrame(rows)
        st.dataframe(df_submain, width="stretch", hide_index=True)
    else:
        st.info("📝 Complete Submain design in Pipe Network Design")
    
    # ============ MAINLINE SECTION ============
    st.markdown("---")
    st.markdown("#### 🚰 Main Line")
    
    if pipe_data['mainline']['segments']:
        segments = pipe_data['mainline']['segments']
        # Aggregate mainline data
        total_loss = sum(seg.get('head_loss_m', seg.get('friction_loss_m', 0)) for seg in segments)
        max_flow = max(seg.get('flow_m3h', 0) for seg in segments)
        pipe_sizes = ', '.join(str(s) for s in sorted(set(seg.get('pipe_nominal_mm', '') for seg in segments), reverse=True))
        
        # Check if this is V3 max daily flow
        flow_method = segments[0].get('flow_method', '') if segments else ''
        
        loss_bar = total_loss / 10.197
        mainline_table = pd.DataFrame([{
            'Section': 'Main Line (Total)',
            'Flow (m³/h)': f"{round(max_flow, 2)} {'(Max Daily)' if 'Max Daily' in flow_method else ''}",
            'Size (mm)': pipe_sizes,
            'Pressure Loss (bar)': f"- {loss_bar:.2f}"
        }])
        st.dataframe(mainline_table, width="stretch", hide_index=True)
        
        # Show info about flow calculation method
        if 'Max Daily' in flow_method or 'V3' in flow_method:
            st.caption("ℹ️ Flow calculated as maximum daily demand considering operational scheduling")
    else:
        st.info("📝 Complete Mainline design in Pipe Network Design")
    
    # ============ ADDITIONAL LOSSES SECTION ============
    st.markdown("---")
    st.markdown("#### ⚙️ Additional System Losses & Pressure Balance")
    
    # Check if this is a drip irrigation system
    drip_data = st.session_state.project_data.get('drip_irrigation', {})
    is_drip_system = bool(drip_data)
    
    col1, col2 = st.columns(2)
    
    # Initialize hydraulic design data if not exists
    if 'hydraulic_design' not in st.session_state.project_data:
        st.session_state.project_data['hydraulic_design'] = {}
    
    hyd_data = st.session_state.project_data['hydraulic_design']
    
    with col1:
        # Fittings loss (10% of pipe losses - calculated automatically)
        fittings_loss = total_pipe_loss * 0.10
        fittings_loss_bar = fittings_loss / 10.197
        
        st.markdown(f"**Fittings Loss (10% of all pipe losses):** `- {fittings_loss_bar:.2f} bar`")
        
        # Backflow unit
        backflow_loss_bar = st.number_input(
            "Backflow Unit Loss (bar)",
            min_value=0.0,
            max_value=2.0,
            value=hyd_data.get('backflow_loss_bar', 0.29),
            step=0.01,
            format="%.2f",
            key="backflow_input"
        )
        
        # Water meter - Default 2m (0.196 bar) for drip, or user value
        default_water_meter = 0.196 if is_drip_system else 0.68  # 2m head for drip
        water_meter_loss_bar = st.number_input(
            "Water Meter Loss (bar)",
            min_value=0.0,
            max_value=2.0,
            value=hyd_data.get('water_meter_loss_bar', default_water_meter),
            step=0.01,
            format="%.2f",
            key="water_meter_input",
            help="Drip default: 0.20 bar (2m head)"
        )
        
        # Drip irrigation specific: Filter head loss
        if is_drip_system:
            filter_loss_bar = st.number_input(
                "Filter Head Loss (bar) - Drip",
                min_value=0.0,
                max_value=2.0,
                value=hyd_data.get('filter_loss_bar', 0.39),  # 4m default
                step=0.01,
                format="%.2f",
                key="filter_loss_input",
                help="Default: 0.39 bar (4m head) for drip irrigation filters"
            )
            
            fertigation_loss_bar = st.number_input(
                "Fertigation Head Loss (bar) - Drip",
                min_value=0.0,
                max_value=2.0,
                value=hyd_data.get('fertigation_loss_bar', 0.49),  # 5m default
                step=0.01,
                format="%.2f",
                key="fertigation_loss_input",
                help="Default: 0.49 bar (5m head) for fertigation system"
            )
        else:
            filter_loss_bar = 0
            fertigation_loss_bar = 0
    
    with col2:
        # Elevation losses/gains
        elevation_loss_bar = st.number_input(
            "Pressure Loss due to Elevation Rise (bar)",
            min_value=0.0,
            max_value=10.0,
            value=hyd_data.get('elevation_loss_bar', 0.0),
            step=0.1,
            format="%.2f",
            help="Enter 0 if no elevation rise",
            key="elevation_loss_input"
        )
        
        elevation_gain_bar = st.number_input(
            "Pressure Gain from Elevation Drop (bar)",
            min_value=0.0,
            max_value=10.0,
            value=hyd_data.get('elevation_gain_bar', 0.0),
            step=0.1,
            format="%.2f",
            help="Enter 0 if no elevation drop",
            key="elevation_gain_input"
        )
        
        # Static pressure available
        static_pressure_bar = st.number_input(
            "Static Pressure Available at Site (bar) - Ps",
            min_value=0.0,
            max_value=20.0,
            value=hyd_data.get('static_pressure_bar', 6.0),
            step=0.1,
            format="%.2f",
            help="Ps - Available static pressure from water source",
            key="static_pressure_input"
        )
    
    # ============ CALCULATE TOTALS ============
    st.markdown("---")
    st.markdown("### 📊 Pressure Summary Table")
    
    # Show drip irrigation indicator if applicable
    if is_drip_system:
        st.info("🌿 **Drip Irrigation Mode** - Including filter and fertigation head losses")
    
    # Total pipe losses in bar
    sprinkler_line_loss_bar = sprinkler_line_loss / 10.197
    lateral_loss_bar = lateral_loss / 10.197
    submain_loss_bar = submain_loss / 10.197
    mainline_loss_bar = mainline_loss / 10.197
    
    # Total system pressure required (Po + Pls)
    # Include drip-specific losses if applicable
    total_required = (
        sprinkler_pressure_bar +           # Sprinkler/emitter operating pressure (Po)
        sprinkler_line_loss_bar +          # Sprinkler line losses
        lateral_loss_bar +                 # Lateral losses
        submain_loss_bar +                 # Submain losses
        mainline_loss_bar +                # Mainline losses
        fittings_loss_bar +                # Fittings (10%)
        backflow_loss_bar +                # Backflow unit
        water_meter_loss_bar +             # Water meter (2m for drip)
        filter_loss_bar +                  # Filter loss (4m for drip)
        fertigation_loss_bar +             # Fertigation loss (5m for drip)
        elevation_loss_bar -               # Elevation loss (-)
        elevation_gain_bar                 # Elevation gain (+)
    )
    
    # Pressure remaining (Pr = Ps - (Po + Pls))
    pressure_remaining = static_pressure_bar - total_required
    
    # Create summary table - different for drip vs sprinkler
    if is_drip_system:
        summary_data = [
            {'Component': 'Emitter Operating Pressure (Po)', 'Pressure (bar)': f"- {sprinkler_pressure_bar:.2f}"},
            {'Component': 'Lateral Line Loss (PE)', 'Pressure (bar)': f"- {lateral_loss_bar:.2f}"},
            {'Component': 'Manifold/Submain Loss (PVC)', 'Pressure (bar)': f"- {submain_loss_bar:.2f}"},
            {'Component': 'Mainline Loss', 'Pressure (bar)': f"- {mainline_loss_bar:.2f}"},
            {'Component': 'Fittings Loss (10%)', 'Pressure (bar)': f"- {fittings_loss_bar:.2f}"},
            {'Component': 'Backflow Unit', 'Pressure (bar)': f"- {backflow_loss_bar:.2f}"},
            {'Component': 'Water Meter (2m)', 'Pressure (bar)': f"- {water_meter_loss_bar:.2f}"},
            {'Component': 'Filter Head Loss (4m)', 'Pressure (bar)': f"- {filter_loss_bar:.2f}"},
            {'Component': 'Fertigation Head Loss (5m)', 'Pressure (bar)': f"- {fertigation_loss_bar:.2f}"},
            {'Component': 'Elevation Rise', 'Pressure (bar)': f"(-) {elevation_loss_bar:.2f}"},
            {'Component': 'Elevation Drop', 'Pressure (bar)': f"(+) {elevation_gain_bar:.2f}"},
            {'Component': '─' * 40, 'Pressure (bar)': '─' * 12},
            {'Component': 'Total pressure required (Po + Pls)', 'Pressure (bar)': f"- {total_required:.2f}"},
            {'Component': 'Static pressure available (Ps)', 'Pressure (bar)': f"+ {static_pressure_bar:.2f}"},
            {'Component': '═' * 40, 'Pressure (bar)': '═' * 12},
            {'Component': 'Pressure Difference (Pr)', 'Pressure (bar)': f"{'+' if pressure_remaining >= 0 else ''}{pressure_remaining:.2f}"},
        ]
    else:
        summary_data = [
            {'Component': 'Sprinkler Operating Pressure (Po)', 'Pressure (bar)': f"- {sprinkler_pressure_bar:.2f}"},
            {'Component': 'Sprinkler Line Loss', 'Pressure (bar)': f"- {sprinkler_line_loss_bar:.2f}"},
            {'Component': 'Lateral Line Loss', 'Pressure (bar)': f"- {lateral_loss_bar:.2f}"},
            {'Component': 'Submain Loss', 'Pressure (bar)': f"- {submain_loss_bar:.2f}"},
            {'Component': 'Mainline Loss', 'Pressure (bar)': f"- {mainline_loss_bar:.2f}"},
            {'Component': 'Fittings Loss (10% of pipe losses)', 'Pressure (bar)': f"- {fittings_loss_bar:.2f}"},
            {'Component': 'Backflow Unit', 'Pressure (bar)': f"- {backflow_loss_bar:.2f}"},
            {'Component': 'Water Meter', 'Pressure (bar)': f"- {water_meter_loss_bar:.2f}"},
            {'Component': 'Losses in pressure due to elevation rise', 'Pressure (bar)': f"(-) {elevation_loss_bar:.2f}"},
            {'Component': 'Pressure gains from elevation drop', 'Pressure (bar)': f"(+) {elevation_gain_bar:.2f}"},
            {'Component': '─' * 40, 'Pressure (bar)': '─' * 12},
        {'Component': 'Total pressure required by the system (Po + Pls)', 'Pressure (bar)': f"- {total_required:.2f}"},
        {'Component': 'Static pressure available to the site (Ps)', 'Pressure (bar)': f"+ {static_pressure_bar:.2f}"},
        {'Component': '═' * 40, 'Pressure (bar)': '═' * 12},
        {'Component': 'Difference between available and required pressure (Pr)', 'Pressure (bar)': f"{'+' if pressure_remaining >= 0 else ''}{pressure_remaining:.2f}"},
    ]
    
    df_summary = pd.DataFrame(summary_data)
    
    # Style the dataframe
    def highlight_result(row):
        if 'Difference' in row['Component']:
            if pressure_remaining >= 0:
                return ['background-color: #d4edda; font-weight: bold'] * len(row)
            else:
                return ['background-color: #f8d7da; font-weight: bold'] * len(row)
        elif 'Total pressure required' in row['Component']:
            return ['background-color: #fff3cd; font-weight: bold'] * len(row)
        elif 'Static pressure available' in row['Component']:
            return ['background-color: #cce5ff; font-weight: bold'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        df_summary.style.apply(highlight_result, axis=1),
        width="stretch",
        hide_index=True,
        height=550
    )
    
    # Result interpretation
    st.markdown("---")
    st.markdown("### Result: Pr = Ps – (Po + Pls)")
    
    if pressure_remaining >= 0:
        st.success(f"""
        ✅ **System is FEASIBLE!**
        
        **Pr = {static_pressure_bar:.2f} – {total_required:.2f} = +{pressure_remaining:.2f} bar**
        
        The available static pressure (Ps = {static_pressure_bar:.2f} bar) is **sufficient** to meet the total system requirement.
        
        There is a surplus of **+{pressure_remaining:.2f} bar** available.
        """)
    else:
        st.error(f"""
        ❌ **System Requires Additional Pressure!**
        
        **Pr = {static_pressure_bar:.2f} – {total_required:.2f} = {pressure_remaining:.2f} bar**
        
        The available static pressure (Ps = {static_pressure_bar:.2f} bar) is **NOT sufficient** to meet the total system requirement.
        
        A pump providing at least **{abs(pressure_remaining):.2f} bar** additional pressure is required.
        """)
    
    # Save button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 Save Pressure Requirements", type="primary", width="stretch"):
            save_data = {
                'sprinkler_pressure_bar': sprinkler_pressure_bar,
                'sprinkler_line_loss_bar': sprinkler_line_loss_bar,
                'lateral_loss_bar': lateral_loss_bar,
                'submain_loss_bar': submain_loss_bar,
                'mainline_loss_bar': mainline_loss_bar,
                'fittings_loss_bar': fittings_loss_bar,
                'backflow_loss_bar': backflow_loss_bar,
                'water_meter_loss_bar': water_meter_loss_bar,
                'elevation_loss_bar': elevation_loss_bar,
                'elevation_gain_bar': elevation_gain_bar,
                'static_pressure_bar': static_pressure_bar,
                'total_required_bar': total_required,
                'pressure_remaining_bar': pressure_remaining,
                'total_pipe_loss_m': total_pipe_loss,
                'is_drip_system': is_drip_system
            }
            # Add drip-specific values if applicable
            if is_drip_system:
                save_data.update({
                    'filter_loss_bar': filter_loss_bar,
                    'fertigation_loss_bar': fertigation_loss_bar,
                    'control_head_loss_bar': filter_loss_bar + fertigation_loss_bar + water_meter_loss_bar
                })
            st.session_state.project_data['hydraulic_design'].update(save_data)
            st.success("✅ Pressure requirements saved!")


def show_system_head():
    """Show total system head calculation in meters"""
    st.markdown('<h2 class="sub-header">Total System Head</h2>', unsafe_allow_html=True)
    
    st.markdown("""
    This section converts the pressure requirements to head (meters) for pump selection.
    
    **Conversion:** 1 bar ≈ 10.197 m head
    """)
    
    # Get hydraulic design data
    hyd_data = st.session_state.project_data.get('hydraulic_design', {})
    
    if not hyd_data.get('total_required_bar'):
        st.warning("⚠️ Please complete Pressure Requirements first and save the data.")
        return
    
    # Get values
    sprinkler_pressure_bar = hyd_data.get('sprinkler_pressure_bar', 0)
    sprinkler_line_loss_bar = hyd_data.get('sprinkler_line_loss_bar', 0)
    lateral_loss_bar = hyd_data.get('lateral_loss_bar', 0)
    submain_loss_bar = hyd_data.get('submain_loss_bar', 0)
    mainline_loss_bar = hyd_data.get('mainline_loss_bar', 0)
    fittings_loss_bar = hyd_data.get('fittings_loss_bar', 0)
    backflow_loss_bar = hyd_data.get('backflow_loss_bar', 0)
    water_meter_loss_bar = hyd_data.get('water_meter_loss_bar', 0)
    elevation_loss_bar = hyd_data.get('elevation_loss_bar', 0)
    elevation_gain_bar = hyd_data.get('elevation_gain_bar', 0)
    static_pressure_bar = hyd_data.get('static_pressure_bar', 0)
    total_required_bar = hyd_data.get('total_required_bar', 0)
    pressure_remaining_bar = hyd_data.get('pressure_remaining_bar', 0)
    
    # Convert to meters (1 bar = 10.197 m)
    conversion = 10.197
    
    st.markdown("### System Head Components")
    
    head_data = [
        {'Component': 'Sprinkler Operating Head', 'Head (m)': round(sprinkler_pressure_bar * conversion, 2), 'Pressure (bar)': round(sprinkler_pressure_bar, 2)},
        {'Component': 'Sprinkler Line Friction', 'Head (m)': round(sprinkler_line_loss_bar * conversion, 2), 'Pressure (bar)': round(sprinkler_line_loss_bar, 2)},
        {'Component': 'Lateral Line Friction', 'Head (m)': round(lateral_loss_bar * conversion, 2), 'Pressure (bar)': round(lateral_loss_bar, 2)},
        {'Component': 'Submain Friction', 'Head (m)': round(submain_loss_bar * conversion, 2), 'Pressure (bar)': round(submain_loss_bar, 2)},
        {'Component': 'Mainline Friction', 'Head (m)': round(mainline_loss_bar * conversion, 2), 'Pressure (bar)': round(mainline_loss_bar, 2)},
        {'Component': 'Fittings Loss (10%)', 'Head (m)': round(fittings_loss_bar * conversion, 2), 'Pressure (bar)': round(fittings_loss_bar, 2)},
        {'Component': 'Backflow Unit', 'Head (m)': round(backflow_loss_bar * conversion, 2), 'Pressure (bar)': round(backflow_loss_bar, 2)},
        {'Component': 'Water Meter', 'Head (m)': round(water_meter_loss_bar * conversion, 2), 'Pressure (bar)': round(water_meter_loss_bar, 2)},
        {'Component': 'Elevation Head (Rise)', 'Head (m)': round(elevation_loss_bar * conversion, 2), 'Pressure (bar)': round(elevation_loss_bar, 2)},
        {'Component': 'Elevation Head (Drop)', 'Head (m)': round(-elevation_gain_bar * conversion, 2), 'Pressure (bar)': round(-elevation_gain_bar, 2)},
    ]
    
    df_head = pd.DataFrame(head_data)
    
    st.dataframe(
        df_head,
        width="stretch",
        hide_index=True
    )
    
    # Summary
    st.markdown("---")
    st.markdown("### Summary")
    
    total_head_required = total_required_bar * conversion
    static_head = static_pressure_bar * conversion
    head_difference = pressure_remaining_bar * conversion
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Head Required", f"{total_head_required:.1f} m", help="Total head the system needs")
    
    with col2:
        st.metric("Static Head Available", f"{static_head:.1f} m", help="Head provided by water source")
    
    with col3:
        delta_color = "normal" if head_difference >= 0 else "inverse"
        st.metric(
            "Head Difference", 
            f"{head_difference:.1f} m",
            delta=f"{'Surplus' if head_difference >= 0 else 'Deficit'}",
            delta_color=delta_color
        )
    
    # Pump requirement
    st.markdown("---")
    st.markdown("### Pump Requirement")
    
    if pressure_remaining_bar < 0:
        pump_head = abs(head_difference)
        st.error(f"""
        **A pump is required!**
        
        - Minimum Pump Head: **{pump_head:.1f} m** ({abs(pressure_remaining_bar):.2f} bar)
        - Recommended Pump Head (with 10% safety): **{pump_head * 1.1:.1f} m** ({abs(pressure_remaining_bar) * 1.1:.2f} bar)
        """)
    else:
        st.success(f"""
        **No pump required for pressure boosting!**
        
        The available static pressure is sufficient for the system.
        
        However, if a pump is used for other purposes (e.g., drawing from a tank), 
        ensure it provides at least **{total_head_required:.1f} m** head.
        """)
    
    # Pie chart of head distribution
    st.markdown("---")
    st.markdown("### Head Distribution")
    
    pipe_friction_head = (sprinkler_line_loss_bar + lateral_loss_bar + submain_loss_bar + mainline_loss_bar) * conversion
    accessories_head = (fittings_loss_bar + backflow_loss_bar + water_meter_loss_bar) * conversion
    elevation_head = abs(elevation_loss_bar - elevation_gain_bar) * conversion
    sprinkler_head = sprinkler_pressure_bar * conversion
    
    fig = go.Figure(data=[go.Pie(
        labels=['Sprinkler Head', 'Pipe Friction', 'Fittings & Accessories', 'Elevation'],
        values=[
            sprinkler_head,
            pipe_friction_head,
            accessories_head,
            elevation_head
        ],
        hole=0.4,
        marker_colors=['#2E86AB', '#A23B72', '#F18F01', '#C73E1D']
    )])
    
    fig.update_layout(
        title="System Head Components Distribution",
        template="plotly_white",
        height=400
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Save button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 Save System Head", type="primary", width="stretch"):
            st.session_state.project_data['hydraulic_design'].update({
                'total_head_required_m': total_head_required,
                'static_head_m': static_head,
                'head_difference_m': head_difference
            })
            st.success("✅ System head saved!")
