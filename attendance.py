import cv2
import numpy as np
from datetime import datetime


class FaceAttendanceSystem:
    """
    Simple face recognition using template matching.
    Works with basic opencv-python (no contrib needed).
    """
    
    def __init__(self, threshold=0.6):
        """
        Initialize the attendance system.
        
        Args:
            threshold: Similarity threshold (0.5-0.7 recommended)
        """
        self.threshold = threshold
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # In-memory storage
        self.users = {}  # {name: [face_template1, face_template2, ...]}
        self.attendance_log = []
        
        print(f"✅ FaceAttendanceSystem initialized (Template Matching)")
        print(f"   Threshold: {threshold}")
    
    def _detect_and_extract_face(self, image):
        """Detect and extract face from image."""
        try:
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    return None
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) == 0:
                print("⚠ No face detected")
                return None
            
            # Get largest face
            (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
            face_roi = gray[y:y+h, x:x+w]
            
            # Resize to standard size and normalize
            face_roi = cv2.resize(face_roi, (100, 100))
            face_roi = cv2.equalizeHist(face_roi)  # Normalize lighting
            
            return face_roi
        
        except Exception as e:
            print(f"❌ Face detection error: {e}")
            return None
    
    def _calculate_similarity(self, face1, face2):
        """Calculate similarity between two face templates using correlation."""
        # Template matching using normalized cross-correlation
        result = cv2.matchTemplate(face1, face2, cv2.TM_CCOEFF_NORMED)
        similarity = result[0][0]
        return similarity
    
    def register_user(self, name, image):
        """
        Register a new user.
        
        Args:
            name: User's name
            image: OpenCV image (BGR format)
        
        Returns:
            success: True if registered, False otherwise
        """
        print(f"\n📝 Registering: {name}")
        
        face_template = self._detect_and_extract_face(image)
        
        if face_template is None:
            print(f"❌ Registration failed - no face detected")
            return False
        
        if name not in self.users:
            self.users[name] = []
        
        self.users[name].append(face_template)
        
        print(f"✅ Registered: {name} (Total templates: {len(self.users[name])})")
        return True
    
    def recognize_user(self, image):
        """
        Recognize user from image.
        
        Args:
            image: OpenCV image (BGR format)
        
        Returns:
            (name, confidence, similarity): Recognized name, confidence %, and similarity
        """
        query_face = self._detect_and_extract_face(image)
        
        if query_face is None:
            return "Unknown", 0.0, 0.0
        
        if len(self.users) == 0:
            print("⚠ No registered users")
            return "Unknown", 0.0, 0.0
        
        best_name = "Unknown"
        best_similarity = -1.0
        
        # Compare with all stored templates
        for name, templates in self.users.items():
            for template in templates:
                similarity = self._calculate_similarity(query_face, template)
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_name = name
        
        # Calculate confidence
        confidence = best_similarity * 100
        
        if best_similarity >= self.threshold:
            print(f"✅ Recognized: {best_name} (similarity: {best_similarity:.3f}, confidence: {confidence:.1f}%)")
            return best_name, confidence, best_similarity
        else:
            print(f"❌ Unknown (closest: {best_name} at {best_similarity:.3f})")
            return "Unknown", 0.0, best_similarity
    
    def mark_attendance(self, image, time_type="in"):
        """Mark attendance."""
        name, confidence, similarity = self.recognize_user(image)
        
        if name == "Unknown":
            print(f"❌ Attendance not marked: Unknown person")
            return False, "Unknown", 0.0
        
        record = {
            "name": name,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "similarity": round(similarity, 3),
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
