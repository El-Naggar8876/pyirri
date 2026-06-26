"""
Pipe Network Design Module
Size laterals, submains, and mainlines

IMPORTANT: This module supports systems WITH or WITHOUT submain lines.
When no submain exists, the mainline connects directly to laterals and takes
on the role of the submain for flow distribution and valve placement.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from shapely.geometry import Polygon, LineString, Point, MultiPoint
from shapely.ops import unary_union
from math import sqrt, atan2, cos, sin

# Canonical engineering kernels (single source of truth, unit-tested in tests/).
from modules.engineering_kernels import (
    hazen_williams_headloss as _hw_headloss,
    christiansen_f_factor as _f_factor,
)

# Import the plot creation function from pipe_network_layout
from modules.pipe_network_layout import create_interactive_plot

# Import DevLogger for toggleable debug output
from components.logger import DevLogger, log_debug, log_info, log_warning


def has_submain_lines(pipe_network_design=None, fig=None):
    """
    Check if the system has submain lines drawn.
    
    This function checks multiple sources to determine if submains exist:
    1. pipe_network_design data structure
    2. Plot figure traces (if provided)
    3. Session state network data
    
    Returns:
        tuple: (has_submains: bool, submain_count: int, submain_lines: list)
    """
    submain_lines = []
    
    # Check pipe_network_design data
    if pipe_network_design is None:
        pipe_network_design = st.session_state.project_data.get('pipe_network_design', {})
    
    # Get submains from network structure
    network = pipe_network_design.get('network', {})
    submains_data = network.get('submains', [])
    
    if submains_data:
        for submain in submains_data:
            if len(submain) >= 2:
                submain_lines.append(submain)
    
    # Also check direct submains key
    direct_submains = pipe_network_design.get('submains', [])
    if direct_submains:
        for submain in direct_submains:
            if len(submain) >= 2 and submain not in submain_lines:
                submain_lines.append(submain)
    
    # Check pipe_network_state in session
    if 'pipe_network_state' in st.session_state:
        state_network = st.session_state.pipe_network_state.get('network', {})
        state_submains = state_network.get('submains', [])
        for submain in state_submains:
            if len(submain) >= 2 and submain not in submain_lines:
                submain_lines.append(submain)
    
    # If figure is provided, also check for Submain traces
    if fig is not None:
        for trace in fig.data:
            if trace.name and 'Submain' in str(trace.name):
                if hasattr(trace, 'x') and hasattr(trace, 'y') and len(trace.x) >= 2:
                    # Found a submain trace
                    if not submain_lines:  # Only add if not already found
                        submain_lines.append(list(zip(trace.x, trace.y)))
    
    has_submains = len(submain_lines) > 0
    return has_submains, len(submain_lines), submain_lines


def get_mainline_valve_connections(mainline_valves, pipe_network_design, operational_data):
    """
    Get valve connections for mainline, handling both:
    1. Systems WITH submains: mainline valves connect to submains
    2. Systems WITHOUT submains: mainline connects directly to laterals
    
    Returns:
        list: List of valve connection data with flow information
    """
    has_submains, _, _ = has_submain_lines(pipe_network_design)
    
    valve_connections = []
    subplot_discharge_m3h = operational_data.get('subplot_discharge', 0)
    
    if subplot_discharge_m3h == 0:
        # Try to calculate from sprinkler data
        if 'sprinkler_data' in st.session_state.project_data:
            sprinkler = st.session_state.project_data['sprinkler_data']
            n_sprinklers_per_line = operational_data.get('n_sprinklers_per_line', 0)
            n_lines_per_subplot = operational_data.get('n_lines_per_subplot', 0)
            sprinkler_flow_lh = sprinkler.get('flow', 0)
            sprinkler_flow_m3h = sprinkler_flow_lh / 1000 if sprinkler_flow_lh > 0 else 0
            
            if n_sprinklers_per_line > 0 and n_lines_per_subplot > 0 and sprinkler_flow_m3h > 0:
                subplot_discharge_m3h = n_sprinklers_per_line * n_lines_per_subplot * sprinkler_flow_m3h
    
    for mv in mainline_valves:
        connection = {
            'valve': mv,
            'x': mv.get('x', 0),
            'y': mv.get('y', 0),
            'flow_m3h': 0,
            'connection_type': 'unknown',
            'subplots_served': []
        }
        
        if has_submains:
            # Traditional: mainline valve connects to submain
            connection['connection_type'] = 'submain'
            submain_indices = mv.get('submain_indices', [])
            if not submain_indices:
                single_idx = mv.get('submain_idx', None)
                if single_idx is not None:
                    submain_indices = [single_idx]
            
            # Get flow from submain designs
            for submain_idx in submain_indices:
                temp_key = f'temp_submain_{submain_idx}_design'
                saved_key = f'submain_{submain_idx}_design'
                
                design_data = None
                if temp_key in st.session_state:
                    design_data = st.session_state[temp_key]
                elif saved_key in st.session_state.project_data:
                    design_data = st.session_state.project_data[saved_key]
                
                if design_data:
                    segments = design_data.get('segments', [])
                    if segments:
                        seg1_flow = segments[0].get('full_flow_m3h', segments[0].get('flow_m3h', 0))
                        connection['flow_m3h'] += seg1_flow
                    else:
                        connection['flow_m3h'] += design_data.get('full_inlet_flow_m3h', 
                                                                  design_data.get('total_flow_m3h', 0))
        else:
            # No submains: mainline valve connects directly to laterals
            connection['connection_type'] = 'direct_lateral'
            
            # Get subplots served by this valve
            lateral_valves = pipe_network_design.get('valves', [])
            
            # Find lateral valves near this mainline valve position
            valve_x, valve_y = mv.get('x', 0), mv.get('y', 0)
            tolerance = 30.0  # meters - lateral valves within this distance
            
            nearby_subplots = []
            for lv in lateral_valves:
                lv_x, lv_y = lv.get('x', 0), lv.get('y', 0)
                dist = sqrt((valve_x - lv_x)**2 + (valve_y - lv_y)**2)
                
                if dist <= tolerance:
                    selected_subplots = lv.get('selected_subplots', [])
                    nearby_subplots.extend(selected_subplots)
            
            connection['subplots_served'] = list(set(nearby_subplots))
            connection['flow_m3h'] = len(connection['subplots_served']) * subplot_discharge_m3h
        
        valve_connections.append(connection)
    
    return valve_connections


def show():
    st.markdown('<h1 class="main-header">Pipe Network Design</h1>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
    Design pipe network including laterals, submains, and mainlines with proper sizing
    to maintain acceptable velocities and friction losses.
    </div>
    """, unsafe_allow_html=True)
    
    # Initialize pipe_network_design and restore valves from project_data
    # This ensures valves are available even when coming directly to this page
    if 'pipe_network_design' not in st.session_state.project_data:
        st.session_state.project_data['pipe_network_design'] = {
            'mainlines': [], 'submains': [], 'laterals': [], 'sprinklers': [], 'valves': []
        }
    
    network = st.session_state.project_data['pipe_network_design']
    
    # Restore valve_table from project_data if not in session state
    if 'valve_table' not in st.session_state:
        if 'valve_table' in st.session_state.project_data and st.session_state.project_data['valve_table']:
            st.session_state.valve_table = st.session_state.project_data['valve_table']
        elif network.get('valves'):
            # Reconstruct from network valves
            st.session_state.valve_table = [
                {
                    'name': v.get('name', f'V{i+1}'),
                    'subplots': v.get('selected_subplots', []),
                    'irrigation_day': v.get('irrigation_day', 'Not assigned'),
                    'x': v.get('x', 0),
                    'y': v.get('y', 0),
                    'auto_positioned': v.get('auto_positioned', False)
                }
                for i, v in enumerate(network['valves'])
            ]
        else:
            st.session_state.valve_table = []
    
    # Rebuild network['valves'] from valve_table if valve_table exists but network valves is empty
    if st.session_state.valve_table and not network.get('valves'):
        network['valves'] = []
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
            network['valves'].append(valve_data)
    
    # Solid Set system only - show all pipe types
    tabs = st.tabs(["Sprinkler Line", "Lateral Design", "Submain Design", "Mainline Design", "Network Summary"])
    
    with tabs[0]:
        show_sprinkler_line_design()
    
    with tabs[1]:
        show_lateral_design()
    
    with tabs[2]:
        show_submain_design()
    
    with tabs[3]:
        show_mainline_design()
    
    with tabs[4]:
        show_network_summary()


def calculate_f_factor(n_outlets):
    """Christiansen F-factor (delegates to engineering_kernels; unit-tested)."""
    return _f_factor(n_outlets)


def calculate_hazen_williams(Q_m3h, D_mm, L_m, C=130):
    """Hazen-Williams head loss in metres.

    Delegates to engineering_kernels.hazen_williams_headloss (single source of
    truth, exercised directly by the regression tests in tests/).
    """
    return _hw_headloss(Q_m3h, D_mm, L_m, C)


def get_standard_pipe_sizes():
    """Return standard PVC pipe sizes with nominal and internal diameters"""
    return [
        {'nominal': 20, 'internal': 17.6},
        {'nominal': 25, 'internal': 22.0},
        {'nominal': 32, 'internal': 28.0},
        {'nominal': 40, 'internal': 35.2},
        {'nominal': 50, 'internal': 44.0},
        {'nominal': 63, 'internal': 55.4},
        {'nominal': 75, 'internal': 66.0},
        {'nominal': 90, 'internal': 79.2},
        {'nominal': 110, 'internal': 96.8},
        {'nominal': 125, 'internal': 110.0},
        {'nominal': 140, 'internal': 123.2},
        {'nominal': 160, 'internal': 140.8},
        {'nominal': 200, 'internal': 176.0},
        {'nominal': 250, 'internal': 220.0},
        {'nominal': 315, 'internal': 277.2}
    ]


def calculate_mainline_flow_by_subplot_days(grouped_valves_downstream, lateral_valves, 
                                             subplot_day_assignments, lateral_flow_m3h):
    """
    Calculate mainline segment flow by counting ACTUAL SUBPLOTS per day.
    
    This is the most accurate method:
    1. For each downstream mainline valve → get its submain indices
    2. For each submain → find lateral valves on it
    3. For each lateral valve → get its subplots
    4. For each subplot → look up its irrigation day
    5. Count subplots per day → calculate flow per day
    6. Return MAX daily flow
    
    Parameters:
    -----------
    grouped_valves_downstream : list
        List of grouped mainline valves downstream of this segment
        Each has: distance, submain_refs, submain_indices, total_flow
    lateral_valves : list
        All lateral valves from pipe_network_design['valves']
    subplot_day_assignments : dict
        Mapping of subplot number to irrigation day {1: 1, 2: 1, 3: 2, ...}
    lateral_flow_m3h : float
        Flow per lateral/subplot in m³/h
    
    Returns:
    --------
    tuple: (max_daily_flow, daily_breakdown, details_dict)
    """
    import streamlit as st
    
    # If no scheduling data, fall back to sum of all
    if not subplot_day_assignments:
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        return total_flow, {}, {
            'method': 'sum_all',
            'reason': 'No subplot_day_assignments available',
            'total_flow': total_flow
        }
    
    # Get all irrigation days
    all_days = sorted(set(subplot_day_assignments.values()))
    if not all_days:
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        return total_flow, {}, {
            'method': 'sum_all', 
            'reason': 'No days in subplot_day_assignments',
            'total_flow': total_flow
        }
    
    # Initialize per-day counters
    subplots_per_day = {day: [] for day in all_days}  # day -> list of subplot IDs
    flow_per_day = {day: 0 for day in all_days}
    
    # Detailed breakdown for debugging
    breakdown = {
        'method': 'subplot_day_counting',
        'all_days': all_days,
        'lateral_flow_m3h': lateral_flow_m3h,
        'mainline_valves': [],
        'per_day_details': {day: {'subplots': [], 'flow': 0} for day in all_days}
    }
    
    # Collect ALL subplots served by downstream mainline valves
    all_downstream_subplots = set()
    
    for gv in grouped_valves_downstream:
        submain_refs = gv.get('submain_refs', [])
        submain_indices = gv.get('submain_indices', [])
        
        mv_breakdown = {
            'submain_refs': submain_refs,
            'submain_indices': submain_indices,
            'subplots_found': []
        }
        
        # For each submain this mainline valve serves
        for submain_idx in submain_indices:
            # Get submain design data to find which lateral valves are on it
            temp_key = f'temp_submain_{submain_idx}_design'
            saved_key = f'submain_{submain_idx}_design'
            
            # Method 1: Check submain design for stored valve info
            design_data = None
            if temp_key in st.session_state:
                design_data = st.session_state.get(temp_key)
            elif hasattr(st.session_state, 'project_data'):
                design_data = st.session_state.project_data.get(saved_key)
            
            # Get subplots from the submain's valves
            # We need to find lateral valves that belong to this submain
            # Since we don't have direct submain-to-valve mapping, 
            # we use the submain's stored subplot info or count from lateral_valves
            
            if design_data:
                # Check if submain design has stored day_flows info
                day_flows = design_data.get('day_flows', {})
                if day_flows:
                    for day, count in day_flows.items():
                        if day in subplots_per_day:
                            # Add placeholder subplot IDs for counting
                            for _ in range(count):
                                subplots_per_day[day].append(f"S{submain_idx}_D{day}")
                            mv_breakdown['subplots_found'].append(f"Submain {submain_idx+1}: {count} subplots on Day {day}")
        
        breakdown['mainline_valves'].append(mv_breakdown)
    
    # If we didn't find subplots from submain design, try direct lateral valve lookup
    if all(len(subs) == 0 for subs in subplots_per_day.values()):
        # Fallback: Check lateral_valves directly for their subplot assignments
        breakdown['method'] = 'lateral_valve_direct_lookup'
        
        for valve in lateral_valves:
            selected_subplots = valve.get('selected_subplots', [])
            for subplot_id in selected_subplots:
                day = subplot_day_assignments.get(subplot_id)
                if day is not None and day in subplots_per_day:
                    if subplot_id not in all_downstream_subplots:
                        all_downstream_subplots.add(subplot_id)
                        subplots_per_day[day].append(subplot_id)
    
    # Calculate flow per day
    for day in all_days:
        subplot_count = len(subplots_per_day[day])
        day_flow = subplot_count * lateral_flow_m3h
        flow_per_day[day] = day_flow
        breakdown['per_day_details'][day] = {
            'subplot_count': subplot_count,
            'subplots': subplots_per_day[day][:10],  # Limit for display
            'flow': day_flow
        }
    
    # If still no data, fall back to sum
    if all(f == 0 for f in flow_per_day.values()):
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        breakdown['method'] = 'fallback_sum'
        breakdown['reason'] = 'Could not determine subplot-day distribution'
        return total_flow, flow_per_day, breakdown
    
    # Find maximum daily flow
    max_daily_flow = max(flow_per_day.values())
    max_day = [d for d, f in flow_per_day.items() if f == max_daily_flow][0]
    
    breakdown['max_daily_flow'] = max_daily_flow
    breakdown['max_day'] = max_day
    breakdown['flow_per_day'] = flow_per_day
    
    return max_daily_flow, flow_per_day, breakdown


def calculate_max_daily_flow_for_mainline_v3(grouped_valves_downstream, pipe_network_design, 
                                              subplot_day_assignments, operational_data):
    """
    V3: Most accurate mainline flow calculation using submain flow data.
    
    FIXED: Instead of relying on potentially incorrect day_flows (which can have 
    double-counted valves from adjacent submains), we calculate directly from:
    1. Submain's full_inlet_flow_m3h (accurate flow)
    2. Primary operating day (which day the majority of flow occurs)
    
    For submains with mixed-day operation, we still use the full inlet flow
    assigned to the primary day (conservative approach).
    
    ENHANCED: Now also supports no-submain systems where mainline connects
    directly to laterals.
    
    Returns the MAX daily flow (not sum of all submains).
    """
    import streamlit as st
    
    # Get lateral flow rate (flow per subplot)
    lateral_flow_m3h = operational_data.get('subplot_discharge', 0)
    if lateral_flow_m3h == 0:
        lateral_flow_m3h = operational_data.get('lateral_flow_m3h', 20.8)  # Default
    
    # Get all lateral valves (for fallback and no-submain systems)
    lateral_valves = pipe_network_design.get('valves', [])
    
    # Check if this is a no-submain system
    is_no_submain = st.session_state.get('no_submain_system', False)
    
    # Also detect no-submain by checking if any submain indices exist
    has_submain_indices = any(gv.get('submain_indices', []) for gv in grouped_valves_downstream)
    
    if is_no_submain or not has_submain_indices:
        # NO-SUBMAIN SYSTEM: Calculate flow directly from valve data
        # Use the pre-calculated flow from grouped valves
        
        if not subplot_day_assignments:
            # No scheduling - sum all flows
            total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
            return total_flow, {}, {
                'method': 'no_submain_sum_all',
                'message': 'No-submain system - sum of all valve flows'
            }
        
        all_days = sorted(set(subplot_day_assignments.values()))
        daily_flow = {day: 0.0 for day in all_days}
        daily_contributions = {day: [] for day in all_days}
        
        # For no-submain systems, try to get flow assignment by subplot day
        for gv in grouped_valves_downstream:
            valve_flow = gv.get('total_flow', 0)
            submain_refs = gv.get('submain_refs', [])
            
            if valve_flow > 0:
                # Try to determine which day this valve flow belongs to
                # Look at lateral valves near this mainline valve
                # For now, distribute flow equally across days (conservative)
                flow_per_day = valve_flow / len(all_days) if all_days else valve_flow
                for day in all_days:
                    daily_flow[day] += flow_per_day
                    daily_contributions[day].append(f"Valve: {flow_per_day:.1f} m³/h")
        
        # Get max daily flow
        if all(f == 0 for f in daily_flow.values()):
            total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
            return total_flow, daily_flow, {
                'method': 'no_submain_fallback',
                'message': 'No-submain system - using total flow'
            }
        
        max_daily_flow = max(daily_flow.values())
        max_day = [d for d, f in daily_flow.items() if f == max_daily_flow][0]
        
        return max_daily_flow, daily_flow, {
            'method': 'no_submain_daily_calc',
            'message': 'No-submain system - max daily flow calculated',
            'max_day': max_day,
            'daily_flow': daily_flow,
            'daily_contributions': daily_contributions
        }
    
    # STANDARD CASE: System has submains
    # If no scheduling data, fall back to sum
    if not subplot_day_assignments:
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        return total_flow, {}, {
            'method': 'sum_all_no_schedule',
            'message': 'No operational scheduling - using sum of all submain flows'
        }
    
    all_days = sorted(set(subplot_day_assignments.values()))
    
    # Initialize daily accumulators - using FLOW directly, not subplot counts
    daily_flow = {day: 0.0 for day in all_days}
    daily_contributions = {day: [] for day in all_days}  # Track which submains contribute
    
    # Build breakdown for debugging
    breakdown = {
        'method': 'v3_submain_primary_day',
        'lateral_flow_m3h': lateral_flow_m3h,
        'all_days': all_days,
        'downstream_mainline_valves': len(grouped_valves_downstream),
        'submain_details': []
    }
    
    # Track which submains we've processed (avoid double counting)
    processed_submains = set()
    
    # For each downstream mainline valve group
    for gv_idx, gv in enumerate(grouped_valves_downstream):
        submain_refs = gv.get('submain_refs', [])
        submain_indices = gv.get('submain_indices', [])
        
        # For each submain served by this mainline valve
        for i, sub_idx in enumerate(submain_indices):
            if sub_idx in processed_submains:
                continue
            processed_submains.add(sub_idx)
            
            # FIXED: Use correct ref_name from submain index, not misaligned list
            ref_name = f"Submain {sub_idx + 1}"
            
            # Get submain design data - try temp first, then saved
            temp_key = f'temp_submain_{sub_idx}_design'
            saved_key = f'submain_{sub_idx}_design'
            
            submain_design = None
            source = "not found"
            if temp_key in st.session_state:
                submain_design = st.session_state[temp_key]
                source = f"temp ({temp_key})"
            elif hasattr(st.session_state, 'project_data') and saved_key in st.session_state.project_data:
                submain_design = st.session_state.project_data[saved_key]
                source = f"saved ({saved_key})"
            
            submain_entry = {
                'submain_idx': sub_idx,
                'ref_name': ref_name,
                'source': source,
                'flow_m3h': 0,
                'primary_day': None
            }
            
            if submain_design:
                # Get the FULL INLET FLOW (this is accurate from segment calculation)
                full_flow = submain_design.get('full_inlet_flow_m3h', 0)
                if full_flow == 0:
                    segments = submain_design.get('segments', [])
                    if segments:
                        full_flow = segments[0].get('full_flow_m3h', segments[0].get('flow_m3h', 0))
                
                # Get the PRIMARY operating day for this submain
                primary_day = submain_design.get('primary_operating_day')
                
                submain_entry['flow_m3h'] = full_flow
                submain_entry['primary_day'] = primary_day
                
                if primary_day is not None and primary_day in daily_flow:
                    # Assign the FULL submain flow to its primary operating day
                    daily_flow[primary_day] += full_flow
                    daily_contributions[primary_day].append(f"{ref_name}: {full_flow:.1f} m³/h")
                elif full_flow > 0:
                    # No primary day - might need fallback
                    # Check operating_days list
                    operating_days = submain_design.get('operating_days', [])
                    if operating_days:
                        # Split flow among operating days (conservative)
                        primary_day = operating_days[0]  # Use first day
                        if primary_day in daily_flow:
                            daily_flow[primary_day] += full_flow
                            daily_contributions[primary_day].append(f"{ref_name}: {full_flow:.1f} m³/h (from operating_days)")
                            submain_entry['primary_day'] = primary_day
            
            breakdown['submain_details'].append(submain_entry)
    
    # If we got no flow data from submain designs, use the grouped valve totals
    if all(f == 0 for f in daily_flow.values()):
        breakdown['method'] = 'v3_fallback_valve_totals'
        
        # Use the grouped valve's total_flow and try to assign based on position
        for gv in grouped_valves_downstream:
            total_flow = gv.get('total_flow', 0)
            if total_flow > 0:
                # Assign to Day 1 as fallback (conservative)
                if 1 in daily_flow:
                    daily_flow[1] += total_flow
                elif all_days:
                    daily_flow[all_days[0]] += total_flow
    
    breakdown['daily_flow'] = dict(daily_flow)
    breakdown['daily_contributions'] = daily_contributions
    
    # Convert to flow_per_day format for compatibility
    flow_per_day = dict(daily_flow)
    
    # Calculate subplot counts from flows (for display)
    daily_subplot_count = {}
    for day, flow in daily_flow.items():
        daily_subplot_count[day] = int(round(flow / lateral_flow_m3h)) if lateral_flow_m3h > 0 else 0
    breakdown['daily_subplot_counts'] = daily_subplot_count
    
    # Get max daily flow
    if not flow_per_day or all(f == 0 for f in flow_per_day.values()):
        # Final fallback to sum
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        breakdown['method'] = 'final_fallback_sum'
        breakdown['max_daily_flow'] = total_flow
        breakdown['fallback_reason'] = 'No submain design data found'
        return total_flow, flow_per_day, breakdown
    
    max_daily_flow = max(flow_per_day.values())
    max_day = [d for d, f in flow_per_day.items() if f == max_daily_flow][0]
    
    breakdown['max_daily_flow'] = max_daily_flow
    breakdown['max_day'] = max_day
    
    return max_daily_flow, flow_per_day, breakdown


def calculate_max_daily_flow_for_mainline_v2(grouped_valves_downstream, valve_table, subplot_day_assignments,
                                               operational_data):
    """
    Calculate the MAXIMUM DAILY flow for a mainline segment.
    
    This considers operational scheduling - which submains operate on which days.
    Each submain has a 'primary_operating_day' that determines when it operates.
    
    The mainline should be sized for the MAX daily demand, not the sum of all submains.
    
    Parameters:
    -----------
    grouped_valves_downstream : list
        List of grouped mainline valves downstream of this segment
        Each has: distance, submain_refs, submain_indices, total_flow
    valve_table : list
        The lateral valve table (V1, V2, etc.) with subplot assignments
    subplot_day_assignments : dict
        Mapping of subplot number to irrigation day
    operational_data : dict
        Operational design data
    
    Returns:
    --------
    tuple: (max_daily_flow, flow_breakdown_dict, details_str)
    """
    import streamlit as st
    
    # If no scheduling data, fall back to sum
    if not subplot_day_assignments:
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        return total_flow, {}, "No scheduling data - using total sum"
    
    # Get unique days
    all_days = sorted(set(subplot_day_assignments.values()))
    if not all_days:
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        return total_flow, {}, "No days defined - using total sum"
    
    # Initialize daily flow accumulators
    daily_flow_contributions = {day: 0 for day in all_days}
    daily_submain_details = {day: [] for day in all_days}
    
    # For each downstream mainline valve (grouped), determine which days it operates
    for gv in grouped_valves_downstream:
        submain_indices = gv.get('submain_indices', [])
        submain_refs = gv.get('submain_refs', [])
        
        # Process each submain individually to determine its day
        for i, submain_idx in enumerate(submain_indices):
            # Get submain design data to find its operating day and flow
            temp_key = f'temp_submain_{submain_idx}_design'
            saved_key = f'submain_{submain_idx}_design'
            
            design_data = None
            if temp_key in st.session_state:
                design_data = st.session_state[temp_key]
            elif 'project_data' in st.session_state and saved_key in st.session_state.project_data:
                design_data = st.session_state.project_data[saved_key]
            
            if not design_data:
                continue
            
            # Get the submain's flow (full inlet flow)
            segments = design_data.get('segments', [])
            if segments:
                submain_flow = segments[0].get('full_flow_m3h', segments[0].get('flow_m3h', 0))
            else:
                submain_flow = design_data.get('full_inlet_flow_m3h', design_data.get('total_flow_m3h', 0))
            
            # Get the submain's PRIMARY operating day (this is the key fix!)
            primary_day = design_data.get('primary_operating_day')
            operating_days = design_data.get('operating_days', [])
            
            # Determine which day(s) to assign this submain's flow
            if primary_day is not None:
                # Use the primary operating day
                days_to_use = [primary_day]
            elif operating_days:
                # Fall back to operating_days list (use first day)
                days_to_use = [operating_days[0]]
            else:
                # Fall back: assume all days (conservative)
                days_to_use = all_days
            
            # Get submain reference name
            ref_name = submain_refs[i] if i < len(submain_refs) else f"Submain {submain_idx + 1}"
            
            # Add flow to the appropriate day(s)
            for day in days_to_use:
                if day in daily_flow_contributions:
                    daily_flow_contributions[day] += submain_flow
                    daily_submain_details[day].append(f"{ref_name}: {submain_flow:.1f} m³/h")
    
    # Find the maximum daily flow
    if not daily_flow_contributions or all(v == 0 for v in daily_flow_contributions.values()):
        total_flow = sum(gv['total_flow'] for gv in grouped_valves_downstream)
        return total_flow, {}, "Could not determine daily operation - using total"
    
    max_daily_flow = max(daily_flow_contributions.values())
    max_day = [d for d, f in daily_flow_contributions.items() if f == max_daily_flow][0]
    
    details_parts = [f"Max on Day {max_day}: {max_daily_flow:.1f} m³/h"]
    for day in sorted(daily_flow_contributions.keys()):
        flow = daily_flow_contributions[day]
        submains = daily_submain_details.get(day, [])
        details_parts.append(f"Day {day}: {flow:.1f} m³/h ({len(submains)} submains)")
    
    return max_daily_flow, daily_flow_contributions, " | ".join(details_parts)


def show_sprinkler_line_design():
    """Design sprinkler line (farthest point in hydraulic design)"""
    st.markdown('<h2 class="sub-header">Sprinkler Line Design</h2>', unsafe_allow_html=True)
    
    # Header
    with st.expander("ℹ️ About Hydraulic Design Starting Point", expanded=False):
        st.markdown("""
        The sprinkler line is the **farthest point** in the irrigation system. Hydraulic design starts here 
        and works upstream: **Sprinkler Line → Lateral → Submain → Mainline → Pump**
        
        This ensures adequate pressure at the critical (farthest) sprinkler.
        """)
    
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete sprinkler selection first.")
        return
    
    sprinkler = st.session_state.project_data['sprinkler_data']
    operational_data = st.session_state.project_data.get('operational_data', {})
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    
    # Get SUBPLOT-LEVEL parameters from operational design (using correct keys)
    n_sprinklers_per_line = operational_data.get('n_sprinklers_per_line', 6)  # Subplot level
    n_lines_per_subplot = operational_data.get('n_lines_per_subplot', 6)  # Subplot level
    subplot_discharge_m3h = operational_data.get('subplot_discharge', 18.72)  # Total subplot discharge
    
    # Get basic parameters - try operational_data first, then sprinkler_data
    sprinkler_spacing = round(operational_data.get('spacing_along', sprinkler.get('spacing_along', 12)), 1)
    field_length = field_geometry.get('length_m', 850)
    field_width = field_geometry.get('width_m', 688)
    spacing_between = round(operational_data.get('spacing_between', sprinkler.get('spacing_between', 12)), 1)
    
    n_rows = operational_data.get('n_rows', 1)
    n_cols = operational_data.get('n_cols', 1)
    
    # Flow requirements - INDIVIDUAL sprinkler discharge
    sprinkler_flow_lh = sprinkler.get('flow', 500)
    sprinkler_flow_m3h = round(sprinkler_flow_lh / 1000, 3)
    sprinkler_flow_lps = round(sprinkler_flow_lh / 3600, 3)
    sprinkler_pressure = sprinkler.get('pressure', 30)
    
    # Calculate line length based on actual sprinkler count
    line_length = n_sprinklers_per_line * sprinkler_spacing
    
    # Create field visualization with automatic farthest line highlighting
    st.markdown("#### 📍 Design Location - Farthest Sprinkler Line")
    st.caption("The farthest sprinkler line from water source is automatically highlighted in LIME GREEN.")
    
    # Get the current network data from pipe_network_layout (CORRECT KEY)
    network_data = st.session_state.project_data.get('pipe_network_design', {
        'mainlines': [],
        'submains': [],
        'laterals': [],
        'sprinklers': []
    })
    
    # Create the plot using the same function
    drawing_state = {
        'is_drawing': False,
        'mode': None,
        'points': [],
        'enable_snap': False,
        'snap_size': 25.0,
        'show_alignment_guides': False,
        'show_measurements': False,
        'last_snap_point': None,
        'last_snap_type': None
    }
    
    # Generate the plot (includes automatic farthest sprinkler line highlighting)
    fig = create_interactive_plot(field_geometry, operational_data, network_data, drawing_state)
    
    # ADD SIMPLE LIME GREEN HIGHLIGHT - Find the FARTHEST sprinkler line from water source
    # Calculate actual distance from water source, not just highest Y coordinate
    
    water_source_local = field_geometry.get('water_source_local')
    
    # Debug: Show water source location
    if water_source_local:
        log_debug(f"Water source at: X={water_source_local[0]:.1f}m, Y={water_source_local[1]:.1f}m")
    
    # Look through the figure traces and find sprinkler lines + their sprinklers
    sprinkler_lines = []
    sprinkler_markers = []  # To find actual sprinklers (green dots)
    
    for trace in fig.data:
        # Find sprinkler LINE traces (blue lines)
        if trace.name and 'Sprinkler Line' in str(trace.name):
            if hasattr(trace, 'y') and len(trace.y) > 0 and hasattr(trace, 'x'):
                avg_y = sum(trace.y) / len(trace.y)
                avg_x = sum(trace.x) / len(trace.x)
                
                # Calculate DISTANCE from water source (not just Y coordinate!)
                if water_source_local:
                    distance_from_source = sqrt((avg_x - water_source_local[0])**2 + 
                                               (avg_y - water_source_local[1])**2)
                else:
                    # Fallback: use distance from origin
                    distance_from_source = sqrt(avg_x**2 + avg_y**2)
                
                # Calculate actual line length
                if len(trace.x) >= 2:
                    line_length_actual = sqrt((trace.x[-1] - trace.x[0])**2 + (trace.y[-1] - trace.y[0])**2)
                else:
                    line_length_actual = 0
                
                sprinkler_lines.append({
                    'trace': trace,
                    'avg_y': avg_y,
                    'avg_x': avg_x,
                    'distance': distance_from_source,
                    'x': list(trace.x),
                    'y': list(trace.y),
                    'length': line_length_actual,
                    'line_y_min': min(trace.y) if trace.y else 0,
                    'line_y_max': max(trace.y) if trace.y else 0,
                    'line_x_min': min(trace.x) if trace.x else 0,
                    'line_x_max': max(trace.x) if trace.x else 0
                })
        
        # Find AUTO SPRINKLER markers (green dots)
        # Check for both 'Auto Sprinklers' and 'Sprinkler' names
        if trace.name and ('Auto Sprinklers' in str(trace.name) or 'Sprinkler' in str(trace.name)):
            if hasattr(trace, 'x') and hasattr(trace, 'y') and trace.mode and 'markers' in trace.mode:
                for i in range(len(trace.x)):
                    sprinkler_markers.append({
                        'x': trace.x[i],
                        'y': trace.y[i]
                    })
    
    # Debug: Show all lines and their distances
    if sprinkler_lines:
        log_debug(f"Found {len(sprinkler_lines)} sprinkler lines")
        for i, line in enumerate(sorted(sprinkler_lines, key=lambda x: x['distance'], reverse=True)[:5]):
            log_debug(f"  Line {i+1}: Distance={line['distance']:.1f}m, Center=({line['avg_x']:.1f}, {line['avg_y']:.1f}), Length={line['length']:.1f}m")
    
    if sprinkler_lines:
        # Find the line with MAXIMUM DISTANCE from water source (true farthest)
        farthest_line = max(sprinkler_lines, key=lambda x: x['distance'])
        
        # Count sprinklers ON THIS LINE using perpendicular distance from line
        farthest_line_n_sprinklers = 0
        max_distance_from_line = 2.0  # Sprinkler must be within 2m of the line
        
        # Get line endpoints
        line_x1, line_y1 = farthest_line['x'][0], farthest_line['y'][0]
        line_x2, line_y2 = farthest_line['x'][-1], farthest_line['y'][-1]
        line_length = farthest_line['length']
        
        if line_length > 0:
            for sprinkler in sprinkler_markers:
                sx, sy = sprinkler['x'], sprinkler['y']
                
                # Calculate perpendicular distance from point to line
                # Using formula: distance = |ax + by + c| / sqrt(a² + b²)
                # Line equation: (y2-y1)x - (x2-x1)y + x2*y1 - y2*x1 = 0
                numerator = abs((line_y2 - line_y1) * sx - (line_x2 - line_x1) * sy + line_x2 * line_y1 - line_y2 * line_x1)
                denominator = sqrt((line_y2 - line_y1)**2 + (line_x2 - line_x1)**2)
                
                if denominator > 0:
                    distance_to_line = numerator / denominator
                    
                    # Also check if sprinkler is within the line's length range (projection on line)
                    # Calculate projection parameter t
                    dx = line_x2 - line_x1
                    dy = line_y2 - line_y1
                    t = ((sx - line_x1) * dx + (sy - line_y1) * dy) / (dx**2 + dy**2)
                    
                    # Sprinkler must be: close to line AND within line's extent (with small tolerance)
                    if distance_to_line <= max_distance_from_line and -0.05 <= t <= 1.05:
                        farthest_line_n_sprinklers += 1
        
        # Add SEMI-TRANSPARENT LIME GREEN overlay so you can see sprinklers underneath
        fig.add_trace(go.Scatter(
            x=farthest_line['x'],
            y=farthest_line['y'],
            mode='lines+markers',
            line=dict(color='rgba(0, 255, 0, 0.6)', width=12, dash='solid'),  # Semi-transparent lime
            marker=dict(size=18, color='rgba(0, 255, 0, 0.5)', symbol='circle', 
                       line=dict(width=3, color='rgba(255, 255, 255, 0.8)')),
            name='🎯 DESIGN LINE (FARTHEST)',
            hovertemplate='DESIGN SPRINKLER LINE<br>X: %{x:.1f}m<br>Y: %{y:.1f}m<extra></extra>',
            showlegend=True,
            opacity=0.7
        ))
        
        # Store farthest line info for configuration display
        farthest_line_length = farthest_line['length']
        
        st.success(f"✅ Farthest sprinkler line: Distance from source = {farthest_line['distance']:.1f}m, Length = {farthest_line_length:.1f}m, Sprinklers = {farthest_line_n_sprinklers}")
    else:
        st.warning("⚠️ No sprinkler lines found to highlight. Please ensure sprinklers are generated in Operational Design.")
        farthest_line_length = line_length
        farthest_line_n_sprinklers = n_sprinklers_per_line
    
    # Display the plot
    st.plotly_chart(fig, width="stretch", key="sprinkler_overview_map")
    
    # Configuration - SPECIFIC TO FARTHEST LINE (SIMPLIFIED)
    st.markdown("#### ⚙️ Configuration")
    
    # USE DETECTED SPRINKLER COUNT (or allow user override)
    col_a, col_b = st.columns([2, 1])
    with col_a:
        st.caption(f"Auto-detected: {farthest_line_n_sprinklers} sprinklers on farthest line")
    with col_b:
        n_sprinklers_design = st.number_input(
            "Override Sprinkler Count",
            min_value=1,
            max_value=50,
            value=farthest_line_n_sprinklers,
            step=1,
            help="Auto-detected count. Adjust if needed."
        )
    
    # Recalculate line length based on actual sprinkler count and spacing
    line_length_design = n_sprinklers_design * sprinkler_spacing
    
    # Calculate flows specific to this farthest line
    farthest_line_total_flow_m3h = n_sprinklers_design * sprinkler_flow_m3h
    farthest_line_total_flow_lh = n_sprinklers_design * sprinkler_flow_lh
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Sprinklers on Line", f"{n_sprinklers_design}")
        st.metric("Line Length", f"{line_length_design:.1f} m")
        st.metric("Sprinkler Spacing", f"{sprinkler_spacing} m")
    with col2:
        st.metric("Flow per Sprinkler", f"{sprinkler_flow_lh} L/h")
        st.metric("Flow per Sprinkler", f"{sprinkler_flow_m3h:.3f} m³/h")
        st.metric("Line Total Flow", f"{farthest_line_total_flow_lh:.0f} L/h")
    with col3:
        st.metric("Line Total Flow", f"{farthest_line_total_flow_m3h:.2f} m³/h")
        st.caption(f"{n_sprinklers_design} × {sprinkler_flow_m3h:.3f} m³/h")
        st.metric("Operating Pressure", f"{sprinkler_pressure} m")
    
    # Variable pipe sizing
    st.markdown("#### 🔧 Variable Pipe Sizing Design")
    
    # Design mode selection
    design_mode = st.radio(
        "Design Mode",
        ["Automatic (Optimized)", "Manual (Select Each Segment)"],
        help="Automatic mode selects optimal pipe sizes. Manual mode lets you choose diameters for each segment."
    )
    
    # Design parameters
    col1, col2 = st.columns(2)
    with col1:
        max_velocity = st.number_input("Maximum Velocity (m/s)", min_value=0.5, max_value=3.0, value=1.5, step=0.1,
                                       help="Recommended: 1.0-2.0 m/s for PVC pipes")
        C_coefficient = st.number_input("Hazen-Williams C", min_value=100, max_value=150, value=130, step=5,
                                       help="C=130 for PVC, C=120 for PE")
    with col2:
        max_friction_loss_pct = st.number_input("Max Friction Loss (%)", min_value=5.0, max_value=20.0, value=10.0, step=1.0,
                                                help="Friction loss as % of operating pressure")
        min_velocity = st.number_input("Minimum Velocity (m/s)", min_value=0.3, max_value=1.5, value=0.6, step=0.1,
                                      help="Minimum to prevent sediment buildup")
    
    # Show available pipe sizes
    with st.expander("📏 Available Pipe Sizes"):
        pipe_sizes = get_standard_pipe_sizes()
        df_sizes = pd.DataFrame(pipe_sizes)
        df_sizes.columns = ['Nominal Ø (mm)', 'Internal Ø (mm)']
        st.dataframe(df_sizes, width="stretch")
    
    # Calculate variable sizing
    calculate_button = st.button("🔍 Calculate Variable Pipe Sizing", type="primary")
    
    # Initialize session state for manual selections
    if 'manual_pipe_selections' not in st.session_state:
        st.session_state.manual_pipe_selections = {}
    
    # Manual selection interface (show BEFORE calculation if in manual mode)
    if design_mode == "Manual (Select Each Segment)":
        # Check if we have previous design results (use temp if available, else saved)
        if 'temp_sprinkler_line_design' in st.session_state:
            previous_segments = st.session_state.temp_sprinkler_line_design.get('segments', [])
        elif 'sprinkler_line_design' in st.session_state.project_data:
            previous_segments = st.session_state.project_data['sprinkler_line_design'].get('segments', [])
        else:
            previous_segments = []
        
        # Check if previous segments match current sprinkler count
        if previous_segments and len(previous_segments) == n_sprinklers_design:
            st.markdown("---")
            st.markdown("#### 🎛️ Manual Pipe Selection")
            st.caption("Select pipe diameter for each segment, then click 'Calculate' to update.")
            
            pipe_sizes = get_standard_pipe_sizes()
            
            # Create columns for segment selection
            n_cols_display = min(5, n_sprinklers_design)
            cols = st.columns(n_cols_display)
            
            for i, seg in enumerate(previous_segments):
                col_idx = i % n_cols_display
                with cols[col_idx]:
                    segment_key = f"seg_{seg['segment']}"
                    
                    # Create pipe size options
                    pipe_options = [f"Ø{s['nominal']} mm" for s in pipe_sizes]
                    current_idx = next((idx for idx, s in enumerate(pipe_sizes) 
                                      if s['nominal'] == seg['pipe_nominal_mm']), 0)
                    
                    # Initialize if not set
                    if segment_key not in st.session_state.manual_pipe_selections:
                        st.session_state.manual_pipe_selections[segment_key] = current_idx
                    
                    # Display segment info with compact formatting
                    st.markdown(f"**Seg {seg['segment']}**")
                    st.caption(f"{seg['position']}")
                    st.caption(f"Q: {seg['flow_m3h']} m³/h")
                    if 'velocity_ms' in seg:
                        st.caption(f"V: {seg['velocity_ms']} m/s")
                    
                    # Pipe selector
                    selected_idx = st.selectbox(
                        "Pipe Size",
                        range(len(pipe_sizes)),
                        index=st.session_state.manual_pipe_selections[segment_key],
                        format_func=lambda x: pipe_options[x],
                        key=f"select_{segment_key}",
                        label_visibility="collapsed"
                    )
                    
                    st.session_state.manual_pipe_selections[segment_key] = selected_idx
            
            st.markdown("---")
            
            # Save button for manual selections
            col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
            with col_save2:
                if st.button("💾 Save Pipe Selections", type="secondary", width="stretch", key="save_manual_sprinkler"):
                    st.success("✅ Pipe selections saved! Click 'Calculate' to update the design.")
    
    # Check if we should show results (either just calculated OR previously saved/temp data exists)
    show_results = calculate_button or 'temp_sprinkler_line_design' in st.session_state
    
    if calculate_button:
        
        segments = []
        pipe_sizes = get_standard_pipe_sizes()
        
        # CORRECTED FLOW LOGIC: Design from FARTHEST sprinkler back to INLET
        # Segment 1 = farthest sprinkler (lowest flow), Segment n = inlet (highest flow)
        # Use the ACTUAL sprinkler count from the detected/configured line
        for i in range(n_sprinklers_design):
            # Segment number: 1 = farthest, n = inlet
            segment_num = i + 1
            
            # Number of sprinklers served by this segment
            # Segment 1 (farthest) serves 1 sprinkler, Segment n (inlet) serves all sprinklers
            n_downstream_sprinklers = segment_num
            
            # Flow in this segment = number of sprinklers served × individual sprinkler flow
            segment_flow_m3h = n_downstream_sprinklers * sprinkler_flow_m3h
            segment_flow_lps = segment_flow_m3h * 1000 / 3600
            
            segment_length = sprinkler_spacing
            
            # Automatic or Manual pipe selection
            if design_mode == "Manual (Select Each Segment)":
                # User selects pipe size for this segment
                segment_key = f"seg_{segment_num}"
                
                # Find optimal size as default
                optimal_size = None
                for size in pipe_sizes:
                    D_mm = size['internal']
                    D_m = D_mm / 1000
                    Q_m3s = segment_flow_m3h / 3600
                    area = 3.14159 * (D_m / 2) ** 2
                    velocity = Q_m3s / area if area > 0 else 999
                    
                    if min_velocity <= velocity <= max_velocity:
                        optimal_size = size
                        break
                
                if optimal_size is None:
                    optimal_size = pipe_sizes[0]  # Default to smallest
                
                # Get default index
                default_idx = next((idx for idx, s in enumerate(pipe_sizes) if s['nominal'] == optimal_size['nominal']), 0)
                
                if segment_key not in st.session_state.manual_pipe_selections:
                    st.session_state.manual_pipe_selections[segment_key] = default_idx
                
                selected_idx = st.session_state.manual_pipe_selections[segment_key]
                selected_size = pipe_sizes[selected_idx]
            
            else:
                # Automatic selection - TELESCOPING ALGORITHM
                # Find the SMALLEST pipe that keeps velocity <= max_velocity
                # No monotonic constraint - pipes should GET SMALLER as flow decreases
                
                selected_size = None
                
                # Try each pipe size from SMALLEST to LARGEST
                for size in pipe_sizes:
                    D_mm = size['internal']
                    D_m = D_mm / 1000
                    
                    # Calculate velocity for this segment's actual flow
                    Q_m3s = segment_flow_m3h / 3600
                    area = 3.14159 * (D_m / 2) ** 2
                    velocity = Q_m3s / area if area > 0 else 0
                    
                    # Check if velocity is within acceptable range
                    # Primary constraint: velocity <= max_velocity
                    if velocity <= max_velocity:
                        # Found a valid pipe - check if velocity is too low
                        if velocity >= min_velocity:
                            # Perfect - velocity is in the ideal range
                            selected_size = size
                            break
                        else:
                            # Velocity is below minimum, but we accept it since we can't go smaller
                            # This is just a warning condition, not a failure
                            selected_size = size
                            break
                
                # Fallback: if even the largest pipe exceeds max_velocity (very high flow)
                # Use the largest available pipe
                if selected_size is None:
                    selected_size = pipe_sizes[-1]
            
            # Calculate friction loss for this segment (using Hazen-Williams with F-factor)
            # Apply Christiansen F-factor for multiple outlets
            F = calculate_f_factor(n_downstream_sprinklers)
            effective_flow = segment_flow_m3h * F
            
            hf_segment = calculate_hazen_williams(effective_flow, selected_size['internal'], segment_length, C_coefficient)
            
            # Calculate velocity
            D_m = selected_size['internal'] / 1000
            Q_m3s = segment_flow_m3h / 3600
            area = 3.14159 * (D_m / 2) ** 2
            velocity = Q_m3s / area if area > 0 else 0
            
            # Determine position (distance from inlet)
            # Segment 1 is farthest from inlet, segment n is at inlet
            distance_from_inlet = (n_sprinklers_design - segment_num) * sprinkler_spacing
            
            # Position description: show sprinkler numbers correctly
            # Segment 1: Spr 5 → Spr 6 (farthest)
            # Segment 6: Inlet → Spr 1 (at inlet)
            if segment_num == n_sprinklers_design:
                position = f"Inlet → Spr 1"
            else:
                from_spr = n_sprinklers_design - segment_num
                to_spr = from_spr + 1
                position = f"Spr {from_spr} → Spr {to_spr}"
            
            segments.append({
                'segment': segment_num,
                'position': position,
                'distance_from_inlet_m': distance_from_inlet,
                'length_m': segment_length,
                'n_downstream_sprinklers': n_downstream_sprinklers,
                'flow_m3h': round(segment_flow_m3h, 3),
                'flow_lps': round(segment_flow_lps, 2),
                'effective_flow_m3h': round(effective_flow, 3),
                'pipe_nominal_mm': selected_size['nominal'],
                'pipe_internal_mm': selected_size['internal'],
                'velocity_ms': round(velocity, 2),
                'friction_loss_m': round(hf_segment, 4),
                'F_factor': round(F, 4)
            })
        
        # Total friction loss
        total_friction_loss = sum(seg['friction_loss_m'] for seg in segments)
        friction_loss_pct = (total_friction_loss / sprinkler_pressure) * 100 if sprinkler_pressure > 0 else 0
        
        # Velocity check
        max_velocity_observed = max(seg['velocity_ms'] for seg in segments) if segments else 0
        min_velocity_observed = min(seg['velocity_ms'] for seg in segments) if segments else 0
        
        # Check if design meets criteria
        velocity_ok = min_velocity <= min_velocity_observed and max_velocity_observed <= max_velocity
        friction_ok = friction_loss_pct <= max_friction_loss_pct
        
        # Save results (temporarily in session state, needs explicit save)
        st.session_state.temp_sprinkler_line_design = {
            'segments': segments,
            'total_length_m': line_length_design,
            'n_sprinklers': n_sprinklers_design,
            'total_flow_m3h': round(n_sprinklers_design * sprinkler_flow_m3h, 3),
            'total_friction_loss_m': round(total_friction_loss, 4),
            'friction_loss_pct': round(friction_loss_pct, 2),
            'max_velocity_ms': max_velocity,
            'min_velocity_ms': min_velocity,
            'max_velocity_observed': round(max_velocity_observed, 2),
            'min_velocity_observed': round(min_velocity_observed, 2),
            'C_coefficient': C_coefficient,
            'design_mode': design_mode,
            'sprinkler_spacing': sprinkler_spacing
        }
    
    # DISPLAY RESULTS SECTION - Show if just calculated OR if temp data exists
    if show_results and 'temp_sprinkler_line_design' in st.session_state:
        # Load data from temp state
        design_data = st.session_state.temp_sprinkler_line_design
        segments = design_data['segments']
        total_friction_loss = design_data['total_friction_loss_m']
        friction_loss_pct = design_data['friction_loss_pct']
        max_velocity_observed = design_data['max_velocity_observed']
        min_velocity_observed = design_data['min_velocity_observed']
        max_velocity = design_data['max_velocity_ms']
        min_velocity = design_data['min_velocity_ms']
        line_length_design = design_data['total_length_m']
        n_sprinklers_design = design_data['n_sprinklers']
        sprinkler_spacing = design_data['sprinkler_spacing']
        C_coefficient = design_data['C_coefficient']
        design_mode = design_data['design_mode']
        
        # Check if design meets criteria
        velocity_ok = min_velocity <= min_velocity_observed and max_velocity_observed <= max_velocity
        friction_ok = friction_loss_pct <= max_friction_loss_pct
        
        # Display results with status indicators
        status_col1, status_col2, status_col3, status_col4 = st.columns([2, 2, 2, 1])
        with status_col1:
            if friction_ok:
                st.success(f"✅ Friction Loss: {total_friction_loss:.3f} m ({friction_loss_pct:.1f}%)")
            else:
                st.error(f"⚠️ Friction Loss: {total_friction_loss:.3f} m ({friction_loss_pct:.1f}%) - EXCEEDS LIMIT")
        
        with status_col2:
            if velocity_ok:
                st.success(f"✅ Velocity: {min_velocity_observed:.2f} - {max_velocity_observed:.2f} m/s")
            else:
                st.warning(f"⚠️ Velocity: {min_velocity_observed:.2f} - {max_velocity_observed:.2f} m/s - CHECK LIMITS")
        
        with status_col3:
            if friction_ok and velocity_ok:
                st.success("✅ Design OK")
            else:
                st.warning("⚠️ Design needs adjustment")
        
        with status_col4:
            # SAVE BUTTON
            if st.button("💾 Save", type="primary", width="stretch"):
                st.session_state.project_data['sprinkler_line_design'] = st.session_state.temp_sprinkler_line_design.copy()
                st.success("✅ Sprinkler Line Design Saved Successfully!")
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Visual Diagram", 
            "📈 Performance Analysis", 
            "📋 Detailed Table",
            "💡 Advisory"
        ])
        
        with tab1:
            st.markdown("##### Sprinkler Line - Variable Pipe Sizing Diagram")
            fig_diagram = create_sprinkler_line_diagram(segments, sprinkler_spacing)
            st.plotly_chart(fig_diagram, width="stretch", key="sprinkler_line_diagram")
            
            # Flow distribution chart
            st.markdown("##### Flow Distribution Along Line")
            fig_flow = create_flow_distribution_chart(segments)
            st.plotly_chart(fig_flow, width="stretch", key="sprinkler_flow_dist")
        
        with tab2:
            fig_perf = create_performance_charts(segments)
            st.plotly_chart(fig_perf, width="stretch", key="sprinkler_perf")
        
        with tab3:
            st.markdown("##### Detailed Segment Information")
            df = pd.DataFrame(segments)
            
            # Reorder and rename columns for better display
            display_columns = {
                'segment': 'Seg #',
                'position': 'Position',
                'distance_from_inlet_m': 'Distance (m)',
                'n_downstream_sprinklers': '# Downstream Spr',
                'flow_m3h': 'Flow (m³/h)',
                'flow_lps': 'Flow (L/s)',
                'pipe_nominal_mm': 'Pipe Ø (mm)',
                'velocity_ms': 'Velocity (m/s)',
                'friction_loss_m': 'Friction Loss (m)',
                'F_factor': 'F-Factor'
            }
            
            df_display = df[list(display_columns.keys())].copy()
            df_display.columns = list(display_columns.values())
            
            # Color code based on velocity
            def highlight_velocity(row):
                vel = row['Velocity (m/s)']
                if vel < min_velocity:
                    return ['background-color: #fff3cd'] * len(row)  # Yellow
                elif vel > max_velocity:
                    return ['background-color: #f8d7da'] * len(row)  # Red
                else:
                    return ['background-color: #d4edda'] * len(row)  # Green
            
            # Format numeric columns to max 2 decimal places
            format_dict = {col: '{:.2f}' for col in df_display.select_dtypes(include=['float64', 'float32', 'number']).columns}
            
            st.dataframe(
                df_display.style.apply(highlight_velocity, axis=1).format(format_dict),
                width="stretch",
                height=400
            )
            
            # Summary metrics
            st.markdown("##### Summary")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Length", f"{line_length_design:.1f} m")
            with col2:
                st.metric("Total Flow", f"{n_sprinklers_design * sprinkler_flow_m3h:.2f} m³/h")
            with col3:
                st.metric("Friction Loss", f"{total_friction_loss:.3f} m")
            with col4:
                st.metric("Velocity Range", f"{min_velocity_observed:.2f}-{max_velocity_observed:.2f} m/s")
            with col5:
                unique_sizes = len(set(seg['pipe_nominal_mm'] for seg in segments))
                st.metric("Pipe Sizes Used", f"{unique_sizes}")
        
        with tab4:
            st.markdown("##### 💡 Design Advisory")
            
            # Provide recommendations
            advisories = []
            
            # Check friction loss
            if friction_loss_pct > max_friction_loss_pct:
                advisories.append({
                    'type': 'error',
                    'message': f"❌ **Friction Loss Exceeded**: {friction_loss_pct:.1f}% > {max_friction_loss_pct}%",
                    'recommendation': "Consider using larger pipe diameters for high-flow segments (closer to inlet)."
                })
            elif friction_loss_pct > max_friction_loss_pct * 0.8:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Friction Loss High**: {friction_loss_pct:.1f}% (limit: {max_friction_loss_pct}%)",
                    'recommendation': "Design is near the limit. Consider slight diameter increase for safety margin."
                })
            else:
                advisories.append({
                    'type': 'success',
                    'message': f"✅ **Friction Loss OK**: {friction_loss_pct:.1f}% (limit: {max_friction_loss_pct}%)",
                    'recommendation': "Friction loss is within acceptable range."
                })
            
            # Check velocities
            if max_velocity_observed > max_velocity:
                advisories.append({
                    'type': 'error',
                    'message': f"❌ **Velocity Too High**: {max_velocity_observed:.2f} m/s > {max_velocity} m/s",
                    'recommendation': "Increase pipe diameter for high-velocity segments to prevent erosion and noise."
                })
            
            if min_velocity_observed < min_velocity:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Velocity Too Low**: {min_velocity_observed:.2f} m/s < {min_velocity} m/s",
                    'recommendation': "Low velocities may allow sediment buildup. Consider smaller diameter for low-flow segments."
                })
            
            if velocity_ok:
                advisories.append({
                    'type': 'success',
                    'message': f"✅ **Velocities OK**: {min_velocity_observed:.2f} - {max_velocity_observed:.2f} m/s",
                    'recommendation': "All velocities are within recommended range."
                })
            
            # Optimization suggestions
            unique_sizes = set(seg['pipe_nominal_mm'] for seg in segments)
            if len(unique_sizes) > 3:
                advisories.append({
                    'type': 'info',
                    'message': f"ℹ️ **Multiple Pipe Sizes**: Using {len(unique_sizes)} different diameters",
                    'recommendation': "Consider if reducing the number of different pipe sizes would simplify procurement and installation."
                })
            
            # Display advisories
            for adv in advisories:
                if adv['type'] == 'error':
                    st.error(adv['message'])
                elif adv['type'] == 'warning':
                    st.warning(adv['message'])
                elif adv['type'] == 'success':
                    st.success(adv['message'])
                else:
                    st.info(adv['message'])
                
                st.markdown(f"**Recommendation:** {adv['recommendation']}")
                st.markdown("---")
            
            # Optimal pipe size suggestion
            st.markdown("##### 🎯 Suggested Optimal Combinations")
            
            # Group consecutive segments with same diameter
            pipe_groups = []
            current_group = {'diameter': segments[0]['pipe_nominal_mm'], 'start': 1, 'end': 1, 'length': segments[0]['length_m']}
            
            for i in range(1, len(segments)):
                if segments[i]['pipe_nominal_mm'] == current_group['diameter']:
                    current_group['end'] = segments[i]['segment']
                    current_group['length'] += segments[i]['length_m']
                else:
                    pipe_groups.append(current_group)
                    current_group = {
                        'diameter': segments[i]['pipe_nominal_mm'], 
                        'start': segments[i]['segment'], 
                        'end': segments[i]['segment'],
                        'length': segments[i]['length_m']
                    }
            pipe_groups.append(current_group)
            
            st.markdown("**Current Design Summary:**")
            for group in pipe_groups:
                if group['start'] == group['end']:
                    st.markdown(f"- **Ø{group['diameter']} mm**: Segment {group['start']} ({group['length']:.1f} m)")
                else:
                    st.markdown(f"- **Ø{group['diameter']} mm**: Segments {group['start']}-{group['end']} ({group['length']:.1f} m)")
            
            st.markdown("**Material List:**")
            for group in pipe_groups:
                st.markdown(f"- Ø{group['diameter']} mm PVC pipe: {group['length']:.1f} m")


def create_sprinkler_line_diagram(segments, spacing):
    """Create visual diagram of sprinkler line with variable pipe sizing"""
    
    if not segments:
        return go.Figure()
    
    fig = go.Figure()
    
    # Get unique pipe sizes and assign colors
    unique_sizes = sorted(list(set(seg['pipe_nominal_mm'] for seg in segments)))
    colors = ['#3498db', '#e74c3c', '#2ecc71', '#f39c12', '#9b59b6', '#1abc9c', '#e67e22', '#34495e']
    size_colors = {size: colors[i % len(colors)] for i, size in enumerate(unique_sizes)}
    
    # REVERSE segments for drawing: Draw from INLET (left) to FARTHEST (right)
    # Segment array: [Seg1=farthest, Seg2, ..., SegN=inlet]
    # Drawing order: [SegN=inlet, ..., Seg2, Seg1=farthest]
    segments_reversed = list(reversed(segments))
    
    # Draw pipe segments from INLET (left, x=0) to FARTHEST SPRINKLER (right)
    x_pos = 0
    
    for i, seg in enumerate(segments_reversed):
        x_end = x_pos + seg['length_m']
        
        # Pipe segment - line width proportional to pipe diameter
        # Scale: 20mm pipe = 8 width, 315mm pipe = 55 width (linear scaling)
        line_width = 5 + (seg['pipe_nominal_mm'] / 6)  # Better visual scaling
        
        # Check if this is first occurrence of this pipe size for legend
        is_first_of_size = True
        for j in range(i):
            if segments_reversed[j]['pipe_nominal_mm'] == seg['pipe_nominal_mm']:
                is_first_of_size = False
                break
        
        fig.add_trace(go.Scatter(
            x=[x_pos, x_end],
            y=[0, 0],
            mode='lines',
            line=dict(
                color=size_colors[seg['pipe_nominal_mm']],
                width=line_width
            ),
            name=f"Ø{seg['pipe_nominal_mm']} mm",
            showlegend=is_first_of_size,
            hovertext=f"<b>Segment {seg['segment']}</b><br>" +
                     f"{seg['position']}<br>" +
                     f"Pipe: Ø{seg['pipe_nominal_mm']} mm (ID: {seg['pipe_internal_mm']} mm)<br>" +
                     f"Flow: {seg['flow_m3h']:.2f} m³/h ({seg['flow_lps']:.2f} L/s)<br>" +
                     f"Downstream Sprinklers: {seg['n_downstream_sprinklers']}<br>" +
                     f"Velocity: {seg['velocity_ms']:.2f} m/s<br>" +
                     f"Friction Loss: {seg['friction_loss_m']:.4f} m",
            hoverinfo='text'
        ))
        
        # Sprinkler marker at end of segment
        # Only draw if this is not the last segment (inlet doesn't have sprinkler at start)
        if i < len(segments_reversed) - 1:
            fig.add_trace(go.Scatter(
                x=[x_end],
                y=[0],
                mode='markers+text',
                marker=dict(size=14, color='darkblue', symbol='diamond', line=dict(width=2, color='white')),
                text=[f"{len(segments) - i}"],  # Sprinkler number from inlet
                textposition="top center",
                textfont=dict(size=10, color='darkblue', family='Arial Black'),
                showlegend=False,
                hovertext=f"<b>Sprinkler {len(segments) - i}</b><br>" +
                         f"Individual Flow: {seg['flow_m3h'] / max(seg['n_downstream_sprinklers'], 1):.2f} m³/h<br>" +
                         f"Position: {x_end:.1f} m from inlet",
                hoverinfo='text'
            ))
        
        # Add flow label above each segment
        fig.add_trace(go.Scatter(
            x=[(x_pos + x_end) / 2],
            y=[0.5],
            mode='text',
            text=[f"{seg['flow_m3h']:.1f} m³/h"],
            textposition="middle center",
            textfont=dict(size=9, color=size_colors[seg['pipe_nominal_mm']]),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        x_pos = x_end
    
    # Add farthest sprinkler marker at the end
    fig.add_trace(go.Scatter(
        x=[x_pos],
        y=[0],
        mode='markers+text',
        marker=dict(size=14, color='navy', symbol='diamond', line=dict(width=2, color='white')),
        text=["FARTHEST"],
        textposition="top center",
        textfont=dict(size=10, color='navy', family='Arial Black'),
        showlegend=False,
        hovertext=f"<b>Farthest Sprinkler</b><br>Flow: {segments[0]['flow_m3h']:.2f} m³/h",
        hoverinfo='text'
    ))
    
    # Add inlet marker at start
    fig.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode='markers+text',
        marker=dict(size=18, color='red', symbol='square'),
        text=["INLET"],
        textposition="bottom center",
        textfont=dict(size=11, color='red', family='Arial Black'),
        showlegend=False,
        hovertext="<b>Lateral Inlet</b><br>Total Line Flow: " + 
                 f"{segments[-1]['flow_m3h']:.2f} m³/h",
        hoverinfo='text'
    ))
    
    fig.update_layout(
        title="Sprinkler Line - Variable Pipe Sizing (Inlet → Farthest Sprinkler)",
        xaxis_title="Distance from Inlet (m)",
        yaxis_title="",
        height=350,
        showlegend=True,
        yaxis=dict(visible=False, range=[-1, 2]),
        hovermode='closest',
        plot_bgcolor='rgba(240, 240, 240, 0.5)'
    )
    
    return fig


def create_flow_distribution_chart(segments):
    """Create chart showing flow distribution along the line"""
    
    if not segments:
        return go.Figure()
    
    fig = go.Figure()
    
    # Prepare data - handle missing fields for backward compatibility
    positions = [seg.get('distance_from_inlet_m', i * seg.get('length_m', 0)) for i, seg in enumerate(segments)]
    flows = [seg['flow_m3h'] for seg in segments]
    
    # Check if this is sprinkler line data (has n_downstream_sprinklers) or lateral data (has n_lines_downstream)
    if 'n_downstream_sprinklers' in segments[0]:
        # Sprinkler line data
        n_downstream = [seg['n_downstream_sprinklers'] for seg in segments]
        downstream_label = 'Downstream Sprinklers'
        title = "Flow Distribution: Decreasing Flow from Inlet to Farthest Sprinkler"
    elif 'n_lines_downstream' in segments[0]:
        # Lateral line data
        n_downstream = [seg['n_lines_downstream'] for seg in segments]
        downstream_label = 'Downstream Lines'
        title = "Flow Distribution: Decreasing Flow from Inlet to Farthest Sprinkler Line"
    else:
        # Fallback for old data
        n_downstream = [seg['segment'] for seg in segments]
        downstream_label = 'Segment Number'
        title = "Flow Distribution Along Line"
    
    # Flow bar chart
    fig.add_trace(go.Bar(
        x=positions,
        y=flows,
        name='Segment Flow',
        marker=dict(
            color=flows,
            colorscale='Blues',
            showscale=True,
            colorbar=dict(title="Flow (m³/h)")
        ),
        hovertext=[f"<b>Segment {seg['segment']}</b><br>" +
                  f"Position: {seg.get('distance_from_inlet_m', i * seg.get('length_m', 0)):.1f} m<br>" +
                  f"Flow: {seg['flow_m3h']:.2f} m³/h" +
                  (f"<br>Downstream Sprinklers: {seg['n_downstream_sprinklers']}" if 'n_downstream_sprinklers' in seg else 
                   f"<br>Downstream Lines: {seg['n_lines_downstream']}" if 'n_lines_downstream' in seg else "")
                  for i, seg in enumerate(segments)],
        hoverinfo='text'
    ))
    
    # Add line showing number of downstream outlets
    fig.add_trace(go.Scatter(
        x=positions,
        y=n_downstream,
        name=f'# {downstream_label}',
        yaxis='y2',
        mode='lines+markers',
        line=dict(color='orange', width=3, dash='dash'),
        marker=dict(size=10, color='orange')
    ))
    
    fig.update_layout(
        title=title,
        xaxis_title="Distance from Inlet (m)",
        yaxis_title="Segment Flow (m³/h)",
        yaxis2=dict(
            title=f"Number of {downstream_label}",
            overlaying='y',
            side='right'
        ),
        height=400,
        hovermode='x unified',
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(255, 255, 255, 0.9)",
            bordercolor="gray",
            borderwidth=1
        )
    )
    
    return fig


def create_performance_charts(segments):
    """Create performance analysis charts for velocity and pressure"""
    
    if not segments:
        return go.Figure()
    
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=1,
        subplot_titles=(
            "Velocity Distribution Along Line", 
            "Cumulative Friction Loss",
            "Pipe Diameter Changes"
        ),
        vertical_spacing=0.12,
        specs=[[{"secondary_y": False}],
               [{"secondary_y": False}],
               [{"secondary_y": True}]]
    )
    
    # Prepare data - handle missing fields for backward compatibility
    distances = [seg.get('distance_from_inlet_m', i * seg.get('length_m', 0)) for i, seg in enumerate(segments)]
    velocities = [seg['velocity_ms'] for seg in segments]
    diameters = [seg['pipe_nominal_mm'] for seg in segments]
    flows = [seg['flow_m3h'] for seg in segments]
    
    # 1. Velocity chart
    fig.add_trace(
        go.Scatter(
            x=distances,
            y=velocities,
            mode='lines+markers',
            name='Velocity',
            line=dict(color='blue', width=3),
            marker=dict(size=8),
            hovertext=[f"Segment {seg['segment']}<br>Velocity: {seg['velocity_ms']:.2f} m/s<br>Flow: {seg['flow_m3h']:.2f} m³/h" 
                      for seg in segments],
            hoverinfo='text'
        ),
        row=1, col=1
    )
    
    # 2. Friction loss chart
    cumulative_loss = []
    total = 0
    for seg in segments:
        total += seg['friction_loss_m']
        cumulative_loss.append(total)
    
    fig.add_trace(
        go.Scatter(
            x=distances,
            y=cumulative_loss,
            mode='lines+markers',
            name='Cumulative Friction Loss',
            line=dict(color='red', width=3),
            marker=dict(size=8),
            fill='tozeroy',
            fillcolor='rgba(255,0,0,0.1)',
            hovertext=[f"Position: {d:.1f} m<br>Cumulative Loss: {cumulative_loss[i]:.4f} m" 
                      for i, d in enumerate(distances)],
            hoverinfo='text'
        ),
        row=2, col=1
    )
    
    # 3. Pipe diameter chart with flow overlay
    fig.add_trace(
        go.Scatter(
            x=distances,
            y=diameters,
            mode='lines+markers',
            name='Pipe Diameter',
            line=dict(color='green', width=3, shape='hv'),  # Step function
            marker=dict(size=10, color='green'),
            hovertext=[f"Segment {seg['segment']}<br>Pipe: Ø{seg['pipe_nominal_mm']} mm" 
                      for seg in segments],
            hoverinfo='text'
        ),
        row=3, col=1
    )
    
    # Add flow on secondary y-axis
    fig.add_trace(
        go.Scatter(
            x=distances,
            y=flows,
            mode='lines+markers',
            name='Flow',
            line=dict(color='orange', width=2, dash='dash'),
            marker=dict(size=6, color='orange'),
            hovertext=[f"Segment {seg['segment']}<br>Flow: {seg['flow_m3h']:.2f} m³/h" 
                      for seg in segments],
            hoverinfo='text'
        ),
        row=3, col=1,
        secondary_y=True
    )
    
    # Update axes
    fig.update_xaxes(title_text="Distance from Inlet (m)", row=3, col=1)
    fig.update_yaxes(title_text="Velocity (m/s)", row=1, col=1)
    fig.update_yaxes(title_text="Friction Loss (m)", row=2, col=1)
    fig.update_yaxes(title_text="Pipe Diameter (mm)", row=3, col=1)
    fig.update_yaxes(title_text="Flow (m³/h)", row=3, col=1, secondary_y=True)
    
    fig.update_layout(
        height=900, 
        showlegend=True,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    return fig


def show_lateral_design():
    """Design lateral line using SELECTED lateral from Pipe Network Layout"""
    st.markdown('<h2 class="sub-header">Lateral Line Design</h2>', unsafe_allow_html=True)
    
    # ============================================================================
    # SECTION 1: DESIGN LOCATION - LATERAL LINE VISUALIZATION
    # ============================================================================
    with st.expander("ℹ️ About Lateral Design", expanded=False):
        st.markdown("""
        Select a lateral line to design. Laterals connect multiple sprinkler lines and deliver water from the submain.
        """)
    
    # Measurement Tool
    col_meas1, col_meas2, col_meas3 = st.columns([2, 2, 3])
    with col_meas1:
        if st.button("📏 Measure Distance", key="measure_tool_lateral", help="Activate measurement on the map below"):
            drawing_state = st.session_state.get('drawing_state', {})
            drawing_state['mode'] = 'Measure'
            drawing_state['is_drawing'] = True
            drawing_state['points'] = []
            st.session_state.drawing_state = drawing_state
            if 'measurement' not in st.session_state:
                st.session_state.measurement = None
            st.rerun()
    
    with col_meas2:
        if st.button("❌ Clear Measurement", key="clear_measure_lateral"):
            if 'measurement' in st.session_state:
                st.session_state.measurement = None
            st.rerun()
    
    with col_meas3:
        if 'measurement' in st.session_state and st.session_state.measurement:
            meas = st.session_state.measurement
            st.success(f"📏 **{meas['distance']:.2f} m** | From ({meas['point1'][0]:.1f}, {meas['point1'][1]:.1f}) to ({meas['point2'][0]:.1f}, {meas['point2'][1]:.1f})")
    
    # Get necessary data
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    operational_data = st.session_state.project_data.get('operational_data', {})
    pipe_network_design = st.session_state.project_data.get('pipe_network_design', {})
    
    # Initialize drawing_state with required keys if not present
    drawing_state = st.session_state.get('drawing_state', {})
    if 'is_drawing' not in drawing_state:
        drawing_state = {
            'is_drawing': False,
            'mode': None,
            'points': []
        }
    
    # Create the full field map
    from modules.pipe_network_layout import create_interactive_plot
    fig = create_interactive_plot(field_geometry, operational_data, pipe_network_design, drawing_state)
    
    if fig is None:
        st.warning("⚠️ No field geometry available. Please complete System Layout first.")
        return
    
    # Extract lateral lines from the plot
    lateral_lines = []
    water_source_local = field_geometry.get('water_source_local', [0, 0])
    
    for trace in fig.data:
        # Detect lateral lines (check for name containing 'Lateral')
        if trace.name and 'Lateral' in str(trace.name):
            if hasattr(trace, 'x') and hasattr(trace, 'y') and len(trace.x) >= 2:
                # Calculate lateral length
                lateral_length = 0
                for i in range(len(trace.x) - 1):
                    dx = trace.x[i+1] - trace.x[i]
                    dy = trace.y[i+1] - trace.y[i]
                    lateral_length += sqrt(dx**2 + dy**2)
                
                # Calculate average position (for distance calculation)
                avg_x = sum(trace.x) / len(trace.x)
                avg_y = sum(trace.y) / len(trace.y)
                
                # Calculate distance from water source
                distance_from_source = sqrt((avg_x - water_source_local[0])**2 + (avg_y - water_source_local[1])**2)
                
                lateral_lines.append({
                    'x': list(trace.x),
                    'y': list(trace.y),
                    'length': lateral_length,
                    'distance_from_source': distance_from_source,
                    'avg_x': avg_x,
                    'avg_y': avg_y
                })
    
    if not lateral_lines:
        st.warning("⚠️ No lateral lines detected. Please draw laterals in Pipe Network Layout first.")
        st.stop()
    
    # Find farthest lateral (for default selection)
    farthest_lateral = max(lateral_lines, key=lambda x: x['distance_from_source'])
    
    # Count sprinkler lines that intersect this lateral AND count total sprinklers
    # Use perpendicular distance method to check if sprinkler line crosses lateral
    sprinkler_lines_on_lateral = 0
    sprinkler_line_traces = []
    total_sprinklers_on_lateral = 0  # Count actual sprinklers
    
    for trace in fig.data:
        if trace.name and 'Sprinkler Line' in str(trace.name):
            if hasattr(trace, 'x') and hasattr(trace, 'y') and len(trace.x) >= 2:
                spr_x1, spr_y1 = trace.x[0], trace.y[0]
                spr_x2, spr_y2 = trace.x[-1], trace.y[-1]
                
                # Check if sprinkler line intersects with lateral line
                # For each segment of the lateral
                intersects = False
                for i in range(len(farthest_lateral['x']) - 1):
                    lat_x1 = farthest_lateral['x'][i]
                    lat_y1 = farthest_lateral['y'][i]
                    lat_x2 = farthest_lateral['x'][i+1]
                    lat_y2 = farthest_lateral['y'][i+1]
                    
                    # Calculate if sprinkler line endpoints are close to this lateral segment
                    # Use perpendicular distance from points to line segment
                    lat_length = sqrt((lat_x2 - lat_x1)**2 + (lat_y2 - lat_y1)**2)
                    
                    if lat_length > 0:
                        # Check first endpoint of sprinkler line
                        numerator1 = abs((lat_y2 - lat_y1) * spr_x1 - (lat_x2 - lat_x1) * spr_y1 + lat_x2 * lat_y1 - lat_y2 * lat_x1)
                        dist1 = numerator1 / lat_length
                        
                        # Check second endpoint of sprinkler line  
                        numerator2 = abs((lat_y2 - lat_y1) * spr_x2 - (lat_x2 - lat_x1) * spr_y2 + lat_x2 * lat_y1 - lat_y2 * lat_x1)
                        dist2 = numerator2 / lat_length
                        
                        # Calculate projection parameter to ensure point is within segment bounds
                        dx = lat_x2 - lat_x1
                        dy = lat_y2 - lat_y1
                        t1 = ((spr_x1 - lat_x1) * dx + (spr_y1 - lat_y1) * dy) / (dx**2 + dy**2)
                        t2 = ((spr_x2 - lat_x1) * dx + (spr_y2 - lat_y1) * dy) / (dx**2 + dy**2)
                        
                        # If either endpoint is close to lateral AND within segment bounds
                        if (dist1 < 3.0 and -0.1 <= t1 <= 1.1) or (dist2 < 3.0 and -0.1 <= t2 <= 1.1):
                            intersects = True
                            break
                
                if intersects:
                    sprinkler_lines_on_lateral += 1
                    sprinkler_line_traces.append({
                        'x': [spr_x1, spr_x2],
                        'y': [spr_y1, spr_y2]
                    })
    
    # Now count actual sprinklers on these sprinkler lines
    for trace in fig.data:
        # Look for sprinkler markers (green dots)
        if trace.name and ('Sprinkler' in str(trace.name) or 'Auto Sprinklers' in str(trace.name)):
            if hasattr(trace, 'x') and hasattr(trace, 'y') and trace.mode and 'markers' in trace.mode:
                # For each sprinkler marker, check if it's on one of our sprinkler lines
                for i in range(len(trace.x)):
                    sx, sy = trace.x[i], trace.y[i]
                    
                    # Check against each sprinkler line that connects to lateral
                    for spr_line in sprinkler_line_traces:
                        line_x1, line_y1 = spr_line['x'][0], spr_line['y'][0]
                        line_x2, line_y2 = spr_line['x'][1], spr_line['y'][1]
                        
                        line_length = sqrt((line_x2 - line_x1)**2 + (line_y2 - line_y1)**2)
                        
                        if line_length > 0:
                            # Calculate perpendicular distance from sprinkler to line
                            numerator = abs((line_y2 - line_y1) * sx - (line_x2 - line_x1) * sy + line_x2 * line_y1 - line_y2 * line_x1)
                            distance_to_line = numerator / line_length
                            
                            # Calculate projection parameter
                            dx = line_x2 - line_x1
                            dy = line_y2 - line_y1
                            t = ((sx - line_x1) * dx + (sy - line_y1) * dy) / (dx**2 + dy**2)
                            
                            # Sprinkler must be close to line AND within line's extent
                            if distance_to_line <= 2.0 and -0.05 <= t <= 1.05:
                                total_sprinklers_on_lateral += 1
                                break  # Don't count same sprinkler twice
    
    # Highlight sprinkler lines that connect to farthest lateral
    for idx, spr_trace in enumerate(sprinkler_line_traces):
        fig.add_trace(go.Scatter(
            x=spr_trace['x'],
            y=spr_trace['y'],
            mode='lines',
            line=dict(color='cyan', width=3),
            name='Farthest Sprinkler Lines' if idx == 0 else None,
            showlegend=(idx == 0),
            legendgroup='farthest_sprinklers',
            hoverinfo='skip'
        ))
    
    # Highlight the farthest lateral in lime green (draw AFTER sprinkler lines so it's on top)
    fig.add_trace(go.Scatter(
        x=farthest_lateral['x'],
        y=farthest_lateral['y'],
        mode='lines+markers',
        line=dict(color='rgba(0, 255, 0, 0.8)', width=12),
        marker=dict(size=12, color='lime', symbol='circle'),
        name='🎯 DESIGN LATERAL (FARTHEST)',
        hovertext=f"<b>Farthest Lateral</b><br>" +
                 f"Length: {farthest_lateral['length']:.1f} m<br>" +
                 f"Distance from source: {farthest_lateral['distance_from_source']:.1f} m<br>" +
                 f"Sprinkler lines: {sprinkler_lines_on_lateral}<br>" +
                 f"Total sprinklers: {total_sprinklers_on_lateral}",
        hoverinfo='text'
    ))
    
    # Display the map
    st.plotly_chart(fig, width="stretch", key="lateral_overview_map")
    
    # Show configuration metrics
    st.markdown("#### 📊 Design Lateral Configuration")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("🎯 Design Lateral", "Farthest")
        st.caption(f"Distance: {farthest_lateral['distance_from_source']:.1f} m")
    
    with col2:
        st.metric("📏 Lateral Length", f"{farthest_lateral['length']:.1f} m")
        st.caption("Total lateral pipe length")
    
    with col3:
        st.metric("💧 Sprinkler Lines", f"{sprinkler_lines_on_lateral}")
        st.caption(f"Total sprinklers: {total_sprinklers_on_lateral}")
    
    with col4:
        # Get sprinkler data for flow calculation
        if 'sprinkler_data' in st.session_state.project_data:
            sprinkler = st.session_state.project_data['sprinkler_data']
            sprinkler_flow_m3h = sprinkler.get('flow', 500) / 1000  # L/h to m³/h
            # Calculate flow based on ACTUAL sprinkler count
            total_flow = total_sprinklers_on_lateral * sprinkler_flow_m3h
            st.metric("🌊 Total Flow", f"{total_flow:.2f} m³/h")
            st.caption(f"{total_sprinklers_on_lateral} × {sprinkler_flow_m3h:.3f} m³/h")
        else:
            st.metric("🌊 Total Flow", "N/A")
            st.caption("Complete sprinkler selection")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 2: PIPE NETWORK DESIGN FOR FARTHEST LATERAL
    # ============================================================================
    
    # Use the farthest lateral we already detected
    # No need to check for selected_line - we'll design the farthest lateral automatically
    
    if not lateral_lines:
        st.error("❌ No lateral lines found. Please draw laterals in Pipe Network Layout first.")
        return
    
    # Calculate lateral length
    lateral_length = farthest_lateral['length']
    
    # Get sprinkler data
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete sprinkler selection first.")
        return
    
    sprinkler = st.session_state.project_data['sprinkler_data']
    
    # Get sprinkler line design data (total flow per sprinkler LINE, not per individual sprinkler)
    sprinkler_line_flow_m3h = None
    if 'temp_sprinkler_line_design' in st.session_state:
        sprinkler_line_flow_m3h = st.session_state.temp_sprinkler_line_design.get('total_flow_m3h')
    elif 'sprinkler_line_design' in st.session_state.project_data:
        sprinkler_line_flow_m3h = st.session_state.project_data['sprinkler_line_design'].get('total_flow_m3h')
    
    # Fallback: calculate from individual sprinkler data if sprinkler line design not available
    if sprinkler_line_flow_m3h is None:
        st.warning("⚠️ Complete Sprinkler Line Design first for accurate lateral calculations.")
        # Use operational data as fallback
        operational_data = st.session_state.project_data.get('operational_data', {})
        sprinklers_per_line = operational_data.get('sprinklers_between_lines', 6)
        sprinkler_flow_lh = sprinkler.get('flow', 500)
        sprinkler_line_flow_m3h = round((sprinklers_per_line * sprinkler_flow_lh) / 1000, 3)
        st.caption(f"Using calculated flow: {sprinklers_per_line} sprinklers × {sprinkler_flow_lh} L/h = {sprinkler_line_flow_m3h} m³/h per line")
    
    sprinkler_spacing = round(sprinkler.get('spacing_between', 12), 1)
    n_sprinkler_lines = sprinkler_lines_on_lateral  # Number of sprinkler LINES on this lateral
    
    # If detection failed, fall back to calculation
    if n_sprinkler_lines == 0:
        n_sprinkler_lines = int(lateral_length / sprinkler_spacing) if sprinkler_spacing > 0 else 1
    
    sprinkler_pressure = sprinkler.get('pressure', 30)
    
    # Configuration
    st.markdown("#### ⚙️ Configuration")
    
    # Basic info display
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Lateral Length", f"{lateral_length:.1f} m")
        st.metric("Sprinkler Line Spacing", f"{sprinkler_spacing} m")
    with col2:
        st.metric("Sprinkler Lines on Lateral", f"{n_sprinkler_lines}")
        st.metric("Default Flow per Line", f"{sprinkler_line_flow_m3h:.2f} m³/h")
    with col3:
        st.metric("Pressure Required", f"{sprinkler_pressure} m")
    
    # Advanced Configuration - Individual Sprinkler Line Details
    with st.expander("📋 Individual Sprinkler Line Configuration", expanded=False):
        st.caption("For irregular fields: Configure each sprinkler line individually if they have different numbers of sprinklers.")
        
        # Initialize individual line configuration in session state
        if 'lateral_line_config' not in st.session_state:
            st.session_state.lateral_line_config = {}
        
        # Check if config needs reset (number of lines changed)
        config_key = f"lateral_{n_sprinkler_lines}_lines"
        if st.session_state.lateral_line_config.get('config_key') != config_key:
            st.session_state.lateral_line_config = {
                'config_key': config_key,
                'use_individual': False,
                'lines': {}
            }
        
        # Toggle for individual configuration
        use_individual_config = st.checkbox(
            "Configure each sprinkler line individually",
            value=st.session_state.lateral_line_config.get('use_individual', False),
            key="use_individual_lateral_config"
        )
        st.session_state.lateral_line_config['use_individual'] = use_individual_config
        
        # Get default values from sprinkler line design
        default_sprinklers_per_line = 8  # Default
        default_sprinkler_flow_lh = 500  # Default L/h
        
        if 'temp_sprinkler_line_design' in st.session_state:
            design = st.session_state.temp_sprinkler_line_design
            default_sprinklers_per_line = design.get('n_sprinklers', 8)
            default_sprinkler_flow_lh = design.get('sprinkler_flow_lh', 500)
        elif 'sprinkler_line_design' in st.session_state.project_data:
            design = st.session_state.project_data['sprinkler_line_design']
            default_sprinklers_per_line = design.get('n_sprinklers', 8)
            default_sprinkler_flow_lh = design.get('sprinkler_flow_lh', 500)
        
        if use_individual_config:
            st.markdown("##### Configure Each Sprinkler Line")
            
            # Create input grid for each line
            n_cols = min(5, n_sprinkler_lines)
            
            for row_start in range(0, n_sprinkler_lines, n_cols):
                cols = st.columns(n_cols)
                for col_idx, line_num in enumerate(range(row_start + 1, min(row_start + n_cols + 1, n_sprinkler_lines + 1))):
                    with cols[col_idx]:
                        st.markdown(f"**Line {line_num}**")
                        
                        # Get stored or default value
                        line_key = f"line_{line_num}"
                        stored_sprinklers = st.session_state.lateral_line_config.get('lines', {}).get(line_key, {}).get('n_sprinklers', default_sprinklers_per_line)
                        
                        n_sprinklers = st.number_input(
                            "Sprinklers",
                            min_value=1,
                            max_value=50,
                            value=stored_sprinklers,
                            key=f"lateral_line_{line_num}_sprinklers",
                            label_visibility="collapsed"
                        )
                        
                        # Calculate and show flow for this line
                        line_flow = (n_sprinklers * default_sprinkler_flow_lh) / 1000  # m³/h
                        st.caption(f"{n_sprinklers} spr × {default_sprinkler_flow_lh} L/h")
                        st.caption(f"= **{line_flow:.2f} m³/h**")
                        
                        # Store in session state
                        if 'lines' not in st.session_state.lateral_line_config:
                            st.session_state.lateral_line_config['lines'] = {}
                        st.session_state.lateral_line_config['lines'][line_key] = {
                            'n_sprinklers': n_sprinklers,
                            'flow_m3h': line_flow
                        }
            
            # Show total flow calculation
            total_configured_flow = sum(
                st.session_state.lateral_line_config.get('lines', {}).get(f'line_{i}', {}).get('flow_m3h', sprinkler_line_flow_m3h)
                for i in range(1, n_sprinkler_lines + 1)
            )
            st.success(f"📊 **Total Lateral Flow (configured)**: {total_configured_flow:.2f} m³/h")
        else:
            st.caption(f"Using uniform configuration: {n_sprinkler_lines} lines × {sprinkler_line_flow_m3h:.2f} m³/h = {n_sprinkler_lines * sprinkler_line_flow_m3h:.2f} m³/h total")
    
    # Variable pipe sizing
    st.markdown("#### 🔧 Variable Pipe Sizing Design")
    
    # Design mode selection
    design_mode_lateral = st.radio(
        "Design Mode",
        ["Automatic (Optimized)", "Manual (Select Each Segment)"],
        help="Automatic mode selects optimal pipe sizes. Manual mode lets you choose diameters for each segment.",
        key="lateral_design_mode"
    )
    
    st.caption("Design Approach: Pipe diameter DECREASES from inlet to end (telescoping)")
    
    # Design parameters
    col1, col2 = st.columns(2)
    with col1:
        max_velocity = st.number_input("Maximum Velocity (m/s)", min_value=0.5, max_value=3.0, value=1.5, step=0.1, key='lateral_vel',
                                       help="Recommended: 1.0-2.0 m/s for PVC pipes")
        C_coefficient = st.number_input("Hazen-Williams C", min_value=100, max_value=150, value=130, step=5, key='lateral_c',
                                       help="C=130 for PVC, C=120 for PE")
    with col2:
        max_friction_loss = st.number_input("Max Friction Loss (%)", min_value=5.0, max_value=20.0, value=10.0, step=1.0, key='lateral_fric',
                                            help="Friction loss as % of operating pressure")
        min_velocity = st.number_input("Minimum Velocity (m/s)", min_value=0.3, max_value=1.5, value=0.6, step=0.1, key='lateral_min_vel',
                                      help="Minimum to prevent sediment buildup")
    
    # Show available pipe sizes
    with st.expander("📏 Available Pipe Sizes"):
        pipe_sizes = get_standard_pipe_sizes()
        df_sizes = pd.DataFrame(pipe_sizes)
        df_sizes.columns = ['Nominal Ø (mm)', 'Internal Ø (mm)']
        st.dataframe(df_sizes, width="stretch")
    
    # Calculate variable sizing
    calculate_lateral_button = st.button("🔍 Calculate Lateral Pipe Sizing", type="primary")
    
    # Initialize session state for manual selections
    if 'manual_lateral_pipe_selections' not in st.session_state:
        st.session_state.manual_lateral_pipe_selections = {}
    
    # Manual selection interface (show BEFORE calculation if in manual mode)
    if design_mode_lateral == "Manual (Select Each Segment)":
        # Check if we have previous design results (use temp if available, else saved)
        if 'temp_lateral_design' in st.session_state:
            previous_segments = st.session_state.temp_lateral_design.get('segments', [])
        elif 'lateral_design' in st.session_state.project_data:
            previous_segments = st.session_state.project_data['lateral_design'].get('segments', [])
        else:
            previous_segments = []
        
        # Check if previous segments match current sprinkler line count
        if previous_segments and len(previous_segments) == n_sprinkler_lines:
            st.markdown("---")
            st.markdown("#### 🎛️ Manual Pipe Selection")
            st.caption("Select pipe diameter for each segment, then click 'Calculate' to update.")
            
            pipe_sizes = get_standard_pipe_sizes()
            
            # Create columns for segment selection
            n_cols_display = min(5, n_sprinkler_lines)
            cols = st.columns(n_cols_display)
            
            for i, seg in enumerate(previous_segments):
                col_idx = i % n_cols_display
                with cols[col_idx]:
                    segment_key = f"lateral_seg_{seg['segment']}"
                    
                    # Create pipe size options
                    pipe_options = [f"Ø{s['nominal']} mm" for s in pipe_sizes]
                    current_idx = next((idx for idx, s in enumerate(pipe_sizes) 
                                      if s['nominal'] == seg['pipe_nominal_mm']), 0)
                    
                    # Initialize if not set
                    if segment_key not in st.session_state.manual_lateral_pipe_selections:
                        st.session_state.manual_lateral_pipe_selections[segment_key] = current_idx
                    
                    # Display segment info with compact formatting
                    st.markdown(f"**Seg {seg['segment']}**")
                    st.caption(f"Flow: {seg['flow_m3h']} m³/h")
                    if 'velocity_ms' in seg:
                        st.caption(f"V: {seg['velocity_ms']} m/s")
                    
                    # Pipe selector
                    selected_idx = st.selectbox(
                        "Pipe Size",
                        range(len(pipe_sizes)),
                        index=st.session_state.manual_lateral_pipe_selections[segment_key],
                        format_func=lambda x: pipe_options[x],
                        key=f"select_{segment_key}",
                        label_visibility="collapsed"
                    )
                    
                    st.session_state.manual_lateral_pipe_selections[segment_key] = selected_idx
            
            st.markdown("---")
            
            # Save button for manual selections
            col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
            with col_save2:
                if st.button("💾 Save Pipe Selections", type="secondary", width="stretch", key="save_manual_lateral"):
                    st.success("✅ Pipe selections saved! Click 'Calculate' to update the design.")
    
    # Check if we should show results
    show_lateral_results = calculate_lateral_button or 'temp_lateral_design' in st.session_state
    
    if calculate_lateral_button:
        
        # Christiansen F-factor (used for friction loss calculation, NOT for flow reduction)
        F = calculate_f_factor(n_sprinkler_lines)
        
        segments = []
        cumulative_length = 0
        
        pipe_sizes = get_standard_pipe_sizes()
        
        # Get individual line configuration if enabled
        use_individual_config = st.session_state.get('lateral_line_config', {}).get('use_individual', False)
        line_flows = {}  # Dictionary to store flow for each line
        
        if use_individual_config:
            # Use individually configured flows
            for line_num in range(1, n_sprinkler_lines + 1):
                line_key = f"line_{line_num}"
                line_data = st.session_state.lateral_line_config.get('lines', {}).get(line_key, {})
                line_flows[line_num] = line_data.get('flow_m3h', sprinkler_line_flow_m3h)
        else:
            # Use uniform flow for all lines
            for line_num in range(1, n_sprinkler_lines + 1):
                line_flows[line_num] = sprinkler_line_flow_m3h
        
        # CORRECTED FLOW LOGIC: TELESCOPING - Design from INLET to FARTHEST SPRINKLER LINE
        # Segment 1 = inlet (highest flow - serves all sprinkler lines), Segment n = farthest (lowest flow - serves 1 line)
        # Each segment carries CUMULATIVE flow of all downstream sprinkler lines
        #
        # Example with 5 sprinkler lines (each 4.2 m³/h):
        # - Segment 5 (Line 4→5): Carries flow for Line 5 only = 4.2 m³/h
        # - Segment 4 (Line 3→4): Carries flow for Lines 4+5 = 8.4 m³/h
        # - Segment 3 (Line 2→3): Carries flow for Lines 3+4+5 = 12.6 m³/h
        # - Segment 2 (Line 1→2): Carries flow for Lines 2+3+4+5 = 16.8 m³/h
        # - Segment 1 (Inlet→Line 1): Carries flow for ALL lines = 21.0 m³/h
        
        for i in range(n_sprinkler_lines):
            # Segment number: 1 = inlet (highest flow), n = farthest (lowest flow)
            segment_num = i + 1
            
            # Number of sprinkler lines DOWNSTREAM of this segment (still to be served)
            # Segment 1 (inlet) serves ALL n sprinkler lines
            # Segment n (farthest) serves only 1 sprinkler line (the last one)
            n_lines_downstream = n_sprinkler_lines - i
            
            # Flow in this segment = SUM of flows for all downstream sprinkler lines
            # Downstream lines are: (segment_num) to n_sprinkler_lines
            # Which means lines (i+1) to n_sprinkler_lines in 1-based indexing
            segment_flow_m3h = sum(line_flows[line_num] for line_num in range(segment_num, n_sprinkler_lines + 1))
            
            # IMPORTANT: Use ACTUAL flow for pipe sizing (no F-factor reduction)
            # F-factor is applied only for friction loss calculation
            segment_flow_for_pipe_sizing = segment_flow_m3h  # Full flow!
            
            # For friction loss calculation, we can optionally apply F-factor
            segment_flow_for_friction = segment_flow_m3h * F
            
            segment_length = sprinkler_spacing
            cumulative_length += segment_length
            
            # Automatic or Manual pipe selection
            if design_mode_lateral == "Manual (Select Each Segment)":
                # User selects pipe size for this segment
                segment_key = f"lateral_seg_{i + 1}"
                
                # Find optimal size as default
                optimal_size = None
                for size in pipe_sizes:
                    D_mm = size['internal']
                    D_m = D_mm / 1000
                    Q_m3s = segment_flow_for_pipe_sizing / 3600
                    area = 3.14159 * (D_m / 2) ** 2
                    velocity = Q_m3s / area if area > 0 else 999
                    
                    if min_velocity <= velocity <= max_velocity:
                        optimal_size = size
                        break
                
                if optimal_size is None:
                    optimal_size = pipe_sizes[0]  # Default to smallest
                
                # Get default index
                default_idx = next((idx for idx, s in enumerate(pipe_sizes) if s['nominal'] == optimal_size['nominal']), 0)
                
                if segment_key not in st.session_state.manual_lateral_pipe_selections:
                    st.session_state.manual_lateral_pipe_selections[segment_key] = default_idx
                
                selected_idx = st.session_state.manual_lateral_pipe_selections[segment_key]
                selected_size = pipe_sizes[selected_idx]
            
            else:
                # TELESCOPING ALGORITHM - Find smallest pipe that keeps velocity <= max_velocity
                selected_size = None
                for size in pipe_sizes:
                    D_mm = size['internal']
                    D_m = D_mm / 1000
                    
                    Q_m3s = segment_flow_for_pipe_sizing / 3600
                    area = 3.14159 * (D_m / 2) ** 2
                    velocity = Q_m3s / area if area > 0 else 0
                    
                    # Check if velocity is within acceptable range
                    if velocity <= max_velocity:
                        # Found a valid pipe - check if velocity is too low
                        if velocity >= min_velocity:
                            # Perfect - velocity is in the ideal range
                            selected_size = size
                            break
                        else:
                            # Velocity is below minimum, but accept it (we can't go smaller)
                            selected_size = size
                            break
                
                # Fallback: if even the largest pipe exceeds max_velocity
                if selected_size is None:
                    selected_size = pipe_sizes[-1]
            
            # Use friction flow (with F-factor) for friction loss calculation
            hf_segment = calculate_hazen_williams(segment_flow_for_friction, selected_size['internal'], segment_length, C_coefficient)
            
            # Use actual flow for velocity calculation (for display purposes)
            D_m = selected_size['internal'] / 1000
            Q_m3s = segment_flow_for_pipe_sizing / 3600
            area = 3.14159 * (D_m / 2) ** 2
            velocity = Q_m3s / area if area > 0 else 0
            
            # Calculate distance from inlet (cumulative distance)
            distance_from_inlet = cumulative_length - segment_length
            
            # Position description: show which sprinkler lines are served
            # Segment 1: Inlet → Line 1 (serves all lines)
            # Segment n: Line (n-1) → Line n (serves only last line)
            if segment_num == 1:
                position = f"Inlet → Line 1"
            else:
                position = f"Line {segment_num - 1} → Line {segment_num}"
            
            segments.append({
                'segment': segment_num,
                'position': position,
                'length_m': segment_length,
                'distance_from_inlet_m': round(distance_from_inlet, 1),
                'n_lines_downstream': n_lines_downstream,
                'flow_m3h': round(segment_flow_m3h, 3),  # Store ACTUAL flow (not reduced by F-factor)
                'pipe_nominal_mm': selected_size['nominal'],
                'pipe_internal_mm': selected_size['internal'],
                'velocity_ms': round(velocity, 2),
                'friction_loss_m': round(hf_segment, 3),
                'sprinkler_line_flow_m3h': round(line_flows.get(segment_num, sprinkler_line_flow_m3h), 3)  # Flow for this specific line
            })
        
        total_friction_loss = sum(seg['friction_loss_m'] for seg in segments)
        friction_loss_pct = (total_friction_loss / sprinkler_pressure) * 100 if sprinkler_pressure > 0 else 0
        
        # Velocity check
        max_velocity_observed = max(seg['velocity_ms'] for seg in segments) if segments else 0
        min_velocity_observed = min(seg['velocity_ms'] for seg in segments) if segments else 0
        velocity_ok = min_velocity <= min_velocity_observed and max_velocity_observed <= max_velocity
        friction_ok = friction_loss_pct <= max_friction_loss
        
        # Calculate total flow at inlet (first segment, which serves all sprinkler lines)
        total_flow_m3h = segments[0]['flow_m3h'] if segments else 0
        
        # Save results to temp state
        st.session_state.temp_lateral_design = {
            'lateral_index': 0,  # Farthest lateral (always index 0 for now)
            'segments': segments,
            'total_length_m': cumulative_length,
            'total_flow_m3h': round(total_flow_m3h, 3),
            'total_friction_loss_m': round(total_friction_loss, 3),
            'friction_loss_pct': round(friction_loss_pct, 2),
            'F_factor': round(F, 4),
            'max_velocity_ms': max_velocity,
            'min_velocity_ms': min_velocity,
            'max_velocity_observed': round(max_velocity_observed, 2),
            'min_velocity_observed': round(min_velocity_observed, 2),
            'C_coefficient': C_coefficient,
            'design_mode': design_mode_lateral,
            'n_sprinkler_lines': n_sprinkler_lines,
            'sprinkler_line_spacing': sprinkler_spacing,
            'sprinkler_line_flow_m3h': sprinkler_line_flow_m3h
        }
    
    # DISPLAY RESULTS SECTION - Show if just calculated OR if temp data exists
    if show_lateral_results and 'temp_lateral_design' in st.session_state:
        # Load data from temp state
        design_data = st.session_state.temp_lateral_design
        segments = design_data['segments']
        total_friction_loss = design_data['total_friction_loss_m']
        friction_loss_pct = design_data['friction_loss_pct']
        max_velocity_observed = design_data['max_velocity_observed']
        min_velocity_observed = design_data['min_velocity_observed']
        max_velocity = design_data['max_velocity_ms']
        min_velocity = design_data['min_velocity_ms']
        cumulative_length = design_data['total_length_m']
        cumulative_flow = design_data['total_flow_m3h']
        F = design_data['F_factor']
        C_coefficient = design_data['C_coefficient']
        lateral_index = design_data['lateral_index']
        design_mode_lateral = design_data.get('design_mode', 'Automatic (Optimized)')
        n_sprinkler_lines = design_data.get('n_sprinkler_lines', design_data.get('n_sprinklers', len(segments)))  # Backward compatibility
        sprinkler_spacing = design_data.get('sprinkler_line_spacing', design_data.get('sprinkler_spacing', sprinkler_spacing))  # Backward compatibility
        sprinkler_line_flow_m3h = design_data.get('sprinkler_line_flow_m3h', 0.52)
        
        # Check if design meets criteria
        velocity_ok = min_velocity <= min_velocity_observed and max_velocity_observed <= max_velocity
        friction_ok = friction_loss_pct <= max_friction_loss
        
        # Display status indicators with save button
        status_col1, status_col2, status_col3, status_col4 = st.columns([2, 2, 2, 1])
        with status_col1:
            if friction_ok:
                st.success(f"✅ Friction Loss: {total_friction_loss:.2f} m ({friction_loss_pct:.1f}%)")
            else:
                st.error(f"⚠️ Friction Loss: {total_friction_loss:.2f} m ({friction_loss_pct:.1f}%) - EXCEEDS LIMIT")
        
        with status_col2:
            if velocity_ok:
                st.success(f"✅ Velocity: {min_velocity_observed:.2f} - {max_velocity_observed:.2f} m/s")
            else:
                st.warning(f"⚠️ Velocity: {min_velocity_observed:.2f} - {max_velocity_observed:.2f} m/s - CHECK LIMITS")
        
        with status_col3:
            if friction_ok and velocity_ok:
                st.success("✅ Design OK")
            else:
                st.warning("⚠️ Design needs adjustment")
        
        with status_col4:
            # SAVE BUTTON
            if st.button("💾 Save", type="primary", width="stretch", key="save_lateral"):
                st.session_state.project_data['lateral_design'] = st.session_state.temp_lateral_design.copy()
                st.success("✅ Lateral Design Saved Successfully!")
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Visual Diagram",
            "📈 Performance Analysis",
            "📋 Detailed Table",
            "💡 Advisory"
        ])
        
        with tab1:
            st.markdown("##### Lateral Line - Variable Pipe Sizing Diagram")
            fig_diagram = create_lateral_line_diagram(segments, sprinkler_spacing)
            st.plotly_chart(fig_diagram, width="stretch", key="lateral_line_diagram")
        
        with tab2:
            fig_perf = create_performance_charts(segments)
            st.plotly_chart(fig_perf, width="stretch", key="lateral_perf")
        
        with tab3:
            st.markdown("##### Detailed Segment Information")
            df = pd.DataFrame(segments)
            
            # Add distance_from_inlet_m if missing (for backward compatibility)
            if 'distance_from_inlet_m' not in df.columns and len(segments) > 0:
                # Calculate distance from cumulative length
                distances = []
                cumulative = 0
                for seg in segments:
                    distances.append(cumulative)
                    cumulative += seg.get('length_m', 0)
                df['distance_from_inlet_m'] = distances
            
            # Reorder and rename columns for better display
            display_columns = {
                'segment': 'Seg #',
                'position': 'Position',
                'distance_from_inlet_m': 'Distance (m)',
                'length_m': 'Length (m)',
                'n_lines_downstream': 'Lines Served',
                'flow_m3h': 'Flow (m³/h)',
                'pipe_nominal_mm': 'Pipe Ø (mm)',
                'velocity_ms': 'Velocity (m/s)',
                'friction_loss_m': 'Friction Loss (m)'
            }
            
            # Only include columns that exist
            available_columns = {k: v for k, v in display_columns.items() if k in df.columns}
            
            df_display = df[list(available_columns.keys())].copy()
            df_display.columns = list(available_columns.values())
            
            # Color code based on velocity
            def highlight_velocity(row):
                vel = row['Velocity (m/s)']
                if vel < min_velocity:
                    return ['background-color: #fff3cd'] * len(row)  # Yellow
                elif vel > max_velocity:
                    return ['background-color: #f8d7da'] * len(row)  # Red
                else:
                    return ['background-color: #d4edda'] * len(row)  # Green
            
            # Format numeric columns to max 2 decimal places
            format_dict = {col: '{:.2f}' for col in df_display.select_dtypes(include=['float64', 'float32', 'number']).columns}
            
            st.dataframe(
                df_display.style.apply(highlight_velocity, axis=1).format(format_dict),
                width="stretch",
                height=400
            )
            
            # Summary metrics
            st.markdown("##### Summary")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Length", f"{cumulative_length:.1f} m")
            with col2:
                total_flow = segments[0]['flow_m3h'] if segments else 0  # Inlet flow = total lateral flow
                st.metric("Total Flow", f"{total_flow:.2f} m³/h")
            with col3:
                st.metric("Friction Loss", f"{total_friction_loss:.3f} m")
            with col4:
                st.metric("Velocity Range", f"{min_velocity_observed:.2f}-{max_velocity_observed:.2f} m/s")
            with col5:
                unique_sizes = len(set(seg['pipe_nominal_mm'] for seg in segments))
                st.metric("Pipe Sizes Used", f"{unique_sizes}")
        
        with tab4:
            st.markdown("##### 💡 Design Advisory")
            
            # Provide recommendations
            advisories = []
            
            # Check friction loss
            if friction_loss_pct > max_friction_loss:
                advisories.append({
                    'type': 'error',
                    'message': f"❌ **Friction Loss Exceeded**: {friction_loss_pct:.1f}% > {max_friction_loss}%",
                    'recommendation': "Consider using larger pipe diameters for high-flow segments (closer to inlet)."
                })
            elif friction_loss_pct > max_friction_loss * 0.8:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Friction Loss High**: {friction_loss_pct:.1f}% (80% of limit)",
                    'recommendation': "Design is acceptable but operating near limits. Consider margin for future expansion."
                })
            else:
                advisories.append({
                    'type': 'success',
                    'message': f"✅ **Friction Loss OK**: {friction_loss_pct:.1f}%",
                    'recommendation': "Friction loss is within acceptable limits."
                })
            
            # Check velocity
            low_velocity_segments = [s for s in segments if s['velocity_ms'] < min_velocity]
            high_velocity_segments = [s for s in segments if s['velocity_ms'] > max_velocity]
            
            if low_velocity_segments:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Low Velocity Warning**: {len(low_velocity_segments)} segment(s) below {min_velocity} m/s",
                    'recommendation': "Low velocities may lead to sediment buildup. This is acceptable if unavoidable with available pipe sizes."
                })
            
            if high_velocity_segments:
                advisories.append({
                    'type': 'error',
                    'message': f"❌ **High Velocity Warning**: {len(high_velocity_segments)} segment(s) exceed {max_velocity} m/s",
                    'recommendation': "High velocities increase friction and may damage fittings. Use larger pipe diameters."
                })
            
            if velocity_ok:
                advisories.append({
                    'type': 'success',
                    'message': f"✅ **Velocities OK**: {min_velocity_observed:.2f} - {max_velocity_observed:.2f} m/s",
                    'recommendation': "All velocities are within recommended range."
                })
            
            # Optimization suggestions
            unique_sizes = set(seg['pipe_nominal_mm'] for seg in segments)
            if len(unique_sizes) > 3:
                advisories.append({
                    'type': 'info',
                    'message': f"ℹ️ **Multiple Pipe Sizes**: Using {len(unique_sizes)} different diameters",
                    'recommendation': "Consider if reducing the number of different pipe sizes would simplify procurement and installation."
                })
            
            # Display advisories
            for adv in advisories:
                if adv['type'] == 'error':
                    st.error(adv['message'])
                elif adv['type'] == 'warning':
                    st.warning(adv['message'])
                elif adv['type'] == 'success':
                    st.success(adv['message'])
                else:
                    st.info(adv['message'])
                
                st.markdown(f"**Recommendation:** {adv['recommendation']}")
                st.markdown("---")
            
            # Material list
            st.markdown("##### 📦 Material List")
            
            # Group consecutive segments with same diameter
            pipe_groups = []
            current_group = {'diameter': segments[0]['pipe_nominal_mm'], 'start': 1, 'end': 1, 'length': segments[0]['length_m']}
            
            for i in range(1, len(segments)):
                if segments[i]['pipe_nominal_mm'] == current_group['diameter']:
                    current_group['end'] = segments[i]['segment']
                    current_group['length'] += segments[i]['length_m']
                else:
                    pipe_groups.append(current_group)
                    current_group = {
                        'diameter': segments[i]['pipe_nominal_mm'],
                        'start': segments[i]['segment'],
                        'end': segments[i]['segment'],
                        'length': segments[i]['length_m']
                    }
            pipe_groups.append(current_group)
            
            st.markdown("**Pipe Requirements:**")
            for group in pipe_groups:
                if group['start'] == group['end']:
                    st.markdown(f"- **Ø{group['diameter']} mm PVC**: {group['length']:.1f} m (Segment {group['start']})")
                else:
                    st.markdown(f"- **Ø{group['diameter']} mm PVC**: {group['length']:.1f} m (Segments {group['start']}-{group['end']})")
            
            # Total material summary
            st.markdown("**Total Materials:**")
            total_by_size = {}
            for group in pipe_groups:
                if group['diameter'] not in total_by_size:
                    total_by_size[group['diameter']] = 0
                total_by_size[group['diameter']] += group['length']
            
            for diameter in sorted(total_by_size.keys()):
                st.markdown(f"- Ø{diameter} mm PVC pipe: **{total_by_size[diameter]:.1f} m**")


def create_lateral_line_diagram(segments, spacing):
    """Create visual diagram of lateral line with variable pipe sizing"""
    
    if not segments:
        return go.Figure()
    
    fig = go.Figure()
    
    # Sort unique sizes from LARGEST to SMALLEST for legend (inlet has largest pipe)
    unique_sizes = sorted(list(set(seg['pipe_nominal_mm'] for seg in segments)), reverse=True)
    colors = ['#d62728', '#2ca02c', '#ff7f0e', '#1f77b4', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
    size_colors = {size: colors[i % len(colors)] for i, size in enumerate(unique_sizes)}
    
    # Segments are already in order: Segment 1 = inlet (highest flow), Segment N = farthest (lowest flow)
    # This is correct for drawing left to right
    
    # Add inlet marker at position 0 with pipe size info
    inlet_flow = segments[0]['flow_m3h'] if segments else 0
    inlet_pipe = segments[0]['pipe_nominal_mm'] if segments else 0
    fig.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode='markers+text',
        marker=dict(size=18, color='red', symbol='square'),
        text=[f"INLET\n(Ø{inlet_pipe}mm)"],
        textposition="bottom center",
        textfont=dict(size=10, color='red', family='Arial Black'),
        showlegend=False,
        hovertext=f"<b>Lateral Inlet</b><br>Total Flow: {inlet_flow:.2f} m³/h<br>Starting Pipe: Ø{inlet_pipe}mm",
        hoverinfo='text'
    ))
    
    # Track sizes used for legend
    sizes_in_legend = set()
    
    x_pos = 0
    for i, seg in enumerate(segments):
        x_end = x_pos + seg['length_m']
        
        # Line width proportional to pipe diameter for visual clarity
        line_width = 5 + (seg['pipe_nominal_mm'] / 6)
        
        # Check if this is first occurrence of this pipe size for legend
        show_in_legend = seg['pipe_nominal_mm'] not in sizes_in_legend
        if show_in_legend:
            sizes_in_legend.add(seg['pipe_nominal_mm'])
        
        fig.add_trace(go.Scatter(
            x=[x_pos, x_end],
            y=[0, 0],
            mode='lines',
            line=dict(
                color=size_colors[seg['pipe_nominal_mm']],
                width=line_width
            ),
            name=f"Ø{seg['pipe_nominal_mm']} mm",
            showlegend=show_in_legend,
            legendrank=unique_sizes.index(seg['pipe_nominal_mm']),  # Order legend by size
            hovertext=f"<b>Segment {seg['segment']}</b><br>" +
                     f"{seg.get('position', 'Segment ' + str(seg['segment']))}<br>" +
                     f"Pipe: Ø{seg['pipe_nominal_mm']} mm (ID: {seg['pipe_internal_mm']} mm)<br>" +
                     f"Flow: {seg['flow_m3h']:.2f} m³/h<br>" +
                     (f"Lines Served: {seg['n_lines_downstream']}<br>" if 'n_lines_downstream' in seg else "") +
                     f"Velocity: {seg['velocity_ms']:.2f} m/s<br>" +
                     f"Friction Loss: {seg['friction_loss_m']:.3f} m",
            hoverinfo='text'
        ))
        
        # Add flow label above each segment (like sprinkler line diagram)
        fig.add_trace(go.Scatter(
            x=[(x_pos + x_end) / 2],
            y=[0.5],
            mode='text',
            text=[f"{seg['flow_m3h']:.1f} m³/h"],
            textposition="middle center",
            textfont=dict(size=9, color=size_colors[seg['pipe_nominal_mm']]),
            showlegend=False,
            hoverinfo='skip'
        ))
        
        # Sprinkler line connection marker at end of segment
        fig.add_trace(go.Scatter(
            x=[x_end],
            y=[0],
            mode='markers+text',
            marker=dict(size=14, color='darkgreen', symbol='square', line=dict(width=2, color='white')),
            text=[f"L{seg['segment']}"],  # Line number
            textposition="top center",
            textfont=dict(size=10, color='darkgreen', family='Arial Black'),
            showlegend=False,
            hovertext=f"<b>Sprinkler Line {seg['segment']}</b><br>" +
                     f"Connection Point<br>" +
                     f"Flow to this line: {seg.get('sprinkler_line_flow_m3h', seg['flow_m3h'] / max(seg.get('n_lines_downstream', 1), 1)):.2f} m³/h",
            hoverinfo='text'
        ))
        
        x_pos = x_end
    
    # Add "FARTHEST" label at the end
    fig.add_trace(go.Scatter(
        x=[x_pos + 5],  # Slightly beyond last point
        y=[0],
        mode='text',
        text=["FARTHEST"],
        textposition="middle right",
        textfont=dict(size=10, color='navy', family='Arial Black'),
        showlegend=False,
        hoverinfo='skip'
    ))
    
    # Calculate total length for x-axis range
    total_length = sum(seg['length_m'] for seg in segments)
    
    fig.update_layout(
        title="Lateral Line - Variable Pipe Sizing",
        xaxis_title="Distance from Inlet (m)",
        yaxis_title="",
        height=350,
        showlegend=True,
        legend=dict(
            traceorder='normal',
            title='Pipe Sizes'
        ),
        xaxis=dict(range=[-5, total_length + 15]),  # Start before 0 to show inlet marker clearly
        yaxis=dict(visible=False, range=[-1, 2]),
        hovermode='closest',
        plot_bgcolor='rgba(240, 240, 240, 0.5)'
    )
    
    return fig


def create_submain_line_diagram(segments, spacing):
    """Create visual diagram of submain line with variable pipe sizing"""
    
    if not segments:
        return go.Figure()
    
    fig = go.Figure()
    
    unique_sizes = sorted(list(set(seg['pipe_nominal_mm'] for seg in segments)))
    colors = ['#8B4513', '#FF6347', '#32CD32', '#FF8C00', '#9370DB', '#20B2AA', '#DC143C', '#696969']
    size_colors = {size: colors[i % len(colors)] for i, size in enumerate(unique_sizes)}
    
    # Add inlet marker at position 0
    fig.add_trace(go.Scatter(
        x=[0],
        y=[0],
        mode='markers+text',
        marker=dict(size=20, color='blue', symbol='circle', line=dict(width=3, color='white')),
        text=["INLET"],
        textposition="bottom center",
        textfont=dict(size=11, color='blue', family='Arial Black'),
        showlegend=False,
        hovertext="<b>Inlet Point</b><br>Water source connection",
        hoverinfo='text'
    ))
    
    x_pos = 0
    for i, seg in enumerate(segments):
        x_end = x_pos + seg['length_m']
        
        # Line width proportional to pipe diameter
        line_width = 5 + (seg['pipe_nominal_mm'] / 6)
        
        # Check if this is first occurrence of this pipe size for legend
        is_first_of_size = True
        for j in range(i):
            if segments[j]['pipe_nominal_mm'] == seg['pipe_nominal_mm']:
                is_first_of_size = False
                break
        
        fig.add_trace(go.Scatter(
            x=[x_pos, x_end],
            y=[0, 0],
            mode='lines',
            line=dict(
                color=size_colors[seg['pipe_nominal_mm']],
                width=line_width
            ),
            name=f"Ø{seg['pipe_nominal_mm']} mm",
            showlegend=is_first_of_size,
            hovertext=f"<b>Segment {seg['segment']}</b><br>" +
                     f"{seg.get('position', 'Segment ' + str(seg['segment']))}<br>" +
                     f"Pipe: Ø{seg['pipe_nominal_mm']} mm (ID: {seg['pipe_internal_mm']} mm)<br>" +
                     f"Flow: {seg['flow_m3h']:.2f} m³/h<br>" +
                     (f"Laterals Served: {seg['n_laterals_downstream']}<br>" if 'n_laterals_downstream' in seg else "") +
                     f"Velocity: {seg['velocity_ms']:.2f} m/s<br>" +
                     f"Friction Loss: {seg['friction_loss_m']:.3f} m",
            hoverinfo='text'
        ))
        
        # Valve/lateral connection marker at end of segment
        valve_label = seg.get('valve_label', f"V{seg['segment']}")
        fig.add_trace(go.Scatter(
            x=[x_end],
            y=[0],
            mode='markers+text',
            marker=dict(size=16, color='darkorange', symbol='star', line=dict(width=2, color='white')),
            text=[valve_label],
            textposition="top center",
            textfont=dict(size=10, color='darkorange', family='Arial Black'),
            showlegend=False,
            hovertext=f"<b>{valve_label}</b><br>" +
                     f"Connection Point at {x_end:.1f}m<br>" +
                     f"Flow to this lateral: {seg.get('lateral_flow_m3h', seg['flow_m3h']):.2f} m³/h",
            hoverinfo='text'
        ))
        
        x_pos = x_end
    
    # Add end point marker if needed (after last valve)
    if segments:
        fig.add_trace(go.Scatter(
            x=[x_pos],
            y=[0],
            mode='markers+text',
            marker=dict(size=14, color='gray', symbol='circle', line=dict(width=2, color='white')),
            text=["END"],
            textposition="top center",
            textfont=dict(size=9, color='gray', family='Arial'),
            showlegend=False,
            hovertext="<b>End of Submain</b>",
            hoverinfo='text'
        ))
    
    fig.update_layout(
        title="Submain Line - Variable Pipe Sizing",
        xaxis_title="Distance from Inlet (m)",
        yaxis_title="",
        height=300,
        showlegend=True,
        yaxis=dict(visible=False, range=[-1, 1]),
        hovermode='closest'
    )
    
    return fig


def show_submain_design():
    """Design submain line with irrigation scheduling flow calculation"""
    st.markdown('<h2 class="sub-header">Submain Design</h2>', unsafe_allow_html=True)
    
    # ============================================================================
    # SECTION 1: DESIGN LOCATION - SUBMAIN LINE VISUALIZATION
    # ============================================================================
    with st.expander("ℹ️ About Submain Design", expanded=False):
        st.markdown("""
        The submain connects multiple laterals (subplots) to the mainline.
        Flow calculation considers the **irrigation schedule** - how many subplots operate simultaneously.
        """)
    
    # Measurement Tool
    col_meas1, col_meas2, col_meas3 = st.columns([2, 2, 3])
    with col_meas1:
        if st.button("📏 Measure Distance", key="measure_tool_submain", help="Activate measurement on the map below"):
            drawing_state = st.session_state.get('drawing_state', {})
            drawing_state['mode'] = 'Measure'
            drawing_state['is_drawing'] = True
            drawing_state['points'] = []
            st.session_state.drawing_state = drawing_state
            if 'measurement' not in st.session_state:
                st.session_state.measurement = None
            st.rerun()
    
    with col_meas2:
        if st.button("❌ Clear Measurement", key="clear_measure_submain"):
            if 'measurement' in st.session_state:
                st.session_state.measurement = None
            st.rerun()
    
    with col_meas3:
        if 'measurement' in st.session_state and st.session_state.measurement:
            meas = st.session_state.measurement
            st.success(f"📏 **{meas['distance']:.2f} m** | From ({meas['point1'][0]:.1f}, {meas['point1'][1]:.1f}) to ({meas['point2'][0]:.1f}, {meas['point2'][1]:.1f})")
    
    # Get necessary data
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    operational_data = st.session_state.project_data.get('operational_data', {})
    pipe_network_design = st.session_state.project_data.get('pipe_network_design', {})
    
    # Initialize drawing_state with required keys if not present
    drawing_state = st.session_state.get('drawing_state', {})
    if 'is_drawing' not in drawing_state:
        drawing_state = {
            'is_drawing': False,
            'mode': None,
            'points': []
        }
    
    # Create the full field map
    from modules.pipe_network_layout import create_interactive_plot
    fig = create_interactive_plot(field_geometry, operational_data, pipe_network_design, drawing_state)
    
    if fig is None:
        st.warning("⚠️ No field geometry available. Please complete System Layout first.")
        return
    
    # Extract submain lines from the plot
    submain_lines = []
    water_source_local = field_geometry.get('water_source_local', [0, 0])
    
    for trace in fig.data:
        # Detect submain lines (check for name containing 'Submain')
        if trace.name and 'Submain' in str(trace.name):
            if hasattr(trace, 'x') and hasattr(trace, 'y') and len(trace.x) >= 2:
                # Calculate submain length
                submain_length = 0
                for i in range(len(trace.x) - 1):
                    dx = trace.x[i+1] - trace.x[i]
                    dy = trace.y[i+1] - trace.y[i]
                    submain_length += sqrt(dx**2 + dy**2)
                
                # Calculate average position (for distance calculation)
                avg_x = sum(trace.x) / len(trace.x)
                avg_y = sum(trace.y) / len(trace.y)
                
                # Calculate distance from water source
                distance_from_source = sqrt((avg_x - water_source_local[0])**2 + (avg_y - water_source_local[1])**2)
                
                submain_lines.append({
                    'x': list(trace.x),
                    'y': list(trace.y),
                    'length': submain_length,
                    'distance_from_source': distance_from_source,
                    'avg_x': avg_x,
                    'avg_y': avg_y
                })
    
    if not submain_lines:
        # ========================================================================
        # NO SUBMAIN CASE: Mainline connects directly to laterals
        # ========================================================================
        st.info("""
        ℹ️ **No Submain Lines Detected**
        
        Your system layout does not include submain lines. This is a valid configuration where:
        - The **mainline** connects **directly to lateral lines**
        - The mainline takes on the role of water distribution to laterals
        - Valve placement is on the mainline at lateral connection points
        
        **This tab can be skipped.** Proceed to **Mainline Design** to design the pipe network.
        """)
        
        # Display the field map anyway
        st.plotly_chart(fig, width="stretch", key="no_submain_field_map")
        
        # Show system info
        st.markdown("#### 📊 System Configuration")
        
        total_subplots = operational_data.get('total_subplots', 1)
        subplots_per_day = operational_data.get('subplots_per_day', 1)
        subplot_discharge_m3h = operational_data.get('subplot_discharge', 0)
        
        if subplot_discharge_m3h == 0:
            if 'sprinkler_data' in st.session_state.project_data:
                sprinkler = st.session_state.project_data['sprinkler_data']
                n_sprinklers_per_line = operational_data.get('n_sprinklers_per_line', 0)
                n_lines_per_subplot = operational_data.get('n_lines_per_subplot', 0)
                sprinkler_flow_lh = sprinkler.get('flow', 0)
                sprinkler_flow_m3h = sprinkler_flow_lh / 1000 if sprinkler_flow_lh > 0 else 0
                
                if n_sprinklers_per_line > 0 and n_lines_per_subplot > 0 and sprinkler_flow_m3h > 0:
                    subplot_discharge_m3h = n_sprinklers_per_line * n_lines_per_subplot * sprinkler_flow_m3h
        
        total_system_flow = min(total_subplots, subplots_per_day) * subplot_discharge_m3h
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("🌿 Total Subplots", f"{total_subplots}")
        with col2:
            st.metric("📅 Subplots per Day", f"{subplots_per_day}")
        with col3:
            st.metric("💧 Total System Flow", f"{total_system_flow:.2f} m³/h")
        
        st.caption("⬇️ **Next Step**: Go to **Mainline Design** tab to design the mainline pipe sizing.")
        
        # Store flag indicating no submains
        st.session_state['no_submain_system'] = True
        
        return
    
    # ========================================================================
    # NORMAL CASE: System has submain lines
    # ========================================================================
    st.session_state['no_submain_system'] = False
    
    # Find farthest submain only
    farthest_submain = max(submain_lines, key=lambda x: x['distance_from_source'])
    farthest_submain_idx = submain_lines.index(farthest_submain)
    
    # Highlight only the farthest submain
    fig.add_trace(go.Scatter(
        x=farthest_submain['x'],
        y=farthest_submain['y'],
        mode='lines+markers',
        line=dict(color='rgba(255, 140, 0, 0.8)', width=12),
        marker=dict(size=12, color='orange', symbol='square'),
        name='🎯 FARTHEST SUBMAIN',
        hovertext=f"<b>Farthest Submain</b><br>" +
                 f"Length: {farthest_submain['length']:.1f} m<br>" +
                 f"Distance from source: {farthest_submain['distance_from_source']:.1f} m",
        hoverinfo='text',
        showlegend=True
    ))
    
    # Display the map
    st.plotly_chart(fig, width="stretch", key="submain_overview_map")
    
    # ============================================================================
    # SECTION 2: FLOW CALCULATION FOR EACH SUBMAIN
    # ============================================================================
    st.markdown("#### 💧 Flow Calculation - Individual Submains")
    
    # Get irrigation schedule data from operational design
    subplots_per_day_raw = operational_data.get('subplots_per_day', 1)
    total_subplots = operational_data.get('total_subplots', 1)
    total_irrigation_days = operational_data.get('total_irrigation_days', 1)
    subplot_discharge_m3h = operational_data.get('subplot_discharge', 0)
    
    # If subplot_discharge is 0, calculate from sprinkler data
    if subplot_discharge_m3h == 0:
        if 'sprinkler_data' in st.session_state.project_data:
            sprinkler = st.session_state.project_data['sprinkler_data']
            n_sprinklers_per_line = operational_data.get('n_sprinklers_per_line', 0)
            n_lines_per_subplot = operational_data.get('n_lines_per_subplot', 0)
            sprinkler_flow_lh = sprinkler.get('flow', 0)
            sprinkler_flow_m3h = sprinkler_flow_lh / 1000 if sprinkler_flow_lh > 0 else 0
            
            # Calculate subplot discharge = lateral flow = sprinklers per line × lines per subplot × flow per sprinkler
            if n_sprinklers_per_line > 0 and n_lines_per_subplot > 0 and sprinkler_flow_m3h > 0:
                subplot_discharge_m3h = n_sprinklers_per_line * n_lines_per_subplot * sprinkler_flow_m3h
                st.info(f"""
                ℹ️ **Calculated lateral/subplot flow from sprinkler data:**
                - Sprinklers per line: {n_sprinklers_per_line}
                - Lines per subplot: {n_lines_per_subplot}
                - Flow per sprinkler: {sprinkler_flow_m3h:.3f} m³/h
                - **Lateral flow (subplot discharge) = {subplot_discharge_m3h:.2f} m³/h**
                """)
            else:
                st.warning(f"""
                ⚠️ **Cannot calculate subplot flow - missing operational data:**
                - Sprinklers per line: {n_sprinklers_per_line}
                - Lines per subplot: {n_lines_per_subplot}
                - Sprinkler flow: {sprinkler_flow_lh} L/h ({sprinkler_flow_m3h:.3f} m³/h)
                """)
    
    # Ensure subplots per day doesn't exceed total subplots available
    subplots_per_day = min(subplots_per_day_raw, total_subplots)
    
    # Validation
    if subplot_discharge_m3h == 0:
        st.error("""
        ⚠️ **Missing Operational Design Data**
        
        Please complete these steps:
        1. Go to **Operational Design** tab
        2. Complete all calculations
        3. Click the **💾 Save Operational Design** button
        4. Return to this tab
        
        The system needs sprinkler count and layout data to calculate subplot flow.
        """)
        st.stop()
    
    # Show note if subplots per day was capped
    if subplots_per_day < subplots_per_day_raw:
        st.warning(f"""
        ℹ️ **Note**: Operational Design calculated capacity for {subplots_per_day_raw} subplots/day, 
        but only {total_subplots} subplots exist in the field. Using **{subplots_per_day} subplots/day** for calculations.
        """)
    
    st.info(f"""
    **Irrigation Schedule:**
    - Total subplots in field: {total_subplots}
    - Subplots irrigated per day: {subplots_per_day}
    - Total irrigation cycle: {int(total_irrigation_days)} days
    - Each subplot flow: {subplot_discharge_m3h:.2f} m³/h
    """)
    
    # Get valves from pipe network design
    valves = pipe_network_design.get('valves', [])
    
    # Helper function to detect valves along a submain line
    def count_valves_on_line(x_coords, y_coords, valves, tolerance=15.0):
        """Count valves that are on or near a line segment"""
        if len(x_coords) < 2 or not valves:
            return 0, []
        
        valves_on_line = []
        total_subplots = 0
        
        for valve in valves:
            vx, vy = valve['x'], valve['y']
            
            # Check distance to each segment of the polyline
            min_dist = float('inf')
            for i in range(len(x_coords) - 1):
                x1, y1 = x_coords[i], y_coords[i]
                x2, y2 = x_coords[i + 1], y_coords[i + 1]
                
                # Calculate perpendicular distance from point to line segment
                dx = x2 - x1
                dy = y2 - y1
                
                if dx == 0 and dy == 0:
                    # Point segment
                    dist = np.sqrt((vx - x1)**2 + (vy - y1)**2)
                else:
                    # Line segment
                    t = max(0, min(1, ((vx - x1) * dx + (vy - y1) * dy) / (dx * dx + dy * dy)))
                    proj_x = x1 + t * dx
                    proj_y = y1 + t * dy
                    dist = np.sqrt((vx - proj_x)**2 + (vy - proj_y)**2)
                
                min_dist = min(min_dist, dist)
            
            # If valve is close enough to the line, count it
            if min_dist <= tolerance:
                valves_on_line.append(valve)
                total_subplots += valve.get('subplots_served', 0)
        
        return total_subplots, valves_on_line
    
    # Calculate flow for EACH submain individually
    num_submains = len(submain_lines)
    
    # Check if we have valve data to use
    use_valve_detection = len(valves) > 0
    
    if not use_valve_detection:
        # Fallback: Distribute subplots equally across submains
        subplots_per_submain = total_subplots // num_submains
        remaining_subplots = total_subplots % num_submains
    
    # Show configuration for each submain
    for idx, submain in enumerate(submain_lines):
        # Calculate subplots served by this submain
        if use_valve_detection:
            # Detect valves along this submain line
            laterals_served, submain_valves = count_valves_on_line(submain['x'], submain['y'], valves, tolerance=20.0)
            valve_detection_note = f"✓ Detected {len(submain_valves)} valve(s) on this submain"
        else:
            # Equal distribution fallback
            laterals_served = subplots_per_submain + (1 if idx < remaining_subplots else 0)
            valve_detection_note = "⚠️ Using equal distribution (no valves placed)"
        
        # Mark if this is the farthest submain
        is_farthest = (idx == farthest_submain_idx)
        title_prefix = "🎯 **FARTHEST " if is_farthest else "**"
        
        # Calculate flow for this submain
        if laterals_served <= subplots_per_day:
            design_flow = laterals_served * subplot_discharge_m3h
            peak_flow = design_flow
            scenario_text = f"All {laterals_served} subplots operate simultaneously"
        else:
            design_flow = min(laterals_served, subplots_per_day) * subplot_discharge_m3h
            peak_flow = laterals_served * subplot_discharge_m3h
            scenario_text = f"Maximum {min(laterals_served, subplots_per_day)} subplots operate simultaneously"
        
        # Display configuration for this submain
        with st.expander(f"{title_prefix}Submain {idx + 1} Configuration**", expanded=is_farthest):
            st.caption(valve_detection_note)
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("📏 Length", f"{submain['length']:.1f} m")
                st.caption(f"Distance: {submain['distance_from_source']:.1f} m from source")
            
            with col2:
                st.metric("🌿 Subplots Served", f"{laterals_served}")
                st.caption(f"Out of {total_subplots} total subplots")
            
            with col3:
                st.metric("🌊 Design Flow", f"{design_flow:.2f} m³/h")
                st.caption(f"{min(laterals_served, subplots_per_day)} × {subplot_discharge_m3h:.2f} m³/h")
            
            if peak_flow > design_flow:
                st.info(f"""
                **Flow Scenarios:**
                - Design Flow: {design_flow:.2f} m³/h ({scenario_text})
                - Peak Flow: {peak_flow:.2f} m³/h (if all {laterals_served} subplots operated simultaneously)
                """)
            else:
                st.success(f"✅ {scenario_text} - Design Flow = Peak Flow")
    
    st.markdown("---")
    
    # Summary of all submains
    st.markdown("#### 📊 Submain System Summary")
    
    total_system_flow = min(total_subplots, subplots_per_day) * subplot_discharge_m3h
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Submains", f"{num_submains}")
        st.metric("Total System Flow", f"{total_system_flow:.2f} m³/h")
    with col2:
        st.metric("Subplots per Submain", f"~{total_subplots // num_submains}")
        st.metric("Operating Subplots", f"{min(total_subplots, subplots_per_day)}")
    
    st.markdown("---")
    
    # ============================================================================
    # SECTION 3: SELECT SUBMAIN FOR VARIABLE PIPE SIZING DESIGN
    # ============================================================================
    st.markdown("### 🔧 Variable Pipe Sizing Design")
    
    st.caption("Select a submain below to design its variable pipe sizing.")
    
    # Create submain data list with flow calculations
    submain_data_list = []
    for idx, submain in enumerate(submain_lines):
        # Calculate subplots served by this submain
        if use_valve_detection:
            laterals_served, submain_valves = count_valves_on_line(submain['x'], submain['y'], valves, tolerance=20.0)
        else:
            laterals_served = subplots_per_submain + (1 if idx < remaining_subplots else 0)
        
        # Calculate flow
        if laterals_served <= subplots_per_day:
            design_flow = laterals_served * subplot_discharge_m3h
        else:
            design_flow = min(laterals_served, subplots_per_day) * subplot_discharge_m3h
        
        is_farthest = (idx == farthest_submain_idx)
        
        submain_data_list.append({
            'index': idx,
            'submain': submain,
            'laterals_served': laterals_served,
            'design_flow': design_flow,
            'is_farthest': is_farthest
        })
    
    # Submain selection
    submain_options = []
    for data in submain_data_list:
        idx = data['index']
        prefix = "🎯 " if data['is_farthest'] else ""
        submain_options.append(
            f"{prefix}Submain {idx + 1}: {data['submain']['length']:.1f}m, "
            f"{data['laterals_served']} laterals, {data['design_flow']:.1f} m³/h"
        )
    
    # Default to farthest submain
    default_idx = next((i for i, data in enumerate(submain_data_list) if data['is_farthest']), 0)
    
    selected_submain_display = st.selectbox(
        "Select Submain to Design",
        range(len(submain_options)),
        format_func=lambda x: submain_options[x],
        index=default_idx,
        help="Choose which submain line to design with variable pipe sizing"
    )
    
    # Get selected submain data
    selected_data = submain_data_list[selected_submain_display]
    selected_submain = selected_data['submain']
    selected_submain_idx = selected_data['index']
    laterals_on_submain = selected_data['laterals_served']
    submain_length = selected_submain['length']
    
    st.markdown("---")
    
    # Detect laterals/valves on the selected submain
    laterals_on_submain, submain_valves = count_valves_on_line(
        selected_submain['x'], 
        selected_submain['y'], 
        valves, 
        tolerance=20.0
    )
    
    # Get subplot day assignments from operational design
    subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
    
    # Map valves to their subplot IDs based on spatial proximity
    # Valves store 'selected_subplots' (list) - determine irrigation days for each subplot
    valve_day_map = {}
    if subplot_day_assignments and submain_valves:
        # Get subplot spatial positions if available
        subplot_positions = {}
        
        # Try to get subplot positions from session state (created during field visualization)
        if 'subplot_positions' in st.session_state:
            subplot_positions = st.session_state.subplot_positions
        
        for valve in submain_valves:
            # Get all subplots this valve serves
            selected_subplots = valve.get('selected_subplots', [])
            
            # Determine days this valve operates on (could be multiple!)
            valve_operating_days = set()
            subplot_days_detail = {}  # subplot_id -> day
            
            if selected_subplots and len(selected_subplots) > 0:
                for subplot_id in selected_subplots:
                    day = subplot_day_assignments.get(subplot_id)
                    if day is not None:
                        valve_operating_days.add(day)
                        subplot_days_detail[subplot_id] = day
                
                # Store all operating days for this valve
                valve['operating_days'] = list(valve_operating_days)
                valve['subplot_days'] = subplot_days_detail
                
                # For backwards compatibility, set primary day (most common day)
                if valve_operating_days:
                    # Count subplots per day for this valve
                    day_counts = {}
                    for sp, d in subplot_days_detail.items():
                        day_counts[d] = day_counts.get(d, 0) + 1
                    primary_day = max(day_counts.keys(), key=lambda d: day_counts[d])
                    valve['irrigation_day'] = primary_day
                    valve['subplot_id'] = selected_subplots[0]
                else:
                    valve['irrigation_day'] = 'Not assigned'
                    valve['subplot_id'] = 'Unknown'
            else:
                # No selected_subplots - try to find by proximity
                if subplot_positions:
                    valve_x = valve.get('x', 0)
                    valve_y = valve.get('y', 0)
                    
                    if isinstance(valve_x, dict):
                        valve_x = 0
                    if isinstance(valve_y, dict):
                        valve_y = 0
                        
                    min_distance = float('inf')
                    primary_subplot_id = None
                    
                    for subplot_num, (sub_x, sub_y) in subplot_positions.items():
                        dist = ((valve_x - sub_x)**2 + (valve_y - sub_y)**2)**0.5
                        if dist < min_distance:
                            min_distance = dist
                            primary_subplot_id = subplot_num
                    
                    if primary_subplot_id:
                        valve['subplot_id'] = primary_subplot_id
                        day = subplot_day_assignments.get(primary_subplot_id)
                        if day is not None:
                            valve['irrigation_day'] = day
                            valve['operating_days'] = [day]
                        else:
                            valve['irrigation_day'] = 'Not assigned'
                            valve['operating_days'] = []
                    else:
                        valve['subplot_id'] = 'Unknown'
                        valve['irrigation_day'] = 'Not assigned'
                        valve['operating_days'] = []
                else:
                    valve['subplot_id'] = 'Unknown'
                    valve['irrigation_day'] = 'Not assigned'
                    valve['operating_days'] = []
    
    # Get lateral design data if available
    lateral_flow_m3h = None
    if 'temp_lateral_design' in st.session_state:
        lateral_flow_m3h = st.session_state.temp_lateral_design.get('total_flow_m3h')
    elif 'lateral_design' in st.session_state.project_data:
        lateral_flow_m3h = st.session_state.project_data['lateral_design'].get('total_flow_m3h')
    
    # Fallback: use subplot discharge
    if lateral_flow_m3h is None or lateral_flow_m3h == 0:
        lateral_flow_m3h = subplot_discharge_m3h
        log_info(f"Using subplot discharge as lateral flow: {lateral_flow_m3h:.2f} m³/h per lateral")
    else:
        log_info(f"Using lateral design flow: {lateral_flow_m3h:.2f} m³/h per lateral (from Lateral Design)")
    
    # If no valves detected, use spacing-based estimate
    if laterals_on_submain == 0:
        lateral_spacing = operational_data.get('spacing_between_lines', 15.0)
        laterals_on_submain = max(1, int(submain_length / lateral_spacing))
        st.warning(f"⚠️ No valves detected on submain. Estimated {laterals_on_submain} laterals based on {lateral_spacing}m spacing")
    
    # Allow override
    st.markdown(f"#### ⚙️ Configuration - Submain {selected_submain_idx + 1}")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Submain Length", f"{submain_length:.1f} m")
        lateral_spacing_display = submain_length / laterals_on_submain if laterals_on_submain > 0 else 0
        st.metric("Lateral Spacing", f"{lateral_spacing_display:.1f} m")
    with col2:
        n_laterals = st.number_input(
            "Laterals on Submain",
            min_value=1,
            max_value=50,
            value=laterals_on_submain,
            help="Number of lateral lines connected to this submain",
            key=f"n_laterals_submain_{selected_submain_idx}"
        )
        st.metric("Flow per Lateral", f"{lateral_flow_m3h:.2f} m³/h")
    with col3:
        st.metric("Total Submain Flow", f"{round(n_laterals * lateral_flow_m3h, 2)} m³/h")
        sprinkler_pressure = st.session_state.project_data.get('sprinkler_data', {}).get('pressure', 30)
        st.metric("Pressure Required", f"{sprinkler_pressure} m")
    
    # Variable pipe sizing
    st.markdown("#### 🔧 Variable Pipe Sizing Design")
    
    # Design mode selection
    design_mode_submain = st.radio(
        "Design Mode",
        ["Automatic (Optimized)", "Manual (Select Each Segment)"],
        help="Automatic mode selects optimal pipe sizes. Manual mode lets you choose diameters for each segment.",
        key=f"submain_design_mode_{selected_submain_idx}"
    )
    
    st.caption("Design Approach: Pipe diameter DECREASES from inlet to end (telescoping)")
    
    # Design parameters
    col1, col2 = st.columns(2)
    with col1:
        max_velocity = st.number_input("Maximum Velocity (m/s)", min_value=0.5, max_value=3.0, value=1.5, step=0.1, key=f'submain_vel_{selected_submain_idx}',
                                       help="Recommended: 1.0-2.0 m/s for PVC pipes")
        C_coefficient = st.number_input("Hazen-Williams C", min_value=100, max_value=150, value=130, step=5, key=f'submain_C_{selected_submain_idx}',
                                       help="C=130 for PVC, C=120 for older pipes")
    with col2:
        max_friction_loss = st.number_input("Max Friction Loss (%)", min_value=1.0, max_value=20.0, value=10.0, step=1.0, key=f'submain_friction_{selected_submain_idx}',
                                            help="Friction loss as % of operating pressure")
        min_velocity = st.number_input("Minimum Velocity (m/s)", min_value=0.3, max_value=1.5, value=0.6, step=0.1, key=f'submain_min_vel_{selected_submain_idx}',
                                      help="Minimum to prevent sediment buildup")
    
    # Show available pipe sizes
    with st.expander("📏 Available Pipe Sizes"):
        pipe_sizes = get_standard_pipe_sizes()
        df_sizes = pd.DataFrame(pipe_sizes)
        df_sizes.columns = ['Nominal Ø (mm)', 'Internal Ø (mm)']
        st.dataframe(df_sizes, width="stretch")
    
    # Calculate variable sizing
    calculate_submain_button = st.button("🔍 Calculate Submain Pipe Sizing", type="primary", key=f"calc_submain_{selected_submain_idx}")
    
    # Initialize session state for manual selections for this submain
    submain_manual_key = f'manual_submain_{selected_submain_idx}_pipe_selections'
    if submain_manual_key not in st.session_state:
        st.session_state[submain_manual_key] = {}
    
    # Manual selection interface
    if design_mode_submain == "Manual (Select Each Segment)":
        temp_design_key = f'temp_submain_{selected_submain_idx}_design'
        saved_design_key = f'submain_{selected_submain_idx}_design'
        
        if temp_design_key in st.session_state:
            previous_segments = st.session_state[temp_design_key].get('segments', [])
        elif saved_design_key in st.session_state.project_data:
            previous_segments = st.session_state.project_data[saved_design_key].get('segments', [])
        else:
            previous_segments = []
        
        if previous_segments and len(previous_segments) == n_laterals:
            st.markdown("---")
            st.markdown("#### 🎛️ Manual Pipe Selection")
            st.caption("Select pipe diameter for each segment, then click 'Calculate' to update.")
            
            pipe_sizes = get_standard_pipe_sizes()
            n_cols_display = min(5, n_laterals)
            cols = st.columns(n_cols_display)
            
            for i, seg in enumerate(previous_segments):
                col_idx = i % n_cols_display
                with cols[col_idx]:
                    segment_key = f"submain_seg_{seg['segment']}"
                    
                    pipe_options = [f"Ø{s['nominal']} mm" for s in pipe_sizes]
                    current_idx = next((idx for idx, s in enumerate(pipe_sizes) 
                                      if s['nominal'] == seg['pipe_nominal_mm']), 0)
                    
                    if segment_key not in st.session_state[submain_manual_key]:
                        st.session_state[submain_manual_key][segment_key] = current_idx
                    
                    st.markdown(f"**Seg {seg['segment']}**")
                    st.caption(f"Flow: {seg['flow_m3h']} m³/h")
                    if 'velocity_ms' in seg:
                        st.caption(f"V: {seg['velocity_ms']} m/s")
                    
                    selected_idx = st.selectbox(
                        "Pipe Size",
                        range(len(pipe_sizes)),
                        index=st.session_state[submain_manual_key][segment_key],
                        format_func=lambda x: pipe_options[x],
                        key=f"select_{segment_key}_sm{selected_submain_idx}",
                        label_visibility="collapsed"
                    )
                    
                    st.session_state[submain_manual_key][segment_key] = selected_idx
            
            st.markdown("---")
            
            # Save button for manual selections
            col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
            with col_save2:
                if st.button("💾 Save Pipe Selections", type="secondary", width="stretch", key=f"save_manual_submain_{selected_submain_idx}"):
                    st.success("✅ Pipe selections saved! Click 'Calculate' to update the design.")
    
    # Check if we should show results
    temp_design_key = f'temp_submain_{selected_submain_idx}_design'
    show_submain_results = calculate_submain_button or temp_design_key in st.session_state
    
    if calculate_submain_button:
        
        # Christiansen F-factor
        F = calculate_f_factor(n_laterals)
        
        segments = []
        cumulative_length = 0
        lateral_spacing_calc = submain_length / n_laterals if n_laterals > 0 else 15.0
        
        pipe_sizes = get_standard_pipe_sizes()
        
        # SMART FLOW CALCULATION CONSIDERING OPERATIONAL SCHEDULE
        # Calculate actual distance along submain line for each valve
        if submain_valves and len(submain_valves) > 0:
            # Get submain line coordinates
            submain_x = selected_submain.get('x', [])
            submain_y = selected_submain.get('y', [])
            
            # Ensure we have valid coordinate arrays
            if not isinstance(submain_x, list) or not isinstance(submain_y, list):
                submain_x = []
                submain_y = []
            
            if len(submain_x) < 2 or len(submain_y) < 2:
                st.error("Invalid submain coordinates - cannot calculate distances along line")
                return
            
            # Find the inlet point (where mainline connects to this submain)
            # PRIORITY: Use mainline valve position if available, else fall back to water source
            
            # Try to find mainline valve that connects to this submain
            inlet_point = None
            mainline_valves = []
            
            # Check multiple locations for mainline valves
            if 'pipe_network_state' in st.session_state:
                mainline_valves = st.session_state.pipe_network_state.get('network', {}).get('mainline_valves', [])
            if not mainline_valves and 'mainline_valve_table' in st.session_state:
                mainline_valves = st.session_state.mainline_valve_table
            if not mainline_valves:
                mainline_valves = pipe_network_design.get('network', {}).get('mainline_valves', [])
            
            # Find the mainline valve that serves this submain
            for mv in mainline_valves:
                submain_indices = mv.get('submain_indices', [])
                if not submain_indices:
                    single_idx = mv.get('submain_idx')
                    if single_idx is not None:
                        submain_indices = [single_idx]
                
                if selected_submain_idx in submain_indices:
                    # Found the mainline valve for this submain
                    inlet_point = (float(mv.get('x', 0)), float(mv.get('y', 0)))
                    log_debug(f"Found mainline valve for submain {selected_submain_idx + 1} at ({inlet_point[0]:.1f}, {inlet_point[1]:.1f})")
                    break
            
            # Fallback to water source if no mainline valve found
            if inlet_point is None:
                water_source = field_geometry.get('water_source_local', [0, 0])
                inlet_point = (float(water_source[0]), float(water_source[1]))
                log_debug(f"No mainline valve found for submain {selected_submain_idx + 1}, using water source as inlet")
            
            # Find which vertex of the submain line is closest to the inlet point
            inlet_idx = 0
            min_dist_to_inlet = float('inf')
            
            for i in range(len(submain_x)):
                try:
                    dx = float(submain_x[i]) - inlet_point[0]
                    dy = float(submain_y[i]) - inlet_point[1]
                    dist = (dx*dx + dy*dy)**0.5
                    if dist < min_dist_to_inlet:
                        min_dist_to_inlet = dist
                        inlet_idx = i
                except (ValueError, TypeError, IndexError):
                    continue
            
            log_debug(f"Inlet point found at vertex {inlet_idx} of submain line (distance {min_dist_to_inlet:.1f}m from inlet point)")
            
            # Function to find closest point on submain line and distance along line from inlet
            def get_distance_along_line(valve_x, valve_y, line_x, line_y, inlet_vertex_idx):
                """Calculate distance along the line from inlet to the point closest to the valve"""
                # Ensure inputs are numeric
                try:
                    valve_x = float(valve_x)
                    valve_y = float(valve_y)
                except (ValueError, TypeError):
                    return 0.0
                
                min_dist_to_line = float('inf')
                closest_segment_idx = 0
                closest_t = 0
                
                # Find which line segment the valve is closest to
                for i in range(len(line_x) - 1):
                    try:
                        x1, y1 = float(line_x[i]), float(line_y[i])
                        x2, y2 = float(line_x[i + 1]), float(line_y[i + 1])
                    except (ValueError, TypeError, IndexError):
                        continue
                    
                    # Vector from segment start to end
                    dx = x2 - x1
                    dy = y2 - y1
                    segment_length_sq = dx*dx + dy*dy
                    
                    if segment_length_sq > 0:
                        # Parameter t for projection onto line segment (0 to 1)
                        t = max(0, min(1, ((valve_x - x1) * dx + (valve_y - y1) * dy) / segment_length_sq))
                        
                        # Closest point on this segment
                        proj_x = x1 + t * dx
                        proj_y = y1 + t * dy
                        
                        # Distance from valve to this point
                        dist = ((valve_x - proj_x)**2 + (valve_y - proj_y)**2)**0.5
                        
                        if dist < min_dist_to_line:
                            min_dist_to_line = dist
                            closest_segment_idx = i
                            closest_t = t
                
                # Calculate distance from inlet to the valve's closest point
                # Need to handle case where inlet might not be at start or end
                distance_along_line = 0.0
                
                if closest_segment_idx >= inlet_vertex_idx:
                    # Valve is "downstream" from inlet (later in the line array)
                    # Add length from inlet to start of closest segment
                    for i in range(inlet_vertex_idx, closest_segment_idx):
                        try:
                            dx = float(line_x[i+1]) - float(line_x[i])
                            dy = float(line_y[i+1]) - float(line_y[i])
                            distance_along_line += (dx*dx + dy*dy)**0.5
                        except (ValueError, TypeError, IndexError):
                            continue
                    
                    # Add partial length within the closest segment
                    if closest_segment_idx < len(line_x) - 1:
                        try:
                            dx = float(line_x[closest_segment_idx+1]) - float(line_x[closest_segment_idx])
                            dy = float(line_y[closest_segment_idx+1]) - float(line_y[closest_segment_idx])
                            segment_length = (dx*dx + dy*dy)**0.5
                            distance_along_line += closest_t * segment_length
                        except (ValueError, TypeError, IndexError):
                            pass
                else:
                    # Valve is "upstream" from inlet (earlier in the line array)
                    # Go backwards from inlet
                    for i in range(inlet_vertex_idx - 1, closest_segment_idx, -1):
                        try:
                            dx = float(line_x[i+1]) - float(line_x[i])
                            dy = float(line_y[i+1]) - float(line_y[i])
                            distance_along_line += (dx*dx + dy*dy)**0.5
                        except (ValueError, TypeError, IndexError):
                            continue
                    
                    # Add partial length within the closest segment
                    if closest_segment_idx < len(line_x) - 1:
                        try:
                            dx = float(line_x[closest_segment_idx+1]) - float(line_x[closest_segment_idx])
                            dy = float(line_y[closest_segment_idx+1]) - float(line_y[closest_segment_idx])
                            segment_length = (dx*dx + dy*dy)**0.5
                            distance_along_line += (1 - closest_t) * segment_length
                        except (ValueError, TypeError, IndexError):
                            pass
                
                return distance_along_line
            
            # Calculate distance along submain line for each valve
            for valve in submain_valves:
                # Ensure valve has x and y as numbers (not dicts)
                valve_x = valve.get('x', 0)
                valve_y = valve.get('y', 0)
                
                # Handle case where x or y might be stored as a dict or other non-numeric type
                if not isinstance(valve_x, (int, float)):
                    valve_x = 0
                if not isinstance(valve_y, (int, float)):
                    valve_y = 0
                
                valve['distance_along_line'] = get_distance_along_line(
                    valve_x, valve_y, submain_x, submain_y, inlet_idx
                )
            
            # Sort valves by distance along the line (closest to start first)
            sorted_valves = sorted(submain_valves, key=lambda v: float(v.get('distance_along_line', 0)))
            
            # WORKAROUND: If all valves are at the same position, distribute them evenly
            unique_positions = set(v.get('distance_along_line', 0) for v in sorted_valves)
            if len(unique_positions) == 1 and len(sorted_valves) > 1:
                st.warning(f"⚠️ All {len(sorted_valves)} valves appear to be at the same position. Using lateral spacing ({lateral_spacing_calc:.1f}m) to distribute them.")
                # Calculate total submain length
                total_submain_length = 0
                for i in range(len(submain_x) - 1):
                    try:
                        dx = float(submain_x[i+1]) - float(submain_x[i])
                        dy = float(submain_y[i+1]) - float(submain_y[i])
                        total_submain_length += (dx*dx + dy*dy)**0.5
                    except (ValueError, TypeError, IndexError):
                        continue
                
                # Distribute valves evenly based on lateral spacing
                for i, valve in enumerate(sorted_valves):
                    valve['distance_along_line'] = i * lateral_spacing_calc
                    if valve['distance_along_line'] > total_submain_length:
                        valve['distance_along_line'] = total_submain_length * (i / len(sorted_valves))

            
            # Group valves by physical position (merge valves at same location)
            # Increased tolerance to handle valves placed at similar positions
            position_tolerance = 10.0  # meters - valves within 10m are considered at same position
            valve_groups = []
            
            i = 0
            while i < len(sorted_valves):
                current_position = float(sorted_valves[i].get('distance_along_line', 0))
                group = [sorted_valves[i]]
                
                # Add all valves at approximately the same position to this group
                j = i + 1
                while j < len(sorted_valves):
                    valve_position = float(sorted_valves[j].get('distance_along_line', 0))
                    if abs(valve_position - current_position) <= position_tolerance:
                        group.append(sorted_valves[j])
                        j += 1
                    else:
                        break
                
                # Use the average position of all valves in the group
                avg_position = sum(float(v.get('distance_along_line', 0)) for v in group) / len(group)
                
                valve_groups.append({
                    'position': avg_position,
                    'valves': group,
                    'count': len(group)
                })
                
                i = j
            
            # Calculate segment-by-segment flow based on operational schedule
            log_debug(f"Smart Flow Calculation: {len(valve_groups)} connection point(s) with {len(sorted_valves)} total valves on this submain")
            
            # DEBUG: Show valve distances
            with st.expander("🔍 Valve Positions (Debug)", expanded=False):
                st.write(f"**Submain line**: {len(submain_x)} vertices")
                st.write(f"**Inlet source**: ({inlet_point[0]:.1f}, {inlet_point[1]:.1f})")
                st.write(f"**Inlet vertex**: {inlet_idx} at ({submain_x[inlet_idx]:.1f}, {submain_y[inlet_idx]:.1f})")
                st.write("---")
                for i, valve in enumerate(sorted_valves):
                    valve_x = valve.get('x', 0)
                    valve_y = valve.get('y', 0)
                    if isinstance(valve_x, (int, float)) and isinstance(valve_y, (int, float)):
                        st.write(f"Valve {i+1}: Position ({valve_x:.1f}, {valve_y:.1f}) → Distance = {valve.get('distance_along_line', 0):.2f}m along line")
                    else:
                        st.write(f"Valve {i+1}: Invalid coordinates (x={type(valve_x).__name__}, y={type(valve_y).__name__})")
                st.write("---")
                st.write(f"**Submain vertices:**")
                for i in range(len(submain_x)):
                    st.write(f"  Vertex {i}: ({submain_x[i]:.1f}, {submain_y[i]:.1f})")
            
            # Show valve schedule breakdown with per-subplot day info
            with st.expander("🔍 View Valve Schedule Analysis"):
                for group_idx, group in enumerate(valve_groups):
                    st.markdown(f"**Connection Point {group_idx + 1}** at {group['position']:.1f}m:")
                    for valve in group['valves']:
                        selected_subplots = valve.get('selected_subplots', [])
                        subplot_days = valve.get('subplot_days', {})
                        operating_days = valve.get('operating_days', [])
                        
                        if selected_subplots and subplot_days:
                            # Show each subplot with its day
                            subplot_details = []
                            for sp in selected_subplots:
                                day = subplot_days.get(sp, '?')
                                subplot_details.append(f"Plot {sp} (Day {day})")
                            st.write(f"  • Valve: {', '.join(subplot_details)}")
                            if len(operating_days) > 1:
                                st.write(f"    ⚠️ This valve serves subplots on **multiple days**: {operating_days}")
                        elif selected_subplots:
                            # Have subplots but no day mapping
                            irr_day = valve.get('irrigation_day', 'Not assigned')
                            subplots_str = ', '.join(map(str, selected_subplots))
                            st.write(f"  • Valve: Subplot(s) {subplots_str}, Day {irr_day}")
                        else:
                            subplot_id = valve.get('subplot_id', 'Unknown')
                            irr_day = valve.get('irrigation_day', 'Not assigned')
                            st.write(f"  • Valve: Subplot {subplot_id}, Day {irr_day}")
            
            # Build segments between connection points (not individual valves)
            n_connection_points = len(valve_groups)
            segments_data = []
            
            # FLOW CALCULATION BASED ON VALVE ASSIGNMENTS
            # Each valve represents actual flow demand at that connection point
            # For accurate results, place a valve at each grid intersection (1-2 plots per valve)
            
            # Minimum segment length - skip segments shorter than this
            MIN_SEGMENT_LENGTH = 5.0  # meters
            
            # Create segment for each section between connection points
            # Skip the first segment if the first valve group is at/near the inlet
            first_valve_near_inlet = valve_groups[0]['position'] < MIN_SEGMENT_LENGTH if valve_groups else False
            
            segment_num = 0
            for i in range(n_connection_points):
                # Determine segment boundaries
                if i == 0:
                    # First segment: from inlet (0m) to first connection point
                    segment_start_dist = 0
                    segment_end_dist = valve_groups[i]['position']
                else:
                    # Subsequent segments: from previous connection point to current one
                    segment_start_dist = valve_groups[i-1]['position']
                    segment_end_dist = valve_groups[i]['position']
                
                segment_length = segment_end_dist - segment_start_dist
                
                # Skip very short segments (valves at same/similar positions)
                if segment_length < MIN_SEGMENT_LENGTH:
                    continue
                
                segment_num += 1
                
                # Calculate maximum concurrent flow for THIS segment
                # This segment must carry flow for ALL valves from connection point i to the end
                downstream_valve_groups = valve_groups[i:]
                
                # Flatten all downstream valves
                all_downstream_valves = []
                for vg in downstream_valve_groups:
                    all_downstream_valves.extend(vg['valves'])
                
                # Group downstream SUBPLOTS by irrigation day
                # IMPORTANT: A single valve can serve subplots on DIFFERENT days!
                valves_per_day = {}
                subplots_per_day_dict = {}  # Count SUBPLOTS per day
                
                for valve in all_downstream_valves:
                    selected_subplots = valve.get('selected_subplots', [])
                    
                    if selected_subplots and subplot_day_assignments:
                        # Check each subplot this valve serves and assign to correct day
                        for subplot_id in selected_subplots:
                            day = subplot_day_assignments.get(subplot_id)
                            if day is not None:
                                if day not in subplots_per_day_dict:
                                    subplots_per_day_dict[day] = 0
                                subplots_per_day_dict[day] += 1
                                
                                # Track valves per day (a valve counts for a day if any subplot is on that day)
                                if day not in valves_per_day:
                                    valves_per_day[day] = set()
                                valves_per_day[day].add(id(valve))
                    else:
                        # Fallback: use valve's irrigation_day if no subplot list
                        day = valve.get('irrigation_day', None)
                        if day and day != 'Not assigned':
                            if day not in subplots_per_day_dict:
                                subplots_per_day_dict[day] = 0
                            subplots_per_day_dict[day] += 1  # Count as 1 subplot
                            
                            if day not in valves_per_day:
                                valves_per_day[day] = set()
                            valves_per_day[day].add(id(valve))
                
                # Convert valve sets to counts
                valves_per_day = {day: len(valves) for day, valves in valves_per_day.items()}
                
                # Maximum concurrent laterals = max SUBPLOTS operating on any single day
                if subplots_per_day_dict:
                    max_concurrent_laterals = max(subplots_per_day_dict.values())
                    days_served = len(subplots_per_day_dict)
                elif valves_per_day:
                    # Fallback to counting valves if subplot count not available
                    max_concurrent_laterals = max(valves_per_day.values())
                    days_served = len(valves_per_day)
                else:
                    # Fallback if no day assignments - COUNT ACTUAL SUBPLOTS
                    total_subplots_downstream = 0
                    for valve in all_downstream_valves:
                        selected_subplots = valve.get('selected_subplots', [])
                        total_subplots_downstream += len(selected_subplots) if selected_subplots else 1
                    max_concurrent_laterals = total_subplots_downstream
                    days_served = 1
                
                # Segment flow = max concurrent laterals × flow per lateral
                segment_flow_m3h = max_concurrent_laterals * lateral_flow_m3h
                
                # Create valve label for this connection point
                valve_labels = []
                for valve in valve_groups[i]['valves']:
                    selected_subplots = valve.get('selected_subplots', [])
                    if selected_subplots:
                        valve_labels.append(f"V(Subplots {','.join(map(str, selected_subplots))})")
                    else:
                        subplot_id = valve.get('subplot_id', '?')
                        valve_labels.append(f"V{subplot_id}")
                
                valve_label_str = " & ".join(valve_labels) if valve_labels else f"V{segment_num}"
                
                # Count total subplots downstream (for debugging display)
                total_subplots_downstream = 0
                for valve in all_downstream_valves:
                    selected_subplots = valve.get('selected_subplots', [])
                    total_subplots_downstream += len(selected_subplots) if selected_subplots else 1
                
                segments_data.append({
                    'segment_num': segment_num,
                    'start_dist': segment_start_dist,
                    'end_dist': segment_end_dist,
                    'length': segment_length,
                    'downstream_valves': len(all_downstream_valves),
                    'downstream_subplots': total_subplots_downstream,  # Total subplots downstream
                    'max_concurrent': max_concurrent_laterals,
                    'downstream_days': days_served,
                    'valves_per_day': valves_per_day,  # For debugging
                    'subplots_per_day_dict': subplots_per_day_dict,  # For debugging
                    'flow_m3h': segment_flow_m3h,
                    'valve_label': valve_label_str  # Valve label for visualization
                })
            
            # Show flow calculation breakdown
            with st.expander("📐 Segment Flow Calculation Breakdown"):
                for seg in segments_data:
                    st.markdown(f"**Segment {seg['segment_num']}**: {seg['start_dist']:.1f}m → {seg['end_dist']:.1f}m")
                    st.write(f"• **Length**: {seg['length']:.1f}m")
                    st.write(f"• Downstream: {seg['downstream_valves']} valves serving **{seg['downstream_subplots']} subplots**")
                    
                    if seg.get('subplots_per_day_dict'):
                        st.write("• **Subplots by day** (used for flow calculation):")
                        for day, count in sorted(seg['subplots_per_day_dict'].items()):
                            valve_count = seg.get('valves_per_day', {}).get(day, 0)
                            st.write(f"  - Day {day}: **{count} subplot(s)** from {valve_count} valve(s)")
                    elif seg.get('valves_per_day'):
                        st.write("• Valves by day:")
                        for day, count in sorted(seg['valves_per_day'].items()):
                            st.write(f"  - Day {day}: {count} valve(s)")
                    
                    st.write(f"• **Max concurrent**: {seg['max_concurrent']} subplots (worst case = Day with most subplots)")
                    st.write(f"• **Segment flow**: {seg['flow_m3h']:.2f} m³/h = {seg['max_concurrent']} subplots × {lateral_flow_m3h:.2f} m³/h/subplot")
                    st.markdown("---")
            
        else:
            # Fallback: No valve data - use simple uniform spacing
            st.warning("⚠️ No valve schedule data available. Using uniform spacing assumption.")
            lateral_spacing_calc = submain_length / n_laterals if n_laterals > 0 else 15.0
            segments_data = []
            for i in range(n_laterals):
                segment_flow_m3h = (n_laterals - i) * lateral_flow_m3h
                segments_data.append({
                    'segment_num': i + 1,
                    'start_dist': i * lateral_spacing_calc,
                    'end_dist': (i + 1) * lateral_spacing_calc,
                    'length': lateral_spacing_calc,
                    'downstream_valves': n_laterals - i,
                    'max_concurrent': n_laterals - i,
                    'downstream_days': 1,
                    'flow_m3h': segment_flow_m3h
                })
        
        # Now design pipes for each segment
        for seg_data in segments_data:
            i = seg_data['segment_num'] - 1
            segment_num = seg_data['segment_num']
            segment_length = seg_data['length']
            segment_flow_m3h = seg_data['flow_m3h']
            
            # Apply F-factor
            segment_flow = segment_flow_m3h * F
            
            cumulative_length += segment_length
            
            # Automatic or Manual pipe selection
            if design_mode_submain == "Manual (Select Each Segment)":
                segment_key = f"submain_seg_{i + 1}"
                submain_manual_key = f'manual_submain_{selected_submain_idx}_pipe_selections'
                
                # Find optimal size as default
                optimal_size = None
                for size in pipe_sizes:
                    D_mm = size['internal']
                    D_m = D_mm / 1000
                    Q_m3s = segment_flow / 3600
                    area = 3.14159 * (D_m / 2) ** 2
                    velocity = Q_m3s / area if area > 0 else 999
                    
                    if min_velocity <= velocity <= max_velocity:
                        optimal_size = size
                        break
                
                if optimal_size is None:
                    optimal_size = pipe_sizes[0]
                
                default_idx = next((idx for idx, s in enumerate(pipe_sizes) if s['nominal'] == optimal_size['nominal']), 0)
                
                if segment_key not in st.session_state[submain_manual_key]:
                    st.session_state[submain_manual_key][segment_key] = default_idx
                
                selected_idx = st.session_state[submain_manual_key][segment_key]
                selected_size = pipe_sizes[selected_idx]
            
            else:
                # TELESCOPING ALGORITHM - Find smallest pipe where velocity <= max_velocity
                selected_size = None
                for size in pipe_sizes:
                    D_mm = size['internal']
                    D_m = D_mm / 1000
                    
                    Q_m3s = segment_flow / 3600
                    area = 3.14159 * (D_m / 2) ** 2
                    velocity = Q_m3s / area if area > 0 else 0
                    
                    if velocity <= max_velocity:
                        if velocity >= min_velocity:
                            selected_size = size
                            break
                        else:
                            selected_size = size
                            break
                
                if selected_size is None:
                    selected_size = pipe_sizes[-1]
            
            hf_segment = calculate_hazen_williams(segment_flow, selected_size['internal'], segment_length, C_coefficient)
            
            D_m = selected_size['internal'] / 1000
            Q_m3s = segment_flow / 3600
            area = 3.14159 * (D_m / 2) ** 2
            velocity = Q_m3s / area if area > 0 else 0
            
            distance_from_inlet = cumulative_length - segment_length
            
            # Position description
            if segment_num == 1:
                position = f"Inlet → Valve 1"
            else:
                position = f"Valve {segment_num - 1} → Valve {segment_num}"
            
            # Include smart flow calculation data
            # Note: flow_m3h = design flow (with F-factor for pipe sizing)
            #       full_flow_m3h = total flow without F-factor (for mainline calculation)
            segments.append({
                'segment': segment_num,
                'position': position,
                'valve_label': seg_data.get('valve_label', f"V{segment_num}"),  # Actual valve label
                'length_m': segment_length,
                'distance_from_inlet_m': round(distance_from_inlet, 1),
                'n_laterals_downstream': seg_data.get('downstream_valves', 0),
                'max_concurrent_laterals': seg_data.get('max_concurrent', 0),
                'downstream_days': seg_data.get('downstream_days', 1),
                'flow_m3h': round(segment_flow, 3),  # Design flow (with F-factor)
                'full_flow_m3h': round(segment_flow_m3h, 3),  # Full flow (without F-factor) for mainline
                'pipe_nominal_mm': selected_size['nominal'],
                'pipe_internal_mm': selected_size['internal'],
                'velocity_ms': round(velocity, 2),
                'friction_loss_m': round(hf_segment, 3)
            })
        
        total_friction_loss = sum(seg['friction_loss_m'] for seg in segments)
        friction_loss_pct = (total_friction_loss / sprinkler_pressure) * 100 if sprinkler_pressure > 0 else 0
        
        max_velocity_observed = max(seg['velocity_ms'] for seg in segments) if segments else 0
        min_velocity_observed = min(seg['velocity_ms'] for seg in segments) if segments else 0
        velocity_ok = min_velocity <= min_velocity_observed and max_velocity_observed <= max_velocity
        friction_ok = friction_loss_pct <= max_friction_loss
        
        total_flow_m3h = segments[0]['flow_m3h'] if segments else 0
        # Full inlet flow (without F-factor) for mainline design
        full_inlet_flow_m3h = segments[0]['full_flow_m3h'] if segments else 0
        
        # Calculate which irrigation days this submain operates on
        # This is critical for mainline design to determine concurrent operation
        submain_operating_days = set()
        submain_day_flows = {}  # day -> flow contribution
        if submain_valves:
            for valve in submain_valves:
                # Get all subplots this valve serves and their days
                selected_subplots = valve.get('selected_subplots', [])
                subplot_days = valve.get('subplot_days', {})
                
                if selected_subplots and subplot_days:
                    # Count each subplot for its specific day
                    for subplot_id in selected_subplots:
                        day = subplot_days.get(subplot_id)
                        if day is not None:
                            submain_operating_days.add(day)
                            if day not in submain_day_flows:
                                submain_day_flows[day] = 0
                            submain_day_flows[day] += 1  # Count subplot
                elif selected_subplots and subplot_day_assignments:
                    # Fallback: look up days from global assignments
                    for subplot_id in selected_subplots:
                        day = subplot_day_assignments.get(subplot_id)
                        if day is not None:
                            submain_operating_days.add(day)
                            if day not in submain_day_flows:
                                submain_day_flows[day] = 0
                            submain_day_flows[day] += 1
                else:
                    # Fallback: use valve's irrigation_day
                    irr_day = valve.get('irrigation_day')
                    if irr_day and irr_day != 'Not assigned':
                        submain_operating_days.add(irr_day)
                        num_subplots = len(selected_subplots) if selected_subplots else 1
                        if irr_day not in submain_day_flows:
                            submain_day_flows[irr_day] = 0
                        submain_day_flows[irr_day] += num_subplots
        
        # Determine primary operating day (day with most subplots served)
        primary_operating_day = None
        if submain_day_flows:
            primary_operating_day = max(submain_day_flows.keys(), key=lambda d: submain_day_flows[d])
        
        # Save results to temp state (per submain)
        temp_design_key = f'temp_submain_{selected_submain_idx}_design'
        st.session_state[temp_design_key] = {
            'submain_index': selected_submain_idx,
            'segments': segments,
            'total_length_m': cumulative_length,
            'total_flow_m3h': round(total_flow_m3h, 3),
            'full_inlet_flow_m3h': round(full_inlet_flow_m3h, 3),  # Full flow for mainline design
            'total_friction_loss_m': round(total_friction_loss, 3),
            'friction_loss_pct': round(friction_loss_pct, 2),
            'F_factor': round(F, 4),
            'max_velocity_ms': max_velocity,
            'min_velocity_ms': min_velocity,
            'max_velocity_observed': round(max_velocity_observed, 2),
            'min_velocity_observed': round(min_velocity_observed, 2),
            'C_coefficient': C_coefficient,
            'design_mode': design_mode_submain,
            'n_laterals': n_laterals,
            'lateral_spacing': lateral_spacing_calc,
            'lateral_flow_m3h': lateral_flow_m3h,
            'operating_days': list(submain_operating_days),  # Days this submain operates on
            'primary_operating_day': primary_operating_day,  # Main day (for flow allocation)
            'day_flows': submain_day_flows  # Breakdown by day
        }
    
    # DISPLAY RESULTS SECTION
    temp_design_key = f'temp_submain_{selected_submain_idx}_design'
    if show_submain_results and temp_design_key in st.session_state:
        design_data = st.session_state[temp_design_key]
        segments = design_data['segments']
        total_friction_loss = design_data['total_friction_loss_m']
        friction_loss_pct = design_data['friction_loss_pct']
        max_velocity_observed = design_data['max_velocity_observed']
        min_velocity_observed = design_data['min_velocity_observed']
        max_velocity = design_data['max_velocity_ms']
        min_velocity = design_data['min_velocity_ms']
        cumulative_length = design_data['total_length_m']
        F = design_data['F_factor']
        C_coefficient = design_data['C_coefficient']
        submain_index = design_data['submain_index']
        design_mode_submain = design_data.get('design_mode', 'Automatic (Optimized)')
        n_laterals = design_data.get('n_laterals', len(segments))
        lateral_spacing_calc = design_data.get('lateral_spacing', 15.0)
        lateral_flow_m3h = design_data.get('lateral_flow_m3h', 0)
        
        velocity_ok = min_velocity <= min_velocity_observed and max_velocity_observed <= max_velocity
        friction_ok = friction_loss_pct <= max_friction_loss
        
        # Display status indicators with save button
        status_col1, status_col2, status_col3, status_col4 = st.columns([2, 2, 2, 1])
        with status_col1:
            if friction_ok:
                st.success(f"✅ Friction Loss: {total_friction_loss:.2f} m ({friction_loss_pct:.1f}%)")
            else:
                st.error(f"❌ Friction Loss: {total_friction_loss:.2f} m ({friction_loss_pct:.1f}%) - EXCEEDS {max_friction_loss}%")
        
        with status_col2:
            if velocity_ok:
                st.success(f"✅ Velocity: {min_velocity_observed:.2f}-{max_velocity_observed:.2f} m/s")
            else:
                st.warning(f"⚠️ Velocity: {min_velocity_observed:.2f}-{max_velocity_observed:.2f} m/s - CHECK LIMITS")
        
        with status_col3:
            if friction_ok and velocity_ok:
                st.success("✅ Design OK")
            else:
                st.warning("⚠️ Design needs adjustment")
        
        with status_col4:
            saved_design_key = f'submain_{selected_submain_idx}_design'
            if st.button("💾 Save", type="primary", width="stretch", key=f"save_submain_{selected_submain_idx}"):
                st.session_state.project_data[saved_design_key] = st.session_state[temp_design_key].copy()
                st.success(f"✅ Submain {selected_submain_idx + 1} Design Saved!")
        
        # Tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Visual Diagram",
            "📈 Performance Analysis",
            "📋 Detailed Table",
            "💡 Advisory"
        ])
        
        with tab1:
            st.markdown("##### Submain Line - Variable Pipe Sizing Diagram")
            fig_diagram = create_submain_line_diagram(segments, lateral_spacing_calc)
            st.plotly_chart(fig_diagram, width="stretch", key=f"submain_diagram_{selected_submain_idx}")
        
        with tab2:
            fig_perf = create_performance_charts(segments)
            st.plotly_chart(fig_perf, width="stretch", key=f"submain_perf_{selected_submain_idx}")
        
        with tab3:
            st.markdown("##### Detailed Segment Information")
            df = pd.DataFrame(segments)
            
            if 'distance_from_inlet_m' not in df.columns and len(segments) > 0:
                distances = []
                cumulative = 0
                for seg in segments:
                    distances.append(cumulative)
                    cumulative += seg.get('length_m', 0)
                df['distance_from_inlet_m'] = distances
            
            display_columns = {
                'segment': 'Seg #',
                'position': 'Position',
                'distance_from_inlet_m': 'Distance (m)',
                'length_m': 'Length (m)',
                'n_laterals_downstream': 'Total Valves',
                'max_concurrent_laterals': 'Max Concurrent',
                'downstream_days': 'Days Served',
                'flow_m3h': 'Flow (m³/h)',
                'pipe_nominal_mm': 'Pipe Ø (mm)',
                'velocity_ms': 'Velocity (m/s)',
                'friction_loss_m': 'Friction Loss (m)'
            }
            
            available_columns = {k: v for k, v in display_columns.items() if k in df.columns}
            df_display = df[list(available_columns.keys())].copy()
            df_display.columns = list(available_columns.values())
            
            def highlight_velocity(row):
                vel = row['Velocity (m/s)']
                if vel < min_velocity:
                    return ['background-color: #fff3cd'] * len(row)
                elif vel > max_velocity:
                    return ['background-color: #f8d7da'] * len(row)
                else:
                    return ['background-color: #d4edda'] * len(row)
            
            # Format numeric columns to max 2 decimal places
            format_dict = {col: '{:.2f}' for col in df_display.select_dtypes(include=['float64', 'float32', 'number']).columns}
            
            st.dataframe(
                df_display.style.apply(highlight_velocity, axis=1).format(format_dict),
                width="stretch",
                height=400
            )
            
            # Summary metrics
            st.markdown("##### Summary")
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("Total Length", f"{cumulative_length:.1f} m")
            with col2:
                total_flow = segments[0]['flow_m3h'] if segments else 0
                st.metric("Total Flow", f"{total_flow:.2f} m³/h")
            with col3:
                st.metric("Friction Loss", f"{total_friction_loss:.3f} m")
            with col4:
                st.metric("Velocity Range", f"{min_velocity_observed:.2f}-{max_velocity_observed:.2f} m/s")
            with col5:
                unique_sizes = len(set(seg['pipe_nominal_mm'] for seg in segments))
                st.metric("Pipe Sizes Used", f"{unique_sizes}")
        
        with tab4:
            st.markdown("##### 💡 Design Advisory")
            
            # Show intelligent flow calculation summary
            st.info("""
            🧠 **Smart Flow Calculation Active**
            
            This design considers your operational irrigation schedule:
            - Each segment's flow is based on **maximum concurrent laterals** on any single day
            - NOT based on total laterals (which would assume all operate simultaneously)
            - Results in optimized pipe sizing that matches actual operating conditions
            """)
            
            advisories = []
            
            if friction_loss_pct > max_friction_loss:
                advisories.append({
                    'type': 'error',
                    'message': f"❌ **Friction Loss Exceeded**: {friction_loss_pct:.1f}% > {max_friction_loss}%",
                    'recommendation': "Consider using larger pipe diameters for high-flow segments (closer to inlet)."
                })
            elif friction_loss_pct > max_friction_loss * 0.8:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Friction Loss High**: {friction_loss_pct:.1f}% (80% of limit)",
                    'recommendation': "Design is acceptable but operating near limits."
                })
            else:
                advisories.append({
                    'type': 'success',
                    'message': f"✅ **Friction Loss OK**: {friction_loss_pct:.1f}% < {max_friction_loss}%",
                    'recommendation': "Friction loss is within acceptable limits."
                })
            
            if max_velocity_observed > max_velocity:
                advisories.append({
                    'type': 'error',
                    'message': f"❌ **Velocity Exceeded**: {max_velocity_observed:.2f} m/s > {max_velocity:.2f} m/s",
                    'recommendation': "Increase pipe diameter in high-velocity segments."
                })
            elif max_velocity_observed > max_velocity * 0.9:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Velocity High**: {max_velocity_observed:.2f} m/s (90% of limit)",
                    'recommendation': "Consider larger pipes for segments near velocity limit."
                })
            
            if min_velocity_observed < min_velocity:
                advisories.append({
                    'type': 'warning',
                    'message': f"⚠️ **Velocity Too Low**: {min_velocity_observed:.2f} m/s < {min_velocity:.2f} m/s",
                    'recommendation': "Low velocity may cause sediment buildup. Consider smaller pipes in low-flow segments."
                })
            
            for adv in advisories:
                if adv['type'] == 'error':
                    st.error(f"{adv['message']}\n\n💡 {adv['recommendation']}")
                elif adv['type'] == 'warning':
                    st.warning(f"{adv['message']}\n\n💡 {adv['recommendation']}")
                else:
                    st.success(adv['message'])
            
            st.markdown("---")
            st.markdown("##### 📋 Design Parameters Used")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"- Laterals: {n_laterals}")
                st.write(f"- Lateral spacing: {lateral_spacing_calc:.1f} m")
                st.write(f"- Flow per lateral: {lateral_flow_m3h:.2f} m³/h")
                st.write(f"- F-factor (Christiansen): {F:.4f}")
            with col2:
                st.write(f"- Hazen-Williams C: {C_coefficient}")
                st.write(f"- Max velocity: {max_velocity:.2f} m/s")
                st.write(f"- Min velocity: {min_velocity:.2f} m/s")
                st.write(f"- Design mode: {design_mode_submain}")
    
    st.markdown("---")
    
    # Show subplot distribution and schedule (original content)
    if laterals_on_submain > 0:
        st.markdown("#### 📋 Subplot Distribution")
        st.write(f"This submain serves **{laterals_on_submain} subplots** (laterals)")
        
        if laterals_on_submain <= subplots_per_day:
            st.success(f"✅ All {laterals_on_submain} subplots can operate simultaneously within the {subplots_per_day} subplots/day capacity")
        else:
            days_needed = int(np.ceil(laterals_on_submain / subplots_per_day))
            st.caption(f"Subplots operate in rotation: {days_needed} days needed to irrigate all {laterals_on_submain} subplots ({subplots_per_day} per day)")
            
            with st.expander("🗓️ View Irrigation Schedule Breakdown", expanded=False):
                for day in range(1, days_needed + 1):
                    start_idx = (day - 1) * subplots_per_day
                    end_idx = min(day * subplots_per_day, laterals_on_submain)
                    subplots_this_day = end_idx - start_idx
                    flow_this_day = subplots_this_day * subplot_discharge_m3h
                    
                    st.write(f"**Day {day}**: Subplots {start_idx + 1}-{end_idx} operate ({subplots_this_day} subplots × {subplot_discharge_m3h:.2f} m³/h = {flow_this_day:.2f} m³/h)")



def show_mainline_design():
    """Design mainline with segment-by-segment flow calculation based on mainline valves"""
    st.markdown('<h2 class="sub-header">Mainline Design</h2>', unsafe_allow_html=True)
    
    # Measurement Tool
    col_meas1, col_meas2, col_meas3 = st.columns([2, 2, 3])
    with col_meas1:
        if st.button("📏 Measure Distance", key="measure_tool_mainline", help="Activate measurement on the map below"):
            drawing_state = st.session_state.get('drawing_state', {})
            drawing_state['mode'] = 'Measure'
            drawing_state['is_drawing'] = True
            drawing_state['points'] = []
            st.session_state.drawing_state = drawing_state
            if 'measurement' not in st.session_state:
                st.session_state.measurement = None
            st.rerun()
    
    with col_meas2:
        if st.button("❌ Clear Measurement", key="clear_measure_mainline"):
            if 'measurement' in st.session_state:
                st.session_state.measurement = None
            st.rerun()
    
    with col_meas3:
        if 'measurement' in st.session_state and st.session_state.measurement:
            meas = st.session_state.measurement
            st.success(f"📏 **{meas['distance']:.2f} m** | From ({meas['point1'][0]:.1f}, {meas['point1'][1]:.1f}) to ({meas['point2'][0]:.1f}, {meas['point2'][1]:.1f})")
    
    with st.expander("ℹ️ About Mainline Design", expanded=False):
        st.markdown("""
        The mainline delivers water from the source to all submains. 
        **Place Mainline Valves** in Pipe Network Layout to mark mainline-submain connection points, 
        then calculate variable pipe sizing based on each submain's flow demand.
        """)
    
    # DEBUG: Show available submain design data
    with st.expander("🔧 Submain Design Data (Debug)", expanded=False):
        st.markdown("**Session State Keys (temp_submain_*_design):**")
        temp_keys = [k for k in st.session_state.keys() if 'temp_submain_' in str(k) and '_design' in str(k)]
        if temp_keys:
            for key in sorted(temp_keys):
                data = st.session_state.get(key, {})
                segments = data.get('segments', [])
                if segments:
                    design_flow = segments[0].get('flow_m3h', 0)
                    full_flow = segments[0].get('full_flow_m3h', 0)
                    st.write(f"✅ `{key}`: {len(segments)} segments")
                    st.write(f"   - Design Flow (with F): **{design_flow:.2f} m³/h**")
                    st.write(f"   - Full Flow (for mainline): **{full_flow:.2f} m³/h**")
                else:
                    st.write(f"✅ `{key}`: no segments")
        else:
            st.warning("No temp_submain_*_design keys found in session_state")
        
        st.markdown("**Project Data Keys (submain_*_design):**")
        saved_keys = [k for k in st.session_state.project_data.keys() if 'submain_' in str(k) and '_design' in str(k)]
        if saved_keys:
            for key in sorted(saved_keys):
                data = st.session_state.project_data.get(key, {})
                segments = data.get('segments', [])
                if segments:
                    design_flow = segments[0].get('flow_m3h', 0)
                    full_flow = segments[0].get('full_flow_m3h', 0)
                    st.write(f"✅ `{key}`: {len(segments)} segments")
                    st.write(f"   - Design Flow (with F): **{design_flow:.2f} m³/h**")
                    st.write(f"   - Full Flow (for mainline): **{full_flow:.2f} m³/h**")
                else:
                    st.write(f"✅ `{key}`: no segments")
        else:
            st.write("No submain_*_design keys found in project_data")
        
        st.markdown("**Mainline Valve Data:**")
        mv_sources = [
            ('mainline_valve_table', st.session_state.get('mainline_valve_table', [])),
            ('pipe_network_state.mainline_valves', st.session_state.get('pipe_network_state', {}).get('mainline_valves', [])),
            ('pipe_network_design.mainline_valves', st.session_state.project_data.get('pipe_network_design', {}).get('mainline_valves', []))
        ]
        for name, valves in mv_sources:
            if valves:
                st.write(f"✅ `{name}`: {len(valves)} valves")
                for mv in valves:
                    indices = mv.get('submain_indices', [])
                    st.write(f"   - {mv.get('name', '?')}: indices={indices}, ref={mv.get('submain_reference', '?')}")
            else:
                st.write(f"❌ `{name}`: empty or not found")
    
    # Get necessary data
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    operational_data = st.session_state.project_data.get('operational_data', {})
    pipe_network_design = st.session_state.project_data.get('pipe_network_design', {})
    
    # Initialize drawing_state with required keys if not present
    drawing_state = st.session_state.get('drawing_state', {})
    if 'is_drawing' not in drawing_state:
        drawing_state = {
            'is_drawing': False,
            'mode': None,
            'points': []
        }
    
    # Create the full field map
    from modules.pipe_network_layout import create_interactive_plot
    fig = create_interactive_plot(field_geometry, operational_data, pipe_network_design, drawing_state)
    
    if fig is None:
        st.warning("⚠️ No field geometry available. Please complete System Layout first.")
        return
    
    # Extract mainline lines from the plot
    mainline_lines = []
    water_source_local = field_geometry.get('water_source_local', [0, 0])
    
    for trace in fig.data:
        if trace.name and 'Mainline' in str(trace.name):
            if hasattr(trace, 'x') and hasattr(trace, 'y') and len(trace.x) >= 2:
                mainline_length = 0
                for i in range(len(trace.x) - 1):
                    dx = trace.x[i+1] - trace.x[i]
                    dy = trace.y[i+1] - trace.y[i]
                    mainline_length += sqrt(dx**2 + dy**2)
                
                avg_x = sum(trace.x) / len(trace.x)
                avg_y = sum(trace.y) / len(trace.y)
                distance_from_source = sqrt((avg_x - water_source_local[0])**2 + (avg_y - water_source_local[1])**2)
                
                mainline_lines.append({
                    'x': list(trace.x),
                    'y': list(trace.y),
                    'length': mainline_length,
                    'distance_from_source': distance_from_source,
                    'avg_x': avg_x,
                    'avg_y': avg_y
                })
    
    if not mainline_lines:
        st.warning("⚠️ No mainline lines detected. Please draw mainline in Pipe Network Layout first.")
        st.stop()
    
    # Highlight ALL mainline lines
    for idx, mainline in enumerate(mainline_lines):
        colors = ['crimson', 'darkred', 'firebrick', 'indianred', 'lightcoral']
        color = colors[idx % len(colors)]
        
        fig.add_trace(go.Scatter(
            x=mainline['x'],
            y=mainline['y'],
            mode='lines+markers',
            line=dict(color='rgba(220, 20, 60, 0.8)', width=12),
            marker=dict(size=12, color=color, symbol='star'),
            name=f'🎯 MAINLINE {idx + 1}',
            hovertext=f"<b>Mainline {idx + 1}</b><br>" +
                     f"Length: {mainline['length']:.1f} m<br>" +
                     f"Distance from source: {mainline['distance_from_source']:.1f} m",
            hoverinfo='text',
            showlegend=True
        ))
    
    # Display the map
    st.plotly_chart(fig, width="stretch", key="mainline_overview_map")
    
    # ============================================================================
    # SECTION 2: CHECK FOR MAINLINE VALVES
    # ============================================================================
    # Look for mainline_valves in multiple locations
    network = {}
    mainline_valves = []
    
    # First try pipe_network_state (primary location from pipe_network_layout)
    if 'pipe_network_state' in st.session_state:
        network = st.session_state.pipe_network_state.get('network', {})
        mainline_valves = network.get('mainline_valves', [])
    
    # Also check mainline_valve_table in session_state (UI management table)
    if not mainline_valves and 'mainline_valve_table' in st.session_state:
        mainline_valves = st.session_state.mainline_valve_table
    
    # Also check pipe_network_design in project_data (fallback)
    if not mainline_valves:
        network = pipe_network_design.get('network', {})
        mainline_valves = network.get('mainline_valves', [])
    
    if not mainline_valves or len(mainline_valves) == 0:
        # Check if this is a no-submain system
        is_no_submain = st.session_state.get('no_submain_system', False) or not has_submain_lines()
        
        if is_no_submain:
            st.warning("""
            ⚠️ **No Mainline Valves Placed**
            
            **No-Submain System Detected** - Mainline connects directly to laterals.
            
            To design variable pipe sizing for the mainline:
            1. Go to **Pipe Network Layout**
            2. Click **🟣 MainValve** tool button
            3. Use **Auto-place at Lateral Intersections** button, OR
            4. Click on the mainline where each lateral connects
            5. Return here to calculate pipe sizing
            
            The mainline valve positions define the segments for variable pipe sizing.
            """)
        else:
            st.warning("""
            ⚠️ **No Mainline Valves Placed**
            
            To design variable pipe sizing for the mainline:
            1. Go to **Pipe Network Layout**
            2. Click **🟣 MainValve** tool button
            3. Click on the mainline where each submain connects
            4. Assign each valve to its corresponding submain
            5. Return here to calculate pipe sizing
            
            The mainline valve positions define the segments for variable pipe sizing.
            """)
        
        # Show fallback: simple single-pipe sizing
        st.markdown("---")
        st.markdown("### 💧 Simple Flow Calculation (No Segments)")
        
        total_subplots = operational_data.get('total_subplots', 1)
        subplots_per_day = min(operational_data.get('subplots_per_day', 1), total_subplots)
        subplot_discharge_m3h = operational_data.get('subplot_discharge', 0)
        
        if subplot_discharge_m3h == 0:
            if 'sprinkler_data' in st.session_state.project_data:
                sprinkler = st.session_state.project_data['sprinkler_data']
                n_sprinklers_per_line = operational_data.get('n_sprinklers_per_line', 0)
                n_lines_per_subplot = operational_data.get('n_lines_per_subplot', 0)
                sprinkler_flow_lh = sprinkler.get('flow', 0)
                sprinkler_flow_m3h = sprinkler_flow_lh / 1000 if sprinkler_flow_lh > 0 else 0
                
                if n_sprinklers_per_line > 0 and n_lines_per_subplot > 0 and sprinkler_flow_m3h > 0:
                    subplot_discharge_m3h = n_sprinklers_per_line * n_lines_per_subplot * sprinkler_flow_m3h
        
        if subplot_discharge_m3h > 0:
            total_system_flow = subplots_per_day * subplot_discharge_m3h
            st.metric("💧 Total System Flow", f"{total_system_flow:.2f} m³/h")
            st.caption(f"{subplots_per_day} operating subplots × {subplot_discharge_m3h:.2f} m³/h each")
        
        return
    
    # ============================================================================
    # SECTION 3: MAINLINE VALVE SUMMARY
    # ============================================================================
    st.markdown("---")
    
    # Check if this is a no-submain system
    has_submains, _, _ = has_submain_lines(pipe_network_design, fig)
    is_no_submain_system = st.session_state.get('no_submain_system', not has_submains)
    
    if is_no_submain_system:
        st.markdown("### 🟣 Mainline Valves (Direct Lateral Connections)")
        st.info("""
        ℹ️ **No-Submain Configuration Detected**
        
        Your system has the mainline connecting directly to lateral lines (no submains).
        The mainline valves mark where laterals/subplots connect to the mainline.
        """)
    else:
        st.markdown("### 🟣 Mainline Valves (Submain Connections)")
    
    # Get lateral valves and subplot discharge for no-submain calculations
    lateral_valves = pipe_network_design.get('valves', [])
    subplot_discharge_m3h = operational_data.get('subplot_discharge', 0)
    
    if subplot_discharge_m3h == 0:
        if 'sprinkler_data' in st.session_state.project_data:
            sprinkler = st.session_state.project_data['sprinkler_data']
            n_sprinklers_per_line = operational_data.get('n_sprinklers_per_line', 0)
            n_lines_per_subplot = operational_data.get('n_lines_per_subplot', 0)
            sprinkler_flow_lh = sprinkler.get('flow', 0)
            sprinkler_flow_m3h = sprinkler_flow_lh / 1000 if sprinkler_flow_lh > 0 else 0
            
            if n_sprinklers_per_line > 0 and n_lines_per_subplot > 0 and sprinkler_flow_m3h > 0:
                subplot_discharge_m3h = n_sprinklers_per_line * n_lines_per_subplot * sprinkler_flow_m3h
    
    # Build valve table with flow data
    valve_table_data = []
    for i, mv in enumerate(mainline_valves):
        # Get submain reference - try multiple formats for compatibility
        submain_ref = mv.get('submain_reference', None)
        if not submain_ref or submain_ref == 'Not assigned':
            submain_names = mv.get('submain_names', [])
            if submain_names:
                submain_ref = ', '.join(submain_names)
            else:
                submain_ref = 'Not assigned'
        
        # Get submain indices - may have multiple submains per valve
        submain_indices = mv.get('submain_indices', [])
        if not submain_indices:
            single_idx = mv.get('submain_idx', None)
            if single_idx is not None:
                submain_indices = [single_idx]
        
        # Calculate flow based on system type
        valve_flow = 0
        connection_info = submain_ref
        
        if is_no_submain_system:
            # NO-SUBMAIN CASE: Calculate flow from nearby lateral valves
            valve_x, valve_y = mv.get('x', 0), mv.get('y', 0)
            tolerance = 30.0  # meters - lateral valves within this distance
            
            nearby_subplots = []
            for lv in lateral_valves:
                lv_x, lv_y = lv.get('x', 0), lv.get('y', 0)
                dist = sqrt((valve_x - lv_x)**2 + (valve_y - lv_y)**2)
                
                if dist <= tolerance:
                    selected_subplots = lv.get('selected_subplots', [])
                    nearby_subplots.extend(selected_subplots)
            
            nearby_subplots = list(set(nearby_subplots))
            valve_flow = len(nearby_subplots) * subplot_discharge_m3h
            
            if nearby_subplots:
                connection_info = f"Laterals: {len(nearby_subplots)} subplots"
            else:
                # If no nearby lateral valves found, estimate from position
                # This is a fallback - calculate based on mainline segment position
                connection_info = "Direct lateral connection"
                # Use a default flow estimate based on operational data
                subplots_per_valve = operational_data.get('total_subplots', 1) // max(1, len(mainline_valves))
                valve_flow = subplots_per_valve * subplot_discharge_m3h
        else:
            # NORMAL CASE: Get flow from submain designs
            for submain_idx in submain_indices:
                temp_key = f'temp_submain_{submain_idx}_design'
                saved_key = f'submain_{submain_idx}_design'
                
                design_data = None
                if temp_key in st.session_state:
                    design_data = st.session_state[temp_key]
                elif saved_key in st.session_state.project_data:
                    design_data = st.session_state.project_data[saved_key]
                
                if design_data:
                    # Get Segment 1 FULL flow (without F-factor)
                    segments = design_data.get('segments', [])
                    if segments and len(segments) > 0:
                        seg1_flow = segments[0].get('full_flow_m3h', segments[0].get('flow_m3h', 0))
                        valve_flow += seg1_flow
                    else:
                        valve_flow += design_data.get('full_inlet_flow_m3h', design_data.get('total_flow_m3h', 0))
        
        # Store the calculated flow in the mainline valve for later use
        mv['calculated_flow_m3h'] = valve_flow
        
        valve_table_data.append({
            'Valve': f'M{i+1}',
            'Connection': connection_info,
            'X': round(mv.get('x', 0), 1),
            'Y': round(mv.get('y', 0), 1),
            'Flow (m³/h)': round(valve_flow, 2) if valve_flow > 0 else 'Not calculated'
        })
    
    st.dataframe(pd.DataFrame(valve_table_data), width="stretch", hide_index=True)
    
    # Check if any submain designs are missing (only for systems WITH submains)
    missing_designs = []
    all_have_flow = True
    
    if not is_no_submain_system:
        # Only check for missing submain designs if system has submains
        for mv in mainline_valves:
            submain_indices = mv.get('submain_indices', [])
            if not submain_indices:
                single_idx = mv.get('submain_idx', None)
                if single_idx is not None:
                    submain_indices = [single_idx]
            
            for submain_idx in submain_indices:
                temp_key = f'temp_submain_{submain_idx}_design'
                saved_key = f'submain_{submain_idx}_design'
                submain_name = f'Submain {submain_idx + 1}'
                
                if temp_key not in st.session_state and saved_key not in st.session_state.project_data:
                    missing_designs.append(submain_name)
                    all_have_flow = False
        
        if missing_designs:
            st.warning(f"""
            ⚠️ **Missing Submain Designs**: {', '.join(set(missing_designs))}
            
            **To calculate mainline pipe sizing:**
            1. Go to **Submain Design** tab
            2. Select each submain and click **🔍 Calculate Submain Pipe Sizing**
            3. The system uses **Segment 1 flow** (inlet flow) from each submain design
            4. Return here to calculate mainline sizing
            
            💡 **Why Segment 1?** The inlet segment of each submain carries the total flow entering from the mainline.
            This is the flow the mainline must deliver to each submain connection point.
            """)
    else:
        # No-submain system: check if we have flow data from lateral valves
        total_calculated_flow = sum(mv.get('calculated_flow_m3h', 0) for mv in mainline_valves)
        if total_calculated_flow == 0:
            st.warning("""
            ⚠️ **Flow Calculation Note**
            
            Could not automatically determine flow for each mainline valve connection.
            The system will estimate flow based on the number of subplots and irrigation schedule.
            
            **For more accurate results:**
            - Ensure lateral valves are placed and assigned to subplots in **Pipe Network Layout**
            - Ensure **Operational Design** has calculated subplot discharge
            """)
    
    # ============================================================================
    # SECTION 4: SELECT MAINLINE FOR VARIABLE PIPE SIZING DESIGN
    # ============================================================================
    st.markdown("---")
    st.markdown("### 🔧 Variable Pipe Sizing Design")
    
    if len(mainline_lines) == 0:
        st.error("No mainline found. Please draw mainline in Pipe Network Layout.")
        return
    
    # Create mainline selection similar to submain design
    st.caption("Select a mainline below to design its variable pipe sizing.")
    
    mainline_options = []
    for idx, ml in enumerate(mainline_lines):
        mainline_options.append(
            f"Mainline {idx + 1}: {ml['length']:.1f}m, Distance from source: {ml['distance_from_source']:.1f}m"
        )
    
    selected_mainline_idx = st.selectbox(
        "Select Mainline to Design",
        range(len(mainline_options)),
        format_func=lambda x: mainline_options[x],
        index=0,
        help="Choose which mainline to design with variable pipe sizing"
    )
    
    selected_mainline = mainline_lines[selected_mainline_idx]
    mainline_length = selected_mainline['length']
    mainline_x = selected_mainline['x']
    mainline_y = selected_mainline['y']
    
    st.success(f"📏 **Selected Mainline {selected_mainline_idx + 1}**: {mainline_length:.1f} m total length")
    
    # Design mode selection
    design_mode = st.radio(
        "Design Mode",
        ["Automatic (Optimized)", "Manual (Select Each Segment)"],
        horizontal=True,
        key=f"mainline_design_mode_{selected_mainline_idx}"
    )
    
    # Design parameters - user configurable velocity limits
    st.markdown("#### ⚙️ Design Parameters")
    col1, col2, col3 = st.columns(3)
    with col1:
        mainline_max_velocity = st.number_input(
            "Maximum Velocity (m/s)", 
            min_value=1.0, max_value=3.0, value=2.0, step=0.1,
            help="Recommended: 1.5-2.5 m/s for mainlines. Higher velocity = smaller pipes but more friction loss.",
            key=f"mainline_max_vel_{selected_mainline_idx}"
        )
    with col2:
        mainline_min_velocity = st.number_input(
            "Minimum Velocity (m/s)", 
            min_value=0.3, max_value=1.5, value=0.5, step=0.1,
            help="Minimum to prevent sediment buildup (typically 0.5-0.6 m/s)",
            key=f"mainline_min_vel_{selected_mainline_idx}"
        )
    with col3:
        mainline_C_coefficient = st.number_input(
            "Hazen-Williams C", 
            min_value=100, max_value=150, value=140, step=5,
            help="C=140 for new PVC, C=130 for aged PVC, C=120 for PE",
            key=f"mainline_C_{selected_mainline_idx}"
        )
    
    st.markdown("---")
    
    # Calculate button
    calculate_mainline_button = st.button("🔍 Calculate Mainline Pipe Sizing", type="primary", key=f"calc_mainline_{selected_mainline_idx}")
    
    # Per-mainline storage keys
    temp_design_key = f'temp_mainline_{selected_mainline_idx}_design'
    saved_design_key = f'mainline_{selected_mainline_idx}_design'
    mainline_manual_key = f'manual_mainline_{selected_mainline_idx}_pipe_selections'
    
    if mainline_manual_key not in st.session_state:
        st.session_state[mainline_manual_key] = {}
    
    # Check if we have saved or temp results for this mainline
    has_temp_design = temp_design_key in st.session_state
    has_saved_design = saved_design_key in st.session_state.project_data
    show_mainline_results = calculate_mainline_button or has_temp_design or has_saved_design
    
    # Load saved design into temp if no temp exists
    if not has_temp_design and has_saved_design:
        st.session_state[temp_design_key] = st.session_state.project_data[saved_design_key].copy()
        log_info("Loaded saved mainline design")
    
    if calculate_mainline_button:
        # Find the inlet point (closest to water source)
        inlet_idx = 0
        min_dist_to_source = float('inf')
        
        for i in range(len(mainline_x)):
            dx = float(mainline_x[i]) - float(water_source_local[0])
            dy = float(mainline_y[i]) - float(water_source_local[1])
            dist = (dx*dx + dy*dy)**0.5
            if dist < min_dist_to_source:
                min_dist_to_source = dist
                inlet_idx = i
        
        log_debug(f"Inlet point found at vertex {inlet_idx} (distance {min_dist_to_source:.1f}m from water source)")
        
        # Calculate distance along mainline for each valve
        def get_distance_along_mainline(valve_x, valve_y, line_x, line_y, inlet_vertex_idx):
            """Calculate distance along the mainline from inlet to the valve position"""
            try:
                valve_x = float(valve_x)
                valve_y = float(valve_y)
            except (ValueError, TypeError):
                return 0.0
            
            min_dist_to_line = float('inf')
            closest_segment_idx = 0
            closest_t = 0
            
            for i in range(len(line_x) - 1):
                try:
                    x1, y1 = float(line_x[i]), float(line_y[i])
                    x2, y2 = float(line_x[i + 1]), float(line_y[i + 1])
                except (ValueError, TypeError, IndexError):
                    continue
                
                dx = x2 - x1
                dy = y2 - y1
                segment_length_sq = dx*dx + dy*dy
                
                if segment_length_sq > 0:
                    t = max(0, min(1, ((valve_x - x1) * dx + (valve_y - y1) * dy) / segment_length_sq))
                    proj_x = x1 + t * dx
                    proj_y = y1 + t * dy
                    dist = ((valve_x - proj_x)**2 + (valve_y - proj_y)**2)**0.5
                    
                    if dist < min_dist_to_line:
                        min_dist_to_line = dist
                        closest_segment_idx = i
                        closest_t = t
            
            # Calculate distance from inlet
            distance_along_line = 0.0
            
            if closest_segment_idx >= inlet_vertex_idx:
                for i in range(inlet_vertex_idx, closest_segment_idx):
                    try:
                        dx = float(line_x[i+1]) - float(line_x[i])
                        dy = float(line_y[i+1]) - float(line_y[i])
                        distance_along_line += (dx*dx + dy*dy)**0.5
                    except (ValueError, TypeError, IndexError):
                        continue
                
                if closest_segment_idx < len(line_x) - 1:
                    try:
                        dx = float(line_x[closest_segment_idx+1]) - float(line_x[closest_segment_idx])
                        dy = float(line_y[closest_segment_idx+1]) - float(line_y[closest_segment_idx])
                        segment_length = (dx*dx + dy*dy)**0.5
                        distance_along_line += closest_t * segment_length
                    except (ValueError, TypeError, IndexError):
                        pass
            else:
                for i in range(inlet_vertex_idx - 1, closest_segment_idx, -1):
                    try:
                        dx = float(line_x[i+1]) - float(line_x[i])
                        dy = float(line_y[i+1]) - float(line_y[i])
                        distance_along_line += (dx*dx + dy*dy)**0.5
                    except (ValueError, TypeError, IndexError):
                        continue
                
                if closest_segment_idx < len(line_x) - 1:
                    try:
                        dx = float(line_x[closest_segment_idx+1]) - float(line_x[closest_segment_idx])
                        dy = float(line_y[closest_segment_idx+1]) - float(line_y[closest_segment_idx])
                        segment_length = (dx*dx + dy*dy)**0.5
                        distance_along_line += (1 - closest_t) * segment_length
                    except (ValueError, TypeError, IndexError):
                        pass
            
            return distance_along_line
        
        # Calculate distance for each mainline valve
        valve_distances = []
        for mv in mainline_valves:
            vx = mv.get('x', 0)
            vy = mv.get('y', 0)
            dist = get_distance_along_mainline(vx, vy, mainline_x, mainline_y, inlet_idx)
            
            # Get submain reference - try multiple formats
            submain_ref = mv.get('submain_reference', None)
            if not submain_ref or submain_ref == 'Not assigned':
                submain_names = mv.get('submain_names', [])
                if submain_names:
                    submain_ref = ', '.join(submain_names)
                else:
                    submain_ref = 'Unknown'
            
            # Get submain indices - may have multiple submains per valve
            submain_indices = mv.get('submain_indices', [])
            if not submain_indices:
                single_idx = mv.get('submain_idx', None)
                if single_idx is not None:
                    submain_indices = [single_idx]
            
            # Get flow based on system type
            valve_flow = 0
            flow_details = []  # For debugging
            
            if is_no_submain_system:
                # NO-SUBMAIN CASE: Use pre-calculated flow from mainline valve
                valve_flow = mv.get('calculated_flow_m3h', 0)
                
                if valve_flow == 0:
                    # Fallback: estimate from operational data
                    subplots_per_valve = operational_data.get('total_subplots', 1) // max(1, len(mainline_valves))
                    valve_flow = subplots_per_valve * subplot_discharge_m3h
                
                flow_details.append(f"Direct lateral connection: {valve_flow:.2f} m³/h")
                submain_ref = f"Lateral Connection {mainline_valves.index(mv) + 1}"
            else:
                # NORMAL CASE: Get flow from submain designs
                for submain_idx in submain_indices:
                    temp_key = f'temp_submain_{submain_idx}_design'
                    saved_key = f'submain_{submain_idx}_design'
                    
                    design_data = None
                    source = "not found"
                    if temp_key in st.session_state:
                        design_data = st.session_state[temp_key]
                        source = f"temp (session_state['{temp_key}'])"
                    elif saved_key in st.session_state.project_data:
                        design_data = st.session_state.project_data[saved_key]
                        source = f"saved (project_data['{saved_key}'])"
                    
                    if design_data:
                        # Get Segment 1 FULL flow (inlet segment - without F-factor)
                        # For mainline design, we need the full flow, not the reduced design flow
                        segments = design_data.get('segments', [])
                        if segments and len(segments) > 0:
                            # Use full_flow_m3h (without F-factor) if available, fallback to flow_m3h
                            seg1_flow = segments[0].get('full_flow_m3h', segments[0].get('flow_m3h', 0))
                            valve_flow += seg1_flow
                            flow_details.append(f"Submain {submain_idx+1}: {seg1_flow:.2f} m³/h (full flow) from {source}")
                        else:
                            # Fallback to full_inlet_flow_m3h or total_flow_m3h
                            fallback_flow = design_data.get('full_inlet_flow_m3h', design_data.get('total_flow_m3h', 0))
                            valve_flow += fallback_flow
                            flow_details.append(f"Submain {submain_idx+1}: {fallback_flow:.2f} m³/h (fallback) from {source}")
                    else:
                        flow_details.append(f"Submain {submain_idx+1}: NO DATA FOUND (tried {temp_key} and {saved_key})")
            
            valve_distances.append({
                'valve': mv,
                'distance': dist,
                'submain_ref': submain_ref,
                'submain_indices': submain_indices,
                'submain_flow': valve_flow,
                'flow_details': flow_details  # Add debug info
            })
        
        # Sort by distance from inlet
        valve_distances.sort(key=lambda v: v['distance'])
        
        # DEBUG: Show valve distances and flows
        st.markdown("#### 🔍 Mainline Valve Analysis")
        debug_data = []
        for vd in valve_distances:
            debug_data.append({
                'Distance (m)': round(vd['distance'], 1),
                'Submains': vd['submain_ref'],
                'Submain Indices': str(vd['submain_indices']),
                'Flow (m³/h)': round(vd['submain_flow'], 2)
            })
        st.dataframe(pd.DataFrame(debug_data), width="stretch", hide_index=True)
        
        # Show detailed flow breakdown
        st.markdown("##### 📋 Flow Data Sources (Debug)")
        for vd in valve_distances:
            with st.expander(f"Valve @ {vd['distance']:.1f}m - {vd['submain_ref']}"):
                if vd.get('flow_details'):
                    for detail in vd['flow_details']:
                        st.write(f"• {detail}")
                else:
                    st.write("No flow details available")
        
        # Group valves that are very close (within tolerance)
        MAINLINE_VALVE_TOLERANCE = 10  # meters
        MIN_SEGMENT_LENGTH = 5  # minimum segment length
        
        grouped_valves = []
        for vd in valve_distances:
            if not grouped_valves or (vd['distance'] - grouped_valves[-1]['distance']) > MAINLINE_VALVE_TOLERANCE:
                grouped_valves.append({
                    'distance': vd['distance'],
                    'submain_refs': [vd['submain_ref']],
                    'submain_indices': list(vd['submain_indices']),  # Track indices
                    'total_flow': vd['submain_flow']
                })
            else:
                grouped_valves[-1]['submain_refs'].append(vd['submain_ref'])
                grouped_valves[-1]['submain_indices'].extend(vd['submain_indices'])
                grouped_valves[-1]['total_flow'] += vd['submain_flow']
        
        # Show grouped valves
        st.markdown("#### 📍 Mainline Connection Points (Grouped)")
        for i, gv in enumerate(grouped_valves):
            all_refs = ', '.join(gv['submain_refs'])
            st.write(f"**Point {i+1}** @ {gv['distance']:.1f}m: {all_refs} → Flow: **{gv['total_flow']:.2f} m³/h**")
        
        # ========================================================================
        # Get valve_table (lateral valves) and subplot_day_assignments for 
        # calculating MAX DAILY FLOW instead of sum of all flows
        # ========================================================================
        lateral_valves = pipe_network_design.get('valves', [])
        subplot_day_assignments = operational_data.get('subplot_day_assignments', {})
        
        # Show operational scheduling info and submain day assignments
        if subplot_day_assignments:
            st.markdown("#### 🗓️ Operational Scheduling Detected")
            all_days = sorted(set(subplot_day_assignments.values()))
            
            # Show which day each submain operates on
            st.markdown("**Submain Operating Days:**")
            submain_day_info = []
            for gv in grouped_valves:
                for i, submain_idx in enumerate(gv.get('submain_indices', [])):
                    temp_key = f'temp_submain_{submain_idx}_design'
                    saved_key = f'submain_{submain_idx}_design'
                    design_data = None
                    if temp_key in st.session_state:
                        design_data = st.session_state[temp_key]
                    elif saved_key in st.session_state.project_data:
                        design_data = st.session_state.project_data[saved_key]
                    
                    ref_name = gv['submain_refs'][i] if i < len(gv['submain_refs']) else f"Submain {submain_idx+1}"
                    if design_data:
                        primary_day = design_data.get('primary_operating_day', 'Unknown')
                        operating_days = design_data.get('operating_days', [])
                        flow = design_data.get('full_inlet_flow_m3h', 0)
                        if flow == 0:
                            segs = design_data.get('segments', [])
                            if segs:
                                flow = segs[0].get('full_flow_m3h', segs[0].get('flow_m3h', 0))
                        st.write(f"  - {ref_name}: **Day {primary_day}** ({flow:.1f} m³/h)")
                    else:
                        st.write(f"  - {ref_name}: No design data")
            
            st.info(f"""
            **Irrigation Schedule**: Field is divided into **{len(all_days)} irrigation days**
            
            The mainline will be sized for **maximum daily demand**, not the sum of all submains.
            This ensures pipes are sized for the actual operational flow, not over-designed.
            """)
            
            # Show detailed V3 calculation preview
            with st.expander("🔍 Detailed Flow Calculation Preview (V3 Method)", expanded=True):
                st.markdown("""
                **Calculation Logic:**
                For each mainline segment, we trace:
                1. **Downstream Mainline Valves** → which submains they feed
                2. **Submain day_flows** → how many subplots operate on each day
                3. **Flow per day** = subplots × lateral_flow_rate
                4. **Design flow** = MAX(Day 1, Day 2, ...) 
                """)
                
                # Get lateral flow
                lateral_flow = operational_data.get('subplot_discharge', 0)
                if lateral_flow == 0:
                    lateral_flow = operational_data.get('lateral_flow_m3h', 20.8)
                
                # Calculate and show preview for the inlet segment (all submains)
                max_daily_flow, daily_breakdown, flow_details = calculate_max_daily_flow_for_mainline_v3(
                    grouped_valves,  # All downstream grouped valves
                    pipe_network_design,
                    subplot_day_assignments,
                    operational_data
                )
                
                st.markdown(f"**Lateral Flow Rate**: {lateral_flow:.2f} m³/h per subplot")
                st.markdown(f"**Method Used**: {flow_details.get('method', 'Unknown')}")
                
                # Show per-day breakdown
                if daily_breakdown:
                    st.markdown("**Daily Flow Summary:**")
                    day_data = []
                    for day in sorted(daily_breakdown.keys()):
                        flow = daily_breakdown[day]
                        subplot_count = flow_details.get('daily_subplot_counts', {}).get(day, 0)
                        day_data.append({
                            'Day': day,
                            'Subplots': subplot_count,
                            'Flow (m³/h)': round(flow, 2),
                            'Status': '← MAX (design)' if flow == max_daily_flow else ''
                        })
                    st.dataframe(pd.DataFrame(day_data), width="stretch", hide_index=True)
                
                # Show submain contributions (FIXED: now shows flow, not subplot counts)
                submain_details = flow_details.get('submain_details', [])
                if submain_details:
                    st.markdown("**Submain Flow Assignments:**")
                    for sd in submain_details:
                        flow = sd.get('flow_m3h', 0)
                        primary_day = sd.get('primary_day')
                        ref_name = sd.get('ref_name', 'Unknown')
                        if flow > 0 and primary_day is not None:
                            st.write(f"  - **{ref_name}**: {flow:.1f} m³/h → Day {primary_day}")
                        elif flow > 0:
                            st.write(f"  - **{ref_name}**: {flow:.1f} m³/h (no day assigned)")
                        else:
                            st.write(f"  - **{ref_name}**: No flow data ({sd.get('source', 'unknown source')})")
                
                # Show daily contributions (which submains contribute to each day)
                daily_contribs = flow_details.get('daily_contributions', {})
                if daily_contribs and any(daily_contribs.values()):
                    st.markdown("**Daily Flow Totals:**")
                    for day in sorted(daily_contribs.keys()):
                        contribs = daily_contribs[day]
                        day_flow = flow_details.get('daily_flow', {}).get(day, 0)
                        if contribs:
                            st.write(f"  - **Day {day}**: {day_flow:.1f} m³/h")
                            for contrib in contribs:
                                st.caption(f"      {contrib}")
                
                # Compare with sum of all
                sum_all = sum(gv['total_flow'] for gv in grouped_valves)
                st.markdown("---")
                st.markdown("**Comparison:**")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Sum All Flows", f"{sum_all:.1f} m³/h", help="If all submains operated simultaneously")
                with col2:
                    st.metric("Max Daily Flow", f"{max_daily_flow:.1f} m³/h", help="Actual max flow considering scheduling")
                with col3:
                    reduction = ((sum_all - max_daily_flow) / sum_all * 100) if sum_all > 0 else 0
                    st.metric("Reduction", f"{reduction:.1f}%", help="Pipe sizing reduction from scheduling")
        else:
            st.warning("⚠️ No operational scheduling found. Using sum of all flows (conservative).")
        
        # Create segments between valve positions
        n_connections = len(grouped_valves)
        F = calculate_f_factor(n_connections)
        
        segments = []
        pipe_sizes = get_standard_pipe_sizes()
        segment_number = 1
        
        # Velocity limits - use user-configured values
        min_velocity = mainline_min_velocity
        max_velocity = mainline_max_velocity
        C_coefficient = mainline_C_coefficient
        
        def find_optimal_pipe(flow_m3h, pipe_sizes_list, min_v=0.5, max_v=2.5):
            """Find optimal pipe size for given flow"""
            for size in pipe_sizes_list:
                D_mm = size['internal']
                D_m = D_mm / 1000
                Q_m3s = flow_m3h / 3600
                area = 3.14159 * (D_m / 2) ** 2
                velocity = Q_m3s / area if area > 0 else 999
                
                if min_v <= velocity <= max_v:
                    return size
            # If no size in range, return largest
            return pipe_sizes_list[-1]
        
        def calc_velocity(flow_m3h, D_mm):
            """Calculate velocity in m/s"""
            D_m = D_mm / 1000
            Q_m3s = flow_m3h / 3600
            area = 3.14159 * (D_m / 2) ** 2
            return Q_m3s / area if area > 0 else 0
        
        # Segment from inlet to first valve
        if grouped_valves and grouped_valves[0]['distance'] > MIN_SEGMENT_LENGTH:
            # ====================================================================
            # CORRECTED: Use MAX DAILY FLOW instead of sum of all flows
            # This considers operational scheduling (irrigation days)
            # V3: Uses submain day_flows for most accurate calculation
            # ====================================================================
            
            # Calculate max daily flow considering operational scheduling
            max_daily_flow, daily_breakdown, flow_details = calculate_max_daily_flow_for_mainline_v3(
                grouped_valves,  # All downstream grouped valves
                pipe_network_design,
                subplot_day_assignments,
                operational_data
            )
            
            # Use max daily flow if operational scheduling exists, otherwise sum all
            if subplot_day_assignments and max_daily_flow > 0:
                total_flow = max_daily_flow
                flow_method = "Max Daily Flow (V3)"
            else:
                total_flow = sum(gv['total_flow'] for gv in grouped_valves)
                flow_method = "Sum of All (no scheduling)"
            
            seg_length = grouped_valves[0]['distance']
            
            # Build downstream submains string showing ALL submains
            all_downstream_refs = []
            for gv in grouped_valves:
                all_downstream_refs.extend(gv['submain_refs'])
            downstream_str = ', '.join(all_downstream_refs)
            
            if design_mode == "Manual (Select Each Segment)":
                seg_key = f"mainline_seg_{segment_number}"
                if seg_key in st.session_state[mainline_manual_key]:
                    selected_pipe = pipe_sizes[st.session_state[mainline_manual_key][seg_key]]
                else:
                    selected_pipe = find_optimal_pipe(total_flow, pipe_sizes, min_velocity, max_velocity)
            else:
                selected_pipe = find_optimal_pipe(total_flow, pipe_sizes, min_velocity, max_velocity)
            
            velocity = calc_velocity(total_flow, selected_pipe['internal'])
            head_loss = calculate_hazen_williams(total_flow, selected_pipe['internal'], seg_length, C_coefficient)
            
            segments.append({
                'segment': segment_number,
                'start_m': 0,
                'end_m': round(seg_length, 1),
                'length_m': round(seg_length, 1),
                'downstream_submains': downstream_str,
                'flow_m3h': round(total_flow, 2),
                'flow_method': flow_method,
                'daily_breakdown': daily_breakdown,
                'flow_details': flow_details,
                'pipe_nominal_mm': selected_pipe['nominal'],
                'pipe_inner_mm': selected_pipe['internal'],
                'velocity_ms': round(velocity, 2),
                'head_loss_m': round(head_loss, 3)
            })
            segment_number += 1
        
        # Segments between valves
        for i in range(len(grouped_valves) - 1):
            seg_start = grouped_valves[i]['distance']
            seg_end = grouped_valves[i + 1]['distance']
            seg_length = seg_end - seg_start
            
            if seg_length < MIN_SEGMENT_LENGTH:
                continue
            
            # ====================================================================
            # CORRECTED: Use MAX DAILY FLOW for downstream submains
            # V3: Uses submain day_flows for most accurate calculation
            # ====================================================================
            
            # Get downstream grouped valves (from i+1 onwards)
            downstream_grouped = grouped_valves[i+1:]
            
            # Calculate max daily flow for downstream submains
            max_daily_flow, daily_breakdown, flow_details = calculate_max_daily_flow_for_mainline_v3(
                downstream_grouped,
                pipe_network_design,
                subplot_day_assignments,
                operational_data
            )
            
            # Use max daily flow if operational scheduling exists, otherwise sum all
            if subplot_day_assignments and max_daily_flow > 0:
                total_flow = max_daily_flow
                flow_method = "Max Daily Flow (V3)"
            else:
                total_flow = sum(gv['total_flow'] for gv in downstream_grouped)
                flow_method = "Sum of All (no scheduling)"
            
            # Build downstream submains string
            all_downstream_refs = []
            for gv in downstream_grouped:
                all_downstream_refs.extend(gv['submain_refs'])
            downstream_str = ', '.join(all_downstream_refs)
            
            if total_flow <= 0:
                continue
            
            if design_mode == "Manual (Select Each Segment)":
                seg_key = f"mainline_seg_{segment_number}"
                if seg_key in st.session_state[mainline_manual_key]:
                    selected_pipe = pipe_sizes[st.session_state[mainline_manual_key][seg_key]]
                else:
                    selected_pipe = find_optimal_pipe(total_flow, pipe_sizes, min_velocity, max_velocity)
            else:
                selected_pipe = find_optimal_pipe(total_flow, pipe_sizes, min_velocity, max_velocity)
            
            velocity = calc_velocity(total_flow, selected_pipe['internal'])
            head_loss = calculate_hazen_williams(total_flow, selected_pipe['internal'], seg_length, C_coefficient)
            
            segments.append({
                'segment': segment_number,
                'start_m': round(seg_start, 1),
                'end_m': round(seg_end, 1),
                'length_m': round(seg_length, 1),
                'downstream_submains': downstream_str,
                'flow_m3h': round(total_flow, 2),
                'flow_method': flow_method,
                'daily_breakdown': daily_breakdown,
                'flow_details': flow_details,
                'pipe_nominal_mm': selected_pipe['nominal'],
                'pipe_inner_mm': selected_pipe['internal'],
                'velocity_ms': round(velocity, 2),
                'head_loss_m': round(head_loss, 3)
            })
            segment_number += 1
        
        # Calculate totals
        total_head_loss = sum(s['head_loss_m'] for s in segments) * F
        total_length = sum(s['length_m'] for s in segments)
        max_flow = max(s['flow_m3h'] for s in segments) if segments else 0
        
        # Store design in session state
        st.session_state[temp_design_key] = {
            'segments': segments,
            'total_head_loss': total_head_loss,
            'total_length': total_length,
            'max_flow': max_flow,
            'n_connections': n_connections,
            'f_factor': F,
            'design_mode': design_mode,
            'grouped_valves': grouped_valves
        }
    
    # ============================================================================
    # SECTION 5: DISPLAY RESULTS
    # ============================================================================
    if show_mainline_results and temp_design_key in st.session_state:
        design_data = st.session_state[temp_design_key]
        segments = design_data['segments']
        
        if not segments:
            st.warning("No segments calculated. Please check mainline valve positions and submain designs.")
            return
        
        # Summary metrics
        st.markdown("---")
        st.markdown("#### 📊 Mainline Design Summary")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📏 Total Length", f"{design_data['total_length']:.1f} m")
        with col2:
            st.metric("🔢 Segments", f"{len(segments)}")
        with col3:
            st.metric("💧 Max Flow", f"{design_data['max_flow']:.2f} m³/h")
        with col4:
            st.metric("📉 Total Head Loss", f"{design_data['total_head_loss']:.3f} m")
        
        st.caption(f"Christiansen F-factor: {design_data['f_factor']:.3f} ({design_data['n_connections']} submain connections)")
        
        # Segment details table
        st.markdown("---")
        st.markdown("#### 📐 Segment Flow Calculation Breakdown")
        
        df_segments = pd.DataFrame(segments)
        df_display = df_segments[['segment', 'start_m', 'end_m', 'length_m', 'downstream_submains', 
                                   'flow_m3h', 'pipe_nominal_mm', 'velocity_ms', 'head_loss_m']].copy()
        df_display.columns = ['Seg', 'Start (m)', 'End (m)', 'Length (m)', 'Downstream Submains',
                              'Flow (m³/h)', 'Pipe Ø (mm)', 'Velocity (m/s)', 'Head Loss (m)']
        
        # Format numeric columns to max 2 decimal places
        format_dict = {col: '{:.2f}' for col in df_display.select_dtypes(include=['float64', 'float32', 'number']).columns}
        
        st.dataframe(df_display.style.format(format_dict), width="stretch", hide_index=True)
        
        # Show daily flow breakdown debug info
        with st.expander("📅 Daily Flow Breakdown (Debug)", expanded=False):
            st.markdown("**How flow is calculated for each segment:**")
            st.markdown("""
            The mainline is sized for **maximum daily demand**, not the sum of all flows.
            This considers which submains operate on the same irrigation day.
            """)
            
            for seg in segments:
                st.markdown(f"---\n**Segment {seg['segment']}** ({seg['start_m']}m → {seg['end_m']}m)")
                st.write(f"- **Flow Method**: {seg.get('flow_method', 'Unknown')}")
                st.write(f"- **Design Flow**: {seg['flow_m3h']:.2f} m³/h")
                st.write(f"- **Downstream Submains**: {seg.get('downstream_submains', 'N/A')}")
                
                # Show daily breakdown if available
                daily_breakdown = seg.get('daily_breakdown', {})
                if daily_breakdown:
                    st.write("**Daily Flow Contributions:**")
                    for day, flow in sorted(daily_breakdown.items()):
                        if flow > 0 and flow == max(daily_breakdown.values()):
                            st.write(f"  - Day {day}: **{flow:.2f} m³/h** ← MAX (used for design)")
                        elif flow > 0:
                            st.write(f"  - Day {day}: {flow:.2f} m³/h")
                
                # Show flow details if available (V3 returns a dict)
                flow_details = seg.get('flow_details', {})
                if isinstance(flow_details, dict):
                    method = flow_details.get('method', 'Unknown')
                    st.caption(f"Calculation method: {method}")
                    
                    # Show daily subplot counts
                    daily_counts = flow_details.get('daily_subplot_counts', {})
                    if daily_counts:
                        count_str = ', '.join([f"Day {d}: {c}" for d, c in sorted(daily_counts.items()) if c > 0])
                        st.caption(f"Subplots per day: {count_str}")
                    
                    # Show submain contributions
                    daily_contribs = flow_details.get('daily_contributions', {})
                    if daily_contribs:
                        for day, contribs in sorted(daily_contribs.items()):
                            if contribs:
                                st.caption(f"Day {day} submains: {', '.join(contribs)}")
                elif flow_details:
                    st.caption(f"Details: {flow_details}")
        
        # Manual selection interface
        if design_mode == "Manual (Select Each Segment)":
            st.markdown("---")
            st.markdown("#### 🎛️ Manual Pipe Selection")
            st.caption("Select pipe diameter for each segment, then click 'Calculate' to update.")
            
            pipe_sizes = get_standard_pipe_sizes()
            n_cols_display = min(5, len(segments))
            cols = st.columns(n_cols_display)
            
            for i, seg in enumerate(segments):
                col_idx = i % n_cols_display
                with cols[col_idx]:
                    segment_key = f"mainline_seg_{seg['segment']}"
                    
                    pipe_options = [f"Ø{s['nominal']} mm" for s in pipe_sizes]
                    current_idx = next((idx for idx, s in enumerate(pipe_sizes) 
                                      if s['nominal'] == seg['pipe_nominal_mm']), 0)
                    
                    if segment_key not in st.session_state[mainline_manual_key]:
                        st.session_state[mainline_manual_key][segment_key] = current_idx
                    
                    st.markdown(f"**Seg {seg['segment']}**")
                    st.caption(f"Flow: {seg['flow_m3h']} m³/h")
                    st.caption(f"V: {seg['velocity_ms']} m/s")
                    
                    selected_idx = st.selectbox(
                        "Pipe Size",
                        range(len(pipe_sizes)),
                        index=st.session_state[mainline_manual_key][segment_key],
                        format_func=lambda x: pipe_options[x],
                        key=f"select_mainline_{selected_mainline_idx}_{segment_key}",
                        label_visibility="collapsed"
                    )
                    
                    st.session_state[mainline_manual_key][segment_key] = selected_idx
        
        # Pipe sizing diagram
        st.markdown("---")
        st.markdown("#### 📊 Mainline Pipe Sizing Diagram")
        
        try:
            diagram_fig = create_mainline_diagram(segments, design_data['total_length'])
            st.plotly_chart(diagram_fig, width="stretch", key=f"mainline_diagram_{selected_mainline_idx}")
        except Exception as e:
            st.warning(f"Could not create diagram: {e}")
        
        # Save design
        st.markdown("---")
        col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
        with col_save2:
            if st.button("💾 Save Mainline Design", type="primary", width="stretch", key=f"save_mainline_{selected_mainline_idx}_design"):
                st.session_state.project_data[saved_design_key] = design_data.copy()
                st.success(f"✅ Mainline {selected_mainline_idx + 1} design saved to project!")


def create_mainline_diagram(segments, total_length):
    """Create a visual diagram of mainline pipe sizing"""
    if not segments:
        return go.Figure()
    
    fig = go.Figure()
    
    # Color scale for pipe sizes
    min_size = min(s['pipe_nominal_mm'] for s in segments)
    max_size = max(s['pipe_nominal_mm'] for s in segments)
    
    y_base = 0
    
    for seg in segments:
        # Calculate color based on pipe size
        if max_size > min_size:
            norm_size = (seg['pipe_nominal_mm'] - min_size) / (max_size - min_size)
        else:
            norm_size = 0.5
        
        # Color from blue (small) to red (large)
        r = int(255 * norm_size)
        b = int(255 * (1 - norm_size))
        color = f'rgb({r}, 100, {b})'
        
        # Height proportional to pipe diameter
        height = seg['pipe_nominal_mm'] / 10
        
        # Draw segment
        fig.add_trace(go.Scatter(
            x=[seg['start_m'], seg['end_m'], seg['end_m'], seg['start_m'], seg['start_m']],
            y=[y_base - height/2, y_base - height/2, y_base + height/2, y_base + height/2, y_base - height/2],
            fill='toself',
            fillcolor=color,
            line=dict(color='black', width=1),
            name=f"Seg {seg['segment']}: Ø{seg['pipe_nominal_mm']}mm",
            hovertext=f"<b>Segment {seg['segment']}</b><br>" +
                     f"Length: {seg['length_m']:.1f} m<br>" +
                     f"Flow: {seg['flow_m3h']:.2f} m³/h<br>" +
                     f"Pipe: Ø{seg['pipe_nominal_mm']} mm<br>" +
                     f"Velocity: {seg['velocity_ms']:.2f} m/s",
            hoverinfo='text'
        ))
        
        # Add label
        mid_x = (seg['start_m'] + seg['end_m']) / 2
        fig.add_annotation(
            x=mid_x,
            y=y_base + height/2 + 2,
            text=f"Ø{seg['pipe_nominal_mm']}",
            showarrow=False,
            font=dict(size=10)
        )
    
    # Add flow arrows
    fig.add_annotation(
        x=0,
        y=y_base - 10,
        text="← Water Source",
        showarrow=False,
        font=dict(size=12, color='blue')
    )
    
    fig.add_annotation(
        x=total_length,
        y=y_base - 10,
        text="End →",
        showarrow=False,
        font=dict(size=12, color='gray')
    )
    
    fig.update_layout(
        title="Mainline Variable Pipe Sizing",
        xaxis_title="Distance from Inlet (m)",
        yaxis_title="",
        showlegend=True,
        height=400,
        yaxis=dict(showticklabels=False, zeroline=False),
        xaxis=dict(zeroline=False)
    )
    
    return fig


def show_network_summary():
    """Show complete network summary with all pipe designs in a unified table"""
    st.markdown('<h2 class="sub-header">Network Summary</h2>', unsafe_allow_html=True)
    
    # Check if this is a no-submain system
    is_no_submain_system = st.session_state.get('no_submain_system', False)
    
    with st.expander("ℹ️ About Network Summary", expanded=False):
        if is_no_submain_system:
            st.markdown("""
            **Network Summary Table** shows the pipe network design for the **farthest (critical) path**:
            - **Sprinkler Line**: Farthest sprinkler line from water source
            - **Lateral Line**: Farthest lateral from mainline inlet
            - **Mainline(s)**: All mainline segments (connects directly to laterals, no submain)
            
            ℹ️ *This system has no submain - the mainline connects directly to lateral lines.*
            """)
        else:
            st.markdown("""
            **Network Summary Table** shows the pipe network design for the **farthest (critical) path**:
            - **Sprinkler Line**: Farthest sprinkler line from water source
            - **Lateral Line**: Farthest lateral from submain inlet
            - **Submain**: Farthest submain from mainline
            - **Mainline(s)**: All mainline segments (connects to pump)
            """)
    
    # Function to get design data (prioritize saved project_data over temp state)
    def get_design_data(saved_key, temp_key):
        """Get design data prioritizing saved project data over temp state"""
        if saved_key in st.session_state.project_data:
            return st.session_state.project_data[saved_key]
        elif temp_key in st.session_state:
            return st.session_state[temp_key]
        return None
    
    # Collect all design data for the summary table
    summary_rows = []
    designs_found = {
        'sprinkler': False,
        'lateral': False,
        'submain': False,
        'mainline': False
    }
    
    # 1. Sprinkler Line Design (Farthest sprinkler line - single design)
    sprinkler_design = get_design_data('sprinkler_line_design', 'temp_sprinkler_line_design')
    
    if sprinkler_design and 'segments' in sprinkler_design:
        designs_found['sprinkler'] = True
        for seg in sprinkler_design['segments']:
            summary_rows.append({
                'Line Type': '🌊 Sprinkler Line (Farthest)',
                'Position': seg.get('position', ''),
                'Flow (m³/h)': seg.get('flow_m3h', 0),
                'Pipe Ø (mm)': seg.get('pipe_nominal_mm', ''),
                'Friction Loss (m)': seg.get('friction_loss_m', 0)
            })
    
    # 2. Lateral Design (Farthest lateral - single design)
    lateral_design = get_design_data('lateral_design', 'temp_lateral_design')
    
    if lateral_design and 'segments' in lateral_design:
        designs_found['lateral'] = True
        for seg in lateral_design['segments']:
            summary_rows.append({
                'Line Type': '📏 Lateral Line (Farthest)',
                'Position': seg.get('position', ''),
                'Flow (m³/h)': seg.get('flow_m3h', 0),
                'Pipe Ø (mm)': seg.get('pipe_nominal_mm', ''),
                'Friction Loss (m)': seg.get('friction_loss_m', 0)
            })
    
    # 3. Submain Design - Find the FARTHEST submain (only if system has submains)
    # Collect all saved submain designs
    submain_designs = {}
    
    # Only check for submain designs if this is NOT a no-submain system
    if not is_no_submain_system:
        # Check project_data for saved submain designs
        for key in st.session_state.project_data.keys():
            if key.startswith('submain_') and key.endswith('_design') and not key.startswith('temp_'):
                try:
                    idx = int(key.split('_')[1])
                    submain_designs[idx] = st.session_state.project_data[key]
                except (ValueError, IndexError):
                    pass
        
        # Also check temp state
        for key in st.session_state.keys():
            if key.startswith('temp_submain_') and key.endswith('_design'):
                try:
                    idx = int(key.split('_')[2])
                    if idx not in submain_designs:  # Only add if not already saved
                        submain_designs[idx] = st.session_state[key]
                except (ValueError, IndexError):
                    pass
    
    # Use the farthest submain (submain 0 is typically the farthest)
    if submain_designs:
        designs_found['submain'] = True
        # Get submain 0 (farthest) or the lowest index available
        farthest_idx = min(submain_designs.keys())
        farthest_submain = submain_designs[farthest_idx]
        
        if 'segments' in farthest_submain:
            for seg in farthest_submain['segments']:
                summary_rows.append({
                    'Line Type': f'🔀 Submain (Farthest)',
                    'Position': seg.get('position', ''),
                    'Flow (m³/h)': seg.get('flow_m3h', 0),
                    'Pipe Ø (mm)': seg.get('pipe_nominal_mm', ''),
                    'Friction Loss (m)': seg.get('friction_loss_m', 0)
                })
    elif is_no_submain_system:
        # Mark submain as "N/A" for no-submain systems
        designs_found['submain'] = True  # Consider it "done" since it's not applicable
    
    # 4. Mainline Designs - Include ALL mainlines (ONE ROW PER MAINLINE with aggregated data)
    mainline_designs = {}
    
    # Check project_data for saved mainline designs
    for key in st.session_state.project_data.keys():
        if key.startswith('mainline_') and key.endswith('_design') and not key.startswith('temp_'):
            try:
                idx = int(key.split('_')[1])
                mainline_designs[idx] = st.session_state.project_data[key]
            except (ValueError, IndexError):
                pass
    
    # Also check temp state (only if not already in saved designs)
    for key in st.session_state.keys():
        if key.startswith('temp_mainline_') and key.endswith('_design'):
            try:
                idx = int(key.split('_')[2])
                if idx not in mainline_designs:  # Only add if not already saved
                    mainline_designs[idx] = st.session_state[key]
            except (ValueError, IndexError):
                pass
    
    # Add ONE ROW PER MAINLINE (aggregate segments)
    if mainline_designs:
        designs_found['mainline'] = True
        n_mainlines = len(mainline_designs)
        for ml_idx in sorted(mainline_designs.keys()):
            mainline_design = mainline_designs[ml_idx]
            if 'segments' in mainline_design:
                segments = mainline_design['segments']
                
                # Aggregate data for this mainline
                total_friction = sum(seg.get('head_loss_m', seg.get('friction_loss_m', 0)) for seg in segments)
                max_flow = max(seg.get('flow_m3h', 0) for seg in segments)  # Inlet flow (highest)
                
                # Get pipe sizes used (list unique sizes)
                pipe_sizes = list(set(seg.get('pipe_nominal_mm', '') for seg in segments))
                pipe_sizes_str = ', '.join(str(s) for s in sorted(pipe_sizes, reverse=True))
                
                # Label
                label = f'🚰 Mainline {ml_idx + 1}' if n_mainlines > 1 else '🚰 Mainline'
                
                # Position info - show segment count if multiple
                if len(segments) > 1:
                    position = f"{len(segments)} segments"
                else:
                    position = "1 segment"
                
                summary_rows.append({
                    'Line Type': label,
                    'Position': position,
                    'Flow (m³/h)': max_flow,
                    'Pipe Ø (mm)': pipe_sizes_str,
                    'Friction Loss (m)': total_friction
                })
    
    # Display the summary table
    if summary_rows:
        st.markdown("### 📋 Farthest Path Pipe Network Summary")
        
        df_summary = pd.DataFrame(summary_rows)
        
        # Define colors for each line type
        def highlight_line_type(row):
            line_type = row['Line Type']
            if 'Sprinkler' in line_type:
                return ['background-color: #e3f2fd'] * len(row)  # Light blue
            elif 'Lateral' in line_type:
                return ['background-color: #e8f5e9'] * len(row)  # Light green
            elif 'Submain' in line_type:
                return ['background-color: #fff3e0'] * len(row)  # Light orange
            elif 'Mainline' in line_type:
                return ['background-color: #fce4ec'] * len(row)  # Light pink
            return [''] * len(row)
        
        # Format numeric columns to 2 decimal places
        format_dict = {
            'Flow (m³/h)': '{:.2f}',
            'Friction Loss (m)': '{:.2f}'
        }
        
        styled_df = df_summary.style.apply(highlight_line_type, axis=1).format(format_dict)
        
        st.dataframe(styled_df, width="stretch", hide_index=True, height=400)
        
        # Summary statistics
        st.markdown("---")
        st.markdown("### 📊 Critical Path Statistics")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_friction = df_summary['Friction Loss (m)'].sum()
            st.metric("🔻 Total Friction Loss", f"{total_friction:.2f} m")
        
        with col2:
            max_flow = df_summary['Flow (m³/h)'].max()
            st.metric("💧 Max Flow", f"{max_flow:.2f} m³/h")
        
        with col3:
            pipe_sizes = df_summary['Pipe Ø (mm)'].unique()
            st.metric("🔧 Pipe Sizes Used", f"{len(pipe_sizes)}")
        
        with col4:
            total_segments = len(df_summary)
            st.metric("📐 Total Segments", f"{total_segments}")
        
        # Pipe sizes breakdown by line type
        st.markdown("---")
        st.markdown("### 🔧 Pipe Sizes Breakdown by Line Type")
        
        # Group by line type and pipe size
        pipe_summary = df_summary.groupby(['Line Type', 'Pipe Ø (mm)']).agg({
            'Flow (m³/h)': 'max',
            'Friction Loss (m)': 'sum'
        }).reset_index()
        pipe_summary.columns = ['Line Type', 'Pipe Ø (mm)', 'Max Flow (m³/h)', 'Total Friction Loss (m)']
        
        format_dict_summary = {
            'Max Flow (m³/h)': '{:.2f}',
            'Total Friction Loss (m)': '{:.2f}'
        }
        
        st.dataframe(
            pipe_summary.style.format(format_dict_summary),
            width="stretch",
            hide_index=True
        )
        
        # Save button
        st.markdown("---")
        col_save1, col_save2, col_save3 = st.columns([1, 2, 1])
        with col_save2:
            if st.button("💾 Save Network Summary", type="primary", width="stretch", key="save_network_summary_btn"):
                # Compile summary data for saving
                network_summary_data = {
                    'summary_table': summary_rows,
                    'total_friction_loss_m': round(total_friction, 2),
                    'max_flow_m3h': round(max_flow, 2),
                    'pipe_sizes_used': list(pipe_sizes),
                    'total_segments': total_segments,
                    'designs_included': designs_found,
                    'pipe_breakdown': pipe_summary.to_dict('records')
                }
                
                st.session_state.project_data['network_summary'] = network_summary_data
                st.success("✅ Network Summary saved! It will be included when you save to cloud.")
        
        # Show status of each design
        st.markdown("---")
        st.markdown("### 📊 Design Status")
        
        status_cols = st.columns(4)
        with status_cols[0]:
            if designs_found['sprinkler']:
                st.success("✅ Sprinkler Line")
            else:
                st.warning("⚠️ Sprinkler Line - Not designed")
        
        with status_cols[1]:
            if designs_found['lateral']:
                st.success("✅ Lateral Line")
            else:
                st.warning("⚠️ Lateral Line - Not designed")
        
        with status_cols[2]:
            if is_no_submain_system:
                st.info("ℹ️ Submain - N/A (no submain)")
            elif designs_found['submain']:
                st.success("✅ Submain")
            else:
                st.warning("⚠️ Submain - Not designed")
        
        with status_cols[3]:
            if designs_found['mainline']:
                st.success("✅ Mainline")
            else:
                st.warning("⚠️ Mainline - Not designed")
        
        # Tip for dynamic updates
        st.caption("💡 **Tip**: This summary automatically updates when you save changes in any design tab. Make sure to click 'Save' in each design tab after making changes.")
        
    else:
        st.warning("📝 No pipe designs have been saved yet.")
        
        # Different getting started message based on system type
        if is_no_submain_system:
            st.markdown("""
            ### Getting Started (No-Submain System)
            
            Your system has no submain lines. Complete the following designs in order:
            
            1. **🌊 Sprinkler Line** - Design and save the farthest sprinkler line
            2. **📏 Lateral Design** - Design and save the farthest lateral pipe
            3. ~~**🔀 Submain Design**~~ - *Not applicable (no submains)*
            4. **🚰 Mainline Design** - Design and save all mainline pipes
            
            After saving designs in each tab, return here to see the complete network summary.
            
            ---
            
            **Note**: In your configuration, the mainline connects directly to lateral lines.
            """)
        else:
            st.markdown("""
            ### Getting Started
            
            Complete the following designs in order and **save each one**:
            
            1. **🌊 Sprinkler Line** - Design and save the farthest sprinkler line
            2. **📏 Lateral Design** - Design and save the farthest lateral pipe
            3. **🔀 Submain Design** - Design and save the submain pipes
            4. **🚰 Mainline Design** - Design and save all mainline pipes
            
            After saving designs in each tab, return here to see the complete network summary.
            
            ---
            
            **Note**: The summary shows the **critical hydraulic path** - the farthest point from the water source
            which requires the most pressure to reach.
            """)


def create_pipe_sizing_diagram(segments, title="Pipe Sizing Diagram"):
    """Create generic pipe sizing diagram"""
    if not segments:
        return go.Figure()
    
    return create_lateral_line_diagram(segments, segments[0]['length_m'] if segments else 12)


def create_network_schematic():
    """Create complete network schematic"""
    st.info("Network schematic visualization will be implemented here.")
