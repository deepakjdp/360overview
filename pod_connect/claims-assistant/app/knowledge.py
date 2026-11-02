"""Reference knowledge: denial codes and plan policy. Synthetic wording for the prototype.

In production, load these from versioned, approved sources (denial code table, plan documents)
and filter by plan and effective date.
"""
import re

DENIAL_CODES = {
    "CO-16": "The claim was missing information the plan needed to process it.",
    "CO-29": "The claim was sent after the plan's filing deadline (timely filing limit).",
    "CO-50": "The plan decided the service did not meet its medical necessity criteria.",
    "CO-197": "The service needed prior authorization (approval before the visit) and none was on file.",
    "PR-1": "Part of the cost was applied to your deductible, which is the amount you pay before the plan pays.",
    "PR-2": "Part of the cost is your coinsurance, your share of the cost after the deductible.",
}

POLICY = [
    {"id": "PPO-GOLD-APPEALS", "plan_id": "PPO-GOLD", "title": "Appeals (PPO Gold)",
     "text": "You can appeal a denied claim within 180 days of the denial notice. Send the appeal form with your "
             "provider's supporting letter and any medical records. A decision is made within 30 days."},
    {"id": "PPO-GOLD-PRIORAUTH", "plan_id": "PPO-GOLD", "title": "Prior authorization (PPO Gold)",
     "text": "Advanced imaging such as MRI and CT requires prior authorization. Your provider can request it. "
             "If it was missed, your provider can ask for a retrospective review within 14 days of the service."},
    {"id": "PPO-GOLD-NECESSITY", "plan_id": "PPO-GOLD", "title": "Medical necessity (PPO Gold)",
     "text": "If a service is denied as not medically necessary, you can ask for the criteria used and request a "
             "review by a clinician who was not involved in the original decision."},
    {"id": "PPO-GOLD-DEDUCTIBLE", "plan_id": "PPO-GOLD", "title": "Deductible (PPO Gold)",
     "text": "The deductible is the amount you pay for covered services before the plan starts to pay. "
             "Visits to your primary care provider have a flat copay and do not count toward the deductible."},
    {"id": "HMO-BASIC-APPEALS", "plan_id": "HMO-BASIC", "title": "Appeals (HMO Basic)",
     "text": "You can appeal a denied claim within 120 days of the denial notice. Use the member portal or send "
             "the appeal form to Member Services. A decision is made within 30 days."},
    {"id": "HMO-BASIC-FILING", "plan_id": "HMO-BASIC", "title": "Timely filing (HMO Basic)",
     "text": "Claims must be submitted within 180 days of the service date. Claims sent later are denied unless "
             "the provider shows a valid reason for the delay."},
    {"id": "HMO-BASIC-DEDUCTIBLE", "plan_id": "HMO-BASIC", "title": "Deductible (HMO Basic)",
     "text": "The deductible is the amount you pay for covered services before the plan starts to pay. After you "
             "meet it, you pay coinsurance until you reach your out-of-pocket maximum."},
]

_WORD = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set:
    return set(_WORD.findall(text.lower()))


def explain_denial(code):
    return DENIAL_CODES.get(code) if code else None


def search_policy(query: str, plan_id: str, top_k: int = 2):
    """Keyword-overlap retrieval limited to the member's plan. Swap for vector search (pgvector) in production."""
    q = _tokens(query)
    scored = []
    for doc in POLICY:
        if doc["plan_id"] != plan_id:
            continue
        score = len(q & _tokens(doc["title"] + " " + doc["text"]))
        if score:
            scored.append((score, doc))
    scored.sort(key=lambda s: -s[0])
    return [d for _, d in scored[:top_k]]
