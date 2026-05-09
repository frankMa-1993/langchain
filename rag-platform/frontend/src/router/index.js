import { createRouter, createWebHistory } from "vue-router";
import KbListPage from "../pages/KbListPage.vue";
import KbDocsPage from "../pages/KbDocsPage.vue";
import ChatPage from "../pages/ChatPage.vue";

const routes = [
  { path: "/", name: "home", component: KbListPage },
  { path: "/kb/:kbId", name: "kbDocs", component: KbDocsPage },
  { path: "/chat", name: "chat", component: ChatPage },
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

export const router = createRouter({
  history: createWebHistory(),
  routes,
});
