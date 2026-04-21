import { useEffect, useMemo, useRef, useState } from "react";
import { getDocumentStatus, uploadDocument } from "../api/documents";

const stages = [
  { key: "upload", label: "Upload" },
  { key: "parse", label: "Parse" },
  { key: "parent_store", label: "Parent store" },
  { key: "vector_store", label: "Vector store" },
];

const statusRank = {
  pending: 0,
  processing: 1,
  done: 2,
  failed: 3,
};

function normalizeStageStatus(value) {
  const raw = String(value || "pending").toLowerCase();
  if (raw === "completed" || raw === "success") return "done";
  if (raw === "running" || raw === "in_progress") return "processing";
  if (raw === "error") return "failed";
  return raw;
}

function StagePill({ stage, status }) {
  const normalized = normalizeStageStatus(status);
  return (
    <div className={`stage-pill ${normalized}`}>
      <span className="stage-index">{stage.label.slice(0, 1)}</span>
      <div>
        <strong>{stage.label}</strong>
        <small>{normalized}</small>
      </div>
    </div>
  );
}

export default function Upload() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [jobState, setJobState] = useState(null);
  const pollRef = useRef(null);

  const stageMap = useMemo(() => {
    const job = jobState?.job || jobState;
    const rawStages = job?.stages || {};
    const currentStage = job?.current_stage;
    const status = normalizeStageStatus(job?.status || jobState?.status);

    return stages.reduce((acc, stage) => {
      const explicit = rawStages?.[stage.key]?.status || rawStages?.[stage.key];
      if (explicit) {
        acc[stage.key] = normalizeStageStatus(explicit);
        return acc;
      }
      if (status === "failed" && currentStage === stage.key) {
        acc[stage.key] = "failed";
        return acc;
      }
      const currentIndex = stages.findIndex((item) => item.key === currentStage);
      const stageIndex = stages.findIndex((item) => item.key === stage.key);
      if (status === "done") acc[stage.key] = "done";
      else if (stageIndex < currentIndex) acc[stage.key] = "done";
      else if (stageIndex === currentIndex) acc[stage.key] = "processing";
      else acc[stage.key] = "pending";
      return acc;
    }, {});
  }, [jobState]);

  const progress = useMemo(() => {
    if (!jobState) return 0;
    const total = stages.length * 2;
    const doneScore = stages.reduce((sum, stage) => {
      const rank = statusRank[stageMap[stage.key]] || 0;
      return sum + Math.min(rank, 2);
    }, 0);
    return Math.round((doneScore / total) * 100);
  }, [jobState, stageMap]);

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function pollStatus(documentId) {
    try {
      const status = await getDocumentStatus(documentId);
      setJobState(status);
      const jobStatus = normalizeStageStatus(status?.job?.status || status?.status);
      if (jobStatus === "done" || jobStatus === "failed") {
        stopPolling();
        setUploading(false);
      }
    } catch (err) {
      setError(err?.message || "Failed to load upload status");
      stopPolling();
      setUploading(false);
    }
  }

  async function handleUpload(event) {
    event.preventDefault();
    if (!file) return;

    stopPolling();
    setUploading(true);
    setMessage("");
    setError("");
    setJobState(null);

    try {
      const data = await uploadDocument(file);
      const documentId = data?.document_id ?? data?.id;
      setMessage(
        `Accepted ${file.name}${documentId ? ` as document ${documentId}` : ""}.`
      );
      if (documentId) {
        await pollStatus(documentId);
        pollRef.current = setInterval(() => pollStatus(documentId), 1200);
      } else {
        setUploading(false);
      }
    } catch (err) {
      setError(err?.message || "Upload failed");
      setUploading(false);
    }
  }

  useEffect(() => stopPolling, []);

  return (
    <div className="two-column-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Upload pipeline</h2>
            <p className="panel-subtitle">
              Files are indexed through hierarchical chunks and vector storage.
            </p>
          </div>
        </div>

        <form className="upload-form" onSubmit={handleUpload}>
          <label className="drop-zone">
            <input
              type="file"
              accept=".pdf,.txt,.md"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
            <span className="drop-icon">+</span>
            <strong>{file ? file.name : "Choose a document"}</strong>
            <small>PDF, TXT, and Markdown files are supported.</small>
          </label>

          <div className="upload-actions">
            <button
              type="submit"
              disabled={!file || uploading}
              className="primary-button"
            >
              <span className="button-icon">U</span>
              {uploading ? "Indexing" : "Upload"}
            </button>
            <button
              type="button"
              className="ghost-button"
              onClick={() => {
                setFile(null);
                setMessage("");
                setError("");
                setJobState(null);
                stopPolling();
              }}
              disabled={uploading}
            >
              Clear
            </button>
          </div>
        </form>

        {message && <div className="alert success">{message}</div>}
        {error && <div className="alert error">{error}</div>}
      </section>

      <aside className="panel">
        <div className="panel-header compact">
          <div>
            <h2 className="panel-title">DocumentJob</h2>
            <p className="panel-subtitle">Stage-level ingestion status</p>
          </div>
          <span className="metric-chip">{progress}%</span>
        </div>

        <div className="progress-track">
          <div className="progress-bar" style={{ width: `${progress}%` }} />
        </div>

        <div className="stage-list">
          {stages.map((stage) => (
            <StagePill
              key={stage.key}
              stage={stage}
              status={stageMap[stage.key]}
            />
          ))}
        </div>

        {jobState?.job?.error_message && (
          <div className="alert error">{jobState.job.error_message}</div>
        )}
      </aside>
    </div>
  );
}
