from fastapi import Request

from aibase.api.auth import Principal
from aibase.audit import AuditEvent, AuditSink
from aibase.core.context import request_id_var
from aibase.core.settings import Settings
from aibase.providers.factory import Providers


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_providers(request: Request) -> Providers:
    providers: Providers = request.app.state.providers
    return providers


def get_audit(request: Request) -> AuditSink:
    sink: AuditSink = request.app.state.audit
    return sink


def record_audit(
    sink: AuditSink, principal: Principal, action: str, resource: str = "-", **extra: str | None
) -> None:
    """Resource must be an opaque ID, never PHI."""
    sink.write(
        AuditEvent(
            actor=principal.subject,
            tenant_id=principal.tenant_id,
            action=action,
            resource=resource,
            request_id=request_id_var.get(),
            **extra,
        )
    )
