import os
import io
import json
import calendar
import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

from utils.ui import apply_saas_theme, render_header, render_kpi_card, icon, safe_html
from utils.storage import create_job_workspace, cleanup_stale_workspaces
from automations.metro_kpi import execute_metro_kpi
from utils.ai import stream_metro_kpi_performance

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Metro KPI | Operations Hub",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_saas_theme()
cleanup_stale_workspaces()
load_dotenv()

st.sidebar.markdown("""
    <div class="sidebar-brand">
        <h2>Ops Hub</h2>
    </div>
""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE & CLIENT DATA
# ============================================================
if "metro_running" not in st.session_state: st.session_state.metro_running = False
if "metro_df" not in st.session_state: st.session_state.metro_df = None
if "metro_ai" not in st.session_state: st.session_state.metro_ai = None

with open("clients.json", "r") as f:
    ALL_CLIENT_DATA = json.load(f)

render_header(
    title="Metro KPI Analytics",
    subtitle="Extract, process, and evaluate daily Metro performance metrics.",
    badge_text="Processing" if st.session_state.metro_running else "Ready",
    badge_type="warning" if st.session_state.metro_running else "success",
)

# ============================================================
# WORKSPACE CONFIGURATION (Client & Date Filters)
# ============================================================
safe_html(f"""<div class="section-eyebrow">{icon("sliders-horizontal")} WORKSPACE CONFIGURATION</div>""")

with st.container(border=True):
    client_col, date_col = st.columns(2)
    
    with client_col:
        client_choice = st.selectbox(
            "Client workspace",
            options=list(ALL_CLIENT_DATA.keys())
        )

    with date_col:
        scope_option = st.selectbox(
            "Reporting period",
            ["This Month", "Today", "Yesterday", "Custom Date Range"],
        )

    today = datetime.date.today()

    if scope_option == "This Month":
        start_date = today.replace(day=1)
        end_date = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    elif scope_option == "Today":
        start_date, end_date = today, today
    elif scope_option == "Yesterday":
        yesterday = today - datetime.timedelta(days=1)
        start_date, end_date = yesterday, yesterday
    else:
        selected_range = st.date_input("Custom date range", (today - datetime.timedelta(days=7), today))
        if isinstance(selected_range, tuple) and len(selected_range) == 2:
            start_date, end_date = selected_range
        elif isinstance(selected_range, tuple) and len(selected_range) == 1:
            start_date = end_date = selected_range[0]
        else:
            start_date = end_date = selected_range

    date_list = [start_date + datetime.timedelta(days=x) for x in range((end_date - start_date).days + 1)]

    safe_html(f"""
        <div class="selection-summary">
            <div class="selection-item">{icon("building-2")}<span><strong>{client_choice}</strong></span></div>
            <div class="selection-divider"></div>
            <div class="selection-item">{icon("calendar-days")}<span><strong>{start_date.strftime('%b %d, %Y')}</strong> to <strong>{end_date.strftime('%b %d, %Y')}</strong></span></div>
            <div class="selection-divider"></div>
            <div class="selection-item">{icon("database")}<span><strong>{len(date_list)}</strong> days queued</span></div>
        </div>
    """)

# ============================================================
# CREDENTIAL ROUTING
# ============================================================
if client_choice == "Ampcs":
    active_user = os.getenv("AMPCS_USERNAME")
    active_pass = os.getenv("AMPCS_PASSWORD")
elif client_choice == "Client B":
    active_user = os.getenv("CLIENT_B_USERNAME")
    active_pass = os.getenv("CLIENT_B_PASSWORD")
else:
    active_user, active_pass = None, None

if not active_user or not active_pass:
    st.error(f"Credentials for {client_choice} are missing in the .env file.")
    st.stop()

action_col, info_col = st.columns([1, 3])
with action_col:
    run_clicked = st.button("Run KPI Extraction", type="primary", disabled=st.session_state.metro_running, use_container_width=True)

with info_col:
    safe_html(f"""<div class="execution-info">{icon("shield-check")}<div><strong>Encrypted Execution</strong><span>Credentials remain isolated server-side.</span></div></div>""")

# ============================================================
# EXECUTION ENGINE
# ============================================================
if run_clicked:
    st.session_state.metro_running = True
    st.session_state.metro_df = None
    st.session_state.metro_ai = None
    
    workspace = create_job_workspace()
    progress_bar = st.progress(0, text="Initializing workflow...")

    def ui_progress(current, total, message):
        fraction = current / total if total > 0 else 0
        progress_bar.progress(fraction, text=f"[{current}/{total} days] {message}")

    try:
        df = execute_metro_kpi(active_user, active_pass, date_list, workspace, progress_callback=ui_progress)
        st.session_state.metro_df = df
        progress_bar.progress(1.0, text="KPI Extraction successfully generated.")
    except Exception as e:
        progress_bar.progress(1.0, text=f"Execution failed: {str(e)}")
        st.error(f"Error: {e}")
    finally:
        st.session_state.metro_running = False
        st.rerun()

# ============================================================
# RESULTS & ANALYTICS
# ============================================================
if st.session_state.metro_df is None and not st.session_state.metro_running:
    safe_html(f"""
        <div class="empty-state">
            <div class="empty-state-icon">{icon("table-2")}</div>
            <h3>No data generated</h3>
            <p>Select a date range and run the extraction to view interactive KPI data, charts, and exports.</p>
        </div>
    """)

elif st.session_state.metro_df is not None:
    df = st.session_state.metro_df
    
    total_boxes = df['Boxes'].sum()
    avg_conv = df['Conv %'].mean()
    total_acc = df['Acc $'].sum()
    total_ppd = df['PPD'].sum()

    safe_html(f"""
        <div class="section-header">
            <div>
                <div class="section-eyebrow">{icon("table-2")} METRO KPI RESULTS</div>
                <h2>Review performance metrics</h2>
            </div>
            <div class="result-count"><strong>{len(df):,}</strong><span>records</span></div>
        </div>
    """)

    k1, k2, k3, k4 = st.columns(4)
    with k1: render_kpi_card("Total Boxes", f"{total_boxes:,.0f}", "database")
    with k2: render_kpi_card("Avg Conversion", f"{avg_conv * 100:.1f}%", "table-2")
    with k3: render_kpi_card("Accessory Rev", f"${total_acc:,.2f}", "building-2")
    with k4: render_kpi_card("Total PPD", f"{total_ppd:,.0f}", "circle-check")
        
    st.write("") 

    if 'Boxes' in df.columns and 'Store ID' in df.columns:
        with st.container(border=True):
            chart_df = df.groupby('Store ID')['Boxes'].sum().reset_index()
            chart_df = chart_df.sort_values(by='Boxes', ascending=False).head(15)
            
            fig = px.bar(
                chart_df, x='Store ID', y='Boxes',
                title="<b>Box Volume Analytics</b><br><span style='font-size:13px;color:#64748B'>Top 15 locations by unit volume</span>",
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter, sans-serif", color="#0F172A"),
                title_font=dict(size=18, color="#0F172A"),
                margin=dict(l=10, r=10, t=60, b=10), showlegend=False,
                xaxis=dict(showgrid=False, title="", tickangle=-45, linecolor='#E2E8F0'),
                yaxis=dict(showgrid=True, title="", gridcolor='#F1F5F9', griddash='dash', zeroline=False),
                hovermode="x unified"
            )
            fig.update_traces(marker_color='#9564dd', marker_line_color='#3e0f8d', marker_line_width=1.5, opacity=0.9, width=0.4)
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            
            # --- AI INSIGHTS GENERATOR ---
            st.write("")
            ai_col, _ = st.columns([1, 2])
            with ai_col:
                generate_ai = st.button("Generate AI Executive Summary", use_container_width=True)

            if generate_ai or st.session_state.metro_ai:
                with st.container(border=True):
                    safe_html("""
                        <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
                            <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#9564dd;"></span>
                            <span style="color:#3e0f8d; font-weight:700; font-size:12px; letter-spacing:0.08em; text-transform:uppercase;">
                                AI Performance Insights
                            </span>
                        </div>
                    """)
                    if generate_ai:
                        st.session_state.metro_ai = st.write_stream(stream_metro_kpi_performance(df))
                    else:
                        st.markdown(st.session_state.metro_ai)

    st.write("")

    with st.container(border=True):
        col_config = {
            "Acc $": st.column_config.NumberColumn("Acc $", format="$ %.2f"),
            "Base MRC": st.column_config.NumberColumn("Base MRC", format="$ %.2f"),
            "Conv %": st.column_config.NumberColumn("Conv %", format="%.1f%%"),
            "Month": st.column_config.DateColumn("Date", format="MMM DD, YYYY"),
        }
        
        st.dataframe(df, use_container_width=True, hide_index=False, height=400, column_config=col_config)

        footer_left, footer_mid, footer_right = st.columns([2, 1, 1])
        with footer_left: safe_html(f"""<div class="table-footer" style="padding-top: 5px;">Showing <strong>{len(df):,}</strong> records</div>""")
        
        with footer_mid:
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button("Export CSV", data=csv_data, file_name="metro_kpi.csv", mime="text/csv", use_container_width=True)
        
        with footer_right:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Metro KPI Data')
            st.download_button("Export Excel", data=excel_buffer.getvalue(), file_name="metro_kpi.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)