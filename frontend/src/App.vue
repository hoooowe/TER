<template>
  <div class="app">
    <header class="app-header">
      <h1>教师情感识别</h1>
      <nav v-if="user" class="mode-tabs">
        <button
          :class="['tab', { active: mode === 'dual' }]"
          @click="switchMode('dual')"
        >
          🎓 双维编码
        </button>
        <button
          :class="['tab', { active: mode === 'history' }]"
          @click="switchMode('history')"
        >
          🕘 识别历史
        </button>
      </nav>
      <div v-if="user" class="user-area">
        <span class="user-name">{{ user.username }}</span>
        <button class="logout-btn" @click="onLogout">退出</button>
      </div>
    </header>

    <main class="app-main">
      <LoginView
        v-if="!user && authChecked"
        :hint="loginHint"
        @success="onLoginSuccess"
      />

      <div v-else-if="!user && !authChecked" class="auth-loading">检查登录状态…</div>

      <!-- 教学情绪-行为双维自动编码（本分支唯一功能） -->
      <template v-else-if="mode === 'dual'">
        <DualCodingView ref="dualViewRef" />
      </template>

      <!-- 识别历史：仅双维任务，点击进入双维视图 -->
      <template v-else-if="mode === 'history'">
        <div class="history-layout">
          <HistoryPanel
            ref="historyPanelRef"
            :active-job-id="jobId"
            job-type-filter="dual"
            @select="onSelectHistory"
          />
          <section class="panel panel-right history-result">
            <div class="right-placeholder">
              <div class="placeholder-icon">🎓</div>
              <p class="placeholder-title">教学情绪-行为双维编码</p>
              <p class="placeholder-hint">
                点击左侧历史记录，在「双维编码」页查看、复核并导出标准化编码表；
                也可直接切换到「双维编码」上传新的教学视频
              </p>
            </div>
          </section>
        </div>
      </template>

    </main>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import DualCodingView from './components/DualCodingView.vue'
import LoginView from './components/LoginView.vue'
import HistoryPanel from './components/HistoryPanel.vue'
import { fetchMe, logout } from './api.js'

// 本分支仅提供「教学情绪-行为双维编码」
const mode = ref('dual') // dual | history
const user = ref(null)
const authChecked = ref(false)
const loginHint = ref('')
const dualViewRef = ref(null)
const historyPanelRef = ref(null)

function switchMode(newMode) {
  mode.value = newMode
}

async function onSelectHistory(item) {
  if (!item?.job_id) return
  if (item.job_type && item.job_type !== 'dual') return
  mode.value = 'dual'
  await new Promise((r) => setTimeout(r, 0))
  dualViewRef.value?.openHistoryItem?.(item)
}

function onLoginSuccess(data) {
  user.value = data
  loginHint.value = ''
  mode.value = 'dual'
  historyPanelRef.value?.reload?.()
}

async function onLogout() {
  try {
    await logout()
  } catch (_) {
    // ignore
  }
  user.value = null
  mode.value = 'dual'
  loginHint.value = ''
  dualViewRef.value?.resetAll?.()
}

onMounted(async () => {
  try {
    const res = await fetchMe()
    user.value = res.data
    loginHint.value = ''
  } catch (_) {
    user.value = null
    loginHint.value = ''
  } finally {
    authChecked.value = true
  }
})
</script>

<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: #f5f5f7;
  color: #333;
}
.app { min-height: 100vh; }
.app-header {
  background: #fff;
  padding: 16px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 24px;
}
.app-header h1 { font-size: 18px; font-weight: 600; }
.mode-tabs { display: flex; gap: 4px; flex: 1; }
.tab {
  padding: 6px 16px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.tab:hover { border-color: #007AFF; color: #007AFF; }
.tab:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.tab.active { background: #007AFF; color: #fff; border-color: #007AFF; }

.user-area {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-left: auto;
}
.user-name {
  font-size: 13px;
  color: #555;
  font-weight: 600;
}
.logout-btn {
  border: 1px solid #ddd;
  background: #fff;
  border-radius: 8px;
  padding: 5px 12px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
}
.logout-btn:hover { border-color: #FF3B30; color: #FF3B30; }

.app-main {
  max-width: 1400px;
  margin: 24px auto;
  padding: 0 20px 40px;
}
.auth-loading {
  text-align: center;
  color: #8E8E93;
  padding: 60px 0;
  font-size: 14px;
}

.workspace {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(360px, 1.1fr);
  gap: 16px;
  align-items: start;
}
.history-layout {
  display: grid;
  grid-template-columns: minmax(300px, 0.9fr) minmax(360px, 1.2fr);
  gap: 16px;
  align-items: start;
}
.panel {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.panel-left,
.panel-right { min-height: 280px; }

.left-placeholder,
.right-placeholder {
  background: #fff;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  padding: 24px;
}
.right-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 280px;
  color: #8E8E93;
  border: 1px dashed #e0e0e0;
}
.placeholder-icon { font-size: 36px; margin-bottom: 12px; }
.placeholder-title { font-size: 15px; font-weight: 600; color: #555; margin-bottom: 6px; }
.placeholder-hint { font-size: 13px; color: #999; }
.right-placeholder.processing { border-style: solid; border-color: #e8f0ff; background: #f8fbff; }
.mini-progress {
  width: 70%;
  max-width: 240px;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
  margin-top: 16px;
}
.mini-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #007AFF, #5ac8fa);
  border-radius: 4px;
  transition: width 0.3s ease;
}

.left-stack { display: flex; flex-direction: column; gap: 16px; }

.error-banner {
  background: #fff0f0;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  padding: 12px 16px;
  color: #c62828;
  font-size: 14px;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  background: #fff;
  border-radius: 12px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.mode-toggle { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.mode-label { font-size: 13px; color: #666; }
.mode-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 16px;
  background: #eef5ff;
  color: #007AFF;
  font-size: 12px;
  font-weight: 500;
}
.history-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 16px;
  background: #fff4e5;
  color: #FF9500;
  font-size: 12px;
  font-weight: 500;
}
.live-badge {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 16px;
  background: #e8f8ee;
  color: #34C759;
  font-size: 12px;
  font-weight: 600;
}
.live-progress {
  display: flex;
  align-items: center;
  gap: 10px;
  background: #fff;
  border-radius: 12px;
  padding: 10px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}
.live-progress-bar {
  flex: 0 0 160px;
  height: 8px;
  background: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}
.live-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #34C759, #5ac8fa);
  border-radius: 4px;
  transition: width 0.25s ease;
}
.live-progress-text {
  font-size: 12px;
  color: #666;
}
.mode-btn {
  padding: 4px 14px;
  border: 1px solid #ddd;
  border-radius: 16px;
  background: #fff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.mode-btn:hover { border-color: #007AFF; color: #007AFF; }
.mode-btn:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.mode-btn.active { background: #007AFF; color: #fff; border-color: #007AFF; }

.export-actions { display: flex; gap: 8px; flex-wrap: wrap; }
.export-btn {
  padding: 6px 14px;
  border-radius: 16px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.15s;
  background: #fff;
}
.export-btn:focus-visible { outline: 2px solid #007AFF; outline-offset: 2px; }
.export-btn:disabled { opacity: 0.55; cursor: not-allowed; }
.export-btn.csv {
  border-color: #34C759;
  color: #34C759;
  background: #fff;
}
.export-btn.csv:hover:not(:disabled) { background: #34C759; color: #fff; }
.export-btn.excel {
  background: #34C759;
  color: #fff;
  border-color: #34C759;
}
.export-btn.excel:hover:not(:disabled) { background: #2DA44E; }
.export-btn.open {
  border-color: #007AFF;
  color: #007AFF;
}
.export-btn.open:hover { background: #007AFF; color: #fff; }

.export-hint {
  font-size: 12px;
  color: #666;
  margin: -4px 4px 0;
}

@media (max-width: 960px) {
  .workspace,
  .history-layout {
    grid-template-columns: 1fr;
  }
  .app-main { padding: 0 12px 32px; }
  .app-header { flex-wrap: wrap; gap: 12px; }
}
</style>
