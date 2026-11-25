"""Fail-closed policy: this release never provisions paid compute or APIs."""
from dataclasses import dataclass

@dataclass(frozen=True)
class ResourcePolicy:
    allow_paid: bool = False
    require_user_approval_for_external: bool = True
    stop_when_free_quota_unavailable: bool = True

class PaidResourceBlocked(PermissionError):
    pass

def authorize_resource(provider: str, tier: str, policy: ResourcePolicy = ResourcePolicy()) -> None:
    if tier.strip().lower() not in {"free", "local", "self-hosted"} and not policy.allow_paid:
        raise PaidResourceBlocked(f"Blocked non-free resource: {provider} ({tier}). No paid fallback is permitted.")
