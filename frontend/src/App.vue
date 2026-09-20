<script setup>
import { ref, reactive, watch, onMounted, provide } from 'vue'
import DataPanel from './components/DataPanel.vue'
import ReportPanel from './components/ReportPanel.vue'
import GlossaryDrawer from './components/GlossaryDrawer.vue'
import { getSample, runCheck } from './api'

// ---------- 全局状态 ----------
const glossary = ref([])
const entries = ref([])
const sourceLabel = ref('')

// AI 配置：持久化到浏览器 localStorage（密钥不落服务器），刷新自动带出
const LLM_STORAGE_KEY = 'termguard_llm'
const llm = reactive({ enabled: false, apiKey: '', baseUrl: 'https://api.deepseek.com', model: 'deepseek-chat' })
function loadLlmStorage() {
  try {
    const saved = JSON.parse(localStorage.getItem(LLM_STORAGE_KEY) || 'null')
    if (saved && typeof saved === 'object') {
      llm.apiKey = saved.apiKey || ''
      llm.baseUrl = saved.baseUrl || llm.baseUrl
      llm.model = saved.model || llm.model
      llm.enabled = !!saved.enabled
    }
  } catch (e) { /* 忽略损坏数据 */ }
}
function persistLlm() {
  try {
    localStorage.setItem(LLM_STORAGE_KEY, JSON.stringify({
      apiKey: llm.apiKey, baseUrl: llm.baseUrl, model: llm.model, enabled: llm.enabled,
    }))
  } catch (e) { /* localStorage 不可用时静默 */ }
}
function clearLlmStorage() {
  try { localStorage.removeItem(LLM_STORAGE_KEY) } catch (e) { /* ignore */ }
  llm.apiKey = ''
  llm.enabled = false
}
loadLlmStorage()
watch(llm, persistLlm, { deep: true })
const loading = ref(false)
const result = ref(null)          // {stats, issues, ai_error, llm_enabled}
const drawerOpen = ref(false)
const toast = ref('')
let toastTimer = null

function notify(msg) {
  toast.value = msg
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 3200)
}

async function loadSample() {
  const d = await getSample()
  glossary.value = d.glossary
  entries.value = d.entries
  sourceLabel.value = `内置示例 · 游戏本地化文案（${d.entries.length} 句，术语库 ${d.glossary.length} 条）`
}

async function run() {
  if (!entries.value.length) { notify('⚠️ 没有可检查的文本'); return }
  loading.value = true
  result.value = null
  try {
    const res = await runCheck({
      entries: entries.value.map((e, i) => ({ line: e.line ?? i + 1, source: e.source, target: e.target })),
      glossary: glossary.value,
      llm: { enabled: llm.enabled, api_key: llm.apiKey, base_url: llm.baseUrl, model: llm.model },
    })
    if (!res.ok) { notify('⚠️ ' + (res.error || '检查失败')); return }
    result.value = res
  } catch (e) {
    notify('❌ 无法连接后端服务，请确认已启动 python main.py')
  } finally {
    loading.value = false
  }
}

onMounted(loadSample)
provide('termguard', { glossary, entries, sourceLabel, llm, run, loading, result, notify, clearLlmStorage })
</script>

<template>
  <div class="app-wrap">
    <!-- ===== 顶栏 ===== -->
    <header class="topbar">
      <div class="brand">
        <div class="logo">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none">
            <path d="M12 2L4 5.5v5.1c0 5 3.4 9.6 8 10.9 4.6-1.3 8-5.9 8-10.9V5.5L12 2z"
                  fill="url(#lg1)" />
            <path d="M8.8 12l2.2 2.2 4.2-4.6" stroke="#0b1023" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            <defs><linearGradient id="lg1" x1="4" y1="2" x2="20" y2="21">
              <stop stop-color="#22d3ee" /><stop offset=".55" stop-color="#5b8cff" /><stop offset="1" stop-color="#8b5cf6" />
            </linearGradient></defs>
          </svg>
        </div>
        <div class="brand-txt">
          <div class="brand-name">TermGuard <span class="cn">术语卫士</span></div>
          <div class="brand-sub">游戏本地化 · 术语一致性智能质检助手</div>
        </div>
      </div>
      <div class="topbar-right">
        <span class="tag-chip"><i class="dot dot-cyan"></i>规则引擎 v1.0</span>
        <span class="tag-chip"><i class="dot dot-violet"></i>AI 语境复核</span>
        <button class="btn btn-ghost small" @click="drawerOpen = true">⚙ 术语库管理</button>
      </div>
    </header>

    <!-- ===== 主体 ===== -->
    <main class="app-main">
      <aside class="side-col">
        <DataPanel @run="run" @openGlossary="drawerOpen = true" />
      </aside>
      <section class="report-col">
        <ReportPanel />
      </section>
    </main>

    <!-- ===== 术语库抽屉 ===== -->
    <GlossaryDrawer v-if="drawerOpen" @close="drawerOpen = false" />

    <!-- ===== Toast ===== -->
    <transition name="toast">
      <div v-if="toast" class="toast">{{ toast }}</div>
    </transition>
  </div>
</template>

<style scoped>
.app-wrap { max-width: 1480px; margin: 0 auto; padding: 18px 22px 40px; }
.topbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 4px 18px;
}
.brand { display: flex; align-items: center; gap: 13px; }
.logo {
  width: 46px; height: 46px; border-radius: 13px;
  display: grid; place-items: center;
  background: linear-gradient(145deg, rgba(34,211,238,.15), rgba(139,92,246,.15));
  border: 1px solid var(--line-strong);
  box-shadow: 0 0 24px rgba(91,140,255,.25);
}
.brand-name { font-size: 21px; font-weight: 800; letter-spacing: .5px; }
.brand-name .cn { font-weight: 600; color: var(--cyan); margin-left: 6px; font-size: 16px; }
.brand-sub { font-size: 12px; color: var(--txt-dim); margin-top: 2px; }
.topbar-right { display: flex; align-items: center; gap: 10px; }
.tag-chip {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 11.5px; color: var(--txt-dim);
  padding: 5px 11px; border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255,255,255,.03);
}
.dot { width: 7px; height: 7px; border-radius: 50%; display: inline-block; }
.dot-cyan { background: var(--cyan); box-shadow: 0 0 8px var(--cyan); }
.dot-violet { background: var(--violet); box-shadow: 0 0 8px var(--violet); }
.btn.small { padding: 6px 13px; font-size: 12.5px; }

.app-main { display: grid; grid-template-columns: 350px 1fr; gap: 18px; align-items: start; }
.side-col { position: sticky; top: 18px; }
.toast {
  position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%);
  background: rgba(15, 20, 38, .95); border: 1px solid var(--line-strong);
  padding: 12px 22px; border-radius: 12px; font-size: 13.5px;
  box-shadow: 0 10px 40px rgba(0,0,0,.5); z-index: 100; color: var(--txt);
  backdrop-filter: blur(10px);
}
.toast-enter-active, .toast-leave-active { transition: all .25s ease; }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateX(-50%) translateY(10px); }
</style>
