import streamlit as st
import plotly.graph_objects as go
import numpy as np
from typing import Dict, List, Tuple
from shapely.geometry import Polygon, LineString, box
from shapely.ops import split

# Import DevLogger for toggleable debug output
from components.logger import DevLogger, log_debug, log_info, log_warning

def show():
    """Operational design and field subdivision - Professional compact layout"""
    st.markdown('<h1 class="main-header">📐 Operational Design</h1>', unsafe_allow_html=True)
    
    # Check prerequisites
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete sprinkler selection first.")
        return
    
    # Show Solid Set operational design (only system type supported)
    show_solid_set_operational_design()

def show_solid_set_operational_design():
    """Operational design for solid set system - Streamlined professional layout"""
    
    sprinkler = st.session_state.project_data['sprinkler_data']
    
    # Get actual values from sprinkler selection
    Q_sprinkler_lhr = sprinkler.get('flow')  # l/hr from database
    spacing_along = sprinkler.get('spacing_along')
    spacing_between = sprinkler.get('spacing_between')
    pressure = sprinkler.get('pressure')
    
    # Validate that required data exists
    if not all([Q_sprinkler_lhr, spacing_along, spacing_between]):
        st.error("⚠️ Missing sprinkler parameters. Please complete spacing design in Sprinkler Selection page.")
        return
    
    # Convert flow from l/hr to m³/hr
    Q_sprinkler = Q_sprinkler_lhr / 1000  # m³/hr
    
    # Calculate application rate from actual sprinkler data
    application_rate = (Q_sprinkler * 1000 / (spacing_along * spacing_between))  # mm/hr
    
    # =========================================================================
    # SECTION 1: System Parameters Card (Compact)
    # =========================================================================
    with st.expander("💧 System Parameters", expanded=True):
        cols = st.columns(5)
        cols[0].metric("Flow Rate", f"{Q_sprinkler_lhr:.0f} l/hr")
        cols[1].metric("Spacing Along", f"{spacing_along:.1f} m")
        cols[2].metric("Spacing Between", f"{spacing_between:.1f} m")
        cols[3].metric("Application Rate", f"{application_rate:.2f} mm/hr")
        cols[4].metric("Pressure", f"{pressure:.0f} kPa")
    
    # =========================================================================
    # SECTION 2: Field Dimensions (Compact)
    # =========================================================================
    saved_operational = st.session_state.project_data.get('operational_data', {})
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    
    with st.expander("📐 Field Dimensions", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_area = st.number_input(
                "Total Area (ha)", min_value=0.1, max_value=10000.0,
                value=float(field_geometry.get('area_ha', st.session_state.project_data.get('area', 128.52)) or 128.52),
                step=0.1, help="From field mapping or manual entry"
            )
        
        with col2:
            field_length = st.number_input(
                "Field Length (m)", min_value=50.0, max_value=10000.0,
                value=float(field_geometry.get('length_m', 850.0)),
                step=10.0
            )
        
        with col3:
            field_width = st.number_input(
                "Field Width (m)", min_value=50.0, max_value=10000.0,
                value=float(field_geometry.get('width_m', 750.0)),
                step=10.0
            )
        
        with col4:
            num_main_fields = st.number_input(
                "Main Fields", min_value=1, max_value=10,
                value=int(saved_operational.get('num_main_fields', 2)), step=1
            )
        
        if field_geometry.get('boundary'):
            st.caption("📍 Dimensions loaded from interactive map")
    
    # Calculate sprinkler layout for the field
    N_sprinklers_line = int(field_length / spacing_along)
    N_sprinkler_lines = int(field_width / spacing_between)
    Q_sprinkler_line = N_sprinklers_line * Q_sprinkler
    Q_lateral = Q_sprinkler_line * N_sprinkler_lines
    
    # =========================================================================
    # SECTION 3: Water Source & Constraints (Compact)
    # =========================================================================
    with st.expander("🚰 Water Source & Operating Hours", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            available_discharge = st.number_input(
                "Available Discharge (m³/hr)", min_value=10.0, max_value=10000.0,
                value=float(saved_operational.get('available_discharge', 400.0)), step=10.0
            )
        
        with col2:
            daily_operating_hours = st.number_input(
                "Operating Hours/Day", min_value=1.0, max_value=24.0,
                value=float(saved_operational.get('daily_operating_hours', 16.0)), step=1.0
            )
        
        with col3:
            irrigation_data = st.session_state.project_data.get('irrigation_requirements', {})
            default_interval = irrigation_data.get('irrigation_interval', 4)
            irrigation_interval = st.number_input(
                "Irrigation Interval (days)", min_value=1.0, max_value=14.0,
                value=float(saved_operational.get('irrigation_interval', float(default_interval))), step=0.5
            )
        
        with col4:
            gross_depth = irrigation_data.get('gross_depth', 0)
            if gross_depth > 0:
                st.metric("Gross Depth (GIR)", f"{gross_depth:.1f} mm")
            else:
                gross_depth = st.number_input("Gross Depth (mm)", min_value=10.0, value=50.0, step=5.0)
    
    # Auto-save input values
    if 'operational_data' not in st.session_state.project_data:
        st.session_state.project_data['operational_data'] = {}
    
    st.session_state.project_data['operational_data'].update({
        'available_discharge': available_discharge,
        'daily_operating_hours': daily_operating_hours,
        'irrigation_interval': irrigation_interval,
        'num_main_fields': num_main_fields,
        'N_sprinklers_line': N_sprinklers_line,
        'N_sprinkler_lines': N_sprinkler_lines,
        'total_sprinklers': N_sprinklers_line * N_sprinkler_lines,
        'Q_lateral': Q_lateral
    })
    
    # Check if operational data already exists
    has_subdivision_data = st.session_state.project_data.get('operational_data', {}).get('total_subplots') is not None
    has_irrigation_data = st.session_state.project_data.get('operational_data', {}).get('total_irrigation_days') is not None
    
    if has_subdivision_data and 'show_subdivision' not in st.session_state:
        st.session_state['show_subdivision'] = True
    if has_irrigation_data and 'show_irrigation_calcs' not in st.session_state:
        st.session_state['show_irrigation_calcs'] = True
    
    # =========================================================================
    # CALCULATE BUTTON
    # =========================================================================
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🔄 Calculate Field Subdivision & Irrigation", type="primary", width="stretch"):
            st.session_state['show_subdivision'] = True
            st.session_state['show_irrigation_calcs'] = True
    
    # Show results if calculated
    if st.session_state.get('show_subdivision', False):
        show_field_subdivision(sprinkler, total_area, field_length, field_width)
        
        if st.session_state.get('show_irrigation_calcs', False):
            calculate_irrigation_management(
                sprinkler, available_discharge, daily_operating_hours,
                gross_depth, irrigation_interval,
                total_area, field_length, field_width, num_main_fields
            )

def show_field_subdivision(sprinkler, total_area, field_length, field_width):
    """Show field subdivision based on 1 ha standard subplots - Compact professional layout"""
    
    # Automatic Subplot Division (1 ha = 125m × 85m)
    if total_area <= 1.0:
        subplot_length = field_length
        subplot_width = field_width
        subplot_area_ha = total_area
        total_subplots = 1
        n_length = 1
        n_width = 1
    else:
        # Standard subplot dimensions for 1 ha
        standard_subplot_length = 125
        standard_subplot_width = 85
        
        divisions_by_125 = field_length / standard_subplot_length
        divisions_by_85 = field_length / standard_subplot_width
        divisions_width_by_125 = field_width / standard_subplot_length
        divisions_width_by_85 = field_width / standard_subplot_width
        
        def is_acceptable_division(value):
            decimal_part = value - int(value)
            return decimal_part < 0.15 or decimal_part > 0.85
        
        option1_valid = is_acceptable_division(divisions_by_125) and is_acceptable_division(divisions_width_by_85)
        option2_valid = is_acceptable_division(divisions_by_85) and is_acceptable_division(divisions_width_by_125)
        
        if option1_valid:
            n_length = round(divisions_by_125)
            n_width = round(divisions_width_by_85)
            subplot_length = standard_subplot_length
            subplot_width = standard_subplot_width
        elif option2_valid:
            n_length = round(divisions_by_85)
            n_width = round(divisions_width_by_125)
            subplot_length = standard_subplot_width
            subplot_width = standard_subplot_length
        else:
            n_length = round(divisions_by_125)
            n_width = round(divisions_width_by_85)
            subplot_length = standard_subplot_length
            subplot_width = standard_subplot_width
        
        total_subplots = n_length * n_width
        subplot_area_ha = 1.0
    
    n_rows = n_length
    n_cols = n_width
    
    # Show subdivision summary in expander
    with st.expander("📋 Field Subdivision Results", expanded=True):
        cols = st.columns(4)
        cols[0].metric("Total Subplots", total_subplots)
        cols[1].metric("Grid Layout", f"{n_rows} × {n_cols}")
        cols[2].metric("Subplot Size", f"{subplot_length}m × {subplot_width}m")
        cols[3].metric("Subplot Area", f"~{subplot_area_ha:.1f} ha")
    
    # Calculate effective subplot count for irregular fields
    effective_subplots = total_subplots
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    local_polygon = field_geometry.get('local_polygon', None)
    
    if local_polygon and total_subplots > 1:
        from shapely.geometry import Polygon, box as shapely_box
        poly = Polygon(local_polygon)
        
        subplot_width_calc = field_width / n_cols
        subplot_length_calc = field_length / n_rows
        standard_subplot_area = subplot_width_calc * subplot_length_calc
        
        effective_subplots = 0
        subplot_areas = []
        
        for row in range(n_rows):
            for col in range(n_cols):
                x0 = col * subplot_width_calc
                x1 = (col + 1) * subplot_width_calc
                y0 = row * subplot_length_calc
                y1 = (row + 1) * subplot_length_calc
                
                subplot_rect = shapely_box(x0, y0, x1, y1)
                clipped = subplot_rect.intersection(poly)
                
                if not clipped.is_empty and clipped.area > (standard_subplot_area * 0.01):
                    fraction = clipped.area / standard_subplot_area
                    effective_subplots += fraction
                    subplot_areas.append({'row': row, 'col': col, 'area_fraction': fraction, 'area_m2': clipped.area})
        
        st.session_state.project_data['operational_data'].update({
            'subplot_areas': subplot_areas,
            'effective_subplots': effective_subplots
        })
        
        if abs(effective_subplots - total_subplots) > 0.5:
            st.caption(f"📐 Effective subplots: {effective_subplots:.1f} (adjusted for irregular field shape)")
    
    # Auto-save subdivision data
    if 'operational_data' not in st.session_state.project_data:
        st.session_state.project_data['operational_data'] = {}
    
    st.session_state.project_data['operational_data'].update({
        'total_subplots': total_subplots,
        'effective_subplots': effective_subplots if local_polygon else total_subplots,
        'n_rows': n_rows,
        'n_cols': n_cols
    })
    
    # Show subdivision diagram in expander
    with st.expander("🗺️ Subdivision Layout Diagram", expanded=False):
        create_subdivision_diagram(total_subplots, n_rows, n_cols, field_length, field_width, sprinkler)


def calculate_irrigation_management(sprinkler, available_discharge, daily_operating_hours,
                                    gross_depth, irrigation_interval,
                                    total_area, field_length, field_width, num_main_fields):
    """Calculate irrigation management parameters - Streamlined professional layout"""
    
    Q_sprinkler_lhr = sprinkler.get('flow')
    spacing_along = sprinkler.get('spacing_along')
    spacing_between = sprinkler.get('spacing_between')
    
    if not all([Q_sprinkler_lhr, spacing_along, spacing_between]):
        st.error("⚠️ Missing sprinkler data. Cannot perform calculations.")
        return
    
    Q_sprinkler = Q_sprinkler_lhr / 1000  # m³/hr
    
    operational_data = st.session_state.project_data.get('operational_data', {})
    total_subplots = operational_data.get('total_subplots', 1)
    n_rows = operational_data.get('n_rows', 1)
    n_cols = operational_data.get('n_cols', 1)
    
    subplot_length = field_length / n_rows
    subplot_width = field_width / n_cols
    
    # Core calculations
    Rs = (Q_sprinkler / (spacing_along * spacing_between)) * 1000  # mm/hr
    Ti = gross_depth / Rs  # hours
    
    if Ti <= 0:
        st.error("⚠️ Invalid irrigation time. Check sprinkler flow rate and spacing.")
        return
    
    N_cycles = int(daily_operating_hours / Ti)
    
    if N_cycles == 0:
        st.error(f"⚠️ Irrigation time ({Ti:.1f} hrs) exceeds daily operating hours ({daily_operating_hours} hrs)")
        return
    
    N_sprinklers_line = int(field_length / spacing_along)
    N_sprinkler_lines = int(field_width / spacing_between)
    Q_sprinkler_line = N_sprinklers_line * Q_sprinkler
    Q_lateral = Q_sprinkler_line * N_sprinkler_lines
    
    N_sprinklers_subplot = int(subplot_length / spacing_along)
    N_lines_subplot = int(subplot_width / spacing_between)
    Q_subplot = N_sprinklers_subplot * N_lines_subplot * Q_sprinkler
    
    if Q_subplot <= 0:
        st.error("⚠️ Invalid subplot discharge.")
        return
    
    N_subplots_per_cycle = int(available_discharge / Q_subplot)
    
    if N_subplots_per_cycle == 0:
        st.error(f"⚠️ Insufficient discharge: Need {Q_subplot:.1f} m³/hr, have {available_discharge:.1f} m³/hr")
        return
    
    N_subplots_per_day = N_cycles * N_subplots_per_cycle
    
    if N_subplots_per_day == 0:
        st.error("⚠️ System cannot irrigate any subplots per day")
        return
    
    effective_subplots = operational_data.get('effective_subplots', total_subplots)
    total_irrigation_days = np.ceil(effective_subplots / N_subplots_per_day)
    
    subplots_per_plot = 8
    total_plots = int(np.ceil(total_subplots / subplots_per_plot))
    
    # =========================================================================
    # RESULTS DISPLAY - Compact Professional Layout
    # =========================================================================
    st.markdown("---")
    
    # Key Results Summary (Always visible)
    with st.expander("📊 Irrigation Results Summary", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Application Rate", f"{Rs:.2f} mm/hr")
        col2.metric("Irrigation Time", f"{Ti:.2f} hrs/event")
        col3.metric("Cycles/Day", N_cycles)
        col4.metric("Subplots/Day", N_subplots_per_day)
        
        col5, col6, col7, col8 = st.columns(4)
        col5.metric("Subplot Discharge", f"{Q_subplot:.1f} m³/hr")
        col6.metric("Subplots/Cycle", N_subplots_per_cycle)
        col7.metric("Total Days", f"{total_irrigation_days:.0f}")
        col8.metric("Total Sprinklers", f"{N_sprinklers_line * N_sprinkler_lines:,}")
        
        # Validation
        if total_irrigation_days > irrigation_interval:
            st.error(f"⚠️ Cycle time ({total_irrigation_days:.0f} days) exceeds irrigation interval ({irrigation_interval} days)")
        else:
            st.success(f"✅ System feasible: {total_irrigation_days:.0f} days fits within {irrigation_interval}-day interval")
    
    # Detailed Calculations (Collapsible)
    with st.expander("📐 Detailed Calculations", expanded=False):
        st.latex(r"R_s = \frac{Q_{sprinkler}}{D_{along} \times D_{between}} = \frac{" + 
                 f"{Q_sprinkler:.3f}" + r"}{" + f"{spacing_along:.1f}" + r" \times " + f"{spacing_between:.1f}" + 
                 r"} = " + f"{Rs:.2f}" + r" \text{{ mm/hr}}")
        
        st.latex(r"T_i = \frac{GIR}{R_s} = \frac{" + f"{gross_depth:.1f}" + r"}{" + f"{Rs:.2f}" + 
                 r"} = " + f"{Ti:.2f}" + r" \text{{ hours}}")
        
        st.latex(r"N_{cycles/day} = \frac{" + f"{daily_operating_hours:.0f}" + r"}{" + f"{Ti:.2f}" + 
                 r"} = " + f"{N_cycles}")
        
        st.latex(r"Q_{subplot} = " + f"{N_sprinklers_subplot}" + r" \times " + f"{N_lines_subplot}" + 
                 r" \times " + f"{Q_sprinkler:.3f}" + r" = " + f"{Q_subplot:.2f}" + r" \text{{ m³/hr}}")
        
        st.latex(r"N_{subplots/cycle} = \frac{" + f"{available_discharge:.0f}" + r"}{" + f"{Q_subplot:.1f}" + 
                 r"} = " + f"{N_subplots_per_cycle}")
        
        st.latex(r"N_{subplots/day} = " + f"{N_cycles}" + r" \times " + f"{N_subplots_per_cycle}" + 
                 r" = " + f"{N_subplots_per_day}")
        
        st.latex(r"Total\_days = \frac{" + f"{effective_subplots:.1f}" + r"}{" + f"{N_subplots_per_day}" + 
                 r"} = " + f"{total_irrigation_days:.0f}")
    
    # Sprinkler Layout Diagrams (Collapsible)
    with st.expander("🌱 Subplot Sprinkler Layout", expanded=False):
        create_subplot_layout_diagram(N_sprinklers_subplot, N_lines_subplot, 
                                      subplot_length, subplot_width,
                                      spacing_along, spacing_between)
    
    with st.expander("🗺️ Field Layout with Sprinkler Detail", expanded=False):
        create_field_with_subplot_detail(total_subplots, n_rows, n_cols, 
                                         field_length, field_width,
                                         N_sprinklers_subplot, N_lines_subplot,
                                         spacing_along, spacing_between)
    
    # Irrigation Schedule Diagram
    with st.expander("📅 Irrigation Schedule Layout", expanded=True):
        st.caption(f"Each color represents subplots irrigated on the same day ({N_subplots_per_day} subplots/day)")
        create_irrigation_schedule_diagram(
            total_subplots, n_rows, n_cols, field_length, field_width,
            N_subplots_per_day, int(total_irrigation_days)
        )
    
    # Manual Day Assignment (Collapsible)
    with st.expander("🔧 Manual Day Assignment Override", expanded=False):
        show_manual_day_assignment_ui(int(total_irrigation_days), N_subplots_per_day)
    
    # Save Button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("💾 Save Operational Design", type="primary", width="stretch", key="save_op_design"):
            st.session_state.project_data['operational_data'].update({
                'available_discharge': available_discharge,
                'daily_operating_hours': daily_operating_hours,
                'gross_irrigation_depth': gross_depth,
                'irrigation_interval': irrigation_interval,
                'application_rate': Rs,
                'irrigation_time': Ti,
                'cycles_per_day': N_cycles,
                'subplot_discharge': Q_subplot,
                'subplots_per_cycle': N_subplots_per_cycle,
                'subplots_per_day': N_subplots_per_day,
                'total_subplots': total_subplots,
                'total_irrigation_days': total_irrigation_days,
                'num_main_fields': num_main_fields,
                'subplots_per_plot': subplots_per_plot,
                'n_rows': n_rows,
                'n_cols': n_cols,
                'n_sprinklers_per_line': N_sprinklers_subplot,
                'n_lines_per_subplot': N_lines_subplot,
                'spacing_along': spacing_along,
                'spacing_between': spacing_between,
                'field_organization': {
                    'main_fields': num_main_fields,
                    'plots': total_plots,
                    'subplots': total_subplots
                }
            })
            st.success("✅ Operational design saved successfully!")


def show_manual_day_assignment_ui(total_days: int, subplots_per_day: float):
    """Compact UI for manually overriding subplot day assignments."""
    
    operational_data = st.session_state.project_data.get('operational_data', {})
    subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
    actual_total_days = operational_data.get('actual_total_days', total_days)
    
    if not subplot_day_assignments:
        st.caption("No subplot assignments available yet. Calculate irrigation first.")
        return
    
    if 'manual_day_overrides' not in st.session_state:
        st.session_state.manual_day_overrides = {}
    
    current_assignments = dict(subplot_day_assignments)
    current_assignments.update(st.session_state.manual_day_overrides)
    
    day_colors = {
        1: '#FF6B6B', 2: '#4ECDC4', 3: '#45B7D1', 4: '#FFA07A', 5: '#98D8C8',
        6: '#F7DC6F', 7: '#BB8FCE', 8: '#85C1E2', 9: '#F8B88B', 10: '#A9DFBF'
    }
    
    st.caption("Click tabs to reassign subplots to different irrigation days")
    
    day_tabs = st.tabs([f"Day {d}" for d in range(1, actual_total_days + 1)])
    
    subplots_by_day = {d: [] for d in range(1, actual_total_days + 1)}
    for subplot_num, day in current_assignments.items():
        if 1 <= day <= actual_total_days:
            subplots_by_day[day].append(subplot_num)
    
    for day in subplots_by_day:
        subplots_by_day[day].sort()
    
    changes_made = False
    new_assignments = dict(current_assignments)
    
    for day_idx, day_tab in enumerate(day_tabs):
        day_num = day_idx + 1
        with day_tab:
            color = day_colors.get(day_num, '#CCCCCC')
            st.markdown(f'<div style="background:{color};padding:5px;border-radius:3px;text-align:center;font-weight:bold;">Day {day_num}: {len(subplots_by_day[day_num])} subplots</div>', unsafe_allow_html=True)
            
            cols = st.columns(5)
            all_subplots = sorted(current_assignments.keys())
            
            for idx, subplot_num in enumerate(all_subplots):
                col = cols[idx % 5]
                current_day = current_assignments.get(subplot_num, 1)
                is_on_this_day = current_day == day_num
                
                with col:
                    new_value = st.checkbox(
                        f"SP {subplot_num}", value=is_on_this_day,
                        key=f"day_{day_num}_subplot_{subplot_num}"
                    )
                    if new_value and not is_on_this_day:
                        new_assignments[subplot_num] = day_num
                        changes_made = True
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Apply Changes", type="primary", key="apply_day_changes", width="stretch"):
            if changes_made or st.session_state.manual_day_overrides:
                st.session_state.manual_day_overrides = {
                    k: v for k, v in new_assignments.items() 
                    if v != subplot_day_assignments.get(k)
                }
                st.session_state.project_data['operational_data']['subplot_day_assignments'] = new_assignments
                st.session_state.project_data['operational_data']['manual_overrides_applied'] = True
                st.rerun()
    
    with col2:
        if st.button("↩️ Reset", key="reset_day_assignments", width="stretch"):
            st.session_state.manual_day_overrides = {}
            if 'manual_overrides_applied' in st.session_state.project_data.get('operational_data', {}):
                del st.session_state.project_data['operational_data']['manual_overrides_applied']
            st.rerun()


def create_subplot_layout_diagram(n_sprinklers_per_line, n_lines, 
                                  subplot_length, subplot_width,
                                  spacing_along, spacing_between):
    """Create visual diagram showing sprinkler layout within a single subplot"""
    
    from shapely.geometry import Polygon, MultiPoint
    import numpy as np
    
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    local_polygon = field_geometry.get('local_polygon', None)
    is_regular_quad = False
    rotation_angle = 0
    
    if local_polygon:
        poly = Polygon(local_polygon)
        corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
        is_regular_quad = len(corners) == 4
        
        if is_regular_quad:
            # Calculate field orientation angle
            # Sort corners to find bottom edge
            corners_sorted = sorted(corners, key=lambda p: (p[1], p[0]))
            bottom_left = min(corners_sorted[:2], key=lambda p: p[0])
            bottom_right = max(corners_sorted[:2], key=lambda p: p[0])
            
            # Calculate angle of bottom edge (field orientation)
            dx = bottom_right[0] - bottom_left[0]
            dy = bottom_right[1] - bottom_left[1]
            rotation_angle = np.degrees(np.arctan2(dy, dx))
    
    fig = go.Figure()
    
    # Draw subplot boundary (85m wide × 125m long)
    if is_regular_quad and abs(rotation_angle) > 1:  # If field has significant rotation
        # Create rotated rectangle
        angle_rad = np.radians(rotation_angle)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        # Define corners of rotated rectangle (centered at origin first)
        corners = [
            (0, 0),
            (subplot_width * cos_a, subplot_width * sin_a),
            (subplot_width * cos_a - subplot_length * sin_a, subplot_width * sin_a + subplot_length * cos_a),
            (-subplot_length * sin_a, subplot_length * cos_a),
            (0, 0)
        ]
        
        fig.add_trace(go.Scatter(
            x=[c[0] for c in corners],
            y=[c[1] for c in corners],
            mode='lines',
            line=dict(color='black', width=3),
            name='Sub-plot Boundary',
            showlegend=True
        ))
    else:
        # Standard rectangular boundary
        fig.add_trace(go.Scatter(
            x=[0, subplot_width, subplot_width, 0, 0],
            y=[0, 0, subplot_length, subplot_length, 0],
            mode='lines',
            line=dict(color='black', width=3),
            name='Sub-plot Boundary',
            showlegend=True
        ))
    
    # Draw sprinkler lines with correct orientation
    if is_regular_quad and abs(rotation_angle) > 1:
        # Rotated sprinkler lines parallel to field edges
        angle_rad = np.radians(rotation_angle)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        for line_idx in range(n_lines):
            # Distance along width for this line
            dist_along_width = (line_idx + 0.5) * spacing_between
            
            # Start point (along bottom edge)
            start_x = dist_along_width * cos_a
            start_y = dist_along_width * sin_a
            
            # End point (along top edge) - move perpendicular to width edge
            end_x = start_x - subplot_length * sin_a
            end_y = start_y + subplot_length * cos_a
            
            # Draw sprinkler line
            fig.add_trace(go.Scatter(
                x=[start_x, end_x],
                y=[start_y, end_y],
                mode='lines',
                line=dict(color='blue', width=2, dash='solid'),
                name='Sprinkler Line' if line_idx == 0 else None,
                showlegend=(line_idx == 0),
                legendgroup='sprinkler_lines'
            ))
            
            # Draw sprinklers along this rotated line
            for sprinkler_idx in range(n_sprinklers_per_line):
                dist_along_line = (sprinkler_idx + 0.5) * spacing_along
                
                # Position along the rotated line
                spr_x = start_x - dist_along_line * sin_a
                spr_y = start_y + dist_along_line * cos_a
                
                fig.add_trace(go.Scatter(
                    x=[spr_x],
                    y=[spr_y],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='green',
                        symbol='circle',
                        line=dict(color='darkgreen', width=1)
                    ),
                    name='Sprinkler' if line_idx == 0 and sprinkler_idx == 0 else None,
                    showlegend=(line_idx == 0 and sprinkler_idx == 0),
                    legendgroup='sprinklers',
                    hovertemplate=f'<b>Sprinkler</b><br>Line {line_idx + 1}<br>Position {sprinkler_idx + 1}<extra></extra>'
                ))
                
                # Draw coverage circles
                if line_idx < 2 and sprinkler_idx < 3:
                    coverage_radius = min(spacing_along, spacing_between) / 2
                    theta = np.linspace(0, 2*np.pi, 30)
                    circle_x = spr_x + coverage_radius * np.cos(theta)
                    circle_y = spr_y + coverage_radius * np.sin(theta)
                    
                    fig.add_trace(go.Scatter(
                        x=circle_x,
                        y=circle_y,
                        mode='lines',
                        line=dict(color='lightgreen', width=1, dash='dot'),
                        fill='toself',
                        fillcolor='rgba(144, 238, 144, 0.1)',
                        name='Coverage Area' if line_idx == 0 and sprinkler_idx == 0 else None,
                        showlegend=(line_idx == 0 and sprinkler_idx == 0),
                        legendgroup='coverage',
                        hoverinfo='skip'
                    ))
    else:
        # Standard vertical sprinkler lines (no rotation)
        for line_idx in range(n_lines):
            line_x = (line_idx + 0.5) * spacing_between
            
            fig.add_trace(go.Scatter(
                x=[line_x, line_x],
                y=[0, subplot_length],
                mode='lines',
                line=dict(color='blue', width=2, dash='solid'),
                name='Sprinkler Line' if line_idx == 0 else None,
                showlegend=(line_idx == 0),
                legendgroup='sprinkler_lines'
            ))
            
            for sprinkler_idx in range(n_sprinklers_per_line):
                sprinkler_y = (sprinkler_idx + 0.5) * spacing_along
                
                fig.add_trace(go.Scatter(
                    x=[line_x],
                    y=[sprinkler_y],
                    mode='markers',
                    marker=dict(
                        size=8,
                        color='green',
                        symbol='circle',
                        line=dict(color='darkgreen', width=1)
                    ),
                    name='Sprinkler' if line_idx == 0 and sprinkler_idx == 0 else None,
                    showlegend=(line_idx == 0 and sprinkler_idx == 0),
                    legendgroup='sprinklers',
                    hovertemplate=f'<b>Sprinkler</b><br>Line {line_idx + 1}<br>Position {sprinkler_idx + 1}<extra></extra>'
                ))
                
                if line_idx < 2 and sprinkler_idx < 3:
                    coverage_radius = min(spacing_along, spacing_between) / 2
                    theta = np.linspace(0, 2*np.pi, 30)
                    circle_x = line_x + coverage_radius * np.cos(theta)
                    circle_y = sprinkler_y + coverage_radius * np.sin(theta)
                    
                    fig.add_trace(go.Scatter(
                        x=circle_x,
                        y=circle_y,
                        mode='lines',
                        line=dict(color='lightgreen', width=1, dash='dot'),
                        fill='toself',
                        fillcolor='rgba(144, 238, 144, 0.1)',
                        name='Coverage Area' if line_idx == 0 and sprinkler_idx == 0 else None,
                        showlegend=(line_idx == 0 and sprinkler_idx == 0),
                        legendgroup='coverage',
                        hoverinfo='skip'
                    ))
    
    # Add dimension annotations
    # Width dimension (top) - should show 85m
    fig.add_annotation(
        x=subplot_width/2, y=subplot_length + 5,
        text=f"{int(subplot_width)} m",
        showarrow=False,
        font=dict(size=14, color='black', family='Arial Black'),
        bgcolor='white',
        bordercolor='black',
        borderwidth=1
    )
    
    # Length dimension (right side) - should show 125m
    fig.add_annotation(
        x=subplot_width + 10, y=subplot_length/2,
        text=f"{int(subplot_length)} m",
        showarrow=False,
        font=dict(size=14, color='black', family='Arial Black'),
        textangle=-90,
        bgcolor='white',
        bordercolor='black',
        borderwidth=1
    )
    
    # Spacing annotations
    # Spacing along (between sprinklers along the line - vertical direction)
    if n_sprinklers_per_line > 1:
        fig.add_annotation(
            x=subplot_width + 15, y=spacing_along/2,
            text=f"Spacing: {int(spacing_along)} m",
            showarrow=True,
            arrowhead=3,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor='black',
            ax=subplot_width + 15, ay=spacing_along * 1.5,
            font=dict(size=11, color='blue'),
            textangle=-90
        )
    
    # Spacing between lines (horizontal direction)
    if n_lines > 1:
        fig.add_annotation(
            x=spacing_between/2, y=-8,
            text=f"Line Spacing: {int(spacing_between)} m",
            showarrow=True,
            arrowhead=3,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor='black',
            ax=spacing_between * 1.5, ay=-8,
            font=dict(size=11, color='blue')
        )
    
    # Layout
    fig.update_layout(
        title=f"Single Sub-Plot Layout: {n_sprinklers_per_line} Sprinklers × {n_lines} Lines",
        xaxis_title="Width (m)",
        yaxis_title="Length (m)",
        template="plotly_white",
        height=600,
        yaxis=dict(scaleanchor="x", scaleratio=1),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.15,
            xanchor="center",
            x=0.5
        ),
        margin=dict(l=80, r=80, t=80, b=100)
    )
    
    st.plotly_chart(fig, width="stretch")


def create_field_with_subplot_detail(total_subplots, n_rows, n_cols,
                                     field_length, field_width,
                                     n_sprinklers_per_line, n_lines,
                                     spacing_along, spacing_between):
    """Create field subdivision diagram with sprinkler detail in one subplot
    
    Args:
        total_subplots: Total number of subplots
        n_rows: Number of rows
        n_cols: Number of columns
        field_length: Total field length in meters
        field_width: Total field width in meters
        n_sprinklers_per_line: Number of sprinklers per line
        n_lines: Number of sprinkler lines
        spacing_along: Spacing between sprinklers (m)
        spacing_between: Spacing between lines (m)
    """
    
    # Get actual field boundary from GPS data
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    local_polygon = field_geometry.get('local_polygon', None)
    
    fig = go.Figure()
    
    # Detect if field is regular quadrilateral (4 corners) or irregular
    from shapely.geometry import Polygon, MultiPoint, LineString, Point
    is_regular_quad = False
    
    if local_polygon:
        poly = Polygon(local_polygon)
        corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
        is_regular_quad = len(corners) == 4
    
    # Draw actual field boundary
    if local_polygon:
        boundary_x = [coord[0] for coord in local_polygon]
        boundary_y = [coord[1] for coord in local_polygon]
        boundary_x.append(boundary_x[0])
        boundary_y.append(boundary_y[0])
        
        fig.add_trace(go.Scatter(
            x=boundary_x,
            y=boundary_y,
            mode='lines',
            line=dict(color='black', width=3),
            name='Field Boundary',
            fill='toself',
            fillcolor='rgba(200, 200, 200, 0.1)'
        ))
    else:
        fig.add_trace(go.Scatter(
            x=[0, field_width, field_width, 0, 0],
            y=[0, 0, field_length, field_length, 0],
            mode='lines',
            line=dict(color='black', width=3),
            name='Field Boundary',
            fill='toself',
            fillcolor='rgba(200, 200, 200, 0.1)'
        ))
    
    # Draw subplot grid lines using smart orientation detection
    from shapely.geometry import Point, Polygon, LineString, MultiPoint
    from shapely.ops import split
    import numpy as np
    
    poly = None
    if local_polygon:
        poly = Polygon(local_polygon)
        bounds = poly.bounds
        min_x, min_y, max_x, max_y = bounds
    else:
        min_x, min_y = 0, 0
        max_x, max_y = field_width, field_length
    
    # Draw subplot division grid lines (edge-parallel for regular, bounding box for irregular)
    if is_regular_quad and local_polygon:
        # REGULAR QUADRILATERAL: Edge-parallel subplot grid lines
        
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
        
        # Define edges
        left_edge = (bottom_left, top_left)
        right_edge = (bottom_right, top_right)
        bottom_edge = (bottom_left, bottom_right)
        top_edge = (top_left, top_right)
        
        # Draw horizontal division lines (parallel to width edges)
        for i in range(1, n_rows):
            fraction = i / n_rows
            
            # Interpolate between left and right edges
            left_point = (
                left_edge[0][0] + fraction * (left_edge[1][0] - left_edge[0][0]),
                left_edge[0][1] + fraction * (left_edge[1][1] - left_edge[0][1])
            )
            right_point = (
                right_edge[0][0] + fraction * (right_edge[1][0] - right_edge[0][0]),
                right_edge[0][1] + fraction * (right_edge[1][1] - right_edge[0][1])
            )
            
            # Create line and intersect with polygon
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
                            showlegend=False,
                            hoverinfo='skip',
                            opacity=0.8
                        ))
        
        # Draw vertical division lines (parallel to length edges)
        for i in range(1, n_cols):
            fraction = i / n_cols
            
            # Interpolate between bottom and top edges
            bottom_point = (
                bottom_edge[0][0] + fraction * (bottom_edge[1][0] - bottom_edge[0][0]),
                bottom_edge[0][1] + fraction * (bottom_edge[1][1] - bottom_edge[0][1])
            )
            top_point = (
                top_edge[0][0] + fraction * (top_edge[1][0] - top_edge[0][0]),
                top_edge[0][1] + fraction * (top_edge[1][1] - top_edge[0][1])
            )
            
            # Create line and intersect with polygon
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
                            showlegend=False,
                            hoverinfo='skip',
                            opacity=0.8
                        ))
    else:
        # IRREGULAR POLYGON or NO GPS: Use simple bounding box subdivision
        subplot_width = field_width / n_cols
        subplot_length = field_length / n_rows
        
        if poly:
            # For irregular polygons, use bounding box lines
            # Horizontal lines
            for i in range(1, n_rows):
                y_pos = min_y + (i * (max_y - min_y) / n_rows)
                test_line = LineString([(min_x - 100, y_pos), (max_x + 100, y_pos)])
                intersection = test_line.intersection(poly)
                
                if not intersection.is_empty:
                    if intersection.geom_type == 'LineString':
                        coords = list(intersection.coords)
                        fig.add_trace(go.Scatter(
                            x=[c[0] for c in coords],
                            y=[c[1] for c in coords],
                            mode='lines',
                            line=dict(color='black', width=1.5, dash='dash'),
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
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
            
            # Vertical lines
            for i in range(1, n_cols):
                x_pos = min_x + (i * (max_x - min_x) / n_cols)
                test_line = LineString([(x_pos, min_y - 100), (x_pos, max_y + 100)])
                intersection = test_line.intersection(poly)
                
                if not intersection.is_empty:
                    if intersection.geom_type == 'LineString':
                        coords = list(intersection.coords)
                        fig.add_trace(go.Scatter(
                            x=[c[0] for c in coords],
                            y=[c[1] for c in coords],
                            mode='lines',
                            line=dict(color='black', width=1.5, dash='dash'),
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
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
        else:
            # Simple rectangular field without GPS
            # Vertical lines
            for i in range(1, n_cols):
                x_pos = i * subplot_width
                fig.add_trace(go.Scatter(
                    x=[x_pos, x_pos],
                    y=[0, field_length],
                    mode='lines',
                    line=dict(color='black', width=1.5, dash='dash'),
                    showlegend=False,
                    hoverinfo='skip',
                    opacity=0.8
                ))
            
            # Horizontal lines
            for i in range(1, n_rows):
                y_pos = i * subplot_length
                fig.add_trace(go.Scatter(
                    x=[0, field_width],
                    y=[y_pos, y_pos],
                    mode='lines',
                    line=dict(color='black', width=1.5, dash='dash'),
                    showlegend=False,
                    hoverinfo='skip',
                    opacity=0.8
                ))
    
    # Smart adaptive sprinkler placement for ANY field shape
    from shapely.ops import split
    import numpy as np
    
    poly = None
    if local_polygon:
        poly = Polygon(local_polygon)
        bounds = poly.bounds
        min_x, min_y, max_x, max_y = bounds
    else:
        min_x, min_y = 0, 0
        max_x, max_y = field_width, field_length
    
    legend_added = {'line': False, 'sprinkler': False}
    
    # PERFORMANCE OPTIMIZATION: Collect all lines and sprinklers, then draw in batches
    all_line_coords = []  # List of line coordinate lists
    all_sprinkler_x = []
    all_sprinkler_y = []
    
    # Smart adaptive sprinkler placement based on field shape
    if is_regular_quad and poly:
        # REGULAR QUADRILATERAL: Use edge-parallel sprinkler lines
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
        
        # Subplot dimensions
        subplot_width = field_width / n_cols
        subplot_length = field_length / n_rows
        
        # Generate sprinkler lines for each subplot
        subplot_count = 0
        for row in range(n_rows):
            for col in range(n_cols):
                subplot_count += 1
                # Calculate this subplot's corner fractions
                row_frac_bottom = row / n_rows
                row_frac_top = (row + 1) / n_rows
                col_frac_left = col / n_cols
                col_frac_right = (col + 1) / n_cols
                
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
                    line_end = (
                        subplot_tl[0] + line_fraction_in_subplot * (subplot_tr[0] - subplot_tl[0]),
                        subplot_tl[1] + line_fraction_in_subplot * (subplot_tr[1] - subplot_tl[1])
                    )
                    
                    # Create line and intersect with field polygon (for irregular boundaries)
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
                    
                    # Collect line coordinates and place sprinklers
                    for segment in line_segments:
                        coords = list(segment.coords)
                        all_line_coords.append(coords)
                        
                        # Place sprinklers along this line segment
                        segment_length = segment.length
                        
                        sprinklers_before = len(all_sprinkler_x)
                        
                        # Calculate actual number of sprinklers based on segment length
                        # Use ceiling to ensure we don't miss coverage at the end
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
                            
                            # Add sprinkler directly (line segment already clipped to field boundaries)
                            all_sprinkler_x.append(sprinkler_x)
                            all_sprinkler_y.append(sprinkler_y)
                        
                        sprinklers_added = len(all_sprinkler_x) - sprinklers_before
                        if sprinklers_added == 0:
                            log_debug(f"Row {row}, Col {col}, Line {line_idx}: No sprinklers added. Segment length: {segment_length:.1f}m, Required: {n_sprinklers_per_line} sprinklers at {spacing_along:.1f}m spacing")
                        elif col == 0 and line_idx == 0:  # Log first line of first column in each row
                            log_debug(f"Row {row}, Col {col}, Line {line_idx}: Added {sprinklers_added} sprinklers")
        
        log_debug(f"Total subplots processed in quadrilateral: {subplot_count}")
    
    else:
        # IRREGULAR POLYGON: Use vertical bounding box approach
        # Place sprinkler lines within each subplot
        
        subplot_width = field_width / n_cols
        subplot_length = field_length / n_rows
        
        # Generate sprinkler lines for each subplot
        for row in range(n_rows):
            for col in range(n_cols):
                # Calculate this subplot's bounding box
                subplot_min_x = min_x + col * (max_x - min_x) / n_cols
                subplot_max_x = min_x + (col + 1) * (max_x - min_x) / n_cols
                subplot_min_y = min_y + row * (max_y - min_y) / n_rows
                subplot_max_y = min_y + (row + 1) * (max_y - min_y) / n_rows
                
                subplot_actual_width = subplot_max_x - subplot_min_x
                
                # For each sprinkler line within this subplot
                for line_idx in range(n_lines):
                    # Position of this vertical line within the subplot
                    # Lines are evenly distributed across the subplot width
                    line_x = subplot_min_x + (line_idx + 0.5) * (subplot_actual_width / n_lines)
                    
                    if line_x > subplot_max_x:
                        continue
                    
                    # Create a vertical line from subplot bottom to top
                    test_line = LineString([(line_x, subplot_min_y - 10), (line_x, subplot_max_y + 10)])
                    
                    if poly:
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
                        
                        # Collect line coordinates and sprinklers
                        for segment in line_segments:
                            coords = list(segment.coords)
                            all_line_coords.append(coords)
                            
                            # Place sprinklers along this line segment
                            segment_length = segment.length
                            
                            # Calculate actual number of sprinklers based on segment length
                            # Use ceiling to ensure we don't miss coverage at the end
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
                                
                                # Calculate sprinkler position along the line
                                sprinkler_x = coords[0][0] + t * (coords[-1][0] - coords[0][0])
                                sprinkler_y = coords[0][1] + t * (coords[-1][1] - coords[0][1])
                                
                                # Add sprinkler directly (line segment already clipped to field boundaries)
                                all_sprinkler_x.append(sprinkler_x)
                                all_sprinkler_y.append(sprinkler_y)
                    else:
                        # Simple rectangular field without polygon
                        all_line_coords.append([(line_x, subplot_min_y), (line_x, subplot_max_y)])
                        
                        for spr_idx in range(n_sprinklers_per_line):
                            sprinkler_y = subplot_min_y + (spr_idx + 0.5) * spacing_along
                            
                            if sprinkler_y <= subplot_max_y:
                                all_sprinkler_x.append(line_x)
                                all_sprinkler_y.append(sprinkler_y)
    
    # BATCH DRAW: Add all lines in one trace, all sprinklers in another (MUCH faster)
    # Draw all sprinkler lines at once
    total_lines = len(all_line_coords)
    total_sprinklers = len(all_sprinkler_x)
    
    # Check for unique sprinkler positions
    unique_positions = set(zip(all_sprinkler_x, all_sprinkler_y))
    unique_count = len(unique_positions)
    
    # Display debug info in Streamlit UI
    st.info(f"""
    **Debug Info:**
    - Total lines drawn: {total_lines}
    - Total sprinklers placed: {total_sprinklers}
    - **Unique sprinkler positions: {unique_count}** {'⚠️ DUPLICATES DETECTED!' if unique_count < total_sprinklers else '✓'}
    - Grid: {n_rows} rows × {n_cols} cols × {n_lines} lines/subplot = {n_rows * n_cols * n_lines} expected lines
    - Expected sprinklers: ~{n_rows * n_cols * n_lines * n_sprinklers_per_line}
    - Sprinklers per line config: {n_sprinklers_per_line}
    """)
    
    for coords in all_line_coords:
        fig.add_trace(go.Scatter(
            x=[c[0] for c in coords],
            y=[c[1] for c in coords],
            mode='lines',
            line=dict(color='blue', width=1),
            name='Sprinkler Line' if not legend_added['line'] else None,
            showlegend=not legend_added['line'],
            legendgroup='sprinkler_lines',
            hoverinfo='skip'
        ))
        legend_added['line'] = True
    
    # Draw all sprinklers at once
    if all_sprinkler_x:
        fig.add_trace(go.Scatter(
            x=all_sprinkler_x,
            y=all_sprinkler_y,
            mode='markers',
            marker=dict(
                size=6,  # Increased from 4 to 6 for better visibility
                color='green',
                symbol='circle',
                opacity=0.8  # Added opacity to see overlapping
            ),
            name='Sprinkler',
            showlegend=True,
            legendgroup='sprinklers',
            hovertemplate='<b>Sprinkler</b><extra></extra>'
        ))
    
    # Layout
    fig.update_layout(
        title=f"Field Subdivision with Sprinkler Detail (Top-Right Subplot)",
        xaxis_title="Width (m)",
        yaxis_title="Length (m)",
        template="plotly_white",
        height=600,
        yaxis=dict(scaleanchor="x", scaleratio=1),
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        )
    )
    
    # Add water source icon if available
    water_source_local = field_geometry.get('water_source_local')
    if water_source_local:
        fig.add_trace(go.Scatter(
            x=[water_source_local[0]],
            y=[water_source_local[1]],
            mode='markers',
            marker=dict(size=12, color='blue', symbol='circle'),
            name='Water Source',
            showlegend=True,
            hovertemplate='Water Source<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
        ))
    
    st.plotly_chart(fig, width="stretch", key="operational_schedule_diagram")


def create_subdivision_diagram(total_subplots, n_rows, n_cols,
                               field_length, field_width, sprinkler=None):
    """Create visual diagram of field subdivision into subplots
    
    Args:
        total_subplots: Total number of subplots
        n_rows: Number of rows (divisions along length)
        n_cols: Number of columns (divisions along width)
        field_length: Total field length in meters
        field_width: Total field width in meters
        sprinkler: Sprinkler data dict (optional) - if provided, shows sprinkler layout in one subplot
    """
    
    st.markdown("### 📋 Field Subdivision Diagram")
    
    # Get actual field boundary from GPS data
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    local_polygon = field_geometry.get('local_polygon', None)
    
    fig = go.Figure()
    
    # Draw actual field boundary from GPS delineation
    if local_polygon:
        # Extract x and y coordinates
        boundary_x = [coord[0] for coord in local_polygon]
        boundary_y = [coord[1] for coord in local_polygon]
        
        # Close the polygon
        boundary_x.append(boundary_x[0])
        boundary_y.append(boundary_y[0])
        
        fig.add_trace(go.Scatter(
            x=boundary_x,
            y=boundary_y,
            mode='lines',
            line=dict(color='black', width=3),
            name='Field Boundary',
            fill='toself',
            fillcolor='rgba(200, 200, 200, 0.1)'
        ))
    else:
        # Fallback to rectangle if no GPS boundary
        fig.add_trace(go.Scatter(
            x=[0, field_width, field_width, 0, 0],
            y=[0, 0, field_length, field_length, 0],
            mode='lines',
            line=dict(color='black', width=3),
            name='Field Boundary',
            fill='toself',
            fillcolor='rgba(200, 200, 200, 0.1)'
        ))
    
    # Draw subplot grid lines using smart detection (works for all polygon types)
    if total_subplots > 1 and local_polygon:
        from shapely.geometry import Polygon, LineString, MultiPoint
        
        # Create shapely polygon
        poly = Polygon(local_polygon)
        
        # Detect if this is a regular quadrilateral (4 well-defined corners)
        # Get convex hull corners
        corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
        
        is_regular_quad = len(corners) == 4
        
        if is_regular_quad:
            # REGULAR QUADRILATERAL: Use edge-parallel interpolation method
            # This respects the actual field orientation
            
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
            
            # Define edges
            left_edge = (bottom_left, top_left)
            right_edge = (bottom_right, top_right)
            bottom_edge = (bottom_left, bottom_right)
            top_edge = (top_left, top_right)
            
            # Draw horizontal division lines (gold) - parallel to width edges
            for i in range(1, n_rows):
                fraction = i / n_rows
                
                # Interpolate between left and right edges
                left_point = (
                    left_edge[0][0] + fraction * (left_edge[1][0] - left_edge[0][0]),
                    left_edge[0][1] + fraction * (left_edge[1][1] - left_edge[0][1])
                )
                right_point = (
                    right_edge[0][0] + fraction * (right_edge[1][0] - right_edge[0][0]),
                    right_edge[0][1] + fraction * (right_edge[1][1] - right_edge[0][1])
                )
                
                # Create line and intersect with polygon
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
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
            
            # Draw vertical division lines (black dashed) - parallel to length edges
            for i in range(1, n_cols):
                fraction = i / n_cols
                
                # Interpolate between bottom and top edges
                bottom_point = (
                    bottom_edge[0][0] + fraction * (bottom_edge[1][0] - bottom_edge[0][0]),
                    bottom_edge[0][1] + fraction * (bottom_edge[1][1] - bottom_edge[0][1])
                )
                top_point = (
                    top_edge[0][0] + fraction * (top_edge[1][0] - top_edge[0][0]),
                    top_edge[0][1] + fraction * (top_edge[1][1] - top_edge[0][1])
                )
                
                # Create line and intersect with polygon
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
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
        else:
            # IRREGULAR POLYGON: Use bounding box method
            # This works for any complex shape
            
            minx, miny, maxx, maxy = poly.bounds
            
            # Draw horizontal division lines (black dashed)
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
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
            
            # Draw vertical division lines (red)
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
                                showlegend=False,
                                hoverinfo='skip',
                                opacity=0.8
                            ))
    elif total_subplots > 1:
        # Fallback for rectangular fields without GPS boundary
        min_x, max_x = 0, field_width
        min_y, max_y = 0, field_length
        actual_width = max_x - min_x
        actual_length = max_y - min_y
        
        # Simple vertical and horizontal lines
        for i in range(1, n_cols):
            x_pos = min_x + (i * actual_width / n_cols)
            fig.add_trace(go.Scatter(
                x=[x_pos, x_pos],
                y=[min_y, max_y],
                mode='lines',
                line=dict(color='brown', width=1, dash='dot'),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        for i in range(1, n_rows):
            y_pos = min_y + (i * actual_length / n_rows)
            fig.add_trace(go.Scatter(
                x=[min_x, max_x],
                y=[y_pos, y_pos],
                mode='lines',
                line=dict(color='brown', width=1, dash='dot'),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Layout
    fig.update_layout(
        title=f"Field Subdivision: {n_rows} × {n_cols} = {total_subplots} Subplots",
        xaxis_title="Width (m)",
        yaxis_title="Length (m)",
        template="plotly_white",
        height=600,
        yaxis=dict(scaleanchor="x", scaleratio=1),
        showlegend=True
    )
    
    st.plotly_chart(fig, width="stretch")


def create_irrigation_schedule_diagram(total_subplots, n_rows, n_cols,
                                       field_length, field_width,
                                       subplots_per_day, total_days):
    """Create visual diagram showing which subplots are irrigated each day
    
    Args:
        total_subplots: Total number of subplots
        n_rows: Number of rows (divisions along length)
        n_cols: Number of columns (divisions along width)
        field_length: Total field length in meters
        field_width: Total field width in meters
        subplots_per_day: Number of subplots irrigated per day (for regular fields)
        total_days: Total days to complete irrigation cycle
    """
    
    # Define distinct colors for each day (using a color palette)
    day_colors = [
        '#FF6B6B',  # Red - Day 1
        '#4ECDC4',  # Teal - Day 2
        '#45B7D1',  # Blue - Day 3
        '#FFA07A',  # Light Salmon - Day 4
        '#98D8C8',  # Mint - Day 5
        '#F7DC6F',  # Yellow - Day 6
        '#BB8FCE',  # Purple - Day 7
        '#85C1E2',  # Sky Blue - Day 8
        '#F8B88B',  # Peach - Day 9
        '#A9DFBF',  # Light Green - Day 10
    ]
    
    # Extend color list if needed
    while len(day_colors) < total_days:
        day_colors.extend(day_colors[:total_days - len(day_colors)])
    
    fig = go.Figure()
    
    # Get actual field boundary from GPS data (same as subdivision diagram)
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    local_polygon = field_geometry.get('local_polygon', None)
    
    # Draw actual field boundary from GPS delineation
    if local_polygon:
        # Extract x and y coordinates
        boundary_x = [coord[0] for coord in local_polygon]
        boundary_y = [coord[1] for coord in local_polygon]
        
        # Close the polygon
        boundary_x.append(boundary_x[0])
        boundary_y.append(boundary_y[0])
        
        fig.add_trace(go.Scatter(
            x=boundary_x,
            y=boundary_y,
            mode='lines',
            line=dict(color='black', width=3),
            name='Field Boundary',
            showlegend=False
        ))
    else:
        # Fallback to rectangle if no GPS boundary
        fig.add_trace(go.Scatter(
            x=[0, field_width, field_width, 0, 0],
            y=[0, 0, field_length, field_length, 0],
            mode='lines',
            line=dict(color='black', width=3),
            name='Field Boundary',
            showlegend=False
        ))
    
    # Calculate subplot dimensions
    subplot_width = field_width / n_cols
    subplot_length = field_length / n_rows
    standard_subplot_area = subplot_width * subplot_length  # Area of one full subplot
    
    # Check if subplots are within field boundary for irregular shapes
    from shapely.geometry import Polygon, Point, box as shapely_box, LineString, MultiPoint
    from shapely.ops import unary_union
    poly = None
    is_regular_quad = False
    
    if local_polygon:
        poly = Polygon(local_polygon)
        # Detect if field is regular quadrilateral (4 corners)
        corners = list(MultiPoint(local_polygon).convex_hull.exterior.coords)[:-1]
        is_regular_quad = len(corners) == 4
    
    # Get water source location for distance-based sorting
    water_source_local = field_geometry.get('water_source_local')
    
    # For area-based scheduling
    target_area_per_day = subplots_per_day * standard_subplot_area
    current_day = 1
    current_day_area = 0
    day_legend_added = set()  # Track which days have been added to legend
    
    # First pass: collect all subplots with their properties
    subplot_data = []  # List of (center_coords, clipped_area, geometry_coords, subplot_info)
    
    # SMART SUBDIVISION: Edge-parallel for regular quads, bounding box for irregular
    if is_regular_quad and poly:
        # REGULAR QUADRILATERAL: Use edge-parallel subdivision
        
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
        
        # Define edges for interpolation
        left_edge = (bottom_left, top_left)
        right_edge = (bottom_right, top_right)
        bottom_edge = (bottom_left, bottom_right)
        top_edge = (top_left, top_right)
        
        # Generate subplots using edge-parallel interpolation
        for row in range(n_rows):
            for col in range(n_cols):
                # Calculate fractions for this subplot's boundaries
                row_frac_bottom = row / n_rows
                row_frac_top = (row + 1) / n_rows
                col_frac_left = col / n_cols
                col_frac_right = (col + 1) / n_cols
                
                # Interpolate four corners of this subplot
                # Bottom-left corner
                bl_left = (
                    left_edge[0][0] + row_frac_bottom * (left_edge[1][0] - left_edge[0][0]),
                    left_edge[0][1] + row_frac_bottom * (left_edge[1][1] - left_edge[0][1])
                )
                bl_right = (
                    right_edge[0][0] + row_frac_bottom * (right_edge[1][0] - right_edge[0][0]),
                    right_edge[0][1] + row_frac_bottom * (right_edge[1][1] - right_edge[0][1])
                )
                bottom_left_corner = (
                    bl_left[0] + col_frac_left * (bl_right[0] - bl_left[0]),
                    bl_left[1] + col_frac_left * (bl_right[1] - bl_left[1])
                )
                
                # Bottom-right corner
                br_left = bl_left
                br_right = bl_right
                bottom_right_corner = (
                    br_left[0] + col_frac_right * (br_right[0] - br_left[0]),
                    br_left[1] + col_frac_right * (br_right[1] - br_left[1])
                )
                
                # Top-left corner
                tl_left = (
                    left_edge[0][0] + row_frac_top * (left_edge[1][0] - left_edge[0][0]),
                    left_edge[0][1] + row_frac_top * (left_edge[1][1] - left_edge[0][1])
                )
                tl_right = (
                    right_edge[0][0] + row_frac_top * (right_edge[1][0] - right_edge[0][0]),
                    right_edge[0][1] + row_frac_top * (right_edge[1][1] - right_edge[0][1])
                )
                top_left_corner = (
                    tl_left[0] + col_frac_left * (tl_right[0] - tl_left[0]),
                    tl_left[1] + col_frac_left * (tl_right[1] - tl_left[1])
                )
                
                # Top-right corner
                tr_left = tl_left
                tr_right = tl_right
                top_right_corner = (
                    tr_left[0] + col_frac_right * (tr_right[0] - tr_left[0]),
                    tr_left[1] + col_frac_right * (tr_right[1] - tr_left[1])
                )
                
                # Create subplot polygon and clip to field boundary
                subplot_coords = [bottom_left_corner, bottom_right_corner, top_right_corner, top_left_corner]
                subplot_poly = Polygon(subplot_coords)
                clipped_subplot = subplot_poly.intersection(poly)
                
                # Skip if no intersection or very small intersection
                if clipped_subplot.is_empty:
                    continue
                
                subplot_area = subplot_width * subplot_length
                clipped_area = clipped_subplot.area
                
                if clipped_area < (subplot_area * 0.01):  # Less than 1% overlap - skip tiny slivers
                    continue
                
                # Get coordinates of the clipped shape
                if clipped_subplot.geom_type == 'Polygon':
                    coords = list(clipped_subplot.exterior.coords)
                elif clipped_subplot.geom_type == 'MultiPolygon':
                    # Use the largest polygon
                    largest = max(clipped_subplot.geoms, key=lambda p: p.area)
                    coords = list(largest.exterior.coords)
                else:
                    # Skip invalid geometries
                    continue
                
                x_coords = [c[0] for c in coords]
                y_coords = [c[1] for c in coords]
                
                # Calculate center for this subplot
                center_x = sum(x_coords[:-1]) / (len(x_coords) - 1)
                center_y = sum(y_coords[:-1]) / (len(y_coords) - 1)
                
                # Store subplot data for sorting
                subplot_data.append({
                    'center': (center_x, center_y),
                    'area': clipped_area,
                    'x_coords': x_coords,
                    'y_coords': y_coords
                })
    
    else:
        # IRREGULAR POLYGON or NO GPS: Use bounding box subdivision
        for row in range(n_rows):
            for col in range(n_cols):
                # Calculate subplot corners
                x0 = col * subplot_width
                x1 = (col + 1) * subplot_width
                y0 = row * subplot_length
                y1 = (row + 1) * subplot_length
                
                if poly:
                    # Create subplot rectangle and clip to field boundary
                    subplot_rect = shapely_box(x0, y0, x1, y1)
                    clipped_subplot = subplot_rect.intersection(poly)
                    
                    # Skip if no intersection or very small intersection
                    if clipped_subplot.is_empty:
                        continue
                    
                    subplot_area = subplot_width * subplot_length
                    clipped_area = clipped_subplot.area
                    
                    if clipped_area < (subplot_area * 0.01):  # Less than 1% overlap - skip tiny slivers
                        continue
                    
                    # Get coordinates of the clipped shape
                    if clipped_subplot.geom_type == 'Polygon':
                        coords = list(clipped_subplot.exterior.coords)
                    elif clipped_subplot.geom_type == 'MultiPolygon':
                        # Use the largest polygon
                        largest = max(clipped_subplot.geoms, key=lambda p: p.area)
                        coords = list(largest.exterior.coords)
                    else:
                        # Skip invalid geometries
                        continue
                    
                    x_coords = [c[0] for c in coords]
                    y_coords = [c[1] for c in coords]
                else:
                    # Simple rectangle for regular fields
                    x_coords = [x0, x1, x1, x0, x0]
                    y_coords = [y0, y0, y1, y1, y0]
                    clipped_area = standard_subplot_area  # Full area for non-clipped subplots
                
                # Calculate center for this subplot
                center_x = sum(x_coords[:-1]) / (len(x_coords) - 1)
                center_y = sum(y_coords[:-1]) / (len(y_coords) - 1)
                
                # Store subplot data for sorting
                subplot_data.append({
                    'center': (center_x, center_y),
                    'area': clipped_area,
                    'x_coords': x_coords,
                    'y_coords': y_coords,
                    'row': row,  # Store grid position for sequential numbering
                    'col': col
                })
    
    # =============================================================================
    # SEQUENTIAL NUMBERING: Number subplots row-by-row, bottom to top, left to right
    # This creates a logical numbering: 1,2,3,4... flowing across the field
    # =============================================================================
    
    if len(subplot_data) > 0:
        import math
        
        # FIRST: Sort for SEQUENTIAL NUMBERING (row by row, bottom to top)
        # This gives subplots numbers 1, 2, 3... in a logical spatial order
        subplot_data.sort(key=lambda s: (s.get('row', 0), s.get('col', 0)))
        
        # =============================================================================
        # CONTIGUOUS DAY GROUPING: Assign days to spatially adjacent groups
        # Strategy: Create horizontal strips where each day covers adjacent rows
        # This ensures Day 1 plots are all together, Day 2 plots are all together, etc.
        # =============================================================================
        
        # Get field orientation
        centers = [s['center'] for s in subplot_data]
        x_coords_all = [c[0] for c in centers]
        y_coords_all = [c[1] for c in centers]
        x_range = max(x_coords_all) - min(x_coords_all) if len(x_coords_all) > 0 else 1
        y_range = max(y_coords_all) - min(y_coords_all) if len(y_coords_all) > 0 else 1
        
        # Determine if field is more horizontal or vertical
        is_horizontal = x_range >= y_range
        
        if water_source_local:
            # Calculate distance from water source for each subplot
            for subplot in subplot_data:
                dx = subplot['center'][0] - water_source_local[0]
                dy = subplot['center'][1] - water_source_local[1]
                subplot['ws_distance'] = math.sqrt(dx*dx + dy*dy)
            
            # GROUP BY DISTANCE BANDS from water source
            # Sort by distance, then assign days to distance bands
            # This ensures Day 1 = farthest plots (all together), Day 2 = next band, etc.
            
            # Sort by distance (farthest first for Day 1)
            subplot_data_by_distance = sorted(subplot_data, key=lambda s: -s['ws_distance'])
            
            # Calculate how many subplots per day
            actual_subplot_count = len(subplot_data)
            subplots_per_day_calc = actual_subplot_count / total_days if total_days > 0 else actual_subplot_count
            
            # Assign day numbers based on position in distance-sorted list
            for i, subplot in enumerate(subplot_data_by_distance):
                day_num = min(int(i / subplots_per_day_calc) + 1, total_days)
                subplot['assigned_day'] = day_num
            
            # Now re-sort back to row/col order for sequential numbering display
            subplot_data.sort(key=lambda s: (s.get('row', 0), s.get('col', 0)))
        else:
            # NO WATER SOURCE: Assign days by row groups (top to bottom)
            # Day 1 = top rows, Day 2 = next rows, etc.
            actual_subplot_count = len(subplot_data)
            subplots_per_day_calc = actual_subplot_count / total_days if total_days > 0 else actual_subplot_count
            
            # Sort by row (top to bottom = high y to low y), then by column
            subplot_data_by_rows = sorted(subplot_data, key=lambda s: (-s['center'][1], s['center'][0]))
            
            for i, subplot in enumerate(subplot_data_by_rows):
                day_num = min(int(i / subplots_per_day_calc) + 1, total_days)
                subplot['assigned_day'] = day_num
            
            # Re-sort back to row/col order for sequential numbering display
            subplot_data.sort(key=lambda s: (s.get('row', 0), s.get('col', 0)))
    
    # RECALCULATE based on ACTUAL number of subplots after clipping
    actual_subplot_count = len(subplot_data)
    
    # Safety check: if no subplots generated, initialize empty assignments and show warning
    if actual_subplot_count == 0:
        st.warning("⚠️ No subplots could be generated for this field configuration. Please check field geometry and subplot dimensions.")
        # Initialize empty assignments to prevent errors in pipe network
        st.session_state.project_data['operational_data']['subplot_day_assignments'] = {}
        st.session_state.project_data['operational_data']['actual_total_days'] = total_days
        return
    
    # Calculate TOTAL EFFECTIVE AREA (sum of all clipped subplot areas)
    total_effective_area = sum(subplot['area'] for subplot in subplot_data)
    effective_subplots = total_effective_area / standard_subplot_area if standard_subplot_area > 0 else actual_subplot_count
    
    # Use effective subplots (area-based) for calculation instead of grid count
    if effective_subplots > 0 and subplots_per_day > 0:
        actual_days_needed = int(np.ceil(effective_subplots / subplots_per_day))
        # Use the minimum of calculated days and the irrigation interval constraint
        actual_total_days = min(actual_days_needed, total_days)
    else:
        actual_total_days = total_days
    
    # Recalculate target area per day based on actual days
    if actual_total_days > 0:
        actual_subplots_per_day = effective_subplots / actual_total_days
        target_area_per_day = actual_subplots_per_day * standard_subplot_area
    else:
        actual_subplots_per_day = subplots_per_day
        target_area_per_day = subplots_per_day * standard_subplot_area
    
    # Now assign days based on area and draw subplots
    current_day = 1
    current_day_area = 0
    subplot_day_assignments = {}  # Store subplot number -> day mapping
    subplot_centers = {}  # Store subplot number -> (x, y) center coordinates
    subplot_polygons = {}  # Store subplot number -> polygon coordinates for valve positioning
    
    # Check for manual overrides from user AND existing saved assignments
    manual_overrides = st.session_state.get('manual_day_overrides', {})
    existing_assignments = st.session_state.project_data.get('operational_data', {}).get('subplot_day_assignments', {})
    # IMPORTANT: Also use existing assignments even without manual overrides flag
    # This ensures that saved schedules persist across page refreshes
    has_saved_assignments = bool(existing_assignments)
    has_manual_overrides = bool(manual_overrides) or st.session_state.project_data.get('operational_data', {}).get('manual_overrides_applied', False)
    
    for subplot_num, subplot in enumerate(subplot_data):
        clipped_area = subplot['area']
        x_coords = subplot['x_coords']
        y_coords = subplot['y_coords']
        center_x, center_y = subplot['center']
        
        # Store center coordinates and polygon for valve auto-positioning
        subplot_centers[subplot_num + 1] = (center_x, center_y)
        # Store polygon as list of (x,y) tuples (excluding last duplicate point)
        subplot_polygons[subplot_num + 1] = list(zip(x_coords[:-1], y_coords[:-1]))
        
        # CHECK FOR SAVED/MANUAL ASSIGNMENTS FIRST
        # Priority: 1) Manual overrides, 2) Saved assignments, 3) Algorithm assignment
        subplot_id = subplot_num + 1
        if subplot_id in manual_overrides:
            # Manual override takes highest priority
            day_num = manual_overrides[subplot_id]
        elif has_saved_assignments and subplot_id in existing_assignments:
            # Use previously saved assignment (persists across page refreshes)
            day_num = existing_assignments[subplot_id]
        else:
            # USE PRE-ASSIGNED DAY from contiguous grouping algorithm
            # This ensures spatially adjacent plots are on the same day
            day_num = subplot.get('assigned_day', 1)
        
        if day_num > actual_total_days:
            day_num = actual_total_days
        
        # Store the assignment (1-indexed subplot number)
        subplot_day_assignments[subplot_num + 1] = day_num
        
        color_idx = (day_num - 1) % len(day_colors)
        color = day_colors[color_idx]
        
        # Add colored shape for this subplot
        show_in_legend = day_num not in day_legend_added
        if show_in_legend:
            day_legend_added.add(day_num)
        
        fig.add_trace(go.Scatter(
            x=x_coords,
            y=y_coords,
            fill='toself',
            fillcolor=color,
            opacity=0.6,
            line=dict(color='black', width=1),
            name=f'Day {day_num}',
            showlegend=show_in_legend,
            hovertemplate=f'<b>Subplot {subplot_num + 1}</b><br>Irrigated on Day {day_num}<extra></extra>'
        ))
        
        # Add subplot number label in center
        fig.add_trace(go.Scatter(
            x=[center_x],
            y=[center_y],
            mode='text',
            text=f'{subplot_num + 1}',
            textfont=dict(size=10, color='black'),
            showlegend=False,
            hoverinfo='skip'
        ))
    
    # Save subplot day assignments, centers, AND polygons to session state for pipe network layout
    st.session_state.project_data['operational_data']['subplot_day_assignments'] = subplot_day_assignments
    st.session_state.project_data['operational_data']['subplot_centers'] = subplot_centers
    st.session_state.project_data['operational_data']['subplot_polygons'] = subplot_polygons
    st.session_state.project_data['operational_data']['actual_total_days'] = actual_total_days
    
    # Layout
    fig.update_layout(
        title=f"Operational Design Layout: {actual_total_days} Days ({actual_subplots_per_day:.1f} subplots/day) - {effective_subplots:.1f} effective subplots ({actual_subplot_count} displayed)",
        xaxis_title="Width (m)",
        yaxis_title="Length (m)",
        template="plotly_white",
        height=600,
        yaxis=dict(scaleanchor="x", scaleratio=1),
        showlegend=True,
        legend=dict(
            title="Irrigation Day",
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02
        )
    )
    
    # Add water source icon if available
    water_source_local = field_geometry.get('water_source_local')
    if water_source_local:
        fig.add_trace(go.Scatter(
            x=[water_source_local[0]],
            y=[water_source_local[1]],
            mode='markers',
            marker=dict(size=12, color='blue', symbol='circle'),
            name='Water Source',
            showlegend=True,
            hovertemplate='Water Source<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>'
        ))
    
    # Display both diagrams side by side
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"#### 📅 All Physical Subplots ({actual_subplot_count} displayed)")
        st.plotly_chart(fig, width="stretch", key="all_subplots_diagram")
    
    with col2:
        st.markdown(f"#### 📐 Effective Subplots (~{effective_subplots:.1f})")
        
        # Create second figure with NEW subdivision into ~9 subplots
        fig_eff = go.Figure()
        
        # Draw field boundary
        if local_polygon:
            boundary_x = [coord[0] for coord in local_polygon]
            boundary_y = [coord[1] for coord in local_polygon]
            boundary_x.append(boundary_x[0])
            boundary_y.append(boundary_y[0])
            
            fig_eff.add_trace(go.Scatter(
                x=boundary_x,
                y=boundary_y,
                mode='lines',
                line=dict(color='black', width=3),
                name='Field Boundary',
                showlegend=False
            ))
        
        # Calculate new grid dimensions for effective subplots
        # If effective = 9.2, create a grid that produces ~9 subplots
        num_effective_subplots = max(1, int(np.floor(effective_subplots)))  # Ensure at least 1
        
        # Calculate best grid layout (try to keep aspect ratio)
        aspect_ratio = field_width / field_length if field_length > 0 else 1
        
        # Safety check for dimensions
        if field_width <= 0 or field_length <= 0:
            st.error("Invalid field dimensions")
            return
        
        # Try different grid configurations to find best fit
        best_config = None
        min_diff = float('inf')
        
        for cols in range(1, num_effective_subplots + 1):
            rows = int(np.ceil(num_effective_subplots / cols))
            total = rows * cols
            config_aspect = cols / rows if rows > 0 else 1
            
            # Score based on total count and aspect ratio match
            diff = abs(total - num_effective_subplots) + abs(config_aspect - aspect_ratio) * 2
            
            if diff < min_diff:
                min_diff = diff
                best_config = (rows, cols)
        
        # Safety fallback
        if best_config is None:
            best_config = (1, 1)
        
        eff_n_rows, eff_n_cols = best_config
        eff_subplot_width = field_width / eff_n_cols
        eff_subplot_length = field_length / eff_n_rows
        eff_standard_area = eff_subplot_width * eff_subplot_length
        
        # Create subplot data for effective grid
        eff_subplot_data = []
        
        # Use same logic as main diagram but with new grid dimensions
        if is_regular_quad and poly:
            # REGULAR QUADRILATERAL: Edge-parallel subdivision
            for row in range(eff_n_rows):
                for col in range(eff_n_cols):
                    row_frac_bottom = row / eff_n_rows
                    row_frac_top = (row + 1) / eff_n_rows
                    col_frac_left = col / eff_n_cols
                    col_frac_right = (col + 1) / eff_n_cols
                    
                    # Calculate subplot corners by interpolating on field edges
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
                    
                    subplot_br = (
                        subplot_bl_left[0] + col_frac_right * (subplot_bl_right[0] - subplot_bl_left[0]),
                        subplot_bl_left[1] + col_frac_right * (subplot_bl_right[1] - subplot_bl_left[1])
                    )
                    
                    subplot_tr = (
                        subplot_tl_left[0] + col_frac_right * (subplot_tl_right[0] - subplot_tl_left[0]),
                        subplot_tl_left[1] + col_frac_right * (subplot_tl_right[1] - subplot_tl_left[1])
                    )
                    
                    # Create subplot polygon
                    subplot_poly = Polygon([subplot_bl, subplot_br, subplot_tr, subplot_tl])
                    
                    # Safety check for valid polygon
                    if not subplot_poly.is_valid:
                        continue
                    
                    intersection = subplot_poly.intersection(poly)
                    
                    if not intersection.is_empty and intersection.area > (eff_standard_area * 0.01):
                        # Handle different geometry types
                        if intersection.geom_type == 'Polygon':
                            coords = list(intersection.exterior.coords)
                        elif intersection.geom_type in ['MultiPolygon', 'GeometryCollection']:
                            # Take largest polygon
                            if hasattr(intersection, 'geoms'):
                                largest = max(intersection.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                                if hasattr(largest, 'exterior'):
                                    coords = list(largest.exterior.coords)
                                else:
                                    continue
                            else:
                                continue
                        else:
                            continue
                        
                        x_coords = [c[0] for c in coords]
                        y_coords = [c[1] for c in coords]
                        
                        if len(x_coords) < 4:  # Need at least 3 points + closing point
                            continue
                        
                        center_x = sum(x_coords[:-1]) / (len(x_coords) - 1)
                        center_y = sum(y_coords[:-1]) / (len(y_coords) - 1)
                        
                        eff_subplot_data.append({
                            'center': (center_x, center_y),
                            'area': intersection.area,
                            'x_coords': x_coords,
                            'y_coords': y_coords
                        })
        else:
            # IRREGULAR or NO GPS: Bounding box subdivision
            for row in range(eff_n_rows):
                for col in range(eff_n_cols):
                    x0 = col * eff_subplot_width
                    x1 = (col + 1) * eff_subplot_width
                    y0 = row * eff_subplot_length
                    y1 = (row + 1) * eff_subplot_length
                    
                    if poly:
                        subplot_rect = shapely_box(x0, y0, x1, y1)
                        clipped_subplot = subplot_rect.intersection(poly)
                        
                        if not clipped_subplot.is_empty and clipped_subplot.area > (eff_standard_area * 0.01):
                            # Handle different geometry types
                            if clipped_subplot.geom_type == 'Polygon':
                                coords = list(clipped_subplot.exterior.coords)
                            elif clipped_subplot.geom_type in ['MultiPolygon', 'GeometryCollection']:
                                # Take largest polygon
                                if hasattr(clipped_subplot, 'geoms'):
                                    largest = max(clipped_subplot.geoms, key=lambda g: g.area if hasattr(g, 'area') else 0)
                                    if hasattr(largest, 'exterior'):
                                        coords = list(largest.exterior.coords)
                                    else:
                                        continue
                                else:
                                    continue
                            else:
                                continue
                            
                            x_coords = [c[0] for c in coords]
                            y_coords = [c[1] for c in coords]
                            
                            if len(x_coords) < 4:  # Need at least 3 points + closing
                                continue
                            
                            center_x = sum(x_coords[:-1]) / (len(x_coords) - 1)
                            center_y = sum(y_coords[:-1]) / (len(y_coords) - 1)
                            
                            eff_subplot_data.append({
                                'center': (center_x, center_y),
                                'area': clipped_subplot.area,
                                'x_coords': x_coords,
                                'y_coords': y_coords
                            })
                    else:
                        x_coords = [x0, x1, x1, x0, x0]
                        y_coords = [y0, y0, y1, y1, y0]
                        center_x = (x0 + x1) / 2
                        center_y = (y0 + y1) / 2
                        
                        eff_subplot_data.append({
                            'center': (center_x, center_y),
                            'area': eff_standard_area,
                            'x_coords': x_coords,
                            'y_coords': y_coords
                        })
        
        # Sort by distance from water source (same as main diagram)
        if water_source_local and len(eff_subplot_data) > 0:
            for subplot in eff_subplot_data:
                dx = subplot['center'][0] - water_source_local[0]
                dy = subplot['center'][1] - water_source_local[1]
                subplot['distance'] = math.sqrt(dx*dx + dy*dy)
            eff_subplot_data.sort(key=lambda s: s['distance'], reverse=True)
        
        # Calculate effective area for this grid
        eff_total_area = sum(sp['area'] for sp in eff_subplot_data)
        eff_calculated = eff_total_area / eff_standard_area if eff_standard_area > 0 else len(eff_subplot_data)
        
        # Safety check: if no subplots generated, show warning
        if len(eff_subplot_data) == 0:
            st.warning("No effective subplots could be generated for this field shape. Showing field boundary only.")
            # Just show the diagram with boundary and water source
            if water_source_local:
                fig_eff.add_trace(go.Scatter(
                    x=[water_source_local[0]],
                    y=[water_source_local[1]],
                    mode='markers',
                    marker=dict(size=12, color='blue', symbol='circle'),
                    name='Water Source',
                    showlegend=True
                ))
            fig_eff.update_layout(
                title=f"Effective Grid: Unable to generate subplots",
                xaxis_title="Width (m)",
                yaxis_title="Length (m)",
                template="plotly_white",
                height=600,
                yaxis=dict(scaleanchor="x", scaleratio=1)
            )
            st.plotly_chart(fig_eff, width="stretch", key="effective_subplots_diagram")
            return  # Exit early
        
        # Assign colors by checking which days from main diagram this subplot overlaps
        # This shows multi-day subplots with mixed/gradient colors
        day_legend_added_eff = set()
        
        for subplot_num, subplot in enumerate(eff_subplot_data):
            clipped_area = subplot['area']
            x_coords = subplot['x_coords']
            y_coords = subplot['y_coords']
            center_x, center_y = subplot['center']
            
            # Safety check for valid coordinates
            if len(x_coords) < 4 or len(y_coords) < 4:
                continue
            
            # Check which days from the main diagram (24 subplots) overlap with this effective subplot
            try:
                eff_subplot_poly = Polygon(list(zip(x_coords[:-1], y_coords[:-1])))
                if not eff_subplot_poly.is_valid:
                    # Fallback: use default day assignment
                    overlapping_days = {1}
                else:
                    overlapping_days = set()
                    
                    # Check overlap with each main diagram subplot
                    for main_idx, main_subplot in enumerate(subplot_data):
                        try:
                            main_poly = Polygon(list(zip(main_subplot['x_coords'][:-1], main_subplot['y_coords'][:-1])))
                            
                            if not main_poly.is_valid:
                                continue
                            
                            if eff_subplot_poly.intersects(main_poly):
                                # Calculate which day this main subplot belongs to
                                main_cumulative = 0
                                main_day = 1
                                
                                for check_idx in range(main_idx + 1):
                                    check_area = subplot_data[check_idx]['area']
                                    
                                    if main_cumulative + check_area > target_area_per_day * 1.05 and main_day < actual_total_days:
                                        main_day += 1
                                        main_cumulative = check_area
                                    else:
                                        main_cumulative += check_area
                                
                                overlapping_days.add(min(main_day, actual_total_days))
                        except Exception:
                            # Skip invalid main subplots
                            continue
            except Exception:
                # Fallback if polygon creation fails
                overlapping_days = {1}
            
            # If no overlaps found (shouldn't happen), use default
            if not overlapping_days:
                overlapping_days = {1}
            
            days_list = sorted(list(overlapping_days))
            
            # Single day: solid color
            if len(days_list) == 1:
                day_num = days_list[0]
                color_idx = (day_num - 1) % len(day_colors)
                color = day_colors[color_idx]
                
                show_in_legend = day_num not in day_legend_added_eff
                if show_in_legend:
                    day_legend_added_eff.add(day_num)
                
                fig_eff.add_trace(go.Scatter(
                    x=x_coords,
                    y=y_coords,
                    fill='toself',
                    fillcolor=color,
                    opacity=0.6,
                    line=dict(color='black', width=2),
                    name=f'Day {day_num}',
                    showlegend=show_in_legend,
                    hovertemplate=f'<b>Subplot {subplot_num + 1}</b><br>Day {day_num}<br>Area: {clipped_area:.0f} m²<extra></extra>'
                ))
            
            # Multiple days: show with hatching/pattern or split display
            else:
                # Create gradient/split effect by layering
                for i, day_num in enumerate(days_list):
                    color_idx = (day_num - 1) % len(day_colors)
                    color = day_colors[color_idx]
                    
                    show_in_legend = day_num not in day_legend_added_eff
                    if show_in_legend:
                        day_legend_added_eff.add(day_num)
                    
                    # Adjust opacity to create striped effect
                    opacity = 0.3 + (i * 0.15)
                    
                    fig_eff.add_trace(go.Scatter(
                        x=x_coords,
                        y=y_coords,
                        fill='toself',
                        fillcolor=color,
                        opacity=opacity,
                        line=dict(color='black', width=2 if i == len(days_list)-1 else 0),
                        name=f'Day {day_num}',
                        showlegend=show_in_legend,
                        hovertemplate=f'<b>Subplot {subplot_num + 1}</b><br>Days: {", ".join(map(str, days_list))}<br>Area: {clipped_area:.0f} m²<extra></extra>'
                    ))
            
            # Add subplot number label
            label_text = f'{subplot_num + 1}'
            if len(days_list) > 1:
                label_text += f'\\n({",".join(map(str, days_list))})'
            
            fig_eff.add_trace(go.Scatter(
                x=[center_x],
                y=[center_y],
                mode='text',
                text=label_text,
                textfont=dict(size=10, color='black', family='Arial Black'),
                showlegend=False,
                hoverinfo='skip'
            ))
        
        # Add water source
        if water_source_local:
            fig_eff.add_trace(go.Scatter(
                x=[water_source_local[0]],
                y=[water_source_local[1]],
                mode='markers',
                marker=dict(size=12, color='blue', symbol='circle'),
                name='Water Source',
                showlegend=True,
                hovertemplate='Water Source<extra></extra>'
            ))
        
        # Layout
        fig_eff.update_layout(
            title=f"Effective Grid: {eff_n_rows}×{eff_n_cols} = {len(eff_subplot_data)} Subplots ({eff_calculated:.1f} Effective)",
            xaxis_title="Width (m)",
            yaxis_title="Length (m)",
            template="plotly_white",
            height=600,
            yaxis=dict(scaleanchor="x", scaleratio=1),
            showlegend=True,
            legend=dict(
                title="Irrigation Day",
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="left",
                x=1.02
            )
        )
        
        st.plotly_chart(fig_eff, width="stretch", key="effective_subplots_diagram")

