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

pageContent.appendChild(dashboardView.element);
pageContent.appendChild(campaignListView.element);
pageContent.appendChild(campaignEditView.element);
pageContent.appendChild(homeView.element);
pageContent.appendChild(stockClipView.element);
pageContent.appendChild(aiView.element);

const allViews = [dashboardView.element, campaignListView.element, campaignEditView.element, homeView.element, stockClipView.element, aiView.element];
const navItems = shellComp.navItems;

// ── State ──
let polling = null;
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

// ── Processing Controls ──
function lockControls(state) {
  homeView.fields.url.disabled = state;
  homeView.fields.clips.disabled = state;
  homeView.fields.subtitle.disabled = state;
  homeView.fields.highlight.disabled = state;
  homeView.fields.captions.disabled = state;
  homeView.fields.hook.disabled = state;
  homeView.fields.ytTitle.disabled = state;
  homeView.fields.start.disabled = state;
  if (state) {
    homeView.fields.start.style.opacity = '0.5';
    homeView.fields.start.style.cursor = 'not-allowed';
  } else {
    homeView.fields.start.style.opacity = '1';
    homeView.fields.start.style.cursor = 'pointer';
  }
}

function updateStepStatus(status) {
  const statusLower = (status || '').toLowerCase();
  function setStep(el, cls, text) {
    if (!el) return;
    const span = el.querySelector('.step-status');
    if (span) { span.className = 'step-status ' + cls; span.textContent = text; }
  }
  // Preparing step: mark as ongoing during download/highlight, done when clips start
  if (statusLower.includes('download') || statusLower.includes('subtitle') || statusLower.includes('transcrib') || statusLower.includes('highlight') || statusLower.includes('finding') || statusLower.includes('checking') || statusLower.includes('segment')) {
    setStep(homeView.fields.stepPreparing, 'ongoing', 'Ongoing');
  } else if (statusLower.includes('clip') || statusLower.includes('process') || statusLower.includes('portrait') || statusLower.includes('caption') || statusLower.includes('hook') || statusLower.includes('complete')) {
    setStep(homeView.fields.stepPreparing, 'complete', 'Done');
  } else if (statusLower.startsWith('error')) {
    setStep(homeView.fields.stepPreparing, 'failed', 'Failed');
  }
}

// ── Terminal State ──
let termDotInterval = null;   // animated dots timer
let termDotCount = 0;
let termErrorLines = [];      // accumulated error strings
let termCurrentLine = null;   // DOM span for current status
let termErrorBlock = null;    // DOM div for error section
let termLastStatus = '';      // track last status to detect new lines

function termInit() {
  termErrorLines = [];
  termCurrentLine = null;
  termErrorBlock = null;
  termLastStatus = '';
  homeView.fields.terminal.innerHTML = '';

  // Current-status line
  termCurrentLine = document.createElement('span');
  termCurrentLine.style.color = 'rgba(255,255,255,0.85)';
  homeView.fields.terminal.appendChild(termCurrentLine);

  termStartDots('Processing running');

  // Reset clip progress UI
  if (homeView.fields.inProgressList) homeView.fields.inProgressList.innerHTML = '';
  if (homeView.fields.waitingList) homeView.fields.waitingList.innerHTML = '';
  if (homeView.fields.errorLogBox) homeView.fields.errorLogBox.innerHTML = '';
  if (homeView.fields.progressCount) homeView.fields.progressCount.textContent = '0/0';
  if (homeView.fields.inProgressBadge) homeView.fields.inProgressBadge.textContent = '0';
  if (homeView.fields.waitingBadge) homeView.fields.waitingBadge.textContent = '0';
  if (homeView.fields.errorBadge) homeView.fields.errorBadge.textContent = '0';
  // Reset preparing step
  const prepSpan = homeView.fields.stepPreparing ? homeView.fields.stepPreparing.querySelector('.step-status') : null;
  if (prepSpan) { prepSpan.className = 'step-status'; prepSpan.textContent = 'Waiting'; }
}

function termStartDots(prefix) {
  if (termDotInterval) clearInterval(termDotInterval);
  termDotCount = 0;
  termDotInterval = setInterval(() => {
    termDotCount = (termDotCount % 3) + 1;
    if (termCurrentLine) {
      termCurrentLine.textContent = prefix + '.'.repeat(termDotCount);
    }
  }, 400);
}

function termStopDots() {
  if (termDotInterval) {
    clearInterval(termDotInterval);
    termDotInterval = null;
  }
}

function termSetLine(text, color) {
  termStopDots();
  if (termCurrentLine) {
    termCurrentLine.textContent = text;
    termCurrentLine.style.color = color || 'rgba(255,255,255,0.85)';
  }
  homeView.fields.terminal.scrollTop = homeView.fields.terminal.scrollHeight;
}

function termAddError(errText) {
  // Build error block if first error
  if (!termErrorBlock) {
    const divider = document.createElement('div');
    divider.style.cssText = 'margin:10px 0 6px; border-top:1px solid rgba(255,255,255,0.15); padding-top:8px; color:rgba(255,100,100,0.8); font-size:11px;';
    divider.textContent = '──────────────────────── Error Log ────────────────────────';
    homeView.fields.terminal.appendChild(divider);

    termErrorBlock = document.createElement('div');
    termErrorBlock.style.cssText = 'color: rgba(255,100,100,0.9); font-size:11px; white-space:pre-wrap; word-break:break-all; margin-top:4px;';
    homeView.fields.terminal.appendChild(termErrorBlock);
  }
  termErrorLines.push(errText);
  termErrorBlock.textContent = termErrorLines.join('\n');
  homeView.fields.terminal.scrollTop = homeView.fields.terminal.scrollHeight;
}

function termFinish(isError) {
  termStopDots();
  if (isError) {
    if (homeView.fields.termLabel) homeView.fields.termLabel.textContent = 'Error';
    termCurrentLine.style.color = 'rgba(255,100,100,0.9)';
  } else {
    if (homeView.fields.termLabel) homeView.fields.termLabel.textContent = 'Done';
    termCurrentLine.style.color = '#a3ff33';
  }
}

// ── Processing Controls ─────────────────────────────────────────
async function start() {
  const url = homeView.fields.url.value.trim();
  if (!url) return;
  lockControls(true);
  if (homeView.fields.termLabel) homeView.fields.termLabel.textContent = 'Running';
  homeView.fields.status.textContent = 'Starting...';
  homeView.fields.bar.style.width = '0%';
  termInit();

  try {
    const res = await window.pywebview.api.start_processing(
      url,
      parseInt(homeView.fields.clips.value, 10),
      homeView.fields.captions.checked,
      homeView.fields.hook.checked,
      homeView.fields.subtitle.value,
      homeView.fields.portrait.checked,
      homeView.fields.highlight.checked,
      homeView.fields.ytTitle.checked,
      homeView.fields.campaign ? homeView.fields.campaign.value : "",
      homeView.fields.subtitleStyle ? homeView.fields.subtitleStyle.value : "capcut",
      homeView.fields.clipMode ? homeView.fields.clipMode() : "fixed"
    );
    if (res && res.status === 'started') {
      poll();
      polling = setInterval(poll, 500);
    } else {
      homeView.fields.status.textContent = 'Busy - another process is running';
      termSetLine('Another process is already running.', 'rgba(255,200,50,0.9)');
      if (homeView.fields.termLabel) homeView.fields.termLabel.textContent = 'Busy';
      lockControls(false);
    }
  } catch (e) {
    homeView.fields.status.textContent = 'Error: ' + e;
    termAddError(String(e));
    termFinish(true);
    lockControls(false);
  }
}

// ── Clip Card Rendering ──
function renderClipCard(clip, isRunning) {
  const card = document.createElement('div');
  card.style.cssText = 'padding:10px 12px;border:1px solid var(--border-light);border-radius:8px;background:var(--bg);' + (isRunning ? 'border-left:3px solid var(--success);' : '');

  const row1 = document.createElement('div');
  row1.style.cssText = 'display:flex;align-items:center;justify-content:space-between;gap:8px;';
  const title = document.createElement('span');
  title.style.cssText = 'font-size:12px;font-weight:600;flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
  title.textContent = clip.title || 'Untitled';
  const score = document.createElement('span');
  score.style.cssText = 'font-size:10px;font-weight:700;background:rgba(163,255,51,0.15);color:#3d6b10;padding:2px 8px;border-radius:10px;white-space:nowrap;';
  score.textContent = clip.virality_score != null ? clip.virality_score.toFixed(1) : '?';
  row1.appendChild(title);
  row1.appendChild(score);
  card.appendChild(row1);

  const row2 = document.createElement('div');
  row2.style.cssText = 'display:flex;align-items:center;justify-content:space-between;margin-top:4px;';
  const time = document.createElement('span');
  time.style.cssText = 'font-size:10px;color:var(--text-muted);';
  time.textContent = (clip.start_time || '?') + ' - ' + (clip.end_time || '?');
  const step = document.createElement('span');
  step.style.cssText = 'font-size:10px;color:' + (isRunning ? 'var(--success)' : 'var(--text-muted)') + ';';
  step.textContent = isRunning ? (clip.step || 'Processing') : 'Queued';
  row2.appendChild(time);
  row2.appendChild(step);
  card.appendChild(row2);

  if (isRunning && clip.step_progress != null) {
    const barTrack = document.createElement('div');
    barTrack.style.cssText = 'height:3px;background:var(--border);border-radius:2px;overflow:hidden;margin-top:6px;';
    const barFill = document.createElement('div');
    barFill.style.cssText = 'height:100%;background:var(--success);transition:width 0.3s ease;width:' + Math.min(100, (clip.step_progress * 100)).toFixed(0) + '%;';
    barTrack.appendChild(barFill);
    card.appendChild(barTrack);
  }

  return card;
}

function renderErrorCard(clip) {
  const card = document.createElement('div');
  card.style.cssText = 'padding:8px 12px;background:rgba(239,68,68,0.05);border:1px solid rgba(239,68,68,0.15);border-radius:8px;font-size:11px;color:var(--error);';
  card.textContent = 'Clip ' + clip.index + ' - "' + (clip.title || '?') + '": ' + (clip.error || 'Unknown error');
  return card;
}

function renderClipsUI(clips) {
  if (!clips || clips.length === 0) return;

  const running = clips.filter(c => c.status === 'running').sort((a,b) => a.index - b.index);
  const waiting = clips.filter(c => c.status === 'waiting').sort((a,b) => a.index - b.index);
  const errors = clips.filter(c => c.status === 'error').sort((a,b) => a.index - b.index);
  const done = clips.filter(c => c.status === 'done').length;

  // Update counter
  if (homeView.fields.progressCount) {
    homeView.fields.progressCount.textContent = done + '/' + clips.length;
  }

  // In progress
  homeView.fields.inProgressList.innerHTML = '';
  running.forEach(c => homeView.fields.inProgressList.appendChild(renderClipCard(c, true)));
  if (homeView.fields.inProgressBadge) homeView.fields.inProgressBadge.textContent = running.length;

  // Waiting
  homeView.fields.waitingList.innerHTML = '';
  waiting.forEach(c => homeView.fields.waitingList.appendChild(renderClipCard(c, false)));
  if (homeView.fields.waitingBadge) homeView.fields.waitingBadge.textContent = waiting.length;

  // Errors
  homeView.fields.errorLogBox.innerHTML = '';
  errors.forEach(c => homeView.fields.errorLogBox.appendChild(renderErrorCard(c)));
  if (homeView.fields.errorBadge) homeView.fields.errorBadge.textContent = errors.length;
}

async function poll() {
  try {
    const p = await window.pywebview.api.get_progress();
    const pr = Math.max(0, Math.min(1, p.progress || 0));
    const status = p.status || '';
    homeView.fields.bar.style.width = (pr * 100).toFixed(1) + '%';
    homeView.fields.status.textContent = status;

    if (status !== termLastStatus) {
      termLastStatus = status;
      const sl = status.toLowerCase();

      if (sl.startsWith('error')) {
        // Error: push to error block, stop dots
        termSetLine(status, 'rgba(255,100,100,0.9)');
        termAddError(status);
      } else if (
        sl.includes('download') ||
        sl.includes('mb/') ||
        sl.includes('kb/') ||
        sl.includes('gb/')
      ) {
        // Download progress — replace current line, no dots
        termStopDots();
        termSetLine(status);
        if (homeView.fields.termLabel) homeView.fields.termLabel.textContent = 'Downloading';
      } else if (sl === 'complete' || sl === 'running' || sl === '') {
        // Generic running state — animated dots
        if (!termDotInterval) termStartDots('Processing running');
      } else {
        // Any other descriptive status (highlight, editing…) — show as-is, replace
        termStopDots();
        termSetLine(status);
      }
    } else if (
      // Keep refreshing download lines even if status string changed only in bytes
      (status.toLowerCase().includes('mb/') ||
       status.toLowerCase().includes('kb/') ||
       status.toLowerCase().includes('gb/'))
    ) {
      termSetLine(status);
    }

    updateStepStatus(status);

    // Poll per-clip status
    try {
      const cs = await window.pywebview.api.get_clips_status();
      if (cs && cs.clips) renderClipsUI(cs.clips);
    } catch {}

    if (status && (status.startsWith('error') || status === 'complete')) {
      clearInterval(polling);
      polling = null;
      termFinish(status.startsWith('error'));
      lockControls(false);
    }
  } catch {
    clearInterval(polling);
    polling = null;
    termFinish(true);
    lockControls(false);
  }
}

homeView.fields.start.addEventListener('click', start);

// ── Terminal Copy Button ──
if (homeView.fields.termCopyBtn) {
  homeView.fields.termCopyBtn.addEventListener('click', () => {
    const text = homeView.fields.terminal.textContent || '';
    navigator.clipboard.writeText(text).then(() => {
      homeView.fields.termCopyBtn.textContent = 'Copied!';
      setTimeout(() => { homeView.fields.termCopyBtn.textContent = 'Copy'; }, 1500);
    }).catch(() => {});
  });
}

// ── Install All Button ──
const installBtn = aiView.element.querySelector('.btn-lime');
if (installBtn) {
  installBtn.addEventListener('click', async () => {
    installBtn.disabled = true;
    installBtn.textContent = 'Installing...';
    try {
      await window.pywebview.api.install_dependencies();
      installBtn.textContent = 'Installing (bg)...';

      const maxAttempts = 40; // 40 x 3s = 2 menit
      let attempts = 0;
      const poll = setInterval(async () => {
        attempts++;
        await loadDepStatus();
        const deps = await window.pywebview.api.check_dependencies();
        const allOk = deps.ffmpeg && deps.deno && deps.whisper && deps.ytdlp;
        if (allOk || attempts >= maxAttempts) {
          clearInterval(poll);
          installBtn.disabled = false;
          installBtn.textContent = 'Install All';
        }
      }, 3000);
    } catch(e) {
      installBtn.textContent = 'Error';
      installBtn.disabled = false;
    }
  });
}

// ── Save AI Settings ──
aiView.fields.saveBtn.addEventListener('click', async () => {
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
          model: model
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
    const savePromises = [
      window.pywebview.api.save_ai_settings(payload),
      window.pywebview.api.save_watermark_settings(wmPayload),
      window.pywebview.api.save_credit_watermark_settings(cwPayload),
      window.pywebview.api.save_hook_style_settings(hsPayload),
      window.pywebview.api.save_face_tracking_settings(ftPayload),
    ];
    // Only save output dir if user actually set a path
    if (odPath) savePromises.push(window.pywebview.api.save_output_dir_settings(odPayload));
    
    const results = await Promise.all(savePromises);
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
});

// Auto-save logic for AI Settings
let aiSaveTimeout = null;
aiView.element.addEventListener('input', (e) => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    clearTimeout(aiSaveTimeout);
    aiSaveTimeout = setTimeout(() => {
      if (aiView.fields.saveBtn) aiView.fields.saveBtn.click();
    }, 1000);
  }
});
aiView.element.addEventListener('change', (e) => {
  if (e.target.tagName === 'SELECT' || e.target.type === 'checkbox' || e.target.type === 'radio') {
    if (aiView.fields.saveBtn) aiView.fields.saveBtn.click();
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
      const cmModels = allModels.filter(isSTT);
      const hmModels = allModels.filter(isTTS);
      const ytModels = allModels.filter(isChat);

      if (aiView.fields.hfModel) {
        const pref = aiView.fields.hfModel.value;
        setSelectOptions(aiView.fields.hfModel, hfModels, pref);
        if (homeView.fields.highlightSub) setSelectOptions(homeView.fields.highlightSub, hfModels, pref);
      }
      if (aiView.fields.cmModel) {
        const pref = aiView.fields.cmModel.value;
        setSelectOptions(aiView.fields.cmModel, cmModels, pref);
        if (homeView.fields.captionSub) setSelectOptions(homeView.fields.captionSub, cmModels, pref);
      }
      if (aiView.fields.hmModel) {
        const pref = aiView.fields.hmModel.value;
        setSelectOptions(aiView.fields.hmModel, hmModels, pref);
        if (homeView.fields.hookSub) setSelectOptions(homeView.fields.hookSub, hmModels, pref);
      }
      if (aiView.fields.ytModel) {
        const pref = aiView.fields.ytModel.value;
        setSelectOptions(aiView.fields.ytModel, ytModels, pref);
        if (homeView.fields.ytTitleSub) setSelectOptions(homeView.fields.ytTitleSub, ytModels, pref);
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

// ── Setup Home Select Synchronization ──
function syncHomeSelect(homeSel, aiSel) {
  if (!homeSel || !aiSel) return;
  homeSel.addEventListener('change', () => {
    aiSel.value = homeSel.value;
    if (aiView.fields.saveBtn) aiView.fields.saveBtn.click();
  });
  aiSel.addEventListener('change', () => {
    homeSel.value = aiSel.value;
    if (aiView.fields.saveBtn) aiView.fields.saveBtn.click();
  });
}
syncHomeSelect(homeView.fields.highlightSub, aiView.fields.hfModel);
syncHomeSelect(homeView.fields.captionSub, aiView.fields.cmModel);
syncHomeSelect(homeView.fields.hookSub, aiView.fields.hmModel);
syncHomeSelect(homeView.fields.ytTitleSub, aiView.fields.ytModel);

aiView.fields.hfValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.hfUrl,
  key: aiView.fields.hfKey,
  modelSelect: aiView.fields.hfModel,
  homeSelect: homeView.fields.highlightSub,
  status: aiView.fields.hfValidateStatus
}));

aiView.fields.cmValidateBtn.addEventListener('click', () => validateAndLoad({
  url: aiView.fields.cmUrl,
  key: aiView.fields.cmKey,
  modelSelect: aiView.fields.cmModel,
  homeSelect: homeView.fields.captionSub,
  status: aiView.fields.cmValidateStatus
}));

if (aiView.fields.hmValidateBtn) {
  aiView.fields.hmValidateBtn.addEventListener('click', () => validateAndLoad({
    url: { value: GEMINI_BASE_URL },
    key: aiView.fields.hmKey,
    modelSelect: aiView.fields.hmModel,
    homeSelect: homeView.fields.hookSub,
    status: aiView.fields.hmValidateStatus
  }));
}

if (aiView.fields.cpValidateBtn) {
  aiView.fields.cpValidateBtn.addEventListener('click', () => validateAndLoad({
    url: aiView.fields.cpUrl,
    key: aiView.fields.cpKey,
    modelSelect: aiView.fields.ytModel,
    homeSelect: homeView.fields.ytTitleSub,
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
      const res = await window.pywebview.api.test_model(payload.base_url, payload.api_key, payload.model, payload.model_type);
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

    // Update feature toggle sub-labels in homeView with the loaded model
    setSelectOptions(homeView.fields.highlightSub, [hf.model].filter(Boolean), hf.model || '');
    setSelectOptions(homeView.fields.captionSub, [cm.model].filter(Boolean), cm.model || '');
    setSelectOptions(homeView.fields.hookSub, [hm.model].filter(Boolean), hm.model || '');
    setSelectOptions(homeView.fields.ytTitleSub, [yt.model].filter(Boolean), yt.model || '');
    
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

// ── Load Dependency Status ──
async function loadDepStatus() {
  try {
    const deps = await window.pywebview.api.check_dependencies();
    const dots = aiView.element.querySelectorAll('.dep-dot');
    // Map: yt-dlp, ffmpeg, deno, whisper
    const depMap = [deps.ytdlp, deps.ffmpeg, deps.deno, deps.whisper];
    dots.forEach((dot, i) => {
      const ok = depMap[i];
      dot.classList.toggle('err', !ok);
      dot.classList.toggle('ok', !!ok);
    });
  } catch(e) { console.warn('Dep status load failed:', e); }
}

window.addEventListener('pywebviewready', init);
window.addEventListener('pywebviewready', loadDepStatus);
// Fallback: if pywebviewready never fires (dev browser mode), init after delay
setTimeout(() => {
  if (!window._initDone) init();
  if (!window._depsDone) loadDepStatus();
}, 1500);
window._initDone = false;
window._depsDone = false;

