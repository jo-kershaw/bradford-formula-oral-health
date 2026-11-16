"""Check output file organisation using synthetic/public data only."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from analysis_runner import write_table_pair, create_run_folders
from plots_external_reference import write_ohid_reference


def test_analysis_csv_and_markdown_are_in_different_folders(tmp_path):
    section = tmp_path / 'tables' / 'analysis'
    write_table_pair(pd.DataFrame({'n_children': [12]}), 'example', section, 'synthetic')
    csv = section / 'csv' / 'SYNTHETIC_example.csv'
    md = section / 'markdown' / 'SYNTHETIC_example.md'
    assert csv.is_file() and md.is_file()
    assert pd.read_csv(csv)['n_children'].tolist() == [12]
    assert 'SYNTHETIC DATA' in md.read_text(encoding='utf-8')
    assert not (section / 'SYNTHETIC_example.csv').exists()
    assert not (section / 'SYNTHETIC_example.md').exists()


def test_external_ohid_table_and_source_are_organised(tmp_path):
    figure = write_ohid_reference(tmp_path)
    base = tmp_path / 'tables' / 'external_reference'
    assert (base / 'csv' / 'ohid_bradford_england_all_index.csv').exists()
    assert (base / 'markdown' / 'ohid_bradford_england_all_index.md').exists()
    assert (base / 'markdown' / 'OHID_SOURCE.md').exists()
    assert figure.exists()


def test_old_results_are_not_touched_by_new_layout(tmp_path, monkeypatch):
    import analysis_runner
    monkeypatch.setattr(analysis_runner, 'RESULTS_ROOT', tmp_path)
    first = create_run_folders('synthetic')
    (first / 'RUN_INFO.txt').write_text('keep me', encoding='utf-8')
    second = create_run_folders('synthetic')
    assert first != second
    assert (first / 'RUN_INFO.txt').read_text(encoding='utf-8') == 'keep me'
