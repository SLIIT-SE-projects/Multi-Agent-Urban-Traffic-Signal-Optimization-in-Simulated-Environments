/**
 * Minimal Express model service template.
 *
 * Implements the model_service.yaml contract with stub /predict logic.
 * Researchers comfortable with Node.js can use this as a starting point.
 *
 * Run:
 *   npm install
 *   npm start
 */
const express = require('express');

const app = express();
app.use(express.json({ limit: '20mb' }));  // big to handle large network/snapshot payloads

// ── Per-session state ─────────────────────────────────────────────────
let session_id = null;
let network = null;
const started_at = Date.now();


// ── Endpoints ─────────────────────────────────────────────────────────

app.get('/info', (req, res) => {
  res.json({
    name: process.env.MODEL_NAME || 'researcher_template_node',
    version: '0.1.0',
    snapshot_schema_version: '1',
    action_schema_version: '1',
    decision_interval_steps: parseInt(process.env.DECISION_INTERVAL_STEPS || '15', 10),
    action_types_supported: ['binary_switch'],
    supports_warm_start: true,
    max_inference_ms: parseInt(process.env.MAX_INFERENCE_MS || '500', 10),
    description: 'Stub template — replace /predict body with your model',
    author: process.env.AUTHOR || 'researcher',
    license: 'MIT',
  });
});


app.get('/health', (req, res) => {
  res.json({
    status: session_id ? 'ok' : 'not_ready',
    model_loaded: session_id !== null,
    session_id,
    uptime_seconds: (Date.now() - started_at) / 1000,
  });
});


app.post('/reset', (req, res) => {
  const body = req.body || {};
  if (!body.session_id) {
    return res.status(400).json({ detail: 'session_id is required' });
  }
  session_id = body.session_id;
  network = body.network || {};

  // ╭─ RESEARCHER HOOK 1 ──────────────────────────────────────────╮
  // │  Build internal data structures from `network` here.          │
  // │  See contracts/schemas/network.schema.json for the shape.    │
  // ╰───────────────────────────────────────────────────────────────╯

  res.json({ status: 'ready', session_id, warmup_steps: 0 });
});


app.post('/predict', (req, res) => {
  if (!session_id) {
    return res.status(503).json({ detail: 'Session not initialized — call /reset first' });
  }
  const body = req.body || {};
  if (body.session_id !== session_id) {
    return res.status(400).json({
      detail: `session_id mismatch: expected ${session_id}, got ${body.session_id}`,
    });
  }
  const step = body.step || 0;
  const snapshot = body.snapshot || {};
  const t0 = Date.now();

  // ╭─ RESEARCHER HOOK 2 ──────────────────────────────────────────╮
  // │  Replace with your inference. Inputs:                         │
  // │    snapshot.intersections: {tls_id: {phase_index, ...}}       │
  // │    snapshot.lanes:         {lane_id: {queue_length, ...}}     │
  // │  Output: actions dict, see action.schema.json for shape.      │
  // ╰───────────────────────────────────────────────────────────────╯

  const actions = {};
  for (const tls_id of Object.keys(snapshot.intersections || {})) {
    // STUB: always keep current phase. Replace with real logic.
    actions[tls_id] = { type: 'binary_switch', value: 0 };
  }

  const inference_ms = Date.now() - t0;

  res.json({
    session_id,
    step,
    actions,
    telemetry: {
      inference_time_ms: inference_ms,
      // Optional: model_specific: {my_metric: 0.42}
    },
  });
});


app.post('/teardown', (req, res) => {
  session_id = null;
  network = null;
  res.json({ status: 'released' });
});


// ── Entry point ───────────────────────────────────────────────────────

const port = parseInt(process.env.PORT || '9000', 10);
app.listen(port, '0.0.0.0', () => {
  console.log(`[Researcher Template] Listening on 0.0.0.0:${port}`);
});
