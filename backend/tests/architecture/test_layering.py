"""Dependency rules between backend packages (see AGENTS.md, "Architecture rules").

Scientific code must stay independent of the web framework so that it can be
developed and tested in isolation.
"""

import ast
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]

WEB_FRAMEWORK = ("fastapi", "starlette", "uvicorn")

# Package directory -> module prefixes that code in the package must not import.
FORBIDDEN_IMPORTS = {
    "app/models": (*WEB_FRAMEWORK, "app.api", "app.core", "app.algorithms", "app.domains"),
    "app/algorithms": (*WEB_FRAMEWORK, "app.api", "app.domains"),
    "app/domains": (*WEB_FRAMEWORK, "app.api"),
}


def imported_modules(path: Path) -> set[str]:
    """Return the absolute names of every module imported by the file at `path`."""
    package = path.relative_to(BACKEND_ROOT).with_suffix("").parts[:-1]
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            # Resolve relative imports against the package that contains the file.
            base = package[: len(package) - (node.level - 1)] if node.level else ()
            module = ".".join([*base, *([node.module] if node.module else [])])
            modules.add(module)
            modules.update(f"{module}.{alias.name}" for alias in node.names)
    return modules


def is_within(module: str, prefix: str) -> bool:
    return module == prefix or module.startswith(prefix + ".")


@pytest.mark.parametrize("package", sorted(FORBIDDEN_IMPORTS))
def test_package_respects_the_dependency_rules(package: str) -> None:
    violations = [
        f"{path.relative_to(BACKEND_ROOT).as_posix()} imports {module}"
        for path in sorted((BACKEND_ROOT / package).rglob("*.py"))
        for module in sorted(imported_modules(path))
        if any(is_within(module, prefix) for prefix in FORBIDDEN_IMPORTS[package])
    ]

    assert violations == []
