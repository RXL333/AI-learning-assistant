import { computed, onMounted, ref } from "vue";
import { api } from "../api.js";
import { modeState } from "../mode.js";
import { showToast } from "../toast.js";

export default {
  name: "TodayReviewPage",
  setup() {
    const loading = ref(false);
    const data = ref(null);
    const message = ref("");

    const summary = computed(() => data.value?.summary || {});
    const tasks = computed(() => data.value?.tasks || []);
    const currentMode = computed(() => modeState.modes.find((item) => item.mode_key === modeState.selectedModeKey) || null);
    const statusLabel = (status) => {
      const map = { unmastered: "还不熟", fuzzy: "有点模糊", mastered: "基本掌握" };
      return map[status] || "还不熟";
    };

    const load = async () => {
      loading.value = true;
      message.value = "";
      const r = await api("/review/today");
      if (r.code === 0) {
        data.value = r.data || null;
      } else {
        message.value = r.message || "加载失败";
      }
      loading.value = false;
    };

    const completeTask = async (task) => {
      if (!task?.id) return;
      const r = await api(`/review/today/${task.id}/complete`, {
        method: "POST",
        body: JSON.stringify({ remembered: true }),
      });
      if (r.code === 0) {
        showToast("任务已完成");
        await load();
      } else {
        showToast(r.message || "完成失败", "error");
      }
    };

    onMounted(load);

    return {
      loading,
      data,
      summary,
      tasks,
      currentMode,
      message,
      statusLabel,
      load,
      completeTask,
    };
  },
  template: `
    <div class="page review-page today-review-page">
      <section class="review-hero">
        <div class="review-hero-main">
          <p class="eyebrow">今日复习</p>
          <h1>今天要先回看哪些内容</h1>
          <p class="hero-copy">系统会根据错题掌握度和下次复习时间，自动整理出今天最值得先做的任务。</p>
          <div class="review-hero-actions">
            <button class="ghost" @click="load" :disabled="loading">{{ loading ? "刷新中..." : "刷新任务" }}</button>
            <span class="muted">{{ message || (data?.date ? "生成日期：" + data.date : "") }}</span>
          </div>
        </div>
        <div class="review-hero-side">
          <div class="review-kpi-grid">
            <article class="review-kpi accent-green">
              <small>当前模式</small>
              <strong>{{ currentMode?.mode_name || "通用模式" }}</strong>
            </article>
          </div>
          <div class="review-kpi-grid">
            <article class="review-kpi accent-orange">
              <small>今日任务</small>
              <strong>{{ summary.task_count || 0 }}</strong>
            </article>
            <article class="review-kpi accent-blue">
              <small>预计总时长</small>
              <strong>{{ summary.total_estimated_minutes || 0 }} 分钟</strong>
            </article>
          </div>
        </div>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">任务列表</p>
            <h2>按掌握度和遗忘节奏自动安排</h2>
          </div>
        </div>

        <div v-if="!tasks.length" class="empty-state">今天没有需要优先复习的内容。</div>

        <div class="stack-list review-task-list">
          <article v-for="task in tasks" :key="task.id" class="content-card review-task-card">
            <div class="content-head">
              <div>
                <span class="pill">{{ task.subject }}</span>
                <span class="pill neutral">{{ statusLabel(task.mastery_status) }}</span>
              </div>
              <span class="pill neutral">{{ task.estimated_minutes }} 分钟</span>
            </div>

            <h3>{{ task.title || (task.subject + " 错题复习") }}</h3>

            <div class="review-task-block">
              <strong>推荐原因</strong>
              <p>{{ task.reason }}</p>
            </div>

            <div class="review-task-block">
              <strong>复习内容</strong>
              <p>{{ task.question_text }}</p>
            </div>

            <div class="history-meta">
              <span>下次复习：{{ task.next_review }}</span>
              <span>任务日期：{{ task.task_date }}</span>
              <span>优先级：{{ task.priority }}</span>
            </div>

            <div class="actions">
              <button @click="completeTask(task)" :disabled="task.status === 'done'">
                {{ task.status === 'done' ? "已完成" : "完成复习" }}
              </button>
            </div>
          </article>
        </div>
      </section>
    </div>
  `,
};
