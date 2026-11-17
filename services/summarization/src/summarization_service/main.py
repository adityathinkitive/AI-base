from fastapi import FastAPI

from aibase.api import create_app
from aibase.core.settings import Settings, get_settings
from aibase.providers.factory import Providers
from summarization_service.api import router


def create_service_app(
    settings: Settings | None = None, providers: Providers | None = None
) -> FastAPI:
    settings = settings or get_settings().model_copy(update={"service_name": "summarization"})
    return create_app(
        settings, title="Summarization Service", routers=[router], providers=providers
    )
