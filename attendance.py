import cv2
import numpy as np
from deepface import DeepFace
from datetime import datetime


class FaceAttendanceSystem:
    """
    Face recognition attendance system using DeepFace.
    Uses DeepFace library with in-memory storage.
    """
    
    def __init__(self, model_name="Facenet512", distance_metric="cosine", tolerance=0.4):
        """
        Initialize the attendance system.
        
        Args:
            model_name: Recognition model (Facenet512, VGG-Face, ArcFace, etc.)
            distance_metric: Distance metric (cosine, euclidean, euclidean_l2)
            tolerance: Recognition tolerance (lower = stricter, default 0.4 for cosine)
        """
        self.model_name = model_name
        self.distance_metric = distance_metric
        self.tolerance = tolerance
        
        # In-memory storage
        self.users = {}  # {name: [embedding1, embedding2, ...]}
        self.attendance_log = []  # [{name, timestamp, distance, type}, ...]
        
        print(f"✅ FaceAttendanceSystem initialized")
        print(f"   Model: {model_name}")
        print(f"   Distance Metric: {distance_metric}")
        print(f"   Tolerance: {tolerance}")
    
    def _generate_encoding(self, image):
        """Generate face embedding from image using DeepFace."""
        try:
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    return None
            
            result = DeepFace.represent(
                img_path=image,
                model_name=self.model_name,
                enforce_detection=True,
                detector_backend="opencv",
                align=True
            )
            
            if len(result) == 0:
                return None
            
            embedding = np.array(result[0]["embedding"])
            return embedding
        
        except Exception as e:
            print(f"❌ Encoding error: {e}")
            return None
    
    def _calculate_distance(self, embedding1, embedding2):
        """Calculate distance between two embeddings."""
        if self.distance_metric == "cosine":
            return 1 - np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
        elif self.distance_metric == "euclidean":
            return np.linalg.norm(embedding1 - embedding2)
        elif self.distance_metric == "euclidean_l2":
            return np.linalg.norm(embedding1 - embedding2) / np.sqrt(np.sum(embedding1**2) + np.sum(embedding2**2))
        else:
            return 1 - np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
    
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
        
        for name, encodings_list in self.users.items():
            for encoding in encodings_list:
                distance = self._calculate_distance(query_encoding, encoding)
                
                if distance < best_distance:
                    best_distance = distance
                    best_name = name
        
        # Calculate confidence (inverse of distance, normalized to 0-100%)
        if self.distance_metric == "cosine":
            confidence = max(0, (1 - best_distance) * 100)
        else:
            confidence = max(0, (self.tolerance - best_distance) / self.tolerance * 100)
        
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
