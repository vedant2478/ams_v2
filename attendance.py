import cv2
import numpy as np
from datetime import datetime


class FaceAttendanceSystem:
    """
    Lightweight face recognition using OpenCV only (no dlib required).
    Uses Local Binary Patterns Histograms (LBPH) for face recognition.
    """
    
    def __init__(self, threshold=50):
        """
        Initialize the attendance system.
        
        Args:
            threshold: Recognition threshold (lower = stricter, default 50)
        """
        self.threshold = threshold
        self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
        
        # In-memory storage
        self.users = {}  # {name: user_id}
        self.user_id_counter = 0
        self.face_samples = []  # List of face samples
        self.face_labels = []   # Corresponding labels
        self.attendance_log = []
        self.is_trained = False
        
        print(f"✅ FaceAttendanceSystem initialized (OpenCV LBPH)")
        print(f"   Threshold: {threshold}")
    
    def _detect_face(self, image):
        """Detect face in image and return face ROI."""
        try:
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    return None
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
            
            faces = face_cascade.detectMultiScale(gray, 1.3, 5)
            
            if len(faces) == 0:
                print("⚠ No face detected")
                return None
            
            # Return first face
            (x, y, w, h) = faces[0]
            face_roi = gray[y:y+h, x:x+w]
            
            # Resize to standard size
            face_roi = cv2.resize(face_roi, (200, 200))
            
            return face_roi
        
        except Exception as e:
            print(f"❌ Face detection error: {e}")
            return None
    
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
        
        face_roi = self._detect_face(image)
        
        if face_roi is None:
            print(f"❌ Registration failed - no face detected")
            return False
        
        # Assign user ID
        if name not in self.users:
            self.users[name] = self.user_id_counter
            self.user_id_counter += 1
        
        user_id = self.users[name]
        
        # Add face sample
        self.face_samples.append(face_roi)
        self.face_labels.append(user_id)
        
        # Retrain recognizer
        self.face_recognizer.train(self.face_samples, np.array(self.face_labels))
        self.is_trained = True
        
        print(f"✅ Registered: {name} (ID: {user_id}, Samples: {self.face_labels.count(user_id)})")
        return True
    
    def recognize_user(self, image):
        """
        Recognize user from image.
        
        Args:
            image: OpenCV image (BGR format)
        
        Returns:
            (name, confidence, distance): Recognized name, confidence %, and distance
        """
        if not self.is_trained:
            print("⚠ No trained users")
            return "Unknown", 0.0, 100.0
        
        face_roi = self._detect_face(image)
        
        if face_roi is None:
            return "Unknown", 0.0, 100.0
        
        # Predict
        label, distance = self.face_recognizer.predict(face_roi)
        
        # Find name from label
        name = "Unknown"
        for user_name, user_id in self.users.items():
            if user_id == label:
                name = user_name
                break
        
        # Calculate confidence (inverse of distance)
        confidence = max(0, (100 - distance))
        
        if distance <= self.threshold:
            print(f"✅ Recognized: {name} (distance: {distance:.1f}, confidence: {confidence:.1f}%)")
            return name, confidence, distance
        else:
            print(f"❌ Unknown (closest: {name} at {distance:.1f})")
            return "Unknown", 0.0, distance
    
    def mark_attendance(self, image, time_type="in"):
        """
        Mark attendance.
        
        Args:
            image: OpenCV image (BGR format)
            time_type: "in" or "out"
        
        Returns:
            (success, name, confidence): Tuple
        """
        name, confidence, distance = self.recognize_user(image)
        
        if name == "Unknown":
            print(f"❌ Attendance not marked: Unknown person")
            return False, "Unknown", 0.0
        
        record = {
            "name": name,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "distance": round(distance, 1),
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
        """Delete a user (requires retraining)."""
        if name not in self.users:
            print(f"❌ User not found: {name}")
            return False
        
        user_id = self.users[name]
        del self.users[name]
        
        # Remove samples
        indices_to_remove = [i for i, label in enumerate(self.face_labels) if label == user_id]
        for index in sorted(indices_to_remove, reverse=True):
            del self.face_samples[index]
            del self.face_labels[index]
        
        # Retrain if samples remain
        if len(self.face_samples) > 0:
            self.face_recognizer.train(self.face_samples, np.array(self.face_labels))
        else:
            self.is_trained = False
        
        print(f"✅ Deleted user: {name}")
        return True
    
    def clear_attendance_log(self):
        """Clear all attendance records."""
        self.attendance_log = []
        print("✅ Attendance log cleared")
