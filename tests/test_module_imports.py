import importlib
from pathlib import Path


def test_all_core_modules_import():
    package = Path(__file__).parents[1] / "src" / "xau_detective"
    modules = sorted(
        path.stem
        for path in package.glob("*.py")
        if path.name != "__init__.py"
    )
    for module in modules:
        importlib.import_module(f"xau_detective.{module}")
