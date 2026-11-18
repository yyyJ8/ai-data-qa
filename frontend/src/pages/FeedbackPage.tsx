import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client'
import type { FeedbackItem, PromoteResult } from '../api/types'

const FILTERS = [
  { value: '', label: '全部' },
  { value: '待处理', label: '待处理' },
  { value: '已处理', label: '已处理' },
]

export function FeedbackPage() {
  const [items, setItems] = useState<FeedbackItem[]>([])
  const [filter, setFilter] = useState('')
  const [selected, setSelected] = useState<FeedbackItem | null>(null)
  const [remark, setRemark] = useState('')
  const [correctedSql, setCorrectedSql] = useState('')
  const [status, setStatus] = useState<'待处理' | '已处理'>('已处理')
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      const query = filter ? `?status=${encodeURIComponent(filter)}` : ''
      setItems(await apiClient.get<FeedbackItem[]>(`/api/feedback${query}`))
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    }
  }, [filter])

  useEffect(() => {
    load()
  }, [load])

  const open = (item: FeedbackItem) => {
    setSelected(item)
    setStatus(item.status)
    setRemark(item.remark ?? '')
    setCorrectedSql(item.corrected_sql ?? '')
  }

  const save = async () => {
    if (!selected) return
    try {
      const updated = await apiClient.patch<FeedbackItem>(`/api/feedback/${selected.feedback_id}`, {
        status,
        remark,
        corrected_sql: correctedSql,
      })
      setSelected(updated)
      setMessage('处理已保存')
      await load()
      window.setTimeout(() => setMessage(null), 2500)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    }
  }

  const promote = async () => {
    if (!selected) return
    try {
      if (correctedSql.trim() !== (selected.corrected_sql ?? '').trim()) {
        await apiClient.patch<FeedbackItem>(`/api/feedback/${selected.feedback_id}`, {
          corrected_sql: correctedSql,
        })
      }
      const result = await apiClient.post<PromoteResult>(
        `/api/feedback/${selected.feedback_id}/promote`,
        {},
      )
      setSelected(null)
      setMessage(`已写入评测集：${result.case_id}（${result.rows} 行）`)
      await load()
      window.setTimeout(() => setMessage(null), 3500)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error))
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>回复校对</h1>
          <p className="muted small">用户标注「数据有误」的记录，处理后可回灌为评测样本</p>
        </div>
        <div className="tabs">
          {FILTERS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={filter === item.value ? 'tab active' : 'tab'}
              onClick={() => setFilter(item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </header>

      {message && <div className="toast">{message}</div>}

      <div className="card">
        {items.length === 0 ? (
          <p className="muted">暂无反馈</p>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: 48 }}>#</th>
                <th>问题</th>
                <th style={{ width: 200 }}>原因</th>
                <th style={{ width: 100 }}>状态</th>
                <th style={{ width: 160 }}>提交时间</th>
                <th style={{ width: 90 }}>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={item.feedback_id}>
                  <td>{index + 1}</td>
                  <td>{item.question}</td>
                  <td>{item.reason || '-'}</td>
                  <td>
                    <span className={`tag ${item.status === '待处理' ? 'orange' : 'green'}`}>
                      {item.status}
                    </span>
                  </td>
                  <td>{item.created_at}</td>
                  <td>
                    {item.promoted_at ? (
                      <span className="muted small">已回灌</span>
                    ) : (
                      <button type="button" className="link" onClick={() => open(item)}>
                        处理
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <div className="modal-mask" onClick={() => setSelected(null)}>
          <div className="modal" onClick={(event) => event.stopPropagation()}>
            <h3>处理反馈</h3>
            <p className="muted small">{selected.question}</p>
            {selected.sql && <pre className="sql-preview">{selected.sql}</pre>}

            <label className="field">
              <span className="field-label">状态</span>
              <select value={status} onChange={(event) => setStatus(event.target.value as '待处理' | '已处理')}>
                <option value="待处理">待处理</option>
                <option value="已处理">已处理</option>
              </select>
            </label>

            <label className="field">
              <span className="field-label">修正 SQL（写入评测集用，需可执行且返回数据）</span>
              <textarea
                rows={4}
                className="mono"
                value={correctedSql}
                placeholder="SELECT unit_name AS 单元 FROM dim_unit WHERE ..."
                onChange={(event) => setCorrectedSql(event.target.value)}
              />
            </label>

            <label className="field">
              <span className="field-label">处理备注</span>
              <textarea rows={2} value={remark} onChange={(event) => setRemark(event.target.value)} />
            </label>

            <div className="row-gap">
              <button className="btn primary" type="button" onClick={save}>
                保存
              </button>
              <button
                className="btn"
                type="button"
                onClick={promote}
                disabled={!!selected.promoted_at || !correctedSql.trim()}
              >
                写入评测集
              </button>
              <button className="btn" type="button" onClick={() => setSelected(null)}>
                取消
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
