import cv2
import numpy as np
from datetime import datetime
import insightface
from insightface.app import FaceAnalysis
from sklearn.metrics.pairwise import cosine_similarity


class FaceAttendanceSystem:
    """
    Face recognition using InsightFace (ONNX Runtime).
    Better accuracy than OpenCV LBPH, lighter than DeepFace.
    """
    
    def __init__(self, threshold=0.4):
        """
        Initialize the attendance system.
        
        Args:
            threshold: Similarity threshold (lower = stricter, 0.3-0.5 recommended)
        """
        self.threshold = threshold
        
        # Initialize InsightFace
        print("🔄 Initializing InsightFace...")
        self.app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
        self.app.prepare(ctx_id=0, det_size=(640, 640))
        
        # In-memory storage
        self.users = {}  # {name: [embedding1, embedding2, ...]}
        self.attendance_log = []
        
        print(f"✅ FaceAttendanceSystem initialized (InsightFace)")
        print(f"   Threshold: {threshold}")
    
    def _generate_encoding(self, image):
        """
        Generate face embedding from image using InsightFace.
        
        Args:
            image: OpenCV image (BGR format)
        
        Returns:
            embedding: Numpy array or None if no face detected
        """
        try:
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    return None
            
            # Detect faces and get embeddings
            faces = self.app.get(image)
            
            if len(faces) == 0:
                print("⚠ No face detected")
                return None
            
            # Return embedding of first (largest) face
            embedding = faces[0].embedding
            
            # Normalize embedding
            embedding = embedding / np.linalg.norm(embedding)
            
            return embedding
        
        except Exception as e:
            print(f"❌ Encoding error: {e}")
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
        
        embedding = self._generate_encoding(image)
        
        if embedding is None:
            print(f"❌ Registration failed - no face detected")
            return False
        
        if name not in self.users:
            self.users[name] = []
        
        self.users[name].append(embedding)
        
        print(f"✅ Registered: {name} (Total embeddings: {len(self.users[name])})")
        return True
    
    def recognize_user(self, image):
        """
        Recognize user from image.
        
        Args:
            image: OpenCV image (BGR format)
        
        Returns:
            (name, confidence, similarity): Recognized name, confidence %, and similarity score
        """
        query_embedding = self._generate_encoding(image)
        
        if query_embedding is None:
            return "Unknown", 0.0, 0.0
        
        if len(self.users) == 0:
            print("⚠ No registered users")
            return "Unknown", 0.0, 0.0
        
        best_name = "Unknown"
        best_similarity = -1.0
        
        # Compare with all stored embeddings
        for name, embeddings_list in self.users.items():
            for embedding in embeddings_list:
                # Calculate cosine similarity
                similarity = cosine_similarity(
                    query_embedding.reshape(1, -1),
                    embedding.reshape(1, -1)
                )[0][0]
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_name = name
        
        # Calculate confidence
        confidence = best_similarity * 100
        
        # Check threshold (for cosine similarity, higher is better)
        if best_similarity >= self.threshold:
            print(f"✅ Recognized: {best_name} (similarity: {best_similarity:.3f}, confidence: {confidence:.1f}%)")
            return best_name, confidence, best_similarity
        else:
            print(f"❌ Unknown (closest: {best_name} at {best_similarity:.3f})")
            return "Unknown", 0.0, best_similarity
    
    def mark_attendance(self, image, time_type="in"):
        """
        Mark attendance.
        
        Args:
            image: OpenCV image (BGR format)
            time_type: "in" or "out"
        
        Returns:
            (success, name, confidence): Tuple
        """
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
