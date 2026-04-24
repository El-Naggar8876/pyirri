"""
Pump Selection Module - Professional Edition
Advanced pump selection with polynomial curve fitting and duty point analysis.

Features:
- Polynomial curve calculations for accurate pump performance
- Interactive pump vs system curve visualization
- Professional pump cards with efficiency badges
- Power and energy analysis

Formulas:
- Head Curve: H = a + (b × Q) + (c × Q²)
- Efficiency: Eff = d + (e × Q) + (f × Q²)
- Power: P_kW = (Q × H) / (367 × Eff)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os

# Import pump math utilities
from .pump_math_utils import (
    PumpCurveSolver, 
    PumpDatabaseManager, 
    PumpMatch,
    get_efficiency_badge_color,
    format_power_display
)


def show():
    st.markdown('<h1 class="main-header">🔧 Pump Selection</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    <b>Professional Pump Selection Engine</b><br>
    Uses polynomial curve fitting with real manufacturer data for accurate pump analysis.
    <br><br>
    <b>Formulas Used:</b><br>
    • Head: H = a + (b × Q) + (c × Q²)<br>
    • Efficiency: Eff = d + (e × Q) + (f × Q²)<br>
    • Power: P<sub>kW</sub> = (Q × H) / (367 × Eff)
    </div>
    """, unsafe_allow_html=True)
    
    tabs = st.tabs(["📊 System Requirements", "🎯 Pump Matching", "📈 Performance Curves", "⚡ Power Analysis"])
    
    with tabs[0]:
        show_system_requirements()
    
    with tabs[1]:
        show_pump_matching()
    
    with tabs[2]:
        show_performance_curves()
    
    with tabs[3]:
        show_power_analysis()


def get_system_requirements():
    """
    Get flow and head from hydraulic design or pipe network design.
    
    PRIORITY: temp state (most recent calculations) > saved project_data
    
    This ensures that when user recalculates in Pipe Network Design,
    the pump selection automatically reflects the updated values.
    """
    flow_m3h = 0
    head_m = 0
    auto_detected = {
        'flow': False, 
        'head': False,
        'flow_source': '',
        'head_source': '',
        'flow_method': ''
    }
    
    # ========================================================================
    # GET HEAD from hydraulic design
    # ========================================================================
    hyd_data = st.session_state.project_data.get('hydraulic_design', {})
    
    if 'total_head_required_m' in hyd_data:
        head_m = hyd_data['total_head_required_m']
        auto_detected['head'] = True
        auto_detected['head_source'] = 'Hydraulic Design (saved)'
    elif 'total_required_bar' in hyd_data:
        head_m = hyd_data['total_required_bar'] * 10.197
        auto_detected['head'] = True
        auto_detected['head_source'] = 'Hydraulic Design (bar converted)'
    
    # ========================================================================
    # GET FLOW from mainline design - CHECK TEMP STATE FIRST (most current)
    # ========================================================================
    
    # Method 1: Check temp state first (most recent calculations)
    for idx in range(10):  # Check first 10 possible mainline indices
        temp_key = f'temp_mainline_{idx}_design'
        if temp_key in st.session_state:
            design = st.session_state[temp_key]
            if design and 'segments' in design:
                segments = design['segments']
                if segments:
                    max_flow = max(seg.get('flow_m3h', 0) for seg in segments)
                    if max_flow > flow_m3h:
                        flow_m3h = max_flow
                        auto_detected['flow'] = True
                        auto_detected['flow_source'] = f'Mainline {idx+1} (temp - most recent)'
                        # Check if this is V3 max daily flow
                        flow_method = segments[0].get('flow_method', '')
                        auto_detected['flow_method'] = flow_method
    
    # Method 2: If no temp data, check saved project_data
    if flow_m3h == 0:
        for key in st.session_state.project_data.keys():
            if key.startswith('mainline_') and key.endswith('_design') and not key.startswith('temp_'):
                design = st.session_state.project_data[key]
                if design and 'segments' in design:
                    segments = design['segments']
                    if segments:
                        max_flow = max(seg.get('flow_m3h', 0) for seg in segments)
                        if max_flow > flow_m3h:
                            flow_m3h = max_flow
                            auto_detected['flow'] = True
                            auto_detected['flow_source'] = f'{key} (saved)'
                            flow_method = segments[0].get('flow_method', '')
                            auto_detected['flow_method'] = flow_method
    
    return flow_m3h, head_m, auto_detected


def get_pipe_network_summary():
    """
    Get a summary of all pipe network design data for display.
    Similar to hydraulic_design.py get_pipe_network_data() but simplified.
    """
    summary = {
        'sprinkler_line': {'flow': 0, 'friction_loss': 0, 'designed': False},
        'lateral': {'flow': 0, 'friction_loss': 0, 'designed': False},
        'submain': {'flow': 0, 'friction_loss': 0, 'designed': False},
        'mainline': {'flow': 0, 'friction_loss': 0, 'designed': False, 'flow_method': ''}
    }
    
    # Helper to check temp then saved
    def get_design(temp_key, saved_key):
        if temp_key in st.session_state:
            return st.session_state[temp_key], 'temp'
        elif saved_key in st.session_state.project_data:
            return st.session_state.project_data[saved_key], 'saved'
        return None, None
    
    # Sprinkler Line
    design, src = get_design('temp_sprinkler_line_design', 'sprinkler_line_design')
    if design and 'segments' in design:
        segs = design['segments']
        summary['sprinkler_line']['flow'] = max(s.get('flow_m3h', 0) for s in segs) if segs else 0
        summary['sprinkler_line']['friction_loss'] = sum(s.get('friction_loss_m', 0) for s in segs)
        summary['sprinkler_line']['designed'] = True
    
    # Lateral
    design, src = get_design('temp_lateral_design', 'lateral_design')
    if design and 'segments' in design:
        segs = design['segments']
        summary['lateral']['flow'] = max(s.get('flow_m3h', 0) for s in segs) if segs else 0
        summary['lateral']['friction_loss'] = sum(s.get('friction_loss_m', 0) for s in segs)
        summary['lateral']['designed'] = True
    
    # Submain (farthest - index 0)
    for idx in range(10):
        temp_key = f'temp_submain_{idx}_design'
        saved_key = f'submain_{idx}_design'
        design, src = get_design(temp_key, saved_key)
        if design and 'segments' in design and idx == 0:
            segs = design['segments']
            summary['submain']['flow'] = design.get('full_inlet_flow_m3h', 
                max(s.get('full_flow_m3h', s.get('flow_m3h', 0)) for s in segs) if segs else 0)
            summary['submain']['friction_loss'] = design.get('total_friction_loss_m',
                sum(s.get('friction_loss_m', 0) for s in segs))
            summary['submain']['designed'] = True
            break
    
    # Mainline - check temp first
    for idx in range(10):
        temp_key = f'temp_mainline_{idx}_design'
        if temp_key in st.session_state:
            design = st.session_state[temp_key]
            if design and 'segments' in design:
                segs = design['segments']
                summary['mainline']['flow'] = max(s.get('flow_m3h', 0) for s in segs) if segs else 0
                summary['mainline']['friction_loss'] = sum(s.get('head_loss_m', s.get('friction_loss_m', 0)) for s in segs)
                summary['mainline']['designed'] = True
                summary['mainline']['flow_method'] = segs[0].get('flow_method', '') if segs else ''
                break
    
    # If no temp mainline, check saved
    if not summary['mainline']['designed']:
        for key in st.session_state.project_data.keys():
            if key.startswith('mainline_') and key.endswith('_design') and not key.startswith('temp_'):
                design = st.session_state.project_data[key]
                if design and 'segments' in design:
                    segs = design['segments']
                    summary['mainline']['flow'] = max(s.get('flow_m3h', 0) for s in segs) if segs else 0
                    summary['mainline']['friction_loss'] = sum(s.get('head_loss_m', s.get('friction_loss_m', 0)) for s in segs)
                    summary['mainline']['designed'] = True
                    summary['mainline']['flow_method'] = segs[0].get('flow_method', '') if segs else ''
                    break
    
    return summary


def get_sprinkler_info():
    """
    Get sprinkler data from sprinkler selection module.
    Same logic as hydraulic_design.py
    """
    sprinkler_data = st.session_state.project_data.get('sprinkler_data', {})
    if sprinkler_data:
        flow_lh = sprinkler_data.get('flow', 3000)  # l/h
        flow_m3h = flow_lh / 1000
        return {
            'name': sprinkler_data.get('model', 'Unknown'),
            'pressure_kpa': sprinkler_data.get('pressure', 300),
            'flow_m3h': flow_m3h,
            'flow_lh': flow_lh,
            'found': True
        }
    return {
        'name': 'Not Selected',
        'pressure_kpa': 300,
        'flow_m3h': 3.0,
        'flow_lh': 3000,
        'found': False
    }


def show_system_requirements():
    """Display and configure system requirements with automatic data linkage"""
    st.markdown('<h2 class="sub-header">System Requirements</h2>', unsafe_allow_html=True)
    
    # Get auto-detected values
    auto_flow, auto_head, auto_detected = get_system_requirements()
    
    # Get pipe network summary for display
    pipe_summary = get_pipe_network_summary()
    
    # Get sprinkler info
    sprinkler_info = get_sprinkler_info()
    
    # Initialize pump data
    if 'pump_data' not in st.session_state.project_data:
        st.session_state.project_data['pump_data'] = {}
    
    pump_data = st.session_state.project_data['pump_data']
    
    # ========================================================================
    # DATA LINKAGE STATUS SECTION
    # ========================================================================
    with st.expander("📊 Data Linkage Status", expanded=True):
        st.markdown("**Data is automatically linked from other modules:**")
        
        # Create status columns
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### 🔵 Sprinkler Selection")
            if sprinkler_info['found']:
                st.success(f"✅ {sprinkler_info['name']}")
                st.caption(f"   {sprinkler_info['pressure_kpa']} kPa, {sprinkler_info['flow_lh']:.0f} l/h")
            else:
                st.warning("⚠️ Not selected yet")
            
            st.markdown("##### 🌊 Sprinkler Line")
            if pipe_summary['sprinkler_line']['designed']:
                st.success(f"✅ {pipe_summary['sprinkler_line']['flow']:.2f} m³/h")
                st.caption(f"   Friction: {pipe_summary['sprinkler_line']['friction_loss']:.3f} m")
            else:
                st.info("📝 Not designed yet")
            
            st.markdown("##### 📏 Lateral Line")
            if pipe_summary['lateral']['designed']:
                st.success(f"✅ {pipe_summary['lateral']['flow']:.2f} m³/h")
                st.caption(f"   Friction: {pipe_summary['lateral']['friction_loss']:.3f} m")
            else:
                st.info("📝 Not designed yet")
        
        with col2:
            st.markdown("##### 🔀 Submain (Farthest)")
            if pipe_summary['submain']['designed']:
                st.success(f"✅ {pipe_summary['submain']['flow']:.2f} m³/h")
                st.caption(f"   Friction: {pipe_summary['submain']['friction_loss']:.3f} m")
            else:
                st.info("📝 Not designed yet")
            
            st.markdown("##### 🚰 Mainline")
            if pipe_summary['mainline']['designed']:
                flow_method = pipe_summary['mainline']['flow_method']
                method_badge = " (Max Daily)" if 'Max Daily' in flow_method else ""
                st.success(f"✅ {pipe_summary['mainline']['flow']:.2f} m³/h{method_badge}")
                st.caption(f"   Friction: {pipe_summary['mainline']['friction_loss']:.3f} m")
                if 'V3' in flow_method or 'Max Daily' in flow_method:
                    st.caption("   ℹ️ Flow considers operational scheduling")
            else:
                st.info("📝 Not designed yet")
            
            st.markdown("##### 🔧 Hydraulic Design")
            hyd_data = st.session_state.project_data.get('hydraulic_design', {})
            if hyd_data.get('total_head_required_m') or hyd_data.get('total_required_bar'):
                head_m = hyd_data.get('total_head_required_m', hyd_data.get('total_required_bar', 0) * 10.197)
                st.success(f"✅ Total Head: {head_m:.1f} m")
            else:
                st.info("📝 Not calculated yet")
        
        st.markdown("---")
        st.caption("💡 Data updates automatically when you recalculate designs. Refresh this page to see updates.")
    
    # ========================================================================
    # FLOW AND HEAD DISPLAY
    # ========================================================================
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 💧 Flow Requirement")
        
        if auto_detected['flow'] and auto_flow > 0:
            st.success(f"✅ Auto-detected from Pipe Network Design")
            
            # Show flow method info
            flow_method = auto_detected.get('flow_method', '')
            if 'Max Daily' in flow_method or 'V3' in flow_method:
                st.info("📅 Using **Max Daily Flow** (operational scheduling)")
            
            st.metric("Required Flow Rate", f"{auto_flow:.1f} m³/h")
            st.caption(f"({auto_flow / 3.6:.2f} l/s) | Source: {auto_detected.get('flow_source', 'Mainline')}")
            required_flow = auto_flow
        else:
            st.warning("⚠️ Complete Mainline design for auto-detection")
            required_flow = st.number_input(
                "Required Flow Rate (m³/h)",
                min_value=1.0,
                max_value=1000.0,
                value=pump_data.get('required_flow_m3h', 50.0),
                step=5.0,
                key="manual_flow"
            )
    
    with col2:
        st.markdown("#### 📊 Head Requirement")
        
        if auto_detected['head'] and auto_head > 0:
            st.success(f"✅ Auto-detected from Hydraulic Design")
            st.metric("Required Total Head", f"{auto_head:.1f} m")
            st.caption(f"({auto_head * 0.0981:.2f} bar) | Source: {auto_detected.get('head_source', 'Hydraulic Design')}")
            required_head = auto_head
        else:
            st.warning("⚠️ Complete Hydraulic Design for auto-detection")
            required_head = st.number_input(
                "Required Total Head (m)",
                min_value=5.0,
                max_value=200.0,
                value=pump_data.get('required_head_m', 40.0),
                step=5.0,
                key="manual_head"
            )
    
    st.markdown("---")
    
    # Additional parameters
    st.markdown("#### ⚙️ Additional Parameters")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        static_head_ratio = st.slider(
            "Static Head Ratio (%)",
            min_value=20,
            max_value=80,
            value=int(pump_data.get('static_head_ratio', 40)),
            step=5,
            help="Percentage of total head that is static (elevation + pressure)"
        )
    
    with col2:
        suction_lift = st.number_input(
            "Suction Lift (m)",
            min_value=0.0,
            max_value=8.0,
            value=pump_data.get('suction_lift', 0.0),
            step=0.5,
            help="Vertical distance from water source to pump"
        )
        
        if suction_lift > 7:
            st.error("⚠️ Cavitation risk! Consider submersible pump.")
    
    with col3:
        npsh_available = 10.33 - suction_lift - 1.0
        st.metric("NPSH Available", f"{npsh_available:.1f} m")
        
        if npsh_available < 2:
            st.error("❌ NPSH too low!")
    
    # Display summary
    st.markdown("---")
    st.markdown("### 📋 Requirements Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Flow", f"{required_flow:.1f} m³/h", delta=f"{required_flow/3.6:.1f} l/s")
    with col2:
        st.metric("Head", f"{required_head:.1f} m", delta=f"{required_head * 0.0981:.2f} bar")
    with col3:
        static_head = required_head * (static_head_ratio / 100)
        st.metric("Static Head", f"{static_head:.1f} m")
    with col4:
        friction_head = required_head - static_head
        st.metric("Friction Head", f"{friction_head:.1f} m")
    
    # Save requirements
    if st.button("💾 Save Requirements", type="primary", width="stretch"):
        st.session_state.project_data['pump_data'].update({
            'required_flow_m3h': required_flow,
            'required_head_m': required_head,
            'static_head_ratio': static_head_ratio,
            'static_head_m': static_head,
            'friction_head_m': friction_head,
            'suction_lift': suction_lift,
            'npsh_available': npsh_available
        })
        # Also save to temp state for cloud save
        st.session_state.temp_pump_data = st.session_state.project_data['pump_data'].copy()
        st.success("✅ Requirements saved! Proceed to Pump Matching.")
        st.rerun()


def show_pump_matching():
    """Show matching pumps with professional cards and multi-pump configurations"""
    st.markdown('<h2 class="sub-header">Pump Matching Engine</h2>', unsafe_allow_html=True)
    
    pump_data = st.session_state.project_data.get('pump_data', {})
    
    if 'required_flow_m3h' not in pump_data or 'required_head_m' not in pump_data:
        st.warning("⚠️ Please configure System Requirements first.")
        return
    
    required_flow = pump_data['required_flow_m3h']
    required_head = pump_data['required_head_m']
    
    # Load pump database
    try:
        db_manager = PumpDatabaseManager()
        all_pumps = db_manager.get_all_pumps()
    except Exception as e:
        st.error(f"Error loading pump database: {e}")
        return
    
    if not all_pumps:
        st.warning("No pumps found in database.")
        return
    
    # ============ PUMP CONFIGURATION SECTION ============
    st.markdown("### ⚙️ Pump Configuration")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        pump_config = st.radio(
            "Configuration Type",
            options=["Single Pump", "Parallel (↑ Flow)", "Series (↑ Head)"],
            help="Parallel: Multiple pumps increase total flow\nSeries: Multiple pumps increase total head",
            horizontal=True
        )
    
    with col2:
        if pump_config != "Single Pump":
            num_pumps = st.number_input(
                "Number of Pumps",
                min_value=2,
                max_value=6,
                value=2,
                step=1
            )
        else:
            num_pumps = 1
    
    with col3:
        # Calculate per-pump requirements
        if pump_config == "Parallel (↑ Flow)":
            per_pump_flow = required_flow / num_pumps
            per_pump_head = required_head
            config_icon = "🔀"
            config_desc = f"Each pump: {per_pump_flow:.1f} m³/h @ {per_pump_head:.1f} m"
        elif pump_config == "Series (↑ Head)":
            per_pump_flow = required_flow
            per_pump_head = required_head / num_pumps
            config_icon = "⬆️"
            config_desc = f"Each pump: {per_pump_flow:.1f} m³/h @ {per_pump_head:.1f} m"
        else:
            per_pump_flow = required_flow
            per_pump_head = required_head
            config_icon = "1️⃣"
            config_desc = f"Single pump: {per_pump_flow:.1f} m³/h @ {per_pump_head:.1f} m"
        
        st.info(f"{config_icon} {config_desc}")
    
    # Show configuration diagram
    if pump_config != "Single Pump":
        show_pump_configuration_diagram(pump_config, num_pumps, required_flow, required_head, per_pump_flow, per_pump_head)
    
    # Design point info box
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("System Flow", f"{required_flow:.1f} m³/h")
    with col2:
        st.metric("System Head", f"{required_head:.1f} m")
    with col3:
        st.metric("Per-Pump Flow", f"{per_pump_flow:.1f} m³/h")
    with col4:
        st.metric("Per-Pump Head", f"{per_pump_head:.1f} m")
    
    # Find suitable pumps for the per-pump requirements
    matches = db_manager.find_suitable_pumps(per_pump_flow, per_pump_head)
    
    # Filter options
    st.markdown("---")
    st.markdown("### 🔍 Filter Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        brand_filter = st.multiselect(
            "Filter by Brand",
            options=sorted(list(set(m.brand for m in matches))),
            default=[]
        )
    with col2:
        show_unsuitable = st.checkbox("Show all pumps (including unsuitable)", value=True)
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=["Match Score", "Efficiency", "Power", "Brand"],
            index=0
        )
    
    # Apply filters
    filtered_matches = matches
    if brand_filter:
        filtered_matches = [m for m in filtered_matches if m.brand in brand_filter]
    if not show_unsuitable:
        filtered_matches = [m for m in filtered_matches if m.is_suitable]
    
    # Sort
    if sort_by == "Match Score":
        filtered_matches.sort(key=lambda m: (-int(m.is_suitable), -m.match_score))
    elif sort_by == "Efficiency":
        filtered_matches.sort(key=lambda m: -m.efficiency_at_required_flow)
    elif sort_by == "Power":
        filtered_matches.sort(key=lambda m: m.power_at_required_flow)
    elif sort_by == "Brand":
        filtered_matches.sort(key=lambda m: (m.brand, m.model))
    
    # Display pump cards
    st.markdown("---")
    st.markdown("### 🏆 Available Pumps")
    
    if not filtered_matches:
        st.error("""
        ❌ **No matching pumps found!**
        
        **Try these options:**
        1. Switch to **Parallel** configuration to reduce flow per pump
        2. Switch to **Series** configuration to reduce head per pump
        3. Increase number of pumps
        4. Enable "Show all pumps" to see what's available
        """)
        return
    
    # Count suitable
    suitable_count = sum(1 for m in filtered_matches if m.is_suitable)
    total_in_db = len(matches)
    
    if suitable_count > 0:
        st.success(f"✅ Found **{suitable_count}** suitable pumps out of **{total_in_db}** in database")
    else:
        st.warning(f"⚠️ No exact matches. Showing **{len(filtered_matches)}** pumps - consider multi-pump configuration")
    
    # Render pump cards
    for i, match in enumerate(filtered_matches):
        render_pump_card_enhanced(match, i, per_pump_flow, per_pump_head, num_pumps, pump_config)


def show_pump_configuration_diagram(config_type: str, num_pumps: int, total_flow: float, total_head: float, per_pump_flow: float, per_pump_head: float):
    """Show a visual diagram of pump configuration"""
    
    if config_type == "Parallel (↑ Flow)":
        # Parallel configuration diagram
        st.markdown("""
        <div style="background: linear-gradient(135deg, #e3f2fd 0%, #bbdefb 100%); border-radius: 10px; padding: 20px; margin: 10px 0;">
            <h4 style="color: #1565c0; margin-bottom: 15px;">🔀 Parallel Pump Configuration</h4>
            <p style="color: #424242;"><b>How it works:</b> Pumps operate side-by-side, each contributing to total flow while maintaining the same head.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Visual representation
        cols = st.columns(num_pumps + 2)
        with cols[0]:
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: #e8f5e9; border-radius: 8px;">
                <b>INLET</b><br>
                ➡️<br>
                {total_flow:.0f} m³/h
            </div>
            """, unsafe_allow_html=True)
        
        for i in range(num_pumps):
            with cols[i + 1]:
                st.markdown(f"""
                <div style="text-align: center; padding: 15px; background: #fff3e0; border-radius: 8px; border: 2px solid #ff9800;">
                    <b>PUMP {i+1}</b><br>
                    🔧<br>
                    {per_pump_flow:.0f} m³/h<br>
                    @ {per_pump_head:.0f} m
                </div>
                """, unsafe_allow_html=True)
        
        with cols[-1]:
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; background: #e3f2fd; border-radius: 8px;">
                <b>OUTLET</b><br>
                ➡️<br>
                {total_flow:.0f} m³/h<br>
                @ {total_head:.0f} m
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f"""
        **Formula:** Total Flow = Pump₁ Flow + Pump₂ Flow + ... = **{num_pumps} × {per_pump_flow:.1f} = {total_flow:.1f} m³/h**
        
        **Advantages:**
        - ✅ Redundancy - system can operate if one pump fails
        - ✅ Variable capacity - run 1, 2, or all pumps as needed
        - ✅ Smaller individual pumps = lower cost per unit
        """)
    
    elif config_type == "Series (↑ Head)":
        # Series configuration diagram
        st.markdown("""
        <div style="background: linear-gradient(135deg, #fce4ec 0%, #f8bbd9 100%); border-radius: 10px; padding: 20px; margin: 10px 0;">
            <h4 style="color: #c2185b; margin-bottom: 15px;">⬆️ Series Pump Configuration</h4>
            <p style="color: #424242;"><b>How it works:</b> Pumps are staged one after another, each adding to the total head while maintaining the same flow.</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Visual representation - horizontal flow
        st.markdown(f"""
        <div style="display: flex; align-items: center; justify-content: center; gap: 10px; padding: 20px;">
            <div style="text-align: center; padding: 15px; background: #e8f5e9; border-radius: 8px;">
                <b>INLET</b><br>{total_flow:.0f} m³/h<br>0 m
            </div>
            <span style="font-size: 24px;">➡️</span>
        """, unsafe_allow_html=True)
        
        cols = st.columns(num_pumps + 1)
        cumulative_head = 0
        for i in range(num_pumps):
            cumulative_head += per_pump_head
            with cols[i]:
                st.markdown(f"""
                <div style="text-align: center; padding: 15px; background: #fff3e0; border-radius: 8px; border: 2px solid #ff9800;">
                    <b>PUMP {i+1}</b><br>
                    🔧<br>
                    +{per_pump_head:.0f} m<br>
                    Total: {cumulative_head:.0f} m
                </div>
                """, unsafe_allow_html=True)
        
        with cols[-1]:
            st.markdown(f"""
            <div style="text-align: center; padding: 15px; background: #e3f2fd; border-radius: 8px;">
                <b>OUTLET</b><br>
                {total_flow:.0f} m³/h<br>
                @ {total_head:.0f} m
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown(f"""
        **Formula:** Total Head = Pump₁ Head + Pump₂ Head + ... = **{num_pumps} × {per_pump_head:.1f} = {total_head:.1f} m**
        
        **Advantages:**
        - ✅ Achieve very high heads with standard pumps
        - ✅ Multistage concept - common in borehole pumps
        - ✅ Can use identical pumps for simplified maintenance
        """)


def show_power_configuration_summary(config_type: str, num_pumps: int):
    """Show a compact configuration summary for Power Analysis tab"""
    
    if config_type == "Parallel (↑ Flow)":
        icon = "🔀"
        color = "#1565c0"
        desc = "Pumps in parallel - flow is divided"
    elif config_type == "Series (↑ Head)":
        icon = "⬆️"
        color = "#c2185b"
        desc = "Pumps in series - head is divided"
    else:
        return  # No diagram needed for single pump
    
    pump_icons = " → ".join(["⚙️"] * min(num_pumps, 5))
    if num_pumps > 5:
        pump_icons += f" (+ {num_pumps - 5} more)"
    
    st.markdown(f"""
    <div style="background: linear-gradient(90deg, {color}20 0%, {color}10 100%); border-left: 4px solid {color}; border-radius: 4px; padding: 15px; margin-bottom: 15px;">
        <span style="font-size: 18px;">{icon} <b>{num_pumps}× Pumps {config_type.split(' ')[0]}</b></span>
        <br><span style="color: #666;">{desc}</span>
        <br><span style="font-size: 16px; color: #333;">{pump_icons}</span>
    </div>
    """, unsafe_allow_html=True)


def render_pump_card_enhanced(match: PumpMatch, index: int, per_pump_flow: float, per_pump_head: float, num_pumps: int, config_type: str):
    """Render an enhanced professional pump card with multi-pump support"""
    
    # Determine card style based on suitability
    if match.is_suitable:
        border_color = "#28a745"
        badge_text = "✅ SUITABLE"
        badge_color = "#28a745"
    else:
        border_color = "#ffc107"
        badge_text = "⚠️ CHECK SPECS"
        badge_color = "#ffc107"
    
    # Efficiency badge
    eff_color, eff_label = get_efficiency_badge_color(match.efficiency_at_required_flow)
    
    # Calculate total system values for multi-pump
    if config_type == "Parallel (↑ Flow)":
        total_power = match.power_at_required_flow * num_pumps
        system_desc = f"{num_pumps}× in parallel"
    elif config_type == "Series (↑ Head)":
        total_power = match.power_at_required_flow * num_pumps
        system_desc = f"{num_pumps}× in series"
    else:
        total_power = match.power_at_required_flow
        system_desc = "Single pump"
    
    with st.container():
        st.markdown(f"""
        <div style="border: 2px solid {border_color}; border-radius: 12px; padding: 20px; margin-bottom: 15px; background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%); box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                <div>
                    <h3 style="margin: 0; color: #2c3e50;">{match.brand}</h3>
                    <h4 style="margin: 0; color: #3498db;">{match.model}</h4>
                </div>
                <span style="background-color: {badge_color}; color: white; padding: 8px 20px; border-radius: 25px; font-weight: bold; font-size: 14px;">{badge_text}</span>
            </div>
            <p style="color: #7f8c8d; margin-bottom: 15px; font-style: italic;">{match.description}</p>
            <div style="background: #ecf0f1; padding: 8px 15px; border-radius: 20px; display: inline-block;">
                <span style="color: #2c3e50; font-weight: 500;">🔧 {system_desc}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Metrics row
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "Head @ Flow", 
                f"{match.head_at_required_flow:.1f} m",
                delta=f"{match.head_margin_percent:+.1f}%"
            )
        
        with col2:
            st.metric(
                "Per-Pump Power", 
                format_power_display(match.power_at_required_flow)
            )
        
        with col3:
            st.metric(
                "Total Power", 
                format_power_display(total_power),
                delta=f"{num_pumps} pump(s)" if num_pumps > 1 else None
            )
        
        with col4:
            st.metric(
                "Efficiency", 
                f"{match.efficiency_at_required_flow:.1f}%"
            )
        
        with col5:
            st.metric(
                "Match Score", 
                f"{match.match_score:.0f}/100"
            )
        
        # Efficiency badge
        st.markdown(f"""
        <span style="background-color: {eff_color}; color: white; padding: 5px 15px; border-radius: 15px; font-size: 13px; font-weight: 500;">
            {eff_label}
        </span>
        """, unsafe_allow_html=True)
        
        # Expandable details
        with st.expander(f"📊 Detailed Specifications - {match.model}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Pump Specifications:**")
                st.write(f"• Brand: {match.brand}")
                st.write(f"• Model: {match.model}")
                st.write(f"• RPM: {match.rpm}")
                st.write(f"• Impeller: {match.impeller_diameter_mm} mm")
            
            with col2:
                st.markdown("**Performance @ Design Point:**")
                st.write(f"• Head: {match.head_at_required_flow:.1f} m")
                st.write(f"• Efficiency: {match.efficiency_at_required_flow:.1f}%")
                st.write(f"• Power: {match.power_at_required_flow:.2f} kW")
                st.write(f"• Head Margin: {match.head_margin_percent:+.1f}%")
            
            with col3:
                st.markdown("**System Configuration:**")
                st.write(f"• Configuration: {config_type}")
                st.write(f"• Number of Pumps: {num_pumps}")
                st.write(f"• Total Power: {total_power:.2f} kW")
                if match.catalog_link:
                    st.markdown(f"[📖 View Manufacturer Catalog]({match.catalog_link})")
            
            # Cost estimate
            st.markdown("---")
            st.markdown("**💰 Estimated Costs (Budget):**")
            
            # Rough cost estimates based on power (USD)
            pump_cost_per_kw = 45  # USD per kW - rough estimate for agricultural pumps
            installation_factor = 1.3
            
            per_pump_cost = match.power_at_required_flow * pump_cost_per_kw
            total_pump_cost = per_pump_cost * num_pumps
            total_installed = total_pump_cost * installation_factor
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Per Pump (est.)", f"$ {per_pump_cost:,.0f}")
            with col2:
                st.metric("All Pumps (est.)", f"$ {total_pump_cost:,.0f}")
            with col3:
                st.metric("Installed (est.)", f"$ {total_installed:,.0f}")
            
            st.caption("*Estimates only - contact supplier for actual pricing*")
            
            # Select button
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button(f"✅ Select {match.brand} {match.model}", key=f"select_{index}", type="primary", width="stretch"):
                    st.session_state.project_data['pump_data'].update({
                        'selected_pump_id': match.pump_id,
                        'selected_brand': match.brand,
                        'selected_model': match.model,
                        'selected_head': match.head_at_required_flow,
                        'selected_efficiency': match.efficiency_at_required_flow,
                        'selected_power_kw': match.power_at_required_flow,
                        'pump_configuration': config_type,
                        'num_pumps': num_pumps,
                        'total_power_kw': total_power,
                        'per_pump_flow': per_pump_flow,
                        'per_pump_head': per_pump_head,
                        'duty_point': {
                            'flow_m3h': match.duty_point.flow_m3h,
                            'head_m': match.duty_point.head_m,
                            'efficiency': match.duty_point.efficiency_percent,
                            'power_kw': match.duty_point.power_kw
                        } if match.duty_point.is_valid else None
                    })
                    # Also save to temp state for cloud save
                    st.session_state.temp_pump_data = st.session_state.project_data['pump_data'].copy()
                    st.success(f"✅ {num_pumps}× {match.model} selected ({config_type})!")
                    st.rerun()
        
        st.markdown("<br>", unsafe_allow_html=True)


def show_performance_curves():
    """Show interactive pump and system curves - redesigned for clarity"""
    st.markdown('<h2 class="sub-header">Performance Curves</h2>', unsafe_allow_html=True)
    
    pump_data = st.session_state.project_data.get('pump_data', {})
    
    if 'selected_model' not in pump_data:
        st.warning("⚠️ Please select a pump first in the Pump Matching tab.")
        return
    
    required_flow = pump_data.get('required_flow_m3h', 50)
    required_head = pump_data.get('required_head_m', 40)
    static_ratio = pump_data.get('static_head_ratio', 40) / 100
    
    # Get multi-pump configuration
    pump_config = pump_data.get('pump_configuration', 'Single Pump')
    num_pumps = pump_data.get('num_pumps', 1)
    per_pump_flow = pump_data.get('per_pump_flow', required_flow)
    per_pump_head = pump_data.get('per_pump_head', required_head)
    
    # Display configuration info
    st.success(f"**Selected:** {num_pumps}× {pump_data.get('selected_brand', '')} {pump_data.get('selected_model', '')} ({pump_config})")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("System Flow", f"{required_flow:.1f} m³/h")
    with col2:
        st.metric("System Head", f"{required_head:.1f} m")
    with col3:
        st.metric("Per-Pump Flow", f"{per_pump_flow:.1f} m³/h")
    with col4:
        st.metric("Per-Pump Head", f"{per_pump_head:.1f} m")
    
    # Load selected pump data
    try:
        db_manager = PumpDatabaseManager()
        pump_db = db_manager.get_pump_by_id(pump_data.get('selected_pump_id', ''))
        
        if pump_db:
            solver = PumpCurveSolver(pump_db)
        else:
            st.error("Pump data not found in database.")
            return
    except Exception as e:
        st.error(f"Error: {e}")
        return
    
    # Show data source indicator
    data_source = solver.get_data_source()
    if solver.mode == "digitized":
        st.info(f"**Data Source:** {data_source} ✅ Accurate manufacturer data")
    else:
        st.warning(f"**Data Source:** {data_source} ⚠️ Estimated values - verify with manufacturer for final specification")
    
    # Generate pump curve data
    flows_single, heads_single, efficiencies = solver.generate_pump_curve_points(50)
    
    # System curve
    static_head = required_head * static_ratio
    friction_k = solver.calculate_system_curve_k(required_head, required_flow, static_ratio)
    max_flow_for_sys = solver.limits.max_flow_m3h * 1.1
    sys_flows, sys_heads = solver.generate_system_curve_points(static_head, friction_k, max_flow_for_sys, 50)
    
    # Find duty point
    duty_point = solver.find_duty_point(static_head, friction_k)
    
    # Get BEP info
    bep_flow = solver.bep.q_bep
    bep_head = solver.calculate_head(bep_flow)
    bep_eff = solver.bep.eff_bep
    
    # Calculate efficiency at operating point
    if duty_point.is_valid:
        operating_eff = duty_point.efficiency_percent
        duty_flow = duty_point.flow_m3h
        duty_head = duty_point.head_m
    else:
        operating_eff = 0
        duty_flow = required_flow
        duty_head = required_head
    
    # ========================================
    # CHART 1: H-Q Curve with Efficiency Zones
    # ========================================
    st.markdown("### 📈 Pump Head-Flow Curve (H-Q Diagram)")
    
    fig1 = go.Figure()
    
    # Add efficiency zone shading (background colored bands)
    # These show efficiency ranges along the pump curve
    max_head = max(heads_single) * 1.1
    
    # Create efficiency zones as colored regions under the pump curve
    # Zone colors: Red (low) -> Yellow (medium) -> Green (high)
    eff_zones = [
        (0, 50, 'rgba(255, 82, 82, 0.15)', 'Low Efficiency (<50%)'),
        (50, 65, 'rgba(255, 193, 7, 0.15)', 'Moderate (50-65%)'),
        (65, 75, 'rgba(255, 235, 59, 0.15)', 'Good (65-75%)'),
        (75, 100, 'rgba(76, 175, 80, 0.15)', 'Excellent (>75%)')
    ]
    
    # Add pump curve (main blue line)
    fig1.add_trace(
        go.Scatter(
            x=flows_single, 
            y=heads_single,
            mode='lines',
            name='Pump Curve (H-Q)',
            line=dict(color='#1565C0', width=4),
            hovertemplate='<b>Pump Curve</b><br>Flow: %{x:.1f} m³/h<br>Head: %{y:.1f} m<extra></extra>'
        )
    )
    
    # Add system curve (red dashed)
    fig1.add_trace(
        go.Scatter(
            x=sys_flows, 
            y=sys_heads,
            mode='lines',
            name='System Curve',
            line=dict(color='#E53935', width=3, dash='dash'),
            hovertemplate='<b>System Curve</b><br>Flow: %{x:.1f} m³/h<br>Head: %{y:.1f} m<extra></extra>'
        )
    )
    
    # Add BEP marker
    fig1.add_trace(
        go.Scatter(
            x=[bep_flow],
            y=[bep_head],
            mode='markers',
            name=f'BEP (η={bep_eff:.0f}%)',
            marker=dict(size=16, color='#4CAF50', symbol='circle', 
                       line=dict(width=2, color='white')),
            hovertemplate=f'<b>Best Efficiency Point</b><br>Flow: {bep_flow:.0f} m³/h<br>Head: {bep_head:.1f} m<br>Efficiency: {bep_eff:.0f}%<extra></extra>'
        )
    )
    
    # Add Operating Point with efficiency annotation
    if duty_point.is_valid:
        fig1.add_trace(
            go.Scatter(
                x=[duty_flow],
                y=[duty_head],
                mode='markers+text',
                name=f'Operating Point (η={operating_eff:.1f}%)',
                marker=dict(size=20, color='#FF9800', symbol='star', 
                           line=dict(width=2, color='#E65100')),
                text=[f'η={operating_eff:.0f}%'],
                textposition='top center',
                textfont=dict(size=12, color='#E65100', family='Arial Black'),
                hovertemplate=f'<b>OPERATING POINT</b><br>Flow: {duty_flow:.1f} m³/h<br>Head: {duty_head:.1f} m<br>Efficiency: {operating_eff:.1f}%<extra></extra>'
            )
        )
    
    # Add Design Point
    fig1.add_trace(
        go.Scatter(
            x=[required_flow],
            y=[required_head],
            mode='markers',
            name='Design Requirement',
            marker=dict(size=14, color='#9C27B0', symbol='diamond',
                       line=dict(width=2, color='white')),
            hovertemplate=f'<b>Design Point</b><br>Flow: {required_flow:.1f} m³/h<br>Head: {required_head:.1f} m<extra></extra>'
        )
    )
    
    fig1.update_layout(
        title=dict(
            text=f"<b>{pump_data.get('selected_brand', '')} {pump_data.get('selected_model', '')}</b>",
            x=0.5,
            font=dict(size=16)
        ),
        xaxis_title="Flow Rate Q (m³/h)",
        yaxis_title="Head H (m)",
        template="plotly_white",
        height=450,
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        ),
        hovermode='closest'
    )
    
    st.plotly_chart(fig1, width="stretch")
    
    # ========================================
    # CHART 2: Efficiency Curve (Simple & Clear)
    # ========================================
    st.markdown("### 📊 Pump Efficiency Curve")
    
    fig2 = go.Figure()
    
    # Efficiency curve
    fig2.add_trace(
        go.Scatter(
            x=flows_single,
            y=efficiencies,
            mode='lines',
            name='Efficiency Curve',
            line=dict(color='#4CAF50', width=3),
            fill='tozeroy',
            fillcolor='rgba(76, 175, 80, 0.2)',
            hovertemplate='Flow: %{x:.1f} m³/h<br>Efficiency: %{y:.1f}%<extra></extra>'
        )
    )
    
    # Mark BEP on efficiency curve
    fig2.add_trace(
        go.Scatter(
            x=[bep_flow],
            y=[bep_eff],
            mode='markers+text',
            name=f'BEP ({bep_eff:.0f}%)',
            marker=dict(size=14, color='#2E7D32', symbol='circle',
                       line=dict(width=2, color='white')),
            text=[f'Peak: {bep_eff:.0f}%'],
            textposition='top center',
            textfont=dict(size=11, color='#2E7D32'),
            hovertemplate=f'<b>Best Efficiency Point</b><br>Flow: {bep_flow:.0f} m³/h<br>Efficiency: {bep_eff:.0f}%<extra></extra>'
        )
    )
    
    # Mark Operating Point on efficiency curve
    if duty_point.is_valid:
        fig2.add_trace(
            go.Scatter(
                x=[duty_flow],
                y=[operating_eff],
                mode='markers+text',
                name=f'Operating ({operating_eff:.1f}%)',
                marker=dict(size=16, color='#FF9800', symbol='star',
                           line=dict(width=2, color='#E65100')),
                text=[f'{operating_eff:.0f}%'],
                textposition='bottom center',
                textfont=dict(size=12, color='#E65100', family='Arial Black'),
                hovertemplate=f'<b>Operating Point</b><br>Flow: {duty_flow:.1f} m³/h<br>Efficiency: {operating_eff:.1f}%<extra></extra>'
            )
        )
        
        # Add vertical line from operating point to x-axis for clarity
        fig2.add_shape(
            type="line",
            x0=duty_flow, y0=0,
            x1=duty_flow, y1=operating_eff,
            line=dict(color="#FF9800", width=2, dash="dot")
        )
        
        # Add horizontal line from operating point to y-axis
        fig2.add_shape(
            type="line",
            x0=0, y0=operating_eff,
            x1=duty_flow, y1=operating_eff,
            line=dict(color="#FF9800", width=2, dash="dot")
        )
    
    # Add efficiency zones as horizontal bands
    fig2.add_hrect(y0=0, y1=50, fillcolor="rgba(255,82,82,0.1)", 
                   line_width=0, annotation_text="Low", annotation_position="right")
    fig2.add_hrect(y0=50, y1=65, fillcolor="rgba(255,193,7,0.1)", 
                   line_width=0, annotation_text="Moderate", annotation_position="right")
    fig2.add_hrect(y0=65, y1=75, fillcolor="rgba(255,235,59,0.1)", 
                   line_width=0, annotation_text="Good", annotation_position="right")
    fig2.add_hrect(y0=75, y1=100, fillcolor="rgba(76,175,80,0.1)", 
                   line_width=0, annotation_text="Excellent", annotation_position="right")
    
    fig2.update_layout(
        title=dict(
            text="<b>Efficiency vs Flow Rate</b>",
            x=0.5,
            font=dict(size=14)
        ),
        xaxis_title="Flow Rate Q (m³/h)",
        yaxis_title="Efficiency η (%)",
        template="plotly_white",
        height=350,
        yaxis=dict(range=[0, 100]),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5
        )
    )
    
    st.plotly_chart(fig2, width="stretch")
    
    # ========================================
    # VISUAL EFFICIENCY SUMMARY
    # ========================================
    st.markdown("---")
    st.markdown("### 🎯 Operating Point Summary")
    
    # Create a clear visual summary
    if duty_point.is_valid:
        # Efficiency gauge using progress bar style
        eff_color = "#4CAF50" if operating_eff > 75 else "#FFC107" if operating_eff >= 60 else "#F44336"
        eff_rating = "🟢 Excellent" if operating_eff > 75 else "🟡 Good" if operating_eff >= 60 else "🔴 Low"
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("##### 📍 Operating Point")
            st.markdown(f"""
            | Parameter | Value |
            |-----------|-------|
            | **Flow Rate** | {duty_flow:.1f} m³/h |
            | **Head** | {duty_head:.1f} m |
            | **Efficiency** | {operating_eff:.1f}% |
            | **Shaft Power** | {duty_point.power_kw:.1f} kW |
            """)
        
        with col2:
            st.markdown("##### 🎯 Best Efficiency Point (BEP)")
            st.markdown(f"""
            | Parameter | Value |
            |-----------|-------|
            | **BEP Flow** | {bep_flow:.1f} m³/h |
            | **BEP Head** | {bep_head:.1f} m |
            | **Peak Efficiency** | {bep_eff:.1f}% |
            """)
            
            # Deviation from BEP
            deviation = abs(duty_flow - bep_flow) / bep_flow * 100
            deviation_status = "🟢 Optimal" if deviation <= 15 else "🟡 Acceptable" if deviation <= 30 else "🔴 Far"
            st.markdown(f"**Deviation:** {deviation:.0f}% ({deviation_status})")
        
        with col3:
            st.markdown("##### ⚡ Efficiency Rating")
            
            # Visual efficiency bar
            st.markdown(f"<h1 style='text-align: center; color: {eff_color};'>{operating_eff:.0f}%</h1>", 
                       unsafe_allow_html=True)
            st.markdown(f"<p style='text-align: center; font-size: 18px;'>{eff_rating}</p>", 
                       unsafe_allow_html=True)
            
            # Progress bar
            st.progress(operating_eff / 100)
            
            # Efficiency scale legend
            st.caption("Scale: 🔴 <60% | 🟡 60-75% | 🟢 >75%")
    else:
        st.warning("⚠️ Could not calculate operating point. Check pump selection.")
    
    # Explanation
    with st.expander("ℹ️ Understanding the Charts"):
        st.markdown("""
        ### Chart 1: Head-Flow Curve (H-Q Diagram)
        This is the main pump performance chart:
        - **Blue Line (Pump Curve)**: Shows how much head (pressure) the pump can deliver at different flow rates
        - **Red Dashed Line (System Curve)**: Shows how much head your piping system requires at different flow rates
        - **Orange Star (Operating Point)**: Where the pump actually operates - intersection of pump and system curves
        - **Purple Diamond (Design Point)**: Your design requirements
        - **Green Circle (BEP)**: Best Efficiency Point - where the pump is most efficient
        
        ### Chart 2: Efficiency Curve
        Shows pump efficiency at different flow rates:
        - **Green Line**: Efficiency curve peaks at BEP and drops off on both sides
        - **Colored Zones**: Background shows efficiency quality regions
        - **Dotted Lines**: Show exactly where your operating point falls on the efficiency scale
        
        ### Reading Your Efficiency
        1. Find the **Orange Star** (Operating Point) on the efficiency chart
        2. Follow the **horizontal dotted line** to the Y-axis to read efficiency
        3. The number shown directly on the star is your operating efficiency
        """)
    
    # Show pump curve data for transparency
    with st.expander("📊 Pump Curve Data Source"):
        if solver.mode == "digitized":
            st.success("✅ **Digitized Manufacturer Data** - High accuracy")
            st.markdown(f"**Source:** {solver.digitized.source if solver.digitized.source else 'Not specified'}")
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### H-Q Data Points")
                import pandas as pd
                hq_df = pd.DataFrame({
                    'Flow (m³/h)': solver.digitized.flow_points,
                    'Head (m)': solver.digitized.head_points
                })
                st.dataframe(hq_df, width="stretch", hide_index=True)
            
            with col2:
                st.markdown("##### Efficiency Data Points")
                eff_df = pd.DataFrame({
                    'Flow (m³/h)': solver.digitized.eff_flow_points,
                    'Efficiency (%)': solver.digitized.eff_points
                })
                st.dataframe(eff_df, width="stretch", hide_index=True)
        else:
            st.warning("⚠️ **BEP Estimation Model** - For preliminary design only")
            st.markdown("""
            This pump uses an **estimated** efficiency curve based on the Best Efficiency Point (BEP).
            
            **Parameters used:**
            """)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("BEP Flow", f"{solver.bep.q_bep:.0f} m³/h")
            with col2:
                st.metric("BEP Efficiency", f"{solver.bep.eff_bep:.0f}%")
            with col3:
                st.metric("Shape Factor", f"{solver.bep.shape_factor:.1f}")
            
            st.markdown("""
            **⚠️ Important:** For final pump specification, obtain the actual manufacturer performance curve 
            and use digitized data for accurate efficiency values.
            
            **How to get accurate data:**
            1. Request performance curves from pump manufacturer (PDF or datasheet)
            2. Digitize the H-Q and efficiency curves (use tools like WebPlotDigitizer)
            3. Add the digitized data points to the pump database
            """)
    
    # Save Performance Curves Analysis
    st.markdown("---")
    if st.button("💾 Save Performance Analysis", type="primary", width="stretch"):
        # Update pump data with performance curve info
        st.session_state.project_data['pump_data'].update({
            'performance_curves_saved': True,
            'operating_duty_point': {
                'flow_m3h': duty_point.flow_m3h if duty_point.is_valid else None,
                'head_m': duty_point.head_m if duty_point.is_valid else None,
                'efficiency_percent': duty_point.efficiency_percent if duty_point.is_valid else None,
                'power_kw': duty_point.power_kw if duty_point.is_valid else None
            }
        })
        # Also save to temp state for cloud save
        st.session_state.temp_pump_data = st.session_state.project_data['pump_data'].copy()
        st.success("✅ Performance analysis saved! Will be included in cloud save.")


def show_power_analysis():
    """Show power and energy analysis with multi-pump support"""
    st.markdown('<h2 class="sub-header">Power & Energy Analysis</h2>', unsafe_allow_html=True)
    
    pump_data = st.session_state.project_data.get('pump_data', {})
    
    if 'selected_model' not in pump_data:
        st.warning("⚠️ Please select a pump first.")
        return
    
    # Get multi-pump configuration
    pump_config = pump_data.get('pump_configuration', 'Single Pump')
    num_pumps = pump_data.get('num_pumps', 1)
    per_pump_flow = pump_data.get('per_pump_flow', pump_data.get('required_flow_m3h', 50))
    per_pump_head = pump_data.get('per_pump_head', pump_data.get('required_head_m', 40))
    
    # Display configuration
    st.success(f"**Configuration:** {num_pumps}× {pump_data.get('selected_brand', '')} {pump_data.get('selected_model', '')} ({pump_config})")
    
    # Configuration diagram for multi-pump
    if num_pumps > 1:
        show_power_configuration_summary(pump_config, num_pumps)
    
    # Get values (per pump for power calculation)
    flow = per_pump_flow
    head = per_pump_head
    pump_efficiency = pump_data.get('selected_efficiency', 70)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### ⚡ Power Calculations (Per Pump)")
        
        st.latex(r"P_{kW} = \frac{Q \times H}{367 \times \eta}")
        
        st.markdown("**Per Pump Values:**")
        st.markdown(f"- Q = {flow:.1f} m³/h")
        st.markdown(f"- H = {head:.1f} m")
        st.markdown(f"- η = {pump_efficiency:.1f}% = {pump_efficiency/100:.3f}")
        
        # Calculate power per pump using metric formula
        power_per_pump_kw = (flow * head) / (367 * (pump_efficiency / 100))
        
        # Total power for all pumps
        total_pump_power_kw = power_per_pump_kw * num_pumps
        
        st.markdown("---")
        
        # Motor efficiency
        motor_efficiency = st.slider(
            "Motor Efficiency (%)",
            min_value=70,
            max_value=95,
            value=85,
            step=1
        )
        
        motor_power_per_pump = power_per_pump_kw / (motor_efficiency / 100)
        total_motor_power = motor_power_per_pump * num_pumps
        
        # Per pump metrics
        st.markdown("#### Per Pump")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric("Shaft Power", f"{power_per_pump_kw:.2f} kW")
        with col_b:
            st.metric("Motor Input", f"{motor_power_per_pump:.2f} kW")
        
        # Total metrics (for multi-pump)
        if num_pumps > 1:
            st.markdown(f"#### Total ({num_pumps} Pumps)")
            col_c, col_d = st.columns(2)
            with col_c:
                st.metric("Total Shaft Power", f"{total_pump_power_kw:.2f} kW")
            with col_d:
                st.metric("Total Motor Input", f"{total_motor_power:.2f} kW")
        
        # Overall efficiency
        overall_eff = (pump_efficiency / 100) * (motor_efficiency / 100) * 100
        st.metric("Overall Wire-to-Water Efficiency", f"{overall_eff:.1f}%")
    
    with col2:
        st.markdown("### 📅 Energy Consumption")
        
        # Operating schedule
        hours_per_day = st.number_input(
            "Operating Hours per Day",
            min_value=1,
            max_value=24,
            value=int(pump_data.get('operating_hours', 10)),
            step=1
        )
        
        days_per_year = st.number_input(
            "Operating Days per Year",
            min_value=1,
            max_value=365,
            value=int(pump_data.get('operating_days', 180)),
            step=10
        )
        
        annual_hours = hours_per_day * days_per_year
        # Use total motor power for all pumps
        daily_energy = total_motor_power * hours_per_day
        annual_energy = total_motor_power * annual_hours
        
        if num_pumps > 1:
            st.info(f"**Note:** Energy calculated for all {num_pumps} pumps running simultaneously")
        
        st.metric("Daily Energy", f"{daily_energy:.1f} kWh")
        st.metric("Annual Energy", f"{annual_energy:,.0f} kWh")
        st.metric("Annual Operating Hours", f"{annual_hours:,} hrs")
    
    # Cost analysis
    st.markdown("---")
    st.markdown("### 💰 Energy Cost Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Get stored rate, but clamp to valid USD range if it's an old ZAR value
        stored_rate = pump_data.get('electricity_rate', 0.12)
        if stored_rate > 0.50:  # Old ZAR value stored, convert to reasonable USD default
            stored_rate = 0.12
        
        electricity_rate = st.number_input(
            "Electricity Rate ($/kWh)",
            min_value=0.05,
            max_value=0.50,
            value=stored_rate,
            step=0.01,
            help="US electricity rate (avg. $0.10-0.15/kWh)"
        )
    
    with col2:
        daily_cost = daily_energy * electricity_rate
        st.metric("Daily Cost", f"$ {daily_cost:,.2f}")
    
    with col3:
        annual_cost = annual_energy * electricity_rate
        st.metric("Annual Cost", f"$ {annual_cost:,.0f}")
    
    # Multi-pump cost breakdown
    if num_pumps > 1:
        st.markdown("---")
        st.markdown("### 🔢 Multi-Pump Cost Breakdown")
        
        pump_unit_price = pump_data.get('selected_price', 0)
        total_equipment_cost = pump_unit_price * num_pumps
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Unit Price", f"$ {pump_unit_price:,.0f}")
        with col2:
            st.metric(f"Total Equipment ({num_pumps}×)", f"$ {total_equipment_cost:,.0f}")
        with col3:
            # Installation estimate (20% of equipment)
            installation = total_equipment_cost * 0.20
            st.metric("Est. Installation", f"$ {installation:,.0f}")
        with col4:
            total_project = total_equipment_cost + installation
            st.metric("Total Project Cost", f"$ {total_project:,.0f}")
    
    # Comparison chart
    st.markdown("---")
    st.markdown("### 📊 Power Source Comparison")
    
    power_sources = {
        'Grid Power': {'cost': electricity_rate, 'reliability': 0.95, 'carbon': 'Medium'},
        'Diesel Generator': {'cost': 0.25, 'reliability': 0.95, 'carbon': 'Very High'},
        'Solar PV + Battery': {'cost': 0.08, 'reliability': 0.85, 'carbon': 'Very Low'},
        'Solar PV (Day only)': {'cost': 0.05, 'reliability': 0.70, 'carbon': 'Zero'}
    }
    
    comparison_data = []
    for source, data in power_sources.items():
        annual_cost_src = annual_energy * data['cost']
        comparison_data.append({
            'Power Source': source,
            'Cost ($/kWh)': data['cost'],
            'Annual Cost ($)': annual_cost_src,
            'Reliability': f"{data['reliability']*100:.0f}%",
            'Carbon Footprint': data['carbon']
        })
    
    df_comparison = pd.DataFrame(comparison_data)
    
    st.dataframe(
        df_comparison,
        width="stretch",
        hide_index=True,
        column_config={
            "Cost ($/kWh)": st.column_config.NumberColumn(format="$ %.2f"),
            "Annual Cost ($)": st.column_config.NumberColumn(format="$ %,.0f")
        }
    )
    
    # Save button
    st.markdown("---")
    if st.button("💾 Save Power Analysis", type="primary", width="stretch"):
        st.session_state.project_data['pump_data'].update({
            'pump_power_per_unit_kw': power_per_pump_kw,
            'total_pump_power_kw': total_pump_power_kw,
            'motor_power_per_unit_kw': motor_power_per_pump,
            'total_motor_power_kw': total_motor_power,
            'motor_efficiency': motor_efficiency,
            'overall_efficiency': overall_eff,
            'operating_hours': hours_per_day,
            'operating_days': days_per_year,
            'annual_energy_kwh': annual_energy,
            'electricity_rate': electricity_rate,
            'annual_cost': annual_cost,
            'num_pumps': num_pumps,
            'pump_configuration': pump_config,
            'power_analysis_saved': True
        })
        # Also save to temp state for cloud save
        st.session_state.temp_pump_data = st.session_state.project_data['pump_data'].copy()
        st.success("✅ Power analysis saved! Will be included in cloud save.")
