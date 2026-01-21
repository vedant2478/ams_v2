"""
Database manager for handling all database operations
"""
from sqlalchemy import create_engine, and_, func, desc
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from datetime import datetime, date, timedelta
import numpy as np
import os

from .models import Base, User, Attendance, AttendanceSettings, AttendanceReport


class DatabaseManager:
    """Database manager with all CRUD operations"""
    
    _instance = None
    
    def __new__(cls, db_path='sqlite:///attendance.db'):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path='sqlite:///attendance.db'):
        """
        Initialize database manager
        
        Args:
            db_path (str): SQLite database path (SQLAlchemy URL format)
        """
        if self._initialized:
            return
        
        self.db_path = db_path
        
        # Create engine
        self.engine = create_engine(
            db_path,
            echo=False,  # Set to True for SQL debugging
            pool_pre_ping=True,
            connect_args={'check_same_thread': False}
        )
        
        # Create session factory
        session_factory = sessionmaker(bind=self.engine)
        self.Session = scoped_session(session_factory)
        
        # Create all tables
        self._create_tables()
        
        # Initialize default settings
        self._initialize_settings()
        
        self._initialized = True
        print(f"✓ Database initialized: {db_path}")
    
    def _create_tables(self):
        """Create all database tables"""
        try:
            Base.metadata.create_all(self.engine)
            print("✓ Database tables created/verified")
        except SQLAlchemyError as e:
            print(f"✗ Error creating tables: {e}")
            raise
    
    def _initialize_settings(self):
        """Initialize default settings"""
        session = self.Session()
        try:
            default_settings = [
                ('recognition_threshold', '180', 'Face recognition threshold score'),
                ('cooldown_seconds', '60', 'Cooldown period between attendance marks'),
                ('auto_logout_hours', '12', 'Auto logout after hours'),
                ('camera_index', '1', 'Default camera index')
            ]
            
            for key, value, desc in default_settings:
                existing = session.query(AttendanceSettings).filter_by(setting_key=key).first()
                if not existing:
                    setting = AttendanceSettings(
                        setting_key=key,
                        setting_value=value,
                        description=desc
                    )
                    session.add(setting)
            
            session.commit()
        except SQLAlchemyError as e:
            session.rollback()
            print(f"✗ Error initializing settings: {e}")
        finally:
            session.close()
    
    def get_session(self):
        """Get a new database session"""
        return self.Session()
    
    # ==================== USER OPERATIONS ====================
    
    def create_user(self, name, embedding, **kwargs):
        """
        Create a new user
        
        Args:
            name (str): User's name (unique)
            embedding (np.ndarray): Face embedding vector
            **kwargs: Additional fields (email, mobile_number, department, etc.)
            
        Returns:
            dict: {'success': bool, 'user_id': int, 'message': str, 'user': User}
        """
        session = self.Session()
        try:
            # Serialize embedding
            embedding_binary = User.serialize_embedding(embedding)
            
            # Create user object
            user = User(
                name=name,
                embedding=embedding_binary,
                email=kwargs.get('email'),
                mobile_number=kwargs.get('mobile_number'),
                department=kwargs.get('department'),
                designation=kwargs.get('designation'),
                employee_id=kwargs.get('employee_id'),
                is_active=kwargs.get('is_active', USER_STATUS_ACTIVE)
            )
            
            session.add(user)
            session.commit()
            
            user_id = user.user_id
            print(f"✓ User created: {name} (ID: {user_id})")
            
            return {
                'success': True,
                'user_id': user_id,
                'message': f'User {name} registered successfully',
                'user': user
            }
            
        except IntegrityError as e:
            session.rollback()
            return {
                'success': False,
                'user_id': None,
                'message': f'User {name} already exists',
                'user': None
            }
        except SQLAlchemyError as e:
            session.rollback()
            return {
                'success': False,
                'user_id': None,
                'message': f'Database error: {str(e)}',
                'user': None
            }
        finally:
            session.close()
    
    def get_user_by_id(self, user_id):
        """
        Get user by ID
        
        Args:
            user_id (int): User ID
            
        Returns:
            User: User object or None
        """
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id, is_active=USER_STATUS_ACTIVE).first()
            return user
        finally:
            session.close()
    
    def get_user_by_name(self, name):
        """
        Get user by name
        
        Args:
            name (str): User's name
            
        Returns:
            User: User object or None
        """
        session = self.Session()
        try:
            user = session.query(User).filter_by(
                name=name,
                is_active=USER_STATUS_ACTIVE,
                deleted_at=None
            ).first()
            return user
        finally:
            session.close()
    
    def get_all_users(self, active_only=True):
        """
        Get all users
        
        Args:
            active_only (bool): Return only active users
            
        Returns:
            list: List of User objects
        """
        session = self.Session()
        try:
            query = session.query(User).filter_by(deleted_at=None)
            
            if active_only:
                query = query.filter_by(is_active=USER_STATUS_ACTIVE)
            
            users = query.order_by(User.name).all()
            return users
        finally:
            session.close()
    
    def get_all_embeddings(self, active_only=True):
        """
        Get all user embeddings as dictionary
        
        Args:
            active_only (bool): Return only active users
            
        Returns:
            dict: {name: embedding_array}
        """
        session = self.Session()
        try:
            query = session.query(User.name, User.embedding).filter_by(deleted_at=None)
            
            if active_only:
                query = query.filter_by(is_active=USER_STATUS_ACTIVE)
            
            results = query.all()
            
            embeddings = {}
            for name, embedding_binary in results:
                embeddings[name] = User.deserialize_embedding(embedding_binary)
            
            return embeddings
        finally:
            session.close()
    
    def update_user(self, user_id, **kwargs):
        """
        Update user information
        
        Args:
            user_id (int): User ID
            **kwargs: Fields to update
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            # Update fields
            if 'name' in kwargs:
                user.name = kwargs['name']
            if 'email' in kwargs:
                user.email = kwargs['email']
            if 'mobile_number' in kwargs:
                user.mobile_number = kwargs['mobile_number']
            if 'embedding' in kwargs:
                user.embedding = User.serialize_embedding(kwargs['embedding'])
            if 'department' in kwargs:
                user.department = kwargs['department']
            if 'designation' in kwargs:
                user.designation = kwargs['designation']
            if 'employee_id' in kwargs:
                user.employee_id = kwargs['employee_id']
            if 'is_active' in kwargs:
                user.is_active = kwargs['is_active']
            
            user.updated_at = datetime.now()
            session.commit()
            
            print(f"✓ User updated (ID: {user_id})")
            return {'success': True, 'message': 'User updated successfully'}
            
        except IntegrityError:
            session.rollback()
            return {'success': False, 'message': 'Duplicate name or email'}
        except SQLAlchemyError as e:
            session.rollback()
            return {'success': False, 'message': f'Database error: {str(e)}'}
        finally:
            session.close()
    
    def delete_user(self, user_id, soft_delete=True):
        """
        Delete user
        
        Args:
            user_id (int): User ID
            soft_delete (bool): Soft delete (mark as deleted) or hard delete
            
        Returns:
            dict: {'success': bool, 'message': str}
        """
        session = self.Session()
        try:
            user = session.query(User).filter_by(user_id=user_id).first()
            
            if not user:
                return {'success': False, 'message': 'User not found'}
            
            if soft_delete:
                user.deleted_at = datetime.now()
                user.is_active = USER_STATUS_INACTIVE
                action = 'deactivated'
            else:
                session.delete(user)
                action = 'deleted'
            
            session.commit()
            print(f"✓ User {action} (ID: {user_id})")
            return {'success': True, 'message': f'User {action} successfully'}
            
        except SQLAlchemyError as e:
            session.rollback()
            return {'success': False, 'message': f'Database error: {str(e)}'}
        finally:
            session.close()
    
    def get_user_count(self, active_only=True):
        """Get total number of users"""
        session = self.Session()
        try:
            query = session.query(func.count(User.user_id)).filter_by(deleted_at=None)
            
            if active_only:
                query = query.filter_by(is_active=USER_STATUS_ACTIVE)
            
            return query.scalar()
        finally:
            session.close()
    
    # ==================== ATTENDANCE OPERATIONS ====================
    
    def mark_attendance(self, name, time_type=ATTENDANCE_TYPE_IN, recognition_score=None, **kwargs):
        """
        Mark attendance for a user
        
        Args:
            name (str): User's name
            time_type (str): 'in' or 'out'
            recognition_score (float): Face recognition score
            **kwargs: Additional fields (location, device_id, notes)
            
        Returns:
            dict: {'success': bool, 'attendance_id': int, 'message': str}
        """
        session = self.Session()
        try:
            # Get user
            user = session.query(User).filter_by(
                name=name,
                is_active=USER_STATUS_ACTIVE,
                deleted_at=None
            ).first()
            
            if not user:
                return {
                    'success': False,
                    'attendance_id': None,
                    'message': f'User {name} not found'
                }
            
            # Create attendance record
            attendance = Attendance(
                user_id=user.user_id,
                name=name,
                time_type=time_type,
                recognition_score=recognition_score,
                location=kwargs.get('location'),
                device_id=kwargs.get('device_id'),
                notes=kwargs.get('notes'),
                is_manual=kwargs.get('is_manual', 0)
            )
            
            session.add(attendance)
            session.commit()
            
            attendance_id = attendance.attendance_id
            timestamp = attendance.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            print(f"✓ Attendance marked: {name} | {time_type.upper()} | {timestamp}")
            
            return {
                'success': True,
                'attendance_id': attendance_id,
                'message': f'Attendance marked for {name}',
                'timestamp': timestamp
            }
            
        except SQLAlchemyError as e:
            session.rollback()
            return {
                'success': False,
                'attendance_id': None,
                'message': f'Database error: {str(e)}'
            }
        finally:
            session.close()
    
    def get_attendance_records(self, limit=50, offset=0):
        """
        Get attendance records
        
        Args:
            limit (int): Number of records
            offset (int): Offset for pagination
            
        Returns:
            list: List of Attendance objects
        """
        session = self.Session()
        try:
            records = session.query(Attendance)\
                .order_by(desc(Attendance.timestamp))\
                .limit(limit)\
                .offset(offset)\
                .all()
            return records
        finally:
            session.close()
    
    def get_user_attendance(self, user_id, limit=50):
        """
        Get attendance records for a specific user
        
        Args:
            user_id (int): User ID
            limit (int): Number of records
            
        Returns:
            list: List of Attendance objects
        """
        session = self.Session()
        try:
            records = session.query(Attendance)\
                .filter_by(user_id=user_id)\
                .order_by(desc(Attendance.timestamp))\
                .limit(limit)\
                .all()
            return records
        finally:
            session.close()
    
    def get_attendance_by_date(self, target_date=None):
        """
        Get attendance records for a specific date
        
        Args:
            target_date (date): Target date (None for today)
            
        Returns:
            list: List of Attendance objects
        """
        if target_date is None:
            target_date = date.today()
        
        session = self.Session()
        try:
            records = session.query(Attendance)\
                .filter(func.date(Attendance.timestamp) == target_date)\
                .order_by(desc(Attendance.timestamp))\
                .all()
            return records
        finally:
            session.close()
    
    def get_attendance_count(self):
        """Get total attendance records"""
        session = self.Session()
        try:
            return session.query(func.count(Attendance.attendance_id)).scalar()
        finally:
            session.close()
    
    # ==================== STATISTICS AND REPORTS ====================
    
    def get_statistics(self):
        """
        Get database statistics
        
        Returns:
            dict: Statistics
        """
        session = self.Session()
        try:
            stats = {
                'total_users': session.query(func.count(User.user_id)).filter_by(
                    is_active=USER_STATUS_ACTIVE,
                    deleted_at=None
                ).scalar(),
                'total_attendance': session.query(func.count(Attendance.attendance_id)).scalar(),
                'today_attendance': session.query(func.count(Attendance.attendance_id)).filter(
                    func.date(Attendance.timestamp) == date.today()
                ).scalar(),
                'week_attendance': session.query(func.count(Attendance.attendance_id)).filter(
                    Attendance.timestamp >= datetime.now() - timedelta(days=7)
                ).scalar()
            }
            return stats
        finally:
            session.close()
    
    def get_today_present_users(self):
        """Get list of users who marked attendance today"""
        session = self.Session()
        try:
            users = session.query(Attendance.name).distinct()\
                .filter(func.date(Attendance.timestamp) == date.today())\
                .all()
            return [user[0] for user in users]
        finally:
            session.close()
    
    # ==================== UTILITY METHODS ====================
    
    def close(self):
        """Close all sessions"""
        self.Session.remove()
        print("✓ Database sessions closed")
    
    def backup_database(self, backup_path=None):
        """
        Backup database (for SQLite)
        
        Args:
            backup_path (str): Backup file path
        """
        if not self.db_path.startswith('sqlite:///'):
            return {'success': False, 'error': 'Backup only supported for SQLite'}
        
        import shutil
        
        if backup_path is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = f'backup_attendance_{timestamp}.db'
        
        try:
            db_file = self.db_path.replace('sqlite:///', '')
            shutil.copy2(db_file, backup_path)
            print(f"✓ Database backed up to: {backup_path}")
            return {'success': True, 'path': backup_path}
        except Exception as e:
            print(f"✗ Backup error: {e}")
            return {'success': False, 'error': str(e)}


# Example usage
if __name__ == "__main__":
    # Initialize database
    db = DatabaseManager('sqlite:///test_attendance.db')
    
    # Test user creation
    print("\n=== Testing User Operations ===")
    embedding1 = np.random.rand(128)
    result = db.create_user(
        name="John Doe",
        embedding=embedding1,
        email="john@example.com",
        department="Engineering"
    )
    print(result)
    
    # Get all users
    print("\n=== All Users ===")
    users = db.get_all_users()
    for user in users:
        print(f"{user.name} (ID: {user.user_id}) - {user.department}")
    
    # Mark attendance
    print("\n=== Testing Attendance ===")
    db.mark_attendance("John Doe", "in", 95.5)
    
    # Get statistics
    print("\n=== Statistics ===")
    stats = db.get_statistics()
    print(stats)
    
    # Cleanup
    db.close()
