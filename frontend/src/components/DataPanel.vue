<script setup>
import { ref, computed, inject } from 'vue'
import { parseBilingualText } from '../api'

const { glossary, entries, sourceLabel, llm, loading, notify, clearLlmStorage } = inject('termguard')
const emit = defineEmits(['run', 'openGlossary'])

const tab = ref('sample')           // sample | paste
const pasteText = ref('')
const fileInput = ref(null)

const entryCount = computed(() => entries.value.length)
const canRun = computed(() => entryCount.value > 0 && !loading.value)

function useSample() {
  tab.value = 'sample'
  notify('📦 已载入内置游戏本地化示例，可直接开始质检')
}

function applyParsed(list, label) {
  if (!list.length) { notify('⚠️ 未解析到有效内容（每行格式：源文,译文 或 源文<TAB>译文）'); return }
  entries.value = list.map((e, i) => ({ line: i + 1, source: e.source, target: e.target }))
  sourceLabel.value = label
  notify(`✅ 已载入 ${list.length} 句待检文本`)
}

function applyPaste() {
  const list = parseBilingualText(pasteText.value)
  applyParsed(list, `粘贴文本 · ${list.length} 句`)
}

function onFile(e) {
  const f = e.target.files && e.target.files[0]
  if (!f) return
  const reader = new FileReader()
  reader.onload = () => {
    const list = parseBilingualText(String(reader.result))
    applyParsed(list, `文件 ${f.name} · ${list.length} 句`)
  }
  reader.readAsText(f, 'utf-8')
  e.target.value = ''
}

function addSampleRows() {
  // 复制示例文本到粘贴区，方便演示自定义数据
  const samplePair = [
    'Equip your new armor, {player}!|请装备你的新护甲！',
    'Quest: Defeat 10 monsters to earn 500 gold.|任务：击败100只怪物获得500金币。',
    'This item is Soulbound.|此物品为灵魂绑定物品。',
  ]
  pasteText.value = samplePair.join('\n')
  tab.value = 'paste'
}

const llmPlaceholder = computed(() => llm.enabled ? 'sk-...（仅保存在本地浏览器）' : '')
</script>

<template>
  <div class="panel side-panel">
    <!-- 数据源 -->
    <div class="block">
      <div class="section-title">① 待检文本</div>
      <div class="seg">
        <button :class="['seg-btn', tab === 'sample' && 'on']" @click="useSample">内置示例</button>
        <button :class="['seg-btn', tab === 'paste' && 'on']" @click="tab = 'paste'">粘贴/上传</button>
      </div>

      <div v-if="tab === 'sample'" class="sample-card">
        <div class="sample-icon">🎮</div>
        <div>
          <p class="sample-t1">游戏本地化 · 含错 Demo</p>
          <p class="sample-t2">26 句游戏文案，故意埋入术语 / 占位符 / 数字 / 漏译等 14 处典型错误，用于演示质检能力。</p>
          <button class="btn btn-ghost tiny" @click="addSampleRows">复制几条到粘贴区试试 →</button>
        </div>
      </div>

      <template v-else>
        <div class="paste-head">
          <span class="label" style="margin:0">每行一条：<code>英文源文,中文译文</code>（支持 Tab 分隔）</span>
          <button class="btn btn-ghost tiny" @click="fileInput.click()">📂 上传 .csv/.txt</button>
          <input ref="fileInput" type="file" accept=".csv,.txt,.tsv" hidden @change="onFile" />
        </div>
        <textarea v-model="pasteText" rows="7" spellcheck="false"
                  placeholder="Welcome back, Commander!,欢迎回来，指挥官！&#10;Cloud Sync enabled.,云同步已开启。"></textarea>
        <button class="btn tiny mt8" style="width:100%" @click="applyPaste">载入以上文本</button>
      </template>

      <div class="data-status" v-if="entryCount">
        <i class="ok"></i>
        <span class="ellipsis">{{ sourceLabel }}</span>
      </div>
    </div>

    <!-- 术语库 -->
    <div class="block">
      <div class="row-between">
        <div class="section-title" style="margin:0">② 术语库 Glossary</div>
        <button class="btn btn-ghost tiny" @click="emit('openGlossary')">编辑</button>
      </div>
      <p class="mini-note">术语表驱动一致性检查：精确匹配 + 上下文限定词条（如 Level→等级 / Level 3→第 3 章）。</p>
      <div class="gloss-stats">
        <span class="gs-item"><b>{{ glossary.length }}</b> 词条</span>
        <span class="gs-item"><b>{{ glossary.filter(g => g.keep_english).length }}</b> 保留英文</span>
        <span class="gs-item"><b>{{ glossary.filter(g => g.context).length }}</b> 带语境</span>
      </div>
    </div>

    <!-- AI 复核 -->
    <div class="block">
      <div class="row-between">
        <div class="section-title" style="margin:0">③ AI 语境复核 <span class="opt-tag">可选</span></div>
        <button class="switch" :class="{ on: llm.enabled }" @click="llm.enabled = !llm.enabled">
          <span class="knob"></span>
        </button>
      </div>
      <p class="mini-note">大模型复核语境 / 语域 / 信息遗漏等语义问题。<b>不配置 Key 时自动降级为仅规则检查</b>（演示不受影响）。</p>
      <template v-if="llm.enabled">
        <div class="field">
          <span class="label">API Key（DeepSeek 等，兼容 OpenAI）</span>
          <div class="key-row">
            <input v-model="llm.apiKey" type="password" :placeholder="llmPlaceholder" spellcheck="false" />
            <button v-if="llm.apiKey" class="btn btn-ghost tiny" @click="clearLlmStorage">清除</button>
          </div>
          <p class="key-tip">🔒 密钥仅保存在<b>本浏览器</b>（localStorage），刷新页面自动带出，不上传服务器</p>
        </div>
        <div class="grid2">
          <div class="field">
            <span class="label">Base URL</span>
            <input v-model="llm.baseUrl" type="text" spellcheck="false" />
          </div>
          <div class="field">
            <span class="label">模型</span>
            <input v-model="llm.model" type="text" spellcheck="false" />
          </div>
        </div>
      </template>
    </div>

    <!-- 运行 -->
    <button class="btn btn-primary run-btn" :disabled="!canRun" @click="emit('run')">
      <span v-if="loading" class="spinner"></span>
      <template v-else>▶</template>
      {{ loading ? '质检中…' : (entryCount ? `开始质检 · ${entryCount} 句` : '请先载入待检文本') }}
    </button>
  </div>
</template>

<style scoped>
.side-panel { padding: 18px; display: flex; flex-direction: column; gap: 20px; }
.block { }
.row-between { display: flex; align-items: center; justify-content: space-between; gap: 8px; }

.seg { display: grid; grid-template-columns: 1fr 1fr; gap: 4px; padding: 4px; background: rgba(9,13,26,.6); border: 1px solid var(--line); border-radius: 11px; margin-bottom: 12px; }
.seg-btn { padding: 8px 0; border: none; background: transparent; color: var(--txt-dim); font-size: 13px; font-weight: 600; border-radius: 8px; cursor: pointer; transition: all .18s; }
.seg-btn.on { background: linear-gradient(120deg, rgba(34,211,238,.18), rgba(139,92,246,.2)); color: var(--txt); box-shadow: 0 2px 10px rgba(91,140,255,.15); }

.sample-card { display: flex; gap: 12px; align-items: flex-start; background: rgba(91,140,255,.06); border: 1px dashed rgba(91,140,255,.35); border-radius: 11px; padding: 12px; }
.sample-icon { font-size: 26px; line-height: 1.2; }
.sample-t1 { font-weight: 700; font-size: 13px; }
.sample-t2 { font-size: 11.5px; color: var(--txt-dim); margin: 4px 0 8px; line-height: 1.6; }
.btn.tiny { padding: 4px 10px; font-size: 11.5px; border-radius: 8px; }
.mt8 { margin-top: 8px; }

.paste-head { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-bottom: 8px; }
.paste-head code { font-family: var(--mono); color: var(--cyan); font-size: 11px; }

.data-status { display: flex; align-items: center; gap: 8px; margin-top: 10px; font-size: 12px; color: var(--txt-dim); }
.data-status .ok { width: 8px; height: 8px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); flex: none; }
.ellipsis { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.mini-note { font-size: 11.5px; color: var(--txt-dim); line-height: 1.7; margin-top: 10px; }
.mini-note b { color: var(--cyan); font-weight: 600; }
.opt-tag { font-size: 10px; color: var(--amber); border: 1px solid rgba(251,191,36,.4); border-radius: 6px; padding: 1px 6px; letter-spacing: .5px; }

.gloss-stats { display: flex; gap: 10px; margin-top: 12px; flex-wrap: wrap; }
.gs-item { font-size: 11.5px; color: var(--txt-faint); background: rgba(255,255,255,.03); border: 1px solid var(--line); padding: 5px 10px; border-radius: 8px; }
.gs-item b { color: var(--txt); font-size: 13px; margin-right: 2px; }

.switch { width: 42px; height: 23px; border-radius: 999px; background: rgba(255,255,255,.08); border: 1px solid var(--line-strong); position: relative; cursor: pointer; transition: all .2s; flex: none; }
.switch .knob { position: absolute; top: 2px; left: 2px; width: 17px; height: 17px; border-radius: 50%; background: #8892b0; transition: all .2s; }
.switch.on { background: linear-gradient(120deg, rgba(34,211,238,.7), rgba(139,92,246,.75)); border-color: transparent; }
.switch.on .knob { left: 21px; background: #fff; box-shadow: 0 0 10px rgba(255,255,255,.6); }

.field { margin-top: 10px; }
.key-row { display: flex; gap: 6px; }
.key-row input { flex: 1; }
.key-tip { font-size: 11px; color: var(--txt-faint); margin-top: 6px; line-height: 1.6; }
.key-tip b { color: var(--green); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }

.run-btn { width: 100%; margin-top: 2px; }
.spinner {
  width: 14px; height: 14px; border-radius: 50%;
  border: 2px solid rgba(8,17,43,.35); border-top-color: #08112b;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
