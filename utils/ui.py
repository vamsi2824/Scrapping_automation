import re
import streamlit as st
from pathlib import Path

# ============================================================
# HTML FLATTENER (THE FIX)
# ============================================================
def safe_html(html_str: str):
    """
    Safely renders HTML in Streamlit by stripping all leading indentation 
    and squashing newlines. This prevents Streamlit's Markdown parser 
    from accidentally turning indented HTML tags into code blocks.
    """
    # Remove leading spaces from each line
    no_indent = re.sub(r'^[ \t]+', '', html_str, flags=re.MULTILINE)
    # Replace newlines with spaces to create one continuous HTML string
    single_line = no_indent.replace('\n', ' ')
    st.markdown(single_line, unsafe_allow_html=True)

# ============================================================
# ICON SYSTEM
# ============================================================
ICON_PATH = {
    "sliders-horizontal": """
        <svg viewBox="0 0 24 24">
            <line x1="4" y1="6" x2="20" y2="6"/>
            <line x1="4" y1="12" x2="20" y2="12"/>
            <line x1="4" y1="18" x2="20" y2="18"/>
            <circle cx="8" cy="6" r="2"/>
            <circle cx="16" cy="12" r="2"/>
            <circle cx="10" cy="18" r="2"/>
        </svg>
    """,
    "building-2": """
        <svg viewBox="0 0 24 24">
            <path d="M4 21V5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v16"/>
            <path d="M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2"/>
            <path d="M10 21v-3h4v3"/>
        </svg>
    """,
    "calendar-days": """
        <svg viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="17" rx="2"/>
            <line x1="16" y1="2" x2="16" y2="6"/>
            <line x1="8" y1="2" x2="8" y2="6"/>
            <line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
    """,
    "shield-check": """
        <svg viewBox="0 0 24 24">
            <path d="M12 3l8 4v5c0 5-3.5 8-8 9-4.5-1-8-4-8-9V7l8-4z"/>
            <path d="M8.5 12l2.2 2.2 4.8-5"/>
        </svg>
    """,
    "table-2": """
        <svg viewBox="0 0 24 24">
            <rect x="3" y="3" width="18" height="18" rx="2"/>
            <line x1="3" y1="9" x2="21" y2="9"/>
            <line x1="3" y1="15" x2="21" y2="15"/>
            <line x1="9" y1="3" x2="9" y2="21"/>
        </svg>
    """,
    "database": """
        <svg viewBox="0 0 24 24">
            <ellipse cx="12" cy="5" rx="8" ry="3"/>
            <path d="M4 5v7c0 2 3.6 3 8 3s8-1 8-3V5"/>
            <path d="M4 12v7c0 2 3.6 3 8 3s8-1 8-3v-7"/>
        </svg>
    """,
    "circle-check": """
        <svg viewBox="0 0 24 24">
            <circle cx="12" cy="12" r="9"/>
            <path d="M8 12l2.5 2.5L16 9"/>
        </svg>
    """,
}

def icon(name: str) -> str:
    svg = ICON_PATH.get(name, "")
    return f'<span class="icon">{svg}</span>'

# ============================================================
# THEME
# ============================================================
def apply_saas_theme():
    css_path = Path(__file__).parent.parent / "assets" / "style.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ============================================================
# HEADER
# ============================================================
def render_header(title: str, subtitle: str, badge_text: str = None, badge_type: str = "neutral"):
    badge_html = ""
    if badge_text:
        badge_html = f"""
            <div class="page-status {badge_type}">
                <span class="status-dot"></span>
                {badge_text}
            </div>
        """

    safe_html(f"""
        <div class="page-header">
            <div class="page-header-main">
                <div class="page-icon">
                    {icon("table-2")}
                </div>
                <div>
                    <div class="breadcrumb">
                        Operations Hub
                        <span>/</span>
                        Reconciliation
                    </div>
                    <h1>{title}</h1>
                    <p>{subtitle}</p>
                </div>
            </div>
            {badge_html}
        </div>
    """)

# ============================================================
# KPI
# ============================================================
def render_kpi_card(label: str, value: str, icon_name: str = "database"):
    safe_html(f"""
        <div class="kpi-card">
            <div class="kpi-icon">
                {icon(icon_name)}
            </div>
            <div class="kpi-content">
                <span class="metric-label">{label}</span>
                <span class="metric-value">{value}</span>
            </div>
        </div>
    """)