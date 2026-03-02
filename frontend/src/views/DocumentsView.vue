<template>
  <div class="documents-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <h1>文档管理</h1>
      </el-col>
    </el-row>
    
    <!-- 上传区域 -->
    <el-row style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>上传文档</span>
              <el-text type="info">
                支持格式: {{ supportedFormats.join(', ') }}
              </el-text>
            </div>
          </template>
          
          <el-upload
            drag
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="false"
            accept=".txt,.md,.pdf,.docx,.html,.csv,.json,.xlsx"
          >
            <el-icon class="el-icon--upload" :size="48"><UploadFilled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
          </el-upload>
          
          <!-- 上传进度 -->
          <div v-if="Object.keys(documentStore.uploadProgress).length > 0" class="upload-progress">
            <div
              v-for="(progress, fileId) in documentStore.uploadProgress"
              :key="fileId"
              class="progress-item"
            >
              <span>{{ fileId.split('_')[0] }}</span>
              <el-progress :percentage="progress" />
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 文档列表 -->
    <el-row style="margin-top: 20px">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>文档列表</span>
              <el-button type="primary" :loading="documentStore.loading" @click="refreshList">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>
          
          <el-table
            v-loading="documentStore.loading"
            :data="documentStore.documents"
            style="width: 100%"
          >
            <el-table-column prop="file_name" label="文件名" min-width="200">
              <template #default="{ row }">
                <div class="file-name">
                  <el-icon><Document /></el-icon>
                  <span>{{ row.file_name }}</span>
                </div>
              </template>
            </el-table-column>
            
            <el-table-column prop="file_type" label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.file_type }}</el-tag>
              </template>
            </el-table-column>
            
            <el-table-column prop="file_size" label="大小" width="120">
              <template #default="{ row }">
                {{ formatFileSize(row.file_size) }}
              </template>
            </el-table-column>
            
            <el-table-column prop="status" label="状态" width="120">
              <template #default="{ row }">
                <status-badge :status="row.status" />
              </template>
            </el-table-column>
            
            <el-table-column prop="chunk_count" label="块数" width="100">
              <template #default="{ row }">
                {{ row.chunk_count || '-' }}
              </template>
            </el-table-column>
            
            <el-table-column prop="created_at" label="上传时间" width="180">
              <template #default="{ row }">
                {{ formatDate(row.created_at) }}
              </template>
            </el-table-column>
            
            <el-table-column label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button
                  v-if="row.status === 'failed'"
                  type="primary"
                  link
                  @click="showError(row)"
                >
                  查看错误
                </el-button>
                <el-button type="danger" link @click="handleDelete(row)">
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          
          <!-- 分页 -->
          <div class="pagination">
            <el-pagination
              v-model:current-page="currentPage"
              v-model:page-size="pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="documentStore.total"
              layout="total, sizes, prev, pager, next"
              @size-change="handleSizeChange"
              @current-change="handleCurrentChange"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>
    
    <!-- 错误详情对话框 -->
    <el-dialog
      v-model="errorDialogVisible"
      title="错误详情"
      width="500px"
    >
      <el-alert
        :title="currentError"
        type="error"
        :closable="false"
        show-icon
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { UploadFilled, Refresh, Document } from '@element-plus/icons-vue'
import { useDocumentStore } from '@/stores/document'
import StatusBadge from '@/components/StatusBadge.vue'
import type { Document as DocType, UploadFile } from '@/types'

const documentStore = useDocumentStore()
const currentPage = ref(1)
const pageSize = ref(20)
const supportedFormats = ref(['.txt', '.md', '.pdf', '.docx', '.html', '.csv', '.json', '.xlsx'])
const errorDialogVisible = ref(false)
const currentError = ref('')

onMounted(() => {
  refreshList()
})

watch([currentPage, pageSize], () => {
  refreshList()
})

const refreshList = () => {
  documentStore.fetchDocuments({
    page: currentPage.value,
    page_size: pageSize.value
  })
}

const handleFileChange = async (uploadFile: UploadFile) => {
  const file = uploadFile.raw
  if (!file) return
  
  const result = await documentStore.uploadDocument(file)
  
  if (result.success) {
    ElMessage.success('文档上传成功，正在处理中')
    refreshList()
  } else {
    ElMessage.error(result.error)
  }
}

const handleDelete = async (row: DocType) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除文档 "${row.file_name}" 吗？`,
      '确认删除',
      {
        confirmButtonText: '删除',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    const result = await documentStore.deleteDocument(row.id)
    if (result.success) {
      ElMessage.success('删除成功')
    } else {
      ElMessage.error(result.error)
    }
  } catch {
    // 用户取消
  }
}

const showError = (row: DocType) => {
  currentError.value = row.error_message || '未知错误'
  errorDialogVisible.value = true
}

const handleSizeChange = (val: number) => {
  pageSize.value = val
  currentPage.value = 1
}

const handleCurrentChange = (val: number) => {
  currentPage.value = val
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

const formatDate = (dateStr: string): string => {
  if (!dateStr) return '-'
  const date = new Date(dateStr)
  return date.toLocaleString('zh-CN')
}
</script>

<style scoped>
.documents-container {
  padding: 20px;
}

h1 {
  margin: 0;
  color: #303133;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-progress {
  margin-top: 16px;
}

.progress-item {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 8px;
}

.progress-item span {
  width: 150px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-name {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pagination {
  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}
</style>
