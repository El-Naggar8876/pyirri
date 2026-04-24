"""
Engineering/CAD Theme Configuration
===================================
Professional "Blueprint Blue/Gray" theme for irrigation design software.
Provides centralized styling, colors, and CSS for consistent UI.
"""

# =============================================================================
# COLOR PALETTE - Engineering/Blueprint Theme
# =============================================================================

COLORS = {
    # Primary palette
    "primary": "#0078d4",           # Microsoft Blue - primary actions
    "primary_dark": "#004578",      # Dark blue - hover states
    "primary_light": "#4da6ff",     # Light blue - highlights
    
    # Accent colors
    "accent_orange": "#ff6b35",     # Warning/attention
    "accent_green": "#00c853",      # Success/valid
    "accent_red": "#f44336",        # Error/invalid
    "accent_yellow": "#ffc107",     # Caution
    
    # Neutral palette (Blueprint theme)
    "bg_dark": "#1a1a2e",           # Dark sidebar background
    "bg_darker": "#16213e",         # Darker elements
    "bg_canvas": "#f5f7fa",         # Light canvas background
    "bg_canvas_dark": "#0f1419",    # Dark mode canvas
    "bg_card": "#ffffff",           # Card backgrounds
    "bg_card_dark": "#1e2530",      # Dark mode cards
    
    # Text colors
    "text_primary": "#1a1a2e",      # Main text (light mode)
    "text_secondary": "#6c757d",    # Secondary text
    "text_muted": "#adb5bd",        # Muted/disabled text
    "text_inverse": "#f8f9fa",      # Text on dark backgrounds
    
    # Pipe network colors (CAD standard)
    "pipe_mainline": "#e63946",     # Red - Mainline
    "pipe_submain": "#ff9f1c",      # Orange - Submain
    "pipe_lateral": "#2ec4b6",      # Teal - Lateral
    "pipe_sprinkler": "#3d5a80",    # Navy - Sprinkler line
    
    # Status colors
    "status_ok": "#00c853",
    "status_warning": "#ff9800",
    "status_error": "#f44336",
    "status_info": "#2196f3",
    
    # Grid/Canvas
    "grid_line": "#e0e6ed",
    "grid_line_dark": "#2a3441",
    "grid_major": "#c8d1dc",
    "grid_major_dark": "#3d4a5c",
}

# =============================================================================
# TYPOGRAPHY
# =============================================================================

FONTS = {
    "primary": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "monospace": "'JetBrains Mono', 'Roboto Mono', 'Fira Code', monospace",
    "heading": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
}

FONT_SIZES = {
    "xs": "0.75rem",
    "sm": "0.875rem",
    "base": "1rem",
    "lg": "1.125rem",
    "xl": "1.25rem",
    "2xl": "1.5rem",
    "3xl": "2rem",
    "4xl": "2.5rem",
}

# =============================================================================
# SPACING & LAYOUT
# =============================================================================

LAYOUT = {
    "sidebar_width": "280px",
    "results_panel_width": "320px",
    "canvas_min_width": "70%",
    "border_radius": "8px",
    "border_radius_sm": "4px",
    "border_radius_lg": "12px",
    "shadow_sm": "0 1px 2px rgba(0,0,0,0.05)",
    "shadow_md": "0 4px 6px rgba(0,0,0,0.1)",
    "shadow_lg": "0 10px 25px rgba(0,0,0,0.15)",
}

# =============================================================================
# MAIN CSS STYLESHEET
# =============================================================================

def get_main_css(dark_mode: bool = False) -> str:
    """Generate main CSS stylesheet based on theme mode."""
    
    bg_canvas = COLORS["bg_canvas_dark"] if dark_mode else COLORS["bg_canvas"]
    bg_card = COLORS["bg_card_dark"] if dark_mode else COLORS["bg_card"]
    text_primary = COLORS["text_inverse"] if dark_mode else COLORS["text_primary"]
    grid_line = COLORS["grid_line_dark"] if dark_mode else COLORS["grid_line"]
    grid_major = COLORS["grid_major_dark"] if dark_mode else COLORS["grid_major"]
    
    return f"""
    <style>
    /* =================================================================
       GOOGLE FONTS IMPORT
       ================================================================= */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
    
    /* =================================================================
       ROOT VARIABLES
       ================================================================= */
    :root {{
        --color-primary: {COLORS["primary"]};
        --color-primary-dark: {COLORS["primary_dark"]};
        --color-primary-light: {COLORS["primary_light"]};
        --color-success: {COLORS["accent_green"]};
        --color-warning: {COLORS["accent_orange"]};
        --color-error: {COLORS["accent_red"]};
        --color-info: {COLORS["status_info"]};
        --bg-canvas: {bg_canvas};
        --bg-card: {bg_card};
        --text-primary: {text_primary};
        --text-secondary: {COLORS["text_secondary"]};
        --font-primary: {FONTS["primary"]};
        --font-mono: {FONTS["monospace"]};
        --border-radius: {LAYOUT["border_radius"]};
        --shadow-md: {LAYOUT["shadow_md"]};
    }}
    
    /* =================================================================
       GLOBAL STYLES
       ================================================================= */
    .stApp {{
        font-family: var(--font-primary);
    }}
    
    /* Hide Streamlit branding and pages navigation */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* Hide the pages directory navigation (shows 'app', 'EMERGENCY_RECOVERY') */
    [data-testid="stSidebarNav"] {{
        display: none !important;
    }}
    
    /* =================================================================
       SIDEBAR STYLING - Engineering Dark Theme
       ================================================================= */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {COLORS["bg_dark"]} 0%, {COLORS["bg_darker"]} 100%);
        border-right: 1px solid rgba(255,255,255,0.1);
    }}
    
    [data-testid="stSidebar"] * {{
        color: {COLORS["text_inverse"]} !important;
    }}
    
    [data-testid="stSidebar"] .stSelectbox label,
    [data-testid="stSidebar"] .stNumberInput label,
    [data-testid="stSidebar"] .stTextInput label {{
        color: {COLORS["text_muted"]} !important;
        font-size: {FONT_SIZES["sm"]};
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    
    [data-testid="stSidebar"] .stSelectbox > div > div,
    [data-testid="stSidebar"] .stNumberInput > div > div > input,
    [data-testid="stSidebar"] .stTextInput > div > div > input {{
        background-color: rgba(255,255,255,0.08) !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        border-radius: var(--border-radius);
        color: {COLORS["text_inverse"]} !important;
    }}
    
    [data-testid="stSidebar"] .stSelectbox > div > div:hover,
    [data-testid="stSidebar"] .stNumberInput > div > div > input:hover,
    [data-testid="stSidebar"] .stTextInput > div > div > input:hover {{
        border-color: var(--color-primary) !important;
    }}
    
    /* Sidebar section headers */
    [data-testid="stSidebar"] .sidebar-section-header {{
        color: var(--color-primary-light) !important;
        font-size: {FONT_SIZES["sm"]};
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 1rem 0 0.5rem 0;
        border-bottom: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 0.75rem;
    }}
    
    /* Sidebar buttons (including Logout) - Make them visible */
    [data-testid="stSidebar"] .stButton > button {{
        background: linear-gradient(135deg, #ff6b35 0%, #e55a2b 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        border-radius: var(--border-radius) !important;
        transition: all 0.2s ease !important;
        width: 100% !important;
        margin-top: 0.5rem !important;
    }}
    
    [data-testid="stSidebar"] .stButton > button:hover {{
        background: linear-gradient(135deg, #ff8555 0%, #ff6b35 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(255, 107, 53, 0.4) !important;
    }}
    
    /* =================================================================
       SIDEBAR EXPANDER - Premium Navigation Style
       ================================================================= */
    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        background: transparent !important;
        border: none !important;
        margin: 0.5rem 0 !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stExpander"] > details {{
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        overflow: hidden !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stExpander"] > details > summary {{
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.15) 0%, rgba(0, 90, 180, 0.1) 100%) !important;
        padding: 0.875rem 1rem !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05) !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stExpander"] > details > summary:hover {{
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.25) 0%, rgba(0, 90, 180, 0.15) 100%) !important;
    }}
    
    [data-testid="stSidebar"] [data-testid="stExpander"] > details[open] > summary {{
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.2) 0%, rgba(0, 90, 180, 0.12) 100%) !important;
        border-radius: 12px 12px 0 0 !important;
    }}
    
    /* Expander content area - 2-column grid for better space usage */
    [data-testid="stSidebar"] [data-testid="stExpander"] > details > div {{
        background: rgba(0, 0, 0, 0.15) !important;
        padding: 0.75rem !important;
    }}
    
    /* Make button container use grid layout for 2-column arrangement */
    [data-testid="stSidebar"] [data-testid="stExpander"] > details > div > div {{
        display: grid !important;
        grid-template-columns: repeat(2, 1fr) !important;
        gap: 8px !important;
    }}
    
    /* =================================================================
       SIDEBAR NAV BUTTONS - HIGH-VISIBILITY ACTION CARDS
       ================================================================= */
    [data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button {{
        /* Card styling with rounded corners and lighter background */
        background: rgba(255, 255, 255, 0.08) !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-radius: 10px !important;
        
        /* Generous padding for clear hit target (12px+) */
        padding: 14px 12px !important;
        margin: 0 !important;
        
        /* Typography - 1rem bold */
        text-align: center !important;
        font-weight: 700 !important;
        font-size: 1rem !important;
        line-height: 1.3 !important;
        letter-spacing: 0.01em !important;
        color: rgba(255, 255, 255, 0.95) !important;
        
        /* Icon sizing - make icons 50% larger via font-size inheritance */
        /* Icons will be ~1.5x larger due to parent font-size increase */
        
        /* Smooth transitions for hover/active states */
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2) !important;
        
        /* Ensure proper sizing in grid */
        width: 100% !important;
        min-height: 60px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }}
    
    /* HOVER STATE - Bright accent border and color shift */
    [data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button:hover {{
        background: rgba(77, 166, 255, 0.15) !important;
        border: 2px solid {COLORS["primary_light"]} !important;
        color: white !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 4px 12px rgba(77, 166, 255, 0.3) !important;
    }}
    
    /* ACTIVE/SELECTED STATE - Clear visual distinction */
    [data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, rgba(0, 200, 83, 0.25) 0%, rgba(0, 150, 60, 0.15) 100%) !important;
        border: 2px solid {COLORS["accent_green"]} !important;
        color: {COLORS["accent_green"]} !important;
        font-weight: 700 !important;
        box-shadow: 0 0 12px rgba(0, 200, 83, 0.3), 0 2px 8px rgba(0, 0, 0, 0.2) !important;
    }}
    
    /* Active button hover - slight enhancement */
    [data-testid="stSidebar"] [data-testid="stExpander"] .stButton > button[kind="primary"]:hover {{
        background: linear-gradient(135deg, rgba(0, 200, 83, 0.35) 0%, rgba(0, 150, 60, 0.2) 100%) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 0 16px rgba(0, 200, 83, 0.4), 0 4px 12px rgba(0, 0, 0, 0.25) !important;
    }}
    
    /* =================================================================
       SIDEBAR NAVIGATION - Professional Commercial Style
       ================================================================= */
    /* Style the radio button group as sleek navigation */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div {{
        display: flex;
        flex-direction: column;
        gap: 4px;
    }}
    
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label {{
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 8px;
        padding: 10px 14px;
        margin: 0;
        cursor: pointer;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        align-items: center;
        font-weight: 500;
        font-size: 0.9rem;
        letter-spacing: 0.01em;
        position: relative;
        overflow: hidden;
    }}
    
    /* Hide the default radio circle */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label > div:first-child {{
        display: none !important;
    }}
    
    /* Hover effect */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label:hover {{
        background: rgba(255, 255, 255, 0.08);
        border-color: rgba(77, 166, 255, 0.3);
        transform: translateX(4px);
    }}
    
    /* Selected/Active state */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label[data-checked="true"],
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label:has(input:checked) {{
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.15) 0%, rgba(0, 120, 212, 0.08) 100%);
        border-color: {COLORS["primary"]};
        border-left: 3px solid {COLORS["primary"]};
        color: {COLORS["primary_light"]} !important;
    }}
    
    /* Active indicator line animation */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label[data-checked="true"]::before,
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label:has(input:checked)::before {{
        content: '';
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 3px;
        background: linear-gradient(180deg, {COLORS["primary_light"]} 0%, {COLORS["primary"]} 100%);
        border-radius: 0 2px 2px 0;
    }}
    
    /* Icon spacing in nav items */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div > label p {{
        margin: 0;
        padding-left: 4px;
    }}
    
    /* Hide the 'app' label from pages selector */
    [data-testid="stSidebarNav"] {{
        display: none !important;
    }}
    
    /* =================================================================
       MAIN CANVAS AREA - Graph Paper Background
       ================================================================= */
    .main-canvas {{
        background-color: {bg_canvas};
        background-image: 
            linear-gradient({grid_line} 1px, transparent 1px),
            linear-gradient(90deg, {grid_line} 1px, transparent 1px),
            linear-gradient({grid_major} 1px, transparent 1px),
            linear-gradient(90deg, {grid_major} 1px, transparent 1px);
        background-size: 10px 10px, 10px 10px, 50px 50px, 50px 50px;
        border-radius: var(--border-radius);
        border: 1px solid {grid_major};
        min-height: 600px;
        padding: 1rem;
    }}
    
    /* =================================================================
       CARD COMPONENTS
       ================================================================= */
    .engineering-card {{
        background: {bg_card};
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-md);
        padding: 1.25rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(0,0,0,0.08);
    }}
    
    .engineering-card-header {{
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid var(--color-primary);
    }}
    
    .engineering-card-title {{
        font-size: {FONT_SIZES["lg"]};
        font-weight: 600;
        color: {text_primary};
        margin: 0;
    }}
    
    /* =================================================================
       SYSTEM HEALTH / QUICK STATS CARD
       ================================================================= */
    .system-health-card {{
        background: linear-gradient(135deg, {COLORS["bg_dark"]} 0%, {COLORS["bg_darker"]} 100%);
        border-radius: var(--border-radius);
        padding: 1.5rem;
        color: {COLORS["text_inverse"]};
        border-left: 4px solid var(--color-primary);
    }}
    
    .system-health-title {{
        font-size: {FONT_SIZES["sm"]};
        text-transform: uppercase;
        letter-spacing: 1px;
        color: {COLORS["text_muted"]};
        margin-bottom: 0.5rem;
    }}
    
    .system-health-value {{
        font-family: var(--font-mono);
        font-size: {FONT_SIZES["3xl"]};
        font-weight: 700;
        color: {COLORS["text_inverse"]};
        line-height: 1.2;
    }}
    
    .system-health-unit {{
        font-size: {FONT_SIZES["lg"]};
        color: {COLORS["text_muted"]};
        margin-left: 0.25rem;
    }}
    
    .system-health-status {{
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: {FONT_SIZES["sm"]};
        font-weight: 500;
        margin-top: 0.5rem;
    }}
    
    .status-ok {{
        background: rgba(0, 200, 83, 0.2);
        color: {COLORS["status_ok"]};
    }}
    
    .status-warning {{
        background: rgba(255, 152, 0, 0.2);
        color: {COLORS["status_warning"]};
    }}
    
    .status-error {{
        background: rgba(244, 67, 54, 0.2);
        color: {COLORS["status_error"]};
    }}
    
    /* =================================================================
       TOOLBAR BUTTONS - CAD Style
       ================================================================= */
    .toolbar-container {{
        display: flex;
        gap: 0.5rem;
        padding: 0.75rem;
        background: {bg_card};
        border-radius: var(--border-radius);
        border: 1px solid rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }}
    
    .stButton > button {{
        font-family: var(--font-primary);
        font-weight: 500;
        border-radius: var(--border-radius);
        transition: all 0.2s ease;
    }}
    
    .stButton > button:hover {{
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }}
    
    /* Primary action buttons */
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, var(--color-primary) 0%, var(--color-primary-dark) 100%);
        border: none;
    }}
    
    /* Tool buttons (active state) */
    .tool-active > div > button {{
        background: var(--color-primary) !important;
        color: white !important;
        border: 2px solid var(--color-primary-dark) !important;
        box-shadow: 0 0 0 3px rgba(0, 120, 212, 0.3);
    }}
    
    /* =================================================================
       INPUT VALIDATION STYLES
       ================================================================= */
    .validation-error {{
        color: {COLORS["accent_red"]};
        font-size: {FONT_SIZES["sm"]};
        margin-top: 0.25rem;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }}
    
    .validation-error::before {{
        content: "⚠";
    }}
    
    .validation-warning {{
        color: {COLORS["accent_orange"]};
        font-size: {FONT_SIZES["sm"]};
        margin-top: 0.25rem;
        display: flex;
        align-items: center;
        gap: 0.25rem;
    }}
    
    .input-invalid {{
        border-color: {COLORS["accent_red"]} !important;
        box-shadow: 0 0 0 2px rgba(244, 67, 54, 0.2) !important;
    }}
    
    /* =================================================================
       METRIC DISPLAYS - Technical Data
       ================================================================= */
    [data-testid="stMetric"] {{
        background: {bg_card};
        padding: 1rem;
        border-radius: var(--border-radius);
        border: 1px solid rgba(0,0,0,0.08);
    }}
    
    [data-testid="stMetric"] label {{
        font-size: {FONT_SIZES["sm"]};
        text-transform: uppercase;
        letter-spacing: 0.5px;
        color: var(--text-secondary);
    }}
    
    [data-testid="stMetric"] [data-testid="stMetricValue"] {{
        font-family: var(--font-mono);
        font-weight: 600;
    }}
    
    /* =================================================================
       TOAST NOTIFICATIONS
       ================================================================= */
    .toast-container {{
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
    }}
    
    .toast {{
        padding: 1rem 1.5rem;
        border-radius: var(--border-radius);
        box-shadow: var(--shadow-lg);
        display: flex;
        align-items: center;
        gap: 0.75rem;
        animation: slideIn 0.3s ease;
        max-width: 400px;
    }}
    
    .toast-success {{
        background: {COLORS["accent_green"]};
        color: white;
    }}
    
    .toast-error {{
        background: {COLORS["accent_red"]};
        color: white;
    }}
    
    .toast-warning {{
        background: {COLORS["accent_orange"]};
        color: white;
    }}
    
    .toast-info {{
        background: {COLORS["status_info"]};
        color: white;
    }}
    
    @keyframes slideIn {{
        from {{
            transform: translateX(100%);
            opacity: 0;
        }}
        to {{
            transform: translateX(0);
            opacity: 1;
        }}
    }}
    
    /* =================================================================
       DEVELOPER MODE BADGE
       ================================================================= */
    .dev-mode-badge {{
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        background: rgba(255, 107, 53, 0.2);
        color: {COLORS["accent_orange"]};
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: {FONT_SIZES["xs"]};
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}
    
    .dev-log {{
        background: {COLORS["bg_darker"]};
        color: {COLORS["accent_green"]};
        font-family: var(--font-mono);
        font-size: {FONT_SIZES["xs"]};
        padding: 0.5rem 0.75rem;
        border-radius: var(--border-radius);
        margin: 0.25rem 0;
        border-left: 3px solid {COLORS["accent_green"]};
    }}
    
    /* =================================================================
       EXPANDER STYLING
       ================================================================= */
    .streamlit-expanderHeader {{
        font-weight: 600;
        font-size: {FONT_SIZES["base"]};
    }}
    
    /* =================================================================
       TABLE STYLING - Technical Data
       ================================================================= */
    .stDataFrame {{
        font-family: var(--font-mono);
    }}
    
    .stDataFrame th {{
        background: {COLORS["bg_dark"]} !important;
        color: {COLORS["text_inverse"]} !important;
        font-weight: 600;
        text-transform: uppercase;
        font-size: {FONT_SIZES["xs"]};
        letter-spacing: 0.5px;
    }}
    
    /* =================================================================
       MAIN HEADER STYLING
       ================================================================= */
    .main-header {{
        font-size: {FONT_SIZES["3xl"]};
        font-weight: 700;
        color: {COLORS["primary"]};
        margin-bottom: 0.5rem;
    }}
    
    .sub-header {{
        font-size: {FONT_SIZES["xl"]};
        font-weight: 600;
        color: {text_primary};
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }}
    
    /* =================================================================
       INFO/WARNING BOXES - Refined
       ================================================================= */
    .info-box {{
        background: linear-gradient(135deg, rgba(0, 120, 212, 0.08) 0%, rgba(0, 120, 212, 0.04) 100%);
        border: 1px solid rgba(0, 120, 212, 0.2);
        border-left: 4px solid var(--color-primary);
        padding: 1rem 1.25rem;
        border-radius: var(--border-radius);
        margin: 0.75rem 0;
    }}
    
    .warning-box {{
        background: linear-gradient(135deg, rgba(255, 152, 0, 0.08) 0%, rgba(255, 152, 0, 0.04) 100%);
        border: 1px solid rgba(255, 152, 0, 0.2);
        border-left: 4px solid var(--color-warning);
        padding: 1rem 1.25rem;
        border-radius: var(--border-radius);
        margin: 0.75rem 0;
    }}
    
    .success-box {{
        background: linear-gradient(135deg, rgba(0, 200, 83, 0.08) 0%, rgba(0, 200, 83, 0.04) 100%);
        border: 1px solid rgba(0, 200, 83, 0.2);
        border-left: 4px solid var(--color-success);
        padding: 1rem 1.25rem;
        border-radius: var(--border-radius);
        margin: 0.75rem 0;
    }}
    
    .error-box {{
        background: linear-gradient(135deg, rgba(244, 67, 54, 0.08) 0%, rgba(244, 67, 54, 0.04) 100%);
        border: 1px solid rgba(244, 67, 54, 0.2);
        border-left: 4px solid var(--color-error);
        padding: 1rem 1.25rem;
        border-radius: var(--border-radius);
        margin: 0.75rem 0;
    }}
    
    /* =================================================================
       RESPONSIVE ADJUSTMENTS
       ================================================================= */
    @media (max-width: 768px) {{
        .system-health-value {{
            font-size: {FONT_SIZES["2xl"]};
        }}
        
        .main-canvas {{
            min-height: 400px;
        }}
    }}
    
    /* =================================================================
       STREAMLIT TABS - SEGMENTED ACTION TABS / PILL BUTTONS
       ================================================================= */
    /* Tab container - horizontal layout with gap */
    [data-testid="stTabs"] {{
        background: transparent;
    }}
    
    /* Tab list container */
    [data-testid="stTabs"] [role="tablist"] {{
        background: rgba(0, 0, 0, 0.03);
        border-radius: 12px;
        padding: 6px;
        gap: 6px !important;
        border: 1px solid rgba(0, 0, 0, 0.08);
    }}
    
    /* Individual tab buttons - PILL/BUTTON SHAPE */
    [data-testid="stTabs"] [role="tablist"] button {{
        /* Pill shape with rounded corners */
        border-radius: 10px !important;
        border: 2px solid transparent !important;
        
        /* INACTIVE STATE - Subtle gray background */
        background: rgba(108, 117, 125, 0.12) !important;
        
        /* Typography - Larger font size */
        font-size: 1rem !important;
        font-weight: 600 !important;
        letter-spacing: 0.02em !important;
        color: {COLORS["text_secondary"]} !important;
        
        /* Generous padding (10px top/bottom, 20px sides) */
        padding: 12px 24px !important;
        margin: 0 !important;
        
        /* Smooth transitions */
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        
        /* Remove default underline indicator */
        box-shadow: none !important;
    }}
    
    /* Tab button text container */
    [data-testid="stTabs"] [role="tablist"] button p {{
        font-size: 1rem !important;
        font-weight: 600 !important;
        margin: 0 !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }}
    
    /* HOVER STATE for inactive tabs */
    [data-testid="stTabs"] [role="tablist"] button:hover {{
        background: rgba(0, 120, 212, 0.12) !important;
        border-color: rgba(0, 120, 212, 0.3) !important;
        color: {COLORS["primary"]} !important;
        transform: translateY(-1px) !important;
    }}
    
    /* ACTIVE/SELECTED STATE - High contrast solid background */
    [data-testid="stTabs"] [role="tablist"] button[aria-selected="true"] {{
        /* Solid green/blue background with white text */
        background: linear-gradient(135deg, {COLORS["primary"]} 0%, {COLORS["primary_dark"]} 100%) !important;
        border-color: {COLORS["primary_dark"]} !important;
        color: white !important;
        
        /* Elevated appearance */
        box-shadow: 0 4px 12px rgba(0, 120, 212, 0.35), 0 2px 4px rgba(0, 0, 0, 0.1) !important;
        transform: translateY(-1px) !important;
    }}
    
    /* Active tab text - ensure white color */
    [data-testid="stTabs"] [role="tablist"] button[aria-selected="true"] p {{
        color: white !important;
    }}
    
    /* Active tab hover - slight enhancement */
    [data-testid="stTabs"] [role="tablist"] button[aria-selected="true"]:hover {{
        background: linear-gradient(135deg, {COLORS["primary_light"]} 0%, {COLORS["primary"]} 100%) !important;
        box-shadow: 0 6px 16px rgba(0, 120, 212, 0.4), 0 3px 6px rgba(0, 0, 0, 0.12) !important;
    }}
    
    /* Remove the default bottom border indicator line */
    [data-testid="stTabs"] [role="tablist"]::after,
    [data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
        display: none !important;
    }}
    
    /* Tab panel content area */
    [data-testid="stTabs"] [role="tabpanel"] {{
        padding-top: 1.5rem !important;
        border-top: 1px solid rgba(0, 0, 0, 0.08);
        margin-top: 0.75rem;
    }}
    
    /* GREEN VARIANT for specific workflow tabs (Water Requirements) */
    .workflow-tabs [data-testid="stTabs"] [role="tablist"] button[aria-selected="true"] {{
        background: linear-gradient(135deg, {COLORS["accent_green"]} 0%, #16a34a 100%) !important;
        border-color: #16a34a !important;
        box-shadow: 0 4px 12px rgba(0, 200, 83, 0.35), 0 2px 4px rgba(0, 0, 0, 0.1) !important;
    }}
    
    .workflow-tabs [data-testid="stTabs"] [role="tablist"] button[aria-selected="true"]:hover {{
        background: linear-gradient(135deg, #22c55e 0%, {COLORS["accent_green"]} 100%) !important;
        box-shadow: 0 6px 16px rgba(0, 200, 83, 0.4), 0 3px 6px rgba(0, 0, 0, 0.12) !important;
    }}
    </style>
    """


def get_graph_paper_css() -> str:
    """Get CSS specifically for graph paper canvas background."""
    return """
    <style>
    .graph-paper-canvas {
        background-color: #f8fafb;
        background-image: 
            linear-gradient(#e8eef3 1px, transparent 1px),
            linear-gradient(90deg, #e8eef3 1px, transparent 1px),
            linear-gradient(#d0dbe5 1px, transparent 1px),
            linear-gradient(90deg, #d0dbe5 1px, transparent 1px);
        background-size: 10px 10px, 10px 10px, 100px 100px, 100px 100px;
        background-position: -1px -1px, -1px -1px, -1px -1px, -1px -1px;
        border: 2px solid #c8d4e0;
        border-radius: 8px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.06);
    }
    </style>
    """


# =============================================================================
# COMPONENT TEMPLATES
# =============================================================================

def system_health_card(title: str, value: str, unit: str, status: str = "ok") -> str:
    """Generate HTML for a system health metric card."""
    status_class = f"status-{status}"
    status_text = {"ok": "✓ Normal", "warning": "⚠ Check", "error": "✗ Critical"}
    
    return f"""
    <div class="system-health-card">
        <div class="system-health-title">{title}</div>
        <div>
            <span class="system-health-value">{value}</span>
            <span class="system-health-unit">{unit}</span>
        </div>
        <div class="system-health-status {status_class}">{status_text.get(status, status)}</div>
    </div>
    """


def engineering_card(title: str, icon: str, content: str) -> str:
    """Generate HTML for an engineering-style card."""
    return f"""
    <div class="engineering-card">
        <div class="engineering-card-header">
            <span style="font-size: 1.25rem;">{icon}</span>
            <h3 class="engineering-card-title">{title}</h3>
        </div>
        <div class="engineering-card-content">
            {content}
        </div>
    </div>
    """


def validation_message(message: str, level: str = "error") -> str:
    """Generate HTML for inline validation message."""
    css_class = "validation-error" if level == "error" else "validation-warning"
    return f'<div class="{css_class}">{message}</div>'


def dev_mode_badge() -> str:
    """Generate HTML for developer mode indicator badge."""
    return '<span class="dev-mode-badge">🔧 Dev Mode</span>'
