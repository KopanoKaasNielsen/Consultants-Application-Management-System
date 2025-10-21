"""Custom throttling policies tailored to role-based JWT claims."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping, MutableMapping, Optional, Set

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle

from apps.users.constants import ROLE_GROUP_MAP, UserRole


@dataclass(frozen=True)
class _RateSelection:
    """Container describing the active rate for a request."""

    rate: str
    roles: Set[UserRole]


class RoleBasedRateThrottle(SimpleRateThrottle):
    """Throttle requests based on the caller's effective application roles."""

    scope = "role"

    #: Roles that are exempt from throttling entirely.
    unlimited_roles = {UserRole.ADMIN}

    def __init__(self) -> None:
        self.role_rates = self._load_role_rates()
        self._active_roles: Set[UserRole] = set()
        super().__init__()

    @staticmethod
    def _load_role_rates() -> Mapping[UserRole, str]:
        """Return the rate configuration declared in Django settings."""

        config: Mapping[str, str] = (
            getattr(settings, "REST_FRAMEWORK", {}) or {}
        ).get("ROLE_BASED_THROTTLE_RATES", {})

        rates: MutableMapping[UserRole, str] = {}
        for key, rate in config.items():
            if isinstance(key, UserRole):
                role = key
            else:
                try:
                    role = UserRole(str(key).lower())
                except ValueError:
                    continue
            rates[role] = rate

        if not rates:
            rates = {
                UserRole.CONSULTANT: "60/min",
                UserRole.STAFF: "30/min",
                UserRole.BOARD: "15/min",
            }
        return rates

    def allow_request(self, request, view):  # type: ignore[override]
        rate_selection = self._select_rate(request)
        if rate_selection is None:
            self.rate = None
            self.num_requests, self.duration = None, None
            self._active_roles = set()
            return True

        self.rate = rate_selection.rate
        self.num_requests, self.duration = self.parse_rate(self.rate)
        self._active_roles = rate_selection.roles
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):  # type: ignore[override]
        if not self._active_roles:
            return None

        ident = self._identify_request(request)
        if ident is None:
            return None

        role_fragment = ",".join(
            sorted(role.value for role in self._active_roles if role in self.role_rates)
        )
        cache_ident = f"{role_fragment}:{ident}" if role_fragment else ident
        return self.cache_format % {"scope": self.scope, "ident": cache_ident}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _select_rate(self, request) -> Optional[_RateSelection]:
        roles = self._resolve_roles(request)
        if roles & self.unlimited_roles:
            return None

        applicable_roles = [role for role in roles if role in self.role_rates]
        if not applicable_roles:
            return None

        best_rate: Optional[str] = None
        best_roles: Set[UserRole] = set()
        best_ratio: Optional[float] = None

        for role in applicable_roles:
            rate = self.role_rates[role]
            num_requests, duration = self.parse_rate(rate)
            if not num_requests or not duration:
                continue
            ratio = num_requests / duration
            if best_ratio is None or ratio < best_ratio:
                best_rate = rate
                best_ratio = ratio
                best_roles = {role}
            elif ratio == best_ratio and best_rate == rate:
                best_roles.add(role)

        if best_rate is None:
            return None

        return _RateSelection(rate=best_rate, roles=best_roles)

    def _resolve_roles(self, request) -> Set[UserRole]:
        roles: Set[UserRole] = set()

        token_roles = getattr(request, "jwt_roles", None)
        if token_roles:
            if isinstance(token_roles, (str, UserRole)):
                token_iterable = [token_roles]
            else:
                token_iterable = token_roles
            for token_role in token_iterable:
                if isinstance(token_role, UserRole):
                    roles.add(token_role)
                    continue
                try:
                    roles.add(UserRole(str(token_role).lower()))
                except ValueError:
                    continue

        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False):
            if getattr(user, "is_superuser", False):
                roles.update(self.role_rates.keys() | self.unlimited_roles)
                return roles

            groups_manager = getattr(user, "groups", None)
            if groups_manager is not None:
                group_names = set(groups_manager.values_list("name", flat=True))
                if group_names:
                    for role, mapped_groups in ROLE_GROUP_MAP.items():
                        if group_names & mapped_groups:
                            roles.add(role)

        return roles

    def _identify_request(self, request) -> Optional[str]:
        user = getattr(request, "user", None)
        if getattr(user, "is_authenticated", False) and getattr(user, "pk", None) is not None:
            return f"user:{user.pk}"

        auth_header = request.META.get("HTTP_AUTHORIZATION")
        if auth_header:
            digest = hashlib.sha256(auth_header.encode("utf-8")).hexdigest()
            return f"token:{digest}"

        ident = self.get_ident(request)
        return f"ip:{ident}" if ident else None

    def parse_rate(self, rate):  # type: ignore[override]
        num_requests, duration = super().parse_rate(rate)
        if num_requests is None or duration is None:
            raise ValueError("Role-based throttle requires concrete rate definitions.")
        return num_requests, duration
