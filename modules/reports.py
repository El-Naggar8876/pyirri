"""
Reports & Export Module
Generate comprehensive design reports and export data from all project modules.

Data Sources:
- project_data: Basic project info (name, location, area)
- field_geometry: Field dimensions and shape
- sprinkler_data: Selected sprinkler details
- operational_data: Irrigation scheduling and subplot configuration
- sprinkler_line_design: Sprinkler pipe design
- lateral_design: Lateral pipe design  
- submain_*_design: Submain pipe designs
- mainline_*_design: Mainline pipe designs
- network_summary: Complete pipe network summary
- hydraulic_design: System pressure and head calculations
- pump_data: Pump selection and performance
- cost_data: BOQ and cost estimates
- irrigation_requirements: Crop water requirements
- crop_parameters: Crop type and coefficients
- climate_data: Weather/climate information
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import io
import json
from typing import Dict, List, Any, Optional

# ============================================================================
# DATA EXTRACTION HELPERS
# ============================================================================

def get_project_data() -> dict:
    """Get project_data with safe defaults"""
    if 'project_data' not in st.session_state:
        st.session_state.project_data = {}
    return st.session_state.project_data

def safe_get(data: dict, *keys, default=None):
    """Safely navigate nested dictionaries"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data if data is not None else default

def get_all_data_sources() -> Dict[str, Dict]:
    """Get all available data sources with their status"""
    project = get_project_data()
    
    sources = {
        'project_info': {
            'name': 'Project Information',
            'data': {
                'project_name': project.get('project_name'),
                'location': project.get('location'),
                'area': project.get('area'),
            },
            'available': bool(project.get('project_name'))
        },
        'field_geometry': {
            'name': 'Field Geometry',
            'data': project.get('field_geometry', {}),
            'available': bool(project.get('field_geometry'))
        },
        'sprinkler_data': {
            'name': 'Sprinkler Selection',
            'data': project.get('sprinkler_data', {}),
            'available': bool(project.get('sprinkler_data'))
        },
        'operational_data': {
            'name': 'Operational Design',
            'data': project.get('operational_data', {}),
            'available': bool(project.get('operational_data'))
        },
        'irrigation_requirements': {
            'name': 'Crop Water Requirements',
            'data': project.get('irrigation_requirements', {}),
            'available': bool(project.get('irrigation_requirements'))
        },
        'sprinkler_line_design': {
            'name': 'Sprinkler Line Design',
            'data': project.get('sprinkler_line_design', {}),
            'available': bool(project.get('sprinkler_line_design'))
        },
        'lateral_design': {
            'name': 'Lateral Design',
            'data': project.get('lateral_design', {}),
            'available': bool(project.get('lateral_design'))
        },
        'network_summary': {
            'name': 'Pipe Network Summary',
            'data': project.get('network_summary', {}),
            'available': bool(project.get('network_summary'))
        },
        'hydraulic_design': {
            'name': 'Hydraulic Design',
            'data': project.get('hydraulic_design', {}),
            'available': bool(project.get('hydraulic_design'))
        },
        'pump_data': {
            'name': 'Pump Selection',
            'data': project.get('pump_data', {}),
            'available': bool(project.get('pump_data', {}).get('selected_model') or project.get('pump_data', {}).get('selected_pump_id'))
        },
        'cost_data': {
            'name': 'Cost Estimation',
            'data': project.get('cost_data', {}),
            'available': bool(project.get('cost_data', {}).get('boq') or project.get('cost_data', {}).get('materials_subtotal'))
        }
    }
    
    # Check for submain designs
    submain_designs = {}
    for key in project.keys():
        if key.startswith('submain_') and key.endswith('_design'):
            submain_designs[key] = project[key]
    if submain_designs:
        sources['submain_designs'] = {
            'name': f'Submain Designs ({len(submain_designs)})',
            'data': submain_designs,
            'available': True
        }
    
    # Check for mainline designs
    mainline_designs = {}
    for key in project.keys():
        if key.startswith('mainline_') and key.endswith('_design'):
            mainline_designs[key] = project[key]
    if mainline_designs:
        sources['mainline_designs'] = {
            'name': f'Mainline Designs ({len(mainline_designs)})',
            'data': mainline_designs,
            'available': True
        }
    
    return sources

def calculate_data_completeness() -> tuple:
    """Calculate project data completeness"""
    sources = get_all_data_sources()
    
    # Core required sections
    required = ['project_info', 'sprinkler_data', 'operational_data', 'pump_data']
    optional = ['field_geometry', 'irrigation_requirements', 'sprinkler_line_design', 
                'lateral_design', 'network_summary', 'hydraulic_design', 'cost_data']
    
    required_complete = sum(1 for s in required if sources.get(s, {}).get('available', False))
    optional_complete = sum(1 for s in optional if sources.get(s, {}).get('available', False))
    
    total_complete = required_complete + optional_complete
    total_sections = len(required) + len(optional)
    
    return required_complete, len(required), optional_complete, len(optional), total_complete, total_sections

# ============================================================================
# MAIN MODULE
# ============================================================================

def show():
    st.markdown('<h1 class="main-header">📑 Reports & Export</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    Generate comprehensive design reports and export project data. Reports are automatically 
    populated from your completed design modules.
    </div>
    """, unsafe_allow_html=True)
    
    # Show data completeness status
    show_data_completeness_status()
    
    tabs = st.tabs(["📊 Project Dashboard", "📝 Design Report", "📋 Technical Specs", 
                    "📥 Export Data", "🔍 Data Inspector"])
    
    with tabs[0]:
        show_project_dashboard()
    
    with tabs[1]:
        show_design_report()
    
    with tabs[2]:
        show_technical_specs()
    
    with tabs[3]:
        show_export_data()
    
    with tabs[4]:
        show_data_inspector()

def show_data_completeness_status():
    """Show status bar of data completeness"""
    req_done, req_total, opt_done, opt_total, total_done, total = calculate_data_completeness()
    
    completion_pct = (total_done / total) * 100 if total > 0 else 0
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        st.progress(completion_pct / 100)
    
    with col2:
        st.metric("Design Completion", f"{completion_pct:.0f}%")
    
    with col3:
        if req_done < req_total:
            st.warning(f"Required: {req_done}/{req_total}")
        else:
            st.success(f"Required: {req_done}/{req_total} ✓")

# ============================================================================
# PROJECT DASHBOARD
# ============================================================================

def show_project_dashboard():
    """Show comprehensive project dashboard with all key metrics"""
    st.markdown('<h2 class="sub-header">Project Dashboard</h2>', unsafe_allow_html=True)
    
    project = get_project_data()
    sources = get_all_data_sources()
    
    # Project Header
    st.markdown("### 🏗️ Project Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        project_name = project.get('project_name', 'Unnamed Project')
        st.metric("Project Name", project_name if project_name else "Not Set")
    
    with col2:
        area = project.get('area', 0)
        field_geom = project.get('field_geometry', {})
        if field_geom.get('area_ha'):
            area = field_geom['area_ha']
        st.metric("Field Area", f"{area:.2f} ha" if area else "Not Set")
    
    with col3:
        location = project.get('location', '')
        st.metric("Location", location if location else "Not Set")
    
    with col4:
        # Get crop type - check direct crop_type first, then fallbacks
        crop = project.get('crop_type', '')
        if not crop:
            crop = safe_get(project, 'irrigation_requirements', 'crop_type', default='')
        if not crop:
            crop = safe_get(project, 'crop_parameters', 'crop_name', default='')
        st.metric("Crop", crop if crop else "Not Set")
    
    st.markdown("---")
    
    # Sprinkler System Section
    if sources['sprinkler_data']['available']:
        st.markdown("### 🎯 Sprinkler System")
        spr = project.get('sprinkler_data', {})
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Model", spr.get('model', 'N/A'))
        with col2:
            st.metric("Nozzle", spr.get('nozzle', 'N/A'))
        with col3:
            st.metric("Pressure", f"{spr.get('pressure', 0)} kPa")
        with col4:
            st.metric("Flow Rate", f"{spr.get('flow', 0)} l/h")
        with col5:
            spacing_along = spr.get('spacing_along', 0)
            spacing_between = spr.get('spacing_between', 0)
            st.metric("Spacing", f"{spacing_along:.2f}×{spacing_between:.2f} m")
        
        st.markdown("---")
    
    # Operational Design Section
    if sources['operational_data']['available']:
        st.markdown("### 📋 Operational Design")
        op = project.get('operational_data', {})
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            n_lines = op.get('N_sprinkler_lines', 0)
            st.metric("Sprinkler Lines", f"{n_lines}")
        with col2:
            n_per_line = op.get('N_sprinklers_line', 0)
            st.metric("Sprinklers/Line", f"{n_per_line}")
        with col3:
            total_spr = op.get('total_sprinklers', n_lines * n_per_line if n_lines and n_per_line else 0)
            st.metric("Total Sprinklers", f"{total_spr:,}")
        with col4:
            subplots = op.get('total_subplots', 0)
            st.metric("Subplots", f"{subplots}")
        with col5:
            irr_days = op.get('total_irrigation_days', 0)
            st.metric("Irrigation Days", f"{irr_days}")
        
        st.markdown("---")
    
    # Pipe Network Section
    has_pipe_data = (sources.get('sprinkler_line_design', {}).get('available') or 
                     sources.get('lateral_design', {}).get('available') or
                     sources.get('network_summary', {}).get('available'))
    
    if has_pipe_data:
        st.markdown("### 🔧 Pipe Network")
        
        # Calculate pipe totals
        pipe_summary = calculate_pipe_summary(project)
        
        if pipe_summary:
            cols = st.columns(len(pipe_summary))
            for i, (pipe_type, data) in enumerate(pipe_summary.items()):
                with cols[i]:
                    st.metric(
                        pipe_type, 
                        f"{data['total_length']:.0f} m",
                        help=f"Sizes: {data['sizes']}"
                    )
        
        st.markdown("---")
    
    # Hydraulic Design Section
    if sources['hydraulic_design']['available']:
        st.markdown("### 💧 Hydraulic Design")
        hyd = project.get('hydraulic_design', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # total_head_required_m is the primary key saved by hydraulic_design module
            total_head = hyd.get('total_head_required_m', hyd.get('total_head_m', hyd.get('design_head', 0)))
            st.metric("Total Head", f"{total_head:.1f} m")
        with col2:
            static_head = hyd.get('static_head_m', hyd.get('head_difference_m', hyd.get('elevation_diff', 0)))
            st.metric("Static Head", f"{static_head:.1f} m")
        with col3:
            # Sum all friction losses from stored bar values
            total_friction = (hyd.get('sprinkler_line_loss_bar', 0) + hyd.get('lateral_loss_bar', 0) + 
                              hyd.get('submain_loss_bar', 0) + hyd.get('mainline_loss_bar', 0)) * 10.197
            friction_loss = hyd.get('total_pipe_loss_m', total_friction)
            st.metric("Friction Loss", f"{friction_loss:.1f} m")
        with col4:
            # Sprinkler pressure in bar converted to m
            pressure_bar = hyd.get('sprinkler_pressure_bar', 0)
            pressure_m = pressure_bar * 10.197 if pressure_bar > 0 else hyd.get('operating_pressure', 0)/10
            st.metric("Operating Pressure", f"{pressure_m:.1f} m")
        
        st.markdown("---")
    
    # Pump Selection Section
    if sources['pump_data']['available']:
        st.markdown("### ⚡ Pump Selection")
        pump = project.get('pump_data', {})
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            model = pump.get('selected_model', pump.get('model', 'N/A'))
            st.metric("Model", model)
        with col2:
            brand = pump.get('selected_brand', pump.get('brand', ''))
            st.metric("Brand", brand if brand else "N/A")
        with col3:
            # Get flow from duty_point or required flow
            duty = pump.get('duty_point', {})
            if duty and duty.get('flow_m3h'):
                flow = duty['flow_m3h']
            else:
                flow = pump.get('per_pump_flow', pump.get('required_flow_m3h', 0))
            st.metric("Flow Rate", f"{flow:.1f} m³/h")
        with col4:
            # Get head from duty_point or selected head or required head
            if duty and duty.get('head_m'):
                head = duty['head_m']
            else:
                head = pump.get('selected_head', pump.get('required_head_m', 0))
            st.metric("Head", f"{head:.1f} m")
        with col5:
            # Get power from duty_point or calculated
            if duty and duty.get('power_kw'):
                power = duty['power_kw']
            else:
                power = pump.get('selected_power_kw', pump.get('total_power_kw', 0))
            st.metric("Power", f"{power:.1f} kW")
        
        # Efficiency info
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            # Get efficiency from duty_point or selected_efficiency
            if duty and duty.get('efficiency'):
                eff = duty['efficiency']
            else:
                eff = pump.get('selected_efficiency', 0)
            st.metric("Efficiency", f"{eff:.1f}%")
        with col2:
            num_pumps = pump.get('num_pumps', 1)
            if num_pumps > 1:
                st.metric("Configuration", f"{num_pumps}× Pumps")
            else:
                config = pump.get('pump_configuration', 'Single Pump')
                st.metric("Configuration", config)
        with col3:
            rpm = pump.get('rpm', 0)
            if rpm > 0:
                st.metric("Speed", f"{rpm} RPM")
        
        st.markdown("---")
    
    # Cost Summary Section
    if sources['cost_data']['available']:
        st.markdown("### 💰 Cost Summary")
        cost = project.get('cost_data', {})
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            materials = cost.get('materials_subtotal', 0)
            st.metric("Materials", f"${materials:,.0f}")
        with col2:
            total = cost.get('total_project_cost', 0)
            st.metric("Total Project Cost", f"${total:,.0f}")
        with col3:
            area = project.get('area', 1)
            cost_per_ha = cost.get('cost_per_ha', total/area if area > 0 else 0)
            st.metric("Cost/Hectare", f"${cost_per_ha:,.0f}")
        with col4:
            n_items = len(cost.get('boq', []))
            st.metric("BOQ Items", f"{n_items}")

def calculate_pipe_summary(project: dict) -> Dict[str, Dict]:
    """Calculate pipe summary from all design sources"""
    summary = {}
    
    # Sprinkler Line
    spr_line = project.get('sprinkler_line_design', {})
    op_data = project.get('operational_data', {})
    n_lines = op_data.get('N_sprinkler_lines', 1)
    
    if spr_line:
        length_per_line = spr_line.get('total_length_m', 0)
        total_length = length_per_line * n_lines
        sizes = set()
        for seg in spr_line.get('segments', []):
            sizes.add(seg.get('pipe_nominal_mm', 0))
        
        if total_length > 0:
            summary['Sprinkler Lines'] = {
                'total_length': total_length,
                'sizes': ', '.join(f"{s}mm" for s in sorted(sizes) if s > 0)
            }
    
    # Lateral
    lat_design = project.get('lateral_design', {})
    n_laterals = op_data.get('total_subplots', 1)
    
    if lat_design:
        length_per_lateral = lat_design.get('total_length_m', 0)
        total_length = length_per_lateral * n_laterals
        sizes = set()
        for seg in lat_design.get('segments', []):
            sizes.add(seg.get('pipe_nominal_mm', 0))
        
        if total_length > 0:
            summary['Laterals'] = {
                'total_length': total_length,
                'sizes': ', '.join(f"{s}mm" for s in sorted(sizes) if s > 0)
            }
    
    # Submains
    submain_length = 0
    submain_sizes = set()
    for key in project.keys():
        if key.startswith('submain_') and key.endswith('_design'):
            design = project[key]
            if design and 'segments' in design:
                for seg in design['segments']:
                    submain_length += seg.get('length_m', seg.get('segment_length_m', 0))
                    submain_sizes.add(seg.get('pipe_nominal_mm', 0))
    
    if submain_length > 0:
        summary['Submains'] = {
            'total_length': submain_length,
            'sizes': ', '.join(f"{s}mm" for s in sorted(submain_sizes) if s > 0)
        }
    
    # Mainlines
    mainline_length = 0
    mainline_sizes = set()
    for key in project.keys():
        if key.startswith('mainline_') and key.endswith('_design'):
            design = project[key]
            if design and 'segments' in design:
                for seg in design['segments']:
                    mainline_length += seg.get('length_m', seg.get('segment_length_m', 0))
                    mainline_sizes.add(seg.get('pipe_nominal_mm', 0))
    
    if mainline_length > 0:
        summary['Mainlines'] = {
            'total_length': mainline_length,
            'sizes': ', '.join(f"{s}mm" for s in sorted(mainline_sizes) if s > 0)
        }
    
    return summary

# ============================================================================
# DESIGN REPORT
# ============================================================================

def show_design_report():
    """Generate comprehensive design report"""
    st.markdown('<h2 class="sub-header">Comprehensive Design Report</h2>', unsafe_allow_html=True)
    
    project = get_project_data()
    
    if not project.get('project_name') and not project.get('sprinkler_data'):
        st.warning("⚠️ No project data available. Please complete the design workflow.")
        st.info("Complete at least: Project Setup, Sprinkler Selection, and Operational Design")
        return
    
    # Generate report
    report = generate_full_report(project)
    
    # Display report in formatted container
    st.markdown(report)
    
    # Download options
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.download_button(
            label="📥 Download Report (TXT)",
            data=report.replace('###', '').replace('**', '').replace('---', '-'*40),
            file_name=f"{project.get('project_name', 'irrigation')}_design_report.txt",
            mime="text/plain"
        )
    
    with col2:
        st.download_button(
            label="📥 Download Report (MD)",
            data=report,
            file_name=f"{project.get('project_name', 'irrigation')}_design_report.md",
            mime="text/markdown"
        )
    
    with col3:
        if st.button("🖨️ Print Version"):
            st.info("Use browser's Print function (Ctrl+P) to save as PDF")

# ============================================================================
# TECHNICAL SPECIFICATIONS
# ============================================================================

def show_technical_specs():
    """Show technical specifications sheet"""
    st.markdown('<h2 class="sub-header">Technical Specifications</h2>', unsafe_allow_html=True)
    
    project = get_project_data()
    
    specs = []
    
    # Header
    specs.append(f"# TECHNICAL SPECIFICATIONS")
    specs.append(f"**Project:** {project.get('project_name', 'Irrigation System')}")
    specs.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d')}")
    specs.append("")
    
    # Project Info
    specs.append("## 1. PROJECT INFORMATION")
    specs.append(f"- **Location:** {project.get('location', 'N/A')}")
    
    field_geom = project.get('field_geometry', {})
    area = field_geom.get('area_ha', project.get('area', 0))
    specs.append(f"- **Total Area:** {area:.2f} hectares")
    
    if field_geom.get('length_m') and field_geom.get('width_m'):
        specs.append(f"- **Field Dimensions:** {field_geom['length_m']:.0f}m × {field_geom['width_m']:.0f}m")
    
    specs.append("")
    
    # Crop & Climate
    irr_req = project.get('irrigation_requirements', {})
    crop_params = project.get('crop_parameters', {})
    
    # Get crop from direct crop_type first, then fallbacks
    crop = project.get('crop_type', '')
    if not crop:
        crop = crop_params.get('crop_name', irr_req.get('crop_type', ''))
    
    if crop or irr_req or crop_params:
        specs.append("## 2. CROP & IRRIGATION REQUIREMENTS")
        
        specs.append(f"- **Crop Type:** {crop if crop else 'N/A'}")
        
        if irr_req.get('peak_etc'):
            specs.append(f"- **Peak ETc:** {irr_req['peak_etc']:.2f} mm/day")
        if irr_req.get('gross_depth'):
            specs.append(f"- **Gross Irrigation Depth:** {irr_req['gross_depth']:.1f} mm")
        if irr_req.get('irrigation_interval'):
            specs.append(f"- **Irrigation Interval:** {irr_req['irrigation_interval']:.1f} days")
        if irr_req.get('application_efficiency'):
            specs.append(f"- **Application Efficiency:** {irr_req['application_efficiency']}%")
        
        specs.append("")
    
    # Sprinkler Specifications
    spr = project.get('sprinkler_data', {})
    if spr:
        specs.append("## 3. SPRINKLER SPECIFICATIONS")
        specs.append(f"- **System Type:** Solid Set Sprinkler")
        specs.append(f"- **Model:** {spr.get('model', 'N/A')}")
        specs.append(f"- **Manufacturer:** {spr.get('brand', 'N/A')}")
        specs.append(f"- **Nozzle Size:** {spr.get('nozzle', 'N/A')}")
        specs.append(f"- **Operating Pressure:** {spr.get('pressure', 0)} kPa ({spr.get('pressure', 0)/10:.1f} m)")
        specs.append(f"- **Flow Rate:** {spr.get('flow', 0)} l/h ({spr.get('flow', 0)/1000:.3f} m³/h)")
        specs.append(f"- **Wetted Diameter:** {spr.get('diameter', 0)} m")
        specs.append(f"- **Spacing Along:** {spr.get('spacing_along', 0):.2f} m")
        specs.append(f"- **Spacing Between:** {spr.get('spacing_between', 0):.2f} m")
        
        # Calculate application rate
        spacing_a = spr.get('spacing_along', 1)
        spacing_b = spr.get('spacing_between', 1)
        flow = spr.get('flow', 0)
        if spacing_a > 0 and spacing_b > 0 and flow > 0:
            app_rate = flow / (spacing_a * spacing_b)
            specs.append(f"- **Application Rate:** {app_rate:.2f} mm/h")
        
        specs.append("")
    
    # Operational Design
    op = project.get('operational_data', {})
    if op:
        specs.append("## 4. OPERATIONAL DESIGN")
        specs.append(f"- **Sprinkler Lines:** {op.get('N_sprinkler_lines', 'N/A')}")
        specs.append(f"- **Sprinklers per Line:** {op.get('N_sprinklers_line', 'N/A')}")
        specs.append(f"- **Total Sprinklers:** {op.get('total_sprinklers', 'N/A')}")
        specs.append(f"- **Total Subplots:** {op.get('total_subplots', 'N/A')}")
        specs.append(f"- **Operating Hours/Day:** {op.get('daily_operating_hours', 'N/A')} hours")
        specs.append(f"- **Irrigation Interval:** {op.get('irrigation_interval', 'N/A')} days")
        specs.append(f"- **Total Irrigation Days:** {op.get('total_irrigation_days', 'N/A')}")
        specs.append("")
    
    # Pipe Network Specifications
    pipe_summary = calculate_pipe_summary(project)
    if pipe_summary:
        specs.append("## 5. PIPE NETWORK SPECIFICATIONS")
        
        # Sprinkler Line
        spr_line = project.get('sprinkler_line_design', {})
        if spr_line:
            specs.append("### 5.1 Sprinkler Lines")
            specs.append(f"- **Material:** PVC/PE")
            specs.append(f"- **Length per Line:** {spr_line.get('total_length_m', 0):.1f} m")
            specs.append(f"- **Number of Lines:** {op.get('N_sprinkler_lines', 1)}")
            specs.append(f"- **Total Length:** {pipe_summary.get('Sprinkler Lines', {}).get('total_length', 0):.0f} m")
            specs.append(f"- **Pipe Sizes:** {pipe_summary.get('Sprinkler Lines', {}).get('sizes', 'N/A')}")
            specs.append(f"- **Total Friction Loss:** {spr_line.get('total_friction_loss_m', 0):.3f} m")
        
        # Lateral
        lat = project.get('lateral_design', {})
        if lat:
            specs.append("### 5.2 Lateral Lines")
            specs.append(f"- **Material:** PVC/PE")
            specs.append(f"- **Length per Lateral:** {lat.get('total_length_m', 0):.1f} m")
            specs.append(f"- **Number of Laterals:** {op.get('total_subplots', 1)}")
            specs.append(f"- **Total Length:** {pipe_summary.get('Laterals', {}).get('total_length', 0):.0f} m")
            specs.append(f"- **Pipe Sizes:** {pipe_summary.get('Laterals', {}).get('sizes', 'N/A')}")
            specs.append(f"- **Total Friction Loss:** {lat.get('total_friction_loss_m', 0):.3f} m")
        
        if pipe_summary.get('Submains'):
            specs.append("### 5.3 Submain Lines")
            specs.append(f"- **Material:** PVC")
            specs.append(f"- **Total Length:** {pipe_summary['Submains']['total_length']:.0f} m")
            specs.append(f"- **Pipe Sizes:** {pipe_summary['Submains']['sizes']}")
        
        if pipe_summary.get('Mainlines'):
            specs.append("### 5.4 Mainline")
            specs.append(f"- **Material:** PVC/Steel")
            specs.append(f"- **Total Length:** {pipe_summary['Mainlines']['total_length']:.0f} m")
            specs.append(f"- **Pipe Sizes:** {pipe_summary['Mainlines']['sizes']}")
        
        specs.append("")
    
    # Hydraulic Design
    hyd = project.get('hydraulic_design', {})
    if hyd:
        specs.append("## 6. HYDRAULIC DESIGN")
        # Use correct keys: total_head_required_m is the primary key
        total_head = hyd.get('total_head_required_m', hyd.get('total_head_m', hyd.get('design_head', 0)))
        specs.append(f"- **Total Dynamic Head:** {total_head:.1f} m")
        specs.append(f"- **Static Head:** {hyd.get('static_head_m', hyd.get('head_difference_m', 0)):.1f} m")
        # Calculate sprinkler pressure in m from bar
        spr_pressure_bar = hyd.get('sprinkler_pressure_bar', 0)
        spr_pressure_m = spr_pressure_bar * 10.197 if spr_pressure_bar > 0 else 0
        specs.append(f"- **Sprinkler Pressure Head:** {spr_pressure_m:.1f} m")
        # Sum friction losses from bar values
        total_friction = (hyd.get('sprinkler_line_loss_bar', 0) + hyd.get('lateral_loss_bar', 0) + 
                          hyd.get('submain_loss_bar', 0) + hyd.get('mainline_loss_bar', 0)) * 10.197
        friction_loss = hyd.get('total_pipe_loss_m', total_friction)
        specs.append(f"- **Total Friction Loss:** {friction_loss:.1f} m")
        # Minor losses
        minor = (hyd.get('fittings_loss_bar', 0) + hyd.get('backflow_loss_bar', 0) + hyd.get('water_meter_loss_bar', 0)) * 10.197
        specs.append(f"- **Minor Losses:** {minor:.1f} m")
        specs.append("")
    
    # Pump Specifications
    pump = project.get('pump_data', {})
    duty = pump.get('duty_point', {}) or {}
    if pump.get('selected_model') or pump.get('selected_pump_id'):
        specs.append("## 7. PUMP SPECIFICATIONS")
        specs.append(f"- **Brand:** {pump.get('selected_brand', pump.get('brand', 'N/A'))}")
        specs.append(f"- **Model:** {pump.get('selected_model', pump.get('model', 'N/A'))}")
        specs.append(f"- **Type:** {pump.get('pump_configuration', pump.get('description', 'Centrifugal'))}")
        rpm = pump.get('rpm', 0)
        specs.append(f"- **Speed:** {rpm if rpm else 'N/A'} RPM")
        specs.append(f"- **Impeller Diameter:** {pump.get('impeller_diameter_mm', 'N/A')} mm")
        
        specs.append("### Operating Point")
        # Get values from duty_point or fallback to required values
        flow = duty.get('flow_m3h') if duty.get('flow_m3h') else pump.get('per_pump_flow', pump.get('required_flow_m3h', 0))
        head = duty.get('head_m') if duty.get('head_m') else pump.get('selected_head', pump.get('required_head_m', 0))
        eff = duty.get('efficiency') if duty.get('efficiency') else pump.get('selected_efficiency', 0)
        power = duty.get('power_kw') if duty.get('power_kw') else pump.get('selected_power_kw', pump.get('total_power_kw', 0))
        
        specs.append(f"- **Flow Rate:** {flow:.1f} m³/h")
        specs.append(f"- **Total Head:** {head:.1f} m")
        specs.append(f"- **Efficiency:** {eff:.1f}%")
        specs.append(f"- **Power Required:** {power:.1f} kW")
        
        num_pumps = pump.get('num_pumps', 1)
        if num_pumps > 1:
            specs.append(f"- **Number of Pumps:** {num_pumps}")
            specs.append(f"- **Total System Power:** {pump.get('total_power_kw', power * num_pumps):.1f} kW")
        
        specs.append("")
    
    # Display specifications
    specs_text = "\n".join(specs)
    st.markdown(specs_text)
    
    # Download
    st.markdown("---")
    st.download_button(
        label="📥 Download Technical Specs",
        data=specs_text,
        file_name=f"{project.get('project_name', 'irrigation')}_technical_specs.md",
        mime="text/markdown"
    )

# ============================================================================
# EXPORT DATA
# ============================================================================

def show_export_data():
    """Export project data in various formats"""
    st.markdown('<h2 class="sub-header">Export Project Data</h2>', unsafe_allow_html=True)
    
    project = get_project_data()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📁 Export Formats")
        
        # JSON Export
        st.markdown("#### Complete Project (JSON)")
        json_data = json.dumps(project, indent=2, default=str)
        st.download_button(
            label="📥 Download Project JSON",
            data=json_data,
            file_name=f"{project.get('project_name', 'irrigation_project')}_complete.json",
            mime="application/json"
        )
        
        st.markdown("---")
        
        # BOQ Export
        cost_data = project.get('cost_data', {})
        boq = cost_data.get('boq', [])
        
        if boq:
            st.markdown("#### Bill of Quantities (Excel)")
            boq_df = pd.DataFrame(boq)
            
            # Create Excel file
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                boq_df.to_excel(writer, sheet_name='Bill of Quantities', index=False)
                
                # Add summary sheet
                if cost_data.get('category_totals'):
                    summary_data = []
                    for cat, total in cost_data['category_totals'].items():
                        summary_data.append({'Category': cat, 'Total ($)': total})
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Category Summary', index=False)
            
            st.download_button(
                label="📥 Download BOQ (Excel)",
                data=output.getvalue(),
                file_name=f"{project.get('project_name', 'irrigation')}_boq.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("💡 Generate BOQ in Cost Estimation module first")
        
        st.markdown("---")
        
        # Pipe Network Export
        if project.get('network_summary') or project.get('sprinkler_line_design'):
            st.markdown("#### Pipe Network Data (CSV)")
            
            pipe_data = []
            
            # Sprinkler line segments
            spr_line = project.get('sprinkler_line_design', {})
            for seg in spr_line.get('segments', []):
                pipe_data.append({
                    'Line Type': 'Sprinkler Line',
                    'Segment': seg.get('segment', ''),
                    'Position': seg.get('position', ''),
                    'Length (m)': seg.get('length_m', seg.get('segment_length_m', 0)),
                    'Pipe Size (mm)': seg.get('pipe_nominal_mm', ''),
                    'Flow (m³/h)': seg.get('flow_m3h', ''),
                    'Velocity (m/s)': seg.get('velocity_ms', ''),
                    'Friction Loss (m)': seg.get('friction_loss_m', '')
                })
            
            # Lateral segments
            lat = project.get('lateral_design', {})
            for seg in lat.get('segments', []):
                pipe_data.append({
                    'Line Type': 'Lateral',
                    'Segment': seg.get('segment', ''),
                    'Position': seg.get('position', ''),
                    'Length (m)': seg.get('length_m', seg.get('segment_length_m', 0)),
                    'Pipe Size (mm)': seg.get('pipe_nominal_mm', ''),
                    'Flow (m³/h)': seg.get('flow_m3h', ''),
                    'Velocity (m/s)': seg.get('velocity_ms', ''),
                    'Friction Loss (m)': seg.get('friction_loss_m', '')
                })
            
            if pipe_data:
                pipe_df = pd.DataFrame(pipe_data)
                csv = pipe_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download Pipe Data (CSV)",
                    data=csv,
                    file_name=f"{project.get('project_name', 'irrigation')}_pipe_network.csv",
                    mime="text/csv"
                )
    
    with col2:
        st.markdown("### 📊 Data Summary")
        
        sources = get_all_data_sources()
        
        # Count available data
        available_count = sum(1 for s in sources.values() if s.get('available'))
        total_count = len(sources)
        
        st.metric("Data Sections Available", f"{available_count}/{total_count}")
        
        st.markdown("---")
        
        st.markdown("#### Available Data Sections")
        for key, source in sources.items():
            icon = "✅" if source['available'] else "❌"
            st.write(f"{icon} {source['name']}")
        
        st.markdown("---")
        
        st.markdown("#### Quick Stats")
        
        op = project.get('operational_data', {})
        if op.get('total_sprinklers'):
            st.write(f"🎯 **Sprinklers:** {op['total_sprinklers']:,}")
        
        pipe_summary = calculate_pipe_summary(project)
        total_pipe = sum(p['total_length'] for p in pipe_summary.values())
        if total_pipe > 0:
            st.write(f"🔧 **Total Pipe:** {total_pipe:,.0f} m")
        
        cost = project.get('cost_data', {})
        if cost.get('total_project_cost'):
            st.write(f"💰 **Total Cost:** ${cost['total_project_cost']:,.0f}")

# ============================================================================
# DATA INSPECTOR
# ============================================================================

def show_data_inspector():
    """Debug view to inspect all stored project data"""
    st.markdown('<h2 class="sub-header">Data Inspector</h2>', unsafe_allow_html=True)
    
    st.info("🔍 This tool shows all data stored in your project for debugging and verification.")
    
    project = get_project_data()
    sources = get_all_data_sources()
    
    # Select data source to inspect
    source_names = {key: source['name'] for key, source in sources.items()}
    selected = st.selectbox(
        "Select data source to inspect",
        options=list(source_names.keys()),
        format_func=lambda x: f"{'✅' if sources[x]['available'] else '❌'} {source_names[x]}"
    )
    
    if selected and sources[selected]['available']:
        data = sources[selected]['data']
        
        st.markdown(f"### {sources[selected]['name']}")
        
        if isinstance(data, dict):
            # Show as formatted JSON
            st.json(data)
            
            # Also show as table if possible
            if all(not isinstance(v, (dict, list)) for v in data.values()):
                st.markdown("#### Summary Table")
                df = pd.DataFrame([data]).T
                df.columns = ['Value']
                st.dataframe(df)
        else:
            st.write(data)
    else:
        st.warning(f"No data available for {sources.get(selected, {}).get('name', selected)}")
    
    # Show all keys in project_data
    st.markdown("---")
    with st.expander("📋 All Project Data Keys"):
        keys = list(project.keys())
        st.write(f"**Total keys:** {len(keys)}")
        for key in sorted(keys):
            value = project[key]
            if isinstance(value, dict):
                st.write(f"- `{key}`: dict ({len(value)} items)")
            elif isinstance(value, list):
                st.write(f"- `{key}`: list ({len(value)} items)")
            else:
                st.write(f"- `{key}`: {type(value).__name__}")

# ============================================================================
# REPORT GENERATION
# ============================================================================

def generate_full_report(project: dict) -> str:
    """Generate comprehensive design report"""
    lines = []
    
    # Header
    lines.append("=" * 80)
    lines.append("# SPRINKLER IRRIGATION SYSTEM DESIGN REPORT")
    lines.append("=" * 80)
    lines.append("")
    lines.append(f"**Project:** {project.get('project_name', 'Irrigation System')}")
    lines.append(f"**Location:** {project.get('location', 'N/A')}")
    lines.append(f"**Report Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("---")
    
    # 1. Project Overview
    lines.append("")
    lines.append("## 1. PROJECT OVERVIEW")
    lines.append("")
    
    field_geom = project.get('field_geometry', {})
    area = field_geom.get('area_ha', project.get('area', 0))
    
    lines.append(f"- **Total Area:** {area:.2f} hectares")
    if field_geom.get('length_m') and field_geom.get('width_m'):
        lines.append(f"- **Field Dimensions:** {field_geom['length_m']:.0f}m × {field_geom['width_m']:.0f}m")
    
    crop_params = project.get('crop_parameters', {})
    irr_req = project.get('irrigation_requirements', {})
    # Get crop from direct crop_type first, then fallbacks
    crop = project.get('crop_type', '')
    if not crop:
        crop = crop_params.get('crop_name', irr_req.get('crop_type', ''))
    lines.append(f"- **Crop Type:** {crop if crop else 'N/A'}")
    lines.append(f"- **System Type:** Solid Set Sprinkler Irrigation")
    
    # 2. Irrigation Requirements
    if irr_req:
        lines.append("")
        lines.append("## 2. IRRIGATION REQUIREMENTS")
        lines.append("")
        lines.append(f"- **Peak Crop Water Demand (ETc):** {irr_req.get('peak_etc', 0):.2f} mm/day")
        lines.append(f"- **Gross Irrigation Depth:** {irr_req.get('gross_depth', 0):.1f} mm")
        lines.append(f"- **Irrigation Interval:** {irr_req.get('irrigation_interval', 0):.1f} days")
        lines.append(f"- **Application Efficiency:** {irr_req.get('application_efficiency', 80)}%")
        
        if irr_req.get('daily_volume'):
            lines.append(f"- **Daily Water Volume:** {irr_req['daily_volume']:.0f} m³/day")
    
    # 3. Sprinkler System Design
    spr = project.get('sprinkler_data', {})
    if spr:
        lines.append("")
        lines.append("## 3. SPRINKLER SYSTEM DESIGN")
        lines.append("")
        lines.append(f"### Selected Sprinkler")
        lines.append(f"- **Model:** {spr.get('model', 'N/A')}")
        lines.append(f"- **Manufacturer:** {spr.get('brand', 'N/A')}")
        lines.append(f"- **Nozzle:** {spr.get('nozzle', 'N/A')}")
        lines.append(f"- **Operating Pressure:** {spr.get('pressure', 0)} kPa")
        lines.append(f"- **Flow Rate:** {spr.get('flow', 0)} l/h")
        lines.append(f"- **Wetted Diameter:** {spr.get('diameter', 0)} m")
        lines.append("")
        lines.append(f"### Layout")
        lines.append(f"- **Spacing Along:** {spr.get('spacing_along', 0):.2f} m")
        lines.append(f"- **Spacing Between:** {spr.get('spacing_between', 0):.2f} m")
        
        # Calculate application rate
        spacing_a = spr.get('spacing_along', 1)
        spacing_b = spr.get('spacing_between', 1)
        flow = spr.get('flow', 0)
        if spacing_a > 0 and spacing_b > 0:
            app_rate = flow / (spacing_a * spacing_b)
            lines.append(f"- **Application Rate:** {app_rate:.2f} mm/h")
    
    # 4. Operational Design
    op = project.get('operational_data', {})
    if op:
        lines.append("")
        lines.append("## 4. OPERATIONAL DESIGN")
        lines.append("")
        lines.append(f"### Field Configuration")
        lines.append(f"- **Number of Sprinkler Lines:** {op.get('N_sprinkler_lines', 'N/A')}")
        lines.append(f"- **Sprinklers per Line:** {op.get('N_sprinklers_line', 'N/A')}")
        lines.append(f"- **Total Sprinklers:** {op.get('total_sprinklers', 'N/A')}")
        lines.append(f"- **Total Subplots:** {op.get('total_subplots', 'N/A')}")
        lines.append("")
        lines.append(f"### Irrigation Schedule")
        lines.append(f"- **Daily Operating Hours:** {op.get('daily_operating_hours', 'N/A')} hours")
        lines.append(f"- **Irrigation Interval:** {op.get('irrigation_interval', 'N/A')} days")
        lines.append(f"- **Total Irrigation Days:** {op.get('total_irrigation_days', 'N/A')}")
        
        if op.get('Q_lateral'):
            lines.append(f"- **Lateral Flow Rate:** {op['Q_lateral']:.2f} m³/h")
    
    # 5. Pipe Network Design
    pipe_summary = calculate_pipe_summary(project)
    if pipe_summary:
        lines.append("")
        lines.append("## 5. PIPE NETWORK DESIGN")
        lines.append("")
        
        # Sprinkler Line
        spr_line = project.get('sprinkler_line_design', {})
        if spr_line:
            lines.append(f"### 5.1 Sprinkler Lines")
            lines.append(f"- **Length per Line:** {spr_line.get('total_length_m', 0):.1f} m")
            lines.append(f"- **Number of Lines:** {op.get('N_sprinkler_lines', 1)}")
            lines.append(f"- **Total Length:** {pipe_summary.get('Sprinkler Lines', {}).get('total_length', 0):.0f} m")
            lines.append(f"- **Pipe Sizes:** {pipe_summary.get('Sprinkler Lines', {}).get('sizes', 'N/A')}")
            lines.append(f"- **Friction Loss:** {spr_line.get('total_friction_loss_m', 0):.3f} m")
            lines.append("")
        
        # Lateral
        lat = project.get('lateral_design', {})
        if lat:
            lines.append(f"### 5.2 Lateral Lines")
            lines.append(f"- **Length per Lateral:** {lat.get('total_length_m', 0):.1f} m")
            lines.append(f"- **Number of Laterals:** {op.get('total_subplots', 1)}")
            lines.append(f"- **Total Length:** {pipe_summary.get('Laterals', {}).get('total_length', 0):.0f} m")
            lines.append(f"- **Pipe Sizes:** {pipe_summary.get('Laterals', {}).get('sizes', 'N/A')}")
            lines.append(f"- **Friction Loss:** {lat.get('total_friction_loss_m', 0):.3f} m")
            lines.append("")
        
        if pipe_summary.get('Submains'):
            lines.append(f"### 5.3 Submain Lines")
            lines.append(f"- **Total Length:** {pipe_summary['Submains']['total_length']:.0f} m")
            lines.append(f"- **Pipe Sizes:** {pipe_summary['Submains']['sizes']}")
            lines.append("")
        
        if pipe_summary.get('Mainlines'):
            lines.append(f"### 5.4 Mainline")
            lines.append(f"- **Total Length:** {pipe_summary['Mainlines']['total_length']:.0f} m")
            lines.append(f"- **Pipe Sizes:** {pipe_summary['Mainlines']['sizes']}")
            lines.append("")
    
    # 6. Hydraulic Design
    hyd = project.get('hydraulic_design', {})
    if hyd:
        lines.append("")
        lines.append("## 6. HYDRAULIC DESIGN")
        lines.append("")
        lines.append(f"### System Head Requirements")
        # Use correct key: total_head_required_m
        total_head = hyd.get('total_head_required_m', hyd.get('total_head_m', hyd.get('design_head', 0)))
        lines.append(f"- **Total Dynamic Head:** {total_head:.1f} m")
        lines.append(f"- **Static Head:** {hyd.get('static_head_m', hyd.get('head_difference_m', 0)):.1f} m")
        # Sprinkler pressure in m (convert from bar if needed)
        spr_pressure_bar = hyd.get('sprinkler_pressure_bar', 0)
        spr_pressure_m = spr_pressure_bar * 10.197 if spr_pressure_bar > 0 else 0
        lines.append(f"- **Sprinkler Pressure Head:** {spr_pressure_m:.1f} m")
        # Sum friction losses
        total_friction = (hyd.get('sprinkler_line_loss_bar', 0) + hyd.get('lateral_loss_bar', 0) + 
                          hyd.get('submain_loss_bar', 0) + hyd.get('mainline_loss_bar', 0)) * 10.197
        friction_loss = hyd.get('total_pipe_loss_m', total_friction)
        lines.append(f"- **Total Friction Loss:** {friction_loss:.1f} m")
        # Minor losses
        minor = (hyd.get('fittings_loss_bar', 0) + hyd.get('backflow_loss_bar', 0) + hyd.get('water_meter_loss_bar', 0)) * 10.197
        lines.append(f"- **Minor Losses:** {minor:.1f} m")
    
    # 7. Pump Selection
    pump = project.get('pump_data', {})
    duty = pump.get('duty_point', {}) or {}
    if pump.get('selected_model') or pump.get('selected_pump_id'):
        lines.append("")
        lines.append("## 7. PUMP SELECTION")
        lines.append("")
        lines.append(f"### Selected Pump")
        lines.append(f"- **Brand:** {pump.get('selected_brand', pump.get('brand', 'N/A'))}")
        lines.append(f"- **Model:** {pump.get('selected_model', pump.get('model', 'N/A'))}")
        lines.append(f"- **Type:** {pump.get('pump_configuration', pump.get('description', 'Centrifugal'))}")
        lines.append("")
        lines.append(f"### Operating Characteristics")
        # Get values from duty_point or fallback to required/selected values
        flow = duty.get('flow_m3h') if duty.get('flow_m3h') else pump.get('per_pump_flow', pump.get('required_flow_m3h', 0))
        head = duty.get('head_m') if duty.get('head_m') else pump.get('selected_head', pump.get('required_head_m', 0))
        eff = duty.get('efficiency') if duty.get('efficiency') else pump.get('selected_efficiency', 0)
        power = duty.get('power_kw') if duty.get('power_kw') else pump.get('selected_power_kw', pump.get('total_power_kw', 0))
        rpm = pump.get('rpm', 0)
        
        lines.append(f"- **Flow Rate at Duty Point:** {flow:.1f} m³/h")
        lines.append(f"- **Head at Duty Point:** {head:.1f} m")
        lines.append(f"- **Efficiency:** {eff:.1f}%")
        lines.append(f"- **Power Required:** {power:.1f} kW")
        lines.append(f"- **Speed:** {rpm if rpm else 'N/A'} RPM")
        
        num_pumps = pump.get('num_pumps', 1)
        if num_pumps > 1:
            lines.append(f"- **Number of Pumps:** {num_pumps}")
            lines.append(f"- **Total System Power:** {pump.get('total_power_kw', power * num_pumps):.1f} kW")
    
    # 8. Cost Estimate
    cost = project.get('cost_data', {})
    if cost.get('materials_subtotal') or cost.get('total_project_cost'):
        lines.append("")
        lines.append("## 8. PROJECT COST ESTIMATE")
        lines.append("")
        lines.append(f"### Cost Summary")
        lines.append(f"- **Materials Cost:** ${cost.get('materials_subtotal', 0):,.2f}")
        
        if cost.get('installation_cost'):
            lines.append(f"- **Installation Cost:** ${cost['installation_cost']:,.2f}")
        if cost.get('engineering_cost'):
            lines.append(f"- **Engineering & Design:** ${cost['engineering_cost']:,.2f}")
        if cost.get('contingency_cost'):
            lines.append(f"- **Contingency:** ${cost['contingency_cost']:,.2f}")
        
        if cost.get('total_project_cost'):
            lines.append(f"- **TOTAL PROJECT COST:** ${cost['total_project_cost']:,.2f}")
        
        if area > 0:
            cost_per_ha = cost.get('cost_per_ha', cost.get('total_project_cost', 0) / area)
            lines.append(f"- **Cost per Hectare:** ${cost_per_ha:,.2f}/ha")
        
        # Economic analysis
        if cost.get('payback_period'):
            lines.append("")
            lines.append(f"### Economic Analysis")
            lines.append(f"- **Payback Period:** {cost['payback_period']:.1f} years")
        if cost.get('roi'):
            lines.append(f"- **Return on Investment:** {cost['roi']:.1f}%")
        if cost.get('npv'):
            lines.append(f"- **Net Present Value:** ${cost['npv']:,.0f}")
    
    # Footer
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("*Report generated by Sprinkler Irrigation Design Application*")
    lines.append(f"*South Africa Irrigation Design Manual 2025*")
    
    return "\n".join(lines)
