"""PAPER ledger account-id namespaces shared between `apps/api` and `apps/ai_worker` -- the two
processes that read/write PAPER ledger state for a given user, each under its own fully separate
account. See `docs/adr/016-ai-autonomous-account.md` (2026-09-23). `apps/api/portfolio_routes.py`
defines its own `paper_account_id` (the deterministic account) locally rather than importing it
from here, since
only this AI-account namespace is needed by more than one process today -- lifting the other one
too, with no second caller, would be speculative.
"""


def paper_ai_account_id(user_id: str) -> str:
    """The AI-autonomous path's own ledger namespace -- fully separate from `paper:<user_id>`
    (the deterministic account) so neither loop can ever touch the other's simulated cash/
    positions."""
    return f"paper-ai:{user_id}"
