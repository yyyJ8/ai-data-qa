import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test } from '@playwright/test'

const E2E_CASES = path.resolve(process.cwd(), 'e2e-cases.jsonl')

test('四个页面可以互相导航', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '你好，我是 AI 问数助手' })).toBeVisible()

  await page.getByRole('button', { name: /数据台账/ }).click()
  await expect(page.getByRole('heading', { name: '数据台账' })).toBeVisible()

  await page.getByRole('button', { name: /应用配置/ }).click()
  await expect(page.getByRole('heading', { name: '应用配置' })).toBeVisible()

  await page.getByRole('button', { name: /回复校对/ }).click()
  await expect(page.getByRole('heading', { name: '回复校对' })).toBeVisible()
})

test('问数能流式返回表格与图表', async ({ page, request }) => {
  const health = await (await request.get('/api/health')).json()
  test.skip(!health.llm?.configured, '未配置模型 Key，跳过真实问数')

  await page.goto('/')
  await page.getByPlaceholder(/请写下您的想法/).fill('2026年收入前3的经营单元')
  await page.getByRole('button', { name: '发送' }).click()

  await expect(page.locator('.answer-card')).toBeVisible()
  await expect(page.locator('.answer-card')).toContainText('数据表格', { timeout: 50_000 })
  await expect
    .poll(async () => page.locator('.answer-card .data-table tbody tr').count(), { timeout: 50_000 })
    .toBeGreaterThan(0)
  await expect(page.locator('.answer-card .chart canvas')).toBeVisible()
  await expect(page.locator('.answer-card')).toContainText('结论')
})

test('台账分页可用且导出链接正确', async ({ page, request }) => {
  const first = await (await request.get('/api/data/dim_unit?page=1&page_size=20')).json()
  expect(first.total).toBe(21)

  await page.goto('/')
  await page.getByRole('button', { name: /数据台账/ }).click()
  await expect(page.getByText('共 21 行')).toBeVisible()

  await page.getByRole('button', { name: '下一页' }).click()
  await expect(page.getByText('第 2 / 2 页')).toBeVisible()

  const exportLink = page.getByRole('link', { name: /导出 Excel/ })
  await expect(exportLink).toHaveAttribute('href', /\/api\/data\/dim_unit\/export/)
})

test('应用配置保存后给出提示', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /应用配置/ }).click()

  const toggle = page.locator('.switch').first()
  await toggle.click()
  await toggle.click()

  await page.getByRole('button', { name: '保存应用配置' }).click()
  await expect(page.locator('.toast')).toContainText('应用配置已保存')
})

test('重开会话能还原表格与图表', async ({ page, request }) => {
  const health = await (await request.get('/api/health')).json()
  test.skip(!health.llm?.configured, '未配置模型 Key，跳过真实问数')

  await page.goto('/')
  await page.getByPlaceholder(/请写下您的想法/).fill('2026年各产品线收入占比')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.locator('.answer-card .chart canvas')).toBeVisible({ timeout: 50_000 })

  await page.reload()
  await page.locator('.session-item').first().click()

  await expect(page.locator('.answer-card .data-table tbody tr').first()).toBeVisible({ timeout: 15_000 })
  await expect(page.locator('.answer-card .chart canvas')).toBeVisible()
})

test('反馈提交后会出现在校对列表', async ({ page, request }) => {
  const question = `e2e 反馈 ${Date.now()}`
  const created = await request.post('/api/feedback', { data: { question, reason: 'e2e' } })
  expect(created.status()).toBe(201)

  await page.goto('/')
  await page.getByRole('button', { name: /回复校对/ }).click()
  await expect(page.getByText(question)).toBeVisible()
})

test('校对填写修正 SQL 后可回灌评测集', async ({ page, request }) => {
  writeFileSync(E2E_CASES, '', 'utf-8')

  const question = `e2e 回灌 ${Date.now()}`
  const created = await request.post('/api/feedback', { data: { question, reason: '数据有误' } })
  const feedbackId = (await created.json()).feedback_id as number
  await request.patch(`/api/feedback/${feedbackId}`, {
    data: { corrected_sql: 'SELECT unit_name AS 单元 FROM dim_unit' },
  })

  await page.goto('/')
  await page.getByRole('button', { name: /回复校对/ }).click()
  await page
    .locator('tr', { hasText: question })
    .getByRole('button', { name: '处理' })
    .click()

  await expect(page.locator('.modal')).toBeVisible()
  await page.getByRole('button', { name: '写入评测集' }).click()
  await expect(page.locator('.toast')).toContainText('已写入评测集')

  const lines = readFileSync(E2E_CASES, 'utf-8').trim().split('\n')
  expect(lines).toHaveLength(1)
  const saved = JSON.parse(lines[0])
  expect(saved.question).toBe(question)
  expect(saved.tags).toContain('from_feedback')
  expect(saved.sql).toContain('dim_unit')
})
