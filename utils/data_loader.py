import pandas as pd


def load_csv(file):
    """
    Load an uploaded CSV file into a DataFrame.
    """
    try:
        df = pd.read_csv(file)
        return df

    except Exception as e:
        raise ValueError(f"Unable to read CSV file: {e}")