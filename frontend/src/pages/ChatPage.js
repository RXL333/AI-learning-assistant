import { computed, nextTick, onMounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api } from "../api.js";
import { authState } from "../auth.js";
import { modeState } from "../mode.js";
import { showToast } from "../toast.js";

async function readEventStream(response, handlers) {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("当前环境暂不支持流式回答。");

  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done });

    let boundary = buffer.indexOf("\n\n");
    while (boundary !== -1) {
      const block = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      boundary = buffer.indexOf("\n\n");

      const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
      if (!lines.length) continue;

      let eventName = "message";
      let dataText = "";
      for (const line of lines) {
        if (line.startsWith("event:")) eventName = line.slice(6).trim();
        if (line.startsWith("data:")) dataText += line.slice(5).trim();
      }
      if (!dataText) continue;

      let data = {};
      try {
        data = JSON.parse(dataText);
      } catch {
        data = { message: dataText };
      }

      if (eventName === "delta" && handlers.onDelta) handlers.onDelta(data);
      if (eventName === "done" && handlers.onDone) handlers.onDone(data);
      if (eventName === "error" && handlers.onError) handlers.onError(data);
    }

    if (done) break;
  }
}

function initConvertState(state, key) {
  if (!state[key]) state[key] = { wrong_question: false, review: false, mindmap: false };
  return state[key];
}

export default {
  name: "ChatPage",
  setup() {
    const route = useRoute();
    const router = useRouter();
    const records = ref([]);
    const form = reactive({ subject: "通用", question: "" });
    const loading = ref(false);
    const message = ref("");
    const errorMessage = ref("");
    const chatBox = ref(null);
    const lastAutoAsk = ref("");
    const modelName = ref("");
    const convertLoading = reactive({});
    const converted = reactive({});
    const abortController = ref(null);

    const currentMode = computed(() => modeState.modes.find((item) => item.mode_key === modeState.selectedModeKey) || null);
    const currentModeLabel = computed(() => currentMode.value?.mode_name || "通用模式");
    const encourageMode = computed(() => modeState.selectedModeKey === "encourage");

    const shouldShowStructured = (item) => {
      if (!item?.structured) return false;
      if ((item.mode_key || modeState.selectedModeKey) === "encourage") return false;
      return true;
    };

    const scrollBottom = async () => {
      await nextTick();
      if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight;
    };

    const loadMeta = async () => {
      const r = await api("/chat/meta");
      if (r.code === 0) modelName.value = r.data?.model || "";
    };

    const loadHistory = async () => {
      message.value = "";
      const r = await api("/chat/history?page=1&page_size=50");
      if (r.code === 0) {
        records.value = (r.data || []).slice().reverse();
        await scrollBottom();
      } else {
        message.value = r.message || "加载历史失败";
      }
    };

    const send = async () => {
      const question = form.question.trim();
      if (!question || loading.value) return;

      loading.value = true;
      message.value = "";
      errorMessage.value = "";

      const subject = form.subject.trim() || "通用";
      form.question = "";

      const tempId = `stream-${Date.now()}`;
      const pendingRecord = {
        id: tempId,
        question,
        answer: "",
        structured: null,
        follow_ups: [],
        structured_quality: "fallback",
        subject,
        mode_key: modeState.selectedModeKey || "general",
        model: modelName.value || "streaming",
        created_at: "生成中...",
        streaming: true,
        feedback_type: "",
      };
      records.value.push(pendingRecord);
      await scrollBottom();

      const controller = new AbortController();
      abortController.value = controller;

      try {
        const response = await fetch("/api/chat/stream", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(authState.token ? { Authorization: `Bearer ${authState.token}` } : {}),
          },
          body: JSON.stringify({ question, subject, mode_key: modeState.selectedModeKey || "general" }),
          signal: controller.signal,
        });

        if (response.status === 401) throw new Error("登录已失效，请重新登录。");
        if (!response.ok) throw new Error(`请求失败：${response.status}`);

        await readEventStream(response, {
          onDelta: async (data) => {
            pendingRecord.answer += data.content || "";
            await scrollBottom();
          },
          onDone: async (data) => {
            const index = records.value.findIndex((item) => item.id === tempId);
            if (index !== -1) records.value[index] = { ...data, streaming: false, feedback_type: "" };
            message.value = "回答已完成";
            await scrollBottom();
          },
          onError: (data) => {
            throw new Error(data.message || "发送失败");
          },
        });
      } catch (error) {
        if (error.name === "AbortError") {
          const index = records.value.findIndex((item) => item.id === tempId);
          if (index !== -1) records.value[index].streaming = false;
          message.value = "已停止生成";
        } else {
          records.value = records.value.filter((item) => item.id !== tempId);
          errorMessage.value = error.message || "发送失败";
          showToast(errorMessage.value, "error");
        }
      } finally {
        loading.value = false;
        abortController.value = null;
      }
    };

    const stopGenerating = () => {
      if (abortController.value) abortController.value.abort();
    };

    const consumePrefill = async () => {
      const ask = typeof route.query.ask === "string" ? route.query.ask.trim() : "";
      const subject = typeof route.query.subject === "string" ? route.query.subject.trim() : "";
      const auto = route.query.auto === "1";
      if (!ask) return;
      form.question = ask;
      if (subject) form.subject = subject;
      const autoKey = `${form.subject}::${ask}`;
      if (auto && lastAutoAsk.value !== autoKey && !loading.value) {
        lastAutoAsk.value = autoKey;
        await send();
        await router.replace({ path: "/chat" });
      }
    };

    const remove = async (id) => {
      if (String(id).startsWith("stream-")) return;
      const r = await api(`/chat/${id}`, { method: "DELETE" });
      if (r.code === 0) {
        records.value = records.value.filter((item) => item.id !== id);
      } else {
        message.value = r.message || "删除失败";
      }
    };

    const clearAll = async () => {
      if (!records.value.length) return;
      const r = await api("/chat/clear", { method: "DELETE" });
      if (r.code === 0) {
        records.value = [];
        message.value = "问答记录已清空";
        errorMessage.value = "";
      } else {
        message.value = r.message || "清空失败";
      }
    };

    const sendFeedback = async (item, feedbackType) => {
      if (!item?.id || String(item.id).startsWith("stream-")) return;
      try {
        const r = await api(`/chat/${item.id}/feedback`, {
          method: "POST",
          body: JSON.stringify({ feedback_type: feedbackType }),
        });
        if (r.code !== 0) throw new Error(r.message || "反馈失败");
        item.feedback_type = feedbackType;
        showToast(feedbackType === "useful" ? "已标记为有帮助" : "已标记为还没听懂");
      } catch (error) {
        showToast(error.message || "反馈失败", "error");
      }
    };

    const convertFromChat = async (item, type) => {
      if (!item?.id || item.streaming || String(item.id).startsWith("stream-")) return;
      const recordKey = String(item.id);
      const state = initConvertState(converted, recordKey);
      if (state[type]) return;

      if (!convertLoading[recordKey]) convertLoading[recordKey] = {};
      convertLoading[recordKey][type] = true;

      try {
        const pathMap = {
          wrong_question: "/convert/to-wrong-question",
          review: "/convert/to-review",
          mindmap: "/convert/to-mindmap",
        };
        const r = await api(pathMap[type], { method: "POST", body: JSON.stringify({ chat_id: item.id }) });
        if (r.code !== 0) throw new Error(r.message || "转换失败");

        state[type] = true;
        const data = r.data || {};
        if (type === "wrong_question") {
          const count = data.created_count || 0;
          showToast(count ? `已加入错题本（${count} 条）` : "这条问答已经在错题本里了");
        } else if (type === "review") {
          const count = data.created_count || 0;
          showToast(count ? `已加入复习计划（${count} 项）` : "这条问答已经在复习计划里了");
        } else {
          showToast("思维导图已生成");
        }
      } catch (error) {
        showToast(error.message || "转换失败", "error");
      } finally {
        convertLoading[recordKey][type] = false;
      }
    };

    const isConverting = (id, type) => Boolean(convertLoading[String(id)]?.[type]);
    const isConverted = (id, type) => Boolean(converted[String(id)]?.[type]);

    onMounted(async () => {
      await loadMeta();
      await loadHistory();
      await consumePrefill();
    });

    return {
      records,
      form,
      send,
      stopGenerating,
      loadHistory,
      remove,
      clearAll,
      loading,
      message,
      errorMessage,
      chatBox,
      modelName,
      convertFromChat,
      isConverting,
      isConverted,
      sendFeedback,
      currentModeLabel,
      currentMode,
      encourageMode,
      shouldShowStructured,
    };
  },
  template: `
    <div class="page">
      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">AI 问答</p>
            <h2>{{ encourageMode ? '更轻一点地聊，也可以继续学' : '结构化回答 + 反馈 + 后续转换' }}</h2>
          </div>
          <div class="actions">
            <button class="ghost" @click="loadHistory">刷新历史</button>
            <button class="ghost danger" @click="clearAll">清空记录</button>
          </div>
        </div>

        <div class="chat-meta-card single-meta">
          <div class="chat-meta-item">
            <span class="chat-meta-label">当前模式</span>
            <strong>{{ currentModeLabel }}</strong>
            <span class="muted">{{ currentMode?.description || '根据你的问题自动组织回答。' }}</span>
          </div>
          <div class="chat-meta-item" v-if="modelName">
            <span class="chat-meta-label">当前模型</span>
            <strong>{{ modelName }}</strong>
          </div>
        </div>

        <div v-if="errorMessage" class="chat-error-banner">
          <strong>本次调用失败</strong>
          <span>{{ errorMessage }}</span>
        </div>

        <div class="form-row two-col">
          <input v-model="form.subject" placeholder="学科，例如：操作系统" />
          <span class="muted inline-tip">
            {{ encourageMode ? '鼓励模式会尽量保持自然对话，不额外展开结论、例题和知识点块。' : '回答完成后可以直接转成错题、复习任务或思维导图。' }}
          </span>
        </div>

        <div class="chat-list rich-chat" ref="chatBox">
          <div v-if="!records.length" class="empty-state">还没有问答记录，先提一个问题。</div>
          <article v-for="item in records" :key="item.id" class="qa-card">
            <div class="qa-head">
              <div>
                <span class="pill">{{ item.subject }}</span>
                <span class="muted">{{ item.created_at }}</span>
                <span class="pill neutral">{{ item.model || "未记录模型" }}</span>
              </div>
              <button class="ghost small danger" @click="remove(item.id)" :disabled="item.streaming">删除这条</button>
            </div>

            <div class="qa-block user-block">
              <strong>你问：</strong>
              <p>{{ item.question }}</p>
            </div>

            <div class="qa-block ai-block streaming-answer" :class="{ typing: item.streaming }">
              <strong>AI 回答：</strong>
              <p>{{ item.answer || (item.streaming ? "正在生成..." : "暂无内容") }}</p>
            </div>

            <div v-if="shouldShowStructured(item)" class="chat-structured">
              <div class="structured-grid">
                <div class="structured-item">
                  <strong>结论</strong>
                  <p>{{ item.structured.conclusion }}</p>
                </div>
                <div class="structured-item">
                  <strong>解释</strong>
                  <p>{{ item.structured.explanation }}</p>
                </div>
              </div>

              <div class="structured-item">
                <strong>例题</strong>
                <p><b>题目：</b>{{ item.structured.example?.question }}</p>
                <p><b>答案：</b>{{ item.structured.example?.answer }}</p>
                <p><b>分析：</b>{{ item.structured.example?.analysis }}</p>
              </div>

              <div class="structured-grid">
                <div class="structured-item">
                  <strong>易错点</strong>
                  <ul class="structured-list">
                    <li v-for="(pitfall, idx) in (item.structured.pitfalls || [])" :key="idx">{{ pitfall }}</li>
                  </ul>
                </div>
                <div class="structured-item">
                  <strong>延伸知识</strong>
                  <ul class="structured-list">
                    <li v-for="(ext, idx) in (item.structured.extensions || [])" :key="idx">{{ ext }}</li>
                  </ul>
                </div>
              </div>

              <div class="structured-item" v-if="(item.follow_ups || []).length">
                <strong>你接下来还可以问</strong>
                <ul class="structured-list">
                  <li v-for="(q, idx) in (item.follow_ups || [])" :key="idx">{{ q }}</li>
                </ul>
              </div>
            </div>

            <div class="actions feedback-actions">
              <button class="ghost" @click="sendFeedback(item, 'useful')" :disabled="item.feedback_type === 'useful'">
                {{ item.feedback_type === 'useful' ? '已标记为有帮助' : '标记为有帮助' }}
              </button>
              <button class="ghost" @click="sendFeedback(item, 'confusing')" :disabled="item.feedback_type === 'confusing'">
                {{ item.feedback_type === 'confusing' ? '已标记为还没听懂' : '标记为还没听懂' }}
              </button>
            </div>

            <div class="actions convert-actions">
              <button
                class="ghost"
                @click="convertFromChat(item, 'wrong_question')"
                :disabled="item.streaming || isConverting(item.id, 'wrong_question') || isConverted(item.id, 'wrong_question')"
              >
                {{ isConverted(item.id, 'wrong_question') ? '已加入错题本' : (isConverting(item.id, 'wrong_question') ? '处理中...' : '加入错题本') }}
              </button>
              <button
                class="ghost"
                @click="convertFromChat(item, 'review')"
                :disabled="item.streaming || isConverting(item.id, 'review') || isConverted(item.id, 'review')"
              >
                {{ isConverted(item.id, 'review') ? '已加入复习计划' : (isConverting(item.id, 'review') ? '处理中...' : '加入复习计划') }}
              </button>
              <button
                class="ghost"
                @click="convertFromChat(item, 'mindmap')"
                :disabled="item.streaming || isConverting(item.id, 'mindmap') || isConverted(item.id, 'mindmap')"
              >
                {{ isConverted(item.id, 'mindmap') ? '已生成思维导图' : (isConverting(item.id, 'mindmap') ? '处理中...' : '生成思维导图') }}
              </button>
            </div>
          </article>
        </div>

        <div class="compose-box">
          <textarea rows="4" v-model="form.question" @keydown.enter.exact.prevent="send" placeholder="输入问题，按 Enter 发送，Shift + Enter 换行"></textarea>
          <div class="compose-actions">
            <p class="muted">{{ message }}</p>
            <div class="actions">
              <button @click="send" :disabled="loading">{{ loading ? "生成中..." : "发送问题" }}</button>
              <button v-if="loading" class="ghost danger" @click="stopGenerating">停止生成</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  `,
};
