import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter, RouterLink, RouterView } from "vue-router";
import { authState, clearAuth } from "./auth.js";
import { modeState, setModes, setSelectedModeKey } from "./mode.js";
import { toastState } from "./toast.js";
import { api } from "./api.js";

function formatNow(timestamp) {
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(timestamp);
}

export default {
  name: "App",
  components: { RouterLink, RouterView },
  setup() {
    const route = useRoute();
    const router = useRouter();
    const isAuthPage = computed(() => ["/login", "/register"].includes(route.path));
    const currentModel = ref("");
    const nowText = ref(formatNow(Date.now()));
    let timer = null;

    const logout = () => {
      clearAuth();
      router.push("/login");
    };

    const loadMeta = async () => {
      if (isAuthPage.value || !authState.token) {
        currentModel.value = "";
        setModes([]);
        return;
      }

      try {
        const r = await api("/chat/meta");
        if (r.code === 0) {
          currentModel.value = r.data?.model || "";
          setModes(r.data?.modes || []);
          const availableKeys = new Set((r.data?.modes || []).map((item) => item.mode_key));
          const nextMode = availableKeys.has(modeState.selectedModeKey)
            ? modeState.selectedModeKey
            : r.data?.default_mode || "general";
          setSelectedModeKey(nextMode);
        }
      } catch {
        currentModel.value = "";
        setModes([]);
      }
    };

    onMounted(() => {
      timer = window.setInterval(() => {
        nowText.value = formatNow(Date.now());
      }, 1000);
      loadMeta();
    });

    onBeforeUnmount(() => {
      if (timer) window.clearInterval(timer);
    });

    watch(() => route.path, loadMeta);
    watch(() => authState.token, loadMeta);

    return { authState, isAuthPage, logout, toastState, currentModel, nowText, modeState, setSelectedModeKey };
  },
  template: `
    <div>
      <header v-if="!isAuthPage" class="topbar">
        <div class="brand-block">
          <div class="brand-mark">AI</div>
          <div>
            <div class="brand">AI 学习助手</div>
            <div class="brand-sub">问答、错题、复习、导图一体化</div>
          </div>
        </div>
        <nav class="tabs">
          <RouterLink class="tab-link" to="/dashboard">首页</RouterLink>
          <RouterLink class="tab-link" to="/chat">AI 问答</RouterLink>
          <RouterLink class="tab-link" to="/wrong-book">错题本</RouterLink>
          <RouterLink class="tab-link" to="/quiz">AI 出题</RouterLink>
          <RouterLink class="tab-link" to="/history">学习历史</RouterLink>
          <RouterLink class="tab-link" to="/review">复习中心</RouterLink>
          <RouterLink class="tab-link" to="/mindmap">思维导图</RouterLink>
          <RouterLink class="tab-link" to="/profile">个人中心</RouterLink>
        </nav>
        <div class="right">
          <div class="topbar-status">
            <div class="user-badge mode-badge">
              <span class="chat-meta-label">当前模式</span>
              <select class="mode-select" :value="modeState.selectedModeKey" @change="setSelectedModeKey($event.target.value)">
                <option v-for="item in modeState.modes" :key="item.mode_key" :value="item.mode_key">
                  {{ item.mode_name }}
                </option>
              </select>
            </div>
            <div v-if="currentModel" class="user-badge model-badge">
              <span class="chat-meta-label">当前模型</span>
              <strong>{{ currentModel }}</strong>
            </div>
            <div class="user-badge clock-badge">
              <span class="chat-meta-label">当前时间</span>
              <strong>{{ nowText }}</strong>
            </div>
          </div>
          <div class="user-badge">
            <span class="user-dot"></span>
            <span>{{ authState.username || "未登录" }}</span>
          </div>
          <button class="ghost" @click="logout">退出登录</button>
        </div>
      </header>
      <main class="app">
        <RouterView />
      </main>
      <div class="toast-stack">
        <div v-for="item in toastState.items" :key="item.id" class="toast-item" :class="item.type">
          {{ item.message }}
        </div>
      </div>
    </div>
  `,
};
