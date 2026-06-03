from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from onyx.configs.constants import TokenRateLimitScope
from onyx.db.models import UserGroup
from onyx.db.models import TokenRateLimit
from onyx.db.models import TokenRateLimit__UserGroup
from onyx.error_handling.error_codes import OnyxErrorCode
from onyx.error_handling.exceptions import OnyxError
from onyx.server.token_rate_limits.models import TokenRateLimitArgs


def fetch_all_user_token_rate_limits(
    db_session: Session,
    enabled_only: bool = False,
    ordered: bool = True,
) -> Sequence[TokenRateLimit]:
    query = select(TokenRateLimit).where(
        TokenRateLimit.scope == TokenRateLimitScope.USER
    )

    if enabled_only:
        query = query.where(TokenRateLimit.enabled.is_(True))

    if ordered:
        query = query.order_by(TokenRateLimit.created_at.desc())

    return db_session.scalars(query).all()


def fetch_all_global_token_rate_limits(
    db_session: Session,
    enabled_only: bool = False,
    ordered: bool = True,
) -> Sequence[TokenRateLimit]:
    query = select(TokenRateLimit).where(
        TokenRateLimit.scope == TokenRateLimitScope.GLOBAL
    )

    if enabled_only:
        query = query.where(TokenRateLimit.enabled.is_(True))

    if ordered:
        query = query.order_by(TokenRateLimit.created_at.desc())

    token_rate_limits = db_session.scalars(query).all()
    return token_rate_limits


def fetch_all_user_group_token_rate_limits(
    db_session: Session,
    enabled_only: bool = False,
    ordered: bool = True,
) -> dict[str, Sequence[TokenRateLimit]]:
    query = (
        select(UserGroup.name, TokenRateLimit)
        .join(
            TokenRateLimit__UserGroup,
            TokenRateLimit__UserGroup.user_group_id == UserGroup.id,
        )
        .join(
            TokenRateLimit,
            TokenRateLimit.id == TokenRateLimit__UserGroup.rate_limit_id,
        )
        .where(TokenRateLimit.scope == TokenRateLimitScope.USER_GROUP)
    )

    if enabled_only:
        query = query.where(TokenRateLimit.enabled.is_(True))

    if ordered:
        query = query.order_by(UserGroup.name.asc(), TokenRateLimit.created_at.desc())

    rows = db_session.execute(query).all()
    grouped: dict[str, list[TokenRateLimit]] = {}
    for group_name, token_limit in rows:
        grouped.setdefault(group_name, []).append(token_limit)
    return grouped


def fetch_user_group_token_rate_limits(
    db_session: Session,
    user_group_id: int,
    enabled_only: bool = False,
    ordered: bool = True,
) -> Sequence[TokenRateLimit]:
    query = (
        select(TokenRateLimit)
        .join(
            TokenRateLimit__UserGroup,
            TokenRateLimit__UserGroup.rate_limit_id == TokenRateLimit.id,
        )
        .where(
            TokenRateLimit.scope == TokenRateLimitScope.USER_GROUP,
            TokenRateLimit__UserGroup.user_group_id == user_group_id,
        )
    )

    if enabled_only:
        query = query.where(TokenRateLimit.enabled.is_(True))

    if ordered:
        query = query.order_by(TokenRateLimit.created_at.desc())

    return db_session.scalars(query).all()


def insert_user_token_rate_limit(
    db_session: Session,
    token_rate_limit_settings: TokenRateLimitArgs,
) -> TokenRateLimit:
    token_limit = TokenRateLimit(
        enabled=token_rate_limit_settings.enabled,
        token_budget=token_rate_limit_settings.token_budget,
        period_hours=token_rate_limit_settings.period_hours,
        scope=TokenRateLimitScope.USER,
    )
    db_session.add(token_limit)
    db_session.commit()

    return token_limit


def insert_user_group_token_rate_limit(
    db_session: Session,
    user_group_id: int,
    token_rate_limit_settings: TokenRateLimitArgs,
) -> TokenRateLimit:
    user_group = db_session.get(UserGroup, user_group_id)
    if user_group is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"UserGroup with id '{user_group_id}' not found",
        )

    token_limit = TokenRateLimit(
        enabled=token_rate_limit_settings.enabled,
        token_budget=token_rate_limit_settings.token_budget,
        period_hours=token_rate_limit_settings.period_hours,
        scope=TokenRateLimitScope.USER_GROUP,
    )
    db_session.add(token_limit)
    db_session.flush()
    db_session.add(
        TokenRateLimit__UserGroup(
            rate_limit_id=token_limit.id,
            user_group_id=user_group_id,
        )
    )
    db_session.commit()

    return token_limit


def insert_global_token_rate_limit(
    db_session: Session,
    token_rate_limit_settings: TokenRateLimitArgs,
) -> TokenRateLimit:
    token_limit = TokenRateLimit(
        enabled=token_rate_limit_settings.enabled,
        token_budget=token_rate_limit_settings.token_budget,
        period_hours=token_rate_limit_settings.period_hours,
        scope=TokenRateLimitScope.GLOBAL,
    )
    db_session.add(token_limit)
    db_session.commit()

    return token_limit


def update_token_rate_limit(
    db_session: Session,
    token_rate_limit_id: int,
    token_rate_limit_settings: TokenRateLimitArgs,
) -> TokenRateLimit:
    token_limit = db_session.get(TokenRateLimit, token_rate_limit_id)
    if token_limit is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"TokenRateLimit with id '{token_rate_limit_id}' not found",
        )

    token_limit.enabled = token_rate_limit_settings.enabled
    token_limit.token_budget = token_rate_limit_settings.token_budget
    token_limit.period_hours = token_rate_limit_settings.period_hours
    db_session.commit()

    return token_limit


def delete_token_rate_limit(
    db_session: Session,
    token_rate_limit_id: int,
) -> None:
    token_limit = db_session.get(TokenRateLimit, token_rate_limit_id)
    if token_limit is None:
        raise OnyxError(
            OnyxErrorCode.NOT_FOUND,
            f"TokenRateLimit with id '{token_rate_limit_id}' not found",
        )

    db_session.query(TokenRateLimit__UserGroup).filter(
        TokenRateLimit__UserGroup.rate_limit_id == token_rate_limit_id
    ).delete()

    db_session.delete(token_limit)
    db_session.commit()
