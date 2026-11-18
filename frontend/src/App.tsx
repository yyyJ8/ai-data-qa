import { useState } from 'react'
import { ChatPage } from './pages/ChatPage'
import { ConfigPage } from './pages/ConfigPage'
import { DataPage } from './pages/DataPage'
import { FeedbackPage } from './pages/FeedbackPage'
import { ModelPage } from './pages/ModelPage'

type Page = 'qa' | 'config' | 'model' | 'data' | 'feedback'

interface NavChild {
  id: Page
  label: string
}

interface NavGroup {
  id: string
  label: string
  icon: string
  page?: Page
  children?: NavChild[]
}

const NAV: NavGroup[] = [
  { id: 'qa', label: '智能问数', icon: '◈', page: 'qa' },
  {
    id: 'system',
    label: '系统管理',
    icon: '⚙',
    children: [{ id: 'config', label: '应用配置' }],
  },
  {
    id: 'feedback-group',
    label: '反馈管理',
    icon: '⚑',
    children: [{ id: 'feedback', label: '回复校对' }],
  },
]

const PAGE_TITLES: Record<Page, string> = {
  qa: 'AI 智能问数对话',
  config: '应用配置',
  model: '模型配置',
  data: '数据台账',
  feedback: '回复校对',
}

const PARENT: Record<Page, string | null> = {
  qa: null,
  config: '系统管理',
  model: '系统管理',
  data: null,
  feedback: '反馈管理',
}

export default function App() {
  const [page, setPage] = useState<Page>('qa')
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({ system: true })
  const [sessionOpen, setSessionOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)

  const toggleGroup = (id: string) =>
    setOpenGroups((prev) => ({ ...prev, [id]: !prev[id] }))

  const go = (target: Page) => setPage(target)

  const isChildActive = (group: NavGroup) => group.children?.some((c) => c.id === page)

  return (
    <div className="app">
      <header className="topbar">
        <div className="topbar-brand">
          <span className="brand-mark">▁▂▃</span>
          <span>AI问数</span>
        </div>
        <div className="topbar-right">
          <button className="topbar-link" type="button" onClick={() => setPage('data')} title="数据台账">
            ▤ 台账
          </button>
          <button className="icon-btn" type="button" title="消息通知">
            🔔
          </button>
          <button className="avatar-btn" type="button" onClick={() => setMenuOpen(!menuOpen)}>
            管
          </button>
          {menuOpen && (
            <div className="avatar-menu">
              <div className="muted small">版本 v0.4.0</div>
              <button type="button" onClick={() => window.location.reload()}>
                重新加载
              </button>
            </div>
          )}
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <nav>
            {NAV.map((group) =>
              group.children ? (
                <div key={group.id} className="nav-group">
                  <button
                    type="button"
                    className={`nav-item${isChildActive(group) ? ' group-active' : ''}`}
                    onClick={() => toggleGroup(group.id)}
                  >
                    <span className="nav-icon">{group.icon}</span>
                    <span>{group.label}</span>
                    <span className={`nav-arrow${openGroups[group.id] ? ' open' : ''}`}>›</span>
                  </button>
                  {openGroups[group.id] && (
                    <div className="nav-children">
                      {group.children.map((child) => (
                        <button
                          key={child.id}
                          type="button"
                          className={`nav-child${page === child.id ? ' active' : ''}`}
                          onClick={() => go(child.id)}
                        >
                          {child.label}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ) : (
                <button
                  key={group.id}
                  type="button"
                  className={`nav-item${page === group.page ? ' active' : ''}`}
                  onClick={() => group.page && go(group.page)}
                >
                  <span className="nav-icon">{group.icon}</span>
                  <span>{group.label}</span>
                </button>
              ),
            )}
          </nav>
          <div className="sidebar-foot">
            <span className="muted small">华鲲振宇 · 实操作业</span>
          </div>
        </aside>

        <main className="main">
          <div className="content-head">
            {page === 'qa' ? (
              <>
                <button
                  className="icon-btn"
                  type="button"
                  title="展开/收起会话列表"
                  onClick={() => setSessionOpen(!sessionOpen)}
                >
                  ☰
                </button>
                <h1>{PAGE_TITLES.qa}</h1>
                <span className="icon-btn ghost-holder" />
              </>
            ) : (
              <div className="breadcrumb">
                {PARENT[page] && (
                  <>
                    {page === 'model' ? (
                      <button type="button" className="crumb-link" onClick={() => setPage('config')}>
                        {PARENT[page]}
                      </button>
                    ) : (
                      <span>{PARENT[page]}</span>
                    )}
                    <span className="crumb-sep">/</span>
                  </>
                )}
                <span>{PAGE_TITLES[page]}</span>
              </div>
            )}
          </div>

          <div className="content-body">
            {page === 'qa' && <ChatPage sessionOpen={sessionOpen} />}
            {page === 'config' && <ConfigPage onNavigate={(target) => setPage(target)} />}
            {page === 'model' && <ModelPage />}
            {page === 'data' && <DataPage />}
            {page === 'feedback' && <FeedbackPage />}
          </div>
        </main>
      </div>
    </div>
  )
}
