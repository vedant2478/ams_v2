import cv2
import numpy as np
import face_recognition


class FaceRecognitionSystem:
    """Face Recognition System using dlib's 128-d face encodings"""
    
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def extract_face_embedding(self, frame):
        """
        Extract 128-dimensional face embedding using face_recognition library
        Returns: 128-d numpy array or None
        """
        try:
            if frame is None or frame.size == 0:
                return None
            
            # Convert BGR to RGB (face_recognition uses RGB)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # Get face encodings (128-d)
            encodings = face_recognition.face_encodings(rgb_frame)
            
            if len(encodings) > 0:
                return encodings[0]  # Return first face encoding (128-d)
            
            return None
            
        except Exception as e:
            print(f"Embedding error: {e}")
            return None
    
    def register_face_from_frame(self, frame, name):
        """
        Register face from a single frame
        Returns: dict with success status and 128-d embedding
        """
        result = {
            'success': False,
            'name': name,
            'embedding': None,
            'message': ''
        }
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces using face_recognition library
        face_locations = face_recognition.face_locations(rgb_frame)
        
        if len(face_locations) > 0:
            # Get 128-d encodings
            encodings = face_recognition.face_encodings(rgb_frame, face_locations)
            
            if len(encodings) > 0:
                result['success'] = True
                result['embedding'] = encodings[0]  # 128-d numpy array
                result['message'] = f"Face captured successfully"
                print(f"✓ Embedding extracted: shape={encodings[0].shape}, length={len(encodings[0])}")
                return result
        
        result['message'] = "No face detected in frame"
        return result
    
    def detect_and_recognize_faces(self, frame, known_faces, threshold=0.6):
        """
        Detect and recognize faces in frame using 128-d encodings
        Returns: list of dicts with recognition results and bounding boxes
        
        Args:
            threshold: Distance threshold (lower = stricter). Default 0.6 is good.
        """
        results = []
        
        # Convert BGR to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Detect faces
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        
        for (top, right, bottom, left), encoding in zip(face_locations, face_encodings):
            min_dist = float('inf')
            recognized_name = "Unknown"
            
            # Compare with known faces
            for name, known_embedding in known_faces.items():
                # Euclidean distance between 128-d vectors
                dist = np.linalg.norm(encoding - known_embedding)
                
                if dist < min_dist:
                    min_dist = dist
                    if dist < threshold:
                        recognized_name = name
            
            # Convert coordinates (face_recognition uses top,right,bottom,left)
            # to OpenCV format (x, y, w, h)
            x, y, w, h = left, top, right - left, bottom - top
            
            results.append({
                'name': recognized_name,
                'score': min_dist,
                'bbox': (x, y, w, h),
                'success': recognized_name != "Unknown" and min_dist < threshold
            })
        
        return results
