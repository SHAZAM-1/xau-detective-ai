from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "project_health_check.py"


def test_health_checker_runs_and_reports_inventory():
    result = subprocess.run(
        [sys.executable, str(CHECKER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert "# XAU Detective AI — Project Health Check" in result.stdout
    assert "Source inventory:" in result.stdout
    assert "Test inventory:" in result.stdout
