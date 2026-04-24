"""
Components Package
==================
Reusable UI components for the Irrigation Design application.
"""

from .logger import DevLogger, log_debug, log_info, log_warning, log_error, render_dev_mode_toggle
from .validators import (
    validate_positive_number,
    validate_range,
    validate_pressure,
    validate_flow_rate,
    validate_pipe_diameter,
    validate_spacing,
    validate_velocity,
    validate_friction_loss,
    ValidationResult,
    render_validation_message,
    validated_number_input
)
from .toast import show_toast, ToastType, toast_success, toast_error, toast_warning, toast_info
from .icons import Icon, get_icon
from .quick_stats import render_system_health, render_quick_stat, render_system_health_panel, render_bom_summary
from .export_utils import (
    export_bom_csv,
    export_design_summary_csv,
    export_pipe_network_csv,
    export_hydraulic_results_csv,
    export_full_report_json,
    render_export_panel,
    generate_bom_dataframe
)

__all__ = [
    # Logger
    'DevLogger', 'log_debug', 'log_info', 'log_warning', 'log_error', 'render_dev_mode_toggle',
    # Validators
    'validate_positive_number', 'validate_range', 'validate_pressure',
    'validate_flow_rate', 'validate_pipe_diameter', 'validate_spacing',
    'validate_velocity', 'validate_friction_loss',
    'ValidationResult', 'render_validation_message', 'validated_number_input',
    # Toast
    'show_toast', 'ToastType', 'toast_success', 'toast_error', 'toast_warning', 'toast_info',
    # Icons
    'Icon', 'get_icon',
    # Quick Stats
    'render_system_health', 'render_quick_stat', 'render_system_health_panel', 'render_bom_summary',
    # Export
    'export_bom_csv', 'export_design_summary_csv', 'export_pipe_network_csv',
    'export_hydraulic_results_csv', 'export_full_report_json', 'render_export_panel',
    'generate_bom_dataframe'
]
