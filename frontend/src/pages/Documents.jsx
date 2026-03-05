import { useEffect, useState } from "react";
import { listDocuments, deleteDocument } from "../api/documents";

function StatusBadge({ status }) {
  const styles = {
    DONE: "bg-green-100 text-green-700",
    PROCESSING: "bg-yellow-100 text-yellow-700",
    FAILED: "bg-red-100 text-red-700",
  };

  return (
    <span
      className={`px-3 py-1 text-xs rounded-full font-medium ${
        styles[status] || "bg-gray-100"
      }`}
    >
      {status}
    </span>
  );
}

export default function Documents() {
  const [docs, setDocs] = useState([]);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function loadDocs() {
    try {
      setLoading(true);
      setError(null);
      const data = await listDocuments();
      const items = Array.isArray(data) ? data : data.items;
      setDocs(items || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleDelete(documentId) {
    if (!confirm("Delete this document?")) return;

    try {
      await deleteDocument(documentId);
      await loadDocs();
    } catch (e) {
      alert(e.message);
    }
  }

  useEffect(() => {
    loadDocs();
    const timer = setInterval(loadDocs, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h2 className="text-lg font-semibold">Documents</h2>
        <button
          onClick={loadDocs}
          className="px-4 py-2 rounded-lg border border-gray-300 hover:bg-gray-100"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && <p className="text-red-600">Error: {error}</p>}
      {docs.length === 0 && <p className="text-gray-500">No documents</p>}

      <div className="space-y-3">
        {docs.map((doc) => (
          <div
            key={doc.document_id}
            className="border rounded-lg p-4 flex justify-between items-center"
          >
            <div>
              <p className="font-medium">{doc.filename}</p>

              {/* ✅ 展示用序号（连续） */}
              <p className="text-sm text-gray-500">
                No: {doc.display_id ?? "-"}
              </p>

              {/* ✅ 可选：保留真实 ID，方便你调试（不想显示就删掉这一行） */}
              <p className="text-xs text-gray-400">
                ID: {doc.document_id}
              </p>
            </div>

            <div className="flex items-center gap-3">
              <StatusBadge status={doc.status} />

              <button
                onClick={() => handleDelete(doc.document_id)}
                className="px-3 py-1 text-sm text-red-600 border border-red-200 rounded hover:bg-red-50"
              >
                Delete
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}