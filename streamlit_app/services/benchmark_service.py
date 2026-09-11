import subprocess
import pandas as pd
from pathlib import Path

RESULTS_FILE = Path("evaluation/results.csv")

def run_benchmarks():
    result = subprocess.run(
        ["python", "evaluation/run_benchmarks.py"],
        capture_output=True,
        text=True,
    )
    return result.stdout

def load_results():
    if RESULTS_FILE.exists():
        return pd.read_csv(RESULTS_FILE)
    return pd.DataFrame()