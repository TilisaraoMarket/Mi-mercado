import os
from dotenv import load_dotenv

# Carga variables de entorno desde un archivo .env si existe
load_dotenv()

class Config:
    # Configuración básica
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Configuración de bases de datos
    MONGO_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/mimercado')
    
    # Configuración de servicios externos
    STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', 'sk_test_4eC39HqLyjWDarjtT1zdp7dc')
    
    # Configuración de seguridad y sesiones
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'True').lower() in ['true', '1']
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.environ.get('SESSION_COOKIE_SAMESITE', 'Lax')
    PERMANENT_SESSION_LIFETIME = int(os.environ.get('SESSION_LIFETIME', '86400'))  # 24 hours in seconds
    
    # Configuración de entorno
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1']
