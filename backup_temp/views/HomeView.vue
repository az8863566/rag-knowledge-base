<template>
  <div class="home-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <h1>知识库概览</h1>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="stat-header">
              <el-icon :size="24"><Document /></el-icon>
              <span>文档总数</span>
            </div>
          </template>
          <div class="stat-value">
            {{ documentStore.stats?.total_documents || 0 }}
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="stat-header">
              <el-icon :size="24"><DataLine /></el-icon>
              <span>向量总数</span>
            </div>
          </template>
          <div class="stat-value">
            {{ documentStore.stats?.total_vectors || 0 }}
          </div>
        </el-card>
      </el-col>
      
      <el-col :span="8">
        <el-card>
          <template #header>
            <div class="stat-header">
              <el-icon :size="24"><Collection /></el-icon>
              <span>文档块数</span>
            </div>
          </template>
          <div class="stat-value">
            {{ documentStore.stats?.total_chunks || 0 }}
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="$router.push('/documents')">
              <el-icon><Plus /></el-icon>
              上传文档
            </el-button>
            <el-button @click="refreshStats">
              <el-icon><Refresh /></el-icon>
              刷新统计
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Document, DataLine, Collection, Plus, Refresh } from '@element-plus/icons-vue'
import { useDocumentStore } from '@/stores/document'

const documentStore = useDocumentStore()

onMounted(() => {
  documentStore.fetchStats()
})

const refreshStats = () => {
  documentStore.fetchStats()
}
</script>

<style scoped>
.home-container {
  padding: 20px;
}

h1 {
  margin: 0;
  color: #303133;
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #606266;
}

.stat-value {
  font-size: 36px;
  font-weight: bold;
  color: #409EFF;
  text-align: center;
  padding: 20px 0;
}

.card-header {
  font-weight: bold;
}

.quick-actions {
  display: flex;
  gap: 16px;
}
</style>
