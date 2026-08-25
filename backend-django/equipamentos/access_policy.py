from __future__ import annotations

from django.utils import timezone

from .models import UserAccessPolicy


def is_mis_admin(user) -> bool:
    return bool(user and user.is_authenticated and user.is_active and (user.is_staff or user.is_superuser))


def ensure_access_policy(user) -> UserAccessPolicy | None:
    if not user or not user.is_authenticated:
        return None
    policy, _ = UserAccessPolicy.objects.get_or_create(user=user)
    if is_mis_admin(user) and policy.expires_at is not None:
        policy.expires_at = None
        policy.save(update_fields=['expires_at', 'updated_at'])
    return policy


def access_is_valid(user) -> bool:
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_mis_admin(user):
        return True
    policy = ensure_access_policy(user)
    return bool(policy and policy.expires_at and policy.expires_at > timezone.now())
