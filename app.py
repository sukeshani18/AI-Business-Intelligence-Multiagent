

import streamlit as st

import pandas as pd

import plotly.express as px

from io import BytesIO

from reportlab.lib import colors

from reportlab.lib.pagesizes import A4

from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image as PDFImage, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from utils.data_loader import load_csv

from utils.data_summary import generate_dataset_summary

from graph.workflow import business_workflow

# ==================================================

# PAGE CONFIGURATION

# ==================================================

st.set_page_config(

    page_title="AI Business Intelligence",

    page_icon="📊",

    layout="wide"

)

# ==================================================

# PROFESSIONAL DESIGN

# ==================================================

st.markdown("""
<style>
:root {
    color-scheme: dark;
    --app-bg: #07090D;
    --surface: #111722;
    --surface-raised: #151E2B;
    --surface-hover: #1B2635;
    --text-main: #F1F5F9;
    --text-muted: #A5B1C2;
    --text-soft: #7F8DA2;
    --border: #273449;
    --accent: #60A5FA;
}
html, body, .stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stToolbar"] {
    background: var(--app-bg) !important;
    color: var(--text-main) !important;
}
.block-container { padding-top: 2.6rem; padding-bottom: 1.6rem; max-width: 1500px; }
.main-title { font-size: clamp(25px, 2.2vw, 34px); line-height: 1.3; font-weight: 800; color: #F8FAFC; letter-spacing: -0.7px; margin: 0 0 5px 0; overflow: visible; }
.subtitle { font-size: 14px; line-height: 1.5; color: var(--text-muted); margin: 0 0 18px 0; }
.section-heading { font-size: 20px; line-height: 1.3; font-weight: 750; color: #E8EEF7; margin-top: 19px; margin-bottom: 11px; }
.kpi-card { position: relative; overflow: hidden; background: linear-gradient(145deg, #172130 0%, #101722 100%); border: 1px solid #2A374B; border-radius: 15px; padding: 15px 16px 13px; min-height: 112px; box-shadow: 0 7px 22px rgba(0,0,0,.22); }
.kpi-card::before { content: ""; position: absolute; top: 0; left: 0; right: 0; height: 3px; background: var(--kpi-accent, var(--accent)); }
.kpi-topline { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.kpi-label { font-size: 12px; line-height: 1.35; font-weight: 650; color: #AAB7C8; }
.kpi-icon { width: 30px; height: 30px; display: inline-flex; align-items: center; justify-content: center; border-radius: 9px; background: color-mix(in srgb, var(--kpi-accent, var(--accent)) 17%, #172130); color: #F8FAFC; font-size: 15px; }
.kpi-value { font-size: clamp(22px, 1.8vw, 27px); line-height: 1.2; font-weight: 800; color: #F8FAFC; margin-top: 9px; letter-spacing: -0.4px; }
.kpi-caption { font-size: 10px; color: #8190A5; margin-top: 5px; }
div[data-testid="stPlotlyChart"] { background: #111722 !important; border: 1px solid #273449; border-radius: 14px; padding: 3px; box-shadow: 0 5px 18px rgba(0,0,0,.18); }
[data-testid="stSidebar"] { background: #0D121B !important; border-right: 1px solid #202B3A; }
[data-testid="stSidebar"] * { color: #E2E8F0; }
.stMarkdown, p, label, [data-testid="stCaptionContainer"] { color: var(--text-main); }
[data-testid="stSelectbox"] label, [data-testid="stMultiSelect"] label, [data-testid="stDateInput"] label, [data-testid="stTextArea"] label, [data-testid="stFileUploader"] label { color: #D5DEEA !important; }
[data-baseweb="select"] > div, [data-baseweb="input"] > div, [data-baseweb="textarea"] > div, [data-testid="stDateInput"] input, [data-testid="stTextArea"] textarea { background: #151E2B !important; color: #F1F5F9 !important; border-color: #344258 !important; }
[data-baseweb="popover"], [data-baseweb="menu"] { background: #151E2B !important; color: #F1F5F9 !important; }
[data-testid="stFileUploader"] section { background: #111722 !important; border: 1px dashed #40516A !important; }
[data-testid="stExpander"] { background: #111722; border: 1px solid #273449; border-radius: 10px; }
.stButton > button, .stDownloadButton > button { border-radius: 9px; font-weight: 650; }
hr { border-color: #273449 !important; }
</style>
""", unsafe_allow_html=True)

# ==================================================

# COLUMN DETECTION HELPERS

# ==================================================

def find_column(columns, keywords):

    for column in columns:

        name = str(column).lower().replace("_", " ").strip()

        if any(keyword in name for keyword in keywords):

            return column

    return None

def is_identifier(column):

    name = str(column).lower().replace("_", " ").strip()

    identifier_names = [

        "id",

        "customer id",

        "order id",

        "product id",

        "transaction id",

        "invoice id",

        "employee id",

        "account id",

        "phone",

        "phone number",

        "postal code",

        "zip code"

    ]

    if name in identifier_names:

        return True

    if name.endswith(" id") or name.endswith(" code"):

        return True

    if name.startswith("id "):

        return True

    return False

def detect_date_column(df):

    date_keywords = [

        "date",

        "time",

        "timestamp",

        "order date",

        "purchase date"

    ]

    for column in df.columns:

        name = str(column).lower()

        if not any(word in name for word in date_keywords):

            continue

        converted = pd.to_datetime(

            df[column],

            errors="coerce"

        )

        if converted.notna().mean() >= 0.70:

            df[column] = converted

            return column

    return None

def get_numeric_columns(df):

    return [

        column

        for column in df.select_dtypes(include="number").columns

        if not is_identifier(column)

    ]

def get_business_metric(df):

    numeric_columns = get_numeric_columns(df)

    preferred_keywords = [

        "revenue",

        "sales",

        "profit",

        "amount",

        "total",

        "price",

        "income",

        "cost",

        "quantity",

        "units",

        "value"

    ]

    for keyword in preferred_keywords:

        for column in numeric_columns:

            if keyword in str(column).lower():

                return column

    return numeric_columns[0] if numeric_columns else None

def get_category_column(df):

    categorical_columns = df.select_dtypes(

        include=["object", "category", "bool"]

    ).columns.tolist()

    preferred_keywords = [

        "product",

        "category",

        "region",

        "city",

        "segment",

        "department",

        "country",

        "state",

        "channel",

        "contract",

        "status",

        "type",

        "customer"

    ]

    candidates = []

    for column in categorical_columns:

        unique_count = df[column].nunique(dropna=True)

        # Allow even one unique value after filtering.

        if unique_count == 0 or unique_count > 20:

            continue

        candidates.append(column)

    for keyword in preferred_keywords:

        for column in candidates:

            if keyword in str(column).lower():

                return column

    return candidates[0] if candidates else None

# ==================================================
# DISPLAY LABELS
# ==================================================

def humanize_column(column):
    """Turn raw dataset column names into readable dashboard labels."""
    text = str(column).replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    replacements = {"id": "ID", "sku": "SKU", "url": "URL", "api": "API", "qty": "Quantity", "amt": "Amount", "avg": "Average"}
    return " ".join(replacements.get(word.lower(), word.capitalize()) for word in text.split())


def kpi_icon(label):
    text = str(label).lower()
    if "revenue" in text or "sales" in text: return "💰", "#0D9488"
    if "profit" in text or "income" in text: return "📈", "#2563EB"
    if "customer" in text: return "👥", "#8B5CF6"
    if "order" in text or "record" in text: return "🧾", "#F59E0B"
    if "churn" in text: return "⚠️", "#EF4444"
    if "retain" in text: return "🤝", "#0D9488"
    return "📊", "#64748B"

# ==================================================

# FORMATTING

# ==================================================

def format_number(value):

    if pd.isna(value):

        return "0"

    value = float(value)

    if abs(value) >= 1_000_000:

        return f"{value / 1_000_000:.2f}M"

    if abs(value) >= 1_000:

        return f"{value / 1_000:.2f}K"

    if value.is_integer():

        return f"{value:,.0f}"

    return f"{value:,.2f}"

# ==================================================

# DYNAMIC KPI CARDS

# ==================================================

def get_kpis(df):

    kpis = []

    numeric_columns = df.select_dtypes(

        include="number"

    ).columns.tolist()

    revenue_column = find_column(

        numeric_columns,

        ["revenue", "sales", "total amount", "total sales"]

    )

    profit_column = find_column(

        numeric_columns,

        ["profit", "net income"]

    )

    customer_column = find_column(

        df.columns,

        ["customer id", "customer_id", "customer_name", "customer name"]

    )

    order_column = find_column(

        df.columns,

        ["order id", "order_id", "invoice id", "transaction id"]

    )

    churn_column = find_column(

        df.columns,

        ["churn", "churn status"]

    )

    if churn_column is not None:

        churn_values = (

            df[churn_column]

            .astype(str)

            .str.strip()

            .str.lower()

        )

        churned = churn_values.isin([

            "yes",

            "true",

            "1",

            "churned"

        ]).sum()

        total = len(df)

        retained = total - churned

        churn_rate = (

            churned / total *100

            if total else 0

        )

        kpis.extend([

            ("Total Customers", format_number(

                df[customer_column].nunique()

                if customer_column else total

            )),

            ("Churned Customers", format_number(churned)),

            ("Retained Customers", format_number(retained)),

            ("Churn Rate", f"{churn_rate:.2f}%")

        ])

        return kpis

    if revenue_column is not None:

        kpis.append((

            "Total Revenue",

            format_number(df[revenue_column].sum())

        ))

    if profit_column is not None:

        kpis.append((

            "Total Profit",

            format_number(df[profit_column].sum())

        ))

    if customer_column is not None:

        kpis.append((

            "Total Customers",

            format_number(df[customer_column].nunique())

        ))

    if order_column is not None:

        kpis.append((

            "Total Orders",

            format_number(df[order_column].nunique())

        ))

    if len(kpis) < 4:

        kpis.append((

            "Total Records",

            format_number(len(df))

        ))

    if len(kpis) < 4:

        kpis.append((

            "Total Columns",

            format_number(len(df.columns))

        ))

    return kpis[:4]

# ==================================================

# CHART STYLING

# ==================================================

CHART_COLORS = [
    "#60A5FA", "#2DD4BF", "#FBBF24", "#A78BFA",
    "#F472B6", "#FB7185", "#38BDF8", "#A3E635"
]

def style_chart(fig, height=390):
    # The dashboard uses a consistent dark visual theme.
    text_color = "#D8E1ED"
    title_color = "#F8FAFC"
    grid_color = "#293548"
    axis_color = "#53647B"
    chart_bg = "#111722"
    fig.update_layout(
        template="plotly_dark",
        height=height,
        font=dict(family="Arial", size=12, color=text_color),
        title=dict(x=0.04, xanchor="left", y=0.97,
                   font=dict(size=15, color=title_color)),
        margin=dict(l=25, r=22, t=52, b=35),
        paper_bgcolor=chart_bg,
        plot_bgcolor=chart_bg,
        showlegend=False,
        hoverlabel=dict(bgcolor="#202B3A", bordercolor="#40516A",
                        font_color="#F8FAFC")
    )
    fig.update_xaxes(showgrid=False, linecolor=axis_color, color=text_color,
                     tickfont=dict(color="#AAB7C8"), title_font=dict(color="#D8E1ED"))
    fig.update_yaxes(gridcolor=grid_color, zeroline=False, color=text_color,
                     tickfont=dict(color="#AAB7C8"), title_font=dict(color="#D8E1ED"))
    return fig

# ==================================================

# PDF REPORT

# ==================================================

def _pdf_chart_image(fig, width=3.35, height=2.25):
    """Convert a Matplotlib figure into an in-memory PDF image."""
    image_buffer = BytesIO()
    fig.tight_layout()
    fig.savefig(image_buffer, format="png", dpi=170, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    image_buffer.seek(0)
    return PDFImage(image_buffer, width=width * inch, height=height * inch)


def _make_pdf_charts(df, metric_column, category_column, date_column):
    """Build dashboard charts from the currently filtered dataframe."""
    charts = []
    palette = ["#2563EB", "#0D9488", "#F59E0B", "#8B5CF6", "#EC4899",
               "#EF4444", "#06B6D4", "#84CC16"]

    if metric_column and category_column and metric_column in df.columns and category_column in df.columns:
        grouped = (df.groupby(category_column, dropna=False)[metric_column]
                   .sum().sort_values(ascending=True).tail(10))
        if not grouped.empty:
            fig, ax = plt.subplots(figsize=(7, 4.2))
            bars = ax.barh([str(x) for x in grouped.index], grouped.values, color="#0D9488")
            ax.set_title(f"{humanize_column(metric_column)} by {humanize_column(category_column)}", loc="left", weight="bold")
            ax.set_xlabel(humanize_column(metric_column))
            ax.grid(axis="x", alpha=.2)
            ax.set_axisbelow(True)
            ax.spines[["top", "right", "left"]].set_visible(False)
            ax.bar_label(bars, labels=[format_number(float(v)) for v in grouped.values], padding=3, fontsize=8)
            charts.append(("Business Performance", _pdf_chart_image(fig)))

    if category_column and category_column in df.columns:
        counts = df[category_column].astype(str).value_counts().head(8)
        if not counts.empty:
            fig, ax = plt.subplots(figsize=(6, 4.2))
            wedges, _, _ = ax.pie(counts.values, labels=None, autopct="%1.1f%%", startangle=90,
                                  colors=palette[:len(counts)], pctdistance=.72,
                                  wedgeprops={"width": .42, "edgecolor": "white", "linewidth": 2})
            ax.set_title(f"{humanize_column(category_column)} Mix", loc="left", weight="bold")
            ax.legend(wedges, [str(x) for x in counts.index], loc="center left",
                      bbox_to_anchor=(.92, .5), frameon=False, fontsize=8)
            charts.append(("Category Distribution", _pdf_chart_image(fig)))

    if metric_column and metric_column in df.columns:
        values = pd.to_numeric(df[metric_column], errors="coerce").dropna()
        if not values.empty:
            fig, ax = plt.subplots(figsize=(7, 4.2))
            ax.hist(values, bins=min(20, max(5, values.nunique())), color="#2563EB", edgecolor="white", alpha=.9)
            ax.set_title(f"Distribution of {humanize_column(metric_column)}", loc="left", weight="bold")
            ax.set_xlabel(humanize_column(metric_column))
            ax.set_ylabel("Frequency")
            ax.grid(axis="y", alpha=.2)
            ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
            charts.append(("Numerical Analysis", _pdf_chart_image(fig)))

    if date_column and metric_column and date_column in df.columns and metric_column in df.columns:
        trend = (df[[date_column, metric_column]].dropna()
                 .groupby(date_column)[metric_column].sum().sort_index())
        if not trend.empty:
            fig, ax = plt.subplots(figsize=(7, 4.2))
            if len(trend) > 1:
                ax.plot(trend.index, trend.values, color="#0D9488", marker="o", linewidth=2.5)
            else:
                ax.bar([str(trend.index[0])], trend.values, color="#0D9488")
            ax.set_title(f"{humanize_column(metric_column)} Over Time", loc="left", weight="bold")
            ax.set_xlabel("Date")
            ax.set_ylabel(humanize_column(metric_column))
            ax.grid(axis="y", alpha=.2)
            ax.set_axisbelow(True)
            ax.spines[["top", "right"]].set_visible(False)
            fig.autofmt_xdate(rotation=25)
            charts.append(("Performance Trend", _pdf_chart_image(fig)))

    return charts


def generate_pdf(df, kpis, metric_column=None, category_column=None,
                 date_column=None, dataset_name="Business Dataset",
                 ai_findings="", business_insights=""):
    """Create a multi-page, Power BI-style business dashboard PDF."""
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer, pagesize=A4, rightMargin=34, leftMargin=34,
        topMargin=34, bottomMargin=34, title="AI Business Intelligence Report"
    )
    base_styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle", parent=base_styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=27, textColor=HexColor("#172B4D"), alignment=TA_LEFT,
        spaceAfter=5
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle", parent=base_styles["Normal"], fontSize=9,
        textColor=HexColor("#64748B"), leading=13, spaceAfter=12
    )
    section_style = ParagraphStyle(
        "ReportSection", parent=base_styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=HexColor("#172B4D"),
        spaceBefore=12, spaceAfter=8
    )
    body_style = ParagraphStyle(
        "ReportBody", parent=base_styles["BodyText"], fontSize=8.5,
        leading=12, textColor=HexColor("#334155"), spaceAfter=5
    )
    small_style = ParagraphStyle(
        "ReportSmall", parent=body_style, fontSize=7, leading=9
    )

    elements = [
        Paragraph("AI Business Intelligence Report", title_style),
        Paragraph(
            f"{dataset_name} &nbsp; | &nbsp; Generated {pd.Timestamp.now().strftime('%d %b %Y, %I:%M %p')}"
            f" &nbsp; | &nbsp; {len(df):,} filtered records",
            subtitle_style
        ),
    ]

    # Report scope / selected analysis
    scope_rows = [["REPORT SCOPE", "SELECTED ANALYSIS"],
                  [f"Records: {len(df):,}\nColumns: {len(df.columns):,}",
                   f"Metric: {humanize_column(metric_column) if metric_column else 'Not selected'}\n"
                   f"Category: {humanize_column(category_column) if category_column else 'Not selected'}"]]
    scope_table = Table(scope_rows, colWidths=[3.55*inch, 3.55*inch])
    scope_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HexColor("#172B4D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 8),
        ("BACKGROUND", (0,1), (-1,1), HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0,1), (-1,1), HexColor("#334155")),
        ("GRID", (0,0), (-1,-1), .5, HexColor("#CBD5E1")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 9),
        ("RIGHTPADDING", (0,0), (-1,-1), 9),
        ("TOPPADDING", (0,0), (-1,-1), 8),
        ("BOTTOMPADDING", (0,0), (-1,-1), 8),
    ]))
    elements.extend([scope_table, Paragraph("Business Overview", section_style)])

    # KPI tiles
    kpi_cells = []
    for label, value in kpis[:4]:
        kpi_cells.append(Paragraph(
            f'<font color="#64748B" size="7">{label.upper()}</font><br/>'
            f'<font color="#172B4D" size="17"><b>{value}</b></font>', body_style
        ))
    if kpi_cells:
        while len(kpi_cells) < 4:
            kpi_cells.append(Paragraph("", body_style))
        kpi_table = Table([kpi_cells], colWidths=[1.78*inch]*4)
        kpi_table.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), HexColor("#F8FAFC")),
            ("BOX", (0,0), (-1,-1), .7, HexColor("#D9E2EF")),
            ("INNERGRID", (0,0), (-1,-1), .6, HexColor("#D9E2EF")),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 9),
            ("RIGHTPADDING", (0,0), (-1,-1), 7),
            ("TOPPADDING", (0,0), (-1,-1), 11),
            ("BOTTOMPADDING", (0,0), (-1,-1), 11),
        ]))
        elements.extend([kpi_table, Spacer(1, 8)])

    # Dataset quality snapshot
    missing_total = int(df.isna().sum().sum())
    duplicate_rows = int(df.duplicated().sum())
    quality_text = (f"Missing cells: {missing_total:,} &nbsp; | &nbsp; "
                    f"Duplicate rows: {duplicate_rows:,} &nbsp; | &nbsp; "
                    f"Columns: {len(df.columns):,}")
    elements.extend([Paragraph("Data Quality Snapshot", section_style), Paragraph(quality_text, body_style)])

    # Dashboard charts in two-column layout
    chart_items = _make_pdf_charts(df, metric_column, category_column, date_column)
    if chart_items:
        elements.append(Paragraph("Dashboard Visualizations", section_style))
        for i in range(0, len(chart_items), 2):
            row = []
            for _, chart_image in chart_items[i:i+2]:
                row.append(chart_image)
            if len(row) == 1:
                row.append(Paragraph("", body_style))
            chart_table = Table([row], colWidths=[3.55*inch, 3.55*inch])
            chart_table.setStyle(TableStyle([
                ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                ("LEFTPADDING", (0,0), (-1,-1), 2),
                ("RIGHTPADDING", (0,0), (-1,-1), 2),
                ("TOPPADDING", (0,0), (-1,-1), 4),
                ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ]))
            elements.append(chart_table)

    # Include generated AI analysis when available
    if ai_findings or business_insights:
        elements.append(PageBreak())
        elements.append(Paragraph("AI Business Analysis", section_style))
        if ai_findings:
            elements.append(Paragraph("Data Analyst Findings", section_style))
            for paragraph in str(ai_findings).split("\n"):
                clean = paragraph.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if clean:
                    elements.append(Paragraph(clean, body_style))
        if business_insights:
            elements.append(Paragraph("Business Insights &amp; Strategies", section_style))
            for paragraph in str(business_insights).split("\n"):
                clean = paragraph.strip().replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                if clean:
                    elements.append(Paragraph(clean, body_style))

    # Dataset preview, kept concise and landscape-friendly within A4 width
    elements.append(PageBreak())
    elements.append(Paragraph("Dataset Preview", section_style))
    preview = df.head(12).copy().fillna("")
    max_cols = min(len(preview.columns), 7)
    preview = preview.iloc[:, :max_cols]
    table_data = [[Paragraph(f"<b>{humanize_column(c)}</b>", small_style) for c in preview.columns]]
    for _, row in preview.iterrows():
        table_data.append([Paragraph(str(v)[:55].replace("&", "&amp;").replace("<", "&lt;"), small_style)
                           for v in row.tolist()])
    preview_table = Table(table_data, repeatRows=1, colWidths=[7.1*inch/max_cols]*max_cols)
    preview_table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), HexColor("#172B4D")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, HexColor("#F1F5F9")]),
        ("GRID", (0,0), (-1,-1), .35, HexColor("#CBD5E1")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 4),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))
    elements.append(preview_table)
    elements.append(Spacer(1, 8))
    elements.append(Paragraph("Note: This report uses the records and analysis currently selected in the dashboard. The preview displays up to 12 rows and 7 columns.", small_style))

    document.build(elements)
    buffer.seek(0)
    return buffer

# ==================================================

# HEADER

# ==================================================

st.markdown(

    '<div class="main-title">📊 AI Business Intelligence</div>',

    unsafe_allow_html=True

)

st.markdown(

    '<div class="subtitle">Understand business performance, discover opportunities and make data-driven decisions.</div>',

    unsafe_allow_html=True

)

# ==================================================

# CSV UPLOAD

# ==================================================

uploaded_file = st.file_uploader(

    "Upload your business dataset",

    type=["csv"]

)

if uploaded_file is None:

    st.info("Upload a CSV file to generate your dashboard.")

    st.stop()

try:

    df = load_csv(uploaded_file)

    if df.empty:

        st.warning("The uploaded dataset is empty.")

        st.stop()

except Exception as e:

    st.error(f"CSV loading failed: {e}")

    st.stop()

df = df.copy()

date_column = detect_date_column(df)

# ==================================================

# SIDEBAR FILTERS

# ==================================================

st.sidebar.title("Dashboard Filters")

st.sidebar.caption(

    "Choose filters to explore your dataset."

)

filtered_df = df.copy()

# DATE FILTER

if date_column is not None:

    min_date = df[date_column].min().date()

    max_date = df[date_column].max().date()

    selected_dates = st.sidebar.date_input(

        "Date Range",

        value=(min_date, max_date),

        min_value=min_date,

        max_value=max_date

    )

    if (

        isinstance(selected_dates, (tuple, list))

        and len(selected_dates) == 2

    ):

        start_date, end_date = selected_dates

        filtered_df = filtered_df[

            (filtered_df[date_column].dt.date >= start_date) &

            (filtered_df[date_column].dt.date <= end_date)

        ]

else:

    st.sidebar.info("No date column detected.")

# CATEGORY FILTERS

categorical_columns = filtered_df.select_dtypes(

    include=["object", "category", "bool"]

).columns.tolist()

if date_column in categorical_columns:

    categorical_columns.remove(date_column)

for column in categorical_columns[:3]:

    options = sorted(

        filtered_df[column]

        .dropna()

        .astype(str)

        .unique()

        .tolist()

    )

    if 1 < len(options) <= 100:

        selected_values = st.sidebar.multiselect(

            column,

            options,

            default=[],

            placeholder="All values",

            key=f"filter_{column}"

        )

        if selected_values:

            filtered_df = filtered_df[

                filtered_df[column]

                .astype(str)

                .isin(selected_values)

            ]

# ==================================================

# FILTER VALIDATION

# ==================================================

if filtered_df.empty:

    st.warning(

        "No records match the selected filters. "

        "Please change your filters."

    )

    if st.button("Reset Filters"):

        for key in list(st.session_state.keys()):

            if key.startswith("filter_"):

                del st.session_state[key]

        st.rerun()

    st.stop()

# ==================================================

# BUSINESS OVERVIEW

# ==================================================

st.markdown(

    '<div class="section-heading">Business Overview</div>',

    unsafe_allow_html=True

)

kpis = get_kpis(filtered_df)

if not kpis:

    kpis = [("Total Records", format_number(len(filtered_df)))]

kpi_columns = st.columns(4, gap="medium")

for index, (label, value) in enumerate(kpis):
    with kpi_columns[index]:
        icon, accent = kpi_icon(label)
        safe_label = humanize_column(label)
        st.markdown(
            f'<div class="kpi-card" style="--kpi-accent:{accent}">'
            f'<div class="kpi-topline"><div class="kpi-label">{safe_label}</div>'
            f'<div class="kpi-icon">{icon}</div></div>'
            f'<div class="kpi-value">{value}</div>'
            f'<div class="kpi-caption">For the selected data</div></div>',
            unsafe_allow_html=True
        )

# ==================================================

# INTERACTIVE CHART SELECTION

# ==================================================

numeric_columns = get_numeric_columns(filtered_df)

category_candidates = filtered_df.select_dtypes(

    include=["object", "category", "bool"]

).columns.tolist()

category_candidates = [

    column for column in category_candidates

    if 1 <= filtered_df[column].nunique(dropna=True) <= 100

]

st.markdown(

    '<div class="section-heading">Choose Your Analysis</div>',

    unsafe_allow_html=True

)

selector1, selector2 = st.columns(2)

with selector1:

    if numeric_columns:

        default_metric = get_business_metric(filtered_df)

        metric_index = (

            numeric_columns.index(default_metric)

            if default_metric in numeric_columns else 0

        )

        metric_column = st.selectbox(

            "Business Metric",

            numeric_columns,

            index=metric_index

        )

    else:

        metric_column = None

        st.info("No suitable numerical metric found.")

with selector2:

    if category_candidates:

        default_category = get_category_column(filtered_df)

        category_index = (

            category_candidates.index(default_category)

            if default_category in category_candidates else 0

        )

        category_column = st.selectbox(

            "Analysis Category",

            category_candidates,

            index=category_index

        )

    else:

        category_column = None

        st.info("No suitable category found.")

# ==================================================

# BUSINESS ANALYTICS

# ==================================================

st.markdown(

    '<div class="section-heading">Business Analytics</div>',

    unsafe_allow_html=True

)

left_chart, right_chart = st.columns(2, gap="large")

# ==================================================

# BAR CHART

# ==================================================

with left_chart:

    if metric_column and category_column:

        bar_data = (

            filtered_df

            .groupby(category_column, dropna=False)[metric_column]

            .sum()

            .reset_index()

            .sort_values(metric_column, ascending=False)

        )

        fig_bar = px.bar(

            bar_data,

            x=metric_column,

            y=category_column,

            orientation="h",

            text=metric_column,

            title=f"{humanize_column(metric_column)} by {humanize_column(category_column)}",

            color_discrete_sequence=["#0D9488"]

        )

        fig_bar.update_traces(

            texttemplate="%{text:,.2f}",

            textposition="outside"

        )

        fig_bar.update_layout(

            yaxis={"categoryorder": "total ascending"},

            xaxis_title=humanize_column(metric_column),

            yaxis_title=humanize_column(category_column)

        )

        fig_bar = style_chart(fig_bar, 300)

        st.plotly_chart(

            fig_bar,

            use_container_width=True

        )

    else:

        st.info("Select a numerical metric and category to view this chart.")

    # --------------------------------------------------

# DONUT CHART

# --------------------------------------------------

with right_chart:

    if category_column is not None:

        pie_data = (

            filtered_df[category_column]

            .astype(str)

            .value_counts()

            .head(8)

            .reset_index()

        )

        pie_data.columns = [

            category_column,

            "Count"

        ]

        fig_pie = px.pie(

            pie_data,

            names=category_column,

            values="Count",

            hole=0.58,

            color_discrete_sequence=CHART_COLORS,

            title=f"{humanize_column(category_column)} Mix"

        )

        fig_pie.update_traces(

            textposition="inside",

            textinfo="percent",

            marker=dict(

                line=dict(

                    color="#111722",

                    width=3

                )

            ),

            hovertemplate=(

                "%{label}<br>"

                "Records: %{value}<br>"

                "Share: %{percent}"

                "<extra></extra>"

            )

        )

        fig_pie.update_layout(

            showlegend=True,

            legend=dict(

                orientation="h",

                yanchor="bottom",

                y=-0.20,

                xanchor="center",

                x=0.5,

                font=dict(size=10)

            )

        )

        fig_pie = style_chart(fig_pie, 300)
        fig_pie.update_layout(
            showlegend=True,
            legend=dict(orientation="v", yanchor="middle", y=0.5,
                        xanchor="left", x=1.01, font=dict(size=9)),
            margin=dict(l=12, r=105, t=52, b=18)
        )

        st.plotly_chart(

            fig_pie,

            use_container_width=True

        )

    else:

        st.info(

            "No suitable category column is available for distribution."

        )

# ==================================================
# PERFORMANCE ANALYSIS
# ==================================================

analysis_left, analysis_right = st.columns(2, gap="large")

with analysis_left:
    if metric_column is not None:

        st.markdown(

            '<div class="section-heading">Numerical Analysis</div>',

            unsafe_allow_html=True

        )

        histogram_data = filtered_df[metric_column].dropna()

        if not histogram_data.empty:

            fig_hist = px.histogram(

                histogram_data.to_frame(),

                x=metric_column,

                nbins=25,

                color_discrete_sequence=["#2563EB"],

                title=f"{humanize_column(metric_column)} Distribution"

            )

            fig_hist.update_traces(

                marker_line_width=0,

                opacity=0.85

            )

            fig_hist.update_layout(

                xaxis_title=humanize_column(metric_column),

                yaxis_title="Frequency",

                showlegend=False

            )

            fig_hist = style_chart(fig_hist, 280)

            st.plotly_chart(

                fig_hist,

                use_container_width=True

            )

    else:

        st.info(

            "No suitable business metric was found. "

            "Identifier columns are excluded from numerical analysis."

        )


with analysis_right:
    if date_column is not None and metric_column is not None:

        st.markdown(

            '<div class="section-heading">Performance Trend</div>',

            unsafe_allow_html=True

        )

        line_data = (

            filtered_df[[date_column, metric_column]]

            .dropna()

            .groupby(date_column)[metric_column]

            .sum()

            .reset_index()

            .sort_values(date_column)

        )

        if not line_data.empty:

            if line_data[date_column].nunique() >= 2:

                fig_line = px.line(

                    line_data,

                    x=date_column,

                    y=metric_column,

                    markers=True,

                    title=f"{humanize_column(metric_column)} Over Time",

                    color_discrete_sequence=["#0D9488"]

                )

                fig_line.update_traces(

                    line=dict(width=3),

                    marker=dict(size=8),

                    hovertemplate=(

                        "%{x}<br>"

                        f"{metric_column}: %{{y:,.2f}}"

                        "<extra></extra>"

                    )

                )

                fig_line.update_layout(

                    xaxis_title="Date",

                    yaxis_title=humanize_column(metric_column),

                    showlegend=False

                )

            else:

                fig_line = px.bar(

                    line_data,

                    x=date_column,

                    y=metric_column,

                    text=metric_column,

                    title=f"{humanize_column(metric_column)} by Date",

                    color_discrete_sequence=["#0D9488"]

                )

                fig_line.update_traces(

                    texttemplate="%{text:,.2f}",

                    textposition="outside"

                )

                fig_line.update_layout(

                    xaxis_title="Date",

                    yaxis_title=humanize_column(metric_column),

                    showlegend=False

                )

            fig_line = style_chart(fig_line, 300)

            st.plotly_chart(

                fig_line,

                use_container_width=True

            )

        else:

            st.info(

                "No valid date and business metric records "

                "are available for the selected filters."

            )


# ==================================================

# AI BUSINESS ANALYST

# ==================================================

st.markdown(

    '<div class="section-heading">AI Business Analyst</div>',

    unsafe_allow_html=True

)

st.write(

    "Ask questions about your dataset and receive "

    "findings, explanations and practical strategies."

)

user_question = st.text_area(

    "Your business question",

    placeholder=(

        "Example: What are the main business problems "

        "and how can we improve performance?"

    ),

    height=100

)

if st.button(

    "Generate AI Analysis",

    type="primary"

):

    if not user_question.strip():

        st.warning("Please enter a question.")

    else:

        try:

            with st.spinner(

                "AI agents are analyzing your data..."

            ):

                dataset_summary = generate_dataset_summary(

                    filtered_df

                )

                result = business_workflow.invoke({

                    "df": filtered_df,

                    "dataset_summary": dataset_summary,

                    "user_question": user_question,

                    "analysis_result": "",

                    "business_insights": ""

                })

            st.session_state["ai_analysis_result"] = result["analysis_result"]
            st.session_state["ai_business_insights"] = result["business_insights"]

            st.subheader("📊 Data Analyst Findings")
            st.markdown(result["analysis_result"])

            st.subheader("💡 Business Insights and Strategies")
            st.markdown(result["business_insights"])

        except Exception as e:

            st.error(

                f"AI analysis failed: {e}"

            )

# ==================================================

# PDF REPORT

# ==================================================

st.markdown(

    '<div class="section-heading">Export Business Report</div>',

    unsafe_allow_html=True

)

try:

    pdf_file = generate_pdf(
        filtered_df,
        kpis,
        metric_column=metric_column,
        category_column=category_column,
        date_column=date_column,
        dataset_name=getattr(uploaded_file, "name", "Business Dataset"),
        ai_findings=st.session_state.get("ai_analysis_result", ""),
        business_insights=st.session_state.get("ai_business_insights", "")
    )

    st.download_button(

        label="📄 Download PDF Report",

        data=pdf_file,

        file_name="AI_Business_Intelligence_Report.pdf",

        mime="application/pdf"

    )

except Exception as e:

    st.warning(

        f"PDF report could not be generated: {e}"

    )

# ==================================================

# DATASET PREVIEW

# ==================================================

with st.expander("View Dataset Preview"):

    st.dataframe(

        filtered_df.head(100),

        use_container_width=True

    )

with st.expander("Dataset Information"):

    st.write(

        "Total Records:",

        len(filtered_df)

    )

    st.write(

        "Total Columns:",

        len(filtered_df.columns)

    )

    st.write(

        "Column Names:",

        list(filtered_df.columns)

    )

    st.write("Missing Values")

    missing_data = (

        filtered_df.isnull()

        .sum()

        .reset_index()

    )

    missing_data.columns = [

        "Column",

        "Missing Values"

    ]

    st.dataframe(

        missing_data,

        use_container_width=True

    )

    st.write("Numerical Statistics")

    if numeric_columns:

        st.dataframe(

            filtered_df[numeric_columns]

            .describe()

            .transpose(),

            use_container_width=True

        )

    else:

        st.info("No suitable numerical columns available.")
