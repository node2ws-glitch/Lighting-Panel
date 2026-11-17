from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine
from app import models  # noqa: F401
from app.middleware import SecurityAndRateLimitMiddleware
from app.routes import router
from app.billing import router as billing_router
from app.operations import router as operations_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield

settings = get_settings()
production = settings.environment.lower() == 'production'
if production and any('localhost' in origin or '127.0.0.1' in origin for origin in settings.cors_origin_list):
    raise RuntimeError('Production CORS_ORIGINS must not contain localhost origins')
app = FastAPI(title=settings.app_name, version='0.4.0', lifespan=lifespan,
    docs_url=None if production else '/docs',
    redoc_url=None if production else '/redoc',
    openapi_url=None if production else '/openapi.json')
app.add_middleware(SecurityAndRateLimitMiddleware, default_limit=settings.rate_limit_per_minute)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False,
    allow_methods=['GET', 'POST', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=['Authorization', 'Content-Type', 'Stripe-Signature', 'X-Node-Token', 'X-Request-ID'])
app.include_router(router, prefix=settings.api_prefix)
app.include_router(billing_router, prefix=settings.api_prefix)
app.include_router(operations_router, prefix=settings.api_prefix)

@app.get('/')
def root():
    return {'name': settings.app_name, 'docs': None if production else '/docs', 'health': f'{settings.api_prefix}/health'}
