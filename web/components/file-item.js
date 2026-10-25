/**
 * FileItem Component — Figma node 16:828
 * https://www.figma.com/design/Tk4JsGqmPD54nj6ULCPj1P/Untitled?node-id=16-828&m=dev
 *
 * Three variants matching Figma symbols:
 *  - V1 (16:712): Title + Info, lime edit button — Dashboard Stock Clips & Jobs Proses
 *  - V2 (16:967): Title + Info, edit+trash icons top-right + file size bottom — Stock Clip page > Jobs panel
 *  - V3 (16:950): Title + Info, trash + Play + Upload buttons — Stock Clip page > Clips panel
 *
 * Usage:
 *   const el = FileItem.v1({ title, info, onEdit });
 *   const el = FileItem.v2({ title, info, size, onEdit, onDelete });
 *   const el = FileItem.v3({ title, info, onDelete, onPlay, onUpload });
 */

window.FileItem = (function () {

  // ── Shared base item styles (dark bg, 50px row) ──────────────
  // Figma: background rgba dark, border-radius, height 50px
  const BASE_ITEM_STYLE = `
    display:flex;
    align-items:center;
    height:50px;
    padding:0 13px;
    background:#2A2F2B;
    border-radius:8px;
    margin-bottom:6px;
    box-sizing:border-box;
    transition:background 150ms ease;
    cursor:default;
  `;

  // Icon SVGs
  const ICON_EDIT = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>`;
  const ICON_TRASH = `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>`;

  /**
   * LIGHT_ITEM_STYLE: Used by V1, V2, V3 matching the new Light Mode Dashboard/StockClip designs
   */
  const LIGHT_ITEM_STYLE = `
    display:flex;
    align-items:center;
    height:50px;
    padding:0 13px;
    background:#FFFFFF;
    border:1px solid #F3F4F6;
    border-radius:8px;
    margin-bottom:8px;
    box-sizing:border-box;
    transition:border-color 150ms ease, box-shadow 150ms ease;
    cursor:default;
  `;

  /**
   * V1 — Figma 2:220 (Dashboard Stock Clips / Jobs Proses)
   * 258×50px, LIGHT bg, border, title+info, lime edit button 20×20px (right)
   */
  function v1({ title = 'Judul', info1 = 'Info', info2 = 'Info', onEdit } = {}) {
    const el = document.createElement('div');
    el.className = 'file-item file-item-v1';
    el.style.cssText = LIGHT_ITEM_STYLE;
    el.onmouseover = () => { el.style.borderColor = '#E5E7EB'; el.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)'; };
    el.onmouseout  = () => { el.style.borderColor = '#F3F4F6'; el.style.boxShadow = 'none'; };

    el.innerHTML = `
      <!-- Left: text block -->
      <div style="flex:1;min-width:0;">
        <div class="fi-title" style="font-size:14px;font-weight:600;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;">${title}</div>
        <div class="fi-sub" style="font-size:12px;color:#6B7280;margin-top:2px;line-height:1.2;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">
          <span>${info1}</span><span style="margin:0 4px;">-</span><span>${info2}</span>
        </div>
      </div>
      <!-- Right: edit button -->
      <button class="fi-btn-edit" title="Edit" style="
        width:20px;height:20px;
        border-radius:4px;
        background:#8DC63F;
        border:none;
        display:flex;align-items:center;justify-content:center;
        cursor:pointer;
        flex-shrink:0;
        margin-left:10px;
        transition:background 150ms ease;
      " onmouseover="this.style.background='#7AB332'" onmouseout="this.style.background='#8DC63F'">
        ${ICON_EDIT}
      </button>
    `;

    if (onEdit) {
      el.querySelector('.fi-btn-edit').addEventListener('click', onEdit);
    }

    return el;
  }

  /**
   * V2 — Figma 3:3340 (Stock Clip > Jobs)
   * 258×50px, LIGHT bg, title+info, inline edit/trash, file size
   */
  function v2({ title = 'Judul', info1 = 'Info', info2 = 'Info', size = '3.1mb', onEdit, onDelete } = {}) {
    const el = document.createElement('div');
    el.className = 'file-item file-item-v2';
    el.style.cssText = LIGHT_ITEM_STYLE;
    el.onmouseover = () => { el.style.borderColor = '#E5E7EB'; el.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)'; };
    el.onmouseout  = () => { el.style.borderColor = '#F3F4F6'; el.style.boxShadow = 'none'; };

    el.innerHTML = `
      <div style="flex:1;min-width:0;">
        <div class="fi-title" style="font-size:14px;font-weight:600;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;">${title}</div>
        <div class="fi-sub" style="font-size:12px;color:#6B7280;margin-top:2px;line-height:1.2;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">
          <span>${info1}</span><span style="margin:0 4px;">-</span><span>${info2}</span>
        </div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;margin-left:10px;">
        <div style="display:flex;gap:6px;">
          <button class="fi-btn-edit2" title="Edit" style="background:transparent;border:none;cursor:pointer;padding:2px;display:flex;align-items:center;opacity:0.6;transition:opacity 150ms;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.6'">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#4B5563" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          </button>
          <button class="fi-btn-del" title="Delete" style="background:transparent;border:none;cursor:pointer;padding:2px;display:flex;align-items:center;opacity:0.6;transition:opacity 150ms;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.6'">
            ${ICON_TRASH}
          </button>
        </div>
        <div style="font-size:11px;color:#6B7280;margin-top:2px;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">${size}</div>
      </div>
    `;

    if (onEdit) el.querySelector('.fi-btn-edit2').addEventListener('click', onEdit);
    if (onDelete) el.querySelector('.fi-btn-del').addEventListener('click', onDelete);

    return el;
  }

  /**
   * V3 — Figma 3:3679 (Stock Clip > Clips)
   * Full width, LIGHT bg, title+info, trash button, Play (outline), Upload (lime)
   */
  function v3({ title = 'Judul', info1 = 'Info', info2 = 'Info', onDelete, onPlay, onUpload } = {}) {
    const el = document.createElement('div');
    el.className = 'file-item file-item-v3';
    el.style.cssText = LIGHT_ITEM_STYLE;
    el.onmouseover = () => { el.style.borderColor = '#E5E7EB'; el.style.boxShadow = '0 1px 2px rgba(0,0,0,0.05)'; };
    el.onmouseout  = () => { el.style.borderColor = '#F3F4F6'; el.style.boxShadow = 'none'; };

    el.innerHTML = `
      <div style="flex:1;min-width:0;">
        <div class="fi-title" style="font-size:14px;font-weight:600;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3;">${title}</div>
        <div class="fi-sub" style="font-size:12px;color:#6B7280;margin-top:2px;line-height:1.2;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;">
          <span>${info1}</span><span style="margin:0 4px;">-</span><span>${info2}</span>
        </div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;margin-left:12px;">
        <button class="fi-btn-del" title="Delete" style="background:transparent;border:none;cursor:pointer;padding:4px;display:flex;align-items:center;opacity:0.8;transition:opacity 150ms;" onmouseover="this.style.opacity='1'" onmouseout="this.style.opacity='0.8'">
          ${ICON_TRASH}
        </button>
        <button class="fi-btn-play" style="
          height:28px;padding:0 12px;
          background:#FFFFFF;border:1px solid #E5E7EB;border-radius:6px;
          color:#374151;font-size:12px;font-weight:500;
          cursor:pointer;display:flex;align-items:center;gap:4px;
          transition:background 150ms ease;
        " onmouseover="this.style.background='#F9FAFB'" onmouseout="this.style.background='#FFFFFF'">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg> Play
        </button>
        <button class="fi-btn-upload" style="
          height:28px;padding:0 12px;
          background:#8DC63F;border:none;border-radius:6px;
          color:#FFFFFF;font-size:12px;font-weight:500;
          cursor:pointer;display:flex;align-items:center;gap:4px;
          transition:background 150ms ease;
        " onmouseover="this.style.background='#7AB332'" onmouseout="this.style.background='#8DC63F'">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg> Upload
        </button>
      </div>
    `;

    if (onDelete) el.querySelector('.fi-btn-del').addEventListener('click', onDelete);
    if (onPlay) el.querySelector('.fi-btn-play').addEventListener('click', onPlay);
    if (onUpload) el.querySelector('.fi-btn-upload').addEventListener('click', onUpload);

    return el;
  }

  return { v1, v2, v3 };

})();
