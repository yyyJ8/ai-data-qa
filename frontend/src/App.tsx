import { useState } from 'react'
import { ChatPage } from './pages/ChatPage'
import { DataPage } from './pages/DataPage'

type Page = 'qa' | 'data' | 'config' | 'feedback'

const NAV: { id: Page; label: string; hint: string }[] = [
  { id: 'qa', label: '智能问数', hint: '自然语言取数' },
  { id: 'data', label: '数据台账', hint: '浏览与导出' },
  { id: 'config', label: '应用配置', hint: '模型与开场白' },
  { id: 'feedback', label: '回复校对', hint: '反馈处理' },
]

function ComingSoon({ label }: { label: string }) {
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <h1>{label}</h1>
          <p className="muted small">该页面将在下一步实现</p>
        </div>
      </header>
    </div>
  )
}

export default function App() {
  const [page, setPage] = useState<Page>('qa')

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <span className="logo">AI</span>
          <span>AI问数</span>
        </div>
        <nav>
          {NAV.map((item) => (
            <button
              key={item.id}
              type="button"
              className={`nav-item${page === item.id ? ' active' : ''}`}
              onClick={() => setPage(item.id)}
            >
              <span className="nav-label">{item.label}</span>
              <span className="nav-hint">{item.hint}</span>
            </button>
          ))}
        </nav>
        <footer className="sidebar-foot">
          <span className="muted small">华鲲振宇 · 实操作业</span>
        </footer>
      </aside>

      <main className="main">
        {page === 'qa' && <ChatPage />}
        {page === 'data' && <DataPage />}
        {page === 'config' && <ComingSoon label="应用配置" />}
        {page === 'feedback' && <ComingSoon label="回复校对" />}
      </main>
    </div>
  )
}
