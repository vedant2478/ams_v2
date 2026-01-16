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
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 10  # Reduced to avoid timeout
        
    def start(self, camera_index=1):
        """
        Start the camera capture
        """
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            # Set lower resolution for better performance
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """
        Update camera frame with rotation fix
        """
        if self.capture and self.capture.isOpened():
            ret, frame = self.capture.read()
            
            if ret and frame is not None:
                # ROTATE 90 DEGREES CLOCKWISE to fix orientation
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                
                h, w = frame.shape[:2]
                buf = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).tobytes()
                texture = Texture.create(size=(w, h), colorfmt='rgb')
                texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                self.texture = texture
    
    def stop(self):
        """
        Stop the camera capture
        """
        Clock.unschedule(self.update)
        if self.capture:
            self.capture.release()
            self.capture = None
        print("Camera stopped")


class FaceAttendanceScreen(Screen):
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    
    def on_enter(self):
        Clock.schedule_once(self.setup_camera, 0.5)
    
    def setup_camera(self, dt):
        try:
            self.ids.camera_feed.start(camera_index=1)
        except Exception as e:
            print(f"Camera setup error: {e}")
    
    def on_time_type_change(self, time_type):
        self.current_time_type = time_type
        print(f"Time type changed to: {time_type}")
    
    def update_welcome_message(self, username):
        self.current_user = username
        self.ids.welcome_label.text = f'"{username}" --> Welcome'
    
    def go_back(self):
        try:
            self.ids.camera_feed.stop()
        except:
            pass
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        try:
            self.ids.camera_feed.stop()
        except:
            pass
