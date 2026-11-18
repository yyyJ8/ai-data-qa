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

export function ChatPage() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [config, setConfig] = useState<AppConfig | null>(null)
  const [items, setItems] = useState<ChatItem[]>([])
  const [sessionId, setSessionId] = useState<number | null>(null)
  const [title, setTitle] = useState('AI 智能问数')
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
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
              updateDraft((draft) =>
                draft.stages.push({
                  step: Number(data.step),
                  title: String(data.title),
                  detail: String(data.detail),
                }),
              )
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
        detail.messages.map((message, index) =>
          message.role === 'user'
            ? { kind: 'user', text: message.content }
            : {
                kind: 'assistant',
                draft: {
                  question: detail.messages[index - 1]?.content,
                  stages: [],
                  streaming: false,
                  insight: message.content,
                  chart: message.chart ?? undefined,
                  meta: {
                    sql: message.sql ?? undefined,
                    elapsed_ms: Number(message.meta?.elapsed_ms ?? 0),
                  },
                },
              },
        ),
      )
    } catch (error) {
      console.error('加载会话详情失败', error)
    }
  }

  const greeting = config?.greeting ?? true
  const questions = config?.greetingQuestions ?? []

  return (
    <div className="chat-layout">
      <aside className="session-bar">
        <div className="session-head">
          <span>近 30 天记录</span>
          <button className="ghost" onClick={newChat} type="button" title="开启新对话">
            ＋
          </button>
        </div>
        <div className="session-list">
          {sessions.length === 0 && <p className="muted small">还没有会话</p>}
          {sessions.map((session) => (
            <button
              key={session.session_id}
              type="button"
              className={`session-item${session.session_id === sessionId ? ' active' : ''}`}
              onClick={() => openSession(session.session_id)}
            >
              <span className="session-title">{session.title}</span>
              <span className="muted small">{session.message_count} 条</span>
            </button>
          ))}
        </div>
      </aside>

      <main className="chat-main">
        <header className="chat-head">
          <h2>{title}</h2>
          <span className="muted small">deepseek-flash · text2sql</span>
        </header>

        <div className="messages">
          {items.length === 0 && (
            <div className="welcome">
              <h1>你好，我是 AI 问数助手</h1>
              {greeting && <p className="muted">{config?.greetingText}</p>}
              {greeting && questions.length > 0 && (
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
              )}
            </div>
          )}

          {items.map((item, index) =>
            item.kind === 'user' ? (
              <div className="bubble user" key={index}>
                {item.text}
              </div>
            ) : (
              <AnswerCard key={index} draft={item.draft} />
            ),
          )}
          <div ref={bottomRef} />
        </div>

        <div className="composer">
          <textarea
            value={input}
            placeholder="请写下您的想法…（Enter 发送，Shift+Enter 换行）"
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault()
                send(input)
              }
            }}
            rows={2}
          />
          {busy ? (
            <button className="send stop" onClick={stop} type="button">
              停止
            </button>
          ) : (
            <button className="send" onClick={() => send(input)} disabled={!input.trim()} type="button">
              发送
            </button>
          )}
        </div>
      </main>
    </div>
  )
}
