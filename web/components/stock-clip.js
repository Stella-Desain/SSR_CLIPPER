window.Components = window.Components || {};

window.Components.StockClipView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'stock-clip';

  // Folder video yang lagi dipilih di Jobs panel. null = tampilkan semua ("All Video")
  let selectedFolderId = null;

  // Page header
  const pageHeader = document.createElement('div');
  pageHeader.style.marginBottom = '28px';
  pageHeader.innerHTML = `<h1 class="page-title">Stock Clip</h1><p class="page-subtitle">An easy way to manage clips with care and precision.</p>`;
  section.appendChild(pageHeader);

  // 2-column layout
  const layout = document.createElement('div');
  layout.style.cssText = 'display:grid;grid-template-columns:4fr 8fr;gap:20px;min-height:calc(100vh - 240px);';

  // ── Left: Jobs Panel (= daftar folder video) ──
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
    <select id="stock-campaign-filter" class="select" style="width:auto;min-width:140px;max-width:200px;"><option value="all">Video: All</option></select>
    <span id="stock-clips-count" style="font-size:13px;color:var(--text-secondary);font-weight:500;">Clips: 0</span>
  `;
  jobsBody.appendChild(filterRow);

  // Jobs list (video folders)
  const jobsList = document.createElement('div');
  jobsList.style.cssText = 'flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:8px;padding-right:8px;padding-bottom:8px;';
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
        <select id="stock-status-filter" class="select" style="width:auto;">
            <option value="all">Semua Status</option>
            <option value="belum_diupload">Belum diupload</option>
            <option value="terjadwal">Terjadwal</option>
            <option value="uploading">Uploading</option>
            <option value="sukses">Sukses</option>
            <option value="gagal">Gagal</option>
        </select>
        <button id="distribute-btn" class="btn btn-lime" disabled style="opacity:0.5;">Distribusikan & upload</button>
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

  // Clips list container wrapper
  const clipsBodyWrapper = document.createElement('div');
  clipsBodyWrapper.style.cssText = 'flex:1;display:flex;flex-direction:column;position:relative;overflow:hidden;';
  clipsPanel.appendChild(clipsBodyWrapper);

  // Clips list
  const clipsBody = document.createElement('div');
  clipsBody.style.cssText = 'flex:1;overflow-y:auto;padding:20px 24px;display:flex;flex-direction:column;gap:10px;';
  clipsBodyWrapper.appendChild(clipsBody);
  // (action bar footer removed — upload is handled by the single header button)


  layout.appendChild(jobsPanel);
  layout.appendChild(clipsPanel);
  section.appendChild(layout);
  
  let selectedClipIds = new Set();
  let currentVisibleClips = [];
  
  function updateDistributeButton() {
      const btn = section.querySelector('#distribute-btn');
      if (selectedClipIds.size > 0) {
          btn.textContent = `Upload (${selectedClipIds.size})`;
          btn.disabled = false;
          btn.style.opacity = '1';
      } else {
          const eligible = currentVisibleClips.filter(c => c.upload_status === 'belum_diupload');
          btn.textContent = 'Upload Semua';
          btn.disabled = eligible.length === 0;
          btn.style.opacity = eligible.length === 0 ? '0.5' : '1';
      }
  }
  
  section.querySelector('#distribute-btn').onclick = async () => {
      const distributeBtn = section.querySelector('#distribute-btn');
      const idsToUpload = selectedClipIds.size > 0
          ? Array.from(selectedClipIds)
          : currentVisibleClips.filter(c => c.upload_status === 'belum_diupload').map(c => c.id);

      if (idsToUpload.length === 0) return;

      const originalText = distributeBtn.textContent;
      distributeBtn.disabled = true;
      distributeBtn.textContent = 'Mengupload...';

      try {
          const res = await window.pywebview.api.quick_upload(idsToUpload);
          if (res && res.status === 'ok') {
              selectedClipIds.clear();
              await refresh();
          } else {
              alert('Gagal upload: ' + (res?.message || 'Unknown error'));
              distributeBtn.disabled = false;
              distributeBtn.textContent = originalText;
          }
      } catch (e) {
          alert('Terjadi error saat upload');
          distributeBtn.disabled = false;
          distributeBtn.textContent = originalText;
      }
  };

  let currentCampaignFilter = null; // Used for deep linking from Campaign page

  async function refresh(campaignId = null, autoSelectUnuploaded = false) {
    if (campaignId !== null && typeof campaignId === 'string') {
        currentCampaignFilter = campaignId;
    }
    
    if (!window.pywebview || !window.pywebview.api) return;
    try {
      const stats = await window.pywebview.api.get_dashboard_stats();
      const folders = await window.pywebview.api.get_video_folders();
      const foldersById = {};
      folders.forEach(f => { foldersById[f.id] = f; });

      // Kalau folder yang lagi dipilih ternyata sudah kehapus, reset ke "All"
      if (selectedFolderId && !foldersById[selectedFolderId]) {
        selectedFolderId = null;
      }

      // ── Update Jobs panel (list folder video) ──
      jobsList.innerHTML = '';
      if (folders.length === 0) {
        jobsList.innerHTML = '<div style="padding:16px;color:var(--text-secondary);font-size:13px;">No jobs found.</div>';
      } else {
        folders.forEach(folder => {
          const item = window.FileItem.v2({
            title: folder.title || 'Unknown Video',
            info1: `${folder.clip_count} clip${folder.clip_count === 1 ? '' : 's'}`,
            info2: folder.date ? new Date(folder.date).toLocaleDateString() : '',
            size: '',
            onDelete: async () => {
              if (confirm('Delete this video and all its clips?')) {
                const res = await window.pywebview.api.delete_video_folder(folder.id);
                if (res && res.status === 'ok') refresh();
              }
            }
          });

          item.style.cursor = 'pointer';
          if (selectedFolderId === folder.id) {
            item.style.borderColor = '#8DC63F';
            item.style.boxShadow = '0 0 0 1px #8DC63F';
          }
          item.addEventListener('click', (e) => {
            if (e.target.closest('.fi-btn-del') || e.target.closest('.fi-btn-edit2')) return;
            selectedFolderId = (selectedFolderId === folder.id) ? null : folder.id;
            refresh();
          });

          jobsList.appendChild(item);
        });
      }

      // ── Sync Campaign dropdown dengan daftar folder video ──
      const filterSelect = section.querySelector('#stock-campaign-filter');
      filterSelect.innerHTML = '<option value="all">Video: All</option>';
      folders.forEach(f => {
        const opt = document.createElement('option');
        opt.value = f.id;
        opt.textContent = 'Video: ' + (f.title.length > 20 ? f.title.substring(0, 20) + '...' : f.title);
        filterSelect.appendChild(opt);
      });
      filterSelect.value = selectedFolderId && foldersById[selectedFolderId] ? selectedFolderId : 'all';
      filterSelect.onchange = () => {
        selectedFolderId = filterSelect.value === 'all' ? null : filterSelect.value;
        currentCampaignFilter = null; // Clear campaign filter if user manually changes video folder
        refresh();
      };

      // ── Update Clips panel ──
      let clips = await window.pywebview.api.get_stock_clips(selectedFolderId);
      
      // Update filter dropdown with counts
      const statusSummary = await window.pywebview.api.get_clip_upload_status_summary();
      const statusSelect = section.querySelector('#stock-status-filter');
      const currentStatusFilter = statusSelect.value;
      
      statusSelect.innerHTML = `
          <option value="all">Semua Status</option>
          <option value="belum_diupload">Belum diupload (${statusSummary.belum_diupload || 0})</option>
          <option value="terjadwal">Terjadwal (${statusSummary.terjadwal || 0})</option>
          <option value="uploading">Uploading (${statusSummary.uploading || 0})</option>
          <option value="sukses">Sukses (${statusSummary.sukses || 0})</option>
          <option value="gagal">Gagal (${statusSummary.gagal || 0})</option>
      `;
      statusSelect.value = currentStatusFilter;
      statusSelect.onchange = () => refresh();

      // Client-side filtering
      if (currentStatusFilter !== 'all') {
          clips = clips.filter(c => c.upload_status === currentStatusFilter);
      }
      if (currentCampaignFilter) {
          clips = clips.filter(c => c.campaign_id === currentCampaignFilter);
          // Update subtitle
          const subTitleEl = section.querySelector('#clips-sub-title');
          if (subTitleEl) subTitleEl.textContent = `Filtered by Campaign: ${currentCampaignFilter}`;
      } else {
          const subTitleEl = section.querySelector('#clips-sub-title');
          if (subTitleEl) subTitleEl.textContent = selectedFolderId && foldersById[selectedFolderId] ? foldersById[selectedFolderId].title : 'All Video';
      }

      // client-side filtering done — track visible clips
      currentVisibleClips = clips;

      if (autoSelectUnuploaded) {
          const idsToUpload = clips.filter(c => c.upload_status === 'belum_diupload').map(c => c.id);
          if (idsToUpload.length > 0) {
              await window.pywebview.api.quick_upload(idsToUpload);
              await refresh();
              return;
          }
      }

      const countEl = section.querySelector('#stock-clips-count');
      if (countEl) countEl.textContent = `Clips: ${clips.length}`;

      const subCountEl = section.querySelector('#clips-sub-count');
      const subSizeEl = section.querySelector('#clips-sub-size');
      
      if (subCountEl) subCountEl.textContent = `Clips: ${clips.length}`;
      if (subSizeEl) subSizeEl.textContent = `Size: ${stats.storageUsed}`;

      clipsBody.innerHTML = '';

      if (clips.length === 0) {
        clipsBody.innerHTML = '<div style="padding:16px;color:var(--text-secondary);font-size:13px;">No clips found.</div>';
      } else {
        // Build badges styles
        const badgeStyles = {
            'belum_diupload': { bg: '#F3F4F6', text: '#374151' },
            'terjadwal': { bg: '#FEF3C7', text: '#92400E' },
            'uploading': { bg: '#DBEAFE', text: '#1E40AF' },
            'sukses': { bg: '#DCFCE7', text: '#166534' },
            'gagal': { bg: '#FEE2E2', text: '#991B1B' }
        };

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
            onTitleChange: async (newTitle) => {
              const res = await window.pywebview.api.update_clip_title(c.path, newTitle);
              if (!res || res.status !== 'ok') {
                  alert('Gagal menyimpan judul: ' + (res?.message || 'Unknown error'));
                  refresh();
              } else {
                  c.title = newTitle;
              }
            }
          });

          // Create wrapper for checkbox + clip item
          const rowWrapper = document.createElement('div');
          rowWrapper.style.cssText = 'display:flex;align-items:center;gap:12px;width:100%;';
          
          const checkbox = document.createElement('input');
          checkbox.type = 'checkbox';
          checkbox.style.cssText = 'width:16px;height:16px;cursor:pointer;flex-shrink:0;';
          checkbox.checked = selectedClipIds.has(c.id);
          
          checkbox.addEventListener('change', () => {
              if (checkbox.checked) {
                  selectedClipIds.add(c.id);
              } else {
                  selectedClipIds.delete(c.id);
              }
              updateDistributeButton();
          });
          
          rowWrapper.appendChild(checkbox);
          
          // Append badge to the info area of FileItem
          const infoArea = clip.querySelector('.fi-info') || clip.querySelector('.file-sub');
          if (infoArea) {
              const badge = document.createElement('span');
              const style = badgeStyles[c.upload_status] || badgeStyles['belum_diupload'];
              badge.style.cssText = `background:${style.bg};color:${style.text};padding:2px 6px;border-radius:4px;font-size:10px;font-weight:600;margin-left:8px;text-transform:uppercase;`;
              badge.textContent = c.upload_status.replace('_', ' ');
              infoArea.appendChild(badge);
          }
          
          clip.style.flex = '1';
          rowWrapper.appendChild(clip);

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

          clipsBody.appendChild(rowWrapper);
        });
      }
      
      updateDistributeButton();

    } catch(e) {
      console.error("Failed to load stock clips", e);
    }
  }

  return { element: section, refresh };
};
