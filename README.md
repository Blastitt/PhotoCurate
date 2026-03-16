# PhotoCurate

Multi-tenant SaaS platform for photographers — AI-powered photo scoring, client galleries, and cloud delivery.

## Features

- **AI Photo Scoring** — Automatic sharpness, exposure, composition, and aesthetic scoring using OpenCV, with optional Azure AI Vision for face analysis and embeddings
- **Duplicate Detection** — Perceptual hashing and embedding similarity to group near-duplicates
- **Auto-Pick** — Ranks photos by composite score, picks the best from each duplicate group, selects top N for the gallery
- **Client Galleries** — Shareable link with optional PIN protection; clients browse watermarked previews and submit selections
- **Watermarking** — Per-tenant logo overlay with configurable position, opacity, scale, and tiled mode
- **White Balance** — Auto (gray-world) or manual temperature/tint correction on gallery previews
- **Cloud Delivery** — Google Drive, Dropbox, and OneDrive integration via OAuth2
- **Adobe Lightroom Integration** — Optional OAuth2 connection to Adobe Lightroom Cloud; import photos from Lightroom albums, push originals back to Lightroom, and flag client selections directly in the photographer's catalog
- **Self-Hostable** — Abstractions over storage (Azure Blob / MinIO) and messaging (Azure Service Bus / NATS) with Docker Compose for single-node deployment

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+ (for the frontend)
- PostgreSQL 15+
- Redis 7+
- Poetry

### Backend

```bash
# Install dependencies
poetry install

# Copy environment config
cp .env.example .env
# Edit .env with your database credentials and JWT secret

# Run database migrations
poetry run alembic upgrade head

# Start development server
poetry run uvicorn photocurate.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on http://localhost:3000 and proxies API requests to the backend at http://localhost:8000.

### Docker Compose (Self-Hosted)

```bash
docker compose up -d
```

This starts the full stack: API (`:8000`), frontend (`:3000`), PostgreSQL, Redis, MinIO (`:9000`), and NATS.

### Backend Test Harness

Use the dedicated test Compose stack so integration tests do not share the development database:

```bash
docker compose -f docker-compose.test.yml up -d
pytest tests/test_auth_routes.py tests/test_session_routes.py tests/test_gallery_routes.py tests/test_scoring.py tests/test_delivery.py tests/test_infrastructure.py
```

The test harness defaults to `postgresql+asyncpg://photocurate_test:photocurate_test@127.0.0.1:5433/photocurate_test`.
Override it with `PHOTOCURATE_TEST_DATABASE_URL` if you need a different isolated database target.

## Project Structure

```
src/photocurate/
├── main.py                 # FastAPI app entrypoint
├── config.py               # Pydantic Settings configuration
├── core/                   # Shared domain models, abstractions
│   ├── models/             # SQLAlchemy ORM models
│   ├── schemas/            # Pydantic request/response schemas
│   ├── storage.py          # BlobStore ABC
│   └── queue.py            # MessageQueue ABC
├── api/                    # Core API (authenticated, photographer-facing)
│   ├── deps.py             # Dependency injection
│   ├── auth.py             # JWT authentication
│   └── routes/             # API route modules
│       ├── auth_routes.py      # Register, login, current user
│       ├── session_routes.py   # Sessions CRUD, uploads, finalize, LR import
│       ├── adobe_routes.py     # Adobe OAuth, Lightroom browse, feature flags
│       ├── client_routes.py    # Client management
│       └── gallery_routes.py   # Gallery creation, delivery, branding
├── gallery/                # Public gallery API (slug + PIN access)
│   └── routes.py
├── infrastructure/         # Cloud provider implementations
│   ├── azure_blob.py       # Azure Blob Storage
│   ├── minio_blob.py       # MinIO (S3-compatible)
│   ├── azure_queue.py      # Azure Service Bus
│   ├── nats_queue.py       # NATS
│   └── adobe_lightroom.py  # Adobe Lightroom API v2 client
└── workers/                # Background workers
    ├── scoring.py          # AI scoring (OpenCV + optional Azure AI Vision)
    ├── autopick.py         # Duplicate grouping + top-N auto-selection
    ├── image_processing.py # Resize, watermark, WB correction, EXIF strip
    ├── delivery.py         # Cloud storage delivery (Drive, Dropbox, OneDrive)
    └── lightroom_sync.py   # Push-to-Lightroom and flag-selection workers

frontend/
├── src/
│   ├── lib/
│   │   ├── api.ts              # Typed API client for all endpoints
│   │   ├── auth-context.tsx    # React auth context (JWT)
│   │   └── features-context.tsx # Feature-flag context (Adobe, etc.)
│   ├── components/
│   │   └── dashboard-shell.tsx # Sidebar layout with navigation
│   └── app/
│       ├── login/              # Login / register page
│       ├── dashboard/          # Photographer dashboard (auth required)
│       │   ├── sessions/       # Session list, create, detail (upload, review, gallery, WB settings)
│       │   ├── clients/        # Client management
│       │   ├── branding/       # Watermark logo + settings
│       │   └── settings/       # Integrations (Adobe Lightroom connection)
│       └── gallery/
│           └── [slug]/         # Public client gallery (PIN, photo grid, lightbox, selection)
├── Dockerfile
└── package.json
```

## API Endpoints

### Authenticated (photographer)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/register` | Register new account + tenant |
| POST | `/api/v1/auth/login` | Login, returns JWT |
| GET | `/api/v1/auth/me` | Current user info |
| POST | `/api/v1/sessions` | Create shoot session |
| GET | `/api/v1/sessions` | List sessions |
| GET | `/api/v1/sessions/:id` | Get session detail |
| PATCH | `/api/v1/sessions/:id` | Update session |
| DELETE | `/api/v1/sessions/:id` | Delete session |
| POST | `/api/v1/sessions/:id/upload-urls` | Get presigned upload URLs |
| POST | `/api/v1/sessions/:id/finalize` | Trigger AI processing |
| GET | `/api/v1/sessions/:id/photos` | List photos with AI scores |
| PATCH | `/api/v1/sessions/photos/:id` | Update photo status |
| PATCH | `/api/v1/sessions/:id/processing-config` | Update WB settings |
| POST | `/api/v1/sessions/:id/gallery` | Create shareable gallery |
| POST | `/api/v1/galleries/:id/deliver` | Trigger cloud delivery |
| GET | `/api/v1/tenants/branding` | Get watermark config |
| POST | `/api/v1/tenants/branding` | Update watermark config |
| POST | `/api/v1/tenants/branding/logo` | Upload watermark logo |
| POST | `/api/v1/clients` | Create client |
| GET | `/api/v1/clients` | List clients |
| DELETE | `/api/v1/clients/:id` | Delete client |
| POST | `/api/v1/sessions/:id/import-lightroom` | Import photos from a Lightroom album |
| GET | `/api/v1/adobe/connect` | Get Adobe OAuth2 authorization URL |
| GET | `/api/v1/adobe/callback` | Adobe OAuth2 callback |
| DELETE | `/api/v1/adobe/disconnect` | Disconnect Adobe account |
| GET | `/api/v1/adobe/status` | Check Adobe connection status |
| POST | `/api/v1/adobe/retry-pending` | Retry pending Lightroom tasks |
| GET | `/api/v1/adobe/albums` | List Lightroom albums |
| GET | `/api/v1/adobe/albums/:id/assets` | List assets in a Lightroom album |
| GET | `/api/v1/adobe/assets` | List Lightroom catalog assets |
| GET | `/api/v1/config/features` | Feature flags (Adobe enabled, etc.) |

### Public (client gallery)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/gallery/:slug` | Load gallery |
| POST | `/gallery/:slug/verify-pin` | Verify gallery PIN |
| GET | `/gallery/:slug/photos` | List gallery photos |
| POST | `/gallery/:slug/selections` | Submit photo selections |
| GET | `/gallery/:slug/status` | Check gallery status |

## Configuration

All settings are loaded from environment variables (`.env` file). See `.env.example` for the full list. Key settings:

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://...localhost/photocurate` | PostgreSQL connection string |
| `STORAGE_PROVIDER` | `minio` | `minio` or `azure` |
| `QUEUE_PROVIDER` | `nats` | `nats` or `azure_servicebus` |
| `JWT_SECRET_KEY` | — | Secret key for JWT tokens (change in production) |
| `AZURE_AI_VISION_ENDPOINT` | — | Optional: Azure AI Vision endpoint for face analysis |
| `AZURE_AI_VISION_KEY` | — | Optional: Azure AI Vision API key |
| `ADOBE_CLIENT_ID` | — | Optional: Adobe Developer Console client ID for Lightroom integration |
| `ADOBE_CLIENT_SECRET` | — | Optional: Adobe Developer Console client secret |
| `ADOBE_OAUTH_REDIRECT_URI` | — | Optional: OAuth2 callback URL (e.g. `http://localhost:3000/api/v1/adobe/callback`) |
| `ADOBE_TOKEN_ENCRYPTION_KEY` | — | Optional: Fernet key for encrypting stored Adobe tokens |

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
