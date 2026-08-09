/**
 * Dashboard View — Pixel-perfect Figma implementation
 * Figma node: 2:29 (Bento Grid Layout) within 2:2 (Dashboard)
 * Ref: https://www.figma.com/design/Tk4JsGqmPD54nj6ULCPj1P/Untitled?node-id=2-29
 */
window.Components = window.Components || {};

window.Components.DashboardView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'dashboard';
  section.style.cssText = 'padding:32px;background:#F5F5F5;min-height:100%;';

  // ── HEADER SECTION (Figma 2:21) ─────────────────────────────
  const hdrSection = document.createElement('div');
  hdrSection.style.cssText = 'display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:32px;';
  hdrSection.innerHTML = `
    <div>
      <h1 style="font-size:34px;font-weight:700;color:#111827;letter-spacing:-0.02em;line-height:1.15;margin-bottom:8px;">Dashboard</h1>
      <p style="font-size:14px;font-weight:400;color:#6B7280;line-height:1.5;">An any way to manage sales with care and precision.</p>
    </div>
    <button id="btn-repliz-dashboard" style="height:38px;padding:0 17px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;font-size:14px;font-weight:500;color:#374151;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,0.05);transition:background 150ms ease;" onmouseover="this.style.background='#F9FAFB'" onmouseout="this.style.background='#FFFFFF'">
      Repliz Dashboard
    </button>
  `;
  section.appendChild(hdrSection);

  // ── BENTO GRID (Figma 2:29) — root container ─────────────────
  // Layout: 2 columns = Left 2/3 (632px) + Right 1/3 (308px)
  // with 16px gap
  const bentoRoot = document.createElement('div');
  bentoRoot.style.cssText = 'display:grid;grid-template-columns:1fr 308px;gap:16px;align-items:start;';

  // ── LEFT COLUMN (Figma 2:30) ─────────────────────────────────
  const leftCol = document.createElement('div');
  leftCol.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

  // ── TOP KPI ROW (Figma 2:31) — 3 equal KPI cards ─────────────
  const kpiRow = document.createElement('div');
  kpiRow.style.cssText = 'display:grid;grid-template-columns:repeat(3,1fr);gap:16px;';

  // KPI 1 — Account (dark card, Figma 2:32)
  const kpi1 = document.createElement('div');
  kpi1.style.cssText = `
    background:#0A0F11;
    border-radius:12px;
    padding:25px;
    height:132px;
    display:flex;
    flex-direction:column;
    justify-content:space-between;
    box-shadow:0 4px 12px rgba(0,0,0,0.25);
  `;
  kpi1.innerHTML = `
    <!-- Title row: dot + label (Figma 2:34) -->
    <div style="display:flex;align-items:center;gap:8px;">
      <div style="width:8px;height:8px;border-radius:50%;background:#8DC63F;flex-shrink:0;"></div>
      <span style="font-size:14px;font-weight:500;color:rgba(255,255,255,0.9);letter-spacing:0.01em;">Account</span>
    </div>
    <!-- Sub-stats + big number (Figma 2:38) -->
    <div>
      <!-- icon-stats row (Figma 2:40) -->
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
        <!-- 12 + TikTok -->
        <span style="display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:rgba(255,255,255,0.65);">
          12
          <svg width="10" height="10" viewBox="0 0 24 24" fill="rgba(255,255,255,0.65)"><path d="M12.53.02C13.84 0 15.14.01 16.44 0c.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.12-3.44-3.17-3.8-5.46-.4-2.51.13-5.23 1.82-7.08 1.49-1.7 3.8-2.61 6.09-2.11l.01 4.26c-1.15-.22-2.42-.16-3.42.49-1.25.76-1.88 2.37-1.47 3.79.43 1.54 2.1 2.53 3.69 2.18 1.13-.24 2.01-1.19 2.22-2.34.09-.54.12-1.09.12-1.64 0-4.93-.01-9.86.01-14.79Z"/></svg>
        </span>
        <!-- 12 + YouTube -->
        <span style="display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:rgba(255,255,255,0.65);">
          12
          <svg width="10" height="10" viewBox="0 0 24 24" fill="rgba(255,255,255,0.65)"><path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34l-.01-8.92a8.16 8.16 0 004.76 1.52V4.46a4.85 4.85 0 01-1-.23z"/></svg>
        </span>
        <!-- 12 + Instagram -->
        <span style="display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:rgba(255,255,255,0.65);">
          12
          <svg width="10" height="10" viewBox="0 0 24 24" fill="rgba(255,255,255,0.65)"><path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zm0-2.163c-3.259 0-3.667.014-4.947.072-4.358.2-6.78 2.618-6.98 6.98-.059 1.281-.073 1.689-.073 4.948 0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98 1.281.058 1.689.072 4.948.072 3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98-1.281-.059-1.69-.073-4.949-.073zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z"/></svg>
        </span>
      </div>
      <!-- Big label (Figma 2:54) -->
      <div style="font-size:22px;font-weight:700;color:#FFFFFF;letter-spacing:-0.02em;line-height:1.1;">12 Campaign</div>
    </div>
  `;
  kpiRow.appendChild(kpi1);

  // KPI 2 — Jobs (light card, Figma 4:4564)
  const kpi2 = document.createElement('div');
  kpi2.style.cssText = `
    background:#FFFFFF;
    border-radius:12px;
    border:1px solid #E5E7EB;
    padding:25px;
    height:132px;
    display:flex;
    flex-direction:column;
    justify-content:space-between;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
  `;
  kpi2.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;">
      <div style="width:8px;height:8px;border-radius:50%;background:#8DC63F;flex-shrink:0;"></div>
      <span style="font-size:14px;font-weight:500;color:#374151;">Jobs</span>
    </div>
    <div>
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">
        <!-- 12 + Plus icon -->
        <span style="display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:#6B7280;">
          12
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#6B7280" stroke-width="2.5"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </span>
        <!-- 12 + Trash icon -->
        <span style="display:flex;align-items:center;gap:4px;font-size:12px;font-weight:600;color:#6B7280;">
          12
          <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#6B7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
        </span>
      </div>
      <div style="font-size:22px;font-weight:700;color:#111827;letter-spacing:-0.02em;line-height:1.1;">123 Clips</div>
    </div>
  `;
  kpiRow.appendChild(kpi2);

  // KPI 3 — Status (light card, Figma 4:4314)
  const kpi3 = document.createElement('div');
  kpi3.style.cssText = `
    background:#FFFFFF;
    border-radius:12px;
    border:1px solid #E5E7EB;
    padding:25px;
    height:132px;
    display:flex;
    flex-direction:column;
    justify-content:space-between;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
  `;
  // Status items from Figma 4:4583 — 2x2 grid
  kpi3.innerHTML = `
    <div style="display:flex;align-items:center;gap:8px;">
      <div style="width:8px;height:8px;border-radius:50%;background:#8DC63F;flex-shrink:0;"></div>
      <span style="font-size:14px;font-weight:500;color:#374151;">Status</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 12px;">
      <div style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500;color:#374151;">
        <div style="width:8px;height:8px;border-radius:50%;background:#EF4444;flex-shrink:0;"></div>yt-dlp
      </div>
      <div style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500;color:#374151;">
        <div style="width:8px;height:8px;border-radius:50%;background:#EF4444;flex-shrink:0;"></div>ffmpeg
      </div>
      <div style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500;color:#374151;">
        <div style="width:8px;height:8px;border-radius:50%;background:#EF4444;flex-shrink:0;"></div>deno
      </div>
      <div style="display:flex;align-items:center;gap:8px;font-size:13px;font-weight:500;color:#374151;">
        <div style="width:8px;height:8px;border-radius:50%;background:#EF4444;flex-shrink:0;"></div>whisper
      </div>
    </div>
  `;
  kpiRow.appendChild(kpi3);

  leftCol.appendChild(kpiRow);

  // ── BOTTOM ROW: Campaign + Stock Clips (Figma 2:89) ──────────
  // 2 equal columns with 16px gap
  const bottomRow = document.createElement('div');
  bottomRow.style.cssText = 'display:grid;grid-template-columns:1fr 1fr;gap:16px;';

  // ── CAMPAIGN CARD (Figma 2:90) ──────────────────────────────
  const campaignCard = document.createElement('div');
  campaignCard.style.cssText = `
    background:#FFFFFF;
    border-radius:12px;
    border:1px solid #E5E7EB;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
    overflow:hidden;
  `;

  // Card header
  const campHead = document.createElement('div');
  campHead.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:25px 25px 0 25px;';
  campHead.innerHTML = `
    <h2 style="font-size:18px;font-weight:700;color:#111827;line-height:1.2;">Campaign</h2>
    <button style="display:flex;align-items:center;gap:6px;height:30px;padding:0 13px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;font-size:12px;font-weight:500;color:#374151;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,0.04);transition:background 150ms ease;" onmouseover="this.style.background='#F9FAFB'" onmouseout="this.style.background='#FFFFFF'">
      <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/></svg>
      Restock Clip
    </button>
  `;
  campaignCard.appendChild(campHead);

  // Tree container (Figma 2:99)
  const treeContainer = document.createElement('div');
  treeContainer.style.cssText = 'padding:20px 25px 25px 25px;display:flex;flex-direction:column;gap:0;';

  function makeTreeItem(name, isOpen) {
    const item = document.createElement('div');
    item.style.cssText = 'margin-bottom:0;';

    // Summary row (Figma 2:101) — lime green bg when expanded
    const summary = document.createElement('div');
    summary.style.cssText = `
      display:flex;
      justify-content:space-between;
      align-items:center;
      padding:9px 10px 9px 6px;
      border-radius:6px;
      background:${isOpen ? '#F2FCE2' : 'transparent'};
      cursor:pointer;
      transition:background 150ms ease;
    `;
    summary.innerHTML = `
      <div style="display:flex;align-items:center;gap:6px;">
        <!-- chevron icon (Figma 2:104) -->
        <svg style="width:7px;height:7px;color:${isOpen ? '#2E4D0F' : '#6B7280'};transform:${isOpen ? 'rotate(0deg)' : 'rotate(-90deg)'};" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9 6 6 6-6"/></svg>
        <span style="font-size:13px;font-weight:600;color:${isOpen ? '#2E4D0F' : '#374151'};">${name}</span>
      </div>
      <div style="display:flex;align-items:center;gap:12px;">
        <!-- count + chat icon -->
        <span style="display:flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:${isOpen ? '#2E4D0F' : '#6B7280'};">
          3
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M21 3H3c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h18c1.1 0 2-.9 2-2V5c0-1.1-.9-2-2-2zm0 16H3V5h18v14zm-11-2l6-5-6-5v10z"/></svg>
        </span>
        <!-- count + play icon -->
        <span style="display:flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:${isOpen ? '#2E4D0F' : '#6B7280'};">
          150
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
        </span>
      </div>
    `;
    item.appendChild(summary);

    // Children rows (Figma 2:117)
    const childrenSlot = document.createElement('div');
    childrenSlot.style.cssText = `
      position:relative;
      padding-left:20px;
      display:${isOpen ? 'block' : 'none'};
    `;
    // Vertical divider (Figma 2:118) — 1px line from Figma x=18
    const vline = document.createElement('div');
    vline.style.cssText = 'position:absolute;left:18px;top:0;bottom:10px;width:1px;background:#E5E7EB;';
    childrenSlot.appendChild(vline);

    const childNames = ['Cliper Account 1', 'Cliper Account 1', 'Cliper Account 1'];
    childNames.forEach((childName, idx) => {
      const childRow = document.createElement('div');
      childRow.style.cssText = `
        display:flex;
        justify-content:space-between;
        align-items:center;
        padding:9px 0 9px 20px;
        cursor:pointer;
        transition:background 150ms ease;
        border-radius:4px;
      `;
      childRow.innerHTML = `
        <div style="display:flex;align-items:center;gap:8px;">
          <div style="width:12px;height:12px;border-radius:50%;background:#111827;flex-shrink:0;"></div>
          <span style="font-size:13px;font-weight:400;color:#374151;">${childName}</span>
        </div>
        <div style="display:flex;align-items:center;gap:4px;font-size:11px;font-weight:600;color:#6B7280;">
          50
          <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor" style="color:#6B7280;"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 14.5v-9l6 4.5-6 4.5z"/></svg>
        </div>
      `;
      // horizontal connector from divider to row
      const hconn = document.createElement('div');
      hconn.style.cssText = 'position:absolute;left:18px;top:'+(19 + idx*38)+'px;width:14px;height:1px;background:#E5E7EB;';
      childrenSlot.appendChild(hconn);
      childrenSlot.appendChild(childRow);
    });

    item.appendChild(childrenSlot);
    return item;
  }

  treeContainer.appendChild(makeTreeItem('Timothy Ronald', true));

  // gap between tree items
  const treeSpacer = document.createElement('div');
  treeSpacer.style.height = '8px';
  treeContainer.appendChild(treeSpacer);

  treeContainer.appendChild(makeTreeItem('Q3 Product Launch', true));

  campaignCard.appendChild(treeContainer);
  bottomRow.appendChild(campaignCard);

  // ── STOCK CLIPS CARD (Figma 2:220) ─────────────────────────
  const stockCard = document.createElement('div');
  stockCard.style.cssText = `
    background:#FFFFFF;
    border-radius:12px;
    border:1px solid #E5E7EB;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
    overflow:hidden;
  `;

  // Stock header (Figma 2:222)
  const stockHead = document.createElement('div');
  stockHead.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:25px 25px 0 25px;';
  stockHead.innerHTML = `
    <h2 style="font-size:18px;font-weight:700;color:#111827;line-height:1.2;">Stock Clips</h2>
    <span style="font-size:13px;font-weight:400;color:#6B7280;">Size all: 450mb</span>
  `;
  stockCard.appendChild(stockHead);

  // Filters row (Figma 2:233 / 4:4103)
  const stockFilter = document.createElement('div');
  stockFilter.style.cssText = 'display:flex;align-items:center;padding:12px 25px 0 25px;gap:8px;';
  stockFilter.innerHTML = `
    <div style="flex:1;height:26px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:6px;padding:0 9px;display:flex;align-items:center;font-size:13px;color:#374151;">Campaign: All</div>
    <div style="height:26px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:6px;padding:0 8px;display:flex;align-items:center;font-size:13px;color:#374151;white-space:nowrap;">Clips: 45</div>
  `;
  stockCard.appendChild(stockFilter);

  // File list (Figma 2:239)
  const stockList = document.createElement('div');
  stockList.style.cssText = 'padding:8px 0 4px 0;overflow-y:auto;max-height:320px;';

  for (let i = 0; i < 8; i++) {
    const fileItem = window.FileItem.v1({
      title: 'Keluar Dari Mindset Budak',
      info1: 'Durasi: 24s',
      info2: '3.1mb',
      onEdit: () => console.log('Edit clicked')
    });
    stockList.appendChild(fileItem);
  }

  stockCard.appendChild(stockList);
  bottomRow.appendChild(stockCard);

  leftCol.appendChild(bottomRow);
  bentoRoot.appendChild(leftCol);

  // ── RIGHT COLUMN — Jobs Proses (Figma 2:288) ─────────────────
  const rightCol = document.createElement('div');
  rightCol.style.cssText = `
    background:#FFFFFF;
    border-radius:12px;
    border:1px solid #E5E7EB;
    box-shadow:0 1px 3px rgba(0,0,0,0.06);
    overflow:hidden;
    height:100%;
  `;

  // Jobs header (Figma 2:290-291)
  const jobsHead = document.createElement('div');
  jobsHead.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:25px 25px 0 25px;';
  jobsHead.innerHTML = `
    <h2 style="font-size:18px;font-weight:700;color:#111827;line-height:1.2;">Jobs Proses</h2>
    <button style="display:flex;align-items:center;gap:5px;height:30px;padding:0 13px;background:#FFFFFF;border:1px solid #E5E7EB;border-radius:8px;font-size:12px;font-weight:500;color:#374151;cursor:pointer;box-shadow:0 1px 2px rgba(0,0,0,0.04);transition:background 150ms ease;" onmouseover="this.style.background='#F9FAFB'" onmouseout="this.style.background='#FFFFFF'">
      <svg width="8" height="8" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
      New Clip
    </button>
  `;
  rightCol.appendChild(jobsHead);

  // Jobs list (Figma 2:298 — starts at y:79)
  const jobsList = document.createElement('div');
  jobsList.style.cssText = 'padding:8px 0 4px 0;overflow-y:auto;max-height:520px;';

  const jobsData = [
    { status: 'Export...',    isFailed: false },
    { status: 'Editing...',   isFailed: false },
    { status: 'Highlight...', isFailed: false },
    { status: 'Download...',  isFailed: false },
    { status: 'Failed',       isFailed: true },
    { status: 'Failed',       isFailed: true },
    { status: 'Failed',       isFailed: true },
    { status: 'Failed',       isFailed: true },
    { status: 'Failed',       isFailed: true },
  ];

  jobsData.forEach(j => {
    const statusText = j.isFailed ? 'Failed' : j.status;
    const fileItem = window.FileItem.v1({
      title: 'Keluar Dari Mindset Budak',
      info1: '12/12 Clips',
      info2: statusText,
      onEdit: () => console.log('Edit clicked')
    });
    // Optional: override the info2 color if failed to red to match the design intent
    if (j.isFailed) {
      const sub = fileItem.querySelector('.fi-sub');
      if (sub && sub.lastElementChild) {
        sub.lastElementChild.style.color = '#EF4444';
      }
    }
    jobsList.appendChild(fileItem);
  });

  rightCol.appendChild(jobsList);
  bentoRoot.appendChild(rightCol);

  section.appendChild(bentoRoot);
  return { element: section };
};
