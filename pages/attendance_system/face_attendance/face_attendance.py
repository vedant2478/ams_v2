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
        self.fps = 30
        
    def start(self, camera_index=1):
        """
        Start the camera capture
        """
        print(f"KivyCamera: start() called with camera_index={camera_index}")
        try:
            # Open camera at index 1
            self.capture = cv2.VideoCapture(camera_index)
            print(f"KivyCamera: VideoCapture created: {self.capture}")
            
            if not self.capture.isOpened():
                print(f"ERROR: Could not open camera at index {camera_index}")
                return
            
            print("KivyCamera: Camera opened successfully")
            
            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Warm up camera
            print("KivyCamera: Warming up camera...")
            for i in range(5):
                ret, frame = self.capture.read()
                print(f"  Warm-up frame {i}: ret={ret}")
            
            # Schedule frame updates
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"KivyCamera: Clock scheduled at {self.fps} FPS")
            print("="*50)
            
        except Exception as e:
            print(f"ERROR in start(): {e}")
            import traceback
            traceback.print_exc()
    
    def update(self, dt):
        """
        Update camera frame
        """
        if not self.capture:
            print("ERROR: self.capture is None")
            return
            
        if not self.capture.isOpened():
            print("ERROR: capture is not opened")
            return
        
        try:
            ret, frame = self.capture.read()
            
            if not ret:
                print("ERROR: Failed to read frame (ret=False)")
                return
                
            if frame is None:
                print("ERROR: Frame is None")
                return
            
            # Get frame dimensions
            h, w = frame.shape[:2]
            print(f"Frame captured: {w}x{h}")
            
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
            print(f"Texture updated: {w}x{h}")
            
        except Exception as e:
            print(f"ERROR in update(): {e}")
            import traceback
            traceback.print_exc()
    
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
        Clock.schedule_once(self.setup_camera, 0.5)
    
    def setup_camera(self, dt):
        """
        Setup and start camera feed
        """
        print("FaceAttendanceScreen: setup_camera() called")
        try:
            # Check if camera_feed exists in ids
            if 'camera_feed' not in self.ids:
                print("ERROR: 'camera_feed' not found in self.ids")
                print(f"Available ids: {list(self.ids.keys())}")
                return
            
            print(f"camera_feed widget: {self.ids.camera_feed}")
            print(f"camera_feed type: {type(self.ids.camera_feed)}")
            
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
