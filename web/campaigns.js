// ── Helper UI List & Chips ──

function getChipValues(container) {
  const chips = container.querySelectorAll('.chip');
  return Array.from(chips).map(c => c.textContent.replace('×', '').trim());
}

function addChip(container, value) {
  value = value.trim();
  if (!value) return;
  const chip = document.createElement('div');
  chip.className = 'chip';
  chip.style.cssText = 'background:#e9ecef;padding:4px 8px;border-radius:16px;font-size:12px;display:flex;align-items:center;gap:4px;';
  chip.innerHTML = `<span>${value}</span><span style="cursor:pointer;color:#dc3545;font-weight:bold;">×</span>`;
  chip.querySelector('span:last-child').addEventListener('click', () => chip.remove());
  container.insertBefore(chip, container.lastElementChild); // before the input
}

function setChips(container, values) {
  // Clear existing chips
  const chips = container.querySelectorAll('.chip');
  chips.forEach(c => c.remove());
  (values || []).forEach(v => addChip(container, v));
}

// Hooks List
function getHooksListValues(container) {
  const textareas = container.querySelectorAll('textarea');
  return Array.from(textareas).map(ta => ta.value.trim()).filter(Boolean);
}

function addHookItem(container, value = '') {
  const item = document.createElement('div');
  item.style.cssText = 'display:flex;gap:8px;align-items:flex-start;';
  const ta = document.createElement('textarea');
  ta.className = 'input';
  ta.style.cssText = 'flex:1;height:40px;resize:vertical;';
  ta.value = value;
  const delBtn = document.createElement('button');
  delBtn.className = 'btn btn-outline';
  delBtn.style.cssText = 'padding:8px;color:#dc3545;border-color:#dc3545;';
  delBtn.textContent = '×';
  delBtn.addEventListener('click', () => item.remove());
  item.appendChild(ta);
  item.appendChild(delBtn);
  container.appendChild(item);
}

function setHooksList(container, values) {
  container.innerHTML = '';
  (values || []).forEach(v => addHookItem(container, v));
}

// Rule List (Do / Don't)
function getRuleListValues(container) {
  const inputs = container.querySelectorAll('input');
  return Array.from(inputs).map(inp => inp.value.trim()).filter(Boolean);
}

function addRuleItem(container, value = '') {
  const item = document.createElement('div');
  item.style.cssText = 'display:flex;gap:8px;align-items:center;';
  const inp = document.createElement('input');
  inp.type = 'text';
  inp.className = 'input';
  inp.style.flex = '1';
  inp.value = value;
  const delBtn = document.createElement('button');
  delBtn.className = 'btn btn-outline';
  delBtn.style.cssText = 'padding:6px 10px;color:#dc3545;border-color:#dc3545;';
  delBtn.textContent = '×';
  delBtn.addEventListener('click', () => item.remove());
  item.appendChild(inp);
  item.appendChild(delBtn);
  container.appendChild(item);
}

function setRuleList(container, values) {
  container.innerHTML = '';
  (values || []).forEach(v => addRuleItem(container, v));
}

// Aturan Umum List (Title + Description)
function getAturanUmumValues(container) {
  const items = container.querySelectorAll('.aturan-item');
  return Array.from(items).map(item => {
    return {
      title: item.querySelector('.aturan-title').value.trim(),
      description: item.querySelector('.aturan-desc').value.trim()
    };
  }).filter(obj => obj.title || obj.description);
}

function addAturanUmumItem(container, title = '', description = '') {
  const item = document.createElement('div');
  item.className = 'aturan-item';
  item.style.cssText = 'display:flex;flex-direction:column;gap:4px;padding:8px;border:1px solid #dee2e6;border-radius:4px;position:relative;';
  
  const delBtn = document.createElement('button');
  delBtn.className = 'btn';
  delBtn.style.cssText = 'position:absolute;top:4px;right:4px;background:none;color:#dc3545;padding:0 4px;font-size:16px;line-height:1;border:none;cursor:pointer;';
  delBtn.innerHTML = '×';
  delBtn.addEventListener('click', () => item.remove());
  
  const titleInp = document.createElement('input');
  titleInp.type = 'text';
  titleInp.className = 'input aturan-title';
  titleInp.placeholder = 'Judul Aturan';
  titleInp.value = title;
  
  const descInp = document.createElement('textarea');
  descInp.className = 'input aturan-desc';
  descInp.style.cssText = 'height:40px;resize:vertical;';
  descInp.placeholder = 'Deskripsi';
  descInp.value = description;
  
  item.appendChild(delBtn);
  item.appendChild(titleInp);
  item.appendChild(descInp);
  container.appendChild(item);
}

function setAturanUmumList(container, values) {
  container.innerHTML = '';
  (values || []).forEach(v => addAturanUmumItem(container, v.title, v.description));
}

function getCheckedAccountIds() {
  const checkboxes = campaignEditView.fields.accountPickerList.querySelectorAll('input[type="checkbox"]:checked');
  return Array.from(checkboxes).map(cb => cb.value);
}

function updateAccountCounter() {
  const list = campaignEditView.fields.accountPickerList;
  const total = list.querySelectorAll('input[type="checkbox"]').length;
  const checked = list.querySelectorAll('input[type="checkbox"]:checked').length;
  campaignEditView.fields.accountCounter.textContent = `${checked}/${total} akun dipilih`;
}

// ── Event Attachment untuk Helper UI ──

function attachDynamicUIEvents() {
  const fields = campaignEditView.fields;
  
  // Hashtags
  fields.hashtagsRealInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addChip(fields.hashtagsInput, e.target.value);
      e.target.value = '';
    }
  });
  
  // Angles
  fields.anglesRealInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addChip(fields.anglesInput, e.target.value);
      e.target.value = '';
    }
  });
  
  // List Add Buttons
  fields.addHookBtn.addEventListener('click', () => addHookItem(fields.hooksList));
  fields.addDoBtn.addEventListener('click', () => addRuleItem(fields.doRulesList));
  fields.addDontBtn.addEventListener('click', () => addRuleItem(fields.dontRulesList));
  fields.addAturanUmumBtn.addEventListener('click', () => addAturanUmumItem(fields.aturanUmumList));
}

// Attach once
attachDynamicUIEvents();

// ── AI Extraction Logic ──

function applyExtractedBrief(res) {
  if (!res || res.status !== 'ok') {
    alert('Ekstraksi gagal: ' + (res ? res.message : 'unknown error'));
    return;
  }
  const d = res.extracted;
  const f = campaignEditView.fields;
  
  if (d.name) f.nameInput.value = d.name;
  
  const b = d.brief || {};
  f.durasiMinInput.value = b.durasi_min || 15;
  f.durasiMaxInput.value = b.durasi_max || 180;
  f.maxClipsPerDayInput.value = b.max_clips_per_day || 2;
  setChips(f.hashtagsInput, b.hashtags || []);
  f.taggedAccountsInput.value = (b.tagged_accounts || []).join(', ');
  setHooksList(f.hooksList, b.hooks || []);
  f.catatanArea.value = b.catatan || '';
  setChips(f.anglesInput, b.angles || []);
  f.personaArea.value = b.persona || '';
  f.tujuanInput.value = b.tujuan || '';
  f.ctaInput.value = b.cta || '';
  
  setRuleList(f.doRulesList, d.do_rules || []);
  setRuleList(f.dontRulesList, d.dont_rules || []);
  setAturanUmumList(f.aturanUmumList, d.aturan_umum || []);
}

async function runExtraction({ text, filePath }) {
  const f = campaignEditView.fields;
  f.extractBtn.disabled = true;
  f.extractBtn.textContent = 'Extracting...';
  try {
    let res;
    if (filePath) {
      const ext = filePath.split('.').pop().toLowerCase();
      if (['png', 'jpg', 'jpeg', 'webp'].includes(ext)) {
        const b64 = await window.pywebview.api.read_file_as_base64(filePath);
        res = await window.pywebview.api.extract_campaign_brief("image", b64);
      } else {
        res = await window.pywebview.api.extract_campaign_brief("doc", filePath);
      }
    } else {
      res = await window.pywebview.api.extract_campaign_brief("text", text);
    }
    applyExtractedBrief(res);
  } catch (err) {
    alert("Error extraction: " + err);
  } finally {
    f.extractBtn.disabled = false;
    f.extractBtn.textContent = 'Create brief';
  }
}

// ── Campaign Logic ──

let currentCampaignId = null;

async function refreshCampaignList() {
  const campaigns = await window.pywebview.api.get_campaigns();
  
  // Update grid
  const grid = campaignListView.fields.grid;
  grid.innerHTML = '';
  
  // Update home dropdown
  const select = homeView.fields.campaign;
  select.innerHTML = '<option value="">Tanpa campaign</option>';
  
  campaigns.forEach(c => {
    // Add to home dropdown
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.name;
    select.appendChild(opt);

    // Add to grid
    const card = document.createElement('div');
    card.className = 'card';
    card.style.cssText = 'padding:16px;display:flex;flex-direction:column;gap:12px;cursor:pointer;position:relative;overflow:hidden;';
    
    // Banner 3:2
    if (c.banner_path) {
      const bannerUrl = c.banner_path.replace(/\\/g, '/');
      const banner = document.createElement('div');
      banner.style.cssText = `width:100%;aspect-ratio:3/2;background-image:url("file:///${bannerUrl}");background-size:cover;background-position:center;border-radius:4px;`;
      card.appendChild(banner);
    }
    
    const title = document.createElement('h3');
    title.style.cssText = 'margin:0;font-size:18px;font-weight:600;';
    title.textContent = c.name;
    
    const status = document.createElement('button');
    status.title = 'Delete Campaign';
    status.style.cssText = 'background:transparent;border:none;cursor:pointer;padding:4px;display:flex;align-items:center;align-self:flex-start;opacity:0.6;transition:opacity 150ms;';
    status.onmouseover = () => status.style.opacity = '1';
    status.onmouseout = () => status.style.opacity = '0.6';
    status.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#EF4444" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>`;
    status.addEventListener('click', async (e) => {
      e.stopPropagation();
      if (!confirm(`Hapus campaign "${c.name}"?`)) return;
      await window.pywebview.api.delete_campaign(c.id);
      refreshCampaignList();
    });
    
    const topRow = document.createElement('div');
    topRow.style.cssText = 'display:flex;justify-content:space-between;align-items:flex-start;';
    topRow.appendChild(title);
    topRow.appendChild(status);
    
    card.appendChild(topRow);
    
    // Stats
    const statStr = document.createElement('div');
    statStr.style.cssText = 'font-size:12px;color:var(--text-muted);';
    statStr.textContent = 'Loading stats...';
    card.appendChild(statStr);

    if (c.id) {
        window.pywebview.api.get_campaign_stats(c.id).then(stats => {
            if (stats) {
                statStr.textContent = `${stats.account_count || 0} akun · ${stats.clip_in_stock || 0} clip`;
            }
        });
    }

    // Action buttons
    const btnsRow = document.createElement('div');
    btnsRow.style.cssText = 'display:flex;gap:8px;margin-top:auto;';
    const stokBtn = document.createElement('button');
    stokBtn.className = 'btn btn-outline';
    stokBtn.style.flex = '1';
    stokBtn.textContent = 'Stok';
    const uploadBtn = document.createElement('button');
    uploadBtn.className = 'btn btn-lime';
    uploadBtn.style.flex = '1';
    uploadBtn.textContent = 'Upload';
    
    stokBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      setActiveView('stock-clip');
      stockClipView.refresh(c.id, false);
    });

    uploadBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      setActiveView('stock-clip');
      stockClipView.refresh(c.id, true);
    });

    btnsRow.appendChild(stokBtn);
    btnsRow.appendChild(uploadBtn);
    card.appendChild(btnsRow);

    card.addEventListener('click', () => openCampaignEdit(c.id));
    grid.appendChild(card);
  });
}

async function populateAccountPicker(selectedIds = []) {
  const f = campaignEditView.fields;
  const list = f.accountPickerList;
  list.innerHTML = 'Loading accounts...';
  
  try {
    const res = await window.pywebview.api.get_repliz_accounts();
    list.innerHTML = '';
    if (res && res.status === 'ok') {
      const accounts = res.accounts || [];
      if (accounts.length === 0) {
        list.innerHTML = '<span style="color:#6c757d;font-size:12px;">Tidak ada akun terhubung</span>';
      } else {
        accounts.forEach(acc => {
          const lbl = document.createElement('label');
          lbl.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer;font-size:14px;';
          const cb = document.createElement('input');
          cb.type = 'checkbox';
          cb.value = acc._id;
          if (selectedIds.includes(acc._id)) cb.checked = true;
          cb.addEventListener('change', updateAccountCounter);
          
          let icon = '📱';
          if (acc.type === 'youtube') icon = '▶️';
          else if (acc.type === 'instagram') icon = '📸';
          
          lbl.appendChild(cb);
          lbl.append(` ${icon} ${acc.name}`);
          list.appendChild(lbl);
        });
      }
    } else {
      list.innerHTML = '<span style="color:#dc3545;font-size:12px;">Gagal memuat akun</span>';
    }
  } catch (err) {
    list.innerHTML = '<span style="color:#dc3545;font-size:12px;">Error memuat akun</span>';
  }
  updateAccountCounter();
}

async function openCampaignEdit(id = null) {
  currentCampaignId = id;
  const f = campaignEditView.fields;
  
  // Reset form
  f.nameInput.value = '';
  f.statusSelect.value = 'active';
  f.durasiMinInput.value = '15';
  f.durasiMaxInput.value = '180';
  setChips(f.hashtagsInput, []);
  f.taggedAccountsInput.value = '';
  setHooksList(f.hooksList, []);
  f.catatanArea.value = '';
  setChips(f.anglesInput, []);
  f.personaArea.value = '';
  f.tujuanInput.value = '';
  f.ctaInput.value = '';
  
  setRuleList(f.doRulesList, []);
  setRuleList(f.dontRulesList, []);
  setAturanUmumList(f.aturanUmumList, []);
  
  f.contextArea.value = '';
  f.bannerPreview.style.backgroundImage = 'none';
  f.bannerText.style.display = 'block';
  f.statsDiv.style.display = 'none';
  f.cardBtnsDiv.style.display = 'none';
  
  let selectedAccounts = [];

  if (id) {
    const campaigns = await window.pywebview.api.get_campaigns();
    const c = campaigns.find(x => x.id === id);
    if (c) {
      f.nameInput.value = c.name;
      f.statusSelect.value = c.status || 'active';
      
      const b = c.brief || {};
      f.durasiMinInput.value = b.durasi_min || 15;
      f.durasiMaxInput.value = b.durasi_max || 180;
      f.maxClipsPerDayInput.value = b.max_clips_per_day || 2;
      setChips(f.hashtagsInput, b.hashtags || []);
      f.taggedAccountsInput.value = (b.tagged_accounts || []).join(', ');
      setHooksList(f.hooksList, b.hooks || []);
      f.catatanArea.value = b.catatan || c.context || '';
      setChips(f.anglesInput, b.angles || []);
      f.personaArea.value = b.persona || '';
      f.tujuanInput.value = b.tujuan || '';
      f.ctaInput.value = b.cta || '';
      
      setRuleList(f.doRulesList, c.do_rules || []);
      setRuleList(f.dontRulesList, c.dont_rules || []);
      setAturanUmumList(f.aturanUmumList, c.aturan_umum || []);
      
      selectedAccounts = c.account_ids || [];

      if (c.banner_path) {
        const bannerUrl = c.banner_path.replace(/\\/g, '/');
        f.bannerPreview.style.backgroundImage = `url("file:///${bannerUrl}")`;
        f.bannerText.style.display = 'none';
      }
      
      const stats = await window.pywebview.api.get_campaign_stats(id);
      if (stats) {
          f.statsDiv.style.display = 'block';
          f.statsDiv.innerHTML = `<strong>Statistics:</strong><br/>${stats.account_count || 0} akun terhubung<br/>${stats.clip_uploaded || 0} clip diupload &middot; ${stats.clip_in_stock || 0} di stok`;
          f.cardBtnsDiv.style.display = 'flex';
          
          // Re-attach button events for edit view
          f.stokBtn.onclick = () => { 
            setActiveView('stock-clip'); 
            stockClipView.refresh(id, false);
          };
          f.uploadBtn.onclick = () => { 
            setActiveView('stock-clip');
            stockClipView.refresh(id, true);
          };
      }
    }
  }
  
  populateAccountPicker(selectedAccounts);
  setActiveView('campaign-edit');
}

async function saveCampaign() {
  const f = campaignEditView.fields;
  
  const data = {
    name: f.nameInput.value.trim(),
    status: f.statusSelect.value,
    account_ids: getCheckedAccountIds(),
    brief: {
      durasi_min: parseInt(f.durasiMinInput.value) || 15,
      durasi_max: parseInt(f.durasiMaxInput.value) || 180,
      hashtags: getChipValues(f.hashtagsInput),
      tagged_accounts: f.taggedAccountsInput.value.split(',').map(s => s.trim()).filter(Boolean),
      hooks: getHooksListValues(f.hooksList),
      catatan: f.catatanArea.value.trim(),
      angles: getChipValues(f.anglesInput),
      persona: f.personaArea.value.trim(),
      tujuan: f.tujuanInput.value.trim(),
      cta: f.ctaInput.value.trim(),
      max_clips_per_day: parseInt(f.maxClipsPerDayInput.value) || 2
    },
    do_rules: getRuleListValues(f.doRulesList),
    dont_rules: getRuleListValues(f.dontRulesList),
    aturan_umum: getAturanUmumValues(f.aturanUmumList)
  };
  
  if (!data.name) {
    alert("Campaign name is required");
    return;
  }
  
  f.saveBtn.disabled = true;
  f.saveBtn.textContent = 'Saving...';
  
  try {
    let newId = currentCampaignId;
    if (currentCampaignId) {
      await window.pywebview.api.update_campaign(currentCampaignId, data);
    } else {
      const res = await window.pywebview.api.create_campaign(data);
      if (res && res.id) newId = res.id;
    }
    
    await refreshCampaignList();
    setActiveView('campaign');
  } catch(e) {
    alert("Error saving campaign: " + e);
  } finally {
    f.saveBtn.disabled = false;
    f.saveBtn.textContent = 'Save Campaign';
  }
}

// ── Attach Events ──
campaignListView.fields.createBtn.addEventListener('click', () => openCampaignEdit(null));

campaignEditView.fields.backBtn.addEventListener('click', () => {
  setActiveView('campaign');
});

campaignEditView.fields.saveBtn.addEventListener('click', saveCampaign);

// Document / Banner Path Workarounds
campaignEditView.fields.bannerPreview.addEventListener('click', async (e) => {
    e.preventDefault(); 
    if (!currentCampaignId) {
        alert("Please save the campaign first before uploading a banner.");
        return;
    }
    try {
        const res = await window.pywebview.api.browse_watermark_image(); // Reuse browse function
        if (res && res.status === 'ok') {
            const upRes = await window.pywebview.api.upload_campaign_banner(currentCampaignId, res.path);
            if (upRes && upRes.status === 'ok') {
                const bannerUrl = upRes.banner_path.replace(/\\/g, '/');
                campaignEditView.fields.bannerPreview.style.backgroundImage = `url("file:///${bannerUrl}")`;
                campaignEditView.fields.bannerText.style.display = 'none';
            } else {
                alert("Upload failed: " + (upRes ? upRes.message : ""));
            }
        }
    } catch(err) {
        console.error(err);
    }
});

// Remove default click from bannerPreview that triggers bannerInput
if (campaignEditView.fields.bannerInput && campaignEditView.fields.bannerInput.parentNode) {
  campaignEditView.fields.bannerInput.remove();
}

campaignEditView.fields.docFile.parentElement.addEventListener('click', async (e) => {
    e.preventDefault(); 
    try {
        // Reuse browse_watermark_image (but ideally needs a specific file picker in python backend)
        const res = await window.pywebview.api.browse_brief_file(); 
        if (res && res.status === 'ok') {
            await runExtraction({ text: null, filePath: res.path });
        }
    } catch (err) {
        console.error(err);
    }
});

campaignEditView.fields.extractBtn.addEventListener('click', async () => {
    const text = campaignEditView.fields.contextArea.value.trim();
    if (!text) {
        alert("Teks brief kosong. Paste teks atau upload dokumen.");
        return;
    }
    await runExtraction({ text, filePath: null });
});
