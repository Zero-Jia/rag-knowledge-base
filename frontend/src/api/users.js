import { apiFetch } from "./client";

/**
 * Register new user: POST /users/
 * payload: { username, email?, password }
 */
export async function registerUser({ username, email, password }) {
  return apiFetch("/users/", {
    method: "POST",
    body: JSON.stringify({
      username,
      email,
      password,
    }),
  });
}