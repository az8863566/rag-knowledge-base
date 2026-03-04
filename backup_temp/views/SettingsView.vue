<template>
  <div class="settings-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <h1>系统设置</h1>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>检索参数</span>
            </div>
          </template>

          <el-form label-width="140px" label-position="left">
            <el-form-item label="相似度阈值">
              <div class="threshold-control">
                <el-slider
                  v-model="localThreshold"
                  :min="0"
                  :max="1"
                  :step="0.01"
                  :format-tooltip="(val: number) => `${(val * 100).toFixed(0)}%`"
                  style="flex: 1"
                />
                <el-input-number
                  v-model="localThreshold"
                  :min="0"
                  :max="1"
                  :step="0.01"
                  :precision="2"
                  size="small"
                  style="width: 120px; margin-left: 16px"
                />
              </div>
              <div class="threshold-info">
                <el-tag size="small" :type="chatStore.thresholdSource === 'runtime' ? 'warning' : 'info'">
                  {{ chatStore.thresholdSource === 'runtime' ? '运行时设置' : '配置文件' }}
                </el-tag>
                <span class="threshold-hint">低于此值的检索结果将被过滤</span>
              </div>
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="saving" @click="handleSave">
                保存
              </el-button>
              <el-button @click="handleReset">
                恢复默认 (80%)
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const localThreshold = ref(0.75)
const saving = ref(false)

onMounted(async () => {
  await chatStore.fetchThreshold()
  localThreshold.value = chatStore.threshold
})

const handleSave = async () => {
  saving.value = true
  try {
    const result = await chatStore.updateThreshold(localThreshold.value)
    if (result.success) {
      ElMessage.success(`阈值已更新为 ${(localThreshold.value * 100).toFixed(0)}%`)
    } else {
      ElMessage.error(result.error || '更新失败')
    }
  } finally {
    saving.value = false
  }
}

const handleReset = async () => {
  localThreshold.value = 0.75
  saving.value = true
  try {
    const result = await chatStore.updateThreshold(0.75)
    if (result.success) {
      ElMessage.success('阈值已恢复为默认值 80%')
    } else {
      ElMessage.error(result.error || '恢复失败')
    }
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.settings-container {
  padding: 20px;
}

h1 {
  margin: 0;
  color: #303133;
}

.card-header {
  font-weight: bold;
}

.threshold-control {
  display: flex;
  align-items: center;
  width: 100%;
}

.threshold-info {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.threshold-hint {
  font-size: 12px;
  color: #909399;
}
</style>
