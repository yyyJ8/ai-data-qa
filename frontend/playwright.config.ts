import { defineConfig, devices } from '@playwright/test'

// E2E 使用独立后端端口与独立语料文件，避免与 docker 容器（8000）互相干扰
const API_PORT = 8010
const WEB_PORT = 5174

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chrome', use: { ...devices['Desktop Chrome'], channel: 'chrome' } },
  ],
  webServer: [
    {
      command: `.venv\\Scripts\\python.exe -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: '../backend',
      url: `http://127.0.0.1:${API_PORT}/api/health`,
      reuseExistingServer: true,
      timeout: 60_000,
      env: { EVAL_CASES_PATH: 'frontend/e2e-cases.jsonl' },
    },
    {
      command: `pnpm exec vite --port ${WEB_PORT} --host 127.0.0.1`,
      cwd: '.',
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: true,
      timeout: 60_000,
      env: { VITE_API_TARGET: `http://127.0.0.1:${API_PORT}` },
    },
  ],
})
