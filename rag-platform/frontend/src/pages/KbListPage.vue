<script setup>
import { ref, onMounted, reactive } from "vue";
import { message } from "ant-design-vue";
import { ApiError, apiJson } from "../api";

const rows = ref([]);
const total = ref(0);
const loading = ref(false);
const open = ref(false);
const formRef = ref();
const formState = reactive({ name: "", description: "" });

const columns = [
  { title: "名称", dataIndex: "name", key: "name" },
  { title: "描述", dataIndex: "description", key: "description", ellipsis: true },
  { title: "操作", key: "a", width: 280 },
];

async function load() {
  loading.value = true;
  try {
    const res = await apiJson("/knowledge-bases?page=1&page_size=50");
    rows.value = res.items;
    total.value = res.total;
  } catch (e) {
    if (e instanceof ApiError) message.error(`${e.message}${e.requestId ? ` (${e.requestId})` : ""}`);
    else message.error("加载失败");
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void load();
});

async function handleModalOk() {
  try {
    await formRef.value.validate();
  } catch {
    return false;
  }
  try {
    await apiJson("/knowledge-bases", {
      method: "POST",
      body: JSON.stringify({ name: formState.name, description: formState.description || null }),
    });
    message.success("已创建");
    open.value = false;
    formRef.value.resetFields();
    await load();
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
    else message.error("创建失败");
    return false;
  }
}

async function removeKb(id) {
  try {
    await apiJson(`/knowledge-bases/${id}`, { method: "DELETE" });
    message.success("知识库已删除");
    await load();
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
    else message.error("删除失败");
  }
}

function cancelModal() {
  open.value = false;
}
</script>

<template>
  <div style="padding: 24px; max-width: 1100px; margin: 0 auto">
    <a-space style="margin-bottom: 16px; width: 100%; justify-content: space-between">
      <a-typography-title :level="3" style="margin: 0">知识库</a-typography-title>
      <a-button type="primary" @click="open = true">新建知识库</a-button>
    </a-space>
    <a-card>
      <a-table
        row-key="id"
        :loading="loading"
        :data-source="rows"
        :columns="columns"
        :pagination="{ total, pageSize: 50, showSizeChanger: false }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'a'">
            <a-space>
              <router-link :to="`/kb/${record.id}`">文档</router-link>
              <router-link :to="`/chat?kb=${record.id}`">对话</router-link>
              <a-popconfirm
                title="确定删除此知识库？"
                description="删除后将无法恢复，关联的文档和会话也将被删除。"
                ok-text="删除"
                cancel-text="取消"
                :ok-button-props="{ danger: true }"
                @confirm="removeKb(record.id)"
              >
                <a-button size="small" danger>删除</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>
    <a-modal
      v-model:open="open"
      title="新建知识库"
      ok-text="确定"
      cancel-text="取消"
      destroy-on-close
      @ok="handleModalOk"
      @cancel="cancelModal"
    >
      <a-form ref="formRef" :model="formState" layout="vertical">
        <a-form-item name="name" label="名称" :rules="[{ required: true, message: '请输入名称' }]">
          <a-input v-model:value="formState.name" />
        </a-form-item>
        <a-form-item name="description" label="描述">
          <a-textarea v-model:value="formState.description" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
