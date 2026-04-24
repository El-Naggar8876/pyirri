"""
Quick Stats & System Health Component
=====================================
High-visibility metric cards for critical engineering data.
"""

import streamlit as st
from typing import Optional, Literal
from config.theme import system_health_card, COLORS


def render_system_health(
    title: str,
    value: float,
    unit: str,
    threshold_warning: Optional[float] = None,
    threshold_error: Optional[float] = None,
    inverse: bool = False,
    format_spec: str = ".2f"
) -> str:
    """
    Render a system health metric card with automatic status coloring.
    
    Args:
        title: Metric title (e.g., "Total Friction Loss")
        value: Numeric value
        unit: Unit string (e.g., "m", "kPa", "%")
        threshold_warning: Value above which to show warning (yellow)
        threshold_error: Value above which to show error (red)
        inverse: If True, lower values are worse (e.g., efficiency)
        format_spec: Python format spec for value display
    
    Returns:
        HTML string for the card
    """
    # Determine status
    status = "ok"
    
    if inverse:
        # Lower is worse (e.g., efficiency)
        if threshold_error is not None and value < threshold_error:
            status = "error"
        elif threshold_warning is not None and value < threshold_warning:
            status = "warning"
    else:
        # Higher is worse (e.g., friction loss)
        if threshold_error is not None and value > threshold_error:
            status = "error"
        elif threshold_warning is not None and value > threshold_warning:
            status = "warning"
    
    # Format value
    formatted_value = f"{value:{format_spec}}"
    
    # Generate and render HTML
    html = system_health_card(title, formatted_value, unit, status)
    st.markdown(html, unsafe_allow_html=True)
    
    return status


def render_quick_stat(
    label: str,
    value: str,
    delta: Optional[str] = None,
    delta_color: Literal["normal", "inverse", "off"] = "normal",
    help_text: Optional[str] = None
):
    """
    Render a quick stat using Streamlit's metric with enhanced styling.
    
    Args:
        label: Metric label
        value: Main value to display
        delta: Optional delta/change value
        delta_color: Color scheme for delta
        help_text: Optional help tooltip
    """
    st.metric(
        label=label,
        value=value,
        delta=delta,
        delta_color=delta_color,
        help=help_text
    )


def render_system_health_panel(data: dict):
    """
    Render a complete system health panel with multiple metrics.
    
    Args:
        data: Dictionary with keys:
            - total_friction_loss: float (m)
            - pressure_at_nozzle: float (kPa)
            - system_efficiency: float (%)
            - total_flow: float (m³/h)
    """
    st.markdown("""
    <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); 
                padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">
        <h3 style="color: #4da6ff; margin: 0 0 1rem 0; font-size: 0.9rem; 
                   text-transform: uppercase; letter-spacing: 1px;">
            ⚡ System Health
        </h3>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Total Friction Loss
        friction_loss = data.get('total_friction_loss', 0)
        render_system_health(
            title="Total Friction Loss",
            value=friction_loss,
            unit="m",
            threshold_warning=5.0,
            threshold_error=10.0,
            format_spec=".2f"
        )
    
    with col2:
        # Pressure at Furthest Nozzle
        pressure = data.get('pressure_at_nozzle', 0)
        render_system_health(
            title="Pressure @ Furthest Nozzle",
            value=pressure,
            unit="kPa",
            threshold_warning=200,
            threshold_error=150,
            inverse=True,  # Lower pressure is worse
            format_spec=".0f"
        )
    
    col3, col4 = st.columns(2)
    
    with col3:
        # System Efficiency
        efficiency = data.get('system_efficiency', 0)
        render_system_health(
            title="System Efficiency",
            value=efficiency,
            unit="%",
            threshold_warning=75,
            threshold_error=60,
            inverse=True,  # Lower efficiency is worse
            format_spec=".1f"
        )
    
    with col4:
        # Total System Flow
        flow = data.get('total_flow', 0)
        st.markdown(f"""
        <div class="system-health-card" style="border-left-color: #2196f3;">
            <div class="system-health-title">Total System Flow</div>
            <div>
                <span class="system-health-value">{flow:.1f}</span>
                <span class="system-health-unit">m³/h</span>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_bom_summary(items: list):
    """
    Render Bill of Materials summary card.
    
    Args:
        items: List of dicts with keys: name, quantity, unit, cost (optional)
    """
    total_cost = sum(item.get('cost', 0) for item in items)
    
    st.markdown("""
    <div class="engineering-card">
        <div class="engineering-card-header">
            <span style="font-size: 1.25rem;">📋</span>
            <h3 class="engineering-card-title">Material Summary</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Create summary table
    for item in items[:5]:  # Show top 5 items
        st.markdown(f"""
        <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; 
                    border-bottom: 1px solid rgba(0,0,0,0.1);">
            <span style="color: #6c757d;">{item['name']}</span>
            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 600;">
                {item['quantity']} {item['unit']}
            </span>
        </div>
        """, unsafe_allow_html=True)
    
    if len(items) > 5:
        st.caption(f"+ {len(items) - 5} more items...")
    
    if total_cost > 0:
        st.markdown(f"""
        <div style="margin-top: 1rem; padding-top: 1rem; border-top: 2px solid #0078d4;">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: 600;">Estimated Total</span>
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 1.25rem; 
                            font-weight: 700; color: #0078d4;">
                    R {total_cost:,.2f}
                </span>
            </div>
        </div>
        """, unsafe_allow_html=True)
