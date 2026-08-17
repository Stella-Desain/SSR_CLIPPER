window.Components = window.Components || {};

window.Components.DistributionPanel = function (selectedClipIds, onDone) {
  // Modal overlay
  const overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;z-index:9999;';
  
  // Modal container
  const modal = document.createElement('div');
  modal.style.cssText = 'background:#FFFFFF;width:600px;max-height:90vh;border-radius:12px;display:flex;flex-direction:column;box-shadow:0 10px 25px rgba(0,0,0,0.1);font-family:Inter,sans-serif;';
  
  // Header
  const header = document.createElement('div');
  header.style.cssText = 'padding:20px 24px;border-bottom:1px solid #E5E7EB;display:flex;justify-content:space-between;align-items:center;';
  header.innerHTML = '<h2 style="margin:0;font-size:18px;font-weight:600;color:#111827;">Distribusi & Jadwal Upload</h2>';
  
  const closeBtn = document.createElement('button');
  closeBtn.innerHTML = '✕';
  closeBtn.style.cssText = 'background:none;border:none;font-size:18px;cursor:pointer;color:#6B7280;';
  closeBtn.onclick = () => close();
  header.appendChild(closeBtn);
  modal.appendChild(header);

  // Body
  const body = document.createElement('div');
  body.style.cssText = 'padding:24px;flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:20px;';
  modal.appendChild(body);

  // Config Section
  const configSection = document.createElement('div');
  configSection.style.cssText = 'display:flex;flex-direction:column;gap:16px;background:#F9FAFB;padding:16px;border-radius:8px;border:1px solid #E5E7EB;';
  body.appendChild(configSection);

  // Campaign Info / Dropdown
  const campaignWrap = document.createElement('div');
  configSection.appendChild(campaignWrap);

  // Max clips
  const maxClipsWrap = document.createElement('div');
  maxClipsWrap.style.cssText = 'display:flex;align-items:center;gap:12px;';
  maxClipsWrap.innerHTML = '<label style="font-size:14px;font-weight:500;color:#374151;">Maks clip per akun / hari:</label>';
  const maxClipsInput = document.createElement('input');
  maxClipsInput.type = 'number';
  maxClipsInput.value = 2;
  maxClipsInput.min = 1;
  maxClipsInput.style.cssText = 'width:60px;padding:6px 8px;border:1px solid #D1D5DB;border-radius:6px;font-size:14px;';
  maxClipsInput.onchange = () => loadPreview();
  maxClipsWrap.appendChild(maxClipsInput);
  configSection.appendChild(maxClipsWrap);

  // Preview Section
  const previewSection = document.createElement('div');
  previewSection.style.cssText = 'display:flex;flex-direction:column;gap:12px;';
  body.appendChild(previewSection);

  const previewTitle = document.createElement('h3');
  previewTitle.style.cssText = 'margin:0;font-size:15px;font-weight:600;color:#374151;';
  previewTitle.textContent = 'Preview Jadwal';
  previewSection.appendChild(previewTitle);

  const previewList = document.createElement('div');
  previewList.style.cssText = 'display:flex;flex-direction:column;gap:8px;';
  previewSection.appendChild(previewList);

  const overflowNote = document.createElement('div');
  overflowNote.style.cssText = 'font-size:13px;color:#D97706;padding-top:4px;';
  previewSection.appendChild(overflowNote);

  // Footer
  const footer = document.createElement('div');
  footer.style.cssText = 'padding:16px 24px;border-top:1px solid #E5E7EB;display:flex;justify-content:flex-end;gap:12px;';
  
  const cancelBtn = document.createElement('button');
  cancelBtn.textContent = 'Batal';
  cancelBtn.style.cssText = 'padding:8px 16px;border:1px solid #D1D5DB;background:#FFF;border-radius:6px;font-size:14px;font-weight:500;color:#374151;cursor:pointer;';
  cancelBtn.onclick = () => close();
  
  const confirmBtn = document.createElement('button');
  confirmBtn.textContent = 'Konfirmasi & jadwalkan';
  confirmBtn.style.cssText = 'padding:8px 16px;border:none;background:#8DC63F;border-radius:6px;font-size:14px;font-weight:500;color:#FFF;cursor:pointer;';
  
  footer.appendChild(cancelBtn);
  footer.appendChild(confirmBtn);
  modal.appendChild(footer);
  overlay.appendChild(modal);
  
  let currentCampaignId = null;
  let currentAssignments = [];
  
  function close() {
    if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
  }

  async function init() {
    document.body.appendChild(overlay);
    await loadPreview(null); // try auto-detect
  }

  async function loadPreview(forceCampaignId = null) {
      previewList.innerHTML = '<div style="font-size:14px;color:#6B7280;padding:20px;text-align:center;">Memuat preview...</div>';
      confirmBtn.disabled = true;
      confirmBtn.style.opacity = '0.5';
      
      const maxPerDay = maxClipsInput.value || 2;
      const res = await window.pywebview.api.preview_distribution(Array.from(selectedClipIds), forceCampaignId || currentCampaignId, maxPerDay);
      
      campaignWrap.innerHTML = ''; // reset
      
      if (res && res.status === 'mixed_or_missing_campaign') {
          // Show dropdown
          campaignWrap.innerHTML = `
              <div style="font-size:13px;color:#B91C1C;margin-bottom:8px;">⚠️ ${res.message}</div>
              <div style="display:flex;align-items:center;gap:12px;">
                  <label style="font-size:14px;font-weight:500;color:#374151;">Pilih Campaign:</label>
                  <select id="dist-campaign-select" style="flex:1;padding:6px 8px;border:1px solid #D1D5DB;border-radius:6px;font-size:14px;background:#FFF;">
                      <option value="default">Semua Akun (Default)</option>
                  </select>
              </div>
          `;
          
          const select = campaignWrap.querySelector('#dist-campaign-select');
          try {
              const camps = await window.pywebview.api.get_campaigns();
              if (camps && camps.length > 0) {
                  camps.forEach(c => {
                      const opt = document.createElement('option');
                      opt.value = c.id;
                      opt.textContent = c.name;
                      select.appendChild(opt);
                  });
              }
          } catch(e) {}
          
          if (currentCampaignId) {
              select.value = currentCampaignId;
          }
          
          select.onchange = () => {
              currentCampaignId = select.value;
              loadPreview(currentCampaignId);
          };
          
          previewList.innerHTML = '<div style="font-size:14px;color:#6B7280;padding:20px;text-align:center;">Silakan pilih campaign untuk melihat preview</div>';
          overflowNote.textContent = '';
          return;
      }
      
      if (res && res.status === 'ok') {
          currentCampaignId = res.campaign_id;
          currentAssignments = res.assignments;
          
          if (res.auto_detected) {
              campaignWrap.innerHTML = `
                  <div style="display:flex;align-items:center;justify-content:space-between;">
                      <div style="display:flex;align-items:center;gap:8px;">
                          <span style="color:#10B981;font-size:16px;">✓</span>
                          <span style="font-size:14px;font-weight:600;color:#111827;">${res.campaign_name}</span>
                      </div>
                      <a href="#" id="change-camp-link" style="font-size:12px;color:#3B82F6;text-decoration:none;">Ganti campaign / kelola akun</a>
                  </div>
              `;
              campaignWrap.querySelector('#change-camp-link').onclick = (e) => {
                  e.preventDefault();
                  close();
                  // navigate to campaign edit
                  document.querySelectorAll('.nav-item').forEach(n => {
                    n.classList.toggle('active', n.dataset.view === 'campaign-edit');
                  });
                  document.querySelectorAll('.view').forEach(v => {
                    v.classList.toggle('active', v.dataset.view === 'campaign-edit');
                  });
                  // We should ideally open the specific campaign, but triggering the view is enough for now
              };
          } else {
              campaignWrap.innerHTML = `
                  <div style="display:flex;align-items:center;gap:12px;">
                      <label style="font-size:14px;font-weight:500;color:#374151;">Campaign Aktif:</label>
                      <span style="font-size:14px;font-weight:600;color:#111827;">${res.campaign_name}</span>
                  </div>
              `;
          }
          
          previewList.innerHTML = '';
          if (res.assignments.length === 0) {
              previewList.innerHTML = '<div style="font-size:14px;color:#6B7280;padding:20px;text-align:center;">Tidak ada jadwal yang bisa dibuat.</div>';
          } else {
              res.assignments.forEach(asn => {
                  const item = document.createElement('div');
                  item.style.cssText = 'display:flex;align-items:center;padding:10px 12px;border:1px solid #E5E7EB;border-radius:6px;background:#FFF;gap:12px;';
                  
                  // Dot
                  const dot = document.createElement('div');
                  dot.style.cssText = 'width:8px;height:8px;border-radius:50%;background:#D1D5DB;';
                  item.appendChild(dot);
                  
                  // Title
                  const title = document.createElement('div');
                  title.style.cssText = 'flex:1;font-size:13px;font-weight:500;color:#111827;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
                  title.textContent = asn.clip_title;
                  item.appendChild(title);
                  
                  // Account
                  const acc = document.createElement('div');
                  acc.style.cssText = 'display:flex;align-items:center;gap:6px;font-size:12px;color:#4B5563;background:#F3F4F6;padding:4px 8px;border-radius:4px;';
                  acc.textContent = `[${asn.platform}] ${asn.account_name}`;
                  item.appendChild(acc);
                  
                  // Time
                  const time = document.createElement('div');
                  time.style.cssText = 'font-size:13px;color:#6B7280;width:130px;text-align:right;';
                  const dt = new Date(asn.scheduled_at);
                  time.textContent = dt.toLocaleDateString() + ' ' + dt.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                  item.appendChild(time);
                  
                  previewList.appendChild(item);
              });
              
              confirmBtn.disabled = false;
              confirmBtn.style.opacity = '1';
          }
          
          if (res.overflow_count > 0) {
              overflowNote.textContent = res.overflow_note;
          } else {
              overflowNote.textContent = '';
          }
      }
  }

  confirmBtn.onclick = async () => {
      confirmBtn.disabled = true;
      confirmBtn.textContent = 'Menjadwalkan...';
      const res = await window.pywebview.api.confirm_distribution(currentAssignments);
      if (res && res.status === 'ok') {
          close();
          if (onDone) onDone();
      } else {
          alert('Gagal menjadwalkan: ' + (res?.message || 'Unknown error'));
          confirmBtn.disabled = false;
          confirmBtn.textContent = 'Konfirmasi & jadwalkan';
      }
  };

  init();

  return { element: overlay, open: init, close };
};
