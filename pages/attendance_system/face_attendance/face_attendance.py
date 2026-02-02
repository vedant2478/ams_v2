from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.properties import StringProperty, BooleanProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.network.urlrequest import UrlRequest  # ✅ Add this
from datetime import datetime
from components.base_screen import BaseScreen
from threading import Thread, Lock
import queue
import cv2
import numpy as np
import time
import json  # ✅ Add this

# Import the generalized face recognition system
from face_recognition_system import FaceRecognitionSystem

# Import database manager
from pages.attendance_system.database.db_manager import DatabaseManager             


class KivyCamera(Image):
    """Optimized camera widget with multithreading and safe cleanup"""
    
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30
        self.current_frame = None
        self.stopped = False
        self.frame_queue = queue.Queue(maxsize=2)
        self.thread = None
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
            
            # Optimized settings
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            try:
                self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            except:
                print("MJPEG codec not available")
            
            # Verify settings
            actual_width = self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)
            actual_height = self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)
            print(f"Camera resolution: {int(actual_width)}x{int(actual_height)}")
            
            # Start capture thread
            self.stopped = False
            self.thread = Thread(target=self._capture_frames, daemon=True)
            self.thread.start()
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            self.camera_ready = True
            print(f"✓ Camera started successfully with threading")
            
        except Exception as e:
            print(f"✗ Error starting camera: {e}")
            import traceback
            traceback.print_exc()
    
    def _capture_frames(self):
        """Background thread for frame capture"""
        print("Camera capture thread started")
        try:
            while not self.stopped:
                if self.capture and self.capture.isOpened():
                    try:
                        ret, frame = self.capture.read()
                        if ret and frame is not None:
                            if not self.frame_queue.empty():
                                try:
                                    self.frame_queue.get_nowait()
                                except queue.Empty:
                                    pass
                            
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
        except Exception as e:
            print(f"Display update error: {e}")
    
    def get_current_frame(self):
        """Get current frame thread-safely"""
        if self.current_frame is not None:
            return self.current_frame.copy()
        return None
    
    def stop(self):
        """Stop camera and thread safely"""
        print("Stopping camera...")
        
        try:
            Clock.unschedule(self.update)
        except:
            pass
        
        self.stopped = True
        self.camera_ready = False
        
        if self.thread and self.thread.is_alive():
            print("Waiting for camera thread to finish...")
            self.thread.join(timeout=2.0)
            if self.thread.is_alive():
                print("Warning: Camera thread did not stop gracefully")
        
        try:
            while not self.frame_queue.empty():
                self.frame_queue.get_nowait()
        except:
            pass
        
        if self.capture:
            try:
                self.capture.release()
            except Exception as e:
                print(f"Camera release error: {e}")
            self.capture = None
        
        self.current_frame = None
        print("Camera stopped successfully")


class FaceAttendanceScreen(BaseScreen):
    """Optimized attendance screen with face recognition and Django API integration"""
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    processing = BooleanProperty(False)
    
    # ✅ Django API Configuration
    API_BASE_URL = "http://192.168.1.100:8000/api/attendance"  # Change to your server IP
    
    def __init__(self, **kwargs):
        super(FaceAttendanceScreen, self).__init__(**kwargs)
        
        # Initialize face recognition system
        self.face_system = FaceRecognitionSystem()
        
        # Initialize database manager
        self.db = DatabaseManager('sqlite:///csi_attendance.dev.sqlite')
        
        # Data storage (cached from database)
        self.registered_faces = {}
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
    
    # ✅ Django API Methods
    def hit_django_api(self, name, time_type):
        """Hit Django API for sign-in or sign-out"""
        try:
            # Determine which endpoint to hit
            if time_type == "in":
                url = f"{self.API_BASE_URL}/create-vedant-attendance/"
                action = "Sign In"
            else:
                url = f"{self.API_BASE_URL}/signout-vedant-attendance/"
                action = "Sign Out"
            
            print(f"→ Hitting Django API: {action} for {name}")
            print(f"   URL: {url}")
            
            # Make async request
            UrlRequest(
                url,
                on_success=lambda req, result: self.on_api_success(req, result, name, action),
                on_failure=lambda req, result: self.on_api_failure(req, result, name, action),
                on_error=lambda req, error: self.on_api_error(req, error, name, action),
                timeout=10
            )
            
        except Exception as e:
            print(f"✗ API request error: {e}")
    
    def on_api_success(self, request, result, name, action):
        """Handle successful API response"""
        try:
            print(f"✓ {action} API Response:")
            print(f"   Status: {result.get('status')}")
            print(f"   Message: {result.get('message')}")
            
            if result.get('status') == 'success':
                data = result.get('data', {})
                print(f"   Employee: {data.get('employee')}")
                print(f"   Time: {data.get('sign_in_time') or data.get('sign_out_time')}")
                
                if action == "Sign Out":
                    print(f"   Total Hours: {data.get('total_hours')}")
                    print(f"   Overtime: {data.get('overtime')}")
                
                # Show success message on UI (optional)
                self.show_api_status(f"{action} successful!", "success")
            else:
                print(f"✗ API returned error: {result.get('message')}")
                self.show_api_status(result.get('message', 'Error'), "error")
                
        except Exception as e:
            print(f"✗ Error processing API response: {e}")
    
    def on_api_failure(self, request, result):
        """Handle API request failure"""
        print(f"✗ API Request Failed:")
        print(f"   Result: {result}")
        self.show_api_status("API request failed", "error")
    
    def on_api_error(self, request, error):
        """Handle API request error"""
        print(f"✗ API Request Error:")
        print(f"   Error: {error}")
        self.show_api_status(f"Connection error: {error}", "error")
    
    def show_api_status(self, message, status_type):
        """Show API status message on UI (optional - implement based on your UI)"""
        try:
            if hasattr(self, 'ids') and 'status_label' in self.ids:
                self.ids.status_label.text = message
                
                # Color based on status
                if status_type == "success":
                    self.ids.status_label.color = (0, 1, 0, 1)  # Green
                else:
                    self.ids.status_label.color = (1, 0, 0, 1)  # Red
                
                # Clear after 3 seconds
                Clock.schedule_once(lambda dt: self.clear_status(), 3)
        except:
            pass
    
    def clear_status(self):
        """Clear status message"""
        try:
            if hasattr(self, 'ids') and 'status_label' in self.ids:
                self.ids.status_label.text = ""
        except:
            pass
    
    # Existing methods continue...
    
    def on_enter(self):
        """Called when screen is entered"""
        print("FaceAttendanceScreen: Entering...")
        
        # Load registered faces from database
        self.load_embeddings_from_db()
        
        print(f"Loaded {len(self.registered_faces)} registered faces from database")
        
        # Setup camera with delay
        if self._camera_setup_event:
            try:
                self._camera_setup_event.cancel()
            except:
                pass
        self._camera_setup_event = Clock.schedule_once(self.setup_camera, 0.1)
        
        # Start background recognition thread
        self.recognition_stopped = False
        self.recognition_thread = Thread(target=self._recognition_worker, daemon=True)
        self.recognition_thread.start()
        
        # Schedule frame capture for recognition
        if self._auto_recognize_event:
            try:
                self._auto_recognize_event.cancel()
            except:
                pass
        self._auto_recognize_event = Clock.schedule_interval(self.capture_for_recognition, 2.0)
    
    def load_embeddings_from_db(self):
        """Load all user embeddings from database"""
        try:
            self.registered_faces = self.db.get_all_embeddings(active_only=True)
            print(f"✓ Loaded {len(self.registered_faces)} embeddings from database")
        except Exception as e:
            print(f"✗ Error loading embeddings: {e}")
            self.registered_faces = {}
    
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
        print("Recognition worker thread started")
        try:
            while not self.recognition_stopped:
                try:
                    # Get frame to process
                    frame = None
                    with self.recognition_lock:
                        if self.frame_for_recognition is not None:
                            frame = self.frame_for_recognition
                            self.frame_for_recognition = None
                    
                    if frame is None:
                        time.sleep(0.1)
                        continue
                    
                    # Process recognition
                    results = self.face_system.detect_and_recognize_faces(
                        frame, self.registered_faces, threshold=self.threshold
                    )
                    
                    # Update UI on main thread
                    Clock.schedule_once(lambda dt: self._process_recognition_results(results), 0)
                    
                except Exception as e:
                    print(f"Recognition worker error: {e}")
                
                time.sleep(0.1)
        except Exception as e:
            print(f"Recognition thread exception: {e}")
        finally:
            print("Recognition worker thread stopped")
    
    def _process_recognition_results(self, results):
        """Process recognition results and hit Django API"""
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
                            
                            # Save to local database
                            db_result = self.db.mark_attendance(
                                name=name,
                                time_type=self.current_time_type,
                                recognition_score=score
                            )
                            
                            if db_result['success']:
                                # Update UI
                                self.update_welcome_message(name)
                                timestamp = db_result.get('timestamp', current_time.strftime("%Y-%m-%d %H:%M:%S"))
                                print(f"✓ {self.current_time_type.upper()} marked: {name} | {timestamp} | Score: {score:.0f}")
                                
                                # ✅ HIT DJANGO API
                                self.hit_django_api(name, self.current_time_type)
                                
                                self.last_recognized[name] = current_time
                            else:
                                print(f"✗ Database error: {db_result['message']}")
            
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
        """Get registered users list from database"""
        try:
            users = self.db.get_all_users(active_only=True)
            return [user.name for user in users]
        except Exception as e:
            print(f"✗ Error getting user list: {e}")
            return []
    
    def get_attendance_log(self, limit=10):
        """Get recent attendance log from database"""
        try:
            records = self.db.get_attendance_records(limit=limit)
            return [
                (record.name, record.timestamp.strftime("%Y-%m-%d %H:%M:%S"), 
                 record.recognition_score, record.time_type)
                for record in records
            ]
        except Exception as e:
            print(f"✗ Error getting attendance log: {e}")
            return []
    
    def get_today_attendance(self):
        """Get today's attendance records"""
        try:
            records = self.db.get_attendance_by_date()
            return records
        except Exception as e:
            print(f"✗ Error getting today's attendance: {e}")
            return []
    
    def get_statistics(self):
        """Get attendance statistics"""
        try:
            return self.db.get_statistics()
        except Exception as e:
            print(f"✗ Error getting statistics: {e}")
            return {}
    
    def go_back(self):
        """Navigate back with cleanup"""
        print("FaceAttendanceScreen: Going back...")
        self._cleanup()
        
        # Get final statistics from database
        try:
            stats = self.db.get_statistics()
            print(f"\n=== Session Summary ===")
            print(f"Registered Users: {stats.get('total_users', 0)}")
            print(f"Total Attendance Records: {stats.get('total_attendance', 0)}")
            print(f"Today's Attendance: {stats.get('today_attendance', 0)}")
            print("Going back...")
        except Exception as e:
            print(f"Error getting statistics: {e}")
        
        if hasattr(self, 'manager') and self.manager:
            self.manager.current = "attendance_type"
    
    def _cleanup(self):
        """Cleanup resources"""
        print("FaceAttendanceScreen: Cleaning up...")
        
        # Stop recognition thread first
        self.recognition_stopped = True
        if self.recognition_thread and self.recognition_thread.is_alive():
            print("Waiting for recognition thread...")
            self.recognition_thread.join(timeout=2.0)
            if self.recognition_thread.is_alive():
                print("Warning: Recognition thread did not stop gracefully")
        
        # Cancel scheduled events
        if self._auto_recognize_event:
            try:
                self._auto_recognize_event.cancel()
            except:
                pass
            self._auto_recognize_event = None
        
        if self._camera_setup_event:
            try:
                self._camera_setup_event.cancel()
            except:
                pass
            self._camera_setup_event = None
        
        # Stop camera
        try:
            if hasattr(self, 'ids') and 'camera_feed' in self.ids:
                camera = self.ids.camera_feed
                if camera:
                    camera.stop()
                    time.sleep(0.2)
        except Exception as e:
            print(f"Camera stop error: {e}")
        
        print("FaceAttendanceScreen: Cleanup complete")
    
    def on_leave(self):
        """Called when screen is left"""
        self._cleanup()
