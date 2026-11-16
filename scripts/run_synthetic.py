"""Run the analysis on artificial data."""
from configuration import load_settings
from analysis_runner import run_pipeline
import sys


if __name__ == "__main__":
    selected_settings = sys.argv[1] if len(sys.argv) > 1 else "analysis_settings"
    if len(sys.argv) > 2:
        raise SystemExit("Usage: python run_synthetic.py [analysis_settings_module]")
    run_pipeline(load_settings(selected_settings), mode="synthetic")
