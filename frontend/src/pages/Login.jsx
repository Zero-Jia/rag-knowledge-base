import { useState } from "react";
import { login } from "../api/auth";
import { apiFetch } from "../api/client";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [me, setMe] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setMe(null);

    try {
      // 🔐 调用登录接口
      const data = await login(username, password);

      // ✅ 兼容两种返回：
      // 1) { access_token: "..." }
      // 2) { token: "..." }
      const token = data?.access_token || data?.token;
      if (!token) throw new Error("No access_token in response");

      // ✅ 保存 token
      localStorage.setItem("access_token", token);

      alert("Login success");

      // ✅ 验收点：调用一个需要鉴权的接口，确保 token 有效
      const docs = await apiFetch("/documents", { method: "GET" });
      setMe({ ok: true, preview: docs });

      // 🔥 关键：强制刷新，让 App 重新读取 token
      window.location.reload();
    } catch (err) {
      setError(err?.message || "Login failed");
    }
  }

  return (
    <div style={{ maxWidth: 360, margin: "60px auto", fontFamily: "sans-serif" }}>
      <form onSubmit={handleSubmit} style={{ display: "grid", gap: 12 }}>
        <h2>Login</h2>

        <input
          placeholder="username"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
        />

        <input
          type="password"
          placeholder="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />

        <button type="submit" disabled={!username || !password}>
          Login
        </button>

        {error && <p style={{ color: "red" }}>{error}</p>}
        {me && (
          <pre style={{ background: "#f6f6f6", padding: 12, overflow: "auto" }}>
            {JSON.stringify(me.preview, null, 2)}
          </pre>
        )}
      </form>

      <div style={{ marginTop: 16, fontSize: 12, opacity: 0.7 }}>
        Tip: 打开 DevTools → Application → Local Storage 查看 access_token
      </div>
    </div>
  );
}
