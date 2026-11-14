"""Structural rules: isolation from the backend, read-only access, English-only code."""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "orbit_agent"
SOURCES = sorted(
    path for folder in ("orbit_agent", "scripts", "tests") for path in (ROOT / folder).rglob("*.py")
)
FORBIDDEN_IMPORTS = {"app", "backend", "rag"}
# Frequent Italian function words and project terms that do not occur in English prose.
ITALIAN_WORDS = re.compile(
    r"\b(della|dello|delle|degli|nella|nelle|sono|questo|questa|anche|perch[eé]|quindi|"
    r"valutazione|misurazioni?|sonno|qualit[aà]|dati|risultati|fonti|citazioni|verifica|"
    r"incertezza|equipaggio|astronauta|errore|risposta|richiesta|utente)\b",
    re.IGNORECASE,
)


def _imported_modules(path: Path) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


def test_agent_does_not_import_backend_or_rag_code() -> None:
    for path in SOURCES:
        assert not (_imported_modules(path) & FORBIDDEN_IMPORTS), path


def test_only_the_model_client_sends_post_requests() -> None:
    senders = [
        path.name
        for path in PACKAGE.rglob("*.py")
        if re.search(r"transport\(\s*\"POST\"", path.read_text(encoding="utf-8"))
    ]

    assert senders == ["llm.py"]


def test_no_network_library_bypasses_the_transport() -> None:
    allowed = {"http.py"}
    for path in PACKAGE.rglob("*.py"):
        if path.name in allowed:
            continue
        assert not (_imported_modules(path) & {"urllib3", "requests", "httpx", "httpx2", "socket"})
        assert "urlopen" not in path.read_text(encoding="utf-8"), path


def test_source_code_is_ascii_english() -> None:
    for path in [*SOURCES, ROOT / "README.md", ROOT / ".env.example"]:
        text = path.read_text(encoding="utf-8")
        if path.name == "test_architecture.py":
            continue
        assert text.isascii(), f"non-ASCII character in {path}"
        assert not ITALIAN_WORDS.search(text), f"{path}: {ITALIAN_WORDS.search(text).group(0)}"


def test_prompts_and_fixed_wording_are_english() -> None:
    from orbit_agent.composer import SYSTEM_PROMPT
    from orbit_agent.models import DISCLAIMER

    for text in (SYSTEM_PROMPT, DISCLAIMER):
        assert text.isascii() and not ITALIAN_WORDS.search(text)
