
# Face Recognition System

A real-time Face Recognition and Attendance Management System developed using React, FastAPI, OpenCV, InsightFace and ONNX Runtime.

The system uses a laptop camera to detect and recognize registered people and automatically records their attendance with the current date and time.

---

## Features

- Real-time face detection using laptop camera
- Face recognition using InsightFace embeddings
- Registered person management
- Add new face profiles
- Upload multiple training images
- Select images from multiple folders
- Remove individual images before registration
- Duplicate face registration prevention
- Mixed-person photo detection during registration
- Edit registered person's name and class
- Delete face profiles
- Restore deleted profiles
- Unknown-person detection
- Multi-frame recognition confirmation
- Automatic attendance marking
- One attendance record per person per day
- Attendance date and time storage
- Attendance search and filtering
- CSV attendance export
- Persistent face profiles and attendance records
- React-based dashboard interface

---

## Recognition Workflow

```text
Face Recognition System
        |
        v
Start Recognition
        |
        v
Laptop Camera
        |
        v
Detect Face
        |
        v
Generate Face Embedding
        |
        v
Compare With Registered Profiles
        |
        +----------------------+
        |                      |
        v                      v
Recognized                 Unknown
        |
        v
8-Frame Confirmation
        |
        v
Show Name + Class
        |
        v
Mark Attendance
        |
        v
Save Date + Time
