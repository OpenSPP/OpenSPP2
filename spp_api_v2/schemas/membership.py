# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Membership operation schemas for OpenSPP API V2"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .base import CodeableConcept, Identifier, Reference


class AddMemberRequest(BaseModel):
    """Request to add a member to a group"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "entity": {
                    "reference": "Individual/urn:gov:ph:psa:national-id|PH-123456789",
                    "display": "Maria Santos",
                },
                "role": {
                    "coding": [
                        {
                            "system": "urn:openspp:vocab:relationship",
                            "code": "head",
                            "display": "Head of Household",
                        }
                    ]
                },
                "startDate": "2024-01-15",
            }
        },
    )

    entity: Reference = Field(
        ...,
        description="Reference to Individual to add as member",
    )
    role: CodeableConcept | None = Field(
        None,
        description="Membership role (head, spouse, child, etc.)",
    )
    start_date: date | None = Field(
        None,
        alias="startDate",
        description="When membership starts",
    )


class RemoveMemberRequest(BaseModel):
    """Request to remove a member from a group"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "entity": {
                    "reference": "Individual/urn:gov:ph:psa:national-id|PH-123456789",
                    "display": "Maria Santos",
                },
                "endedDate": "2024-12-31",
                "reason": "Moved to another household",
            }
        },
    )

    entity: Reference = Field(
        ...,
        description="Reference to Individual to remove",
    )
    ended_date: date | None = Field(
        None,
        alias="endedDate",
        description="When membership ends",
    )
    reason: str | None = Field(
        None,
        description="Reason for removal",
    )


class UpdateMemberRequest(BaseModel):
    """Request to update a member's role or period in a group"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "role": {
                    "coding": [
                        {
                            "system": "urn:openspp:vocab:relationship",
                            "code": "head",
                            "display": "Head of Household",
                        }
                    ]
                },
                "startDate": "2024-01-15",
            }
        },
    )

    role: CodeableConcept | None = Field(
        None,
        description="New role for the member",
    )
    start_date: date | None = Field(
        None,
        alias="startDate",
        description="When membership starts/started",
    )
    ended_date: date | None = Field(
        None,
        alias="endedDate",
        description="When membership ends/ended",
    )


class MembershipResponse(BaseModel):
    """Response for membership operations"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "GroupMember",
                "group": {
                    "reference": "Group/urn:openspp:group|HH-2024-001",
                    "display": "Santos Household",
                },
                "entity": {
                    "reference": "Individual/urn:gov:ph:psa:national-id|PH-123456789",
                    "display": "Maria Santos",
                },
                "role": {
                    "coding": [
                        {
                            "system": "urn:openspp:vocab:relationship",
                            "code": "head",
                            "display": "Head of Household",
                        }
                    ]
                },
                "startDate": "2024-01-15",
                "endedDate": None,
                "status": "active",
            }
        },
    )

    type: Literal["GroupMember"] = Field(
        "GroupMember",
        description="Resource type discriminator",
    )
    group: Reference = Field(
        ...,
        description="Reference to the Group",
    )
    entity: Reference = Field(
        ...,
        description="Reference to the Individual member",
    )
    role: CodeableConcept | None = Field(
        None,
        description="Member's role in the group",
    )
    start_date: date | None = Field(
        None,
        alias="startDate",
        description="When membership starts/started",
    )
    ended_date: date | None = Field(
        None,
        alias="endedDate",
        description="When membership ends/ended",
    )
    status: str = Field(
        ...,
        pattern="^(active|inactive)$",
        description="Current membership status",
    )


class GroupMembershipBundle(BaseModel):
    """Bundle of group memberships for an individual"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "type": "GroupMember",
                "total": 2,
                "entry": [
                    {
                        "resource": {
                            "type": "GroupMember",
                            "group": {
                                "reference": "Group/urn:openspp:group|HH-2024-001",
                                "display": "Santos Household",
                            },
                            "entity": {
                                "reference": "Individual/urn:gov:ph:psa:national-id|PH-123",
                                "display": "Maria Santos",
                            },
                            "role": {
                                "coding": [
                                    {
                                        "system": "urn:openspp:vocab:relationship",
                                        "code": "head",
                                        "display": "Head of Household",
                                    }
                                ]
                            },
                            "status": "active",
                        }
                    }
                ],
            }
        },
    )

    type: Literal["GroupMembershipList"] = Field(
        "GroupMembershipList",
        description="Resource type discriminator",
    )
    total: int = Field(
        ...,
        description="Total number of group memberships",
    )
    entry: list[dict] = Field(
        default_factory=list,
        description="List of group membership entries",
    )


class SplitGroupRequest(BaseModel):
    """Request to split a group into two groups"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "newGroupIdentifier": [
                    {
                        "system": "urn:openspp:group",
                        "value": "HH-2024-002",
                    }
                ],
                "membersToMove": [
                    {
                        "reference": "Individual/urn:gov:ph:psa:national-id|PH-111",
                        "display": "Juan dela Cruz",
                    },
                    {
                        "reference": "Individual/urn:gov:ph:psa:national-id|PH-222",
                        "display": "Ana dela Cruz",
                    },
                ],
                "newHead": {
                    "reference": "Individual/urn:gov:ph:psa:national-id|PH-111",
                    "display": "Juan dela Cruz",
                },
            }
        },
    )

    new_group_identifier: list[Identifier] = Field(
        ...,
        alias="newGroupIdentifier",
        min_length=1,
        description="Identifier(s) for the new group",
    )
    members_to_move: list[Reference] = Field(
        ...,
        alias="membersToMove",
        min_length=1,
        description="Members to move to the new group",
    )
    new_head: Reference | None = Field(
        None,
        alias="newHead",
        description="Head of the new group (must be in membersToMove if specified)",
    )


class MergeGroupRequest(BaseModel):
    """Request to merge one group into another"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "sourceGroup": {
                    "reference": "Group/urn:openspp:group|HH-2024-001",
                    "display": "Santos Household",
                },
                "targetGroup": {
                    "reference": "Group/urn:openspp:group|HH-2024-002",
                    "display": "Reyes Household",
                },
                "roleMapping": {
                    "head": "member",
                    "spouse": "spouse",
                },
            }
        },
    )

    source_group: Reference = Field(
        ...,
        alias="sourceGroup",
        description="Group to merge FROM (will be deactivated)",
    )
    target_group: Reference = Field(
        ...,
        alias="targetGroup",
        description="Group to merge INTO (will receive all members)",
    )
    role_mapping: dict[str, str] | None = Field(
        None,
        alias="roleMapping",
        description="Map source roles to target roles (optional)",
    )


class MembershipHistoryEntry(BaseModel):
    """Entry in membership history"""

    model_config = ConfigDict(
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T10:30:00Z",
                "action": "added",
                "member": {
                    "reference": "Individual/urn:gov:ph:psa:national-id|PH-123456789",
                    "display": "Maria Santos",
                },
                "newRole": {
                    "coding": [
                        {
                            "system": "urn:openspp:vocab:relationship",
                            "code": "head",
                            "display": "Head of Household",
                        }
                    ]
                },
                "changedBy": "user@example.com",
            }
        },
    )

    timestamp: datetime = Field(
        ...,
        description="When the change occurred",
    )
    action: str = Field(
        ...,
        pattern="^(added|removed|role_changed|status_changed)$",
        description="Type of membership change",
    )
    member: Reference = Field(
        ...,
        description="Reference to the Individual member",
    )
    old_role: CodeableConcept | None = Field(
        None,
        alias="oldRole",
        description="Previous role (for role_changed action)",
    )
    new_role: CodeableConcept | None = Field(
        None,
        alias="newRole",
        description="New role (for added or role_changed action)",
    )
    changed_by: str | None = Field(
        None,
        alias="changedBy",
        description="User who made the change",
    )
