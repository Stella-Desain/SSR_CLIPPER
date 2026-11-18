window.Components = window.Components || {};

window.Components.HomeView = function () {
  const section = document.createElement('section');
  section.className = 'view entrance';
  section.dataset.view = 'create-clip';

  const pageHeader = document.createElement('div');
  pageHeader.style.marginBottom = '28px';
  pageHeader.innerHTML = '<h1 class="page-title">Create Clip</h1><p class="page-subtitle">Masukkan sumber video dan pilih campaign untuk mulai membuat clip.</p>';
  section.appendChild(pageHeader);

  const layout = document.createElement('div');
  layout.className = 'create-clip-layout has-progress';
  const inputs = document.createElement('div');
  inputs.className = 'card card-body create-clip-inputs';
  layout.appendChild(inputs);

  function inputGroup(title, target) {
    const group = document.createElement('div');
    group.className = 'create-clip-group';
    const label = document.createElement('label');
    label.className = 'field-label';
    label.htmlFor = target;
    label.textContent = title;
    group.appendChild(label);
    inputs.appendChild(group);
    return group;
  }

  const urlGroup = inputGroup('Sumber video', 'url');
  const urlRow = document.createElement('div');
  urlRow.className = 'create-clip-source-row';
  const urlInput = document.createElement('textarea');
  urlInput.rows = 4;
  urlInput.className = 'input';
  urlInput.id = 'url';
  urlInput.placeholder = 'Link YouTube atau file MP4, satu sumber per baris. File juga bisa diseret ke sini.';
  urlInput.setAttribute('aria-describedby', 'source-feedback');
  const pasteBtn = document.createElement('button');
  pasteBtn.className = 'btn btn-outline';
  pasteBtn.type = 'button';
  pasteBtn.textContent = 'Tempel';
  const sourceFeedback = document.createElement('p');
  sourceFeedback.id = 'source-feedback';
  sourceFeedback.className = 'create-clip-feedback';
  sourceFeedback.setAttribute('role', 'status');
  pasteBtn.addEventListener('click', async () => {
    if (urlInput.disabled) return;
    try {
      const value = await navigator.clipboard.readText();
      if (!urlInput.disabled) urlInput.value = value;
      sourceFeedback.textContent = '';
    } catch {
      sourceFeedback.textContent = 'Clipboard belum dapat dibaca. Tempel link langsung ke kolom sumber video.';
    }
  });
  urlRow.append(urlInput, pasteBtn);
  urlGroup.append(urlRow, sourceFeedback);

  const campGroup = inputGroup('Campaign', 'home-campaign-select');
  const campSelect = document.createElement('select');
  campSelect.className = 'select';
  campSelect.id = 'home-campaign-select';
  campSelect.innerHTML = '<option value="">Pilih campaign</option>';
  campGroup.appendChild(campSelect);

  const countGroup = inputGroup('Jumlah clip', 'clips');
  let clipMode = 'fixed';
  const clipModeRow = document.createElement('div');
  clipModeRow.className = 'create-clip-mode';
  clipModeRow.setAttribute('role', 'group');
  clipModeRow.setAttribute('aria-label', 'Cara menentukan jumlah clip');
  const btnFixed = document.createElement('button');
  btnFixed.className = 'btn btn-outline';
  btnFixed.textContent = 'Tentukan jumlah';
  btnFixed.type = 'button';
  const btnAI = document.createElement('button');
  btnAI.className = 'btn btn-outline';
  btnAI.textContent = 'AI menentukan';
  btnAI.type = 'button';
  clipModeRow.append(btnFixed, btnAI);
  const clipsInput = document.createElement('input');
  clipsInput.type = 'number';
  clipsInput.min = '1';
  clipsInput.max = '100';
  clipsInput.step = '1';
  clipsInput.value = '5';
  clipsInput.className = 'input';
  clipsInput.id = 'clips';
  const clipModeHint = document.createElement('p');
  clipModeHint.className = 'create-clip-feedback';
  clipModeHint.id = 'clip-count-hint';
  clipModeHint.setAttribute('role', 'status');
  clipsInput.setAttribute('aria-describedby', clipModeHint.id);
  function setClipMode(mode) {
    clipMode = mode;
    btnFixed.setAttribute('aria-pressed', String(mode === 'fixed'));
    btnAI.setAttribute('aria-pressed', String(mode === 'ai'));
    clipsInput.hidden = mode === 'ai';
    clipModeHint.textContent = mode === 'ai'
      ? 'Jumlah clip mengikuti highlight yang memenuhi kualitas campaign.'
      : 'Jumlah yang ingin dibuat dari setiap sumber video.';
  }
  btnFixed.addEventListener('click', () => setClipMode('fixed'));
  btnAI.addEventListener('click', () => setClipMode('ai'));
  setClipMode('fixed');
  countGroup.append(clipModeRow, clipsInput, clipModeHint);

  const cookieSection = inputGroup('Cookie', 'cookies-btn');
  const cookiesBtn = document.createElement('button');
  cookiesBtn.id = 'cookies-btn';
  cookiesBtn.className = 'btn btn-outline';
  cookiesBtn.type = 'button';
  cookiesBtn.textContent = 'Pilih file cookies.txt';
  const cookieStatus = document.createElement('p');
  cookieStatus.className = 'create-clip-feedback';
  cookieStatus.setAttribute('role', 'status');
  cookieStatus.textContent = 'Opsional untuk sumber yang membutuhkan login. Cookie tersimpan akan digunakan kembali.';
  cookieSection.append(cookiesBtn, cookieStatus);
  let cookiesBusy = false;
  cookiesBtn.addEventListener('click', async () => {
    if (cookiesBusy) return;
    cookiesBusy = true;
    cookiesBtn.disabled = true;
    try {
      const result = await window.pywebview.api.upload_cookies();
      if (result.status === 'ok') cookieStatus.textContent = 'Cookie tersimpan dan siap digunakan.';
      else if (result.status === 'error') cookieStatus.textContent = result.message || 'Cookie belum dapat disimpan.';
    } catch (error) {
      cookieStatus.textContent = 'Cookie belum dapat diunggah: ' + String(error);
    } finally {
      cookiesBusy = false;
      cookiesBtn.disabled = inputs.dataset.locked === 'true';
    }
  });

  const formError = document.createElement('p');
  formError.className = 'create-clip-feedback wf-error';
  formError.setAttribute('role', 'alert');
  inputs.appendChild(formError);
  const startBtn = document.createElement('button');
  startBtn.className = 'btn btn-lime-full create-clip-submit';
  startBtn.id = 'start';
  startBtn.type = 'button';
  startBtn.textContent = 'Create Clip';
  inputs.appendChild(startBtn);

  const jobsPanel = document.createElement('section');
  jobsPanel.className = 'create-clip-progress create-clip-jobs';
  jobsPanel.setAttribute('aria-label', 'Pekerjaan video');
  const jobsHeader = document.createElement('div');
  jobsHeader.className = 'wf-header';
  const jobsHeading = document.createElement('h2');
  jobsHeading.className = 'card-title';
  jobsHeading.textContent = 'Pekerjaan video';
  const refreshJobsBtn = document.createElement('button');
  refreshJobsBtn.className = 'btn btn-outline';
  refreshJobsBtn.type = 'button';
  refreshJobsBtn.textContent = 'Perbarui';
  jobsHeader.append(jobsHeading, refreshJobsBtn);
  const jobsFeedback = document.createElement('p');
  jobsFeedback.className = 'create-job-feedback';
  jobsFeedback.setAttribute('role', 'status');
  const jobsList = document.createElement('div');
  jobsList.className = 'create-job-list';
  const jobsEmpty = document.createElement('p');
  jobsEmpty.className = 'wf-empty';
  jobsEmpty.textContent = 'Belum ada pekerjaan. Setiap sumber video akan menjadi satu pekerjaan.';
  const progressPanel = document.createElement('section');
  progressPanel.className = 'create-job-details';
  progressPanel.id = 'create-job-details';
  progressPanel.hidden = true;
  const selectedTitle = document.createElement('h3');
  selectedTitle.className = 'create-job-detail-header';
  selectedTitle.id = 'selected-job-title';
  const selectedMeta = document.createElement('p');
  selectedMeta.className = 'create-job-row-meta';
  const selectedCounts = document.createElement('p');
  selectedCounts.className = 'create-job-counts';
  progressPanel.setAttribute('aria-labelledby', selectedTitle.id);
  progressPanel.append(selectedTitle, selectedMeta, selectedCounts);
  jobsPanel.append(jobsHeader, jobsFeedback, jobsList, jobsEmpty, progressPanel);
  layout.appendChild(jobsPanel);
  section.appendChild(layout);

  const progressCard = document.createElement('div');
  progressCard.className = 'card';
  progressCard.style.cssText = 'flex:1;display:flex;flex-direction:column;background:var(--surface-2);border:0.5px solid var(--border);border-radius:12px;padding:1rem 1.25rem;';

  const progressHeader = document.createElement('div');
  progressHeader.style.cssText = 'display:flex;justify-content:space-between;align-items:center;margin-bottom:14px;';
  const progressCount = document.createElement('span');
  progressCount.id = 'progress-count';
  progressCount.style.cssText = 'font-size:20px;font-weight:500;color:var(--text-primary);';
  progressCount.textContent = '0/0';
  progressHeader.innerHTML = '<h4 style="margin:0;font-size:16px;font-weight:600;">Progress pekerjaan</h4>';
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
  progressPanel.appendChild(progressCard);

  const openStockBtn = document.createElement('button');
  openStockBtn.className = 'btn btn-lime-full';
  openStockBtn.textContent = 'Open Clip Stock';
  openStockBtn.addEventListener('click', () => setActiveView('stock-clip'));
  progressPanel.appendChild(openStockBtn);

  return {
    element: section,
    fields: {
      url: urlInput,
      campaign: campSelect,
      start: startBtn,
      clips: clipsInput,
      clipMode: () => clipMode,
      sourceFeedback,
      formError,
      sourceActions: urlGroup,
      jobsList,
      jobsEmpty,
      jobsFeedback,
      refreshJobsBtn,
      selectedTitle,
      selectedMeta,
      selectedCounts,
      progressPanel,
      setLocked: (locked) => {
        inputs.dataset.locked = String(locked);
        inputs.querySelectorAll('input, textarea, select, button').forEach(control => {
          control.disabled = locked || (control === cookiesBtn && cookiesBusy);
        });
      },
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
