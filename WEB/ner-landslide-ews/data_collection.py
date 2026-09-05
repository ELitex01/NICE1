""" from data_collection import merge_csv.
reads every CSV inside train/ and test/ folders."""
import os
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))

def merge_csv(folder):
    path = os.path.join(_HERE, folder)
    files = sorted(f for f in os.listdir(path) if f.lower().endswith(".csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {path}")
    return pd.concat([pd.read_csv(os.path.join(path, f)) for f in files],
                     ignore_index=True)