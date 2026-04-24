"""
Crop Water Requirements Module
Calculates ET0, crop coefficients, and irrigation requirements
Based on FAO Penman-Monteith equation and crop coefficient approach
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Import field layout visualization functions
try:
    from modules.field_layout_manager import (
        render_field_layout_visualization,
        render_field_layout_summary,
        get_field_layout,
        get_blocks_by_irrigation_type
    )
    FIELD_LAYOUT_AVAILABLE = True
except ImportError:
    FIELD_LAYOUT_AVAILABLE = False


def show_field_layout_section():
    """Display field layout visualization for sprinkler blocks at the top of the module."""
    if not FIELD_LAYOUT_AVAILABLE:
        return
    
    field_layout = get_field_layout()
    sprinkler_blocks = get_blocks_by_irrigation_type('sprinkler')
    
    # Only show if there are sprinkler blocks defined
    if not sprinkler_blocks:
        return
    
    st.markdown("---")
    st.markdown("### 🌧️ Sprinkler Irrigation Field Layout")
    
    with st.expander("📊 View Field Layout from Home Page Setup", expanded=True):
        # Show summary cards
        render_field_layout_summary(irrigation_filter='sprinkler')
        
        # Show visualization
        render_field_layout_visualization(
            irrigation_filter='sprinkler',
            title="Sprinkler Irrigation Blocks - Field Layout",
            height=400,
            show_legend=True
        )
        
        # Show additional info
        st.info("""
        💡 **This visualization shows your sprinkler irrigation blocks from the Field Layout setup on the Home page.**
        
        The crop water requirements calculated below will apply to these blocks. Any changes to the field layout 
        should be made on the Home page under "Field Layout & Blocks" tab.
        """)
    
    st.markdown("---")


def show():
    st.markdown('<h1 class="main-header">Crop Water Requirements</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    Calculate reference evapotranspiration (ET₀) and crop water requirements using the 
    FAO Penman-Monteith equation and crop coefficient approach.
    </div>
    """, unsafe_allow_html=True)
    
    # Check if project is set up
    if not st.session_state.project_data.get('project_name'):
        st.warning("⚠️ Please set up your project information in the Home page first.")
        return
    
    # Show field layout visualization for sprinkler blocks
    show_field_layout_section()
    
    tabs = st.tabs(["Climate Data", "ET₀ Calculation", "Crop Coefficients", "Irrigation Requirements"])
    
    # Tab 1: Climate Data
    with tabs[0]:
        show_climate_data_input()
    
    # Tab 2: ET0 Calculation
    with tabs[1]:
        show_et0_calculation()
    
    # Tab 3: Crop Coefficients
    with tabs[2]:
        show_crop_coefficients()
    
    # Tab 4: Irrigation Requirements
    with tabs[3]:
        show_irrigation_requirements()

def show_climate_data_input():
    """Input climate data for ET0 calculation"""
    st.markdown('<h2 class="sub-header">Climate Data Input</h2>', unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Location Parameters")
        latitude = st.number_input(
            "Latitude (decimal degrees)",
            min_value=-90.0,
            max_value=90.0,
            value=float(st.session_state.project_data.get('climate_data', {}).get('latitude', 0.0)),
            step=0.1,
            help="Positive for North, negative for South"
        )
        
        altitude = st.session_state.project_data.get('altitude', 0.0)
        st.info(f"Altitude: {altitude} m (from project settings)")
        
        st.markdown("#### Monthly Climate Data")
        input_method = st.radio(
            "Data Input Method",
            ["Manual Entry", "Upload CSV", "Upload CSV (AQUASTAT)"],
            horizontal=True,
            help="AQUASTAT format includes pre-calculated ET₀ values"
        )
    
    with col2:
        st.markdown("#### Growing Season")
        month_options = ['January', 'February', 'March', 'April', 'May', 'June',
                        'July', 'August', 'September', 'October', 'November', 'December']
        
        start_month = st.selectbox(
            "Growing Season Start Month",
            options=month_options,
            index=month_options.index(
                st.session_state.project_data.get('climate_data', {}).get('start_month', 'January')
            )
        )
        
        end_month = st.selectbox(
            "Growing Season End Month",
            options=month_options,
            index=month_options.index(
                st.session_state.project_data.get('climate_data', {}).get('end_month', 'December')
            )
        )
    
    if input_method == "Manual Entry":
        show_manual_climate_input(start_month, end_month, month_options)
    elif input_method == "Upload CSV (AQUASTAT)":
        show_aquastat_upload()
    else:
        show_csv_upload()
    
    # Save climate data
    if st.button("Save Climate Data", type="primary"):
        climate_data = st.session_state.get('temp_climate_data', {})
        climate_data['latitude'] = latitude
        climate_data['start_month'] = start_month
        climate_data['end_month'] = end_month
        
        st.session_state.project_data['climate_data'] = climate_data
        st.success("✅ Climate data saved successfully!")

def show_manual_climate_input(start_month, end_month, month_options):
    """Manual entry of climate data"""
    st.markdown("---")
    st.markdown("#### Enter Monthly Climate Parameters")
    
    # Get month range
    start_idx = month_options.index(start_month)
    end_idx = month_options.index(end_month)
    
    if end_idx >= start_idx:
        months = month_options[start_idx:end_idx+1]
    else:
        months = month_options[start_idx:] + month_options[:end_idx+1]
    
    # Initialize dataframe
    if 'temp_climate_data' not in st.session_state:
        st.session_state.temp_climate_data = {}
    
    # Check if we have existing data in project
    existing_data = st.session_state.project_data.get('climate_data', {}).get('monthly_data')
    
    # Force reload from project data if temp data doesn't exist or project was just loaded
    project_just_loaded = st.session_state.get('_cwr_climate_loaded_from_project') != st.session_state.project_data.get('project_name', '')
    
    if 'monthly_data' not in st.session_state.temp_climate_data or project_just_loaded:
        if existing_data is not None:
            # Handle both DataFrame and dict (from JSON load)
            if isinstance(existing_data, pd.DataFrame):
                st.session_state.temp_climate_data['monthly_data'] = existing_data.copy()
            elif isinstance(existing_data, (dict, list)):
                # Convert from dict/list back to DataFrame
                try:
                    st.session_state.temp_climate_data['monthly_data'] = pd.DataFrame(existing_data)
                except Exception:
                    st.session_state.temp_climate_data['monthly_data'] = pd.DataFrame({
                        'Month': months,
                        'T_max (°C)': [30.0] * len(months),
                        'T_min (°C)': [15.0] * len(months),
                        'RH_mean (%)': [60.0] * len(months),
                        'Wind Speed (m/s)': [2.0] * len(months),
                        'Sunshine Hours (h)': [8.0] * len(months),
                        'Rainfall (mm)': [50.0] * len(months)
                    })
            else:
                st.session_state.temp_climate_data['monthly_data'] = pd.DataFrame({
                    'Month': months,
                    'T_max (°C)': [30.0] * len(months),
                    'T_min (°C)': [15.0] * len(months),
                    'RH_mean (%)': [60.0] * len(months),
                    'Wind Speed (m/s)': [2.0] * len(months),
                    'Sunshine Hours (h)': [8.0] * len(months),
                    'Rainfall (mm)': [50.0] * len(months)
                })
        else:
            st.session_state.temp_climate_data['monthly_data'] = pd.DataFrame({
                'Month': months,
                'T_max (°C)': [30.0] * len(months),
                'T_min (°C)': [15.0] * len(months),
                'RH_mean (%)': [60.0] * len(months),
                'Wind Speed (m/s)': [2.0] * len(months),
                'Sunshine Hours (h)': [8.0] * len(months),
                'Rainfall (mm)': [50.0] * len(months)
            })
        
        # Mark that we've loaded from this project
        st.session_state['_cwr_climate_loaded_from_project'] = st.session_state.project_data.get('project_name', '')
    
    # Data editor
    df = st.data_editor(
        st.session_state.temp_climate_data['monthly_data'],
        hide_index=True,
        width="stretch",
        column_config={
            "Month": st.column_config.TextColumn("Month", disabled=True),
            "T_max (°C)": st.column_config.NumberColumn("Max Temp (°C)", min_value=-10, max_value=50, step=0.1),
            "T_min (°C)": st.column_config.NumberColumn("Min Temp (°C)", min_value=-20, max_value=40, step=0.1),
            "RH_mean (%)": st.column_config.NumberColumn("Humidity (%)", min_value=0, max_value=100, step=1),
            "Wind Speed (m/s)": st.column_config.NumberColumn("Wind (m/s)", min_value=0, max_value=20, step=0.1),
            "Sunshine Hours (h)": st.column_config.NumberColumn("Sunshine (h)", min_value=0, max_value=16, step=0.1),
            "Rainfall (mm)": st.column_config.NumberColumn("Rainfall (mm)", min_value=0, step=1)
        }
    )
    
    st.session_state.temp_climate_data['monthly_data'] = df

def show_csv_upload():
    """Upload climate data from CSV"""
    st.markdown("---")
    st.markdown("#### Upload Climate Data CSV")
    
    st.info("""
    CSV file should contain columns: Month, T_max, T_min, RH_mean, Wind_Speed, Sunshine_Hours, Rainfall
    """)
    
    uploaded_file = st.file_uploader("Choose a CSV file", type=['csv'])
    
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.session_state.temp_climate_data['monthly_data'] = df
            st.success("✅ Data uploaded successfully!")
            st.dataframe(df, width="stretch")
        except Exception as e:
            st.error(f"Error reading CSV: {e}")


def show_aquastat_upload():
    """
    Upload climate data from AQUASTAT format CSV.
    AQUASTAT provides pre-calculated ET₀ values.
    
    Expected columns:
    - Month: Jan, Feb, Mar, etc.
    - Prc. (mm/m): Precipitation
    - Tmp. min. (°C): Minimum temperature
    - Tmp. max. (°C): Maximum temperature  
    - Tmp. Mean (°C): Mean temperature
    - Rel. Hum. (%): Relative humidity
    - Sun shine (J m⁻² day⁻¹): Solar radiation
    - Wind (2m) (m/s): Wind speed at 2m
    - ETo (mm/m): Reference evapotranspiration (monthly)
    """
    st.markdown("---")
    st.markdown("#### Upload AQUASTAT Climate Data")
    
    st.info("""
    🌍 **AQUASTAT Format** - Data from FAO AQUASTAT includes pre-calculated ET₀ values.
    
    Expected columns: `Month`, `Prc.`, `Tmp. min.`, `Tmp. max.`, `Tmp. Mean`, `Rel. Hum.`, `Sun shine`, `Wind (2m)`, `ETo`
    
    💡 The ET₀ values will be used directly (no Penman-Monteith calculation needed).
    """)
    
    uploaded_file = st.file_uploader("Choose AQUASTAT CSV file", type=['csv'], key='aquastat_upload')
    
    if uploaded_file is not None:
        try:
            # Try different encodings for AQUASTAT data (may contain special characters)
            df_raw = None
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
            
            for encoding in encodings:
                try:
                    uploaded_file.seek(0)  # Reset file pointer
                    df_raw = pd.read_csv(uploaded_file, encoding=encoding)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            
            if df_raw is None:
                st.error("❌ Could not decode CSV file. Please save it as UTF-8.")
                return
            
            # Show raw data
            with st.expander("📄 Raw AQUASTAT Data", expanded=False):
                st.dataframe(df_raw, width="stretch")
            
            # Map AQUASTAT columns to our format
            df_converted = convert_aquastat_format(df_raw)
            
            if df_converted is not None:
                # Store the converted data
                if 'temp_climate_data' not in st.session_state:
                    st.session_state.temp_climate_data = {}
                
                st.session_state.temp_climate_data['monthly_data'] = df_converted
                st.session_state.temp_climate_data['data_source'] = 'AQUASTAT'
                st.session_state.temp_climate_data['has_eto'] = True
                
                st.success("✅ AQUASTAT data uploaded and converted successfully!")
                
                # Display converted data
                st.markdown("#### Converted Climate Data")
                st.dataframe(
                    df_converted,
                    hide_index=True,
                    width="stretch",
                    column_config={
                        "ET₀ (mm/day)": st.column_config.NumberColumn("ET₀ (mm/day)", format="%.2f"),
                        "ET₀ (mm/month)": st.column_config.NumberColumn("ET₀ (mm/month)", format="%.1f")
                    }
                )
                
                # Show summary metrics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Avg ET₀", f"{df_converted['ET₀ (mm/day)'].mean():.2f} mm/day")
                with col2:
                    st.metric("Max ET₀", f"{df_converted['ET₀ (mm/day)'].max():.2f} mm/day")
                with col3:
                    st.metric("Annual ET₀", f"{df_converted['ET₀ (mm/month)'].sum():.0f} mm")
                with col4:
                    st.metric("Annual Rainfall", f"{df_converted['Rainfall (mm)'].sum():.0f} mm")
                
        except Exception as e:
            st.error(f"❌ Error reading AQUASTAT CSV: {e}")
            st.info("Please ensure your file has the correct AQUASTAT column format.")


def convert_aquastat_format(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Convert AQUASTAT format to our standard format.
    
    AQUASTAT columns -> Our columns:
    - Month -> Month (expanded to full name)
    - Tmp. max. -> T_max (°C)
    - Tmp. min. -> T_min (°C)
    - Rel. Hum. -> RH_mean (%)
    - Wind (2m) -> Wind Speed (m/s)
    - Sun shine -> Sunshine Hours (h) [converted from J/m²/day]
    - Prc. -> Rainfall (mm)
    - ETo -> ET₀ (mm/day) [converted from mm/month]
    """
    try:
        # Map month abbreviations to full names
        month_map = {
            'Jan': 'January', 'Feb': 'February', 'Mar': 'March', 'Apr': 'April',
            'May': 'May', 'Jun': 'June', 'Jul': 'July', 'Aug': 'August',
            'Sep': 'September', 'Oct': 'October', 'Nov': 'November', 'Dec': 'December'
        }
        
        # Days per month for ET₀ conversion
        days_map = {
            'January': 31, 'February': 28, 'March': 31, 'April': 30,
            'May': 31, 'June': 30, 'July': 31, 'August': 31,
            'September': 30, 'October': 31, 'November': 30, 'December': 31
        }
        
        # Flexible column matching (handle variations in column names)
        col_mapping = {}
        raw_cols = df_raw.columns.tolist()
        
        for col in raw_cols:
            col_lower = col.lower().strip()
            if 'month' in col_lower:
                col_mapping['Month'] = col
            elif 'max' in col_lower and 'tmp' in col_lower:
                col_mapping['T_max'] = col
            elif 'min' in col_lower and 'tmp' in col_lower:
                col_mapping['T_min'] = col
            elif 'mean' in col_lower and 'tmp' in col_lower:
                col_mapping['T_mean'] = col
            elif 'hum' in col_lower or 'rh' in col_lower:
                col_mapping['RH'] = col
            elif 'wind' in col_lower:
                col_mapping['Wind'] = col
            elif 'sun' in col_lower or 'shine' in col_lower:
                col_mapping['Sunshine'] = col
            elif 'prc' in col_lower or 'precip' in col_lower or 'rain' in col_lower:
                col_mapping['Rainfall'] = col
            elif 'eto' in col_lower or 'et0' in col_lower:
                col_mapping['ETo'] = col
        
        # Validate required columns
        required = ['Month', 'ETo']
        missing = [r for r in required if r not in col_mapping]
        if missing:
            st.error(f"Missing required columns: {missing}")
            st.info(f"Found columns: {raw_cols}")
            return None
        
        # Create converted dataframe
        df = pd.DataFrame()
        
        # Month - convert abbreviations to full names
        months_raw = df_raw[col_mapping['Month']].tolist()
        df['Month'] = [month_map.get(m.strip(), m) for m in months_raw]
        
        # Temperature columns
        if 'T_max' in col_mapping:
            df['T_max (°C)'] = pd.to_numeric(df_raw[col_mapping['T_max']], errors='coerce')
        elif 'T_mean' in col_mapping:
            df['T_max (°C)'] = pd.to_numeric(df_raw[col_mapping['T_mean']], errors='coerce') + 5
        else:
            df['T_max (°C)'] = 30.0
            
        if 'T_min' in col_mapping:
            df['T_min (°C)'] = pd.to_numeric(df_raw[col_mapping['T_min']], errors='coerce')
        elif 'T_mean' in col_mapping:
            df['T_min (°C)'] = pd.to_numeric(df_raw[col_mapping['T_mean']], errors='coerce') - 5
        else:
            df['T_min (°C)'] = 15.0
        
        # Humidity
        if 'RH' in col_mapping:
            df['RH_mean (%)'] = pd.to_numeric(df_raw[col_mapping['RH']], errors='coerce')
        else:
            df['RH_mean (%)'] = 60.0
        
        # Wind speed (already at 2m in AQUASTAT)
        if 'Wind' in col_mapping:
            df['Wind Speed (m/s)'] = pd.to_numeric(df_raw[col_mapping['Wind']], errors='coerce')
        else:
            df['Wind Speed (m/s)'] = 2.0
        
        # Sunshine - AQUASTAT gives J/m²/day, convert to approximate hours
        # Average solar constant ~1000 W/m² = 1000 J/m²/s
        # Daily sunshine hours ≈ Solar radiation (MJ/m²/day) / 2.5 (rough conversion)
        if 'Sunshine' in col_mapping:
            sunshine_raw = pd.to_numeric(df_raw[col_mapping['Sunshine']], errors='coerce')
            # If values are large (J/m²/day format like 20,000,000+)
            if sunshine_raw.mean() > 1000000:
                df['Sunshine Hours (h)'] = sunshine_raw / 2500000  # Rough J to hours
            else:
                df['Sunshine Hours (h)'] = sunshine_raw / 2.5  # MJ to hours
        else:
            df['Sunshine Hours (h)'] = 8.0
        
        # Rainfall (mm/month in AQUASTAT)
        if 'Rainfall' in col_mapping:
            df['Rainfall (mm)'] = pd.to_numeric(df_raw[col_mapping['Rainfall']], errors='coerce')
        else:
            df['Rainfall (mm)'] = 0.0
        
        # ET₀ - AQUASTAT provides mm/month, convert to mm/day
        eto_monthly = pd.to_numeric(df_raw[col_mapping['ETo']], errors='coerce')
        days_in_month = df['Month'].map(days_map)
        df['ET₀ (mm/day)'] = eto_monthly / days_in_month
        df['ET₀ (mm/month)'] = eto_monthly
        
        return df
        
    except Exception as e:
        st.error(f"Error converting AQUASTAT format: {e}")
        return None

def show_et0_calculation():
    """Calculate ET0 using FAO Penman-Monteith or display AQUASTAT ET₀"""
    st.markdown('<h2 class="sub-header">Reference Evapotranspiration (ET₀)</h2>', unsafe_allow_html=True)
    
    if 'climate_data' not in st.session_state.project_data or \
       'monthly_data' not in st.session_state.project_data.get('climate_data', {}):
        st.warning("⚠️ Please input climate data first.")
        return
    
    climate_data = st.session_state.project_data['climate_data']
    df = climate_data['monthly_data'].copy()
    latitude = climate_data.get('latitude', 0.0)
    altitude = st.session_state.project_data.get('altitude', 0.0)
    data_source = climate_data.get('data_source', 'Manual')
    has_eto = climate_data.get('has_eto', False)
    
    # Check if ET₀ is already available (AQUASTAT data)
    if has_eto and 'ET₀ (mm/day)' in df.columns:
        st.success("✅ **ET₀ values from AQUASTAT** - Pre-calculated reference evapotranspiration.")
        st.info("🌍 Data source: FAO AQUASTAT (no Penman-Monteith calculation needed)")
    else:
        st.info("📐 Calculating ET₀ using FAO Penman-Monteith equation...")
        
        # Calculate ET0 for each month
        et0_values = []
        
        for idx, row in df.iterrows():
            month_name = row['Month']
            month_num = ['January', 'February', 'March', 'April', 'May', 'June',
                         'July', 'August', 'September', 'October', 'November', 'December'].index(month_name) + 1
            
            et0 = calculate_et0_penman_monteith(
                t_max=row['T_max (°C)'],
                t_min=row['T_min (°C)'],
                rh_mean=row['RH_mean (%)'],
                wind_speed=row['Wind Speed (m/s)'],
                sunshine_hours=row['Sunshine Hours (h)'],
                latitude=latitude,
                altitude=altitude,
                month=month_num
            )
            et0_values.append(et0)
        
        df['ET₀ (mm/day)'] = et0_values
        df['ET₀ (mm/month)'] = df['ET₀ (mm/day)'] * df['Month'].map(get_days_in_month)
    
    # Display results
    st.dataframe(
        df,
        hide_index=True,
        width="stretch",
        column_config={
            "ET₀ (mm/day)": st.column_config.NumberColumn("ET₀ (mm/day)", format="%.2f"),
            "ET₀ (mm/month)": st.column_config.NumberColumn("ET₀ (mm/month)", format="%.1f")
        }
    )
    
    # Update climate data with ET0
    st.session_state.project_data['climate_data']['monthly_data'] = df
    
    # Visualization
    st.markdown("#### ET₀ Visualization")
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=df['Month'],
        y=df['ET₀ (mm/day)'],
        name='ET₀ (mm/day)',
        marker_color='lightblue'
    ))
    
    fig.update_layout(
        title="Monthly Reference Evapotranspiration",
        xaxis_title="Month",
        yaxis_title="ET₀ (mm/day)",
        template="plotly_white",
        height=400
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Summary statistics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Average ET₀", f"{df['ET₀ (mm/day)'].mean():.2f} mm/day")
    with col2:
        st.metric("Maximum ET₀", f"{df['ET₀ (mm/day)'].max():.2f} mm/day")
    with col3:
        st.metric("Minimum ET₀", f"{df['ET₀ (mm/day)'].min():.2f} mm/day")
    with col4:
        st.metric("Total (Season)", f"{df['ET₀ (mm/month)'].sum():.0f} mm")

def calculate_et0_penman_monteith(t_max, t_min, rh_mean, wind_speed, sunshine_hours, 
                                   latitude, altitude, month):
    """
    Calculate ET0 using FAO Penman-Monteith equation
    """
    # Mean temperature
    t_mean = (t_max + t_min) / 2
    
    # Atmospheric pressure (kPa)
    P = 101.3 * ((293 - 0.0065 * altitude) / 293) ** 5.26
    
    # Psychrometric constant (kPa/°C)
    gamma = 0.000665 * P
    
    # Saturation vapour pressure (kPa)
    e_tmax = 0.6108 * np.exp((17.27 * t_max) / (t_max + 237.3))
    e_tmin = 0.6108 * np.exp((17.27 * t_min) / (t_min + 237.3))
    es = (e_tmax + e_tmin) / 2
    
    # Actual vapour pressure (kPa)
    ea = es * (rh_mean / 100)
    
    # Slope of saturation vapour pressure curve (kPa/°C)
    delta = (4098 * es) / ((t_mean + 237.3) ** 2)
    
    # Extraterrestrial radiation (MJ/m²/day)
    Ra = calculate_extraterrestrial_radiation(latitude, month)
    
    # Solar radiation (MJ/m²/day) - estimated from sunshine hours
    N = calculate_daylight_hours(latitude, month)
    Rs = (0.25 + 0.50 * sunshine_hours / N) * Ra if N > 0 else Ra * 0.5
    
    # Net shortwave radiation (MJ/m²/day)
    alpha = 0.23  # albedo
    Rns = (1 - alpha) * Rs
    
    # Net longwave radiation (MJ/m²/day)
    stefan_boltzmann = 4.903e-9
    Rnl = stefan_boltzmann * (
        ((t_max + 273.16)**4 + (t_min + 273.16)**4) / 2
    ) * (0.34 - 0.14 * np.sqrt(ea)) * (1.35 * Rs / (0.75 * Ra) - 0.35)
    
    # Net radiation (MJ/m²/day)
    Rn = Rns - Rnl
    
    # Soil heat flux (MJ/m²/day) - negligible for daily calculations
    G = 0
    
    # Wind speed at 2m height (m/s)
    u2 = wind_speed
    
    # ET0 calculation (mm/day)
    numerator = 0.408 * delta * (Rn - G) + gamma * (900 / (t_mean + 273)) * u2 * (es - ea)
    denominator = delta + gamma * (1 + 0.34 * u2)
    
    ET0 = numerator / denominator
    
    return max(0, ET0)

def calculate_extraterrestrial_radiation(latitude, month):
    """Calculate extraterrestrial radiation Ra"""
    # Solar constant
    Gsc = 0.0820  # MJ/m²/min
    
    # Day of year (middle of month)
    doy = sum(get_days_in_month(m) for m in ['January', 'February', 'March', 'April', 'May', 'June',
                                               'July', 'August', 'September', 'October', 'November', 'December'][:month-1]) + 15
    
    # Inverse relative distance Earth-Sun
    dr = 1 + 0.033 * np.cos(2 * np.pi * doy / 365)
    
    # Solar declination
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    
    # Latitude in radians
    phi = latitude * np.pi / 180
    
    # Sunset hour angle
    ws = np.arccos(-np.tan(phi) * np.tan(delta))
    
    # Extraterrestrial radiation
    Ra = (24 * 60 / np.pi) * Gsc * dr * (
        ws * np.sin(phi) * np.sin(delta) + 
        np.cos(phi) * np.cos(delta) * np.sin(ws)
    )
    
    return Ra

def calculate_daylight_hours(latitude, month):
    """Calculate maximum daylight hours"""
    doy = sum(get_days_in_month(m) for m in ['January', 'February', 'March', 'April', 'May', 'June',
                                               'July', 'August', 'September', 'October', 'November', 'December'][:month-1]) + 15
    
    delta = 0.409 * np.sin(2 * np.pi * doy / 365 - 1.39)
    phi = latitude * np.pi / 180
    ws = np.arccos(-np.tan(phi) * np.tan(delta))
    
    N = (24 / np.pi) * ws
    return N

def get_days_in_month(month_name):
    """Return number of days in month"""
    days_dict = {
        'January': 31, 'February': 28, 'March': 31, 'April': 30,
        'May': 31, 'June': 30, 'July': 31, 'August': 31,
        'September': 30, 'October': 31, 'November': 30, 'December': 31
    }
    return days_dict.get(month_name, 30)

def show_crop_coefficients():
    """Show crop coefficient selection and adjustment"""
    st.markdown('<h2 class="sub-header">Crop Coefficients (Kc)</h2>', unsafe_allow_html=True)
    
    crop_type = st.session_state.project_data.get('crop_type', '')
    
    if not crop_type:
        st.warning("⚠️ Please select a crop type in the Home page.")
        return
    
    st.info(f"Selected Crop: **{crop_type}**")
    
    # Crop coefficient database (FAO-56)
    kc_database = get_kc_database()
    
    if crop_type in kc_database:
        kc_values = kc_database[crop_type]
    else:
        kc_values = {'Kc_ini': 0.5, 'Kc_mid': 1.0, 'Kc_end': 0.8}
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Growth Stage Lengths (days)")
        l_ini = st.number_input("Initial Stage", min_value=1, value=kc_values.get('L_ini', 20), step=1)
        l_dev = st.number_input("Development Stage", min_value=1, value=kc_values.get('L_dev', 30), step=1)
        l_mid = st.number_input("Mid-season Stage", min_value=1, value=kc_values.get('L_mid', 40), step=1)
        l_late = st.number_input("Late Season Stage", min_value=1, value=kc_values.get('L_late', 30), step=1)
        
        total_season = l_ini + l_dev + l_mid + l_late
        st.metric("Total Growing Season", f"{total_season} days")
    
    with col2:
        st.markdown("#### Crop Coefficients")
        kc_ini = st.number_input(
            "Kc Initial",
            min_value=0.1,
            max_value=1.5,
            value=float(kc_values['Kc_ini']),
            step=0.05,
            help="Crop coefficient during initial stage"
        )
        
        kc_mid = st.number_input(
            "Kc Mid-season",
            min_value=0.1,
            max_value=1.5,
            value=float(kc_values['Kc_mid']),
            step=0.05,
            help="Crop coefficient during mid-season"
        )
        
        kc_end = st.number_input(
            "Kc End",
            min_value=0.1,
            max_value=1.5,
            value=float(kc_values['Kc_end']),
            step=0.05,
            help="Crop coefficient at end of season"
        )
    
    # Generate Kc curve
    days = list(range(1, total_season + 1))
    kc_curve = generate_kc_curve(l_ini, l_dev, l_mid, l_late, kc_ini, kc_mid, kc_end)
    
    # Visualization
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=days,
        y=kc_curve,
        mode='lines',
        name='Kc',
        line=dict(color='green', width=2),
        fill='tozeroy'
    ))
    
    # Add stage markers
    stage_ends = [l_ini, l_ini + l_dev, l_ini + l_dev + l_mid, total_season]
    stage_names = ['Initial', 'Development', 'Mid-season', 'Late season']
    colors = ['blue', 'orange', 'green', 'red']
    
    for i, (end, name, color) in enumerate(zip(stage_ends, stage_names, colors)):
        fig.add_vline(x=end, line_dash="dash", line_color=color, annotation_text=name)
    
    fig.update_layout(
        title="Crop Coefficient Curve",
        xaxis_title="Days after Planting",
        yaxis_title="Crop Coefficient (Kc)",
        template="plotly_white",
        height=400,
        yaxis_range=[0, max(kc_curve) * 1.1]
    )
    
    st.plotly_chart(fig, width="stretch")
    
    # Save crop parameters
    if st.button("Save Crop Parameters", type="primary"):
        st.session_state.project_data['crop_parameters'] = {
            'L_ini': l_ini,
            'L_dev': l_dev,
            'L_mid': l_mid,
            'L_late': l_late,
            'Kc_ini': kc_ini,
            'Kc_mid': kc_mid,
            'Kc_end': kc_end,
            'total_season': total_season,
            'kc_curve': kc_curve
        }
        st.success("✅ Crop parameters saved successfully!")

def get_kc_database():
    """Database of crop coefficients for common crops"""
    return {
        'Wheat': {'Kc_ini': 0.3, 'Kc_mid': 1.15, 'Kc_end': 0.4, 'L_ini': 15, 'L_dev': 30, 'L_mid': 65, 'L_late': 40},
        'Maize': {'Kc_ini': 0.3, 'Kc_mid': 1.20, 'Kc_end': 0.6, 'L_ini': 20, 'L_dev': 35, 'L_mid': 40, 'L_late': 30},
        'Barley': {'Kc_ini': 0.3, 'Kc_mid': 1.15, 'Kc_end': 0.4, 'L_ini': 15, 'L_dev': 25, 'L_mid': 50, 'L_late': 30},
        'Potatoes': {'Kc_ini': 0.5, 'Kc_mid': 1.15, 'Kc_end': 0.75, 'L_ini': 25, 'L_dev': 30, 'L_mid': 45, 'L_late': 25},
        'Vegetables': {'Kc_ini': 0.5, 'Kc_mid': 1.05, 'Kc_end': 0.95, 'L_ini': 20, 'L_dev': 30, 'L_mid': 35, 'L_late': 15},
        'Citrus': {'Kc_ini': 0.7, 'Kc_mid': 0.65, 'Kc_end': 0.7, 'L_ini': 60, 'L_dev': 90, 'L_mid': 120, 'L_late': 95},
        'Grapes': {'Kc_ini': 0.3, 'Kc_mid': 0.85, 'Kc_end': 0.45, 'L_ini': 20, 'L_dev': 40, 'L_mid': 120, 'L_late': 60},
        'Apples': {'Kc_ini': 0.45, 'Kc_mid': 0.95, 'Kc_end': 0.7, 'L_ini': 20, 'L_dev': 50, 'L_mid': 130, 'L_late': 40},
        'Alfalfa': {'Kc_ini': 0.4, 'Kc_mid': 1.20, 'Kc_end': 1.15, 'L_ini': 10, 'L_dev': 20, 'L_mid': 20, 'L_late': 10},
        'Grass/Pasture': {'Kc_ini': 0.9, 'Kc_mid': 0.95, 'Kc_end': 0.95, 'L_ini': 10, 'L_dev': 20, 'L_mid': 90, 'L_late': 60}
    }

def generate_kc_curve(l_ini, l_dev, l_mid, l_late, kc_ini, kc_mid, kc_end):
    """Generate Kc curve for entire growing season"""
    kc_curve = []
    
    # Initial stage
    kc_curve.extend([kc_ini] * l_ini)
    
    # Development stage (linear increase)
    for i in range(l_dev):
        kc = kc_ini + (kc_mid - kc_ini) * (i / l_dev)
        kc_curve.append(kc)
    
    # Mid-season stage
    kc_curve.extend([kc_mid] * l_mid)
    
    # Late season stage (linear decrease)
    for i in range(l_late):
        kc = kc_mid - (kc_mid - kc_end) * (i / l_late)
        kc_curve.append(kc)
    
    return kc_curve

def show_irrigation_requirements():
    """Calculate irrigation requirements"""
    st.markdown('<h2 class="sub-header">Irrigation Requirements</h2>', unsafe_allow_html=True)
    
    # Check prerequisites
    if 'climate_data' not in st.session_state.project_data or \
       'monthly_data' not in st.session_state.project_data.get('climate_data', {}):
        st.warning("⚠️ Please enter climate data first.")
        return
    
    monthly_data = st.session_state.project_data['climate_data']['monthly_data']
    
    if 'ET₀ (mm/day)' not in monthly_data.columns:
        st.warning("⚠️ Please calculate ET₀ first.")
        return
    
    if 'crop_parameters' not in st.session_state.project_data:
        st.warning("⚠️ Please set crop coefficients first.")
        return
    
    crop_params = st.session_state.project_data['crop_parameters']
    
    if 'kc_curve' not in crop_params:
        st.warning("⚠️ Please generate Kc curve in the Crop Coefficients tab first.")
        return
    
    # Get data
    climate_df = st.session_state.project_data['climate_data']['monthly_data']
    crop_params = st.session_state.project_data['crop_parameters']
    soil_type = st.session_state.project_data.get('soil_type', 'Loam')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Soil Water Parameters")
        
        # Soil water holding capacity
        soil_whc = get_soil_water_capacity(soil_type)
        
        fc = st.number_input(
            "Field Capacity (mm/m)",
            min_value=50.0,
            max_value=500.0,
            value=float(soil_whc['FC']),
            step=10.0,
            help="Soil water content at field capacity"
        )
        
        pwp = st.number_input(
            "Permanent Wilting Point (mm/m)",
            min_value=10.0,
            max_value=300.0,
            value=float(soil_whc['PWP']),
            step=10.0,
            help="Soil water content at wilting point"
        )
        
        taw = fc - pwp
        st.metric("Total Available Water (TAW)", f"{taw:.1f} mm/m")
        
        root_depth = st.number_input(
            "Effective Root Depth (m)",
            min_value=0.1,
            max_value=3.0,
            value=0.6,
            step=0.1
        )
        
        raw_fraction = st.slider(
            "Readily Available Water (fraction of TAW)",
            min_value=0.1,
            max_value=0.8,
            value=0.5,
            step=0.05,
            help="Fraction of TAW that can be depleted without stress"
        )
        
        raw = taw * raw_fraction * root_depth
        st.metric("RAW", f"{raw:.1f} mm")
    
    with col2:
        st.markdown("#### Irrigation System Parameters")
        
        application_efficiency = st.slider(
            "Application Efficiency (%)",
            min_value=50,
            max_value=95,
            value=75,
            step=5,
            help="Sprinkler system application efficiency"
        )
        
        peak_et_month = climate_df.loc[climate_df['ET₀ (mm/day)'].idxmax(), 'Month']
        st.info(f"Peak ET₀ month: {peak_et_month}")
        
        design_et = climate_df['ET₀ (mm/day)'].max()
        st.metric("Design ET₀", f"{design_et:.2f} mm/day")
        
        management_factor = st.slider(
            "Management Allowed Depletion (MAD) %",
            min_value=20,
            max_value=80,
            value=50,
            step=5,
            help="Management allowed depletion as % of TAW"
        )
    
    # Calculate irrigation requirements
    st.markdown("---")
    st.markdown("#### Calculated Irrigation Requirements")
    
    # Peak ETc
    peak_kc = max(crop_params['kc_curve'])
    peak_etc = design_et * peak_kc
    
    # Net irrigation depth
    net_depth = (taw * management_factor / 100) * root_depth
    
    # Gross irrigation depth
    gross_depth = net_depth / (application_efficiency / 100)
    
    # Irrigation interval
    irrigation_interval_raw = net_depth / peak_etc
    
    # Round irrigation interval with custom logic:
    # < 0.5 rounds down, > 0.5 rounds up, = 0.5 keeps .5
    decimal_part = irrigation_interval_raw - int(irrigation_interval_raw)
    if decimal_part < 0.5:
        irrigation_interval = int(irrigation_interval_raw)
    elif decimal_part > 0.5:
        irrigation_interval = int(irrigation_interval_raw) + 1
    else:  # decimal_part == 0.5
        irrigation_interval = int(irrigation_interval_raw) + 0.5
    
    # Peak irrigation requirement (gross)
    peak_irrigation_rate = gross_depth / irrigation_interval
    
    # Display results
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Peak ETc", f"{peak_etc:.2f} mm/day")
    with col2:
        st.metric("Net Irrigation Depth", f"{net_depth:.1f} mm")
    with col3:
        st.metric("Gross Irrigation Depth", f"{gross_depth:.1f} mm")
    with col4:
        # Display with appropriate decimal places
        if irrigation_interval == int(irrigation_interval):
            st.metric("Irrigation Interval", f"{int(irrigation_interval)} days")
        else:
            st.metric("Irrigation Interval", f"{irrigation_interval:.1f} days")
    
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Peak Irrigation Rate", f"{peak_irrigation_rate:.2f} mm/day")
    with col2:
        area = st.session_state.project_data.get('area', 0)
        if area > 0:
            daily_volume = peak_irrigation_rate * area * 10  # m³/day
            st.metric("Daily Water Volume", f"{daily_volume:.0f} m³/day")
        else:
            st.metric("Daily Water Volume", "Set area first")
    
    # Save irrigation requirements
    if st.button("Save Irrigation Requirements", type="primary"):
        st.session_state.project_data['irrigation_requirements'] = {
            'FC': fc,
            'PWP': pwp,
            'TAW': taw,
            'root_depth': root_depth,
            'RAW': raw,
            'raw_fraction': raw_fraction,
            'application_efficiency': application_efficiency,
            'management_factor': management_factor,
            'peak_etc': peak_etc,
            'net_depth': net_depth,
            'gross_depth': gross_depth,
            'irrigation_interval': irrigation_interval,
            'peak_irrigation_rate': peak_irrigation_rate,
            'daily_volume': daily_volume if area > 0 else 0
        }
        st.success("✅ Irrigation requirements saved successfully!")

def get_soil_water_capacity(soil_type):
    """Get typical soil water holding capacity"""
    soil_data = {
        'Sandy': {'FC': 120, 'PWP': 40},
        'Loamy Sand': {'FC': 150, 'PWP': 60},
        'Sandy Loam': {'FC': 200, 'PWP': 80},
        'Loam': {'FC': 250, 'PWP': 110},
        'Silty Loam': {'FC': 280, 'PWP': 130},
        'Silt': {'FC': 300, 'PWP': 140},
        'Clay Loam': {'FC': 320, 'PWP': 180},
        'Clay': {'FC': 360, 'PWP': 220}
    }
    return soil_data.get(soil_type, {'FC': 250, 'PWP': 110})
