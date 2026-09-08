const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`

function setDateRange(start: string, end: string) {
  const inputs = document.querySelectorAll<HTMLInputElement>('.date-range input[type="date"]')
  if (inputs.length < 2) return
  for (const [input, value] of [[inputs[0], start], [inputs[1], end]] as const) {
    const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')?.set
    setter?.call(input, value)
    input.dispatchEvent(new Event('input', { bubbles: true }))
    input.dispatchEvent(new Event('change', { bubbles: true }))
  }
}

function range(kind: 'week' | 'month' | 'year') {
  const d = new Date()
  const y = d.getFullYear()
  const m = d.getMonth()
  if (kind === 'year') return { start: `${y}-01-01`, end: `${y}-12-31` }
  if (kind === 'month') {
    const last = new Date(y, m + 1, 0)
    return { start: `${y}-${String(m + 1).padStart(2,'0')}-01`, end: iso(last) }
  }
  const start = new Date(y, m, d.getDate() - d.getDay() + 1)
  const end = new Date(y, m, d.getDate() - d.getDay() + 7)
  return { start: iso(start), end: iso(end) }
}

function enhancePeriodControls(root: ParentNode) {
  const cards = root.querySelector<HTMLElement>('.period-cards')
  if (!cards || cards.dataset.enhanced === '1') return
  cards.dataset.enhanced = '1'
  cards.innerHTML = '<div class="quick-range"><span class="quick-range-title">快速设置</span><button type="button" data-range="week">本周</button><button type="button" data-range="month">本月</button><button type="button" data-range="year">今年</button></div>'
  cards.querySelectorAll<HTMLButtonElement>('button[data-range]').forEach(btn => {
    btn.addEventListener('click', () => {
      const kind = btn.dataset.range as 'week' | 'month' | 'year'
      const r = range(kind)
      setDateRange(r.start, r.end)
      cards.querySelectorAll('button[data-range]').forEach(b => b.classList.toggle('selected', b === btn))
    })
  })
}

function hideSmallPieLabels(root: ParentNode) {
  root.querySelectorAll<HTMLElement>('.pie-wrap').forEach(wrap => {
    const legend = wrap.parentElement?.querySelector('.pie-legend')
    if (!legend) return
    const percentages = [...legend.querySelectorAll('.pie-legend-row .legend-value')].map(el => {
      const m = el.textContent?.match(/·\s*(\d+)%/)
      return m ? Number(m[1]) : 0
    })
    const labels = [...wrap.querySelectorAll<SVGTextElement>('svg text')]
    labels.forEach((label, index) => {
      if (index < percentages.length && percentages[index] < 8) label.style.visibility = 'hidden'
    })
  })
}

const observer = new MutationObserver(() => {
  enhancePeriodControls(document)
  hideSmallPieLabels(document)
})
observer.observe(document.body, { childList: true, subtree: true })

requestAnimationFrame(() => {
  enhancePeriodControls(document)
  hideSmallPieLabels(document)
})
