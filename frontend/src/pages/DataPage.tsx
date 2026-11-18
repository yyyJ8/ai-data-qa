import { useEffect, useState } from 'react'
import { apiClient, exportUrl } from '../api/client'
import type { PagedTable } from '../api/types'
import { DataTable } from '../components/DataTable'

const TABLES = [
  { id: 'dim_unit', label: '经营单元' },
  { id: 'dim_industry', label: '行业' },
  { id: 'dim_product_line', label: '产品线' },
  { id: 'dim_product', label: '产品型号' },
  { id: 'dim_customer', label: '客户' },
  { id: 'fact_target', label: '年度目标' },
  { id: 'fact_revenue', label: '收入明细' },
  { id: 'fact_order', label: '订单' },
  { id: 'fact_collection', label: '回款' },
  { id: 'fact_ppl', label: 'PPL 项目' },
]

const PAGE_SIZE = 20

export function DataPage() {
  const [table, setTable] = useState(TABLES[0].id)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [data, setData] = useState<PagedTable | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!query) return
    const timer = window.setTimeout(() => {
      setSearch(query)
      setPage(1)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) })
    if (search.trim()) params.set('q', search.trim())
    apiClient
      .get<PagedTable>(`/api/data/${table}?${params.toString()}`)
      .then((result) => {
        if (!cancelled) setData(result)
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [table, page, search])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>数据台账</h1>
          <p className="muted small">业务库只读浏览，支持关键词过滤与 Excel 导出</p>
        </div>
        <a className="btn" href={exportUrl(table, search)} target="_blank" rel="noreferrer">
          导出 Excel
        </a>
      </header>

      <div className="toolbar">
        <select
          value={table}
          onChange={(event) => {
            setTable(event.target.value)
            setPage(1)
          }}
        >
          {TABLES.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}（{item.id}）
            </option>
          ))}
        </select>
        <input
          value={query}
          placeholder="搜索表内文本字段…"
          onChange={(event) => setQuery(event.target.value)}
        />
        {data && <span className="muted small">共 {data.total} 行</span>}
      </div>

      {error && <div className="error-banner">{error}</div>}
      {loading && <p className="muted">加载中…</p>}

      {data && !loading && (
        <>
          <DataTable data={data} max={PAGE_SIZE} />
          <div className="pager">
            <button type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              上一页
            </button>
            <span className="muted small">
              第 {page} / {totalPages} 页
            </span>
            <button type="button" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              下一页
            </button>
          </div>
        </>
      )}
    </div>
  )
}
