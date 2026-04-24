"""
Export Utilities Component
==========================
Export functionality for design data, reports, and BOM.
"""

import streamlit as st
import pandas as pd
import io
import json
from datetime import datetime
from typing import Optional, Dict, List, Any


def export_bom_csv(bom_data: List[Dict], project_name: str = "irrigation_project") -> bytes:
    """
    Export Bill of Materials to CSV format.
    
    Args:
        bom_data: List of BOM items with keys like: item, description, quantity, unit, unit_price, total
        project_name: Project name for filename
    
    Returns:
        CSV bytes for download
    """
    df = pd.DataFrame(bom_data)
    
    # Ensure standard columns exist
    standard_columns = ['Item', 'Description', 'Quantity', 'Unit', 'Unit Price (R)', 'Total (R)']
    for col in standard_columns:
        if col not in df.columns:
            df[col] = ''
    
    # Reorder columns
    existing_cols = [c for c in standard_columns if c in df.columns]
    other_cols = [c for c in df.columns if c not in standard_columns]
    df = df[existing_cols + other_cols]
    
    return df.to_csv(index=False).encode('utf-8')


def export_design_summary_csv(design_data: Dict, project_name: str = "irrigation_project") -> bytes:
    """
    Export design summary to CSV format.
    
    Args:
        design_data: Dictionary containing design parameters and results
        project_name: Project name for filename
    
    Returns:
        CSV bytes for download
    """
    # Flatten nested design data
    rows = []
    
    def flatten_dict(d: dict, prefix: str = ""):
        for key, value in d.items():
            full_key = f"{prefix}{key}" if prefix else key
            if isinstance(value, dict):
                flatten_dict(value, f"{full_key}.")
            elif isinstance(value, (list, tuple)):
                rows.append({"Parameter": full_key, "Value": str(value)})
            else:
                rows.append({"Parameter": full_key, "Value": value})
    
    flatten_dict(design_data)
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode('utf-8')


def export_pipe_network_csv(network_data: Dict) -> bytes:
    """
    Export pipe network data to CSV format.
    
    Args:
        network_data: Pipe network dictionary with mainlines, submains, laterals, valves
    
    Returns:
        CSV bytes for download
    """
    rows = []
    
    # Export mainlines
    for i, mainline in enumerate(network_data.get('mainlines', [])):
        for j, point in enumerate(mainline):
            rows.append({
                'Type': 'Mainline',
                'Line_ID': i + 1,
                'Point_ID': j + 1,
                'X': point[0],
                'Y': point[1]
            })
    
    # Export submains
    for i, submain in enumerate(network_data.get('submains', [])):
        for j, point in enumerate(submain):
            rows.append({
                'Type': 'Submain',
                'Line_ID': i + 1,
                'Point_ID': j + 1,
                'X': point[0],
                'Y': point[1]
            })
    
    # Export laterals
    for i, lateral in enumerate(network_data.get('laterals', [])):
        for j, point in enumerate(lateral):
            rows.append({
                'Type': 'Lateral',
                'Line_ID': i + 1,
                'Point_ID': j + 1,
                'X': point[0],
                'Y': point[1]
            })
    
    # Export valves
    for i, valve in enumerate(network_data.get('valves', [])):
        rows.append({
            'Type': 'Valve',
            'Line_ID': valve.get('name', f'V{i+1}'),
            'Point_ID': 1,
            'X': valve.get('x', 0),
            'Y': valve.get('y', 0)
        })
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode('utf-8')


def export_hydraulic_results_csv(hydraulic_data: Dict) -> bytes:
    """
    Export hydraulic calculation results to CSV.
    
    Args:
        hydraulic_data: Dictionary with hydraulic calculation results
    
    Returns:
        CSV bytes for download
    """
    rows = []
    
    # System overview
    rows.append({'Category': 'System Overview', 'Parameter': 'Total Friction Loss', 
                 'Value': hydraulic_data.get('total_friction_loss', 0), 'Unit': 'm'})
    rows.append({'Category': 'System Overview', 'Parameter': 'System Flow', 
                 'Value': hydraulic_data.get('total_flow', 0), 'Unit': 'm³/h'})
    rows.append({'Category': 'System Overview', 'Parameter': 'Pressure at Furthest Nozzle', 
                 'Value': hydraulic_data.get('pressure_at_nozzle', 0), 'Unit': 'kPa'})
    
    # Pipe segments
    for segment_type in ['mainline', 'submain', 'lateral']:
        segments = hydraulic_data.get(f'{segment_type}_segments', [])
        for i, seg in enumerate(segments):
            rows.append({
                'Category': segment_type.title(),
                'Parameter': f'Segment {i+1} - Diameter',
                'Value': seg.get('diameter_mm', seg.get('pipe_nominal_mm', '')),
                'Unit': 'mm'
            })
            rows.append({
                'Category': segment_type.title(),
                'Parameter': f'Segment {i+1} - Flow',
                'Value': seg.get('flow_m3h', ''),
                'Unit': 'm³/h'
            })
            rows.append({
                'Category': segment_type.title(),
                'Parameter': f'Segment {i+1} - Friction Loss',
                'Value': seg.get('friction_loss_m', seg.get('head_loss_m', '')),
                'Unit': 'm'
            })
    
    df = pd.DataFrame(rows)
    return df.to_csv(index=False).encode('utf-8')


def export_full_report_json(project_data: Dict) -> bytes:
    """
    Export full project data as JSON for backup/import.
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        JSON bytes for download
    """
    # Add export metadata
    export_data = {
        'export_date': datetime.now().isoformat(),
        'export_version': '1.0',
        'project_data': project_data
    }
    
    return json.dumps(export_data, indent=2, default=str).encode('utf-8')


def render_export_panel():
    """
    Render the export panel with download buttons.
    Shows in the Results Panel / Sidebar.
    
    Note: Download buttons are rendered directly (not nested inside st.button)
    to prevent MediaFileStorageError when the app reruns. Streamlit stores
    download file data in memory with unique IDs - nesting them in conditionals
    causes the files to be unavailable after reruns.
    """
    st.markdown("""
    <div class="engineering-card">
        <div class="engineering-card-header">
            <span style="font-size: 1.25rem;">📥</span>
            <h3 class="engineering-card-title">Export Reports</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    project_data = st.session_state.get('project_data', {})
    project_name = project_data.get('project_name', 'irrigation_project')
    # Use a stable filename without timestamp to reduce file ID churn
    safe_project_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in project_name)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # BOM Export - render download button directly if data available
        bom_data = project_data.get('cost_data', {}).get('bom', [])
        if bom_data:
            csv_bytes = export_bom_csv(bom_data, project_name)
            st.download_button(
                label="📋 Download BOM.csv",
                data=csv_bytes,
                file_name=f"{safe_project_name}_BOM.csv",
                mime="text/csv",
                key="download_bom"
            )
        else:
            st.button("📋 Export BOM", key="export_bom_btn", disabled=True, 
                     help="No BOM data available. Complete Cost Estimation first.")
    
    with col2:
        # Pipe Network Export - render download button directly if data available
        network_data = project_data.get('pipe_network_design', {})
        if network_data:
            csv_bytes = export_pipe_network_csv(network_data)
            st.download_button(
                label="🗺️ Download Network.csv",
                data=csv_bytes,
                file_name=f"{safe_project_name}_Network.csv",
                mime="text/csv",
                key="download_network"
            )
        else:
            st.button("🗺️ Export Network", key="export_network_btn", disabled=True,
                     help="No network data available. Design pipe network first.")
    
    col3, col4 = st.columns(2)
    
    with col3:
        # Hydraulic Results Export - render download button directly if data available
        hydraulic_data = project_data.get('hydraulic_design', {})
        if hydraulic_data:
            csv_bytes = export_hydraulic_results_csv(hydraulic_data)
            st.download_button(
                label="💧 Download Hydraulics.csv",
                data=csv_bytes,
                file_name=f"{safe_project_name}_Hydraulics.csv",
                mime="text/csv",
                key="download_hydraulics"
            )
        else:
            st.button("💧 Export Hydraulics", key="export_hydraulics_btn", disabled=True,
                     help="No hydraulic data available. Complete Hydraulic Design first.")
    
    with col4:
        # Full Project Backup - always available
        json_bytes = export_full_report_json(project_data)
        st.download_button(
            label="💾 Download Project.json",
            data=json_bytes,
            file_name=f"{safe_project_name}_Full.json",
            mime="application/json",
            key="download_full"
        )


def generate_bom_dataframe(project_data: Dict) -> pd.DataFrame:
    """
    Generate a Bill of Materials DataFrame from project data.
    
    Args:
        project_data: Complete project data dictionary
    
    Returns:
        DataFrame with BOM data
    """
    bom_items = []
    
    # Pipe materials
    network = project_data.get('pipe_network_design', {})
    
    # Calculate mainline length
    mainline_length = 0
    for mainline in network.get('mainlines', []):
        for i in range(len(mainline) - 1):
            p1, p2 = mainline[i], mainline[i+1]
            mainline_length += ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
    
    if mainline_length > 0:
        bom_items.append({
            'Item': 'Mainline Pipe',
            'Description': 'uPVC Class 9',
            'Quantity': round(mainline_length, 1),
            'Unit': 'm',
            'Unit Price (R)': 150,
            'Total (R)': round(mainline_length * 150, 2)
        })
    
    # Calculate submain length
    submain_length = 0
    for submain in network.get('submains', []):
        for i in range(len(submain) - 1):
            p1, p2 = submain[i], submain[i+1]
            submain_length += ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
    
    if submain_length > 0:
        bom_items.append({
            'Item': 'Submain Pipe',
            'Description': 'uPVC Class 6',
            'Quantity': round(submain_length, 1),
            'Unit': 'm',
            'Unit Price (R)': 85,
            'Total (R)': round(submain_length * 85, 2)
        })
    
    # Calculate lateral length
    lateral_length = 0
    for lateral in network.get('laterals', []):
        for i in range(len(lateral) - 1):
            p1, p2 = lateral[i], lateral[i+1]
            lateral_length += ((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)**0.5
    
    if lateral_length > 0:
        bom_items.append({
            'Item': 'Lateral Pipe',
            'Description': 'LDPE PN4',
            'Quantity': round(lateral_length, 1),
            'Unit': 'm',
            'Unit Price (R)': 25,
            'Total (R)': round(lateral_length * 25, 2)
        })
    
    # Valves
    num_valves = len(network.get('valves', []))
    if num_valves > 0:
        bom_items.append({
            'Item': 'Gate Valve',
            'Description': '50mm Brass',
            'Quantity': num_valves,
            'Unit': 'ea',
            'Unit Price (R)': 450,
            'Total (R)': round(num_valves * 450, 2)
        })
    
    # Sprinklers
    sprinkler_data = project_data.get('sprinkler_data', {})
    num_sprinklers = int(project_data.get('area', 0) * sprinkler_data.get('sprinklers_per_ha', 0))
    if num_sprinklers > 0:
        bom_items.append({
            'Item': 'Sprinkler Head',
            'Description': sprinkler_data.get('model', 'Impact Sprinkler'),
            'Quantity': num_sprinklers,
            'Unit': 'ea',
            'Unit Price (R)': 180,
            'Total (R)': round(num_sprinklers * 180, 2)
        })
    
    return pd.DataFrame(bom_items)
