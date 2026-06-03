from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from onyx.auth.schemas import UserRole
from onyx.auth.permissions import require_permission
from onyx.configs.constants import PUBLIC_API_TAGS
from onyx.db.engine.sql_engine import get_session
from onyx.db.enums import Permission
from onyx.db.models import User
from onyx.db.user_group import add_users_to_user_group
from onyx.db.user_group import fetch_user_group
from onyx.db.user_group import fetch_user_groups
from onyx.db.user_group import fetch_user_groups_for_user
from onyx.db.user_group import get_user_group_permissions
from onyx.db.user_group import insert_user_group
from onyx.db.user_group import mark_user_group_for_deletion
from onyx.db.user_group import rename_user_group
from onyx.db.user_group import set_user_group_curator_status
from onyx.db.user_group import set_user_group_permission
from onyx.db.user_group import update_user_group
from onyx.db.user_group import update_user_group_agents
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.user_group.models import AddUsersToUserGroupRequest
from onyx.server.user_group.models import MinimalUserGroupSnapshot
from onyx.server.user_group.models import SetCuratorRequest
from onyx.server.user_group.models import SetPermissionRequest
from onyx.server.user_group.models import SetPermissionResponse
from onyx.server.user_group.models import UpdateGroupAgentsRequest
from onyx.server.user_group.models import UserGroup
from onyx.server.user_group.models import UserGroupCreate
from onyx.server.user_group.models import UserGroupRename
from onyx.server.user_group.models import UserGroupUpdate


router = APIRouter(prefix="/manage", tags=PUBLIC_API_TAGS)


@router.get("/admin/user-group")
def list_user_groups(
    include_default: bool = False,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[UserGroup]:
    return [
        UserGroup.from_model(user_group)
        for user_group in fetch_user_groups(
            db_session=db_session,
            include_default=include_default,
        )
    ]


@router.get("/user-groups/minimal")
def list_minimal_user_groups(
    include_default: bool = False,
    user: User = Depends(require_permission(Permission.BASIC_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[MinimalUserGroupSnapshot]:
    if user.role == UserRole.ADMIN:
        user_groups = fetch_user_groups(db_session, include_default=include_default)
    else:
        user_groups = fetch_user_groups_for_user(
            db_session=db_session,
            user_id=user.id,
            include_default=include_default,
        )
    return [
        MinimalUserGroupSnapshot(id=user_group.id, name=user_group.name)
        for user_group in user_groups
    ]


@router.get("/admin/user-group/{user_group_id}")
def get_user_group(
    user_group_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    user_group = fetch_user_group(db_session, user_group_id)
    if user_group is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"UserGroup with id '{user_group_id}' not found",
        )
    return UserGroup.from_model(user_group)


@router.get("/admin/user-group/{user_group_id}/permissions")
def get_permissions_for_user_group(
    user_group_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> list[str]:
    return [
        permission.value
        for permission in get_user_group_permissions(
            db_session=db_session,
            user_group_id=user_group_id,
        )
    ]


@router.put("/admin/user-group/{user_group_id}/permissions")
def set_permissions_for_user_group(
    user_group_id: int,
    set_permission_request: SetPermissionRequest,
    user: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> SetPermissionResponse:
    set_user_group_permission(
        db_session=db_session,
        user_group_id=user_group_id,
        permission=set_permission_request.permission,
        enabled=set_permission_request.enabled,
        granted_by=user.id,
    )
    return SetPermissionResponse(
        permission=set_permission_request.permission,
        enabled=set_permission_request.enabled,
    )


@router.post("/admin/user-group")
def create_user_group(
    user_group_create: UserGroupCreate,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    return UserGroup.from_model(
        insert_user_group(
            db_session=db_session,
            user_group_create=user_group_create,
        )
    )


@router.patch("/admin/user-group/rename")
def rename_group(
    user_group_rename: UserGroupRename,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    return UserGroup.from_model(
        rename_user_group(
            db_session=db_session,
            user_group_id=user_group_rename.id,
            name=user_group_rename.name,
        )
    )


@router.patch("/admin/user-group/{user_group_id}")
def edit_user_group(
    user_group_id: int,
    user_group_update: UserGroupUpdate,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    return UserGroup.from_model(
        update_user_group(
            db_session=db_session,
            user_group_id=user_group_id,
            user_group_update=user_group_update,
        )
    )


@router.post("/admin/user-group/{user_group_id}/add-users")
def add_users(
    user_group_id: int,
    add_users_request: AddUsersToUserGroupRequest,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    return UserGroup.from_model(
        add_users_to_user_group(
            db_session=db_session,
            user_group_id=user_group_id,
            user_ids=add_users_request.user_ids,
        )
    )


@router.post("/admin/user-group/{user_group_id}/set-curator")
def set_curator(
    user_group_id: int,
    set_curator_request: SetCuratorRequest,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    return UserGroup.from_model(
        set_user_group_curator_status(
            db_session=db_session,
            user_group_id=user_group_id,
            set_curator_request=set_curator_request,
        )
    )


@router.delete("/admin/user-group/{user_group_id}")
def delete_user_group(
    user_group_id: int,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> None:
    mark_user_group_for_deletion(db_session=db_session, user_group_id=user_group_id)


@router.patch("/admin/user-group/{user_group_id}/agents")
def edit_group_agents(
    user_group_id: int,
    update_group_agents_request: UpdateGroupAgentsRequest,
    _: User = Depends(require_permission(Permission.FULL_ADMIN_PANEL_ACCESS)),
    db_session: Session = Depends(get_session),
) -> UserGroup:
    return UserGroup.from_model(
        update_user_group_agents(
            db_session=db_session,
            user_group_id=user_group_id,
            added_agent_ids=update_group_agents_request.added_agent_ids,
            removed_agent_ids=update_group_agents_request.removed_agent_ids,
        )
    )
