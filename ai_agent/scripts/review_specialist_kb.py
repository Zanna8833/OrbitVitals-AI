"""Review Marco's specialist knowledge base (`rag/knowledge_base`) for use by MedGemma.

Writes `orbit_agent/specialist_evidence/admission.json`, the list of documents and
sections the agent may give to the specialist model. Nothing in `rag/` is changed: the
review only reads it. The rules are fixed and stated here; a section is admitted only
when every rule passes, and everything else is quarantined with its reasons.

Document rules
- Category `protocol` (emergency and treatment procedures) is quarantined: the
  monitoring assistant must not give emergency steps, drugs or doses.
- Category `reference-values` is quarantined: reference values would act as clinical
  thresholds, which the agent must not introduce.

Section rules (for the remaining `knowledge` and `faq` documents)
- Purpose: a section written as instructions for the `rag/` assistant ("Notes for the
  assistant", "How to use this document") is not evidence.
- Provenance: the section cites at least one numbered source, and every source it cites
  is on a host from `_VERIFIED_HOSTS` (NASA, PubMed Central, DOI, journal publishers,
  a space agency). Sources hosted elsewhere, notably a third-party copy of the ISS
  medical emergency manual (governmentattic.org), are not verified and quarantine the
  section that cites them. A section without citations has unknown provenance.
- Content: no medication, drug name, dose or unit of dose; no emergency or treatment
  wording; no numbered step list; no advice addressed to a crew member ("What to do:");
  no numeric comparison that reads as a threshold; nothing the agent's prompt-injection
  screen (`orbit_agent/evidence/sanitizer.py`) flags.

The admission is pinned to the SHA-256 of each file and of each admitted section; the
agent refuses a document or section that changed after this review.

Usage, from `ai_agent/`:

    python -m scripts.review_specialist_kb            # write the admission file
    python -m scripts.review_specialist_kb --check    # fail if it is out of date
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from orbit_agent.evidence.sanitizer import screen_text

AGENT_ROOT = Path(__file__).resolve().parents[1]
KNOWLEDGE_BASE = AGENT_ROOT.parent / "rag" / "knowledge_base"
ADMISSION_PATH = AGENT_ROOT / "orbit_agent" / "specialist_evidence" / "admission.json"
REVIEWED_ON = "2026-11-15"

_QUARANTINED_CATEGORIES = {
    "protocol": "emergency or treatment protocol",
    "reference-values": "reference values would act as clinical thresholds",
}
_VERIFIED_HOSTS = {
    "www.nasa.gov",
    "nasa.gov",
    "ntrs.nasa.gov",
    "science.nasa.gov",
    "humanresearchroadmap.nasa.gov",
    "standards.nasa.gov",
    "pmc.ncbi.nlm.nih.gov",
    "doi.org",
    "journals.physiology.org",
    "physoc.onlinelibrary.wiley.com",
    "www.frontiersin.org",
    "www.asc-csa.gc.ca",
    "escholarship.org",
}
_MEDICATION = re.compile(
    r"\b(medication\w*|medicine\w*|drug\w*|dose\w*|dosage|dosing|tablet\w*|pill\w*|"
    r"capsule\w*|inject\w*|administer\w*|prescri\w*|antibiotic\w*|analgesic\w*|"
    r"anti-?\w+ (agent|drug)s?|ibuprofen|acetaminophen|paracetamol|aspirin|melatonin|"
    r"modafinil|armodafinil|zolpidem|zaleplon|benzodiazepine\w*|hypnotic\w*|"
    r"epinephrine|adrenaline|naloxone|promethazine|scopolamine|meclizine|bisphosphonate\w*|"
    r"alendronate|zoledron\w*|potassium citrate|statin\w*|antihistamine\w*|"
    r"\w+(pril|olol|azepam|floxacin|cillin|mycin|prazole|sartan|dronate|setron))\b"
    r"|\b\d+(\.\d+)?\s?(mg|mcg|ug|\u00b5g|ml|mL|IU)\b",
    re.IGNORECASE,
)
_EMERGENCY_OR_TREATMENT = re.compile(
    r"\b(emergenc\w*|immediate action\w*|first aid|cpr|defibrillat\w*|tourniquet\w*|"
    r"resuscitat\w*|evacuat\w*|treat\w*|therap\w*|intervention\w*|escalat\w*|"
    r"(call|contact|notify) the flight surgeon|surgery|surgical)\b",
    re.IGNORECASE,
)
_STEP_LIST = re.compile(r"(?m)^\s*\d+\.\s")
_THRESHOLD = re.compile(
    r"[<>\u2264\u2265]\s*\d|\b(above|below|over|under|exceed\w*|at least|at most|greater "
    r"than|less than)\s+\d",
    re.IGNORECASE,
)
_CITATION = re.compile(r"\[(\d+)\]")
# Advice addressed to a crew member ("What to do:", "Eat regular meals", "you should").
_ADVICE = re.compile(
    r"\bwhat to do\b|\byou (should|must|can)\b|\bshould be (checked|reported|seen)\b|"
    r"^\s*[-*]\s*(eat|drink|take|avoid|move|postpone|report|track|use|stop|rest|call|"
    r"tell|keep|choose|check|make sure|try)\b",
    re.IGNORECASE | re.MULTILINE,
)
# Sections written as instructions for the rag/ assistant are not evidence.
_ADDRESSES_ASSISTANT = re.compile(
    r"\b(assistant|how to use this document|related documents|monitoring cues)\b", re.IGNORECASE
)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_document(text: str) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """Header and `## ` sections, read the same way as `rag/src/assistant/knowledge.py`."""
    lines = text.split("\n")
    header: dict[str, str] = {}
    body = text
    if lines and lines[0].strip() == "---":
        for number in range(1, len(lines)):
            line = lines[number]
            if line.strip() == "---":
                body = "\n".join(lines[number + 1 :])
                break
            if ":" in line:
                key, value = line.split(":", 1)
                header[key.strip()] = value.strip()
        else:
            header = {}
    sections: list[tuple[str, str]] = []
    title, current = "Overview", []
    for line in body.split("\n"):
        if line.startswith("## "):
            if "\n".join(current).strip():
                sections.append((title, "\n".join(current).strip()))
            title, current = line[3:].strip(), []
        else:
            current.append(line)
    if "\n".join(current).strip():
        sections.append((title, "\n".join(current).strip()))
    return header, sections


def source_list(header: dict[str, str]) -> list[str]:
    return [
        item.strip() for item in header.get("sources", "").strip("[] ").split(",") if item.strip()
    ]


def section_problems(title: str, text: str, sources: list[str]) -> list[str]:
    problems = []
    if _ADDRESSES_ASSISTANT.search(title):
        problems.append("written as instructions for an assistant, not as evidence")
    cited = sorted({int(number) for number in _CITATION.findall(text)})
    if not cited:
        problems.append("no cited source: provenance unknown")
    for number in cited:
        if not 1 <= number <= len(sources):
            problems.append(f"cites [{number}], which is not in the source list")
            continue
        host = urlparse(sources[number - 1]).hostname or ""
        if host not in _VERIFIED_HOSTS:
            problems.append(f"cites [{number}] on {host}, which is not a verified host")
    content = f"{title}\n{text}"
    if _MEDICATION.search(content):
        problems.append("mentions a medication, a drug or a dose")
    if _EMERGENCY_OR_TREATMENT.search(content):
        problems.append("contains emergency or treatment wording")
    if _STEP_LIST.search(text):
        problems.append("contains a numbered list of steps")
    if _ADVICE.search(text):
        problems.append("contains advice addressed to a crew member")
    screened = screen_text(content)
    if screened:
        problems.append(f"instruction-like wording ({', '.join(screened)})")
    if _THRESHOLD.search(content):
        problems.append("contains a numeric comparison that reads as a threshold")
    return problems


def review(knowledge_base: Path = KNOWLEDGE_BASE) -> dict:
    documents = []
    for path in sorted(knowledge_base.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        header, sections = read_document(raw)
        if "id" not in header:
            continue
        category = header.get("category", "")
        sources = source_list(header)
        entry = {
            "id": header["id"],
            "file": path.name,
            "file_sha256": sha256_text(raw),
            "title": header.get("title", header["id"]),
            "category": category,
            "sources": sources,
            "decision": "quarantined",
            "reasons": [],
            "sections": [],
        }
        if category in _QUARANTINED_CATEGORIES:
            entry["reasons"] = [f"category '{category}': {_QUARANTINED_CATEGORIES[category]}"]
        elif category not in {"knowledge", "faq"}:
            entry["reasons"] = [f"category '{category}' was not reviewed"]
        else:
            for title, text in sections:
                problems = section_problems(title, text, sources)
                entry["sections"].append(
                    {
                        "title": title,
                        "sha256": sha256_text(text),
                        "decision": "quarantined" if problems else "admitted",
                        "reasons": problems,
                    }
                )
            if any(section["decision"] == "admitted" for section in entry["sections"]):
                entry["decision"] = "admitted"
            else:
                entry["reasons"] = ["no section passed the review"]
        documents.append(entry)
    admitted = [d for d in documents if d["decision"] == "admitted"]
    return {
        "knowledge_base": "rag/knowledge_base",
        "reviewed_on": REVIEWED_ON,
        "verified_hosts": sorted(_VERIFIED_HOSTS),
        "summary": {
            "documents": len(documents),
            "admitted_documents": len(admitted),
            "admitted_sections": sum(
                1 for d in admitted for s in d["sections"] if s["decision"] == "admitted"
            ),
            "quarantined_documents": len(documents) - len(admitted),
        },
        "notice": (
            "Admitted sections are general space-medicine context written by the rag/ "
            "module's author, given only to the specialist model as background. They are "
            "not shown to the operator and are not crew data. The licences of the works "
            "they cite were not reviewed one by one; only the hosts were."
        ),
        "documents": documents,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    result = review()
    text = json.dumps(result, indent=2, ensure_ascii=True) + "\n"
    if arguments.check:
        current = ADMISSION_PATH.read_text(encoding="utf-8") if ADMISSION_PATH.exists() else ""
        if current != text:
            print("The specialist admission file is out of date; run the review again.")
            return 1
        print("The specialist admission file is up to date.")
        return 0
    ADMISSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    ADMISSION_PATH.write_text(text, encoding="utf-8")
    summary = result["summary"]
    print(
        f"{summary['documents']} documents: {summary['admitted_documents']} admitted with "
        f"{summary['admitted_sections']} sections, {summary['quarantined_documents']} quarantined"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
