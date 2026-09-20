<script setup>
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts'
import { inject } from 'vue'
import { reviewIssue, addException, removeException, getFeedback, generateReport } from '../api'

const { result, entries, loading, notify, llm, sourceLabel, glossary } = inject('termguard')

const filterType = ref('全部')
const onlyHigh = ref(false)
const dimLines = ref(new Set())   // 被忽略（且已记录）的行 -> 淡化
const acted = ref(new Set())      // 已操作过的 issue key
const feedback = ref(null)        // 闭环反馈状态
const view = ref('issues')        // issues | all

// AI 质检报告
const reportText = ref('')
const reportMode = ref('')
const generating = ref(false)
async function genReport() {
  if (!result.value) return
  generating.value = true
  reportText.value = ''
  try {
    const res = await generateReport({
      name: sourceLabel.value,
      stats: stats.value,
      issues: result.value.issues,
      llm: { enabled: llm.enabled, api_key: llm.apiKey, base_url: llm.baseUrl, model: llm.model },
    })
    reportMode.value = res.mode
    reportText.value = res.text || '（报告为空）'
    notify(res.mode === 'ai' ? '🤖 AI 报告已生成' : '📊 已生成规则统计总结（未用 AI）')
  } catch (e) {
    reportText.value = '报告生成失败，请确认后端服务正常。'
    notify('❌ 报告生成失败')
  } finally {
    generating.value = false
  }
}
// 极简 Markdown -> HTML（仅处理本报告用到的语法，避免引入依赖）
function esc(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function renderMd(text) {
  return esc(String(text || ''))
    .replace(/^### (.*)$/gm, '<h4>$1</h4>')
    .replace(/^## (.*)$/gm, '<h3>$1</h3>')
    .replace(/^\d+\. (.*)$/gm, '<li>$1</li>')
    .replace(/^- (.*)$/gm, '<li>$1</li>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
    .replace(/\n([^\n<][^\n]*)/g, '<p>$1</p>')
    .replace(/\n/g, '')
}

const stats = computed(() => result.value?.stats || null)

const lineIssueMap = computed(() => {
  const m = {}
  for (const i of result.value?.issues || []) (m[i.line] = m[i.line] || []).push(i)
  return m
})

const issues = computed(() => {
  if (!result.value) return []
  let list = result.value.issues
  if (filterType.value !== '全部') list = list.filter(i => i.type === filterType.value)
  if (onlyHigh.value) list = list.filter(i => i.sev === 'high')
  return list
})
const typeCounts = computed(() => {
  const m = {}
  for (const i of result.value?.issues || []) m[i.type] = (m[i.type] || 0) + 1
  return m
})

const passRate = computed(() => {
  if (!stats.value) return 0
  const total = stats.value.total_lines
  return total ? Math.round(((total - stats.value.issue_lines) / total) * 100) : 0
})

const entryMap = computed(() => {
  const m = {}
  for (const e of entries.value) m[e.line] = e
  return m
})

function issuesOf(line) { return lineIssueMap.value[line] || [] }

function scrollToIssue(line) {
  view.value = 'issues'
  filterType.value = '全部'
  onlyHigh.value = false
  nextTick(() => {
    const el = document.getElementById(`issue-${line}-0`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    // 高亮闪烁提示
    if (el) {
      el.classList.add('flash')
      setTimeout(() => el.classList.remove('flash'), 1800)
    }
  })
}

function issueKey(it) { return `${it.line}|${it.type}|${it.title}` }

// ---------- 反馈闭环 ----------
async function loadFeedback() {
  try {
    const f = await getFeedback()
    if (f.ok) feedback.value = f
  } catch (e) { /* 忽略：闭环面板非关键路径 */ }
}

async function act(it, verdict) {
  const key = issueKey(it)
  if (acted.value.has(key)) return
  acted.value.add(key)
  const ent = entryMap.value[it.line]
  try {
    await reviewIssue({
      line: it.line, type: it.type, title: it.title,
      source: ent?.source || '', target: ent?.target || '',
      term: it.term || '', verdict,
    })
    if (verdict === 'ignore') {
      const s = new Set(dimLines.value); s.add(it.line); dimLines.value = s
      notify('🗑 已记录为忽略 —— 同一词条忽略满 2 次将触发豁免建议')
    } else {
      notify('✅ 已记录：确认问题 —— 同一词条多次确认将触发术语提醒')
    }
    await loadFeedback()
  } catch (e) {
    acted.value.delete(key)
    notify('❌ 记录失败：无法连接后端')
  }
}

async function grantException(src) {
  try {
    await addException({ source: src, reason: '译员忽略 ≥2 次' })
    await loadFeedback()
    notify(`⚡ 已豁免「${src}」—— 重新质检后该词条将不再报错`)
  } catch (e) { notify('❌ 豁免失败') }
}

async function revokeException(src) {
  try {
    await removeException({ source: src })
    await loadFeedback()
    notify('↩ 已移除豁免')
  } catch (e) { notify('❌ 操作失败') }
}

const delta = computed(() => {
  if (!result.value?.prev || !stats.value) return null
  return stats.value.issue_lines - result.value.prev.issue_lines
})
const deltaText = computed(() => {
  if (delta.value === null) return ''
  if (delta.value < 0) return `↓ 减少 ${-delta.value} 个问题句`
  if (delta.value > 0) return `↑ 增多 ${delta.value} 个问题句`
  return '持平'
})

const typeColors = {
  '术语': '#a78bfa', '术语不一致': '#7aa2ff', '占位符': '#22d3ee',
  '数字': '#fbbf24', '漏译': '#fb7185', '未翻译': '#fb7185',
  '疑似漏译': '#fb923c', 'AI 复核': '#34d399',
}

// ---------- 图表 ----------
const pieRef = ref(null)
const gaugeRef = ref(null)
let pieChart = null, gaugeChart = null

function renderCharts() {
  const s = stats.value
  if (!s || !pieRef.value || !gaugeRef.value) return
  // v-else-if 分支切换会重建容器 DOM，旧实例必须释放后重新 init，否则图表丢失
  if (pieChart) { pieChart.dispose(); pieChart = null }
  if (gaugeChart) { gaugeChart.dispose(); gaugeChart = null }
  pieChart = echarts.init(pieRef.value)
  const byType = s.by_type || {}
  const pieData = Object.entries(byType).map(([name, value]) => ({ name, value }))
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c} 处 ({d}%)', backgroundColor: '#101a33', borderColor: 'rgba(124,148,220,.3)', textStyle: { color: '#e8edfb' } },
    legend: { bottom: 0, icon: 'circle', itemWidth: 8, itemHeight: 8, textStyle: { color: '#93a0c0', fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['58%', '80%'], center: ['50%', '44%'],
      itemStyle: { borderColor: '#0c1120', borderWidth: 2, borderRadius: 4 },
      label: { show: false },
      data: pieData.map(d => ({ ...d, itemStyle: { color: typeColors[d.name] || '#5b8cff' } })),
    }],
  }, true)

  const total = s.total_lines
  const clean = s.clean_lines
  gaugeChart = echarts.init(gaugeRef.value)
  gaugeChart.setOption({
    series: [{
      type: 'gauge', startAngle: 220, endAngle: -40, min: 0, max: total || 1,
      radius: '100%', center: ['50%', '52%'],
      progress: { show: true, width: 13, itemStyle: { color: { type: 'linear', x: 0, y: 0, x2: 1, y2: 0, colorStops: [{ offset: 0, color: '#22d3ee' }, { offset: 1, color: '#8b5cf6' }] } } },
      axisLine: { lineStyle: { width: 13, color: [[1, 'rgba(124,148,220,.14)']] } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      pointer: { show: false },
      anchor: { show: false },
      title: { show: false },
      detail: {
        valueAnimation: true, offsetCenter: [0, '62%'],
        formatter: v => `{a|${Math.round(v / (total || 1) * 100)}%}`,
        rich: { a: { fontSize: 26, fontWeight: 800, color: '#e8edfb' } },
      },
      data: [{ value: clean }],
    }],
  }, true)
}

function resizeCharts() {
  pieChart?.resize(); gaugeChart?.resize()
}

watch(() => result.value, async () => {
  dimLines.value = new Set()
  acted.value = new Set()
  filterType.value = '全部'
  onlyHigh.value = false
  view.value = 'issues'
  reportText.value = ''
  reportMode.value = ''
  await nextTick()
  renderCharts()
  loadFeedback()
})

window.addEventListener('resize', resizeCharts)
onBeforeUnmount(() => {
  window.removeEventListener('resize', resizeCharts)
  pieChart?.dispose(); gaugeChart?.dispose()
})
</script>

<template>
  <!-- 空状态 -->
  <div v-if="!result && !loading" class="panel empty">
    <div class="empty-inner">
      <div class="empty-logo">🛡️</div>
      <h2>术语卫士 · 待命</h2>
      <p>左侧载入待检双语文本与术语库，点击「开始质检」<br />规则引擎将扫描术语一致性、占位符、数字与漏译问题</p>
      <div class="empty-tags">
        <span>🔤 术语一致性</span><span>🧩 占位符</span><span>🔢 数字</span><span>🚫 漏译</span><span>🤖 AI 语境复核</span>
      </div>
    </div>
  </div>

  <!-- 运行中 -->
  <div v-else-if="loading" class="panel empty">
    <div class="empty-inner">
      <div class="scanning"><span></span><span></span><span></span></div>
      <h2>正在质检…</h2>
      <p>规则引擎扫描占位符 / 数字 / 术语…</p>
    </div>
  </div>

  <!-- 报告 -->
  <template v-else-if="result">
    <div class="report fade-up">
      <!-- 头部统计卡 -->
      <div class="stat-row">
        <div class="panel stat-card hero">
          <div class="stat-label">通过率 <span class="pass-emoji" v-if="passRate >= 60">✅</span><span v-else>⚠️</span></div>
          <div class="stat-num grad-num">{{ passRate }}<small>%</small></div>
          <div class="stat-sub">{{ stats.clean_lines }} / {{ stats.total_lines }} 句无问题</div>
        </div>
        <div class="panel stat-card">
          <div class="stat-label">检查句数</div>
          <div class="stat-num">{{ stats.total_lines }}</div>
          <div class="stat-sub">双语对照行</div>
        </div>
        <div class="panel stat-card">
          <div class="stat-label">问题句</div>
          <div class="stat-num warn-num">{{ stats.issue_lines }}</div>
          <div class="stat-sub">含 {{ stats.high }} 处高危</div>
        </div>
        <div class="panel stat-card">
          <div class="stat-label">命中问题</div>
          <div class="stat-num red-num">{{ stats.total_issues }}</div>
          <div class="stat-sub">按规则归类</div>
        </div>
        <div class="panel stat-card ai">
          <div class="stat-label">AI 复核</div>
          <div class="stat-num">{{ stats.ai_issues || 0 }}</div>
          <div class="stat-sub">{{ result.llm_enabled ? '已启用 LLM' : '未启用（降级为纯规则）' }}</div>
        </div>
      </div>

      <div v-if="result.ai_error" class="ai-note">🤖 {{ result.ai_error }}</div>

      <!-- 反馈闭环条 -->
      <div v-if="feedback" class="panel loop-bar">
        <div class="loop-info">
          <span class="loop-title">🔄 反馈闭环</span>
          <span class="loop-stat">✓ 已确认 {{ feedback.confirm }} · 已忽略 {{ feedback.ignore }}</span>
          <span v-if="result.prev" class="loop-regress" :class="delta > 0 ? 'worse' : delta < 0 ? 'better' : 'flat'">
            较上次检查：问题句 {{ result.prev.issue_lines }} → {{ stats.issue_lines }}（{{ deltaText }}）
          </span>
        </div>
        <div class="loop-actions">
          <span v-for="s in feedback.exception_suggestions" :key="'sug' + s.source" class="chip-box sug">
            「{{ s.source }}」已忽略 {{ s.count }} 次，建议豁免
            <button class="btn tiny" @click="grantException(s.source)">加入豁免</button>
          </span>
          <span v-for="a in feedback.term_alerts" :key="'alert' + a.source" class="chip-box alert">
            「{{ a.source }}」已确认违规 {{ a.count }} 次，建议在术语库备注中强调规范
          </span>
          <span v-for="e in feedback.exceptions" :key="'ex' + e.source" class="chip-box ex">
            ⚡ 豁免中：{{ e.source }}
            <button class="btn tiny ghost" @click="revokeException(e.source)">✕ 移除</button>
          </span>
          <span v-if="!feedback.exception_suggestions.length && !feedback.term_alerts.length && !feedback.exceptions.length"
                class="loop-empty">暂无待处理反馈 —— 对问题点「✓ 已修复 / 忽略」，系统会沉淀规则，越用越准</span>
        </div>
      </div>

      <!-- AI 质检报告 -->
      <div class="panel ai-report">
        <div class="ar-head">
          <div class="ar-title">🤖 AI 质检报告
            <span class="ar-sub">把技术问题翻译成业务语言，给 PM / 客户看</span>
            <span v-if="reportMode === 'ai'" class="ar-tag ai">AI 生成</span>
            <span v-if="reportMode === 'rule'" class="ar-tag rule">规则统计</span>
          </div>
          <button class="btn tiny" :disabled="generating" @click="genReport">
            {{ generating ? '生成中…' : (reportText ? '↻ 重新生成' : '生成报告') }}
          </button>
        </div>
        <div v-if="generating" class="ar-loading">
          <span class="spinner2"></span> 正在让 AI 梳理本次质检的作用是…
        </div>
        <div v-else-if="reportText" class="ar-body" v-html="renderMd(reportText)"></div>
        <div v-else class="ar-empty">
          生成本次质检的<b>业务级总结</b>：问题集中在哪、哪些术语反复出错、先修什么、对玩家/品牌有什么影响。
        </div>
      </div>

      <!-- 图表区 -->
      <div class="chart-row">
        <div class="panel chart-card">
          <div class="chart-title">问题类型分布</div>
          <div ref="pieRef" class="chart-box"></div>
        </div>
        <div class="panel chart-card">
          <div class="chart-title">质量总览</div>
          <div ref="gaugeRef" class="chart-box gauge-box"></div>
          <div class="gauge-sub">无问题句占比</div>
        </div>
      </div>

      <!-- 明细面板 -->
      <div class="panel list-panel">
        <div class="list-head">
          <div class="seg-view">
            <button :class="['sv', view === 'issues' && 'on']" @click="view = 'issues'">
              ⚠ 问题视图<em>{{ issues.length }}</em>
            </button>
            <button :class="['sv', view === 'all' && 'on']" @click="view = 'all'">
              📋 全文对照<em>{{ entries.length }}</em>
            </button>
          </div>
          <div class="filters" v-if="view === 'issues'">
            <div class="chips">
              <button v-for="t in ['全部', ...Object.keys(typeCounts)]" :key="t"
                      :class="['chip', filterType === t && 'on']" @click="filterType = t">
                {{ t }}<em v-if="t !== '全部'">{{ typeCounts[t] }}</em>
              </button>
            </div>
            <label class="high-only"><input type="checkbox" v-model="onlyHigh" /> 只看高危</label>
          </div>
        </div>

        <!-- 全文对照视图 -->
        <div v-if="view === 'all'" class="all-view">
          <p class="all-hint">💡 绿 ✓ 为无问题句；带 ⚠ 的问题行点击可跳转到对应问题详情</p>
          <table class="full-table">
            <thead>
              <tr>
                <th style="width:56px">行</th>
                <th style="width:92px">状态</th>
                <th>英文源文</th>
                <th>中文译文</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in entries" :key="e.line"
                  :class="['ft-row', issuesOf(e.line).length ? 'bad' : 'ok', dimLines.has(e.line) && 'dim']"
                  @click="issuesOf(e.line).length && scrollToIssue(e.line)">
                <td class="ft-line">L{{ e.line }}</td>
                <td>
                  <span v-if="!issuesOf(e.line).length" class="st st-ok">✓ 无问题</span>
                  <span v-else class="st st-bad" title="点击查看详情">⚠ {{ issuesOf(e.line).length }} 处</span>
                </td>
                <td class="ft-src mono">{{ e.source }}</td>
                <td class="ft-tgt">{{ e.target || '（空）' }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <!-- 问题视图 -->
        <template v-else>
          <div v-if="!issues.length" class="no-issues">🎉 当前筛选下没有问题，质量很棒！</div>
          <div v-for="(it, idx) in issues" :key="it.line + it.type + it.title + idx"
               :id="`issue-${it.line}-${idx === 0 ? 0 : idx}`"
               class="issue" :class="{ dim: dimLines.has(it.line) }">
            <div class="issue-main">
              <span class="line-num">L{{ it.line }}</span>
              <span class="badge" :class="'badge-' + it.type">{{ it.type }}</span>
              <span class="sev-dot" :class="it.sev === 'high' ? 'red' : 'amber'" :title="it.sev === 'high' ? '高危' : '提醒'"></span>
              <span class="issue-title">{{ it.title }}</span>
              <div class="issue-actions">
                <button class="btn tiny act-ok" :disabled="acted.has(issueKey(it))"
                        @click="act(it, 'confirm')">✓ 已修复</button>
                <button class="btn tiny ghost" :disabled="acted.has(issueKey(it))"
                        @click="act(it, 'ignore')">{{ acted.has(issueKey(it)) ? '已记录' : '忽略' }}</button>
              </div>
            </div>
            <p class="issue-detail">{{ it.detail }}</p>
            <p v-if="it.fix" class="issue-fix">💡 {{ it.fix }}</p>
            <div v-if="entryMap[it.line]" class="seg-box">
              <div class="seg-line src"><span class="seg-tag">EN</span><span class="mono">{{ entryMap[it.line].source }}</span></div>
              <div class="seg-line tgt"><span class="seg-tag">中文</span><span>{{ entryMap[it.line].target || '（空）' }}</span></div>
            </div>
          </div>
        </template>
      </div>
    </div>
  </template>
</template>

<style scoped>
.empty { min-height: 560px; display: grid; place-items: center; }
.empty-inner { text-align: center; padding: 40px; }
.empty-logo { font-size: 58px; margin-bottom: 14px; filter: drop-shadow(0 0 24px rgba(91,140,255,.5)); }
.empty h2 { font-size: 22px; margin-bottom: 10px; }
.empty p { color: var(--txt-dim); font-size: 13.5px; line-height: 1.9; }
.empty-tags { margin-top: 22px; display: flex; gap: 8px; justify-content: center; flex-wrap: wrap; }
.empty-tags span { font-size: 12px; padding: 6px 13px; border-radius: 999px; background: rgba(255,255,255,.04); border: 1px solid var(--line); color: var(--txt-dim); }

.scanning { display: flex; gap: 8px; justify-content: center; margin-bottom: 20px; }
.scanning span { width: 12px; height: 12px; border-radius: 50%; background: var(--grad); animation: bounce .9s infinite ease-in-out; }
.scanning span:nth-child(2) { animation-delay: .15s; }
.scanning span:nth-child(3) { animation-delay: .3s; }
@keyframes bounce { 0%,100% { transform: translateY(0); opacity: .5 } 50% { transform: translateY(-12px); opacity: 1 } }

.report { display: flex; flex-direction: column; gap: 14px; }
.stat-row { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; }
.stat-card { padding: 15px 17px; }
.stat-label { font-size: 11.5px; color: var(--txt-dim); display: flex; align-items: center; gap: 6px; }
.pass-emoji { font-size: 12px; }
.stat-num { font-size: 30px; font-weight: 800; margin: 6px 0 2px; line-height: 1; }
.stat-num small { font-size: 16px; font-weight: 700; }
.grad-num { background: var(--grad); -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent; }
.warn-num { color: var(--amber); }
.red-num { color: var(--red); }
.stat-sub { font-size: 11px; color: var(--txt-faint); }
.stat-card.hero { border-color: rgba(91,140,255,.4); box-shadow: 0 0 30px rgba(91,140,255,.12); }

.ai-note { font-size: 12px; color: var(--amber); background: rgba(251,191,36,.08); border: 1px dashed rgba(251,191,36,.35); padding: 8px 13px; border-radius: 9px; }

/* 反馈闭环条 */
.loop-bar { padding: 12px 16px; display: flex; flex-direction: column; gap: 9px; border-color: rgba(52,211,153,.25); }
.loop-info { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
.loop-title { font-size: 13px; font-weight: 800; color: var(--green); }
.loop-stat { font-size: 12px; color: var(--txt-dim); }
.loop-regress { font-size: 12px; padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.loop-regress.better { color: #6ee7b7; background: rgba(52,211,153,.1); border: 1px solid rgba(52,211,153,.3); }
.loop-regress.worse { color: #fda4af; background: rgba(251,113,133,.1); border: 1px solid rgba(251,113,133,.3); }
.loop-regress.flat { color: var(--txt-dim); background: rgba(255,255,255,.04); border: 1px solid var(--line); }
.loop-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.chip-box { font-size: 12px; display: inline-flex; align-items: center; gap: 8px; padding: 5px 11px; border-radius: 9px; }
.chip-box.sug { background: rgba(251,191,36,.08); border: 1px solid rgba(251,191,36,.3); color: #fcd34d; }
.chip-box.alert { background: rgba(251,113,133,.07); border: 1px dashed rgba(251,113,133,.3); color: #fda4af; }
.chip-box.ex { background: rgba(34,211,238,.07); border: 1px solid rgba(34,211,238,.3); color: #67e8f9; }
.loop-empty { font-size: 11.5px; color: var(--txt-faint); padding: 2px 0; }

.issue-actions { display: flex; gap: 6px; }
.btn.act-ok { background: rgba(52,211,153,.12); border-color: rgba(52,211,153,.4); color: #6ee7b7; }
.btn.act-ok:hover { background: rgba(52,211,153,.22); }

/* AI 质检报告 */
.ai-report { padding: 16px 18px; border-color: rgba(139,92,246,.28); }
.ar-head { display: flex; justify-content: space-between; align-items: center; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.ar-title { font-size: 14px; font-weight: 800; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ar-sub { font-size: 11.5px; font-weight: 400; color: var(--txt-dim); }
.ar-tag { font-size: 10px; padding: 2px 8px; border-radius: 999px; font-weight: 700; letter-spacing: .5px; }
.ar-tag.ai { color: #c4b5fd; background: rgba(139,92,246,.16); border: 1px solid rgba(139,92,246,.4); }
.ar-tag.rule { color: #93a0c0; background: rgba(255,255,255,.06); border: 1px solid var(--line); }
.ar-loading { font-size: 13px; color: var(--txt-dim); display: flex; align-items: center; gap: 9px; padding: 6px 0; }
.spinner2 { width: 14px; height: 14px; border-radius: 50%; border: 2px solid rgba(139,92,246,.3); border-top-color: #a78bfa; animation: spin .7s linear infinite; }
.ar-body { font-size: 13px; line-height: 1.8; color: var(--txt); }
.ar-body h3 { font-size: 13px; font-weight: 800; color: var(--violet); margin: 12px 0 4px; }
.ar-body h4 { font-size: 12.5px; font-weight: 700; margin: 8px 0 3px; }
.ar-body p { margin: 3px 0; }
.ar-body ul { margin: 2px 0 6px; padding-left: 18px; }
.ar-body li { margin: 2px 0; }
.ar-body b { color: #c4b5fd; }
.ar-empty { font-size: 12.5px; color: var(--txt-faint); line-height: 1.7; padding: 4px 0; }
.ar-empty b { color: var(--violet); }

.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.chart-card { padding: 16px 18px; position: relative; }
.chart-title { font-size: 13px; font-weight: 700; margin-bottom: 4px; color: var(--txt); }
.chart-box { height: 250px; }
.gauge-box { height: 210px; }
.gauge-sub { text-align: center; font-size: 11.5px; color: var(--txt-faint); margin-top: -6px; }

.list-panel { padding: 18px; }
.list-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; flex-wrap: wrap; margin-bottom: 14px; }
.seg-view { display: flex; gap: 4px; background: rgba(9,13,26,.6); border: 1px solid var(--line); padding: 4px; border-radius: 11px; }
.sv { padding: 7px 15px; border: none; background: transparent; color: var(--txt-dim); font-size: 13px; font-weight: 700; border-radius: 8px; cursor: pointer; transition: all .18s; }
.sv em { font-style: normal; font-size: 11px; color: var(--txt-faint); margin-left: 5px; background: rgba(255,255,255,.06); padding: 1px 7px; border-radius: 999px; }
.sv.on { background: linear-gradient(120deg, rgba(34,211,238,.18), rgba(139,92,246,.2)); color: var(--txt); box-shadow: 0 2px 10px rgba(91,140,255,.15); }
.sv.on em { color: var(--cyan); }

.filters { display: flex; flex-direction: column; align-items: flex-end; gap: 8px; }
.chips { display: flex; gap: 6px; flex-wrap: wrap; }
.chip { font-size: 11.5px; padding: 4px 11px; border-radius: 999px; border: 1px solid var(--line); background: transparent; color: var(--txt-dim); cursor: pointer; transition: all .15s; }
.chip em { font-style: normal; color: var(--txt-faint); margin-left: 4px; font-size: 10.5px; }
.chip.on { background: rgba(91,140,255,.18); color: var(--txt); border-color: rgba(91,140,255,.5); }
.high-only { font-size: 12px; color: var(--txt-dim); display: flex; align-items: center; gap: 6px; cursor: pointer; }
.high-only input { accent-color: var(--cyan); }

/* 全文对照 */
.all-hint { font-size: 12px; color: var(--txt-faint); margin-bottom: 10px; }
.full-table { width: 100%; border-collapse: collapse; }
.full-table thead th { font-size: 11px; color: var(--txt-faint); text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line); font-weight: 700; letter-spacing: .5px; }
.full-table tbody tr { border-bottom: 1px solid rgba(124,148,220,.07); transition: background .15s; }
.full-table tbody tr:last-child { border-bottom: none; }
.full-table td { padding: 9px 10px; font-size: 12.5px; vertical-align: top; line-height: 1.6; }
.ft-row.bad { cursor: pointer; border-left: 3px solid transparent; }
.ft-row.bad:hover { background: rgba(251,113,133,.05); border-left-color: var(--red); }
.ft-row.ok { border-left: 3px solid transparent; }
.ft-row.ok:hover { background: rgba(255,255,255,.02); }
.ft-row.dim { opacity: .45; }
.ft-line { font-family: var(--mono); font-size: 11px; color: var(--txt-faint); }
.st { font-size: 11px; font-weight: 700; padding: 2px 9px; border-radius: 999px; white-space: nowrap; }
.st-ok { color: #6ee7b7; background: rgba(52,211,153,.1); border: 1px solid rgba(52,211,153,.3); }
.st-bad { color: #fda4af; background: rgba(251,113,133,.1); border: 1px solid rgba(251,113,133,.35); cursor: pointer; }
.ft-src.mono { font-family: var(--mono); color: #9db8ff; word-break: break-word; }
.ft-tgt { color: var(--txt); word-break: break-word; }

.no-issues { text-align: center; color: var(--txt-dim); padding: 40px 0; font-size: 14px; }

.issue { border: 1px solid var(--line); border-radius: 11px; padding: 13px 15px; margin-bottom: 10px; background: rgba(255,255,255,.02); transition: opacity .2s; scroll-margin-top: 10px; }
.issue.dim { opacity: .4; }
.issue.flash { animation: flashGlow 1.8s ease; }
@keyframes flashGlow {
  0% { box-shadow: 0 0 0 2px rgba(34,211,238,.7); }
  100% { box-shadow: 0 0 0 2px rgba(34,211,238,0); }
}
.issue-main { display: flex; align-items: center; gap: 9px; flex-wrap: wrap; }
.line-num { font-family: var(--mono); font-size: 11px; color: var(--txt-faint); background: rgba(255,255,255,.05); border-radius: 6px; padding: 2px 7px; }
.sev-dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.sev-dot.red { background: var(--red); box-shadow: 0 0 8px var(--red); }
.sev-dot.amber { background: var(--amber); box-shadow: 0 0 8px var(--amber); }
.issue-title { font-size: 13.5px; font-weight: 700; flex: 1; min-width: 160px; }
.btn.tiny { padding: 3px 10px; font-size: 11px; border-radius: 7px; }
.btn.ghost { background: transparent; }
.issue-detail { font-size: 12.5px; color: var(--txt-dim); margin: 8px 0 4px; line-height: 1.7; }
.issue-fix { font-size: 12.5px; color: #a5e8d6; line-height: 1.7; }
.seg-box { margin-top: 10px; display: grid; gap: 6px; background: rgba(9,13,26,.5); border-radius: 9px; padding: 10px 12px; }
.seg-line { display: flex; gap: 9px; align-items: baseline; font-size: 12.5px; line-height: 1.7; }
.seg-tag { flex: none; font-size: 9.5px; font-weight: 800; letter-spacing: 1px; color: var(--txt-faint); background: rgba(255,255,255,.06); padding: 1px 6px; border-radius: 5px; }
.seg-line.src .mono { font-family: var(--mono); color: #9db8ff; }
.seg-line.tgt { color: var(--txt); }
</style>
