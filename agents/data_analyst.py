
import re
import difflib
import pandas as pd

from utils.llm_client import get_llm


MAX_PROMPT_CHARS = 14000


# =====================================================
# 1. COLUMN DETECTION
# =====================================================

def normalize_text(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def find_column(df, question, column_list):

    question_normalized = normalize_text(question)

    for column in column_list:

        column_normalized = normalize_text(column)

        if column_normalized and column_normalized in question_normalized:
            return column

    normalized_columns = {
        normalize_text(column): column
        for column in column_list
    }

    question_words = re.findall(r"[a-z0-9]+", question.lower())

    for word in question_words:

        if len(word) < 3:
            continue

        matches = difflib.get_close_matches(
            normalize_text(word),
            normalized_columns.keys(),
            n=1,
            cutoff=0.85
        )

        if matches:
            return normalized_columns[matches[0]]

    return None


# =====================================================
# 2. CALCULATION TYPE
# =====================================================

def detect_calculation_type(user_question):

    question = user_question.lower()

    if any(word in question for word in ["average", "mean", "avg"]):
        return "average"

    if any(word in question for word in ["how many", "count", "number of"]):
        return "count"

    if any(word in question for word in ["highest", "maximum", "max", "most", "top"]):
        return "maximum"

    if any(word in question for word in ["lowest", "minimum", "min", "least", "bottom"]):
        return "minimum"

    if any(word in question for word in ["total", "sum", "overall"]):
        return "sum"

    if any(word in question for word in [
        "trend", "growth", "over time", "monthly", "yearly"
    ]):
        return "trend"

    return "general"


# =====================================================
# 3. NUMERICAL SUMMARY
# =====================================================

def calculate_numeric_summary(df):

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    results = {}

    for column in numeric_columns[:8]:

        series = pd.to_numeric(
            df[column],
            errors="coerce"
        ).dropna()

        if series.empty:
            continue

        results[str(column)] = {
            "total": round(float(series.sum()), 2),
            "average": round(float(series.mean()), 2),
            "maximum": round(float(series.max()), 2),
            "minimum": round(float(series.min()), 2),
            "count": int(series.count())
        }

    return results


# =====================================================
# 4. CATEGORY SUMMARY
# =====================================================

def calculate_category_summary(df):

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    preferred_keywords = [
        "category", "product", "region",
        "segment", "customer", "country"
    ]

    selected_categories = []

    for keyword in preferred_keywords:

        for column in categorical_columns:

            if (
                keyword in str(column).lower()
                and column not in selected_categories
                and 2 <= df[column].nunique(dropna=True) <= 100
            ):
                selected_categories.append(column)
                break

        if len(selected_categories) >= 3:
            break

    for column in categorical_columns:

        if len(selected_categories) >= 3:
            break

        if (
            column not in selected_categories
            and 2 <= df[column].nunique(dropna=True) <= 30
        ):
            selected_categories.append(column)

    results = {}

    for category in selected_categories:

        for numeric in numeric_columns[:3]:

            grouped = (
                df.groupby(category, dropna=False)[numeric]
                .agg(["sum", "mean", "count"])
                .sort_values("sum", ascending=False)
                .head(5)
                .round(2)
            )

            results[
                f"{numeric} grouped by {category}"
            ] = grouped.to_dict(orient="index")

    return results


# =====================================================
# 5. DYNAMIC CALCULATION ENGINE
# =====================================================

def execute_calculation(df, user_question):

    calculation_type = detect_calculation_type(user_question)

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    all_columns = df.columns.tolist()

    question = user_question.lower()

    # COUNT
    if calculation_type == "count":

        selected_column = find_column(
            df, user_question, all_columns
        )

        if selected_column:

            series = df[selected_column].dropna()

            if any(word in selected_column.lower() for word in [
                "id", "customer", "product", "order"
            ]):
                result = series.nunique()
                method = "unique count"
            else:
                result = series.count()
                method = "non-empty count"

            return {
                "operation": "count",
                "column": str(selected_column),
                "result": int(result),
                "method": method
            }

        return {
            "operation": "count",
            "result": int(len(df)),
            "method": "total records"
        }

    # GENERAL QUESTION
    if calculation_type == "general":

        return {
            "operation": "general",
            "message": "No specific calculation detected."
        }

    if not numeric_columns:

        return {
            "error": "No numerical columns available."
        }

    # FIND METRIC
    metric_column = find_column(
        df, user_question, numeric_columns
    )

    if metric_column is None:

        metric_keywords = [
            "sales", "revenue", "profit",
            "amount", "total", "quantity"
        ]

        for keyword in metric_keywords:

            for column in numeric_columns:

                if keyword in str(column).lower():
                    metric_column = column
                    break

            if metric_column:
                break

    if metric_column is None:

        if len(numeric_columns) == 1:
            metric_column = numeric_columns[0]
        else:
            return {
                "error": "Could not identify the numerical metric.",
                "available_columns": [
                    str(col) for col in numeric_columns[:15]
                ]
            }

    series = pd.to_numeric(
        df[metric_column],
        errors="coerce"
    ).dropna()

    if series.empty:
        return {
            "error": f"No valid values in {metric_column}."
        }

    # CATEGORY COMPARISON
    category_column = find_column(
        df, user_question, categorical_columns
    )

    comparison_requested = any(word in question for word in [
        "by", "per", "region", "category",
        "product", "segment", "department",
        "compare", "which"
    ])

    if category_column and comparison_requested:

        grouped = (
            df.groupby(category_column, dropna=False)[metric_column]
            .agg(["sum", "mean", "count"])
        )

        sort_column = (
            "mean" if calculation_type == "average" else "sum"
        )

        ascending = calculation_type == "minimum"

        result = (
            grouped.sort_values(
                sort_column,
                ascending=ascending
            )
            .head(5)
            .round(2)
        )

        return {
            "operation": f"{calculation_type} by category",
            "metric": str(metric_column),
            "category": str(category_column),
            "results": result.to_dict(orient="index")
        }

    # DIRECT CALCULATION
    if calculation_type == "sum":
        result = series.sum()

    elif calculation_type == "average":
        result = series.mean()

    elif calculation_type == "maximum":
        result = series.max()

    elif calculation_type == "minimum":
        result = series.min()

    elif calculation_type == "trend":

        date_column = next(
            (
                col for col in df.columns
                if "date" in str(col).lower()
            ),
            None
        )

        if date_column is None:
            return {
                "error": "No date column identified."
            }

        dates = pd.to_datetime(
            df[date_column],
            errors="coerce"
        )

        trend = pd.DataFrame({
            "period": dates.dt.to_period("M").astype(str),
            "value": pd.to_numeric(
                df[metric_column],
                errors="coerce"
            )
        }).dropna()

        grouped = (
            trend.groupby("period")["value"]
            .sum()
            .sort_index()
            .tail(24)
        )

        return {
            "operation": "monthly trend",
            "metric": str(metric_column),
            "results": {
                str(key): round(float(value), 2)
                for key, value in grouped.items()
            }
        }

    else:
        return {
            "error": "Unsupported calculation."
        }

    return {
        "operation": calculation_type,
        "column": str(metric_column),
        "result": round(float(result), 2)
    }


# =====================================================
# 6. DATASET INFORMATION
# =====================================================

def generate_dataset_information(df):

    information = []

    information.append("DATASET OVERVIEW")
    information.append(f"Total records: {len(df):,}")
    information.append(f"Total columns: {len(df.columns)}")

    information.append(
        "Columns: " +
        ", ".join(str(col) for col in df.columns[:35])
    )

    information.append("\nCOLUMN TYPES AND MISSING VALUES")

    for column in df.columns[:25]:

        missing = int(df[column].isnull().sum())

        information.append(
            f"- {column}: {df[column].dtype}; "
            f"Missing={missing:,}"
        )

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    information.append("\nNUMERICAL STATISTICS")

    for column in numeric_columns[:8]:

        values = pd.to_numeric(
            df[column],
            errors="coerce"
        ).dropna()

        if not values.empty:

            information.append(
                f"- {column}: "
                f"Total={values.sum():,.2f}, "
                f"Average={values.mean():,.2f}, "
                f"Min={values.min():,.2f}, "
                f"Max={values.max():,.2f}"
            )

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    information.append("\nCATEGORICAL INFORMATION")

    selected = []

    for keyword in [
        "category", "product", "region",
        "customer", "country", "segment"
    ]:

        for column in categorical_columns:

            if keyword in str(column).lower():
                if column not in selected:
                    selected.append(column)

        if len(selected) >= 5:
            break

    for column in categorical_columns:

        if len(selected) >= 5:
            break

        if (
            column not in selected
            and df[column].nunique(dropna=True) <= 100
        ):
            selected.append(column)

    for column in selected:

        counts = (
            df[column]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .head(5)
        )

        information.append(f"\n{column}:")

        for value, count in counts.items():
            information.append(f"- {value}: {count:,}")

    result = "\n".join(information)

    return result[:9000]


# =====================================================
# 7. MAIN DATA ANALYST AGENT
# =====================================================

def analyze_dataset(df, user_question):

    if df is None or df.empty:
        return "The uploaded dataset is empty."

    # Python calculations
    numeric_results = calculate_numeric_summary(df)

    category_results = calculate_category_summary(df)

    dynamic_result = execute_calculation(
        df,
        user_question
    )

    dataset_info = generate_dataset_information(df)

    # Compact LLM prompt
    prompt = f"""
You are an experienced Business Data Analyst.

Analyze the user's question using the supplied
dataset information and Python calculation results.

DATASET INFORMATION:
{dataset_info}

NUMERICAL CALCULATIONS:
{numeric_results}

CATEGORY-WISE CALCULATIONS:
{category_results}

QUESTION-BASED PYTHON CALCULATION:
{dynamic_result}

USER QUESTION:
{user_question}

INSTRUCTIONS:

1. Answer the exact question.
2. Give priority to Python calculation results.
3. Never invent numerical values.
4. Explain findings in simple English.
5. Mention relevant column names.
6. Do not confuse totals, averages and counts.
7. If information is unavailable, say so clearly.
8. Keep the response concise and professional.

FORMAT:

Direct Answer
Important Findings
Business Recommendation
"""

    prompt = prompt[:MAX_PROMPT_CHARS]

    # LLM request
    try:

        llm = get_llm()

        response = llm.invoke(prompt)

        content = getattr(response, "content", response)

        if not isinstance(content, str):
            content = str(content)

        if not content.strip():
            raise ValueError("Data Analyst returned an empty response.")

        return content

    except Exception as e:

        raise RuntimeError(
            f"Data Analyst LLM request failed: {str(e)}"
        ) from e
