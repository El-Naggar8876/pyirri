"""
Sprinkler Irrigation Design — open-access edition for SoftwareX.

This entry-point exposes the sprinkler design workflow as a single Streamlit
application.  No login or user management is required: the app opens directly
on the home page.

Run locally with:
    streamlit run app.py
"""

from __future__ import annotations

import streamlit as st

from config.theme import get_main_css, get_graph_paper_css
from components.logger import render_dev_mode_toggle

from modules import (
    home,
    crop_water_requirements,
    sprinkler_selection,
    operational_design,
    pipe_network_layout,
    pipe_network_design,
    hydraulic_design,
    pump_selection,
    cost_estimation,
    reports,
    get_import_errors,
)

# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Sprinkler Irrigation Design",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------
if "dark_mode" not in st.session_state:
    st.session_state.dark_mode = False

st.markdown(get_main_css(dark_mode=st.session_state.dark_mode), unsafe_allow_html=True)
st.markdown(get_graph_paper_css(), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session-state defaults
# ---------------------------------------------------------------------------
if "project_data" not in st.session_state:
    st.session_state.project_data = {
        "project_name": "",
        "location": "",
        "area": 0,
        "crop_type": "",
        "soil_type": "",
        "water_source": "",
        "climate_data": {},
        "crop_parameters": {},
        "irrigation_requirements": {},
        "sprinkler_data": {},
        "hydraulic_design": {},
        "pipe_network": {},
        "pump_data": {},
        "layout_data": {},
        "cost_data": {},
        "field_geometry": {},
        "field_layout": {
            "main_boundary": None,
            "main_boundary_local": None,
            "water_source": None,
            "water_source_local": None,
            "crop_blocks": [],
            "irrigation_assignment": {},
            "workflow_step": "draw_boundary",
            "total_area_ha": 0,
            "created_at": None,
            "updated_at": None,
        },
    }

if "selected_line" not in st.session_state:
    st.session_state.selected_line = {"type": None, "index": None}

if "current_drawing" not in st.session_state:
    st.session_state.current_drawing = {
        "mode": "Mainline",
        "points": [],
        "is_drawing": False,
        "draw_method": "Click-to-Click",
        "enable_angle_snap": False,
        "angle_snap_increment": 45,
        "enable_length_constraint": False,
        "target_length": 50.0,
        "show_measurements": True,
        "show_alignment_guides": True,
        "enable_snap": True,
        "snap_size": 25.0,
        "enable_intersection_snap": True,
        "enable_line_snap": True,
        "valve_coverage": "full",
        "valve_direction": 0,
        "show_operational_overlay": True,
    }

# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
PAGES: dict[str, object] = {
    "🏠 Home": home,
    "🌾 Crop Water Requirements": crop_water_requirements,
    "💧 Sprinkler Selection": sprinkler_selection,
    "📋 Operational Design": operational_design,
    "🔵 Pipe Network Layout": pipe_network_layout,
    "🚰 Pipe Network Design": pipe_network_design,
    "🧮 Hydraulic Design": hydraulic_design,
    "⚙️ Pump Selection": pump_selection,
    "💰 Cost Estimation": cost_estimation,
    "📊 Reports & Export": reports,
}


def _sidebar() -> str:
    st.sidebar.markdown(
        """
        <div style="text-align:center;padding:1rem 0;">
            <div style="font-size:2rem;">💧</div>
            <div style="font-size:1.05rem;font-weight:700;color:#4da6ff;letter-spacing:1px;">
                SPRINKLER DESIGN
            </div>
            <div style="font-size:0.7rem;color:#6c757d;letter-spacing:2px;">
                SoftwareX Edition
            </div>
        </div>
        <hr/>
        """,
        unsafe_allow_html=True,
    )

    if "nav_selection" not in st.session_state:
        st.session_state.nav_selection = "🏠 Home"

    for label in PAGES:
        is_active = st.session_state.nav_selection == label
        if st.sidebar.button(
            label,
            key=f"nav_{label}",
            width="stretch",
            type="primary" if is_active else "secondary",
        ):
            st.session_state.nav_selection = label
            st.rerun()

    st.sidebar.markdown("---")
    render_dev_mode_toggle()

    st.sidebar.markdown("---")
    dark = st.sidebar.checkbox("🌙 Dark mode", value=st.session_state.dark_mode)
    if dark != st.session_state.dark_mode:
        st.session_state.dark_mode = dark
        st.rerun()

    st.sidebar.markdown(
        """
        <hr/>
        <div style="font-size:0.7rem;color:#6c757d;text-align:center;">
            Open-source · MIT licence<br/>
            Companion software to a SoftwareX article
        </div>
        """,
        unsafe_allow_html=True,
    )
    return st.session_state.nav_selection


def main() -> None:
    errors = get_import_errors()
    if errors:
        with st.sidebar.expander("⚠️ Import warnings", expanded=False):
            for e in errors:
                st.caption(e)

    page_label = _sidebar()
    page = PAGES.get(page_label)
    if page is not None and hasattr(page, "show"):
        page.show()
    else:
        st.error(f"Page '{page_label}' is not available.")


if __name__ == "__main__":
    main()
