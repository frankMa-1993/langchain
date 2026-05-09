<script setup>
import { computed, ref, watch, onMounted } from "vue";
import { useRoute } from "vue-router";
import { message, Modal } from "ant-design-vue";
import { ApiError, apiJson, streamChat } from "../api";

const route = useRoute();
const kbFromUrl = computed(() => route.query.kb);

const kbs = ref([]);
const kbId = ref(undefined);
const convs = ref([]);
const convId = ref(undefined);
const msgs = ref([]);
const input = ref("");
const hybrid = ref(true);
const streaming = ref(false);
const abortRef = ref(null);

const batchMode = ref(false);
const selectedConvIds = ref([]);

const kbOptions = computed(() => kbs.value.map((k) => ({ label: k.name, value: k.id })));

async function loadKbs() {
  try {
    const res = await apiJson("/knowledge-bases?page=1&page_size=100");
    kbs.value = res.items;
    if (!kbId.value && res.items[0]) kbId.value = res.items[0].id;
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
  }
}

async function loadConvs() {
  if (!kbId.value) return;
  try {
    const res = await apiJson(`/conversations?kb_id=${kbId.value}&page=1&page_size=50`);
    convs.value = res.items;
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
  }
}

async function loadMsgs(cid) {
  try {
    const res = await apiJson(`/conversations/${cid}/messages?page=1&page_size=200`);
    msgs.value = res.items.map((x) => ({
      role: x.role,
      content: x.content,
      sources: x.sources || undefined,
    }));
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
  }
}

watch(
  () => kbFromUrl.value,
  (v) => {
    if (v) kbId.value = v;
  },
  { immediate: true }
);

watch(kbId, (newId, oldId) => {
  if (oldId !== undefined && newId !== oldId) convId.value = undefined;
  void loadConvs();
});

watch(convId, (cid) => {
  if (cid) void loadMsgs(cid);
  else msgs.value = [];
});

onMounted(() => {
  void loadKbs();
});

async function newChat() {
  if (!kbId.value) return;
  try {
    const c = await apiJson("/conversations", {
      method: "POST",
      body: JSON.stringify({ kb_id: kbId.value }),
    });
    convId.value = c.id;
    msgs.value = [];
    await loadConvs();
    message.success("新会话");
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
  }
}

async function removeConv(id) {
  try {
    await apiJson(`/conversations/${id}`, { method: "DELETE" });
    message.success("会话已删除");
    if (convId.value === id) {
      convId.value = undefined;
      msgs.value = [];
    }
    await loadConvs();
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
    else message.error("删除失败");
  }
}

function batchRemove() {
  if (selectedConvIds.value.length === 0) return;
  Modal.confirm({
    title: "确认批量删除",
    content: `确定要删除选中的 ${selectedConvIds.value.length} 个会话吗？此操作无法恢复。`,
    okText: "删除",
    okButtonProps: { danger: true },
    cancelText: "取消",
    async onOk() {
      try {
        await apiJson("/conversations/batch-delete", {
          method: "POST",
          body: JSON.stringify({ ids: selectedConvIds.value }),
        });
        message.success(`已删除 ${selectedConvIds.value.length} 个会话`);
        if (convId.value && selectedConvIds.value.includes(convId.value)) {
          convId.value = undefined;
          msgs.value = [];
        }
        selectedConvIds.value = [];
        batchMode.value = false;
        await loadConvs();
      } catch (e) {
        if (e instanceof ApiError) message.error(e.message);
        else message.error("批量删除失败");
      }
    },
  });
}

function toggleConvSelection(id) {
  selectedConvIds.value = selectedConvIds.value.includes(id)
    ? selectedConvIds.value.filter((x) => x !== id)
    : [...selectedConvIds.value, id];
}

function selectAllConvs() {
  selectedConvIds.value = convs.value.map((c) => c.id);
}

function clearSelection() {
  selectedConvIds.value = [];
}

function exitBatchMode() {
  batchMode.value = false;
  selectedConvIds.value = [];
}

async function send() {
  const text = input.value.trim();
  if (!text || !convId.value) {
    message.warning("请选择或创建会话");
    return;
  }
  input.value = "";
  msgs.value = [...msgs.value, { role: "user", content: text }];
  streaming.value = true;
  abortRef.value?.abort();
  abortRef.value = new AbortController();
  let acc = "";
  let sources;
  try {
    await streamChat(
      convId.value,
      text,
      hybrid.value,
      (ev) => {
        if (ev.type === "sources") sources = ev.sources;
        if (ev.type === "delta") {
          acc += ev.delta;
          const copy = [...msgs.value];
          const last = copy[copy.length - 1];
          if (last && last.role === "assistant")
            copy[copy.length - 1] = { ...last, content: acc, sources };
          else copy.push({ role: "assistant", content: acc, sources });
          msgs.value = copy;
        }
      },
      abortRef.value.signal
    );
    {
      const copy = [...msgs.value];
      const last = copy[copy.length - 1];
      if (last && last.role === "assistant") copy[copy.length - 1] = { ...last, content: acc, sources };
      msgs.value = copy;
    }
  } catch (e) {
    if (e instanceof ApiError) message.error(e.message);
    else if (e?.name !== "AbortError") message.error("发送失败");
  } finally {
    streaming.value = false;
  }
}

function stopStream() {
  abortRef.value?.abort();
}

function confirmRemoveConv(c) {
  Modal.confirm({
    title: "确认删除",
    content: `确定要删除会话 "${c.title || c.id.slice(0, 8)}" 吗？`,
    okText: "删除",
    okButtonProps: { danger: true },
    cancelText: "取消",
    onOk: () => removeConv(c.id),
  });
}

function onConvListClick(c) {
  if (!batchMode.value) convId.value = c.id;
}

const indeterminate = computed(
  () => selectedConvIds.value.length > 0 && selectedConvIds.value.length < convs.value.length
);
const allChecked = computed(
  () => selectedConvIds.value.length === convs.value.length && convs.value.length > 0
);

function onSelectAllChange(e) {
  if (e.target.checked) selectAllConvs();
  else clearSelection();
}

function onInputKeydown(e) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    void send();
  }
}
</script>

<template>
  <div style="display: flex; height: 100%; min-height: 520px">
    <div
      style="
        width: 280px;
        border-right: 1px solid #f0f0f0;
        padding: 12px;
        overflow: auto;
        display: flex;
        flex-direction: column;
      "
    >
      <a-space direction="vertical" style="width: 100%" :size="'middle'">
        <a-typography-text type="secondary">知识库</a-typography-text>
        <a-select
          style="width: 100%"
          :options="kbOptions"
          v-model:value="kbId"
          placeholder="选择知识库"
        />
        <a-button type="primary" block @click="newChat" :disabled="!kbId || batchMode">新会话</a-button>
        <a-button v-if="!batchMode" block @click="batchMode = true" :disabled="!kbId || convs.length === 0">
          批量管理
        </a-button>
        <a-typography-text type="secondary">历史会话</a-typography-text>
        <a-list
          size="small"
          :data-source="convs"
          :locale="{ emptyText: '暂无' }"
          style="flex: 1; overflow: auto"
        >
          <template #renderItem="{ item: c }">
            <a-list-item
              :style="{
                cursor: batchMode ? 'default' : 'pointer',
                background: convId === c.id ? '#e6f4ff' : undefined,
                paddingLeft: batchMode ? '8px' : '12px',
              }"
              @click="onConvListClick(c)"
            >
              <a-space style="width: 100%">
                <a-checkbox
                  v-if="batchMode"
                  :checked="selectedConvIds.includes(c.id)"
                  @change="() => toggleConvSelection(c.id)"
                  @click.stop
                />
                <a-typography-text ellipsis :title="c.title || c.id" style="flex: 1">
                  {{ c.title || c.id.slice(0, 8) }}
                </a-typography-text>
                <a-button
                  v-if="!batchMode"
                  size="small"
                  danger
                  type="text"
                  @click.stop="confirmRemoveConv(c)"
                >
                  删除
                </a-button>
              </a-space>
            </a-list-item>
          </template>
        </a-list>
      </a-space>
      <div v-if="batchMode" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #f0f0f0">
        <a-space direction="vertical" style="width: 100%">
          <a-space>
            <a-checkbox :indeterminate="indeterminate" :checked="allChecked" @change="onSelectAllChange">
              全选 ({{ selectedConvIds.length }}/{{ convs.length }})
            </a-checkbox>
          </a-space>
          <a-space style="width: 100%; justify-content: space-between">
            <a-button size="small" @click="exitBatchMode">取消</a-button>
            <a-button size="small" danger type="primary" :disabled="selectedConvIds.length === 0" @click="batchRemove">
              删除选中
            </a-button>
          </a-space>
        </a-space>
      </div>
    </div>
    <div style="flex: 1; display: flex; flex-direction: column; padding: 16px">
      <a-card size="small" style="margin-bottom: 12px">
        <a-space wrap>
          <span>
            混合检索（语义+BM25）
            <a-typography-text type="secondary" style="margin-left: 8px">
              提高召回和相关性，能用语义/关键词混合查找答案
            </a-typography-text>
          </span>
          <a-switch v-model:checked="hybrid" />
        </a-space>
      </a-card>
      <div style="flex: 1; overflow: auto; margin-bottom: 12px">
        <a-empty v-if="!convId" description="创建或选择一个会话" />
        <template v-else>
          <div v-for="(m, i) in msgs" :key="i" style="margin-bottom: 16px">
            <a-typography-text strong>{{ m.role === "user" ? "你" : "助手" }}</a-typography-text>
            <div style="white-space: pre-wrap; margin-top: 4px">{{ m.content }}</div>
            <a-collapse
              v-if="m.role === 'assistant' && m.sources && m.sources.length > 0"
              size="small"
              style="margin-top: 8px"
            >
              <a-collapse-panel :key="'src-' + i" :header="'来源 (' + m.sources.length + ')'">
                <ul style="padding-left: 16px; margin: 0">
                  <li v-for="s in m.sources" :key="s.chunk_id">
                    <a-typography-text type="secondary">
                      {{ s.filename }}{{ s.page != null ? ` · p.${s.page}` : "" }}
                    </a-typography-text>
                    <div>{{ s.excerpt }}</div>
                  </li>
                </ul>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </template>
      </div>
      <a-space-compact style="width: 100%">
        <a-textarea
          :rows="2"
          v-model:value="input"
          placeholder="输入问题…"
          :disabled="streaming || !convId"
          style="flex: 1"
          @keydown="onInputKeydown"
        />
        <a-button type="primary" :loading="streaming" @click="send" :disabled="!convId">发送</a-button>
        <a-button v-if="streaming" danger @click="stopStream">停止</a-button>
      </a-space-compact>
    </div>
  </div>
</template>
