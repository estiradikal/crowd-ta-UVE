'use strict';

(() => {
  const CLIENT_VERSION = '2.0.0';
  const ENDPOINT = '/audio-monitoring/';
  const FLUSH_INTERVAL_MS = 30000;
  const MAX_EVENTS = 250;

  let state = null;
  let flushTimer = null;
  let flushPromise = null;

  function getCookie(name) {
    if (!document.cookie) return null;
    const prefix = `${name}=`;
    const cookie = document.cookie.split(';')
      .map((entry) => entry.trim())
      .find((entry) => entry.startsWith(prefix));
    return cookie ? decodeURIComponent(cookie.slice(prefix.length)) : null;
  }

  function newSessionId() {
    if (window.crypto && typeof window.crypto.randomUUID === 'function') {
      return window.crypto.randomUUID();
    }
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
      const random = Math.floor(Math.random() * 16);
      const value = character === 'x' ? random : ((random & 0x3) | 0x8);
      return value.toString(16);
    });
  }

  function initialMetrics() {
    return {
      durationSeconds: 0,
      speechSeconds: 0,
      silenceSeconds: 0,
      noiseSeconds: 0,
      averageSpeechProbability: 0,
      longestSilenceSeconds: 0,
      speechEvents: 0,
      nonSpeechEvents: 0,
      vadAlerts: 0,
      musicAlerts: 0,
      singingAlerts: 0,
      lastAudioLabel: '',
    };
  }

  function updateSyncStatus(value) {
    const element = document.getElementById('audio-sync-status');
    if (element) element.textContent = value;
  }

  function eventSeconds() {
    if (!state) return 0;
    return Math.max(0, (performance.now() - state.startedAt) / 1000);
  }

  function buildPayload(final = false) {
    return {
      session_id: state.sessionId,
      task_id: state.taskId,
      client_version: CLIENT_VERSION,
      client_timezone: state.timezone,
      client_utc_offset_minutes: state.utcOffsetMinutes,
      final,
      metrics: state.metrics,
      events: state.events,
    };
  }

  async function flush(final = false, keepalive = false) {
    if (!state) return null;
    if (flushPromise && !final) return flushPromise;

    const payload = JSON.stringify(buildPayload(final));
    updateSyncStatus('GUARDANDO');
    const request = fetch(ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      keepalive,
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCookie('csrftoken') || '',
      },
      body: payload,
    }).then((response) => {
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      updateSyncStatus(final ? 'FINALIZADO' : 'GUARDADO');
      state.dirty = false;
      return response.json();
    }).catch((error) => {
      console.error('[AUDIO SESSION] No se pudieron guardar las métricas:', error);
      updateSyncStatus('PENDIENTE');
      return null;
    }).finally(() => {
      if (flushPromise === request) flushPromise = null;
    });

    flushPromise = request;
    return request;
  }

  function start(taskId) {
    if (flushTimer) clearInterval(flushTimer);
    state = {
      sessionId: newSessionId(),
      taskId: String(taskId || ''),
      startedAt: performance.now(),
      timezone: (() => {
        try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ''; }
        catch (error) { return ''; }
      })(),
      utcOffsetMinutes: new Date().getTimezoneOffset(),
      metrics: initialMetrics(),
      events: [],
      dirty: true,
    };
    updateSyncStatus('ACTIVO');
    log('session_started', 'MONITOR INICIADO');
    void flush(false);
    flushTimer = setInterval(() => {
      if (state && state.dirty) void flush(false);
    }, FLUSH_INTERVAL_MS);
    return state.sessionId;
  }

  function log(type, label = '', confidence = null, details = {}) {
    if (!state) return;
    state.events.push({
      type: String(type).slice(0, 64),
      label: String(label).slice(0, 128),
      at_seconds: Number(eventSeconds().toFixed(2)),
      confidence: Number.isFinite(confidence) ? Math.max(0, Math.min(1, confidence)) : null,
      details,
    });
    if (state.events.length > MAX_EVENTS) {
      state.events.splice(0, state.events.length - MAX_EVENTS);
    }
    state.dirty = true;
  }

  function setMetrics(metrics) {
    if (!state || !metrics) return;
    Object.assign(state.metrics, metrics);
    state.dirty = true;
  }

  function increment(metricName, amount = 1) {
    if (!state || !(metricName in state.metrics)) return;
    state.metrics[metricName] = Number(state.metrics[metricName] || 0) + amount;
    state.dirty = true;
  }

  async function finish(metrics = {}) {
    if (!state) return null;
    if (flushPromise) await flushPromise;
    setMetrics(metrics);
    state.metrics.durationSeconds = Math.max(
      Number(state.metrics.durationSeconds || 0),
      Math.round(eventSeconds()),
    );
    log('session_finished', 'MONITOR FINALIZADO');
    if (flushTimer) {
      clearInterval(flushTimer);
      flushTimer = null;
    }
    const result = await flush(true);
    return result;
  }

  window.addEventListener('pagehide', () => {
    if (state && state.dirty) void flush(false, true);
  });

  window.CrowdAudioSession = {
    start,
    log,
    setMetrics,
    increment,
    flush,
    finish,
    getSessionId: () => state ? state.sessionId : null,
  };
})();
