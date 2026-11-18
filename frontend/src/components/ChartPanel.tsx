import { useEffect, useRef } from 'react'
import * as echarts from 'echarts'
import type { TableData } from '../api/types'

export function ChartPanel({ type, data }: { type: string; data: TableData }) {
  const container = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = container.current
    if (!el) return

    const numeric = data.columns
      .map((_, index) => index)
      .filter((index) => index > 0 && data.rows.some((row) => typeof row[index] === 'number'))
    if (!numeric.length) return

    const categories = data.rows.map((row) => String(row[0] ?? ''))
    const series = numeric.map((index) => ({
      name: data.columns[index],
      data: data.rows.map((row) => Number(row[index] ?? 0)),
    }))

    const chart = echarts.init(el)
    const common = {
      tooltip: { trigger: type === 'pie' ? 'item' : 'axis' },
      legend: { bottom: 0, textStyle: { fontSize: 11 } },
      grid: { left: 48, right: 16, top: 24, bottom: 44 },
    }

    if (type === 'pie') {
      const index = numeric[0]
      chart.setOption({
        tooltip: { trigger: 'item' },
        legend: { bottom: 0 },
        series: [
          {
            type: 'pie',
            radius: ['42%', '68%'],
            label: { formatter: '{b} {d}%' },
            data: data.rows.map((row) => ({
              name: String(row[0] ?? ''),
              value: Number(row[index] ?? 0),
            })),
          },
        ],
      })
    } else {
      chart.setOption({
        ...common,
        xAxis: { type: 'category', data: categories, axisLabel: { fontSize: 11 } },
        yAxis: { type: 'value', axisLabel: { fontSize: 11 } },
        series: series.map((item) => ({
          ...item,
          type: type === 'line' ? 'line' : 'bar',
          smooth: type === 'line',
          barMaxWidth: 36,
        })),
      })
    }

    const observer = new ResizeObserver(() => chart.resize())
    observer.observe(el)
    return () => {
      observer.disconnect()
      chart.dispose()
    }
  }, [type, data])

  const numeric = data.columns.some(
    (_, index) => index > 0 && data.rows.some((row) => typeof row[index] === 'number'),
  )
  if (!numeric) return <p className="muted">当前结果没有可绘制的数值列</p>

  return <div className="chart" ref={container} />
}
