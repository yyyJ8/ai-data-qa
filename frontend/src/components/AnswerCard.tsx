import { useState } from 'react'
import { apiClient } from '../api/client'
import type { AssistantDraft } from '../api/types'
import { ChartPanel } from './ChartPanel'
import { DataTable } from './DataTable'
import { StageList } from './StageList'

export function AnswerCard({
  draft,
  onAsk,
}: {
  draft: AssistantDraft
  onAsk?: (question: string) => void
}) {
  const [feedbackSent, setFeedbackSent] = useState(false)
  const [copied, setCopied] = useState(false)
  const showChart = draft.chart && draft.chart !== 'table' && draft.table && draft.chart !== 'none'

  const copyInsight = async () => {
    if (!draft.insight) return
    try {
      await navigator.clipboard.writeText(draft.insight)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 2000)
    } catch (error) {
      console.error('复制失败', error)
    }
  }

  const submitFeedback = async () => {
    if (!draft.question || feedbackSent) return
    try {
      await apiClient.post('/api/feedback', { question: draft.question, reason: '数据有误' })
      setFeedbackSent(true)
    } catch (error) {
      console.error('提交反馈失败', error)
    }
  }

  return (
    <article className="answer-card">
      <header className="answer-head">
        <span className="avatar ai">AI</span>
        <span className="answer-title">问数结果</span>
        {draft.streaming && <span className="dot-pulse" />}
        {draft.error && <span className="badge danger">失败</span>}
      </header>

      {draft.error && <div className="error-banner">{draft.error}</div>}

      <StageList stages={draft.stages} />

      {draft.table && (
        <section className="module">
          <div className="module-title">
            <span className="num">2</span>数据表格
            <span className="muted small">共 {draft.table.rows.length} 行</span>
          </div>
          <DataTable data={draft.table} />
        </section>
      )}

      {showChart && (
        <section className="module">
          <div className="module-title">
            <span className="num">3</span>数据可视化
          </div>
          <ChartPanel type={draft.chart!} data={draft.table!} />
        </section>
      )}

      {draft.insight && (
        <section className="module">
          <div className="module-title">
            <span className="num">4</span>结论
          </div>
          <p className="insight">{draft.insight}</p>
        </section>
      )}

      {draft.followups && draft.followups.length > 0 && (
        <div className="followups">
          <span className="muted small">继续问：</span>
          {draft.followups.map((question) => (
            <button key={question} className="chip" type="button" onClick={() => onAsk?.(question)}>
              {question}
            </button>
          ))}
        </div>
      )}

      {draft.meta?.sql && (
        <details className="sql-block">
          <summary>查看 SQL{draft.meta.elapsed_ms ? ` · ${draft.meta.elapsed_ms} ms` : ''}</summary>
          <pre>{draft.meta.sql}</pre>
        </details>
      )}

      {draft.meta && (draft.meta.prompt_tokens || draft.meta.completion_tokens) ? (
        <footer className="answer-foot">
          <span>
            tokens: {draft.meta.prompt_tokens ?? 0} / {draft.meta.completion_tokens ?? 0}
          </span>
          <div className="answer-actions">
            <button className="link" type="button" onClick={copyInsight} disabled={!draft.insight}>
              {copied ? '已复制' : '复制结论'}
            </button>
            {draft.question && onAsk && (
              <button className="link" type="button" onClick={() => onAsk(draft.question!)}>
                再问一次
              </button>
            )}
            {draft.question && (
              <button className="link" type="button" onClick={submitFeedback} disabled={feedbackSent}>
                {feedbackSent ? '已提交反馈' : '反馈数据有误'}
              </button>
            )}
          </div>
        </footer>
      ) : null}
    </article>
  )
}
