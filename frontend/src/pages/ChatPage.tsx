import { useCallback, useEffect, useRef, useState } from 'react'
import { apiClient, streamChat } from '../api/client'
import type { AppConfig, AssistantDraft, ChatItem, Session } from '../api/types'
import { AnswerCard } from '../components/AnswerCard'

interface StoredMessage {
  message_id: number
  role: string
  content: string
  sql?: string | null
  chart?: string | null
  meta?: Record<string, unknown>
}

interface SessionDetail extends Session {
  messages: StoredMessage[]
}

export function ChatPage({ sessionOpen }: { sessionOpen: boolean }) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [items, setItems] = useState<ChatItem[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [title, setTitle] = useState('AI 智能问数')
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [quickOpen, setQuickOpen] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const bottomRef = useRef<HTMLDivElement | null>(null)

  const refreshSessions = useCallback(async () => {
    try {
      setSessions(await apiClient.get<Session[]>('/api/sessions'))
    } catch (error) {
      console.error('加载会话失败', error)
    }
  }, [])

  useEffect(() => {
    refreshSessions()
    apiClient
      .get<AppConfig>('/api/config/app')
      .then(setConfig)
      .catch((error) => console.error('加载配置失败', error))
  }, [refreshSessions])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [items])

  useEffect(() => {
    document.title = title ? `${title} · AI问数` : 'AI问数'
  }, [title])

  const updateDraft = (mutate: (draft: AssistantDraft) => void) => {
    setItems((prev) => {
      const next = [...prev]
      const last = next[next.length - 1]
      if (last && last.kind === 'assistant') {
        const draft: AssistantDraft = { ...last.draft, stages: [...last.draft.stages] }
        mutate(draft)
        next[next.length - 1] = { kind: 'assistant', draft }
      }
      return next
    })
  }

  const send = async (question: string) => {
    const text = question.trim()
    if (!text || busy) return

    setBusy(true)
    setInput('')
    setItems((prev) => [
      ...prev,
      { kind: 'user', text },
      { kind: 'assistant', draft: { question: text, stages: [], streaming: true } },
    ])

    const controller = new AbortController()
    abortRef.current = controller

    try {
      await streamChat(
        text,
        sessionId,
        (event, data) => {
          switch (event) {
            case 'session':
              setSessionId(Number(data.session_id))
              setTitle(String(data.title))
              break
            case 'stage':
              updateDraft((draft) => {
                const step = Number(data.step)
                draft.stages.push({ step, title: String(data.title), detail: String(data.detail) })
                if (step === 1) {
                  draft.tables = String(data.detail).split('、').filter(Boolean)
                }
              })
              break
            case 'table':
              updateDraft((draft) => {
                draft.table = {
                  columns: data.columns as string[],
                  rows: data.rows as (string | number | null)[][],
                }
              })
              break
            case 'chart':
              updateDraft((draft) => {
                draft.chart = String(data.type)
              })
              break
            case 'insight':
              updateDraft((draft) => {
                draft.insight = String(data.text)
              })
              break
            case 'followups':
              updateDraft((draft) => {
                draft.followups = (data.items as string[]) ?? []
              })
              break
            case 'error':
              updateDraft((draft) => {
                draft.error = String(data.message)
                draft.streaming = false
              })
              break
            case 'done':
              updateDraft((draft) => {
                draft.meta = {
                  sql: data.sql ? String(data.sql) : undefined,
                  elapsed_ms: Number(data.elapsed_ms ?? 0),
                  prompt_tokens: Number(data.prompt_tokens ?? 0),
                  completion_tokens: Number(data.completion_tokens ?? 0),
                }
                draft.streaming = false
              })
              break
            default:
              break
          }
        },
        controller.signal,
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error)
      updateDraft((draft) => {
        draft.error = controller.signal.aborted ? '已取消本次提问' : message
        draft.streaming = false
      })
    } finally {
      setBusy(false)
      abortRef.current = null
      refreshSessions()
    }
  }

  const stop = () => {
    abortRef.current?.abort()
    setBusy(false)
  }

  const newChat = () => {
    setItems([])
    setSessionId(null)
    setTitle('AI 智能问数')
  }

  const openSession = async (id: number) => {
    if (busy) return
    try {
      const detail = await apiClient.get<SessionDetail>(`/api/sessions/${id}`)
      setSessionId(detail.session_id)
      setTitle(detail.title)
      setItems(
        detail.messages.map((message, index) => {
          if (message.role === 'user') return { kind: 'user', text: message.content }
          const meta = message.meta ?? {}
          const columns = meta.columns as string[] | undefined
          const rows = meta.rows_data as (string | number | null)[][] | undefined
          return {
            kind: 'assistant',
            draft: {
              question: detail.messages[index - 1]?.content,
              stages: [],
              streaming: false,
              insight: message.content,
              chart: message.chart ?? undefined,
              table: columns && rows ? { columns, rows } : undefined,
              followups: (meta.followups as string[] | undefined) ?? [],
              meta: {
                sql: message.sql ?? undefined,
                elapsed_ms: Number(meta.elapsed_ms ?? 0),
              },
            },
          }
        }),
      )
    } catch (error) {
      console.error('加载会话详情失败', error)
    }
  }

  const greeting = config?.greeting ?? true
  const questions = config?.greetingQuestions ?? []

  const togglePin = async (session: Session) => {
    try {
      await apiClient.patch(`/api/sessions/${session.session_id}`, { pinned: !session.pinned })
      await refreshSessions()
    } catch (error) {
      console.error('置顶失败', error)
    }
  }

  const renameSession = async (session: Session) => {
    const title = window.prompt('重命名会话', session.title)?.trim()
    if (!title) return
    try {
      await apiClient.patch(`/api/sessions/${session.session_id}`, { title })
      if (session.session_id === sessionId) setTitle(title)
      await refreshSessions()
    } catch (error) {
      console.error('重命名失败', error)
    }
  }

  const removeSession = async (session: Session) => {
    if (!window.confirm(`删除会话「${session.title}」？该操作不可恢复。`)) return
    try {
      await apiClient.delete(`/api/sessions/${session.session_id}`)
      if (session.session_id === sessionId) newChat()
      await refreshSessions()
    } catch (error) {
      console.error('删除失败', error)
    }
  }

  return (
    <div className="chat-layout">
      <aside className={sessionOpen ? 'session-bar' : 'session-bar hidden'}>
        <div className="session-head">
          <span>近 30 天记录</span>
          <button className="ghost" onClick={newChat} type="button" title="开启新对话">
            ＋
          </button>
        </div>
        <div className="session-list">
          {sessions.length === 0 && <p className="muted small">还没有会话</p>}
          {sessions.map((session) => (
            <div
              key={session.session_id}
              className={`session-item${session.session_id === sessionId ? ' active' : ''}`}
            >
              <button
                type="button"
                className="session-main"
                onClick={() => openSession(session.session_id)}
              >
                <span className="session-title">
                  {session.pinned ? '📌 ' : ''}
                  {session.title}
                </span>
                <span className="muted small">{session.message_count} 条</span>
              </button>
              <div className="session-actions">
                <button type="button" title={session.pinned ? '取消置顶' : '置顶'} onClick={() => togglePin(session)}>
                  {session.pinned ? '★' : '☆'}
                </button>
                <button type="button" title="重命名" onClick={() => renameSession(session)}>
                  ✎
                </button>
                <button type="button" title="删除" onClick={() => removeSession(session)}>
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      </aside>

      <main className="chat-main">

        <div className="messages">
          {items.length === 0 && (
            <div className="welcome">
              <h1>你好</h1>
              <h2>我是 AI 问数助手</h2>
              {greeting && <p className="welcome-desc">{config?.greetingText}</p>}
              {greeting && questions.length > 0 && (
                <div className="quick-block">
                  <p className="quick-title">你可以这么问我</p>
                  <div className="quick-grid">
                    {questions.map((question) => (
                      <button
                        key={question}
                        type="button"
                        className="quick"
                        onClick={() => send(question)}
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {items.map((item, index) =>
            item.kind === 'user' ? (
              <div className="bubble user" key={index}>
                {item.text}
              </div>
            ) : (
              <AnswerCard key={index} draft={item.draft} onAsk={send} />
            ),
          )}
          <div ref={bottomRef} />
        </div>

        <div className="composer">
          {quickOpen && questions.length > 0 && (
            <div className="quick-pop">
              {questions.map((question) => (
                <button
                  key={question}
                  type="button"
                  onClick={() => {
                    setQuickOpen(false)
                    send(question)
                  }}
                >
                  {question}
                </button>
              ))}
            </div>
          )}
          <div className="composer-pill">
            <button
              className="pill-btn"
              type="button"
              title="快捷提问"
              onClick={() => setQuickOpen(!quickOpen)}
            >
              ⚡
            </button>
            <textarea
              value={input}
              placeholder="请写下您的想法…"
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  send(input)
                }
              }}
              rows={1}
            />
            <button className="pill-btn" type="button" title="语音输入未启用" disabled>
              🎤
            </button>
            {busy ? (
              <button className="send-round stop" onClick={stop} type="button" title="停止">
                ■
              </button>
            ) : (
              <button
                className="send-round"
                onClick={() => send(input)}
                disabled={!input.trim()}
                type="button"
                title="发送"
              >
                →
              </button>
            )}
          </div>
        </div>
      </main>
    </div>
  )
}
