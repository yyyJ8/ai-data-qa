import { useState } from 'react'
import type { Stage } from '../api/types'

export function StageList({ stages }: { stages: Stage[] }) {
  const [open, setOpen] = useState(true)
  if (!stages.length) return null

  return (
    <section className="module">
      <button className="module-title collapsible" onClick={() => setOpen(!open)} type="button">
        <span className="num">1</span>
        分析过程
        <span className="chevron">{open ? '收起' : '展开'}</span>
      </button>
      {open && (
        <ol className="stages">
          {stages.map((stage) => (
            <li key={stage.step} className="stage">
              <span className="stage-title">{stage.title}</span>
              <pre className={stage.title.includes('SQL') ? 'stage-detail sql' : 'stage-detail'}>
                {stage.detail}
              </pre>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
