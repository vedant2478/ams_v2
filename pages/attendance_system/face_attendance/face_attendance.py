from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.properties import StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from datetime import datetime
import cv2
import numpy as np

# Import the generalized face recognition system
from face_recognition_system import FaceRecognitionSystem


class KivyCamera(Image):
    """Custom camera widget using OpenCV for live camera feed"""
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        
    def start(self, camera_index=1):
        """Start the camera capture"""
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """Update camera frame"""
        if self.capture and self.capture.isOpened():
            if self.capture.grab():
                ret, frame = self.capture.retrieve()
                
                if ret and frame is not None:
                    # Store current frame for face recognition
                    self.current_frame = frame.copy()
                    
                    # ROTATE 180 DEGREES
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                    
                    h, w = frame.shape[:2]
                    buf = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes()
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


class RegistrationPopup(Popup):
    """Popup for user registration"""
    
    def __init__(self, face_system, registered_faces, camera_widget, **kwargs):
        super(RegistrationPopup, self).__init__(**kwargs)
        self.face_system = face_system
        self.registered_faces = registered_faces
        self.camera_widget = camera_widget
        
        self.sample_count = 0
        self.target_samples = 5
        self.username = None
        self.samples = []
        
        self.title = "Register New User"
        self.size_hint = (0.8, 0.5)
        self.auto_dismiss = False
        
        # Layout
        layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Instructions
        self.instruction_label = Label(
            text="Step 1: Enter your name",
            size_hint_y=0.3,
            color=(0.9, 0.95, 1, 1)
        )
        layout.add_widget(self.instruction_label)
        
        # Name input
        self.name_input = TextInput(
            hint_text="Enter your name",
            multiline=False,
            size_hint_y=0.2
        )
        layout.add_widget(self.name_input)
        
        # Status label
        self.status_label = Label(
            text="",
            size_hint_y=0.2,
            color=(0.9, 0.95, 1, 1)
        )
        layout.add_widget(self.status_label)
        
        # Buttons
        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)
        
        self.capture_btn = Button(
            text="Capture Face",
            disabled=True,
            background_normal='',
            background_color=(0.18, 0.35, 0.50, 0.85)
        )
        self.capture_btn.bind(on_release=self.on_capture)
        btn_layout.add_widget(self.capture_btn)
        
        cancel_btn = Button(
            text="Cancel",
            background_normal='',
            background_color=(0.5, 0.2, 0.2, 0.85)
        )
        cancel_btn.bind(on_release=self.dismiss)
        btn_layout.add_widget(cancel_btn)
        
        layout.add_widget(btn_layout)
        
        self.content = layout
        
        # Bind name input
        self.name_input.bind(text=self.on_name_change)
    
    def on_name_change(self, instance, value):
        """Enable capture button when name is entered"""
        if value.strip():
            self.capture_btn.disabled = False
            self.username = value.strip()
            self.instruction_label.text = f"Step 2: Look at camera and click 'Capture Face' ({self.target_samples} times)"
        else:
            self.capture_btn.disabled = True
    
    def on_capture(self, instance):
        """Handle capture button press"""
        if not self.username:
            return
        
        # Get current frame from camera
        frame = self.camera_widget.get_current_frame()
        
        if frame is None:
            self.status_label.text = "❌ No camera frame available!"
            return
        
        # Register face from frame
        result = self.face_system.register_face_from_frame(frame, self.username)
        
        if result['success']:
            self.samples.append(result['embedding'])
            self.sample_count += 1
            self.status_label.text = f"✅ Sample {self.sample_count}/{self.target_samples} captured!"
            
            if self.sample_count >= self.target_samples:
                # Average all samples
                avg_embedding = np.mean(self.samples, axis=0)
                self.registered_faces[self.username] = avg_embedding
                
                self.status_label.text = f"✅ {self.username} registered successfully!"
                print(f"✓ {self.username} added to system")
                Clock.schedule_once(lambda dt: self.dismiss(), 1.5)
        else:
            self.status_label.text = f"❌ {result['message']}"


class FaceAttendanceScreen(Screen):
    """Main attendance screen with face recognition"""
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    processing = BooleanProperty(False)
    registration_mode = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super(FaceAttendanceScreen, self).__init__(**kwargs)
        
        # Initialize face recognition system
        self.face_system = FaceRecognitionSystem()
        
        # Store data in variables (no database)
        self.registered_faces = {}  # {name: embedding}
        self.attendance_log = []    # [(name, timestamp, score, time_type), ...]
        self.last_recognized = {}   # {name: datetime}
        self.threshold = 180
    
    def on_enter(self):
        """Called when screen is entered"""
        print(f"Loaded {len(self.registered_faces)} registered faces")
        
        Clock.schedule_once(self.setup_camera, 0.5)
        # Start auto-recognition every 2 seconds
        Clock.schedule_interval(self.auto_recognize, 2.0)
    
    def setup_camera(self, dt):
        """Setup and start camera feed"""
        try:
            self.ids.camera_feed.start(camera_index=1)
        except Exception as e:
            print(f"Camera setup error: {e}")
    
    def auto_recognize(self, dt):
        """Automatically recognize faces and mark attendance"""
        if self.processing or self.registration_mode:
            return
        
        if len(self.registered_faces) == 0:
            return
        
        try:
            # Get current frame from camera
            frame = self.ids.camera_feed.get_current_frame()
            
            if frame is None:
                return
            
            self.processing = True
            
            # Recognize faces in frame
            results = self.face_system.detect_and_recognize_faces(
                frame, self.registered_faces, threshold=self.threshold
            )
            
            # Process recognition results
            for result in results:
                name = result['name']
                score = result['score']
                
                if name != "Unknown" and score < self.threshold:
                    # Check cooldown (60 seconds between same person)
                    current_time = datetime.now()
                    
                    if name not in self.last_recognized or \
                       (current_time - self.last_recognized[name]).seconds > 60:
                        
                        # Log attendance to variable
                        timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
                        self.attendance_log.append((name, timestamp, score, self.current_time_type))
                        
                        # Update UI
                        self.update_welcome_message(name)
                        print(f"✓ {self.current_time_type.upper()} marked: {name} | {timestamp} | Score: {score:.0f}")
                        
                        self.last_recognized[name] = current_time
            
            self.processing = False
        
        except Exception as e:
            print(f"Auto-recognition error: {e}")
            self.processing = False
    
    def show_registration_popup(self):
        """Show registration popup"""
        self.registration_mode = True
        self.registration_popup = RegistrationPopup(
            face_system=self.face_system,
            registered_faces=self.registered_faces,
            camera_widget=self.ids.camera_feed
        )
        self.registration_popup.bind(on_dismiss=self.on_registration_dismiss)
        self.registration_popup.open()
    
    def on_registration_dismiss(self, instance):
        """Called when registration popup is dismissed"""
        self.registration_mode = False
        print(f"Total registered users: {len(self.registered_faces)}")
    
    def on_time_type_change(self, time_type):
        """Handle toggle button change"""
        self.current_time_type = time_type
        print(f"Time type changed to: {time_type.upper()}")
    
    def update_welcome_message(self, username):
        """Update welcome message"""
        self.current_user = username
        self.ids.welcome_label.text = f'"{username}" --> Welcome'
    
    def get_user_list(self):
        """Get list of registered users"""
        return list(self.registered_faces.keys())
    
    def get_attendance_log(self, limit=10):
        """Get recent attendance log"""
        return self.attendance_log[-limit:]
    
    def go_back(self):
        """Navigate back to previous screen"""
        Clock.unschedule(self.auto_recognize)
        try:
            self.ids.camera_feed.stop()
        except:
            pass
        
        print(f"\n=== Session Summary ===")
        print(f"Registered Users: {len(self.registered_faces)}")
        print(f"Attendance Records: {len(self.attendance_log)}")
        print("Going back...")
        
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        """Called when screen is left - cleanup"""
        Clock.unschedule(self.auto_recognize)
        try:
            self.ids.camera_feed.stop()
        except:
            pass
