<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from "vue";
import { useRoute } from "vue-router";
import { message } from "ant-design-vue";
import { ApiError, apiJson, apiUpload } from "../api";

const route = useRoute();
const kbId = computed(() => route.params.kbId);

const docs = ref([]);
const loading = ref(false);

async function load() {
  if (!kbId.value) return;
  loading.value = true;
  try {
    const res = await apiJson(`/knowledge-bases/${kbId.value}/documents?page=1&page_size=100`);
    docs.value = res.items;
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
    else message.error("加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});

watch(
  () => route.params.kbId,
  () => {
    void load();
  }
);

let pollTimer = null;

watch(
  () => docs.value,
  (list) => {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
    if (list.some((d) => d.status === "pending" || d.status === "processing")) {
      pollTimer = setInterval(() => void load(), 3000);
    }
  },
  { deep: true }
);

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
});

async function pollTask(taskId) {
  try {
    const t = await apiJson(`/tasks/${taskId}`);
    if (t.status === "failed") message.error(t.error_message || "入库失败");
  } catch {
    /* ignore */
  }
}

async function beforeUpload(file) {
  if (!kbId.value) return false;
  try {
    const res = await apiUpload(`/knowledge-bases/${kbId.value}/documents`, file);
    message.success("已上传，处理中…");
    void pollTask(res.task_id);
    await load();
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
    else message.error("上传失败");
  }
  return false;
}

async function remove(id) {
  try {
    await apiJson(`/documents/${id}`, { method: "DELETE" });
    message.success("已删除");
    await load();
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
  }
}

async function reindex(id) {
  try {
    await apiJson(`/documents/${id}/reindex`, { method: "POST" });
    message.success("已加入重索引队列");
    await load();
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
  }
}

function statusColor(s) {
  if (s === "ready") return "green";
  if (s === "failed") return "red";
  return "blue";
}

const columns = [
  { title: "文件名", dataIndex: "filename", key: "filename" },
  { title: "状态", dataIndex: "status", key: "status" },
  { title: "字符数", dataIndex: "char_count", key: "char_count" },
  { title: "错误", dataIndex: "error_message", key: "error_message", ellipsis: true },
  { title: "操作", key: "a" },
];
</script>

<template>
  <div style="padding: 24px; max-width: 1100px; margin: 0 auto">
    <a-space style="margin-bottom: 16px">
      <router-link to="/">← 返回</router-link>
      <a-typography-title :level="3" style="margin: 0">文档管理</a-typography-title>
      <router-link v-if="kbId" :to="`/chat?kb=${kbId}`">
        <a-button type="link">去对话</a-button>
      </router-link>
    </a-space>
    <a-card>
      <a-space style="margin-bottom: 16px">
        <a-upload :show-upload-list="false" :before-upload="beforeUpload">
          <a-button type="primary">上传 PDF / Word / TXT / Markdown</a-button>
        </a-upload>
      </a-space>
      <a-table
        row-key="id"
        :loading="loading"
        :data-source="docs"
        :columns="columns"
        :pagination="false"
      >
        <template #bodyCell="{ column, text, record }">
          <template v-if="column.key === 'status'">
            <a-tag :color="statusColor(text)">{{ text }}</a-tag>
          </template>
          <template v-else-if="column.key === 'error_message'">
            {{ text || "—" }}
          </template>
          <template v-else-if="column.key === 'a'">
            <a-space>
              <a-button size="small" @click="reindex(record.id)">重索引</a-button>
              <a-popconfirm title="确定删除？" @confirm="remove(record.id)">
                <a-button size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
  </div>
</template>
