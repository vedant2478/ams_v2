from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture
import cv2


class KivyCamera(Image):
    """
    Custom camera widget using OpenCV for live camera feed
    """
    def __init__(self, **kwargs):
        print("KivyCamera: __init__ called")
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 15  # Reduced FPS for better stability
        
    def start(self, camera_index=1):
        """
        Start the camera capture
        """
        print(f"KivyCamera: start() called with camera_index={camera_index}")
        try:
            # Try different backends
            backends = [cv2.CAP_V4L2, cv2.CAP_V4L, cv2.CAP_ANY]
            
            for backend in backends:
                print(f"Trying backend: {backend}")
                self.capture = cv2.VideoCapture(camera_index, backend)
                
                if self.capture.isOpened():
                    print(f"Camera opened with backend {backend}")
                    
                    # Set properties BEFORE reading frames
                    self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                    self.capture.set(cv2.CAP_PROP_FPS, 15)
                    
                    # Important: Set format to MJPEG
                    self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
                    
                    # Try to read one test frame with longer timeout
                    print("Testing frame capture...")
                    for attempt in range(3):
                        ret, frame = self.capture.read()
                        print(f"  Attempt {attempt+1}: ret={ret}")
                        if ret and frame is not None:
                            print(f"  Frame captured successfully: {frame.shape}")
                            break
                    
                    if ret and frame is not None:
                        # Success! Schedule frame updates
                        Clock.schedule_interval(self.update, 1.0 / self.fps)
                        print(f"Camera started successfully at {self.fps} FPS")
                        return
                    else:
                        print("Failed to capture test frame, trying next backend")
                        self.capture.release()
                        self.capture = None
            
            print("ERROR: Could not start camera with any backend")
            
        except Exception as e:
            print(f"ERROR in start(): {e}")
            import traceback
            traceback.print_exc()
    
    def update(self, dt):
        """
        Update camera frame
        """
        if not self.capture or not self.capture.isOpened():
            return
        
        try:
            # Grab frame first (non-blocking)
            if not self.capture.grab():
                return
            
            # Then retrieve it
            ret, frame = self.capture.retrieve()
            
            if ret and frame is not None and frame.size > 0:
                # Get frame dimensions
                h, w = frame.shape[:2]
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Flatten to bytes
                buf = frame_rgb.tobytes()
                
                # Create texture
                texture = Texture.create(size=(w, h), colorfmt='rgb')
                texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                texture.flip_vertical()
                
                # Update display
                self.texture = texture
            
        except Exception as e:
            # Ignore occasional errors
            pass
    
    def stop(self):
        """
        Stop the camera capture
        """
        print("KivyCamera: stop() called")
        Clock.unschedule(self.update)
        if self.capture:
            try:
                self.capture.release()
                print("KivyCamera: Camera released")
            except Exception as e:
                print(f"ERROR releasing camera: {e}")
            self.capture = None


class FaceAttendanceScreen(Screen):
    """
    Face Attendance Screen with In-Time/Out-Time toggle and camera feed
    """
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    
    def __init__(self, **kwargs):
        print("FaceAttendanceScreen: __init__ called")
        super(FaceAttendanceScreen, self).__init__(**kwargs)
    
    def on_enter(self):
        """
        Called when screen is entered - initialize camera
        """
        print("FaceAttendanceScreen: on_enter() called")
        Clock.schedule_once(self.setup_camera, 1.0)  # Increased delay
    
    def setup_camera(self, dt):
        """
        Setup and start camera feed
        """
        print("FaceAttendanceScreen: setup_camera() called")
        try:
            if 'camera_feed' not in self.ids:
                print("ERROR: 'camera_feed' not found in self.ids")
                return
            
            # Start camera at index 1
            self.ids.camera_feed.start(camera_index=1)
            
        except Exception as e:
            print(f"ERROR in setup_camera(): {e}")
            import traceback
            traceback.print_exc()
    
    def on_time_type_change(self, time_type):
        """
        Handle toggle button change between In-Time and Out-Time
        """
        self.current_time_type = time_type
        print(f"Time type changed to: {time_type}")
    
    def update_welcome_message(self, username):
        """
        Update welcome message with detected user
        """
        self.current_user = username
        self.ids.welcome_label.text = f'"{username}" --> Welcome'
    
    def go_back(self):
        """
        Navigate back to previous screen
        """
        print("FaceAttendanceScreen: go_back() called")
        try:
            self.ids.camera_feed.stop()
        except Exception as e:
            print(f"ERROR stopping camera: {e}")
        
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        """
        Called when screen is left - cleanup camera
        """
        print("FaceAttendanceScreen: on_leave() called")
        try:
            self.ids.camera_feed.stop()
        except Exception as e:
            print(f"ERROR in on_leave: {e}")
