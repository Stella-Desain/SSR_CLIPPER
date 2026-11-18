"""Consumer CLI for diagnostics; Template Studio is never imported."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.external_templates import import_template, list_presets, template_directory, resolve_preset
from services.mlt_runtime import render_template, runtime_status


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("list")
    importer = sub.add_parser("import")
    importer.add_argument("package")
    render = sub.add_parser("render")
    render.add_argument("preset_id")
    render.add_argument("source")
    render.add_argument("output")
    render.add_argument("--title", default="")
    render.add_argument("--subtitle", help="Subtitle SRT contoh untuk template Editor")
    render.add_argument("--music", help="Musik lokal untuk pengujian template Editor")
    args = parser.parse_args()
    try:
        if args.command == "status":
            result = runtime_status()
        elif args.command == "list":
            result = {"status": "ok", "presets": list_presets()}
        elif args.command == "import":
            result = import_template(args.package)
        else:
            directory = template_directory(args.preset_id)
            preset = resolve_preset(args.preset_id)
            if preset["external_template"]["engine"] == "design":
                from template_sdk.ssr_template_engine.design import load_design, render_design
                from utils.helpers import get_ffmpeg_path
                result = render_design(load_design(directory), directory, args.source, args.output,
                    title=args.title, subtitle_path=args.subtitle, music_path=args.music, ffmpeg=get_ffmpeg_path())
            else:
                result = render_template(directory, args.source, args.output, title=args.title)
    except Exception as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
