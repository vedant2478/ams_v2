# user_registration_service.py

from datetime import datetime
import pytz
from sqlalchemy.orm import Session
from model import AMS_Users, AMS_Event_Log


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
                AMS_Users.pinCode == str(pin),
                AMS_Users.deletedAt == None
            ).first()
            
            if existing_pin:
                print(f"[USER_REG] PIN already registered")
                return {
                    "success": False,
                    "error": "This PIN is already in use"
                }
            
            # Set default validity dates (1 year from now)
            validity_from = datetime.now(self.TZ_INDIA)
            validity_to = datetime.now(self.TZ_INDIA).replace(year=validity_from.year + 1)
            
            # Create new user
            new_user = AMS_Users(
                cardNo=str(card_number),
                pinCode=str(pin),
                name=kwargs.get('name', f'User_{card_number}'),
                email=kwargs.get('email', None),
                mobileNumber=kwargs.get('mobileNumber', None),
                validityFrom=validity_from,
                validityTo=validity_to,
                roleId=kwargs.get('roleId', None),
                lastLoginDate=None,
                isActive=kwargs.get('isActive', '1'),  # String '1' for active
                isActiveInt=kwargs.get('isActiveInt', 1),  # Integer 1 for active
                cabinetId=kwargs.get('cabinetId', None),
                createdAt=datetime.now(self.TZ_INDIA),
                updatedAt=datetime.now(self.TZ_INDIA),
                deletedAt=None,
                fpTemplate=None
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
                event_type=1,  # EVENT_TYPE_EVENT
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
            import traceback
            traceback.print_exc()
            
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
                    event_type=2,  # EVENT_TYPE_ALARM
                    eventDesc=f"User registration failed - Card: {card_number}, Error: {str(e)}",
                    is_posted=0
                )
                
                self.session.add(ams_event_log)
                self.session.commit()
            except Exception as log_error:
                print(f"[USER_REG] Failed to log error: {log_error}")
            
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
