# ebooks — PDF-to-Audio FastAPI Backend

## Brief

A FastAPI backend that accepts PDF uploads, extracts text, converts it to speech via `pocket_tts`, and saves WAV audio chunks. Processing is async — clients submit a job, poll for status.

## Tech Stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI + uvicorn |
| Frontend | Jinja2 templates + HTMX + Alpine.js |
| PDF extraction | `pdf-oxide` (`from pdf_oxide import PdfDocument`) |
| TTS engine | `pocket_tts` (`TTSModel`, built-in voices + WAV cloning) |
| Audio I/O | `scipy.io.wavfile` |
| Config | `pydantic_settings.BaseSettings` from `.env` |
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
- Job list on index page polls via `hx-get` + `hx-swap="innerHTML"` every 5s (`/jobs/list-all`)
- Job detail page polls via `hx-get` + `hx-swap="outerHTML"` every 2s while job is processing
- Alpine.js manages: voice selector, source mode toggle (file vs URL), file drag-and-drop, form validation, upload state, voice sampling

### Template Structure

```
templates/
├── base.html              # HTML skeleton, CDN links (htmx, alpine, tailwind)
├── index.html             # Upload form (file + URL modes) + job list overview
├── job_detail.html        # Single job: progress bar, audio chunk list
├── partials/
│   ├── job_card.html      # Individual job card (for /jobs/list)
│   └── job_list_all.html  # All job cards (for HTMX swap on index)
└── components/            # (empty directory)
```

### Styling

Tailwind CSS via CDN (no build step). Clean, minimal design — upload area, job cards, progress bars, audio file list.

## Chunking Strategy

Line-level with merging: text is split on newlines, then consecutive short lines (<100 characters) are merged into a single chunk. Long lines (&ge;100 chars) stand alone. Each chunk becomes one WAV file.

## Project Structure

```
ebooks/
├── AGENTS.md              # This file
├── pyproject.toml
├── .env                   # All config variables
├── main.py                # Entry point (starts uvicorn)
│
├── app/
│   ├── __init__.py
│   ├── main.py            # FastAPI app factory, lifespan (ensure dirs exist)
│   ├── config.py           # pydantic_settings.BaseSettings from .env
│   ├── pdf_parser.py       # PDF -> text chunks (pdf-oxide)
│   ├── tts_engine.py       # TTSModel wrapper, voice loading, audio generation (module-level singleton)
│   ├── job_manager.py      # In-memory job store (status, progress, book name)
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes.py       # API endpoints (upload, status, list, voices)
│   └── web/
│       ├── __init__.py
│       └── routes.py       # HTML page routes (index, job detail, job list partials)
│
├── templates/              # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   ├── job_detail.html
│   ├── partials/
│   │   ├── job_card.html
│   │   └── job_list_all.html
│   └── components/         # (empty directory)
│
├── voices/                 # Custom voice WAV files on disk (optional)
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
| `VOICE_DIR` | `voices` | Directory containing custom voice WAV files |
| `MAX_FILE_SIZE_MB` | `25` | Max upload size in MB |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/voices` | List available voices (built-in + file-based) |
| `GET` | `/api/voices/{voice_name}/sample` | Play/sample a voice (built-in: generated on-the-fly; file-based: served directly) |
| `POST` | `/api/upload` | Upload PDF or provide URL (`multipart/form-data`). Body: `file` **or** `url` + `voice` (name). Returns `job_id`. |
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

Upload form uses Alpine.js `fetch` POST to `/api/upload`. Supports both file upload and URL input via a toggle. Job list auto-polls via HTMX `hx-get` to `/jobs/list-all` with `hx-trigger="every 5s"`.

## Processing Flow

1. Client POSTs `/api/upload` with PDF file **or** URL + optional voice name (via Alpine.js `fetch`)
2. Server validates input (file extension/size or URL format), picks a default voice if none specified
3. Job is created with status `pending` → immediately starts `processing`
4. Background task (`asyncio.create_task`):
   a. Extract text chunks from PDF via `pdf-oxide` (splits on newlines, merges short lines <100 chars)
   b. Load voice via `TTSModel.get_state_for_audio_prompt()` (built-in name or WAV file path)
   c. For each chunk, generate audio via `TTSModel.generate_audio()` in a thread pool
   d. Save as `output/{book_name}/{idx:03d}.wav` using `scipy.io.wavfile.write`
   e. Update job status to `completed`
5. Client polls `/api/jobs/{job_id}` until status is `completed` or `failed`
6. Client can download individual audio files via `/api/jobs/{job_id}/download/{filename}`

## Voice Selection

- **Built-in voices**: pocket_tts ships with 8 built-in voices (alba, marius, javert, jean, fantine, cosette, eponine, azelma). These are used by name directly.
- **Custom voices**: Server also scans `voices/` directory for `.wav` files. These are cloned via `TTSModel.get_state_for_audio_prompt()`.
- Client picks a voice by name in the upload request (built-in or file-based).
- If no voice specified, server defaults to the first built-in voice (`alba`).
- Voice state is loaded once per job (not cached globally, since pocket_tts may not support concurrent access).
- The TTS model is loaded as a module-level singleton (`tts_engine = TTSEngine()`) — loaded when the module is imported, not in the lifespan.

## Constraints

- Only `.pdf` uploads accepted
- All variables (port, dirs, limits) from `.env`
- Async processing — no blocking uploads
- Output is flat WAV files per book, no sub-chapters
- Frontend: server-rendered Jinja2, HTMX for AJAX, Alpine.js for local state, Tailwind via CDN
- No build step — no webpack, no Vite, no npm
- Templates live in `templates/`, API routes in `app/api/`, web routes in `app/web/`
