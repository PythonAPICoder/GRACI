"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const UI_SOURCE = path.resolve(__dirname, "..", "graci", "visualizer_ui", "visualizer.js");

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, decline) => {
    resolve = accept;
    reject = decline;
  });
  return {promise, resolve, reject};
}

function element(classNames = []) {
  const listeners = new Map();
  const attributes = new Map();
  const styleValues = new Map();
  const classes = new Set(classNames);
  const dataKey = name => name.slice(5).replace(/-([a-z])/g, (_match, letter) => letter.toUpperCase());
  const node = {
    className: "",
    innerHTML: "",
    textContent: "",
    dataset: {},
    hidden: true,
    disabled: false,
    title: "",
    children: [],
    style: {
      values: styleValues,
      setProperty(name, value) { styleValues.set(name, String(value)); },
      removeProperty(name) { styleValues.delete(name); },
      getPropertyValue(name) { return styleValues.get(name) || ""; },
    },
    classList: {
      add(...names) { names.forEach(name => classes.add(name)); },
      remove(...names) { names.forEach(name => classes.delete(name)); },
      contains(name) { return classes.has(name); },
      toggle(name, force) {
        const enabled = force === undefined ? !classes.has(name) : Boolean(force);
        if (enabled) classes.add(name); else classes.delete(name);
        return enabled;
      },
    },
    setAttribute(name, value) {
      attributes.set(name, String(value));
      if (name.startsWith("data-")) this.dataset[dataKey(name)] = String(value);
    },
    removeAttribute(name) {
      attributes.delete(name);
      if (name.startsWith("data-")) delete this.dataset[dataKey(name)];
    },
    getAttribute(name) { return attributes.get(name) ?? null; },
    addEventListener(name, callback) {
      if (!listeners.has(name)) listeners.set(name, new Set());
      listeners.get(name).add(callback);
    },
    removeEventListener(name, callback) { listeners.get(name)?.delete(callback); },
    dispatchEvent(event) {
      const value = typeof event === "string" ? {type: event, target: this} : event;
      for (const callback of listeners.get(value.type) || []) callback(value);
    },
    appendChild(child) { this.children.push(child); return child; },
    getBoundingClientRect() { return {left: 0, top: 0, width: 1, height: 1}; },
    closest() { return null; },
    querySelector: () => element(),
    querySelectorAll: () => [],
  };
  return node;
}

function createHarness({hash = "#processing-audio-diagnostics", reducedMotion = false,
  uiSounds = "on"} = {}) {
  let clock = 1000;
  let timerClock = 0;
  let nextTimerId = 1;
  const timers = new Map();
  const timerHistory = new Map();
  const events = [];
  const audioContexts = [];
  const analysers = [];
  const oscillators = [];
  let contextPlan = {state: "running", resumeGate: null};

  const setTimeoutFake = (callback, delay) => {
    const record = {
      id: nextTimerId++, callback, delay, dueAt: timerClock + delay,
      cleared: false, fired: false,
    };
    timers.set(record.id, record);
    timerHistory.set(record.id, record);
    events.push(`timer-set:${delay}`);
    return record.id;
  };
  const clearTimeoutFake = (id) => {
    const record = timerHistory.get(id);
    if (record) record.cleared = true;
    timers.delete(id);
    events.push("timer-clear");
  };

  class FakeAudioParam {
    constructor() { this.calls = []; }
    cancelScheduledValues(at) { this.calls.push(["cancel", at]); }
    setValueAtTime(value, at) { this.calls.push(["set", value, at]); }
    exponentialRampToValueAtTime(value, at) { this.calls.push(["ramp", value, at]); }
  }

  class FakeOscillator {
    constructor(context) {
      this.context = context;
      this.frequency = new FakeAudioParam();
      this.listeners = new Map();
      this.connections = [];
      this.stopCalls = [];
      this.started = false;
      this.cancelled = false;
      this.ended = false;
      oscillators.push(this);
    }
    connect(target) { this.connections.push(target); }
    disconnect() { this.disconnected = true; }
    addEventListener(name, callback) { this.listeners.set(name, callback); }
    start(when = this.context.currentTime) {
      this.started = true;
      this.startAt = when;
      events.push("oscillator-start");
    }
    stop(when = this.context.currentTime) {
      this.stopCalls.push(when);
      events.push(when <= this.context.currentTime ? "oscillator-stop-now" : "oscillator-stop-scheduled");
      if (when <= this.context.currentTime && !this.cancelled) {
        this.cancelled = true;
        this.finish();
      }
    }
    finish() {
      if (this.ended) return;
      this.ended = true;
      this.listeners.get("ended")?.({type: "ended", target: this});
    }
  }

  class FakeGain {
    constructor(context) {
      this.context = context;
      this.gain = new FakeAudioParam();
      this.connections = [];
    }
    connect(target) { this.connections.push(target); }
    disconnect() { this.disconnected = true; }
  }

  class FakeStereoPanner {
    constructor(context) {
      this.context = context;
      this.pan = new FakeAudioParam();
      this.connections = [];
    }
    connect(target) { this.connections.push(target); }
    disconnect() { this.disconnected = true; }
  }

  class FakeAudioContext {
    constructor() {
      this.state = contextPlan.state;
      this.currentTime = 4;
      this.resumeGate = contextPlan.resumeGate;
      this.destination = {};
      this.sampleRate = 48000;
      this.gains = [];
      this.panners = [];
      audioContexts.push(this);
    }
    createOscillator() { return new FakeOscillator(this); }
    createGain() {
      const gain = new FakeGain(this);
      this.gains.push(gain);
      return gain;
    }
    createStereoPanner() {
      const panner = new FakeStereoPanner(this);
      this.panners.push(panner);
      return panner;
    }
    createMediaElementSource() { return {connect() {}, disconnect() {}}; }
    createAnalyser() {
      const analyser = {
        connect() {},
        frequencyBinCount: 256,
        getByteFrequencyData() {},
        fftSize: 0,
        smoothingTimeConstant: 0,
      };
      analysers.push(analyser);
      return analyser;
    }
    createMediaStreamSource() { return {connect() {}}; }
    createScriptProcessor() { return {connect() {}, disconnect() {}, onaudioprocess: null}; }
    async resume() {
      events.push("context-resume");
      if (this.resumeGate) await this.resumeGate.promise;
      this.state = "running";
    }
    async suspend() { this.state = "suspended"; }
    async close() { this.state = "closed"; }
  }

  class FakeAudio {
    constructor() {
      this.listeners = new Map();
      this.paused = true;
    }
    addEventListener(name, callback) { this.listeners.set(name, callback); }
    removeAttribute() {}
    pause() { this.paused = true; }
    async play() {
      events.push("audio-play");
      this.paused = false;
    }
  }

  const body = element();
  body.dataset.connection = "live";
  body.dataset.systemState = "idle";
  const documentElement = element();
  const packetGroups = new Map();
  for (let route = 1; route <= 14; route += 1) {
    const group = element(["circuit-packet", `packet-${route}`]);
    const far = element(["packet-trail", "packet-trail-far"]);
    const near = element(["packet-trail", "packet-trail-near"]);
    const head = element(["packet-head"]);
    group.children.push(far, near, head);
    group.querySelector = selector => selector === ".packet-head" ? head : null;
    group.querySelectorAll = selector => selector === "path" ? [far, near, head] : [];
    packetGroups.set(route, {group, far, near, head});
  }
  const processingPanel = element();
  const auditionButton = element();
  const elements = new Map([
    ["processing-audio-test-panel", processingPanel],
    ["thinking-pulse-audition", auditionButton],
  ]);
  let createdSvgElements = 0;
  const document = {
    hidden: false,
    body,
    documentElement,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, element());
      return elements.get(id);
    },
    querySelector(selector) {
      const packet = String(selector).match(/^\.circuit-packet\.packet-(\d+)$/);
      if (packet) return packetGroups.get(Number(packet[1]))?.group || null;
      return element();
    },
    querySelectorAll: () => [],
    createElementNS() { createdSvgElements += 1; return element(); },
    createElement: () => element(),
    addEventListener() {},
  };

  const response = (value, blob = null) => ({
    ok: true,
    status: 200,
    async json() { return value; },
    async blob() { return blob ?? new Blob(["RIFF"]); },
  });
  const fetchFake = async (url, options = {}) => {
    const value = String(url);
    events.push(`fetch:${value}`);
    if (value.endsWith("/speech/available")) {
      return response({audio: {artifact_id: "artifact-1"}});
    }
    if (value.endsWith("/speech/claim")) {
      return response({artifact_id: "artifact-1", claim_token: "claim-1"});
    }
    if (value.includes("/speech/audio/")) return response({}, new Blob(["RIFF"]));
    if (value.endsWith("/speech/lifecycle")) return response({});
    throw new Error(`unexpected fetch: ${value} ${options.method || "GET"}`);
  };

  const window = {
    location: {hash},
    AudioContext: FakeAudioContext,
    webkitAudioContext: null,
    addEventListener() {},
    matchMedia: () => ({matches: reducedMotion, addEventListener() {}}),
  };
  const url = {
    createObjectURL() { return "blob:audio"; },
    revokeObjectURL() {},
  };
  const sandbox = {
    window,
    document,
    localStorage: {getItem: () => uiSounds, setItem() {}},
    crypto: {getRandomValues(array) { array.fill(7); return array; }},
    performance: {now: () => ++clock},
    setTimeout: setTimeoutFake,
    clearTimeout: clearTimeoutFake,
    setInterval: () => 1,
    clearInterval() {},
    requestAnimationFrame: () => 1,
    cancelAnimationFrame() {},
    getComputedStyle: () => ({getPropertyValue: () => "0"}),
    fetch: fetchFake,
    Audio: FakeAudio,
    URL: url,
    Blob,
    Uint8Array,
    Uint32Array,
    Float32Array,
    ArrayBuffer,
    DataView,
    Math,
    Date,
    Object,
    JSON,
    Number,
    String,
    Promise,
    console,
  };
  window.window = window;

  let source = fs.readFileSync(UI_SOURCE, "utf8");
  const injection = `
  window.__schedulerTestExports = {
    sound, playback, state, ptt, processingAudioDiagnostics,
    UI_SOUND_CONFIRMATION, THINKING_PULSE_DATA_CHATTER, THINKING_PULSE_LIMITS,
    THINKING_PULSE_PROFILES, THINKING_PULSE_EVENT_TYPES, THINKING_PULSE_OSCILLATORS,
    THINKING_PULSE_PROCESSING_STATES, THINKING_PULSE_STOP_EVENTS,
    THINKING_PULSE_START_EVENTS,
    thinkingPulse, thinkingPulseColor, createThinkingPulseEvent,
    createThinkingPulseGenerator, nextDataChatterEvent, buildThinkingPulseAuditionEvents,
    launchThinkingPulseVisual, clearThinkingPulseVisual, clearAllThinkingPulseVisuals,
    dispatchThinkingPulseEvent, thinkingPulseAudioProfile,
    thinkingPulseAuditionBlockReason, playThinkingPulseAudition,
    cancelThinkingPulseAudition, installProcessingAudioDiagnostics,
    processingSoundMode, processingEntryBlockReason, processingSoundBlockReason,
    armProcessingAudio, cancelProcessingSounds, stopActiveProcessingCues,
    startProcessingCue, queueProcessingPulse, scheduleProcessingSound,
    updateProcessingSounds, diagnosticCueBlockReason, queueSnapshotRefresh,
    thinkingPulseStopFenceReason, updateThinkingPulseStopFence,
    uiSoundsConfirmationBlockReason, playUiSoundsConfirmation,
    playProcessingAudioTest, claimAvailableSpeech, markDisconnected,
    endPresentationSession, installPresentation
  };
`;
  source = source.replace(/\n  start\(\);\r?\n\}\)\(\);\s*$/, `${injection}\n})();`);
  assert.match(source, /__schedulerTestExports/, "test export injection failed");
  vm.runInNewContext(source, sandbox, {filename: UI_SOURCE});
  const api = window.__schedulerTestExports;
  assert.ok(api, "scheduler test exports were not installed");

  return {
    api,
    window,
    document,
    events,
    oscillators,
    audioContexts,
    analysers,
    packetGroups,
    createdSvgElements: () => createdSvgElements,
    finishScheduledOscillators() {
      oscillators.filter(item => item.started && !item.ended).forEach(item => item.finish());
    },
    timers: {
      pending: () => [...timers.values()],
      history: () => [...timerHistory.values()],
      fire(id) {
        const record = timerHistory.get(id);
        assert.ok(record, `unknown timer ${id}`);
        assert.equal(record.fired, false, `timer ${id} fired more than once`);
        assert.equal(record.cleared, false, `timer ${id} fired after cancellation`);
        record.fired = true;
        timers.delete(id);
        timerClock = Math.max(timerClock, record.dueAt);
        return record.callback();
      },
      next() {
        return [...timers.values()].sort((left, right) =>
          left.dueAt - right.dueAt || left.id - right.id)[0] || null;
      },
      now: () => timerClock,
    },
    planContext(plan) { contextPlan = plan; },
    makeContext(plan = {state: "running", resumeGate: null}) {
      const previous = contextPlan;
      contextPlan = plan;
      const context = new FakeAudioContext();
      contextPlan = previous;
      return context;
    },
  };
}

function qwenSnapshot() {
  return {
    system_state: "reasoning",
    agents: {qwen: {state: "active"}, glm: {state: "inactive"}},
    task: {task_id: "turn-1"},
  };
}

function glmSnapshot() {
  return {
    system_state: "reviewing",
    agents: {qwen: {state: "completed"}, glm: {state: "active"}},
    task: {task_id: "turn-review"},
  };
}

function idleSnapshot() {
  return {
    system_state: "idle",
    agents: {qwen: {state: "inactive"}, glm: {state: "inactive"}},
    task: {task_id: null},
  };
}

function snapshotFor(systemState) {
  return {
    system_state: systemState,
    agents: {qwen: {state: "inactive"}, glm: {state: "inactive"}},
    task: {task_id: "transition-turn"},
  };
}

async function flush() {
  await Promise.resolve();
  await Promise.resolve();
}

function closeTo(actual, expected, message) {
  assert.ok(Math.abs(actual - expected) < 1e-9,
    `${message}: expected ${expected}, received ${actual}`);
}

const plain = value => JSON.parse(JSON.stringify(value));
const hue = color => {
  const match = color.match(/^hsl\((\d+) 96% (?:66|70)%\)$/);
  assert.ok(match, `unexpected Thinking Pulse color ${color}`);
  return Number(match[1]);
};
const activeCue = h => [...h.api.sound.activeCues][0] || null;
const productionDiagnostics = (h, stage) => h.api.processingAudioDiagnostics.filter(
  item => item.stage === stage && (item.source === undefined || item.source === "production"));

async function fireProductionTimer(h) {
  const id = h.api.sound.timer;
  assert.ok(id !== null, "production scheduler has no pending event timer");
  await h.timers.fire(id);
  await flush();
  return productionDiagnostics(h, "thinking-pulse-dispatched").at(-1);
}

async function startProduction(h, snapshot = qwenSnapshot()) {
  h.api.state.snapshot = snapshot;
  h.document.body.dataset.systemState = snapshot.system_state;
  if (!h.api.sound.context && h.api.sound.enabled) h.api.sound.context = h.makeContext();
  h.api.updateProcessingSounds(snapshot);
  return fireProductionTimer(h);
}

async function assertDiagnosticVoiceGraph(mode) {
  const h = createHarness();
  const context = h.makeContext();
  h.api.sound.context = context;
  assert.equal(await h.api.playProcessingAudioTest(mode), true);
  const cue = activeCue(h);
  assert.ok(cue, `${mode} diagnostic did not create one bounded cue`);
  const expected = mode === "ui-confirmation" ? h.api.UI_SOUND_CONFIRMATION :
    h.api.thinkingPulseAudioProfile(cue.pulseEvent);
  assert.equal(cue.oscillators.length, expected.voices.length);
  assert.equal(context.gains.length, expected.voices.length + 1);
  assert.equal(context.panners.length, expected.voices.length);
  assert.deepEqual(context.gains[0].gain.calls,
    [["set", expected.masterGain || 1, context.currentTime]]);
  assert.equal(context.gains[0].connections[0], context.destination);
  expected.voices.forEach((voice, index) => {
    const oscillator = h.oscillators[index];
    const voiceGain = context.gains[index + 1];
    const panner = context.panners[index];
    const voiceAt = context.currentTime + voice.delay;
    assert.equal(oscillator.type, voice.oscillator);
    assert.deepEqual(oscillator.frequency.calls.map(call => call[0]), ["set", "ramp"]);
    closeTo(oscillator.frequency.calls[0][1], voice.startFrequency,
      `${mode} voice ${index} start frequency`);
    closeTo(oscillator.frequency.calls[1][1], voice.endFrequency,
      `${mode} voice ${index} end frequency`);
    closeTo(oscillator.frequency.calls[1][2], voiceAt + voice.duration,
      `${mode} voice ${index} full-duration frequency ramp`);
    closeTo(oscillator.startAt, voiceAt, `${mode} voice ${index} start`);
    closeTo(oscillator.stopCalls[0], voiceAt + voice.duration + .006,
      `${mode} voice ${index} stop`);
    assert.deepEqual(voiceGain.gain.calls.map(call => call[0]),
      ["set", "ramp", "ramp", "ramp"]);
    closeTo(voiceGain.gain.calls[1][1], expected.gain * voice.gainRatio,
      `${mode} voice ${index} peak`);
    closeTo(voiceGain.gain.calls[1][2], voiceAt + voice.attack,
      `${mode} voice ${index} attack`);
    closeTo(panner.pan.calls[0][1], voice.pan, `${mode} voice ${index} pan`);
    assert.equal(oscillator.connections[0], voiceGain);
    assert.equal(voiceGain.connections[0], panner);
    assert.equal(panner.connections[0], context.gains[0]);
  });
  assert.equal(h.analysers.length, 0, `${mode} processing created an analyser`);
  return h;
}

async function connectionTrust() {
  const h = createHarness();
  const snapshot = qwenSnapshot();
  h.api.state.snapshot = snapshot;
  h.document.body.dataset.connection = "disconnected";
  h.api.updateProcessingSounds(snapshot);
  assert.equal(h.timers.pending().length, 0, "disconnected state scheduled a processing timer");

  h.document.body.dataset.connection = "live";
  h.api.updateProcessingSounds(snapshot);
  assert.equal(h.timers.pending().length, 1, "trusted live state did not schedule exactly one timer");
  const generation = h.api.sound.generation;

  h.api.markDisconnected();
  assert.equal(h.document.body.dataset.connection, "disconnected");
  assert.equal(h.timers.pending().length, 0, "disconnect left a processing timer pending");
  assert.ok(h.api.sound.generation > generation, "disconnect did not invalidate the timer generation");
  assert.equal(h.api.sound.mode, null, "disconnect retained a processing mode");
}

async function speechClaimCancellation() {
  {
    const h = createHarness();
    const snapshot = qwenSnapshot();
    h.api.state.snapshot = snapshot;
    h.api.updateProcessingSounds(snapshot);
    assert.equal(h.timers.pending().length, 1);
    await h.api.claimAvailableSpeech();
    assert.equal(h.api.sound.timer, null, "speech claim left the pending pulse timer alive");
    assert.equal(h.timers.pending().length, 0, "speech claim left a presentation timer alive");
    assert.ok(h.events.indexOf("timer-clear") < h.events.indexOf("audio-play"),
      "pending chirp was not cancelled before browser playback");
  }

  {
    const h = createHarness();
    const snapshot = qwenSnapshot();
    h.api.state.snapshot = snapshot;
    h.api.sound.context = h.makeContext();
    h.api.updateProcessingSounds(snapshot);
    const dispatched = await fireProductionTimer(h);
    const cue = activeCue(h);
    assert.ok(cue, "fixture did not start an active processing cue");
    assert.equal(cue.eventId, dispatched.eventId);
    const voiceCount = cue.oscillators.length;
    assert.ok(voiceCount === 1 || voiceCount === 2,
      "one Data Chatter event created an unexpected voice count");
    assert.ok(h.api.sound.timer !== null, "fixture did not queue the next pulse event");
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 1);
    await h.api.claimAvailableSpeech();
    assert.equal(h.api.sound.timer, null, "speech claim left the successor timer alive");
    assert.equal(h.timers.pending().length, 0, "speech claim left visual cleanup pending");
    assert.equal(h.api.sound.activeCues.size, 0, "speech claim left an active pulse node alive");
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0,
      "speech claim left processing traffic visible");
    assert.equal(h.events.filter(item => item === "oscillator-stop-now").length, voiceCount,
      "speech claim did not stop every Data Chatter voice");
    assert.ok(h.oscillators.every(item => item.cancelled),
      "speech claim left at least one Data Chatter oscillator running");
    assert.ok(h.events.indexOf("oscillator-stop-now") < h.events.indexOf("audio-play"),
      "active pulse was not stopped before browser playback");
    assert.equal(h.analysers.length, 1,
      "browser speech did not remain the sole analyser owner");
  }
}

async function diagnosticPostResumeRecheck() {
  const h = createHarness();
  const gate = deferred();
  h.api.sound.context = h.makeContext({state: "suspended", resumeGate: gate});
  const resultPromise = h.api.playProcessingAudioTest("qwen");
  await flush();
  assert.equal(h.api.sound.testPending, true, "diagnostic did not remain pending across resume");
  h.document.hidden = true;
  gate.resolve();
  const result = await resultPromise;
  assert.equal(result, false, "diagnostic started after its safety conditions changed");
  assert.equal(h.oscillators.filter(item => item.started).length, 0,
    "diagnostic constructed an oscillator after the tab became hidden");
  assert.equal(h.api.sound.testedModes.has("qwen"), false,
    "blocked diagnostic consumed its one-shot mode allowance");
  assert.equal(h.api.sound.testPending, false, "diagnostic pending latch was not released");
}

async function diagnosticNoOverlap() {
  {
    const h = await assertDiagnosticVoiceGraph("ui-confirmation");
    assert.equal(await h.api.playProcessingAudioTest("qwen"), false,
      "a second exact diagnostic overlapped the active confirmation cue");
    assert.equal(h.oscillators.filter(item => item.started).length, 6,
      "overlap guard allowed more than one exact diagnostic oscillator");
  }

  await assertDiagnosticVoiceGraph("qwen");
  await assertDiagnosticVoiceGraph("glm");

  {
    const h = createHarness();
    const gate = deferred();
    h.api.sound.context = h.makeContext({state: "suspended", resumeGate: gate});
    const first = h.api.playProcessingAudioTest("qwen");
    await flush();
    assert.equal(await h.api.playProcessingAudioTest("glm"), false,
      "a second exact diagnostic overlapped a pending resume");
    gate.resolve();
    assert.equal(await first, true);
    assert.ok([1, 2].includes(h.oscillators.filter(item => item.started).length));
  }
}

async function noOrphanOrDuplicateScheduling() {
  const h = createHarness();
  const snapshot = qwenSnapshot();
  h.api.state.snapshot = snapshot;
  h.api.sound.context = h.makeContext();
  h.api.updateProcessingSounds(snapshot);
  h.api.updateProcessingSounds(snapshot);
  assert.equal(h.timers.pending().length, 1, "duplicate snapshot scheduled duplicate initial timers");

  const firstTimer = h.api.sound.timer;
  await fireProductionTimer(h);
  assert.ok([1, 2].includes(h.oscillators.filter(item => item.started).length));
  assert.notEqual(h.api.sound.timer, firstTimer, "first event did not queue one successor");
  const successor = h.api.sound.timer;
  h.api.updateProcessingSounds(snapshot);
  assert.equal(h.api.sound.timer, successor, "same-mode refresh replaced or duplicated the successor");

  const staleSuccessor = h.timers.history().find(item => item.id === successor);
  const startsBeforeExit = h.oscillators.filter(item => item.started).length;
  const rest = idleSnapshot();
  h.api.state.snapshot = rest;
  h.api.updateProcessingSounds(rest);
  assert.equal(h.api.sound.timer, null, "trusted processing exit retained its scheduler timer");
  assert.equal(h.timers.pending().length, 0,
    "trusted processing exit left scheduler or route cleanup pending");
  await staleSuccessor.callback();
  assert.equal(h.oscillators.filter(item => item.started).length, startsBeforeExit,
    "a cleared stale callback produced an orphan cue");
  assert.equal(h.timers.pending().length, 0, "a cleared stale callback rescheduled itself");

  const race = createHarness();
  const gate = deferred();
  const raceSnapshot = qwenSnapshot();
  race.api.state.snapshot = raceSnapshot;
  race.api.sound.context = race.makeContext({state: "suspended", resumeGate: gate});
  race.api.updateProcessingSounds(raceSnapshot);
  const firing = race.timers.fire(race.api.sound.timer);
  await flush();
  race.api.markDisconnected();
  gate.resolve();
  await firing;
  assert.equal(race.oscillators.filter(item => item.started).length, 0,
    "disconnect during AudioContext resume produced an orphan cue");
  assert.equal(race.timers.pending().length, 0,
    "disconnect during AudioContext resume produced an orphan successor");
}

async function uiConfirmationSuppressionRaces() {
  const transitions = [
    {
      name: "ptt",
      reason: "ptt_starting",
      apply: async h => {
        h.api.cancelProcessingSounds("ptt_start", true);
        h.api.ptt.phase = "starting";
      },
    },
    {
      name: "listening",
      reason: "unsafe_system_state",
      apply: async h => {
        const snapshot = snapshotFor("listening");
        h.api.state.snapshot = snapshot;
        h.document.body.dataset.systemState = "listening";
        h.api.updateProcessingSounds(snapshot);
      },
    },
    {
      name: "playback",
      reason: "browser_playback",
      apply: async h => {
        h.api.playback.artifactId = "claimed-speech";
        h.api.cancelProcessingSounds("browser_playback", true);
      },
    },
    {
      name: "disconnect",
      reason: "resident_disconnected",
      apply: async h => h.api.markDisconnected(),
    },
    {
      name: "session",
      reason: "resident_disconnected",
      apply: async h => {
        const ending = h.api.endPresentationSession();
        assert.equal(h.document.body.dataset.connection, "disconnected",
          "session end did not fail closed synchronously before its first await");
        await ending;
      },
    },
    {
      name: "hidden",
      reason: "hidden_tab",
      apply: async h => {
        h.document.hidden = true;
        h.api.cancelProcessingSounds("hidden_tab", true);
      },
    },
  ];

  for (const transition of transitions) {
    const pre = createHarness();
    pre.api.state.snapshot = idleSnapshot();
    await transition.apply(pre);
    assert.equal(await pre.api.playUiSoundsConfirmation(), false,
      `${transition.name} was not blocked before AudioContext arming`);
    assert.equal(pre.audioContexts.length, 0,
      `${transition.name} created an AudioContext despite pre-arm suppression`);
    assert.equal(pre.oscillators.length, 0,
      `${transition.name} created a pre-arm confirmation oscillator`);
    const preBlock = pre.api.processingAudioDiagnostics.findLast(
      item => item.stage === "ui-confirmation-blocked");
    assert.equal(preBlock.reason, transition.reason, `${transition.name} pre-arm reason`);

    const post = createHarness();
    const gate = deferred();
    post.api.state.snapshot = idleSnapshot();
    post.api.sound.context = post.makeContext({state: "suspended", resumeGate: gate});
    const confirmation = post.api.playUiSoundsConfirmation();
    await flush();
    assert.equal(post.oscillators.length, 0,
      `${transition.name} fixture started before deferred resume completed`);
    await transition.apply(post);
    gate.resolve();
    assert.equal(await confirmation, false,
      `${transition.name} was not rechecked after AudioContext resume`);
    assert.equal(post.oscillators.length, 0,
      `${transition.name} produced a confirmation oscillator after suppression`);
    const postBlock = post.api.processingAudioDiagnostics.findLast(
      item => item.stage === "ui-confirmation-blocked");
    assert.equal(postBlock.reason, transition.reason, `${transition.name} post-resume reason`);
    assert.equal(postBlock.afterResume, true, `${transition.name} lacked post-resume evidence`);
  }
}

async function cueRefreshCancellationBoundaries() {
  {
    const h = createHarness();
    const idle = idleSnapshot();
    h.api.state.snapshot = idle;
    h.api.sound.context = h.makeContext();
    assert.equal(await h.api.playUiSoundsConfirmation(), true);
    const confirmation = activeCue(h);
    assert.equal(confirmation.oscillators.length, 6);
    h.api.updateProcessingSounds(idle);
    assert.equal(activeCue(h), confirmation,
      "benign idle refresh clipped an active UI confirmation");
    assert.equal(h.events.filter(item => item === "oscillator-stop-now").length, 0,
      "benign idle refresh stopped UI confirmation carriers");
    h.api.markDisconnected();
    assert.equal(h.api.sound.activeCues.size, 0,
      "urgent disconnect did not stop the retained UI confirmation");
    assert.equal(h.events.filter(item => item === "oscillator-stop-now").length, 6,
      "urgent disconnect did not stop every UI confirmation carrier");
  }

  for (const safeState of ["idle", "completed", "failed"]) {
    const h = createHarness();
    h.api.state.snapshot = idleSnapshot();
    h.api.sound.context = h.makeContext();
    assert.equal(await h.api.playProcessingAudioTest("qwen"), true);
    const cue = activeCue(h);
    const voiceCount = cue.oscillators.length;
    const snapshot = snapshotFor(safeState);
    h.api.state.snapshot = snapshot;
    h.document.body.dataset.systemState = safeState;
    h.api.updateProcessingSounds(snapshot);
    assert.equal(activeCue(h), cue,
      `${safeState} refresh clipped an active exact diagnostic`);
    assert.equal(h.events.filter(item => item === "oscillator-stop-now").length, 0,
      `${safeState} refresh stopped exact diagnostic carriers`);
  }

  const unsafeStates = ["listening", "warning", "speaking"];
  for (const unsafeState of unsafeStates) {
    const h = createHarness();
    h.api.state.snapshot = idleSnapshot();
    h.api.sound.context = h.makeContext();
    assert.equal(await h.api.playProcessingAudioTest("qwen"), true);
    const voiceCount = activeCue(h).oscillators.length;
    const snapshot = snapshotFor(unsafeState);
    h.api.state.snapshot = snapshot;
    h.document.body.dataset.systemState = unsafeState;
    h.api.updateProcessingSounds(snapshot);
    assert.equal(h.api.sound.activeCues.size, 0,
      `${unsafeState} did not cancel an active exact diagnostic`);
    assert.equal(h.events.filter(item => item === "oscillator-stop-now").length, voiceCount,
      `${unsafeState} did not stop every exact diagnostic carrier`);
  }
}

function assertFrozenCandidateOneProfile(h) {
  const profile = h.api.THINKING_PULSE_DATA_CHATTER;
  const limits = h.api.THINKING_PULSE_LIMITS;
  const profiles = h.api.THINKING_PULSE_PROFILES;
  assert.equal(Object.isFrozen(profile), true);
  assert.equal(Object.isFrozen(limits), true);
  assert.equal(Object.isFrozen(profiles), true);
  assert.equal(profile.id, "data-chatter");
  assert.equal(profile.seed, 7481201);
  assert.equal(profile.masterGain, 2.1960059);
  assert.deepEqual(plain(profile.baseFrequencyHz), [1250, 6100]);
  assert.equal(profile.maximumRenderedFrequencyHz, 10500);
  assert.deepEqual(plain(profile.oscillators), [
    {value: "sine", weight: .56},
    {value: "triangle", weight: .30},
    {value: "square", weight: .14},
  ]);
  assert.deepEqual(plain(profile.eventTypes), [
    {value: "click", weight: .50},
    {value: "pip", weight: .35},
    {value: "sweep", weight: .10},
    {value: "dual", weight: .05},
  ]);
  assert.deepEqual(plain(profile.durationMs), {
    click: [20, 44], pip: [32, 78], sweep: [52, 116], dual: [54, 108],
  });
  assert.deepEqual(plain(profile.eventGain), [.10, .25]);
  assert.deepEqual(plain(profile.clusterSizes), [
    {value: 1, weight: .18}, {value: 2, weight: .22},
    {value: 3, weight: .23}, {value: 4, weight: .18},
    {value: 5, weight: .12}, {value: 6, weight: .07},
  ]);
  assert.deepEqual(plain(profile.initialDelayMs), [80, 150]);
  assert.deepEqual(plain(profile.intraClusterSpacingMs), [22, 64]);
  assert.deepEqual(plain(profile.postClusterSilenceMs), [65, 210]);
  assert.deepEqual(plain(profile.sweepDownRatio), [.62, .84]);
  assert.deepEqual(plain(profile.sweepUpRatio), [1.18, 1.48]);
  assert.equal(profile.sweepUpProbability, .48);
  assert.deepEqual(plain(profile.dualToneRatio), [1.31, 1.71]);
  assert.deepEqual(plain(profile.dualSecondaryGain), [.26, .42]);
  assert.equal(profile.dualUpperProbability, .62);
  assert.deepEqual(plain(profile.pan), [-.18, .18]);
  assert.equal(profile.auditionDurationMs, 10000);
  assert.deepEqual(plain(limits), {
    frequencyMin: 1250, frequencyMax: 6100,
    renderedFrequencyMin: 90, renderedFrequencyMax: 10500,
    gainMin: .10, gainMax: .25,
    audioDurationMin: .02, audioDurationMax: .116,
    packetDurationMin: 1350, packetDurationMax: 2350,
    spacingMin: 22, spacingMax: 326,
    panMin: -.18, panMax: .18, routeCount: 14, maxActiveCues: 6,
  });
  assert.deepEqual(plain(profiles), {
    qwen: {
      colorHues: [168, 186, 202, 222, 252, 288, 322, 28],
      direction: "forward", routes: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
    },
    glm: {
      colorHues: [254, 264, 276, 288, 302], direction: "reverse",
      routes: [1, 2, 4, 5, 7, 8, 10, 12, 14],
    },
  });
  assert.deepEqual(plain(h.api.THINKING_PULSE_EVENT_TYPES).sort(),
    ["click", "dual", "pip", "sweep"]);
  assert.deepEqual(plain(h.api.THINKING_PULSE_OSCILLATORS).sort(),
    ["sine", "square", "triangle"]);

  const low = h.api.createThinkingPulseEvent({
    profile: "qwen", type: "invalid", oscillator: "invalid",
    spacingMs: -1, frequency: -1, endFrequency: -1, gain: -1,
    audioDuration: -1, pan: -1, route: -1, attack: -1,
  }, 0, -1);
  const high = h.api.createThinkingPulseEvent({
    profile: "qwen", spacingMs: 999999, frequency: 999999,
    endFrequency: 999999, gain: 999999, audioDuration: 999999,
    pan: 999999, route: 999999, attack: 999999,
  }, 1, 25);
  assert.equal(Object.isFrozen(low), true);
  assert.equal(low.type, "pip");
  assert.equal(low.oscillator, "sine");
  assert.equal(low.frequency, limits.frequencyMin);
  assert.equal(high.frequency, limits.frequencyMax);
  assert.equal(low.endFrequency, limits.renderedFrequencyMin);
  assert.equal(high.endFrequency, limits.renderedFrequencyMax);
  assert.equal(low.gain, limits.gainMin);
  assert.equal(high.gain, limits.gainMax);
  assert.equal(low.audioDuration, limits.audioDurationMin);
  assert.equal(high.audioDuration, limits.audioDurationMax);
  assert.equal(low.spacingMs, limits.spacingMin);
  assert.equal(high.spacingMs, limits.spacingMax);
  assert.equal(low.pan, limits.panMin);
  assert.equal(high.pan, limits.panMax);
  assert.equal(low.route, 1);
  assert.equal(high.route, limits.routeCount);
  assert.equal(low.attack, .0004);
  assert.equal(high.attack, .006);
  assert.equal(low.launchAtMs, 0);
  assert.equal(high.launchAtMs, 25);
  assert.equal(low.packetDurationMs, limits.packetDurationMax);
  assert.equal(high.packetDurationMs, limits.packetDurationMin);
  assert.equal(low.color, "hsl(168 96% 66%)");
  assert.equal(high.color, "hsl(28 96% 66%)");
  assert.equal(low.direction, "forward");
  assert.equal(high.direction, "forward");
  const glmLow = h.api.createThinkingPulseEvent({...plain(low), profile: "glm"}, 2, 0);
  const glmHigh = h.api.createThinkingPulseEvent({...plain(high), profile: "glm"}, 3, 0);
  assert.equal(glmLow.color, "hsl(254 96% 70%)");
  assert.equal(glmHigh.color, "hsl(302 96% 70%)");
  assert.equal(glmLow.direction, "reverse");
  assert.equal(glmHigh.direction, "reverse");
}

async function dataChatterProfileAndDeterminism() {
  const h = createHarness();
  assertFrozenCandidateOneProfile(h);
  const left = h.api.createThinkingPulseGenerator("deterministic-turn|qwen");
  const right = h.api.createThinkingPulseGenerator("deterministic-turn|qwen");
  const other = h.api.createThinkingPulseGenerator("different-turn|qwen");
  assert.ok(left.initialDelayMs >= 80 && left.initialDelayMs <= 150);
  assert.equal(left.initialDelayMs, right.initialDelayMs);
  const leftEvents = [];
  const rightEvents = [];
  const otherEvents = [];
  for (let index = 0; index < 280; index += 1) {
    leftEvents.push(h.api.nextDataChatterEvent(left, "qwen", index));
    rightEvents.push(h.api.nextDataChatterEvent(right, "qwen", index));
    otherEvents.push(h.api.nextDataChatterEvent(other, "qwen", index));
  }
  assert.deepEqual(plain(leftEvents), plain(rightEvents),
    "same trusted identity did not reproduce the same event stream");
  assert.notDeepEqual(plain(leftEvents.slice(0, 12)), plain(otherEvents.slice(0, 12)),
    "different trusted identities reused an identical event stream");
  assert.deepEqual([...new Set(leftEvents.map(event => event.type))].sort(),
    ["click", "dual", "pip", "sweep"]);
  assert.deepEqual([...new Set(leftEvents.map(event => event.oscillator))].sort(),
    ["sine", "square", "triangle"]);
  leftEvents.forEach(event => {
    const durationBounds = h.api.THINKING_PULSE_DATA_CHATTER.durationMs[event.type];
    assert.ok(event.frequency >= 1250 && event.frequency <= 6100);
    assert.ok(event.endFrequency >= 90 && event.endFrequency <= 10500);
    assert.ok(event.gain >= .10 && event.gain <= .25);
    assert.ok(event.audioDuration * 1000 >= durationBounds[0] - .001);
    assert.ok(event.audioDuration * 1000 <= durationBounds[1] + .001);
    assert.ok(event.spacingMs >= 22 && event.spacingMs <= 326);
    assert.ok(event.pan >= -.18 && event.pan <= .18);
    assert.ok(event.route >= 1 && event.route <= 14);
    assert.ok(event.attack >= .0004 && event.attack <= .006);
    if (event.secondary) {
      assert.equal(event.type, "dual");
      assert.ok(["sine", "triangle"].includes(event.secondary.oscillator));
      assert.ok(event.secondary.gainRatio >= .26 && event.secondary.gainRatio <= .42);
    }
  });
  for (let offset = 0; offset + 14 <= leftEvents.length; offset += 14) {
    assert.deepEqual(leftEvents.slice(offset, offset + 14).map(event => event.route).sort(
      (a, b) => a - b), Array.from({length: 14}, (_value, index) => index + 1));
  }

  const qwenGenerator = h.api.createThinkingPulseGenerator("shared-character");
  const glmGenerator = h.api.createThinkingPulseGenerator("shared-character");
  const qwenEvents = [];
  const glmEvents = [];
  for (let index = 0; index < 80; index += 1) {
    const qwen = h.api.nextDataChatterEvent(qwenGenerator, "qwen", index);
    const glm = h.api.nextDataChatterEvent(glmGenerator, "glm", index);
    qwenEvents.push(qwen);
    glmEvents.push(glm);
    assert.deepEqual(plain(h.api.thinkingPulseAudioProfile(qwen)),
      plain(h.api.thinkingPulseAudioProfile(glm)),
      "GLM changed Candidate 1's fundamental audio character");
    assert.equal(qwen.direction, "forward");
    assert.equal(glm.direction, "reverse");
    assert.ok(hue(glm.color) >= 254 && hue(glm.color) <= 302);
  }
  const qwenHues = qwenEvents.map(event => hue(event.color));
  assert.ok(new Set(qwenHues).size >= 7, "Qwen frequency colors were not substantially varied");
  assert.ok(qwenHues.some(value => value <= 70 || value >= 322));
  assert.ok(qwenHues.some(value => value >= 168 && value < 200));
  assert.ok(qwenHues.some(value => value >= 200 && value < 260));
  assert.ok(new Set(glmEvents.map(event => hue(event.color))).size >= 4,
    "GLM violet bias collapsed to a single color");
  const glmRoutes = h.api.THINKING_PULSE_PROFILES.glm.routes;
  assert.ok(glmEvents.every(event => glmRoutes.includes(event.route)),
    "GLM escaped its approved violet-biased route pool");
  for (let offset = 0; offset + glmRoutes.length <= glmEvents.length;
    offset += glmRoutes.length) {
    assert.deepEqual(glmEvents.slice(offset, offset + glmRoutes.length)
      .map(event => event.route).sort((a, b) => a - b), plain(glmRoutes));
  }

  const audition = h.api.buildThinkingPulseAuditionEvents();
  assert.equal(Object.isFrozen(audition), true);
  assert.ok(audition.length >= 30);
  assert.ok(audition[0].launchAtMs >= 80 && audition[0].launchAtMs <= 150);
  assert.ok(audition.at(-1).launchAtMs >= 9600 && audition.at(-1).launchAtMs < 10000);
  const bins = Array(10).fill(0);
  audition.forEach(event => { bins[Math.min(9, Math.floor(event.launchAtMs / 1000))] += 1; });
  assert.ok(bins.every(count => count > 0), "Candidate 1 activity did not span all ten seconds");
}

async function thinkingPulseEventCoherence() {
  const h = createHarness();
  assertFrozenCandidateOneProfile(h);
  const context = h.makeContext();
  h.api.sound.context = context;
  const generator = h.api.createThinkingPulseGenerator("coherent-event");
  let event = h.api.nextDataChatterEvent(generator, "qwen", 0);
  for (let guard = 0; guard < 80 && !event.secondary; guard += 1) {
    event = h.api.nextDataChatterEvent(generator, "qwen", guard + 1);
  }
  assert.ok(event.secondary, "deterministic fixture did not reach a dual event");
  const profile = h.api.thinkingPulseAudioProfile(event);
  const result = h.api.dispatchThinkingPulseEvent(event, "production");
  assert.equal(result.eventId, event.id);
  assert.equal(result.audioStarted, true);
  assert.equal(result.visualStarted, true);
  assert.equal(result.motionSuppressed, false);
  assert.equal(result.blocked, false);
  assert.equal(h.audioContexts.length, 1, "Thinking Pulse created a second AudioContext");
  assert.equal(h.analysers.length, 0, "Thinking Pulse created a second analyser path");
  assert.equal(h.createdSvgElements(), 0, "Thinking Pulse created a new SVG node");
  assert.equal(h.api.sound.activeCues.size, 1);
  const cue = activeCue(h);
  assert.equal(cue.eventId, event.id);
  assert.equal(cue.context, context);
  assert.equal(cue.oscillators.length, profile.voices.length);
  assert.equal(h.oscillators.length, profile.voices.length);
  assert.equal(context.gains.length, profile.voices.length + 1);
  assert.deepEqual(context.gains[0].gain.calls,
    [["set", h.api.THINKING_PULSE_DATA_CHATTER.masterGain, context.currentTime]]);
  assert.equal(context.gains[0].connections[0], context.destination);
  profile.voices.forEach((voice, index) => {
    const oscillator = h.oscillators[index];
    const voiceGain = context.gains[index + 1];
    assert.equal(oscillator.type, voice.oscillator);
    assert.equal(oscillator.frequency.calls[0][1], voice.startFrequency);
    assert.equal(oscillator.frequency.calls[1][1], voice.endFrequency);
    closeTo(oscillator.frequency.calls[1][2], context.currentTime + voice.delay + voice.duration,
      `voice ${index} full-duration frequency ramp`);
    assert.deepEqual(voiceGain.gain.calls.map(call => call[0]),
      ["set", "ramp", "ramp", "ramp"]);
    closeTo(voiceGain.gain.calls[1][1], event.gain * voice.gainRatio,
      `voice ${index} gain`);
  });

  const activeRoutes = [...h.packetGroups.entries()].filter(
    ([, packet]) => packet.group.dataset.thinkingPulseActive === "true");
  assert.equal(activeRoutes.length, 1,
    "one meaningful audio micro-event did not launch exactly one existing circuit packet");
  const [route, packet] = activeRoutes[0];
  assert.equal(route, event.route);
  assert.equal(packet.group.dataset.thinkingPulseDirection, event.direction);
  assert.equal(packet.group.style.getPropertyValue("--thinking-pulse-color"), event.color);
  assert.equal(packet.group.style.getPropertyValue("--thinking-pulse-duration"),
    `${event.packetDurationMs}ms`);

  const audio = productionDiagnostics(h, "cue-started").at(-1);
  const visual = productionDiagnostics(h, "thinking-pulse-visual-started").at(-1);
  const dispatch = productionDiagnostics(h, "thinking-pulse-dispatched").at(-1);
  assert.equal(audio.eventId, event.id);
  assert.equal(audio.voiceCount, profile.voices.length);
  assert.equal(audio.masterGain, h.api.THINKING_PULSE_DATA_CHATTER.masterGain);
  assert.equal(visual.eventId, event.id);
  assert.equal(visual.route, event.route);
  assert.equal(dispatch.eventId, event.id);
  assert.equal(dispatch.type, event.type);
  assert.equal(dispatch.oscillator, event.oscillator);
  assert.equal(dispatch.route, event.route);
  assert.equal(dispatch.frequency, event.frequency);
  assert.equal(dispatch.color, event.color);
  assert.equal(dispatch.audioStarted, true);
  assert.equal(dispatch.visualStarted, true);

  packet.head.dispatchEvent({
    type: "animationend", target: packet.head, animationName: "unrelated-animation",
  });
  assert.equal(h.api.thinkingPulse.activeVisuals.size, 1);
  packet.head.dispatchEvent({
    type: "animationend", target: packet.head,
    animationName: `thinking-pulse-${event.direction}-head`,
  });
  assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
  assert.equal(packet.group.dataset.thinkingPulseActive, undefined);
  assert.equal(packet.group.style.values.size, 0);
  h.finishScheduledOscillators();
  assert.equal(h.api.sound.activeCues.size, 0);
  assert.equal(context.gains[0].disconnected, true);

  const first = h.api.createThinkingPulseEvent({...plain(event), id: "route-first", route: 4});
  const replacement = h.api.createThinkingPulseEvent({
    ...plain(event), id: "route-replacement", profile: "glm", route: 4,
  });
  assert.equal(h.api.launchThinkingPulseVisual(first), true);
  const stale = h.api.thinkingPulse.activeVisuals.get(4);
  const staleTimer = stale.cleanupTimer;
  assert.equal(h.api.launchThinkingPulseVisual(replacement), true);
  const current = h.api.thinkingPulse.activeVisuals.get(4);
  assert.equal(current.token.eventId, "route-replacement");
  assert.equal(h.timers.history().find(timer => timer.id === staleTimer).cleared, true);
  stale.finish({
    type: "animationend", target: stale.head,
    animationName: "thinking-pulse-forward-head",
  });
  assert.equal(h.api.thinkingPulse.activeVisuals.get(4), current,
    "stale packet completion cleared a newer synchronized event");
  current.finish({
    type: "animationend", target: current.head,
    animationName: "thinking-pulse-reverse-head",
  });
  assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
}

async function thinkingPulseProductionLifecycle() {
  for (const [mode, snapshot, eventCount] of [
    ["qwen", qwenSnapshot(), 14],
    ["glm", glmSnapshot(), 9],
  ]) {
    const h = createHarness();
    h.api.sound.context = h.makeContext();
    h.api.state.snapshot = snapshot;
    h.api.updateProcessingSounds(snapshot);
    const initialTimer = h.api.sound.timer;
    assert.ok(initialTimer !== null);
    h.api.updateProcessingSounds(snapshot);
    assert.equal(h.api.sound.timer, initialTimer,
      `same-mode ${mode} refresh duplicated its scheduler`);
    assert.equal(h.api.thinkingPulse.productionEventCount, 0);
    assert.equal(h.document.body.dataset.thinkingPulseProduction, "true");

    for (let index = 0; index < eventCount; index += 1) {
      const timerBefore = h.api.sound.timer;
      const dispatch = await fireProductionTimer(h);
      assert.ok(dispatch);
      assert.equal(dispatch.profile, mode);
      assert.equal(dispatch.audioStarted, true);
      assert.equal(dispatch.visualStarted, true);
      assert.equal(h.api.thinkingPulse.productionEventCount, index + 1);
      assert.notEqual(h.api.sound.timer, timerBefore);
      const successor = h.api.sound.timer;
      h.api.updateProcessingSounds(snapshot);
      assert.equal(h.api.sound.timer, successor,
        `same-mode ${mode} refresh duplicated successor ${index}`);
      assert.ok(h.api.sound.activeCues.size <= h.api.THINKING_PULSE_LIMITS.maxActiveCues);
      h.finishScheduledOscillators();
    }

    const dispatches = productionDiagnostics(h, "thinking-pulse-dispatched");
    const audio = productionDiagnostics(h, "cue-started");
    const visual = productionDiagnostics(h, "thinking-pulse-visual-started");
    assert.equal(dispatches.length, eventCount);
    assert.equal(audio.length, eventCount);
    assert.equal(visual.length, eventCount);
    assert.deepEqual(audio.map(item => item.eventId), dispatches.map(item => item.eventId));
    assert.deepEqual(visual.map(item => item.eventId), dispatches.map(item => item.eventId));
    if (mode === "qwen") {
      assert.ok(new Set(dispatches.map(item => hue(item.color))).size >= 6);
      assert.deepEqual(plain(dispatches.map(item => item.route).sort((a, b) => a - b)),
        plain(h.api.THINKING_PULSE_PROFILES.qwen.routes));
    } else {
      assert.ok(dispatches.every(item => hue(item.color) >= 254 && hue(item.color) <= 302));
      assert.ok(dispatches.every(item => item.profile === "glm"));
      assert.deepEqual(plain(dispatches.map(item => item.route).sort((a, b) => a - b)),
        plain(h.api.THINKING_PULSE_PROFILES.glm.routes));
    }
    const rest = idleSnapshot();
    h.api.state.snapshot = rest;
    h.api.updateProcessingSounds(rest);
    assert.equal(h.api.sound.timer, null);
    assert.equal(h.api.sound.activeCues.size, 0);
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
    assert.equal(h.timers.pending().length, 0);
  }
}

async function thinkingPulseCancellationBoundaries() {
  for (const stateName of ["idle", "listening", "speaking", "completed", "warning", "failed"]) {
    const h = createHarness();
    await startProduction(h);
    const voiceCount = h.oscillators.length;
    const snapshot = stateName === "idle" ? idleSnapshot() : snapshotFor(stateName);
    h.api.state.snapshot = snapshot;
    h.document.body.dataset.systemState = stateName;
    h.api.updateProcessingSounds(snapshot);
    assert.equal(h.api.sound.timer, null, `${stateName} retained scheduler timer`);
    assert.equal(h.api.sound.pending, false);
    assert.equal(h.api.sound.activeCues.size, 0, `${stateName} retained audio nodes`);
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0,
      `${stateName} retained packet traffic`);
    assert.equal(h.api.thinkingPulse.productionGenerator, null);
    assert.equal(h.document.body.dataset.thinkingPulseProduction, undefined);
    assert.equal(h.timers.pending().length, 0, `${stateName} retained bounded timers`);
    assert.equal(h.events.filter(item => item === "oscillator-stop-now").length, voiceCount);
  }

  for (const phase of ["starting", "capturing"]) {
    const h = createHarness();
    await startProduction(h);
    h.api.ptt.phase = phase;
    h.api.updateProcessingSounds(qwenSnapshot());
    assert.equal(h.api.sound.timer, null, `${phase} PTT retained its scheduler`);
    assert.equal(h.api.sound.activeCues.size, 0, `${phase} PTT retained audio`);
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0,
      `${phase} PTT retained packet traffic`);
    assert.equal(h.timers.pending().length, 0, `${phase} PTT retained timers`);
  }

  for (const [eventType, reason] of Object.entries(plain(
    createHarness().api.THINKING_PULSE_STOP_EVENTS))) {
    const h = createHarness();
    await startProduction(h);
    h.api.queueSnapshotRefresh({
      event_type: eventType, timestamp: "2026-08-31T00:00:00Z", task_id: "turn-stop",
    });
    assert.equal(h.api.sound.timer, null, `${eventType} did not cancel immediately`);
    assert.equal(h.api.sound.activeCues.size, 0);
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
    const cancelled = h.api.processingAudioDiagnostics.findLast(
      item => item.stage === "cue-cancelled");
    assert.equal(cancelled.reason, reason);
    assert.ok(h.api.state.snapshotRefreshTimer !== null,
      `${eventType} did not preserve the bounded snapshot refresh`);
    assert.equal(h.timers.pending().length, 1);
  }
}

async function thinkingPulseStopFenceTransitions() {
  {
    const h = createHarness();
    const qwen = {...qwenSnapshot(), generated_at: "2026-08-31T00:00:00Z"};
    await startProduction(h, qwen);
    h.api.queueSnapshotRefresh({
      event_type: "qwen_completed", timestamp: "2026-08-31T00:00:01Z",
      task_id: "turn-1",
    });
    assert.deepEqual(plain(h.api.sound.stopFence), {
      taskId: "turn-1", mode: "qwen", eventType: "qwen_completed",
      timestamp: "2026-08-31T00:00:01Z",
    });
    assert.equal(h.api.sound.timer, null);
    assert.equal(h.api.thinkingPulseStopFenceReason("qwen", qwen),
      "trusted_stop_qwen_completed");

    h.api.state.snapshot = qwen;
    h.api.updateProcessingSounds(qwen);
    assert.equal(h.api.sound.mode, null,
      "stale same-task Qwen snapshot rearmed after trusted completion");
    assert.equal(h.api.sound.timer, null,
      "stale same-task Qwen snapshot scheduled a new pulse");
    assert.equal(h.api.thinkingPulse.productionGenerator, null);
    assert.equal(h.api.processingAudioDiagnostics.findLast(
      item => item.stage === "cue-suppressed")?.reason,
    "trusted_stop_qwen_completed");

    const glm = {
      ...glmSnapshot(), generated_at: "2026-08-31T00:00:02Z",
      task: {task_id: "turn-1"},
    };
    h.api.queueSnapshotRefresh({
      event_type: "glm_started", timestamp: "2026-08-31T00:00:02Z",
      task_id: "turn-1",
    });
    assert.equal(h.api.thinkingPulseStopFenceReason("glm", glm), null,
      "Qwen completion fence incorrectly blocked same-task GLM review");
    assert.equal(h.api.thinkingPulseStopFenceReason("qwen", qwen),
      "trusted_stop_qwen_completed");
    h.api.state.snapshot = glm;
    h.api.updateProcessingSounds(glm);
    assert.equal(h.api.sound.mode, "glm");
    assert.ok(h.api.sound.timer !== null,
      "same-task trusted GLM start did not arm the review scheduler");
    const dispatch = await fireProductionTimer(h);
    assert.equal(dispatch.profile, "glm");
    assert.ok(hue(dispatch.color) >= 254 && hue(dispatch.color) <= 302);
    h.api.cancelProcessingSounds("completed", true);
  }

  {
    const h = createHarness();
    assert.equal(h.api.updateThinkingPulseStopFence({
      event_type: "review_completed", task_id: "review-turn",
      timestamp: "2026-08-31T00:01:00Z",
    }), "completed");
    assert.equal(h.api.sound.stopFence.mode, "all");
    const staleGlm = {
      ...glmSnapshot(), generated_at: "2026-08-31T00:00:59Z",
      task: {task_id: "review-turn"},
    };
    const staleOtherQwen = {
      ...qwenSnapshot(), generated_at: "2026-08-31T00:00:59Z",
      task: {task_id: "older-autonomous-turn"},
    };
    assert.equal(h.api.thinkingPulseStopFenceReason("glm", staleGlm),
      "trusted_stop_review_completed");
    assert.equal(h.api.thinkingPulseStopFenceReason("qwen", staleOtherQwen),
      "trusted_stop_review_completed");
  }

  for (const generatedAt of [
    "2026-08-31T00:01:59Z", "2026-08-31T00:02:00Z", "invalid", undefined,
  ]) {
    const h = createHarness();
    h.api.updateThinkingPulseStopFence({
      event_type: "qwen_completed", task_id: "completed-turn",
      timestamp: "2026-08-31T00:02:00Z",
    });
    const mismatched = {
      ...qwenSnapshot(), generated_at: generatedAt,
      task: {task_id: "different-turn"},
    };
    assert.equal(h.api.thinkingPulseStopFenceReason("qwen", mismatched),
      "trusted_stop_qwen_completed",
      `mismatched task with ${String(generatedAt)} did not fail closed`);
    assert.ok(h.api.sound.stopFence);
  }

  {
    const h = createHarness();
    h.api.updateThinkingPulseStopFence({
      event_type: "qwen_completed", task_id: "completed-turn",
      timestamp: "2026-08-31T00:02:00Z",
    });
    const strictlyNewer = {
      ...qwenSnapshot(), generated_at: "2026-08-31T00:02:00.001Z",
      task: {task_id: "different-turn"},
    };
    assert.equal(h.api.thinkingPulseStopFenceReason("qwen", strictlyNewer), null);
    assert.equal(h.api.sound.stopFence, null,
      "strictly newer mismatched trusted snapshot did not clear the fence");
  }

  {
    const h = createHarness();
    h.api.updateThinkingPulseStopFence({
      event_type: "qwen_completed", task_id: "iterative-turn",
      timestamp: "2026-08-31T00:03:00Z",
    });
    h.api.updateThinkingPulseStopFence({
      event_type: "qwen_started", task_id: "iterative-turn",
      timestamp: "2026-08-31T00:03:01Z",
    });
    assert.equal(h.api.sound.stopFence, null,
      "same-task explicit Qwen restart did not open a new iteration");

    h.api.updateThinkingPulseStopFence({
      event_type: "task_completed", task_id: "iterative-turn",
      timestamp: "2026-08-31T00:04:00Z",
    });
    assert.equal(h.api.sound.stopFence.mode, "all");
    h.api.updateThinkingPulseStopFence({
      event_type: "task_started", task_id: "iterative-turn",
      timestamp: "2026-08-31T00:04:01Z",
    });
    assert.equal(h.api.sound.stopFence, null,
      "explicit task start did not clear a terminal all-mode fence");
  }
}

async function thinkingPulseUiSoundsAndReducedMotion() {
  {
    const h = createHarness();
    const snapshot = qwenSnapshot();
    const context = h.makeContext();
    h.api.sound.context = context;
    h.api.state.snapshot = snapshot;
    h.api.updateProcessingSounds(snapshot);
    const audibleBeforeOff = await fireProductionTimer(h);
    assert.equal(audibleBeforeOff.audioStarted, true);
    assert.equal(audibleBeforeOff.visualStarted, true);
    const retainedTimer = h.api.sound.timer;
    const retainedGenerator = h.api.thinkingPulse.productionGenerator;

    h.api.installPresentation();
    h.document.getElementById("ui-sounds").dispatchEvent("click");
    await flush();
    assert.equal(h.api.sound.enabled, false);
    assert.equal(context.state, "suspended");
    assert.equal(h.api.sound.activeCues.size, 0);
    assert.equal(h.api.sound.timer, retainedTimer,
      "UI Sounds OFF destroyed the production visual scheduler");
    assert.equal(h.api.thinkingPulse.productionGenerator, retainedGenerator);

    const oscillatorCountWhileOff = h.oscillators.length;
    const silent = await fireProductionTimer(h);
    assert.equal(silent.audioStarted, false);
    assert.equal(silent.visualStarted, true);
    assert.equal(h.oscillators.length, oscillatorCountWhileOff,
      "UI Sounds OFF created a suppressed audio node");
    const successor = h.api.sound.timer;
    assert.ok(successor !== null);

    h.document.getElementById("ui-sounds").dispatchEvent("click");
    await flush();
    assert.equal(h.api.sound.enabled, true);
    assert.equal(context.state, "running");
    assert.equal(h.api.sound.timer, successor,
      "UI Sounds ON duplicated the already-armed scheduler");
    const audibleAfterOn = await fireProductionTimer(h);
    assert.equal(audibleAfterOn.audioStarted, true);
    const startedEventIds = productionDiagnostics(h, "cue-started")
      .map(item => item.eventId);
    assert.deepEqual(plain(startedEventIds),
      [audibleBeforeOff.eventId, audibleAfterOn.eventId],
      "reenabling UI Sounds replayed an event suppressed while OFF");
    assert.ok(!startedEventIds.includes(silent.eventId));
    assert.equal(h.audioContexts.length, 1);
    assert.equal(h.analysers.length, 0);
    h.api.cancelProcessingSounds("completed", true);
    assert.equal(h.timers.pending().length, 0);
  }

  {
    const h = createHarness({uiSounds: "off"});
    const snapshot = qwenSnapshot();
    h.api.state.snapshot = snapshot;
    h.api.updateProcessingSounds(snapshot);
    const first = await fireProductionTimer(h);
    assert.equal(first.audioStarted, false);
    assert.equal(first.visualStarted, true);
    assert.equal(h.audioContexts.length, 0);
    assert.equal(h.oscillators.length, 0);
    h.api.cancelProcessingSounds("completed", true);
  }

  {
    const h = createHarness({reducedMotion: true});
    const dispatch = await startProduction(h);
    assert.equal(dispatch.motionSuppressed, true);
    assert.equal(dispatch.visualStarted, false);
    assert.equal(dispatch.audioStarted, true);
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
    assert.equal(h.createdSvgElements(), 0);
    assert.equal(h.api.sound.activeCues.size, 1);
    h.api.cancelProcessingSounds("completed", true);
    assert.equal(h.timers.pending().length, 0);
  }
}

async function thinkingPulseBoundedResources() {
  {
    const h = createHarness();
    h.api.sound.context = h.makeContext();
    const generator = h.api.createThinkingPulseGenerator("active-cue-bound");
    const results = [];
    for (let index = 0; index < 7; index += 1) {
      results.push(h.api.dispatchThinkingPulseEvent(
        h.api.nextDataChatterEvent(generator, "qwen", index), "production"));
    }
    assert.equal(h.api.sound.activeCues.size, h.api.THINKING_PULSE_LIMITS.maxActiveCues);
    assert.ok(results.slice(0, 6).every(result => !result.blocked));
    assert.equal(results[6].blocked, true);
    assert.equal(results[6].audioStarted, false);
    assert.equal(results[6].visualStarted, false);
    assert.ok(h.oscillators.length <= h.api.THINKING_PULSE_LIMITS.maxActiveCues * 2);
    h.api.cancelProcessingSounds("completed", true);
    assert.equal(h.api.sound.activeCues.size, 0);
    assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
    assert.equal(h.timers.pending().length, 0);
  }

  {
    const h = createHarness();
    const snapshot = qwenSnapshot();
    h.api.sound.context = h.makeContext();
    h.api.state.snapshot = snapshot;
    h.api.updateProcessingSounds(snapshot);
    let maximumPending = 0;
    const routes = [];
    for (let index = 0; index < 70; index += 1) {
      const dispatch = await fireProductionTimer(h);
      routes.push(dispatch.route);
      maximumPending = Math.max(maximumPending, h.timers.pending().length);
      assert.ok(h.api.thinkingPulse.activeVisuals.size <= 14);
      assert.ok(h.api.sound.activeCues.size <= 1);
      h.finishScheduledOscillators();
      assert.equal(h.api.sound.activeCues.size, 0);
    }
    assert.deepEqual([...new Set(routes)].sort((a, b) => a - b),
      Array.from({length: 14}, (_value, index) => index + 1));
    assert.ok(maximumPending <= 15,
      `bounded scheduler accumulated ${maximumPending} pending timers`);
    assert.equal(h.audioContexts.length, 1);
    assert.equal(h.analysers.length, 0);
    assert.equal(h.createdSvgElements(), 0);
    h.api.cancelProcessingSounds("completed", true);
    assert.equal(h.timers.pending().length, 0);
    assert.ok([...h.packetGroups.values()].every(packet =>
      packet.group.dataset.thinkingPulseActive === undefined &&
      packet.group.style.values.size === 0));
  }
}

async function thinkingPulseAuditionSequence() {
  const h = createHarness();
  const pulseEvents = h.api.thinkingPulse.events;
  assert.deepEqual(plain(pulseEvents), plain(h.api.buildThinkingPulseAuditionEvents()));
  assert.ok(pulseEvents.length >= 30);
  assert.equal(h.timers.pending().length, 0,
    "Candidate 1 audition auto-started during module initialization");
  h.api.state.snapshot = idleSnapshot();
  h.api.sound.context = h.makeContext();
  assert.equal(await h.api.playThinkingPulseAudition(), true);
  let priorIndex = 0;
  const observedEventIds = [];
  let guard = 0;
  while (!h.api.thinkingPulse.completed) {
    const timer = h.timers.next();
    assert.ok(timer, "Candidate 1 audition stopped before completion");
    await h.timers.fire(timer.id);
    await flush();
    if (h.api.thinkingPulse.index > priorIndex) {
      for (let index = priorIndex; index < h.api.thinkingPulse.index; index += 1) {
        const event = pulseEvents[index];
        const dispatch = h.api.processingAudioDiagnostics.findLast(item =>
          item.stage === "thinking-pulse-dispatched" &&
          item.source === "thinking-pulse-audition" && item.eventId === event.id);
        const audio = h.api.processingAudioDiagnostics.findLast(item =>
          item.stage === "cue-started" &&
          item.source === "thinking-pulse-audition" && item.eventId === event.id);
        assert.ok(dispatch, `audition event ${event.id} lacked synchronized dispatch evidence`);
        assert.ok(audio, `audition event ${event.id} lacked audio evidence`);
        assert.equal(dispatch.audioStarted, true);
        assert.equal(dispatch.visualStarted, true);
        observedEventIds.push(event.id);
      }
      h.finishScheduledOscillators();
      priorIndex = h.api.thinkingPulse.index;
    }
    guard += 1;
    assert.ok(guard < 600, "Candidate 1 audition timers did not converge");
  }
  assert.deepEqual(observedEventIds, plain(pulseEvents.map(event => event.id)));
  assert.ok(h.api.processingAudioDiagnostics.length <= 96,
    "audition diagnostics exceeded their bounded ring buffer");
  assert.equal(h.api.thinkingPulse.running, false);
  assert.equal(h.api.thinkingPulse.activeVisuals.size, 0);
  assert.equal(h.api.sound.activeCues.size, 0);
  assert.equal(h.timers.pending().length, 0);
  assert.equal(await h.api.playThinkingPulseAudition(), false);
}


const scenarios = {
  "connection-trust": connectionTrust,
  "speech-claim-cancellation": speechClaimCancellation,
  "diagnostic-post-resume-recheck": diagnosticPostResumeRecheck,
  "diagnostic-no-overlap": diagnosticNoOverlap,
  "no-orphan-or-duplicate-scheduling": noOrphanOrDuplicateScheduling,
  "ui-confirmation-suppression-races": uiConfirmationSuppressionRaces,
  "cue-refresh-cancellation-boundaries": cueRefreshCancellationBoundaries,
  "data-chatter-profile-and-determinism": dataChatterProfileAndDeterminism,
  "thinking-pulse-event-coherence": thinkingPulseEventCoherence,
  "thinking-pulse-production-lifecycle": thinkingPulseProductionLifecycle,
  "thinking-pulse-cancellation-boundaries": thinkingPulseCancellationBoundaries,
  "thinking-pulse-stop-fence-transitions": thinkingPulseStopFenceTransitions,
  "thinking-pulse-ui-sounds-and-reduced-motion": thinkingPulseUiSoundsAndReducedMotion,
  "thinking-pulse-bounded-resources": thinkingPulseBoundedResources,
  "thinking-pulse-audition-sequence": thinkingPulseAuditionSequence,
};

async function main() {
  const name = process.argv[2];
  assert.ok(Object.hasOwn(scenarios, name), `unknown scheduler scenario: ${name}`);
  await scenarios[name]();
  process.stdout.write(`${name}: ok\n`);
}

main().catch(error => {
  console.error(error.stack || error);
  process.exitCode = 1;
});
