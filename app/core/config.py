from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv
import os
class Settings(BaseSettings):
    PROJECT_NAME: str = "Document Screening System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB")
    DATABASE_URL: Optional[str] = None

    # Bootstrap User
    BOOTSTRAP_ADMIN_USERNAME: str = os.getenv("BOOTSTRAP_ADMIN_USERNAME")
    BOOTSTRAP_ADMIN_PASSWORD: str = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    BOOTSTRAP_ADMIN_NAME: str = os.getenv("BOOTSTRAP_ADMIN_NAME")
    BOOTSTRAP_ADMIN_DOB: str = os.getenv("BOOTSTRAP_ADMIN_DOB")
    BOOTSTRAP_ADMIN_GENDER: str = os.getenv("BOOTSTRAP_ADMIN_GENDER")
    BOOTSTRAP_ADMIN_AADHAR: str = os.getenv("BOOTSTRAP_ADMIN_AADHAR")
    BOOTSTRAP_ADMIN_PHONE: str = os.getenv("BOOTSTRAP_ADMIN_PHONE")
    BOOTSTRAP_ADMIN_EMAIL: str = os.getenv("BOOTSTRAP_ADMIN_EMAIL")
    BOOTSTRAP_ADMIN_FACE_IMAGE: str = os.getenv("BOOTSTRAP_ADMIN_FACE_IMAGE")

    # Bootstrap System
    BOOTSTRAP_SYSTEM_NAME: str = os.getenv("BOOTSTRAP_SYSTEM_NAME")
    
    # JWT
    SECRET_KEY: str = os.getenv("SECRET_KEY")
    ALGORITHM: str = os.getenv("ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES")

    # Blockchain
    SEPOLIA_RPC_URL: str = os.getenv("SEPOLIA_RPC_URL")
    BLOCKCHAIN_PRIVATE_KEY: str = os.getenv("BLOCKCHAIN_PRIVATE_KEY")
    CONTRACT_ADDRESS: str = os.getenv("CONTRACT_ADDRESS")
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

if not settings.DATABASE_URL:
    settings.DATABASE_URL = f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_SERVER}/{settings.POSTGRES_DB}"