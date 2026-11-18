# Editor implementation contract

Native editable model shared by authoring UI and standalone render SDK. Existing MLT packages remain supported. No GUI required by consumer.

Implementation notes: native framing accepts fit/center only (speaker tracking is retained in existing Clipper presets); renderer rotation is disabled. Native font layers require bundled font_asset_id at publication; authoring resolves installed fonts or imports TTF/OTF. Bridge render progress is consistently 0..100. editor_list_projects additionally exposes thumbnail_url, editor_get_project exposes last_render; editor_shutdown cancels previews when the desktop closes. Campaign mixing inheritance uses editing.music.mixing_overrides; explicit legacy values remain authoritative.

## Model

`{schema_version:1,id:"design-<hex>",name,canvas:{width:1080,height:1920,fps:30,background:"#101820"},layers:[],assets:[],audio:{voice_volume:1,music_volume:0.12,ducking:true,fade_in:0.5,fade_out:1},preview:{video_path:"",subtitle_path:"",music_path:"",title:"Judul clip",duration:30}}`

Layer order is bottom to top. Each layer: `{id,type:"video|subtitle|text|image|rect",name,x,y,width,height,rotation:0,visible:true,locked:false,timing:{mode:"full|start|end|percent",start:0,duration:4},...}`. Coordinates and font sizes in output pixels. Use one video layer (required, full duration) and at most one subtitle layer. Video: `fit:"cover|contain",framing:"fit|center|speaker"`. Text: `binding:"static|title",text,font_family:"Arial",font_size:64,color:"#ffffff",align:"left|center|right",bold:true,outline_color:"#000000",outline_width:2`. Subtitle adds `words_per_group:4,max_lines:2,highlight_color:"#bcff32",background:"#00000000"`. Image: `asset_id,fit:"contain"`. Rect: `color,border_color,border_width`. Initially rotation disabled if runtime does not support it. Audio settings are defaults; existing explicit campaign audio policy remains authoritative.

`full` ignores start/duration and follows source. `start` uses seconds from start. `end` start is seconds before the end (0 means ends at source end, duration specifies length). `percent` uses start and duration in 0..100 percent. Elements clamp to source duration; NEVER truncate source to sample duration. Preview/sample media excluded from published package.

## Bridge API

All errors `{status:"error",message}`; cancellation `{status:"cancelled"}`.

- `editor_list_projects()` => `{status:"ok",projects:[{id,name,canvas,updated_at,archived,published_versions:[]}],presets:[]}`
- `editor_create_project(options)` (name, ratio 9:16/1:1/16:9) => `{status:"ok",project}`
- `editor_get_project(id)` => `{status:"ok",project}`
- `editor_save_project(project)` => `{status:"ok",project}`; no arbitrary new ids, atomic writes, revision conflict detection preferred.
- `editor_duplicate_project(id)` => `{status:"ok",project}`
- `editor_archive_project(id,archived)` => `{status:"ok"}`; preserves published versions.
- `editor_add_asset(id,path,kind)` => `{status:"ok",asset,project}`; image asset copied to project, preview video/audio reference sample only, kind image/video/audio/subtitle/font. Images return `url` for preview.
- `editor_browse_asset(id,kind)` => same result, native dialog available to user, not launched on page load.
- `editor_publish_project(id)` => `{status:"ok",preset,project,path}` version immutable, portable package automatically installed.
- `editor_export_project(id,path)` => `{status:"ok",path}`; optional save dialog if no path.
- `editor_import_project(path)` => `{status:"ok",project}` native packages can open editable model, legacy package imports into library and returns preset with clear no editable model message. Optional open dialog.
- `editor_start_render(id,options={})` => `{status:"ok",render:{id,status,progress}}` async production-equivalent sample render, uses preview paths, finite timeout; no model API calls.
- `editor_get_render(render_id)` => `{status:"ok",render:{id,status,progress,message,path,url}}`
- `editor_cancel_render(render_id)` => `{status:"ok"}`.
- `editor_media_preview(path)` => `{status:"ok",url}` where supported. Persist no URL in package; derive preview via approved local files.
- `editor_list_fonts()` => `{status:"ok",fonts:[...]}`.

## Ownership

Frontend agent: web/components/template-editor.js, web/css/template-editor.css, optional web/editor-model.js; no edits app shell/header/index (root owns integration). Component `window.Components.TemplateEditorView()` returns `{element,refresh,pause}` dataset.view editor. Use bundled `window.Konva`; API direct via window.pywebview.api. No CDN.

Backend agent: services/template_editor.py, backend tests; no app.py edits (root integrates TemplateEditorMixin). Coordinate SDK functions with engine agent.

Engine agent: template_sdk/ssr_template_engine, services/external_templates.py, services/core_workflow.py and required editing/campaign selection changes; render/model/package tests. Native portable package format `ssr-design-template` schema_version 1 (separate from ssr-mlt-template schema 1); native id preset prefix `design:` unless reuse requires changes communicated. Public model validation/default/export/load/render functions in `template_sdk/ssr_template_engine/design.py`.

Root: shell integration, vendor Konva/license, tests/build/doc integration, end-to-end headless actual render validation. Preserve user data and existing dirty changes. No publishing clips or changing campaigns for test.
