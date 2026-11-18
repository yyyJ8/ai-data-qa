import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { AppConfig } from '../api/types'

interface CardDef {
  key: keyof AppConfig
  title: string
  desc: string
  icon: string
  color: string
  gear?: 'greeting' | 'model' | 'hot'
  disabled?: boolean
}

const CARDS: CardDef[] = [
  {
    key: 'greeting',
    title: '对话开场白',
    desc: '开启后，新对话将自动显示开场白引导语（如"欢迎使用智能AI问数..."）',
    icon: '💬',
    color: '#e8f0fe',
    gear: 'greeting',
  },
  {
    key: 'suggestions',
    title: '下一步问题建议',
    desc: '开启后，AI 回复下方自动生成 3 条相关延伸问题提示条',
    icon: '📋',
    color: '#fef3c7',
  },
  {
    key: 'tts',
    title: '文字转语音',
    desc: '开启后，AI 回答支持语音播报功能（本期未启用）',
    icon: '🔊',
    color: '#dcfce7',
    disabled: true,
  },
  {
    key: 'stt',
    title: '语音转文字',
    desc: '开启后，支持通过语音输入问题（本期未启用）',
    icon: '🎙️',
    color: '#f3e8ff',
    disabled: true,
  },
  {
    key: 'modelConfig',
    title: '模型配置',
    desc: '配置各业务场景使用的 AI 模型',
    icon: '🧊',
    color: '#e8f0fe',
    gear: 'model',
  },
  {
    key: 'hotRecommend',
    title: '常问设置',
    desc: '根据经常提问频次，在快捷提问中能看到常问问题',
    icon: '🔥',
    color: '#fef3c7',
    gear: 'hot',
  },
]

export function ConfigPage({ onNavigate }: { onNavigate: (page: 'model' | 'data' | 'feedback') => void }) {
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [message, setMessage] = useState<string | null>(null)
  const [modal, setModal] = useState<null | 'greeting' | 'hot'>(null)
  const [draftText, setDraftText] = useState('')
  const [draftQuestions, setDraftQuestions] = useState<string[]>([])
  const [draftThreshold, setDraftThreshold] = useState(3)
  const [newQuestion, setNewQuestion] = useState('')

  useEffect(() => {
    apiClient
      .get<AppConfig>('/api/config/app')
      .then(setConfig)
      .catch((error) => setMessage(error instanceof Error ? error.message : String(error)))
  }, [])

  const flash = (text: string) => {
    setMessage(text)
    window.setTimeout(() => setMessage(null), 2500)
  }

  const persist = async (next: AppConfig) => {
    setConfig(next)
    try {
      setConfig(await apiClient.put<AppConfig>('/api/config/app', next))
      flash('已保存')
    } catch (error) {
      flash(error instanceof Error ? error.message : String(error))
    }
  }

  const toggle = (key: keyof AppConfig) => {
    if (!config) return
    persist({ ...config, [key]: !config[key] })
  }

  const openGear = (gear: NonNullable<CardDef['gear']>) => {
    if (!config) return
    if (gear === 'model') {
      onNavigate('model')
      return
    }
    if (gear === 'greeting') {
      setDraftText(config.greetingText)
      setDraftQuestions([...config.greetingQuestions])
    }
    if (gear === 'hot') setDraftThreshold(config.hotThreshold)
    setModal(gear)
  }

  const saveGreeting = async () => {
    if (!config) return
    await persist({
      ...config,
      greetingText: draftText.trim() || config.greetingText,
      greetingQuestions: draftQuestions.filter((q) => q.trim()),
    })
    setModal(null)
  }

  const saveHot = async () => {
    if (!config) return
    await persist({ ...config, hotThreshold: Math.max(1, Math.min(100, draftThreshold)) })
    setModal(null)
  }

  if (!config) return <div className="page"><p className="muted">加载中…</p></div>

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>应用配置</h1>
          <p className="muted small">按业务场景开关能力，齿轮可进一步设置</p>
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <div className="config-grid">
        {CARDS.map((card) => (
          <section className={`config-card${card.disabled ? ' disabled' : ''}`} key={card.key}>
            <div className="config-card-top">
              <span className="config-icon" style={{ background: card.color }}>{card.icon}</span>
              <span className="config-name">{card.title}</span>
              <div className="config-actions">
                {card.gear && (
                  <button type="button" className="gear" title="设置" onClick={() => openGear(card.gear!)}>
                    ⚙
                  </button>
                )}
                <button
                  type="button"
                  className={`switch${config[card.key] ? ' on' : ''}`}
                  disabled={card.disabled}
                  onClick={() => toggle(card.key)}
                >
                  <i />
                </button>
              </div>
            </div>
            <p className="config-desc">{card.desc}</p>
          </section>
        ))}
      </div>

      {modal === 'greeting' && (
        <div className="modal-mask" onClick={() => setModal(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <h3>💬 对话开场白</h3>
            <label className="field">
              <span className="field-label">开场白文案</span>
              <textarea rows={3} value={draftText} onChange={(e) => setDraftText(e.target.value)} />
            </label>
            <div className="field">
              <span className="field-label">开场问题（{draftQuestions.length}/10）</span>
              <ul className="chip-list">
                {draftQuestions.map((question, index) => (
                  <li key={`${question}-${index}`}>
                    <span>{question}</span>
                    <button
                      type="button"
                      onClick={() => setDraftQuestions(draftQuestions.filter((_, i) => i !== index))}
                    >
                      ×
                    </button>
                  </li>
                ))}
              </ul>
              <div className="inline-add">
                <input
                  value={newQuestion}
                  placeholder="输入新的开场问题"
                  onChange={(e) => setNewQuestion(e.target.value)}
                />
                <button
                  type="button"
                  className="btn"
                  onClick={() => {
                    if (!newQuestion.trim() || draftQuestions.length >= 10) return
                    setDraftQuestions([...draftQuestions, newQuestion.trim()])
                    setNewQuestion('')
                  }}
                >
                  添加
                </button>
              </div>
            </div>
            <div className="row-gap">
              <button className="btn primary" type="button" onClick={saveGreeting}>保存</button>
              <button className="btn" type="button" onClick={() => setModal(null)}>取消</button>
            </div>
          </div>
        </div>
      )}

      {modal === 'hot' && (
        <div className="modal-mask" onClick={() => setModal(null)}>
          <div className="modal small" onClick={(e) => e.stopPropagation()}>
            <h3>🔥 常问设置</h3>
            <label className="field">
              <span className="field-label">问题频次阈值</span>
              <input
                type="number"
                min={1}
                max={100}
                value={draftThreshold}
                onChange={(e) => setDraftThreshold(Number(e.target.value))}
              />
            </label>
            <p className="muted small">同一问题出现次数超过该值即视为常问</p>
            <div className="row-gap">
              <button className="btn primary" type="button" onClick={saveHot}>保存</button>
              <button className="btn" type="button" onClick={() => setModal(null)}>取消</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
