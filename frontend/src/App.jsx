import { useMemo, useState } from "react";
import "./App.css";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Upload from "./pages/Upload";
import Documents from "./pages/Documents";
import Search from "./pages/Search";
import Chat from "./pages/Chat";

const pages = {
  upload: {
    label: "Upload",
    icon: "U",
    title: "Document Intake",
    subtitle: "Parse files, store parent chunks, then push L3 chunks into vectors.",
  },
  docs: {
    label: "Documents",
    icon: "D",
    title: "Knowledge Library",
    subtitle: "Track indexed files, ingestion status, and cleanup operations.",
  },
  search: {
    label: "Search",
    icon: "S",
    title: "Retrieval Lab",
    subtitle: "Compare vector, hybrid, and rerank retrieval modes.",
  },
  chat: {
    label: "Agent Chat",
    icon: "A",
    title: "Agentic RAG",
    subtitle: "Stream answer steps, second retrieval, and structured rag_trace.",
  },
};

export default function App() {
  const [page, setPage] = useState("chat");
  const [authPage, setAuthPage] = useState("login");
  const token = sessionStorage.getItem("access_token");

  const activePage = useMemo(() => pages[page] || pages.chat, [page]);

  if (!token) {
    return authPage === "login" ? (
      <Login onSwitchToRegister={() => setAuthPage("register")} />
    ) : (
      <Register onSwitchToLogin={() => setAuthPage("login")} />
    );
  }

  const logout = () => {
    sessionStorage.removeItem("access_token");
    localStorage.removeItem("access_token");
    window.location.reload();
  };

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-block">
          <div className="brand-mark">R</div>
          <div>
            <div className="brand-title">RAG Studio</div>
            <div className="brand-subtitle">Knowledge Base</div>
          </div>
        </div>

        <nav className="side-nav" aria-label="Main navigation">
          {Object.entries(pages).map(([name, item]) => (
            <button
              key={name}
              type="button"
              onClick={() => setPage(name)}
              className={`nav-item ${page === name ? "active" : ""}`}
              title={item.label}
            >
              <span className="nav-icon">{item.icon}</span>
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="mini-status">
            <span className="status-dot ok" />
            Backend connected by token
          </div>
          <button
            type="button"
            onClick={logout}
            className="ghost-button sidebar-logout"
            title="Logout"
          >
            <span className="button-icon">X</span>
            Logout
          </button>
        </div>
      </aside>

      <main className="workspace">
        <header className="workspace-header">
          <div>
            <p className="eyebrow">SuperMew style workspace</p>
            <h1>{activePage.title}</h1>
            <p>{activePage.subtitle}</p>
          </div>
          <div className="header-badges">
            <span>L1/L2/L3</span>
            <span>Auto-merge</span>
            <span>Trace</span>
          </div>
        </header>

        <section className="workspace-body">
          {page === "upload" && <Upload />}
          {page === "docs" && <Documents />}
          {page === "search" && <Search />}
          {page === "chat" && <Chat />}
        </section>
      </main>
    </div>
  );
}
