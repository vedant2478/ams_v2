import cv2


def is_face_in_box(frame, box_coords):
    """
    Detect if a face is inside the specified box.
    
    Args:
        frame: Current camera frame (BGR)
        box_coords: Tuple (x1, y1, x2, y2) of the box
    
    Returns:
        (is_inside, face_roi): Boolean and cropped face region
    """
    x1, y1, x2, y2 = box_coords
    
    try:
        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)
        
        for (fx, fy, fw, fh) in faces:
            face_center_x = fx + fw // 2
            face_center_y = fy + fh // 2
            
            # Check if face center is inside the box
            if x1 < face_center_x < x2 and y1 < face_center_y < y2:
                # Return the face ROI from the box area
                face_roi = frame[y1:y2, x1:x2]
                return True, face_roi
        
        return False, None
    
    except Exception as e:
        print(f"Face detection error: {e}")
        return False, None
