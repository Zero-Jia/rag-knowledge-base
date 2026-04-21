import { useState } from "react";
import { login } from "../api/auth";
import { apiFetch } from "../api/client";

export default function Login({ onSwitchToRegister }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const data = await login(username.trim(), password);
      const token = data?.access_token || data?.token;
      if (!token) throw new Error("No access_token in response");

      sessionStorage.setItem("access_token", token);
      await apiFetch("/documents", { method: "GET" });
      window.location.reload();
    } catch (err) {
      setError(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-screen">
      <section className="auth-card">
        <div className="brand-block auth-brand">
          <div className="brand-mark">R</div>
          <div>
            <div className="brand-title">RAG Studio</div>
            <div className="brand-subtitle">Sign in</div>
          </div>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label>
            <span>Username</span>
            <input
              className="field"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              placeholder="Enter username"
            />
          </label>

          <label>
            <span>Password</span>
            <input
              className="field"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
              placeholder="Enter password"
            />
          </label>

          {error && <div className="alert error">{error}</div>}

          <button
            type="submit"
            className="primary-button full-width"
            disabled={!username.trim() || !password || loading}
          >
            {loading ? "Signing in" : "Login"}
          </button>
        </form>

        <div className="auth-switch">
          <span>No account?</span>
          <button type="button" onClick={onSwitchToRegister}>
            Create one
          </button>
        </div>
      </section>
    </main>
  );
}
