<template>
  <div class="auth-card">
    <div class="auth-header">
      <div class="auth-icon">🔐</div>
      <h2>登录</h2>
      <p class="auth-sub">登录后可上传视频、查看并编辑识别结果</p>
    </div>

    <form class="auth-form" @submit.prevent="onSubmit">
      <label class="field">
        <span>用户名</span>
        <input
          v-model.trim="username"
          type="text"
          autocomplete="username"
          placeholder="用户名"
          required
        />
      </label>
      <label class="field">
        <span>密码</span>
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          placeholder="密码"
          required
        />
      </label>

      <p v-if="error" class="auth-error">{{ error }}</p>

      <button class="auth-submit" type="submit" :disabled="loading">
        {{ loading ? '请稍候…' : '登录' }}
      </button>
    </form>

    <div class="auth-footer">
      <p v-if="hint" class="auth-hint">{{ hint }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { login } from '../api.js'

const emit = defineEmits(['success'])
const props = defineProps({
  defaultUsername: { type: String, default: '' },
  hint: { type: String, default: '' },
})

const username = ref(props.defaultUsername || 'account')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function onSubmit() {
  error.value = ''
  if (!username.value || !password.value) {
    error.value = '请填写用户名和密码'
    return
  }

  loading.value = true
  try {
    const res = await login(username.value, password.value)
    emit('success', res.data)
  } catch (e) {
    const detail = e?.response?.data?.detail
    if (e?.response?.status === 429) {
      error.value = detail || '尝试过于频繁，请稍后再试'
    } else if (e?.response?.status === 401) {
      error.value = detail || '用户名或密码错误'
    } else {
      error.value = detail || '登录失败，请重试'
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-card {
  width: min(420px, 100%);
  margin: 48px auto;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.08);
  padding: 28px 28px 22px;
}
.auth-header { text-align: center; margin-bottom: 20px; }
.auth-icon { font-size: 32px; margin-bottom: 8px; }
.auth-header h2 { margin: 0 0 6px; font-size: 20px; color: #222; }
.auth-sub { margin: 0; font-size: 13px; color: #888; }

.auth-form { display: flex; flex-direction: column; gap: 12px; }
.field { display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: #555; }
.field input {
  height: 40px;
  border: 1.5px solid #e2e2e7;
  border-radius: 10px;
  padding: 0 12px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.field input:focus {
  border-color: #007AFF;
  box-shadow: 0 0 0 3px rgba(0, 122, 255, 0.15);
}

.auth-error {
  margin: 0;
  color: #c62828;
  font-size: 13px;
  background: #fff0f0;
  border: 1px solid #ffcdd2;
  border-radius: 8px;
  padding: 8px 10px;
}
.auth-hint {
  margin: 0;
  font-size: 12px;
  color: #8E8E93;
}

.auth-submit {
  margin-top: 4px;
  height: 42px;
  border: none;
  border-radius: 10px;
  background: #007AFF;
  color: #fff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}
.auth-submit:disabled { opacity: 0.6; cursor: not-allowed; }
.auth-submit:hover:not(:disabled) { background: #0066d6; }

.auth-footer {
  margin-top: 16px;
  text-align: center;
}
</style>
