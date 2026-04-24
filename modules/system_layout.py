"""
System Layout Module
Create field layout and visualize system design
Integrated with Field Layout Manager for multi-block support
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def show():
    st.markdown('<h1 class="main-header">System Layout Design</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    Design field layout, visualize sprinkler positions, and plan pipe routing.
    </div>
    """, unsafe_allow_html=True)
    
    # Check for field layout integration
    show_field_layout_integration()
    
    # Solid Set system layout tabs
    tabs = st.tabs(["Field Layout", "Sprinkler Grid", "Pipe Routing", "3D Visualization"])
    with tabs[0]:
        show_field_layout()
    with tabs[1]:
        show_sprinkler_grid()
    with tabs[2]:
        show_pipe_routing()
    with tabs[3]:
        show_3d_visualization()


def show_field_layout_integration():
    """Show integration status with Field Layout Manager."""
    field_layout = st.session_state.project_data.get('field_layout', {})
    crop_blocks = field_layout.get('crop_blocks', [])
    sprinkler_blocks = [b for b in crop_blocks if b.get('irrigation_system') == 'sprinkler']
    
    if sprinkler_blocks:
        st.success(f"""
        ✅ **Field Layout Data Available!**
        
        Found {len(sprinkler_blocks)} sprinkler irrigation block(s) from the Field Layout workflow:
        """)
        
        # Show summary of sprinkler blocks
        cols = st.columns(min(4, len(sprinkler_blocks)))
        for i, block in enumerate(sprinkler_blocks):
            with cols[i % 4]:
                st.markdown(f"""
                <div style="background: {block['color']}33; padding: 10px; border-radius: 8px; border-left: 4px solid {block['color']};">
                    <b>{block['name']}</b><br>
                    🌱 {block['crop_name']}<br>
                    📐 {block.get('area_ha', 0):.2f} ha
                </div>
                """, unsafe_allow_html=True)
        
        st.markdown("---")
    elif field_layout.get('main_boundary'):
        st.info("""
        ℹ️ **Field boundary defined** but no sprinkler blocks assigned.
        
        Go to **Home → Field Layout & Blocks** to create crop blocks and assign them to sprinkler irrigation.
        """)


def show_field_layout():
    """Design field layout"""
    st.markdown('<h2 class="sub-header">Field Layout Configuration</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Field Dimensions")
        
        # Get field dimensions from map if available
        field_geometry = st.session_state.project_data.get('field_geometry', {})
        
        area = st.session_state.project_data.get('area', 0)
        st.metric("Total Area", f"{area} ha")
        
        field_length = st.number_input(
            "Field Length (m)",
            min_value=10.0,
            max_value=2000.0,
            value=float(field_geometry.get('length_m', 500.0)),
            step=10.0,
            help="From field mapping or manual entry"
        )
        
        field_width = st.number_input(
            "Field Width (m)",
            min_value=10.0,
            max_value=2000.0,
            value=float(field_geometry.get('width_m', 400.0)),
            step=10.0,
            help="From field mapping or manual entry"
        )
        
        if field_geometry.get('boundary'):
            st.info("ℹ️ Dimensions from map delineation")
        
        calculated_area = field_length * field_width / 10000  # hectares
        st.metric("Calculated Area", f"{calculated_area:.2f} ha")
        
        if abs(calculated_area - area) > area * 0.1:
            st.warning("⚠️ Calculated area differs significantly from project area")
    
    with col2:
        st.markdown("#### Field Characteristics")
        
        # Show water source location if available
        water_source = field_geometry.get('water_source')
        if water_source:
            st.success("✅ Water source from map")
            st.caption(f"📍 {water_source[0]:.6f}, {water_source[1]:.6f}")
        else:
            st.info("ℹ️ Mark water source on map for optimal layout")
        
        field_shape = st.selectbox(
            "Field Shape",
            options=['Rectangular', 'Irregular', 'L-Shaped', 'Triangular']
        )
        
        slope_direction = st.selectbox(
            "Slope Direction",
            options=['Flat', 'North-South', 'East-West', 'Northeast-Southwest', 
                    'Northwest-Southeast']
        )
        
        avg_slope = st.number_input(
            "Average Slope (%)",
            min_value=0.0,
            max_value=20.0,
            value=2.0,
            step=0.5
        )
        
        obstacles = st.multiselect(
            "Field Obstacles",
            options=['Trees', 'Buildings', 'Roads', 'Waterways', 'Rock outcrops', 'None'],
            default=['None']
        )
    
    # Sprinkler coverage
    st.markdown("---")
    st.markdown("#### Sprinkler Coverage Planning")
    
    if 'sprinkler_data' in st.session_state.project_data:
        sprinkler = st.session_state.project_data['sprinkler_data']
        spacing_along = sprinkler.get('spacing_along', 12)
        spacing_between = sprinkler.get('spacing_between', 12)
        
        n_sprinklers_length = int(field_length / spacing_along)
        n_sprinklers_width = int(field_width / spacing_between)
        total_sprinklers = n_sprinklers_length * n_sprinklers_width
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Sprinklers (Length)", n_sprinklers_length)
        with col2:
            st.metric("Sprinklers (Width)", n_sprinklers_width)
        with col3:
            st.metric("Total Sprinklers", total_sprinklers)
        with col4:
            sprinklers_per_ha = total_sprinklers / calculated_area
            st.metric("Sprinklers/ha", f"{sprinklers_per_ha:.0f}")
    else:
        st.warning("⚠️ Please complete sprinkler selection to calculate coverage")
    
    # Layout pattern
    st.markdown("---")
    st.markdown("#### Layout Pattern")
    
    layout_type = st.selectbox(
        "System Layout Type",
        options=['Solid Set', 'Semi-Permanent', 'Periodic Move', 'Traveling']
    )
    
    if layout_type == 'Solid Set':
        st.info("""
        **Solid Set System:**
        - All laterals and sprinklers permanently installed
        - Can irrigate entire field simultaneously or in blocks
        - Highest initial cost, lowest labor
        - Best uniformity and flexibility
        """)
    elif layout_type == 'Semi-Permanent':
        st.info("""
        **Semi-Permanent System:**
        - Mainline and submains permanent
        - Laterals moved between positions
        - Moderate cost and labor
        - Good flexibility
        """)
    
    # Save layout data
    if st.button("Save Field Layout", type="primary"):
        if 'layout_data' not in st.session_state.project_data:
            st.session_state.project_data['layout_data'] = {}
        
        st.session_state.project_data['layout_data'].update({
            'field_length': field_length,
            'field_width': field_width,
            'field_area': calculated_area,
            'field_shape': field_shape,
            'slope_direction': slope_direction,
            'avg_slope': avg_slope,
            'obstacles': obstacles,
            'layout_type': layout_type
        })
        
        if 'sprinkler_data' in st.session_state.project_data:
            st.session_state.project_data['layout_data'].update({
                'n_sprinklers_length': n_sprinklers_length,
                'n_sprinklers_width': n_sprinklers_width,
                'total_sprinklers': total_sprinklers
            })
        
        st.success("✅ Field layout saved!")
        st.rerun()

def show_sprinkler_grid():
    """Show sprinkler grid layout"""
    st.markdown('<h2 class="sub-header">Sprinkler Grid Layout</h2>', unsafe_allow_html=True)
    
    if 'layout_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete field layout configuration first.")
        return
    
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete sprinkler selection first.")
        return
    
    layout = st.session_state.project_data['layout_data']
    sprinkler = st.session_state.project_data['sprinkler_data']
    
    # Validate layout data has required fields
    if 'field_length' not in layout or 'field_width' not in layout:
        st.warning("⚠️ Field dimensions missing. Please configure field layout first.")
        return
    
    field_length = layout['field_length']
    field_width = layout['field_width']
    spacing_along = sprinkler.get('spacing_along', 12)
    spacing_between = sprinkler.get('spacing_between', 12)
    wetted_diameter = sprinkler.get('diameter', 24)
    
    # Create sprinkler grid
    st.markdown("#### Sprinkler Position Grid")
    
    n_x = int(field_length / spacing_along)
    n_y = int(field_width / spacing_between)
    
    # Visualization options
    col1, col2 = st.columns(2)
    
    with col1:
        show_coverage = st.checkbox("Show Coverage Circles", value=True)
        show_overlap = st.checkbox("Show Overlap Areas", value=False)
    
    with col2:
        view_section = st.selectbox(
            "View Section",
            options=['Full Field', 'Corner Detail (10x10)', 'Edge Detail (20x5)']
        )
    
    # Create figure
    fig = go.Figure()
    
    # Determine display range
    if view_section == 'Corner Detail (10x10)':
        x_range = [0, min(10*spacing_along, field_length)]
        y_range = [0, min(10*spacing_between, field_width)]
        n_x_display = min(10, n_x)
        n_y_display = min(10, n_y)
    elif view_section == 'Edge Detail (20x5)':
        x_range = [0, min(20*spacing_along, field_length)]
        y_range = [0, min(5*spacing_between, field_width)]
        n_x_display = min(20, n_x)
        n_y_display = min(5, n_y)
    else:
        x_range = [0, field_length]
        y_range = [0, field_width]
        n_x_display = n_x
        n_y_display = n_y
    
    # Plot sprinklers
    for i in range(n_y_display):
        for j in range(n_x_display):
            x = j * spacing_along + spacing_along/2
            y = i * spacing_between + spacing_between/2
            
            # Sprinkler point
            fig.add_trace(go.Scatter(
                x=[x], y=[y],
                mode='markers',
                marker=dict(size=8, color='blue', symbol='circle'),
                showlegend=False,
                hovertext=f"Sprinkler ({j+1}, {i+1})"
            ))
            
            # Coverage circle
            if show_coverage:
                theta = np.linspace(0, 2*np.pi, 50)
                circle_x = x + (wetted_diameter/2) * np.cos(theta)
                circle_y = y + (wetted_diameter/2) * np.sin(theta)
                
                fig.add_trace(go.Scatter(
                    x=circle_x, y=circle_y,
                    mode='lines',
                    line=dict(color='lightblue', width=1, dash='dot'),
                    fill='toself' if show_overlap else None,
                    fillcolor='rgba(173, 216, 230, 0.2)' if show_overlap else None,
                    showlegend=False,
                    hoverinfo='skip'
                ))
    
    # Field boundary
    fig.add_trace(go.Scatter(
        x=[0, x_range[1], x_range[1], 0, 0],
        y=[0, 0, y_range[1], y_range[1], 0],
        mode='lines',
        line=dict(color='black', width=2),
        name='Field Boundary',
        showlegend=True
    ))
    
    fig.update_layout(
        title=f"Sprinkler Grid Layout - {view_section}",
        xaxis_title="Distance (m)",
        yaxis_title="Distance (m)",
        template="plotly_white",
        height=600,
        yaxis=dict(scaleanchor="x", scaleratio=1),
        xaxis=dict(range=x_range),
        yaxis_range=y_range
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Coverage statistics
    st.markdown("---")
    st.markdown("#### Coverage Statistics")
    
    total_sprinklers = layout.get('total_sprinklers', n_x * n_y)
    total_flow = total_sprinklers * sprinkler.get('flow', 500) / 1000  # m³/h
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Sprinklers", total_sprinklers)
    with col2:
        st.metric("Total Flow", f"{total_flow:.1f} m³/h")
    with col3:
        coverage_area = total_sprinklers * spacing_along * spacing_between / 10000
        st.metric("Coverage Area", f"{coverage_area:.2f} ha")
    with col4:
        coverage_pct = (coverage_area / layout['field_area']) * 100
        st.metric("Field Coverage", f"{coverage_pct:.1f}%")

def show_pipe_routing():
    """Show pipe routing layout"""
    st.markdown('<h2 class="sub-header">Pipe Routing Design</h2>', unsafe_allow_html=True)
    
    if 'layout_data' not in st.session_state.project_data or \
       'pipe_network' not in st.session_state.project_data:
        st.warning("⚠️ Please complete field layout and pipe network design first.")
        return
    
    layout = st.session_state.project_data['layout_data']
    network = st.session_state.project_data['pipe_network']
    
    # Pipe routing configuration
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Mainline Routing")
        
        pump_location = st.selectbox(
            "Pump/Water Source Location",
            options=['Southwest Corner', 'Southeast Corner', 'Northwest Corner', 
                    'Northeast Corner', 'Center South', 'Center North']
        )
        
        mainline_route = st.selectbox(
            "Mainline Route",
            options=['Direct to Field Center', 'Along Field Edge', 'Diagonal']
        )
    
    with col2:
        st.markdown("#### Lateral Configuration")
        
        lateral_orientation = st.selectbox(
            "Lateral Orientation",
            options=['Perpendicular to Mainline', 'Parallel to Mainline']
        )
        
        valve_locations = st.multiselect(
            "Control Valve Locations",
            options=['Mainline Start', 'Submain Connections', 'Lateral Connections', 
                    'Block Boundaries'],
            default=['Submain Connections']
        )
    
    # Create routing diagram
    st.markdown("---")
    st.markdown("#### Pipe Routing Diagram")
    
    fig = create_routing_diagram(layout, network, pump_location, mainline_route, lateral_orientation)
    st.plotly_chart(fig, width="stretch")
    
    # Pipe lengths summary
    st.markdown("---")
    st.markdown("#### Pipe Material Requirements")
    
    if 'lateral' in network and 'submain' in network and 'mainline' in network:
        # Calculate total lengths
        n_laterals_total = layout.get('n_sprinklers_width', 10)
        n_submains = st.number_input("Number of Submains", min_value=1, value=4)
        
        lateral_length_each = network['lateral'].get('length', 100)
        submain_length_each = network['submain'].get('length', 100)
        mainline_length_total = network['mainline'].get('length', 200)
        
        total_lateral_length = lateral_length_each * n_laterals_total
        total_submain_length = submain_length_each * n_submains
        
        # Create summary table
        pipe_summary = pd.DataFrame({
            'Pipe Type': ['Lateral', 'Submain', 'Mainline', 'TOTAL'],
            'Size (mm)': [
                network['lateral'].get('size_nominal', '-'),
                network['submain'].get('size_nominal', '-'),
                network['mainline'].get('size_nominal', '-'),
                '-'
            ],
            'Unit Length (m)': [
                lateral_length_each,
                submain_length_each,
                mainline_length_total,
                '-'
            ],
            'Quantity': [
                n_laterals_total,
                n_submains,
                1,
                '-'
            ],
            'Total Length (m)': [
                total_lateral_length,
                total_submain_length,
                mainline_length_total,
                total_lateral_length + total_submain_length + mainline_length_total
            ]
        })
        
        st.dataframe(pipe_summary, hide_index=True, width="stretch")
        
        # Save routing data
        if st.button("Save Pipe Routing", type="primary"):
            st.session_state.project_data['layout_data'].update({
                'pump_location': pump_location,
                'mainline_route': mainline_route,
                'lateral_orientation': lateral_orientation,
                'valve_locations': valve_locations,
                'total_lateral_length': total_lateral_length,
                'total_submain_length': total_submain_length,
                'total_mainline_length': mainline_length_total
            })
            st.success("✅ Pipe routing saved!")

def show_3d_visualization():
    """Show 3D terrain and system visualization"""
    st.markdown('<h2 class="sub-header">3D System Visualization</h2>', unsafe_allow_html=True)
    
    if 'layout_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete field layout configuration first.")
        return
    
    layout = st.session_state.project_data['layout_data']
    
    # Validate layout data has required fields
    if 'field_length' not in layout or 'field_width' not in layout:
        st.warning("⚠️ Field dimensions missing. Please configure field layout first.")
        return
    
    # Create terrain
    field_length = layout['field_length']
    field_width = layout['field_width']
    avg_slope = layout.get('avg_slope', 2)
    slope_direction = layout.get('slope_direction', 'Flat')
    
    # Generate terrain mesh
    x = np.linspace(0, field_length, 50)
    y = np.linspace(0, field_width, 50)
    X, Y = np.meshgrid(x, y)
    
    # Create elevation based on slope
    if slope_direction == 'Flat':
        Z = np.zeros_like(X)
    elif slope_direction == 'North-South':
        Z = Y * (avg_slope / 100)
    elif slope_direction == 'East-West':
        Z = X * (avg_slope / 100)
    elif slope_direction == 'Northeast-Southwest':
        Z = (X + Y) * (avg_slope / 100) / np.sqrt(2)
    else:  # Northwest-Southeast
        Z = (X - Y) * (avg_slope / 100) / np.sqrt(2)
    
    # Add some random variation
    Z += np.random.normal(0, avg_slope/10, Z.shape)
    
    # Create 3D surface
    fig = go.Figure(data=[go.Surface(
        x=X, y=Y, z=Z,
        colorscale='Earth',
        showscale=True,
        colorbar=dict(title="Elevation (m)"),
        opacity=0.9
    )])
    
    # Add sprinkler positions if available
    if 'sprinkler_data' in st.session_state.project_data:
        sprinkler = st.session_state.project_data['sprinkler_data']
        spacing_along = sprinkler.get('spacing_along', 12)
        spacing_between = sprinkler.get('spacing_between', 12)
        
        # Calculate number of sprinklers, but limit total display for performance
        n_x_total = int(field_length / spacing_along)
        n_y_total = int(field_width / spacing_between)
        
        # Limit to max 400 sprinklers (20x20) for visualization performance
        max_sprinklers_per_dim = 20
        
        # Use either the actual number or the max, whichever is smaller
        n_x = min(n_x_total, max_sprinklers_per_dim)
        n_y = min(n_y_total, max_sprinklers_per_dim)
        
        sprinkler_x = []
        sprinkler_y = []
        sprinkler_z = []
        
        # Evenly distribute sprinklers across the field dimensions
        for i in range(n_y):
            for j in range(n_x):
                # Calculate position as fraction of field dimensions
                # This ensures even distribution regardless of field size
                if n_x > 1:
                    sx = (j / (n_x - 1)) * (field_length - spacing_along) + spacing_along/2
                else:
                    sx = field_length / 2
                
                if n_y > 1:
                    sy = (i / (n_y - 1)) * (field_width - spacing_between) + spacing_between/2
                else:
                    sy = field_width / 2
                
                # Calculate elevation at this point based on slope
                if slope_direction == 'Flat':
                    sz = 0
                elif slope_direction == 'North-South':
                    sz = sy * (avg_slope / 100)
                elif slope_direction == 'East-West':
                    sz = sx * (avg_slope / 100)
                elif slope_direction == 'Northeast-Southwest':
                    sz = (sx + sy) * (avg_slope / 100) / np.sqrt(2)
                else:  # Northwest-Southeast
                    sz = (sx - sy) * (avg_slope / 100) / np.sqrt(2)
                
                sprinkler_x.append(sx)
                sprinkler_y.append(sy)
                sprinkler_z.append(sz + 1)  # Raise slightly above ground
        
        # Add sprinklers
        fig.add_trace(go.Scatter3d(
            x=sprinkler_x,
            y=sprinkler_y,
            z=sprinkler_z,
            mode='markers',
            marker=dict(size=5, color='blue', symbol='diamond'),
            name='Sprinklers'
        ))
    
    fig.update_layout(
        title="3D Field Terrain and Sprinkler Layout",
        scene=dict(
            xaxis_title="Length (m)",
            yaxis_title="Width (m)",
            zaxis_title="Elevation (m)",
            aspectmode='manual',
            aspectratio=dict(x=2, y=1.5, z=0.5)
        ),
        height=600,
        template="plotly_white"
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Elevation statistics
    st.markdown("---")
    st.markdown("#### Terrain Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Min Elevation", f"{Z.min():.2f} m")
    with col2:
        st.metric("Max Elevation", f"{Z.max():.2f} m")
    with col3:
        st.metric("Elevation Difference", f"{Z.max() - Z.min():.2f} m")
    with col4:
        st.metric("Avg Elevation", f"{Z.mean():.2f} m")

def create_routing_diagram(layout, network, pump_location, mainline_route, lateral_orientation):
    """Create pipe routing diagram"""
    fig = go.Figure()
    
    # Validate layout data
    if 'field_length' not in layout or 'field_width' not in layout:
        return fig  # Return empty figure if data missing
    
    field_length = layout['field_length']
    field_width = layout['field_width']
    
    # Field boundary
    fig.add_trace(go.Scatter(
        x=[0, field_length, field_length, 0, 0],
        y=[0, 0, field_width, field_width, 0],
        mode='lines',
        line=dict(color='black', width=2),
        name='Field Boundary'
    ))
    
    # Check if water source location is available from map
    field_geometry = st.session_state.project_data.get('field_geometry', {})
    water_source_coords = field_geometry.get('water_source')
    
    # Determine pump location
    if water_source_coords:
        # Calculate relative position in field
        # This is approximate - assumes field boundary is rectangular
        boundary = field_geometry.get('boundary')
        if boundary:
            lats = [coord[0] for coord in boundary]
            lons = [coord[1] for coord in boundary]
            min_lat, max_lat = min(lats), max(lats)
            min_lon, max_lon = min(lons), max(lons)
            
            # Normalize water source position to field coordinates
            ws_lat, ws_lon = water_source_coords
            pump_x = ((ws_lon - min_lon) / (max_lon - min_lon)) * field_length if max_lon != min_lon else field_length/2
            pump_y = ((ws_lat - min_lat) / (max_lat - min_lat)) * field_width if max_lat != min_lat else field_width/2
        else:
            # Fallback to default
            pump_positions = {
                'Southwest Corner': (10, 10),
                'Southeast Corner': (field_length - 10, 10),
                'Northwest Corner': (10, field_width - 10),
                'Northeast Corner': (field_length - 10, field_width - 10),
                'Center South': (field_length/2, 10),
                'Center North': (field_length/2, field_width - 10)
            }
            pump_x, pump_y = pump_positions.get(pump_location, (10, 10))
    else:
        # Use manual pump location selection
        pump_positions = {
            'Southwest Corner': (10, 10),
            'Southeast Corner': (field_length - 10, 10),
            'Northwest Corner': (10, field_width - 10),
            'Northeast Corner': (field_length - 10, field_width - 10),
            'Center South': (field_length/2, 10),
            'Center North': (field_length/2, field_width - 10)
        }
        pump_x, pump_y = pump_positions.get(pump_location, (10, 10))
    
    # Draw water source / pump station
    fig.add_trace(go.Scatter(
        x=[pump_x], y=[pump_y],
        mode='markers+text',
        marker=dict(size=25, color='blue', symbol='circle', line=dict(color='darkblue', width=3)),
        text=['💧'],
        textfont=dict(size=20),
        name='Water Source',
        showlegend=True
    ))
    
    # Add circle around water source for visibility
    fig.add_shape(
        type='circle',
        xref='x', yref='y',
        x0=pump_x-15, y0=pump_y-15,
        x1=pump_x+15, y1=pump_y+15,
        line=dict(color='blue', width=2, dash='dash'),
        fillcolor='lightblue',
        opacity=0.3
    )
    
    # Mainline
    if mainline_route == 'Direct to Field Center':
        mainline_x = [pump_x, field_length/2]
        mainline_y = [pump_y, field_width/2]
    elif mainline_route == 'Along Field Edge':
        if pump_y < field_width/2:
            mainline_x = [pump_x, field_length/2]
            mainline_y = [pump_y, pump_y]
        else:
            mainline_x = [pump_x, field_length/2]
            mainline_y = [pump_y, pump_y]
    else:  # Diagonal
        mainline_x = [pump_x, field_length - pump_x]
        mainline_y = [pump_y, field_width - pump_y]
    
    fig.add_trace(go.Scatter(
        x=mainline_x, y=mainline_y,
        mode='lines',
        line=dict(color='darkblue', width=6),
        name='Mainline'
    ))
    
    # Submains (simplified - show 3 submains)
    n_submains = 3
    for i in range(n_submains):
        offset = (i + 1) * field_length / (n_submains + 1)
        
        fig.add_trace(go.Scatter(
            x=[offset, offset],
            y=[0, field_width],
            mode='lines',
            line=dict(color='blue', width=4),
            name='Submain' if i == 0 else None,
            showlegend=True if i == 0 else False
        ))
    
    fig.update_layout(
        title="Pipe Routing Schematic",
        xaxis_title="Length (m)",
        yaxis_title="Width (m)",
        template="plotly_white",
        height=500,
        yaxis=dict(scaleanchor="x", scaleratio=1)
    )
    
    return fig

