// Si no se fija VITE_API_URL a mano, hay dos casos:
// - En desarrollo (Vite corriendo en :5173, o su "preview" en :4173) el backend
//   corre aparte, en el puerto 8000 del mismo host -- así funciona solo tanto en
//   localhost como desde el celular entrando por la IP de la compu en la red
//   local o por Tailscale, sin tener que reconfigurar nada por dispositivo.
// - En producción con un solo contenedor (Railway, por ejemplo: ver Dockerfile),
//   el propio backend FastAPI sirve este frontend ya compilado desde el MISMO
//   origen (mismo dominio, mismo puerto, HTTPS) -- ahí NO hay que agregarle
//   ningún puerto, las rutas /api/* ya caen en el lugar correcto solas. Agregar
//   ":8000" ahí apunta a un puerto que no existe desde afuera (y encima por
//   http:// en una página https://), lo que da "Failed to fetch" en el login.
function resolveApiUrl(): string {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  const { hostname, port } = window.location;
  if (port === "5173" || port === "4173") {
    return `http://${hostname}:8000`;
  }
  return "";
}

const API_URL = resolveApiUrl();

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
