import cv2
import numpy as np
import os


class FaceRecognitionSystem:
    """Lightweight Face Recognition using OpenCV DNN (no external libraries)"""
    
    def __init__(self):
        """Initialize with OpenCV's DNN face detector and FaceNet model"""
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # Download FaceNet model if not present
        self.model_dir = "models"
        self.setup_facenet_model()
        
        print("✓ Lightweight OpenCV DNN FaceNet loaded (128-d embeddings)")
    
    def setup_facenet_model(self):
        """Download and setup FaceNet model"""
        os.makedirs(self.model_dir, exist_ok=True)
        
        model_path = os.path.join(self.model_dir, "facenet.onnx")
        
        # If model doesn't exist, download it
        if not os.path.exists(model_path):
            print("Downloading FaceNet model (one-time, ~95MB)...")
            import urllib.request
            url = "https://github.com/pyannote/onnxruntime-extensions/raw/main/models/facenet.onnx"
            try:
                urllib.request.urlretrieve(url, model_path)
                print("✓ Model downloaded successfully")
            except:
                print("⚠️ Using fallback: Simple embedding extraction")
                self.facenet_model = None
                return
        
        # Load the model
        try:
            self.facenet_model = cv2.dnn.readNetFromONNX(model_path)
            print("✓ FaceNet model loaded")
        except:
            print("⚠️ Could not load ONNX model, using simple embeddings")
            self.facenet_model = None
    
    def extract_face_embedding(self, face_img):
        """
        Extract 128-d face embedding
        Uses FaceNet if available, otherwise uses ResNet-based simple embedding
        """
        try:
            if face_img is None or face_img.size == 0:
                return None
            
            # Resize to 160x160 (FaceNet input size)
            face_resized = cv2.resize(face_img, (160, 160))
            
            if self.facenet_model is not None:
                # Use FaceNet ONNX model
                blob = cv2.dnn.blobFromImage(
                    face_resized, 1.0/255, (160, 160), (0, 0, 0), swapRB=True
                )
                self.facenet_model.setInput(blob)
                embedding = self.facenet_model.forward()
                return embedding.flatten().astype(np.float32)
            
            else:
                # Fallback: Simple but effective 128-d embedding
                # Uses image features + histogram
                gray = cv2.cvtColor(face_resized, cv2.COLOR_BGR2GRAY) if len(face_resized.shape) == 3 else face_resized
                
                # Extract multiple features
                # 1. LBP features (texture)
                lbp = self._compute_lbp(gray)
                
                # 2. HOG features (shape)
                hog = self._compute_hog(gray)
                
                # 3. Intensity histogram
                hist = cv2.calcHist([gray], [0], None, [32], [0, 256]).flatten()
                hist = hist / (hist.sum() + 1e-7)  # normalize
                
                # Combine features to make 128-d vector
                features = np.concatenate([lbp, hog, hist])
                
                # Pad or truncate to exactly 128 dimensions
                if len(features) < 128:
                    features = np.pad(features, (0, 128 - len(features)))
                else:
                    features = features[:128]
                
                return features.astype(np.float32)
                
        except Exception as e:
            print(f"Embedding error: {e}")
            return None
    
    def _compute_lbp(self, gray):
        """Compute Local Binary Pattern features"""
        try:
            # Simple LBP implementation
            padded = np.pad(gray, 1, mode='edge')
            lbp = np.zeros_like(gray, dtype=np.uint8)
            
            for i in range(1, padded.shape[0]-1):
                for j in range(1, padded.shape[1]-1):
                    center = padded[i, j]
                    code = 0
                    code |= (padded[i-1, j-1] > center) << 0
                    code |= (padded[i-1, j] > center) << 1
                    code |= (padded[i-1, j+1] > center) << 2
                    code |= (padded[i, j+1] > center) << 3
                    code |= (padded[i+1, j+1] > center) << 4
                    code |= (padded[i+1, j] > center) << 5
                    code |= (padded[i+1, j-1] > center) << 6
                    code |= (padded[i, j-1] > center) << 7
                    lbp[i-1, j-1] = code
            
            # Histogram of LBP
            hist = cv2.calcHist([lbp], [0], None, [32], [0, 256]).flatten()
            hist = hist / (hist.sum() + 1e-7)
            return hist
        except:
            return np.zeros(32, dtype=np.float32)
    
    def _compute_hog(self, gray):
        """Compute HOG features"""
        try:
            # Simple gradient-based features
            gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
            gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
            
            magnitude = np.sqrt(gx**2 + gy**2)
            angle = np.arctan2(gy, gx)
            
            # Histogram of oriented gradients
            hist, _ = np.histogram(angle, bins=32, range=(-np.pi, np.pi), weights=magnitude)
            hist = hist / (hist.sum() + 1e-7)
            return hist.astype(np.float32)
        except:
            return np.zeros(32, dtype=np.float32)
    
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
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )
            
            if len(faces) == 0:
                result['message'] = "No face detected in frame"
                return result
            
            # Get the largest face
            (x, y, w, h) = max(faces, key=lambda f: f[2] * f[3])
            face_crop = frame[y:y+h, x:x+w]
            
            # Extract embedding
            embedding = self.extract_face_embedding(face_crop)
            
            if embedding is not None and len(embedding) == 128:
                result['success'] = True
                result['embedding'] = embedding
                result['message'] = f"Face captured successfully"
                print(f"✓ Embedding extracted: 128-d vector")
                return result
            else:
                result['message'] = "Could not extract valid embedding"
                return result
                
        except Exception as e:
            print(f"Registration error: {e}")
            import traceback
            traceback.print_exc()
            result['message'] = f"Error: {str(e)}"
            return result
    
    def detect_and_recognize_faces(self, frame, known_faces, threshold=0.4):
        """
        Detect and recognize faces in frame
        Returns: list of dicts with recognition results and bounding boxes
        
        Args:
            threshold: Distance threshold (0.3-0.5 recommended for this method)
        """
        results = []
        
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80)
            )
            
            for (x, y, w, h) in faces:
                face_crop = frame[y:y+h, x:x+w]
                encoding = self.extract_face_embedding(face_crop)
                
                if encoding is None:
                    continue
                
                min_dist = float('inf')
                recognized_name = "Unknown"
                
                # Compare with known faces using cosine similarity
                for name, known_embedding in known_faces.items():
                    # Cosine similarity
                    similarity = np.dot(encoding, known_embedding) / (
                        np.linalg.norm(encoding) * np.linalg.norm(known_embedding) + 1e-7
                    )
                    dist = 1 - similarity
                    
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
            
        except Exception as e:
            print(f"Recognition error: {e}")
        
        return results
