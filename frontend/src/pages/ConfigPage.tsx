import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { AppConfig } from '../api/types'

export function ConfigPage() {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<string | null>(null)
  const [newQuestion, setNewQuestion] = useState('')

  useEffect(() => {
    apiClient
      .get<AppConfig>('/api/config/app')
      .then(setConfig)
      .catch((error) => setMessage(error instanceof Error ? error.message : String(error)))
  }, [])

  const flash = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(null), 3000)
  }

  const save = async () => {
    if (!config) return
    setSaving(true)
    try {
      setConfig(
        await apiClient.put<AppConfig>('/api/config/app', {
          greeting: config.greeting,
          greetingText: config.greetingText,
          greetingQuestions: config.greetingQuestions,
          suggestions: config.suggestions,
          hotThreshold: config.hotThreshold,
        }),
      )
      flash('应用配置已保存')
    } catch (error) {
      flash(error instanceof Error ? error.message : String(error))
    } finally {
      setSaving(false)
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

  if (!config) return <div className="page"><p className="muted">加载中…</p></div>

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>应用配置</h1>
          <p className="muted small">开场白与快捷问题，修改后立即生效</p>
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <section className="card narrow">
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
            onChange={(e) => setConfig({ ...config, greetingText: e.target.value })}
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
              onChange={(e) => setNewQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addQuestion()
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
            onChange={(e) => setConfig({ ...config, hotThreshold: Number(e.target.value) })}
          />
        </label>

        <button className="btn primary" type="button" onClick={save} disabled={saving}>
          保存应用配置
        </button>
      </section>
    </div>
  )
}
