import os
import streamlit as st
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv
from supabase import create_client, Client

# Page layout setup
st.set_page_config(
    page_title="TechPulse • GitHub Market Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Injection for Commercial Dark Theme UI
st.markdown("""
<style>
    /* Dark Theme Custom Styling */
    .stApp {
        background-color: #0e1117;
    }
    .metric-card {
        background: linear-gradient(135deg, rgba(255,255,255,0.05) 0%, rgba(255,255,255,0.01) 100%);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
    }
    .metric-title {
        color: #8b949e;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        color: #f0f6fc;
        font-size: 1.8rem;
        font-weight: 700;
        margin-top: 5px;
    }
    .metric-delta {
        color: #3fb950;
        font-size: 0.85rem;
        margin-top: 4px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

@st.cache_resource
def init_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        st.error("Missing Supabase credentials in environment variables.")
        st.stop()
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

@st.cache_data(ttl=1800)
def load_tech_trends():
    """Fetch core tech stack metrics with date normalization to fix x-axis zoom bugs."""
    response = supabase.table("tech_trends").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    df = pd.DataFrame(response.data)
    
    # Strictly parse snapshot_date as YYYY-MM-DD calendar dates
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    
    # Deduplicate multiple daily runs by keeping the latest entry per tech per day
    if "created_at" in df.columns:
        df = df.sort_values(by="created_at").groupby(["snapshot_date", "tech_name"]).last().reset_index()
    else:
        df = df.groupby(["snapshot_date", "tech_name"]).last().reset_index()
        
    return df

@st.cache_data(ttl=1800)
def load_breakout_repos():
    """Fetch breakout projects with date normalization."""
    response = supabase.table("trending_repos").select("*").execute()
    if not response.data:
        return pd.DataFrame()
    df = pd.DataFrame(response.data)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.date
    return df

# Header Banner
st.title("⚡ TechPulse Market Intelligence")
st.markdown("Real-time open-source telemetry tracking developer adoption, framework market share, and breakout velocity.")

tech_df = load_tech_trends()
breakout_df = load_breakout_repos()

tab1, tab2 = st.tabs(["📊 Ecosystem Market Trends", "🔥 Dynamic Breakout Repos"])

# ==========================================
# TAB 1: CORE TECH STACKS
# ==========================================
with tab1:
    if tech_df.empty:
        st.warning("⚠️ No tech stack data found in Supabase!")
    else:
        latest_date = tech_df["snapshot_date"].max()
        latest_tech = tech_df[tech_df["snapshot_date"] == latest_date].copy()

        # Sidebar Filters
        st.sidebar.header("🎛️ Market Filters")
        categories = ["All Categories"] + list(latest_tech["category"].unique())
        selected_category = st.sidebar.selectbox("Filter Category", categories)

        use_log_scale = st.sidebar.checkbox(
            "Logarithmic Scale", 
            value=False,
            help="Enable to compare smaller high-growth tech alongside giant ecosystems."
        )

        filtered_tech = latest_tech if selected_category == "All Categories" else latest_tech[latest_tech["category"] == selected_category]
        filtered_time_series = tech_df if selected_category == "All Categories" else tech_df[tech_df["category"] == selected_category]

        # Styled KPI Cards
        total_repos = filtered_tech['repo_count'].sum()
        top_tech = filtered_tech.sort_values(by='repo_count', ascending=False).iloc[0]

        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Tracked Tech Stacks</div>
                <div class="metric-value">{len(filtered_tech)}</div>
                <div class="metric-delta">Active Monitoring</div>
            </div>
            """, unsafe_allow_html=True)

        with col2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Total Ecosystem Volume</div>
                <div class="metric-value">{total_repos:,}</div>
                <div class="metric-delta">Public Repositories</div>
            </div>
            """, unsafe_allow_html=True)

        with col3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Dominant Category Leader</div>
                <div class="metric-value">{top_tech['tech_name']}</div>
                <div class="metric-delta">🏆 {top_tech['repo_count']:,} repos</div>
            </div>
            """, unsafe_allow_html=True)

        with col4:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-title">Latest Telemetry Date</div>
                <div class="metric-value">{latest_date.strftime('%b %d, %Y')}</div>
                <div class="metric-delta">Live Supabase Sync</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()

        # --- 📈 MULTI-LINE TIME-SERIES CHART ---
        st.subheader("📈 Adoption Trajectory Over Time (Time-Series)")
        
        time_df = filtered_time_series.sort_values(by="snapshot_date").copy()
        time_df["snapshot_date_str"] = time_df["snapshot_date"].astype(str)

        fig_line = px.line(
            time_df,
            x="snapshot_date_str",
            y="repo_count",
            color="tech_name",
            markers=True,
            log_y=use_log_scale,
            labels={"snapshot_date_str": "Date", "repo_count": "Total Repositories", "tech_name": "Technology"},
            title="Repository Growth Velocity (Click legends to toggle technologies)",
            color_discrete_sequence=px.colors.qualitative.Bold
        )
        fig_line.update_layout(
            height=420,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#f0f6fc"),
            xaxis=dict(type="category", showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig_line, use_container_width=True)

        st.divider()

        # Bar Chart & Pie Chart Row
        col_left, col_right = st.columns([3, 2])

        with col_left:
            st.subheader("📌 Current Developer Mindshare")
            fig_bar = px.bar(
                filtered_tech.sort_values(by="repo_count", ascending=True),
                x="repo_count",
                y="tech_name",
                color="category",
                orientation="h",
                log_x=use_log_scale,
                labels={"tech_name": "", "repo_count": "Total Repositories", "category": "Category"},
                text_auto=".2s",
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_bar.update_layout(
                height=450,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f0f6fc"),
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with col_right:
            st.subheader("🍰 Category Share")
            fig_pie = px.pie(
                filtered_tech,
                names="category",
                values="repo_count",
                hole=0.5,
                color_discrete_sequence=px.colors.qualitative.Pastel
            )
            fig_pie.update_layout(
                height=450,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f0f6fc"),
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        st.divider()

        # Data Table View
        st.subheader("📋 Market Share Data Explorer")
        table_df = filtered_tech.copy()
        table_df["Ecosystem Share (%)"] = (table_df["repo_count"] / table_df["repo_count"].sum() * 100).round(2)
        table_df = table_df.sort_values(by="repo_count", ascending=False)[
            ["tech_name", "category", "repo_count", "Ecosystem Share (%)", "snapshot_date"]
        ]
        
        st.dataframe(
            table_df,
            column_config={
                "tech_name": "Technology Stack",
                "category": "Category",
                "repo_count": st.column_config.NumberColumn("Repository Count", format="%d"),
                "Ecosystem Share (%)": st.column_config.ProgressColumn("Share in View", format="%.2f%%", min_value=0, max_value=100),
                "snapshot_date": "Snapshot Date"
            },
            use_container_width=True,
            hide_index=True
        )

# ==========================================
# TAB 2: DYNAMIC BREAKOUT REPOS
# ==========================================
with tab2:
    st.subheader("🚀 Top Breakout & Emerging GitHub Projects")
    st.markdown("High-velocity repositories created in the **last 30 days**, ranked by community star adoption.")

    if breakout_df.empty:
        st.warning("⚠️ No breakout repo records found!")
    else:
        latest_breakout_date = breakout_df["snapshot_date"].max()
        latest_breakouts = breakout_df[breakout_df["snapshot_date"] == latest_breakout_date].copy()

        col_top_left, col_top_right = st.columns([3, 2])

        with col_top_left:
            st.markdown("##### 📌 Star vs. Fork Velocity")
            fig_scatter = px.scatter(
                latest_breakouts,
                x="stars",
                y="forks",
                size="open_issues",
                color="primary_language",
                hover_name="repo_name",
                hover_data={"description": True, "stars": ":,", "forks": ":,"},
                labels={"stars": "GitHub Stars ⭐", "forks": "Forks 🍴", "primary_language": "Language"},
                color_discrete_sequence=px.colors.qualitative.Bold
            )
            fig_scatter.update_layout(
                height=420,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f0f6fc"),
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)"),
                margin=dict(l=0, r=0, t=10, b=0)
            )
            st.plotly_chart(fig_scatter, use_container_width=True)

        with col_top_right:
            st.markdown("##### 🏆 Top 5 Fast-Rising Breakouts")
            top5_breakouts = latest_breakouts.sort_values(by="stars", ascending=True).tail(5)
            fig_top5 = px.bar(
                top5_breakouts,
                x="stars",
                y="repo_name",
                orientation="h",
                color="primary_language",
                text_auto=".2s",
                labels={"stars": "Stars ⭐", "repo_name": ""}
            )
            fig_top5.update_layout(
                height=420,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#f0f6fc"),
                margin=dict(l=0, r=0, t=10, b=0),
                showlegend=False
            )
            st.plotly_chart(fig_top5, use_container_width=True)

        st.divider()

        st.subheader("⭐ Breakout Repository Explorer")
        display_breakouts = latest_breakouts.sort_values(by="stars", ascending=False)[
            ["repo_name", "stars", "forks", "primary_language", "html_url", "description"]
        ]

        st.dataframe(
            display_breakouts,
            column_config={
                "repo_name": "Repository",
                "stars": st.column_config.NumberColumn("Stars ⭐", format="%d"),
                "forks": st.column_config.NumberColumn("Forks 🍴", format="%d"),
                "primary_language": "Language",
                "html_url": st.column_config.LinkColumn("GitHub Link", display_text="View ↗️"),
                "description": "Description"
            },
            use_container_width=True,
            hide_index=True
        )