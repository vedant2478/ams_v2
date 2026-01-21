"""
Database configuration
"""
import os

# Database configuration
DB_TYPE = 'sqlite'  # or 'mysql', 'postgresql'
DB_NAME = 'attendance.db'
DB_PATH = os.path.join(os.path.dirname(__file__), '..', DB_NAME)

# SQLAlchemy database URL
if DB_TYPE == 'sqlite':
    DATABASE_URL = f'sqlite:///{DB_PATH}'
else:
    # For MySQL/PostgreSQL
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', 'password')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_PORT = os.getenv('DB_PORT', '3306')
    
    if DB_TYPE == 'mysql':
        DATABASE_URL = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
    elif DB_TYPE == 'postgresql':
        DATABASE_URL = f'postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}'

# Settings
RECOGNITION_THRESHOLD = 180
COOLDOWN_SECONDS = 60
AUTO_LOGOUT_HOURS = 12
