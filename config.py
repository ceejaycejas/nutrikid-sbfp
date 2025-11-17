import os
from dotenv import load_dotenv

load_dotenv()


def _default_db_uri() -> str:
    # Prefer PyMySQL driver for Windows compatibility
    user = os.environ.get('MYSQL_USER', 'root')
    password = os.environ.get('MYSQL_PASSWORD', 'root')
    host = os.environ.get('MYSQL_HOST', '127.0.0.1')
    port = os.environ.get('MYSQL_PORT', '3306')
    db = os.environ.get('MYSQL_DB', 'capstone')
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{db}"


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    # Use DATABASE_URL if present; else build a sensible default using PyMySQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or _default_db_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Optional mail settings used by notification/email services (safe defaults)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')