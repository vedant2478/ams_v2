import cv2
import numpy as np
from deepface import DeepFace
from datetime import datetime


# ============================================================
# FaceAttendanceSystem Class (DeepFace Version with Face Box)
# ============================================================
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
        self.attendance_log = []  # [{name, timestamp, distance}, ...]
        
        print(f"✅ FaceAttendanceSystem initialized")
        print(f"   Library: DeepFace")
        print(f"   Model: {model_name}")
        print(f"   Distance Metric: {distance_metric}")
        print(f"   Tolerance: {tolerance}")
        print(f"   Storage: In-memory")
    
    
    def _generate_encoding(self, image):
        """
        Generate face embedding from image using DeepFace.
        
        Args:
            image: OpenCV image (BGR) or path to image file
        
        Returns:
            encoding: Numpy array embedding or None if no face detected
        """
        try:
            # Load image if path is provided
            if isinstance(image, str):
                image = cv2.imread(image)
                if image is None:
                    print(f"❌ Could not load image")
                    return None
            
            # DeepFace.represent returns embeddings
            result = DeepFace.represent(
                img_path=image,
                model_name=self.model_name,
                enforce_detection=True,
                detector_backend="opencv",
                align=True
            )
            
            if len(result) == 0:
                print(f"⚠ No face detected")
                return None
            
            # Return first face embedding as numpy array
            embedding = np.array(result[0]["embedding"])
            return embedding
        
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    
    def _calculate_distance(self, embedding1, embedding2):
        """
        Calculate distance between two embeddings.
        
        Args:
            embedding1, embedding2: Numpy arrays
        
        Returns:
            distance: Float distance value
        """
        if self.distance_metric == "cosine":
            # Cosine distance
            return 1 - np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
        elif self.distance_metric == "euclidean":
            # Euclidean distance
            return np.linalg.norm(embedding1 - embedding2)
        elif self.distance_metric == "euclidean_l2":
            # Euclidean L2 distance
            return np.linalg.norm(embedding1 - embedding2) / np.sqrt(np.sum(embedding1**2) + np.sum(embedding2**2))
        else:
            # Default to cosine
            return 1 - np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
    
    
    def register_user(self, name, image_or_path):
        """
        Register a new user.
        
        Args:
            name: User's name
            image_or_path: OpenCV image (BGR) or image file path
        
        Returns:
            success: True if registered, False otherwise
        """
        print(f"\n📝 [REGISTER] Registering: {name}")
        
        # Generate encoding
        encoding = self._generate_encoding(image_or_path)
        
        if encoding is None:
            print(f"❌ Registration failed")
            return False
        
        # Store encoding
        if name not in self.users:
            self.users[name] = []
        
        self.users[name].append(encoding)
        
        print(f"✅ Registered: {name}")
        print(f"   Total encodings for {name}: {len(self.users[name])}")
        
        return True
    
    
    def recognize_user(self, image_or_path):
        """
        Recognize user from image.
        
        Args:
            image_or_path: OpenCV image (BGR) or image file path
        
        Returns:
            (name, distance): Recognized name and distance
            Returns ("Unknown", 1.0) if not recognized
        """
        print(f"\n🔍 [RECOGNIZE] Analyzing image...")
        
        # Generate query encoding
        query_encoding = self._generate_encoding(image_or_path)
        
        if query_encoding is None:
            print(f"❌ No face detected")
            return "Unknown", 1.0
        
        if len(self.users) == 0:
            print(f"⚠ No registered users")
            return "Unknown", 1.0
        
        # Compare with all stored encodings
        best_name = "Unknown"
        best_distance = float('inf')
        
        for name, encodings_list in self.users.items():
            for encoding in encodings_list:
                distance = self._calculate_distance(query_encoding, encoding)
                
                if distance < best_distance:
                    best_distance = distance
                    best_name = name
        
        # Apply tolerance threshold
        if best_distance <= self.tolerance:
            print(f"✅ Recognized: {best_name} (distance: {best_distance:.3f})")
            return best_name, best_distance
        else:
            print(f"❌ Unknown (closest: {best_name} at {best_distance:.3f})")
            return "Unknown", best_distance
    
    
    def mark_attendance(self, image_or_path):
        """
        Mark attendance by recognizing user and logging.
        
        Args:
            image_or_path: OpenCV image (BGR) or image file path
        
        Returns:
            success: True if attendance marked, False otherwise
        """
        print(f"\n📋 [ATTENDANCE] Marking attendance...")
        
        # Recognize user
        name, distance = self.recognize_user(image_or_path)
        
        if name == "Unknown":
            print(f"❌ Attendance not marked: Unknown person")
            return False
        
        # Log attendance
        record = {
            "name": name,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "distance": round(distance, 3)
        }
        
        self.attendance_log.append(record)
        
        print(f"✅ Attendance marked for: {name}")
        print(f"   Timestamp: {record['timestamp']}")
        
        return True
    
    
    def get_user_list(self):
        """Get list of all registered users."""
        return list(self.users.keys())
    
    
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
    
    
    def print_stats(self):
        """Print system statistics."""
        print(f"\n📊 System Statistics")
        print(f"   Registered users: {len(self.users)}")
        print(f"   Attendance records: {len(self.attendance_log)}")
        if self.users:
            print(f"   Users: {', '.join(self.users.keys())}")



# ============================================================
# Helper Function: Check if face is inside box
# ============================================================
def is_face_in_box(frame, box_coords):
    """
    Detect if a face is inside the specified box.
    
    Args:
        frame: Current camera frame
        box_coords: Tuple (x1, y1, x2, y2) of the box
    
    Returns:
        (is_inside, face_roi): Boolean and cropped face region
    """
    x1, y1, x2, y2 = box_coords
    
    try:
        # Use OpenCV face detector for real-time detection
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        for (fx, fy, fw, fh) in faces:
            face_center_x = fx + fw // 2
            face_center_y = fy + fh // 2
            
            # Check if face center is inside the box
            if x1 < face_center_x < x2 and y1 < face_center_y < y2:
                # Return the face ROI from the box area
                face_roi = frame[y1:y2, x1:x2]
                return True, face_roi
        
        return False, None
    
    except Exception as e:
        return False, None



# ============================================================
# Windows Application with Static Face Box
# ============================================================
def main():
    # Initialize system
    system = FaceAttendanceSystem(
        model_name="Facenet512",
        distance_metric="cosine",
        tolerance=0.4
    )
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Cannot open camera")
        return
    
    # Get frame dimensions
    ret, frame = cap.read()
    if not ret:
        print("❌ Cannot read from camera")
        return
    
    height, width = frame.shape[:2]
    
    # Define static box in center (square shape)
    box_size = min(width, height) // 2
    x1 = (width - box_size) // 2
    y1 = (height - box_size) // 2
    x2 = x1 + box_size
    y2 = y1 + box_size
    box_coords = (x1, y1, x2, y2)
    
    print("\n" + "="*60)
    print("FACE ATTENDANCE SYSTEM - DeepFace with Face Box")
    print("="*60)
    print("\nControls:")
    print("  R - Register new user (face must be in box)")
    print("  A - Mark attendance (face must be in box)")
    print("  L - View user list")
    print("  H - View attendance log")
    print("  S - Show statistics")
    print("  Q - Quit")
    print("="*60)
    print("\n⬜ Position your face inside the GREEN box")
    print("   Box will turn RED when face detected inside")
    
    # Mode flags
    register_mode = False
    attendance_mode = False
    name_to_register = None
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame")
            break
        
        # Check if face is in box
        face_in_box, face_roi = is_face_in_box(frame, box_coords)
        
        # Draw box (GREEN if no face, RED if face detected)
        box_color = (0, 0, 255) if face_in_box else (0, 255, 0)
        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)
        
        # Draw instructions
        status_text = "FACE DETECTED - Ready!" if face_in_box else "Position face in box"
        cv2.putText(frame, status_text, (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)
        
        # Auto-process when face is in box
        if face_in_box and face_roi is not None:
            if register_mode and name_to_register:
                cv2.putText(frame, f"Registering {name_to_register}...", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                success = system.register_user(name_to_register, face_roi)
                register_mode = False
                name_to_register = None
            
            elif attendance_mode:
                cv2.putText(frame, "Marking Attendance...", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                system.mark_attendance(face_roi)
                attendance_mode = False
        
        # Display mode indicators
        if register_mode:
            cv2.putText(frame, "MODE: REGISTER (waiting for face)", (10, height - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        elif attendance_mode:
            cv2.putText(frame, "MODE: ATTENDANCE (waiting for face)", (10, height - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 165, 255), 2)
        
        # Display frame
        cv2.imshow("Face Attendance System", frame)
        
        key = cv2.waitKey(1) & 0xFF
        
        # Register user
        if key == ord('r'):
            name = input("\nEnter name to register: ").strip()
            if name:
                register_mode = True
                name_to_register = name
                print(f"📸 Registration mode activated. Position face in box...")
        
        # Mark attendance
        elif key == ord('a'):
            attendance_mode = True
            print(f"📸 Attendance mode activated. Position face in box...")
        
        # View user list
        elif key == ord('l'):
            print("\n" + "="*60)
            print("REGISTERED USERS")
            print("="*60)
            users = system.get_user_list()
            if users:
                for i, name in enumerate(users, 1):
                    print(f"{i}. {name}")
            else:
                print("No users registered yet")
        
        # View attendance log
        elif key == ord('h'):
            print("\n" + "="*60)
            print("ATTENDANCE LOG (Last 10)")
            print("="*60)
            log = system.get_attendance_log(limit=10)
            if log:
                for record in log:
                    print(f"{record['name']} - {record['timestamp']} (dist: {record['distance']})")
            else:
                print("No attendance records yet")
        
        # Show statistics
        elif key == ord('s'):
            system.print_stats()
        
        # Quit
        elif key == ord('q'):
            print("\n👋 Goodbye!")
            break
    
    cap.release()
    cv2.destroyAllWindows()



# ============================================================
# Run Application
# ============================================================
if __name__ == "__main__":
    main()
