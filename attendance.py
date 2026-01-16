import cv2
import numpy as np
import face_recognition
from datetime import datetime


class FaceAttendanceSystem:
    """
    Face recognition attendance system using face_recognition library.
    Lightweight alternative to DeepFace.
    """
    
    def __init__(self, tolerance=0.6):
        """
        Initialize the attendance system.
        
        Args:
            tolerance: Recognition tolerance (0.6 is default, lower = stricter)
        """
        self.tolerance = tolerance
        
        # In-memory storage
        self.users = {}  # {name: [encoding1, encoding2, ...]}
        self.attendance_log = []  # [{name, timestamp, distance, type}, ...]
        
        print(f"✅ FaceAttendanceSystem initialized")
        print(f"   Library: face_recognition")
        print(f"   Tolerance: {tolerance}")
    
    def _generate_encoding(self, image):
        """
        Generate face encoding from image using face_recognition.
        
        Args:
            image: OpenCV image (BGR format) or path to image
        
        Returns:
            encoding: Numpy array or None if no face detected
        """
        try:
            # Convert from path if needed
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    return None
            
            # Convert BGR to RGB (face_recognition uses RGB)
            rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            
            # Get face encodings
            encodings = face_recognition.face_encodings(rgb_image)
            
            if len(encodings) == 0:
                print(f"⚠ No face detected")
                return None
            
            # Return first face encoding
            return encodings[0]
        
        except Exception as e:
            print(f"❌ Encoding error: {e}")
            return None
    
    def register_user(self, name, image):
        """
        Register a new user.
        
        Args:
            name: User's name
            image: OpenCV image (BGR format) - numpy array
        
        Returns:
            success: True if registered, False otherwise
        """
        print(f"\n📝 Registering: {name}")
        
        encoding = self._generate_encoding(image)
        
        if encoding is None:
            print(f"❌ Registration failed - no face detected")
            return False
        
        if name not in self.users:
            self.users[name] = []
        
        self.users[name].append(encoding)
        
        print(f"✅ Registered: {name} (Total encodings: {len(self.users[name])})")
        return True
    
    def recognize_user(self, image):
        """
        Recognize user from image.
        
        Args:
            image: OpenCV image (BGR format) - numpy array
        
        Returns:
            (name, distance, confidence): Recognized name, distance, and confidence percentage
            Returns ("Unknown", 1.0, 0.0) if not recognized
        """
        query_encoding = self._generate_encoding(image)
        
        if query_encoding is None:
            return "Unknown", 1.0, 0.0
        
        if len(self.users) == 0:
            print("⚠ No registered users")
            return "Unknown", 1.0, 0.0
        
        best_name = "Unknown"
        best_distance = float('inf')
        
        # Compare with all stored encodings
        for name, encodings_list in self.users.items():
            # Use face_recognition's compare_faces
            distances = face_recognition.face_distance(encodings_list, query_encoding)
            min_distance = np.min(distances)
            
            if min_distance < best_distance:
                best_distance = min_distance
                best_name = name
        
        # Calculate confidence (inverse of distance, normalized to 0-100%)
        confidence = max(0, (1 - best_distance) * 100)
        
        if best_distance <= self.tolerance:
            print(f"✅ Recognized: {best_name} (distance: {best_distance:.3f}, confidence: {confidence:.1f}%)")
            return best_name, best_distance, confidence
        else:
            print(f"❌ Unknown (closest: {best_name} at {best_distance:.3f})")
            return "Unknown", best_distance, 0.0
    
    def mark_attendance(self, image, time_type="in"):
        """
        Mark attendance by recognizing user and logging.
        
        Args:
            image: OpenCV image (BGR format) - numpy array
            time_type: "in" or "out"
        
        Returns:
            (success, name, confidence): Tuple of success status, name, and confidence
        """
        name, distance, confidence = self.recognize_user(image)
        
        if name == "Unknown":
            print(f"❌ Attendance not marked: Unknown person")
            return False, "Unknown", 0.0
        
        record = {
            "name": name,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "distance": round(distance, 3),
            "confidence": round(confidence, 1),
            "type": time_type
        }
        
        self.attendance_log.append(record)
        
        print(f"✅ Attendance marked for: {name} ({time_type}) - Confidence: {confidence:.1f}%")
        return True, name, confidence
    
    def get_user_list(self):
        """Get list of all registered users."""
        return list(self.users.keys())
    
    def get_user_count(self):
        """Get total number of registered users."""
        return len(self.users)
    
    def get_attendance_log(self, name=None, limit=10):
        """Get attendance log."""
        if name:
            filtered = [r for r in self.attendance_log if r["name"] == name]
            return filtered[-limit:]
        else:
            return self.attendance_log[-limit:]
    
    def delete_user(self, name):
        """Delete a user."""
        if name in self.users:
            del self.users[name]
            print(f"✅ Deleted user: {name}")
            return True
        else:
            print(f"❌ User not found: {name}")
            return False
    
    def clear_attendance_log(self):
        """Clear all attendance records."""
        self.attendance_log = []
        print("✅ Attendance log cleared")
