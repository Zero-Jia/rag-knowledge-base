import { useState } from "react";
import Login from "./pages/Login";
import Upload from "./pages/Upload";
import Documents from "./pages/Documents";

export default function App() {
  const [page, setPage] = useState("upload");

  const token = localStorage.getItem("access_token");
  if (!token) {
    return <Login />;
  }

  return (
    <div>
      <div style={{ padding: 16, display: "flex", gap: 8 }}>
        <button onClick={() => setPage("upload")}>Upload</button>
        <button onClick={() => setPage("docs")}>Documents</button>
      </div>

      {page === "upload" && <Upload />}
      {page === "docs" && <Documents />}
    </div>
  );
}
