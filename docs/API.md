# Face Recognition System — API Documentation

## Overview

The backend is built using FastAPI and runs locally on:

http://127.0.0.1:8000

Interactive FastAPI documentation:

http://127.0.0.1:8000/docs

Alternative ReDoc documentation:

http://127.0.0.1:8000/redoc

---

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Check whether the API is running |
| GET | `/attendance` | Retrieve saved attendance records |
| GET | `/students` | Retrieve active registered people |
| GET | `/students/deleted` | Retrieve deleted/restorable profiles |
| POST | `/students/register` | Register a new person |
| PUT | `/students/{person_id}` | Edit a registered person's information |
| DELETE | `/students/{person_id}` | Delete a registered profile |
| POST | `/students/deleted/{backup_name}/restore` | Restore a deleted profile |
| POST | `/recognition/start` | Start face recognition |
| POST | `/recognition/stop` | Stop face recognition |
| GET | `/recognition/status` | Check recognition status |
| GET | `/recognition/result` | Get latest recognition result |
| GET | `/video-feed` | Get live camera stream |

---

# 1. API Health Check

## GET `/`

Checks whether the FastAPI backend is running.

Example response:

```json
{
  "message": "Face Recognition System API is running"
}