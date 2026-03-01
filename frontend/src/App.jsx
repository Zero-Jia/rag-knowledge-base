import { useState } from "react";
import Login from "./pages/Login";
import Upload from "./pages/Upload";
import Documents from "./pages/Documents";
import Search from "./pages/Search"; // ✅ 新增：引入 Search 页面

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
        <button onClick={() => setPage("search")}>Search</button> {/* ✅ 新增按钮 */}
      </div>

      {page === "upload" && <Upload />}
      {page === "docs" && <Documents />}
      {page === "search" && <Search />} {/* ✅ 新增页面渲染 */}
    </div>
  );
}