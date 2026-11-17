
import pandas as pd


def generate_dataset_summary(df: pd.DataFrame):

    if df is None or df.empty:
        return "The dataset is empty."

    summary = []

    summary.append("DATASET OVERVIEW")
    summary.append(f"Total records: {len(df):,}")
    summary.append(f"Total columns: {len(df.columns)}")

    # Column information
    summary.append("\nCOLUMN INFORMATION")

    for column in df.columns[:30]:

        missing = int(df[column].isnull().sum())

        summary.append(
            f"- {column}: "
            f"Type={df[column].dtype}, "
            f"Missing={missing:,}"
        )

    if len(df.columns) > 30:
        summary.append("Additional columns omitted from summary.")

    # Numerical summary
    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    summary.append("\nNUMERICAL SUMMARY")

    for column in numeric_columns[:8]:

        values = pd.to_numeric(
            df[column],
            errors="coerce"
        ).dropna()

        if values.empty:
            continue

        summary.append(
            f"- {column}: "
            f"Total={values.sum():,.2f}, "
            f"Average={values.mean():,.2f}, "
            f"Minimum={values.min():,.2f}, "
            f"Maximum={values.max():,.2f}"
        )

    # Categorical summary
    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    summary.append("\nCATEGORICAL SUMMARY")

    selected_columns = []

    preferred_keywords = [
        "category",
        "product",
        "region",
        "customer",
        "country",
        "segment",
        "city"
    ]

    for keyword in preferred_keywords:

        for column in categorical_columns:

            if (
                keyword in str(column).lower()
                and column not in selected_columns
            ):
                selected_columns.append(column)

                if len(selected_columns) >= 5:
                    break

        if len(selected_columns) >= 5:
            break

    for column in categorical_columns:

        if len(selected_columns) >= 5:
            break

        if (
            column not in selected_columns
            and 2 <= df[column].nunique(dropna=True) <= 100
        ):
            selected_columns.append(column)

    for column in selected_columns:

        counts = (
            df[column]
            .fillna("Unknown")
            .astype(str)
            .value_counts()
            .head(5)
        )

        summary.append(f"\n{column}:")

        for value, count in counts.items():
            summary.append(f"- {value}: {count:,}")

    # Strict output size limit
    result = "\n".join(summary)

    return result[:6000]
