const API_BASE = "";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  // Don't set Content-Type for FormData (browser sets multipart boundary)
  if (options.body instanceof FormData) {
    delete headers["Content-Type"];
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || res.statusText);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

// ─── Auth ────────────────────────────────────────────────────────────────────

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: string;
  email: string;
  name: string;
  role: string;
  tenant_id: string;
}

export const auth = {
  register(data: {
    email: string;
    name: string;
    password: string;
    tenant_name: string;
    tenant_slug: string;
  }) {
    return request<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  login(email: string, password: string) {
    return request<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  me() {
    return request<UserResponse>("/api/v1/auth/me");
  },
};

// ─── Sessions ────────────────────────────────────────────────────────────────

export interface SessionResponse {
  id: string;
  tenant_id: string;
  photographer_id: string;
  client_id: string | null;
  title: string;
  description: string | null;
  shoot_date: string | null;
  status: string;
  auto_pick_count: number;
  ai_processing_enabled: boolean;
  lightroom_sync: boolean;
  lightroom_target_album_id: string | null;
  lightroom_target_album_name: string | null;
  wb_mode: string;
  wb_temp_shift: number;
  wb_tint_shift: number;
  wb_strength: number;
  created_at: string;
  updated_at: string;
}

export interface PhotoResponse {
  id: string;
  session_id: string;
  filename: string;
  file_size_bytes: number | null;
  width: number | null;
  height: number | null;
  mime_type: string | null;
  status: string;
  lightroom_asset_id: string | null;
  lightroom_sync_status: string | null;
  created_at: string;
  ai_score: AIScoreResponse | null;
  thumbnail_url: string | null;
  preview_url: string | null;
  face_center_x: number | null;
  face_center_y: number | null;
}

export interface AIScoreResponse {
  sharpness: number | null;
  exposure: number | null;
  composition: number | null;
  aesthetic: number | null;
  face_quality: number | null;
  uniqueness: number | null;
  composite_score: number;
  auto_picked: boolean;
  scored_at: string;
}

export interface PresignedURL {
  filename: string;
  upload_url: string;
  key: string;
}

export const sessions = {
  list() {
    return request<SessionResponse[]>("/api/v1/sessions");
  },

  get(id: string) {
    return request<SessionResponse>(`/api/v1/sessions/${encodeURIComponent(id)}`);
  },

  create(data: {
    title: string;
    description?: string;
    shoot_date?: string;
    client_id?: string;
    auto_pick_count?: number;
    ai_processing_enabled?: boolean;
    lightroom_sync?: boolean;
    lightroom_target_album_id?: string;
    lightroom_target_album_name?: string;
  }) {
    return request<SessionResponse>("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  update(
    id: string,
    data: Partial<{
      title: string;
      description: string;
      shoot_date: string;
      client_id: string;
      auto_pick_count: number;
      status: string;
      ai_processing_enabled: boolean;
      lightroom_sync: boolean;
      lightroom_target_album_id: string;
      lightroom_target_album_name: string;
    }>,
  ) {
    return request<SessionResponse>(`/api/v1/sessions/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  },

  delete(id: string) {
    return request<void>(`/api/v1/sessions/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  getUploadUrls(id: string, filenames: string[]) {
    return request<{ urls: PresignedURL[] }>(
      `/api/v1/sessions/${encodeURIComponent(id)}/upload-urls`,
      {
        method: "POST",
        body: JSON.stringify({ filenames }),
      },
    );
  },

  finalize(id: string) {
    return request<{ detail: string; session_id: string }>(
      `/api/v1/sessions/${encodeURIComponent(id)}/finalize`,
      { method: "POST" },
    );
  },

  listPhotos(id: string) {
    return request<PhotoResponse[]>(
      `/api/v1/sessions/${encodeURIComponent(id)}/photos`,
    );
  },

  updatePhoto(
    photoId: string,
    data: { status?: string },
  ) {
    return request<PhotoResponse>(
      `/api/v1/sessions/photos/${encodeURIComponent(photoId)}`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
    );
  },

  updateProcessingConfig(
    id: string,
    data: {
      wb_mode?: string;
      wb_temp_shift?: number;
      wb_tint_shift?: number;
      wb_strength?: number;
    },
  ) {
    return request<SessionResponse>(
      `/api/v1/sessions/${encodeURIComponent(id)}/processing-config`,
      {
        method: "PATCH",
        body: JSON.stringify(data),
      },
    );
  },
};

// ─── Clients ─────────────────────────────────────────────────────────────────

export interface ClientResponse {
  id: string;
  tenant_id: string;
  name: string;
  email: string | null;
  created_at: string;
}

export const clients = {
  list() {
    return request<ClientResponse[]>("/api/v1/clients");
  },

  get(id: string) {
    return request<ClientResponse>(`/api/v1/clients/${encodeURIComponent(id)}`);
  },

  create(data: { name: string; email?: string }) {
    return request<ClientResponse>("/api/v1/clients", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  delete(id: string) {
    return request<void>(`/api/v1/clients/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },
};

// ─── Galleries ───────────────────────────────────────────────────────────────

export interface GalleryResponse {
  id: string;
  session_id: string;
  slug: string;
  max_selections: number | null;
  expires_at: string | null;
  status: string;
  created_at: string;
  gallery_url: string | null;
}

export interface DeliveryResponse {
  id: string;
  session_id: string;
  provider: string;
  provider_folder_url: string | null;
  status: string;
  photo_count: number | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_at: string;
}

export interface BrandingResponse {
  watermark_logo_key: string | null;
  watermark_logo_url: string | null;
  watermark_opacity: number;
  watermark_position: string;
  watermark_scale: number;
  watermark_padding: number;
  watermark_tile_rotation: number;
  watermark_tile_spacing: number;
}

export const galleries = {
  create(
    sessionId: string,
    data: {
      pin?: string;
      max_selections?: number;
      photo_ids?: string[];
    },
  ) {
    return request<GalleryResponse>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/gallery`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  },

  deliver(
    galleryId: string,
    data: { provider: string; access_token?: string },
  ) {
    return request<DeliveryResponse>(
      `/api/v1/galleries/${encodeURIComponent(galleryId)}/deliver`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  },

  uploadEdited(sessionId: string) {
    return request<{ urls: string[] }>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/edited`,
      { method: "POST" },
    );
  },

  getSelections(sessionId: string) {
    return request<SelectionDetailResponse[]>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/selections`,
    );
  },
};

// ─── Branding ────────────────────────────────────────────────────────────────

export const branding = {
  get() {
    return request<BrandingResponse>("/api/v1/tenants/branding");
  },

  update(data: {
    watermark_opacity?: number;
    watermark_position?: string;
    watermark_scale?: number;
    watermark_padding?: number;
    watermark_tile_rotation?: number;
    watermark_tile_spacing?: number;
  }) {
    return request<BrandingResponse>("/api/v1/tenants/branding", {
      method: "POST",
      body: JSON.stringify(data),
    });
  },

  uploadLogo(file: File) {
    const form = new FormData();
    form.append("file", file);
    return request<BrandingResponse>("/api/v1/tenants/branding/logo", {
      method: "POST",
      body: form,
    });
  },
};

// ─── Public Gallery ──────────────────────────────────────────────────────────

export interface GalleryPublicResponse {
  slug: string;
  max_selections: number | null;
  status: string;
  photos: GalleryPhotoPublic[];
}

export interface GalleryPhotoPublic {
  id: string;
  thumbnail_url: string | null;
  preview_url: string | null;
  face_center_x: number | null;
  face_center_y: number | null;
  sort_order: number;
}

export interface SelectionResponse {
  id: string;
  gallery_id: string;
  client_name: string | null;
  client_email: string | null;
  notes: string | null;
  submitted_at: string;
  photo_count: number;
}

export interface SelectionDetailResponse {
  id: string;
  gallery_id: string;
  client_name: string | null;
  client_email: string | null;
  notes: string | null;
  submitted_at: string;
  photo_ids: string[];
}

export const publicGallery = {
  get(slug: string, token?: string) {
    const qs = token ? `?token=${encodeURIComponent(token)}` : "";
    return request<GalleryPublicResponse>(`/api/v1/gallery/${encodeURIComponent(slug)}${qs}`);
  },

  verifyPin(slug: string, pin: string) {
    return request<{ valid: boolean; token?: string }>(
      `/api/v1/gallery/${encodeURIComponent(slug)}/verify-pin`,
      {
        method: "POST",
        body: JSON.stringify({ pin }),
      },
    );
  },

  listPhotos(slug: string) {
    return request<GalleryPhotoPublic[]>(`/api/v1/gallery/${encodeURIComponent(slug)}/photos`);
  },

  submitSelection(
    slug: string,
    data: {
      photo_ids: string[];
      client_name?: string;
      client_email?: string;
      notes?: string;
    },
  ) {
    return request<SelectionResponse>(
      `/api/v1/gallery/${encodeURIComponent(slug)}/selections`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  },

  status(slug: string) {
    return request<{ slug: string; status: string; max_selections: number | null }>(
      `/api/v1/gallery/${encodeURIComponent(slug)}/status`,
    );
  },
};

// ─── Features ────────────────────────────────────────────────────────────────

export interface FeaturesResponse {
  adobe_lightroom: boolean;
}

export const features = {
  get() {
    return request<FeaturesResponse>("/api/v1/config/features");
  },
};

// ─── Adobe Lightroom ─────────────────────────────────────────────────────────

export interface AdobeStatusResponse {
  connected: boolean;
  catalog_id: string | null;
  pending_task_count: number;
}

export interface AdobeConnectResponse {
  redirect_url: string;
}

export const adobe = {
  connect() {
    return request<AdobeConnectResponse>("/api/v1/adobe/connect");
  },

  disconnect() {
    return request<{ detail: string }>("/api/v1/adobe/disconnect", {
      method: "DELETE",
    });
  },

  status() {
    return request<AdobeStatusResponse>("/api/v1/adobe/status");
  },

  retryPending() {
    return request<{ retried: number }>("/api/v1/adobe/retry-pending", {
      method: "POST",
    });
  },

  listAlbums(limit = 50, after?: string) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (after) params.set("after", after);
    return request<any>(`/api/v1/adobe/albums?${params}`);
  },

  listAlbumAssets(albumId: string, limit = 50, after?: string) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (after) params.set("after", after);
    return request<any>(
      `/api/v1/adobe/albums/${encodeURIComponent(albumId)}/assets?${params}`,
    );
  },

  listAssets(limit = 50, after?: string) {
    const params = new URLSearchParams({ limit: String(limit) });
    if (after) params.set("after", after);
    return request<any>(`/api/v1/adobe/assets?${params}`);
  },

  importToSession(
    sessionId: string,
    data: { asset_ids?: string[]; album_id?: string },
  ) {
    return request<{ detail: string; imported_count: number; photo_ids: string[] }>(
      `/api/v1/sessions/${encodeURIComponent(sessionId)}/import-lightroom`,
      {
        method: "POST",
        body: JSON.stringify(data),
      },
    );
  },
};
