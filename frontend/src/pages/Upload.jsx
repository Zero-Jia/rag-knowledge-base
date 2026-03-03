import { useState } from "react";
import { uploadDocument } from "../api/documents";

export default function Upload() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState(null);
  const [uploading, setUploading] = useState(false);

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) return;

    try {
      setUploading(true);
      setMessage(null);
      const data = await uploadDocument(file);
      const id = data?.document_id ?? data?.id;
      setMessage(`Upload success. Document ID: ${id}`);
    } catch (err) {
      setMessage(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold">Upload Document</h2>

      <form onSubmit={handleUpload} className="flex gap-4 items-center">
        <input
          type="file"
          accept=".pdf,.txt"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="border rounded-lg px-3 py-2"
        />

        <button
          type="submit"
          disabled={!file || uploading}
          className="px-4 py-2 rounded-lg bg-black text-white disabled:bg-gray-400"
        >
          {uploading ? "Uploading..." : "Upload"}
        </button>
      </form>

      {message && (
        <p className="text-sm text-gray-600">{message}</p>
      )}
    </div>
  );
}