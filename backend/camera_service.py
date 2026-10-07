import cv2
import insightface
import threading
import time

from recognition import recognize_face
from attendance import mark_attendance


class CameraService:

    def __init__(self):
        self.camera = None
        self.running = False
        self.thread = None
        self.latest_frame = None

        self.last_person = None
        self.frame_count = 0

        self.confirm_frames = 8
        self.confirmed_people = set()

        # Latest recognition information for React/API
        self.latest_result = {
            "status": "idle",
            "recognized": False,
            "name": None,
            "class": None,
            "person_id": None,
            "similarity": None,
            "margin": None,
            "confirmation": 0,
            "confirmation_required": self.confirm_frames,
            "attendance_status": None,
        }

        print("Loading InsightFace...")

        self.app = insightface.app.FaceAnalysis(
            name="buffalo_l",
            providers=["CPUExecutionProvider"],
        )

        self.app.prepare(
            ctx_id=-1,
            det_size=(640, 640),
        )

        print("InsightFace ready.")

    def start(self):

        if self.running:
            return False

        self.camera = cv2.VideoCapture(0)

        if not self.camera.isOpened():
            self.camera = None
            return False

        self.running = True

        self.last_person = None
        self.frame_count = 0
        self.confirmed_people.clear()

        self.latest_result = {
            "status": "waiting",
            "recognized": False,
            "name": None,
            "class": None,
            "person_id": None,
            "similarity": None,
            "margin": None,
            "confirmation": 0,
            "confirmation_required": self.confirm_frames,
            "attendance_status": None,
        }

        self.thread = threading.Thread(
            target=self._camera_loop,
            daemon=True,
        )

        self.thread.start()

        return True

    def stop(self):

        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=3)

        if self.camera is not None:
            self.camera.release()

        self.camera = None
        self.thread = None
        self.latest_frame = None

        self.last_person = None
        self.frame_count = 0
        self.confirmed_people.clear()

        self.latest_result = {
            "status": "idle",
            "recognized": False,
            "name": None,
            "class": None,
            "person_id": None,
            "similarity": None,
            "margin": None,
            "confirmation": 0,
            "confirmation_required": self.confirm_frames,
            "attendance_status": None,
        }

    def is_running(self):
        return self.running

    def _camera_loop(self):

        while self.running:

            success, frame = self.camera.read()

            if not success:
                time.sleep(0.05)
                continue

            faces = self.app.get(frame)

            # No face detected
            if len(faces) == 0:

                self.last_person = None
                self.frame_count = 0

                self.latest_result = {
                    "status": "waiting",
                    "recognized": False,
                    "name": None,
                    "class": None,
                    "person_id": None,
                    "similarity": None,
                    "margin": None,
                    "confirmation": 0,
                    "confirmation_required": self.confirm_frames,
                    "attendance_status": None,
                }

            for face in faces:

                x1, y1, x2, y2 = face.bbox.astype(int)

                result = recognize_face(
                    face.normed_embedding
                )

                # ------------------------------------------
                # UNKNOWN PERSON
                # ------------------------------------------

                if not result["recognized"]:

                    self.last_person = None
                    self.frame_count = 0

                    color = (0, 0, 255)
                    label = "Unknown"

                    self.latest_result = {
                        "status": "unknown",
                        "recognized": False,
                        "name": "Unknown",
                        "class": None,
                        "person_id": None,
                        "similarity": result["similarity"],
                        "margin": result["margin"],
                        "confirmation": 0,
                        "confirmation_required": self.confirm_frames,
                        "attendance_status": "Not marked",
                    }

                # ------------------------------------------
                # REGISTERED PERSON
                # ------------------------------------------

                else:

                    person_id = result["person_id"]
                    name = result["name"]
                    person_class = result["class"]

                    # Count consecutive recognition frames
                    if person_id == self.last_person:
                        self.frame_count += 1

                    else:
                        self.last_person = person_id
                        self.frame_count = 1

                    # --------------------------------------
                    # STILL CONFIRMING
                    # --------------------------------------

                    if self.frame_count < self.confirm_frames:

                        color = (0, 255, 255)

                        label = (
                            f"Checking {name} "
                            f"{self.frame_count}/"
                            f"{self.confirm_frames}"
                        )

                        self.latest_result = {
                            "status": "checking",
                            "recognized": True,
                            "name": name,
                            "class": person_class,
                            "person_id": person_id,
                            "similarity": result["similarity"],
                            "margin": result["margin"],
                            "confirmation": self.frame_count,
                            "confirmation_required": self.confirm_frames,
                            "attendance_status": (
                                "Waiting for confirmation"
                            ),
                        }

                    # --------------------------------------
                    # PERSON CONFIRMED
                    # --------------------------------------

                    else:

                        color = (0, 255, 0)

                        label = (
                            f"{name} | {person_class}"
                        )

                        attendance_message = (
                            "Already confirmed this session"
                        )

                        if (
                            person_id
                            not in self.confirmed_people
                        ):

                            result_attendance = mark_attendance(
                                person_id,
                                name,
                                person_class,
                            )

                            self.confirmed_people.add(
                                person_id
                            )

                            attendance_message = (
                                result_attendance["message"]
                            )

                            print(
                                name,
                                "-",
                                attendance_message,
                            )

                        self.latest_result = {
                            "status": "recognized",
                            "recognized": True,
                            "name": name,
                            "class": person_class,
                            "person_id": person_id,
                            "similarity": result["similarity"],
                            "margin": result["margin"],
                            "confirmation": self.confirm_frames,
                            "confirmation_required": self.confirm_frames,
                            "attendance_status": attendance_message,
                        }

                # ------------------------------------------
                # DRAW FACE BOX
                # ------------------------------------------

                cv2.rectangle(
                    frame,
                    (x1, y1),
                    (x2, y2),
                    color,
                    2,
                )

                cv2.putText(
                    frame,
                    label,
                    (x1, max(30, y1 - 30)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.65,
                    color,
                    2,
                )

                score_text = (
                    f"Similarity: "
                    f"{result['similarity']:.2f}"
                )

                cv2.putText(
                    frame,
                    score_text,
                    (x1, max(55, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.5,
                    color,
                    2,
                )

            # ----------------------------------------------
            # ENCODE FRAME FOR WEB STREAM
            # ----------------------------------------------

            success, buffer = cv2.imencode(
                ".jpg",
                frame,
                [
                    cv2.IMWRITE_JPEG_QUALITY,
                    80,
                ],
            )

            if success:
                self.latest_frame = buffer.tobytes()

    def get_frame(self):
        return self.latest_frame

    def get_latest_result(self):
        return self.latest_result