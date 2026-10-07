from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form,
    HTTPException,
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

import csv
import cv2
import json
import pickle
import re
import shutil
import time

import numpy as np

from camera_service import CameraService
from recognition import (
    get_registered_people,
    reload_recognition_data,
    MODEL_PATH,
    PEOPLE_FILE,
)


app = FastAPI(title="Face Recognition System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ROOT = Path(__file__).resolve().parent.parent
ATTENDANCE_FILE = ROOT / "attendance" / "attendance.csv"
TRAIN_DATASET = ROOT / "dataset" / "train"
BACKUP_DIR = ROOT / "models" / "backups"
DELETED_DATASET_BACKUP_DIR = BACKUP_DIR / "deleted_datasets"

MIN_VALID_IMAGES = 8
MAX_UPLOAD_IMAGES = 30
MAX_IMAGE_SIZE_MB = 10

DUPLICATE_CENTROID_THRESHOLD = 0.65
DUPLICATE_PHOTO_THRESHOLD = 0.60
DUPLICATE_MATCH_RATIO = 0.60

# Same-person registration consistency protection
CONSISTENCY_PAIR_THRESHOLD = 0.50
CONSISTENCY_CENTROID_THRESHOLD = 0.65
CONSISTENCY_MIN_NEIGHBOR_RATIO = 0.60

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

DELETED_FOLDER_PATTERN = re.compile(
    r"^(?P<person_id>.+)_"
    r"(?P<date>\d{8})_"
    r"(?P<clock>\d{6})_"
    r"(?P<microseconds>\d{6})$"
)

TRAIN_DATASET.mkdir(parents=True, exist_ok=True)
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
DELETED_DATASET_BACKUP_DIR.mkdir(parents=True, exist_ok=True)

camera_service = CameraService()


class UpdateStudentRequest(BaseModel):
    name: str
    class_name: str


def create_person_id(name):
    cleaned = name.strip()
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", cleaned)
    cleaned = cleaned.strip("_")

    if not cleaned:
        raise ValueError("Could not create a valid Person ID.")

    return cleaned


def load_people():
    if not PEOPLE_FILE.exists():
        return {}

    with open(PEOPLE_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_face_database():
    if not MODEL_PATH.exists():
        return {}

    with open(MODEL_PATH, "rb") as file:
        return pickle.load(file)


def save_people_atomic(people):
    temp_file = PEOPLE_FILE.parent / (PEOPLE_FILE.name + ".tmp")

    with open(temp_file, "w", encoding="utf-8") as file:
        json.dump(
            people,
            file,
            indent=2,
            ensure_ascii=False,
        )

    temp_file.replace(PEOPLE_FILE)


def save_model_atomic(database):
    temp_file = MODEL_PATH.parent / (MODEL_PATH.name + ".tmp")

    with open(temp_file, "wb") as file:
        pickle.dump(database, file)

    temp_file.replace(MODEL_PATH)


def create_backups():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

    model_backup = None
    people_backup = None

    if MODEL_PATH.exists():
        model_backup = BACKUP_DIR / f"face_model_{timestamp}.pkl"
        shutil.copy2(MODEL_PATH, model_backup)

    if PEOPLE_FILE.exists():
        people_backup = BACKUP_DIR / f"people_{timestamp}.json"
        shutil.copy2(PEOPLE_FILE, people_backup)

    return model_backup, people_backup


def restore_backups(model_backup, people_backup):
    if model_backup and model_backup.exists():
        shutil.copy2(model_backup, MODEL_PATH)

    if people_backup and people_backup.exists():
        shutil.copy2(people_backup, PEOPLE_FILE)


def calculate_similarity(embedding1, embedding2):
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)

    if norm1 == 0 or norm2 == 0:
        return 0.0

    return float(
        np.dot(embedding1, embedding2)
        / (norm1 * norm2)
    )


def check_duplicate_identity(
    new_embeddings,
    new_centroid,
    database,
):
    closest_result = None

    for existing_id, existing_data in database.items():
        existing_centroid = existing_data.get("embedding")

        if existing_centroid is None:
            continue

        centroid_similarity = calculate_similarity(
            new_centroid,
            existing_centroid,
        )

        existing_training = existing_data.get("training_embeddings")
        photo_scores = []

        for new_embedding in new_embeddings:
            best_photo_score = calculate_similarity(
                new_embedding,
                existing_centroid,
            )

            if existing_training is not None:
                for old_embedding in existing_training:
                    score = calculate_similarity(
                        new_embedding,
                        old_embedding,
                    )

                    if score > best_photo_score:
                        best_photo_score = score

            photo_scores.append(best_photo_score)

        matching_photos = sum(
            score >= DUPLICATE_PHOTO_THRESHOLD
            for score in photo_scores
        )

        match_ratio = matching_photos / len(photo_scores)

        average_photo_similarity = float(
            np.mean(photo_scores)
        )

        duplicate = (
            centroid_similarity >= DUPLICATE_CENTROID_THRESHOLD
            and match_ratio >= DUPLICATE_MATCH_RATIO
        )

        result = {
            "person_id": existing_id,
            "centroid_similarity": round(centroid_similarity, 4),
            "average_photo_similarity": round(average_photo_similarity, 4),
            "matching_photos": matching_photos,
            "total_photos": len(photo_scores),
            "match_ratio": round(match_ratio, 4),
            "duplicate": duplicate,
        }

        if (
            closest_result is None
            or centroid_similarity
            > closest_result["centroid_similarity"]
        ):
            closest_result = result

    return closest_result


def check_registration_consistency(
    embeddings,
    filenames,
):
    """
    Verify that all accepted registration photos form one strong
    face-identity cluster before any profile is saved.
    """

    matrix = np.stack(embeddings).astype(np.float32)
    total = len(matrix)

    if total < 2:
        return {
            "consistent": False,
            "consistent_count": total,
            "inconsistent_count": 0,
            "inconsistent_files": [],
            "centroid_scores": [],
            "neighbor_ratios": [],
            "minimum_centroid_similarity": 0.0,
            "average_centroid_similarity": 0.0,
            "minimum_neighbor_ratio": 0.0,
        }

    # Pairwise cosine similarity. Embeddings are already normalized.
    pairwise = np.clip(
        matrix @ matrix.T,
        -1.0,
        1.0,
    )

    # For each photo, measure how much of the batch agrees with it.
    neighbor_counts = np.sum(
        pairwise >= CONSISTENCY_PAIR_THRESHOLD,
        axis=1,
    ) - 1

    neighbor_ratios = (
        neighbor_counts
        / max(total - 1, 1)
    )

    # Choose the most central photo as the robust anchor.
    average_pair_scores = (
        (np.sum(pairwise, axis=1) - 1.0)
        / max(total - 1, 1)
    )

    ranking_score = (
        neighbor_ratios
        + (0.01 * average_pair_scores)
    )

    anchor_index = int(
        np.argmax(ranking_score)
    )

    dominant_indices = np.where(
        pairwise[anchor_index]
        >= CONSISTENCY_PAIR_THRESHOLD
    )[0]

    if len(dominant_indices) == 0:
        dominant_indices = np.array(
            [anchor_index],
            dtype=int,
        )

    robust_centroid = np.mean(
        matrix[dominant_indices],
        axis=0,
    )

    centroid_norm = np.linalg.norm(
        robust_centroid
    )

    if centroid_norm == 0:
        return {
            "consistent": False,
            "consistent_count": 0,
            "inconsistent_count": total,
            "inconsistent_files": list(filenames),
            "centroid_scores": [0.0] * total,
            "neighbor_ratios": [
                round(float(value), 4)
                for value in neighbor_ratios
            ],
            "minimum_centroid_similarity": 0.0,
            "average_centroid_similarity": 0.0,
            "minimum_neighbor_ratio": round(
                float(np.min(neighbor_ratios)),
                4,
            ),
        }

    robust_centroid = (
        robust_centroid
        / centroid_norm
    )

    centroid_scores = np.clip(
        matrix @ robust_centroid,
        -1.0,
        1.0,
    )

    consistent_mask = (
        (
            centroid_scores
            >= CONSISTENCY_CENTROID_THRESHOLD
        )
        &
        (
            neighbor_ratios
            >= CONSISTENCY_MIN_NEIGHBOR_RATIO
        )
    )

    consistent_indices = np.where(
        consistent_mask
    )[0]

    inconsistent_indices = np.where(
        ~consistent_mask
    )[0]

    inconsistent_files = [
        filenames[index]
        for index in inconsistent_indices
    ]

    return {
        "consistent": (
            len(inconsistent_indices) == 0
        ),
        "consistent_count": int(
            len(consistent_indices)
        ),
        "inconsistent_count": int(
            len(inconsistent_indices)
        ),
        "inconsistent_files": inconsistent_files,
        "centroid_scores": [
            round(float(value), 4)
            for value in centroid_scores
        ],
        "neighbor_ratios": [
            round(float(value), 4)
            for value in neighbor_ratios
        ],
        "minimum_centroid_similarity": round(
            float(np.min(centroid_scores)),
            4,
        ),
        "average_centroid_similarity": round(
            float(np.mean(centroid_scores)),
            4,
        ),
        "minimum_neighbor_ratio": round(
            float(np.min(neighbor_ratios)),
            4,
        ),
    }


def parse_deleted_folder_name(folder_name):
    match = DELETED_FOLDER_PATTERN.match(folder_name)

    if not match:
        return None, None

    person_id = match.group("person_id")
    deleted_at = None

    try:
        deleted_at = datetime.strptime(
            (
                match.group("date")
                + "_"
                + match.group("clock")
                + "_"
                + match.group("microseconds")
            ),
            "%Y%m%d_%H%M%S_%f",
        ).isoformat(timespec="seconds")
    except ValueError:
        pass

    return person_id, deleted_at


def find_person_in_people_backups(person_id):
    backup_files = sorted(
        BACKUP_DIR.glob("people_*.json"),
        reverse=True,
    )

    for backup_file in backup_files:
        try:
            with open(
                backup_file,
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            if person_id in data:
                return data[person_id]

        except Exception:
            continue

    return None


def get_deleted_profile_info(folder):
    manifest_file = folder / "restore_info.json"
    manifest = None

    if manifest_file.exists():
        try:
            with open(
                manifest_file,
                "r",
                encoding="utf-8",
            ) as file:
                manifest = json.load(file)
        except Exception:
            manifest = None

    parsed_person_id, parsed_deleted_at = parse_deleted_folder_name(
        folder.name
    )

    person_id = (
        manifest.get("person_id")
        if manifest
        else parsed_person_id
    )

    if not person_id:
        return None

    metadata = find_person_in_people_backups(person_id) or {}

    name = (
        (manifest.get("name") if manifest else None)
        or metadata.get("name")
        or person_id.replace("_", " ")
    )

    class_name = (
        (manifest.get("class") if manifest else None)
        or metadata.get("class", "")
    )

    deleted_at = (
        manifest.get("deleted_at")
        if manifest
        else parsed_deleted_at
    )

    image_files = [
        path
        for path in folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    ]

    return {
        "backup_name": folder.name,
        "person_id": person_id,
        "name": name,
        "class": class_name,
        "deleted_at": deleted_at,
        "images": len(image_files),
        "restorable": (
            len(image_files) >= MIN_VALID_IMAGES
            and bool(class_name)
        ),
    }


def write_restore_manifest(
    folder,
    person_id,
    name,
    class_name,
    deleted_at,
):
    manifest = {
        "person_id": person_id,
        "name": name,
        "class": class_name,
        "deleted_at": deleted_at,
    }

    with open(
        folder / "restore_info.json",
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            manifest,
            file,
            indent=2,
            ensure_ascii=False,
        )


def get_safe_deleted_folder(backup_name):
    base = DELETED_DATASET_BACKUP_DIR.resolve()
    candidate = (
        DELETED_DATASET_BACKUP_DIR / backup_name
    ).resolve()

    if candidate.parent != base:
        raise HTTPException(
            status_code=400,
            detail="Invalid deleted profile backup.",
        )

    if not candidate.exists() or not candidate.is_dir():
        raise HTTPException(
            status_code=404,
            detail="Deleted profile backup not found.",
        )

    return candidate


def build_face_profile_from_folder(folder):
    embeddings = []
    skipped_images = []

    image_files = sorted([
        path
        for path in folder.iterdir()
        if (
            path.is_file()
            and path.suffix.lower() in IMAGE_EXTENSIONS
        )
    ])

    for image_file in image_files:
        try:
            image = cv2.imread(str(image_file))

            if image is None:
                skipped_images.append({
                    "file": image_file.name,
                    "reason": "Could not read image",
                })
                continue

            faces = camera_service.app.get(image)

            if len(faces) == 0:
                skipped_images.append({
                    "file": image_file.name,
                    "reason": "No face detected",
                })
                continue

            if len(faces) > 1:
                skipped_images.append({
                    "file": image_file.name,
                    "reason": "Multiple faces detected",
                })
                continue

            embedding = np.asarray(
                faces[0].normed_embedding,
                dtype=np.float32,
            )

            embedding_norm = np.linalg.norm(embedding)

            if (
                embedding_norm == 0
                or not np.isfinite(embedding).all()
            ):
                skipped_images.append({
                    "file": image_file.name,
                    "reason": "Invalid face embedding",
                })
                continue

            embeddings.append(
                embedding / embedding_norm
            )

        except Exception as error:
            skipped_images.append({
                "file": image_file.name,
                "reason": str(error),
            })

    if len(embeddings) < MIN_VALID_IMAGES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "This deleted profile does not have enough "
                    "valid face photos to restore safely."
                ),
                "required": MIN_VALID_IMAGES,
                "valid": len(embeddings),
                "skipped": skipped_images,
            },
        )

    embedding_matrix = np.stack(embeddings)

    centroid = np.mean(
        embedding_matrix,
        axis=0,
    )

    centroid_norm = np.linalg.norm(centroid)

    if centroid_norm == 0:
        raise HTTPException(
            status_code=500,
            detail="Could not rebuild the deleted face profile.",
        )

    centroid = (
        centroid / centroid_norm
    ).astype(np.float32)

    return {
        "embeddings": embeddings,
        "embedding_matrix": embedding_matrix,
        "centroid": centroid,
        "valid_images": len(embeddings),
        "skipped_images": skipped_images,
    }


@app.get("/")
def home():
    return {
        "message": "Face Recognition System API is running"
    }


@app.get("/attendance")
def get_attendance():
    if not ATTENDANCE_FILE.exists():
        return {
            "count": 0,
            "attendance": [],
        }

    records = []

    with open(
        ATTENDANCE_FILE,
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            records.append({
                "person_id": row["Person ID"],
                "name": row["Name"],
                "class": row["Class"],
                "date": row["Date"],
                "time": row["Time"],
            })

    records.reverse()

    return {
        "count": len(records),
        "attendance": records,
    }


@app.get("/students")
def get_students():
    students = get_registered_people()

    return {
        "count": len(students),
        "students": students,
    }


@app.get("/students/deleted")
def get_deleted_students():
    profiles = []

    for folder in sorted(
        DELETED_DATASET_BACKUP_DIR.iterdir(),
        key=lambda path: path.name,
        reverse=True,
    ):
        if not folder.is_dir():
            continue

        info = get_deleted_profile_info(folder)

        if info:
            profiles.append(info)

    return {
        "count": len(profiles),
        "deleted_profiles": profiles,
    }


@app.post(
    "/students/deleted/{backup_name}/restore"
)
def restore_deleted_student(
    backup_name: str
):
    if camera_service.is_running():
        raise HTTPException(
            status_code=409,
            detail=(
                "Stop face recognition before "
                "restoring a deleted person."
            ),
        )

    backup_folder = get_safe_deleted_folder(
        backup_name
    )

    info = get_deleted_profile_info(
        backup_folder
    )

    if not info:
        raise HTTPException(
            status_code=400,
            detail="Could not read deleted profile metadata.",
        )

    person_id = info["person_id"]
    name = info["name"].strip()
    class_name = (
        info["class"].strip()
        if info["class"]
        else ""
    )

    if not class_name:
        raise HTTPException(
            status_code=400,
            detail=(
                "The deleted profile's class could not be "
                "recovered from backup."
            ),
        )

    try:
        people = load_people()
        database = load_face_database()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load current "
                f"registration data: {error}"
            ),
        )

    if (
        person_id in people
        or person_id in database
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                "This person is already active "
                "in the recognition system."
            ),
        )

    person_folder = TRAIN_DATASET / person_id

    if person_folder.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                "An active dataset folder with "
                "this Person ID already exists."
            ),
        )

    rebuilt = build_face_profile_from_folder(
        backup_folder
    )

    duplicate_result = check_duplicate_identity(
        rebuilt["embeddings"],
        rebuilt["centroid"],
        database,
    )

    if (
        duplicate_result
        and duplicate_result["duplicate"]
    ):
        existing_person_id = duplicate_result["person_id"]

        existing_name = (
            people
            .get(existing_person_id, {})
            .get("name", existing_person_id)
        )

        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "This deleted face appears to already be "
                    "registered under another active profile."
                ),
                "existing_person_id": existing_person_id,
                "existing_name": existing_name,
                "centroid_similarity": (
                    duplicate_result[
                        "centroid_similarity"
                    ]
                ),
            },
        )

    model_backup = None
    people_backup = None

    manifest_data = {
        "person_id": person_id,
        "name": name,
        "class": class_name,
        "deleted_at": info.get("deleted_at"),
    }

    try:
        model_backup, people_backup = create_backups()

        manifest_file = (
            backup_folder
            / "restore_info.json"
        )

        if manifest_file.exists():
            manifest_file.unlink()

        shutil.move(
            str(backup_folder),
            str(person_folder),
        )

        people[person_id] = {
            "name": name,
            "class": class_name,
        }

        database[person_id] = {
            "embedding": rebuilt["centroid"],
            "training_embeddings": (
                rebuilt["embedding_matrix"]
            ),
        }

        save_people_atomic(people)
        save_model_atomic(database)
        reload_recognition_data()

    except Exception as error:
        restore_backups(
            model_backup,
            people_backup,
        )

        try:
            if (
                person_folder.exists()
                and not backup_folder.exists()
            ):
                shutil.move(
                    str(person_folder),
                    str(backup_folder),
                )

            if backup_folder.exists():
                write_restore_manifest(
                    backup_folder,
                    manifest_data["person_id"],
                    manifest_data["name"],
                    manifest_data["class"],
                    manifest_data["deleted_at"],
                )

        except Exception:
            pass

        reload_recognition_data()

        raise HTTPException(
            status_code=500,
            detail=(
                "Restore failed. Previous active data was "
                f"restored. Error: {error}"
            ),
        )

    return {
        "success": True,
        "message": "Deleted person restored successfully",
        "person": {
            "person_id": person_id,
            "name": name,
            "class": class_name,
        },
        "images": {
            "valid": rebuilt["valid_images"],
            "skipped": len(
                rebuilt["skipped_images"]
            ),
        },
        "total_registered": len(people),
    }


@app.put("/students/{person_id}")
def update_student(
    person_id: str,
    request: UpdateStudentRequest,
):
    if camera_service.is_running():
        raise HTTPException(
            status_code=409,
            detail=(
                "Stop face recognition before "
                "editing a registered person."
            ),
        )

    name = request.name.strip()
    class_name = request.class_name.strip()

    if len(name) < 2:
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid name.",
        )

    if not class_name:
        raise HTTPException(
            status_code=400,
            detail="Please enter a class.",
        )

    try:
        people = load_people()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load registered "
                f"people: {error}"
            ),
        )

    if person_id not in people:
        raise HTTPException(
            status_code=404,
            detail="Registered person not found.",
        )

    old_data = people[person_id].copy()

    model_backup = None
    people_backup = None

    try:
        model_backup, people_backup = create_backups()

        people[person_id] = {
            "name": name,
            "class": class_name,
        }

        save_people_atomic(people)
        reload_recognition_data()

    except Exception as error:
        restore_backups(
            model_backup,
            people_backup,
        )

        reload_recognition_data()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not update person. Previous data "
                f"was restored. Error: {error}"
            ),
        )

    return {
        "success": True,
        "message": "Person updated successfully",
        "person": {
            "person_id": person_id,
            "name": name,
            "class": class_name,
        },
        "previous": {
            "name": old_data.get("name", ""),
            "class": old_data.get("class", ""),
        },
    }


@app.delete("/students/{person_id}")
def delete_student(
    person_id: str
):
    if camera_service.is_running():
        raise HTTPException(
            status_code=409,
            detail=(
                "Stop face recognition before "
                "deleting a registered person."
            ),
        )

    try:
        people = load_people()
        database = load_face_database()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load registration "
                f"data: {error}"
            ),
        )

    exists_in_people = person_id in people
    exists_in_database = person_id in database

    if (
        not exists_in_people
        and not exists_in_database
    ):
        raise HTTPException(
            status_code=404,
            detail="Registered person not found.",
        )

    person_info = people.get(
        person_id,
        {}
    )

    person_name = person_info.get(
        "name",
        person_id
    )

    person_class = person_info.get(
        "class",
        ""
    )

    person_folder = TRAIN_DATASET / person_id

    model_backup = None
    people_backup = None
    dataset_backup = None

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"
    )

    deleted_at = datetime.now().isoformat(
        timespec="seconds"
    )

    try:
        model_backup, people_backup = create_backups()

        if person_folder.exists():
            dataset_backup = (
                DELETED_DATASET_BACKUP_DIR
                / f"{person_id}_{timestamp}"
            )

            shutil.move(
                str(person_folder),
                str(dataset_backup),
            )

            write_restore_manifest(
                dataset_backup,
                person_id,
                person_name,
                person_class,
                deleted_at,
            )

        if person_id in people:
            del people[person_id]

        if person_id in database:
            del database[person_id]

        save_people_atomic(people)
        save_model_atomic(database)
        reload_recognition_data()

    except Exception as error:
        restore_backups(
            model_backup,
            people_backup,
        )

        if (
            dataset_backup
            and dataset_backup.exists()
        ):
            manifest_file = (
                dataset_backup
                / "restore_info.json"
            )

            if manifest_file.exists():
                try:
                    manifest_file.unlink()
                except OSError:
                    pass

            if person_folder.exists():
                shutil.rmtree(
                    person_folder,
                    ignore_errors=True,
                )

            shutil.move(
                str(dataset_backup),
                str(person_folder),
            )

        reload_recognition_data()

        raise HTTPException(
            status_code=500,
            detail=(
                "Could not delete person. Previous data "
                f"was restored. Error: {error}"
            ),
        )

    return {
        "success": True,
        "message": "Person deleted successfully",
        "deleted_person": {
            "person_id": person_id,
            "name": person_name,
            "class": person_class,
        },
        "attendance_history_preserved": True,
        "dataset_backup_created": (
            dataset_backup is not None
        ),
        "remaining_registered": len(people),
    }


@app.post("/students/register")
async def register_student(
    name: str = Form(...),
    class_name: str = Form(...),
    files: list[UploadFile] = File(...),
):
    if camera_service.is_running():
        raise HTTPException(
            status_code=409,
            detail=(
                "Stop face recognition before "
                "registering a new person."
            ),
        )

    name = name.strip()
    class_name = class_name.strip()

    if len(name) < 2:
        raise HTTPException(
            status_code=400,
            detail="Please enter a valid name.",
        )

    if not class_name:
        raise HTTPException(
            status_code=400,
            detail="Please enter a class.",
        )

    if len(files) < MIN_VALID_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Upload at least {MIN_VALID_IMAGES} "
                "face photos."
            ),
        )

    if len(files) > MAX_UPLOAD_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum {MAX_UPLOAD_IMAGES} photos "
                "can be uploaded at once."
            ),
        )

    try:
        person_id = create_person_id(name)
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error),
        )

    try:
        people = load_people()
        database = load_face_database()
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=(
                "Could not load current registration "
                f"data: {error}"
            ),
        )

    existing_ids = {
        current_id.lower(): current_id
        for current_id in people.keys()
    }

    if person_id.lower() in existing_ids:
        existing_id = existing_ids[
            person_id.lower()
        ]

        raise HTTPException(
            status_code=409,
            detail=(
                "A person with this ID "
                f"already exists: {existing_id}"
            ),
        )

    if person_id in database:
        raise HTTPException(
            status_code=409,
            detail=(
                "This Person ID already exists "
                "in the face model."
            ),
        )

    embeddings = []
    valid_images = []
    valid_filenames = []
    skipped_images = []

    max_bytes = (
        MAX_IMAGE_SIZE_MB
        * 1024
        * 1024
    )

    for index, upload in enumerate(
        files,
        start=1,
    ):
        filename = (
            upload.filename
            or f"image_{index}"
        )

        try:
            content = await upload.read()

            if not content:
                skipped_images.append({
                    "file": filename,
                    "reason": "Empty file",
                })
                continue

            if len(content) > max_bytes:
                skipped_images.append({
                    "file": filename,
                    "reason": (
                        "Image larger than "
                        f"{MAX_IMAGE_SIZE_MB} MB"
                    ),
                })
                continue

            numpy_data = np.frombuffer(
                content,
                dtype=np.uint8,
            )

            image = cv2.imdecode(
                numpy_data,
                cv2.IMREAD_COLOR,
            )

            if image is None:
                skipped_images.append({
                    "file": filename,
                    "reason": "Could not read image",
                })
                continue

            faces = camera_service.app.get(
                image
            )

            if len(faces) == 0:
                skipped_images.append({
                    "file": filename,
                    "reason": "No face detected",
                })
                continue

            if len(faces) > 1:
                skipped_images.append({
                    "file": filename,
                    "reason": "Multiple faces detected",
                })
                continue

            embedding = np.asarray(
                faces[0].normed_embedding,
                dtype=np.float32,
            )

            embedding_norm = np.linalg.norm(
                embedding
            )

            if (
                embedding_norm == 0
                or not np.isfinite(embedding).all()
            ):
                skipped_images.append({
                    "file": filename,
                    "reason": "Invalid face embedding",
                })
                continue

            embedding = (
                embedding / embedding_norm
            )

            embeddings.append(
                embedding
            )

            valid_images.append(
                image.copy()
            )

            valid_filenames.append(
                filename
            )

        except Exception as error:
            skipped_images.append({
                "file": filename,
                "reason": str(error),
            })

    if len(embeddings) < MIN_VALID_IMAGES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Not enough valid face photos.",
                "required": MIN_VALID_IMAGES,
                "valid": len(embeddings),
                "skipped": skipped_images,
            },
        )

    # --------------------------------------------------
    # SAME-PERSON PHOTO CONSISTENCY CHECK
    # --------------------------------------------------

    consistency = check_registration_consistency(
        embeddings,
        valid_filenames,
    )

    if not consistency["consistent"]:
        inconsistent_files = consistency[
            "inconsistent_files"
        ]

        shown_files = ", ".join(
            inconsistent_files[:6]
        )

        if len(inconsistent_files) > 6:
            shown_files += (
                f" and {len(inconsistent_files) - 6} more"
            )

        message = (
            "Uploaded photos are not consistent enough "
            "to create one identity. "
            f"{consistency['consistent_count']} of "
            f"{len(embeddings)} valid photos match the "
            "dominant face profile; "
            f"{consistency['inconsistent_count']} appear "
            "inconsistent."
        )

        if shown_files:
            message += (
                f" Check or replace: {shown_files}."
            )

        message += (
            " Please use clear photos of the same person "
            "only, then try again."
        )

        raise HTTPException(
            status_code=400,
            detail={
                "message": message,
                "consistent": consistency[
                    "consistent_count"
                ],
                "inconsistent": consistency[
                    "inconsistent_count"
                ],
                "total_valid": len(embeddings),
                "inconsistent_files": inconsistent_files,
                "minimum_centroid_similarity": (
                    consistency[
                        "minimum_centroid_similarity"
                    ]
                ),
                "average_centroid_similarity": (
                    consistency[
                        "average_centroid_similarity"
                    ]
                ),
                "minimum_neighbor_ratio": (
                    consistency[
                        "minimum_neighbor_ratio"
                    ]
                ),
            },
        )

    embedding_matrix = np.stack(
        embeddings
    )

    centroid = np.mean(
        embedding_matrix,
        axis=0,
    )

    centroid_norm = np.linalg.norm(
        centroid
    )

    if centroid_norm == 0:
        raise HTTPException(
            status_code=500,
            detail="Could not create face profile.",
        )

    centroid = (
        centroid / centroid_norm
    ).astype(np.float32)

    duplicate_result = check_duplicate_identity(
        embeddings,
        centroid,
        database,
    )

    if (
        duplicate_result
        and duplicate_result["duplicate"]
    ):
        existing_person_id = duplicate_result["person_id"]

        existing_name = (
            people
            .get(existing_person_id, {})
            .get("name", existing_person_id)
        )

        raise HTTPException(
            status_code=409,
            detail={
                "message": (
                    "This face appears to already be registered."
                ),
                "existing_person_id": existing_person_id,
                "existing_name": existing_name,
                "centroid_similarity": (
                    duplicate_result[
                        "centroid_similarity"
                    ]
                ),
                "matching_photos": (
                    duplicate_result[
                        "matching_photos"
                    ]
                ),
                "total_photos": (
                    duplicate_result[
                        "total_photos"
                    ]
                ),
                "match_ratio": (
                    duplicate_result[
                        "match_ratio"
                    ]
                ),
            },
        )

    closest_person = None
    closest_similarity = None

    for existing_id, existing_data in database.items():
        existing_embedding = existing_data.get(
            "embedding"
        )

        if existing_embedding is None:
            continue

        similarity = calculate_similarity(
            centroid,
            existing_embedding,
        )

        if (
            closest_similarity is None
            or similarity > closest_similarity
        ):
            closest_similarity = similarity
            closest_person = existing_id

    database[person_id] = {
        "embedding": centroid,
        "training_embeddings": embedding_matrix,
    }

    people[person_id] = {
        "name": name,
        "class": class_name,
    }

    person_folder = TRAIN_DATASET / person_id

    if person_folder.exists():
        raise HTTPException(
            status_code=409,
            detail=(
                "A dataset folder for this "
                "Person ID already exists."
            ),
        )

    model_backup = None
    people_backup = None

    try:
        model_backup, people_backup = create_backups()

        person_folder.mkdir(
            parents=True,
            exist_ok=False,
        )

        for index, image in enumerate(
            valid_images,
            start=1,
        ):
            output_file = (
                person_folder
                / f"{index:03d}.jpg"
            )

            saved = cv2.imwrite(
                str(output_file),
                image,
            )

            if not saved:
                raise RuntimeError(
                    "Could not save "
                    f"{output_file.name}"
                )

        save_people_atomic(people)
        save_model_atomic(database)
        reload_recognition_data()

    except Exception as error:
        if person_folder.exists():
            shutil.rmtree(
                person_folder,
                ignore_errors=True,
            )

        restore_backups(
            model_backup,
            people_backup,
        )

        reload_recognition_data()

        raise HTTPException(
            status_code=500,
            detail=(
                "Registration failed. Previous data "
                f"was restored. Error: {error}"
            ),
        )

    closest_data = None

    if closest_person is not None:
        closest_data = {
            "person_id": closest_person,
            "similarity": round(
                closest_similarity,
                4
            ),
        }

    return {
        "success": True,
        "message": "Person registered successfully",
        "person": {
            "person_id": person_id,
            "name": name,
            "class": class_name,
        },
        "images": {
            "uploaded": len(files),
            "valid": len(embeddings),
            "skipped": len(skipped_images),
        },
        "skipped_images": skipped_images,
        "consistency": {
            "passed": True,
            "minimum_centroid_similarity": (
                consistency[
                    "minimum_centroid_similarity"
                ]
            ),
            "average_centroid_similarity": (
                consistency[
                    "average_centroid_similarity"
                ]
            ),
            "minimum_neighbor_ratio": (
                consistency[
                    "minimum_neighbor_ratio"
                ]
            ),
        },
        "closest_existing_profile": closest_data,
        "total_registered": len(people),
    }


@app.post("/recognition/start")
def start_recognition():
    if camera_service.is_running():
        return {
            "success": False,
            "running": True,
            "message": "Recognition is already running",
        }

    started = camera_service.start()

    if not started:
        return {
            "success": False,
            "running": False,
            "message": "Could not open camera",
        }

    return {
        "success": True,
        "running": True,
        "message": "Recognition started",
    }


@app.post("/recognition/stop")
def stop_recognition():
    if not camera_service.is_running():
        return {
            "success": False,
            "running": False,
            "message": "Recognition is not running",
        }

    camera_service.stop()

    return {
        "success": True,
        "running": False,
        "message": "Recognition stopped",
    }


@app.get("/recognition/status")
def recognition_status():
    return {
        "running": camera_service.is_running()
    }


@app.get("/recognition/result")
def recognition_result():
    if not camera_service.is_running():
        return {
            "status": "stopped",
            "recognized": False,
            "name": None,
            "class": None,
            "person_id": None,
            "similarity": None,
            "margin": None,
            "confirmation": 0,
            "confirmation_required": 8,
            "attendance_status": None,
        }

    return camera_service.get_latest_result()


def generate_video():
    while True:
        if not camera_service.is_running():
            time.sleep(0.1)
            continue

        frame = camera_service.get_frame()

        if frame is None:
            time.sleep(0.03)
            continue

        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n"
            + frame
            + b"\r\n"
        )


@app.get("/video-feed")
def video_feed():
    return StreamingResponse(
        generate_video(),
        media_type=(
            "multipart/x-mixed-replace; boundary=frame"
        ),
    )
