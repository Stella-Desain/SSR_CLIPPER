/* ═══════════════════════════════════════
   Clipper - App Shell
   ═══════════════════════════════════════ */

const GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta/openai/';

const root = document.getElementById('app');
const shell = document.createElement('div');
shell.className = 'shell';
root.appendChild(shell);

// ── Build Shell: Sidebar + Main ──
const shellComp = window.Components.Shell();
shell.appendChild(shellComp.sidebar);

const mainWrapper = document.createElement('div');
mainWrapper.className = 'main-wrapper';
mainWrapper.appendChild(shellComp.topHeader);

const pageContent = document.createElement('div');
pageContent.className = 'page-content';
mainWrapper.appendChild(pageContent);
shell.appendChild(mainWrapper);

// ── Build Views ──
const dashboardView = window.Components.DashboardView();
const campaignListView = window.Components.CampaignListView();
const campaignEditView = window.Components.CampaignEditView();
const homeView = window.Components.HomeView();
const stockClipView = window.Components.StockClipView();
const aiView = window.Components.AiSettingsView();
const templateEditorView = window.Components.TemplateEditorView();

pageContent.appendChild(dashboardView.element);
pageContent.appendChild(campaignListView.element);
pageContent.appendChild(campaignEditView.element);
pageContent.appendChild(homeView.element);
pageContent.appendChild(stockClipView.element);
pageContent.appendChild(aiView.element);
pageContent.appendChild(templateEditorView.element);

const allViews = [dashboardView.element, campaignListView.element, campaignEditView.element, homeView.element, stockClipView.element, aiView.element, templateEditorView.element];
const navItems = shellComp.navItems;

// ── State ──
let providerType = 'ytclip';

// ── Navigation ──
function setActiveView(name) {
  allViews.forEach(v => v.classList.toggle('active', v.dataset.view === name));
  navItems.forEach(n => n.classList.toggle('active', n.dataset.view === name));
  // Scroll to top
  pageContent.scrollTop = 0;
  
  // Refresh data if view has a refresh method
  if (name === 'dashboard' && dashboardView.refresh) dashboardView.refresh();
  if (name === 'stock-clip' && stockClipView.refresh) stockClipView.refresh();
  if (name === 'editor' && templateEditorView.refresh) templateEditorView.refresh();
  else if (templateEditorView.pause) templateEditorView.pause();
  if (name === 'create-clip' && homeView.refresh) homeView.refresh();
  else if (homeView.pause) homeView.pause();
}

navItems.forEach(item => {
  item.addEventListener('click', () => {
    const view = item.dataset.view;
    if (view === 'credit') return; // Not implemented yet
    setActiveView(view);
  });
});

// ── API Helpers ──
function waitForApi() {
  return new Promise((resolve) => {
    if (window.pywebview && window.pywebview.api) {
      resolve();
      return;
    }
    let tries = 0;
    const timer = setInterval(() => {
      tries += 1;
      if (window.pywebview && window.pywebview.api) {
        clearInterval(timer);
        resolve();
      } else if (tries > 50) {
        clearInterval(timer);
        resolve();
      }
    }, 100);
  });
}

// ── Provider Management ──
function setProviderType(type, applyBaseUrl) {
  providerType = type;
  aiView.fields.providerButtons.forEach(btn => {
    const isActive = btn.dataset.provider === type;
    btn.style.background = isActive ? 'var(--lime)' : 'var(--card)';
    btn.style.color = isActive ? 'var(--text-on-lime)' : 'var(--text)';
    btn.style.borderColor = isActive ? 'var(--lime)' : 'var(--border)';
    btn.style.fontWeight = isActive ? '700' : '500';
  });

  const showCustom = type === 'custom';
  document.querySelectorAll('.url-field').forEach(el => {
    el.classList.toggle('hidden', !showCustom);
  });

  if (applyBaseUrl && !showCustom) {
    const baseUrl = type === 'ytclip' ? 'https://ai-api.ytclip.org/v1' : 'https://api.openai.com/v1';
    // Only update hfUrl — hmUrl (Gemini) has its own fixed endpoint
    aiView.fields.hfUrl.value = baseUrl;
    aiView.fields.hmUrl.value = 'https://generativelanguage.googleapis.com/v1beta/openai/';
  }
}

function setSelectOptions(select, models, preferred) {
  if (!select) return;
  select.innerHTML = '';
  
  function shortName(m) {
    if (!m) return '';
    const parts = m.split('/');
    return parts[parts.length - 1] || m;
  }

  if (!models || models.length === 0) {
    const opt = document.createElement('option');
    opt.value = preferred || '';
    opt.textContent = preferred ? shortName(preferred) : 'No models';
    select.appendChild(opt);
    return;
  }
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m;
    opt.textContent = shortName(m);
    select.appendChild(opt);
  });
  if (preferred && models.includes(preferred)) {
    select.value = preferred;
  }
}

// ── Create Clip: queued jobs and per-source progress ──
let createEnqueuePending = false;
let createJobsTimer = null;
let createJobsRequest = null;
let createJobs = [];
let selectedCreateJob = null;
const createJobRows = new Map();
const createJobLabels = {
  queued:'Antrean', running:'Berjalan', completed:'Selesai', partial:'Sebagian gagal',
  failed:'Gagal', interrupted:'Terhenti', cancelled:'Dibatalkan', cancelling:'Membatalkan', paused:'Dijeda',
};
const createNode = (tag, text, className) => {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
};
function createJobsVisible() {
  return homeView.element.classList.contains('active') && !document.hidden;
}
function createJobTitle(job) {
  return job.title || job.source_title || String(job.source || '').split(/[\\/]/).filter(Boolean).pop() || 'Sumber video';
}
function createJobCounts(job) {
  const clips = Array.isArray(job.clips) ? job.clips : [];
  const counts = job.counts || {};
  return {
    planned: counts.planned ?? clips.length,
    completed: counts.completed ?? clips.filter(clip => clip.status === 'done').length,
    failed: counts.failed ?? clips.filter(clip => clip.status === 'error').length,
    cancelled: counts.cancelled ?? clips.filter(clip => clip.status === 'cancelled').length,
    requested: counts.requested ?? (job.options?.clip_mode === 'ai' ? null : job.options?.num_clips),
  };
}
function createJobCountLabel(job) {
  const counts = createJobCounts(job);
  if (counts.planned > 0) return `${counts.completed}/${counts.planned} clip selesai`;
  if (job.status === 'queued') return counts.requested ? `Target ${counts.requested} clip` : 'Jumlah ditentukan AI';
  if (job.status === 'running') return 'Menganalisis sumber';
  return `${counts.completed} clip selesai`;
}
function selectCreateJob(id) {
  selectedCreateJob = selectedCreateJob === id ? null : id;
  renderCreateJobs();
}
function renderCreateJobs() {
  const fields = homeView.fields;
  const ids = new Set(createJobs.map(job => job.id));
  for (const [id, row] of createJobRows) {
    if (!ids.has(id)) { row.button.remove(); createJobRows.delete(id); }
  }
  fields.jobsEmpty.hidden = createJobs.length > 0;
  for (const [position, job] of createJobs.entries()) {
    let row = createJobRows.get(job.id);
    if (!row) {
      const button = createNode('button', undefined, 'create-job-row');
      button.type = 'button';
      button.setAttribute('aria-controls', 'create-job-details');
      const info = createNode('span', undefined, 'create-job-row-info');
      const title = createNode('strong');
      const meta = createNode('span', undefined, 'create-job-row-meta');
      const status = createNode('span');
      info.append(title, meta);
      button.append(info, status);
      button.addEventListener('click', () => selectCreateJob(job.id));
      row = {button, title, meta, status};
      createJobRows.set(job.id, row);
      fields.jobsList.appendChild(button);
    }
    if (fields.jobsList.children[position] !== row.button) {
      fields.jobsList.insertBefore(row.button, fields.jobsList.children[position] || null);
    }
    row.title.textContent = createJobTitle(job);
    row.meta.textContent = `${job.campaign?.name || job.campaign_id || 'Campaign'} · ${createJobCountLabel(job)}`;
    row.status.className = 'wf-badge wf-' + job.status;
    row.status.textContent = (createJobLabels[job.status] || job.status) + (job.queue_position ? ` #${job.queue_position}` : '');
    row.button.setAttribute('aria-expanded', String(job.id === selectedCreateJob));
  }
  const selected = createJobs.find(job => job.id === selectedCreateJob);
  fields.progressPanel.hidden = !selected;
  if (selected) renderCreateJobDetails(selected);
}
function renderCreateClip(clip) {
  const card = createNode('div', undefined, 'create-job-clip');
  card.append(createNode('strong', clip.title || `Clip ${clip.index || ''}`));
  const states = {waiting:'Menunggu', queued:'Menunggu', running:'Berjalan', processing:'Berjalan', done:'Selesai', error:'Gagal', cancelled:'Dibatalkan'};
  card.append(createNode('p', clip.error || clip.step || states[clip.status] || clip.status));
  if (!['done','error','cancelled','waiting','queued'].includes(clip.status) && Number.isFinite(clip.step_progress)) {
    const meter = createNode('progress');
    meter.max = 1;
    meter.value = Math.max(0, Math.min(1, clip.step_progress));
    meter.setAttribute('aria-label', `Progress ${clip.title || 'clip'}`);
    card.appendChild(meter);
  }
  return card;
}
function renderCreateJobDetails(job) {
  const fields = homeView.fields;
  const clips = Array.isArray(job.clips) ? job.clips : [];
  const counts = createJobCounts(job);
  fields.selectedTitle.textContent = createJobTitle(job);
  fields.selectedMeta.textContent = `${job.campaign?.name || job.campaign_id || 'Campaign'} · ${createJobLabels[job.status] || job.status}`;
  fields.selectedCounts.textContent = [createJobCountLabel(job), counts.failed ? `${counts.failed} gagal` : '', counts.cancelled ? `${counts.cancelled} dibatalkan` : ''].filter(Boolean).join(' · ');
  fields.progressCount.textContent = counts.planned ? `${counts.completed}/${counts.planned}` : '—';
  const progress = Number(job.progress);
  fields.bar.style.width = `${Math.round((Number.isFinite(progress) ? Math.max(0, Math.min(1, progress)) : 0) * 100)}%`;
  fields.status.textContent = job.error || job.step || (job.queue_position ? `Menunggu giliran #${job.queue_position}` : createJobLabels[job.status]) || '';
  const preparing = fields.stepPreparing.querySelector('.step-status');
  if (preparing) {
    const done = clips.length > 0 || job.status === 'completed';
    preparing.className = 'step-status ' + (done ? 'complete' : job.status === 'running' ? 'ongoing' : ['failed','interrupted'].includes(job.status) ? 'failed' : '');
    preparing.textContent = done ? 'Selesai' : job.status === 'running' ? 'Berjalan' : ['failed','interrupted'].includes(job.status) ? 'Terhenti' : 'Menunggu';
  }
  const waiting = clips.filter(clip => ['waiting','queued'].includes(clip.status));
  const running = clips.filter(clip => !['waiting','queued','done','error','cancelled'].includes(clip.status));
  const errors = clips.filter(clip => clip.status === 'error');
  fields.inProgressList.replaceChildren(...running.map(renderCreateClip));
  fields.waitingList.replaceChildren(...waiting.map(renderCreateClip));
  fields.errorLogBox.replaceChildren(...errors.map(renderCreateClip));
  if (job.error && !errors.some(clip => clip.error === job.error)) fields.errorLogBox.append(createNode('p', job.error, 'wf-error'));
  fields.inProgressBadge.textContent = String(running.length);
  fields.waitingBadge.textContent = String(waiting.length);
  fields.errorBadge.textContent = String(errors.length || (job.error ? 1 : 0));
  fields.termLabel.textContent = 'Log pekerjaan';
  const logs = Array.isArray(job.logs) ? job.logs : [];
  const logText = logs.map(entry => typeof entry === 'string' ? entry : [entry.timestamp, entry.message].filter(Boolean).join(' · ')).join('\n');
  const terminalText = logText || job.error || job.step || (job.status === 'queued' ? 'Pekerjaan menunggu giliran.' : 'Belum ada log tersimpan untuk pekerjaan ini.');
  if (fields.terminal.textContent !== terminalText) {
    const nearBottom = fields.terminal.scrollHeight - fields.terminal.scrollTop - fields.terminal.clientHeight < 32;
    fields.terminal.textContent = terminalText;
    if (nearBottom) fields.terminal.scrollTop = fields.terminal.scrollHeight;
  }
}
async function refreshCreateJobs() {
  if (createJobsRequest) return createJobsRequest;
  clearTimeout(createJobsTimer);
  if (!window.pywebview?.api) return;
  homeView.fields.refreshJobsBtn.disabled = true;
  createJobsRequest = Promise.resolve().then(async () => {
    try {
      const result = await window.pywebview.api.get_workflow_jobs();
      if (result.status !== 'ok') throw Error(result.message || 'Pekerjaan belum dapat dimuat.');
      createJobs = Array.isArray(result.jobs) ? result.jobs : [];
      homeView.fields.jobsFeedback.textContent = result.worker_note || '';
      homeView.fields.jobsFeedback.classList.remove('wf-error');
      renderCreateJobs();
    } catch (error) {
      homeView.fields.jobsFeedback.textContent = 'Pekerjaan belum dapat diperbarui: ' + String(error);
      homeView.fields.jobsFeedback.classList.add('wf-error');
    } finally {
      createJobsRequest = null;
      homeView.fields.refreshJobsBtn.disabled = false;
      if (createJobsVisible()) createJobsTimer = setTimeout(refreshCreateJobs, 2000);
    }
  });
  return createJobsRequest;
}
async function start() {
  if (createEnqueuePending) return;
  const fields = homeView.fields;
  const source = fields.url.value.trim();
  const campaignId = fields.campaign.value;
  const clipMode = fields.clipMode();
  const clipCount = Number(fields.clips.value);
  fields.formError.textContent = '';
  if (!source) {
    fields.formError.textContent = 'Masukkan link atau pilih file video terlebih dahulu.';
    fields.url.focus();
    return;
  }
  if (!campaignId) {
    fields.formError.textContent = 'Pilih campaign untuk menggunakan template editing-nya.';
    fields.campaign.focus();
    return;
  }
  if (clipMode === 'fixed' && (!Number.isSafeInteger(clipCount) || clipCount < 1 || clipCount > 100)) {
    fields.formError.textContent = 'Jumlah clip harus berupa bilangan bulat antara 1 dan 100.';
    fields.clips.focus();
    return;
  }
  createEnqueuePending = true;
  fields.setLocked(true);
  fields.start.textContent = 'Menambahkan pekerjaan…';
  try {
    const result = await window.pywebview.api.enqueue_sources(
      source.split(/\r?\n/).map(value => value.trim()).filter(Boolean),
      campaignId,
      {num_clips:clipMode === 'ai' ? 0 : clipCount, clip_mode:clipMode}
    );
    if (result?.status !== 'started') throw Error(result?.message || 'Pekerjaan belum dapat ditambahkan.');
    fields.url.value = '';
    fields.sourceFeedback.textContent = `${result.jobs?.length || 1} pekerjaan ditambahkan. Anda dapat menambahkan sumber berikutnya.`;
  } catch (error) {
    fields.formError.textContent = String(error);
  } finally {
    createEnqueuePending = false;
    fields.setLocked(false);
    fields.start.textContent = 'Create Clip';
  }
  // Wait for any older snapshot before fetching the newly added job list.
  if (createJobsRequest) await createJobsRequest;
  await refreshCreateJobs();
}
homeView.fields.start.addEventListener('click', start);
homeView.fields.refreshJobsBtn.addEventListener('click', refreshCreateJobs);
homeView.refresh = refreshCreateJobs;
homeView.pause = () => clearTimeout(createJobsTimer);
document.addEventListener('visibilitychange', () => {
  if (createJobsVisible()) refreshCreateJobs();
  else homeView.pause();
});
homeView.fields.termCopyBtn.addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(homeView.fields.terminal.textContent || '');
    homeView.fields.termCopyBtn.textContent = 'Tersalin';
    setTimeout(() => { homeView.fields.termCopyBtn.textContent = 'Copy'; }, 1500);
  } catch {
    homeView.fields.jobsFeedback.textContent = 'Log belum dapat disalin ke clipboard.';
  }
});

// ── Install All Button ──
const installBtn = aiView.element.querySelector('.btn-lime');
if (installBtn) {
  installBtn.addEventListener('click', async () => {
    if (installBtn.disabled) return;
    dependencyInstallAllPending = true;
    installBtn.disabled = true;
    installBtn.textContent = 'Starting...';
    try {
      const result = await window.pywebview.api.install_dependencies();
      if (result.status === 'error') throw new Error(result.message || 'Installation failed');
      dependencyFeedback('');
    } catch (error) {
      dependencyFeedback(error.message || String(error));
    } finally {
      dependencyInstallAllPending = false;
      await loadDepStatus();
      scheduleDependencyPoll();
    }
  });
}

// ── Save AI Settings ──
async function persistAiSettings() {
  // Use Custom Provider as fallback for empty keys to enable a "Global Provider" workflow
  const cpUrl = aiView.fields.cpUrl ? aiView.fields.cpUrl.value.trim() : "";
  const cpKey = aiView.fields.cpKey ? aiView.fields.cpKey.value.trim() : "";

  const getUrl = (field, defaultUrl) => {
      const val = field ? field.value.trim() : "";
      return val ? val : (cpUrl || defaultUrl);
  };
  const getKey = (field) => {
      const val = field ? field.value.trim() : "";
      return val ? val : cpKey;
  };

  const getSmartPayload = (defaultUrlField, defaultKeyField, modelField) => {
      let model = modelField ? modelField.value.trim() : "";
      
      let targetUrl = getUrl(defaultUrlField, 'https://api.openai.com/v1');
      let targetKey = getKey(defaultKeyField);
      
      if (model.startsWith("[OpenAI] ")) {
          model = model.replace("[OpenAI] ", "");
          targetUrl = aiView.fields.hfUrl ? aiView.fields.hfUrl.value.trim() : targetUrl;
          targetKey = aiView.fields.hfKey ? aiView.fields.hfKey.value.trim() : targetKey;
      } else if (model.startsWith("[Gemini] ")) {
          model = model.replace("[Gemini] ", "");
          targetUrl = GEMINI_BASE_URL;
          targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : targetKey;
      } else if (model.startsWith("[Custom1] ")) {
          model = model.replace("[Custom1] ", "");
          targetUrl = aiView.fields.cmUrl ? aiView.fields.cmUrl.value.trim() : targetUrl;
          targetKey = aiView.fields.cmKey ? aiView.fields.cmKey.value.trim() : targetKey;
      } else if (model.startsWith("[Custom2] ")) {
          model = model.replace("[Custom2] ", "");
          targetUrl = aiView.fields.cpUrl ? aiView.fields.cpUrl.value.trim() : targetUrl;
          targetKey = aiView.fields.cpKey ? aiView.fields.cpKey.value.trim() : targetKey;
      } else if (model.startsWith("[Custom3] ")) {
          model = model.replace("[Custom3] ", "");
          targetUrl = aiView.fields.c3Url ? aiView.fields.c3Url.value.trim() : targetUrl;
          targetKey = aiView.fields.c3Key ? aiView.fields.c3Key.value.trim() : targetKey;
      } else if (model.startsWith("[Local] ")) {
          model = model.replace("[Local] ", "");
          // Keep targetUrl and targetKey unchanged so we don't corrupt the saved API credentials
      } else {
          // Backward compatibility: Auto-route to Gemini if it's a Gemini model AND no prefix
          const lowerModel = model.toLowerCase();
          if (lowerModel.includes("gemini") && aiView.fields.hmKey && aiView.fields.hmKey.value.trim() !== "") {
              targetUrl = 'https://generativelanguage.googleapis.com/v1beta/openai/';
              targetKey = aiView.fields.hmKey.value.trim();
          }
      }
      
      return {
          base_url: targetUrl,
          api_key: targetKey,
          model: model,
          ...(model.toLowerCase().includes('codex')?{reasoning_effort:'xhigh'}:{})
      };
  };

  const captionMakerPayload = getSmartPayload(aiView.fields.cmUrl, aiView.fields.cmKey, aiView.fields.cmModel);
  
  // If the user selected a local whisper model in Caption Maker, map it to whisper_model
  const localSizes = ['large-v3-turbo', 'medium'];
  let finalWhisperModel = aiView.fields.whisperModel ? aiView.fields.whisperModel.value : "api";
  
  if (localSizes.includes(captionMakerPayload.model)) {
      finalWhisperModel = captionMakerPayload.model;
      // Do not sync the header dropdown visually, because that dropdown is for installation picking only!
  } else {
      finalWhisperModel = "api";
  }

  const payload = {
    _provider_type: "custom",
    provider_type: "custom",
    highlight_finder: getSmartPayload(aiView.fields.hfUrl, aiView.fields.hfKey, aiView.fields.hfModel),
    music_analyzer: getSmartPayload(null, null, aiView.fields.maModel),
    caption_maker: captionMakerPayload,
    hook_maker: getSmartPayload(aiView.fields.hmUrl, aiView.fields.hmKey, aiView.fields.hmModel),
    brief_extractor: getSmartPayload(aiView.fields.c3Url, aiView.fields.c3Key, aiView.fields.beModel),
    custom_provider: {
      base_url: cpUrl,
      api_key: cpKey
    },
    custom_provider_3: {
      base_url: aiView.fields.c3Url ? aiView.fields.c3Url.value.trim() : "",
      api_key: aiView.fields.c3Key ? aiView.fields.c3Key.value.trim() : ""
    },
    yt_title_maker: getSmartPayload(null, null, aiView.fields.ytModel),
    whisper_model: finalWhisperModel,
    repliz: {
      access_key: aiView.fields.replizAccessKey ? aiView.fields.replizAccessKey.value.trim() : "",
      secret_key: aiView.fields.replizSecretKey ? aiView.fields.replizSecretKey.value.trim() : ""
    }
  };
  
  const wmPayload = {
    enabled: aiView.fields.wmEnableCheck ? aiView.fields.wmEnableCheck.checked : false,
    image_path: aiView.fields.wmImagePath ? aiView.fields.wmImagePath.value : "",
    position_x: aiView.fields.wmPosX ? parseFloat(aiView.fields.wmPosX.value) : 0.85,
    position_y: aiView.fields.wmPosY ? parseFloat(aiView.fields.wmPosY.value) : 0.05,
    opacity: aiView.fields.wmOpacity ? parseFloat(aiView.fields.wmOpacity.value) : 0.8,
    scale: aiView.fields.wmScale ? parseFloat(aiView.fields.wmScale.value) : 0.15
  };
  const cwPayload = {
    enabled: aiView.fields.cwEnableCheck ? aiView.fields.cwEnableCheck.checked : false,
    position_x: aiView.fields.cwPosX ? parseFloat(aiView.fields.cwPosX.value) : 0.5,
    position_y: aiView.fields.cwPosY ? parseFloat(aiView.fields.cwPosY.value) : 0.95,
    size: aiView.fields.cwSize ? parseFloat(aiView.fields.cwSize.value) : 0.03,
    opacity: aiView.fields.cwOpacity ? parseFloat(aiView.fields.cwOpacity.value) : 0.7
  };
  const hsPayload = {
    font_name: aiView.fields.hsFontSelect ? aiView.fields.hsFontSelect.value : "Arial",
    font_size: aiView.fields.hsFontSize ? parseFloat(aiView.fields.hsFontSize.value) : 0.054,
    font_color: aiView.fields.hsFontColor ? aiView.fields.hsFontColor.value : "#FFD700",
    bg_color: aiView.fields.hsBgColor ? aiView.fields.hsBgColor.value : "#FFFFFF",
    corner_radius: aiView.fields.hsCorner ? parseInt(aiView.fields.hsCorner.value) : 0,
    position_x: aiView.fields.hsPosX ? parseFloat(aiView.fields.hsPosX.value) : 0.5,
    position_y: aiView.fields.hsPosY ? parseFloat(aiView.fields.hsPosY.value) : 0.333
  };
  const ftPayload = {
    face_tracking_mode: (aiView.fields.ftMediapipeRadio && aiView.fields.ftMediapipeRadio.checked) ? "mediapipe" : "opencv",
    gpu_enabled: aiView.fields.gaEnableCheck ? aiView.fields.gaEnableCheck.checked : false
  };
  const odPayload = {
    output_dir: aiView.fields.odPath ? aiView.fields.odPath.value : ""
  };
  aiView.fields.status.textContent = 'Saving...';
  try {
    const odPath = aiView.fields.odPath ? aiView.fields.odPath.value.trim() : '';
    const saveActions = [
      () => window.pywebview.api.save_ai_settings(payload),
      () => window.pywebview.api.save_watermark_settings(wmPayload),
      () => window.pywebview.api.save_credit_watermark_settings(cwPayload),
      () => window.pywebview.api.save_hook_style_settings(hsPayload),
      () => window.pywebview.api.save_face_tracking_settings(ftPayload),
    ];
    if(!aiView.fields.timezoneSelect.disabled)saveActions.push(async()=>{
      const result=await window.pywebview.api.save_scheduling_settings({timezone:aiView.fields.timezoneSelect.value});
      if(result.status==='ok')window.SSRTime.configure(result.timezone);
      return result;
    });
    // Only save output dir if user actually set a path
    if (odPath) saveActions.push(() => window.pywebview.api.save_output_dir_settings(odPayload));
    
    const results = [];
    for (const save of saveActions) results.push(await save());
    const allOk = results.every(r => r && (r.status === 'ok' || r.status === 'saved'));
    if (!allOk) {
      const errorMsg = results.map(r => r && r.message ? r.message : '').find(m => m) || 'Error saving some settings';
      aiView.fields.status.textContent = errorMsg;
    } else {
      aiView.fields.status.textContent = '\u2713 Saved successfully';
    }
  } catch (err) {
    aiView.fields.status.textContent = 'Error: ' + err.message;
  }
}
aiView.fields.saveBtn.addEventListener('click', persistAiSettings);

let aiAutoSaveTimeout = null;
aiView.element.addEventListener('input', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    clearTimeout(aiAutoSaveTimeout);
    aiAutoSaveTimeout = setTimeout(() => { persistAiSettings(); }, 800);
  }
});
aiView.element.addEventListener('change', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.type === 'checkbox' || e.target.type === 'radio') {
    persistAiSettings();
  }
});

// ── Provider Button Listeners ──
aiView.fields.providerButtons.forEach(btn => {
  btn.addEventListener('click', () => setProviderType(btn.dataset.provider, true));
});

// ── Validate & Load Models ──
async function validateAndLoad(kind) {
  const baseUrl = kind.url ? kind.url.value.trim() : "";
  const apiKey = kind.key ? kind.key.value.trim() : "";
  kind.status.textContent = 'Testing...';
  kind.status.style.color = 'var(--text-muted)';

  try {
      // 1. Fetch models from ALL configured providers
      let allModels = [];
      const providers = [
          { name: 'OpenAI', url: aiView.fields.hfUrl, key: aiView.fields.hfKey },
          { name: 'Gemini', url: { value: GEMINI_BASE_URL }, key: aiView.fields.hmKey },
          { name: 'Custom1', url: aiView.fields.cmUrl, key: aiView.fields.cmKey },
          { name: 'Custom2', url: aiView.fields.cpUrl, key: aiView.fields.cpKey },
          { name: 'Custom3', url: aiView.fields.c3Url, key: aiView.fields.c3Key }
      ];

      // Add local models
      allModels.push('[Local] large-v3-turbo');
      allModels.push('[Local] medium');

      let clickedValid = false;
      let ownModelCount = 0;
      let ownError = null;

      for (const p of providers) {
          if (p.url && p.url.value && p.key && p.key.value) {
              const isOwn = (baseUrl === p.url.value.trim() && apiKey === p.key.value.trim());
              try {
                  const pRes = await window.pywebview.api.get_models(p.url.value.trim(), p.key.value.trim());
                  if (pRes && pRes.models && pRes.models.length > 0) {
                      allModels = allModels.concat(pRes.models.map(m => `[${p.name}] ${m}`));
                      if (isOwn) {
                          clickedValid = true;
                          ownModelCount = pRes.models.length;
                      }
                  } else if (isOwn) {
                      ownError = (pRes && pRes.error) ? pRes.error : 'no models found';
                  }
              } catch (e) {
                  if (isOwn) ownError = String(e);
              }
          }
      }

      // Buang entry yang gak punya prefix provider valid (misal sisa data lama sebelum sistem prefix ada)
      const VALID_PREFIX_RE = /^\[(OpenAI|Gemini|Custom1|Custom2|Custom3|Local)\]\s/;
      allModels = allModels.filter(m => VALID_PREFIX_RE.test(m));

      // Buang duplikat exact-string (misal provider ngirim model ID yang sama 2x)
      allModels = [...new Set(allModels)];

      if (!apiKey) {
          kind.status.textContent = 'Empty';
          kind.status.style.color = 'var(--text-muted)';
      } else if (clickedValid) {
          kind.status.textContent = `Valid, ${ownModelCount} model loaded`;
          kind.status.style.color = 'var(--success)';
      } else if (ownError) {
          kind.status.textContent = `Error ${ownError}`;
          kind.status.style.color = 'var(--error)';
      } else if (allModels.length > 0) {
          kind.status.textContent = 'Other keys loaded';
          kind.status.style.color = 'var(--text-muted)';
      } else {
          kind.status.textContent = 'Error no models found';
          kind.status.style.color = 'var(--error)';
      }
      
      // Categorize models based on strict rules
      // Daftar model Gemini yang BENERAN audio-capable (sinkron dengan comment di app.py get_models())
      // NOTE: Jika backend nambah model Gemini audio-capable baru, tambahkan ke list ini!
      const GEMINI_AUDIO_MODELS = ['gemini-3.6-flash', 'gemini-3.5-flash', 'gemini-3.1-pro-preview'];
      
      const isTTS = (m) => {
          const lower = m.toLowerCase();
          return lower.includes('tts') || lower.endsWith('-tts');
      };
      
      const isSTT = (m) => {
          if (m.startsWith('[Local]')) return true;
          const lower = m.toLowerCase();
          if (lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio')) return true;
          // Gemini: hanya model yang secara eksplisit audio-capable DAN bukan TTS
          const bareName = m.replace(/^\[[^\]]+\]\s*/, ''); // buang prefix "[Custom1] " dll
          if (GEMINI_AUDIO_MODELS.includes(bareName) && !isTTS(m)) return true;
          return false;
      };
      
      const isChat = (m) => {
          if (m.startsWith('[Local]')) return false;
          if (isTTS(m)) return false;
          // Gemini audio-capable model tetap bisa dipakai chat juga, tapi model non-gemini-3
          // yang sudah kena isSTT (whisper/stt/-audio) TIDAK boleh dianggap chat
          const lower = m.toLowerCase();
          if ((lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio')) && !lower.includes('gemini')) {
              return false;
          }
          return true;
      };

      const hfModels = allModels.filter(isChat);
      if (aiView.fields.maModel) setSelectOptions(aiView.fields.maModel,
        allModels.filter(m=>!m.startsWith('[Local]')&&!isTTS(m)), aiView.fields.maModel.value);
      const cmModels = allModels.filter(isSTT);
      const hmModels = allModels.filter(isTTS);
      const ytModels = allModels.filter(isChat);

      if (aiView.fields.hfModel) {
        const pref = aiView.fields.hfModel.value;
        setSelectOptions(aiView.fields.hfModel, hfModels, pref);
      }
      if (aiView.fields.cmModel) {
        const pref = aiView.fields.cmModel.value;
        setSelectOptions(aiView.fields.cmModel, cmModels, pref);
      }
      if (aiView.fields.hmModel) {
        const pref = aiView.fields.hmModel.value;
        setSelectOptions(aiView.fields.hmModel, hmModels, pref);
      }
      if (aiView.fields.ytModel) {
        const pref = aiView.fields.ytModel.value;
        setSelectOptions(aiView.fields.ytModel, ytModels, pref);
      }
      // Brief Extractor model — pakai chat models, sama seperti hfModel/ytModel
      if (aiView.fields.beModel) {
        const pref = aiView.fields.beModel.value;
        setSelectOptions(aiView.fields.beModel, hfModels, pref);
      }
      
      if (aiView.fields.saveBtn) aiView.fields.saveBtn.click();
      
  } catch(e) {
      kind.status.textContent = 'Error: ' + e;
      kind.status.style.color = 'var(--error)';
  }
}


// ── Setup Provider Field Mappings ──

aiView.fields.hfValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.hfUrl,
  key: aiView.fields.hfKey,
  modelSelect: aiView.fields.hfModel,
  status: aiView.fields.hfValidateStatus
}));

aiView.fields.cmValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.cmUrl,
  key: aiView.fields.cmKey,
  modelSelect: aiView.fields.cmModel,
  status: aiView.fields.cmValidateStatus
}));

if (aiView.fields.hmValidateBtn) {
  aiView.fields.hmValidateBtn.addEventListener('click', () => validateAndLoad({
    url: { value: GEMINI_BASE_URL },
    key: aiView.fields.hmKey,
    modelSelect: aiView.fields.hmModel,
    status: aiView.fields.hmValidateStatus
  }));
}

if (aiView.fields.cpValidateBtn) {
  aiView.fields.cpValidateBtn.addEventListener('click', () => validateAndLoad({
    url: aiView.fields.cpUrl,
    key: aiView.fields.cpKey,
    modelSelect: aiView.fields.ytModel,
    status: aiView.fields.cpValidateStatus
  }));
}

if (aiView.fields.reloadModelBtn) {
    aiView.fields.reloadModelBtn.addEventListener('click', async () => {
        aiView.fields.reloadModelBtn.disabled = true;
        aiView.fields.reloadModelBtn.textContent = 'Reloading...';
        try {
            const res = await window.pywebview.api.reload_whisper_model();
            alert(res.message || 'Reload successful');
        } catch (e) {
            alert('Reload error: ' + e);
        }
        aiView.fields.reloadModelBtn.disabled = false;
        aiView.fields.reloadModelBtn.innerHTML = `
          <svg style="width:12px;height:12px;" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" stroke-linecap="round" stroke-linejoin="round"></path></svg>
          Reload Model
        `;
    });
}

// ── Test Model Readiness ──
function resolveModelPayloadForTest(modelField) {
  // Mirror logic dari getSmartPayload: prefix di value option nentuin base_url/key asli
  let model = modelField ? modelField.value.trim() : "";
  let targetUrl = "";
  let targetKey = "";
  let modelType = 'chat';

  if (model.startsWith("[OpenAI] ")) {
      model = model.replace("[OpenAI] ", "");
      targetUrl = aiView.fields.hfUrl ? aiView.fields.hfUrl.value.trim() : "";
      targetKey = aiView.fields.hfKey ? aiView.fields.hfKey.value.trim() : "";
  } else if (model.startsWith("[Gemini] ")) {
      model = model.replace("[Gemini] ", "");
      targetUrl = GEMINI_BASE_URL;
      targetKey = aiView.fields.hmKey ? aiView.fields.hmKey.value.trim() : "";
  } else if (model.startsWith("[Custom1] ")) {
      model = model.replace("[Custom1] ", "");
      targetUrl = aiView.fields.cmUrl ? aiView.fields.cmUrl.value.trim() : "";
      targetKey = aiView.fields.cmKey ? aiView.fields.cmKey.value.trim() : "";
  } else if (model.startsWith("[Custom2] ")) {
      model = model.replace("[Custom2] ", "");
      targetUrl = aiView.fields.cpUrl ? aiView.fields.cpUrl.value.trim() : "";
      targetKey = aiView.fields.cpKey ? aiView.fields.cpKey.value.trim() : "";
  } else if (model.startsWith("[Custom3] ")) {
      model = model.replace("[Custom3] ", "");
      targetUrl = aiView.fields.c3Url ? aiView.fields.c3Url.value.trim() : "";
      targetKey = aiView.fields.c3Key ? aiView.fields.c3Key.value.trim() : "";
  } else if (model.startsWith("[Local] ")) {
      model = model.replace("[Local] ", "");
      modelType = 'local';
      return { base_url: "", api_key: "", model, model_type: modelType };
  }

  // tentuin model_type berdasarkan nama model (pakai pola sama kayak isTTS/isSTT di validateAndLoad)
  const lower = model.toLowerCase();
  if (lower.includes('tts') || lower.endsWith('-tts')) modelType = 'tts';
  else if (lower.includes('whisper') || lower.includes('stt') || lower.endsWith('-audio')) modelType = 'stt';
  else modelType = 'chat';

  return { base_url: targetUrl, api_key: targetKey, model, model_type: modelType };
}

async function testModelReadiness(modelField, testBtn, statusSpan) {
  if (!modelField || !modelField.value || modelField.value.startsWith('Select Model')) {
      statusSpan.textContent = 'Empty';
      statusSpan.style.color = 'var(--error)';
      return;
  }
  testBtn.disabled = true;
  testBtn.textContent = 'Testing...';
  statusSpan.textContent = 'Testing...';
  statusSpan.style.color = 'var(--text-muted)';

  try {
      const payload = resolveModelPayloadForTest(modelField);
      const res = modelField===aiView.fields.maModel
        ? await window.pywebview.api.test_music_audio_model(payload)
        : await window.pywebview.api.test_model(payload.base_url, payload.api_key, payload.model, payload.model_type);
      if (res && res.status === 'ok') {
          statusSpan.textContent = res.message;
          statusSpan.style.color = 'var(--success)';
      } else {
          statusSpan.textContent = res ? res.message : 'Error unknown';
          statusSpan.style.color = 'var(--error)';
      }
  } catch (e) {
      statusSpan.textContent = 'Error: ' + e;
      statusSpan.style.color = 'var(--error)';
  }

  testBtn.disabled = false;
  testBtn.textContent = 'Test';
}

if (aiView.fields.hfModelTestBtn) {
  aiView.fields.hfModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.hfModel, aiView.fields.hfModelTestBtn, aiView.fields.hfModelStatus));
}
if (aiView.fields.cmModelTestBtn) {
  aiView.fields.cmModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.cmModel, aiView.fields.cmModelTestBtn, aiView.fields.cmModelStatus));
}
if (aiView.fields.hmModelTestBtn) {
  aiView.fields.hmModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.hmModel, aiView.fields.hmModelTestBtn, aiView.fields.hmModelStatus));
}
if (aiView.fields.ytModelTestBtn) {
  aiView.fields.ytModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.ytModel, aiView.fields.ytModelTestBtn, aiView.fields.ytModelStatus));
}
if (aiView.fields.beModelTestBtn) {
  aiView.fields.beModelTestBtn.addEventListener('click', () =>
    testModelReadiness(aiView.fields.beModel, aiView.fields.beModelTestBtn, aiView.fields.beModelStatus));
}
if (aiView.fields.maModelTestBtn) aiView.fields.maModelTestBtn.addEventListener('click',()=>
  testModelReadiness(aiView.fields.maModel,aiView.fields.maModelTestBtn,aiView.fields.maModelStatus));

async function loadReplizData() {
    try {
        if (!aiView.fields.accountsTitle) return;
        aiView.fields.accountsTitle.textContent = 'Loading Accounts...';
        const stats = await window.pywebview.api.get_account_stats();
        if (stats.error) {
             aiView.fields.accountsTitle.textContent = 'Failed to load accounts';
             if (aiView.fields.accountsList) aiView.fields.accountsList.innerHTML = '';
             return;
        }
        aiView.fields.accountsTitle.textContent = `${stats.campaigns} Account Connected`;

        if (aiView.fields.accountsList) {
            aiView.fields.accountsList.innerHTML = '';
            const res = await window.pywebview.api.get_repliz_accounts();
            if (res && res.status === 'ok' && res.accounts.length > 0) {
                res.accounts.forEach(acc => {
                    const row = document.createElement('div');
                    row.style.cssText = 'display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:#1A231A;border-radius:6px;';
                    row.innerHTML = `
                        <span style="font-size:13px;color:#E4E4E7;">${acc.name}</span>
                        <span style="font-size:11px;color:#A1A1AA;text-transform:capitalize;">${acc.type}</span>
                    `;
                    aiView.fields.accountsList.appendChild(row);
                });
            } else {
                aiView.fields.accountsList.innerHTML = '<div style="font-size:12px;color:#71717A;padding:8px 0;">No accounts connected yet.</div>';
            }
        }
    } catch (e) {
        if (aiView.fields.accountsTitle) aiView.fields.accountsTitle.textContent = 'Error loading accounts';
    }
}

if (aiView.fields.replizTestBtn) {
    aiView.fields.replizTestBtn.addEventListener('click', async () => {
        const ak = aiView.fields.replizAccessKey.value.trim();
        const sk = aiView.fields.replizSecretKey.value.trim();
        aiView.fields.replizStatus.textContent = 'Testing connection...';
        aiView.fields.replizStatus.style.color = '#A1A1AA';
        try {
            const res = await window.pywebview.api.test_repliz_connection(ak, sk);
            if (res.status === 'success') {
                aiView.fields.replizStatus.textContent = '✓ Connected successfully';
                aiView.fields.replizStatus.style.color = 'var(--success)';
                await persistAiSettings();
                loadReplizData();
            } else {
                aiView.fields.replizStatus.textContent = '✗ ' + (res.message || 'Connection failed');
                aiView.fields.replizStatus.style.color = 'var(--error)';
            }
        } catch(e) {
            aiView.fields.replizStatus.textContent = '✗ Error testing connection';
            aiView.fields.replizStatus.style.color = 'var(--error)';
        }
    });
}

// ── Init ──
async function init() {
  // ALWAYS show dashboard first — don't wait for API
  setProviderType(providerType, false);
  setActiveView('dashboard');

  await waitForApi();
  if (!window.pywebview || !window.pywebview.api) return;

  try{
    const time=await window.pywebview.api.get_scheduling_settings();
    if(time.status!=='ok')throw Error(time.message);
    window.SSRTime.configure(time.timezone);
    const select=aiView.fields.timezoneSelect;
    if(![...select.options].some(option=>option.value===time.timezone))select.add(new Option(time.timezone,time.timezone));
    select.value=time.timezone;select.disabled=false;
  }catch(error){aiView.fields.status.textContent='Zona waktu belum dimuat: '+error;}

  // Load AI settings
  try {
    const ai = await window.pywebview.api.get_ai_settings();
    const hf = (ai && ai.highlight_finder) || {};
    const cm = (ai && ai.caption_maker) || {};
    const hm = (ai && ai.hook_maker) || {};
    if (aiView.fields.hfUrl) aiView.fields.hfUrl.value = hf.base_url || '';
    if (aiView.fields.hfKey) aiView.fields.hfKey.value = hf.api_key || '';
    if (aiView.fields.hfModel) setSelectOptions(aiView.fields.hfModel, [hf.model].filter(Boolean), hf.model || '');
    if (aiView.fields.cmUrl) aiView.fields.cmUrl.value = cm.base_url || '';
    if (aiView.fields.cmKey) aiView.fields.cmKey.value = cm.api_key || '';
    if (aiView.fields.cmModel) setSelectOptions(aiView.fields.cmModel, [cm.model].filter(Boolean), cm.model || '');
    if (aiView.fields.hmUrl) aiView.fields.hmUrl.value = (hm.base_url && hm.base_url !== 'https://api.openai.com/v1') ? hm.base_url : 'https://generativelanguage.googleapis.com/v1beta/openai/';
    if (aiView.fields.hmKey) aiView.fields.hmKey.value = hm.api_key || '';
    if (aiView.fields.hmModel) setSelectOptions(aiView.fields.hmModel, [hm.model].filter(Boolean), hm.model || '');
    
    const cp = (ai && ai.custom_provider) || {};
    const ma = (ai && ai.music_analyzer) || {};
    const maName=ma.model || 'Visual-AI';
    const maDisplay=(!ma.base_url||ma.base_url===cp.base_url)?'[Custom2] '+maName:maName;
    if (aiView.fields.maModel) setSelectOptions(aiView.fields.maModel,[maDisplay],maDisplay);
    const c3 = (ai && ai.custom_provider_3) || {};
    const yt = (ai && ai.yt_title_maker) || {};
    const be = (ai && ai.brief_extractor) || {};
    const rep = (ai && ai.repliz) || {};
    if (aiView.fields.cpUrl) aiView.fields.cpUrl.value = cp.base_url || '';
    if (aiView.fields.cpKey) aiView.fields.cpKey.value = cp.api_key || '';
    if (aiView.fields.ytModel) setSelectOptions(aiView.fields.ytModel, [yt.model].filter(Boolean), yt.model || '');
    if (aiView.fields.c3Url) aiView.fields.c3Url.value = c3.base_url || '';
    if (aiView.fields.c3Key) aiView.fields.c3Key.value = c3.api_key || '';
    if (aiView.fields.beModel) setSelectOptions(aiView.fields.beModel, [be.model].filter(Boolean), be.model || '');
    // Removed: if (aiView.fields.whisperModel && ai.whisper_model) aiView.fields.whisperModel.value = ai.whisper_model;
    if (aiView.fields.replizAccessKey) aiView.fields.replizAccessKey.value = rep.access_key || '';
    if (aiView.fields.replizSecretKey) aiView.fields.replizSecretKey.value = rep.secret_key || '';

    
    // Load Watermark Settings
    const wm = await window.pywebview.api.get_watermark_settings();
    if (wm) {
        if (aiView.fields.wmEnableCheck) aiView.fields.wmEnableCheck.checked = !!wm.enabled;
        if (aiView.fields.wmImagePath) aiView.fields.wmImagePath.value = wm.image_path || '';
        if (aiView.fields.wmPosX) { aiView.fields.wmPosX.value = wm.position_x !== undefined ? wm.position_x : 0.85; aiView.fields.wmPosX.dispatchEvent(new Event('input')); }
        if (aiView.fields.wmPosY) { aiView.fields.wmPosY.value = wm.position_y !== undefined ? wm.position_y : 0.05; aiView.fields.wmPosY.dispatchEvent(new Event('input')); }
        if (aiView.fields.wmOpacity) { aiView.fields.wmOpacity.value = wm.opacity !== undefined ? wm.opacity : 0.8; aiView.fields.wmOpacity.dispatchEvent(new Event('input')); }
        if (aiView.fields.wmScale) { aiView.fields.wmScale.value = wm.scale !== undefined ? wm.scale : 0.15; aiView.fields.wmScale.dispatchEvent(new Event('input')); }
    }
    
    // Load Credit Watermark Settings
    const cw = await window.pywebview.api.get_credit_watermark_settings();
    if (cw) {
        if (aiView.fields.cwEnableCheck) aiView.fields.cwEnableCheck.checked = !!cw.enabled;
        if (aiView.fields.cwPosX) { aiView.fields.cwPosX.value = cw.position_x !== undefined ? cw.position_x : 0.5; aiView.fields.cwPosX.dispatchEvent(new Event('input')); }
        if (aiView.fields.cwPosY) { aiView.fields.cwPosY.value = cw.position_y !== undefined ? cw.position_y : 0.95; aiView.fields.cwPosY.dispatchEvent(new Event('input')); }
        if (aiView.fields.cwSize) { aiView.fields.cwSize.value = cw.size !== undefined ? cw.size : 0.03; aiView.fields.cwSize.dispatchEvent(new Event('input')); }
        if (aiView.fields.cwOpacity) { aiView.fields.cwOpacity.value = cw.opacity !== undefined ? cw.opacity : 0.7; aiView.fields.cwOpacity.dispatchEvent(new Event('input')); }
    }
    
    // Load Hook Style Settings
    const hs = await window.pywebview.api.get_hook_style_settings();
    const fontsRes = await window.pywebview.api.get_system_fonts();
    
    if (aiView.fields.hsFontSelect && fontsRes && fontsRes.status === 'ok') {
        const fonts = fontsRes.fonts || ["Arial"];
        setSelectOptions(aiView.fields.hsFontSelect, fonts, hs ? hs.font_name : "Arial");
    }

    if (hs) {
        if (aiView.fields.hsFontColor) aiView.fields.hsFontColor.value = hs.font_color || '#FFD700';
        if (aiView.fields.hsBgColor) aiView.fields.hsBgColor.value = hs.bg_color || '#FFFFFF';
        if (aiView.fields.hsFontSize) { aiView.fields.hsFontSize.value = hs.font_size !== undefined ? hs.font_size : 0.054; aiView.fields.hsFontSize.dispatchEvent(new Event('input')); }
        if (aiView.fields.hsCorner) { aiView.fields.hsCorner.value = hs.corner_radius !== undefined ? hs.corner_radius : 0; aiView.fields.hsCorner.dispatchEvent(new Event('input')); }
        if (aiView.fields.hsPosX) { aiView.fields.hsPosX.value = hs.position_x !== undefined ? hs.position_x : 0.5; aiView.fields.hsPosX.dispatchEvent(new Event('input')); }
        if (aiView.fields.hsPosY) { aiView.fields.hsPosY.value = hs.position_y !== undefined ? hs.position_y : 0.333; aiView.fields.hsPosY.dispatchEvent(new Event('input')); }
    }

    // Load Face Tracking & GPU Settings
    const ftCfg = await window.pywebview.api.get_face_tracking_settings();
    if (ftCfg) {
        if (ftCfg.face_tracking_mode === 'mediapipe') {
            if (aiView.fields.ftMediapipeRadio) aiView.fields.ftMediapipeRadio.checked = true;
        } else {
            if (aiView.fields.ftOpencvRadio) aiView.fields.ftOpencvRadio.checked = true;
        }
        if (aiView.fields.gaEnableCheck) aiView.fields.gaEnableCheck.checked = !!ftCfg.gpu_enabled;
    }

    // Load Output Dir Settings
    const odCfg = await window.pywebview.api.get_output_dir_settings();
    if (odCfg && aiView.fields.odPath) {
        aiView.fields.odPath.value = odCfg.output_dir || '';
    }

    loadReplizData();
  } catch(e) { console.warn('Settings load failed:', e); }

  try {
    const appCfg = await window.pywebview.api.get_app_config();
    const nameSpan = document.getElementById('header-username');
    if (nameSpan && appCfg && appCfg.owner_name) {
      nameSpan.textContent = appCfg.owner_name;
    }
  } catch(e) { console.warn('App config load failed:', e); }

  // Load provider type
  try {
    const provider = await window.pywebview.api.get_provider_type();
    providerType = (provider && provider.provider_type) || 'ytclip';
    setProviderType(providerType, true);
  } catch(e) { console.warn('Provider type load failed:', e); }

  // Refresh dashboard data now that API is ready
  if (dashboardView.refresh) dashboardView.refresh();
  
  if (typeof refreshCampaignList === 'function') {
      try {
          await refreshCampaignList();
      } catch (e) { console.warn('Failed to load campaigns:', e); }
  }

  window._initDone = true;
}

// ── Dependency status and observable install jobs ──
const dependencyNames = ['ytdlp', 'ffmpeg', 'deno', 'whisper', 'tzdata'];
const dependencyPending = new Set();
let dependencyInstallAllPending = false;
let dependencyPollTimer = null;
let dependencyStatusRequest = null;
let dependencyLastState = null;
let dependencyRequestError = '';

function dependencyFeedback(message) {
  dependencyRequestError = message || '';
  let feedback = aiView.element.querySelector('.dependency-feedback');
  if (!feedback) {
    feedback = document.createElement('p');
    feedback.className = 'dependency-feedback';
    feedback.setAttribute('role', 'status');
    feedback.style.cssText = 'font-size:12px;line-height:1.5;margin:8px 0;max-width:680px;overflow-wrap:anywhere';
    aiView.element.querySelector('.dep-status')?.insertAdjacentElement('afterend', feedback);
  }
  feedback.textContent = message || '';
  feedback.hidden = !message;
}

function scheduleDependencyPoll() {
  if (dependencyPollTimer) return;
  dependencyPollTimer = setTimeout(async () => {
    dependencyPollTimer = null;
    await loadDepStatus();
  }, 2000);
}

function renderDependencyStatus(deps, status) {
  const jobs = status.jobs || {};
  const isActive = job => job && ['queued', 'running'].includes(job.status);
  const busy = dependencyInstallAllPending || dependencyPending.size > 0 || status.active;
  const messages = [];
  dependencyNames.forEach(name => {
    const info = deps[name] || { installed: false, status: 'not_installed' };
    const job = jobs[name] || info.job || {};
    const pending = dependencyPending.has(name) || dependencyInstallAllPending || isActive(job);
    const item = aiView.element.querySelector(`.dep-item[data-dep="${name}"]`);
    const btn = item?.querySelector('.dep-action-btn');
    const dot = item?.querySelector('.dep-dot');
    const failed = job.status === 'failed';
    const restart = job.restart_required;
    const update = info.status === 'update_available';
    if (dot) {
      dot.classList.remove('ok', 'warn', 'err');
      dot.classList.add(pending || update || restart ? 'warn' : failed || !info.installed ? 'err' : 'ok');
    }
    if (item) item.title = [info.version && `Version: ${info.version}`, info.latest && `Available: ${info.latest}`, job.error || info.error].filter(Boolean).join(' · ');
    if (btn) {
      btn.textContent = pending ? (job.status === 'queued' ? 'Queued...' : 'Installing...')
        : failed ? 'Retry' : restart ? 'Restart app' : update ? 'Update' : info.installed ? 'Installed' : 'Install';
      btn.disabled = pending || restart || (info.installed && !update && !failed);
      btn.style.background = pending ? '#9CA3AF' : failed || !info.installed ? '#EF4444' : update || restart ? '#F59E0B' : '#10B981';
      btn.style.color = '#fff';
      btn.style.cursor = btn.disabled ? 'default' : 'pointer';
      btn.title = job.error || info.error || (restart ? 'Restart aplikasi untuk memuat paket yang baru.' : info.status === 'installed' ? 'Terpasang; versi terbaru belum dapat dipastikan.' : '');
    }
    if (failed) messages.push(`${name}: ${job.error || 'Instalasi gagal.'}`);
    else if (!info.installed && info.error) messages.push(info.error);
    if (restart) messages.push(`${name}: restart aplikasi untuk memakai versi baru.`);
  });
  if (deps.update_check?.status === 'failed') messages.push('Pengecekan versi online gagal. Status instalasi lokal tetap tersedia.');
  if (dependencyRequestError) messages.push(dependencyRequestError);
  const previousError = dependencyRequestError;
  dependencyFeedback(messages.join(' '));
  dependencyRequestError = previousError;

  if (installBtn) {
    const needsInstall = dependencyNames.some(name => !deps[name]?.installed);
    const needsUpdate = dependencyNames.some(name => deps[name]?.status === 'update_available' && !jobs[name]?.restart_required);
    const failed = dependencyNames.some(name => jobs[name]?.status === 'failed');
    installBtn.textContent = busy ? 'Installing...' : failed ? 'Retry Failed' : needsInstall ? 'Install All' : needsUpdate ? 'Update All' : 'All Installed';
    installBtn.disabled = busy || (!needsInstall && !needsUpdate && !failed);
  }
  const updatesBtn = aiView.element.querySelector('.dependency-check-updates');
  if (updatesBtn) {
    updatesBtn.disabled = busy || deps.update_check?.status === 'running';
    updatesBtn.textContent = deps.update_check?.status === 'running' ? 'Checking...' : 'Check Updates';
  }
  if (busy || deps.update_check?.status === 'running') scheduleDependencyPoll();
}

async function loadDepStatus() {
  // Share an in-flight request; setTimeout schedules the next poll after completion.
  if (dependencyStatusRequest) return dependencyStatusRequest;
  if (!window.pywebview?.api) return;
  dependencyStatusRequest = (async () => {
    try {
      const deps = await window.pywebview.api.check_dependencies_detailed();
      const jobs = await window.pywebview.api.get_dependency_install_status();
      dependencyLastState = { deps, jobs };
      renderDependencyStatus(deps, jobs);
      window._depsDone = true;
    } catch (error) {
      console.warn('Dep status load failed:', error);
      dependencyFeedback(`Status dependency belum dapat dibaca: ${error.message || error}`);
      // Keep controls locked if an acknowledged job is still running.
      if (dependencyLastState?.jobs.active || dependencyPending.size || dependencyInstallAllPending) scheduleDependencyPoll();
    } finally {
      dependencyStatusRequest = null;
    }
  })();
  return dependencyStatusRequest;
}

if (installBtn) {
  const updatesBtn = document.createElement('button');
  updatesBtn.className = 'btn dependency-check-updates';
  updatesBtn.textContent = 'Check Updates';
  updatesBtn.style.marginLeft = '8px';
  installBtn.insertAdjacentElement('afterend', updatesBtn);
  updatesBtn.addEventListener('click', async () => {
    updatesBtn.disabled = true;
    try {
      await window.pywebview.api.check_dependency_updates();
      dependencyFeedback('');
    } catch (error) {
      dependencyFeedback(error.message || String(error));
    }
    await loadDepStatus();
    scheduleDependencyPoll();
  });
}

// ── Per-dependency Install/Update button handlers ──
document.addEventListener('click', async event => {
  const btn = event.target.closest('.dep-action-btn');
  if (!btn || btn.disabled || !window.pywebview?.api) return;
  const name = btn.dataset.dep;
  if (!dependencyNames.includes(name)) return;
  dependencyPending.add(name);
  btn.disabled = true;
  btn.textContent = 'Starting...';
  try {
    const result = await window.pywebview.api.install_single_dependency(name);
    if (result.status === 'error') throw new Error(result.message || 'Installation failed');
    dependencyFeedback('');
  } catch (error) {
    dependencyFeedback(error.message || String(error));
  } finally {
    dependencyPending.delete(name);
    await loadDepStatus();
    scheduleDependencyPoll();
  }
});

window.addEventListener('pywebviewready', init);
window.addEventListener('pywebviewready', loadDepStatus);
// Fallback: if pywebviewready never fires (dev browser mode), init after delay
setTimeout(() => {
  if (!window._initDone) init();
  if (!window._depsDone) loadDepStatus();
}, 1500);
window._initDone = false;
window._depsDone = false;

