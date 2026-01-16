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
        
    def start(self, camera_index=1):
        """
        Start the camera capture
        Args:
            camera_index: Camera device index (default 1 for your device)
        """
        try:
            # Open camera at index 1
            self.capture = cv2.VideoCapture(camera_index)
            
            if not self.capture.isOpened():
                print(f"Error: Could not open camera at index {camera_index}")
                return
            
            # Set camera properties
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self.capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            
            # Warm up camera - discard first few frames
            for _ in range(5):
                self.capture.read()
            
            # Schedule frame updates
            Clock.schedule_interval(self.update, 1.0 / self.fps)
            print(f"Camera started successfully at index {camera_index}")
            
        except Exception as e:
            print(f"Error starting camera: {e}")
    
    def update(self, dt):
        """
        Update camera frame
        """
        if not self.capture or not self.capture.isOpened():
            return
        
        try:
            ret, frame = self.capture.read()
            
            if ret and frame is not None:
                # Get frame dimensions
                h, w = frame.shape[:2]
                
                # Convert BGR to RGB
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Flatten to bytes
                buf = frame_rgb.tobytes()
                
                # Create texture
                texture = Texture.create(size=(w, h), colorfmt='rgb')
                texture.blit_buffer(buf, colorfmt='rgb', bufferfmt='ubyte')
                texture.flip_vertical()  # Flip texture for correct orientation
                
                # Update display
                self.texture = texture
                
        except Exception as e:
            print(f"Frame update error: {e}")
    
    def stop(self):
        """
        Stop the camera capture
        """
        Clock.unschedule(self.update)
        if self.capture:
            try:
                self.capture.release()
            except:
                pass
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
            # Start camera at index 1
            self.ids.camera_feed.start(camera_index=1)
            
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
    
    def enable_face_detection(self):
        """
        Enable real-time face detection on camera feed
        Call this method to activate face detection
        """
        try:
            # Schedule face detection
            Clock.schedule_interval(self.detect_faces, 0.5)
            print("Face detection enabled")
            
        except Exception as e:
            print(f"Face detection setup error: {e}")
    
    def detect_faces(self, dt):
        """
        Detect faces in current camera frame
        """
        try:
            camera = self.ids.camera_feed
            if camera.capture and camera.capture.isOpened():
                ret, frame = camera.capture.read()
                
                if ret and frame is not None:
                    # Load classifier
                    face_cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                    )
                    
                    # Detect faces
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
                    
                    if len(faces) > 0:
                        # Face detected - update UI
                        self.update_welcome_message("Face Detected")
                    else:
                        self.update_welcome_message("USER_NAME")
                        
        except Exception as e:
            print(f"Face detection error: {e}")
    
    def go_back(self):
        """
        Navigate back to previous screen
        """
        # Unschedule any detection tasks
        Clock.unschedule(self.detect_faces)
        
        # Stop camera
        try:
            self.ids.camera_feed.stop()
        except:
            pass
        
        print("Going back")
        self.manager.current = "attendance_type"
    
    def on_leave(self):
        """
        Called when screen is left - cleanup camera
        """
        # Unschedule any detection tasks
        Clock.unschedule(self.detect_faces)
        
        # Stop camera
        try:
            self.ids.camera_feed.stop()
        except:
            pass
