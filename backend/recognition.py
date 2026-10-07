from pathlib import Path
import json
import pickle
import numpy as np


# --------------------------------------------------
# PATHS
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

MODEL_PATH = (
    ROOT
    / "models"
    / "face_model.pkl"
)

PEOPLE_FILE = (
    ROOT
    / "models"
    / "people.json"
)


# --------------------------------------------------
# RECOGNITION SETTINGS
# --------------------------------------------------

SIMILARITY_THRESHOLD = 0.60
MARGIN_THRESHOLD = 0.15


# --------------------------------------------------
# LOAD FACE DATABASE
# --------------------------------------------------

def load_database():

    if not MODEL_PATH.exists():
        print(
            "WARNING: face_model.pkl not found."
        )

        return {}

    with open(
        MODEL_PATH,
        "rb"
    ) as file:

        return pickle.load(file)


# --------------------------------------------------
# LOAD REGISTERED PEOPLE
# --------------------------------------------------

def load_person_info():

    if not PEOPLE_FILE.exists():
        print(
            "WARNING: people.json not found."
        )

        return {}

    try:

        with open(
            PEOPLE_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            return json.load(file)

    except (
        json.JSONDecodeError,
        OSError
    ) as error:

        print(
            "Could not load people.json:",
            error
        )

        return {}


# --------------------------------------------------
# INITIAL DATA
# --------------------------------------------------

DATABASE = load_database()

PERSON_INFO = load_person_info()


# --------------------------------------------------
# RELOAD RECOGNITION DATA
# --------------------------------------------------

def reload_recognition_data():

    global DATABASE
    global PERSON_INFO

    DATABASE = load_database()

    PERSON_INFO = load_person_info()

    print(
        "Recognition database reloaded."
    )

    print(
        "Registered face profiles:",
        len(DATABASE)
    )

    print(
        "Registered people:",
        len(PERSON_INFO)
    )


# --------------------------------------------------
# GET REGISTERED PEOPLE
# --------------------------------------------------

def get_registered_people():

    people = load_person_info()

    students = []

    for person_id, info in people.items():

        students.append({
            "person_id": person_id,
            "name": info.get(
                "name",
                person_id
            ),
            "class": info.get(
                "class",
                ""
            ),
        })

    return students


# --------------------------------------------------
# COSINE SIMILARITY
# --------------------------------------------------

def cosine_similarity(
    embedding1,
    embedding2
):

    norm1 = np.linalg.norm(
        embedding1
    )

    norm2 = np.linalg.norm(
        embedding2
    )

    if (
        norm1 == 0
        or norm2 == 0
    ):

        return 0.0

    return float(
        np.dot(
            embedding1,
            embedding2
        )
        /
        (
            norm1
            * norm2
        )
    )


# --------------------------------------------------
# RECOGNIZE FACE
# --------------------------------------------------

def recognize_face(
    face_embedding
):

    # No registered faces
    if not DATABASE:

        return {
            "recognized": False,
            "name": "Unknown",
            "class": None,
            "person_id": None,
            "similarity": 0.0,
            "margin": 0.0,
        }

    scores = {}

    for person_id, data in DATABASE.items():

        embedding = data.get(
            "embedding"
        )

        if embedding is None:
            continue

        score = cosine_similarity(
            face_embedding,
            embedding
        )

        scores[person_id] = score

    # Nothing valid to compare against
    if not scores:

        return {
            "recognized": False,
            "name": "Unknown",
            "class": None,
            "person_id": None,
            "similarity": 0.0,
            "margin": 0.0,
        }

    ranked = sorted(
        scores.items(),
        key=lambda item: item[1],
        reverse=True
    )

    best_person = ranked[0][0]
    best_score = ranked[0][1]

    # If there is more than one person,
    # calculate normal top-1 vs top-2 margin.
    if len(ranked) > 1:

        second_score = (
            ranked[1][1]
        )

        margin = (
            best_score
            - second_score
        )

    else:

        # Only one identity exists.
        # Similarity threshold still applies.
        margin = 1.0

    accepted = (
        best_score
        >= SIMILARITY_THRESHOLD
        and
        margin
        >= MARGIN_THRESHOLD
    )

    # Recognition confidence failed
    if not accepted:

        return {
            "recognized": False,
            "name": "Unknown",
            "class": None,
            "person_id": None,
            "similarity": round(
                best_score,
                4
            ),
            "margin": round(
                margin,
                4
            ),
        }

    # Face exists in model but metadata
    # is missing from people.json.
    if best_person not in PERSON_INFO:

        print(
            "WARNING:",
            best_person,
            "exists in face model but not in people.json"
        )

        return {
            "recognized": False,
            "name": "Unknown",
            "class": None,
            "person_id": None,
            "similarity": round(
                best_score,
                4
            ),
            "margin": round(
                margin,
                4
            ),
        }

    info = PERSON_INFO[
        best_person
    ]

    return {
        "recognized": True,
        "name": info.get(
            "name",
            best_person
        ),
        "class": info.get(
            "class",
            ""
        ),
        "person_id": best_person,
        "similarity": round(
            best_score,
            4
        ),
        "margin": round(
            margin,
            4
        ),
    }