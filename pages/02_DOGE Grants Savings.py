import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from io import BytesIO
import base64
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
import plotly.io as pio
import re
from fuzzywuzzy import fuzz

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
        
export_charts = st.sidebar.checkbox("📦 Export Charts for PDF?")

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

# In-Memory Chart Export Buffer
chart_images = {}

def render_and_export_chart(fig, caption, key):
    st.plotly_chart(fig, use_container_width=True)
    st.caption(caption)
    if export_charts:
        buffer = BytesIO()
        fig.write_image(buffer, format="png")
        buffer.seek(0)
        chart_images[key] = buffer


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
    render_and_export_chart(fig1, "Top 10 agencies by cumulative savings.", "top_agencies")
    
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
    render_and_export_chart(fig, "Average savings per canceled grant by agency.", "avg_savings")    

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
    render_and_export_chart(fig3, "Total grant savings per month.", "monthly_trend")

with row2_col2:
    st.markdown("#### Cancellations by Weekday")
    weekday_counts = df["weekday"].value_counts().reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ).fillna(0).reset_index()

    # Rename columns so they can be referenced correctly
    weekday_counts.columns = ["weekday", "count"]

    # Now use the new column names for plotting
    fig2 = px.bar(
        weekday_counts,
        x="weekday",
        y="count",
        labels={"weekday": "Weekday", "count": "Cancellations"},
        title="Cancellations by Weekday",
        height=400
    )
    render_and_export_chart(fig2, "Canceled grants by weekday pattern.", "weekday")

    
st.markdown("---")
st.markdown("### 📄 Downloadable PDF Report")

pdf_output_path = f"DOGE_Grants_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
c = canvas.Canvas(pdf_output_path, pagesize=LETTER)
width, height = LETTER
margin = 50
line_height = 16
cursor = height - margin
page_number = 1
footer_text = "Built by Richie Garafola • RichieGarafola@hotmail.com • github.com/RichieGarafola"

def reset_cursor(): global cursor; cursor = height - margin
def draw_title(title):
    global cursor
    c.setFont("Helvetica-Bold", 18)
    c.setFillColor(HexColor("#003366"))
    c.drawString(margin, cursor, title)
    c.setFillColor(HexColor("#000000"))
    cursor -= 30
def draw_divider():
    global cursor
    c.setStrokeColor(HexColor("#888888"))
    c.line(margin, cursor, width - margin, cursor)
    cursor -= 10
def draw_paragraph(text):
    global cursor
    c.setFont("Helvetica", 12)
    for line in text.split("\n"):
        c.drawString(margin, cursor, line)
        cursor -= line_height
def draw_footer():
    global page_number
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(margin, 20, footer_text)
    c.drawRightString(width - margin, 20, f"Page {page_number}")
    page_number += 1

# --- Cover Page ---
c.setFillColor(HexColor("#003366"))
c.setFont("Helvetica-Bold", 24)
c.drawCentredString(width / 2, height - 100, "DOGE Grants Savings Report")
c.setFont("Helvetica", 16)
c.setFillColor(HexColor("#000000"))
c.drawCentredString(width / 2, height - 140, "Department of Government Efficiency")
c.setFont("Helvetica", 12)
c.drawCentredString(width / 2, height - 180, f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
draw_footer()
c.showPage()

# --- Pre-Calculate Metrics ---
top_agency_value = df.groupby("agency")["savings"].sum().max()
top_agency_pct = (top_agency_value / total_savings * 100) if total_savings else 0
monthly_savings = df.groupby("month")["savings"].sum()
best_month = monthly_savings.idxmax()
best_month_value = monthly_savings.max()
median_savings = df["savings"].median()
mean_savings = df["savings"].mean()

# --- BLUF Section ---
reset_cursor()
draw_title("BLUF: Bottom Line Up Front")
draw_divider()

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Total Canceled Savings:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"${total_savings:,.0f} across {total_records} grants")
cursor -= 2 * line_height

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Top Saving Agency:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"{top_agency}")
cursor -= 2 * line_height

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Most Common Cancellation Day:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"{most_common_weekday}")
cursor -= 2 * line_height

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Peak Month of Savings:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"{best_month} — ${best_month_value:,.0f}")
cursor -= 2 * line_height

draw_footer()
c.showPage()

# --- Table of Contents ---
reset_cursor()
draw_title("Table of Contents")
draw_paragraph("1. BLUF\n2. Summary\n3. Automated Insights\n4. Top 20 Agencies\n5. Charts")
draw_footer()
c.showPage()

# --- Summary ---
reset_cursor()
draw_title("Summary")
draw_paragraph("This report summarizes savings from canceled government grants provided by the Department of Government Efficiency.")
cursor -= 10
draw_title("Key Metrics")
draw_paragraph(
    f"- Total Savings: ${total_savings:,.0f}\n"
    f"- Total Grants Canceled: {total_records}\n"
    f"- Top Saving Agency: {top_agency}\n"
    f"- Most Common Cancellation Day: {most_common_weekday}"
)
draw_footer()
c.showPage()

# --- Automated Insights ---
reset_cursor()
draw_title("Automated Insights")
draw_divider()
draw_paragraph(
    f"- {top_agency} contributed the highest total savings (${top_agency_value:,.0f}, {top_agency_pct:.1f}% of total).\n"
    f"- Peak savings occurred in {best_month}, totaling ${best_month_value:,.0f}.\n"
    f"- Median savings: ${median_savings:,.0f}; Mean: ${mean_savings:,.0f} — suggests skewed distribution."
)
draw_footer()
c.showPage()

# --- Top 20 Agencies ---
reset_cursor()
draw_title("Top 20 Agencies by Grant Savings")
draw_divider()
c.setFont("Courier", 11)
top_agencies = df.groupby("agency")["savings"].sum().sort_values(ascending=False).head(20).reset_index()
for _, row in top_agencies.iterrows():
    c.drawString(margin, cursor, f"{row['agency']:<50} ${row['savings']:>15,.0f}")
    cursor -= line_height
draw_footer()
c.showPage()

# --- Chart Captions & Insights ---
chart_titles = {
    "top_agencies": "Top 10 Agencies by Total Savings",
    "avg_savings": "Avg. Savings per Grant (Top 10 Agencies)",
    "monthly_trend": "Monthly Savings Trend",
    "weekday": "Cancellations by Weekday"
}

chart_captions = {
    "top_agencies": "Agencies with the highest total canceled grant savings.",
    "avg_savings": "Average savings per canceled grant shows efficiency concentration.",
    "monthly_trend": "Monthly trends reveal peak periods of cancellation activity.",
    "weekday": "Cancellation activity distributed across the week."
}

chart_insights = {
    "top_agencies": [
        f"- {top_agencies.iloc[0]['agency']} saved ${top_agencies.iloc[0]['savings']:,.0f}.",
        f"- Total Top 10: ${top_agencies['savings'].sum():,.0f}."
    ],
    "avg_savings": [
        f"- Max avg savings: ${df.groupby('agency')['savings'].mean().max():,.0f}.",
        f"- Indicates high-value cancellations in few agencies."
    ],
    "monthly_trend": [
        f"- Peak month: {best_month} (${best_month_value:,.0f}).",
        f"- Avg monthly: ${monthly_savings.mean():,.0f}."
    ],
    "weekday": [
        f"- Most common: {most_common_weekday}.",
        f"- Least: {df['weekday'].value_counts().idxmin()}."
    ]
}

# --- Render Charts in PDF ---
for key, buffer in chart_images.items():
    if key not in chart_titles:
        continue

    reset_cursor()
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - margin, chart_titles[key])

    image_reader = ImageReader(buffer)
    img_width = 6.5 * inch
    img_height = 4.75 * inch
    img_x = margin
    img_y = height - 450

    c.drawImage(image_reader, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, img_y - 20, chart_captions.get(key, ""))

    # Insight bullets
    c.setFont("Helvetica", 12)
    cursor = img_y - 40
    for insight in chart_insights.get(key, []):
        c.drawString(margin, cursor, insight)
        cursor -= 14

    draw_footer()
    c.showPage()

# --- Finalize PDF ---
c.save()

with open(pdf_output_path, "rb") as pdf_file:
    st.download_button(
        label="📄 Download PDF Report",
        data=pdf_file.read(),
        file_name=pdf_output_path.split("/")[-1],
        mime="application/pdf"
    )