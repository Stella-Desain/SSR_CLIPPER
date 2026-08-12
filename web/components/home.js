window.Components = window.Components || {};

window.Components.HomeView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'create-clip';

  // Page header
  const pageHeader = document.createElement('div');
  pageHeader.style.marginBottom = '28px';
  pageHeader.innerHTML = `<h1 class="page-title">Create Clip</h1><p class="page-subtitle">An easy way to create clips with care and precision.</p>`;
  section.appendChild(pageHeader);

  // 3-col grid
  const grid = document.createElement('div');
  grid.style.cssText = 'display:grid;grid-template-columns:1fr 1fr 1fr;gap:20px;min-height:calc(100vh - 220px);';

  // ── Column 1: Configuration ──
  const col1 = document.createElement('div');
  col1.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

  const configCard = document.createElement('div');
  configCard.className = 'card';
  configCard.style.cssText = 'flex:1;display:flex;flex-direction:column;';

  const configHeader = document.createElement('div');
  configHeader.className = 'card-header';
  configHeader.innerHTML = `
    <h2 class="card-title">Configuration</h2>
    <button class="btn btn-outline" id="cookies-btn">
      <svg style="width:14px;height:14px;" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke-linecap="round" stroke-linejoin="round"></path></svg>
      Cookies
    </button>
  `;
  configCard.appendChild(configHeader);

  const configBody = document.createElement('div');
  configBody.className = 'card-body';
  configBody.style.cssText = 'flex:1;display:flex;flex-direction:column;';

  // YouTube Link
  const urlGroup = document.createElement('div');
  urlGroup.style.marginBottom = '20px';
  urlGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Link Youtube</label>`;
  const urlRow = document.createElement('div');
  urlRow.style.cssText = 'display:flex;gap:8px;';
  const urlInput = document.createElement('input');
  urlInput.className = 'input';
  urlInput.id = 'url';
  urlInput.type = 'text';
  urlInput.placeholder = 'Paste YouTube link here...';
  urlInput.style.flex = '1';
  const pasteBtn = document.createElement('button');
  pasteBtn.className = 'btn btn-outline';
  pasteBtn.textContent = 'Paste';
  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      urlInput.value = text;
    } catch {}
  });
  urlRow.appendChild(urlInput);
  urlRow.appendChild(pasteBtn);
  urlGroup.appendChild(urlRow);
  configBody.appendChild(urlGroup);

  // Features section
  const optLabel = document.createElement('label');
  optLabel.className = 'field-label';
  optLabel.style.cssText = 'display:block;margin-bottom:10px;';
  optLabel.textContent = 'Features';
  configBody.appendChild(optLabel);

  const toggles = document.createElement('div');
  toggles.style.cssText = 'display:flex;flex-direction:column;gap:8px;flex:1;';

  function makeToggle(label, sub, id, checked) {
    const item = document.createElement('div');
    item.className = 'toggle-item';
    const left = document.createElement('div');
    left.innerHTML = `<div class="toggle-item-label">${label}</div><div class="toggle-item-sub">${sub}</div>`;
    const sw = document.createElement('label');
    sw.className = 'toggle-switch';
    const input = document.createElement('input');
    input.type = 'checkbox';
    input.id = id;
    input.checked = checked;
    const slider = document.createElement('span');
    slider.className = 'toggle-slider';
    sw.appendChild(input);
    sw.appendChild(slider);
    item.appendChild(left);
    item.appendChild(sw);
    return { element: item, input };
  }

  const portraitToggle  = makeToggle('Portrait Mode',    'Model name', 'portrait-mode',    false);
  const highlightToggle = makeToggle('Highlight Finder', 'Model name', 'highlight-finder', true);
  const captionToggle   = makeToggle('Caption Maker',    'Model name', 'caption-maker',    true);
  const hookToggle      = makeToggle('Hook Maker',       'Model name', 'hook-maker',       true);
  const titleToggle     = makeToggle('YT Title Maker',   'Model name', 'yt-title-maker',   true);

  toggles.appendChild(portraitToggle.element);
  toggles.appendChild(highlightToggle.element);
  toggles.appendChild(captionToggle.element);
  toggles.appendChild(hookToggle.element);
  toggles.appendChild(titleToggle.element);
  configBody.appendChild(toggles);

  // Clips select
  const clipsLabel = document.createElement('label');
  clipsLabel.className = 'field-label';
  clipsLabel.style.cssText = 'display:block;margin-top:10px;margin-bottom:6px;';
  clipsLabel.textContent = 'Number of Clips';
  configBody.appendChild(clipsLabel);
  const clipsSelect = document.createElement('select');
  clipsSelect.className = 'input';
  clipsSelect.id = 'clips';
  clipsSelect.style.marginBottom = '10px';
  clipsSelect.innerHTML = '<option value="3">3</option><option value="5" selected>5</option><option value="8">8</option>';
  configBody.appendChild(clipsSelect);

  // Subtitle select
  const subtitleLabel = document.createElement('label');
  subtitleLabel.className = 'field-label';
  subtitleLabel.style.cssText = 'display:block;margin-top:10px;margin-bottom:6px;';
  subtitleLabel.textContent = 'Subtitle Language';
  configBody.appendChild(subtitleLabel);
  const subtitleSelect = document.createElement('select');
  subtitleSelect.className = 'input';
  subtitleSelect.id = 'subtitle';
  subtitleSelect.style.marginBottom = '10px';
  subtitleSelect.innerHTML = '<option value="id" selected>Indonesian</option><option value="en">English</option>';
  configBody.appendChild(subtitleSelect);

  // Cookies
  const cookieSection = document.createElement('div');
  cookieSection.style.marginTop = '16px';
  cookieSection.innerHTML = `
    <div style="display:flex;justify-content:space-between;margin-bottom:6px;">
      <label class="field-label">Cookies</label>
      <span style="font-size:11px;color:var(--text-muted);">Expired in 2 weeks</span>
    </div>
    <div class="upload-zone" id="cookies-upload-zone" style="cursor:pointer;">Upload Your Cookies Here</div>
  `;
  configBody.appendChild(cookieSection);

  configCard.appendChild(configBody);
  col1.appendChild(configCard);

  // Bottom button col1
  const saveConfigBtn = document.createElement('button');
  saveConfigBtn.className = 'btn btn-lime-full';
  saveConfigBtn.textContent = 'Save Default Configuration';
  col1.appendChild(saveConfigBtn);

  // ── Column 2: Preview ──
  const col2 = document.createElement('div');
  col2.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

  const preview = document.createElement('div');
  preview.className = 'preview-panel';
  preview.style.flex = '1';
  preview.innerHTML = '<div class="preview-text">9:16</div>';
  col2.appendChild(preview);

  const startBtn = document.createElement('button');
  startBtn.className = 'btn btn-lime-full';
  startBtn.id = 'start';
  startBtn.textContent = 'Create Clip';
  col2.appendChild(startBtn);

  // ── Column 3: Progress ──
  const col3 = document.createElement('div');
  col3.style.cssText = 'display:flex;flex-direction:column;gap:16px;';

  const progressCard = document.createElement('div');
  progressCard.className = 'card';
  progressCard.style.cssText = 'flex:1;display:flex;flex-direction:column;';

  const progressHeader = document.createElement('div');
  progressHeader.className = 'card-header';
  const progressCount = document.createElement('span');
  progressCount.id = 'progress-count';
  progressCount.style.cssText = 'font-size:20px;font-weight:700;';
  progressCount.textContent = '0/0';
  progressHeader.innerHTML = '<h2 class="card-title">Progress</h2>';
  progressHeader.appendChild(progressCount);
  progressCard.appendChild(progressHeader);

  const progressBody = document.createElement('div');
  progressBody.className = 'card-body';
  progressBody.style.cssText = 'flex:1;display:flex;flex-direction:column;';

  // Steps
  const steps = document.createElement('div');
  steps.style.cssText = 'display:flex;flex-direction:column;gap:8px;margin-bottom:16px;';

  function makeStep(label, statusClass, statusText) {
    const s = document.createElement('div');
    s.className = 'step-item';
    s.innerHTML = `<span class="step-label">${label}</span><span class="step-status ${statusClass}">${statusText}</span>`;
    return s;
  }

  const stepDownload = makeStep('Download Clip', '', 'Waiting');
  const stepHighlight = makeStep('Finding Highlight', '', 'Waiting');
  const stepEditing = makeStep('Editing', '', 'Waiting');
  const stepExport = makeStep('Export', '', 'Waiting');

  steps.appendChild(stepDownload);
  steps.appendChild(stepHighlight);
  steps.appendChild(stepEditing);
  steps.appendChild(stepExport);
  progressBody.appendChild(steps);

  // Terminal area
  const termHeader = document.createElement('div');
  termHeader.style.cssText = 'display:flex;justify-content:space-between;margin-bottom:6px;';
  termHeader.innerHTML = `<span class="field-label">Program Running..</span><button class="btn-ghost" style="border:none;background:none;font-size:11px;color:var(--text-muted);cursor:pointer;">Copy</button>`;
  progressBody.appendChild(termHeader);

  const terminal = document.createElement('div');
  terminal.className = 'terminal';
  terminal.id = 'terminal';
  terminal.style.flex = '1';
  terminal.textContent = 'Ready...';
  progressBody.appendChild(terminal);

  // Progress bar
  const progressTrack = document.createElement('div');
  progressTrack.className = 'progress-track';
  progressTrack.style.marginTop = '12px';
  const progressFill = document.createElement('div');
  progressFill.className = 'progress-fill';
  progressFill.id = 'bar';
  progressTrack.appendChild(progressFill);
  progressBody.appendChild(progressTrack);

  const statusDiv = document.createElement('div');
  statusDiv.id = 'status';
  statusDiv.style.cssText = 'font-size:12px;color:var(--text-muted);margin-top:8px;min-height:16px;';
  progressBody.appendChild(statusDiv);

  progressCard.appendChild(progressBody);
  col3.appendChild(progressCard);

  const openStockBtn = document.createElement('button');
  openStockBtn.className = 'btn btn-lime-full';
  openStockBtn.textContent = 'Open Clip Stock';
  openStockBtn.addEventListener('click', () => {
    document.querySelectorAll('.nav-item').forEach(n => {
      n.classList.toggle('active', n.dataset.view === 'stock-clip');
    });
    document.querySelectorAll('.view').forEach(v => {
      v.classList.toggle('active', v.dataset.view === 'stock-clip');
    });
  });
  col3.appendChild(openStockBtn);

  grid.appendChild(col1);
  grid.appendChild(col2);
  grid.appendChild(col3);
  section.appendChild(grid);

  function showToast(msg, isError = false) {
    const toast = document.createElement('div');
    toast.textContent = msg;
    toast.style.cssText = `
      position: fixed; bottom: 20px; right: 20px; 
      background: ${isError ? '#ef4444' : '#10b981'}; 
      color: white; padding: 12px 24px; border-radius: 8px; 
      font-size: 14px; font-weight: 500; z-index: 9999;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
      transition: opacity 0.3s;
    `;
    document.body.appendChild(toast);
    setTimeout(() => { toast.style.opacity = '0'; }, 2500);
    setTimeout(() => { if (toast.parentNode) toast.parentNode.removeChild(toast); }, 2800);
  }

  setTimeout(() => {
    const cookiesBtn = section.querySelector('#cookies-btn');
    const cookiesZone = section.querySelector('#cookies-upload-zone');
    const uploadHandler = async () => {
      try {
        const res = await window.pywebview.api.upload_cookies();
        if (res.status === 'ok') {
          showToast('Cookies uploaded successfully!');
        } else if (res.status === 'error') {
          showToast('Error: ' + res.message, true);
        }
      } catch (err) {
        showToast('Failed to upload cookies', true);
      }
    };
    if (cookiesBtn) cookiesBtn.addEventListener('click', uploadHandler);
    if (cookiesZone) cookiesZone.addEventListener('click', uploadHandler);

    async function loadDefaultConfig() {
      try {
        const config = await window.pywebview.api.get_default_config();
        if (config) {
          if (config.num_clips !== undefined) clipsSelect.value = config.num_clips;
          if (config.portrait !== undefined) portraitToggle.input.checked = config.portrait;
          if (config.highlight_finder !== undefined) highlightToggle.input.checked = config.highlight_finder;
          if (config.add_captions !== undefined) captionToggle.input.checked = config.add_captions;
          if (config.add_hook !== undefined) hookToggle.input.checked = config.add_hook;
          if (config.yt_title_maker !== undefined) titleToggle.input.checked = config.yt_title_maker;
        }
      } catch (err) {}
    }
    loadDefaultConfig();
  }, 0);

  saveConfigBtn.addEventListener('click', async () => {
    const settings = {
      num_clips: parseInt(clipsSelect.value, 10),
      portrait: portraitToggle.input.checked,
      highlight_finder: highlightToggle.input.checked,
      add_captions: captionToggle.input.checked,
      add_hook: hookToggle.input.checked,
      yt_title_maker: titleToggle.input.checked
    };
    try {
      const res = await window.pywebview.api.save_default_config(settings);
      if (res && res.status === 'saved') {
        showToast('Default configuration saved!');
      } else {
        showToast('Failed to save config', true);
      }
    } catch (err) {
      showToast('Error saving config', true);
    }
  });

  return {
    element: section,
    fields: {
      url: urlInput,
      start: startBtn,
      clips: clipsSelect,
      subtitle: subtitleSelect,
      portrait: portraitToggle.input,
      highlight: highlightToggle.input,
      captions: captionToggle.input,
      hook: hookToggle.input,
      ytTitle: titleToggle.input,
      bar: progressFill,
      status: statusDiv,
      terminal,
      stepDownload,
      stepHighlight,
      stepEditing,
      stepExport,
    }
  };
};
