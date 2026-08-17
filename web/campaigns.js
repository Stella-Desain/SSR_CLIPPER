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
    card.style.cssText = 'padding:16px;display:flex;flex-direction:column;gap:12px;cursor:pointer;position:relative;';
    
    // Banner background if exists
    if (c.banner_path) {
      const banner = document.createElement('div');
      // Fix windows path issues in CSS url
      const bannerUrl = c.banner_path.replace(/\\/g, '/');
      banner.style.cssText = `position:absolute;top:0;left:0;right:0;height:80px;background-image:url("file:///${bannerUrl}");background-size:cover;background-position:center;border-radius:8px 8px 0 0;opacity:0.6;`;
      card.appendChild(banner);
      card.style.paddingTop = '96px'; // Push content down
    }
    
    const title = document.createElement('h3');
    title.style.cssText = 'margin:0;font-size:18px;font-weight:600;position:relative;z-index:1;';
    title.textContent = c.name;
    
    const status = document.createElement('span');
    status.style.cssText = `font-size:12px;padding:4px 8px;border-radius:12px;align-self:flex-start;position:relative;z-index:1;${c.status === 'active' ? 'background:#e6f4ea;color:#137333;' : 'background:#f1f3f4;color:#5f6368;'}`;
    status.textContent = c.status.toUpperCase();
    
    card.appendChild(status);
    card.appendChild(title);
    
    // Stats
    if (c.id) {
        window.pywebview.api.get_campaign_stats(c.id).then(stats => {
            if (stats) {
                const statStr = document.createElement('div');
                statStr.style.cssText = 'font-size:12px;color:var(--text-muted);position:relative;z-index:1;';
                statStr.textContent = `${stats.videos_count || 0} Videos | ${stats.clips_count || 0} Clips`;
                card.appendChild(statStr);
            }
        });
    }

    card.addEventListener('click', () => openCampaignEdit(c.id));
    grid.appendChild(card);
  });
}

async function openCampaignEdit(id = null) {
  currentCampaignId = id;
  const fields = campaignEditView.fields;
  
  // Reset form
  fields.nameInput.value = '';
  fields.statusSelect.value = 'active';
  fields.contextArea.value = '';
  fields.hookArea.value = '';
  fields.bannerPreview.style.backgroundImage = 'none';
  fields.bannerText.style.display = 'block';
  fields.statsDiv.style.display = 'none';
  
  if (id) {
    const campaigns = await window.pywebview.api.get_campaigns();
    const c = campaigns.find(x => x.id === id);
    if (c) {
      fields.nameInput.value = c.name;
      fields.statusSelect.value = c.status || 'active';
      fields.contextArea.value = c.context || '';
      fields.hookArea.value = c.extracted_hook || '';
      if (c.banner_path) {
        const bannerUrl = c.banner_path.replace(/\\/g, '/');
        fields.bannerPreview.style.backgroundImage = `url("file:///${bannerUrl}")`;
        fields.bannerText.style.display = 'none';
      }
      
      const stats = await window.pywebview.api.get_campaign_stats(id);
      if (stats) {
          fields.statsDiv.style.display = 'block';
          fields.statsDiv.innerHTML = `<strong>Statistics:</strong><br/>Total Videos: ${stats.videos_count || 0}<br/>Total Clips: ${stats.clips_count || 0}`;
      }
    }
  }
  
  setActiveView('campaign-edit');
}

async function saveCampaign() {
  const fields = campaignEditView.fields;
  const data = {
    name: fields.nameInput.value.trim(),
    status: fields.statusSelect.value,
    context: fields.contextArea.value.trim(),
    extracted_hook: fields.hookArea.value.trim()
  };
  
  if (!data.name) {
    alert("Campaign name is required");
    return;
  }
  
  fields.saveBtn.disabled = true;
  fields.saveBtn.textContent = 'Saving...';
  
  try {
    let newId = currentCampaignId;
    if (currentCampaignId) {
      await window.pywebview.api.update_campaign(currentCampaignId, data);
    } else {
      const res = await window.pywebview.api.create_campaign(data);
      if (res && res.id) newId = res.id;
    }
    
    // Upload banner if selected
    if (newId && fields.bannerInput.files.length > 0) {
      const file = fields.bannerInput.files[0];
      // Note: In pywebview, we cannot easily send File objects directly.
      // So we read it as base64 and send it, or we trigger a pywebview dialog.
      // Wait, the python backend `upload_campaign_banner` expects a `file_path`.
      // Actually, since we're in a browser, we can't get the absolute file path from an <input type="file">!
      // This is a known issue. We'll use a pywebview file dialog instead.
    }

    await refreshCampaignList();
    setActiveView('campaign');
  } catch(e) {
    alert("Error saving campaign: " + e);
  } finally {
    fields.saveBtn.disabled = false;
    fields.saveBtn.textContent = 'Save Campaign';
  }
}

// Attach Events
campaignListView.fields.createBtn.addEventListener('click', () => openCampaignEdit(null));

campaignEditView.fields.backBtn.addEventListener('click', () => {
  setActiveView('campaign');
});

campaignEditView.fields.saveBtn.addEventListener('click', saveCampaign);

// Document / Banner Path Workarounds
// Since JS can't get absolute paths from <input type="file">, we must use window.pywebview.api 
campaignEditView.fields.bannerPreview.addEventListener('click', async (e) => {
    e.preventDefault(); // Stop the default input file click
    if (!currentCampaignId) {
        alert("Please save the campaign first before uploading a banner.");
        return;
    }
    try {
        const res = await window.pywebview.api.browse_watermark_image(); // Reuse browse function
        if (res && res.status === 'ok') {
            const upRes = await window.pywebview.api.upload_campaign_banner(currentCampaignId, res.path);
            if (upRes && upRes.status === 'success') {
                const bannerUrl = upRes.banner_path.replace(/\\/g, '/');
                campaignEditView.fields.bannerPreview.style.backgroundImage = `url("file:///${bannerUrl}")`;
                campaignEditView.fields.bannerText.style.display = 'none';
            } else {
                alert("Upload failed");
            }
        }
    } catch(err) {
        console.error(err);
    }
});

// Remove default click from bannerPreview that triggers bannerInput
campaignEditView.fields.bannerInput.remove(); // Just use pywebview browse instead

// For Document Upload for Brief
campaignEditView.fields.docFile.parentElement.addEventListener('click', async (e) => {
    e.preventDefault(); // Stop default
    try {
        const res = await window.pywebview.api.browse_watermark_image(); // We should create a browse_document function in backend, but for now we can try to pass path
        if (res && res.status === 'ok') {
            campaignEditView.fields.extractBtn.disabled = true;
            campaignEditView.fields.extractBtn.textContent = 'Extracting...';
            
            const extractRes = await window.pywebview.api.extract_campaign_brief(
                campaignEditView.fields.contextArea.value, 
                res.path
            );
            
            if (extractRes && extractRes.status === 'success') {
                campaignEditView.fields.hookArea.value = extractRes.brief;
            } else {
                alert("Extraction failed: " + (extractRes ? extractRes.error : ""));
            }
            campaignEditView.fields.extractBtn.disabled = false;
            campaignEditView.fields.extractBtn.textContent = 'Extract AI Brief';
        }
    } catch (err) {
        console.error(err);
    }
});

campaignEditView.fields.extractBtn.addEventListener('click', async () => {
    campaignEditView.fields.extractBtn.disabled = true;
    campaignEditView.fields.extractBtn.textContent = 'Extracting...';
    
    try {
        const extractRes = await window.pywebview.api.extract_campaign_brief(
            campaignEditView.fields.contextArea.value, 
            null
        );
        
        if (extractRes && extractRes.status === 'success') {
            campaignEditView.fields.hookArea.value = extractRes.brief;
        } else {
            alert("Extraction failed: " + (extractRes ? extractRes.error : ""));
        }
    } catch (err) {
        alert("Error: " + err);
    } finally {
        campaignEditView.fields.extractBtn.disabled = false;
        campaignEditView.fields.extractBtn.textContent = 'Extract AI Brief';
    }
});
