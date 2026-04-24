"""
Developer Logger Component
==========================
Toggleable logging system for development/debugging.
Can be enabled via 'Developer Mode' switch in sidebar.
"""

import streamlit as st
from typing import Any, Optional
from datetime import datetime
from functools import wraps


class DevLogger:
    """
    Development logger that can be toggled on/off.
    When disabled, all log calls are no-ops for zero performance impact.
    """
    
    SESSION_KEY = "dev_mode_enabled"
    LOG_HISTORY_KEY = "dev_log_history"
    MAX_LOG_ENTRIES = 100
    
    @classmethod
    def is_enabled(cls) -> bool:
        """Check if developer mode is enabled."""
        return st.session_state.get(cls.SESSION_KEY, False)
    
    @classmethod
    def enable(cls):
        """Enable developer mode."""
        st.session_state[cls.SESSION_KEY] = True
        if cls.LOG_HISTORY_KEY not in st.session_state:
            st.session_state[cls.LOG_HISTORY_KEY] = []
    
    @classmethod
    def disable(cls):
        """Disable developer mode."""
        st.session_state[cls.SESSION_KEY] = False
    
    @classmethod
    def toggle(cls) -> bool:
        """Toggle developer mode and return new state."""
        new_state = not cls.is_enabled()
        st.session_state[cls.SESSION_KEY] = new_state
        if new_state and cls.LOG_HISTORY_KEY not in st.session_state:
            st.session_state[cls.LOG_HISTORY_KEY] = []
        return new_state
    
    @classmethod
    def _add_to_history(cls, level: str, message: str, context: Optional[str] = None):
        """Add log entry to history (for viewing in debug panel)."""
        if cls.LOG_HISTORY_KEY not in st.session_state:
            st.session_state[cls.LOG_HISTORY_KEY] = []
        
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "level": level,
            "message": message,
            "context": context
        }
        
        st.session_state[cls.LOG_HISTORY_KEY].append(entry)
        
        # Keep only the last MAX_LOG_ENTRIES
        if len(st.session_state[cls.LOG_HISTORY_KEY]) > cls.MAX_LOG_ENTRIES:
            st.session_state[cls.LOG_HISTORY_KEY] = st.session_state[cls.LOG_HISTORY_KEY][-cls.MAX_LOG_ENTRIES:]
    
    @classmethod
    def debug(cls, message: str, context: Optional[str] = None, **kwargs):
        """Log debug message (only when dev mode enabled)."""
        if not cls.is_enabled():
            return
        
        cls._add_to_history("DEBUG", message, context)
        
        # Format with optional key-value pairs
        formatted = f"🔍 {message}"
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" [{details}]"
        
        st.markdown(f'<div class="dev-log">{formatted}</div>', unsafe_allow_html=True)
    
    @classmethod
    def info(cls, message: str, context: Optional[str] = None, **kwargs):
        """Log info message (only when dev mode enabled)."""
        if not cls.is_enabled():
            return
        
        cls._add_to_history("INFO", message, context)
        
        formatted = f"ℹ️ {message}"
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" [{details}]"
        
        st.markdown(
            f'<div class="dev-log" style="border-left-color: #2196f3;">{formatted}</div>',
            unsafe_allow_html=True
        )
    
    @classmethod
    def warning(cls, message: str, context: Optional[str] = None, **kwargs):
        """Log warning message (only when dev mode enabled)."""
        if not cls.is_enabled():
            return
        
        cls._add_to_history("WARNING", message, context)
        
        formatted = f"⚠️ {message}"
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" [{details}]"
        
        st.markdown(
            f'<div class="dev-log" style="border-left-color: #ff9800; color: #ff9800;">{formatted}</div>',
            unsafe_allow_html=True
        )
    
    @classmethod
    def error(cls, message: str, context: Optional[str] = None, **kwargs):
        """Log error message (only when dev mode enabled)."""
        if not cls.is_enabled():
            return
        
        cls._add_to_history("ERROR", message, context)
        
        formatted = f"❌ {message}"
        if kwargs:
            details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
            formatted += f" [{details}]"
        
        st.markdown(
            f'<div class="dev-log" style="border-left-color: #f44336; color: #f44336;">{formatted}</div>',
            unsafe_allow_html=True
        )
    
    @classmethod
    def section(cls, title: str):
        """Log a section header for grouping related logs."""
        if not cls.is_enabled():
            return
        
        st.markdown(
            f'<div class="dev-log" style="border-left-color: #0078d4; background: rgba(0,120,212,0.1); font-weight: 600;">{"="*20} {title} {"="*20}</div>',
            unsafe_allow_html=True
        )
    
    @classmethod
    def data(cls, label: str, data: Any):
        """Log data/variables for inspection."""
        if not cls.is_enabled():
            return
        
        cls._add_to_history("DATA", f"{label}: {data}")
        
        # Truncate long data
        data_str = str(data)
        if len(data_str) > 200:
            data_str = data_str[:200] + "..."
        
        st.markdown(
            f'<div class="dev-log" style="border-left-color: #9c27b0;">📊 <strong>{label}:</strong> {data_str}</div>',
            unsafe_allow_html=True
        )
    
    @classmethod
    def get_history(cls) -> list:
        """Get log history for display."""
        return st.session_state.get(cls.LOG_HISTORY_KEY, [])
    
    @classmethod
    def clear_history(cls):
        """Clear log history."""
        st.session_state[cls.LOG_HISTORY_KEY] = []


# =============================================================================
# CONVENIENCE FUNCTIONS (Module-level shortcuts)
# =============================================================================

def log_debug(message: str, **kwargs):
    """Shortcut for DevLogger.debug()"""
    DevLogger.debug(message, **kwargs)

def log_info(message: str, **kwargs):
    """Shortcut for DevLogger.info()"""
    DevLogger.info(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Shortcut for DevLogger.warning()"""
    DevLogger.warning(message, **kwargs)

def log_error(message: str, **kwargs):
    """Shortcut for DevLogger.error()"""
    DevLogger.error(message, **kwargs)


# =============================================================================
# SIDEBAR COMPONENT
# =============================================================================

def render_dev_mode_toggle():
    """
    Render the Developer Mode toggle in the sidebar.
    Call this in your sidebar setup.
    """
    st.markdown("---")
    st.markdown('<p class="sidebar-section-header">🔧 Developer Tools</p>', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        dev_mode = st.checkbox(
            "Developer Mode",
            value=DevLogger.is_enabled(),
            key="dev_mode_toggle",
            help="Enable verbose logging for troubleshooting"
        )
    
    if dev_mode:
        st.session_state[DevLogger.SESSION_KEY] = True
        st.markdown('<span class="dev-mode-badge">🔧 Dev Mode Active</span>', unsafe_allow_html=True)
        
        # Show log count
        log_count = len(DevLogger.get_history())
        if log_count > 0:
            st.caption(f"📝 {log_count} log entries")
        
        # Clear logs button
        if st.button("🗑️ Clear Logs", key="clear_dev_logs"):
            DevLogger.clear_history()
            st.rerun()
    else:
        st.session_state[DevLogger.SESSION_KEY] = False


def render_log_viewer():
    """
    Render expanded log viewer (for debug panel/expander).
    """
    if not DevLogger.is_enabled():
        return
    
    history = DevLogger.get_history()
    
    if not history:
        st.info("No log entries yet. Logs will appear here as you use the application.")
        return
    
    # Display logs in reverse chronological order
    for entry in reversed(history[-20:]):  # Show last 20
        level_colors = {
            "DEBUG": "#00c853",
            "INFO": "#2196f3",
            "WARNING": "#ff9800",
            "ERROR": "#f44336",
            "DATA": "#9c27b0"
        }
        color = level_colors.get(entry["level"], "#6c757d")
        
        st.markdown(
            f'<div style="font-family: monospace; font-size: 0.75rem; padding: 0.25rem; '
            f'border-left: 2px solid {color}; margin-bottom: 0.25rem; background: rgba(0,0,0,0.02);">'
            f'<span style="color: {color}; font-weight: 600;">[{entry["timestamp"]}] {entry["level"]}</span> '
            f'{entry["message"]}</div>',
            unsafe_allow_html=True
        )
