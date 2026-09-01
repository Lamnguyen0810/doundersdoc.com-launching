"""
The grade is deterministic. The model scores each rubric item 0–4 with a reason;
this module turns those scores into the number and letter shown to the user.
Lawyers own the items and weights — edit here, not in the prompt.
"""

RUBRIC: list[dict] = [
    {"key": "liability", "label": "Liability caps and exclusions", "weight": 15},
    {"key": "ip", "label": "Intellectual property ownership and licences", "weight": 15},
    {"key": "termination", "label": "Termination rights and notice", "weight": 12},
    {"key": "payment", "label": "Payment, fees and equity mechanics", "weight": 12},
    {"key": "confidentiality", "label": "Confidentiality and data", "weight": 10},
    {"key": "indemnity", "label": "Indemnities", "weight": 10},
    {"key": "warranties", "label": "Warranties and representations", "weight": 8},
    {"key": "control", "label": "Control, approvals and escalation rights", "weight": 8},
    {"key": "assignment", "label": "Assignment and change of control", "weight": 5},
    {"key": "law", "label": "Governing law and disputes", "weight": 5},
]
MAX_ITEM_SCORE = 4


def compute_grade(scores: dict[str, int]) -> tuple[int, str]:
    total_weight = sum(r["weight"] for r in RUBRIC)
    earned = 0.0
    for r in RUBRIC:
        s = max(0, min(MAX_ITEM_SCORE, int(scores.get(r["key"], 0))))
        earned += r["weight"] * (s / MAX_ITEM_SCORE)
    grade = round(100 * earned / total_weight)
    return grade, letter_for(grade)


def letter_for(grade: int) -> str:
    if grade >= 85:
        return "A"
    if grade >= 70:
        return "B"
    if grade >= 55:
        return "C"
    if grade >= 40:
        return "D"
    return "E"
