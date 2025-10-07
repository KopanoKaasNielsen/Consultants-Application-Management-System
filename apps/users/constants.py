"""Constants and role/group mappings for the users app."""

from enum import Enum
from typing import Dict, Iterable, Set


COUNTERSTAFF_GROUP_NAME = "CounterStaff"
BACKOFFICE_GROUP_NAME = "BackOffice"
DISAGENTS_GROUP_NAME = "DISAgents"
BOARD_COMMITTEE_GROUP_NAME = "BoardCommittee"
SENIOR_IMMIGRATION_GROUP_NAME = "SeniorImmigration"
ADMINS_GROUP_NAME = "Admins"
CONSULTANTS_GROUP_NAME = "Consultants"


class UserRole(str, Enum):
    """High-level roles recognised by the application."""

    CONSULTANT = "consultant"
    STAFF = "staff"
    BOARD = "board"


ROLE_GROUP_MAP: Dict[UserRole, Set[str]] = {
    UserRole.CONSULTANT: {CONSULTANTS_GROUP_NAME},
    UserRole.STAFF: {
        COUNTERSTAFF_GROUP_NAME,
        BACKOFFICE_GROUP_NAME,
        DISAGENTS_GROUP_NAME,
        SENIOR_IMMIGRATION_GROUP_NAME,
        ADMINS_GROUP_NAME,
        "Staff",
    },
    UserRole.BOARD: {BOARD_COMMITTEE_GROUP_NAME},
}


def groups_for_roles(roles: Iterable[UserRole]) -> Set[str]:
    """Return the set of concrete group names for the given roles."""

    groups: Set[str] = set()
    for role in roles:
        groups.update(ROLE_GROUP_MAP.get(role, set()))
    return groups
