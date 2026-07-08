# ebooks — PDF-to-Audio FastAPI Backend

## Brief

A FastAPI backend that accepts PDF uploads, extracts text, converts it to speech via `pocket_tts`, and saves WAV audio chunks. Processing is async — clients submit a job, poll for status.

## Tech Stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI + uvicorn |
| Frontend | Jinja2 templates + HTMX + Alpine.js |
| PDF extraction | `pdf-oxide` (`from pdf_oxide import PdfDocument`) |
| TTS engine | `pocket_tts` (`TTSModel`, voice via WAV) |
| Audio I/O | `scipy.io.wavfile` |
| Config | `.env` (python-dotenv) |
| Output format | WAV |

## Frontend

Jinja2 templates served by FastAPI's `Jinja2Templates`. No SPA — the frontend is server-rendered HTML with HTMX for AJAX calls and Alpine.js for local state logic.

### Pages

| Route | Template | Description |
|---|---|---|
| `GET /` | `index.html` | Home: upload form + job list |
| `GET /jobs/{job_id}` | `job_detail.html` | Job detail: progress, audio file list |

### HTMX Interactions

- Upload form submits via `fetch` POST to `/api/upload` (Alpine.js handles form submit) → shows success message with job link
- Job list polls via `hx-get` + `hx-swap="innerHTML"` every 5s for all jobs (`/jobs/list-all`)
- Job detail page polls status updates via HTMX polling (not yet implemented in job_detail.html)
- Alpine.js manages: selected voice dropdown, file drag-and-drop state, form validation, upload state

### Template Structure

```
templates/
├── base.html              # HTML skeleton, CDN links (htmx, alpine, tailwind)
├── index.html             # Upload form + job list overview
├── job_detail.html        # Single job: progress bar, audio chunk list
├── partials/
│   ├── job_card.html      # Individual job card (for list and swap)
│   └── job_list_all.html  # All job cards (for HTMX swap)
└── components/            # (empty - voice selector is inline in index.html)
```

### Styling

Tailwind CSS via CDN (no build step). Clean, minimal design — upload area, job cards, progress bars, audio file list.

## Chunking Strategy

Paragraph-level: text is split on blank lines (paragraph boundaries). Each paragraph becomes one WAV file.

## Project Structure

```
ebooks/
├── AGENTS.md              # This file
├── pyproject.toml
├── .env                   # All config variables
├── .env.example           # Template for .env
├── main.py                # Entry point (starts uvicorn)
│
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app factory, lifespan (load TTS model once)
│   ├── config.py           # Pydantic Settings from .env
│   ├── pdf_parser.py       # PDF -> paragraph list (pdf-oxide)
│   ├── tts_engine.py       # TTSModel wrapper, voice loading, audio generation
│   ├── job_manager.py      # In-memory job store (status, progress, book name)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py       # API endpoints (upload, status, list)
│   └── web/
│       ├── __init__.py
│       └── routes.py       # HTML page routes (index, job detail)
│
├── templates/              # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   ├── job_detail.html
│   ├── partials/
│   │   ├── job_card.html
│   │   └── upload_response.html
│   └── components/
│       └── voice_selector.html
│
├── static/                 # Static assets (if any)
│
├── voices/                 # Voice WAV files on disk
│
└── output/                 # Generated audio (gitignored)
    └── {book_name}/
        ├── 000.wav
        ├── 001.wav
        └── ...
```

## .env Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Server port |
| `OUTPUT_DIR` | `output` | Root for generated audio |
| `VOICE_DIR` | `voices` | Directory containing voice WAV files |
| `MAX_FILE_SIZE_MB` | `25` | Max upload size in MB |
| `TTS_MODEL_PATH` | (empty) | Custom TTS model path (empty = use default loading) |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/voices` | List available voices (filenames in `VOICE_DIR`) |
| `GET` | `/api/voices/{voice_name}/sample` | Play/sample a voice WAV file |
| `POST` | `/api/upload` | Upload PDF (`multipart/form-data`). Body: `file` + `voice` (name). Returns `job_id`. |
| `GET` | `/api/jobs/{job_id}` | Get job status: `pending`, `processing`, `completed`, `failed`. Includes progress. |
| `GET` | `/api/jobs` | List all jobs (ids + statuses) |
| `GET` | `/api/jobs/{job_id}/download/{filename}` | Download a specific audio file from a completed job |

## Web Routes (HTML)

| Method | Path | Template | Description |
|---|---|---|---|
| `GET` | `/` | `index.html` | Home page: upload form + job list |
| `GET` | `/jobs/list` | `partials/job_card.html` | Single job card partial (first job only) |
| `GET` | `/jobs/list-all` | `partials/job_list_all.html` | All job cards partial for HTMX swap |
| `GET` | `/jobs/{job_id}` | `job_detail.html` | Job detail with progress and audio list |

Upload form uses Alpine.js `fetch` POST to `/api/upload`. Job list auto-polls via HTMX `hx-get` to `/jobs/list-all` with `hx-trigger="every 5s"`.

## Processing Flow

1. Client POSTs `/api/upload` with PDF + optional voice name (via Alpine.js `fetch`)
2. Server validates file (extension, size), picks a default voice if none specified
3. Job is created with status `pending` → immediately starts `processing`
4. Background task (`asyncio.create_task`):
   a. Extract paragraphs from PDF via `pdf-oxide`
   b. Load voice WAV via `TTSModel.get_state_for_audio_prompt()`
   c. For each paragraph, generate audio via `TTSModel.generate_audio()`
   d. Save as `output/{book_name}/{idx:03d}.wav` using `scipy.io.wavfile.write`
   e. Update job status to `completed`
5. Client polls `/api/jobs/{job_id}` until status is `completed` or `failed`
6. Client can download individual audio files via `/api/jobs/{job_id}/download/{filename}`

## Voice Selection

- Server scans `voices/` directory for `.wav` files at startup
- Client picks a voice by name in the upload request
- If no voice specified, server uses the first voice alphabetically
- Voice WAV files are loaded once per job (not cached globally, since pocket_tts may not support concurrent access)

## Constraints

- Only `.pdf` uploads accepted
- All variables (port, dirs, limits) from `.env`
- Async processing — no blocking uploads
- Output is flat WAV files per book, no sub-chapters
- Frontend: server-rendered Jinja2, HTMX for AJAX, Alpine.js for local state, Tailwind via CDN
- No build step — no webpack, no Vite, no npm
- Templates live in `templates/`, API routes in `app/api/`, web routes in `app/web/`
