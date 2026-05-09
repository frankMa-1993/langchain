<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { theme } from "ant-design-vue";
import { getApiKey, setApiKey } from "./api";

const route = useRoute();

const selectedKeys = computed(() => (route.path.startsWith("/chat") ? ["chat"] : ["home"]));

const keyInput = ref(getApiKey() || "");

function saveApiKey() {
  setApiKey(keyInput.value.trim() || null);
  keyInput.value = getApiKey() || "";
}
</script>

<template>
  <a-config-provider :theme="{ algorithm: theme.defaultAlgorithm }">
    <a-layout style="min-height: 100%">
      <a-layout-header style="display: flex; align-items: center; gap: 16px; padding-inline: 16px">
        <a-typography-text style="color: #fff; font-weight: 600; white-space: nowrap">
          RAG 平台
        </a-typography-text>
        <a-menu
          :selected-keys="selectedKeys"
          theme="dark"
          mode="horizontal"
          :style="{ flex: 1, minWidth: 0, lineHeight: '64px', borderBottom: 'none' }"
        >
          <a-menu-item key="home">
            <router-link to="/">知识库</router-link>
          </a-menu-item>
          <a-menu-item key="chat">
            <router-link to="/chat">对话</router-link>
          </a-menu-item>
        </a-menu>
        <a-space-compact style="max-width: 280px">
          <a-input-password v-model:value="keyInput" placeholder="X-API-Key（可选）" />
          <a-button type="primary" @click="saveApiKey">保存</a-button>
        </a-space-compact>
      </a-layout-header>
      <a-layout-content :style="{ background: route.path === '/chat' ? '#fff' : '#f5f5f5' }">
        <div v-if="route.path === '/chat'" style="background: #fff; min-height: calc(100vh - 64px)">
          <router-view />
        </div>
        <router-view v-else />
      </a-layout-content>
    </a-layout>
  </a-config-provider>
</template>
