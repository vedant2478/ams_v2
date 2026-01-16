import os
import sys
from components.base_screen import BaseScreen
# Suppress OpenCV warnings
os.environ['OPENCV_LOG_LEVEL'] = 'SILENT'
os.environ['OPENCV_VIDEOIO_DEBUG'] = '0'

# Redirect stderr to suppress JPEG warnings
import cv2
cv2.setLogLevel(0)

from kivy.uix.screenmanager import Screen
from kivy.uix.image import Image
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.graphics.texture import Texture



class KivyCamera(Image):
    """
    Custom camera widget using OpenCV for live camera feed
    """
    def __init__(self, **kwargs):
        super(KivyCamera, self).__init__(**kwargs)
        self.capture = None
        self.fps = 30  # Increased FPS for smoother feed
        
    def start(self, camera_index=1):
        """
        Start the camera capture
        """
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            # Optimized settings for smooth playback
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_FPS, 30)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 2)  # Small buffer for low latency
            
            # Set MJPEG format for better performance
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc('M','J','P','G'))
            
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """
        Update camera frame - optimized for smooth playback
        """
        if self.capture and self.capture.isOpened():
            # Use grab() and retrieve() for better performance
            if self.capture.grab():
                ret, frame = self.capture.retrieve()
                
                if ret and frame is not None:
                    # ROTATE 180 DEGREES
                    frame = cv2.rotate(frame, cv2.ROTATE_180)
                    
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


class FaceAttendanceScreen(BaseScreen):
    
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
