import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [attendance, setAttendance] = useState([]);
  const [students, setStudents] = useState([]);
  const [deletedStudents, setDeletedStudents] = useState([]);
  const [loading, setLoading] = useState(true);

  const [recognitionRunning, setRecognitionRunning] =
    useState(false);

  const [recognitionResult, setRecognitionResult] =
    useState(null);

  const [activePage, setActivePage] =
    useState("dashboard");

  const [attendanceSearch, setAttendanceSearch] =
    useState("");

  const [attendanceDate, setAttendanceDate] =
    useState("");

  const [peopleSearch, setPeopleSearch] =
    useState("");

  const [registerName, setRegisterName] =
    useState("");

  const [registerClass, setRegisterClass] =
    useState("");

  const [registerFiles, setRegisterFiles] =
    useState([]);

  const [registerPreviews, setRegisterPreviews] =
    useState([]);

  const [registering, setRegistering] =
    useState(false);

  const [
    registrationFeedback,
    setRegistrationFeedback,
  ] = useState(null);

  const [fileInputKey, setFileInputKey] =
    useState(0);

  const [editingStudent, setEditingStudent] =
    useState(null);

  const [editName, setEditName] =
    useState("");

  const [editClass, setEditClass] =
    useState("");

  const [editSaving, setEditSaving] =
    useState(false);

  const [deletingStudent, setDeletingStudent] =
    useState(null);

  const [deleteSaving, setDeleteSaving] =
    useState(false);

  const [restoringStudent, setRestoringStudent] =
    useState(null);

  const [restoreSaving, setRestoreSaving] =
    useState(false);

  const [
    peopleActionFeedback,
    setPeopleActionFeedback,
  ] = useState(null);

  // ==================================================
  // LOAD DATA
  // ==================================================

  const fetchData = async () => {
    try {
      const [
        attendanceResponse,
        studentsResponse,
        deletedResponse,
      ] = await Promise.all([
        fetch(`${API_URL}/attendance`),
        fetch(`${API_URL}/students`),
        fetch(`${API_URL}/students/deleted`),
      ]);

      const attendanceData =
        await attendanceResponse.json();

      const studentsData =
        await studentsResponse.json();

      const deletedData =
        await deletedResponse.json();

      setAttendance(
        attendanceData.attendance || []
      );

      setStudents(
        studentsData.students || []
      );

      setDeletedStudents(
        deletedData.deleted_profiles || []
      );
    } catch (error) {
      console.error(
        "Could not connect to backend:",
        error
      );
    } finally {
      setLoading(false);
    }
  };

  // ==================================================
  // MAIN POLLING
  // ==================================================

  useEffect(() => {
    const updateDashboard = async () => {
      await fetchData();

      try {
        const response = await fetch(
          `${API_URL}/recognition/status`
        );

        const data =
          await response.json();

        setRecognitionRunning(
          data.running
        );
      } catch (error) {
        console.error(
          "Could not get recognition status:",
          error
        );
      }
    };

    updateDashboard();

    const interval = setInterval(
      updateDashboard,
      3000
    );

    return () =>
      clearInterval(interval);
  }, []);

  // ==================================================
  // LIVE RESULT POLLING
  // ==================================================

  useEffect(() => {
    if (!recognitionRunning) {
      setRecognitionResult(null);
      return;
    }

    const fetchRecognitionResult =
      async () => {
        try {
          const response = await fetch(
            `${API_URL}/recognition/result`
          );

          const data =
            await response.json();

          setRecognitionResult(data);
        } catch (error) {
          console.error(
            "Could not get recognition result:",
            error
          );
        }
      };

    fetchRecognitionResult();

    const interval = setInterval(
      fetchRecognitionResult,
      500
    );

    return () =>
      clearInterval(interval);
  }, [recognitionRunning]);

  // ==================================================
  // PHOTO PREVIEWS
  // ==================================================

  useEffect(() => {
    const previews = registerFiles
      .map((file) => ({
        name: file.name,
        url: URL.createObjectURL(file),
      }));

    setRegisterPreviews(previews);

    return () => {
      previews.forEach((preview) => {
        URL.revokeObjectURL(
          preview.url
        );
      });
    };
  }, [registerFiles]);

  // ==================================================
  // START / STOP RECOGNITION
  // ==================================================

  const handleRecognition = async () => {
    try {
      const endpoint =
        recognitionRunning
          ? "/recognition/stop"
          : "/recognition/start";

      const response = await fetch(
        `${API_URL}${endpoint}`,
        {
          method: "POST",
        }
      );

      const data =
        await response.json();

      setRecognitionRunning(
        data.running
      );

      fetchData();
    } catch (error) {
      console.error(
        "Recognition control error:",
        error
      );
    }
  };

  // ==================================================
  // FILTERS
  // ==================================================

  const getFilteredAttendance = () => {
    return attendance.filter(
      (record) => {
        const search =
          attendanceSearch
            .trim()
            .toLowerCase();

        const name =
          record.name?.toLowerCase() ||
          "";

        const personClass =
          record.class?.toLowerCase() ||
          "";

        const matchesSearch =
          search === "" ||
          name.includes(search) ||
          personClass.includes(search);

        const matchesDate =
          attendanceDate === "" ||
          record.date ===
            attendanceDate;

        return (
          matchesSearch &&
          matchesDate
        );
      }
    );
  };

  const getFilteredStudents = () => {
    const search =
      peopleSearch
        .trim()
        .toLowerCase();

    return students.filter(
      (student) => {
        const name =
          student.name?.toLowerCase() ||
          "";

        const personClass =
          student.class?.toLowerCase() ||
          "";

        const personId =
          student.person_id?.toLowerCase() ||
          "";

        return (
          search === "" ||
          name.includes(search) ||
          personClass.includes(search) ||
          personId.includes(search)
        );
      }
    );
  };

  // ==================================================
  // EXPORT ATTENDANCE
  // ==================================================

  const exportAttendanceCSV = () => {
    const records =
      getFilteredAttendance();

    if (records.length === 0) {
      alert(
        "No attendance records to export."
      );
      return;
    }

    const headers = [
      "Person ID",
      "Name",
      "Class",
      "Date",
      "Time",
      "Status",
    ];

    const rows = records.map(
      (record) => [
        record.person_id,
        record.name,
        record.class,
        record.date,
        record.time,
        "Present",
      ]
    );

    const escapeCSV = (value) => {
      const text =
        String(value ?? "");

      return `"${text.replace(
        /"/g,
        '""'
      )}"`;
    };

    const csvContent = [
      headers
        .map(escapeCSV)
        .join(","),

      ...rows.map((row) =>
        row
          .map(escapeCSV)
          .join(",")
      ),
    ].join("\n");

    const blob = new Blob(
      [csvContent],
      {
        type:
          "text/csv;charset=utf-8;",
      }
    );

    const url =
      URL.createObjectURL(blob);

    const link =
      document.createElement("a");

    link.href = url;

    link.download =
      `attendance-${
        attendanceDate || "all"
      }.csv`;

    document.body.appendChild(
      link
    );

    link.click();

    document.body.removeChild(
      link
    );

    URL.revokeObjectURL(url);
  };

  // ==================================================
  // REGISTRATION
  // ==================================================

  const handleRegisterFiles = (
    event
  ) => {
    const newFiles = Array.from(
      event.target.files || []
    );

    setRegistrationFeedback(null);

    if (newFiles.length === 0) {
      return;
    }

    setRegisterFiles((currentFiles) => {
      const combinedFiles = [
        ...currentFiles,
      ];

      const existingKeys = new Set(
        currentFiles.map(
          (file) =>
            `${file.name}|${file.size}|${file.lastModified}|${file.type}`
        )
      );

      let duplicateCount = 0;

      for (const file of newFiles) {
        const fileKey =
          `${file.name}|${file.size}|${file.lastModified}|${file.type}`;

        if (existingKeys.has(fileKey)) {
          duplicateCount += 1;
          continue;
        }

        if (combinedFiles.length >= 30) {
          break;
        }

        existingKeys.add(fileKey);
        combinedFiles.push(file);
      }

      const addedCount =
        combinedFiles.length -
        currentFiles.length;

      const couldNotAdd =
        newFiles.length -
        duplicateCount -
        addedCount;

      if (couldNotAdd > 0) {
        setRegistrationFeedback({
          type: "error",
          message:
            `Maximum 30 photos are allowed. ${couldNotAdd} photo(s) were not added.`,
        });
      }

      else if (duplicateCount > 0) {
        setRegistrationFeedback({
          type: "success",
          message:
            `${addedCount} new photo(s) added. ${duplicateCount} duplicate photo(s) were skipped.`,
        });
      }

      return combinedFiles;
    });

    // Reset the file input after each selection so the
    // user can choose photos from another folder next.
    setFileInputKey(
      (current) =>
        current + 1
    );
  };

  const removeRegisterFile = (
    indexToRemove
  ) => {
    if (registering) {
      return;
    }

    setRegisterFiles(
      (currentFiles) =>
        currentFiles.filter(
          (_, index) =>
            index !== indexToRemove
        )
    );

    setRegistrationFeedback(null);
  };

  const cancelRegistrationDraft = () => {
    if (registering) {
      return;
    }

    setRegisterName("");
    setRegisterClass("");
    setRegisterFiles([]);
    setRegistrationFeedback(null);

    setFileInputKey(
      (current) =>
        current + 1
    );
  };

  const handleRegisterPerson =
    async (event) => {
      event.preventDefault();

      setRegistrationFeedback(null);

      const name =
        registerName.trim();

      const personClass =
        registerClass.trim();

      if (recognitionRunning) {
        setRegistrationFeedback({
          type: "error",
          message:
            "Stop face recognition before registering a new person.",
        });
        return;
      }

      if (name.length < 2) {
        setRegistrationFeedback({
          type: "error",
          message:
            "Please enter a valid name.",
        });
        return;
      }

      if (!personClass) {
        setRegistrationFeedback({
          type: "error",
          message:
            "Please enter the person's class.",
        });
        return;
      }

      if (
        registerFiles.length < 8
      ) {
        setRegistrationFeedback({
          type: "error",
          message:
            "Please select at least 8 face photos.",
        });
        return;
      }

      if (
        registerFiles.length > 30
      ) {
        setRegistrationFeedback({
          type: "error",
          message:
            "Maximum 30 photos are allowed.",
        });
        return;
      }

      const formData =
        new FormData();

      formData.append(
        "name",
        name
      );

      formData.append(
        "class_name",
        personClass
      );

      registerFiles.forEach(
        (file) => {
          formData.append(
            "files",
            file
          );
        }
      );

      try {
        setRegistering(true);

        const response =
          await fetch(
            `${API_URL}/students/register`,
            {
              method: "POST",
              body: formData,
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          let message =
            "Registration failed.";

          if (
            typeof data.detail ===
            "string"
          ) {
            message =
              data.detail;
          }

          else if (
            data.detail?.message
          ) {
            message =
              data.detail.message;

            if (
              data.detail
                .existing_name
            ) {
              message =
                `This face is already registered as ${data.detail.existing_name}.`;

              if (
                data.detail
                  .centroid_similarity !==
                undefined
              ) {
                message +=
                  ` Similarity: ${data.detail.centroid_similarity.toFixed(
                    3
                  )}.`;
              }
            }

            else if (
              data.detail.valid !==
                undefined &&
              data.detail.required !==
                undefined
            ) {
              message +=
                ` Valid photos: ${data.detail.valid}/${data.detail.required}.`;
            }
          }

          setRegistrationFeedback({
            type: "error",
            message,
          });

          return;
        }

        setRegistrationFeedback({
          type: "success",
          message:
            `${data.person.name} was registered successfully with ` +
            `${data.images.valid} valid face photos.`,
        });

        setRegisterName("");
        setRegisterClass("");
        setRegisterFiles([]);

        setFileInputKey(
          (current) =>
            current + 1
        );

        await fetchData();

      } catch (error) {
        console.error(
          "Registration error:",
          error
        );

        setRegistrationFeedback({
          type: "error",
          message:
            "Could not connect to the registration API.",
        });
      } finally {
        setRegistering(false);
      }
    };

  // ==================================================
  // EDIT
  // ==================================================

  const openEditStudent = (
    student
  ) => {
    if (recognitionRunning) {
      setPeopleActionFeedback({
        type: "error",
        message:
          "Stop face recognition before editing a registered person.",
      });
      return;
    }

    setPeopleActionFeedback(null);
    setEditingStudent(student);
    setEditName(student.name);
    setEditClass(student.class);
  };

  const closeEditStudent = () => {
    if (editSaving) {
      return;
    }

    setEditingStudent(null);
    setEditName("");
    setEditClass("");
  };

  const handleUpdateStudent =
    async (event) => {
      event.preventDefault();

      if (!editingStudent) {
        return;
      }

      if (recognitionRunning) {
        setPeopleActionFeedback({
          type: "error",
          message:
            "Stop face recognition before editing a registered person.",
        });
        return;
      }

      const name =
        editName.trim();

      const personClass =
        editClass.trim();

      if (name.length < 2) {
        setPeopleActionFeedback({
          type: "error",
          message:
            "Please enter a valid name.",
        });
        return;
      }

      if (!personClass) {
        setPeopleActionFeedback({
          type: "error",
          message:
            "Please enter a class.",
        });
        return;
      }

      try {
        setEditSaving(true);
        setPeopleActionFeedback(null);

        const response =
          await fetch(
            `${API_URL}/students/${encodeURIComponent(
              editingStudent.person_id
            )}`,
            {
              method: "PUT",

              headers: {
                "Content-Type":
                  "application/json",
              },

              body: JSON.stringify({
                name,
                class_name:
                  personClass,
              }),
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            typeof data.detail ===
              "string"
              ? data.detail
              : "Could not update person."
          );
        }

        setPeopleActionFeedback({
          type: "success",
          message:
            `${data.person.name} was updated successfully.`,
        });

        setEditingStudent(null);
        setEditName("");
        setEditClass("");

        await fetchData();

      } catch (error) {
        setPeopleActionFeedback({
          type: "error",
          message:
            error.message ||
            "Could not update registered person.",
        });
      } finally {
        setEditSaving(false);
      }
    };

  // ==================================================
  // DELETE
  // ==================================================

  const openDeleteStudent = (
    student
  ) => {
    if (recognitionRunning) {
      setPeopleActionFeedback({
        type: "error",
        message:
          "Stop face recognition before deleting a registered person.",
      });
      return;
    }

    setPeopleActionFeedback(null);
    setDeletingStudent(student);
  };

  const closeDeleteStudent =
    () => {
      if (deleteSaving) {
        return;
      }

      setDeletingStudent(null);
    };

  const handleDeleteStudent =
    async () => {
      if (!deletingStudent) {
        return;
      }

      if (recognitionRunning) {
        setPeopleActionFeedback({
          type: "error",
          message:
            "Stop face recognition before deleting a registered person.",
        });
        return;
      }

      try {
        setDeleteSaving(true);
        setPeopleActionFeedback(null);

        const response =
          await fetch(
            `${API_URL}/students/${encodeURIComponent(
              deletingStudent.person_id
            )}`,
            {
              method: "DELETE",
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          throw new Error(
            typeof data.detail ===
              "string"
              ? data.detail
              : "Could not delete person."
          );
        }

        setPeopleActionFeedback({
          type: "success",
          message:
            `${data.deleted_person.name} was deleted successfully. ` +
            "Attendance history was preserved.",
        });

        setDeletingStudent(null);

        await fetchData();

      } catch (error) {
        setPeopleActionFeedback({
          type: "error",
          message:
            error.message ||
            "Could not delete registered person.",
        });
      } finally {
        setDeleteSaving(false);
      }
    };

  // ==================================================
  // RESTORE
  // ==================================================

  const openRestoreStudent = (
    student
  ) => {
    if (recognitionRunning) {
      setPeopleActionFeedback({
        type: "error",
        message:
          "Stop face recognition before restoring a deleted person.",
      });
      return;
    }

    setPeopleActionFeedback(null);
    setRestoringStudent(student);
  };

  const closeRestoreStudent = () => {
    if (restoreSaving) {
      return;
    }

    setRestoringStudent(null);
  };

  const handleRestoreStudent =
    async () => {
      if (!restoringStudent) {
        return;
      }

      if (recognitionRunning) {
        setPeopleActionFeedback({
          type: "error",
          message:
            "Stop face recognition before restoring a deleted person.",
        });
        return;
      }

      try {
        setRestoreSaving(true);
        setPeopleActionFeedback(null);

        const response =
          await fetch(
            `${API_URL}/students/deleted/${encodeURIComponent(
              restoringStudent.backup_name
            )}/restore`,
            {
              method: "POST",
            }
          );

        const data =
          await response.json();

        if (!response.ok) {
          let message =
            "Could not restore deleted person.";

          if (
            typeof data.detail ===
            "string"
          ) {
            message =
              data.detail;
          }

          else if (
            data.detail?.message
          ) {
            message =
              data.detail.message;

            if (
              data.detail.existing_name
            ) {
              message +=
                ` Existing active profile: ${data.detail.existing_name}.`;
            }
          }

          throw new Error(
            message
          );
        }

        setPeopleActionFeedback({
          type: "success",
          message:
            `${data.person.name} was restored successfully with ` +
            `${data.images.valid} valid face photos.`,
        });

        setRestoringStudent(null);

        await fetchData();

      } catch (error) {
        setPeopleActionFeedback({
          type: "error",
          message:
            error.message ||
            "Could not restore deleted person.",
        });
      } finally {
        setRestoreSaving(false);
      }
    };

  // ==================================================
  // PAGE INFO
  // ==================================================

  const pageTitle = {
    dashboard:
      "Face Recognition System",

    recognition:
      "Face Recognition",

    attendance:
      "Attendance",

    people:
      "Registered People",
  };

  const pageDescription = {
    dashboard:
      "Recognize registered people and manage attendance",

    recognition:
      "Start the camera and recognize registered people",

    attendance:
      "View, search and export saved attendance records",

    people:
      "Manage active, deleted and newly registered face profiles",
  };

  // ==================================================
  // RECOGNITION RESULT
  // ==================================================

  const renderRecognitionResult =
    () => {
      if (!recognitionRunning) {
        return null;
      }

      return (
        <div className="recognition-result-card">
          <div className="result-title">
            <h3>
              Recognition Result
            </h3>

            <span
              className={`result-badge ${
                recognitionResult?.status ||
                "waiting"
              }`}
            >
              {recognitionResult?.status ===
              "recognized"
                ? "Recognized"

                : recognitionResult?.status ===
                  "unknown"
                ? "Unknown"

                : recognitionResult?.status ===
                  "checking"
                ? "Checking"

                : "Waiting"}
            </span>
          </div>

          {!recognitionResult ||
          recognitionResult.status ===
            "waiting" ? (

            <div className="waiting-result">
              <strong>
                Waiting for face...
              </strong>

              <p>
                Position a face
                clearly in front of
                the camera.
              </p>
            </div>

          ) : recognitionResult.status ===
            "unknown" ? (

            <div className="unknown-result">
              <h3>
                Unknown Person
              </h3>

              <p>
                This face is not
                recognized as a
                registered person.
              </p>

              <div className="result-row">
                <span>
                  Similarity
                </span>

                <strong>
                  {recognitionResult.similarity !==
                  null
                    ? recognitionResult.similarity.toFixed(
                        3
                      )
                    : "-"}
                </strong>
              </div>

              <div className="result-row">
                <span>
                  Attendance
                </span>

                <strong>
                  Not Marked
                </strong>
              </div>
            </div>

          ) : (

            <div className="recognized-result">
              <div className="result-row">
                <span>
                  Name
                </span>

                <strong>
                  {
                    recognitionResult.name
                  }
                </strong>
              </div>

              <div className="result-row">
                <span>
                  Class
                </span>

                <strong>
                  {recognitionResult.class ||
                    "-"}
                </strong>
              </div>

              <div className="result-row">
                <span>
                  Similarity
                </span>

                <strong>
                  {recognitionResult.similarity !==
                  null
                    ? recognitionResult.similarity.toFixed(
                        3
                      )
                    : "-"}
                </strong>
              </div>

              <div className="result-row">
                <span>
                  Confirmation
                </span>

                <strong>
                  {
                    recognitionResult.confirmation
                  }
                  /
                  {
                    recognitionResult.confirmation_required
                  }
                </strong>
              </div>

              <div className="confirmation-bar">
                <div
                  className="confirmation-progress"
                  style={{
                    width: `${
                      recognitionResult.confirmation_required
                        ? (
                            recognitionResult.confirmation /
                            recognitionResult.confirmation_required
                          ) * 100
                        : 0
                    }%`,
                  }}
                ></div>
              </div>

              <div className="result-row">
                <span>
                  Attendance
                </span>

                <strong>
                  {recognitionResult.attendance_status ||
                    "-"}
                </strong>
              </div>
            </div>
          )}
        </div>
      );
    };

  // ==================================================
  // CAMERA
  // ==================================================

  const renderCameraPanel = () => {
    return (
      <div className="panel recognition-panel">
        <div className="panel-header">
          <div>
            <h2>
              Recognition Status
            </h2>

            <p>
              Current recognition
              session
            </p>
          </div>
        </div>

        <div className="recognition-display">
          {recognitionRunning ? (

            <div className="live-camera-container">
              <img
                src={`${API_URL}/video-feed`}
                alt="Live face recognition"
                className="live-camera"
              />

              <div className="live-indicator">
                <span className="live-dot"></span>
                LIVE
              </div>
            </div>

          ) : (

            <>
              <div className="camera-icon">
                ◉
              </div>

              <h3>
                Camera Ready
              </h3>

              <p>
                Click Start
                Recognition to begin
              </p>
            </>
          )}
        </div>

        {renderRecognitionResult()}
      </div>
    );
  };

  // ==================================================
  // DASHBOARD PEOPLE
  // ==================================================

  const renderPeoplePanel = () => {
    return (
      <div className="panel">
        <div className="panel-header">
          <div>
            <h2>
              Registered People
            </h2>

            <p>
              People enrolled in the
              recognition system
            </p>
          </div>
        </div>

        <div className="people-list">
          {students.length === 0 ? (

            <div className="empty-state">
              No registered people.
            </div>

          ) : (

            students.map(
              (student) => (

                <div
                  className="person"
                  key={
                    student.person_id
                  }
                >
                  <div className="avatar">
                    {student.name
                      .split(" ")
                      .map(
                        (word) =>
                          word[0]
                      )
                      .slice(0, 2)
                      .join("")}
                  </div>

                  <div>
                    <h3>
                      {
                        student.name
                      }
                    </h3>

                    <p>
                      {
                        student.class
                      }
                    </p>
                  </div>

                  <span className="registered">
                    Registered
                  </span>
                </div>
              )
            )
          )}
        </div>
      </div>
    );
  };

  // ==================================================
  // REGISTER FORM
  // ==================================================

  const renderRegisterPersonForm =
    () => {
      return (
        <section className="panel register-person-panel">
          <div className="panel-header">
            <div>
              <h2>
                Register New Person
              </h2>

              <p>
                Create a new face
                profile for live
                recognition
              </p>
            </div>
          </div>

          {recognitionRunning && (
            <div className="registration-warning">
              Stop Recognition before
              registering a new
              person.
            </div>
          )}

          <form
            onSubmit={
              handleRegisterPerson
            }
            className="registration-form"
          >
            <div className="registration-form-grid">
              <div className="form-field">
                <label>
                  Full Name
                </label>

                <input
                  type="text"
                  value={
                    registerName
                  }
                  onChange={(event) =>
                    setRegisterName(
                      event.target
                        .value
                    )
                  }
                  placeholder="e.g. Ali Khan"
                  disabled={
                    registering
                  }
                />
              </div>

              <div className="form-field">
                <label>
                  Class
                </label>

                <input
                  type="text"
                  value={
                    registerClass
                  }
                  onChange={(event) =>
                    setRegisterClass(
                      event.target
                        .value
                    )
                  }
                  placeholder="e.g. BS CS Sem 5"
                  disabled={
                    registering
                  }
                />
              </div>
            </div>

            <div className="form-field">
              <label>
                Face Photos
              </label>

              <div className="photo-upload-box">
                <input
                  key={
                    fileInputKey
                  }
                  type="file"
                  accept="image/*"
                  multiple
                  onChange={
                    handleRegisterFiles
                  }
                  disabled={
                    registering
                  }
                />

                <p>
                  Select 8–30 clear
                  photos of the same
                  person. You can choose
                  photos from multiple
                  folders.
                </p>

                <small>
                  Every new selection is
                  added to the photos
                  already selected. Use
                  the × button on any
                  preview to remove that
                  photo.
                </small>
              </div>
            </div>

            {registerFiles.length >
              0 && (

              <div className="selected-photo-summary">
                <strong>
                  {
                    registerFiles.length
                  }{" "}
                  photo(s) selected
                </strong>

                <span>
                  {
                    registerFiles.length
                  }/30 · Minimum required: 8
                </span>
              </div>
            )}

            {registerPreviews.length >
              0 && (

              <div className="registration-preview-grid">
                {registerPreviews.map(
                  (
                    preview,
                    index
                  ) => (

                    <div
                      className="registration-preview"
                      key={`${preview.name}-${index}`}
                    >
                      <img
                        src={
                          preview.url
                        }
                        alt={`Selected face ${
                          index + 1
                        }`}
                      />

                      <button
                        type="button"
                        className="remove-photo-button"
                        onClick={() =>
                          removeRegisterFile(
                            index
                          )
                        }
                        disabled={
                          registering
                        }
                        aria-label={`Remove ${preview.name}`}
                        title="Remove photo"
                      >
                        ×
                      </button>

                      <span className="photo-number-badge">
                        {index + 1}
                      </span>
                    </div>
                  )
                )}
              </div>
            )}

            {registrationFeedback && (

              <div
                className={`registration-feedback ${registrationFeedback.type}`}
              >
                {
                  registrationFeedback.message
                }
              </div>
            )}

            <div className="registration-actions">
              <button
                type="button"
                className="cancel-registration-button"
                onClick={
                  cancelRegistrationDraft
                }
                disabled={
                  registering
                }
              >
                Cancel / Clear
              </button>

              <button
                type="submit"
                className="register-person-button"
                disabled={
                  registering ||
                  recognitionRunning
                }
              >
                {registering
                  ? "Processing Face Photos..."
                  : "Register Person"}
              </button>
            </div>
          </form>
        </section>
      );
    };

  // ==================================================
  // ACTIVE PROFILES
  // ==================================================

  const renderRegisteredPeoplePanel =
    () => {
      const filteredStudents =
        getFilteredStudents();

      return (
        <section className="panel registered-people-panel">
          <div className="panel-header">
            <div>
              <h2>
                Active Face Profiles
              </h2>

              <p>
                {
                  filteredStudents.length
                }{" "}
                of {students.length}{" "}
                active profile(s)
                shown
              </p>
            </div>
          </div>

          <div className="people-tools">
            <input
              type="text"
              value={
                peopleSearch
              }
              onChange={(event) =>
                setPeopleSearch(
                  event.target.value
                )
              }
              placeholder="Search by name, class or person ID..."
              className="people-search"
            />

            {peopleSearch && (

              <button
                type="button"
                className="clear-filter-button"
                onClick={() =>
                  setPeopleSearch("")
                }
              >
                Clear
              </button>
            )}
          </div>

          {peopleActionFeedback && (

            <div
              className={`people-action-feedback ${peopleActionFeedback.type}`}
            >
              {
                peopleActionFeedback.message
              }
            </div>
          )}

          {filteredStudents.length ===
          0 ? (

            <div className="empty-state">
              No registered people
              match your search.
            </div>

          ) : (

            <div className="registered-profile-grid">
              {filteredStudents.map(
                (student) => {

                  const initials =
                    student.name
                      .split(" ")
                      .map(
                        (word) =>
                          word[0]
                      )
                      .slice(0, 2)
                      .join("");

                  return (
                    <div
                      className="registered-profile-card"
                      key={
                        student.person_id
                      }
                    >
                      <div className="profile-card-top">
                        <div className="profile-avatar-large">
                          {
                            initials
                          }
                        </div>

                        <span className="profile-status-badge">
                          Registered
                        </span>
                      </div>

                      <div className="profile-main-info">
                        <h3>
                          {
                            student.name
                          }
                        </h3>

                        <p>
                          {
                            student.class
                          }
                        </p>
                      </div>

                      <div className="profile-details">
                        <div className="profile-detail-row">
                          <span>
                            Person ID
                          </span>

                          <strong>
                            {
                              student.person_id
                            }
                          </strong>
                        </div>

                        <div className="profile-detail-row">
                          <span>
                            Class
                          </span>

                          <strong>
                            {
                              student.class
                            }
                          </strong>
                        </div>

                        <div className="profile-detail-row">
                          <span>
                            Registration
                          </span>

                          <strong>
                            Active
                          </strong>
                        </div>
                      </div>

                      <div className="face-profile-ready">
                        <span className="ready-dot"></span>

                        <div>
                          <strong>
                            Face Profile
                            Ready
                          </strong>

                          <p>
                            Available for
                            live recognition
                          </p>
                        </div>
                      </div>

                      <div className="profile-actions">
                        <button
                          type="button"
                          className="edit-profile-button"
                          onClick={() =>
                            openEditStudent(
                              student
                            )
                          }
                        >
                          Edit
                        </button>

                        <button
                          type="button"
                          className="delete-profile-button"
                          onClick={() =>
                            openDeleteStudent(
                              student
                            )
                          }
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  );
                }
              )}
            </div>
          )}
        </section>
      );
    };

  // ==================================================
  // DELETED PROFILES
  // ==================================================

  const renderDeletedPeoplePanel =
    () => {
      return (
        <section className="panel deleted-people-panel">
          <div className="panel-header">
            <div>
              <h2>
                Deleted Profiles
              </h2>

              <p>
                Restore accidentally
                deleted face profiles
                from backup
              </p>
            </div>

            <span className="deleted-count-badge">
              {
                deletedStudents.length
              }{" "}
              backup(s)
            </span>
          </div>

          {deletedStudents.length ===
          0 ? (

            <div className="empty-state">
              No deleted face profile
              backups are available.
            </div>

          ) : (

            <div className="deleted-profile-grid">
              {deletedStudents.map(
                (student) => (

                  <div
                    className="deleted-profile-card"
                    key={
                      student.backup_name
                    }
                  >
                    <div className="deleted-profile-top">
                      <div className="deleted-avatar">
                        ↶
                      </div>

                      <span className="deleted-status-badge">
                        Deleted
                      </span>
                    </div>

                    <h3>
                      {
                        student.name
                      }
                    </h3>

                    <p className="deleted-profile-class">
                      {student.class ||
                        "Class unavailable"}
                    </p>

                    <div className="deleted-profile-details">
                      <div>
                        <span>
                          Person ID
                        </span>

                        <strong>
                          {
                            student.person_id
                          }
                        </strong>
                      </div>

                      <div>
                        <span>
                          Backup Photos
                        </span>

                        <strong>
                          {
                            student.images
                          }
                        </strong>
                      </div>

                      <div>
                        <span>
                          Deleted
                        </span>

                        <strong>
                          {student.deleted_at
                            ? new Date(
                                student.deleted_at
                              ).toLocaleString()
                            : "Backup available"}
                        </strong>
                      </div>
                    </div>

                    <button
                      type="button"
                      className="restore-profile-button"
                      onClick={() =>
                        openRestoreStudent(
                          student
                        )
                      }
                      disabled={
                        !student.restorable
                      }
                    >
                      {student.restorable
                        ? "Restore Profile"
                        : "Backup Not Restorable"}
                    </button>
                  </div>
                )
              )}
            </div>
          )}
        </section>
      );
    };

  // ==================================================
  // ATTENDANCE TABLE
  // ==================================================

  const renderAttendanceTable = (
    recent = false
  ) => {
    const filteredRecords =
      getFilteredAttendance();

    const records = recent
      ? attendance.slice(0, 5)
      : filteredRecords;

    return (
      <section className="panel attendance-panel">
        <div className="panel-header">
          <div>
            <h2>
              {recent
                ? "Recent Attendance"
                : "Attendance Records"}
            </h2>

            <p>
              {recent
                ? "Latest recognized attendance records"
                : `${records.length} record(s) shown`}
            </p>
          </div>

          <button
            type="button"
            className="refresh-button"
            onClick={fetchData}
          >
            Refresh
          </button>
        </div>

        {!recent && (

          <div className="attendance-tools">
            <input
              type="text"
              placeholder="Search by name or class..."
              value={
                attendanceSearch
              }
              onChange={(event) =>
                setAttendanceSearch(
                  event.target.value
                )
              }
              className="attendance-search"
            />

            <input
              type="date"
              value={
                attendanceDate
              }
              onChange={(event) =>
                setAttendanceDate(
                  event.target.value
                )
              }
              className="attendance-date"
            />

            <button
              type="button"
              className="clear-filter-button"
              onClick={() => {
                setAttendanceSearch(
                  ""
                );

                setAttendanceDate(
                  ""
                );
              }}
            >
              Clear
            </button>

            <button
              type="button"
              className="export-button"
              onClick={
                exportAttendanceCSV
              }
            >
              Export CSV
            </button>
          </div>
        )}

        {loading ? (

          <div className="empty-state">
            Loading attendance...
          </div>

        ) : records.length === 0 ? (

          <div className="empty-state">
            {recent
              ? "No attendance records yet."
              : "No matching attendance records."}
          </div>

        ) : (

          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Class</th>
                  <th>Date</th>
                  <th>Time</th>
                  <th>Status</th>
                </tr>
              </thead>

              <tbody>
                {records.map(
                  (
                    record,
                    index
                  ) => (

                    <tr
                      key={`${record.person_id}-${record.date}-${record.time}-${index}`}
                    >
                      <td>
                        <strong>
                          {
                            record.name
                          }
                        </strong>
                      </td>

                      <td>
                        {
                          record.class
                        }
                      </td>

                      <td>
                        {
                          record.date
                        }
                      </td>

                      <td>
                        {
                          record.time
                        }
                      </td>

                      <td>
                        <span className="present">
                          Present
                        </span>
                      </td>
                    </tr>
                  )
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>
    );
  };

  // ==================================================
  // PAGES
  // ==================================================

  const renderDashboardPage =
    () => {
      return (
        <>
          <section className="stats">
            <div className="stat-card">
              <span>
                Registered People
              </span>

              <strong>
                {
                  students.length
                }
              </strong>

              <p>
                Face profiles enrolled
              </p>
            </div>

            <div className="stat-card">
              <span>
                Attendance Records
              </span>

              <strong>
                {
                  attendance.length
                }
              </strong>

              <p>
                Total saved records
              </p>
            </div>

            <div className="stat-card">
              <span>
                Recognition
              </span>

              <strong className="status-text">
                {recognitionRunning
                  ? "Running"
                  : "Ready"}
              </strong>

              <p>
                {recognitionRunning
                  ? "Recognition session active"
                  : "Waiting to start"}
              </p>
            </div>
          </section>

          <section className="content-grid">
            {renderPeoplePanel()}
            {renderCameraPanel()}
          </section>

          {renderAttendanceTable(
            true
          )}
        </>
      );
    };

  const renderRecognitionPage =
    () => {
      return (
        <>
          <section className="stats">
            <div className="stat-card">
              <span>
                Camera
              </span>

              <strong>
                {recognitionRunning
                  ? "Active"
                  : "Ready"}
              </strong>

              <p>
                Live recognition
                camera
              </p>
            </div>

            <div className="stat-card">
              <span>
                Confirmation
              </span>

              <strong>
                8 Frames
              </strong>

              <p>
                Required before
                confirmation
              </p>
            </div>

            <div className="stat-card">
              <span>
                Current Status
              </span>

              <strong>
                {!recognitionRunning
                  ? "Stopped"

                  : recognitionResult?.status ===
                    "recognized"
                  ? "Recognized"

                  : recognitionResult?.status ===
                    "unknown"
                  ? "Unknown"

                  : recognitionResult?.status ===
                    "checking"
                  ? "Checking"

                  : "Waiting"}
              </strong>

              <p>
                Live recognition
                status
              </p>
            </div>
          </section>

          {renderCameraPanel()}
        </>
      );
    };

  const renderAttendancePage =
    () => {
      const filteredCount =
        getFilteredAttendance()
          .length;

      return (
        <>
          <section className="stats">
            <div className="stat-card">
              <span>
                Total Records
              </span>

              <strong>
                {
                  attendance.length
                }
              </strong>

              <p>
                Saved attendance
                entries
              </p>
            </div>

            <div className="stat-card">
              <span>
                Showing
              </span>

              <strong>
                {
                  filteredCount
                }
              </strong>

              <p>
                Records after
                filtering
              </p>
            </div>

            <div className="stat-card">
              <span>
                Registered People
              </span>

              <strong>
                {
                  students.length
                }
              </strong>

              <p>
                Eligible people
              </p>
            </div>
          </section>

          {renderAttendanceTable(
            false
          )}
        </>
      );
    };

  const renderPeoplePage = () => {
    const filteredPeopleCount =
      getFilteredStudents().length;

    return (
      <>
        <section className="stats">
          <div className="stat-card">
            <span>
              Total Registered
            </span>

            <strong>
              {
                students.length
              }
            </strong>

            <p>
              Active face profiles
            </p>
          </div>

          <div className="stat-card">
            <span>
              Profiles Shown
            </span>

            <strong>
              {
                filteredPeopleCount
              }
            </strong>

            <p>
              Current search results
            </p>
          </div>

          <div className="stat-card">
            <span>
              Deleted Backups
            </span>

            <strong>
              {
                deletedStudents.length
              }
            </strong>

            <p>
              Profiles available to restore
            </p>
          </div>
        </section>

        {renderRegisterPersonForm()}

        {renderRegisteredPeoplePanel()}

        {renderDeletedPeoplePanel()}
      </>
    );
  };

  // ==================================================
  // MAIN UI
  // ==================================================

  return (
    <div className="app">
      <aside className="sidebar">
        <div>
          <div className="logo">
            <div className="logo-icon">
              FR
            </div>

            <div>
              <h2>
                Face Recognition
              </h2>

              <p>
                Attendance System
              </p>
            </div>
          </div>

          <nav>
            <button
              type="button"
              className={`nav-item ${
                activePage ===
                "dashboard"
                  ? "active"
                  : ""
              }`}
              onClick={() =>
                setActivePage(
                  "dashboard"
                )
              }
            >
              Dashboard
            </button>

            <button
              type="button"
              className={`nav-item ${
                activePage ===
                "recognition"
                  ? "active"
                  : ""
              }`}
              onClick={() =>
                setActivePage(
                  "recognition"
                )
              }
            >
              Recognition
            </button>

            <button
              type="button"
              className={`nav-item ${
                activePage ===
                "attendance"
                  ? "active"
                  : ""
              }`}
              onClick={() =>
                setActivePage(
                  "attendance"
                )
              }
            >
              Attendance
            </button>

            <button
              type="button"
              className={`nav-item ${
                activePage ===
                "people"
                  ? "active"
                  : ""
              }`}
              onClick={() =>
                setActivePage(
                  "people"
                )
              }
            >
              Registered People
            </button>
          </nav>
        </div>

        <div className="sidebar-footer">
          <span className="status-dot"></span>
          Backend Connected
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <h1>
              {
                pageTitle[
                  activePage
                ]
              }
            </h1>

            <p>
              {
                pageDescription[
                  activePage
                ]
              }
            </p>
          </div>

          {activePage === "recognition" && (
            <button
              type="button"
              className={
                recognitionRunning
                  ? "recognition-button stop"
                  : "recognition-button"
              }
              onClick={
                handleRecognition
              }
            >
              {recognitionRunning
                ? "Stop Recognition"
                : "Start Recognition"}
            </button>
          )}
        </header>

        {activePage ===
          "dashboard" &&
          renderDashboardPage()}

        {activePage ===
          "recognition" &&
          renderRecognitionPage()}

        {activePage ===
          "attendance" &&
          renderAttendancePage()}

        {activePage ===
          "people" &&
          renderPeoplePage()}
      </main>

      {/* EDIT MODAL */}

      {editingStudent && (
        <div className="profile-modal-overlay">
          <div className="profile-modal">

            <div className="profile-modal-header">
              <div>
                <h2>
                  Edit Registered Person
                </h2>

                <p>
                  Update the display
                  name or class.
                </p>
              </div>

              <button
                type="button"
                className="modal-close-button"
                onClick={
                  closeEditStudent
                }
                disabled={
                  editSaving
                }
              >
                ×
              </button>
            </div>

            <form
              onSubmit={
                handleUpdateStudent
              }
              className="profile-edit-form"
            >
              <div className="form-field">
                <label>
                  Person ID
                </label>

                <input
                  type="text"
                  value={
                    editingStudent.person_id
                  }
                  disabled
                />

                <small>
                  Person ID stays
                  unchanged so the
                  existing face profile
                  remains connected.
                </small>
              </div>

              <div className="form-field">
                <label>
                  Name
                </label>

                <input
                  type="text"
                  value={
                    editName
                  }
                  onChange={(event) =>
                    setEditName(
                      event.target.value
                    )
                  }
                  disabled={
                    editSaving
                  }
                />
              </div>

              <div className="form-field">
                <label>
                  Class
                </label>

                <input
                  type="text"
                  value={
                    editClass
                  }
                  onChange={(event) =>
                    setEditClass(
                      event.target.value
                    )
                  }
                  disabled={
                    editSaving
                  }
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="modal-cancel-button"
                  onClick={
                    closeEditStudent
                  }
                  disabled={
                    editSaving
                  }
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  className="modal-save-button"
                  disabled={
                    editSaving
                  }
                >
                  {editSaving
                    ? "Saving..."
                    : "Save Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* DELETE MODAL */}

      {deletingStudent && (
        <div className="profile-modal-overlay">
          <div className="profile-modal delete-modal">

            <div className="delete-modal-icon">
              !
            </div>

            <h2>
              Delete Face Profile?
            </h2>

            <p>
              You are about to delete
              <strong>
                {" "}
                {
                  deletingStudent.name
                }
              </strong>
              .
            </p>

            <div className="delete-warning-box">
              <strong>
                This will remove:
              </strong>

              <p>
                Face recognition
                profile
              </p>

              <p>
                Registered person
                entry
              </p>

              <p>
                Active training
                dataset
              </p>
            </div>

            <div className="delete-preserved-box">
              Attendance history will
              be preserved. The
              training dataset is also
              backed up before removal.
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="modal-cancel-button"
                onClick={
                  closeDeleteStudent
                }
                disabled={
                  deleteSaving
                }
              >
                Cancel
              </button>

              <button
                type="button"
                className="confirm-delete-button"
                onClick={
                  handleDeleteStudent
                }
                disabled={
                  deleteSaving
                }
              >
                {deleteSaving
                  ? "Deleting..."
                  : "Delete Person"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* RESTORE MODAL */}

      {restoringStudent && (
        <div className="profile-modal-overlay">
          <div className="profile-modal restore-modal">

            <div className="restore-modal-icon">
              ↶
            </div>

            <h2>
              Restore Face Profile?
            </h2>

            <p>
              Restore
              <strong>
                {" "}
                {
                  restoringStudent.name
                }
              </strong>
              {" "}
              to the active recognition
              system.
            </p>

            <div className="restore-info-box">
              <div>
                <span>
                  Person ID
                </span>

                <strong>
                  {
                    restoringStudent.person_id
                  }
                </strong>
              </div>

              <div>
                <span>
                  Class
                </span>

                <strong>
                  {
                    restoringStudent.class
                  }
                </strong>
              </div>

              <div>
                <span>
                  Backup Photos
                </span>

                <strong>
                  {
                    restoringStudent.images
                  }
                </strong>
              </div>
            </div>

            <div className="restore-note-box">
              The system will rebuild
              the face embedding from
              the backed-up photos and
              run duplicate-face checks
              before restoring it.
            </div>

            <div className="modal-actions">
              <button
                type="button"
                className="modal-cancel-button"
                onClick={
                  closeRestoreStudent
                }
                disabled={
                  restoreSaving
                }
              >
                Cancel
              </button>

              <button
                type="button"
                className="confirm-restore-button"
                onClick={
                  handleRestoreStudent
                }
                disabled={
                  restoreSaving
                }
              >
                {restoreSaving
                  ? "Restoring..."
                  : "Restore Person"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
