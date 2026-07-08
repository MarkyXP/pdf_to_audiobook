# ebooks

A web application that converts PDF documents into audiobook-style WAV audio chunks using text-to-speech synthesis. Upload a PDF, pick a voice, and get a set of playable audio files — one per text chunk.

**Author:** Mark

## Overview

ebooks provides a simple web interface for turning PDF books into audio. It extracts text from a PDF, splits it into manageable chunks, and converts each chunk to speech using the [pocket-tts](https://github.com/kyutai-org/pocket-tts) engine. Processing happens asynchronously in the background, so the server stays responsive while jobs run.

The application includes both a web UI and a REST API, making it suitable for direct browser use or programmatic integration.

## Features

- **PDF upload or URL import** — upload a PDF file or provide a direct URL to a PDF
- **Voice selection** — choose from 8 built-in pocket-tts voices or clone a custom voice from a WAV file
- **Voice sampling** — preview any voice before committing to a conversion
- **Async job processing** — submit a job and poll for progress without blocking the server
- **Progress tracking** — real-time progress bar showing chunk completion percentage
- **Per-chunk audio files** — each text chunk is saved as an individual WAV file for flexible playback
- **HTMX-powered UI** — live-updating job list and progress without page reloads

## How It Works

1. A PDF is uploaded through the web UI or via the REST API (file or URL)
2. The server extracts text using `pdf-oxide` and splits it into chunks
3. Each chunk is converted to speech using the selected voice
4. Audio chunks are saved as WAV files in `output/{book_name}/`
5. The client polls for job status and downloads completed audio files

## Tech Stack

| Layer | Choice |
|---|---|
| Web framework | FastAPI + uvicorn |
| Frontend | Jinja2 templates + HTMX + Alpine.js |
| Styling | Tailwind CSS (CDN) |
| PDF extraction | pdf-oxide |
| TTS engine | pocket-tts |
| Audio I/O | scipy.io.wavfile |
| Config | pydantic_settings from `.env` |
| Package manager | uv |

## Key Dependencies

| Dependency | Purpose |
|---|---|
| [FastAPI](https://fastapi.tiangolo.com/) | Web framework |
| [pocket-tts](https://github.com/kyutai-org/pocket-tts) | Text-to-speech engine |
| [pdf-oxide](https://github.com/programatik29/pdf-oxide) | PDF text extraction |
| [Jinja2](https://jinja.palletsprojects.com/) | Server-side HTML templating |
| [uvicorn](https://www.uvicorn.org/) | ASGI server |
| [scipy](https://scipy.org/) | WAV file I/O |
| [python-multipart](https://github.com/Kludex/python-multipart) | Multipart form parsing |
| [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) | Settings management from `.env` |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | `.env` file parsing (via pydantic-settings) |

## Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://github.com/astral-sh/uv) package manager

### Local Development

```bash
# Clone the repository
git clone <repo-url>
cd pdf_to_audiobook

# Install dependencies
uv sync

# Edit environment variables (edit .env directly)
nano .env

# Run the server
uv run python main.py
```

The server starts on `http://localhost:8000` by default.

### Docker

```bash
docker compose up -d
```

The service will restart automatically unless explicitly stopped. See the [Docker Setup](#docker-setup) section below for the full configuration.

## Usage

### Web Interface

1. Open `http://localhost:8000` in your browser
2. Select a voice from the dropdown (click **Sample** to preview)
3. Upload a PDF file or paste a URL to a PDF
4. Click **Convert to Audio**
5. Monitor progress in the job list — click a job to see details and download audio

### REST API

```bash
# List available voices
curl http://localhost:8000/api/voices

# Upload a PDF
curl -X POST http://localhost:8000/api/upload \
  -F "file=@book.pdf" \
  -F "voice=alba"

# Or provide a URL instead
curl -X POST http://localhost:8000/api/upload \
  -F "url=https://example.com/book.pdf" \
  -F "voice=marius"

# Check job status
curl http://localhost:8000/api/jobs/{job_id}

# List all jobs
curl http://localhost:8000/api/jobs

# Download an audio file
curl -O http://localhost:8000/api/jobs/{job_id}/download/000.wav
```

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/voices` | List available voices (built-in + file-based) |
| `GET` | `/api/voices/{voice_name}/sample` | Play a voice sample |
| `POST` | `/api/upload` | Upload PDF or provide URL; returns `job_id` |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{job_id}` | Get job status and progress |
| `GET` | `/api/jobs/{job_id}/download/{filename}` | Download an audio file |

## Project Structure

```
ebooks/
├── main.py                # Entry point (starts uvicorn)
├── app/
│   ├── main.py            # FastAPI app factory, lifespan
│   ├── config.py           # Settings from .env
│   ├── pdf_parser.py       # PDF text extraction
│   ├── tts_engine.py       # TTS model wrapper (singleton)
│   ├── job_manager.py      # In-memory job store
│   ├── api/
│   │   └── routes.py       # API endpoints
│   └── web/
│       └── routes.py       # HTML page routes
├── templates/              # Jinja2 templates
│   ├── base.html
│   ├── index.html
│   ├── job_detail.html
│   └── partials/
│       ├── job_card.html
│       └── job_list_all.html
├── voices/                 # Custom voice WAV files (optional)
└── output/                 # Generated audio (gitignored)
```

## Docker Setup

### docker-compose.yml

```yaml
services:
  ebooks:
    build: .
    container_name: ebooks
    restart: unless-stopped
    ports:
      - "8000:8000"
    volumes:
      - ./output:/app/output
      - ./voices:/app/voices
    environment:
      - TZ=Australia/Melbourne
      - HOST=0.0.0.0
      - PORT=8000
      - OUTPUT_DIR=output
      - VOICE_DIR=voices
      - MAX_FILE_SIZE_MB=25
```

### Dockerfile

```dockerfile
FROM python:3.14-slim

ENV TZ=Australia/Melbourne
RUN apt-get update && apt-get install -y --no-install-recommends \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen

COPY . .

EXPOSE 8000

CMD ["uv", "run", "python", "main.py"]
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `TZ` | `Australia/Melbourne` | Timezone |
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Server port |
| `OUTPUT_DIR` | `output` | Root for generated audio |
| `VOICE_DIR` | `voices` | Directory containing custom voice WAV files |
| `MAX_FILE_SIZE_MB` | `25` | Max upload size in MB |

## AI Disclosure

This project was developed with the assistance of AI coding tools. AI was used primarily as an auto-complete and pair-programming aid throughout development. Every line of code was reviewed, tested, and co-authored with a human in the loop. The AI did not make architectural decisions, write documentation, or commit code without explicit human oversight and approval.

## Troubleshooting

- **No audio output** — ensure the `output/` directory exists and is writable. The server creates it on startup if missing.
- **Voice sampling fails** — pocket-tts voices require the model to be loaded. Wait a few seconds after server start before sampling.
- **Large PDFs fail** — increase `MAX_FILE_SIZE_MB` in `.env`. The default is 25 MB.
- **Docker timezone wrong** — verify `TZ=Australia/Melbourne` is set in both the `docker-compose.yml` environment block and the `Dockerfile` `ENV` directive.

## License

This project is licensed under the [MIT License](LICENSE).

Copyright (c) 2026 MarkyXP
