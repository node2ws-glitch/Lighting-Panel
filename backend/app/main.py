from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import engine
from app import models  # noqa: F401
from app.routes import router

@asynccontextmanager
async def lifespan(_: FastAPI):
    yield

settings = get_settings()
app = FastAPI(title=settings.app_name, version='0.2.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=False, allow_methods=['GET', 'POST', 'PATCH', 'OPTIONS'], allow_headers=['Authorization', 'Content-Type'])
app.include_router(router, prefix=settings.api_prefix)

@app.get('/')
def root():
    return {'name': settings.app_name, 'docs': '/docs', 'health': f'{settings.api_prefix}/health'}
