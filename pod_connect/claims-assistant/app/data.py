"""Synthetic data only. No real member information."""
from datetime import date, timedelta


def _in_days(n: int) -> str:
    """Deadlines are relative to today so the demo and tests stay valid over time."""
    return (date.today() + timedelta(days=n)).isoformat()


MEMBERS = {
    "M1001": {"name": "Alex Rivera", "plan_id": "PPO-GOLD", "deductible": 1500.00, "deductible_met": 900.00},
    "M1002": {"name": "Sam Patel", "plan_id": "HMO-BASIC", "deductible": 2500.00, "deductible_met": 2500.00},
}

# Demo bearer tokens -> member id. In production this comes from your IdP (OIDC), never from the request body.
TOKENS = {
    "demo-token-m1001": "M1001",
    "demo-token-m1002": "M1002",
}

CLAIMS = [
    {"claim_id": "CLM-000101", "member_id": "M1001", "service_date": "2025-09-02", "provider": "Lakeside Family Clinic",
     "status": "PAID", "billed": 220.00, "allowed": 160.00, "plan_paid": 128.00, "member_owes": 32.00,
     "denial_code": None, "appeal_deadline": None},
    {"claim_id": "CLM-000102", "member_id": "M1001", "service_date": "2025-09-18", "provider": "Metro Imaging Center",
     "status": "DENIED", "billed": 1850.00, "allowed": 0.00, "plan_paid": 0.00, "member_owes": 1850.00,
     "denial_code": "CO-197", "appeal_deadline": _in_days(60)},
    {"claim_id": "CLM-000103", "member_id": "M1001", "service_date": "2025-10-05", "provider": "Dr. Nina Okafor",
     "status": "PENDING", "billed": 340.00, "allowed": 0.00, "plan_paid": 0.00, "member_owes": 0.00,
     "denial_code": None, "appeal_deadline": None},
    {"claim_id": "CLM-000104", "member_id": "M1001", "service_date": "2025-08-11", "provider": "Riverside Physical Therapy",
     "status": "DENIED", "billed": 600.00, "allowed": 0.00, "plan_paid": 0.00, "member_owes": 600.00,
     "denial_code": "CO-50", "appeal_deadline": _in_days(10)},
    {"claim_id": "CLM-000201", "member_id": "M1002", "service_date": "2025-09-25", "provider": "City General Hospital",
     "status": "PARTIALLY_PAID", "billed": 4200.00, "allowed": 3000.00, "plan_paid": 2400.00, "member_owes": 600.00,
     "denial_code": "PR-1", "appeal_deadline": None},
    {"claim_id": "CLM-000202", "member_id": "M1002", "service_date": "2024-12-01", "provider": "Northside Cardiology",
     "status": "DENIED", "billed": 975.00, "allowed": 0.00, "plan_paid": 0.00, "member_owes": 975.00,
     "denial_code": "CO-29", "appeal_deadline": _in_days(-30)},
]
