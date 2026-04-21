import { useState } from "react";
import { login } from "../api/auth";
import { apiFetch } from "../api/client";
import { registerUser } from "../api/users";

export default function Register({ onSwitchToLogin }) {
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const cleanUsername = username.trim();
      await registerUser({
        username: cleanUsername,
        email: email.trim() || null,
        password,
      });

      const data = await login(cleanUsername, password);
      const token = data?.access_token || data?.token;
      if (!token) throw new Error("No access_token in response");

      sessionStorage.setItem("access_token", token);
      await apiFetch("/documents", { method: "GET" });
      window.location.reload();
    } catch (err) {
      setError(err?.message || "Register failed");
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
            <div className="brand-subtitle">Create account</div>
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
              placeholder="Choose a username"
            />
          </label>

          <label>
            <span>Email</span>
            <input
              className="field"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              placeholder="Optional email"
            />
          </label>

          <label>
            <span>Password</span>
            <input
              className="field"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              placeholder="Create a password"
            />
          </label>

          {error && <div className="alert error">{error}</div>}

          <button
            type="submit"
            className="primary-button full-width"
            disabled={!username.trim() || !password || loading}
          >
            {loading ? "Creating" : "Register"}
          </button>
        </form>

        <div className="auth-switch">
          <span>Already have an account?</span>
          <button type="button" onClick={onSwitchToLogin}>
            Login
          </button>
        </div>
      </section>
    </main>
  );
}
