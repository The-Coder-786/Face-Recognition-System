from pathlib import Path
from datetime import datetime
import csv


ROOT = Path(__file__).resolve().parent.parent

ATTENDANCE_DIR = ROOT / "attendance"
ATTENDANCE_FILE = ATTENDANCE_DIR / "attendance.csv"

ATTENDANCE_DIR.mkdir(
    parents=True,
    exist_ok=True
)


def mark_attendance(person_id, name, person_class):

    now = datetime.now()

    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M:%S")

    # Create file if it does not exist
    if not ATTENDANCE_FILE.exists():

        with open(
            ATTENDANCE_FILE,
            "w",
            newline="",
            encoding="utf-8"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "Person ID",
                "Name",
                "Class",
                "Date",
                "Time"
            ])

    # Check if this person already has attendance today
    with open(
        ATTENDANCE_FILE,
        "r",
        newline="",
        encoding="utf-8"
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:

            if (
                row["Person ID"] == person_id
                and
                row["Date"] == date
            ):
                return {
                    "saved": False,
                    "message": "Attendance already marked today"
                }

    # Save attendance
    with open(
        ATTENDANCE_FILE,
        "a",
        newline="",
        encoding="utf-8"
    ) as file:

        writer = csv.writer(file)

        writer.writerow([
            person_id,
            name,
            person_class,
            date,
            time
        ])

    return {
        "saved": True,
        "message": "Attendance marked successfully",
        "date": date,
        "time": time
    }