import type { AssistantDraft } from '../api/types'
import { ChartPanel } from './ChartPanel'
import { DataTable } from './DataTable'
import { StageList } from './StageList'

export function AnswerCard({ draft }: { draft: AssistantDraft }) {
  const showChart = draft.chart && draft.chart !== 'table' && draft.table && draft.chart !== 'none'

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
        </footer>
      ) : null}
    </article>
  )
}
