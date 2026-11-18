"""Package render XML exported by Kdenlive (not the .kdenlive project)."""
import argparse
import json
from ssr_template_engine import TemplateError, export_template


def main(argv=None):
    parser = argparse.ArgumentParser(description="Export a Kdenlive render .mlt into an SSR template package")
    parser.add_argument("timeline")
    parser.add_argument("output")
    parser.add_argument("--source", required=True, help="Placeholder video used on the full source track")
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--version", type=int, default=1)
    parser.add_argument("--subtitle-style", choices=["clean", "social", "bold"], default="clean")
    parser.add_argument("--source-framing", choices=["speaker", "fit", "center"], default="fit")
    args = parser.parse_args(argv)
    try:
        result = export_template(args.timeline, args.output, source=args.source, template_id=args.id,
            name=args.name, version=args.version, subtitle_style=args.subtitle_style, source_framing=args.source_framing)
    except (TemplateError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps({"status": "ok", "id": result["id"], "version": result["version"], "output": args.output}, ensure_ascii=False))


if __name__ == "__main__":
    main()
