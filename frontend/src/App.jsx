import { useState } from "react";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Upload from "./pages/Upload";
import Documents from "./pages/Documents";
import Search from "./pages/Search";
import Chat from "./pages/Chat";

export default function App() {
  const [page, setPage] = useState("upload");
  const [authPage, setAuthPage] = useState("login"); // ✅ 新增：登录/注册切换

  // ✅ 改为 sessionStorage
  const token = sessionStorage.getItem("access_token");

  if (!token) {
    return authPage === "login" ? (
      <Login onSwitchToRegister={() => setAuthPage("register")} />
    ) : (
      <Register onSwitchToLogin={() => setAuthPage("login")} />
    );
  }

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

  const logout = () => {
    sessionStorage.removeItem("access_token");
    window.location.reload();
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow-sm">
        <div className="max-w-5xl mx-auto px-6 py-4 flex justify-between items-center">
          <h1 className="text-xl font-semibold">RAG Knowledge Base</h1>

          <div className="flex gap-3 items-center">
            {navBtn("upload", "Upload")}
            {navBtn("docs", "Documents")}
            {navBtn("search", "Search")}
            {navBtn("chat", "Chat")}

            {/* ✅ 退出登录按钮 */}
            <button
              onClick={logout}
              className="px-4 py-2 rounded-lg text-sm font-medium border border-gray-300 hover:bg-gray-100 transition"
              title="Logout"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

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