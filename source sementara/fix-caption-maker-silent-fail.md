# Fix: Caption Maker Silently Skips Subtitles

**Branch:** `feature/pywebview-desktop-integration`
**Files:** `app.py`, `clipper_core.py`
**Status:** Diagnosed + patch verified (`python3 -m py_compile` passed)

## Root Cause

`add_captions_api_with_progress()` in `clipper_core.py` is the function `process_clip()` calls when the Caption Maker toggle is on. Every failure point inside it (audio extraction fail, empty/tiny audio, Whisper transcription exception) was caught and handled by logging a soft `Warning:` line, copying the original clip to `output_path` with no captions, then `return`-ing normally.

`process_clip()` only checks `if not final_file.exists(): raise ...`. Since the silent-copy fallback still creates the output file, that check passes, the log prints `✓ Added captions`, and the whole pipeline reports success — but the final video has zero subtitles and there's no error anywhere.

Secondary bug in `app.py`: `local_whisper_settings` was built with key `"model"`, but `AutoClipperCore._load_local_whisper()` reads `settings.get("model_size", ...)`. Key mismatch means any local Whisper model the user picks in settings (e.g. `medium`) is silently ignored and the app always loads `large-v3-turbo`.

## Fix Summary

Replace every silent `log warning → shutil.copy → return` fallback in `add_captions_api_with_progress()` with `raise Exception(...)`. These exceptions already propagate correctly through `process_clip()` → `process()` → `app.py`'s `_run()`, which already does `self.status = f"error: {e}"` — so the UI will actually show the failure instead of hiding it.

Also added a guard: if Whisper transcription succeeds but returns an empty `transcript` (no `words` and no `segments`), raise instead of silently burning an empty subtitle track.

Fixed the `app.py` key mismatch: `"model"` → `"model_size"`.

## Instructions for Gemini (apply to local repo)

Open `clipper_core.py`, locate the method `add_captions_api_with_progress`. Make these three edits inside it, in order.

### Edit 1 — audio extraction / audio file checks

Find:

```python
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        
        if result.returncode != 0:
            self.log(f"  Warning: Audio extraction failed")
            import shutil
            shutil.copy(input_path, output_path)
            return
        
        if progress_callback:
            progress_callback(0.2)
        
        # Check if audio file exists
        if not os.path.exists(audio_file) or os.path.getsize(audio_file) < 1000:
            self.log(f"  Warning: Audio file too small or missing")
            import shutil
            shutil.copy(input_path, output_path)
            if os.path.exists(audio_file):
                os.unlink(audio_file)
            return
```

Replace with:

```python
        result = subprocess.run(cmd, capture_output=True, text=True, creationflags=SUBPROCESS_FLAGS)
        
        if result.returncode != 0:
            self.log(f"  ❌ Audio extraction failed, cannot generate captions")
            self.log(f"  FFmpeg stderr: {result.stderr[-500:] if result.stderr else 'none'}")
            if os.path.exists(audio_file):
                os.unlink(audio_file)
            raise Exception(f"Audio extraction for captions failed: {result.stderr[-300:] if result.stderr else 'unknown FFmpeg error'}")
        
        if progress_callback:
            progress_callback(0.2)
        
        # Check if audio file exists
        if not os.path.exists(audio_file) or os.path.getsize(audio_file) < 1000:
            self.log(f"  ❌ Audio file too small or missing, cannot generate captions")
            if os.path.exists(audio_file):
                os.unlink(audio_file)
            raise Exception("Extracted audio file is missing or too small — source clip may have no audio track")
```

### Edit 2 — Whisper transcription failure + empty-transcript guard

Find:

```python
        # Transcribe using Whisper (local or API based on settings)
        try:
            transcript = self._whisper_transcribe_words(audio_file)
        except Exception as e:
            self.log(f"  Warning: Whisper error: {e}")
            import shutil
            shutil.copy(input_path, output_path)
            os.unlink(audio_file)
            return
        
        os.unlink(audio_file)
        
        if progress_callback:
            progress_callback(0.5)
```

Replace with:

```python
        # Transcribe using Whisper (local or API based on settings)
        try:
            transcript = self._whisper_transcribe_words(audio_file)
        except Exception as e:
            self.log(f"  ❌ Whisper transcription failed, cannot generate captions: {e}")
            if os.path.exists(audio_file):
                os.unlink(audio_file)
            raise Exception(f"Whisper transcription failed: {e}")
        
        os.unlink(audio_file)
        
        # Guard against a "successful" transcription that returned nothing —
        # this used to silently produce a video with an empty subtitle track
        # (no error, no captions, no warning visible anywhere).
        has_words = bool(getattr(transcript, "words", None))
        has_segments = bool(getattr(transcript, "segments", None))
        if not has_words and not has_segments:
            self.log(f"  ❌ Whisper returned no words or segments, cannot generate captions")
            raise Exception(
                "Whisper transcription succeeded but returned empty text "
                "(no words/segments) — check the source audio and the Caption Maker "
                "provider/model configuration"
            )
        
        if progress_callback:
            progress_callback(0.5)
```

### Edit 3 — `app.py` local Whisper key mismatch

Find (around line 205, inside `WebAPI._run`):

```python
        whisper_model_name = ai_providers.get("whisper_model", "api")
        local_whisper_settings = {
            "enabled": whisper_model_name != "api",
            "model": whisper_model_name if whisper_model_name != "api" else None
        }
```

Replace with:

```python
        whisper_model_name = ai_providers.get("whisper_model", "api")
        local_whisper_settings = {
            "enabled": whisper_model_name != "api",
            # key must be "model_size" — AutoClipperCore._load_local_whisper()
            # reads settings.get("model_size", ...). It used to be "model" here,
            # which meant the user's chosen local Whisper model (e.g. "medium")
            # was silently ignored and always fell back to "large-v3-turbo".
            "model_size": whisper_model_name if whisper_model_name != "api" else "large-v3-turbo"
        }
```

## Verification Steps

Run `python3 -m py_compile app.py clipper_core.py` — should exit clean, no output.

Run the app, turn Caption Maker on, process a clip with a bad/empty API key on purpose. Before the fix: video finishes with no subtitles, no error shown. After the fix: `self.status` should become `error: Whisper transcription failed: ...` and surface in the UI instead of a silently "successful" run.

Once confirmed, commit:

```
git add app.py clipper_core.py
git commit -m "fix: surface caption/subtitle generation failures instead of silently skipping"
git push origin feature/pywebview-desktop-integration
```
