from components.base_screen import BaseScreen
from kivy.properties import StringProperty


class AttendanceTypeScreen(BaseScreen):
    def __init__(self, **kwargs):
        super(AttendanceTypeScreen, self).__init__(**kwargs)
    
    def on_biometric_attendance(self):
        
        print("Biometric Attendance selected")
        
    
    def on_face_attendance(self):

        print("Face Attendance selected")
        self.manager.current = "face_attendance"
    
    def on_register_user(self):
        print("Register User selected")
        self.manager.current = "register_user"
    
    
    def go_back(self):
  
        print("Going back")
        # Navigate to previous screen (likely main menu or module select)
        self.manager.current = "module_select"
    