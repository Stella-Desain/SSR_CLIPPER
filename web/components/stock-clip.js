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
    <select id="stock-campaign-filter" class="select" style="width:auto;min-width:140px;max-width:200px;"><option value="all">Campaign: All</option></select>
    <span id="stock-clips-count" style="font-size:13px;color:var(--text-secondary);font-weight:500;">Clips: 0</span>
  `;
  jobsBody.appendChild(filterRow);

  // Jobs list
  const jobsList = document.createElement('div');
  jobsList.style.cssText = 'flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-right:8px;padding-bottom:8px;';

  // File list will be populated in refresh()
  const sampleJobs = [];

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
    <div style="display:flex; gap:8px;">
        <select id="upload-platform" class="select" style="width:100px;">
            <option value="tiktok">TikTok</option>
            <option value="youtube">YouTube</option>
            <option value="repliz">Repliz</option>
        </select>
        <select id="upload-account" class="select" style="width:120px; display:none;">
            <option value="">Select Account...</option>
        </select>
        <button id="upload-all-btn" class="btn btn-pill">Upload Semua</button>
    </div>
  `;
  clipsPanel.appendChild(clipsHeader);

  // Clips subheader
  const clipsSub = document.createElement('div');
  clipsSub.style.cssText = 'padding:14px 24px 0 24px;display:flex;justify-content:space-between;align-items:center;font-size:13px;';
  clipsSub.innerHTML = `
    <div id="clips-sub-title" style="flex:1;max-width:400px;height:32px;border:1px solid var(--border-light);border-radius:4px;display:flex;align-items:center;padding:0 12px;color:var(--text-secondary);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">
      All Video
    </div>
    <div style="display:flex;gap:16px;color:var(--text-secondary);margin-left:16px;">
      <span id="clips-sub-count">Clips: 0</span>
      <span id="clips-sub-size">Size: 0mb</span>
    </div>
  `;
  clipsPanel.appendChild(clipsSub);

  // Clips list
  const clipsBody = document.createElement('div');
  clipsBody.style.cssText = 'flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:10px;';

  // File list will be populated in refresh()

  clipsPanel.appendChild(clipsBody);

  layout.appendChild(jobsPanel);
  layout.appendChild(clipsPanel);
  section.appendChild(layout);
  
  async function refresh() {
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const stats = await window.pywebview.api.get_dashboard_stats();
      
      // Update Jobs panel
      jobsList.innerHTML = '';
      const allJobs = [];
      if (stats.activeJobs && stats.activeJobs.length > 0) allJobs.push(...stats.activeJobs);
      if (stats.recentJobs && stats.recentJobs.length > 0) allJobs.push(...stats.recentJobs.reverse());
      
      if (allJobs.length === 0) {
        jobsList.innerHTML = '<div style="padding:16px;color:var(--text-secondary);font-size:13px;">No jobs found.</div>';
      } else {
        allJobs.forEach(j => {
          const item = window.FileItem.v2({
            title: j.title || 'Unknown Job',
            info1: j.status,
            info2: '',
            size: '',
            onDelete: async () => {
              if (confirm('Delete this job history?')) {
                const res = await window.pywebview.api.delete_job(j.id);
                if (res && res.status === 'ok') refresh();
              }
            }
          });
          const subEl = item.querySelector('.fi-sub');
          if(subEl) {
             subEl.innerHTML = `<span>${j.status}</span>`;
          }
          jobsList.appendChild(item);
        });
      }
      
      // Update Clips panel
      const filterSelect = section.querySelector('#stock-campaign-filter');
      const currentFilter = filterSelect.value || 'all';
      
      let clips = await window.pywebview.api.get_stock_clips();
      
      // Get unique titles for campaigns
      const uniqueTitles = [...new Set(clips.map(c => c.title))];
      filterSelect.innerHTML = '<option value="all">Campaign: All</option>';
      uniqueTitles.forEach(t => {
         const opt = document.createElement('option');
         opt.value = t;
         opt.textContent = 'Campaign: ' + (t.length > 20 ? t.substring(0, 20) + '...' : t);
         filterSelect.appendChild(opt);
      });
      filterSelect.value = uniqueTitles.includes(currentFilter) ? currentFilter : 'all';
      filterSelect.onchange = () => refresh();

      if (filterSelect.value !== 'all') {
         clips = clips.filter(c => c.title === filterSelect.value);
      }
      
      // Update clips count
      const countEl = section.querySelector('#stock-clips-count');
      if (countEl) countEl.textContent = `Clips: ${clips.length}`;
      
      // Update clips subheader
      const subTitleEl = section.querySelector('#clips-sub-title');
      const subCountEl = section.querySelector('#clips-sub-count');
      const subSizeEl = section.querySelector('#clips-sub-size');
      if (subTitleEl) subTitleEl.textContent = filterSelect.value === 'all' ? 'All Video' : filterSelect.value;
      if (subCountEl) subCountEl.textContent = `Clips: ${clips.length}`;
      if (subSizeEl) subSizeEl.textContent = `Size: ${stats.storageUsed}`;

      // Setup Upload Semua button
      const uploadAllBtn = section.querySelector('#upload-all-btn');
      const platformSelect = section.querySelector('#upload-platform');
      const accountSelect = section.querySelector('#upload-account');
      
      platformSelect.addEventListener('change', async () => {
          if (platformSelect.value === 'repliz') {
              accountSelect.style.display = 'block';
              accountSelect.innerHTML = '<option value="">Loading...</option>';
              try {
                  const res = await window.pywebview.api.get_repliz_accounts();
                  accountSelect.innerHTML = '<option value="">Select Account...</option>';
                  if (res && res.status === 'ok') {
                      res.accounts.forEach(acc => {
                          const opt = document.createElement('option');
                          opt.value = acc._id;
                          opt.textContent = acc.name + ' (' + acc.type + ')';
                          accountSelect.appendChild(opt);
                      });
                  } else {
                      accountSelect.innerHTML = '<option value="">Failed to load</option>';
                  }
              } catch(e) {
                  accountSelect.innerHTML = '<option value="">Error</option>';
              }
          } else {
              accountSelect.style.display = 'none';
          }
      });
      
      const newBtn = uploadAllBtn.cloneNode(true);
      uploadAllBtn.parentNode.replaceChild(newBtn, uploadAllBtn);
      
      newBtn.addEventListener('click', async () => {
         if (clips.length === 0) return;
         const platform = platformSelect.value;
         const accountId = accountSelect.value;
         
         if (platform === 'repliz' && !accountId) {
             alert('Please select a Repliz account first.');
             return;
         }
         
         if (!confirm(`Upload ${clips.length} clips to ${platform}?`)) return;
         
         let success = 0, fail = 0;
         newBtn.textContent = 'Uploading...';
         newBtn.disabled = true;
         
         for (let c of clips) {
             try {
                const res = await window.pywebview.api.upload_clip(c.path, platform, {title: c.title, account_id: accountId});
                if (res && res.status === 'success') {
                    success++;
                } else {
                    fail++;
                    console.error("Upload failed for", c.title, res?.message);
                }
             } catch(e) {
                fail++;
             }
         }
         
         newBtn.textContent = 'Upload Semua';
         newBtn.disabled = false;
         alert(`Upload complete!\nSuccess: ${success}\nFailed: ${fail}`);
      });

      clipsBody.innerHTML = '';
      
      if (clips.length === 0) {
        clipsBody.innerHTML = '<div style="padding:16px;color:var(--text-secondary);font-size:13px;">No clips found.</div>';
      } else {
        clips.forEach(c => {
          const clip = window.FileItem.v3({
            title: c.title,
            info1: 'Durasi: ' + c.duration,
            info2: new Date(c.date).toLocaleDateString(),
            onDelete: async () => {
              if (!confirm('Delete this clip?')) return;
              const res = await window.pywebview.api.delete_clip(c.path);
              if (res && res.status === 'ok') refresh();
            },
            onPlay: async () => {
              await window.pywebview.api.play_clip(c.path);
            },
            onUpload: async () => {
              const platform = platformSelect.value;
              const accountId = accountSelect.value;
              
              if (platform === 'repliz' && !accountId) {
                  alert('Please select a Repliz account first.');
                  return;
              }
              
              if (confirm(`Upload this clip to ${platform}?`)) {
                  try {
                      const res = await window.pywebview.api.upload_clip(c.path, platform, {title: c.title, account_id: accountId});
                      if (res && res.status === 'success') {
                          alert('Upload successful!');
                      } else {
                          alert('Upload failed: ' + (res?.message || 'Unknown error'));
                      }
                  } catch (e) {
                      alert('Upload error');
                  }
              }
            }
          });
          
          const actionsDiv = clip.querySelector('.fi-actions');
          if (actionsDiv) {
              const folderBtn = document.createElement('button');
              folderBtn.className = 'icon-btn';
              folderBtn.innerHTML = '📁';
              folderBtn.title = 'Open Folder';
              folderBtn.style.background = 'none';
              folderBtn.style.border = 'none';
              folderBtn.style.cursor = 'pointer';
              folderBtn.style.fontSize = '16px';
              folderBtn.onclick = () => window.pywebview.api.open_output_folder();
              actionsDiv.appendChild(folderBtn);
          }
          
          clipsBody.appendChild(clip);
        });
      }
      
    } catch(e) {
      console.error("Failed to load stock clips", e);
    }
  }

  return { element: section, refresh };
};
