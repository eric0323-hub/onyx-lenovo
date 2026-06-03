from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict

from onyx.db.enums import AccessType
from onyx.db.enums import Permission
from onyx.db.models import ConnectorCredentialPair
from onyx.db.models import User as UserDBModel
from onyx.db.models import UserGroup as UserGroupDBModel
from onyx.server.features.document_set.models import DocumentSetSummary
from onyx.server.features.persona.models import PersonaSnapshot
from onyx.server.models import FullUserSnapshot


class MinimalUserGroupSnapshot(BaseModel):
    id: int
    name: str


class ConnectorSnapshot(BaseModel):
    source: str


class CredentialSnapshot(BaseModel):
    id: int


class ConnectorCredentialPairSnapshot(BaseModel):
    id: int
    name: str
    connector: ConnectorSnapshot
    credential: CredentialSnapshot
    access_type: AccessType

    @classmethod
    def from_model(
        cls, cc_pair: ConnectorCredentialPair
    ) -> "ConnectorCredentialPairSnapshot":
        return cls(
            id=cc_pair.id,
            name=cc_pair.name,
            connector=ConnectorSnapshot(source=cc_pair.connector.source.value),
            credential=CredentialSnapshot(id=cc_pair.credential_id),
            access_type=cc_pair.access_type,
        )


class UserGroup(BaseModel):
    id: int
    name: str
    users: list[FullUserSnapshot]
    curator_ids: list[UUID]
    cc_pairs: list[ConnectorCredentialPairSnapshot]
    document_sets: list[DocumentSetSummary]
    personas: list[PersonaSnapshot]
    is_up_to_date: bool
    is_up_for_deletion: bool
    is_default: bool

    @classmethod
    def from_model(cls, user_group: UserGroupDBModel) -> "UserGroup":
        curator_ids = [
            relationship.user_id
            for relationship in user_group.user_group_relationships
            if relationship.is_curator and relationship.user_id is not None
        ]
        return cls(
            id=user_group.id,
            name=user_group.name,
            users=[
                FullUserSnapshot.from_user_model(user)
                for user in sorted(user_group.users, key=_sort_user_key)
            ],
            curator_ids=curator_ids,
            cc_pairs=[
                ConnectorCredentialPairSnapshot.from_model(cc_pair)
                for cc_pair in sorted(user_group.cc_pairs, key=lambda cc_pair: cc_pair.id)
            ],
            document_sets=[
                DocumentSetSummary.from_model(document_set)
                for document_set in sorted(
                    user_group.document_sets, key=lambda document_set: document_set.id
                )
            ],
            personas=[
                PersonaSnapshot.from_model(persona)
                for persona in sorted(user_group.personas, key=lambda persona: persona.id)
            ],
            is_up_to_date=user_group.is_up_to_date,
            is_up_for_deletion=user_group.is_up_for_deletion,
            is_default=user_group.is_default,
        )


class UserGroupCreate(BaseModel):
    name: str
    user_ids: list[UUID]
    cc_pair_ids: list[int] = []


class UserGroupUpdate(BaseModel):
    user_ids: list[UUID]
    cc_pair_ids: list[int] = []


class UserGroupRename(BaseModel):
    id: int
    name: str


class AddUsersToUserGroupRequest(BaseModel):
    user_ids: list[UUID]


class SetCuratorRequest(BaseModel):
    user_id: UUID
    is_curator: bool


class SetPermissionRequest(BaseModel):
    permission: Permission
    enabled: bool


class SetPermissionResponse(BaseModel):
    permission: Permission
    enabled: bool


class UpdateGroupAgentsRequest(BaseModel):
    added_agent_ids: list[int] = []
    removed_agent_ids: list[int] = []


class UserGroupPermissionSnapshot(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    permission: Permission


def _sort_user_key(user: UserDBModel) -> tuple[str, str]:
    name = user.personal_name or user.email
    return (name.lower(), str(user.id))
