"""Tools the assistant may use. Every tool is scoped to the authenticated member.

The model never builds queries. It only receives the results of these fixed calls.
Asking for another member's claim returns the same result as a claim that does not exist.
"""
from .data import CLAIMS, MEMBERS


def get_member(member_id: str):
    return MEMBERS.get(member_id)


def get_claim(member_id: str, claim_id: str):
    for c in CLAIMS:
        if c["claim_id"] == claim_id and c["member_id"] == member_id:
            return dict(c)
    return None


def list_claims(member_id: str):
    items = [dict(c) for c in CLAIMS if c["member_id"] == member_id]
    return sorted(items, key=lambda c: c["service_date"], reverse=True)
