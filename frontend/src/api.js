// 后端 API 封装
const BASE = ''

async function jsonReq(url, opts = {}) {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function getSample() {
  return jsonReq('/api/sample')
}

export function runCheck(payload) {
  return jsonReq('/api/check', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function saveGlossary(glossary) {
  return jsonReq('/api/glossary/save', {
    method: 'POST',
    body: JSON.stringify({ glossary }),
  })
}

export function resetGlossary() {
  return jsonReq('/api/glossary/reset', { method: 'POST' })
}

export function getFeedback() {
  return jsonReq('/api/feedback')
}

export function reviewIssue(payload) {
  return jsonReq('/api/review', { method: 'POST', body: JSON.stringify(payload) })
}

export function addException(payload) {
  return jsonReq('/api/exceptions/add', { method: 'POST', body: JSON.stringify(payload) })
}

export function removeException(payload) {
  return jsonReq('/api/exceptions/remove', { method: 'POST', body: JSON.stringify(payload) })
}

export function generateReport(payload) {
  return jsonReq('/api/report/generate', { method: 'POST', body: JSON.stringify(payload) })
}

// ---------- 双语文本解析（粘贴 / 文件通用）----------
// 支持每行: 源文<TAB>译文 | 源文,译文 | "源文","译文"
export function parseBilingualText(text) {
  const lines = String(text || '').split(/\r?\n/)
  const out = []
  for (const raw of lines) {
    const line = raw.trim()
    if (!line || line.startsWith('#') || line.startsWith('//')) continue
    const pair = splitPair(line)
    if (pair && (pair[0].trim() || pair[1].trim())) {
      out.push({ source: pair[0].trim(), target: pair[1].trim() })
    }
  }
  return out
}

function splitPair(line) {
  let parts
  if (line.includes('\t')) parts = line.split('\t')
  else if (/^".*",".*"$/.test(line) || /^".*",.*$/.test(line)) parts = parseCsvLine(line)
  else {
    const idx = line.indexOf(',')
    parts = idx === -1 ? [line] : [line.slice(0, idx), line.slice(idx + 1)]
  }
  if (parts.length < 2) return null
  return [unquote(parts[0]), unquote(parts[1])]
}

function parseCsvLine(line) {
  // 简易 CSV 行解析（支持引号包裹与转义双引号）
  const out = []
  let cur = '', inQ = false
  for (let i = 0; i < line.length; i++) {
    const c = line[i]
    if (inQ) {
      if (c === '"' && line[i + 1] === '"') { cur += '"'; i++ }
      else if (c === '"') inQ = false
      else cur += c
    } else if (c === '"') inQ = true
    else if (c === ',') { out.push(cur); cur = '' }
    else cur += c
  }
  out.push(cur)
  return out
}

function unquote(s) {
  const t = s.trim()
  if (t.length >= 2 && t.startsWith('"') && t.endsWith('"')) return t.slice(1, -1)
  return t
}
