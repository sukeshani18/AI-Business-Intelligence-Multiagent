
import re
import difflib
import pandas as pd

from utils.llm_client import get_llm


# =====================================================
# 1. COLUMN DETECTION
# =====================================================

def normalize_text(value):
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def find_column(df, question, column_list):
    """
    Identify a dataset column mentioned in the question.
    """

    question_normalized = normalize_text(question)

    # Exact and partial matching
    for column in column_list:
        column_normalized = normalize_text(column)

        if column_normalized and column_normalized in question_normalized:
            return column

    # Fuzzy matching for slightly different wording
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
# 2. DETECT CALCULATION TYPE
# =====================================================

def detect_calculation_type(user_question):

    question = user_question.lower()

    if any(word in question for word in [
        "average", "mean", "avg"
    ]):
        return "average"

    if any(word in question for word in [
        "how many", "count", "number of"
    ]):
        return "count"

    if any(word in question for word in [
        "highest", "maximum", "max", "most", "top"
    ]):
        return "maximum"

    if any(word in question for word in [
        "lowest", "minimum", "min", "least", "bottom"
    ]):
        return "minimum"

    if any(word in question for word in [
        "total", "sum", "overall"
    ]):
        return "sum"

    if any(word in question for word in [
        "trend", "growth", "over time",
        "month-wise", "monthly", "yearly"
    ]):
        return "trend"

    return "general"


# =====================================================
# 3. NUMERICAL CALCULATIONS
# =====================================================

def calculate_numeric_summary(df):

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns

    results = {}

    for column in numeric_columns:

        series = df[column].dropna()

        if series.empty:
            continue

        results[column] = {
            "total": round(float(series.sum()), 2),
            "average": round(float(series.mean()), 2),
            "maximum": round(float(series.max()), 2),
            "minimum": round(float(series.min()), 2),
            "count": int(series.count())
        }

    return results


# =====================================================
# 4. CATEGORY-WISE CALCULATIONS
# =====================================================

def calculate_category_summary(df):

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns

    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns

    results = {}

    for category in categorical_columns:

        # Avoid very high-cardinality columns
        if df[category].nunique(dropna=True) > 100:
            continue

        for numeric in numeric_columns:

            grouped = (
                df.groupby(category, dropna=False)[numeric]
                .agg(["sum", "mean", "count"])
                .sort_values("sum", ascending=False)
                .head(10)
                .round(2)
            )

            results[f"{numeric} grouped by {category}"] = (
                grouped.to_string()
            )

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

    # ---------------------------------------------
    # COUNT CALCULATION
    # ---------------------------------------------

    if calculation_type == "count":

        selected_column = find_column(
            df, user_question, all_columns
        )

        if selected_column:

            series = df[selected_column].dropna()

            # Count unique customers, products, orders, etc.
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
                "column": selected_column,
                "result": int(result),
                "method": method
            }

        return {
            "operation": "count",
            "result": int(len(df)),
            "method": "total records"
        }

    # ---------------------------------------------
    # GENERAL QUESTION
    # ---------------------------------------------

    if calculation_type == "general":

        return {
            "operation": "general",
            "message": "No specific calculation detected."
        }

    # ---------------------------------------------
    # FIND NUMERICAL COLUMN
    # ---------------------------------------------

    if not numeric_columns:

        return {
            "error": "No numerical columns available."
        }

    metric_column = find_column(
        df, user_question, numeric_columns
    )

    if metric_column is None:

        if len(numeric_columns) == 1:
            metric_column = numeric_columns[0]

        else:
            return {
                "error": "Could not identify the numerical metric.",
                "available_columns": numeric_columns
            }

    series = df[metric_column].dropna()

    if series.empty:

        return {
            "error": f"No valid values in {metric_column}."
        }

    # ---------------------------------------------
    # CATEGORY-WISE COMPARISON
    # ---------------------------------------------

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

        if calculation_type == "maximum":

            result = grouped.sort_values(
                "sum", ascending=False
            ).head(5)

        elif calculation_type == "minimum":

            result = grouped.sort_values(
                "sum", ascending=True
            ).head(5)

        elif calculation_type == "average":

            result = grouped.sort_values(
                "mean", ascending=False
            ).head(5)

        else:

            result = grouped.sort_values(
                "sum", ascending=False
            ).head(5)

        return {
            "operation": f"{calculation_type} by category",
            "metric": metric_column,
            "category": category_column,
            "results": result.round(2).to_dict(orient="index")
        }

    # ---------------------------------------------
    # DIRECT NUMERICAL CALCULATIONS
    # ---------------------------------------------

    if calculation_type == "sum":
        result = series.sum()

    elif calculation_type == "average":
        result = series.mean()

    elif calculation_type == "maximum":
        result = series.max()

    elif calculation_type == "minimum":
        result = series.min()

    else:
        return {
            "error": "Unsupported calculation."
        }

    return {
        "operation": calculation_type,
        "column": metric_column,
        "result": round(float(result), 2)
    }


# =====================================================
# 6. DATASET INFORMATION
# =====================================================

def generate_dataset_information(df):

    information = []

    information.append("DATASET OVERVIEW")

    information.append(f"Total records: {len(df)}")
    information.append(f"Total columns: {len(df.columns)}")

    information.append(
        f"Column names: {list(df.columns)}"
    )

    information.append("\nDATA TYPES AND MISSING VALUES")

    information.append(
        df.dtypes.to_string()
    )

    information.append(
        df.isnull().sum().to_string()
    )

    # Numerical statistics
    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    information.append("\nNUMERICAL STATISTICS")

    if numeric_columns:

        information.append(
            df[numeric_columns].describe().round(2).to_string()
        )

    else:

        information.append("No numerical columns available.")

    # Categorical information
    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns

    information.append("\nCATEGORICAL INFORMATION")

    for column in categorical_columns:

        information.append(f"\n{column}:")

        information.append(
            df[column]
            .value_counts(dropna=False)
            .head(10)
            .to_string()
        )

    return "\n".join(information)


# =====================================================
# 7. MAIN DATA ANALYST AGENT
# =====================================================

def analyze_dataset(df, user_question):

    if df is None or df.empty:
        return "The uploaded dataset is empty."

    try:

        # Initialize LLM
        llm = get_llm()

        # Actual calculations
        numeric_results = calculate_numeric_summary(df)

        category_results = calculate_category_summary(df)

        dynamic_result = execute_calculation(
            df, user_question
        )

        # Dataset information
        dataset_info = generate_dataset_information(df)

        # Prepare AI prompt
        prompt = f"""
You are an experienced Business Data Analyst.

Your task is to analyze business datasets and answer
questions accurately in simple, natural English.

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

1. Answer the user's exact question.
2. Give priority to the actual Python calculation results.
3. Never invent or modify numerical values.
4. Use category-wise results for comparisons.
5. Explain findings in simple English.
6. Mention the relevant column names.
7. Explain possible business reasons only when supported.
8. Suggest practical strategies when relevant.
9. If required information is unavailable, say so clearly.
10. Do not confuse totals, averages and counts.
11. Keep the response concise and professional.
12. Do not claim a calculation was performed if its result
    is unavailable or its required column could not be identified.

ANSWER FORMAT:

- Direct Answer
- Important Findings
- Business Recommendation (when relevant)

Avoid unnecessary technical terminology.
"""

        response = llm.invoke(prompt)

        return response.content

    except Exception as e:

        return (
            "Unable to analyze the dataset at this time. "
            f"Error: {str(e)}"
        )
