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
from threading import Thread
import queue
import cv2
import numpy as np

# Import the face recognition system
from face_recognition_system import FaceRecognitionSystem


class KivyCamera(Image):
    """Optimized camera widget using OpenCV with multithreading"""
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        self.stopped = False
        self.frame_queue = queue.Queue(maxsize=2)  # Limit buffer to reduce latency
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.show_bbox = True
        self.thread = None
        self.frame_skip = 2  # Process every Nth frame for face detection
        self.frame_count = 0
        self.last_faces = []  # Cache last detected faces
        
    def start(self, camera_index=1):
        """Start the camera capture with background thread"""
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            # Optimized camera settings
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Minimum buffer
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            # Start background capture thread
            self.stopped = False
            self.thread = Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            # Schedule UI updates
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully with multithreading")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def _capture_frames(self):
        """Background thread continuously captures frames"""
        while not self.stopped:
            if self.capture and self.capture.isOpened():
                ret, frame = self.capture.read()
                if ret:
                    # Remove old frame if queue is full
                    if not self.frame_queue.empty():
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                    
                    # Add new frame
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        pass
    
    def update(self, dt):
        """Update camera frame display (runs on main thread)"""
        try:
            # Get latest frame from queue
            frame = self.frame_queue.get_nowait()
            
            # Store for face recognition
            self.current_frame = frame.copy()
            
            # Rotate 180 degrees for correct orientation
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            
            # Draw face boxes (with frame skipping optimization)
            if self.show_bbox:
                frame = self.draw_face_boxes(frame)
            
            # Convert to Kivy texture
            h, w = frame.shape[:2]
            buf = cv2.flip(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 0).tobytes()
            texture = Texture.create(size=(w, h), colorfmt='rgb')
            texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
            self.texture = texture
            
        except queue.Empty:
            # No frame available, skip this update
            pass
    
    def draw_face_boxes(self, frame):
        """Draw bounding boxes around detected faces with optimization"""
        self.frame_count += 1
        
        # Process face detection only every Nth frame
        if self.frame_count % self.frame_skip == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Histogram equalization for better detection
            gray = cv2.equalizeHist(gray)
            
            # Optimized detection parameters
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.2,  # Faster than 1.1
                minNeighbors=4,   # Reduced for speed
                minSize=(80, 80), # Reduced from 100x100
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            self.last_faces = faces
        else:
            # Use cached face positions
            faces = self.last_faces
        
        # Draw rectangles around detected faces
        for (x, y, w, h) in faces:
            # Green box
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            
            # Label
            cv2.putText(
                frame,
                'Face Detected',
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )
            
            # Center point
            center_x = x + w // 2
            center_y = y + h // 2
            cv2.circle(frame, (center_x, center_y), 5, (0, 255, 0), -1)
        
        # Show message if no face detected
        if len(faces) == 0:
            cv2.putText(
                frame,
                'No Face Detected',
                (frame.shape[1]//2 - 100, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )
        
        return frame
    
    def get_current_frame(self):
        """Get the current frame for face registration"""
        return self.current_frame
    
    def stop(self):
        """Stop the camera and background thread"""
        # Unschedule UI updates
        Clock.unschedule(self.update)
        
        # Stop background thread
        self.stopped = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        
        # Release camera
        if self.capture:
            self.capture.release()
            self.capture = None
        
        print("Camera stopped")


class RegisterUserScreen(Screen):
    """Optimized screen for registering new users with face recognition"""
    
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
        
        # Scheduled events
        self._capture_scheduled = None
        self._is_processing = False  # Prevent concurrent captures
    
    def on_enter(self):
        """Called when screen is entered"""
        # Reset state
        self.username = ""
        self.sample_count = 0
        self.samples = []
        self.status_message = "Enter name and capture face"
        self._is_processing = False
        
        # Clear text input
        if hasattr(self, 'ids') and 'name_input' in self.ids:
            self.ids.name_input.text = ""
            self.ids.capture_btn.disabled = True
        
        # Get reference to registered faces from face attendance screen
        if self.manager.has_screen('face_attendance'):
            face_screen = self.manager.get_screen('face_attendance')
            self.registered_faces = face_screen.registered_faces
        
        # Delayed camera start for smoother transition
        if self._capture_scheduled:
            self._capture_scheduled.cancel()
        self._capture_scheduled = Clock.schedule_once(self.setup_camera, 0.1)
    
    def setup_camera(self, dt):
        """Setup and start camera feed"""
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
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
                if hasattr(self, 'ids') and 'name_input' in self.ids:
                    self.ids.name_input.text = self.username
        else:
            # Add character
            self.username += key
            if hasattr(self, 'ids') and 'name_input' in self.ids:
                self.ids.name_input.text = self.username
        
        # Update capture button state
        self.on_text_change()
    
    def on_text_change(self):
        """Handle text input changes"""
        if hasattr(self, 'ids') and 'name_input' in self.ids:
            self.username = self.ids.name_input.text.strip()
            
            # Update capture button state
            if self.username and not self._is_processing:
                self.ids.capture_btn.disabled = False
                self.status_message = f"Ready! Click Capture ({self.sample_count}/{self.target_samples})"
            else:
                self.ids.capture_btn.disabled = True
                if not self._is_processing and not self.username:
                    self.status_message = "Enter name and capture face"
    
    def clear_text(self):
        """Clear all text"""
        self.username = ""
        if hasattr(self, 'ids') and 'name_input' in self.ids:
            self.ids.name_input.text = ""
        self.on_text_change()
    
    def on_capture(self):
        """Handle capture button press with debouncing"""
        # Prevent concurrent captures
        if self._is_processing:
            return
        
        if not self.username:
            self.status_message = "⚠️ Please enter a name first!"
            return
        
        # Set processing flag and disable button
        self._is_processing = True
        if hasattr(self, 'ids') and 'capture_btn' in self.ids:
            self.ids.capture_btn.disabled = True
        
        # Get current frame from camera
        if hasattr(self, 'ids') and 'camera_feed' in self.ids:
            frame = self.ids.camera_feed.get_current_frame()
        else:
            frame = None
        
        if frame is None:
            self.status_message = "❌ No camera frame available!"
            self._is_processing = False
            if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                self.ids.capture_btn.disabled = False
            return
        
        # Process capture asynchronously to avoid UI freeze
        Clock.schedule_once(lambda dt: self._process_capture(frame), 0)
    
    def _process_capture(self, frame):
        """Process face capture without blocking UI thread"""
        try:
            # Register face from frame
            result = self.face_system.register_face_from_frame(frame, self.username)
            
            if result['success']:
                self.samples.append(result['embedding'])
                self.sample_count += 1
                self.status_message = f"✅ Sample {self.sample_count}/{self.target_samples} captured!"
                
                # Check if all samples collected
                if self.sample_count >= self.target_samples:
                    # Average all samples for better accuracy
                    avg_embedding = np.mean(self.samples, axis=0)
                    
                    # Store in registered faces
                    if self.registered_faces is not None:
                        self.registered_faces[self.username] = avg_embedding
                    
                    self.status_message = f"✅ {self.username} registered successfully!"
                    print(f"✓ {self.username} added to system with {self.target_samples} samples")
                    
                    # Navigate back after brief delay
                    Clock.schedule_once(lambda dt: self.go_back(), 1.5)
                else:
                    # Re-enable button for next sample
                    self._is_processing = False
                    if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                        self.ids.capture_btn.disabled = False
            else:
                # Registration failed
                self.status_message = f"❌ {result['message']}"
                self._is_processing = False
                if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                    self.ids.capture_btn.disabled = False
        
        except Exception as e:
            print(f"Error processing capture: {e}")
            self.status_message = f"❌ Error: {str(e)}"
            self._is_processing = False
            if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                self.ids.capture_btn.disabled = False
    
    def go_back(self):
        """Navigate back to attendance type screen"""
        # Stop camera before leaving
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                self.ids.camera_feed.stop()
        except Exception as e:
            print(f"Error stopping camera: {e}")
        
        # Navigate to previous screen
        if hasattr(self, 'manager') and self.manager:
            self.manager.current = "attendance_type"
    
    def on_leave(self):
        """Called when screen is left - cleanup resources"""
        # Cancel scheduled camera setup
        if self._capture_scheduled:
            self._capture_scheduled.cancel()
            self._capture_scheduled = None
        
        # Stop camera
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                self.ids.camera_feed.stop()
        except Exception as e:
            print(f"Error in cleanup: {e}")
        
        # Reset processing flag
        self._is_processing = False
