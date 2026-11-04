'use strict';

const LIBRARY_URL = 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1';
const MODEL_ID = 'Xenova/ast-finetuned-audioset-10-10-0.4593';

let classifier = null;
let loadingPromise = null;

function categoryScore(predictions, patterns) {
  return predictions.reduce((best, item) => {
    const label = String(item.label || '');
    if (patterns.some((pattern) => pattern.test(label))) {
      return Math.max(best, Number(item.score) || 0);
    }
    return best;
  }, 0);
}

function summarize(predictions) {
  const singing = categoryScore(predictions, [
    /\bsinging\b/i, /\bchoir\b/i, /\brapping\b/i, /vocal music/i,
  ]);
  const music = categoryScore(predictions, [
    /^music$/i, /\bbackground music\b/i, /\bmusical\b/i,
    /\binstrumental\b/i, /\bsoundtrack\b/i, /\bmelody\b/i,
    /\bguitar\b/i, /\bpiano\b/i, /\bdrum/i, /\borchestra/i,
  ]);
  const speech = categoryScore(predictions, [
    /^speech$/i, /\bconversation\b/i, /\bnarration\b/i,
    /\bmonologue\b/i, /\bspeaking\b/i,
  ]);

  let label = 'AUDIO NO DETERMINADO';
  let confidence = Math.max(singing, music, speech);
  if (singing >= 0.12 && singing >= music) {
    label = 'CANTO PROBABLE';
    confidence = singing;
  } else if (music >= 0.15) {
    label = 'MÚSICA PROBABLE';
    confidence = music;
  } else if (speech >= 0.15) {
    label = 'HABLA PROBABLE';
    confidence = speech;
  }
  return { label, confidence, scores: { singing, music, speech } };
}

async function loadModel() {
  if (classifier) return classifier;
  if (loadingPromise) return loadingPromise;

  loadingPromise = (async () => {
    const { pipeline, env } = await import(LIBRARY_URL);
    env.allowLocalModels = false;
    env.useBrowserCache = true;
    if ('useWasmCache' in env) env.useWasmCache = true;
    classifier = await pipeline('audio-classification', MODEL_ID, {
      dtype: 'q4',
      device: 'wasm',
      progress_callback: (progress) => {
        if (progress && progress.status === 'progress') {
          self.postMessage({
            type: 'progress',
            progress: Number(progress.progress) || 0,
          });
        }
      },
    });
    self.postMessage({ type: 'ready' });
    return classifier;
  })().catch((error) => {
    loadingPromise = null;
    self.postMessage({ type: 'error', stage: 'load', message: String(error.message || error) });
    throw error;
  });
  return loadingPromise;
}

self.onmessage = async (event) => {
  const message = event.data || {};
  if (message.type === 'load') {
    try { await loadModel(); } catch (error) { /* informado arriba */ }
    return;
  }
  if (message.type !== 'analyze') return;

  try {
    const model = await loadModel();
    const waveform = new Float32Array(message.buffer);
    const predictions = await model(waveform, { top_k: 40 });
    const entries = Array.isArray(predictions) ? predictions : [];
    self.postMessage({
      type: 'result',
      generation: message.generation,
      summary: summarize(entries),
      predictions: entries.slice(0, 5).map((item) => ({
        label: String(item.label || '').slice(0, 96),
        score: Number(item.score) || 0,
      })),
    });
  } catch (error) {
    self.postMessage({
      type: 'error',
      stage: 'inference',
      generation: message.generation,
      message: String(error.message || error),
    });
  }
};
