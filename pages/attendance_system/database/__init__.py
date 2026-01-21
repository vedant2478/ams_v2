"""
Database package for face recognition attendance system
"""
from .models import Base, User, Attendance
from .db_manager import DatabaseManager

__all__ = ['Base', 'User', 'Attendance', 'DatabaseManager']
