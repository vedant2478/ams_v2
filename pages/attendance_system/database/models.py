"""
SQLAlchemy models for attendance system
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, LargeBinary, ForeignKey, func
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql.sqltypes import SMALLINT
from datetime import datetime
import numpy as np
import io

Base = declarative_base()


# Constants
ATTENDANCE_TYPE_IN = 'in'
ATTENDANCE_TYPE_OUT = 'out'

USER_STATUS_ACTIVE = 1
USER_STATUS_INACTIVE = 0


class User(Base):
    """User model for registered users with face embeddings"""
    
    __tablename__ = "users"
    
    # Primary key
    user_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User information
    name = Column(String(100), nullable=False, unique=True, index=True)
    email = Column(String(100), unique=True, nullable=True)
    mobile_number = Column(String(15), nullable=True)
    
    # Face recognition data
    embedding = Column(LargeBinary, nullable=False)  # Stores numpy array as binary
    
    # Status and metadata
    is_active = Column(SMALLINT, default=USER_STATUS_ACTIVE, nullable=False)
    registered_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Additional fields
    department = Column(String(100), nullable=True)
    designation = Column(String(100), nullable=True)
    employee_id = Column(String(50), unique=True, nullable=True)
    
    # Relationships
    attendance_records = relationship(
        "Attendance",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self):
        return f"<User(id={self.user_id}, name='{self.name}', active={self.is_active})>"
    
    @staticmethod
    def serialize_embedding(embedding_array):
        """
        Convert numpy array to binary for storage
        
        Args:
            embedding_array (np.ndarray): Face embedding vector
            
        Returns:
            bytes: Binary representation
        """
        out = io.BytesIO()
        np.save(out, embedding_array, allow_pickle=False)
        out.seek(0)
        return out.read()
    
    @staticmethod
    def deserialize_embedding(embedding_binary):
        """
        Convert binary back to numpy array
        
        Args:
            embedding_binary (bytes): Binary representation
            
        Returns:
            np.ndarray: Face embedding vector
        """
        if embedding_binary is None:
            return None
        out = io.BytesIO(embedding_binary)
        out.seek(0)
        return np.load(out, allow_pickle=False)
    
    def to_dict(self, include_embedding=False):
        """
        Convert user object to dictionary
        
        Args:
            include_embedding (bool): Whether to include embedding
            
        Returns:
            dict: User data
        """
        data = {
            'user_id': self.user_id,
            'name': self.name,
            'email': self.email,
            'mobile_number': self.mobile_number,
            'is_active': self.is_active,
            'registered_at': self.registered_at.isoformat() if self.registered_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'department': self.department,
            'designation': self.designation,
            'employee_id': self.employee_id
        }
        
        if include_embedding:
            data['embedding'] = self.deserialize_embedding(self.embedding)
        
        return data


class Attendance(Base):
    """Attendance model for tracking user attendance"""
    
    __tablename__ = "attendance"
    
    # Primary key
    attendance_id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign key to users
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    
    # Attendance information
    name = Column(String(100), nullable=False, index=True)  # Denormalized for quick access
    timestamp = Column(DateTime, default=func.now(), nullable=False, index=True)
    time_type = Column(String(10), nullable=False)  # 'in' or 'out'
    
    # Recognition details
    recognition_score = Column(Float, nullable=True)  # Face recognition confidence score
    
    # Location and device info (optional)
    location = Column(String(100), nullable=True)
    device_id = Column(String(50), nullable=True)
    
    # Metadata
    notes = Column(String(255), nullable=True)
    is_manual = Column(SMALLINT, default=0)  # 0 = auto, 1 = manual entry
    created_at = Column(DateTime, default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="attendance_records")
    
    def __repr__(self):
        return f"<Attendance(id={self.attendance_id}, user='{self.name}', type='{self.time_type}', time={self.timestamp})>"
    
    def to_dict(self):
        """
        Convert attendance object to dictionary
        
        Returns:
            dict: Attendance data
        """
        return {
            'attendance_id': self.attendance_id,
            'user_id': self.user_id,
            'name': self.name,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'time_type': self.time_type,
            'recognition_score': self.recognition_score,
            'location': self.location,
            'device_id': self.device_id,
            'notes': self.notes,
            'is_manual': self.is_manual
        }


class AttendanceSettings(Base):
    """Settings for attendance system"""
    
    __tablename__ = "attendance_settings"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(50), unique=True, nullable=False)
    setting_value = Column(String(255), nullable=True)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<AttendanceSettings(key='{self.setting_key}', value='{self.setting_value}')>"


class AttendanceReport(Base):
    """Daily attendance summary reports"""
    
    __tablename__ = "attendance_reports"
    
    report_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    report_date = Column(DateTime, nullable=False, index=True)
    
    # Timing information
    first_in_time = Column(DateTime, nullable=True)
    last_out_time = Column(DateTime, nullable=True)
    total_duration_minutes = Column(Integer, nullable=True)
    
    # Counts
    total_in_count = Column(Integer, default=0)
    total_out_count = Column(Integer, default=0)
    
    # Status
    is_present = Column(SMALLINT, default=0)
    is_late = Column(SMALLINT, default=0)
    is_early_exit = Column(SMALLINT, default=0)
    
    # Metadata
    generated_at = Column(DateTime, default=func.now())
    
    def __repr__(self):
        return f"<AttendanceReport(user_id={self.user_id}, date={self.report_date})>"
