import importlib.util
import subprocess
import sys
from pathlib import Path

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



def test_changed_test_mapping_uses_imports_not_only_filenames():
    spec = importlib.util.spec_from_file_location(
        "project_health_check", CHECKER
    )
    assert spec is not None and spec.loader is not None
    health = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(health)

    targets = health.test_targets(
        [ROOT / "tests" / "test_numeric_validation_hardening.py"]
    )
    assert "trading_profile" in targets
    assert "mt5_demo_runtime" in targets
