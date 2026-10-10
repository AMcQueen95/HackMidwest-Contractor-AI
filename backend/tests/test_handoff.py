import json
import subprocess
import sys
from pathlib import Path

from backend.app.data.loader import SAMPLE_DIRECTORY

ROOT = Path(__file__).resolve().parents[2]


def test_generator_is_deterministic_and_demo_runs_outside_checkout(tmp_path):
    destination = tmp_path / "books"
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_sample_data.py"),
            "--output",
            str(destination),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    before = {file.name: file.read_bytes() for file in destination.iterdir()}
    assert before == {name: (SAMPLE_DIRECTORY / name).read_bytes() for name in before}
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/generate_sample_data.py"),
            "--output",
            str(destination),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert before == {file.name: file.read_bytes() for file in destination.iterdir()}
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts/demo_finance.py"),
            "--books",
            str(destination),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["monthly_summary"]["profit"] == -7830
    assert report["receivables"]["total_outstanding"] == 21000
    assert report["affordability"]["collection_scenario"]["can_afford"] is True
