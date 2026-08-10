/**
 * Runtime verification script for G.R.A.C.I. Phase 2.1.
 * Tests the configured Ollama endpoint and default model.
 */

const { OllamaService } = require('../dist/services/ollama/service.js');
const { getConfig } = require('../dist/core/config/loader.js');

async function main() {
  console.log('G.R.A.C.I. Phase 2.1 Runtime Verification');
  console.log('==========================================');

  const config = getConfig();
  const service = OllamaService.getInstance();

  console.log(`Testing connection to: ${service.getEndpoint()}`);
  console.log(`Using model: ${config.ollama.default_model}`);

  console.log('\n1. Checking Ollama server health...');
  const healthResult = await service.checkHealth();

  if (!healthResult.success) {
    console.log('FAIL: Health check failed:', healthResult.error);
    process.exit(1);
  }

  console.log('PASS: Health check passed');

  console.log('\n2. Running inference test...');
  const expected = 'G.R.A.C.I. Phase 2 inference verified.';
  const inferenceResult = await service.runInference(
    `Reply with exactly: ${expected}`
  );

  if (!inferenceResult.success) {
    console.log('FAIL: Inference test failed:', inferenceResult.error);
    process.exit(1);
  }

  console.log('PASS: Inference test passed');
  console.log('Response:', inferenceResult.response);

  if (inferenceResult.response !== expected) {
    console.log('FAIL: Response does not match expected value');
    process.exit(1);
  }

  console.log('PASS: Response matches expected value');
  console.log('\nSUCCESS: G.R.A.C.I. Phase 2.1 verification successful!');
}

main().catch((error) => {
  console.error('FAIL: Unexpected verification error:', error);
  process.exit(1);
});
