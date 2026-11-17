from fastapi import FastAPI

from aibase.api import create_app
from aibase.core.settings import Settings, get_settings
from aibase.providers.factory import Providers, build_providers
from transcription_service.api import TASK, make_handler, router


def create_service_app(
    settings: Settings | None = None, providers: Providers | None = None
) -> FastAPI:
    settings = settings or get_settings().model_copy(update={"service_name": "transcription"})
    providers = providers or build_providers(settings)
    providers.queue.register(TASK, make_handler(providers))
    return create_app(
        settings, title="Transcription Service", routers=[router], providers=providers
    )
