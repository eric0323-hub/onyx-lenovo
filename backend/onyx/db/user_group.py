from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from sqlalchemy.orm import Session

from onyx.auth.permissions import NON_TOGGLEABLE_PERMISSIONS
from onyx.db.enums import GrantSource
from onyx.db.enums import Permission
from onyx.db.models import ConnectorCredentialPair
from onyx.db.models import Credential__UserGroup
from onyx.db.models import DocumentSet__UserGroup
from onyx.db.models import LLMProvider__UserGroup
from onyx.db.models import MCPServer__UserGroup
from onyx.db.models import PermissionGrant
from onyx.db.models import Persona
from onyx.db.models import Persona__UserGroup
from onyx.db.models import ScimGroupMapping
from onyx.db.models import Skill__UserGroup
from onyx.db.models import TokenRateLimit
from onyx.db.models import TokenRateLimit__UserGroup
from onyx.db.models import User
from onyx.db.models import User__UserGroup
from onyx.db.models import UserGroup
from onyx.db.models import UserGroup__ConnectorCredentialPair
from onyx.db.permissions import recompute_permissions_for_group__no_commit
from onyx.db.permissions import recompute_user_permissions__no_commit
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.user_group.models import SetCuratorRequest
from onyx.server.user_group.models import UserGroupCreate
from onyx.server.user_group.models import UserGroupUpdate
from onyx.utils.variable_functionality import global_version


def fetch_user_group(db_session: Session, user_group_id: int) -> UserGroup | None:
    return db_session.scalar(
        _user_group_select().where(UserGroup.id == user_group_id)
    )


def fetch_user_groups(
    db_session: Session,
    include_default: bool = False,
) -> Sequence[UserGroup]:
    stmt = _user_group_select().where(UserGroup.is_up_for_deletion.is_(False))
    if not include_default:
        stmt = stmt.where(UserGroup.is_default.is_(False))
    stmt = stmt.order_by(UserGroup.is_default.desc(), UserGroup.name.asc())
    return db_session.scalars(stmt).unique().all()


def fetch_user_groups_for_user(
    db_session: Session,
    user_id: UUID,
    include_default: bool = False,
) -> Sequence[UserGroup]:
    stmt = (
        _user_group_select()
        .join(User__UserGroup)
        .where(
            User__UserGroup.user_id == user_id,
            UserGroup.is_up_for_deletion.is_(False),
        )
        .order_by(UserGroup.name.asc())
    )
    if not include_default:
        stmt = stmt.where(UserGroup.is_default.is_(False))
    return db_session.scalars(stmt).unique().all()


def insert_user_group(
    db_session: Session,
    user_group_create: UserGroupCreate,
) -> UserGroup:
    name = _clean_group_name(user_group_create.name)
    _validate_users_exist(db_session, user_group_create.user_ids)
    _validate_cc_pairs_exist(db_session, user_group_create.cc_pair_ids)

    user_group = UserGroup(
        name=name,
        is_up_to_date=not _requires_async_user_group_sync(),
        is_up_for_deletion=False,
        is_default=False,
        time_last_modified_by_user=func.now(),
    )
    db_session.add(user_group)
    try:
        db_session.flush()
        _replace_group_members__no_commit(
            db_session=db_session,
            user_group_id=user_group.id,
            user_ids=user_group_create.user_ids,
        )
        _replace_group_cc_pairs__no_commit(
            db_session=db_session,
            user_group_id=user_group.id,
            cc_pair_ids=user_group_create.cc_pair_ids,
        )
        db_session.add(
            PermissionGrant(
                group_id=user_group.id,
                permission=Permission.BASIC_ACCESS,
                grant_source=GrantSource.SYSTEM,
            )
        )
        recompute_permissions_for_group__no_commit(user_group.id, db_session)
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        raise OnyxError(
            OnyxErrorCode.DUPLICATE_RESOURCE,
            f"User group named '{name}' already exists.",
        ) from e

    refreshed = fetch_user_group(db_session, user_group.id)
    if refreshed is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Created user group not found.")
    return refreshed


def update_user_group(
    db_session: Session,
    user_group_id: int,
    user_group_update: UserGroupUpdate,
) -> UserGroup:
    user_group = _require_user_group(db_session, user_group_id)
    if user_group.is_up_for_deletion:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "User group is being deleted.")

    _validate_users_exist(db_session, user_group_update.user_ids)
    _validate_cc_pairs_exist(db_session, user_group_update.cc_pair_ids)

    previous_user_ids = {
        relationship.user_id
        for relationship in user_group.user_group_relationships
        if relationship.user_id is not None
    }
    new_user_ids = set(user_group_update.user_ids)
    impacted_user_ids = previous_user_ids | new_user_ids

    _replace_group_members__no_commit(
        db_session=db_session,
        user_group_id=user_group_id,
        user_ids=user_group_update.user_ids,
    )
    _replace_group_cc_pairs__no_commit(
        db_session=db_session,
        user_group_id=user_group_id,
        cc_pair_ids=user_group_update.cc_pair_ids,
    )
    user_group.is_up_to_date = not _requires_async_user_group_sync()
    user_group.time_last_modified_by_user = func.now()
    recompute_user_permissions__no_commit(list(impacted_user_ids), db_session)
    db_session.commit()

    refreshed = fetch_user_group(db_session, user_group_id)
    if refreshed is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Updated user group not found.")
    return refreshed


def add_users_to_user_group(
    db_session: Session,
    user_group_id: int,
    user_ids: list[UUID],
) -> UserGroup:
    user_group = _require_user_group(db_session, user_group_id)
    _validate_users_exist(db_session, user_ids)

    existing_user_ids = {
        relationship.user_id
        for relationship in user_group.user_group_relationships
        if relationship.user_id is not None
    }
    new_user_ids = [user_id for user_id in user_ids if user_id not in existing_user_ids]
    for user_id in new_user_ids:
        db_session.add(User__UserGroup(user_group_id=user_group_id, user_id=user_id))

    user_group.is_up_to_date = not _requires_async_user_group_sync()
    user_group.time_last_modified_by_user = func.now()
    recompute_user_permissions__no_commit(new_user_ids, db_session)
    db_session.commit()

    refreshed = fetch_user_group(db_session, user_group_id)
    if refreshed is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Updated user group not found.")
    return refreshed


def rename_user_group(
    db_session: Session,
    user_group_id: int,
    name: str,
) -> UserGroup:
    user_group = _require_user_group(db_session, user_group_id)
    if user_group.is_default:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "Default groups cannot be renamed.")

    user_group.name = _clean_group_name(name)
    user_group.time_last_modified_by_user = func.now()
    try:
        db_session.commit()
    except IntegrityError as e:
        db_session.rollback()
        raise OnyxError(
            OnyxErrorCode.DUPLICATE_RESOURCE,
            f"User group named '{user_group.name}' already exists.",
        ) from e

    refreshed = fetch_user_group(db_session, user_group_id)
    if refreshed is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Renamed user group not found.")
    return refreshed


def mark_user_group_for_deletion(
    db_session: Session,
    user_group_id: int,
) -> None:
    user_group = _require_user_group_row(db_session, user_group_id)
    if user_group.is_default:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "Default groups cannot be deleted.")

    user_ids = [
        user_id
        for user_id in db_session.scalars(
            select(User__UserGroup.user_id).where(
                User__UserGroup.user_group_id == user_group_id,
                User__UserGroup.user_id.isnot(None),
            )
        ).all()
        if user_id is not None
    ]

    db_session.execute(
        delete(User__UserGroup).where(User__UserGroup.user_group_id == user_group_id)
    )
    db_session.execute(
        delete(UserGroup__ConnectorCredentialPair).where(
            UserGroup__ConnectorCredentialPair.user_group_id == user_group_id
        )
    )
    db_session.execute(
        delete(Persona__UserGroup).where(
            Persona__UserGroup.user_group_id == user_group_id
        )
    )
    db_session.execute(
        delete(DocumentSet__UserGroup).where(
            DocumentSet__UserGroup.user_group_id == user_group_id
        )
    )
    db_session.execute(
        delete(Credential__UserGroup).where(
            Credential__UserGroup.user_group_id == user_group_id
        )
    )
    db_session.execute(
        delete(Skill__UserGroup).where(Skill__UserGroup.user_group_id == user_group_id)
    )
    db_session.execute(
        delete(LLMProvider__UserGroup).where(
            LLMProvider__UserGroup.user_group_id == user_group_id
        )
    )
    db_session.execute(
        delete(MCPServer__UserGroup).where(
            MCPServer__UserGroup.user_group_id == user_group_id
        )
    )
    token_limit_ids = list(
        db_session.scalars(
            select(TokenRateLimit__UserGroup.rate_limit_id).where(
                TokenRateLimit__UserGroup.user_group_id == user_group_id
            )
        ).all()
    )
    db_session.execute(
        delete(TokenRateLimit__UserGroup).where(
            TokenRateLimit__UserGroup.user_group_id == user_group_id
        )
    )
    if token_limit_ids:
        db_session.execute(
            delete(TokenRateLimit).where(TokenRateLimit.id.in_(token_limit_ids))
        )
    db_session.execute(
        delete(ScimGroupMapping).where(ScimGroupMapping.user_group_id == user_group_id)
    )
    db_session.execute(
        delete(PermissionGrant).where(PermissionGrant.group_id == user_group_id)
    )
    if _requires_async_user_group_sync():
        user_group.is_up_for_deletion = True
        user_group.is_up_to_date = False
    else:
        db_session.delete(user_group)
    user_group.time_last_modified_by_user = func.now()
    recompute_user_permissions__no_commit(user_ids, db_session)
    db_session.commit()


def mark_usergroup_as_synced(user_group_id: int, db_session: Session) -> None:
    user_group = _require_user_group_row(db_session, user_group_id)
    if user_group.is_up_for_deletion:
        db_session.delete(user_group)
    else:
        user_group.is_up_to_date = True
        db_session.execute(
            delete(UserGroup__ConnectorCredentialPair).where(
                UserGroup__ConnectorCredentialPair.user_group_id == user_group_id,
                UserGroup__ConnectorCredentialPair.is_current.is_(False),
            )
        )
    db_session.commit()


def set_user_group_curator_status(
    db_session: Session,
    user_group_id: int,
    set_curator_request: SetCuratorRequest,
) -> UserGroup:
    _require_user_group(db_session, user_group_id)
    relationship = db_session.get(
        User__UserGroup,
        {
            "user_group_id": user_group_id,
            "user_id": set_curator_request.user_id,
        },
    )
    if relationship is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            "User must be a group member before they can be made curator.",
        )

    relationship.is_curator = set_curator_request.is_curator
    db_session.commit()

    refreshed = fetch_user_group(db_session, user_group_id)
    if refreshed is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Updated user group not found.")
    return refreshed


def update_user_group_agents(
    db_session: Session,
    user_group_id: int,
    added_agent_ids: list[int],
    removed_agent_ids: list[int],
) -> UserGroup:
    _require_user_group(db_session, user_group_id)
    _validate_personas_exist(db_session, added_agent_ids + removed_agent_ids)

    for persona_id in added_agent_ids:
        existing = db_session.get(
            Persona__UserGroup,
            {"persona_id": persona_id, "user_group_id": user_group_id},
        )
        if existing is None:
            db_session.add(
                Persona__UserGroup(
                    persona_id=persona_id,
                    user_group_id=user_group_id,
                )
            )

    if removed_agent_ids:
        db_session.execute(
            delete(Persona__UserGroup).where(
                Persona__UserGroup.user_group_id == user_group_id,
                Persona__UserGroup.persona_id.in_(removed_agent_ids),
            )
        )

    db_session.commit()
    refreshed = fetch_user_group(db_session, user_group_id)
    if refreshed is None:
        raise OnyxError(OnyxErrorCode.NOT_FOUND, "Updated user group not found.")
    return refreshed


def get_user_group_permissions(
    db_session: Session,
    user_group_id: int,
) -> list[Permission]:
    _require_user_group(db_session, user_group_id)
    return list(
        db_session.scalars(
            select(PermissionGrant.permission)
            .where(
                PermissionGrant.group_id == user_group_id,
                PermissionGrant.is_deleted.is_(False),
            )
            .order_by(PermissionGrant.permission.asc())
        ).all()
    )


def set_user_group_permission(
    db_session: Session,
    user_group_id: int,
    permission: Permission,
    enabled: bool,
    granted_by: UUID | None,
) -> list[Permission]:
    _require_user_group(db_session, user_group_id)
    if permission in NON_TOGGLEABLE_PERMISSIONS:
        raise OnyxError(
            OnyxErrorCode.INVALID_INPUT,
            f"Permission '{permission.value}' cannot be toggled directly.",
        )

    existing = db_session.scalar(
        select(PermissionGrant).where(
            PermissionGrant.group_id == user_group_id,
            PermissionGrant.permission == permission,
        )
    )
    if enabled:
        if existing is None:
            db_session.add(
                PermissionGrant(
                    group_id=user_group_id,
                    permission=permission,
                    grant_source=GrantSource.USER,
                    granted_by=granted_by,
                )
            )
        else:
            existing.is_deleted = False
            existing.grant_source = GrantSource.USER
            existing.granted_by = granted_by
            existing.granted_at = func.now()
    elif existing is not None:
        existing.is_deleted = True

    recompute_permissions_for_group__no_commit(user_group_id, db_session)
    db_session.commit()
    return get_user_group_permissions(db_session, user_group_id)


def _user_group_select():
    return select(UserGroup).options(
        selectinload(UserGroup.users),
        selectinload(UserGroup.user_group_relationships),
        selectinload(UserGroup.cc_pairs).selectinload(
            ConnectorCredentialPair.connector
        ),
        selectinload(UserGroup.cc_pairs).selectinload(
            ConnectorCredentialPair.credential
        ),
        selectinload(UserGroup.document_sets),
        selectinload(UserGroup.personas),
        selectinload(UserGroup.permission_grants),
    )


def _require_user_group(db_session: Session, user_group_id: int) -> UserGroup:
    user_group = fetch_user_group(db_session, user_group_id)
    if user_group is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"UserGroup with id '{user_group_id}' not found",
        )
    return user_group


def _require_user_group_row(db_session: Session, user_group_id: int) -> UserGroup:
    user_group = db_session.get(UserGroup, user_group_id)
    if user_group is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"UserGroup with id '{user_group_id}' not found",
        )
    return user_group


def _clean_group_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        raise OnyxError(OnyxErrorCode.INVALID_INPUT, "Group name is required.")
    return cleaned


def _validate_users_exist(db_session: Session, user_ids: list[UUID]) -> None:
    if not user_ids:
        return
    found_ids = set(
        db_session.scalars(select(User.id).where(User.id.in_(user_ids))).all()
    )
    missing = set(user_ids) - found_ids
    if missing:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"Users not found: {', '.join(str(user_id) for user_id in sorted(missing))}",
        )


def _validate_cc_pairs_exist(db_session: Session, cc_pair_ids: list[int]) -> None:
    if not cc_pair_ids:
        return
    found_ids = set(
        db_session.scalars(
            select(ConnectorCredentialPair.id).where(
                ConnectorCredentialPair.id.in_(cc_pair_ids)
            )
        ).all()
    )
    missing = set(cc_pair_ids) - found_ids
    if missing:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"Connector credential pairs not found: {sorted(missing)}",
        )


def _validate_personas_exist(db_session: Session, persona_ids: list[int]) -> None:
    if not persona_ids:
        return
    found_ids = set(
        db_session.scalars(select(Persona.id).where(Persona.id.in_(persona_ids))).all()
    )
    missing = set(persona_ids) - found_ids
    if missing:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"Agents not found: {sorted(missing)}",
        )


def _replace_group_members__no_commit(
    db_session: Session,
    user_group_id: int,
    user_ids: list[UUID],
) -> None:
    db_session.execute(
        delete(User__UserGroup).where(User__UserGroup.user_group_id == user_group_id)
    )
    db_session.add_all(
        [
            User__UserGroup(user_group_id=user_group_id, user_id=user_id)
            for user_id in user_ids
        ]
    )


def _replace_group_cc_pairs__no_commit(
    db_session: Session,
    user_group_id: int,
    cc_pair_ids: list[int],
) -> None:
    db_session.execute(
        delete(UserGroup__ConnectorCredentialPair).where(
            UserGroup__ConnectorCredentialPair.user_group_id == user_group_id
        )
    )
    db_session.add_all(
        [
            UserGroup__ConnectorCredentialPair(
                user_group_id=user_group_id,
                cc_pair_id=cc_pair_id,
                is_current=True,
            )
            for cc_pair_id in cc_pair_ids
        ]
    )


def _requires_async_user_group_sync() -> bool:
    return global_version.is_ee_version()
