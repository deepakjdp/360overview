"""Orchestrator: routes a question to the tools, builds grounded facts, asks the LLM to explain, then checks the result."""
import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

from . import guardrails, knowledge, tools
from .llm import LLMClient

CLAIM_ID = re.compile(r"\bCLM-\d{6}\b", re.I)
HANDOFF = re.compile(r"\b(human|agent|representative|person|speak to|talk to|complain)\b", re.I)

ESCALATION_NOTE = "I'm connecting you with a member services representative who can see this conversation."


@dataclass
class Answer:
    answer: str
    sources: List[str] = field(default_factory=list)
    escalate: bool = False
    intent: str = "unknown"
    claim_id: Optional[str] = None


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _days_left(deadline: Optional[str]) -> Optional[int]:
    return (date.fromisoformat(deadline) - date.today()).days if deadline else None


def _claim_facts(claim: dict, member: dict):
    """Return (facts_text, allowed_amounts, sources, fallback_answer, escalate)."""
    sources = [f"claim:{claim['claim_id']}"]
    amounts = [claim["billed"], claim["allowed"], claim["plan_paid"], claim["member_owes"]]
    lines = [
        f"Claim {claim['claim_id']} for service on {claim['service_date']} at {claim['provider']}.",
        f"Status: {claim['status']}.",
        f"Billed: {_money(claim['billed'])}. Allowed: {_money(claim['allowed'])}. "
        f"Plan paid: {_money(claim['plan_paid'])}. Member owes: {_money(claim['member_owes'])}.",
    ]
    reason = knowledge.explain_denial(claim["denial_code"])
    if claim["denial_code"]:
        sources.append(f"denial_code:{claim['denial_code']}")
        lines.append(f"Reason code {claim['denial_code']}: {reason or 'No plain-language text is available for this code.'}")

    # Topic rule (why it happened) plus, for denials, the appeals rule (what to do next).
    policy_docs = []
    if reason and claim["status"] in ("DENIED", "PARTIALLY_PAID"):
        policy_docs += knowledge.search_policy(reason, member["plan_id"], top_k=1)
    if claim["status"] == "DENIED":
        policy_docs += [d for d in knowledge.search_policy("appeal denied claim", member["plan_id"], top_k=1)
                        if d not in policy_docs]
    for d in policy_docs:
        sources.append(f"policy:{d['id']}")
        lines.append(f"Plan rule ({d['title']}): {d['text']}")

    left = _days_left(claim["appeal_deadline"])
    deadline_line = ""
    if claim["appeal_deadline"]:
        if left is not None and left >= 0:
            deadline_line = f"The appeal deadline is {claim['appeal_deadline']} ({left} days left)."
        else:
            deadline_line = f"The appeal deadline of {claim['appeal_deadline']} has passed."
        lines.append(deadline_line)

    # Offline template answer (also the safe fallback when the model fails or is not grounded)
    status = claim["status"]
    if status == "PAID":
        text = (f"Claim {claim['claim_id']} was paid. The plan paid {_money(claim['plan_paid'])} and you owe "
                f"{_money(claim['member_owes'])}.")
    elif status == "PENDING":
        text = (f"Claim {claim['claim_id']} is still being processed. No payment decision has been made yet. "
                f"You don't need to do anything now.")
    elif status == "PARTIALLY_PAID":
        text = (f"Claim {claim['claim_id']} was partly paid. The plan paid {_money(claim['plan_paid'])} and you owe "
                f"{_money(claim['member_owes'])}. {reason or ''}").strip()
    else:
        text = f"Claim {claim['claim_id']} was denied. {reason or 'I could not find a plain-language reason for this code.'}"
        for d in policy_docs:
            text += f" {d['text']}"
        if deadline_line:
            text += f" {deadline_line}"
        text += " Your provider's office can also help with the next step."
    escalate = bool(claim["denial_code"] and reason is None)
    return "\n".join(lines), amounts, sources, text, escalate


class ClaimsAssistant:
    def __init__(self, llm: Optional[LLMClient] = None):
        self.llm = llm or LLMClient()

    def ask(self, member_id: str, message: str) -> Answer:
        member = tools.get_member(member_id)
        if not member:
            return Answer("I couldn't verify your account. Please contact member services.", escalate=True, intent="auth")

        ok, refusal = guardrails.check_input(message)
        if not ok:
            return Answer(refusal, escalate=True, intent="refused")

        if HANDOFF.search(message):
            return Answer(ESCALATION_NOTE, escalate=True, intent="handoff")

        ids = CLAIM_ID.findall(message)
        if ids:
            return self._claim_answer(member_id, member, ids[0].upper(), message)

        lowered = message.lower()
        if "deductible" in lowered:
            return self._deductible_answer(member, message)
        if "claim" in lowered or "denied" in lowered or "denial" in lowered:
            return self._list_answer(member_id, message)
        if "appeal" in lowered:
            docs = knowledge.search_policy("appeal", member["plan_id"], top_k=1)
            if docs:
                return Answer(guardrails.redact(docs[0]["text"]), sources=[f"policy:{docs[0]['id']}"], intent="appeal_info")
        return Answer("I can help with claim status, denials, appeals, and your deductible. "
                      "Which claim would you like to look at? You can give me a claim number like CLM-000102.",
                      intent="clarify")

    # --- intents -------------------------------------------------------------------------

    def _claim_answer(self, member_id, member, claim_id, message) -> Answer:
        claim = tools.get_claim(member_id, claim_id)
        if not claim:
            return Answer(f"I can't find claim {claim_id} on your account. Please check the number, "
                          "or I can connect you with a representative.", escalate=True, intent="claim_not_found", claim_id=claim_id)
        facts, amounts, sources, fallback, escalate = _claim_facts(claim, member)
        answer = self.llm.generate(message, facts, fallback)
        if not guardrails.is_grounded(answer, amounts):
            answer = fallback  # model produced an amount not in the facts: use the safe template
        answer = guardrails.redact(answer)
        if escalate:
            answer += " " + ESCALATION_NOTE
        return Answer(answer, sources=sources, escalate=escalate, intent="claim_status", claim_id=claim_id)

    def _deductible_answer(self, member, message) -> Answer:
        remaining = max(member["deductible"] - member["deductible_met"], 0.0)
        facts = (f"Plan {member['plan_id']}. Deductible: {_money(member['deductible'])}. "
                 f"Met so far: {_money(member['deductible_met'])}. Remaining: {_money(remaining)}.")
        docs = knowledge.search_policy("deductible", member["plan_id"], top_k=1)
        sources = ["member:deductible"] + [f"policy:{d['id']}" for d in docs]
        if docs:
            facts += f"\nPlan rule ({docs[0]['title']}): {docs[0]['text']}"
        fallback = (f"Your deductible is {_money(member['deductible'])}. You have met {_money(member['deductible_met'])}, "
                    f"so {_money(remaining)} remains." if remaining else
                    f"Your deductible of {_money(member['deductible'])} has been met for this year.")
        answer = self.llm.generate(message, facts, fallback)
        if not guardrails.is_grounded(answer, [member["deductible"], member["deductible_met"], remaining]):
            answer = fallback
        return Answer(guardrails.redact(answer), sources=sources, intent="deductible")

    def _list_answer(self, member_id, message) -> Answer:
        claims = tools.list_claims(member_id)
        if not claims:
            return Answer("I don't see any claims on your account.", intent="list_claims")
        lines = [f"{c['claim_id']} ({c['service_date']}, {c['provider']}): {c['status']}" for c in claims]
        text = "Here are your recent claims:\n" + "\n".join(f"- {l}" for l in lines) + \
               "\nAsk about any claim number for details, for example: Why was CLM-000102 denied?"
        return Answer(text, sources=[f"claim:{c['claim_id']}" for c in claims], intent="list_claims")
