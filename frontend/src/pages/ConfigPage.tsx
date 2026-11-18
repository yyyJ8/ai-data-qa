import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { AppConfig, ModelConfig, ModelTestResult } from '../api/types'

export function ConfigPage() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [model, setModel] = useState<ModelConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<ModelTestResult | null>(null)
  const [newQuestion, setNewQuestion] = useState('')

  useEffect(() => {
    apiClient.get<AppConfig>('/api/config/app').then(setConfig).catch((error) => setMessage(String(error)))
    apiClient.get<ModelConfig>('/api/config/model').then(setModel).catch((error) => setMessage(String(error)))
  }, [])

  const flash = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(null), 3000)
  }

  const saveApp = async () => {
    if (!config) return
    setSaving(true)
    try {
      const saved = await apiClient.put<AppConfig>('/api/config/app', {
        greeting: config.greeting,
        greetingText: config.greetingText,
        greetingQuestions: config.greetingQuestions,
        suggestions: config.suggestions,
        hotThreshold: config.hotThreshold,
      })
      setConfig(saved)
      flash('应用配置已保存')
    } catch (error) {
      flash(error instanceof Error ? error.message : String(error))
    } finally {
      setSaving(false)
    }
  }

  const saveModel = async () => {
    if (!model) return
    setSaving(true)
    try {
      const saved = await apiClient.put<ModelConfig>('/api/config/model', {
        base_url: model.base_url,
        model: model.model,
        thinking: model.thinking,
        reasoning_effort: model.reasoning_effort,
      })
      setModel(saved)
      flash('模型配置已保存')
    } catch (error) {
      flash(error instanceof Error ? error.message : String(error))
    } finally {
      setSaving(false)
    }
  }

  const testModel = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      setTestResult(await apiClient.post<ModelTestResult>('/api/config/model/test', {}))
    } catch (error) {
      setTestResult({ ok: false, error: error instanceof Error ? error.message : String(error) })
    } finally {
      setTesting(false)
    }
  }

  const addQuestion = () => {
    if (!config) return
    const text = newQuestion.trim()
    if (!text || config.greetingQuestions.length >= 10) return
    setConfig({ ...config, greetingQuestions: [...config.greetingQuestions, text] })
    setNewQuestion('')
  }

  const removeQuestion = (index: number) => {
    if (!config) return
    setConfig({ ...config, greetingQuestions: config.greetingQuestions.filter((_, i) => i !== index) })
  }

  if (!config || !model) return <div className="page"><p className="muted">加载中…</p></div>

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>应用配置</h1>
          <p className="muted small">开场白、快捷问题与模型设置，修改后立即生效</p>
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <div className="grid-2">
        <section className="card">
          <h2>对话体验</h2>

          <label className="form-row">
            <span>展示开场白</span>
            <button
              type="button"
              className={`switch${config.greeting ? ' on' : ''}`}
              onClick={() => setConfig({ ...config, greeting: !config.greeting })}
            >
              <i />
            </button>
          </label>

          <label className="field">
            <span className="field-label">开场白文案</span>
            <textarea
              rows={3}
              value={config.greetingText}
              onChange={(event) => setConfig({ ...config, greetingText: event.target.value })}
            />
          </label>

          <div className="field">
            <span className="field-label">快捷问题（最多 10 条）</span>
            <ul className="chip-list">
              {config.greetingQuestions.map((question, index) => (
                <li key={`${question}-${index}`}>
                  <span>{question}</span>
                  <button type="button" onClick={() => removeQuestion(index)}>
                    ×
                  </button>
                </li>
              ))}
            </ul>
            <div className="inline-add">
              <input
                value={newQuestion}
                placeholder="新增一条快捷问题"
                onChange={(event) => setNewQuestion(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') addQuestion()
                }}
              />
              <button type="button" className="btn" onClick={addQuestion}>
                添加
              </button>
            </div>
          </div>

          <label className="form-row">
            <span>展示延伸问题建议</span>
            <button
              type="button"
              className={`switch${config.suggestions ? ' on' : ''}`}
              onClick={() => setConfig({ ...config, suggestions: !config.suggestions })}
            >
              <i />
            </button>
          </label>

          <label className="form-row">
            <span>常问阈值（次）</span>
            <input
              type="number"
              min={1}
              max={100}
              value={config.hotThreshold}
              onChange={(event) => setConfig({ ...config, hotThreshold: Number(event.target.value) })}
            />
          </label>

          <button className="btn primary" type="button" onClick={saveApp} disabled={saving}>
            保存应用配置
          </button>
        </section>

        <section className="card">
          <h2>模型设置</h2>

          <label className="field">
            <span className="field-label">模型名</span>
            <input
              value={model.model}
              onChange={(event) => setModel({ ...model, model: event.target.value })}
            />
          </label>

          <label className="field">
            <span className="field-label">Base URL</span>
            <input
              value={model.base_url}
              onChange={(event) => setModel({ ...model, base_url: event.target.value })}
            />
          </label>

          <label className="form-row">
            <span>思考模式</span>
            <button
              type="button"
              className={`switch${model.thinking ? ' on' : ''}`}
              onClick={() => setModel({ ...model, thinking: !model.thinking })}
            >
              <i />
            </button>
          </label>

          <label className="field">
            <span className="field-label">思考强度</span>
            <select
              value={model.reasoning_effort}
              onChange={(event) =>
                setModel({ ...model, reasoning_effort: event.target.value as ModelConfig['reasoning_effort'] })
              }
            >
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
            </select>
          </label>

          <p className="muted small">
            API Key：{model.api_key_masked || '未配置'}（只存于服务端 `.env`，不入库、不回传）
          </p>

          <div className="row-gap">
            <button className="btn primary" type="button" onClick={saveModel} disabled={saving}>
              保存模型配置
            </button>
            <button className="btn" type="button" onClick={testModel} disabled={testing}>
              {testing ? '测试中…' : '测试连接'}
            </button>
          </div>

          {testResult && (
            <div className={testResult.ok ? 'result ok' : 'result bad'}>
              {testResult.ok
                ? `连接成功 · ${testResult.model} · ${testResult.latency_ms} ms · 回复「${testResult.reply}」`
                : `连接失败：${testResult.error}`}
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
