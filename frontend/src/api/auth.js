import { apiFetch } from "./client";

export async function login(username, password) {
  const formBody = new URLSearchParams();
  formBody.append("username", username);
  formBody.append("password", password);

  return apiFetch("/auth/login", {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body: formBody.toString(),
  });
}
