
def generate_dataset_summary(df):

    summary = []

    summary.append(f"Total records: {len(df)}")
    summary.append(f"Total columns: {len(df.columns)}")

    summary.append("\nColumn Information:")

    for column in df.columns:
        summary.append(
            f"- {column}: Data type = {df[column].dtype}, "
            f"Missing values = {df[column].isnull().sum()}"
        )

    # Numerical summary
    numeric_columns = df.select_dtypes(
        include="number"
    ).columns.tolist()

    summary.append("\nNumerical Summary:")

    if numeric_columns:
        summary.append(
            df[numeric_columns].describe().to_string()
        )

    # Categorical summary
    categorical_columns = df.select_dtypes(
        include=["object", "category", "bool"]
    ).columns.tolist()

    summary.append("\nCategorical Summary:")

    for column in categorical_columns:

        summary.append(f"\n{column}:")

        summary.append(
            df[column].value_counts().head(10).to_string()
        )

    # Group-wise numerical analysis
    summary.append("\nGroup-wise Numerical Analysis:")

    for category in categorical_columns:

        for numeric in numeric_columns:

            summary.append(
                f"\n{numeric} grouped by {category}:"
            )

            grouped_data = (
                df.groupby(category, dropna=False)[numeric]
                .agg(["sum", "mean", "count"])
                .sort_values("sum", ascending=False)
                .head(10)
            )

            summary.append(grouped_data.to_string())

    return "\n".join(summary)
