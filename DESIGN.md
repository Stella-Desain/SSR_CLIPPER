# SSR_CLIPPER design context

The desktop operator works through briefs, production and review in the existing light content area with a dark green sidebar. Preserve this familiar setting while adding workflow controls.

## Visual system

Use the existing tokens from web/css/base.css: --bg, --card, --text, --text-secondary, --border, --lime and semantic --success/--warning/--error. Inter with system fallback, 12px/8px radii, standard .btn/.input/.select controls. Lime denotes primary actions; status labels include words as well as color.

## Layout

Keep sidebar navigation and restrained toolbars. Dense lists and tables serve jobs and publications. A review surface places the actual video beside editable metadata and rule checks. Collapse multi-column forms on narrow windows. Long filenames and errors wrap rather than expanding the window.

## Interaction

All async controls expose loading, error and retry states. Use semantic labels and focus-visible. Avoid decorative animation. Pause polling when a view is hidden and serialize requests. New views should not trigger installation, AI calls or publication on initial load.
