<template>
  <div class="chat-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <h1>知识库问答</h1>
      </el-col>
    </el-row>

    <el-card class="chat-card">
      <!-- 对话区域 -->
      <div ref="chatArea" class="chat-area">
        <div v-if="chatStore.messages.length === 0" class="empty-hint">
          <el-icon :size="48" color="#c0c4cc"><ChatDotRound /></el-icon>
          <p>向知识库提问，验证文档内容</p>
        </div>

        <div
          v-for="(msg, index) in chatStore.messages"
          :key="index"
          class="message-row"
          :class="msg.role"
        >
          <div class="message-bubble" :class="msg.role">
            <!-- 思考过程区域（可折叠） -->
            <div v-if="msg.thinking && msg.role === 'assistant'" class="thinking-section">
              <el-collapse>
                <el-collapse-item>
                  <template #title>
                    <span class="thinking-title">
                      <el-icon><Loading v-if="msg.isStreaming && !msg.content" /><Aim v-else /></el-icon>
                      思考过程
                      <span v-if="msg.isStreaming && !msg.content" class="streaming-indicator"></span>
                    </span>
                  </template>
                  <div class="thinking-content">{{ msg.thinking }}</div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <!-- 回答内容 -->
            <div class="message-content" :class="{ streaming: msg.isStreaming }">
              {{ msg.content }}
              <span v-if="msg.isStreaming && msg.content" class="cursor-blink">|</span>
            </div>

            <!-- 引用来源 -->
            <div v-if="msg.sources && msg.sources.length > 0 && msg.role === 'assistant'" class="message-sources">
              <el-collapse>
                <el-collapse-item>
                  <template #title>
                    <span class="sources-title">
                      引用来源
                      <el-tag 
                        size="small" 
                        :type="(msg.maxScore || 0) >= (msg.threshold || 0.75) ? 'success' : 'warning'"
                        style="margin-left: 8px;"
                      >
                        最高 {{ ((msg.maxScore || 0) * 100).toFixed(1) }}%
                      </el-tag>
                      <el-tag size="small" type="info" style="margin-left: 4px;">
                        阈值 {{ ((msg.threshold || 0.75) * 100).toFixed(0) }}%
                      </el-tag>
                    </span>
                  </template>
                  <div class="source-list">
                    <div 
                      v-for="(src, si) in msg.sources" 
                      :key="si" 
                      class="source-item"
                      :class="{ 'source-matched': src.relevance_score >= (msg.threshold || 0.75) }"
                    >
                      <el-tag size="small" type="info">{{ src.file_name }}</el-tag>
                      <el-tag 
                        size="small" 
                        :type="src.relevance_score >= (msg.threshold || 0.75) ? 'success' : 'danger'"
                      >
                        {{ (src.relevance_score * 100).toFixed(1) }}%
                      </el-tag>
                    </div>
                  </div>
                </el-collapse-item>
              </el-collapse>
            </div>

            <div v-if="msg.has_context === false && msg.role === 'assistant' && !msg.isStreaming" class="no-context-hint">
              <el-tag size="small" type="warning">未命中知识库</el-tag>
            </div>

            <div class="message-time">{{ msg.timestamp }}</div>
          </div>
        </div>

        <!-- loading -->
        <div v-if="chatStore.loading && chatStore.messages.length > 0 && !chatStore.messages[chatStore.messages.length - 1]?.isStreaming" class="message-row assistant">
          <div class="message-bubble assistant loading-bubble">
            <span class="loading-dots">
              <span></span><span></span><span></span>
            </span>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入问题，按 Enter 发送（Shift+Enter 换行）"
          resize="none"
          :disabled="chatStore.loading"
          @keydown.enter.exact.prevent="handleSend"
        />
        <div class="input-actions">
          <el-button
            type="danger"
            text
            :disabled="chatStore.messages.length === 0"
            @click="chatStore.clearMessages()"
          >
            清空对话
          </el-button>
          <el-button
            type="primary"
            :loading="chatStore.loading"
            :disabled="!inputText.trim()"
            @click="handleSend"
          >
            发送
          </el-button>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch } from 'vue'
import { ChatDotRound, Loading, Aim } from '@element-plus/icons-vue'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const chatArea = ref<HTMLElement>()

const scrollToBottom = () => {
  nextTick(() => {
    if (chatArea.value) {
      chatArea.value.scrollTop = chatArea.value.scrollHeight
    }
  })
}

// 监听消息内容变化（包括流式更新），自动滚动
watch(
  () => chatStore.messages.map(m => m.content + (m.thinking || '')).join(''),
  scrollToBottom
)
watch(() => chatStore.loading, scrollToBottom)

const handleSend = async () => {
  const question = inputText.value.trim()
  if (!question || chatStore.loading) return
  inputText.value = ''
  await chatStore.sendStreamMessage(question)
}
</script>

<style scoped>
.chat-container {
  padding: 20px;
  height: 100%;
  display: flex;
  flex-direction: column;
}

h1 {
  margin: 0;
  color: #303133;
}

.chat-card {
  margin-top: 20px;
  flex: 1;
  display: flex;
  flex-direction: column;
}

.chat-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}

.chat-area {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  min-height: 300px;
  max-height: calc(100vh - 340px);
}

.empty-hint {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 200px;
  color: #c0c4cc;
}

.empty-hint p {
  margin-top: 12px;
  font-size: 14px;
}

.message-row {
  display: flex;
  margin-bottom: 16px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

.message-bubble {
  max-width: 70%;
  padding: 12px 16px;
  border-radius: 12px;
  word-break: break-word;
  white-space: pre-wrap;
}

.message-bubble.user {
  background-color: #409eff;
  color: #fff;
  border-bottom-right-radius: 4px;
}

.message-bubble.assistant {
  background-color: #f4f4f5;
  color: #303133;
  border-bottom-left-radius: 4px;
}

/* 思考过程区域 */
.thinking-section {
  margin-bottom: 12px;
  background: rgba(255, 193, 7, 0.1);
  border-radius: 8px;
  overflow: hidden;
}

.thinking-section :deep(.el-collapse) {
  border: none;
  --el-collapse-header-bg-color: transparent;
}

.thinking-section :deep(.el-collapse-item__header) {
  height: 36px;
  line-height: 36px;
  padding: 0 12px;
  background: transparent;
  border: none;
  font-size: 13px;
  color: #b88000;
}

.thinking-section :deep(.el-collapse-item__wrap) {
  background: transparent;
  border: none;
}

.thinking-section :deep(.el-collapse-item__content) {
  padding: 0 12px 12px;
}

.thinking-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #b88000;
  font-weight: 500;
}

.thinking-title .el-icon {
  font-size: 14px;
}

.thinking-content {
  font-size: 13px;
  line-height: 1.6;
  color: #666;
  white-space: pre-wrap;
}

.streaming-indicator {
  display: inline-block;
  width: 6px;
  height: 6px;
  background: #b88000;
  border-radius: 50%;
  margin-left: 4px;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
}

.message-content {
  line-height: 1.6;
  font-size: 14px;
}

.message-content.streaming {
  min-height: 20px;
}

.cursor-blink {
  animation: blink 1s step-end infinite;
  color: #409eff;
  font-weight: bold;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.message-sources {
  margin-top: 8px;
}

.message-sources :deep(.el-collapse-item__header) {
  height: 28px;
  line-height: 28px;
  font-size: 12px;
  color: #909399;
  background: transparent;
  border: none;
}

.message-sources :deep(.el-collapse-item__wrap) {
  background: transparent;
  border: none;
}

.message-sources :deep(.el-collapse-item__content) {
  padding-bottom: 0;
}

.message-sources :deep(.el-collapse) {
  border: none;
}

.source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.source-item {
  display: flex;
  gap: 4px;
  align-items: center;
}

.source-item.source-matched {
  padding: 4px 8px;
  background: rgba(103, 194, 58, 0.1);
  border-radius: 4px;
}

.sources-title {
  display: flex;
  align-items: center;
}

.no-context-hint {
  margin-top: 8px;
}

.message-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 4px;
  text-align: right;
}

.message-bubble.user .message-time {
  color: rgba(255, 255, 255, 0.7);
}

.loading-bubble {
  padding: 16px 24px;
}

.loading-dots {
  display: inline-flex;
  gap: 4px;
}

.loading-dots span {
  width: 8px;
  height: 8px;
  background-color: #909399;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.loading-dots span:nth-child(1) { animation-delay: -0.32s; }
.loading-dots span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.input-area {
  padding: 16px 20px;
  border-top: 1px solid #e4e7ed;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
