"""Turn an ``EvidenceBundle`` into the final natural-language answer.

Deterministic on purpose. Given the same evidence bundle we always produce
the same prose, so tests can assert against real string contents. An
optional LLM paraphrasing step can run on top of this (see ``llm_client``)
but the numeric contents of the answer always come from evidence — no
hallucination surface.
"""

from __future__ import annotations

from typing import List

from app.chatbot.types import (
    AnswerClassification,
    ChatEvidence,
    ConfidenceLevel,
    EvidenceBundle,
)


_CLASSIFICATION_LABELS = {
    AnswerClassification.REPORTED: "Reported directly by the dataset.",
    AnswerClassification.CALCULATED: "Calculated from reported dataset values.",
    AnswerClassification.ESTIMATED: "Estimated with a documented assumption.",
    AnswerClassification.SCENARIO: (
        "Scenario value — a hypothetical combination, not a forecast."
    ),
    AnswerClassification.UNAVAILABLE: "Data is unavailable for this question.",
    AnswerClassification.INFORMATIONAL: "Descriptive information.",
    AnswerClassification.REFUSED: "Refused: out of scope.",
}


_CONFIDENCE_LABELS = {
    ConfidenceLevel.HIGH: "High",
    ConfidenceLevel.MEDIUM: "Medium",
    ConfidenceLevel.LOW: "Low",
    ConfidenceLevel.NONE: "—",
}


def render_answer(bundle: EvidenceBundle) -> str:
    """Return the assistant-facing text for ``bundle``.

    The layout is:

        <headline>

        Evidence:
        - ...
        - ...

        Calculation:
        - <formula> = <result>

        Note: ...

        Classification: <label>
        Confidence: <label>
    """
    lines: List[str] = []
    lines.append(bundle.headline.strip())

    if bundle.evidence:
        lines.append("")
        lines.append("Evidence:")
        for e in bundle.evidence[:8]:
            lines.append(f"- {_render_evidence(e)}")

    if bundle.calculations:
        lines.append("")
        lines.append("Calculation:")
        for c in bundle.calculations[:3]:
            formula = c.formula.strip()
            result = _fmt_number(c.result)
            entry = f"- {formula}"
            if result:
                entry += f" = {result}"
            if c.explanation:
                entry += f" ({c.explanation})"
            lines.append(entry)

    for note in bundle.notes[:5]:
        if not note:
            continue
        lines.append("")
        lines.append(f"Note: {note}")

    for warn in bundle.warnings[:5]:
        if not warn:
            continue
        lines.append(f"⚠ {warn}")

    lines.append("")
    lines.append(f"Classification: {_CLASSIFICATION_LABELS.get(bundle.classification, bundle.classification.value)}")
    lines.append(f"Confidence: {_CONFIDENCE_LABELS.get(bundle.confidence, bundle.confidence.value)}")

    return "\n".join(l for l in lines if l is not None).rstrip()


def _render_evidence(e: ChatEvidence) -> str:
    parts: List[str] = []
    if e.entity_name and e.entity and e.entity != "primary":
        parts.append(f"[{e.entity_name}]")
    parts.append(e.label + ":")
    display = e.display_value if e.display_value is not None else _fmt_number(e.value)
    parts.append(display or "—")
    if e.period and e.period not in parts and e.period not in e.label:
        parts.append(f"({e.period})")
    return " ".join(parts)


def _fmt_number(v) -> str:
    if v is None:
        return ""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(f) >= 1000:
        return f"{f:,.2f}"
    return f"{f:.2f}"
