@'
# Face Recognition System — Architecture

## 1. System Overview

The Face Recognition System is a web-based application that performs real-time face recognition using a laptop camera.

The system allows administrators/users to:

- Register a person using multiple face images
- Recognize registered people through the laptop camera
- Detect unknown people
- Automatically mark attendance
- Prevent duplicate attendance on the same day
- Edit registered person information
- Delete face profiles
- Restore deleted face profiles
- Search and export attendance records

---

## 2. High-Level Architecture

```text
                    USER
                      |
                      v
              React Frontend
              localhost:5173
                      |
                      |
                HTTP / API
                      |
                      v
               FastAPI Backend
               localhost:8000
                      |
        +-------------+-------------+
        |             |             |
        v             v             v
 Camera Service   Recognition    Attendance
        |             |             |
        v             v             v
    OpenCV        InsightFace      CSV File
        |             |
        v             v
 Laptop Camera   Face Embeddings
                      |
                      v
               Stored Face Model
               face_model.pkl
                      |
                      v
                people.json