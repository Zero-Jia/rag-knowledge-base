import { useEffect, useMemo, useState } from "react";
import { deleteDocument, listDocuments } from "../api/documents";

function normalizeStatus(status) {
  const raw = String(status || "unknown").toLowerCase();
  if (raw === "completed" || raw === "success") return "done";
  if (raw === "running" || raw === "in_progress") return "processing";
  return raw;
}

function StatusBadge({ status }) {
  const normalized = normalizeStatus(status);
  return <span className={`doc-status ${normalized}`}>{normalized}</span>;
}

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const stats = useMemo(() => {
    return docs.reduce(
      (acc, doc) => {
        const status = normalizeStatus(doc.status);
        acc.total += 1;
        acc[status] = (acc[status] || 0) + 1;
        return acc;
      },
      { total: 0, done: 0, processing: 0, failed: 0 }
    );
  }, [docs]);

  async function loadDocs() {
    setLoading(true);
    setError("");
    try {
      const data = await listDocuments();
      const items = Array.isArray(data) ? data : data?.items || [];
      setDocs(items);
    } catch (err) {
      setError(err?.message || "Failed to load documents");
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(documentId) {
    if (!window.confirm("Delete this document?")) return;
    try {
      await deleteDocument(documentId);
      await loadDocs();
    } catch (err) {
      setError(err?.message || "Delete failed");
    }
  }

  useEffect(() => {
    loadDocs();
    const timer = setInterval(loadDocs, 4000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="page-grid">
      <section className="panel">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Indexed documents</h2>
            <p className="panel-subtitle">
              Parent chunks and L3 vector chunks are managed by the backend.
            </p>
          </div>
          <button
            type="button"
            onClick={loadDocs}
            className="ghost-button"
            disabled={loading}
          >
            <span className="button-icon">R</span>
            {loading ? "Refreshing" : "Refresh"}
          </button>
        </div>

        <div className="document-stats">
          <span className="metric-chip">Total {stats.total}</span>
          <span className="metric-chip">Done {stats.done}</span>
          <span className="metric-chip">Processing {stats.processing}</span>
          <span className="metric-chip">Failed {stats.failed}</span>
        </div>

        {error && <div className="alert error">{error}</div>}

        <div className="document-list">
          {docs.map((doc) => (
            <article key={doc.document_id} className="item-card document-row">
              <div className="document-main">
                <div className="doc-file-mark">
                  {(doc.filename || "D").slice(0, 1).toUpperCase()}
                </div>
                <div>
                  <h3>{doc.filename || "Untitled document"}</h3>
                  <div className="doc-meta">
                    <span>No. {doc.display_id ?? "-"}</span>
                    <span className="mono">{doc.document_id}</span>
                  </div>
                </div>
              </div>

              <div className="document-actions">
                <StatusBadge status={doc.status} />
                <button
                  type="button"
                  onClick={() => handleDelete(doc.document_id)}
                  className="danger-button"
                >
                  Delete
                </button>
              </div>
            </article>
          ))}

          {!loading && docs.length === 0 && (
            <div className="empty-state">No documents have been indexed yet.</div>
          )}
        </div>
      </section>
    </div>
  );
}
