import cv2

# Test video1
cap = cv2.VideoCapture(1)
if cap.isOpened():
    print("Camera 1 opened successfully!")
    ret, frame = cap.read()
    if ret:
        print(f"Frame captured: {frame.shape}")
    else:
        print("Cannot read frames")
    cap.release()
else:
    print("Cannot open camera 1")

