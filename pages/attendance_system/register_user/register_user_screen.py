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
import time

# Import the face recognition system
from face_recognition_system import FaceRecognitionSystem

# Import database manager
from database.db_manager import DatabaseManager


class KivyCamera(Image):
    """Optimized camera widget with multithreading and safe cleanup"""
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        self.stopped = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.show_bbox = True
        self.thread = None
        self.frame_skip = 2
        self.frame_count = 0
        self.last_faces = []
        self.camera_ready = False
        
    def start(self, camera_index=1):
        """Start camera with background thread - ONLY camera index 1"""
        try:
            print(f"Starting camera with index {camera_index}...")
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"✗ ERROR: Could not open camera at index {camera_index}")
                return
            
            # Test if we can read frames
            ret, test_frame = self.capture.read()
            if not ret or test_frame is None:
                print(f"✗ ERROR: Camera {camera_index} opened but cannot read frames")
                self.capture.release()
                return
            
            print(f"✓ Camera {camera_index} opened successfully")
            
            # Optimized camera settings
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            try:
                self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            except:
                print("MJPEG codec not available, using default")
            
            # Verify settings
            actual_width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"Camera resolution: {int(actual_width)}x{int(actual_height)}")
            
            # Start background capture thread
            self.stopped = False
            self.thread = Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            # Schedule UI updates
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            self.camera_ready = True
            print(f"✓ Camera started successfully with multithreading")
            
        except Exception as e:
            print(f"✗ Error starting camera: {e}")
            import traceback
            traceback.print_exc()
    
    def _capture_frames(self):
        """Background thread continuously captures frames"""
        print("Camera capture thread started")
        try:
            while not self.stopped:
                if self.capture and self.capture.isOpened():
                    try:
                        ret, frame = self.capture.read()
                        if ret and frame is not None:
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
                        else:
                            time.sleep(0.01)
                    except Exception as e:
                        print(f"Frame capture error: {e}")
                        time.sleep(0.1)
                else:
                    break
        except Exception as e:
            print(f"Camera thread exception: {e}")
        finally:
            print("Camera capture thread stopped")
    
    def update(self, dt):
        """Update camera frame display"""
        try:
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
            pass
        except Exception as e:
            print(f"Display update error: {e}")
    
    def draw_face_boxes(self, frame):
        """Draw bounding boxes around detected faces with optimization"""
        self.frame_count += 1
        
        # Process face detection only every Nth frame
        if self.frame_count % self.frame_skip == 0:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.equalizeHist(gray)
            
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.2,
                minNeighbors=4,
                minSize=(80, 80),
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            self.last_faces = faces
        else:
            faces = self.last_faces
        
        # Draw rectangles around detected faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, 'Face Detected', (x, y - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            
            center_x = x + w // 2
            center_y = y + h // 2
            cv2.circle(frame, (center_x, center_y), 5, (0, 255, 0), -1)
        
        if len(faces) == 0:
            cv2.putText(frame, 'No Face Detected', (frame.shape[1]//2 - 100, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        return frame
    
    def get_current_frame(self):
        """Get the current frame for face registration"""
        if self.current_frame is not None:
            return self.current_frame.copy()
        return None
    
    def stop(self):
        """Stop camera and thread safely"""
        print("Stopping camera...")
        
        # Unschedule UI updates
        try:
            Clock.unschedule(self.update)
        except:
            pass
        
        # Signal thread to stop
        self.stopped = True
        self.camera_ready = False
        
        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            print("Waiting for camera thread to finish...")
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                print("Warning: Camera thread did not stop gracefully")
        
        # Clear the queue
        try:
            while not self.frame_queue.empty():
                self.frame_queue.get_nowait()
        except:
            pass
        
        # Release camera
        if self.capture:
            try:
                self.capture.release()
            except Exception as e:
                print(f"Camera release error: {e}")
            self.capture = None
        
        # Clear current frame
        self.current_frame = None
        
        print("Camera stopped successfully")


class RegisterUserScreen(Screen):
    """Optimized screen for registering new users with face recognition and database storage"""
    
    username = StringProperty("")
    sample_count = NumericProperty(0)
    target_samples = NumericProperty(5)
    status_message = StringProperty("Enter name and capture face")
    
    def __init__(self, **kwargs):
        super(RegisterUserScreen, self).__init__(**kwargs)
        self.name = 'register_user'
        
        # Initialize face recognition system
        self.face_system = FaceRecognitionSystem()
        
        # Initialize database manager
        self.db = DatabaseManager('sqlite:///csi_attendance.dev.sqlite')
        
        # Store samples temporarily
        self.samples = []
        
        # Scheduled events
        self._capture_scheduled = None
        self._is_processing = False
    
    def on_enter(self):
        """Called when screen is entered"""
        print("RegisterUserScreen: Entering...")
        
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
        
        # Delayed camera start for smoother transition
        if self._capture_scheduled:
            try:
                self._capture_scheduled.cancel()
            except:
                pass
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
            if self.username:
                self.username = self.username[:-1]
                if hasattr(self, 'ids') and 'name_input' in self.ids:
                    self.ids.name_input.text = self.username
        else:
            self.username += key
            if hasattr(self, 'ids') and 'name_input' in self.ids:
                self.ids.name_input.text = self.username
        
        self.on_text_change()
    
    def on_text_change(self):
        """Handle text input changes"""
        if hasattr(self, 'ids') and 'name_input' in self.ids:
            self.username = self.ids.name_input.text.strip()
            
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
        if self._is_processing:
            return
        
        if not self.username:
            self.status_message = "⚠️ Please enter a name first!"
            return
        
        self._is_processing = True
        if hasattr(self, 'ids') and 'capture_btn' in self.ids:
            self.ids.capture_btn.disabled = True
        
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
        
        Clock.schedule_once(lambda dt: self._process_capture(frame), 0)
    
    def _process_capture(self, frame):
        """Process face capture without blocking UI thread"""
        try:
            result = self.face_system.register_face_from_frame(frame, self.username)
            
            if result['success']:
                self.samples.append(result['embedding'])
                self.sample_count += 1
                self.status_message = f"✅ Sample {self.sample_count}/{self.target_samples} captured!"
                
                if self.sample_count >= self.target_samples:
                    # Average all samples for better accuracy
                    avg_embedding = np.mean(self.samples, axis=0)
                    
                    # Save to database
                    db_result = self.db.create_user(
                        name=self.username,
                        embedding=avg_embedding
                    )
                    
                    if db_result['success']:
                        self.status_message = f"✅ {self.username} registered successfully!"
                        print(f"✓ {self.username} saved to database (ID: {db_result['user_id']})")
                        
                        # Update face attendance screen's embeddings
                        if self.manager.has_screen('face_attendance'):
                            face_screen = self.manager.get_screen('face_attendance')
                            if hasattr(face_screen, 'load_embeddings_from_db'):
                                face_screen.load_embeddings_from_db()
                        
                        Clock.schedule_once(lambda dt: self.go_back(), 1.5)
                    else:
                        self.status_message = f"❌ Database error: {db_result['message']}"
                        self._is_processing = False
                        if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                            self.ids.capture_btn.disabled = False
                else:
                    self._is_processing = False
                    if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                        self.ids.capture_btn.disabled = False
            else:
                self.status_message = f"❌ {result['message']}"
                self._is_processing = False
                if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                    self.ids.capture_btn.disabled = False
        
        except Exception as e:
            print(f"Error processing capture: {e}")
            import traceback
            traceback.print_exc()
            self.status_message = f"❌ Error: {str(e)}"
            self._is_processing = False
            if hasattr(self, 'ids') and 'capture_btn' in self.ids:
                self.ids.capture_btn.disabled = False
    
    def go_back(self):
        """Navigate back to attendance type screen"""
        print("RegisterUserScreen: Going back...")
        
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                self.ids.camera_feed.stop()
                time.sleep(0.2)
        except Exception as e:
            print(f"Error stopping camera: {e}")
        
        if hasattr(self, 'manager') and self.manager:
            self.manager.current = "attendance_type"
    
    def on_leave(self):
        """Called when screen is left - cleanup resources"""
        print("RegisterUserScreen: Cleaning up...")
        
        # Cancel scheduled camera setup
        if self._capture_scheduled:
            try:
                self._capture_scheduled.cancel()
            except:
                pass
            self._capture_scheduled = None
        
        # Stop camera safely
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                camera = self.ids.camera_feed
                if camera:
                    camera.stop()
                    time.sleep(0.1)
        except Exception as e:
            print(f"Error in camera cleanup: {e}")
        
        # Reset processing flag
        self._is_processing = False
        
        print("RegisterUserScreen: Cleanup complete")
