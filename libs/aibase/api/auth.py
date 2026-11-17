from collections.abc import Callable
from dataclasses import dataclass, field

import jwt
from fastapi import Depends
from starlette.requests import HTTPConnection

from aibase.core.context import tenant_id_var
from aibase.core.errors import Forbidden, Unauthorized
from aibase.core.settings import Settings


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    scopes: frozenset[str] = field(default_factory=frozenset)


def _decode(token: str, settings: Settings) -> Principal:
    cfg = settings.auth
    try:
        claims = jwt.decode(
            token,
            cfg.public_key or "",
            algorithms=cfg.algorithms,
            audience=cfg.audience,
            issuer=cfg.issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        raise Unauthorized("invalid or expired token") from None
    tenant = claims.get(cfg.tenant_claim)
    if not tenant:
        raise Unauthorized("token missing tenant claim")
    raw_scopes = claims.get(cfg.scope_claim, "")
    scopes = raw_scopes.split() if isinstance(raw_scopes, str) else list(raw_scopes)
    return Principal(claims["sub"], str(tenant), frozenset(scopes))


async def get_principal(request: HTTPConnection) -> Principal:
    settings: Settings = request.app.state.settings
    if not settings.auth.enabled:
        principal = Principal("dev-user", "dev-tenant", frozenset({"*"}))
    else:
        header = request.headers.get("authorization", "")
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise Unauthorized("missing bearer token")
        principal = _decode(token, settings)
    tenant_id_var.set(principal.tenant_id)
    return principal


def require_scopes(*required: str) -> Callable[..., Principal]:
    def dependency(principal: Principal = Depends(get_principal)) -> Principal:  # noqa: B008
        if "*" not in principal.scopes and not set(required) <= principal.scopes:
            raise Forbidden("insufficient scope")
        return principal

    return dependency
