import { useState } from "react";
import Login from "./pages/Login";
import Upload from "./pages/Upload";
import Documents from "./pages/Documents";
import Search from "./pages/Search";
import Chat from "./pages/Chat";

export default function App() {
  const [page, setPage] = useState("upload");
  const token = localStorage.getItem("access_token");

  if (!token) return <Login />;

  const navBtn = (name, label) => (
    <button
      onClick={() => setPage(name)}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
        page === name
          ? "bg-black text-white"
          : "border border-gray-300 hover:bg-gray-100"
      }`}
    >
      {label}
    </button>
  );

  return (
    <div className="min-h-screen bg-gray-100">
      {/* 顶部导航 */}
      <header className="bg-white shadow-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-xl font-semibold">
            RAG Knowledge Base
          </h1>
          <div className="flex gap-3">
            {navBtn("upload", "Upload")}
            {navBtn("docs", "Documents")}
            {navBtn("search", "Search")}
            {navBtn("chat", "Chat")}
          </div>
        </div>
      </header>

      {/* 内容区 */}
      <main className="max-w-5xl mx-auto p-6">
        <div className="bg-white rounded-xl shadow-sm p-6">
          {page === "upload" && <Upload />}
          {page === "docs" && <Documents />}
          {page === "search" && <Search />}
          {page === "chat" && <Chat />}
        </div>
      </main>
    </div>
  );
}