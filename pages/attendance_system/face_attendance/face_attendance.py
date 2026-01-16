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
        self.fps = 30
        
    def start(self, camera_index=0):
        """
        Start the camera capture
        Args:
            camera_index: Camera device index (0 for default camera)
        """
        try:
            self.capture = cv2.VideoCapture(camera_index)
            
            # Set camera resolution
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # Schedule frame updates
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print("Camera started successfully")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """
        Update camera frame
        """
        if self.capture and self.capture.isOpened():
            ret, frame = self.capture.read()
            
            if ret:
                # Flip horizontally for mirror effect
                frame = cv2.flip(frame, 1)
                
                # Convert BGR to RGB
                buf = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Convert to Kivy texture
                buf = buf.tobytes()
                texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='rgb')
                texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                
                # Display texture
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
    """
    Face Attendance Screen with In-Time/Out-Time toggle and camera feed
    """
    
    current_time_type = StringProperty("in")
    current_user = StringProperty("USER_NAME")
    
    def __init__(self, **kwargs):
        super(FaceAttendanceScreen, self).__init__(**kwargs)
    
    def on_enter(self):
        """
        Called when screen is entered - initialize camera
        """
        Clock.schedule_once(self.setup_camera, 0.5)
    
    def setup_camera(self, dt):
        """
        Setup and start camera feed
        """
        try:
            # Start the camera feed
            self.ids.camera_feed.start(camera_index=0)
            
        except Exception as e:
            print(f"Camera setup error: {e}")
    
    def on_time_type_change(self, time_type):
        """
        Handle toggle button change between In-Time and Out-Time
        Args:
            time_type: "in" or "out"
        """
        self.current_time_type = time_type
        print(f"Time type changed to: {time_type}")
        
        if time_type == "in":
            print("Ready for In-Time attendance")
        else:
            print("Ready for Out-Time attendance")
    
    def update_welcome_message(self, username):
        """
        Update welcome message with detected user
        Args:
            username: Name of the detected user
        """
        self.current_user = username
        self.ids.welcome_label.text = f'"{username}" --> Welcome'
    
    def process_face_detection(self, frame):
        """
        Process face detection on the current frame
        Args:
            frame: Current camera frame from OpenCV
        Returns:
            Processed frame with face detection overlays
        """
        # Load face cascade classifier
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        
        # Convert to grayscale for face detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detect faces
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        # Draw rectangles around detected faces
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        return frame
    
    def go_back(self):
        """
        Navigate back to previous screen
        """
        # Stop camera before leaving
        self.ids.camera_feed.stop()
        
        print("Going back")
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        """
        Called when screen is left - cleanup camera
        """
        self.ids.camera_feed.stop()
