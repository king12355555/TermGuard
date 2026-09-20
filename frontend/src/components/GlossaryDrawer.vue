<script setup>
import { ref, inject } from 'vue'
import { saveGlossary, resetGlossary } from '../api'

const { glossary, notify } = inject('termguard')
const emit = defineEmits(['close'])

const editing = ref(JSON.parse(JSON.stringify(glossary.value)))
const saving = ref(false)

function addRow() {
  editing.value.push({ source: '', target: '', context: '', keep_english: false, note: '' })
}
function removeRow(i) {
  editing.value.splice(i, 1)
}
async function save() {
  const clean = editing.value
    .filter(t => (t.source || '').trim())
    .map(t => ({ source: t.source.trim(), target: t.target.trim(), context: t.context.trim(), keep_english: !!t.keep_english, note: t.note.trim() }))
  if (!clean.length) { notify('⚠️ 至少保留一条有效词条'); return }
  saving.value = true
  try {
    const res = await saveGlossary(clean)
    if (!res.ok) { notify('⚠️ ' + (res.error || '保存失败')); return }
    glossary.value = clean
    notify(`✅ 术语库已保存（${res.count} 条）→ 已同步到后端 sample_data.py，刷新/重启后仍保留`)
  } catch (e) {
    notify('❌ 保存失败：无法连接后端服务')
  } finally {
    saving.value = false
  }
}
async function restoreDefault() {
  try {
    const res = await resetGlossary()
    if (!res.ok) { notify('⚠️ ' + (res.error || '恢复失败')); return }
    glossary.value = res.glossary
    editing.value = JSON.parse(JSON.stringify(res.glossary))
    notify('↺ 已恢复出厂内置术语库（12 条）')
  } catch (e) {
    notify('❌ 恢复失败：无法连接后端服务')
  }
}
</script>

<template>
  <div class="mask" @click.self="emit('close')">
    <div class="drawer panel">
      <div class="drawer-head">
        <div>
          <div class="h-title">📚 术语库管理 <span class="h-sub">Glossary</span></div>
          <div class="h-desc">词条驱动一致性检查；勾选"保留英文"表示专有名词不可意译；"语境"用于上下文限定词条。</div>
        </div>
        <button class="btn btn-ghost" @click="emit('close')">✕</button>
      </div>

      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th style="width:150px">源文 Source</th>
              <th style="width:150px">标准译法 Target</th>
              <th style="width:170px">语境 Context</th>
              <th style="width:70px">保留英文</th>
              <th>备注</th>
              <th style="width:44px"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(t, i) in editing" :key="i">
              <td><input v-model="t.source" type="text" placeholder="如 Level 3" spellcheck="false" /></td>
              <td><input v-model="t.target" type="text" placeholder="如 第 3 章" spellcheck="false" /></td>
              <td><input v-model="t.context" type="text" placeholder="如 关卡/章节" spellcheck="false" /></td>
              <td class="center"><button class="ck" :class="{ on: t.keep_english }" @click="t.keep_english = !t.keep_english">✓</button></td>
              <td><input v-model="t.note" type="text" placeholder="备注" spellcheck="false" /></td>
              <td class="center"><button class="del" @click="removeRow(i)">🗑</button></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="drawer-foot">
        <div class="left">
          <button class="btn btn-ghost" @click="addRow">＋ 添加词条</button>
          <button class="btn btn-ghost" @click="restoreDefault">↺ 恢复内置示例</button>
        </div>
        <div class="right">
          <span v-if="saving" class="saved-tip">⏳ 正在保存…</span>
          <button class="btn btn-primary" :disabled="saving" @click="save">💾 保存并同步到 sample_data.py</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(4, 6, 12, .66); backdrop-filter: blur(6px); z-index: 90; display: grid; place-items: center; animation: maskIn .18s ease; }
@keyframes maskIn { from { opacity: 0 } }
.drawer { width: min(1060px, 94vw); max-height: 86vh; display: flex; flex-direction: column; overflow: hidden; animation: drawerIn .25s cubic-bezier(.2,.9,.3,1.2); }
@keyframes drawerIn { from { transform: translateY(24px) scale(.98); opacity: 0 } }
.drawer-head { display: flex; justify-content: space-between; align-items: flex-start; padding: 20px 22px 14px; border-bottom: 1px solid var(--line); }
.h-title { font-size: 17px; font-weight: 800; }
.h-sub { color: var(--cyan); font-size: 12px; margin-left: 8px; letter-spacing: 1px; }
.h-desc { font-size: 11.5px; color: var(--txt-dim); margin-top: 6px; line-height: 1.7; }
.table-wrap { flex: 1; overflow: auto; padding: 14px 18px; }
table { width: 100%; border-collapse: separate; border-spacing: 0 8px; }
th { font-size: 11px; color: var(--txt-faint); text-align: left; padding: 0 6px 2px; font-weight: 700; letter-spacing: .5px; }
td { padding: 0 6px; }
td input { padding: 7px 10px; font-size: 12.5px; }
td.center { text-align: center; }
.ck { width: 26px; height: 26px; border-radius: 8px; border: 1px solid var(--line-strong); background: transparent; color: transparent; cursor: pointer; font-size: 13px; transition: all .15s; }
.ck.on { background: linear-gradient(120deg, rgba(34,211,238,.85), rgba(139,92,246,.85)); border-color: transparent; color: #08112b; font-weight: 900; box-shadow: 0 0 10px rgba(34,211,238,.35); }
.del { border: none; background: transparent; cursor: pointer; font-size: 14px; opacity: .5; transition: opacity .15s; }
.del:hover { opacity: 1; }
.drawer-foot { display: flex; justify-content: space-between; align-items: center; padding: 14px 22px 18px; border-top: 1px solid var(--line); gap: 10px; flex-wrap: wrap; }
.left, .right { display: flex; align-items: center; gap: 10px; }
.saved-tip { font-size: 12px; color: var(--green); }
</style>
