# user_registration_service.py

from datetime import datetime
import pytz
from sqlalchemy.orm import Session
from models import AMS_Users, AMS_Event_Log


class UserRegistrationService:
    """
    Service to handle new user registration with card and PIN
    """
    
    TZ_INDIA = pytz.timezone('Asia/Kolkata')
    
    def __init__(self, db_session):
        """
        Initialize the registration service
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.session = db_session
    
    def create_new_user(self, card_number, pin, **kwargs):
        """
        Create a new user with card number and PIN
        
        Args:
            card_number (str): Card number to assign to user
            pin (str): 4-digit PIN for authentication
            **kwargs: Additional user fields (name, email, role, etc.)
            
        Returns:
            dict: Result with status and user data or error message
        """
        try:
            print(f"[USER_REG] Creating new user with card: {card_number}, PIN: {pin}")
            
            # Validate inputs
            if not card_number or not pin:
                return {
                    "success": False,
                    "error": "Card number and PIN are required"
                }
            
            # Check if card already exists
            existing_card = self.session.query(AMS_Users).filter(
                AMS_Users.cardNo == str(card_number),
                AMS_Users.deletedAt == None
            ).first()
            
            if existing_card:
                print(f"[USER_REG] Card {card_number} already registered")
                return {
                    "success": False,
                    "error": f"Card {card_number} is already assigned to {existing_card.name}"
                }
            
            # Check if PIN already exists
            existing_pin = self.session.query(AMS_Users).filter(
                AMS_Users.pinNo == str(pin),
                AMS_Users.deletedAt == None
            ).first()
            
            if existing_pin:
                print(f"[USER_REG] PIN already registered")
                return {
                    "success": False,
                    "error": "This PIN is already in use"
                }
            
            # Create new user
            new_user = AMS_Users(
                cardNo=str(card_number),
                pinNo=str(pin),
                name=kwargs.get('name', f'User_{card_number}'),
                email=kwargs.get('email', None),
                role=kwargs.get('role', 'user'),
                isActive=kwargs.get('isActive', True),
                createdAt=datetime.now(self.TZ_INDIA),
                updatedAt=datetime.now(self.TZ_INDIA),
                deletedAt=None
            )
            
            self.session.add(new_user)
            self.session.flush()  # Get the user ID before commit
            
            # Log registration success event
            ams_event_log = AMS_Event_Log(
                userId=new_user.id,
                keyId=None,
                activityId=None,
                eventId=1001,  # User registration success event ID
                loginType="CARD_PIN",
                access_log_id=None,
                timeStamp=datetime.now(self.TZ_INDIA),
                event_type="EVENT",
                eventDesc=f"New user registered - Card: {card_number}",
                is_posted=0
            )
            
            self.session.add(ams_event_log)
            self.session.commit()
            
            print(f"[USER_REG] ✓ User created successfully: ID={new_user.id}, Name={new_user.name}")
            
            return {
                "success": True,
                "user_id": new_user.id,
                "name": new_user.name,
                "card_number": card_number,
                "message": "User registered successfully"
            }
            
        except Exception as e:
            self.session.rollback()
            print(f"[USER_REG] ✗ Registration failed: {e}")
            
            # Log failure event
            try:
                ams_event_log = AMS_Event_Log(
                    userId=None,
                    keyId=None,
                    activityId=None,
                    eventId=1002,  # User registration failure event ID
                    loginType="CARD_PIN",
                    access_log_id=None,
                    timeStamp=datetime.now(self.TZ_INDIA),
                    event_type="ALARM",
                    eventDesc=f"User registration failed - Card: {card_number}, Error: {str(e)}",
                    is_posted=0
                )
                
                self.session.add(ams_event_log)
                self.session.commit()
            except:
                pass
            
            return {
                "success": False,
                "error": str(e)
            }
    
    def update_user_details(self, user_id, **updates):
        """
        Update user details after initial registration
        
        Args:
            user_id (int): User ID to update
            **updates: Fields to update (name, email, etc.)
            
        Returns:
            bool: Success status
        """
        try:
            user = self.session.query(AMS_Users).filter(
                AMS_Users.id == user_id,
                AMS_Users.deletedAt == None
            ).first()
            
            if not user:
                print(f"[USER_REG] User {user_id} not found")
                return False
            
            # Update fields
            for key, value in updates.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            user.updatedAt = datetime.now(self.TZ_INDIA)
            self.session.commit()
            
            print(f"[USER_REG] User {user_id} updated successfully")
            return True
            
        except Exception as e:
            self.session.rollback()
            print(f"[USER_REG] Update failed: {e}")
            return False
