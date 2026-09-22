# app.py
import streamlit as st
from utils.ui import apply_saas_theme, render_header, render_kpi_card

st.set_page_config(page_title="Operations Hub", page_icon="⚡", layout="wide")
apply_saas_theme()

render_header(
    title="Operations Automation Hub",
    subtitle="Centralized management and on-demand execution engine.",
    badge_text="System Active",
    badge_type="success"
)

# KPI Row
c1, c2, c3 = st.columns(3)
with c1:
    render_kpi_card("Active Automations", "4")
with c2:
    render_kpi_card("Total Runs Today", "18")
with c3:
    render_kpi_card("Workspace Storage", "Isolated (Disk)")

st.markdown(
    """
    <div class="saas-card">
        <div class="saas-card-header">Select a Tool</div>
        <div class="saas-card-subtitle">Choose an automation workflow from the sidebar navigation to get started.</div>
    </div>
    """,
    unsafe_allow_html=True
)