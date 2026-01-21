from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, NumericProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from datetime import datetime
import cv2
import numpy as np


# Import the face recognition system
from face_recognition_system import FaceRecognitionSystem



class KivyCamera(Image):
    """Custom camera widget using OpenCV for live camera feed"""
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.show_bbox = True  # Flag to show/hide bounding box
        
    def start(self, camera_index=1):
        """Start the camera capture"""
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            # Optimized settings for smoother frames
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce buffer for less latency
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """Update camera frame with face detection"""
        if self.capture and self.capture.isOpened():
            # Use grab() and retrieve() for faster capture
            if self.capture.grab():
                ret, frame = self.capture.retrieve()
                
                if ret and frame is not None:
                    # Store current frame for face recognition
                    self.current_frame = frame.copy()
                    
                    # ROTATE 180 for correct orientation
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                    
                    # Detect faces and draw bounding boxes
                    if self.show_bbox:
                        frame = self.draw_face_boxes(frame)
                    
                    # Convert to RGB for display
                    h, w = frame.shape[:2]
                    buf = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 0).tobytes()
                    texture = Texture.create(size=(w, h), colorfmt='rgb')
                    texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                    self.texture = texture
    
    def draw_face_boxes(self, frame):
        """Draw bounding boxes around detected faces"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(100, 100)
        )
        
        # Draw rectangles around faces
        for (x, y, w, h) in faces:
            # Green box for detected face
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
            
            # Add label "Face Detected"
            cv2.putText(
                frame,
                'Face Detected',
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2
            )
            
            # Optional: Draw center crosshair
            center_x = x + w // 2
            center_y = y + h // 2
            cv2.circle(frame, (center_x, center_y), 5, (0, 255, 0), -1)
        
        # If no face detected, show message
        if len(faces) == 0:
            cv2.putText(
                frame,
                'No Face Detected',
                (frame.shape[1]//2 - 100, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 0, 255),
                2
            )
        
        return frame
    
    def get_current_frame(self):
        """Get the current frame"""
        return self.current_frame
    
    def stop(self):
        """Stop the camera capture"""
        Clock.unschedule(self.update)
        if self.capture:
            self.capture.release()
            self.capture = None
        print("Camera stopped")



class RegisterUserScreen(Screen):
    """Screen for registering new users with face recognition"""
    
    username = StringProperty("")
    sample_count = NumericProperty(0)
    target_samples = NumericProperty(5)
    status_message = StringProperty("Enter name and capture face")
    
    def __init__(self, **kwargs):
        super(RegisterUserScreen, self).__init__(**kwargs)
        self.name = 'register_user'
        
        # Initialize face recognition system
        self.face_system = FaceRecognitionSystem()
        
        # Store samples temporarily
        self.samples = []
        
        # Reference to main app's registered faces
        self.registered_faces = None
    
    def on_enter(self):
        """Called when screen is entered"""
        # Reset state
        self.username = ""
        self.sample_count = 0
        self.samples = []
        self.status_message = "Enter name and capture face"
        
        # Clear text input
        if hasattr(self, 'ids') and 'name_input' in self.ids:
            self.ids.name_input.text = ""
        
        # Get reference to registered faces from face attendance screen
        if self.manager.has_screen('face_attendance'):
            face_screen = self.manager.get_screen('face_attendance')
            self.registered_faces = face_screen.registered_faces
        
        # Start camera
        Clock.schedule_once(self.setup_camera, 0.5)
    
    def setup_camera(self, dt):
        """Setup and start camera feed"""
        try:
            self.ids.camera_feed.start(camera_index=1)
        except Exception as e:
            print(f"Camera setup error: {e}")
            self.status_message = f"❌ Camera error: {e}"
    
    def on_key_press(self, key):
        """Handle keyboard key press"""
        if key == '⌫':
            # Backspace - remove last character
            if self.username:
                self.username = self.username[:-1]
                self.ids.name_input.text = self.username
        else:
            # Add character
            self.username += key
            self.ids.name_input.text = self.username
        
        # Update capture button state
        self.on_text_change()
    
    def on_text_change(self):
        """Handle text input changes"""
        self.username = self.ids.name_input.text.strip()
        
        # Update capture button state
        if self.username:
            self.ids.capture_btn.disabled = False
            self.status_message = f"Ready! Click Capture ({self.sample_count}/{self.target_samples})"
        else:
            self.ids.capture_btn.disabled = True
            self.status_message = "Enter name and capture face"
    
    def clear_text(self):
        """Clear all text"""
        self.username = ""
        self.ids.name_input.text = ""
        self.on_text_change()
    
    def on_capture(self):
        """Handle capture button press"""
        if not self.username:
            self.status_message = "⚠️ Please enter a name first!"
            return          
        
        # Get current frame from camera
        frame = self.ids.camera_feed.get_current_frame()
        
        if frame is None:
            self.status_message = "❌ No camera frame available!"
            return
        
        # Register face from frame
        result = self.face_system.register_face_from_frame(frame, self.username)
        
        if result['success']:
            self.samples.append(result['embedding'])
            self.sample_count += 1
            self.status_message = f"✅ Sample {self.sample_count}/{self.target_samples} captured!"
            
            if self.sample_count >= self.target_samples:
                # Average all samples
                avg_embedding = np.mean(self.samples, axis=0)
                
                if self.registered_faces is not None:
                    self.registered_faces[self.username] = avg_embedding
                
                self.status_message = f"✅ {self.username} registered successfully!"
                print(f"✓ {self.username} added to system")
                
                # Go back after 2 seconds
                Clock.schedule_once(lambda dt: self.go_back(), 2.0)
        else:
            self.status_message = f"❌ {result['message']}"
    
    def go_back(self):
        """Navigate back to attendance type screen"""
        try:
            self.ids.camera_feed.stop()
        except:
            pass
        
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        """Called when screen is left - cleanup"""
        try:
            self.ids.camera_feed.stop()
        except:
            pass
