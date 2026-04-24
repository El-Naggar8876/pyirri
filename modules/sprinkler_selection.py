"""
Sprinkler Selection Module
Select appropriate sprinkler type, spacing, and configuration
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

def show():
    st.markdown('<h1 class="main-header">Sprinkler Selection & Spacing</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    Select appropriate sprinkler type and determine optimal spacing based on wind conditions,
    soil type, and irrigation requirements.
    </div>
    """, unsafe_allow_html=True)
    
    tabs = st.tabs(["Sprinkler Selection", "Spacing Design", "Application Rate", "Uniformity"])
    
    with tabs[0]:
        show_sprinkler_selection()
    
    with tabs[1]:
        show_spacing_design()
    
    with tabs[2]:
        show_application_rate()
    
    with tabs[3]:
        show_uniformity_analysis()

def show_sprinkler_selection():
    """Sprinkler type selection"""
    st.markdown('<h2 class="sub-header">Sprinkler Type Selection</h2>', unsafe_allow_html=True)
    
    # Get saved values if they exist
    saved_sprinkler = st.session_state.project_data.get('sprinkler_data', {})
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### System Type")
        
        # Fixed to Solid Set system only
        system_type = 'Solid Set'
        st.info("**System Type:** Solid Set (Fixed)")
        st.markdown("""
        <div class="info-box">
        <strong>Solid Set System:</strong> Permanently installed sprinkler system with fixed 
        sprinklers covering the entire field. Ideal for frequent irrigation and high-value crops.
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("#### Sprinkler Category")
        
        category_options = ['Low Pressure (LP)', 'Medium Pressure (MP)', 'High Pressure (HP)']
        saved_category = saved_sprinkler.get('sprinkler_category', 'Medium Pressure (MP)')
        category_index = category_options.index(saved_category) if saved_category in category_options else 1
        
        sprinkler_category = st.selectbox(
            "Sprinkler Category",
            options=category_options,
            index=category_index,
            key="sprinkler_category_select"
        )
        
        type_options = ['Impact Sprinkler', 'Gear-Driven Rotor', 'Spray Head', 'Rotator Nozzle']
        saved_type = saved_sprinkler.get('sprinkler_type', 'Impact Sprinkler')
        type_index = type_options.index(saved_type) if saved_type in type_options else 0
        
        sprinkler_type = st.selectbox(
            "Sprinkler Type",
            options=type_options,
            index=type_index,
            key="sprinkler_type_select"
        )
    
    with col2:
        st.markdown("#### Operating Conditions")
        
        # Get wind speed from saved data first, then climate data
        avg_wind = saved_sprinkler.get('wind_speed', 2.0)
        if avg_wind == 2.0 and 'climate_data' in st.session_state.project_data:
            climate_df = st.session_state.project_data['climate_data'].get('monthly_data')
            if climate_df is not None:
                # Handle both DataFrame and dict (from JSON load)
                if not isinstance(climate_df, pd.DataFrame):
                    try:
                        climate_df = pd.DataFrame(climate_df)
                    except Exception:
                        climate_df = None
                if climate_df is not None and 'Wind Speed (m/s)' in climate_df.columns:
                    avg_wind = climate_df['Wind Speed (m/s)'].mean()
        
        wind_speed = st.number_input(
            "Average Wind Speed (m/s)",
            min_value=0.0,
            max_value=10.0,
            value=float(avg_wind),
            step=0.1,
            help="Average wind speed during irrigation hours",
            key="sprinkler_wind_speed"
        )
        
        soil_infiltration = get_soil_infiltration_rate(
            st.session_state.project_data.get('soil_type', 'Loam')
        )
        
        st.metric("Soil Infiltration Rate", f"{soil_infiltration:.1f} mm/hr")
        
        terrain_options = ['Flat (0-2%)', 'Gentle (2-5%)', 'Rolling (5-8%)', 'Hilly (>8%)']
        saved_terrain = saved_sprinkler.get('terrain', 'Flat (0-2%)')
        terrain_index = terrain_options.index(saved_terrain) if saved_terrain in terrain_options else 0
        
        terrain = st.selectbox(
            "Terrain",
            options=terrain_options,
            index=terrain_index,
            key="sprinkler_terrain_select"
        )
    
    # Display sprinkler database
    st.markdown("---")
    st.markdown("#### Available Sprinkler Models")
    
    sprinkler_db = get_sprinkler_database()
    filtered_sprinklers = [s for s in sprinkler_db if s['Category'] == sprinkler_category 
                          and s['Type'] == sprinkler_type]
    
    if filtered_sprinklers:
        df_sprinklers = pd.DataFrame(filtered_sprinklers)
        
        # Find saved model index if exists
        saved_model = saved_sprinkler.get('model', '')
        saved_nozzle = saved_sprinkler.get('nozzle', '')
        default_idx = 0
        
        # Try to match saved sprinkler in filtered list
        if saved_model and saved_nozzle:
            for idx, row in df_sprinklers.iterrows():
                if row['Model'] == saved_model and row['Nozzle'] == saved_nozzle:
                    default_idx = list(df_sprinklers.index).index(idx)
                    break
        
        # Interactive selection
        selected_idx = st.selectbox(
            "Select Sprinkler Model",
            options=range(len(df_sprinklers)),
            index=default_idx,
            format_func=lambda x: f"{df_sprinklers.iloc[x]['Model']} - {df_sprinklers.iloc[x]['Nozzle']}",
            help="Choose a sprinkler model from the database",
            key="sprinkler_model_select"
        )
        
        selected_sprinkler = df_sprinklers.iloc[selected_idx].to_dict()
        
        # Display selected sprinkler details
        st.markdown("---")
        st.markdown("#### Selected Sprinkler Specifications")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Model", selected_sprinkler['Model'])
        with col2:
            st.metric("Nozzle Size", selected_sprinkler['Nozzle'])
        with col3:
            st.metric("Operating Pressure", f"{selected_sprinkler['Pressure']} kPa")
        with col4:
            st.metric("Flow Rate", f"{selected_sprinkler['Flow']} l/h")
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Wetted Diameter", f"{selected_sprinkler['Diameter']:.2f} m")
        with col2:
            st.metric("Reference App Rate", f"{selected_sprinkler['App_Rate']:.2f} mm/hr", help="Manufacturer's reference value at standard spacing")
        with col3:
            st.metric("CU (Uniformity)", f"{selected_sprinkler['CU']:.0f}%")
        
        # Display product link if available
        if 'URL' in selected_sprinkler and selected_sprinkler['URL']:
            st.markdown(f"""
            **📄 Product Information:** [View manufacturer specifications]({selected_sprinkler['URL']})
            """)
        
        # Save sprinkler data
        if st.button("Select This Sprinkler", type="primary"):
            st.session_state.project_data['sprinkler_data'] = {
                'system_type': system_type,
                'sprinkler_category': sprinkler_category,
                'sprinkler_type': sprinkler_type,
                'model': selected_sprinkler['Model'],
                'nozzle': selected_sprinkler['Nozzle'],
                'pressure': selected_sprinkler['Pressure'],
                'flow': selected_sprinkler['Flow'],
                'diameter': selected_sprinkler['Diameter'],
                'app_rate': selected_sprinkler['App_Rate'],
                'cu': selected_sprinkler['CU'],
                'wind_speed': wind_speed,
                'terrain': terrain,
                'product_url': selected_sprinkler.get('URL', '')
            }
            st.success(f"✅ Sprinkler selected successfully for **{system_type}** system!")
            st.rerun()
    
    # Show system-specific information
    if 'sprinkler_data' in st.session_state.project_data:
        pass  # Sprinkler data available, proceed to spacing design
    else:
        st.warning("No sprinklers found for the selected criteria. Please adjust your selection.")

def show_spacing_design():
    """Design sprinkler spacing"""
    st.markdown('<h2 class="sub-header">Sprinkler Spacing Design</h2>', unsafe_allow_html=True)
    
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please select a sprinkler first.")
        return
    
    sprinkler = st.session_state.project_data['sprinkler_data']
    
    if 'diameter' not in sprinkler:
        st.warning("⚠️ Sprinkler data incomplete. Please select a sprinkler again.")
        return
    
    wetted_diameter = sprinkler['diameter']
    wind_speed = sprinkler.get('wind_speed', 2.0)
    
    st.info(f"**System Type:** Solid Set | Wetted Diameter: {wetted_diameter} m | Wind Speed: {wind_speed} m/s")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Spacing Parameters")
        
        # Recommend spacing based on wind
        if wind_speed < 2:
            recommended_spacing_ratio = 0.65
            wind_condition = "Low wind"
        elif wind_speed < 4:
            recommended_spacing_ratio = 0.55
            wind_condition = "Moderate wind"
        else:
            recommended_spacing_ratio = 0.45
            wind_condition = "High wind"
        
        st.info(f"Wind Condition: {wind_condition} - Recommended spacing: {recommended_spacing_ratio*100:.0f}% of diameter")
        
        # Use saved values if available, otherwise use recommended
        default_spacing_along = sprinkler.get('spacing_along', wetted_diameter * recommended_spacing_ratio)
        default_spacing_between = sprinkler.get('spacing_between', wetted_diameter * recommended_spacing_ratio)
        default_layout = sprinkler.get('layout_pattern', 'Rectangular')
        
        spacing_along = st.number_input(
            "Spacing Along Lateral (m)",
            min_value=1.0,
            max_value=float(wetted_diameter),
            value=float(default_spacing_along),
            step=0.5,
            help="Distance between sprinklers on the lateral",
            key="spacing_along_input"
        )
        
        spacing_between = st.number_input(
            "Spacing Between Laterals (m)",
            min_value=1.0,
            max_value=float(wetted_diameter),
            value=float(default_spacing_between),
            step=0.5,
            help="Distance between lateral lines",
            key="spacing_between_input"
        )
        
        layout_options = ['Rectangular', 'Square', 'Triangular']
        layout_index = layout_options.index(default_layout) if default_layout in layout_options else 0
        
        layout_pattern = st.selectbox(
            "Layout Pattern",
            options=layout_options,
            index=layout_index,
            help="Sprinkler arrangement pattern",
            key="layout_pattern_select"
        )
    
    with col2:
        st.markdown("#### Calculated Values")
        
        # Spacing ratios
        spacing_ratio_along = spacing_along / wetted_diameter
        spacing_ratio_between = spacing_between / wetted_diameter
        
        st.metric("Spacing Ratio (Along)", f"{spacing_ratio_along:.2f}")
        st.metric("Spacing Ratio (Between)", f"{spacing_ratio_between:.2f}")
        
        # Area covered per sprinkler
        area_per_sprinkler = spacing_along * spacing_between
        st.metric("Area per Sprinkler", f"{area_per_sprinkler:.1f} m²")
        
        # Sprinkler density
        sprinklers_per_ha = 10000 / area_per_sprinkler
        st.metric("Sprinklers per Hectare", f"{sprinklers_per_ha:.0f}")
        
        # Check spacing adequacy
        if spacing_ratio_along > 0.65 or spacing_ratio_between > 0.65:
            st.warning("⚠️ Spacing may be too wide for adequate overlap")
        elif spacing_ratio_along < 0.3 or spacing_ratio_between < 0.3:
            st.warning("⚠️ Spacing may be too narrow (over-designed)")
        else:
            st.success("✅ Spacing is within acceptable range")
    
    # Visualize spacing pattern
    st.markdown("---")
    st.markdown("#### Spacing Layout Visualization")
    
    # Create grid
    n_sprinklers_x = 5
    n_sprinklers_y = 4
    
    fig = go.Figure()
    
    # Plot sprinkler positions
    for i in range(n_sprinklers_y):
        for j in range(n_sprinklers_x):
            x = j * spacing_along
            y = i * spacing_between
            
            # Sprinkler point
            fig.add_trace(go.Scatter(
                x=[x], y=[y],
                mode='markers',
                marker=dict(size=10, color='blue', symbol='circle'),
                showlegend=False,
                hovertext=f"Sprinkler ({j+1}, {i+1})"
            ))
            
            # Wetted circle
            theta = np.linspace(0, 2*np.pi, 100)
            circle_x = x + (wetted_diameter/2) * np.cos(theta)
            circle_y = y + (wetted_diameter/2) * np.sin(theta)
            
            fig.add_trace(go.Scatter(
                x=circle_x, y=circle_y,
                mode='lines',
                line=dict(color='lightblue', width=1, dash='dash'),
                showlegend=False,
                hoverinfo='skip'
            ))
    
    # Add grid lines
    for i in range(n_sprinklers_y):
        y = i * spacing_between
        fig.add_hline(y=y, line_dash="dot", line_color="gray", opacity=0.3)
    
    for j in range(n_sprinklers_x):
        x = j * spacing_along
        fig.add_vline(x=x, line_dash="dot", line_color="gray", opacity=0.3)
    
    fig.update_layout(
        title="Sprinkler Layout Pattern",
        xaxis_title="Distance (m)",
        yaxis_title="Distance (m)",
        template="plotly_white",
        height=500,
        yaxis=dict(scaleanchor="x", scaleratio=1),
        showlegend=False
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Save spacing data
    if st.button("Save Spacing Design", type="primary"):
        st.session_state.project_data['sprinkler_data'].update({
            'spacing_along': spacing_along,
            'spacing_between': spacing_between,
            'layout_pattern': layout_pattern,
            'area_per_sprinkler': area_per_sprinkler,
            'sprinklers_per_ha': sprinklers_per_ha
        })
        st.success("✅ Spacing design saved successfully!")

def show_application_rate():
    """Calculate and verify application rate"""
    st.markdown('<h2 class="sub-header">Application Rate Analysis</h2>', unsafe_allow_html=True)
    
    st.info("""**Important:** This calculates the ACTUAL application rate for YOUR design based on YOUR spacing. 
    This rate changes when you adjust sprinkler spacing and MUST be ≤ soil infiltration rate to prevent runoff.""")
    
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete sprinkler selection and spacing design first.")
        return
    
    sprinkler = st.session_state.project_data['sprinkler_data']
    
    # Solid Set application rate calculation
    if 'spacing_along' not in sprinkler or 'flow' not in sprinkler:
        st.warning("⚠️ Please complete spacing design first.")
        return
    
    flow_rate = sprinkler['flow']  # l/h
    spacing_along = sprinkler['spacing_along']  # m
    spacing_between = sprinkler['spacing_between']  # m
    
    # Calculate application rate
    app_rate = flow_rate / (spacing_along * spacing_between)  # mm/hr
    
    # Get soil infiltration rate
    soil_type = st.session_state.project_data.get('soil_type', 'Loam')
    soil_infiltration = get_soil_infiltration_rate(soil_type)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Actual Sprinkler Application Rate", f"{app_rate:.2f} mm/hr", 
                 help=f"Formula: {flow_rate:.0f} l/hr ÷ ({spacing_along:.2f}m × {spacing_between:.2f}m)")
    with col2:
        st.metric("Soil Infiltration Rate", f"{soil_infiltration:.2f} mm/hr")
    with col3:
        if app_rate <= soil_infiltration:
            st.success("✅ Rate OK")
        else:
            st.error("❌ Rate too high")
    
    # Application rate vs infiltration
    st.markdown("---")
    st.markdown("#### Application Rate vs Soil Infiltration")
    
    if app_rate > soil_infiltration:
        st.error(f"""
        ⚠️ **Warning:** Application rate ({app_rate:.2f} mm/hr) exceeds soil infiltration rate ({soil_infiltration:.1f} mm/hr).
        
        **Consequences:**
        - Surface runoff
        - Reduced irrigation efficiency
        - Potential erosion
        
        **Solutions:**
        1. Increase sprinkler spacing
        2. Use lower flow nozzles
        3. Implement cycle-soak irrigation
        """)
        
        # Recommend cycle-soak
        st.markdown("#### Cycle-Soak Recommendation")
        
        gross_depth = st.session_state.project_data.get('irrigation_requirements', {}).get('gross_depth', 20)
        
        # Operating time to apply gross depth at soil infiltration rate
        operating_time = gross_depth / soil_infiltration  # hours
        
        # Number of cycles
        max_cycle_time = 2  # hours
        n_cycles = int(np.ceil(operating_time / max_cycle_time))
        
        cycle_time = operating_time / n_cycles
        soak_time = cycle_time  # Equal soak time
        
        st.info(f"""
        **Recommended Cycle-Soak Schedule:**
        - Number of cycles: {n_cycles}
        - Irrigation time per cycle: {cycle_time:.1f} hours
        - Soak time between cycles: {soak_time:.1f} hours
        - Total irrigation time: {operating_time:.1f} hours
        - Total time (including soak): {operating_time + soak_time * (n_cycles-1):.1f} hours
        """)
    else:
        st.success("""
        ✅ Application rate is within acceptable limits. No runoff expected.
        """)
    
    # Application uniformity impact
    st.markdown("---")
    st.markdown("#### Irrigation Duration")
    
    if 'irrigation_requirements' in st.session_state.project_data:
        irr_req = st.session_state.project_data['irrigation_requirements']
        gross_depth = irr_req.get('gross_depth', 20)
        
        # Calculate irrigation duration
        irrigation_time = gross_depth / app_rate  # hours
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Gross Application Depth", f"{gross_depth:.1f} mm")
        with col2:
            st.metric("Irrigation Duration", f"{irrigation_time:.2f} hours")
        with col3:
            st.metric("Duration (minutes)", f"{irrigation_time*60:.0f} min")

def show_uniformity_analysis():
    """Analyze distribution uniformity"""
    st.markdown('<h2 class="sub-header">Distribution Uniformity</h2>', unsafe_allow_html=True)
    
    if 'sprinkler_data' not in st.session_state.project_data:
        st.warning("⚠️ Please complete sprinkler selection first.")
        return
    
    sprinkler = st.session_state.project_data['sprinkler_data']
    cu = sprinkler.get('cu', 85)
    
    st.markdown("#### Christiansen Uniformity Coefficient (CU)")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Manufacturer's CU", f"{cu}%")
        
        # Adjust for wind
        wind_speed = sprinkler.get('wind_speed', 2.0)
        
        if wind_speed < 2:
            cu_adjusted = cu
            wind_effect = "Minimal"
        elif wind_speed < 4:
            cu_adjusted = cu - 5
            wind_effect = "Moderate reduction"
        else:
            cu_adjusted = cu - 10
            wind_effect = "Significant reduction"
        
        st.metric("Wind-Adjusted CU", f"{cu_adjusted}%")
        st.info(f"Wind Effect: {wind_effect}")
    
    with col2:
        st.markdown("#### Distribution Uniformity (DU)")
        
        # DU is typically 5-10% lower than CU
        du = cu_adjusted - 8
        
        st.metric("Distribution Uniformity (DU)", f"{du}%")
        
        if du >= 84:
            rating = "Excellent"
            color = "success"
        elif du >= 68:
            rating = "Good"
            color = "info"
        elif du >= 52:
            rating = "Fair"
            color = "warning"
        else:
            rating = "Poor"
            color = "error"
        
        st.markdown(f"**Rating:** :{color}[{rating}]")
    
    # Uniformity impact on efficiency
    st.markdown("---")
    st.markdown("#### Impact on Irrigation Efficiency")
    
    st.markdown(f"""
    **Current Uniformity:** {du}%
    
    **Effects:**
    - Areas receiving less water: {(100-du):.0f}% under-irrigated
    - Potential yield reduction in dry spots
    - Water waste in over-irrigated areas
    
    **Recommendations to Improve Uniformity:**
    1. Reduce sprinkler spacing (increase overlap)
    2. Irrigate during low-wind periods
    3. Ensure proper operating pressure
    4. Regular maintenance and nozzle checks
    5. Use sprinklers with better distribution patterns
    """)
    
    # Simulate distribution pattern
    st.markdown("---")
    st.markdown("#### Distribution Pattern Simulation")
    
    create_distribution_pattern_plot()

def get_sprinkler_database():
    """Database of agricultural sprinkler models from major manufacturers with multiple nozzle options"""
    return [
        # SENNINGER i-Wob IMPACT SPRINKLERS - Multiple Nozzle Sizes
        {'Model': 'Senninger i-Wob', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#7 (3.57mm)', 'Pressure': 138, 'Flow': 200, 'Diameter': 18, 'App_Rate': 3.8, 'CU': 84,
         'URL': 'https://www.senninger.com/products/i-wob'},
        {'Model': 'Senninger i-Wob', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#8 (3.97mm)', 'Pressure': 138, 'Flow': 250, 'Diameter': 20, 'App_Rate': 4.0, 'CU': 85,
         'URL': 'https://www.senninger.com/products/i-wob'},
        {'Model': 'Senninger i-Wob', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#9 (4.37mm)', 'Pressure': 172, 'Flow': 310, 'Diameter': 21, 'App_Rate': 4.3, 'CU': 85,
         'URL': 'https://www.senninger.com/products/i-wob'},
        {'Model': 'Senninger i-Wob', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#10 (4.76mm)', 'Pressure': 172, 'Flow': 380, 'Diameter': 23, 'App_Rate': 4.5, 'CU': 86,
         'URL': 'https://www.senninger.com/products/i-wob'},
        {'Model': 'Senninger i-Wob', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#11 (5.16mm)', 'Pressure': 207, 'Flow': 530, 'Diameter': 26, 'App_Rate': 5.0, 'CU': 87,
         'URL': 'https://www.senninger.com/products/i-wob'},
        {'Model': 'Senninger i-Wob', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#12 (5.56mm)', 'Pressure': 207, 'Flow': 650, 'Diameter': 28, 'App_Rate': 5.3, 'CU': 87,
         'URL': 'https://www.senninger.com/products/i-wob'},
        
        # SENNINGER 3023 IMPACT SPRINKLERS - Multiple Nozzles
        {'Model': 'Senninger 3023', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.0 x 2.0mm', 'Pressure': 276, 'Flow': 520, 'Diameter': 28, 'App_Rate': 5.2, 'CU': 87,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3023', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.37 x 2.38mm', 'Pressure': 276, 'Flow': 650, 'Diameter': 30, 'App_Rate': 5.5, 'CU': 88,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3023', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.76 x 2.78mm', 'Pressure': 310, 'Flow': 820, 'Diameter': 33, 'App_Rate': 6.0, 'CU': 89,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3023', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '5.16 x 3.17mm', 'Pressure': 345, 'Flow': 1050, 'Diameter': 36, 'App_Rate': 6.5, 'CU': 90,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3023', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '5.56 x 3.57mm', 'Pressure': 345, 'Flow': 1250, 'Diameter': 38, 'App_Rate': 6.8, 'CU': 90,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        
        # SENNINGER 3030 IMPACT SPRINKLERS - High Pressure Multiple Nozzles
        {'Model': 'Senninger 3030', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.16 x 3.17mm', 'Pressure': 414, 'Flow': 1180, 'Diameter': 39, 'App_Rate': 6.9, 'CU': 89,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3030', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.56 x 3.57mm', 'Pressure': 414, 'Flow': 1450, 'Diameter': 41, 'App_Rate': 7.2, 'CU': 90,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3030', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.95 x 3.97mm', 'Pressure': 448, 'Flow': 1750, 'Diameter': 44, 'App_Rate': 7.5, 'CU': 91,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        {'Model': 'Senninger 3030', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '6.35 x 4.37mm', 'Pressure': 483, 'Flow': 2100, 'Diameter': 46, 'App_Rate': 8.0, 'CU': 91,
         'URL': 'https://www.senninger.com/products/standard-impact'},
        
        # NELSON R3000 ROTATORS - Full Color Range
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#7 Gray', 'Pressure': 138, 'Flow': 180, 'Diameter': 16, 'App_Rate': 3.7, 'CU': 92,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#8 Blue', 'Pressure': 138, 'Flow': 230, 'Diameter': 18, 'App_Rate': 4.2, 'CU': 92,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#9 Red', 'Pressure': 172, 'Flow': 340, 'Diameter': 21, 'App_Rate': 4.8, 'CU': 93,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#10 Black', 'Pressure': 207, 'Flow': 480, 'Diameter': 24, 'App_Rate': 5.2, 'CU': 94,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '#11 Purple', 'Pressure': 276, 'Flow': 680, 'Diameter': 28, 'App_Rate': 5.8, 'CU': 94,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '#12 Orange', 'Pressure': 310, 'Flow': 850, 'Diameter': 31, 'App_Rate': 6.3, 'CU': 95,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        {'Model': 'Nelson R3000', 'Type': 'Rotator Nozzle', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '#13 Lime', 'Pressure': 345, 'Flow': 1050, 'Diameter': 34, 'App_Rate': 6.7, 'CU': 95,
         'URL': 'https://nelsonirrigation.com/products/rotator'},
        
        # NELSON D3000 IMPACT SPRINKLERS - Multiple Nozzles
        {'Model': 'Nelson D3000', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.76 x 3.18mm', 'Pressure': 310, 'Flow': 720, 'Diameter': 32, 'App_Rate': 5.9, 'CU': 87,
         'URL': 'https://nelsonirrigation.com/products/d3000'},
        {'Model': 'Nelson D3000', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '5.16 x 3.57mm', 'Pressure': 345, 'Flow': 950, 'Diameter': 35, 'App_Rate': 6.4, 'CU': 88,
         'URL': 'https://nelsonirrigation.com/products/d3000'},
        {'Model': 'Nelson D3000', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.56 x 3.57mm', 'Pressure': 414, 'Flow': 1350, 'Diameter': 40, 'App_Rate': 7.2, 'CU': 88,
         'URL': 'https://nelsonirrigation.com/products/d3000'},
        {'Model': 'Nelson D3000', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.95 x 3.97mm', 'Pressure': 448, 'Flow': 1650, 'Diameter': 43, 'App_Rate': 7.6, 'CU': 89,
         'URL': 'https://nelsonirrigation.com/products/d3000'},
        {'Model': 'Nelson D3000', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '6.35 x 4.37mm', 'Pressure': 483, 'Flow': 1950, 'Diameter': 46, 'App_Rate': 8.0, 'CU': 89,
         'URL': 'https://nelsonirrigation.com/products/d3000'},
        
        # NELSON SR100 IMPACT SPRINKLERS - Multiple Nozzles
        {'Model': 'Nelson SR100', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.37 x 2.78mm', 'Pressure': 276, 'Flow': 650, 'Diameter': 30, 'App_Rate': 5.6, 'CU': 86,
         'URL': 'https://nelsonirrigation.com/products/sr100'},
        {'Model': 'Nelson SR100', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.76 x 3.18mm', 'Pressure': 310, 'Flow': 880, 'Diameter': 34, 'App_Rate': 6.2, 'CU': 87,
         'URL': 'https://nelsonirrigation.com/products/sr100'},
        {'Model': 'Nelson SR100', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '5.16 x 3.57mm', 'Pressure': 345, 'Flow': 1100, 'Diameter': 37, 'App_Rate': 6.7, 'CU': 87,
         'URL': 'https://nelsonirrigation.com/products/sr100'},
        
        # JAIN SLEEK PLUS - Multiple Nozzles
        {'Model': 'Jain Sleek Plus', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '3.0 x 1.5mm', 'Pressure': 207, 'Flow': 250, 'Diameter': 20, 'App_Rate': 4.0, 'CU': 83,
         'URL': 'https://www.jains.com/sleek-plus'},
        {'Model': 'Jain Sleek Plus', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '3.5 x 2.0mm', 'Pressure': 207, 'Flow': 320, 'Diameter': 22, 'App_Rate': 4.3, 'CU': 84,
         'URL': 'https://www.jains.com/sleek-plus'},
        {'Model': 'Jain Sleek Plus', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '4.0 x 2.5mm', 'Pressure': 241, 'Flow': 490, 'Diameter': 25, 'App_Rate': 4.9, 'CU': 85,
         'URL': 'https://www.jains.com/sleek-plus'},
        {'Model': 'Jain Sleek Plus', 'Type': 'Impact Sprinkler', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '4.5 x 2.8mm', 'Pressure': 241, 'Flow': 620, 'Diameter': 27, 'App_Rate': 5.4, 'CU': 85,
         'URL': 'https://www.jains.com/sleek-plus'},
        
        # JAIN SUPER 71 - Multiple Nozzles
        {'Model': 'Jain Super 71', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.0 x 2.5mm', 'Pressure': 276, 'Flow': 580, 'Diameter': 29, 'App_Rate': 5.4, 'CU': 85,
         'URL': 'https://www.jains.com/super71'},
        {'Model': 'Jain Super 71', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.5 x 3.0mm', 'Pressure': 310, 'Flow': 780, 'Diameter': 32, 'App_Rate': 6.1, 'CU': 86,
         'URL': 'https://www.jains.com/super71'},
        {'Model': 'Jain Super 71', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '5.0 x 3.5mm', 'Pressure': 345, 'Flow': 1020, 'Diameter': 35, 'App_Rate': 6.7, 'CU': 87,
         'URL': 'https://www.jains.com/super71'},
        {'Model': 'Jain Super 71', 'Type': 'Impact Sprinkler', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '5.5 x 3.8mm', 'Pressure': 345, 'Flow': 1280, 'Diameter': 37, 'App_Rate': 7.1, 'CU': 87,
         'URL': 'https://www.jains.com/super71'},
        
        # JAIN TURBO 90 - Multiple Nozzles
        {'Model': 'Jain Turbo 90', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.0 x 3.2mm', 'Pressure': 380, 'Flow': 1100, 'Diameter': 38, 'App_Rate': 6.8, 'CU': 87,
         'URL': 'https://www.jains.com/turbo90'},
        {'Model': 'Jain Turbo 90', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '5.5 x 3.5mm', 'Pressure': 414, 'Flow': 1380, 'Diameter': 42, 'App_Rate': 7.3, 'CU': 88,
         'URL': 'https://www.jains.com/turbo90'},
        {'Model': 'Jain Turbo 90', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '6.0 x 4.0mm', 'Pressure': 448, 'Flow': 1680, 'Diameter': 45, 'App_Rate': 7.8, 'CU': 89,
         'URL': 'https://www.jains.com/turbo90'},
        {'Model': 'Jain Turbo 90', 'Type': 'Impact Sprinkler', 'Category': 'High Pressure (HP)', 
         'Nozzle': '6.5 x 4.4mm', 'Pressure': 483, 'Flow': 2050, 'Diameter': 48, 'App_Rate': 8.3, 'CU': 89,
         'URL': 'https://www.jains.com/turbo90'},
        
        # RAIN BIRD R50 SPRAY HEADS - Pop-up Sprays for Close Spacing
        {'Model': 'Rain Bird 1800 R50', 'Type': 'Spray Head', 'Category': 'Low Pressure (LP)', 
         'Nozzle': 'R50 (4.6m radius)', 'Pressure': 207, 'Flow': 120, 'Diameter': 9.2, 'App_Rate': 12.0, 'CU': 80,
         'URL': 'https://www.rainbird.com/products/1800-series'},
        {'Model': 'Rain Bird 1800 R75', 'Type': 'Spray Head', 'Category': 'Low Pressure (LP)', 
         'Nozzle': 'R75 (6.9m radius)', 'Pressure': 207, 'Flow': 185, 'Diameter': 13.8, 'App_Rate': 8.5, 'CU': 82,
         'URL': 'https://www.rainbird.com/products/1800-series'},
        {'Model': 'Rain Bird 1800 R100', 'Type': 'Spray Head', 'Category': 'Low Pressure (LP)', 
         'Nozzle': 'R100 (9.1m radius)', 'Pressure': 207, 'Flow': 240, 'Diameter': 18.2, 'App_Rate': 6.5, 'CU': 83,
         'URL': 'https://www.rainbird.com/products/1800-series'},
        
        # RAIN BIRD 5000 SERIES ROTORS - Gear-Driven
        {'Model': 'Rain Bird 5000', 'Type': 'Gear-Driven Rotor', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '2.0 Blue', 'Pressure': 207, 'Flow': 140, 'Diameter': 15, 'App_Rate': 6.0, 'CU': 88,
         'URL': 'https://www.rainbird.com/products/5000-series'},
        {'Model': 'Rain Bird 5000', 'Type': 'Gear-Driven Rotor', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '3.0 Red', 'Pressure': 207, 'Flow': 230, 'Diameter': 18, 'App_Rate': 7.0, 'CU': 89,
         'URL': 'https://www.rainbird.com/products/5000-series'},
        {'Model': 'Rain Bird 5000', 'Type': 'Gear-Driven Rotor', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '4.0 Black', 'Pressure': 276, 'Flow': 380, 'Diameter': 22, 'App_Rate': 7.5, 'CU': 90,
         'URL': 'https://www.rainbird.com/products/5000-series'},
        
        # RAIN BIRD AG-5/AG-7 Agricultural Rotors
        {'Model': 'Rain Bird AG-5', 'Type': 'Gear-Driven Rotor', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#4 Gray', 'Pressure': 207, 'Flow': 280, 'Diameter': 20, 'App_Rate': 4.2, 'CU': 90,
         'URL': 'https://www.rainbird.com/products/ag-5'},
        {'Model': 'Rain Bird AG-5', 'Type': 'Gear-Driven Rotor', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '#5 Black', 'Pressure': 207, 'Flow': 380, 'Diameter': 23, 'App_Rate': 4.6, 'CU': 91,
         'URL': 'https://www.rainbird.com/products/ag-5'},
        {'Model': 'Rain Bird AG-7', 'Type': 'Gear-Driven Rotor', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '#6 Beige', 'Pressure': 276, 'Flow': 550, 'Diameter': 27, 'App_Rate': 5.2, 'CU': 91,
         'URL': 'https://www.rainbird.com/products/ag-7'},
        {'Model': 'Rain Bird AG-7', 'Type': 'Gear-Driven Rotor', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '#7 White', 'Pressure': 276, 'Flow': 720, 'Diameter': 30, 'App_Rate': 5.9, 'CU': 92,
         'URL': 'https://www.rainbird.com/products/ag-7'},
        
        # RIVULIS D3000 ROTATORS - Full Range
        {'Model': 'Rivulis D3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '2.0mm Tan', 'Pressure': 138, 'Flow': 160, 'Diameter': 15, 'App_Rate': 3.5, 'CU': 92,
         'URL': 'https://www.rivulis.com/d3000'},
        {'Model': 'Rivulis D3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '2.4mm Blue', 'Pressure': 138, 'Flow': 210, 'Diameter': 17, 'App_Rate': 4.0, 'CU': 93,
         'URL': 'https://www.rivulis.com/d3000'},
        {'Model': 'Rivulis D3000', 'Type': 'Rotator Nozzle', 'Category': 'Low Pressure (LP)', 
         'Nozzle': '2.8mm Green', 'Pressure': 172, 'Flow': 310, 'Diameter': 20, 'App_Rate': 4.7, 'CU': 94,
         'URL': 'https://www.rivulis.com/d3000'},
        {'Model': 'Rivulis D3000', 'Type': 'Rotator Nozzle', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '3.2mm Red', 'Pressure': 276, 'Flow': 560, 'Diameter': 27, 'App_Rate': 5.5, 'CU': 94,
         'URL': 'https://www.rivulis.com/d3000'},
        {'Model': 'Rivulis D3000', 'Type': 'Rotator Nozzle', 'Category': 'Medium Pressure (MP)', 
         'Nozzle': '3.6mm Black', 'Pressure': 310, 'Flow': 720, 'Diameter': 30, 'App_Rate': 5.9, 'CU': 95,
         'URL': 'https://www.rivulis.com/d3000'},
    ]

def get_soil_infiltration_rate(soil_type):
    """Get basic infiltration rate for soil type (mm/hr)"""
    rates = {
        'Sandy': 25,
        'Loamy Sand': 20,
        'Sandy Loam': 15,
        'Loam': 10,
        'Silty Loam': 8,
        'Silt': 7,
        'Clay Loam': 5,
        'Clay': 3
    }
    return rates.get(soil_type, 10)

def create_distribution_pattern_plot():
    """Create a simulated water distribution pattern"""
    # Create grid
    x = np.linspace(-20, 20, 100)
    y = np.linspace(-20, 20, 100)
    X, Y = np.meshgrid(x, y)
    
    # Simulate overlapping sprinkler patterns (simplified)
    Z = np.zeros_like(X)
    
    # Center sprinkler
    R = np.sqrt(X**2 + Y**2)
    Z += np.maximum(0, 10 - R*0.5)
    
    # Adjacent sprinklers (simplified 4-sprinkler overlap)
    spacing = 12
    for dx, dy in [(spacing, 0), (-spacing, 0), (0, spacing), (0, -spacing)]:
        R = np.sqrt((X-dx)**2 + (Y-dy)**2)
        Z += np.maximum(0, 10 - R*0.5)
    
    # Normalize
    Z = Z / Z.max() * 100
    
    fig = go.Figure(data=[go.Contour(
        z=Z,
        x=x,
        y=y,
        colorscale='Blues',
        contours=dict(
            start=0,
            end=100,
            size=10
        ),
        colorbar=dict(title="Depth (%)")
    )])
    
    # Add sprinkler positions
    positions = [(0, 0), (spacing, 0), (-spacing, 0), (0, spacing), (0, -spacing)]
    for px, py in positions:
        fig.add_trace(go.Scatter(
            x=[px], y=[py],
            mode='markers',
            marker=dict(size=12, color='red', symbol='x'),
            showlegend=False,
            hovertext="Sprinkler"
        ))
    
    fig.update_layout(
        title="Water Distribution Pattern (4-Sprinkler Overlap)",
        xaxis_title="Distance (m)",
        yaxis_title="Distance (m)",
        template="plotly_white",
        height=500,
        yaxis=dict(scaleanchor="x", scaleratio=1)
    )
    
    st.plotly_chart(fig, width="stretch")

