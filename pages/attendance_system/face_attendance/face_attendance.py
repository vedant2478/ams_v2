from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.properties import StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from datetime import datetime
from components.base_screen import BaseScreen
from threading import Thread, Lock
import queue
import cv2
import numpy as np

# Import the generalized face recognition system
from face_recognition_system import FaceRecognitionSystem


class KivyCamera(Image):
    """Optimized camera widget with multithreading"""
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        self.stopped = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.thread = None
        
    def start(self, camera_index=1):
        """Start camera with background thread"""
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            # Optimized settings
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            # Start capture thread
            self.stopped = False
            self.thread = Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully with threading")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def _capture_frames(self):
        """Background thread for frame capture"""
        while not self.stopped:
            if self.capture and self.capture.isOpened():
                ret, frame = self.capture.read()
                if ret:
                    # Clear old frame
                    if not self.frame_queue.empty():
                        try:
                            self.frame_queue.get_nowait()
                        except queue.Empty:
                            pass
                    
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        pass
    
    def update(self, dt):
        """Update display with latest frame"""
        try:
            frame = self.frame_queue.get_nowait()
            self.current_frame = frame.copy()
            
            # Rotate 180 degrees
            frame = cv2.rotate(frame, cv2.ROTATE_180)
            
            # Convert to texture
            h, w = frame.shape[:2]
            buf = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes()
            texture = Texture.create(size=(w, h), colorfmt='rgb')
            texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
            self.texture = texture
            
        except queue.Empty:
            pass
    
    def get_current_frame(self):
        """Get current frame thread-safely"""
        return self.current_frame.copy() if self.current_frame is not None else None
    
    def stop(self):
        """Stop camera and thread"""
        Clock.unschedule(self.update)
        self.stopped = True
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.capture:
            self.capture.release()
            self.capture = None
        print("Camera stopped")


class FaceAttendanceScreen(BaseScreen):
    """Optimized attendance screen with face recognition"""
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    processing = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super(FaceAttendanceScreen, self).__init__(**kwargs)
        
        # Initialize face recognition system
        self.face_system = FaceRecognitionSystem()
        
        # Data storage
        self.registered_faces = {}
        self.attendance_log = []
        self.last_recognized = {}
        self.threshold = 180
        
        # Thread-safe locks
        self.recognition_lock = Lock()
        self.data_lock = Lock()
        
        # Recognition thread
        self.recognition_thread = None
        self.recognition_stopped = False
        self.frame_for_recognition = None
        
        # Scheduled events
        self._auto_recognize_event = None
        self._camera_setup_event = None
    
    def on_enter(self):
        """Called when screen is entered"""
        print(f"Loaded {len(self.registered_faces)} registered faces")
        
        # Setup camera with delay
        if self._camera_setup_event:
            self._camera_setup_event.cancel()
        self._camera_setup_event = Clock.schedule_once(self.setup_camera, 0.1)
        
        # Start background recognition thread
        self.recognition_stopped = False
        self.recognition_thread = Thread(target=self._recognition_worker, daemon=True)
        self.recognition_thread.start()
        
        # Schedule frame capture for recognition
        if self._auto_recognize_event:
            self._auto_recognize_event.cancel()
        self._auto_recognize_event = Clock.schedule_interval(self.capture_for_recognition, 2.0)
    
    def setup_camera(self, dt):
        """Setup camera feed"""
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                self.ids.camera_feed.start(camera_index=1)
        except Exception as e:
            print(f"Camera setup error: {e}")
    
    def capture_for_recognition(self, dt):
        """Capture frame for background recognition"""
        if self.processing or len(self.registered_faces) == 0:
            return
        
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                frame = self.ids.camera_feed.get_current_frame()
                if frame is not None:
                    with self.recognition_lock:
                        self.frame_for_recognition = frame.copy()
        except Exception as e:
            print(f"Frame capture error: {e}")
    
    def _recognition_worker(self):
        """Background thread for face recognition processing"""
        while not self.recognition_stopped:
            try:
                # Get frame to process
                frame = None
                with self.recognition_lock:
                    if self.frame_for_recognition is not None:
                        frame = self.frame_for_recognition
                        self.frame_for_recognition = None
                
                if frame is None:
                    continue
                
                # Process recognition (CPU-intensive task in background)
                results = self.face_system.detect_and_recognize_faces(
                    frame, self.registered_faces, threshold=self.threshold
                )
                
                # Update UI on main thread
                Clock.schedule_once(lambda dt: self._process_recognition_results(results), 0)
                
            except Exception as e:
                print(f"Recognition worker error: {e}")
            
            # Small delay to prevent CPU hogging
            import time
            time.sleep(0.1)
    
    def _process_recognition_results(self, results):
        """Process recognition results on main thread"""
        if self.processing:
            return
        
        try:
            self.processing = True
            
            for result in results:
                name = result['name']
                score = result['score']
                
                if name != "Unknown" and score < self.threshold:
                    current_time = datetime.now()
                    
                    # Check cooldown (60 seconds)
                    with self.data_lock:
                        if name not in self.last_recognized or \
                           (current_time - self.last_recognized[name]).seconds > 60:
                            
                            # Log attendance
                            timestamp = current_time.strftime("%Y-%m-%d %H:%M:%S")
                            self.attendance_log.append((name, timestamp, score, self.current_time_type))
                            
                            # Update UI
                            self.update_welcome_message(name)
                            print(f"✓ {self.current_time_type.upper()} marked: {name} | {timestamp} | Score: {score:.0f}")
                            
                            self.last_recognized[name] = current_time
            
            self.processing = False
        
        except Exception as e:
            print(f"Recognition processing error: {e}")
            self.processing = False
    
    def on_time_type_change(self, time_type):
        """Handle time type toggle"""
        self.current_time_type = time_type
        print(f"Time type changed to: {time_type.upper()}")
    
    def update_welcome_message(self, username):
        """Update welcome message"""
        self.current_user = username
        if hasattr(self, 'ids') and 'welcome_label' in self.ids:
            self.ids.welcome_label.text = f'"{username}" --> Welcome'
    
    def get_user_list(self):
        """Get registered users list"""
        with self.data_lock:
            return list(self.registered_faces.keys())
    
    def get_attendance_log(self, limit=10):
        """Get recent attendance log"""
        with self.data_lock:
            return self.attendance_log[-limit:]
    
    def go_back(self):
        """Navigate back with cleanup"""
        self._cleanup()
        
        print(f"\n=== Session Summary ===")
        print(f"Registered Users: {len(self.registered_faces)}")
        print(f"Attendance Records: {len(self.attendance_log)}")
        print("Going back...")
        
        if hasattr(self, 'manager') and self.manager:
            self.manager.current = "attendance_type"
    
    def _cleanup(self):
        """Cleanup resources"""
        # Stop recognition thread
        self.recognition_stopped = True
        if self.recognition_thread and self.recognition_thread.is_alive():
            self.recognition_thread.join(timeout=1.0)
        
        # Cancel scheduled events
        if self._auto_recognize_event:
            self._auto_recognize_event.cancel()
            self._auto_recognize_event = None
        
        if self._camera_setup_event:
            self._camera_setup_event.cancel()
            self._camera_setup_event = None
        
        # Stop camera
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                self.ids.camera_feed.stop()
        except Exception as e:
            print(f"Camera stop error: {e}")
    
    def on_leave(self):
        """Called when screen is left"""
        self._cleanup()
