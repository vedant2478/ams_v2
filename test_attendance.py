"""
Standalone Face Recognition Demo using OpenCV LBPH
Works on Windows with webcam
No external dependencies except OpenCV
"""

import cv2
import numpy as np
from datetime import datetime
import os


class SimpleFaceRecognition:
    """Simple face recognition system using OpenCV LBPH"""
    
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.face_recognizer = cv2.face.LBPHFaceRecognizer_create()
        
        self.users = {}  # {name: user_id}
        self.user_id_counter = 0
        self.face_samples = []
        self.face_labels = []
        self.is_trained = False
        
        print("✅ Face Recognition System Initialized")
    
    def detect_face(self, frame):
        """Detect face in frame and return face ROI"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
        
        if len(faces) == 0:
            return None, None
        
        # Get largest face
        (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
        face_roi = gray[y:y+h, x:x+w]
        face_roi = cv2.resize(face_roi, (200, 200))
        
        return face_roi, (x, y, w, h)
    
    def register_user(self, name, frame):
        """Register a new user"""
        face_roi, coords = self.detect_face(frame)
        
        if face_roi is None:
            return False, "No face detected"
        
        # Assign user ID
        if name not in self.users:
            self.users[name] = self.user_id_counter
            self.user_id_counter += 1
        
        user_id = self.users[name]
        
        # Add face sample
        self.face_samples.append(face_roi)
        self.face_labels.append(user_id)
        
        # Train recognizer
        self.face_recognizer.train(self.face_samples, np.array(self.face_labels))
        self.is_trained = True
        
        sample_count = self.face_labels.count(user_id)
        return True, f"Registered! Total samples: {sample_count}"
    
    def recognize_user(self, frame):
        """Recognize user from frame"""
        if not self.is_trained:
            return "No users", 0, None
        
        face_roi, coords = self.detect_face(frame)
        
        if face_roi is None:
            return "No face", 0, None
        
        # Predict
        label, distance = self.face_recognizer.predict(face_roi)
        
        # Find name
        name = "Unknown"
        for user_name, user_id in self.users.items():
            if user_id == label:
                name = user_name
                break
        
        # Calculate confidence
        confidence = max(0, 100 - distance)
        
        # Threshold
        if distance > 50:  # Adjustable threshold
            name = "Unknown"
            confidence = 0
        
        return name, confidence, coords


def main():
    """Main demo application"""
    
    # Initialize system
    recognizer = SimpleFaceRecognition()
    
    # Open webcam
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ Cannot open webcam")
        return
    
    print("\n" + "="*60)
    print("FACE RECOGNITION DEMO - OpenCV LBPH")
    print("="*60)
    print("\nControls:")
    print("  R - Start registration mode")
    print("  SPACE - Capture face for registration")
    print("  A - Toggle auto-recognition")
    print("  L - List registered users")
    print("  C - Clear all users")
    print("  Q - Quit")
    print("="*60 + "\n")
    
    # Mode flags
    registration_mode = False
    auto_recognize = True
    name_to_register = None
    capture_count = 0
    target_captures = 5  # Capture 5 samples per user
    
    while True:
        ret, frame = cap.read()
        if not ret:
            print("❌ Failed to grab frame")
            break
        
        display_frame = frame.copy()
        
        # Auto-recognition mode
        if auto_recognize and not registration_mode:
            name, confidence, coords = recognizer.recognize_user(frame)
            
            if coords is not None:
                x, y, w, h = coords
                
                # Draw rectangle and text
                if name != "Unknown" and name != "No face":
                    color = (0, 255, 0)  # Green for recognized
                    label = f"{name} ({confidence:.0f}%)"
                else:
                    color = (0, 0, 255)  # Red for unknown
                    label = "Unknown"
                
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), color, 2)
                cv2.putText(display_frame, label, (x, y-10),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        
        # Registration mode
        elif registration_mode and name_to_register:
            face_roi, coords = recognizer.detect_face(frame)
            
            if coords is not None:
                x, y, w, h = coords
                cv2.rectangle(display_frame, (x, y), (x+w, y+h), (0, 255, 255), 2)
                
                text = f"Registering: {name_to_register}"
                cv2.putText(display_frame, text, (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                
                text2 = f"Samples: {capture_count}/{target_captures} (Press SPACE)"
                cv2.putText(display_frame, text2, (10, 60),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        # Status bar
        status = "AUTO-RECOGNITION ON" if auto_recognize else "AUTO-RECOGNITION OFF"
        if registration_mode:
            status = "REGISTRATION MODE"
        
        cv2.putText(display_frame, status, (10, display_frame.shape[0] - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Display
        cv2.imshow("Face Recognition Demo", display_frame)
        
        # Handle keys
        key = cv2.waitKey(1) & 0xFF
        
        # Start registration
        if key == ord('r'):
            name = input("\n📝 Enter name to register: ").strip()
            if name:
                registration_mode = True
                name_to_register = name
                capture_count = 0
                auto_recognize = False
                print(f"✅ Registration mode activated for: {name}")
                print(f"Position your face and press SPACE to capture {target_captures} samples")
        
        # Capture face sample
        elif key == ord(' ') and registration_mode and name_to_register:
            success, message = recognizer.register_user(name_to_register, frame)
            if success:
                capture_count += 1
                print(f"✅ Sample {capture_count} captured - {message}")
                
                if capture_count >= target_captures:
                    print(f"✅ {name_to_register} registered successfully!")
                    registration_mode = False
                    name_to_register = None
                    auto_recognize = True
            else:
                print(f"❌ {message}")
        
        # Toggle auto-recognition
        elif key == ord('a'):
            if not registration_mode:
                auto_recognize = not auto_recognize
                status = "ON" if auto_recognize else "OFF"
                print(f"🔄 Auto-recognition: {status}")
        
        # List users
        elif key == ord('l'):
            print("\n" + "="*60)
            print("REGISTERED USERS")
            print("="*60)
            users = recognizer.users.keys()
            if users:
                for i, name in enumerate(users, 1):
                    sample_count = recognizer.face_labels.count(recognizer.users[name])
                    print(f"{i}. {name} ({sample_count} samples)")
            else:
                print("No users registered yet")
            print("="*60 + "\n")
        
        # Clear all users
        elif key == ord('c'):
            confirm = input("\n⚠️  Clear all users? (yes/no): ").strip().lower()
            if confirm == 'yes':
                recognizer.users = {}
                recognizer.user_id_counter = 0
                recognizer.face_samples = []
                recognizer.face_labels = []
                recognizer.is_trained = False
                print("✅ All users cleared")
            else:
                print("❌ Cancelled")
        
        # Quit
        elif key == ord('q'):
            print("\n👋 Goodbye!")
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Interrupted by user. Goodbye!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
