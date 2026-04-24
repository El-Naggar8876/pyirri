"""
Cost Estimation Module - Auto-Aggregated System
Automatically pulls all component data from design modules to create comprehensive cost estimates.

Data Sources:
- sprinkler_data: Sprinkler selection (model, flow, pressure, spacing)
- layout_data: Field layout, sprinkler counts, pipe lengths
- sprinkler_line_design: Sprinkler line pipe segments with sizes
- lateral_design: Lateral pipe segments with sizes  
- pipe_network: Network design valves and configurations
- network_summary: Complete network summary with pipe breakdown
- pump_data: Pump selection including power, model, configuration
- hydraulic_design: Head requirements, pressure regulators
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

# ============================================================================
# DATA EXTRACTION HELPERS
# ============================================================================

@dataclass
class ExtractedComponent:
    """Represents an extracted component for costing"""
    category: str
    item: str
    description: str
    unit: str
    quantity: float
    unit_cost: float
    source: str  # Where data came from
    confidence: str  # 'exact', 'calculated', 'estimated'

def safe_get(data: dict, *keys, default=None):
    """Safely navigate nested dictionaries"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data

def get_project_data() -> dict:
    """Get project_data with safe defaults"""
    if 'project_data' not in st.session_state:
        st.session_state.project_data = {}
    return st.session_state.project_data

def extract_sprinkler_components() -> List[ExtractedComponent]:
    """Extract sprinkler-related components from design data"""
    components = []
    project = get_project_data()
    
    sprinkler_data = project.get('sprinkler_data', {})
    layout_data = project.get('layout_data', {})
    operational_data = project.get('operational_data', {})
    hydraulic = project.get('hydraulic_design', {})
    
    # Get total sprinklers - check multiple sources in priority order
    n_sprinklers = 0
    sprinkler_source = 'unknown'
    
    # Priority 1: operational_data.total_sprinklers (from Operational Design)
    if operational_data.get('total_sprinklers', 0) > 0:
        n_sprinklers = operational_data.get('total_sprinklers', 0)
        sprinkler_source = 'operational_data.total_sprinklers'
    # Priority 2: layout_data.total_sprinklers
    elif layout_data.get('total_sprinklers', 0) > 0:
        n_sprinklers = layout_data.get('total_sprinklers', 0)
        sprinkler_source = 'layout_data.total_sprinklers'
    # Priority 3: Calculate from layout dimensions
    elif layout_data.get('n_sprinklers_length', 0) > 0 and layout_data.get('n_sprinklers_width', 0) > 0:
        n_length = layout_data.get('n_sprinklers_length', 0)
        n_width = layout_data.get('n_sprinklers_width', 0)
        n_sprinklers = n_length * n_width
        sprinkler_source = 'layout_data (calculated)'
    # Priority 4: Calculate from operational design parameters
    elif operational_data.get('N_sprinklers_line', 0) > 0 and operational_data.get('N_sprinkler_lines', 0) > 0:
        n_per_line = operational_data.get('N_sprinklers_line', 0)
        n_lines = operational_data.get('N_sprinkler_lines', 0)
        n_sprinklers = n_per_line * n_lines
        sprinkler_source = 'operational_data (calculated)'
    
    # Get sprinkler model details
    model = sprinkler_data.get('model', 'Standard Sprinkler')
    pressure = sprinkler_data.get('pressure', 'N/A')
    nozzle = sprinkler_data.get('nozzle', 'N/A')
    flow_rate = sprinkler_data.get('flow', 0)
    diameter = sprinkler_data.get('diameter', 0)
    
    if n_sprinklers > 0:
        # Sprinkler Heads
        description = f'{model}'
        if nozzle and nozzle != 'N/A':
            description += f' - Nozzle: {nozzle}'
        if pressure and pressure != 'N/A':
            description += f', {pressure} kPa'
        if flow_rate and flow_rate > 0:
            description += f', {flow_rate} L/h'
        
        components.append(ExtractedComponent(
            category='Sprinkler Equipment',
            item='Sprinkler Heads',
            description=description,
            unit='pcs',
            quantity=n_sprinklers,
            unit_cost=15.0,  # Default, will be overridden by cost database
            source=sprinkler_source,
            confidence='exact'
        ))
        
        # Riser assemblies
        components.append(ExtractedComponent(
            category='Sprinkler Equipment',
            item='Riser Assemblies',
            description='Riser pipe with swing joint fittings',
            unit='pcs',
            quantity=n_sprinklers,
            unit_cost=8.0,
            source=sprinkler_source,
            confidence='exact'
        ))
        
        # Pressure regulators (if used)
        use_regulators = hydraulic.get('use_regulators', True)
        if use_regulators:
            components.append(ExtractedComponent(
                category='Sprinkler Equipment',
                item='Pressure Regulators',
                description='In-line pressure regulators',
                unit='pcs',
                quantity=n_sprinklers,
                unit_cost=12.0,
                source='hydraulic_design.use_regulators',
                confidence='exact'
            ))
    elif sprinkler_data:
        # Even if no count available, show what sprinkler is selected with estimated quantity
        description = f'{model}'
        if nozzle and nozzle != 'N/A':
            description += f' - Nozzle: {nozzle}'
        if pressure and pressure != 'N/A':
            description += f', {pressure} kPa'
        
        components.append(ExtractedComponent(
            category='Sprinkler Equipment',
            item='Sprinkler Heads',
            description=description + ' (quantity TBD - complete Operational Design)',
            unit='pcs',
            quantity=0,
            unit_cost=15.0,
            source='sprinkler_data (no count)',
            confidence='estimated'
        ))
    
    return components

def extract_pipe_components() -> List[ExtractedComponent]:
    """
    Extract pipe components from all design sources.
    
    IMPORTANT: Pipe Network Design only designs the FARTHEST line of each type.
    To get total pipe quantities, we must multiply by the number of lines:
    
    - Sprinkler Lines: N_sprinkler_lines × farthest sprinkler line length
    - Lateral Lines: n_plots (or n_laterals) × farthest lateral length
    - Submain Lines: Sum all submain segment lengths (already full length)
    - Mainline: Sum all mainline segment lengths (already full length)
    """
    components = []
    project = get_project_data()
    
    # Dictionary to track pipes: {(size_mm, pipe_type): {'total_length': 0, 'sources': [], 'multiplier': 1}}
    pipe_inventory = {}
    
    # Helper to add pipe to inventory
    def add_pipe(size, length_per_line, n_lines, source, pipe_type):
        """Add pipe to inventory with multiplier for total calculation"""
        try:
            size = int(size) if size else 0
            length_per_line = float(length_per_line) if length_per_line else 0
            n_lines = int(n_lines) if n_lines else 1
        except (ValueError, TypeError):
            return
        
        if size > 0 and length_per_line > 0:
            key = (size, pipe_type)
            total_length = length_per_line * n_lines
            
            if key not in pipe_inventory:
                pipe_inventory[key] = {
                    'total_length': 0, 
                    'length_per_line': 0,
                    'n_lines': n_lines,
                    'sources': []
                }
            pipe_inventory[key]['total_length'] += total_length
            pipe_inventory[key]['length_per_line'] += length_per_line
            if source not in pipe_inventory[key]['sources']:
                pipe_inventory[key]['sources'].append(source)
    
    # =========================================================================
    # GET MULTIPLIERS FROM OPERATIONAL DESIGN
    # =========================================================================
    operational_data = project.get('operational_data', {})
    
    # Number of sprinkler lines (from Operational Design)
    N_sprinkler_lines = operational_data.get('N_sprinkler_lines', 1)
    
    # Number of laterals = number of plots/subplots
    # Each plot typically has one lateral
    total_subplots = operational_data.get('total_subplots', 1)
    effective_subplots = operational_data.get('effective_subplots', total_subplots)
    n_laterals = max(1, int(effective_subplots))
    
    # For irregular fields, use effective_subplots which accounts for partial plots
    irregular_field_factor = effective_subplots / total_subplots if total_subplots > 0 else 1.0
    
    # =========================================================================
    # 1. SPRINKLER LINES - Multiply farthest line length by N_sprinkler_lines
    # =========================================================================
    sprinkler_line = project.get('sprinkler_line_design', {})
    if sprinkler_line:
        segments = sprinkler_line.get('segments', [])
        farthest_line_length = sprinkler_line.get('total_length_m', 0)
        
        # If we have detailed segments, extract by pipe size
        if segments:
            for seg in segments:
                size = seg.get('pipe_nominal_mm', 0)
                seg_length = seg.get('length_m', seg.get('segment_length_m', 0))
                if size > 0 and seg_length > 0:
                    # Total = segment_length × N_sprinkler_lines
                    add_pipe(size, seg_length, N_sprinkler_lines, 
                            f'sprinkler_line × {N_sprinkler_lines}', 'Sprinkler Line')
        elif farthest_line_length > 0:
            # Fallback: use default size 32mm
            add_pipe(32, farthest_line_length, N_sprinkler_lines,
                    f'sprinkler_line × {N_sprinkler_lines}', 'Sprinkler Line')
    
    # =========================================================================
    # 2. LATERAL LINES - Multiply farthest lateral length by n_laterals (n_plots)
    # =========================================================================
    lateral_design = project.get('lateral_design', {})
    if lateral_design:
        segments = lateral_design.get('segments', [])
        farthest_lateral_length = lateral_design.get('total_length_m', 0)
        
        if segments:
            for seg in segments:
                size = seg.get('pipe_nominal_mm', 0)
                seg_length = seg.get('length_m', seg.get('segment_length_m', 0))
                if size > 0 and seg_length > 0:
                    # Total = segment_length × n_laterals
                    add_pipe(size, seg_length, n_laterals,
                            f'lateral × {n_laterals} plots', 'Lateral')
        elif farthest_lateral_length > 0:
            add_pipe(50, farthest_lateral_length, n_laterals,
                    f'lateral × {n_laterals} plots', 'Lateral')
    
    # =========================================================================
    # 3. SUBMAIN LINES - Sum all submain designs (already full lengths)
    # =========================================================================
    # Check for multiple submain designs (submain_0_design, submain_1_design, etc.)
    submain_count = 0
    for key in project.keys():
        if key.startswith('submain_') and key.endswith('_design'):
            try:
                submain_design = project[key]
                if submain_design and 'segments' in submain_design:
                    submain_count += 1
                    for seg in submain_design['segments']:
                        size = seg.get('pipe_nominal_mm', 0)
                        seg_length = seg.get('length_m', seg.get('segment_length_m', 0))
                        if size > 0 and seg_length > 0:
                            # Submain lengths are already total (not per-line)
                            add_pipe(size, seg_length, 1, f'submain_{key}', 'Submain')
            except (KeyError, TypeError):
                pass
    
    # Also check temp submain designs
    for key in list(st.session_state.keys()):
        if key.startswith('temp_submain_') and key.endswith('_design'):
            try:
                submain_design = st.session_state[key]
                if submain_design and 'segments' in submain_design:
                    for seg in submain_design['segments']:
                        size = seg.get('pipe_nominal_mm', 0)
                        seg_length = seg.get('length_m', seg.get('segment_length_m', 0))
                        if size > 0 and seg_length > 0:
                            add_pipe(size, seg_length, 1, f'{key}', 'Submain')
            except (KeyError, TypeError):
                pass
    
    # =========================================================================
    # 4. MAINLINE - Sum all mainline designs (already full lengths)
    # =========================================================================
    mainline_count = 0
    for key in project.keys():
        if key.startswith('mainline_') and key.endswith('_design'):
            try:
                mainline_design = project[key]
                if mainline_design and 'segments' in mainline_design:
                    mainline_count += 1
                    for seg in mainline_design['segments']:
                        size = seg.get('pipe_nominal_mm', 0)
                        seg_length = seg.get('length_m', seg.get('segment_length_m', 0))
                        if size > 0 and seg_length > 0:
                            # Mainline lengths are already total
                            add_pipe(size, seg_length, 1, f'mainline_{key}', 'Mainline')
            except (KeyError, TypeError):
                pass
    
    # Also check temp mainline designs
    for key in list(st.session_state.keys()):
        if key.startswith('temp_mainline_') and key.endswith('_design'):
            try:
                mainline_design = st.session_state[key]
                if mainline_design and 'segments' in mainline_design:
                    for seg in mainline_design['segments']:
                        size = seg.get('pipe_nominal_mm', 0)
                        seg_length = seg.get('length_m', seg.get('segment_length_m', 0))
                        if size > 0 and seg_length > 0:
                            add_pipe(size, seg_length, 1, f'{key}', 'Mainline')
            except (KeyError, TypeError):
                pass
    
    # =========================================================================
    # 5. FALLBACK - Use layout_data if no detailed designs
    # =========================================================================
    layout_data = project.get('layout_data', {})
    
    # Check if we got any sprinkler line data
    has_sprinkler_pipe = any('Sprinkler' in key[1] for key in pipe_inventory.keys())
    if not has_sprinkler_pipe:
        total_sprinkler_pipe = layout_data.get('total_sprinkler_pipe_length', 0)
        if total_sprinkler_pipe > 0:
            add_pipe(32, total_sprinkler_pipe, 1, 'layout_data', 'Sprinkler Line')
    
    # Check if we got any lateral data
    has_lateral_pipe = any('Lateral' in key[1] for key in pipe_inventory.keys())
    if not has_lateral_pipe:
        total_lateral = layout_data.get('total_lateral_length', 0)
        if total_lateral > 0:
            add_pipe(50, total_lateral, 1, 'layout_data', 'Lateral')
    
    # Check if we got any submain data
    has_submain_pipe = any('Submain' in key[1] for key in pipe_inventory.keys())
    if not has_submain_pipe:
        total_submain = layout_data.get('total_submain_length', 0)
        if total_submain > 0:
            add_pipe(75, total_submain, 1, 'layout_data', 'Submain')
    
    # Check if we got any mainline data
    has_mainline_pipe = any('Mainline' in key[1] for key in pipe_inventory.keys())
    if not has_mainline_pipe:
        total_mainline = layout_data.get('total_mainline_length', 0)
        if total_mainline > 0:
            add_pipe(110, total_mainline, 1, 'layout_data', 'Mainline')
    
    # =========================================================================
    # CONVERT INVENTORY TO COMPONENTS
    # =========================================================================
    for (size, pipe_type), data in sorted(pipe_inventory.items()):
        # Unit cost based on pipe size (approximate)
        # Smaller pipes cheaper, larger pipes more expensive
        if size <= 32:
            unit_cost = size * 0.10  # ~$3.20/m for 32mm
        elif size <= 63:
            unit_cost = size * 0.12  # ~$7.56/m for 63mm
        elif size <= 110:
            unit_cost = size * 0.15  # ~$16.50/m for 110mm
        else:
            unit_cost = size * 0.18  # Larger pipes
        
        # Determine confidence level
        if 'layout_data' in str(data['sources']):
            confidence = 'estimated'
        elif '×' in str(data['sources']):
            confidence = 'calculated'
        else:
            confidence = 'exact'
        
        components.append(ExtractedComponent(
            category='Piping',
            item=f'{pipe_type} Pipe {int(size)}mm',
            description=f'PVC/PE Pipe {int(size)}mm - {pipe_type}',
            unit='m',
            quantity=round(data['total_length'], 1),
            unit_cost=unit_cost,
            source=', '.join(data['sources']),
            confidence=confidence
        ))
    
    # Add summary info for tracking
    if pipe_inventory:
        # Log the multipliers used for debugging/verification
        multiplier_info = f"N_sprinkler_lines={N_sprinkler_lines}, n_laterals={n_laterals}"
        if irregular_field_factor < 1.0:
            multiplier_info += f", irregular_factor={irregular_field_factor:.2f}"
    
    return components

def extract_valve_components() -> List[ExtractedComponent]:
    """Extract valve components from design data"""
    components = []
    project = get_project_data()
    
    valve_counts = {
        'gate_valve': {'count': 0, 'sizes': [], 'sources': []},
        'air_valve': {'count': 0, 'sources': []},
        'check_valve': {'count': 0, 'sources': []},
        'pressure_relief': {'count': 0, 'sources': []}
    }
    
    # Check pipe_network for valves
    pipe_network = project.get('pipe_network', {})
    if pipe_network:
        # Look for valve data in the network
        valves = pipe_network.get('valves', [])
        if isinstance(valves, list):
            valve_counts['gate_valve']['count'] += len(valves)
            valve_counts['gate_valve']['sources'].append('pipe_network.valves')
        
        # Submain valves
        n_submains = pipe_network.get('mainline', {}).get('n_submains', 0)
        if n_submains > 0:
            valve_counts['gate_valve']['count'] += n_submains
            valve_counts['gate_valve']['sources'].append('pipe_network.n_submains')
    
    # Check layout data for valve locations
    layout_data = project.get('layout_data', {})
    valve_locations = layout_data.get('valve_locations', '')
    if valve_locations:
        # Try to count valves from description
        if 'submain' in valve_locations.lower():
            valve_counts['gate_valve']['sources'].append('layout_data')
    
    # Ensure minimum valves for a working system
    if valve_counts['gate_valve']['count'] == 0:
        # Estimate based on field size
        area = project.get('area', 0)
        if area > 0:
            # Roughly 1 valve per 2-3 hectares + main control valve
            estimated_valves = max(3, int(area / 2.5) + 1)
            valve_counts['gate_valve']['count'] = estimated_valves
            valve_counts['gate_valve']['sources'].append('estimated from area')
    
    # Air valves - typically at high points and ends
    if valve_counts['air_valve']['count'] == 0:
        valve_counts['air_valve']['count'] = max(2, valve_counts['gate_valve']['count'] // 3)
        valve_counts['air_valve']['sources'].append('estimated')
    
    # Add main check valve at pump
    pump_data = project.get('pump_data', {})
    if pump_data.get('selected_pump_id') or pump_data.get('selected_model'):
        valve_counts['check_valve']['count'] = 1
        valve_counts['check_valve']['sources'].append('pump_data')
    
    # Create components
    if valve_counts['gate_valve']['count'] > 0:
        components.append(ExtractedComponent(
            category='Valves & Fittings',
            item='Gate Valves',
            description='Manual gate valves for zone control',
            unit='pcs',
            quantity=valve_counts['gate_valve']['count'],
            unit_cost=45.0,
            source=', '.join(valve_counts['gate_valve']['sources']),
            confidence='calculated' if 'estimated' not in str(valve_counts['gate_valve']['sources']) else 'estimated'
        ))
    
    if valve_counts['air_valve']['count'] > 0:
        components.append(ExtractedComponent(
            category='Valves & Fittings',
            item='Air Release Valves',
            description='Automatic air release valves',
            unit='pcs',
            quantity=valve_counts['air_valve']['count'],
            unit_cost=35.0,
            source=', '.join(valve_counts['air_valve']['sources']),
            confidence='estimated'
        ))
    
    if valve_counts['check_valve']['count'] > 0:
        components.append(ExtractedComponent(
            category='Valves & Fittings',
            item='Check Valve',
            description='Non-return valve at pump discharge',
            unit='pcs',
            quantity=valve_counts['check_valve']['count'],
            unit_cost=65.0,
            source=', '.join(valve_counts['check_valve']['sources']),
            confidence='exact'
        ))
    
    return components

def extract_pump_components() -> List[ExtractedComponent]:
    """Extract pump and related equipment from pump selection"""
    components = []
    project = get_project_data()
    
    pump_data = project.get('pump_data', {})
    
    if pump_data:
        model = pump_data.get('selected_model', pump_data.get('model', ''))
        brand = pump_data.get('selected_brand', '')
        power_kw = pump_data.get('total_power_kw', pump_data.get('selected_power_kw', 0))
        num_pumps = pump_data.get('num_pumps', 1)
        config = pump_data.get('pump_configuration', 'Single')
        
        if model or power_kw > 0:
            # Calculate pump cost based on power
            if power_kw > 0:
                # $45/kW is a reasonable estimate for installed pump cost
                unit_cost = power_kw * 45 / num_pumps
            else:
                unit_cost = 3000  # Default estimate
            
            description = f'{brand} {model}'.strip() if brand else model
            if config and config != 'Single':
                description += f' ({config} configuration)'
            
            components.append(ExtractedComponent(
                category='Major Equipment',
                item='Pump Unit(s)',
                description=description or f'{power_kw:.1f} kW centrifugal pump',
                unit='set',
                quantity=num_pumps,
                unit_cost=unit_cost,
                source='pump_data',
                confidence='exact' if model else 'estimated'
            ))
            
            # Motor (if separate from pump)
            if power_kw > 0:
                motor_cost = power_kw * 35  # $35/kW for motor
                components.append(ExtractedComponent(
                    category='Major Equipment',
                    item='Electric Motor',
                    description=f'{power_kw:.1f} kW electric motor',
                    unit='pcs',
                    quantity=num_pumps,
                    unit_cost=motor_cost / num_pumps,
                    source='pump_data.total_power_kw',
                    confidence='calculated'
                ))
    
    # Always include filtration and control
    components.append(ExtractedComponent(
        category='Major Equipment',
        item='Filtration System',
        description='Screen or disc filter system',
        unit='set',
        quantity=1,
        unit_cost=1500.0,
        source='default',
        confidence='estimated'
    ))
    
    components.append(ExtractedComponent(
        category='Major Equipment',
        item='Control Panel',
        description='Pump control and automation panel',
        unit='set',
        quantity=1,
        unit_cost=2000.0,
        source='default',
        confidence='estimated'
    ))
    
    return components

def extract_fitting_components(pipe_cost_total: float) -> List[ExtractedComponent]:
    """Calculate fittings as percentage of pipe cost"""
    components = []
    
    if pipe_cost_total > 0:
        fittings_pct = 15.0  # Default 15%
        fittings_cost = pipe_cost_total * (fittings_pct / 100)
        
        components.append(ExtractedComponent(
            category='Piping',
            item='Pipe Fittings',
            description='Elbows, tees, couplings, reducers, etc.',
            unit='lot',
            quantity=1,
            unit_cost=fittings_cost,
            source=f'{fittings_pct:.0f}% of pipe cost',
            confidence='calculated'
        ))
    
    return components

def get_all_extracted_components() -> List[ExtractedComponent]:
    """Master function to extract all components"""
    all_components = []
    
    # Extract from all sources
    all_components.extend(extract_sprinkler_components())
    pipe_components = extract_pipe_components()
    all_components.extend(pipe_components)
    all_components.extend(extract_valve_components())
    all_components.extend(extract_pump_components())
    
    # Calculate fittings based on pipe cost
    pipe_cost_total = sum(c.quantity * c.unit_cost for c in pipe_components)
    all_components.extend(extract_fitting_components(pipe_cost_total))
    
    return all_components

def get_data_completeness_report() -> Dict:
    """Generate a report on data completeness"""
    project = get_project_data()
    
    report = {
        'sprinkler_data': {
            'available': 'sprinkler_data' in project and bool(project['sprinkler_data']),
            'fields': list(project.get('sprinkler_data', {}).keys())
        },
        'layout_data': {
            'available': 'layout_data' in project and bool(project['layout_data']),
            'fields': list(project.get('layout_data', {}).keys())
        },
        'sprinkler_line_design': {
            'available': 'sprinkler_line_design' in project and bool(project['sprinkler_line_design']),
            'fields': list(project.get('sprinkler_line_design', {}).keys())
        },
        'lateral_design': {
            'available': 'lateral_design' in project and bool(project['lateral_design']),
            'fields': list(project.get('lateral_design', {}).keys())
        },
        'network_summary': {
            'available': 'network_summary' in project and bool(project['network_summary']),
            'fields': list(project.get('network_summary', {}).keys())
        },
        'pump_data': {
            'available': 'pump_data' in project and bool(project['pump_data']),
            'fields': list(project.get('pump_data', {}).keys())
        },
        'hydraulic_design': {
            'available': 'hydraulic_design' in project and bool(project['hydraulic_design']),
            'fields': list(project.get('hydraulic_design', {}).keys())
        }
    }
    
    return report

# ============================================================================
# MAIN DISPLAY FUNCTIONS
# ============================================================================

def show():
    st.markdown('<h1 class="main-header">Cost Estimation</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    <b>Smart Auto-Aggregated Cost Estimation</b><br>
    This module automatically extracts component data from all your design modules 
    (sprinklers, pipes, valves, pumps) to generate comprehensive cost estimates.
    <br><br>
    <b>Tip:</b> Set your <b>Unit Costs</b> first, then view the <b>Auto BOQ</b> to see calculated totals.
    </div>
    """, unsafe_allow_html=True)
    
    # Show data status
    show_data_status()
    
    tabs = st.tabs(["💰 Unit Costs", "📊 Auto BOQ", "📈 Cost Summary", "💵 Economic Analysis"])
    
    with tabs[0]:
        show_unit_costs()
    
    with tabs[1]:
        show_auto_bill_of_quantities()
    
    with tabs[2]:
        show_cost_summary()
    
    with tabs[3]:
        show_economic_analysis()

def show_data_status():
    """Show status of available design data"""
    report = get_data_completeness_report()
    
    with st.expander("📋 Design Data Status", expanded=False):
        cols = st.columns(4)
        
        status_items = [
            ('Sprinklers', 'sprinkler_data'),
            ('Layout', 'layout_data'),
            ('Pipe Network', 'network_summary'),
            ('Pump', 'pump_data')
        ]
        
        for i, (name, key) in enumerate(status_items):
            with cols[i]:
                if report[key]['available']:
                    st.success(f"✅ {name}")
                else:
                    st.warning(f"⚠️ {name}")
        
        # Show detailed status
        st.markdown("---")
        st.markdown("**Available Data Sources:**")
        
        for key, info in report.items():
            icon = "✅" if info['available'] else "❌"
            fields_str = f" ({len(info['fields'])} fields)" if info['fields'] else ""
            st.caption(f"{icon} `{key}`{fields_str}")

def show_auto_bill_of_quantities():
    """Generate automatic bill of quantities from all design data"""
    st.markdown('<h2 class="sub-header">Auto-Generated Bill of Quantities</h2>', unsafe_allow_html=True)
    
    st.info("📊 **Smart BOQ**: This automatically extracts quantities from your Sprinkler Selection, "
            "System Layout, Pipe Network Design, and Pump Selection modules. "
            "**Unit costs are applied from the 💰 Unit Costs tab** - adjust prices there to update totals here.")
    
    # Extract all components
    components = get_all_extracted_components()
    
    if not components:
        st.warning("⚠️ No design data found. Please complete at least one design module first.")
        st.markdown("""
        **Required modules:**
        1. **Sprinkler Selection** - Select a sprinkler model
        2. **System Layout** - Define field dimensions and sprinkler count
        3. **Pipe Network Design** - Design and save pipe networks
        4. **Pump Selection** - Select a pump
        """)
        return
    
    # Get cost database for unit cost overrides
    cost_db = get_cost_database()
    
    # Apply cost database overrides
    for comp in components:
        # Override with saved unit costs where applicable
        if 'sprinkler' in comp.item.lower() and 'head' in comp.item.lower():
            comp.unit_cost = cost_db.get('sprinkler', comp.unit_cost)
        elif 'riser' in comp.item.lower():
            comp.unit_cost = cost_db.get('riser', comp.unit_cost)
        elif 'pressure regulator' in comp.item.lower():
            comp.unit_cost = cost_db.get('pressure_regulator', comp.unit_cost)
        elif 'gate valve' in comp.item.lower():
            comp.unit_cost = cost_db.get('gate_valve', comp.unit_cost)
        elif 'air' in comp.item.lower() and 'valve' in comp.item.lower():
            comp.unit_cost = cost_db.get('air_valve', comp.unit_cost)
        elif 'check valve' in comp.item.lower():
            comp.unit_cost = cost_db.get('check_valve', 65.0)
        elif 'pipe' in comp.item.lower() and 'fitting' not in comp.item.lower():
            # Get pipe size from item name
            try:
                size_str = comp.item.split('mm')[0].split()[-1]
                size = int(size_str)
                saved_cost = cost_db.get('pipe_costs', {}).get(str(size), None)
                if saved_cost:
                    comp.unit_cost = saved_cost
            except:
                pass
        elif 'filtration' in comp.item.lower():
            comp.unit_cost = cost_db.get('filter', comp.unit_cost)
        elif 'control' in comp.item.lower():
            comp.unit_cost = cost_db.get('control_system', comp.unit_cost)
    
    # Create BOQ table
    boq_data = []
    for comp in components:
        total = comp.quantity * comp.unit_cost
        boq_data.append({
            'Category': comp.category,
            'Item': comp.item,
            'Description': comp.description,
            'Unit': comp.unit,
            'Qty': comp.quantity,
            'Unit Cost ($)': comp.unit_cost,
            'Total ($)': total,
            'Source': comp.source,
            'Confidence': comp.confidence
        })
    
    df_boq = pd.DataFrame(boq_data)
    
    # Summary by category
    st.markdown("### 📦 Components by Category")
    
    categories = df_boq['Category'].unique()
    category_totals = {}
    
    for cat in categories:
        cat_df = df_boq[df_boq['Category'] == cat]
        cat_total = cat_df['Total ($)'].sum()
        category_totals[cat] = cat_total
        
        with st.expander(f"**{cat}** - ${cat_total:,.2f}", expanded=True):
            display_df = cat_df[['Item', 'Description', 'Unit', 'Qty', 'Unit Cost ($)', 'Total ($)']].copy()
            st.dataframe(
                display_df,
                hide_index=True,
                width="stretch",
                column_config={
                    "Qty": st.column_config.NumberColumn("Qty", format="%.1f"),
                    "Unit Cost ($)": st.column_config.NumberColumn("Unit Cost", format="$%.2f"),
                    "Total ($)": st.column_config.NumberColumn("Total", format="$%.2f")
                }
            )
    
    # Show pipe calculation methodology for transparency
    project = get_project_data()
    operational_data = project.get('operational_data', {})
    N_sprinkler_lines = operational_data.get('N_sprinkler_lines', 0)
    total_subplots = operational_data.get('total_subplots', 1)
    effective_subplots = operational_data.get('effective_subplots', total_subplots)
    
    # Show pipe calculation details if we have pipe data
    pipe_components = [c for c in components if c.category == 'Piping']
    if pipe_components and N_sprinkler_lines > 0:
        with st.expander("📐 **Pipe Quantity Calculation Details**", expanded=False):
            st.markdown("""
            **How pipe quantities are calculated:**
            
            Pipe Network Design only designs the **farthest line** of each type (for worst-case hydraulics).
            To get total pipe requirements, we multiply by the number of lines:
            """)
            
            calc_cols = st.columns(2)
            
            with calc_cols[0]:
                st.markdown("**Multipliers Used:**")
                st.markdown(f"- Sprinkler Lines: **{N_sprinkler_lines}** (from Operational Design)")
                st.markdown(f"- Lateral Lines (plots): **{int(effective_subplots)}** (from Operational Design)")
                if effective_subplots != total_subplots:
                    st.caption(f"  _(adjusted from {total_subplots} for irregular field)_")
                st.markdown("- Submain/Mainline: **1×** (full lengths already)")
            
            with calc_cols[1]:
                st.markdown("**Calculation:**")
                st.markdown("""
                ```
                Total Sprinkler Pipe = Farthest Line × N_sprinkler_lines
                Total Lateral Pipe = Farthest Lateral × n_plots
                Total Submain = Sum of all submain segments
                Total Mainline = Sum of all mainline segments
                ```
                """)
            
            # Show source data
            st.markdown("**Source Data Found:**")
            for comp in pipe_components:
                st.caption(f"• {comp.item}: {comp.quantity:.1f} m (from: {comp.source})")
    
    # Materials subtotal
    materials_total = df_boq['Total ($)'].sum()
    
    st.markdown("---")
    st.markdown("### 💰 Materials Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total Materials Cost", f"${materials_total:,.2f}")
    
    with col2:
        n_items = len(df_boq)
        st.metric("Line Items", f"{n_items}")
    
    with col3:
        exact_items = len([c for c in components if c.confidence == 'exact'])
        confidence_pct = (exact_items / len(components)) * 100 if components else 0
        st.metric("Data Confidence", f"{confidence_pct:.0f}%", help="Percentage of items with exact data")
    
    # Show confidence breakdown
    st.markdown("---")
    st.markdown("### 🎯 Data Confidence Analysis")
    
    conf_cols = st.columns(3)
    confidence_counts = df_boq['Confidence'].value_counts()
    
    with conf_cols[0]:
        exact_count = confidence_counts.get('exact', 0)
        st.success(f"✅ **Exact**: {exact_count} items")
        st.caption("Data directly from saved designs")
    
    with conf_cols[1]:
        calc_count = confidence_counts.get('calculated', 0)
        st.info(f"🔢 **Calculated**: {calc_count} items")
        st.caption("Derived from other design data")
    
    with conf_cols[2]:
        est_count = confidence_counts.get('estimated', 0)
        if est_count > 0:
            st.warning(f"⚠️ **Estimated**: {est_count} items")
            st.caption("Complete more design modules for accuracy")
        else:
            st.success(f"✨ **Estimated**: {est_count} items")
            st.caption("All data is exact or calculated!")
    
    # Download buttons
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        csv = df_boq.to_csv(index=False)
        st.download_button(
            label="📥 Download Full BOQ (CSV)",
            data=csv,
            file_name="irrigation_boq_detailed.csv",
            mime="text/csv"
        )
    
    with col2:
        # Summary CSV
        summary_df = pd.DataFrame({
            'Category': list(category_totals.keys()),
            'Total ($)': list(category_totals.values())
        })
        summary_csv = summary_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Summary (CSV)",
            data=summary_csv,
            file_name="irrigation_boq_summary.csv",
            mime="text/csv"
        )
    
    with col3:
        if st.button("💾 Save to Project", type="primary"):
            if 'cost_data' not in st.session_state.project_data:
                st.session_state.project_data['cost_data'] = {}
            
            st.session_state.project_data['cost_data']['boq'] = df_boq.to_dict('records')
            st.session_state.project_data['cost_data']['materials_subtotal'] = materials_total
            st.session_state.project_data['cost_data']['category_totals'] = category_totals
            st.session_state.project_data['cost_data']['auto_generated'] = True
            st.success("✅ BOQ saved to project!")

def get_cost_database() -> dict:
    """Get the cost database from session or defaults"""
    project = get_project_data()
    cost_data = project.get('cost_data', {})
    cost_db = cost_data.get('cost_database', {})
    
    # Merge with defaults
    defaults = get_default_unit_costs()
    for key, value in defaults.items():
        if key not in cost_db:
            cost_db[key] = value
    
    return cost_db

def show_unit_costs():
    """Input unit costs for materials"""
    st.markdown('<h2 class="sub-header">Unit Cost Database</h2>', unsafe_allow_html=True)
    
    st.info("💡 **Tip**: These unit costs will be used to calculate the Bill of Quantities. "
            "Adjust them to match your local market prices.")
    
    # Initialize or load cost database
    cost_db = get_cost_database()
    
    # Allow editing of unit costs
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**Sprinkler Components**")
        
        sprinkler_cost = st.number_input(
            "Sprinkler Unit Cost ($)",
            min_value=0.0,
            value=float(cost_db.get('sprinkler', 15.0)),
            step=1.0
        )
        
        riser_cost = st.number_input(
            "Riser Assembly ($)",
            min_value=0.0,
            value=float(cost_db.get('riser', 8.0)),
            step=0.5
        )
        
        pressure_regulator_cost = st.number_input(
            "Pressure Regulator ($)",
            min_value=0.0,
            value=float(cost_db.get('pressure_regulator', 12.0)),
            step=1.0
        )
    
    with col2:
        st.markdown("**Valves & Fittings**")
        
        gate_valve_cost = st.number_input(
            "Gate Valve (per unit) ($)",
            min_value=0.0,
            value=float(cost_db.get('gate_valve', 45.0)),
            step=5.0
        )
        
        air_valve_cost = st.number_input(
            "Air Valve ($)",
            min_value=0.0,
            value=float(cost_db.get('air_valve', 35.0)),
            step=5.0
        )
        
        fittings_pct = st.number_input(
            "Fittings (% of pipe cost)",
            min_value=0.0,
            max_value=100.0,
            value=float(cost_db.get('fittings_pct', 15.0)),
            step=1.0
        )
    
    # Pipe costs by size
    st.markdown("---")
    st.markdown("**Pipe Costs ($/meter)**")
    
    # Standard pipe sizes
    standard_sizes = [32, 40, 50, 63, 75, 90, 110, 125, 160, 200]
    
    pipe_costs = {}
    cols = st.columns(5)
    for i, size in enumerate(standard_sizes):
        with cols[i % 5]:
            default_cost = cost_db.get('pipe_costs', {}).get(str(size), size * 0.15)
            pipe_costs[str(size)] = st.number_input(
                f"{size}mm",
                min_value=0.0,
                value=float(default_cost),
                step=0.5,
                key=f"pipe_{size}"
            )
    
    # Equipment costs
    st.markdown("---")
    st.markdown("**Major Equipment**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Auto-calculate pump cost from pump data if available
        project = get_project_data()
        pump_data = project.get('pump_data', {})
        if pump_data.get('total_power_kw', 0) > 0:
            default_pump_cost = pump_data['total_power_kw'] * 45  # $45/kW
            st.caption(f"💡 Auto-calculated: {pump_data['total_power_kw']:.1f} kW × $45/kW")
        else:
            default_pump_cost = cost_db.get('pump', 3000.0)
        
        pump_cost = st.number_input(
            "Pump Unit Cost ($)",
            min_value=0.0,
            value=float(default_pump_cost),
            step=100.0
        )
    
    with col2:
        filter_cost = st.number_input(
            "Filtration System ($)",
            min_value=0.0,
            value=float(cost_db.get('filter', 1500.0)),
            step=100.0
        )
    
    with col3:
        control_system_cost = st.number_input(
            "Control/Automation ($)",
            min_value=0.0,
            value=float(cost_db.get('control_system', 2000.0)),
            step=100.0
        )
    
    # Installation costs
    st.markdown("---")
    st.markdown("**Installation & Overhead Costs**")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        installation_pct = st.number_input(
            "Installation Labor (% of materials)",
            min_value=0.0,
            max_value=100.0,
            value=float(cost_db.get('installation_pct', 20.0)),
            step=1.0
        )
    
    with col2:
        engineering_pct = st.number_input(
            "Engineering/Design (% of total)",
            min_value=0.0,
            max_value=20.0,
            value=float(cost_db.get('engineering_pct', 8.0)),
            step=0.5
        )
    
    with col3:
        contingency_pct = st.number_input(
            "Contingency (% of total)",
            min_value=0.0,
            max_value=20.0,
            value=float(cost_db.get('contingency_pct', 10.0)),
            step=1.0
        )
    
    # Save cost database
    st.markdown("---")
    if st.button("💾 Save Unit Costs", type="primary"):
        if 'cost_data' not in st.session_state.project_data:
            st.session_state.project_data['cost_data'] = {}
        
        st.session_state.project_data['cost_data']['cost_database'] = {
            'sprinkler': sprinkler_cost,
            'riser': riser_cost,
            'pressure_regulator': pressure_regulator_cost,
            'gate_valve': gate_valve_cost,
            'air_valve': air_valve_cost,
            'fittings_pct': fittings_pct,
            'pipe_costs': pipe_costs,
            'pump': pump_cost,
            'filter': filter_cost,
            'control_system': control_system_cost,
            'installation_pct': installation_pct,
            'engineering_pct': engineering_pct,
            'contingency_pct': contingency_pct
        }
        st.success("✅ Unit costs saved!")
        st.rerun()

def show_bill_of_quantities():
    """Generate bill of quantities"""
    st.markdown('<h2 class="sub-header">Bill of Quantities</h2>', unsafe_allow_html=True)
    
    # Check prerequisites
    if 'cost_data' not in st.session_state.project_data or \
       'cost_database' not in st.session_state.project_data['cost_data']:
        st.warning("⚠️ Please set up unit costs first.")
        return
    
    cost_db = st.session_state.project_data['cost_data']['cost_database']
    
    # Gather quantities from design
    boq_items = []
    
    # 1. Sprinklers and accessories
    if 'layout_data' in st.session_state.project_data:
        layout = st.session_state.project_data['layout_data']
        n_sprinklers = layout.get('total_sprinklers', 0)
        
        if n_sprinklers > 0:
            use_regulators = st.session_state.project_data.get('hydraulic_design', {}).get('use_regulators', True)
            
            boq_items.append({
                'Item': 'Sprinklers',
                'Description': st.session_state.project_data.get('sprinkler_data', {}).get('model', 'Standard'),
                'Unit': 'pcs',
                'Quantity': n_sprinklers,
                'Unit Cost ($)': cost_db['sprinkler'],
                'Total Cost ($)': n_sprinklers * cost_db['sprinkler']
            })
            
            boq_items.append({
                'Item': 'Riser Assemblies',
                'Description': 'Riser pipe with fittings',
                'Unit': 'pcs',
                'Quantity': n_sprinklers,
                'Unit Cost ($)': cost_db['riser'],
                'Total Cost ($)': n_sprinklers * cost_db['riser']
            })
            
            if use_regulators:
                boq_items.append({
                    'Item': 'Pressure Regulators',
                    'Description': 'In-line pressure regulators',
                    'Unit': 'pcs',
                    'Quantity': n_sprinklers,
                    'Unit Cost ($)': cost_db['pressure_regulator'],
                    'Total Cost ($)': n_sprinklers * cost_db['pressure_regulator']
                })
    
    # 2. Pipes
    if 'pipe_network' in st.session_state.project_data and 'layout_data' in st.session_state.project_data:
        network = st.session_state.project_data['pipe_network']
        layout_data = st.session_state.project_data['layout_data']
        
        # Lateral pipes
        if 'lateral' in network:
            lateral_size = network['lateral'].get('size_nominal')
            lateral_length = layout_data.get('total_lateral_length', 0)
            
            if lateral_length > 0 and lateral_size:
                unit_cost = cost_db['pipe_costs'].get(str(lateral_size), lateral_size * 0.15)
                boq_items.append({
                    'Item': f'Lateral Pipe {lateral_size}mm',
                    'Description': f'PVC/PE pipe {lateral_size}mm',
                    'Unit': 'm',
                    'Quantity': lateral_length,
                    'Unit Cost ($)': unit_cost,
                    'Total Cost ($)': lateral_length * unit_cost
                })
        
        # Submain pipes
        if 'submain' in network:
            submain_size = network['submain'].get('size_nominal')
            submain_length = layout_data.get('total_submain_length', 0)
            
            if submain_length > 0 and submain_size:
                unit_cost = cost_db['pipe_costs'].get(str(submain_size), submain_size * 0.15)
                boq_items.append({
                    'Item': f'Submain Pipe {submain_size}mm',
                    'Description': f'PVC/PE pipe {submain_size}mm',
                    'Unit': 'm',
                    'Quantity': submain_length,
                    'Unit Cost ($)': unit_cost,
                    'Total Cost ($)': submain_length * unit_cost
                })
        
        # Mainline pipes
        if 'mainline' in network:
            mainline_size = network['mainline'].get('size_nominal')
            mainline_length = layout_data.get('total_mainline_length', network['mainline'].get('length', 0))
            
            if mainline_length > 0 and mainline_size:
                unit_cost = cost_db['pipe_costs'].get(str(mainline_size), mainline_size * 0.15)
                boq_items.append({
                    'Item': f'Mainline Pipe {mainline_size}mm',
                    'Description': f'PVC/PE pipe {mainline_size}mm',
                    'Unit': 'm',
                    'Quantity': mainline_length,
                    'Unit Cost ($)': unit_cost,
                    'Total Cost ($)': mainline_length * unit_cost
                })
    
    # 3. Valves
    if 'pipe_network' in st.session_state.project_data:
        network = st.session_state.project_data['pipe_network']
        
        # Estimate valve quantities
        n_submains = network.get('mainline', {}).get('n_submains', 4)
        n_gate_valves = n_submains + 2  # One per submain plus main control
        n_air_valves = max(3, int(n_submains / 2))
        
        boq_items.append({
            'Item': 'Gate Valves',
            'Description': 'Manual gate valves',
            'Unit': 'pcs',
            'Quantity': n_gate_valves,
            'Unit Cost ($)': cost_db['gate_valve'],
            'Total Cost ($)': n_gate_valves * cost_db['gate_valve']
        })
        
        boq_items.append({
            'Item': 'Air Release Valves',
            'Description': 'Automatic air valves',
            'Unit': 'pcs',
            'Quantity': n_air_valves,
            'Unit Cost ($)': cost_db['air_valve'],
            'Total Cost ($)': n_air_valves * cost_db['air_valve']
        })
    
    # 4. Major equipment
    if 'pump_data' in st.session_state.project_data:
        boq_items.append({
            'Item': 'Pump',
            'Description': st.session_state.project_data['pump_data'].get('selected_model', 'Centrifugal pump'),
            'Unit': 'set',
            'Quantity': 1,
            'Unit Cost ($)': cost_db['pump'],
            'Total Cost ($)': cost_db['pump']
        })
    
    boq_items.append({
        'Item': 'Filtration System',
        'Description': 'Screen or media filter',
        'Unit': 'set',
        'Quantity': 1,
        'Unit Cost ($)': cost_db['filter'],
        'Total Cost ($)': cost_db['filter']
    })
    
    boq_items.append({
        'Item': 'Control System',
        'Description': 'Automation and control panel',
        'Unit': 'set',
        'Quantity': 1,
        'Unit Cost ($)': cost_db['control_system'],
        'Total Cost ($)': cost_db['control_system']
    })
    
    # 5. Fittings (as percentage of pipe cost)
    total_pipe_cost = sum([item['Total Cost ($)'] for item in boq_items if 'Pipe' in item['Item']])
    fittings_cost = total_pipe_cost * (cost_db['fittings_pct'] / 100)
    
    boq_items.append({
        'Item': 'Pipe Fittings',
        'Description': 'Elbows, tees, couplings, etc.',
        'Unit': 'lot',
        'Quantity': 1,
        'Unit Cost ($)': fittings_cost,
        'Total Cost ($)': fittings_cost
    })
    
    # Create DataFrame
    df_boq = pd.DataFrame(boq_items)
    
    # Display BOQ
    st.dataframe(
        df_boq,
        hide_index=True,
        width="stretch",
        column_config={
            "Quantity": st.column_config.NumberColumn("Quantity", format="%.0f"),
            "Unit Cost ($)": st.column_config.NumberColumn("Unit Cost ($)", format="%.2f"),
            "Total Cost ($)": st.column_config.NumberColumn("Total Cost ($)", format="%.2f")
        }
    )
    
    # Summary
    materials_subtotal = df_boq['Total Cost ($)'].sum()
    
    st.markdown("---")
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Materials Subtotal", f"${materials_subtotal:,.2f}")
    
    with col2:
        # Download BOQ
        csv = df_boq.to_csv(index=False)
        st.download_button(
            label="Download BOQ (CSV)",
            data=csv,
            file_name="bill_of_quantities.csv",
            mime="text/csv"
        )
    
    # Save BOQ
    if 'cost_data' not in st.session_state.project_data:
        st.session_state.project_data['cost_data'] = {}
    
    st.session_state.project_data['cost_data']['boq'] = df_boq.to_dict('records')
    st.session_state.project_data['cost_data']['materials_subtotal'] = materials_subtotal

def show_cost_summary():
    """Show complete cost summary"""
    st.markdown('<h2 class="sub-header">Project Cost Summary</h2>', unsafe_allow_html=True)
    
    if 'cost_data' not in st.session_state.project_data or \
       'materials_subtotal' not in st.session_state.project_data['cost_data']:
        st.warning("⚠️ Please generate bill of quantities first (go to Auto BOQ tab and click Save).")
        return
    
    cost_data = st.session_state.project_data['cost_data']
    # Use saved cost_database or defaults
    cost_db = cost_data.get('cost_database', get_default_unit_costs())
    
    materials_cost = cost_data['materials_subtotal']
    
    # Calculate other costs
    installation_cost = materials_cost * (cost_db['installation_pct'] / 100)
    subtotal_before_overhead = materials_cost + installation_cost
    
    engineering_cost = subtotal_before_overhead * (cost_db['engineering_pct'] / 100)
    contingency_cost = subtotal_before_overhead * (cost_db['contingency_pct'] / 100)
    
    total_project_cost = subtotal_before_overhead + engineering_cost + contingency_cost
    
    # Display cost breakdown
    st.markdown("#### Cost Breakdown")
    
    cost_summary = pd.DataFrame({
        'Category': [
            'Materials',
            'Installation Labor',
            'Engineering & Design',
            'Contingency',
            'TOTAL PROJECT COST'
        ],
        'Amount ($)': [
            materials_cost,
            installation_cost,
            engineering_cost,
            contingency_cost,
            total_project_cost
        ],
        'Percentage (%)': [
            (materials_cost / total_project_cost) * 100,
            (installation_cost / total_project_cost) * 100,
            (engineering_cost / total_project_cost) * 100,
            (contingency_cost / total_project_cost) * 100,
            100.0
        ]
    })
    
    st.dataframe(
        cost_summary,
        hide_index=True,
        width="stretch",
        column_config={
            "Amount ($)": st.column_config.NumberColumn("Amount ($)", format="$%,.2f"),
            "Percentage (%)": st.column_config.NumberColumn("Percentage (%)", format="%.1f")
        }
    )
    
    # Cost metrics
    st.markdown("---")
    st.markdown("#### Cost Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Project Cost", f"${total_project_cost:,.0f}")
    
    with col2:
        area = st.session_state.project_data.get('area', 1)
        if area > 0:
            cost_per_ha = total_project_cost / area
            st.metric("Cost per Hectare", f"${cost_per_ha:,.0f}/ha")
    
    with col3:
        if 'layout_data' in st.session_state.project_data:
            n_sprinklers = st.session_state.project_data['layout_data'].get('total_sprinklers', 1)
            if n_sprinklers > 0:
                cost_per_sprinkler = total_project_cost / n_sprinklers
                st.metric("Cost per Sprinkler", f"${cost_per_sprinkler:.0f}")
    
    with col4:
        if 'irrigation_requirements' in st.session_state.project_data:
            flow_rate = st.session_state.project_data['irrigation_requirements'].get('system_flow_rate', 0)
            if flow_rate > 0:
                cost_per_lps = total_project_cost / flow_rate
                st.metric("Cost per l/s Capacity", f"${cost_per_lps:.0f}")
    
    # Cost distribution chart
    st.markdown("---")
    st.markdown("#### Cost Distribution")
    
    fig = go.Figure(data=[go.Pie(
        labels=['Materials', 'Installation', 'Engineering', 'Contingency'],
        values=[materials_cost, installation_cost, engineering_cost, contingency_cost],
        hole=.3
    )])
    
    fig.update_layout(
        title="Project Cost Distribution",
        template="plotly_white",
        height=400
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Save totals
    cost_data.update({
        'installation_cost': installation_cost,
        'engineering_cost': engineering_cost,
        'contingency_cost': contingency_cost,
        'total_project_cost': total_project_cost,
        'cost_per_ha': cost_per_ha if area > 0 else 0
    })

def show_economic_analysis():
    """Economic analysis and payback period"""
    st.markdown('<h2 class="sub-header">Economic Analysis</h2>', unsafe_allow_html=True)
    
    if 'cost_data' not in st.session_state.project_data or \
       'total_project_cost' not in st.session_state.project_data['cost_data']:
        st.warning("⚠️ Please complete cost summary first.")
        return
    
    total_investment = st.session_state.project_data['cost_data']['total_project_cost']
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Investment")
        st.metric("Total Initial Investment", f"${total_investment:,.0f}")
        
        loan_pct = st.slider(
            "Loan Percentage (%)",
            min_value=0,
            max_value=100,
            value=70,
            step=5
        )
        
        loan_amount = total_investment * (loan_pct / 100)
        equity = total_investment - loan_amount
        
        st.metric("Loan Amount", f"${loan_amount:,.0f}")
        st.metric("Owner Equity", f"${equity:,.0f}")
    
    with col2:
        st.markdown("#### Operating Costs (Annual)")
        
        # Energy cost
        if 'pump_data' in st.session_state.project_data and 'annual_cost' in st.session_state.project_data['pump_data']:
            energy_cost = st.session_state.project_data['pump_data']['annual_cost']
        else:
            energy_cost = st.number_input(
                "Energy Cost ($/year)",
                min_value=0.0,
                value=2000.0,
                step=100.0
            )
        
        maintenance_cost = st.number_input(
            "Maintenance ($/year)",
            min_value=0.0,
            value=total_investment * 0.02,  # 2% of investment
            step=100.0,
            help="Annual maintenance and repairs"
        )
        
        labor_cost = st.number_input(
            "Labor Cost ($/year)",
            min_value=0.0,
            value=1000.0,
            step=100.0
        )
        
        total_annual_cost = energy_cost + maintenance_cost + labor_cost
        st.metric("Total Annual O&M", f"${total_annual_cost:,.0f}")
    
    # Benefits analysis
    st.markdown("---")
    st.markdown("#### Benefits Analysis")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        yield_increase = st.number_input(
            "Yield Increase (%)",
            min_value=0.0,
            max_value=200.0,
            value=30.0,
            step=5.0,
            help="Expected yield increase compared to rainfed"
        )
    
    with col2:
        crop_value = st.number_input(
            "Crop Value ($/ha)",
            min_value=0.0,
            value=3000.0,
            step=100.0,
            help="Gross crop value per hectare"
        )
    
    with col3:
        area = st.session_state.project_data.get('area', 1)
        annual_benefit = area * crop_value * (yield_increase / 100)
        st.metric("Annual Benefit", f"${annual_benefit:,.0f}")
    
    # Net benefit and payback
    st.markdown("---")
    st.markdown("#### Financial Indicators")
    
    annual_net_benefit = annual_benefit - total_annual_cost
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Annual Net Benefit", f"${annual_net_benefit:,.0f}")
    
    with col2:
        if annual_net_benefit > 0:
            simple_payback = total_investment / annual_net_benefit
            st.metric("Simple Payback Period", f"{simple_payback:.1f} years")
        else:
            st.metric("Simple Payback Period", "N/A")
    
    with col3:
        roi = (annual_net_benefit / total_investment) * 100
        st.metric("ROI", f"{roi:.1f}%")
    
    # NPV Analysis
    st.markdown("---")
    st.markdown("#### Net Present Value Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        discount_rate = st.slider(
            "Discount Rate (%)",
            min_value=1.0,
            max_value=15.0,
            value=8.0,
            step=0.5
        )
    
    with col2:
        project_life = st.slider(
            "Project Life (years)",
            min_value=5,
            max_value=30,
            value=20,
            step=1
        )
    
    # Calculate NPV
    years = np.arange(0, project_life + 1)
    cash_flows = np.zeros(project_life + 1)
    cash_flows[0] = -total_investment  # Initial investment
    
    for i in range(1, project_life + 1):
        cash_flows[i] = annual_net_benefit
    
    discount_factors = 1 / (1 + discount_rate/100) ** years
    discounted_cash_flows = cash_flows * discount_factors
    
    npv = np.sum(discounted_cash_flows)
    
    # Display NPV
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Net Present Value (NPV)", f"${npv:,.0f}")
        
        if npv > 0:
            st.success("✅ Project is economically viable")
        else:
            st.error("❌ Project may not be economically viable")
    
    with col2:
        # Calculate IRR (simplified)
        if annual_net_benefit > 0:
            irr_estimate = (annual_net_benefit / total_investment) * 100
            st.metric("Estimated IRR", f"{irr_estimate:.1f}%")
    
    # Cash flow chart
    st.markdown("---")
    st.markdown("#### Cumulative Cash Flow")
    
    cumulative_cf = np.cumsum(cash_flows)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=years,
        y=cumulative_cf,
        mode='lines+markers',
        name='Cumulative Cash Flow',
        line=dict(color='blue', width=2)
    ))
    
    fig.add_hline(y=0, line_dash="dash", line_color="red")
    
    fig.update_layout(
        title=f"Cumulative Cash Flow Over {project_life} Years",
        xaxis_title="Year",
        yaxis_title="Cumulative Cash Flow ($)",
        template="plotly_white",
        height=400
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Save economic analysis
    if st.button("Save Economic Analysis", type="primary"):
        st.session_state.project_data['cost_data'].update({
            'annual_energy_cost': energy_cost,
            'annual_maintenance_cost': maintenance_cost,
            'annual_labor_cost': labor_cost,
            'total_annual_cost': total_annual_cost,
            'annual_benefit': annual_benefit,
            'annual_net_benefit': annual_net_benefit,
            'payback_period': simple_payback if annual_net_benefit > 0 else 0,
            'roi': roi,
            'npv': npv,
            'discount_rate': discount_rate,
            'project_life': project_life
        })
        st.success("✅ Economic analysis saved!")

def get_default_unit_costs():
    """Get default unit costs"""
    return {
        'sprinkler': 15.0,
        'riser': 8.0,
        'pressure_regulator': 12.0,
        'gate_valve': 45.0,
        'air_valve': 35.0,
        'fittings_pct': 15.0,
        'pipe_costs': {
            '50': 7.5,
            '63': 9.5,
            '75': 11.0,
            '90': 13.5,
            '110': 16.5,
            '125': 18.5,
            '160': 24.0,
            '200': 30.0
        },
        'pump': 3000.0,
        'filter': 1500.0,
        'control_system': 2000.0,
        'installation_pct': 20.0,
        'engineering_pct': 8.0,
        'contingency_pct': 10.0
    }
