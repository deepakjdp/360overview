"""Input and output guardrails."""
import re

INJECTION = re.compile(
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)|system prompt|developer message|"
    r"reveal your (instructions|prompt)|you are now|act as (?!a member)|jailbreak",
    re.I,
)
MEDICAL_ADVICE = re.compile(
    r"\b(should i (take|stop|start)|dosage|diagnos\w*|what medication|is it safe to|treatment for|symptoms? of)\b", re.I
)
SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")

REFUSE_INJECTION = ("I can only help with questions about your claims and benefits. "
                    "I can't follow that request. A member services representative can help further.")
REFUSE_MEDICAL = ("I can't give medical advice. Please talk to your doctor. "
                  "I can help with questions about your claims, coverage, and appeals.")


def check_input(message: str):
    """Return (allowed, refusal_text). Refusals also escalate to a human."""
    if INJECTION.search(message):
        return False, REFUSE_INJECTION
    if MEDICAL_ADVICE.search(message):
        return False, REFUSE_MEDICAL
    return True, None


def _amounts(text: str):
    return {round(float(m.replace(",", "")), 2) for m in MONEY.findall(text)}


def is_grounded(answer: str, allowed_amounts) -> bool:
    """Every dollar amount in the answer must come from the retrieved facts."""
    allowed = {round(a, 2) for a in allowed_amounts}
    return _amounts(answer) <= allowed


def redact(text: str) -> str:
    return SSN.sub("[REDACTED]", text)
