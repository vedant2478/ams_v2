from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.uix.vkeyboard import VKeyboard
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
        
    def start(self, camera_index=0):
        """Start the camera capture"""
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """Update camera frame"""
        if self.capture and self.capture.isOpened():
            ret, frame = self.capture.read()
            
            if ret and frame is not None:
                # Store current frame for face recognition
                self.current_frame = frame.copy()
                
                # Convert to RGB for display
                h, w = frame.shape[:2]
                buf = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 0).tobytes()
                texture = Texture.create(size=(w, h), colorfmt='rgb')
                texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                self.texture = texture
    
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
    
    def on_text_change(self, instance, value):
        """Handle text input changes"""
        self.username = value.strip()
        
        # Update capture button state
        if self.username:
            self.ids.capture_btn.disabled = False
        else:
            self.ids.capture_btn.disabled = True
    
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
