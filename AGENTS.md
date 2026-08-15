# 🤖 AGENTS.md - AI Developer Guide for SSR_CLIPPER

## 📌 Project Overview
**SSR_CLIPPER** is a desktop application that automates the creation of short-form content (TikTok, Reels, Shorts) from long-form YouTube videos. It leverages AI (GPT-4, Whisper) for highlight detection and captioning, and Computer Vision (OpenCV/MediaPipe) for smart cropping.

## 🏗️ Architecture & Tech Stack

### Core Technology
- **Language**: Python 3.10+
- **Desktop shell**: pywebview (native window wrapping a local web UI)
- **Frontend**: Plain HTML/CSS/JS in `web/` (no framework, no build step)
- **Video Processing**: FFmpeg (via subprocess), OpenCV (face detection), MediaPipe (speaker tracking)
- **Downloading**: yt-dlp
- **AI/ML**:
  - **LLM**: OpenAI-compatible API (GPT-4, Gemini, Groq, YTClip AI, etc. — see `config/ai_provider_config.py`)
  - **Transcription**: OpenAI Whisper API
  - **TTS**: OpenAI TTS (for hooks)

### High-Level Structure
1. **Entry point**: `app.py`
   - `main()` creates a `pywebview` window that loads `web/index.html`.
   - The `WebAPI` class in `app.py` is exposed to the frontend as `js_api=api`.
   - The frontend (`web/app.js` and `web/components/*.js`) calls Python methods via `window.pywebview.api.<method_name>(...)`. There is **no separate REST server** — all Python↔JS communication goes through this bridge.
   - There is no CustomTkinter GUI anymore — the old `pages/`, `dialogs/`, `components/` (CustomTkinter) and `app_tkinter_backup.py` have been removed as dead code.

2. **Backend (Logic)**:
   - `clipper_core.py`: **The Brain**. Contains the `AutoClipperCore` class which orchestrates the entire pipeline:
     1. Download (`download_video`)
     2. Parse Subtitles (`parse_srt`)
     3. AI Highlight Detection (`find_highlights`)
     4. Video Processing (`process_clip`: cut -> portrait -> hook -> captions)

3. **Data & Config**:
   - `config.json`: Stores user settings (API keys, preferences). Managed by `ConfigManager` (`config/config_manager.py`).
   - `cookies.txt`: Required for YouTube authentication (handled by `COOKIES.md` guide).
   - `output/`: Generated clips and metadata (`data.json`).

## 📂 Key Directories & Files

| Path | Description |
|------|-------------|
| **`app.py`** | Entry point. Creates the pywebview window and exposes `WebAPI` (all functions the frontend can call). |
| **`clipper_core.py`** | Core business logic. Contains all video processing and AI interaction code (`AutoClipperCore`). |
| **`web/`** | The actual UI — `index.html`, `app.js`, `css/`, `components/`. This is what renders inside the pywebview window. |
| **`config/`** | `ai_provider_config.py` (provider definitions), `config_manager.py` (read/write `config.json`). |
| **`utils/`** | Helper utilities (`gpu_detector.py`, `dependency_manager.py`, `helpers.py`, `logger.py`, `font_scanner.py`). |
| **`assets/`** | Images and icons. |
| **`build.spec` / `build_macos.spec` / `build_web.spec`** | PyInstaller configs — all three build from `app.py` only. |

## 🔄 Core Workflows

### 1. Highlight Detection Flow
`clipper_core.py` -> `find_highlights`:
1.  Reads `.srt` file from download.
2.  Constructs a prompt using the AI highlight-finding logic + Transcript.
3.  Sends to LLM (GPT-4/Gemini/etc., per configured provider).
4.  Parses JSON response containing start/end timestamps and hook text.

### 2. Portrait Conversion Flow
`clipper_core.py` -> `convert_to_portrait_mediapipe` / `convert_to_portrait_opencv`:
1.  **Face Detection**: Uses OpenCV/MediaPipe to find faces in frames.
2.  **Active Speaker**: Analyzes lip movement (if MediaPipe) or simplistic face tracking (OpenCV).
3.  **Cropping**: calculates the 9:16 crop window, ensuring smooth transitions (simulated camera cuts).

### 3. Captioning Flow
`clipper_core.py` -> `add_captions_api_with_progress`:
1.  Extracts audio from cut clip.
2.  Sends to Whisper API -> gets word-level timestamps.
3.  Generates `.ass` subtitle file with specific styling (Yellow highlight, specific font).
4.  Burns into video using FFmpeg.

## 🛠️ Development Setup

### Requirements
- **FFmpeg** and **yt-dlp** must be in PATH or configured.
- `requirements.txt` contains Python libs.

### Running Locally
```bash
pip install -r requirements.txt
python app.py
