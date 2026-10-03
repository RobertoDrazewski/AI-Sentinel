// Si no se fija VITE_API_URL a mano, usamos el mismo host con el que se abrió la
// página (window.location.hostname). Así funciona solo tanto en localhost como
// desde el celular entrando por la IP de la compu en la red local (ej 192.168.x.x),
// sin tener que reconfigurar nada por dispositivo.
const API_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;

function getToken(): string | null {
  return localStorage.getItem("centinela_token");
}

export function setToken(token: string) {
  localStorage.setItem("centinela_token", token);
}

export function clearToken() {
  localStorage.removeItem("centinela_token");
}

export function streamUrl(cameraId: number): string {
  const token = getToken();
  return `${API_URL}/api/stream/${cameraId}?token=${encodeURIComponent(token || "")}`;
}

export function mediaUrl(path: string): string {
  if (!path) return "";
  // path viene del backend como ruta de archivo tipo "app/snapshots/xxx.jpg"
  const filename = path.split("/").pop();
  if (path.includes("snapshots")) return `${API_URL}/media/snapshots/${filename}`;
  if (path.includes("known_faces")) return `${API_URL}/media/faces/${filename}`;
  return path;
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>)
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!(options.body instanceof FormData) && options.body) {
    headers["Content-Type"] = "application/json";
  }

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch {
      // nada, usamos statusText
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form })
};
