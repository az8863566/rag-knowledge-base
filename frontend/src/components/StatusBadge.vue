<template>
  <el-tag :type="tagType" size="small">
    <el-icon v-if="icon" class="status-icon">
      <component :is="icon" />
    </el-icon>
    {{ label }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Loading, Check, CircleClose, Timer } from '@element-plus/icons-vue'

const props = defineProps<{
  status: 'pending' | 'processing' | 'completed' | 'failed' | string
}>()

const tagType = computed(() => {
  switch (props.status) {
    case 'completed':
      return 'success'
    case 'failed':
      return 'danger'
    case 'processing':
      return 'warning'
    case 'pending':
    default:
      return 'info'
  }
})

const label = computed(() => {
  switch (props.status) {
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    case 'processing':
      return '处理中'
    case 'pending':
    default:
      return '等待中'
  }
})

const icon = computed(() => {
  switch (props.status) {
    case 'completed':
      return Check
    case 'failed':
      return CircleClose
    case 'processing':
      return Loading
    case 'pending':
    default:
      return Timer
  }
})
</script>

<style scoped>
.status-icon {
  margin-right: 4px;
}
</style>
