// 文档列表 + 状态展示
import { useEffect,useState } from "react";
import { listDocuments } from "../api/documents";

export default function Documents(){
    const [docs, setDocs] = useState([]);
    const [error, setError] = useState(null);
    const [loading, setLoading] = useState(false);

    async function loadDocs(){
        try{
            setLoading(true);
            setError(null);
            const data = await listDocuments();

            // 兼容两种：data.items 或 data（直接就是数组）
            const items = Array.isArray(data)?data : data.items;
            setDocs(items||[]);    
        }catch(e){
            setError(e.message);
        }finally{
            setLoading(false);
        }
    }

    useEffect(() => {
        loadDocs();
      
        const timer = setInterval(() => {
          loadDocs();
        }, 3000);
      
        return () => clearInterval(timer);
      }, []);

    return (
        <div style={{ padding: 16 }}>
          <h2>Documents</h2>
    
          <button onClick={loadDocs} disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </button>
    
          {error && <p style={{ color: "crimson" }}>Error: {error}</p>}
    
          <table border="1" cellPadding="8" style={{ marginTop: 12, borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th>ID</th>
                <th>Filename</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.id}</td>
                  <td>{doc.filename}</td>
                  <td>{doc.status}</td>
                </tr>
              ))}
              {docs.length === 0 && (
                <tr>
                  <td colSpan="3" style={{ textAlign: "center" }}>
                    No documents
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      );
    }