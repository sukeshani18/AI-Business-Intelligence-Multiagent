import io
import re
from typing import Any

import pandas as pd
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from graph.workflow import business_workflow
from utils.data_summary import generate_dataset_summary


app = FastAPI(title="AI Business Intelligence API")

app.add_middleware(
    CORSMiddleware,
   allow_origins=[
    "http://localhost:3000",
    "http://127.0.0.1:8000",
    "https://*.vercel.app",
],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

uploaded_df = None


class QuestionRequest(BaseModel):
    question: str


def clean_name(name: str) -> str:
    name = re.sub(r"([a-z])([A-Z])", r"\1 \2", str(name))
    name = name.replace("_", " ").replace("-", " ")
    return " ".join(name.split()).title()


def safe_value(value: Any):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    return value


def safe_records(df: pd.DataFrame):
    records = df.head(10).to_dict(orient="records")
    return [
        {str(key): safe_value(value) for key, value in row.items()}
        for row in records
    ]


def find_column(columns, keywords):
    for keyword in keywords:
        for column in columns:
            normalized = re.sub(
                r"[^a-z0-9]", "", str(column).lower()
            )
            if keyword in normalized:
                return column
    return None


def detect_date_column(df: pd.DataFrame):
    preferred = []

    for column in df.columns:
        name = str(column).lower()
        if any(word in name for word in ["date", "time", "month", "year"]):
            preferred.append(column)

    candidates = preferred + [
        col for col in df.columns if col not in preferred
    ]

    for column in candidates:
        series = df[column]

        if pd.api.types.is_numeric_dtype(series):
            continue

        try:
            parsed = pd.to_datetime(series, errors="coerce")
            valid_ratio = parsed.notna().mean()

            if valid_ratio >= 0.70 and parsed.nunique() >= 2:
                return column, parsed
        except (ValueError, TypeError):
            continue

    return None, None


def get_numeric_columns(df: pd.DataFrame):
    return [
        col for col in df.select_dtypes(include="number").columns
        if not any(
            word in str(col).lower()
            for word in [
                "id", "code", "zip", "postal", "phone",
                "latitude", "longitude"
            ]
        )
    ]


def get_category_column(df: pd.DataFrame):
    preferred_keywords = [
        "category", "product", "region", "city", "segment",
        "department", "channel", "store", "customer", "country",
        "state", "type", "status", "brand"
    ]

    categorical = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    for keyword in preferred_keywords:
        for column in categorical:
            if keyword in str(column).lower():
                unique_count = df[column].nunique(dropna=True)
                if 2 <= unique_count <= 30:
                    return column

    for column in categorical:
        unique_count = df[column].nunique(dropna=True)
        if 2 <= unique_count <= 15:
            return column

    return None


def get_main_metric(df: pd.DataFrame):
    numeric_columns = get_numeric_columns(df)

    metric_keywords = [
        "revenue", "sales", "profit", "amount",
        "turnover", "income", "total", "value",
        "quantity", "units", "price"
    ]

    for keyword in metric_keywords:
        for column in numeric_columns:
            if keyword in str(column).lower():
                return column

    return numeric_columns[0] if numeric_columns else None


def make_kpis(df: pd.DataFrame):
    kpis = []

    revenue_col = find_column(
        df.columns,
        ["revenue", "sales", "turnover", "totalamount", "salesamount"]
    )

    profit_col = find_column(
        df.columns,
        ["profit", "netincome", "earnings"]
    )

    order_col = find_column(
        df.columns,
        ["orderid", "ordernumber", "transactionid"]
    )

    customer_col = find_column(
        df.columns,
        ["customerid", "customername", "clientid", "clientname"]
    )

    def add_kpi(label, value, format_type="number"):
        if value is None:
            return

        try:
            value = float(value)
            if pd.isna(value):
                return
        except (ValueError, TypeError):
            return

        kpis.append({
            "label": label,
            "value": value,
            "format": format_type,
        })

    add_kpi("Total Records", len(df))

    if revenue_col:
        add_kpi("Total Revenue", df[revenue_col].sum(), "currency")

    if profit_col:
        add_kpi("Total Profit", df[profit_col].sum(), "currency")

    if order_col:
        add_kpi("Total Orders", df[order_col].nunique())

    if customer_col:
        add_kpi("Unique Customers", df[customer_col].nunique())

    if revenue_col and order_col:
        order_count = df[order_col].nunique()
        if order_count:
            add_kpi(
                "Average Order Value",
                df[revenue_col].sum() / order_count,
                "currency"
            )

    if len(kpis) == 1:
        metric_col = get_main_metric(df)
        if metric_col:
            add_kpi(
                f"Total {clean_name(metric_col)}",
                df[metric_col].sum(),
                "number"
            )

    return kpis


def make_bar_chart(df, category_col, metric_col):
    if category_col is None:
        return None

    working = df[[category_col]].copy()
    working["_metric"] = df[metric_col] if metric_col else 1

    working[category_col] = (
        working[category_col].fillna("Unknown").astype(str)
    )

    grouped = (
        working.groupby(category_col)["_metric"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    if grouped.empty:
        return None

    metric_name = clean_name(metric_col) if metric_col else "Records"

    return {
        "type": "bar",
        "title": f"{metric_name} by {clean_name(category_col)}",
        "subtitle": f"Top {len(grouped)} categories",
        "labels": [str(x) for x in grouped.index],
        "values": [float(x) for x in grouped.values],
        "metric": metric_name,
    }


def make_donut_chart(df, category_col):
    if category_col is None:
        return None

    counts = (
        df[category_col]
        .fillna("Unknown")
        .astype(str)
        .value_counts()
        .head(6)
    )

    if len(counts) < 2:
        return None

    return {
        "type": "donut",
        "title": f"{clean_name(category_col)} Distribution",
        "subtitle": "Share of records by category",
        "labels": [str(x) for x in counts.index],
        "values": [int(x) for x in counts.values],
        "metric": "Records",
    }


def make_line_chart(df, date_col, parsed_dates, metric_col):
    if date_col is None or parsed_dates is None or metric_col is None:
        return None

    working = pd.DataFrame({
        "date": parsed_dates,
        "metric": pd.to_numeric(df[metric_col], errors="coerce"),
    }).dropna()

    if working.empty:
        return None

    working["period"] = working["date"].dt.to_period("M").astype(str)

    grouped = working.groupby("period")["metric"].sum().sort_index()

    if len(grouped) < 2:
        return None

    return {
        "type": "line",
        "title": f"Monthly {clean_name(metric_col)} Trend",
        "subtitle": f"Performance over time using {clean_name(date_col)}",
        "labels": [str(x) for x in grouped.index],
        "values": [float(x) for x in grouped.values],
        "metric": clean_name(metric_col),
    }


def make_histogram(df, metric_col):
    if metric_col is None:
        return None

    values = pd.to_numeric(df[metric_col], errors="coerce").dropna()

    if len(values) < 5 or values.nunique() < 2:
        return None

    counts, edges = pd.cut(
        values,
        bins=min(8, max(4, values.nunique())),
        include_lowest=True,
        retbins=True,
    )

    grouped = counts.value_counts(sort=False)

    labels = [
        f"{interval.left:,.1f} – {interval.right:,.1f}"
        for interval in grouped.index
    ]

    return {
        "type": "histogram",
        "title": f"{clean_name(metric_col)} Distribution",
        "subtitle": "Frequency distribution of numerical values",
        "labels": labels,
        "values": [int(x) for x in grouped.values],
        "metric": "Frequency",
    }


def generate_analytics(df: pd.DataFrame):
    date_col, parsed_dates = detect_date_column(df)
    metric_col = get_main_metric(df)
    category_col = get_category_column(df)

    charts = []

    line_chart = make_line_chart(
        df, date_col, parsed_dates, metric_col
    )
    if line_chart:
        charts.append(line_chart)

    bar_chart = make_bar_chart(df, category_col, metric_col)
    if bar_chart:
        charts.append(bar_chart)

    donut_chart = make_donut_chart(df, category_col)
    if donut_chart:
        charts.append(donut_chart)

    histogram = make_histogram(df, metric_col)
    if histogram:
        charts.append(histogram)

    return {
        "kpis": make_kpis(df),
        "charts": charts,
        "date_column": str(date_col) if date_col is not None else None,
        "record_count": len(df),
    }


@app.get("/")
def home():
    return {
        "message": "AI Business Intelligence API is running"
    }


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    global uploaded_df

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="Please upload a CSV file."
        )

    try:
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))

        if df.empty:
            raise HTTPException(
                status_code=400,
                detail="The uploaded CSV file is empty."
            )

        if len(df.columns) == 0:
            raise HTTPException(
                status_code=400,
                detail="No columns found in the CSV file."
            )

        uploaded_df = df

        try:
            summary = generate_dataset_summary(df)
        except Exception:
            summary = (
                f"Dataset contains {len(df)} records "
                f"and {len(df.columns)} columns."
            )

        return {
            "filename": file.filename,
            "total_records": int(len(df)),
            "total_columns": int(len(df.columns)),
            "columns": [str(col) for col in df.columns],
            "numeric_columns": [
                str(col) for col in get_numeric_columns(df)
            ],
            "summary": str(summary),
            "preview": safe_records(df),
        }

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process CSV file: {str(exc)}"
        )


@app.get("/analytics")
def get_analytics():
    if uploaded_df is None:
        raise HTTPException(
            status_code=400,
            detail="Please upload a dataset first."
        )

    try:
        return generate_analytics(uploaded_df)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Analytics generation failed: {str(exc)}"
        )


@app.post("/ask")
def ask_question(request: QuestionRequest):
    if uploaded_df is None:
        raise HTTPException(
            status_code=400,
            detail="Please upload a dataset first."
        )

    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Please enter a question."
        )

    try:
        result = business_workflow.invoke({
            "df": uploaded_df,
            "user_question": request.question.strip(),
        })

        if not isinstance(result, dict):
            raise ValueError("Unexpected response from the AI workflow.")

        # Match the actual keys returned by graph/workflow.py
        analysis = result.get(
            "analysis_result",
            result.get("analysis", result.get("data_analysis", ""))
        )

        insights = result.get(
            "business_insights",
            result.get("insights", "")
        )

        if not analysis or not str(analysis).strip():
            raise RuntimeError(
                "The Data Analyst did not return a response."
            )

        if not insights or not str(insights).strip():
            insights = "The Business Analyst did not return any insights."

        return {
            "analysis": str(analysis),
            "insights": str(insights),
        }

    except HTTPException:
        raise

    except Exception as exc:
        error_message = str(exc)
        error_lower = error_message.lower()

        if (
            "413" in error_message
            or "request too large" in error_lower
            or "payload too large" in error_lower
            or "content too large" in error_lower
        ):
            raise HTTPException(
                status_code=413,
                detail=(
                    "The AI request is too large. "
                    "Try a shorter question or a smaller dataset."
                )
            )

        raise HTTPException(
            status_code=502,
            detail=f"AI analysis failed: {error_message}"
        )
