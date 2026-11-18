# Music selection v2

Automatic selection uses Highlight Finder as editorial judge and Music Audio
Analyzer for actual audio observations. The analyzer defaults to `Visual-AI`
using the saved Custom2 credentials; Settings can select another model. No
manual profile import or large local model install is required.

## Selection

- `Reflektif / Action` uses the user's Gemini reference report as editorial
  direction, not independently verified measurements of the TikTok edits.
  Soft vocals, humming and vocal chops are allowed. Strong delivery does not
  automatically imply aggressive music.
- Repliz provides a dated ID / ALL / 7DAY trend snapshot. It is reused for ten
  minutes. A snapshot at most 24 hours old may be used during provider failure;
  `catalog_snapshot.offline_snapshot` records this explicitly. This is not proof
  of engagement or a guarantee of virality.
- Up to five tracks are measured locally and sent as bounded mono MP3 input
  audio to the analyzer. Each profile covers at most 120 seconds of one file.
  Cache identity includes file SHA-256, source time range, endpoint hash,
  requested model and profile version. Returned model and response ID are
  recorded. Changing a router combo without renaming it requires removing its
  semantic cache or bumping the profile version to request fresh observations.
- Criteria and catalog shortlist decisions can be reused for one hour when
  instruction, clip context, catalog snapshot, endpoint, model and reasoning
  effort match. Their provenance is retained with `cache_hit=true`. Final
  passage ranking is not cached, so a failed ranking can be retried.
- The editor compares up to three phrase-based passages per track using the
  transcript, reference direction, signal measurements and timestamped audio
  observations. It receives descriptors, not audio itself. Observations outside
  the analyzed range are never represented as heard.
- Invalid rankings, a low score, missing coverage or uncertain observations
  produce `review_required`, not an automatic quality claim. Missing media
  support fails selection rather than falling back to song titles.

## Review and revisions

New pipeline renders retain a hashed `master_without_music.mp4` after layout
and captions, before background music and platform overlays. Review provides
candidate/passages, start time, gain and light ducking. Preview mixes the chosen
settings with the original dialogue. Music revisions reuse that dry master,
regenerate platform overlays, create a new clip, and reset approval to pending.
They never overwrite an approved original or add music over an existing mix.
Legacy clips without a verified dry master need a source render first.

Feedback labels are good fit, wrong mood, too quiet and vocal clash. They are
bound to the rendered file/revision and kept separate from approval. Recent
campaign feedback is passed to the editor as context, not executable rules.

Final checks estimate the selected music's signal contribution in the encoded
mix by alignment and projection against dry audio and the chosen track.
`music_balance` is a diagnostic, not a taste score or word-intelligibility test.
Below -18 dB relative to source, near -5 dB, or unverifiable contribution raises
a review warning. Existing automatic publishing refuses clips with warnings.
Explicit campaign gain remains authoritative; use the review fader to calibrate
the result. A trend listing does not grant usage rights for every destination.

## Verification

```powershell
py -3.12 -m unittest discover -s tests -p 'test_music*.py'
py -3.12 -m unittest discover -s tests -p test_required_music.py
py -3.12 tools/remix_music_custom2_test.py --volume 0.5
```

The live test requires saved Custom2 Codex-6.1sol and Visual-AI. It reuses the
isolated highlight test from the project with 51 clips. It creates new files in
`output/_tests`, does not alter production clips/config, and never publishes.
Provider tests send real audio files and bypass descriptor caches, so old
successful observations cannot mask a broken current provider. They do not
certify subjective accuracy. An `Unsupported model` error means the router's
selected route rejected the request; it is not treated as a song analysis.
