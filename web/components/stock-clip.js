window.Components = window.Components || {};

window.Components.StockClipView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'stock-clip';

  // Page header
  const pageHeader = document.createElement('div');
  pageHeader.style.marginBottom = '28px';
  pageHeader.innerHTML = `<h1 class="page-title">Stock Clip</h1><p class="page-subtitle">An easy way to manage clips with care and precision.</p>`;
  section.appendChild(pageHeader);

  // 2-column layout
  const layout = document.createElement('div');
  layout.style.cssText = 'display:grid;grid-template-columns:4fr 8fr;gap:20px;min-height:calc(100vh - 240px);';

  // ── Left: Jobs Panel ──
  const jobsPanel = document.createElement('div');
  jobsPanel.className = 'card';
  jobsPanel.style.cssText = 'display:flex;flex-direction:column;max-height:700px;';

  const jobsHeader = document.createElement('div');
  jobsHeader.className = 'card-header';
  jobsHeader.innerHTML = '<h2 class="card-title">Jobs</h2>';
  jobsPanel.appendChild(jobsHeader);

  const jobsBody = document.createElement('div');
  jobsBody.className = 'card-body';
  jobsBody.style.cssText = 'flex:1;display:flex;flex-direction:column;overflow:hidden;';

  // Filter
  const filterRow = document.createElement('div');
  filterRow.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;';
  filterRow.innerHTML = `
    <select class="select" style="width:auto;min-width:140px;"><option>Campaign: All</option></select>
    <span style="font-size:13px;color:var(--text-secondary);font-weight:500;">Clips: 45</span>
  `;
  jobsBody.appendChild(filterRow);

  // Jobs list
  const jobsList = document.createElement('div');
  jobsList.style.cssText = 'flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-right:8px;padding-bottom:8px;';

  const sampleJobs = [
    { title: 'Keluar Dari Mindset Budak', sub: 'Timothy Ronald - 24 apr', size: '3.1mb' },
    { title: 'Keluar Dari Mindset Budak', sub: 'Timothy Ronald - 24 apr', size: '3.1mb' },
    { title: 'Keluar Dari Mindset Budak', sub: 'Timothy Ronald - 24 apr', size: '3.1mb' },
    { title: 'Keluar Dari Mindset Budak', sub: 'Timothy Ronald - 24 apr', size: '3.1mb' },
    { title: 'Keluar Dari Mindset Budak', sub: 'Timothy Ronald - 24 apr', size: '3.1mb' },
  ];

  sampleJobs.forEach(j => {
    const item = window.FileItem.v2({
      title: j.title,
      info1: j.sub,
      info2: '', // Or remove the hyphen logic in component if empty
      size: j.size,
      onEdit: () => console.log('Edit clicked'),
      onDelete: () => console.log('Delete clicked')
    });
    // Fix info2 display since we only have 'sub'
    const subEl = item.querySelector('.fi-sub');
    if(subEl) {
       subEl.innerHTML = `<span>${j.sub}</span>`;
    }
    jobsList.appendChild(item);
  });

  jobsBody.appendChild(jobsList);

  // Create button
  const createBtnWrap = document.createElement('div');
  createBtnWrap.style.cssText = 'margin-top:14px;padding-top:14px;border-top:1px solid var(--border-light);';
  const createBtn = document.createElement('button');
  createBtn.className = 'btn btn-lime-full';
  createBtn.textContent = 'Create Clip New';
  createBtn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => {
      n.classList.toggle('active', n.dataset.view === 'create-clip');
    });
    document.querySelectorAll('.view').forEach(v => {
      v.classList.toggle('active', v.dataset.view === 'create-clip');
    });
  });
  createBtnWrap.appendChild(createBtn);
  jobsBody.appendChild(createBtnWrap);

  jobsPanel.appendChild(jobsBody);

  // ── Right: Clips Panel ──
  const clipsPanel = document.createElement('div');
  clipsPanel.className = 'card';
  clipsPanel.style.cssText = 'display:flex;flex-direction:column;max-height:700px;';

  const clipsHeader = document.createElement('div');
  clipsHeader.className = 'card-header';
  clipsHeader.innerHTML = `
    <h2 class="card-title">Clips</h2>
    <button class="btn btn-pill">Upload Semua</button>
  `;
  clipsPanel.appendChild(clipsHeader);

  // Clips subheader
  const clipsSub = document.createElement('div');
  clipsSub.style.cssText = 'padding:14px 24px 0 24px;display:flex;justify-content:space-between;align-items:center;font-size:13px;';
  clipsSub.innerHTML = `
    <div style="flex:1;max-width:400px;height:32px;border:1px solid var(--border-light);border-radius:4px;display:flex;align-items:center;padding:0 12px;color:var(--text-secondary);">
      Keluar Dari Mindset Budak - Timothy Ronald
    </div>
    <div style="display:flex;gap:16px;color:var(--text-secondary);margin-left:16px;">
      <span>Clips: 45</span>
      <span>Size: 45mb</span>
    </div>
  `;
  clipsPanel.appendChild(clipsSub);

  // Clips list
  const clipsBody = document.createElement('div');
  clipsBody.style.cssText = 'flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:10px;';

  for (let i = 0; i < 7; i++) {
    const clip = window.FileItem.v3({
      title: 'Keluar Dari Mindset Budak',
      info1: 'Durasi: 24s',
      info2: '3.1mb',
      onDelete: () => console.log('Delete clicked'),
      onPlay: () => console.log('Play clicked'),
      onUpload: () => console.log('Upload clicked')
    });
    clipsBody.appendChild(clip);
  }

  clipsPanel.appendChild(clipsBody);

  layout.appendChild(jobsPanel);
  layout.appendChild(clipsPanel);
  section.appendChild(layout);

  return { element: section };
};
