import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", os.getenv("SECRET_TOKEN", "dev-secret"))
    DATABASE_URL = os.getenv("DATABASE_URL")  # Corrected variable name
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRES", 86400))