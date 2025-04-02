import streamlit as st
import pandas as pd
import plotly.io as pio
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime
from io import BytesIO
import base64
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch

st.set_page_config(page_title="DOGE Grants Dashboard", layout="wide")

# --- Load Data from DOGE API ---
@st.cache_data
def get_grant_savings():
    DOGE_API_BASE = "https://api.doge.gov"
    ENDPOINT = "/savings/grants"
    PER_PAGE = 500
    page = 1
    all_grants = []

    while True:
        url = f"{DOGE_API_BASE}{ENDPOINT}"
        params = {
            "sort_by": "savings",
            "sort_order": "desc",
            "page": page,
            "per_page": PER_PAGE,
        }
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if not data.get("success"):
                break
            grants = data["result"].get("grants", [])
            if not grants:
                break
            all_grants.extend(grants)
            page += 1
        except:
            break

    df = pd.DataFrame(all_grants)
    date_col = "deleted_date" if "deleted_date" in df.columns else "date"
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df["savings"] = pd.to_numeric(df["savings"], errors="coerce")
    df["month"] = df[date_col].dt.to_period("M")
    df["weekday"] = df[date_col].dt.day_name()
    df["date_col"] = df[date_col]  # Used for plotting
    return df

# --- Load and process data ---
df = get_grant_savings()

# --- Sidebar Filters ---
st.sidebar.header("\U0001F50D Filter Data")
if "agency" in df.columns:
    agencies = st.sidebar.multiselect("Select Agencies", options=df["agency"].dropna().unique())
    if agencies:
        df = df[df["agency"].isin(agencies)]

# --- Metrics ---
total_savings = df["savings"].sum()
total_records = len(df)
top_agency = df.groupby("agency")["savings"].sum().idxmax() if "agency" in df.columns else "N/A"
most_common_weekday = df["weekday"].value_counts().idxmax()

# --- Layout ---
st.title("Government Grants Cancellations Dashboard")
st.markdown("Analyze grants savings from the Department of Government Efficiency (DOGE) API")

# --- Download Button ---
st.download_button(
    label="\U0001F4C5 Download Data as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="doge_grant_savings.csv",
    mime="text/csv"
)

# --- Key Metrics ---
st.markdown("### \U0001F4CA Key Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("\U0001F4B0 Total Savings", f"${total_savings:,.0f}")
col2.metric("\U0001F4C4 Total Canceled Grants", total_records)
col3.metric("\U0001F3DB Top Saving Agency", top_agency)
st.metric("\U0001F4C6 Most Common Cancellation Day", most_common_weekday)

# --- Charts Layout ---
row1_col1, row1_col2 = st.columns(2)

with row1_col1:
    st.markdown("#### Top 10 Agencies by Total Savings")
    agency_savings = df.groupby("agency")["savings"].sum().sort_values(ascending=False).head(10)
    fig1 = go.Figure(go.Bar(
        x=agency_savings.values,
        y=agency_savings.index,
        orientation='h',
        marker_color='steelblue'
    ))
    fig1.update_layout(
        title="Top 10 Agencies by Total Savings",
        xaxis_title="Total Savings ($)",
        yaxis=dict(title='Agency', autorange="reversed"),
        height=400
    )
    st.plotly_chart(fig1, use_container_width=True)
    pio.write_image(fig1, "top_agencies.png")
    
with row1_col2:
    st.markdown("#### Avg. Savings per Grant (Top 10 Agencies)")
    avg_savings = df.groupby("agency")["savings"].mean().sort_values(ascending=False).head(10)
    fig = px.bar(
        avg_savings,
        x=avg_savings.values,
        y=avg_savings.index,
        orientation='h',
        labels={"x": "Avg. Savings ($)", "y": "Agency"},
        height=400,
        title="High-Impact Agencies: Avg. Savings per Grant"
    )
    st.plotly_chart(fig, use_container_width=True)
    pio.write_image(fig, "avg_savings_per_grant.png")    

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.markdown("#### Monthly Savings Trend")
    monthly_trend = df.groupby("month")["savings"].sum().reset_index()
    monthly_trend["month"] = monthly_trend["month"].astype(str)
    fig3 = px.line(
        monthly_trend,
        x="month",
        y="savings",
        markers=True,
        labels={"month": "Month", "savings": "Savings ($)"},
        title="Monthly Savings Trend",
        height=400
    )
    st.plotly_chart(fig3, use_container_width=True)
    pio.write_image(fig3, "monthly_trend.png")

with row2_col2:
    st.markdown("#### Cancellations by Weekday")
    weekday_counts = df["weekday"].value_counts().reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ).fillna(0)
    fig2 = px.bar(
        weekday_counts.reset_index(),
        x="index",
        y="weekday",
        labels={"index": "Weekday", "weekday": "Cancellations"},
        title="Cancellations by Weekday",
        height=400
    )
    st.plotly_chart(fig2, use_container_width=True)
    pio.write_image(fig2, "weekday_counts.png")

# --- PDF Report ---
st.markdown("---")
st.markdown("### \U0001F4D1 Downloadable PDF Report")

pdf_output_path = "DOGE_Grants_Summary.pdf"
c = canvas.Canvas(pdf_output_path, pagesize=LETTER)
width, height = LETTER
margin = 40
line_height = 14
cursor = height - margin

def draw_title(title):
    global cursor
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, cursor, title)
    cursor -= 30

def draw_paragraph(text):
    global cursor
    c.setFont("Helvetica", 12)
    for line in text.split("\n"):
        if cursor <= margin:
            c.showPage()
            cursor = height - margin
            c.setFont("Helvetica", 12)
        c.drawString(margin, cursor, line)
        cursor -= line_height

# Write summary
cursor = height - margin

draw_title("DOGE Grants Savings Dashboard Summary")
draw_paragraph(f"Generated on: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")

draw_title("Key Metrics")
draw_paragraph(
    f"- Total Savings: ${total_savings:,.0f}\n"
    f"- Total Grants Canceled: {total_records}\n"
    f"- Top Saving Agency: {top_agency}\n"
    f"- Most Common Cancellation Day: {most_common_weekday}"
)

# --- Automated Insights ---
draw_title("Automated Insights")

# Insight 1: Top agency savings amount
top_agency_value = df.groupby("agency")["savings"].sum().max()
top_agency_pct = (top_agency_value / total_savings * 100) if total_savings else 0

# Insight 2: Month with highest savings
monthly_savings = df.groupby("month")["savings"].sum()
best_month = monthly_savings.idxmax() if not monthly_savings.empty else "N/A"
best_month_value = monthly_savings.max() if not monthly_savings.empty else 0

# Insight 3: Median vs. Mean savings
median_savings = df["savings"].median()
mean_savings = df["savings"].mean()

insight_text = f"""
- The agency with the highest total savings contributed ${top_agency_value:,.0f}, 
  which is {top_agency_pct:.1f}% of the total.
- The month with the highest grant savings was {best_month}, totaling ${best_month_value:,.0f}.
- The median savings amount is ${median_savings:,.0f}, compared to a mean of ${mean_savings:,.0f}.
  This suggests that a few high-value cancellations may be skewing the average.
"""
draw_paragraph(insight_text)

# Embed exported chart images into PDF
chart_paths = [
    ("Top 10 Agencies by Total Savings", "top_agencies.png"),
    ("Cancellations by Weekday", "weekday_counts.png"),
    ("Monthly Savings Trend", "monthly_trend.png"),
    ("Savings Distribution", "avg_savings_per_grant.png")
]

for title, img_path in chart_paths:
    c.showPage()
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin, height - margin - 10, title)
    c.drawImage(img_path, margin, height / 2 - 100, width=6.5 * inch, preserveAspectRatio=True, mask='auto')

# Save PDF
c.save()

# Download button
with open(pdf_output_path, "rb") as pdf_file:
    st.download_button(
        label="\U0001F4C4 Download PDF Report",
        data=pdf_file.read(),
        file_name="DOGE_Grants_Summary.pdf",
        mime="application/pdf"
    )
