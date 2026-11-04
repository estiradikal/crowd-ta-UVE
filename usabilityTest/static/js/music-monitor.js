'use strict';

const MUSIC_SAMPLE_RATE = 16000;
const MUSIC_WINDOW_SECONDS = 5;
const MUSIC_WINDOW_SAMPLES = MUSIC_SAMPLE_RATE * MUSIC_WINDOW_SECONDS;
const MUSIC_REQUIRED_WINDOWS = 2;
const MUSIC_IMMEDIATE_CONFIDENCE = 0.45;

const musicScriptURL = document.currentScript ? document.currentScript.src : window.location.href;
const MUSIC_WORKER_URL = new URL('music-classifier-worker.js', musicScriptURL).href;
const AUDIO_WORKLET_URL = new URL('audio-capture-worklet.js', musicScriptURL).href;

let musicWorker = null;
let musicWorkerPromise = null;
let musicWorkerResolve = null;
let musicWorkerReject = null;
let musicWorkerReady = false;
let musicActive = false;
let musicBusy = false;
let musicGeneration = 0;
let musicWarningStreak = 0;
let musicWarningActive = false;
let musicTrack = null;
let musicContext = null;
let musicSource = null;
let musicWorklet = null;
let musicSilentGain = null;
let musicBuffer = null;
let musicBufferPosition = 0;

function musicStatus(value) {
  const element = document.getElementById('music-status');
  if (element) element.textContent = value;
}

function musicDetails(value) {
  const element = document.getElementById('music-top-scores');
  if (element) element.textContent = value;
}

function showMusicAlert(message) {
  const alertMessage = document.getElementById('music-alert-message');
  if (alertMessage) alertMessage.textContent = message;
  const toast = $('#music-warning-toast');
  toast.removeClass('d-none');
  toast.toast('show');
}

function hideMusicAlert() {
  const toast = $('#music-warning-toast');
  toast.toast('hide');
  toast.addClass('d-none');
}

function resampleChunk(input, sourceRate, targetRate) {
  if (sourceRate === targetRate) return input;
  const ratio = sourceRate / targetRate;
  const outputLength = Math.max(1, Math.floor(input.length / ratio));
  const output = new Float32Array(outputLength);
  for (let i = 0; i < outputLength; i++) {
    const position = i * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, input.length - 1);
    const fraction = position - left;
    output[i] = input[left] + (input[right] - input[left]) * fraction;
  }
  return output;
}

function describeTopPredictions(predictions) {
  if (!predictions.length) return 'El modelo no devolvió resultados.';
  return predictions.slice(0, 3).map((entry) =>
    `${entry.label}: ${(100 * entry.score).toFixed(1)}%`
  ).join(' · ');
}

function handleClassification(message) {
  musicBusy = false;
  if (!musicActive || message.generation !== musicGeneration) return;

  const summary = message.summary || {};
  const result = summary.label || 'AUDIO NO DETERMINADO';
  const confidence = Number(summary.confidence) || 0;
  const warning = result === 'MÚSICA PROBABLE' || result === 'CANTO PROBABLE';
  musicDetails(describeTopPredictions(message.predictions || []));

  if (window.CrowdAudioSession) {
    window.CrowdAudioSession.setMetrics({ lastAudioLabel: result });
    window.CrowdAudioSession.log('audio_classification', result, confidence, {
      scores: summary.scores || {},
      top: message.predictions || [],
    });
  }

  if (!warning) {
    musicWarningStreak = 0;
    musicWarningActive = false;
    musicStatus(result);
    hideMusicAlert();
    return;
  }

  musicWarningStreak++;
  const confirmed = confidence >= MUSIC_IMMEDIATE_CONFIDENCE ||
    musicWarningStreak >= MUSIC_REQUIRED_WINDOWS;
  if (!confirmed) {
    musicStatus('VALIDANDO POSIBLE MÚSICA');
    return;
  }

  musicStatus(result);
  const alertLabel = result === 'CANTO PROBABLE' ? 'Possible singing detected' : 'Possible music detected';
  showMusicAlert(`${alertLabel}. Please keep the environment free of music during the test.`);
  if (window.CrowdAudioSession && !musicWarningActive) {
    const metric = result === 'CANTO PROBABLE' ? 'singingAlerts' : 'musicAlerts';
    window.CrowdAudioSession.increment(metric);
    window.CrowdAudioSession.log('audio_warning', result, confidence);
  }
  musicWarningActive = true;
}

function createMusicWorker() {
  if (musicWorkerPromise) return musicWorkerPromise;
  musicWorkerPromise = new Promise((resolve, reject) => {
    musicWorkerResolve = resolve;
    musicWorkerReject = reject;
    try {
      musicWorker = new Worker(MUSIC_WORKER_URL, { type: 'module' });
    } catch (error) {
      reject(error);
      return;
    }

    musicWorker.onmessage = (event) => {
      const message = event.data || {};
      if (message.type === 'progress') {
        musicStatus('DESCARGANDO MODELO');
        musicDetails(`Preparando el clasificador: ${message.progress.toFixed(0)}% del archivo actual.`);
      } else if (message.type === 'ready') {
        musicWorkerReady = true;
        musicWorkerResolve(musicWorker);
        if (!musicActive) {
          musicStatus('MODELO LISTO');
          musicDetails('Esperando el inicio de la tarea.');
        }
      } else if (message.type === 'result') {
        handleClassification(message);
      } else if (message.type === 'error') {
        musicBusy = false;
        console.error('[MUSIC WORKER]', message.message);
        if (message.stage === 'load') {
          musicWorkerReject(new Error(message.message));
          musicStatus('MODELO NO DISPONIBLE');
          musicDetails('La grabación y el detector de voz continúan normalmente.');
        } else if (musicActive) {
          musicStatus('ERROR DE CLASIFICACIÓN');
        }
      }
    };
    musicWorker.onerror = (error) => {
      musicBusy = false;
      console.error('[MUSIC WORKER]', error);
      if (!musicWorkerReady) reject(error);
    };
    musicWorker.postMessage({ type: 'load' });
  }).catch((error) => {
    musicWorkerPromise = null;
    throw error;
  });
  return musicWorkerPromise;
}

function preloadCrowdMusicModel() {
  musicStatus('PREPARANDO MODELO');
  musicDetails('La inteligencia artificial se prepara fuera de la interfaz.');
  return createMusicWorker();
}

function submitMusicWindow() {
  if (!musicActive || !musicWorkerReady || musicBusy || !musicBuffer) return;
  const waveform = musicBuffer;
  musicBuffer = new Float32Array(MUSIC_WINDOW_SAMPLES);
  musicBufferPosition = 0;
  musicBusy = true;
  musicWorker.postMessage({
    type: 'analyze',
    generation: musicGeneration,
    buffer: waveform.buffer,
  }, [waveform.buffer]);
}

function collectMusicAudio(input) {
  if (!musicActive || !musicBuffer || !musicContext) return;
  const chunk = resampleChunk(input, musicContext.sampleRate, MUSIC_SAMPLE_RATE);
  let offset = 0;
  while (offset < chunk.length) {
    const available = MUSIC_WINDOW_SAMPLES - musicBufferPosition;
    const count = Math.min(available, chunk.length - offset);
    musicBuffer.set(chunk.subarray(offset, offset + count), musicBufferPosition);
    musicBufferPosition += count;
    offset += count;
    if (musicBufferPosition === MUSIC_WINDOW_SAMPLES) {
      if (!musicBusy && musicWorkerReady) submitMusicWindow();
      else {
        musicBuffer = new Float32Array(MUSIC_WINDOW_SAMPLES);
        musicBufferPosition = 0;
      }
    }
  }
}

async function startCrowdMusicAnalysis(stream = window.stream) {
  if (musicActive) return;
  if (!stream || !stream.getAudioTracks().some((track) => track.readyState === 'live')) {
    musicStatus('SIN MICRÓFONO');
    return;
  }
  if (!window.AudioWorkletNode) {
    musicStatus('NAVEGADOR NO COMPATIBLE');
    musicDetails('La grabación y el detector de voz continúan normalmente.');
    return;
  }

  const generation = ++musicGeneration;
  musicActive = true;
  musicBusy = false;
  musicWarningStreak = 0;
  musicWarningActive = false;
  musicStatus('INICIANDO ANÁLISIS');

  try {
    const modelPromise = preloadCrowdMusicModel();
    const track = stream.getAudioTracks().find((item) => item.readyState === 'live');
    musicTrack = track.clone();
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error('AudioContext no está disponible.');
    musicContext = new AudioContextClass();
    await musicContext.audioWorklet.addModule(AUDIO_WORKLET_URL);
    if (generation !== musicGeneration || !musicActive) return;

    musicSource = musicContext.createMediaStreamSource(new MediaStream([musicTrack]));
    musicWorklet = new AudioWorkletNode(musicContext, 'crowd-audio-capture', {
      numberOfInputs: 1,
      numberOfOutputs: 1,
      channelCount: 1,
      processorOptions: { chunkSize: 4096 },
    });
    musicSilentGain = musicContext.createGain();
    musicSilentGain.gain.value = 0;
    musicWorklet.port.onmessage = (event) => collectMusicAudio(event.data);
    musicSource.connect(musicWorklet);
    musicWorklet.connect(musicSilentGain);
    musicSilentGain.connect(musicContext.destination);
    musicBuffer = new Float32Array(MUSIC_WINDOW_SAMPLES);
    musicBufferPosition = 0;
    await musicContext.resume();
    await modelPromise;
    if (generation !== musicGeneration || !musicActive) return;
    musicStatus('ANALIZANDO');
    musicDetails('Clasificación en segundo plano cada 5 segundos.');
  } catch (error) {
    if (generation !== musicGeneration) return;
    console.error('[MUSIC] No se pudo iniciar:', error);
    musicStatus('ANÁLISIS NO DISPONIBLE');
    musicDetails('La grabación y el detector de voz continúan normalmente.');
    if (window.CrowdAudioSession) {
      window.CrowdAudioSession.log('music_monitor_error', String(error.message || error));
    }
    await stopCrowdMusicAnalysis('error');
  }
}

async function stopCrowdMusicAnalysis(reason = 'finalizado') {
  ++musicGeneration;
  musicActive = false;
  musicBusy = false;
  musicWarningStreak = 0;
  musicWarningActive = false;
  hideMusicAlert();

  if (musicWorklet) musicWorklet.port.onmessage = null;
  for (const node of [musicSource, musicWorklet, musicSilentGain]) {
    if (node) {
      try { node.disconnect(); } catch (error) { console.warn('[MUSIC]', error); }
    }
  }
  if (musicTrack && musicTrack.readyState === 'live') musicTrack.stop();
  const context = musicContext;
  musicTrack = null;
  musicContext = null;
  musicSource = null;
  musicWorklet = null;
  musicSilentGain = null;
  musicBuffer = null;
  musicBufferPosition = 0;
  if (context && context.state !== 'closed') {
    try { await context.close(); } catch (error) { console.warn('[MUSIC]', error); }
  }
  if (reason === 'finalizado') musicStatus('TAREA FINALIZADA');
  if (reason === 'manual') musicStatus('DETENIDO');
}

window.preloadCrowdMusicModel = preloadCrowdMusicModel;
window.startCrowdMusicAnalysis = startCrowdMusicAnalysis;
window.stopCrowdMusicAnalysis = stopCrowdMusicAnalysis;

void preloadCrowdMusicModel().catch(() => {});
