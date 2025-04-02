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
from reportlab.lib.colors import HexColor
import plotly.io as pio
import re

st.set_page_config(page_title="DOGE Savings Dashboard", layout="wide")

# --- Vendor Normalization Function ---
def normalize_vendor_name(name):
    if pd.isna(name) or not isinstance(name, str) or name.strip() == "":
        return None

    # Normalize string
    name = name.lower()
    name = re.sub(r'\(.*?\)', '', name)  # remove parenthesis
    name = re.sub(r'[^\w\s]', '', name)  # remove punctuation
    name = re.sub(
        r'\b(inc|llc|ltd|corp|co|company|incorporated|services|solutions|consulting|financial|advisory|systems|group|holdings|partners|lp|llp)\b',
        '', name)
    name = re.sub(r'\b(the|of|and|for|in|at|on|by|with|from)\b', '', name)
    name = re.sub(r'\s+', ' ', name)  # normalize whitespace
    name = name.strip()

    return name.split()[0].title() if name else None

def build_vendor_clusters(vendors, threshold=90):
    canonical_names = []
    name_mapping = {}

    for vendor in vendors:
        cleaned = normalize_vendor_name(vendor)
        if not cleaned:
            continue

        match_found = False
        for canon in canonical_names:
            score = fuzz.ratio(cleaned, canon)
            if score >= threshold:
                name_mapping[vendor] = canon
                match_found = True
                break

        if not match_found:
            canonical_names.append(cleaned)
            name_mapping[vendor] = cleaned

    return name_mapping


# --- Load Data from DOGE API ---
@st.cache_data
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
st.sidebar.header("\U0001F50D Filter Data")
agencies = st.sidebar.multiselect("Select Agencies", options=df["agency"].dropna().unique())
vendors = st.sidebar.multiselect("Select Vendors", options=df["vendor_normalized"].dropna().unique())

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
st.title("Government Contract Cancellations Dashboard")
st.markdown("Analyze contract savings from the Department of Government Efficiency (DOGE) API")

# --- Download Button ---
st.download_button(
    label="\U0001F4C5 Download Data as CSV",
    data=df.to_csv(index=False).encode("utf-8"),
    file_name="doge_contract_savings.csv",
    mime="text/csv"
)

# --- Key Metrics ---
st.markdown("### \U0001F4CA Key Metrics")
col1, col2, col3 = st.columns(3)
col1.metric("\U0001F4B0 Total Savings", f"${total_savings:,.0f}")
col2.metric("\U0001F4C4 Total Canceled Contracts", total_contracts)
col3.metric("\U0001F3DB Top Saving Agency", top_agency)

col4, col5 = st.columns(2)
col4.metric("\u26A0\uFE0F Top Affected Vendor", top_vendor)
col5.metric("\U0001F4C6 Most Common Cancellation Day", most_common_weekday)

# --- Charts ---
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
    # Save Plotly charts as images
    pio.write_image(fig1, "top_agencies.png")

with row1_col2:
    st.markdown("#### Top 10 Vendors by Canceled Contract Value")
    vendor_savings = df.groupby("vendor_normalized")["savings"].sum().sort_values(ascending=False).head(10)
    fig2 = go.Figure(go.Bar(
        x=vendor_savings.values,
        y=vendor_savings.index,
        orientation='h',
        marker_color='indianred'
    ))
    fig2.update_layout(
        title="Top 10 Vendors by Canceled Contract Value",
        xaxis_title="Canceled Value ($)",
        yaxis=dict(title='Vendor', autorange="reversed"),
        height=400
    )
    st.plotly_chart(fig2, use_container_width=True)
    # Save Plotly charts as images
    pio.write_image(fig2, "top_vendors.png")

row2_col1, row2_col2 = st.columns(2)

with row2_col1:
    st.markdown("#### Monthly Contract Savings")
    df_month = df.dropna(subset=["deleted_date", "savings"]).copy()
    monthly_data = (
        df_month.groupby(df_month["deleted_date"].dt.to_period("M"))["savings"]
        .sum()
        .reset_index()
    )
    monthly_data.columns = ["Month", "savings"]
    monthly_data["Month"] = monthly_data["Month"].astype(str)
    fig3 = px.line(
        monthly_data,
        x="Month",
        y="savings",
        markers=True,
        labels={"Month": "Month", "savings": "Savings ($)"},
        title="Monthly Contract Savings",
        height=400
    )
    st.plotly_chart(fig3, use_container_width=True)
    pio.write_image(fig3, "monthly_savings.png")


with row2_col2:
    st.markdown("#### Cancellations by Weekday")
    weekday_counts = df["weekday"].value_counts().reindex(
    ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    ).fillna(0).reset_index()

    # Rename columns so they can be referenced correctly
    weekday_counts.columns = ["weekday", "count"]

    # Now use the new column names for plotting
    fig4 = px.bar(
        weekday_counts,
        x="weekday",
        y="count",
        labels={"weekday": "Weekday", "count": "Cancellations"},
        title="Cancellations by Weekday",
        height=400
    )
    st.plotly_chart(fig4, use_container_width=True)
    pio.write_image(fig4, "weekday_cancellations.png")


# --- PDF Report ---
st.markdown("---")
st.markdown("### \U0001F4D1 Downloadable PDF Report")

pdf_output_path = "DOGE_Dashboard_Summary.pdf"
c = canvas.Canvas(pdf_output_path, pagesize=LETTER)
width, height = LETTER
margin = 50
line_height = 16
cursor = height - margin
page_number = 1

footer_text = "Built by Richie Garafola • RichieGarafola@hotmail.com • github.com/RichieGarafola"

def reset_cursor():
    global cursor
    cursor = height - margin

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

# --- Table of Contents ---
reset_cursor()
draw_title("Table of Contents")
draw_paragraph("1. Summary\n2. Automated Insights\n3. Agency-Level Summary\n4. Vendor-Level Summary\n5. Charts")
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

# --- Insights ---
reset_cursor()
draw_title("Automated Insights")
draw_divider()

insights = []
top_agency_savings = df.groupby("agency")["savings"].sum().sort_values(ascending=False).iloc[0]
vendor_loss = df.groupby("vendor_normalized")["savings"].sum().sort_values(ascending=False).iloc[0]
monthly_avg = df.groupby(df["deleted_date"].dt.to_period("M"))["savings"].sum().mean()
monthly_totals = df.groupby(df["deleted_date"].dt.to_period("M"))["savings"].sum()
peak_month = monthly_totals.idxmax().strftime('%B %Y')
peak_savings = monthly_totals.max()

insights.extend([
    f"- {top_agency} saved the most through cancellations: ${top_agency_savings:,.0f}.",
    f"- {top_vendor} was most affected with ${vendor_loss:,.0f} in canceled value.",
    f"- Average monthly savings: ${monthly_avg:,.0f}.",
    f"- Peak savings occurred in {peak_month} totaling ${peak_savings:,.0f}."
])

draw_paragraph("\n".join(insights))
draw_footer()
c.showPage()

# --- Agency Breakdown ---
reset_cursor()
draw_title("Agency-Level Summary")
draw_divider()

agency_table = df.groupby("agency")["savings"].sum().sort_values(ascending=False).reset_index()
for _, row in agency_table.iterrows():
    draw_paragraph(f"- {row['agency']}: ${row['savings']:,.0f}")
    if cursor < 100:
        draw_footer()
        c.showPage()
        reset_cursor()

draw_footer()
c.showPage()

# --- Vendor Breakdown ---
reset_cursor()
draw_title("Vendor-Level Summary")
draw_divider()

vendor_table = df.groupby("vendor_normalized")["savings"].sum().sort_values(ascending=False).reset_index()
for _, row in vendor_table.iterrows():
    draw_paragraph(f"- {row['vendor_normalized']}: ${row['savings']:,.0f}")
    if cursor < 100:
        draw_footer()
        c.showPage()
        reset_cursor()

draw_footer()
c.showPage()

# --- Charts ---
chart_paths = [
    ("Top 10 Agencies by Total Savings", "top_agencies.png"),
    ("Top 10 Vendors by Canceled Contract Value", "top_vendors.png"),
    ("Monthly Contract Savings", "monthly_savings.png"),
    ("Cancellations by Weekday", "weekday_cancellations.png")
]

for title, img_path in chart_paths:
    reset_cursor()
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - margin, title)
    c.drawImage(img_path, margin, height / 2 - 100, width=6.5 * inch, preserveAspectRatio=True, mask='auto')
    draw_footer()
    c.showPage()

# --- Finalize PDF ---
c.save()

with open(pdf_output_path, "rb") as pdf_file:
    st.download_button(
        label="\U0001F4C4 Download PDF Report",
        data=pdf_file.read(),
        file_name="DOGE_Dashboard_Summary.pdf",
        mime="application/pdf"
    )
