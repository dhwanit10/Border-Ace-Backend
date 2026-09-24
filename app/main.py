from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient
from app.core.config import settings
from app.core.database import engine, Base
from app.core.dependencies import get_current_user
from app.core.init_db import reset_database, init_database
from app.api.v1.endpoints import (
    workflow,
    history,
    documents,
    system,
    session,
    auth,
    users,
    verification
)
from app.api.v1.endpoints import blockchain
from app.core.bootstrap import initialize_database


# uncomment this for running the first time and then delete this code 
# initialize_database()



app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# @app.on_event("startup")
# def startup():

#     initialize_database()


# ==========================================
# PUBLIC APIs
# ==========================================

# USER REGISTRATION AND LOGIN
# These must remain public because the user
# needs to get a token before authentication.

app.include_router(
    users.router,
    prefix=f"{settings.API_V1_STR}/users",
    tags=["users"]
)

app.include_router(
    blockchain.router, 
    prefix=f"{settings.API_V1_STR}/blockchain", 
    tags=["blockchain"],
    dependencies=[
        Depends(get_current_user)
    ]
)

# ==========================================
# PROTECTED APIs
# JWT TOKEN REQUIRED
# ==========================================

app.include_router(
    verification.router,
    prefix=f"{settings.API_V1_STR}/verification",
    tags=["verification"],
    dependencies=[
        Depends(get_current_user)
    ]
)


app.include_router(
    workflow.router,
    prefix=f"{settings.API_V1_STR}/workflow",
    tags=["workflow"],
    dependencies=[
        Depends(get_current_user)
    ]
)


app.include_router(
    history.router,
    prefix=f"{settings.API_V1_STR}/data",
    tags=["data"],
    dependencies=[
        Depends(get_current_user)
    ]
)


app.include_router(
    documents.router,
    prefix=f"{settings.API_V1_STR}/documents",
    tags=["documents"],
    dependencies=[
        Depends(get_current_user)
    ]
)


app.include_router(
    system.router,
    prefix=f"{settings.API_V1_STR}/system",
    tags=["system"]
)


app.include_router(
    session.router,
    prefix=f"{settings.API_V1_STR}/session",
    tags=["session"],
    dependencies=[
        Depends(get_current_user)
    ]
)


# Logout can also be protected
app.include_router(
    auth.router,
    prefix=f"{settings.API_V1_STR}/auth",
    tags=["auth"],
    dependencies=[
        Depends(get_current_user)
    ]
)


# ==========================================
# ROOT API
# ==========================================

@app.get("/")
async def root():

    return {
        "message": f"Welcome to {settings.PROJECT_NAME}",
        "version": settings.VERSION
    }


# ==========================================
# HEALTH CHECK
# Keep public for deployment monitoring
# ==========================================

@app.get("/health")
async def health_check():

    return {
        "status": "healthy"
    }