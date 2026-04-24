"""
Toast Notification Component
============================
Professional toast notifications for user feedback.
Replaces crude alerts with auto-dismissing notifications.
"""

import streamlit as st
from enum import Enum
from typing import Optional
import time


class ToastType(Enum):
    """Toast notification types."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# Toast styling constants
TOAST_STYLES = {
    ToastType.SUCCESS: {
        "icon": "✓",
        "bg": "#00c853",
        "title": "Success"
    },
    ToastType.ERROR: {
        "icon": "✗",
        "bg": "#f44336",
        "title": "Error"
    },
    ToastType.WARNING: {
        "icon": "⚠",
        "bg": "#ff9800",
        "title": "Warning"
    },
    ToastType.INFO: {
        "icon": "ℹ",
        "bg": "#2196f3",
        "title": "Info"
    }
}


def show_toast(
    message: str,
    toast_type: ToastType = ToastType.INFO,
    duration: int = 3,
    title: Optional[str] = None
):
    """
    Display a professional toast notification.
    
    Note: Streamlit's native toast (st.toast) is used when available (Streamlit 1.25+).
    Falls back to styled success/error/warning/info for older versions.
    
    Args:
        message: The message to display
        toast_type: Type of toast (SUCCESS, ERROR, WARNING, INFO)
        duration: Duration in seconds (for native toast)
        title: Optional custom title
    """
    style = TOAST_STYLES[toast_type]
    display_title = title or style["title"]
    icon = style["icon"]
    
    # Try to use native Streamlit toast (1.25+)
    try:
        # Map our types to Streamlit's icon parameter
        st.toast(f"{icon} **{display_title}**: {message}", icon=icon)
    except AttributeError:
        # Fallback for older Streamlit versions
        _show_styled_message(message, toast_type, display_title)


def _show_styled_message(message: str, toast_type: ToastType, title: str):
    """Fallback styled message for older Streamlit versions."""
    style = TOAST_STYLES[toast_type]
    
    if toast_type == ToastType.SUCCESS:
        st.success(f"**{title}**: {message}")
    elif toast_type == ToastType.ERROR:
        st.error(f"**{title}**: {message}")
    elif toast_type == ToastType.WARNING:
        st.warning(f"**{title}**: {message}")
    else:
        st.info(f"**{title}**: {message}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def toast_success(message: str, title: str = "Success"):
    """Show a success toast."""
    show_toast(message, ToastType.SUCCESS, title=title)


def toast_error(message: str, title: str = "Error"):
    """Show an error toast."""
    show_toast(message, ToastType.ERROR, title=title)


def toast_warning(message: str, title: str = "Warning"):
    """Show a warning toast."""
    show_toast(message, ToastType.WARNING, title=title)


def toast_info(message: str, title: str = "Info"):
    """Show an info toast."""
    show_toast(message, ToastType.INFO, title=title)


# =============================================================================
# OPERATION FEEDBACK
# =============================================================================

def with_toast_feedback(
    operation_name: str,
    success_message: Optional[str] = None,
    error_message: Optional[str] = None
):
    """
    Decorator to automatically show toast on operation success/failure.
    
    Usage:
        @with_toast_feedback("Save Project")
        def save_project():
            # ... save logic ...
            return True  # or raise exception
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                msg = success_message or f"{operation_name} completed successfully"
                toast_success(msg)
                return result
            except Exception as e:
                msg = error_message or f"{operation_name} failed: {str(e)}"
                toast_error(msg)
                raise
        return wrapper
    return decorator
