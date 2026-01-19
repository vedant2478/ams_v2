import cv2
import numpy as np


class FaceRecognitionSystem:
    """Generalized Face Recognition System - No Database Operations"""
    
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def extract_face_embedding(self, face_img):
        """Extract face embedding from face image"""
        try:
            if face_img is None or face_img.size == 0:
                return None
            
            gray = cv2.cvtColor(face_img, cv2.COLOR_BGR2GRAY)
            resized = cv2.resize(gray, (100, 100))
            embedding = resized.flatten().astype(np.float32) / 255.0
            return embedding
        except Exception as e:
            print(f"Embedding error: {e}")
            return None
    
    def register_face_from_frame(self, frame, name):
        """
        Register face from a single frame
        Returns: dict with success status and embedding
        """
        result = {
            'success': False,
            'name': name,
            'embedding': None,
            'message': ''
        }
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
        )
        
        if len(faces) > 0:
            (x, y, w, h) = faces[0]
            face_crop = frame[y:y+h, x:x+w]
            embedding = self.extract_face_embedding(face_crop)
            
            if embedding is not None:
                result['success'] = True
                result['embedding'] = embedding
                result['message'] = f"Face captured successfully"
                return result
        
        result['message'] = "No face detected in frame"
        return result
    
    def detect_and_recognize_faces(self, frame, known_faces, threshold=180):
        """
        Detect and recognize faces in frame
        Returns: list of dicts with recognition results and bounding boxes
        """
        results = []
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100)
        )
        
        for (x, y, w, h) in faces:
            face_crop = frame[y:y+h, x:x+w]
            embedding = self.extract_face_embedding(face_crop)
            
            if embedding is not None:
                min_dist = float('inf')
                recognized_name = "Unknown"
                
                for name, known_embedding in known_faces.items():
                    dist = np.sum((embedding - known_embedding) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        if dist < threshold:
                            recognized_name = name
                
                results.append({
                    'name': recognized_name,
                    'score': min_dist,
                    'bbox': (x, y, w, h),
                    'success': recognized_name != "Unknown" and min_dist < threshold
                })
        
        return results
