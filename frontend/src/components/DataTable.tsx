import type { TableData } from '../api/types'

export function DataTable({ data, max = 50 }: { data: TableData; max?: number }) {
  const rows = data.rows.slice(0, max)
  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            {data.columns.map((column) => (
              <th key={column}>{column}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell === null || cell === undefined ? '-' : String(cell)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.rows.length > max && (
        <p className="table-note">
          共 {data.rows.length} 行，仅显示前 {max} 行
        </p>
      )}
    </div>
  )
}
