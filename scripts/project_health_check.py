"""Repository-wide static health check for XAU Detective AI."""
from __future__ import annotations

import argparse
import ast
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "xau_detective"
TESTS = ROOT / "tests"
WORKFLOWS = ROOT / ".github" / "workflows"


def run_git(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def module_name(path: Path) -> str:
    return ".".join(path.relative_to(SRC.parent).with_suffix("").parts)


def python_files() -> list[Path]:
    return sorted(SRC.rglob("*.py")) if SRC.exists() else []


def test_files() -> list[Path]:
    return sorted(TESTS.rglob("test_*.py")) if TESTS.exists() else []


def collect_import_graph(files: list[Path]) -> tuple[dict[str, set[str]], list[str]]:
    graph: dict[str, set[str]] = defaultdict(set)
    errors: list[str] = []
    known = {module_name(p) for p in files}

    for path in files:
        name = module_name(path)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{exc.lineno}: {exc.msg}")
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    parts = name.split(".")
                    prefix = parts[: -(node.level)]
                    if node.module:
                        prefix.append(node.module)
                    imported = [".".join(prefix)]
                else:
                    imported = [node.module] if node.module else []
            else:
                continue

            for target in imported:
                if not target or not target.startswith("xau_detective"):
                    continue
                if target in known:
                    graph[name].add(target)
                elif target != "xau_detective":
                    errors.append(f"{name}: unresolved internal import {target}")

    return graph, errors


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    stack: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def dfs(node: str) -> None:
        if node in visiting:
            if node in stack:
                cycles.append(stack[stack.index(node):] + [node])
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for child in sorted(graph.get(node, ())):
            dfs(child)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for node in sorted(graph):
        dfs(node)
    return cycles


def test_targets(tests: list[Path]) -> set[str]:
    targets: set[str] = set()
    for path in tests:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("xau_detective."):
                targets.add(node.module.rsplit(".", 1)[-1])
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("xau_detective."):
                        targets.add(alias.name.rsplit(".", 1)[-1])
    return targets


def changed_files(base: str, head: str) -> list[str]:
    if not base or not head or set(base) == {"0"}:
        return []
    output = run_git("diff", "--name-only", base, head)
    return [line for line in output.splitlines() if line]


def audit_architecture(findings: list[tuple[str, str]]) -> None:
    pipeline = SRC / "pipeline.py"
    risk = SRC / "risk.py"
    models = SRC / "models.py"
    config = ROOT / "config" / "defaults.example.yaml"
    strategy_doc = ROOT / "docs" / "STRATEGY_V1.md"
    risk_doc = ROOT / "docs" / "RISK_MODEL.md"

    pipeline_text = pipeline.read_text(encoding="utf-8") if pipeline.exists() else ""
    risk_text = risk.read_text(encoding="utf-8") if risk.exists() else ""
    models_text = models.read_text(encoding="utf-8") if models.exists() else ""
    config_text = config.read_text(encoding="utf-8") if config.exists() else ""
    strategy_text = strategy_doc.read_text(encoding="utf-8") if strategy_doc.exists() else ""
    risk_doc_text = risk_doc.read_text(encoding="utf-8") if risk_doc.exists() else ""

    if "a.balance * request.risk_fraction" in risk_text:
        findings.append(("FAIL", "Risk sizing uses balance while the risk model specifies equity."))
    elif "a.equity * request.risk_fraction" in risk_text:
        findings.append(("PASS", "Risk sizing uses account equity."))

    if "d1=" in pipeline_text and "compute_features(d1" not in pipeline_text:
        findings.append(("WARN", "D1 context is validated but does not currently contribute evidence or direction."))
    if "entry = m5[-1].close" in pipeline_text:
        findings.append(("WARN", "M5 currently supplies the entry price but no independent M5 confirmation family."))

    for key in ("max_daily_loss", "max_spread", "max_slippage", "require_closed_candle_confirmation"):
        if key in config_text and key not in pipeline_text and key not in risk_text and key not in models_text:
            findings.append(("WARN", f"Configuration key '{key}' is defined but not consumed by the current core pipeline."))

    for key in ("margin", "spread", "slippage"):
        if key in risk_doc_text and key not in models_text and key not in risk_text:
            findings.append(("WARN", f"Risk documentation requires {key} controls, but the current risk domain model does not implement a {key} input/gate."))

    if "A 0–100 setup-quality score" in strategy_text and "ledger.independent_evidence_count * 25" in pipeline_text:
        findings.append(("WARN", "Pipeline has provisional hard-coded setup-score weights; strategy spec says score weights require historical validation."))

    if "validate_candles(candles)" in pipeline_text and "expected_interval" not in pipeline_text:
        findings.append(("WARN", "Pipeline validates OHLC integrity but does not enforce expected timeframe intervals/data-gap checks."))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("HEALTH_BASE_SHA", ""))
    parser.add_argument("--head", default=os.getenv("HEALTH_HEAD_SHA", ""))
    args = parser.parse_args()

    findings: list[tuple[str, str]] = []
    sources = python_files()
    tests = test_files()

    findings.append(("PASS", f"Source inventory: {len(sources)} Python module(s)."))
    findings.append(("PASS", f"Test inventory: {len(tests)} test module(s)."))

    graph, parse_errors = collect_import_graph(sources)
    for error in parse_errors:
        findings.append(("FAIL", f"Python parse error: {error}"))
    if not parse_errors:
        findings.append(("PASS", "Python syntax: all source modules parse successfully."))

    cycles = find_cycles(graph)
    if cycles:
        for cycle in cycles:
            findings.append(("FAIL", "Internal import cycle: " + " -> ".join(cycle)))
    else:
        findings.append(("PASS", "Internal import graph: no cycles detected."))

    targets = test_targets(tests)
    source_names = {p.stem for p in sources}
    untested = sorted(name for name in source_names if name != "__init__" and name not in targets)
    if untested:
        findings.append(("WARN", "Source modules not referenced by tests: " + ", ".join(f"{n}.py" for n in untested)))
    else:
        findings.append(("PASS", "Every source module is referenced by at least one test module."))

    pyproject = ROOT / "pyproject.toml"
    if not pyproject.exists():
        findings.append(("FAIL", "Missing pyproject.toml"))
    else:
        text = pyproject.read_text(encoding="utf-8")
        if "ruff==" not in text:
            findings.append(("FAIL", "Ruff is not exactly pinned; CI lint behavior can drift."))
        else:
            findings.append(("PASS", "Ruff version is exactly pinned."))
        if "pytest>=" not in text or "<10" not in text:
            findings.append(("WARN", "Pytest is not bounded to a tested major range."))

    workflow_files = sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml"))
    if not workflow_files:
        findings.append(("FAIL", "No GitHub Actions workflow found."))
    else:
        findings.append(("PASS", f"GitHub Actions inventory: {len(workflow_files)} workflow file(s)."))
        for path in workflow_files:
            text = path.read_text(encoding="utf-8")
            if "ruff check" in text and "--fix" in text:
                findings.append(("FAIL", f"{path.relative_to(ROOT)} runs Ruff with --fix in CI."))
            if "pytest" in text:
                findings.append(("PASS", f"{path.relative_to(ROOT)} includes pytest."))

    audit_architecture(findings)

    readme = ROOT / "README.md"
    if not readme.exists():
        findings.append(("FAIL", "Missing README.md"))
    else:
        text = readme.read_text(encoding="utf-8").lower()
        drift = {
            "backtest.py": "backtest engine",
            "session.py": "session and liquidity features",
            "liquidity.py": "session and liquidity features",
        }
        source_names = {p.name for p in sources}
        for filename, label in drift.items():
            if filename in source_names and f"[ ] {label}" in text:
                findings.append(("WARN", f"Documentation drift: {filename} exists but README still marks '{label}' as next."))

    for path in sources:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\b(TODO|FIXME|XXX)\b", line, re.IGNORECASE):
                findings.append(("WARN", f"{path.relative_to(ROOT)}:{line_no} contains technical-debt marker."))

    changed = changed_files(args.base, args.head)
    if changed:
        findings.append(("PASS", f"Commit impact: {len(changed)} file(s) changed between {args.base[:8]} and {args.head[:8]}."))
        source_changed = [p for p in changed if p.startswith("src/xau_detective/") and p.endswith(".py")]
        changed_tests = {Path(p).stem.removeprefix("test_") for p in changed if p.startswith("tests/test_")}
        for path in source_changed:
            name = Path(path).stem
            if name != "__init__" and name not in changed_tests:
                findings.append(("WARN", f"Changed source '{name}.py' has no matching test file changed in this commit."))

    failures = sum(status == "FAIL" for status, _ in findings)
    warnings = sum(status == "WARN" for status, _ in findings)
    passes = sum(status == "PASS" for status, _ in findings)

    print("# XAU Detective AI — Project Health Check")
    print()
    print(f"- HEAD: {args.head or run_git('rev-parse', 'HEAD') or 'unknown'}")
    print(f"- PASS: {passes}  WARN: {warnings}  FAIL: {failures}")
    print()
    print("## Findings")
    for status, message in findings:
        print(f"- [{status}] {message}")
    print()
    print("## Scope")
    print("Syntax, internal imports, import cycles, test mapping, CI configuration, dependency pinning, documentation drift, technical-debt markers, and commit-to-commit impact.")
    print()
    print("Read-only: this checker never auto-fixes source code or CI.")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
