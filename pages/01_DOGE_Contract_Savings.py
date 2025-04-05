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

st.set_page_config(page_title="DOGE Contract Savings", layout="wide")

# --- Vendor Normalization ---
def normalize_vendor_name(name):
    if pd.isna(name) or not isinstance(name, str) or name.strip() == "":
        return None
    name = name.lower()
    name = re.sub(r'\(.*?\)', '', name) # remove parenthesis
    name = re.sub(r'[^\w\s]', '', name) # remove punctuation
    name = re.sub(r'\b(inc|llc|ltd|corp|co|company|incorporated|services|solutions|consulting|financial|advisory|systems|group|holdings|partners|lp|llp)\b', '', name)
    name = re.sub(r'\b(the|of|and|for|in|at|on|by|with|from)\b', '', name)
    name = re.sub(r'\s+', ' ', name) # normalize whitespace
    name = name.strip()
    return name.split()[0].title() if name else None

@st.cache_data(ttl=3600)
def get_contract_savings():
    DOGE_API_BASE = "https://api.doge.gov"
    ENDPOINT = "/savings/contracts"
    PER_PAGE = 500
    page = 1
    all_contracts = []

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
            contracts = data["result"]["contracts"]
            if not contracts:
                break
            all_contracts.extend(contracts)
            page += 1
        except:
            break

    df = pd.DataFrame(all_contracts)
    df["deleted_date"] = pd.to_datetime(df["deleted_date"])
    df["savings"] = pd.to_numeric(df["savings"], errors="coerce")
    df["month"] = df["deleted_date"].dt.to_period("M")
    df["weekday"] = df["deleted_date"].dt.day_name()
    df["vendor_normalized"] = df["vendor"].apply(normalize_vendor_name)
    return df

# --- Load and process data ---
df = get_contract_savings()

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filter Data")
agencies = st.sidebar.multiselect("Select Agencies", options=df["agency"].dropna().unique())
vendors = st.sidebar.multiselect("Select Vendors", options=df["vendor_normalized"].dropna().unique())
export_charts = st.sidebar.checkbox("📦 Export Charts for PDF?")

if agencies:
    df = df[df["agency"].isin(agencies)]
if vendors:
    df = df[df["vendor_normalized"].isin(vendors)]

if df.empty:
    st.warning("No data matches your filter criteria.")
    st.stop()

# --- Metrics ---
total_savings = df["savings"].sum()
total_contracts = len(df)
top_agency = df.groupby("agency")["savings"].sum().idxmax()
top_vendor = df.groupby("vendor_normalized")["savings"].sum().idxmax()
most_common_weekday = df["weekday"].value_counts().idxmax()

# --- Layout ---
st.title("📊 Government Contract Cancellations Dashboard")
st.markdown("Analyze contract savings from the Department of Government Efficiency (DOGE) API")

# --- Download CSV ---
st.download_button(
    label="📥 Download CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="doge_contract_savings.csv",
    mime="text/csv"
)

# --- Key Metrics Display ---
st.markdown("### 📌 Key Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("💰 Total Savings", f"${total_savings:,.0f}")
col2.metric("📄 Total Canceled Contracts", total_contracts)
col3.metric("🏛️ Top Saving Agency", top_agency)

col4, col5 = st.columns(2)
col4.metric("⚠️ Top Affected Vendor", top_vendor)
col5.metric("📅 Most Common Cancellation Day", most_common_weekday)

# --- Generate charts and optionally export ---
chart_images = {}

def render_and_export_chart(fig, caption, key):
    st.plotly_chart(fig, use_container_width=True)
    st.caption(caption)
    
    if export_charts:
        buffer = BytesIO()
        try:
            fig.write_image(buffer, format="png")
            buffer.seek(0)
            chart_images[key] = buffer
        except Exception as e:
            st.error(f"❌ Error exporting chart '{key}': {e}")
        else:
            st.success(f"✅ Chart '{key}' exported successfully.")


st.markdown("### 📊 Visualizations")
col1, col2 = st.columns(2)

with col1:
    agency_data = df.groupby("agency")["savings"].sum().sort_values(ascending=False).head(10)
    fig = go.Figure(go.Bar(
        x=agency_data.values,
        y=agency_data.index,
        orientation="h"
    ))
    fig.update_layout(
        title="Top 10 Agencies by Total Savings", 
        xaxis_title="Savings ($)", 
        yaxis=dict(autorange="reversed"),
        margin=dict(l=200, r=20, t=50, b=40))  # ⬅ increases left space
    fig.update_yaxes(automargin=True,tickfont=dict(size=10))
    fig.update_traces(constraintext="both")
    render_and_export_chart(fig, "Top 10 agencies by cumulative savings.", "top_agencies")

with col2:
    vendor_data = df.groupby("vendor_normalized")["savings"].sum().sort_values(ascending=False).head(10)
    fig = go.Figure(go.Bar(
        x=vendor_data.values,
        y=vendor_data.index,
        orientation="h"
    ))
    fig.update_layout(
        title="Top 10 Vendors by Contract Value Lost", 
        xaxis_title="Canceled Value ($)", 
        yaxis=dict(autorange="reversed"),
        margin=dict(l=200, r=20, t=50, b=40))  # ⬅ increases left space
    fig.update_yaxes(automargin=True,tickfont=dict(size=10))
    fig.update_traces(constraintext="both")
    render_and_export_chart(fig, "Top 10 vendors most affected by cancellations.", "top_vendors")

col3, col4 = st.columns(2)

with col3:
    monthly = df.groupby(df["deleted_date"].dt.to_period("M"))["savings"].sum().reset_index()
    monthly.columns = ["Month", "Savings"]
    monthly["Month"] = monthly["Month"].astype(str)
    fig = px.line(
        monthly, 
        x="Month", 
        y="Savings", 
        markers=True, 
        title="Monthly Contract Savings")
    
    render_and_export_chart(fig, "Monthly trend of contract cancellations.", "monthly_savings")

with col4:
    weekday_counts = df["weekday"].value_counts().reindex(
        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ).fillna(0).reset_index()
    weekday_counts.columns = ["Weekday", "Count"]
    fig = px.bar(
        weekday_counts, 
        x="Weekday", 
        y="Count", 
        title="Cancellations by Weekday")
    
    render_and_export_chart(fig, "Distribution of cancellations by weekday.", "weekday")

    
#####################    
# --- PDF Report ---
#####################

st.markdown("---")
st.markdown("### 📄 Downloadable PDF Report")

pdf_output_path = f"DOGE_Contract_Summary_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
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
c.drawCentredString(width / 2, height - 100, "DOGE Contract Savings Report")
c.setFont("Helvetica", 16)
c.setFillColor(HexColor("#000000"))
c.drawCentredString(width / 2, height - 140, "Department of Government Efficiency")
c.setFont("Helvetica", 12)
c.drawCentredString(width / 2, height - 180, f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}")
draw_footer()
c.showPage()

top_agency_savings = df.groupby("agency")["savings"].sum().max()
vendor_loss = df.groupby("vendor_normalized")["savings"].sum().max()
monthly_avg = df.groupby(df["deleted_date"].dt.to_period("M"))["savings"].sum().mean()
monthly_totals = df.groupby(df["deleted_date"].dt.to_period("M"))["savings"].sum()
peak_month = monthly_totals.idxmax().strftime('%B %Y')
peak_savings = monthly_totals.max()

# --- BLUF Section (Page 2) ---
reset_cursor()
draw_title("BLUF: Bottom Line Up Front")
draw_divider()

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Total Canceled Savings:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"${total_savings:,.0f} across {total_contracts} contracts")
cursor -= 2 * line_height

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Top Saving Agency:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"{top_agency}")
cursor -= 2 * line_height

c.setFont("Helvetica-Bold", 12)
c.drawString(margin, cursor, "✔ Most Impacted Vendor:")
cursor -= line_height
c.setFont("Helvetica", 12)
c.drawString(margin + 20, cursor, f"{top_vendor}")
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
c.drawString(margin + 20, cursor, f"{peak_month} — ${peak_savings:,.0f}")
cursor -= 2 * line_height

draw_footer()
c.showPage()


# --- Table of Contents ---
reset_cursor()
draw_title("Table of Contents")
draw_paragraph("1. BLUF\n2. Summary\n3. Automated Insights\n4. Top 20 Agencies\n5. Top 20 Vendors\n6. Charts")
draw_footer()
c.showPage()

# --- Summary ---
reset_cursor()
draw_title("Summary")
draw_paragraph("This report highlights key savings achieved through government contract cancellations.\nThe dashboard includes key metrics, trends, and automated insights from DOGE API.")
cursor -= 10
draw_title("Key Metrics")
draw_paragraph(
    f"- Total Savings: ${total_savings:,.0f}\n"
    f"- Total Contracts Canceled: {total_contracts}\n"
    f"- Top Saving Agency: {top_agency}\n"
    f"- Top Affected Vendor: {top_vendor}\n"
    f"- Most Common Cancellation Day: {most_common_weekday}"
)
draw_footer()
c.showPage()

# --- Automated Insights ---
reset_cursor()
draw_title("Automated Insights")
draw_divider()



insights = [
    f"- {top_agency} saved the most: ${top_agency_savings:,.0f}.",
    f"- {top_vendor} was most affected: ${vendor_loss:,.0f}.",
    f"- Average monthly savings: ${monthly_avg:,.0f}.",
    f"- Peak savings occurred in {peak_month} totaling ${peak_savings:,.0f}."
]
draw_paragraph("\n".join(insights))
draw_footer()
c.showPage()

# --- Top 20 Agencies (Formatted Table) ---
reset_cursor()
draw_title("Top 20 Agencies by Canceled Savings")
draw_divider()
c.setFont("Courier", 11)
top_agencies = df.groupby("agency")["savings"].sum().sort_values(ascending=False).head(20).reset_index()
for _, row in top_agencies.iterrows():
    c.drawString(margin, cursor, f"{row['agency']:<50} ${row['savings']:>15,.0f}")
    cursor -= line_height
draw_footer()
c.showPage()

# --- Top 20 Vendors (Formatted Table) ---
reset_cursor()
draw_title("Top 20 Vendors by Canceled Value")
draw_divider()
c.setFont("Courier", 11)
top_vendors = df.groupby("vendor_normalized")["savings"].sum().sort_values(ascending=False).head(20).reset_index()
for _, row in top_vendors.iterrows():
    c.drawString(margin, cursor, f"{row['vendor_normalized']:<50} ${row['savings']:>15,.0f}")
    cursor -= line_height
draw_footer()
c.showPage()

# --- Charts with Captions and Auto Insights ---
chart_titles = {
    "top_agencies": "Top 10 Agencies by Total Savings",
    "top_vendors": "Top 10 Vendors by Canceled Contract Value",
    "monthly_savings": "Monthly Contract Savings",
    "weekday": "Cancellations by Weekday"
}

chart_captions = {
    "top_agencies": "Agencies with the highest total savings.",
    "top_vendors": "Vendors most financially impacted.",
    "monthly_savings": "Trends in cancellations by month.",
    "weekday": "Most common days for cancellations."
}

chart_insights = {
    "top_agencies": [
        f"- {top_agencies.iloc[0]['agency']} led with ${top_agencies.iloc[0]['savings']:,.0f} saved.",
        f"- Total from Top 10 agencies: ${top_agencies['savings'].sum():,.0f}."
    ],
    "top_vendors": [
        f"- {top_vendors.iloc[0]['vendor_normalized']} lost ${top_vendors.iloc[0]['savings']:,.0f}.",
        f"- Total from Top 10 vendors: ${top_vendors['savings'].sum():,.0f}."
    ],
    "monthly_savings": [
        f"- Peak month was {peak_month} with ${peak_savings:,.0f}.",
        f"- Monthly average savings: ${monthly_avg:,.0f}."
    ],
    "weekday": [
        f"- Most cancellations on {most_common_weekday}.",
        f"- Weekday with fewest cancellations: {df['weekday'].value_counts().idxmin()}."
    ]
}

for key, buffer in chart_images.items():
    if key not in chart_titles:
        continue
    reset_cursor()
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - margin, chart_titles[key])

    image_reader = ImageReader(buffer)
    # Adjusted height, vertical positioning, and spacing
    img_width = 6.5 * inch
    img_height = 4.75 * inch
    img_x = margin
    img_y = height - 450  # higher up the page

    c.drawImage(image_reader, img_x, img_y, width=img_width, height=img_height, preserveAspectRatio=True, mask='auto')

    # Auto Generated Caption and Insights
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(width / 2, height / 2 - 120, chart_captions.get(key, ""))

    c.setFont("Helvetica", 12)
    cursor = height / 2 - 150
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