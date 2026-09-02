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
  urlInput.placeholder = 'https://youtube.com/watch?v=...';
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

  // Campaign Dropdown
  const campGroup = document.createElement('div');
  campGroup.style.marginBottom = '20px';
  campGroup.innerHTML = `<label class="field-label" style="display:block;margin-bottom:6px;">Campaign</label>`;
  const campSelect = document.createElement('select');
  campSelect.className = 'select';
  campSelect.id = 'home-campaign-select';
  campSelect.innerHTML = `<option value="">Tanpa campaign</option>`;
  campGroup.appendChild(campSelect);
  configBody.appendChild(campGroup);

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
    const labelEl = document.createElement('div');
    labelEl.className = 'toggle-item-label';
    labelEl.textContent = label;
    const subEl = document.createElement('select');
    subEl.className = 'toggle-item-sub select';
    subEl.style.cssText = 'background:transparent; border:none; color:var(--text-secondary); padding:0 16px 0 0; height:auto; margin-top:2px; font-size:12px; cursor:pointer; width:100%; outline:none; box-shadow:none;';
    
    // Add default option
    const defOpt = document.createElement('option');
    defOpt.textContent = sub;
    subEl.appendChild(defOpt);

    left.appendChild(labelEl);
    left.appendChild(subEl);
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
    return { element: item, input, subEl };
  }

  const portraitToggle  = makeToggle('Portrait Mode',    'Always enabled', 'portrait-mode',    true);
  const highlightToggle = makeToggle('Highlight Finder', 'Loading...', 'highlight-finder', true);
  const captionToggle   = makeToggle('Caption Maker',    'Loading...', 'caption-maker',    true);
  const hookToggle      = makeToggle('Hook Maker',       'Loading...', 'hook-maker',       true);
  const titleToggle     = makeToggle('YT Title Maker',   'Loading...', 'yt-title-maker',   true);

  // Subtitle Style selector (shown when Caption Maker is ON)
  const subtitleStyleItem = document.createElement('div');
  subtitleStyleItem.className = 'toggle-item';
  subtitleStyleItem.id = 'subtitle-style-container';
  const styleLeft = document.createElement('div');
  const styleLabel = document.createElement('div');
  styleLabel.className = 'toggle-item-label';
  styleLabel.textContent = 'Subtitle Style';
  const styleSub = document.createElement('div');
  styleSub.style.cssText = 'font-size:12px;color:var(--text-secondary);margin-top:2px;';
  styleSub.textContent = 'Visual style for captions';
  styleLeft.appendChild(styleLabel);
  styleLeft.appendChild(styleSub);

  const subtitleStyleSelect = document.createElement('select');
  subtitleStyleSelect.className = 'select';
  subtitleStyleSelect.id = 'subtitle-style';
  subtitleStyleSelect.style.cssText = 'width:auto;min-width:140px;height:32px;font-size:12px;';
  subtitleStyleSelect.innerHTML = `
    <option value="v2" selected>Subtitle V2 (Dynamic Word Pop)</option>
    <option value="v3">Subtitle V3 (Kinetic Emphasis)</option>
    <option value="v1">Subtitle V1 (Classic)</option>
  `;

  subtitleStyleItem.appendChild(styleLeft);
  subtitleStyleItem.appendChild(subtitleStyleSelect);

  captionToggle.input.addEventListener('change', () => {
    subtitleStyleItem.style.display = captionToggle.input.checked ? '' : 'none';
  });

  // Portrait is always on — hide the toggle item from UI
  portraitToggle.element.style.display = 'none';
  portraitToggle.input.checked = true;

  toggles.appendChild(portraitToggle.element);
  toggles.appendChild(highlightToggle.element);
  toggles.appendChild(captionToggle.element);
  toggles.appendChild(subtitleStyleItem);
  toggles.appendChild(hookToggle.element);
  toggles.appendChild(titleToggle.element);
  configBody.appendChild(toggles);

  // Clip mode toggle
  let clipMode = 'fixed';
  const clipModeLabel = document.createElement('label');
  clipModeLabel.className = 'field-label';
  clipModeLabel.style.cssText = 'display:block;margin-top:10px;margin-bottom:6px;';
  clipModeLabel.textContent = 'Number of clips';
  configBody.appendChild(clipModeLabel);

  const clipModeRow = document.createElement('div');
  clipModeRow.style.cssText = 'display:flex;gap:0;margin-bottom:8px;border-radius:8px;overflow:hidden;border:1px solid var(--border);';
  const btnFixed = document.createElement('button');
  btnFixed.textContent = 'Fixed number';
  btnFixed.type = 'button';
  btnFixed.style.cssText = 'flex:1;padding:8px 12px;font-size:12px;font-weight:600;border:none;cursor:pointer;background:var(--lime);color:#1a1a2e;transition:all 0.2s;';
  const btnAI = document.createElement('button');
  btnAI.textContent = 'AI decides';
  btnAI.type = 'button';
  btnAI.style.cssText = 'flex:1;padding:8px 12px;font-size:12px;font-weight:600;border:none;cursor:pointer;background:var(--bg);color:var(--text-secondary);transition:all 0.2s;';
  clipModeRow.appendChild(btnFixed);
  clipModeRow.appendChild(btnAI);
  configBody.appendChild(clipModeRow);

  const clipsInput = document.createElement('input');
  clipsInput.type = 'number';
  clipsInput.min = '1';
  clipsInput.value = '5';
  clipsInput.className = 'input';
  clipsInput.id = 'clips';
  configBody.appendChild(clipsInput);

  const clipModeHint = document.createElement('div');
  clipModeHint.style.cssText = 'font-size:11px;color:var(--text-muted);margin-top:4px;margin-bottom:10px;';
  clipModeHint.textContent = 'Generate this many clips, regardless of score.';
  configBody.appendChild(clipModeHint);

  const aiNote = document.createElement('div');
  aiNote.style.cssText = 'background:rgba(163,255,51,0.08);border:1px solid rgba(163,255,51,0.2);border-radius:8px;padding:10px 12px;font-size:11px;color:#3d6b10;margin-bottom:10px;display:none;';
  aiNote.textContent = 'AI akan menghasilkan sebanyak mungkin clip \u2014 hanya highlight skor sedang & tinggi yang dipakai.';
  configBody.appendChild(aiNote);

  btnFixed.addEventListener('click', () => {
    clipMode = 'fixed';
    btnFixed.style.background = 'var(--lime)'; btnFixed.style.color = '#1a1a2e';
    btnAI.style.background = 'var(--bg)'; btnAI.style.color = 'var(--text-secondary)';
    clipsInput.style.display = ''; clipModeHint.style.display = ''; aiNote.style.display = 'none';
  });
  btnAI.addEventListener('click', () => {
    clipMode = 'ai';
    btnAI.style.background = 'var(--lime)'; btnAI.style.color = '#1a1a2e';
    btnFixed.style.background = 'var(--bg)'; btnFixed.style.color = 'var(--text-secondary)';
    clipsInput.style.display = 'none'; clipModeHint.style.display = 'none'; aiNote.style.display = '';
  });

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
  progressCard.style.cssText = 'flex:1;display:flex;flex-direction:column;background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem;';

  const progressHeader = document.createElement('div');
  progressHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;';
  const progressCount = document.createElement('span');
  progressCount.id = 'progress-count';
  progressCount.style.cssText = 'font-size:20px;font-weight:500;color:var(--text-primary);';
  progressCount.textContent = '0/0';
  progressHeader.innerHTML = '<h2 style="margin:0;font-size:16px;font-weight:600;">Progress</h2>';
  progressHeader.appendChild(progressCount);
  progressCard.appendChild(progressHeader);

  const progressBody = document.createElement('div');
  progressBody.style.cssText = 'flex:1;display:flex;flex-direction:column;';

  function makeStep(label, statusClass, statusText) {
    const s = document.createElement('div');
    s.className = 'step-item';
    s.style.cssText = 'display:flex;justify-content:space-between;align-items:center;background:var(--surface-1);border-radius:var(--radius);padding:8px 12px;margin-bottom:16px;';
    s.innerHTML = `<span class="step-label" style="font-size:13px;color:var(--text-primary);">${label}</span><span class="step-status ${statusClass}" style="font-size:11px;font-weight:500;padding:3px 8px;border-radius:20px;">${statusText}</span>`;
    return s;
  }

  // Preparing step
  const stepPreparing = makeStep('Preparing (download, transcribe, highlights)', '', 'Waiting');
  progressBody.appendChild(stepPreparing);

  // In Progress section
  const inProgressHeader = document.createElement('div');
  inProgressHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;';
  const inProgressLabel = document.createElement('span');
  inProgressLabel.style.cssText = 'font-size:12px;font-weight:500;color:var(--text-secondary);';
  inProgressLabel.textContent = 'In progress';
  const inProgressBadge = document.createElement('span');
  inProgressBadge.style.cssText = 'font-size:11px;color:var(--text-muted);';
  inProgressBadge.textContent = '0';
  inProgressHeader.appendChild(inProgressLabel);
  inProgressHeader.appendChild(inProgressBadge);
  progressBody.appendChild(inProgressHeader);

  const inProgressList = document.createElement('div');
  inProgressList.style.cssText = 'display:flex;flex-direction:column;gap:8px;margin-bottom:16px;';
  progressBody.appendChild(inProgressList);

  // Waiting section
  const waitingHeader = document.createElement('div');
  waitingHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;';
  const waitingLabel = document.createElement('span');
  waitingLabel.style.cssText = 'font-size:12px;font-weight:500;color:var(--text-secondary);';
  waitingLabel.textContent = 'Waiting';
  const waitingBadge = document.createElement('span');
  waitingBadge.style.cssText = 'font-size:11px;color:var(--text-muted);';
  waitingBadge.textContent = '0';
  waitingHeader.appendChild(waitingLabel);
  waitingHeader.appendChild(waitingBadge);
  progressBody.appendChild(waitingHeader);

  const waitingList = document.createElement('div');
  waitingList.style.cssText = 'display:flex;flex-direction:column;gap:8px;margin-bottom:16px;';
  progressBody.appendChild(waitingList);

  // Error log section
  const errorHeader = document.createElement('div');
  errorHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;';
  const errorLabel = document.createElement('span');
  errorLabel.style.cssText = 'font-size:12px;font-weight:500;color:var(--text-secondary);';
  errorLabel.textContent = 'Error log';
  const errorBadge = document.createElement('span');
  errorBadge.style.cssText = 'font-size:11px;color:#A32D2D;';
  errorBadge.textContent = '0';
  errorHeader.appendChild(errorLabel);
  errorHeader.appendChild(errorBadge);
  progressBody.appendChild(errorHeader);

  const errorLogBox = document.createElement('div');
  errorLogBox.style.cssText = 'display:flex;flex-direction:column;gap:4px;';
  progressBody.appendChild(errorLogBox);

  // Terminal area
  const termHeader = document.createElement('div');
  termHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-top:16px;margin-bottom:6px;';
  const termLabel = document.createElement('span');
  termLabel.style.cssText = 'font-size:12px;font-weight:500;color:var(--text-secondary);';
  termLabel.textContent = 'Program Log';
  const termCopyBtn = document.createElement('button');
  termCopyBtn.className = 'btn-ghost';
  termCopyBtn.style.cssText = 'border:none;background:none;font-size:11px;color:var(--text-muted);cursor:pointer;';
  termCopyBtn.textContent = 'Copy';
  termHeader.appendChild(termLabel);
  termHeader.appendChild(termCopyBtn);
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
  progressTrack.style.cssText = 'margin-top:12px;height:4px;background:var(--surface-1);border-radius:2px;overflow:hidden;';
  const progressFill = document.createElement('div');
  progressFill.className = 'progress-fill';
  progressFill.id = 'bar';
  progressFill.style.cssText = 'height:100%;width:0%;background:#8DC63F;transition:width 0.3s ease;';
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
          if (config.num_clips !== undefined) clipsInput.value = config.num_clips;
          if (config.portrait !== undefined) portraitToggle.input.checked = config.portrait;
          if (config.highlight_finder !== undefined) highlightToggle.input.checked = config.highlight_finder;
          if (config.add_captions !== undefined) {
            captionToggle.input.checked = config.add_captions;
            subtitleStyleItem.style.display = config.add_captions ? '' : 'none';
          }
          if (config.add_hook !== undefined) hookToggle.input.checked = config.add_hook;
          if (config.yt_title_maker !== undefined) titleToggle.input.checked = config.yt_title_maker;
          if (config.subtitle_style) subtitleStyleSelect.value = config.subtitle_style;
        }
      } catch (err) {}
    }
    loadDefaultConfig();
  }, 0);

  saveConfigBtn.addEventListener('click', async () => {
    const settings = {
      num_clips: parseInt(clipsInput.value, 10),
      portrait: portraitToggle.input.checked,
      highlight_finder: highlightToggle.input.checked,
      add_captions: captionToggle.input.checked,
      add_hook: hookToggle.input.checked,
      yt_title_maker: titleToggle.input.checked,
      subtitle_style: subtitleStyleSelect.value
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
      campaign: campSelect,
      start: startBtn,
      clips: clipsInput,
      clipMode: () => clipMode,
      subtitle: subtitleSelect,
      subtitleStyle: subtitleStyleSelect,
      portrait: portraitToggle.input,
      highlight: highlightToggle.input,
      captions: captionToggle.input,
      hook: hookToggle.input,
      ytTitle: titleToggle.input,
      highlightSub: highlightToggle.subEl,
      captionSub: captionToggle.subEl,
      hookSub: hookToggle.subEl,
      ytTitleSub: titleToggle.subEl,
      bar: progressFill,
      status: statusDiv,
      terminal,
      termLabel,
      termCopyBtn,
      stepPreparing,
      progressCount,
      inProgressList,
      inProgressBadge,
      waitingList,
      waitingBadge,
      errorLogBox,
      errorBadge,
    }
  };
};
