import streamlit as st

st.set_page_config(page_title="Welcome to DOGE Dashboard", layout="centered")

st.title("🏛️ DOGE Savings Dashboards")
st.markdown("#### Data Transparency for Smarter Government")

st.markdown(
    """
**DOGE Savings Dashboards** is a fully integrated, end-to-end data analytics platform that delivers real-time insights into U.S. government cost savings from contract and grant cancellations.

Built using **Python**, **Streamlit**, and the **DOGE API (Department of Government Efficiency)**, this dashboard automates the full analytics pipeline:
- 🔄 Live data ingestion from federal endpoints
- 🧹 Real-time cleaning and transformation
- 📊 Interactive visualizations for exploration
- 🧠 Automated insights generation
- 📄 One-click PDF reporting with embedded charts
"""
)

st.markdown("### 📊 Explore Dashboards")
st.markdown("- **Contracts**: Analyze canceled contracts and top saving agencies/vendors")
st.markdown("- **Grants**: Monitor revoked grants and trends across time")
# st.markdown("- **Payments** *(coming soon)*: Analyze federal disbursements")

st.markdown("---")

st.info("Use the left sidebar to navigate between dashboards.")

st.markdown(
    """
**Ideal for**: analysts, auditors, transparency advocates, and policy teams  
📥 Export reports • 🧠 Auto-generated insights • 🕵️ Reproducible pipeline
"""
)

st.caption("Built with ❤️ by Richie Garafola • Powered by the DOGE API (Beta)")
