"""
Sprinkler Irrigation Design - User Manual & Documentation
=========================================================
Comprehensive technical documentation for professional irrigation engineers.
Based on FAO Irrigation Manual standards and South African design practices.

Version: 2.0 Professional Edition
"""

import streamlit as st


def show():
    """Main documentation page with tabbed navigation."""
    
    st.markdown('<h1 class="main-header">📖 User Manual & Technical Documentation</h1>', unsafe_allow_html=True)
    
    st.markdown("""
    <div class="info-box">
    <b>Sprinkler Irrigation Design Application - Professional Edition</b><br>
    Complete reference guide for designing solid-set sprinkler irrigation systems.
    This manual covers the full workflow from site assessment to pump selection.
    </div>
    """, unsafe_allow_html=True)
    
    # Main navigation tabs
    tabs = st.tabs([
        "🚀 Quick Start",
        "📐 Module Guide", 
        "🔧 Data Entry",
        "📸 Visual Guide",
        "📊 Technical Reference"
    ])
    
    with tabs[0]:
        show_quick_start()
    
    with tabs[1]:
        show_module_walkthroughs()
    
    with tabs[2]:
        show_data_entry_guide()
    
    with tabs[3]:
        show_visual_guide()
    
    with tabs[4]:
        show_technical_appendix()


def show_quick_start():
    """Project overview and quick start checklist."""
    
    st.markdown("## 🚀 Project Overview & Quick Start")
    
    st.markdown("""
    ### Intended Use
    
    This application is designed for **professional irrigation engineers** to design 
    complete solid-set sprinkler irrigation systems. It follows the methodology outlined in:
    
    - **FAO Irrigation and Drainage Paper No. 24** - Crop Water Requirements
    - **FAO Irrigation Manual** - Planning, Development and Evaluation of Irrigated Agriculture
    - **South African Irrigation Design Manual** - Local standards and practices
    
    The software calculates crop water requirements, selects appropriate sprinklers, 
    designs pipe networks, and sizes pumps—all with professional-grade accuracy.
    """)
    
    st.markdown("---")
    
    # Quick Start Checklist
    st.markdown("### ✅ Quick Start Checklist")
    
    st.markdown("""
    Follow this workflow to complete a design from start to finish:
    """)
    
    checklist_data = [
        ("1", "🏠 Home", "Project Setup", "Enter project name, location, crop type, soil type, and field area", "5 min"),
        ("2", "🌾 Crop Water", "Climate & ET₀", "Input climate data and calculate crop water requirements", "15 min"),
        ("3", "💧 Sprinkler", "Selection & Spacing", "Select sprinkler model and design spacing layout", "10 min"),
        ("4", "📋 Operational", "Field Subdivision", "Divide field into subplots and plan irrigation schedule", "10 min"),
        ("5", "🔵 Network Layout", "CAD Drawing", "Draw pipe network using interactive CAD tools", "20 min"),
        ("6", "🔧 Pipe Design", "Hydraulic Sizing", "Size all pipes (laterals, submains, mainline)", "15 min"),
        ("7", "💎 Hydraulic", "Pressure Analysis", "Calculate friction losses and pressure requirements", "10 min"),
        ("8", "⚡ Pump", "Selection", "Select pump based on flow and head requirements", "10 min"),
        ("9", "💰 Cost", "Estimation", "Generate bill of quantities and cost estimate", "5 min"),
        ("10", "📄 Reports", "Export", "Generate professional PDF reports", "5 min"),
    ]
    
    # Create styled checklist
    st.markdown("""
    | Step | Module | Task | Description | Est. Time |
    |:----:|:------:|:-----|:------------|:---------:|
    """ + "\n".join([f"| {row[0]} | {row[1]} | **{row[2]}** | {row[3]} | {row[4]} |" for row in checklist_data]))
    
    st.markdown("---")
    
    # Pro Tips callout
    st.markdown("""
    > 💡 **Pro Tip: Save Your Work Frequently**
    > 
    > Click the **Save** buttons at the bottom of each module to preserve your data.
    > The application maintains session state, but saving ensures your design persists
    > across sessions.
    """)
    
    st.markdown("""
    > ⚠️ **Important: Complete Modules in Order**
    > 
    > Each module depends on data from previous modules. For example, Pipe Network Design
    > requires sprinkler selection and operational design data to calculate flows correctly.
    """)
    
    st.markdown("---")
    
    # System Requirements
    st.markdown("### 💻 System Requirements")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **Minimum Requirements:**
        - Modern web browser (Chrome, Firefox, Edge)
        - Screen resolution: 1366 × 768
        - Stable internet connection
        """)
    
    with col2:
        st.markdown("""
        **Recommended:**
        - Screen resolution: 1920 × 1080 or higher
        - Mouse with scroll wheel (for CAD tools)
        - PDF viewer for report exports
        """)


def show_module_walkthroughs():
    """Detailed walkthroughs for each module."""
    
    st.markdown("## 📐 Detailed Module Walkthroughs")
    
    # Sub-navigation for modules
    module_tabs = st.tabs([
        "Crop Water",
        "Sprinkler Selection",
        "Operational Design",
        "Pipe Network Layout",
        "Pipe Network Design",
        "Hydraulic Design",
        "Pump Selection"
    ])
    
    # =========================================================================
    # CROP WATER REQUIREMENTS
    # =========================================================================
    with module_tabs[0]:
        st.markdown("### 🌾 Crop Water Requirements")
        
        st.markdown("""
        #### Engineering Logic
        
        This module calculates the **crop water requirement (ETc)** using the FAO Penman-Monteith 
        equation and crop coefficient approach:
        
        $$ET_c = K_c \\times ET_0$$
        
        Where:
        - $ET_c$ = Crop evapotranspiration (mm/day)
        - $K_c$ = Crop coefficient (dimensionless)
        - $ET_0$ = Reference evapotranspiration (mm/day)
        
        The **FAO Penman-Monteith equation** for $ET_0$:
        
        $$ET_0 = \\frac{0.408 \\Delta (R_n - G) + \\gamma \\frac{900}{T+273} u_2 (e_s - e_a)}{\\Delta + \\gamma (1 + 0.34 u_2)}$$
        
        #### Required Inputs
        
        | Parameter | Unit | Description | Typical Range |
        |:----------|:-----|:------------|:--------------|
        | Latitude | degrees | Site location (negative for S. hemisphere) | -35 to 35 |
        | Altitude | m | Elevation above sea level | 0 - 3000 |
        | T_max | °C | Maximum daily temperature | 15 - 45 |
        | T_min | °C | Minimum daily temperature | 0 - 25 |
        | RH_mean | % | Mean relative humidity | 30 - 90 |
        | Wind Speed | m/s | Wind speed at 2m height | 0.5 - 5 |
        | Sunshine Hours | hours | Daily bright sunshine | 4 - 12 |
        | Rainfall | mm | Monthly precipitation | 0 - 300 |
        
        #### Expected Outputs
        
        - **Monthly ET₀ values** (mm/month)
        - **Peak ETc** for design month (mm/day)
        - **Net Irrigation Requirement (NIR)** accounting for effective rainfall
        - **Gross Irrigation Requirement (GIR)** with efficiency factors
        - **Irrigation interval** in days
        """)
        
        st.markdown("""
        > 💡 **Pro Tip: AQUASTAT Data**
        > 
        > You can upload climate data directly from FAO AQUASTAT in CSV format.
        > This includes pre-calculated ET₀ values validated by FAO methodology.
        """)
    
    # =========================================================================
    # SPRINKLER SELECTION
    # =========================================================================
    with module_tabs[1]:
        st.markdown("### 💧 Sprinkler Selection & Spacing")
        
        st.markdown("""
        #### Engineering Logic
        
        Sprinkler selection is based on matching:
        1. **Operating pressure** to available system pressure
        2. **Flow rate** to soil infiltration capacity
        3. **Wetted diameter** to desired coverage
        4. **Application rate** to prevent runoff
        
        ##### Spacing Design
        
        Spacing is expressed as a **ratio of wetted diameter**:
        
        | Wind Condition | Wind Speed | Recommended Spacing Ratio |
        |:---------------|:-----------|:--------------------------|
        | Low wind | < 2 m/s | 65% of diameter |
        | Moderate wind | 2-4 m/s | 55% of diameter |
        | High wind | > 4 m/s | 45% of diameter |
        
        ##### Application Rate Calculation
        
        The **actual application rate** is calculated from your specific spacing:
        
        $$I = \\frac{Q}{S_l \\times S_b}$$
        
        Where:
        - $I$ = Application rate (mm/hr)
        - $Q$ = Sprinkler flow rate (l/hr)
        - $S_l$ = Spacing along lateral (m)
        - $S_b$ = Spacing between laterals (m)
        
        **Critical Check:** Application rate must be ≤ soil infiltration rate!
        
        ##### Uniformity Analysis
        
        **Christiansen Uniformity Coefficient (CU):**
        
        $$CU = 100 \\left(1 - \\frac{\\sum|X_i - \\bar{X}|}{n \\cdot \\bar{X}}\\right)$$
        
        | CU Range | Rating | Acceptable For |
        |:---------|:-------|:---------------|
        | > 90% | Excellent | High-value crops |
        | 84-90% | Good | Most field crops |
        | 75-84% | Fair | Pastures, tolerant crops |
        | < 75% | Poor | Redesign recommended |
        
        #### Required Inputs
        
        | Parameter | Unit | Description |
        |:----------|:-----|:------------|
        | Sprinkler Category | - | Low/Medium/High Pressure |
        | Sprinkler Type | - | Impact, Rotor, Spray, Rotator |
        | Model Selection | - | From manufacturer database |
        | Wind Speed | m/s | Average during irrigation |
        | Spacing Along | m | Distance between sprinklers |
        | Spacing Between | m | Distance between laterals |
        
        #### Expected Outputs
        
        - Selected sprinkler specifications (pressure, flow, diameter)
        - Spacing ratios and adequacy check
        - Sprinklers per hectare
        - Actual application rate vs. soil infiltration
        - Wind-adjusted uniformity coefficient
        """)
        
        # Screenshot placeholder
        st.markdown("""
        ---
        📸 **IMAGE PLACEHOLDER: [Sprinkler Selection Interface]**
        
        *Instructions for user: Capture the Sprinkler Selection tab showing:*
        - *The sprinkler category dropdown*
        - *The available models table*
        - *The "Selected Sprinkler Specifications" metrics*
        - *Annotate the "Select This Sprinkler" button with a red box*
        ---
        """)
    
    # =========================================================================
    # OPERATIONAL DESIGN
    # =========================================================================
    with module_tabs[2]:
        st.markdown("### 📋 Operational Design")
        
        st.markdown("""
        #### Engineering Logic
        
        This module subdivides the field into manageable **subplots** (typically ~1 ha each)
        and creates an **irrigation schedule** based on:
        
        1. Available water discharge (m³/hr)
        2. Operating hours per day
        3. Irrigation interval (days)
        4. Gross irrigation requirement (mm)
        
        ##### Subplot Sizing
        
        Standard subplot dimensions: **125m × 85m ≈ 1.06 ha**
        
        This standard allows:
        - Consistent sprinkler line lengths
        - Standardized valve coverage
        - Efficient pipe sizing
        
        ##### Irrigation Scheduling
        
        The number of irrigation days required:
        
        $$N_{days} = \\frac{\\text{Total Subplots}}{\\text{Subplots per Day}}$$
        
        Where subplots per day is limited by:
        
        $$\\text{Subplots/Day} = \\frac{Q_{available} \\times T_{operating}}{V_{subplot}}$$
        
        #### Required Inputs
        
        | Parameter | Unit | Description |
        |:----------|:-----|:------------|
        | Total Area | ha | Field area to irrigate |
        | Field Length | m | Length dimension |
        | Field Width | m | Width dimension |
        | Available Discharge | m³/hr | Water source capacity |
        | Operating Hours | hr/day | Irrigation window |
        | Irrigation Interval | days | Between irrigation events |
        
        #### Expected Outputs
        
        - Number of subplots (rows × columns)
        - Subplot dimensions and numbering
        - Irrigation days required
        - Subplots assigned to each day
        - Operating schedule matrix
        """)
    
    # =========================================================================
    # PIPE NETWORK LAYOUT
    # =========================================================================
    with module_tabs[3]:
        st.markdown("### 🔵 Pipe Network Layout (CAD Tools)")
        
        st.markdown("""
        #### Overview
        
        This module provides **professional CAD-style drawing tools** for creating 
        the pipe network layout. The interface mimics engineering CAD software with:
        
        - Interactive canvas with grid overlay
        - Node snapping for precise alignment
        - Multiple pipe type layers (mainline, submain, lateral)
        - Real-time measurements and annotations
        
        #### Drawing Tools
        
        | Tool | Color | Purpose |
        |:-----|:------|:--------|
        | 🔴 Mainline | Red | Main supply pipe from pump |
        | 🟠 Submain | Orange | Branch lines from mainline |
        | 🟢 Lateral | Green | Sprinkler lines from submains |
        | 🔵 Valve | Blue markers | Control valves at junctions |
        | ⬜ Field Boundary | Gray | Field perimeter outline |
        
        #### CAD Features
        
        ##### Grid Snapping
        - **Grid sizes:** 5m, 10m, 25m, 50m
        - Ensures pipe endpoints align to grid
        - Creates clean, professional drawings
        
        ##### Angle Constraints
        - Snap to angles: 15°, 30°, 45°, 90°
        - Creates perfectly horizontal, vertical, or diagonal lines
        - Essential for orthogonal pipe layouts
        
        ##### Length Constraints
        - Fix pipe segments to exact lengths
        - Useful for standardized pipe sections
        - Enter target length in meters
        
        ##### Real-Time Measurements
        - Length displayed on each segment
        - Angle indication for non-orthogonal lines
        - Live feedback during drawing
        
        #### Drawing Workflow
        
        1. **Set Drawing Mode** - Select pipe type (Mainline/Submain/Lateral)
        2. **Enable Snapping** - Turn on grid snap for precision
        3. **Click Points** - Click to place pipe vertices
        4. **Complete Segment** - Double-click or press Enter to finish
        5. **Add Valves** - Auto-place at grid intersections or manual placement
        6. **Save Layout** - Click "Save Network Layout" to preserve
        """)
        
        # Screenshot placeholder
        st.markdown("""
        ---
        📸 **IMAGE PLACEHOLDER: [Main Design Canvas]**
        
        *Instructions for user: Capture the main canvas with a sample pipe grid showing:*
        - *The interactive drawing area with grid overlay*
        - *A mainline (red) connected to submains (orange)*
        - *Laterals (green) branching from submains*
        - *Valve markers at intersections*
        - *Draw a red box around the "Drawing Mode" selector*
        - *Draw a blue box around the "Grid Snap" controls*
        ---
        """)
        
        st.markdown("""
        > 💡 **Pro Tip: Node Snapping**
        > 
        > Enable "Intersection Snap" to automatically snap to existing pipe intersections.
        > This ensures valves are placed exactly where pipes meet.
        """)
    
    # =========================================================================
    # PIPE NETWORK DESIGN
    # =========================================================================
    with module_tabs[4]:
        st.markdown("### 🔧 Pipe Network Design (Hydraulic Sizing)")
        
        st.markdown("""
        #### Engineering Logic
        
        Pipe sizing uses the **Hazen-Williams equation** for friction loss:
        
        $$h_f = 10.67 \\times L \\times \\frac{Q^{1.852}}{C^{1.852} \\times D^{4.87}}$$
        
        Where:
        - $h_f$ = Friction head loss (m)
        - $L$ = Pipe length (m)
        - $Q$ = Flow rate (m³/s)
        - $C$ = Hazen-Williams coefficient (130 for PVC)
        - $D$ = Internal pipe diameter (m)
        
        ##### Christiansen F-Factor
        
        For pipes with multiple outlets (laterals), the friction loss is reduced:
        
        $$F = \\frac{1}{m+1} + \\frac{1}{2N} + \\frac{\\sqrt{m-1}}{6N^2}$$
        
        Where:
        - $F$ = Reduction factor
        - $m$ = 1.852 (Hazen-Williams exponent)
        - $N$ = Number of outlets
        
        ##### Design Criteria
        
        | Parameter | Limit | Reason |
        |:----------|:------|:-------|
        | Velocity | 0.3 - 2.0 m/s | Avoid sedimentation/water hammer |
        | Friction Loss | < 20% of operating pressure | Maintain uniform pressure |
        | Pressure Variation | < 20% along lateral | Ensure uniform application |
        
        #### Pipe Sizing Tabs
        
        **Sprinkler Line Design:**
        - Connects sprinklers on a single lateral
        - Typically smallest pipes (20-40mm)
        - Critical for pressure uniformity
        
        **Lateral Design:**
        - Connects multiple sprinkler lines
        - Medium pipes (50-90mm)
        - F-factor applied for multiple outlets
        
        **Submain Design:**
        - Connects laterals to mainline
        - Larger pipes (90-160mm)
        - Flow varies by valve operation schedule
        
        **Mainline Design:**
        - Main supply from pump
        - Largest pipes (160-315mm)
        - Sized for maximum daily flow
        
        #### Required Inputs
        
        | Parameter | Unit | Description |
        |:----------|:-----|:------------|
        | Pipe Length | m | Total segment length |
        | Number of Outlets | - | Sprinklers or connections |
        | Flow Rate | m³/h | Water demand |
        | Pipe Material | - | PVC, HDPE, Steel |
        | C-Value | - | Roughness coefficient |
        
        #### Expected Outputs
        
        - Recommended pipe diameter (mm)
        - Flow velocity (m/s)
        - Friction loss (m)
        - Pressure at each point
        - Bill of quantities (pipe lengths by size)
        """)
        
        st.markdown("""
        > ⚠️ **Warning: Velocity Check**
        > 
        > If velocity exceeds **2.0 m/s**, the pipe is undersized and risks water hammer.
        > If velocity is below **0.3 m/s**, the pipe is oversized and sediment may accumulate.
        """)
    
    # =========================================================================
    # HYDRAULIC DESIGN
    # =========================================================================
    with module_tabs[5]:
        st.markdown("### 💎 Hydraulic Design")
        
        st.markdown("""
        #### Engineering Logic
        
        The hydraulic design module calculates the **system pressure balance**:
        
        $$P_r = P_s - (P_o + P_{ls})$$
        
        Where:
        - $P_r$ = Pressure remaining (surplus or deficit)
        - $P_s$ = Static pressure available at site
        - $P_o$ = Operating pressure for sprinklers
        - $P_{ls}$ = Total system pressure losses
        
        ##### Pressure Components
        
        | Component | Symbol | Description |
        |:----------|:-------|:------------|
        | Sprinkler Operating | $P_o$ | Pressure at nozzle |
        | Sprinkler Line Loss | $h_{sp}$ | Friction in riser pipes |
        | Lateral Line Loss | $h_{lat}$ | Friction in lateral pipes |
        | Submain Loss | $h_{sub}$ | Friction in submain pipes |
        | Mainline Loss | $h_{main}$ | Friction in mainline |
        | Fittings Loss | 10% | Standard allowance |
        | Backflow Unit | Fixed | Typically 0.29 bar |
        | Water Meter | Fixed | Typically 0.68 bar |
        | Elevation | $\\pm$ | Based on terrain |
        
        ##### Conversion Factors
        
        | From | To | Factor |
        |:-----|:---|:-------|
        | bar | kPa | × 100 |
        | bar | m head | × 10.197 |
        | kPa | m head | × 0.10197 |
        | psi | kPa | × 6.895 |
        
        #### System Feasibility
        
        **If $P_r ≥ 0$:** ✅ System is feasible with available pressure
        
        **If $P_r < 0$:** ❌ Pump required to provide additional head
        
        #### Required Inputs
        
        | Parameter | Unit | Description |
        |:----------|:-----|:------------|
        | Static Pressure | bar | Available site pressure |
        | Backflow Loss | bar | Backflow preventer |
        | Water Meter Loss | bar | Meter head loss |
        | Elevation Rise | bar | Head loss from elevation |
        | Elevation Drop | bar | Head gain from drop |
        
        #### Expected Outputs
        
        - Pressure requirements table (bar and m)
        - Total system head (m)
        - Pressure remaining calculation
        - Pump requirement (if needed)
        - Head distribution pie chart
        """)
        
        # Screenshot placeholder
        st.markdown("""
        ---
        📸 **IMAGE PLACEHOLDER: [Hydraulic Results Dashboard]**
        
        *Instructions for user: Capture the Pressure Requirements tab showing:*
        - *The complete pressure summary table*
        - *The result box (green for feasible, red for pump required)*
        - *Draw a red box around the "Pressure Loss" column*
        - *Draw a blue circle around the "Pr" (Pressure remaining) value*
        - *Highlight the "Critical Path" indicator if visible*
        ---
        """)
    
    # =========================================================================
    # PUMP SELECTION
    # =========================================================================
    with module_tabs[6]:
        st.markdown("### ⚡ Pump Selection")
        
        st.markdown("""
        #### Engineering Logic
        
        Pump selection matches the **duty point** (required flow and head) to 
        pump performance curves using polynomial regression:
        
        ##### Head Curve
        $$H = a + bQ + cQ^2$$
        
        ##### Efficiency Curve
        $$\\eta = d + eQ + fQ^2$$
        
        ##### Power Calculation
        $$P_{kW} = \\frac{Q \\times H}{367 \\times \\eta}$$
        
        Where:
        - $H$ = Head (m)
        - $Q$ = Flow rate (m³/h)
        - $\\eta$ = Efficiency (decimal)
        - $P$ = Power (kW)
        
        ##### Selection Criteria
        
        | Parameter | Optimal Range | Reason |
        |:----------|:--------------|:-------|
        | Efficiency | > 70% | Energy cost savings |
        | Operating Point | 80-110% of BEP | Pump longevity |
        | NPSH Available | > NPSH Required + 0.5m | Avoid cavitation |
        
        #### System Curve
        
        The system curve represents pressure requirements at varying flows:
        
        $$H_{system} = H_{static} + K \\times Q^2$$
        
        The intersection of pump curve and system curve is the **operating point**.
        
        #### Required Inputs
        
        - System flow requirement (m³/h) - from mainline design
        - Total head required (m) - from hydraulic design
        - Static head (m) - elevation difference
        
        #### Expected Outputs
        
        - Matched pump recommendations
        - Operating point (flow, head, efficiency)
        - Power consumption (kW)
        - Pump vs. system curve graph
        - Energy cost estimate
        """)


def show_data_entry_guide():
    """Data entry fields and validation rules."""
    
    st.markdown("## 🔧 Data Entry & Validation Rules")
    
    st.markdown("""
    ### Professional Units Used
    
    This application uses **SI metric units** consistent with South African engineering standards:
    """)
    
    # Units table
    units_data = [
        ("Pressure", "kPa, bar", "1 bar = 100 kPa = 10.197 m head"),
        ("Flow Rate", "m³/h, l/h", "1 m³/h = 1000 l/h"),
        ("Pipe Diameter", "mm (nominal)", "Internal diameter used for calculations"),
        ("Length/Distance", "m", "Meters for all dimensions"),
        ("Area", "ha, m²", "1 ha = 10,000 m²"),
        ("Velocity", "m/s", "Water velocity in pipes"),
        ("Head", "m", "Meters of water column"),
        ("Temperature", "°C", "Celsius for climate data"),
        ("Evapotranspiration", "mm/day, mm/month", "Water depth equivalent"),
        ("Application Rate", "mm/hr", "Sprinkler precipitation rate"),
        ("Power", "kW", "Pump power consumption"),
    ]
    
    st.markdown("""
    | Parameter | Units | Notes |
    |:----------|:------|:------|
    """ + "\n".join([f"| {row[0]} | **{row[1]}** | {row[2]} |" for row in units_data]))
    
    st.markdown("---")
    
    # Validation Rules
    st.markdown("### Input Validation Rules")
    
    st.markdown("""
    The application validates all inputs against engineering limits:
    """)
    
    validation_data = [
        ("Pressure", "50 - 1000 kPa", "150 - 500 kPa", "Physical limits for irrigation systems"),
        ("Flow Rate", "0.1 - 500 m³/h", "0.5 - 100 m³/h", "Practical irrigation ranges"),
        ("Pipe Diameter", "10 - 500 mm", "20 - 200 mm", "Standard pipe sizes"),
        ("Spacing", "1 - 100 m", "5 - 30 m", "Typical sprinkler spacing"),
        ("Friction Loss", "0 - 20 m/100m", "< 5 m/100m", "Acceptable head loss"),
        ("Velocity", "0.3 - 3.0 m/s", "0.6 - 2.0 m/s", "Avoid sedimentation/hammer"),
        ("Efficiency", "50 - 100%", "> 70%", "Economic operation"),
    ]
    
    st.markdown("""
    | Parameter | Absolute Limits | Recommended Range | Reason |
    |:----------|:----------------|:------------------|:-------|
    """ + "\n".join([f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |" for row in validation_data]))
    
    st.markdown("---")
    
    # System Health Indicators
    st.markdown("### 🚦 System Health Indicators")
    
    st.markdown("""
    The application displays **color-coded health indicators** to quickly assess design quality:
    """)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        #### 🟢 Green - OK
        - Value within optimal range
        - No action required
        - Design is sound
        """)
    
    with col2:
        st.markdown("""
        #### 🟡 Yellow - Warning
        - Value approaching limits
        - Review recommended
        - May need optimization
        """)
    
    with col3:
        st.markdown("""
        #### 🔴 Red - Error
        - Value exceeds safe limits
        - Immediate action required
        - Redesign necessary
        """)
    
    st.markdown("---")
    
    # Specific health indicators
    st.markdown("### Health Indicator Thresholds")
    
    health_data = [
        ("Total Friction Loss", "< 5 m", "5 - 10 m", "> 10 m"),
        ("Pressure @ Furthest Nozzle", "> 250 kPa", "150 - 250 kPa", "< 150 kPa"),
        ("System Efficiency", "> 75%", "60 - 75%", "< 60%"),
        ("Pipe Velocity", "0.6 - 1.5 m/s", "0.3 - 0.6 or 1.5 - 2.0 m/s", "< 0.3 or > 2.0 m/s"),
        ("Application Rate vs Infiltration", "App Rate < Infiltration", "App Rate ≈ Infiltration", "App Rate > Infiltration"),
        ("Uniformity Coefficient", "> 84%", "75 - 84%", "< 75%"),
    ]
    
    st.markdown("""
    | Indicator | 🟢 Green (OK) | 🟡 Yellow (Warning) | 🔴 Red (Error) |
    |:----------|:--------------|:--------------------|:---------------|
    """ + "\n".join([f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} |" for row in health_data]))
    
    st.markdown("""
    > 💡 **Interpreting Health Status**
    > 
    > A design with all green indicators is optimized for efficiency and safety.
    > Yellow indicators suggest the design works but could be improved.
    > Red indicators require attention before the design can be implemented.
    """)


def show_visual_guide():
    """Visual guide with screenshot placeholders."""
    
    st.markdown("## 📸 Visual Guide & Screenshot Placeholders")
    
    st.markdown("""
    This section provides detailed instructions for capturing screenshots to document your design.
    Each placeholder describes:
    - The specific screen to capture
    - Required annotations
    - What the user should see to confirm correct operation
    """)
    
    st.markdown("---")
    
    # Screenshot 1: Home/Project Setup
    st.markdown("""
    ### 📸 Screenshot 1: Project Setup Screen
    
    **Screen:** Home → Project Information section
    
    **What to Capture:**
    - Project name, location, and date fields
    - Crop type and soil type dropdowns
    - Field area input
    - "Save Project Information" button
    
    **Annotations Needed:**
    - 🔴 Red box around required fields (Project Name, Area)
    - 🔵 Blue arrow pointing to the Save button
    - ✅ Green checkmark next to successfully saved indicator
    
    **Confirmation:** User should see a green success toast message after saving.
    
    ---
    """)
    
    # Screenshot 2: Climate Data Input
    st.markdown("""
    ### 📸 Screenshot 2: Climate Data Entry
    
    **Screen:** Crop Water Requirements → Climate Data tab
    
    **What to Capture:**
    - Monthly climate data table
    - Growing season selector
    - Data input method selector (Manual/CSV/AQUASTAT)
    
    **Annotations Needed:**
    - 🔴 Red box around the data table columns
    - 🔵 Blue highlight on "Upload CSV (AQUASTAT)" option
    - 📝 Note: "Enter all 12 months or growing season only"
    
    **Confirmation:** Table shows valid temperature and humidity ranges.
    
    ---
    """)
    
    # Screenshot 3: ET0 Results
    st.markdown("""
    ### 📸 Screenshot 3: ET₀ Calculation Results
    
    **Screen:** Crop Water Requirements → ET₀ Calculation tab
    
    **What to Capture:**
    - Monthly ET₀ chart (bar or line graph)
    - Peak month indicator
    - ET₀ summary statistics
    
    **Annotations Needed:**
    - 🔴 Circle the peak ET₀ month on the chart
    - 🔵 Highlight the "Peak ET₀" metric value
    - 📝 Note the units (mm/day or mm/month)
    
    **Confirmation:** ET₀ values typically range 3-8 mm/day in South Africa.
    
    ---
    """)
    
    # Screenshot 4: Sprinkler Selection
    st.markdown("""
    ### 📸 Screenshot 4: Sprinkler Selection
    
    **Screen:** Sprinkler Selection → Sprinkler Selection tab
    
    **What to Capture:**
    - Sprinkler category and type dropdowns
    - Available sprinkler models table
    - Selected sprinkler specifications (4 metric cards)
    
    **Annotations Needed:**
    - 🔴 Red box around the model selection dropdown
    - 🔵 Blue arrows pointing to Flow Rate and Pressure metrics
    - ✅ Green highlight on "Select This Sprinkler" button
    
    **Confirmation:** Selected sprinkler shows valid pressure (kPa) and flow (l/h).
    
    ---
    """)
    
    # Screenshot 5: Spacing Visualization
    st.markdown("""
    ### 📸 Screenshot 5: Spacing Layout Visualization
    
    **Screen:** Sprinkler Selection → Spacing Design tab
    
    **What to Capture:**
    - Spacing input fields (along and between)
    - Calculated values panel
    - Visual sprinkler layout plot with wetted circles
    
    **Annotations Needed:**
    - 🔴 Red box around spacing input fields
    - 🔵 Blue circle highlighting overlap between adjacent sprinklers
    - ✅/⚠️ Status indicator for spacing adequacy
    
    **Confirmation:** Wetted circles should overlap ~40-50% for good uniformity.
    
    ---
    """)
    
    # Screenshot 6: Field Subdivision
    st.markdown("""
    ### 📸 Screenshot 6: Field Subdivision Map
    
    **Screen:** Operational Design → After clicking "Calculate Field Subdivision"
    
    **What to Capture:**
    - Field subdivision visualization showing numbered subplots
    - Subplot dimensions table
    - Irrigation schedule matrix
    
    **Annotations Needed:**
    - 🔴 Red labels showing subplot numbers
    - 🔵 Blue lines indicating subplot boundaries
    - 📝 Note the irrigation day color coding
    
    **Confirmation:** Subplots are ~1 ha each (125m × 85m standard).
    
    ---
    """)
    
    # Screenshot 7: CAD Canvas
    st.markdown("""
    ### 📸 Screenshot 7: Pipe Network CAD Canvas
    
    **Screen:** Pipe Network Layout → Main drawing canvas
    
    **What to Capture:**
    - Full canvas with drawn pipe network
    - Mainline (red), Submains (orange), Laterals (green)
    - Valve markers at intersections
    - Grid overlay
    
    **Annotations Needed:**
    - 🔴 Label: "Mainline" on red pipe
    - 🟠 Label: "Submain" on orange pipe
    - 🟢 Label: "Lateral" on green pipe
    - 🔵 Circle around a valve marker
    - 📝 Arrow pointing to "Grid Snap" toggle
    
    **Confirmation:** All pipe connections are clean (snapped to grid).
    
    ---
    """)
    
    # Screenshot 8: Hydraulic Results
    st.markdown("""
    ### 📸 Screenshot 8: Hydraulic Pressure Summary
    
    **Screen:** Hydraulic Design → Pressure Requirements tab
    
    **What to Capture:**
    - Complete pressure requirements table
    - Result box (green/red based on feasibility)
    - Static pressure input
    
    **Annotations Needed:**
    - 🔴 Red box around "Total pressure required" row
    - 🔵 Blue box around "Static pressure available" row
    - ✅/❌ Large indicator on result (Pr = Ps - requirements)
    
    **Confirmation:** If Pr > 0, system is feasible. If Pr < 0, pump required.
    
    ---
    """)
    
    # Screenshot 9: Pump Curves
    st.markdown("""
    ### 📸 Screenshot 9: Pump Performance Curves
    
    **Screen:** Pump Selection → Performance Curves tab
    
    **What to Capture:**
    - Pump curve (Head vs Flow)
    - System curve overlay
    - Operating point intersection
    - Efficiency curve
    
    **Annotations Needed:**
    - 🔴 Circle the operating point intersection
    - 🔵 Label "System Curve" and "Pump Curve"
    - 📝 Note the duty point values (Q, H, η)
    
    **Confirmation:** Operating point should be at 80-110% of BEP (Best Efficiency Point).
    
    ---
    """)
    
    # Screenshot 10: Export Options
    st.markdown("""
    ### 📸 Screenshot 10: Report Export Panel
    
    **Screen:** Reports → Export section
    
    **What to Capture:**
    - Export format options (PDF, Excel)
    - Report sections checkboxes
    - Export button
    
    **Annotations Needed:**
    - 🔴 Red box around "Export as PDF" button
    - 🔵 Blue checkmarks on included sections
    - 📝 Note: "Material List" export option
    
    **Confirmation:** PDF generates with all selected sections and proper formatting.
    """)


def show_technical_appendix():
    """Technical appendix with mathematical assumptions."""
    
    st.markdown("## 📊 Technical Appendix")
    
    st.markdown("""
    ### Mathematical Assumptions & Constants
    
    This section documents the engineering constants and assumptions used by the application.
    Engineers should verify these values match their local standards and project requirements.
    """)
    
    st.markdown("---")
    
    # Pipe Roughness Coefficients
    st.markdown("### Hazen-Williams C-Values (Pipe Roughness)")
    
    c_values = [
        ("PVC (new)", "150", "Polyvinyl chloride - new installation"),
        ("PVC (10 years)", "140", "Aged PVC pipe"),
        ("PVC (design default)", "130", "Conservative design value"),
        ("HDPE (new)", "150", "High-density polyethylene"),
        ("HDPE (10 years)", "140", "Aged HDPE"),
        ("Steel (new)", "120", "New unlined steel"),
        ("Steel (old)", "100", "Corroded/tuberculated steel"),
        ("Concrete", "120", "Concrete pipe"),
        ("Cast Iron (new)", "130", "New cast iron"),
        ("Cast Iron (old)", "80-100", "Heavily tuberculated"),
    ]
    
    st.markdown("""
    | Material | C-Value | Notes |
    |:---------|:--------|:------|
    """ + "\n".join([f"| {row[0]} | **{row[1]}** | {row[2]} |" for row in c_values]))
    
    st.markdown("""
    > 💡 **Default Value:** The application uses **C = 130** for PVC pipe as a conservative 
    > design value that accounts for aging and minor fitting losses.
    """)
    
    st.markdown("---")
    
    # Standard Pipe Sizes
    st.markdown("### Standard PVC Pipe Sizes (Class 6)")
    
    pipe_sizes = [
        ("20", "17.6", "Class 6"),
        ("25", "22.0", "Class 6"),
        ("32", "28.0", "Class 6"),
        ("40", "35.2", "Class 6"),
        ("50", "44.0", "Class 6"),
        ("63", "55.4", "Class 6"),
        ("75", "66.0", "Class 6"),
        ("90", "79.2", "Class 6"),
        ("110", "96.8", "Class 6"),
        ("125", "110.0", "Class 6"),
        ("140", "123.2", "Class 6"),
        ("160", "140.8", "Class 6"),
        ("200", "176.0", "Class 6"),
        ("250", "220.0", "Class 6"),
        ("315", "277.2", "Class 6"),
    ]
    
    st.markdown("""
    | Nominal OD (mm) | Internal ID (mm) | Pressure Class |
    |:----------------|:-----------------|:---------------|
    """ + "\n".join([f"| {row[0]} | **{row[1]}** | {row[2]} |" for row in pipe_sizes]))
    
    st.markdown("---")
    
    # Safety Factors
    st.markdown("### Design Safety Factors")
    
    safety_factors = [
        ("Fittings Loss Allowance", "10%", "Added to pipe friction losses"),
        ("Pump Head Safety", "10%", "Added to calculated pump head"),
        ("Flow Safety Factor", "1.0", "No inflation of design flow"),
        ("Pressure Variation (max)", "20%", "Maximum along lateral"),
        ("Application Rate Safety", "1.0", "Must not exceed infiltration"),
    ]
    
    st.markdown("""
    | Factor | Value | Application |
    |:-------|:------|:------------|
    """ + "\n".join([f"| {row[0]} | **{row[1]}** | {row[2]} |" for row in safety_factors]))
    
    st.markdown("---")
    
    # Soil Infiltration Rates
    st.markdown("### Soil Infiltration Rates")
    
    soil_rates = [
        ("Sandy", "25", "Fast drainage, low water holding"),
        ("Loamy Sand", "20", "Good drainage"),
        ("Sandy Loam", "15", "Well-balanced soil"),
        ("Loam", "10", "Ideal agricultural soil"),
        ("Silty Loam", "8", "Good water retention"),
        ("Silt", "7", "Moderate infiltration"),
        ("Clay Loam", "5", "Slow infiltration"),
        ("Clay", "3", "Very slow infiltration"),
    ]
    
    st.markdown("""
    | Soil Type | Basic Infiltration Rate (mm/hr) | Characteristics |
    |:----------|:--------------------------------|:----------------|
    """ + "\n".join([f"| {row[0]} | **{row[1]}** | {row[2]} |" for row in soil_rates]))
    
    st.markdown("""
    > ⚠️ **Important:** These are basic infiltration rates. Actual rates depend on 
    > soil structure, compaction, moisture content, and slope. Site-specific testing 
    > is recommended for critical designs.
    """)
    
    st.markdown("---")
    
    # Physical Constants
    st.markdown("### Physical Constants")
    
    constants = [
        ("Water Density", "1000 kg/m³", "At 20°C"),
        ("Gravity", "9.81 m/s²", "Standard gravity"),
        ("1 bar", "100 kPa", "Pressure conversion"),
        ("1 bar", "10.197 m H₂O", "Head conversion"),
        ("1 m³/h", "1000 l/h", "Flow conversion"),
        ("1 ha", "10,000 m²", "Area conversion"),
        ("π (pi)", "3.14159", "Circle calculations"),
    ]
    
    st.markdown("""
    | Constant | Value | Notes |
    |:---------|:------|:------|
    """ + "\n".join([f"| {row[0]} | **{row[1]}** | {row[2]} |" for row in constants]))
    
    st.markdown("---")
    
    # Formulas Reference
    st.markdown("### Key Formulas Reference")
    
    st.markdown("""
    #### Hazen-Williams Equation (Friction Loss)
    
    $$h_f = 10.67 \\times L \\times \\frac{Q^{1.852}}{C^{1.852} \\times D^{4.87}}$$
    
    *Where: $h_f$ = head loss (m), $L$ = length (m), $Q$ = flow (m³/s), $C$ = coefficient, $D$ = diameter (m)*
    
    ---
    
    #### Christiansen F-Factor (Multiple Outlets)
    
    $$F = \\frac{1}{m+1} + \\frac{1}{2N} + \\frac{\\sqrt{m-1}}{6N^2}$$
    
    *Where: $m$ = 1.852, $N$ = number of outlets*
    
    ---
    
    #### Flow Velocity
    
    $$V = \\frac{Q}{A} = \\frac{4Q}{\\pi D^2}$$
    
    *Where: $V$ = velocity (m/s), $Q$ = flow (m³/s), $D$ = diameter (m)*
    
    ---
    
    #### Sprinkler Application Rate
    
    $$I = \\frac{Q}{S_l \\times S_b}$$
    
    *Where: $I$ = application rate (mm/hr), $Q$ = flow (l/hr), $S_l$ = spacing along (m), $S_b$ = spacing between (m)*
    
    ---
    
    #### Pump Power
    
    $$P_{kW} = \\frac{Q \\times H}{367 \\times \\eta}$$
    
    *Where: $Q$ = flow (m³/h), $H$ = head (m), $\\eta$ = efficiency (decimal)*
    
    ---
    
    #### System Curve
    
    $$H_{system} = H_{static} + K \\times Q^2$$
    
    *Where: $K$ = system resistance coefficient*
    """)
    
    st.markdown("---")
    
    # References
    st.markdown("### References")
    
    st.markdown("""
    1. **FAO Irrigation and Drainage Paper No. 24** - Crop Water Requirements (Allen et al., 1998)
    
    2. **FAO Irrigation Manual** - Planning, Development and Evaluation of Irrigated Agriculture
    
    3. **South African Irrigation Design Manual** - Department of Agriculture
    
    4. **Sprinkler Irrigation** - Keller & Bliesner, 5th Edition
    
    5. **Hydraulics of Pipelines** - Larock, Jeppson & Watters
    
    6. **ASAE Standards** - American Society of Agricultural Engineers
    """)
    
    st.markdown("---")
    
    # Version Info
    st.markdown("### Application Version Information")
    
    st.info("""
    **Sprinkler Irrigation Design Application**
    
    - Version: 2.0 Professional Edition
    - Release Date: December 2025
    - Target Region: South Africa
    - Standards: FAO, SABI, South African Design Guidelines
    - Developed for: Professional Irrigation Engineers
    """)
