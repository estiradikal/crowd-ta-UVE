'use strict';

const VAD_SILENCE_ALERT_SECONDS = 10;
const VAD_SILENCE_RMS_THRESHOLD = 0.025;
const VAD_UI_INTERVAL_MS = 200;
// Respuesta rápida de la interfaz sin adelantar el registro de voz confirmada.
const VAD_POSITIVE_SPEECH_THRESHOLD = 0.55;
const VAD_NEGATIVE_SPEECH_THRESHOLD = 0.40;
const VAD_MIN_SPEECH_FRAMES = 3;
// Recuperación limitada ante audio presente y probabilidad sostenidamente baja.
const VAD_RECOVERY_LOW_PROBABILITY = 0.20;
const VAD_RECOVERY_AUDIO_RMS = 0.008;
const VAD_RECOVERY_WAIT_MS = 12000;
const VAD_RECOVERY_COOLDOWN_MS = 30000;
const VAD_MAX_AUTOMATIC_RECOVERIES = 0; // Diagnóstico: deshabilitado temporalmente

let crowdVAD = null;
let vadGeneration = 0;
let vadActive = false;
let vadSpeaking = false;
let vadSpeechCandidate = false;
let vadAudioTrack = null;
let levelAudioTrack = null;
let levelAudioContext = null;
let levelAnalyser = null;
let levelSource = null;
let levelTimer = null;
let vadTimer = null;
let vadAudioLevel = 0;
let lastProbabilityUIUpdate = 0;
let vadLowProbabilitySince = 0;
let vadLastRecoveryAt = 0;
let vadRecoveries = 0;
let vadRecoveryInProgress = false;
let vadSourceStream = null;

let vadDiagnosticLastFrameAt = 0;
let vadDiagnosticFrameCount = 0;
let vadDiagnosticLastProbability = 0;
let vadDiagnosticTimer = null;
let vadDiagnosticLastLogAt = 0;

function vadDiagnosticSnapshot(reason) {
  const track = vadAudioTrack;
  const source = vadSourceStream && vadSourceStream.getAudioTracks()[0];
  const now = performance.now();
  const report = {
    reason,
    msSinceLastFrame: vadDiagnosticLastFrameAt ? Math.round(now - vadDiagnosticLastFrameAt) : null,
    frames: vadDiagnosticFrameCount,
    probability: Number(vadDiagnosticLastProbability.toFixed(3)),
    rms: Number(vadAudioLevel.toFixed(4)),
    vadActive,
    vadSpeaking,
    vadSpeechCandidate,
    vadTrackState: track ? track.readyState : 'none',
    sourceTrackState: source ? source.readyState : 'none',
    sourceTrackEnabled: source ? source.enabled : null,
    audioContextState: levelAudioContext ? levelAudioContext.state : 'none',
    musicClass: window.CrowdMusicMonitor ? 'available' : 'not-exposed',
  };
  console.info('[CrowdTA VAD DIAGNOSTICO]', report);
  return report;
}

window.crowdVADDiagnostic = () => vadDiagnosticSnapshot('manual');

function startVADDiagnostics(generation) {
  if (vadDiagnosticTimer) clearInterval(vadDiagnosticTimer);
  vadDiagnosticTimer = setInterval(() => {
    if (generation !== vadGeneration || !vadActive) return;
    const now = performance.now();
    // Registro cada 5 segundos, sin cálculos ni reinicios adicionales.
    if (now - vadDiagnosticLastLogAt >= 5000) {
      vadDiagnosticLastLogAt = now;
      vadDiagnosticSnapshot(vadDiagnosticLastFrameAt && now - vadDiagnosticLastFrameAt > 3000 ? 'SIN FRAMES DEL MODELO' : 'seguimiento');
    }
  }, 1000);
}

function stopVADDiagnostics() {
  if (vadDiagnosticTimer) clearInterval(vadDiagnosticTimer);
  vadDiagnosticTimer = null;
}

let metrics = null;

function initialMetrics() {
  return {
    durationSeconds: 0,
    speechSeconds: 0,
    silenceSeconds: 0,
    noiseSeconds: 0,
    speechEvents: 0,
    nonSpeechEvents: 0,
    vadAlerts: 0,
    longestSilenceSeconds: 0,
    averageSpeechProbability: 0,
    probabilitySum: 0,
    probabilityCount: 0,
    secondsWithoutVoice: 0,
  };
}

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function updateVADStatus(status) {
  setText('vad-status', status);
}

function updateVADProbability(probability) {
  setText('vad-probability', `${(probability * 100).toFixed(1)}%`);
}

function updateVADSilenceTime() {
  setText('vad-silence-time', metrics ? metrics.secondsWithoutVoice : 0);
}

function setPanelColor(color) {
  const panel = document.getElementById('vad-debug-panel');
  if (panel) panel.style.borderColor = color;
}

function showTalkAlert(message) {
  setText('vad-alert-message', message);
  const toast = $('#vad-warning-toast');
  toast.removeClass('d-none');
  toast.toast('show');
}

function hideTalkAlert() {
  const toast = $('#vad-warning-toast');
  toast.toast('hide');
  toast.addClass('d-none');
}

function logAudioEvent(type, label = '', confidence = null, details = {}) {
  if (window.CrowdAudioSession) {
    window.CrowdAudioSession.log(type, label, confidence, details);
  }
}

function resetVADMetrics() {
  metrics = initialMetrics();
  vadSpeaking = false;
  vadSpeechCandidate = false;
  vadAudioLevel = 0;
  lastProbabilityUIUpdate = 0;
  vadLowProbabilitySince = 0;
  vadLastRecoveryAt = 0;
  vadRecoveries = 0;
  vadRecoveryInProgress = false;
  updateVADProbability(0);
  updateVADSilenceTime();
}

function updateLevelStatus() {
  if (!vadActive || !metrics) return;
  if (vadSpeaking) {
    updateVADStatus('VOZ DETECTADA');
    setPanelColor('#198754');
  } else if (vadSpeechCandidate) {
    updateVADStatus('ANALIZANDO VOZ');
    setPanelColor('#0d6efd');
  } else if (vadAudioLevel < VAD_SILENCE_RMS_THRESHOLD) {
    updateVADStatus('SILENCIO');
    setPanelColor('#6c757d');
  } else {
    updateVADStatus('SONIDO NO VERBAL');
    setPanelColor('#fd7e14');
  }
}

async function startAudioLevelMonitor(stream, generation) {
  const track = stream.getAudioTracks().find((item) => item.readyState === 'live');
  if (!track) throw new Error('No se encontró una pista de audio activa.');
  levelAudioTrack = track.clone();
  const AudioContextClass = window.AudioContext || window.webkitAudioContext;
  if (!AudioContextClass) throw new Error('AudioContext no está disponible.');
  levelAudioContext = new AudioContextClass();
  levelAnalyser = levelAudioContext.createAnalyser();
  levelAnalyser.fftSize = 2048;
  levelSource = levelAudioContext.createMediaStreamSource(new MediaStream([levelAudioTrack]));
  levelSource.connect(levelAnalyser);
  const data = new Float32Array(levelAnalyser.fftSize);

  levelTimer = setInterval(() => {
    if (generation !== vadGeneration || !vadActive || !levelAnalyser) return;
    levelAnalyser.getFloatTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i++) sum += data[i] * data[i];
    vadAudioLevel = Math.sqrt(sum / data.length);
    updateLevelStatus();
  }, VAD_UI_INTERVAL_MS);
  await levelAudioContext.resume();
}

function startVADTimer(generation) {
  if (vadTimer) clearInterval(vadTimer);
  vadTimer = setInterval(() => {
    if (generation !== vadGeneration || !vadActive || !metrics) return;
    metrics.durationSeconds++;

    if (vadSpeaking) {
      metrics.speechSeconds++;
      metrics.secondsWithoutVoice = 0;
    } else {
      metrics.secondsWithoutVoice++;
      if (vadAudioLevel < VAD_SILENCE_RMS_THRESHOLD) metrics.silenceSeconds++;
      else metrics.noiseSeconds++;
      metrics.longestSilenceSeconds = Math.max(
        metrics.longestSilenceSeconds,
        metrics.secondsWithoutVoice,
      );
    }
    updateVADSilenceTime();

    if (metrics.secondsWithoutVoice >= VAD_SILENCE_ALERT_SECONDS &&
        metrics.secondsWithoutVoice % VAD_SILENCE_ALERT_SECONDS === 0 &&
        !vadSpeaking) {
      metrics.vadAlerts++;
      showTalkAlert('No speech detected. Please continue thinking aloud while completing the task.');
      setPanelColor('#dc3545');
      logAudioEvent('silence_warning', 'SIN VOZ', null, {
        secondsWithoutVoice: metrics.secondsWithoutVoice,
      });
    }
  }, 1000);
}

async function closeLevelMonitor() {
  if (levelTimer) {
    clearInterval(levelTimer);
    levelTimer = null;
  }
  if (levelSource) {
    try { levelSource.disconnect(); } catch (error) { console.warn('[VAD]', error); }
  }
  if (levelAudioTrack && levelAudioTrack.readyState === 'live') levelAudioTrack.stop();
  const context = levelAudioContext;
  levelAudioTrack = null;
  levelSource = null;
  levelAnalyser = null;
  levelAudioContext = null;
  if (context && context.state !== 'closed') {
    try { await context.close(); } catch (error) { console.warn('[VAD]', error); }
  }
}

async function cleanupVAD() {
  stopVADDiagnostics();
  if (vadTimer) {
    clearInterval(vadTimer);
    vadTimer = null;
  }
  if (crowdVAD) {
    try { crowdVAD.pause(); } catch (error) { console.warn('[VAD]', error); }
  }
  if (vadAudioTrack && vadAudioTrack.readyState === 'live') vadAudioTrack.stop();
  vadAudioTrack = null;
  crowdVAD = null;
  await closeLevelMonitor();
}

async function recoverCrowdVAD(generation) {
  if (generation !== vadGeneration || !vadActive || vadRecoveryInProgress ||
      vadRecoveries >= VAD_MAX_AUTOMATIC_RECOVERIES || !vadSourceStream) return;
  vadRecoveryInProgress = true;
  vadRecoveries++;
  vadLastRecoveryAt = performance.now();
  vadLowProbabilitySince = 0;
  const stream = vadSourceStream;
  updateVADStatus('RECONECTANDO DETECTOR');
  logAudioEvent('vad_recovery', 'REINICIO AUTOMÁTICO DEL DETECTOR', null, {
    attempt: vadRecoveries,
  });
  try {
    // Conserva las métricas y no detiene la grabación principal ni el detector de música.
    await startCrowdVAD(stream, true);
  } finally {
    vadRecoveryInProgress = false;
  }
}

async function startCrowdVAD(stream, preserveMetrics = false) {
  const generation = ++vadGeneration;
  vadActive = false;
  await cleanupVAD();
  if (!preserveMetrics) resetVADMetrics();
  else {
    vadSpeaking = false;
    vadSpeechCandidate = false;
    vadAudioLevel = 0;
    lastProbabilityUIUpdate = 0;
    vadLowProbabilitySince = 0;
    updateVADProbability(0);
  }
  vadSourceStream = stream;
  vadDiagnosticLastFrameAt = 0;
  vadDiagnosticFrameCount = 0;
  vadDiagnosticLastProbability = 0;
  vadDiagnosticLastLogAt = 0;
  hideTalkAlert();
  updateVADStatus('INICIANDO');
  setPanelColor('#6c757d');

  try {
    if (typeof vad === 'undefined' || !vad.MicVAD) {
      throw new Error('La librería Silero VAD no está disponible.');
    }
    if (!stream) throw new Error('No existe un MediaStream.');
    const sourceTrack = stream.getAudioTracks().find((item) => item.readyState === 'live');
    if (!sourceTrack) throw new Error('El stream no contiene audio activo.');

    vadActive = true;
    vadAudioTrack = sourceTrack.clone();
    const vadStream = new MediaStream([vadAudioTrack]);
    await startAudioLevelMonitor(stream, generation);
    if (generation !== vadGeneration || !vadActive) return;

    const instance = await vad.MicVAD.new({
      model: 'v6',
      // Umbrales moderados; no se fuerza una clasificación de música como voz.
      positiveSpeechThreshold: VAD_POSITIVE_SPEECH_THRESHOLD,
      negativeSpeechThreshold: VAD_NEGATIVE_SPEECH_THRESHOLD,
      minSpeechFrames: VAD_MIN_SPEECH_FRAMES,
      processorType: 'AudioWorklet',
      getStream: async () => vadStream,
      pauseStream: async () => {},
      resumeStream: async () => vadStream,
      onnxWASMBasePath: 'https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/',
      baseAssetPath: 'https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.31/dist/',
      onFrameProcessed: (probabilities) => {
        if (generation !== vadGeneration || !vadActive || !metrics) return;
        const probability = Number(probabilities.isSpeech) || 0;
        vadDiagnosticLastFrameAt = performance.now();
        vadDiagnosticFrameCount++;
        vadDiagnosticLastProbability = probability;
        metrics.probabilitySum += probability;
        metrics.probabilityCount++;
        const now = performance.now();
        if (probability >= VAD_RECOVERY_LOW_PROBABILITY || vadSpeaking || vadSpeechCandidate ||
            vadAudioLevel < VAD_RECOVERY_AUDIO_RMS) {
          vadLowProbabilitySince = 0;
        } else if (!vadLowProbabilitySince) {
          vadLowProbabilitySince = now;
        } else if (!vadRecoveryInProgress &&
                   vadRecoveries < VAD_MAX_AUTOMATIC_RECOVERIES &&
                   now - vadLowProbabilitySince >= VAD_RECOVERY_WAIT_MS &&
                   now - vadLastRecoveryAt >= VAD_RECOVERY_COOLDOWN_MS) {
          // Programar fuera del callback para no interrumpir el procesamiento del frame.
          void recoverCrowdVAD(generation).catch((error) => {
            console.error('[VAD] Falló la recuperación automática:', error);
          });
        }
        if (now - lastProbabilityUIUpdate >= VAD_UI_INTERVAL_MS) {
          lastProbabilityUIUpdate = now;
          updateVADProbability(probability);
        }
      },
      onSpeechStart: () => {
        if (generation !== vadGeneration || !vadActive || !metrics) return;
        // El comienzo candidato aparece de inmediato; no modifica estadísticas.
        vadSpeechCandidate = true;
        updateVADStatus('ANALIZANDO VOZ');
        setPanelColor('#0d6efd');
      },
      onSpeechRealStart: () => {
        if (generation !== vadGeneration || !vadActive || !metrics) return;
        vadSpeaking = true;
        vadDiagnosticSnapshot('voz confirmada');
        vadLowProbabilitySince = 0;
        vadSpeechCandidate = false;
        metrics.speechEvents++;
        metrics.secondsWithoutVoice = 0;
        updateVADSilenceTime();
        updateVADStatus('VOZ DETECTADA');
        setPanelColor('#198754');
        hideTalkAlert();
        logAudioEvent('speech_start', 'VOZ DETECTADA');
      },
      onSpeechEnd: () => {
        if (generation !== vadGeneration || !vadActive) return;
        vadSpeaking = false;
        vadSpeechCandidate = false;
        logAudioEvent('speech_end', 'FIN DE VOZ');
      },
      onVADMisfire: () => {
        if (generation !== vadGeneration || !vadActive || !metrics) return;
        vadSpeaking = false;
        vadSpeechCandidate = false;
        metrics.nonSpeechEvents++;
        updateVADStatus('SONIDO NO VERBAL');
        setPanelColor('#fd7e14');
        logAudioEvent('non_speech_sound', 'SONIDO NO VERBAL');
      },
    });

    if (generation !== vadGeneration || !vadActive) {
      try { instance.pause(); } catch (error) { console.warn('[VAD]', error); }
      return;
    }
    crowdVAD = instance;
    await crowdVAD.start();
    if (generation !== vadGeneration || !vadActive) return;
    updateVADStatus('ESCUCHANDO');
    startVADTimer(generation);
    logAudioEvent('vad_ready', 'SILERO V6 LISTO');
    vadDiagnosticSnapshot('inicio');
    startVADDiagnostics(generation);
  } catch (error) {
    if (generation !== vadGeneration) return;
    vadActive = false;
    console.error('[VAD] No se pudo iniciar:', error);
    updateVADStatus('VAD NO DISPONIBLE');
    setPanelColor('#dc3545');
    logAudioEvent('vad_error', String(error.message || error));
    await cleanupVAD();
  }
}

function getVADSummary() {
  if (!metrics) return initialMetrics();
  return {
    durationSeconds: metrics.durationSeconds,
    speechSeconds: metrics.speechSeconds,
    silenceSeconds: metrics.silenceSeconds,
    noiseSeconds: metrics.noiseSeconds,
    averageSpeechProbability: metrics.probabilityCount > 0
      ? metrics.probabilitySum / metrics.probabilityCount
      : 0,
    longestSilenceSeconds: metrics.longestSilenceSeconds,
    speechEvents: metrics.speechEvents,
    nonSpeechEvents: metrics.nonSpeechEvents,
    vadAlerts: metrics.vadAlerts,
  };
}

function getCookie(name) {
  if (!document.cookie) return null;
  const prefix = `${name}=`;
  const cookie = document.cookie.split(';')
    .map((item) => item.trim())
    .find((item) => item.startsWith(prefix));
  return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
}

async function saveVADTaskStatus(summary) {
  if (!summary.durationSeconds) return;
  const noVoiceSeconds = summary.silenceSeconds + summary.noiseSeconds;
  const noVoicePercentage = (noVoiceSeconds / summary.durationSeconds) * 100;
  const formData = new FormData();
  formData.append('taskq', $('#taskq').val() || '');
  formData.append('taskid', $('#taskid').val() || '');
  formData.append('silence', noVoicePercentage.toFixed(2));
  formData.append('task_time', summary.durationSeconds);
  const response = await fetch('/statusupdate/', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'X-CSRFToken': getCookie('csrftoken') || '' },
    body: formData,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
}

async function StopVADAnalysisAndSave() {
  ++vadGeneration;
  vadActive = false;
  vadSpeaking = false;
  vadSpeechCandidate = false;
  vadSourceStream = null;
  const summary = getVADSummary();
  await cleanupVAD();
  hideTalkAlert();
  updateVADStatus('TAREA FINALIZADA');
  setPanelColor('#6c757d');

  if (window.CrowdAudioSession) {
    window.CrowdAudioSession.setMetrics(summary);
  }
  try {
    await saveVADTaskStatus(summary);
  } catch (error) {
    console.error('[VAD] No se pudo guardar el estado de la tarea:', error);
    logAudioEvent('vad_status_save_error', String(error.message || error));
  }
  return summary;
}

window.startCrowdVAD = startCrowdVAD;
window.StopVADAnalysisAndSave = StopVADAnalysisAndSave;
window.getCrowdVADSummary = getVADSummary;
