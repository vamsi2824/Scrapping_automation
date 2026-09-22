
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
from automations.callidus_recon import execute_recon
from utils.ai import stream_store_performance

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Callidus Recon | Operations Hub",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_saas_theme()
cleanup_stale_workspaces()
load_dotenv()

st.sidebar.markdown("""

""", unsafe_allow_html=True)

# ============================================================
# SESSION STATE
# ============================================================
if "job_running" not in st.session_state:
    st.session_state.job_running = False
if "recon_file_path" not in st.session_state:
    st.session_state.recon_file_path = None
if "recon_df" not in st.session_state:
    st.session_state.recon_df = None
if "ai_insight" not in st.session_state:
    st.session_state.ai_insight = None

# ============================================================
# LOAD CLIENT DATA
# ============================================================
with open("clients.json", "r") as f:
    ALL_CLIENT_DATA = json.load(f)

# ============================================================
# HEADER
# ============================================================
render_header(
    title="Callidus Reconciliation",
    subtitle="Extract, consolidate and review multi-store commission statements.",
    badge_text="Processing" if st.session_state.job_running else "Ready",
    badge_type="warning" if st.session_state.job_running else "success",
)

# ============================================================
# WORKSPACE CONFIGURATION
# ============================================================
safe_html(f"""
    <div class="section-eyebrow">
        {icon("sliders-horizontal")}
        WORKSPACE CONFIGURATION
    </div>
""")

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
        if isinstance(selected_range, tuple):
            start_date = selected_range[0]
            end_date = selected_range[1] if len(selected_range) > 1 else selected_range[0]
        else:
            start_date, end_date = selected_range, selected_range

    active_stores = ALL_CLIENT_DATA.get(client_choice, [])
    store_map = {store["name"]: store for store in active_stores}

    selected_names = st.multiselect(
        "Target stores",
        options=list(store_map.keys()),
        placeholder="All stores (leave empty to include every store)",
    )

    target_stores = [store_map[name] for name in selected_names] if selected_names else active_stores

    safe_html(f"""
        <div class="selection-summary">
            <div class="selection-item">
                {icon("building-2")}
                <span>
                    <strong>{len(target_stores)}</strong>
                    stores selected
                </span>
            </div>
            <div class="selection-divider"></div>
            <div class="selection-item">
                {icon("calendar-days")}
                <span>
                    <strong>{start_date.strftime("%b %d, %Y")}</strong>
                    to
                    <strong>{end_date.strftime("%b %d, %Y")}</strong>
                </span>
            </div>
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

# ============================================================
# ACTION BAR
# ============================================================
action_col, info_col = st.columns([1, 3])

with action_col:
    run_clicked = st.button(
        "Run Reconciliation",
        type="primary",
        disabled=(st.session_state.job_running or not active_user),
        use_container_width=True,
    )

with info_col:
    safe_html(f"""
        <div class="execution-info">
            {icon("shield-check")}
            <div>
                <strong>Secure workspace</strong>
                <span>
                    Credentials remain server-side and are never exposed
                    in the browser.
                </span>
            </div>
        </div>
    """)

# ============================================================
# EXECUTION ENGINE
# ============================================================
if run_clicked:
    st.session_state.job_running = True
    st.session_state.recon_file_path = None
    st.session_state.recon_df = None
    st.session_state.ai_insight = None # Reset AI insight on new run

    workspace = create_job_workspace()
    
    progress_bar = st.progress(0, text="Initializing workflow...")

    def ui_progress_callback(current, total, message):
        fraction = current / total if total > 0 else 0
        progress_bar.progress(fraction, text=f"[{current}/{total} stores] {message}")

    try:
        output_file = execute_recon(
            username=active_user,
            password=active_pass,
            stores=target_stores,
            start_date=start_date.strftime("%m/%d/%Y"),
            end_date=end_date.strftime("%m/%d/%Y"),
            workspace_dir=workspace,
            log_fn=None,
            progress_fn=ui_progress_callback
        )

        st.session_state.recon_file_path = str(output_file)
        df = pd.read_excel(output_file, sheet_name="Recon Data")
        st.session_state.recon_df = df
        
        progress_bar.progress(1.0, text="Reconciliation successfully generated.")

    except Exception as e:
        progress_bar.progress(1.0, text=f"Execution failed: {str(e)}")
        st.error(f"Error: {e}")

    finally:
        st.session_state.job_running = False

# ============================================================
# RESULTS & AI INSIGHTS
# ============================================================
if st.session_state.recon_df is None and not st.session_state.job_running:
    safe_html(f"""
        <div class="empty-state">
            <div class="empty-state-icon">{icon("table-2")}</div>
            <h3>No data generated</h3>
            <p>Select a client workspace and run the reconciliation to view interactive data, charts, and exports.</p>
        </div>
    """)

elif st.session_state.recon_df is not None:
    df = st.session_state.recon_df
    total_commission = df['compmrc'].sum() if 'compmrc' in df.columns else 0

    safe_html(f"""
        <div class="section-header">
            <div>
                <div class="section-eyebrow">
                    {icon("table-2")}
                    RECONCILIATION RESULTS
                </div>
                <h2>Review your reconciliation data</h2>
            </div>
            <div class="result-count">
                <strong>{len(df):,}</strong>
                <span>records</span>
            </div>
        </div>
    """)

    # KPI ROW
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        render_kpi_card("Total Commission", f"${total_commission:,.2f}", "database")
    with k2:
        render_kpi_card("Total Records", f"{len(df):,}", "table-2")
    with k3:
        render_kpi_card("Stores Synced", f"{df['Store ID'].nunique():,}" if "Store ID" in df.columns else "—", "building-2")
    with k4:
        render_kpi_card("Status", "Completed", "circle-check")
        
    st.write("") 

    # PREMIUM SAAS CHART
    if 'compmrc' in df.columns and 'Store Name' in df.columns:
        with st.container(border=True):
            chart_df = df.groupby('Store Name')['compmrc'].sum().reset_index()
            chart_df = chart_df.sort_values(by='compmrc', ascending=False).head(15)
            
            fig = px.bar(
                chart_df,
                x='Store Name',
                y='compmrc',
                title="<b>Commission Output Analytics</b><br><span style='font-size:13px;color:#64748B'>Top 15 trailing locations (Revenue vs. Store)</span>",
            )
            
            fig.update_layout(
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(family="Inter, sans-serif", color="#0F172A"),
                title_font=dict(size=18, color="#0F172A"),
                margin=dict(l=10, r=10, t=60, b=10),
                showlegend=False,
                xaxis=dict(showgrid=False, title="", tickangle=-45, linecolor='#E2E8F0'),
                yaxis=dict(showgrid=True, title="", gridcolor='#F1F5F9', griddash='dash', zeroline=False),
                hovermode="x unified"
            )
            
            fig.update_traces(
                marker_color='#9564dd', 
                marker_line_color='#3e0f8d',
                marker_line_width=1.5, 
                opacity=0.9, 
                width=0.4
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
# --- AI INSIGHTS GENERATOR (STREAMED & PERSISTED) ---
            st.write("")
            ai_col, _ = st.columns([1, 2])
            with ai_col:
                generate_ai = st.button(
                    "Generate AI Executive Summary", 
                    use_container_width=True
                )

            if generate_ai or st.session_state.ai_insight:
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
                        # Stream live into UI and persist the full response into session state
                        st.session_state.ai_insight = st.write_stream(stream_store_performance(df))
                    else:
                        st.markdown(st.session_state.ai_insight)
    # DATA TABLE & EXPORTS
    with st.container(border=True):
        col_config = {
            "compmrc": st.column_config.NumberColumn("Commission ($)", format="$ %.2f"),
            "Store Name": st.column_config.TextColumn("Store Name", width="medium"),
        }
        
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=False,
            height=400,
            column_config=col_config
        )

        footer_left, footer_mid, footer_right = st.columns([2, 1, 1])
        with footer_left:
            safe_html(f"""
                <div class="table-footer" style="padding-top: 5px;">
                    Showing <strong>{len(df):,}</strong> records
                </div>
            """)
        
        with footer_mid:
            csv_data = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                label="Export CSV",
                data=csv_data,
                file_name="recon_export.csv",
                mime="text/csv",
                use_container_width=True,
            )
        
        with footer_right:
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Recon Data')
            st.download_button(
                label="Export Excel",
                data=excel_buffer.getvalue(),
                file_name="recon_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )