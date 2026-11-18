"""Opt-in, bounded live diagnostic. Never changes providers or publishes clips."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio", type=Path)
    parser.add_argument("--seconds", type=float, default=12)
    args = parser.parse_args()
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8-sig"))
    from services.music_audio import provider_error_details
    try:
        if args.audio:
            from services.music_audio import MusicAudioAnalyzer
            profile = MusicAudioAnalyzer(cfg, Path(cfg.get("output_dir") or ROOT / "output") / "_cache/music-selection").analyze(
                args.audio, seconds=args.seconds, use_cache=False)
            result = {"status": "ok", "provenance": profile["provenance"], "observations": profile["observations"]}
        else:
            from openai import OpenAI
            provider = cfg["ai_providers"]["highlight_finder"]
            client = OpenAI(api_key=provider["api_key"], base_url=provider["base_url"], timeout=60, max_retries=0)
            response = client.chat.completions.create(model=provider["model"], reasoning_effort="xhigh",
                messages=[{"role": "user", "content": 'Return JSON only: {"ok":true}'}])
            result = {"status": "ok", "requested_model": provider["model"], "returned_model": response.model,
                      "content": response.choices[0].message.content}
    except Exception as exc:
        result = {"status": "error", **provider_error_details(exc)}
    output = json.dumps(result, ensure_ascii=True)
    for provider in cfg.get("ai_providers", {}).values():
        if isinstance(provider, dict) and provider.get("api_key"):
            output = output.replace(provider["api_key"], "[redacted]")
    print(output, flush=True)
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
