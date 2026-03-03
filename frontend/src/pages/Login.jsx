import { useState } from "react";
import { login } from "../api/auth";
import { apiFetch } from "../api/client";

export default function Login() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const data = await login(username, password);
      const token = data?.access_token || data?.token;
      if (!token) throw new Error("No access_token in response");

      localStorage.setItem("access_token", token);

      // 验证 token 是否有效
      await apiFetch("/documents", { method: "GET" });

      window.location.reload();
    } catch (err) {
      setError(err?.message || "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center px-4">
      <div className="w-full max-w-md bg-white rounded-xl shadow-sm p-8 space-y-6">
        
        <div className="text-center">
          <h1 className="text-2xl font-semibold">
            RAG Knowledge Base
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Sign in to continue
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          
          <div>
            <label className="text-sm font-medium">
              Username
            </label>
            <input
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full mt-1 border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-black"
              placeholder="Enter username"
            />
          </div>

          <div>
            <label className="text-sm font-medium">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full mt-1 border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-black"
              placeholder="Enter password"
            />
          </div>

          {error && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!username || !password || loading}
            className="w-full py-2 rounded-lg bg-black text-white font-medium hover:bg-gray-800 disabled:bg-gray-400 transition"
          >
            {loading ? "Signing in..." : "Login"}
          </button>
        </form>

        <div className="text-xs text-gray-400 text-center">
          Tip: Token will be stored in LocalStorage
        </div>
      </div>
    </div>
  );
}