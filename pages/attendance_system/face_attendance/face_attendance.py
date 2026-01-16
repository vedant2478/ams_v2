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
import cv2

# Import the face recognition system
from attendance import FaceAttendanceSystem
from face_detection_utils import is_face_in_box


class KivyCamera(Image):
    """
    Custom camera widget using OpenCV for live camera feed with face detection
    """
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        self.box_coords = None
        
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
            
            # Read one frame to get dimensions and set box coordinates
            ret, frame = self.capture.read()
            if ret:
                height, width = frame.shape[:2]
                box_size = min(width, height) // 2
                x1 = (width - box_size) // 2
                y1 = (height - box_size) // 2
                x2 = x1 + box_size
                y2 = y1 + box_size
                self.box_coords = (x1, y1, x2, y2)
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """Update camera frame with face detection box"""
        if self.capture and self.capture.isOpened():
            if self.capture.grab():
                ret, frame = self.capture.retrieve()
                
                if ret and frame is not None:
                    # Store current frame for face recognition
                    self.current_frame = frame.copy()
                    
                    # Draw detection box
                    if self.box_coords:
                        x1, y1, x2, y2 = self.box_coords
                        
                        # Check if face is in box
                        face_in_box, _ = is_face_in_box(frame, self.box_coords)
                        
                        # Draw box (GREEN if no face, RED if face detected)
                        box_color = (0, 0, 255) if face_in_box else (0, 255, 0)
                        cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 3)
                        
                        # Draw status text
                        status_text = "FACE DETECTED" if face_in_box else "Position face in box"
                        cv2.putText(frame, status_text, (x1, y1 - 10),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, box_color, 2)
                    
                    # ROTATE 180 DEGREES
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                    
                    h, w = frame.shape[:2]
                    buf = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes()
                    texture = Texture.create(size=(w, h), colorfmt='rgb')
                    texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                    self.texture = texture
    
    def get_face_roi(self):
        """Get the face ROI if face is detected in box"""
        if self.current_frame is not None and self.box_coords:
            face_in_box, face_roi = is_face_in_box(self.current_frame, self.box_coords)
            if face_in_box:
                return face_roi
        return None
    
    def stop(self):
        """Stop the camera capture"""
        Clock.unschedule(self.update)
        if self.capture:
            self.capture.release()
            self.capture = None
        print("Camera stopped")


class RegistrationPopup(Popup):
    """Popup for user registration"""
    
    def __init__(self, callback, **kwargs):
        super(RegistrationPopup, self).__init__(**kwargs)
        self.callback = callback
        self.sample_count = 0
        self.target_samples = 3
        self.username = None
        
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
            self.instruction_label.text = f"Step 2: Position face in box and click 'Capture Face' ({self.target_samples} times)"
        else:
            self.capture_btn.disabled = True
    
    def on_capture(self, instance):
        """Handle capture button press"""
        if self.username:
            success = self.callback(self.username)
            
            if success:
                self.sample_count += 1
                self.status_label.text = f"✅ Sample {self.sample_count}/{self.target_samples} captured!"
                
                if self.sample_count >= self.target_samples:
                    self.status_label.text = f"✅ {self.username} registered successfully!"
                    Clock.schedule_once(lambda dt: self.dismiss(), 1.5)
            else:
                self.status_label.text = "❌ No face detected. Position face in box!"


class FaceAttendanceScreen(Screen):
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    processing = BooleanProperty(False)
    registration_mode = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super(FaceAttendanceScreen, self).__init__(**kwargs)
        
        # Initialize face recognition system
        self.face_system = FaceAttendanceSystem(threshold=0.6)
        self.registration_popup = None
    
    def on_enter(self):
        """Called when screen is entered"""
        Clock.schedule_once(self.setup_camera, 0.5)
        # Start auto-recognition every 3 seconds
        Clock.schedule_interval(self.auto_recognize, 3.0)
    
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
        
        try:
            # Get face ROI from camera
            face_roi = self.ids.camera_feed.get_face_roi()
            
            if face_roi is not None:
                self.processing = True
                
                # Mark attendance using the face_system object
                success, name, confidence = self.face_system.mark_attendance(
                    face_roi, 
                    self.current_time_type
                )
                
                if success:
                    self.update_welcome_message(f"{name} ({confidence:.0f}%)")
                else:
                    self.update_welcome_message("Unknown Person")
                
                self.processing = False
        
        except Exception as e:
            print(f"Auto-recognition error: {e}")
            self.processing = False
    
    def show_registration_popup(self):
        """Show registration popup"""
        self.registration_mode = True
        self.registration_popup = RegistrationPopup(callback=self.register_user_capture)
        self.registration_popup.bind(on_dismiss=self.on_registration_dismiss)
        self.registration_popup.open()
    
    def on_registration_dismiss(self, instance):
        """Called when registration popup is dismissed"""
        self.registration_mode = False
    
    def register_user_capture(self, username):
        """
        Capture face sample for registration
        
        Args:
            username: Name of the user to register
        
        Returns:
            success: True if capture successful
        """
        face_roi = self.ids.camera_feed.get_face_roi()
        
        if face_roi is not None:
            success = self.face_system.register_user(username, face_roi)
            return success
        
        return False
    
    def on_time_type_change(self, time_type):
        """Handle toggle button change"""
        self.current_time_type = time_type
        print(f"Time type changed to: {time_type}")
    
    def update_welcome_message(self, username):
        """Update welcome message"""
        self.current_user = username
        self.ids.welcome_label.text = f'"{username}" --> Welcome'
    
    def get_user_list(self):
        """Get list of registered users"""
        return self.face_system.get_user_list()
    
    def get_attendance_log(self, limit=10):
        """Get recent attendance log"""
        return self.face_system.get_attendance_log(limit=limit)
    
    def go_back(self):
        """Navigate back to previous screen"""
        Clock.unschedule(self.auto_recognize)
        try:
            self.ids.camera_feed.stop()
        except:
            pass
        
        print("Going back")
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        """Called when screen is left - cleanup"""
        Clock.unschedule(self.auto_recognize)
        try:
            self.ids.camera_feed.stop()
        except:
            pass
