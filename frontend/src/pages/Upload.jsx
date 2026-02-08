// 上传页面
import { useState } from "react";
import { uploadDocument } from "../api/documents";

export default function Upload(){
    const [file, setFile] = useState(null);
    const [message, setMessage] = useState(null);
    const [uploading, setUploading] = useState(false);

    async function handleUpload(e) {
        e.preventDefault();
        if (!file) return;

        try{
            setUploading(true);
            setMessage(null);
            const data = await uploadDocument(file);
            // 兼容后端返回字段：document_id 或 id
            const id = data?.document_id ??data?.id;
            setMessage(`Upload success. Document ID: ${id}`);
        }catch(err){
            setMessage(`Upload failed: ${err.message}`);
        }finally{
            setUploading(false);
        }
    }

    return (
        <div style={{padding:16}}>
            <h2>Upload Document</h2>

            <form onSubmit={handleUpload}>
                <input
                type="file"
                accept=".pdf,.txt"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                />
                <button type="submit" disabled= {!file||uploading} style={{marginLeft:8}}>
                    {uploading ? "Uploading..." : "Upload"}
                </button>
            </form>
            {message && <p style={{ marginTop: 12 }}>{message}</p>}
        </div>
    );
}