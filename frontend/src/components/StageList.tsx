import { useState } from 'react'
import type { Stage } from '../api/types'

export function StageList({ stages }: { stages: Stage[] }) {
  const [open, setOpen] = useState(false)
  if (!stages.length) return null

  return (
    <div className="aa-wrap">
      <button className="aa-bar" onClick={() => setOpen(!open)} type="button">
        <span className="aa-bar-icon">⌁</span>
        分析过程
        <span className="aa-bar-arrow">{open ? '▾' : '▸'}</span>
        <span className="aa-bar-hint">{open ? '点击收起' : '点击展开'}</span>
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
    </div>
  )
}
