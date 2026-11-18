import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { ModelConfig, ModelTestResult } from '../api/types'

export function ModelPage() {
  const [model, setModel] = useState<ModelConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [testResult, setTestResult] = useState<ModelTestResult | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    apiClient
      .get<ModelConfig>('/api/config/model')
      .then(setModel)
      .catch((error) => setMessage(error instanceof Error ? error.message : String(error)))
  }, [])

  const flash = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(null), 3000)
  }

  const save = async () => {
    if (!model) return
    setSaving(true)
    try {
      setModel(
        await apiClient.put<ModelConfig>('/api/config/model', {
          base_url: model.base_url,
          model: model.model,
          thinking: model.thinking,
          reasoning_effort: model.reasoning_effort,
        }),
      )
      flash('模型配置已保存')
    } catch (error) {
      flash(error instanceof Error ? error.message : String(error))
    } finally {
      setSaving(false)
    }
  }

  const test = async () => {
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

  if (!model) return <div className="page"><p className="muted">加载中…</p></div>

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>模型配置</h1>
          <p className="muted small">配置生效后立即作用于问数链路；密钥只保存在服务端</p>
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <section className="card narrow">
        <label className="field">
          <span className="field-label">模型名</span>
          <input value={model.model} onChange={(e) => setModel({ ...model, model: e.target.value })} />
        </label>

        <label className="field">
          <span className="field-label">Base URL</span>
          <input value={model.base_url} onChange={(e) => setModel({ ...model, base_url: e.target.value })} />
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
            onChange={(e) =>
              setModel({ ...model, reasoning_effort: e.target.value as ModelConfig['reasoning_effort'] })
            }
          >
            <option value="low">low</option>
            <option value="medium">medium</option>
            <option value="high">high</option>
          </select>
        </label>

        <p className="muted small">
          API Key：{model.api_key_masked || '未配置'}（仅存于服务端 .env，不入库、不回传）
        </p>

        <div className="row-gap">
          <button className="btn primary" type="button" onClick={save} disabled={saving}>
            保存配置
          </button>
          <button className="btn" type="button" onClick={test} disabled={testing}>
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
  )
}
