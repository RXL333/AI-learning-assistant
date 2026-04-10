import { computed, onMounted, ref } from "vue";
import { api } from "../api.js";
import { showToast } from "../toast.js";

const RANGE_OPTIONS = [7, 14, 30];

function formatDateLabel(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
  }).format(date);
}

function weekdayLabel(value) {
  if (!value) return "";
  const date = new Date(`${value}T00:00:00`);
  return ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][(date.getDay() + 6) % 7];
}

function dayTag(value) {
  if (!value) return "";
  const current = new Date(`${value}T00:00:00`);
  const diff = Math.floor((Date.now() - current.getTime()) / 86400000);
  if (diff === 0) return "今天";
  if (diff === 1) return "昨天";
  return `${diff} 天前`;
}

export default {
  name: "HistoryPage",
  setup() {
    const loading = ref(false);
    const rangeDays = ref(14);
    const payload = ref({ summary: {}, weak_points: [], days: [] });

    const summary = computed(() => payload.value?.summary || {});
    const weakPoints = computed(() => payload.value?.weak_points || []);
    const days = computed(() => payload.value?.days || []);

    const load = async () => {
      loading.value = true;
      try {
        const r = await api(`/history/daily?days=${rangeDays.value}`);
        if (r.code === 0) {
          payload.value = r.data || { summary: {}, weak_points: [], days: [] };
        } else {
          showToast(r.message || "学习轨迹加载失败", "error");
        }
      } finally {
        loading.value = false;
      }
    };

    const setRange = async (value) => {
      if (rangeDays.value === value || loading.value) return;
      rangeDays.value = value;
      await load();
    };

    onMounted(load);

    return {
      loading,
      rangeDays,
      rangeOptions: RANGE_OPTIONS,
      summary,
      weakPoints,
      days,
      formatDateLabel,
      weekdayLabel,
      dayTag,
      setRange,
    };
  },
  template: `
    <div class="page history-page history-lite-page">
      <section class="card panel-card history-lite-hero">
        <div class="section-head">
          <div>
            <p class="eyebrow">学习轨迹</p>
            <h1>回看你最近学了什么</h1>
          </div>
        </div>
        <div class="history-range-bar">
          <button
            v-for="option in rangeOptions"
            :key="option"
            class="ghost"
            :class="{ active: rangeDays === option }"
            :disabled="loading"
            @click="setRange(option)"
          >
            最近 {{ option }} 天
          </button>
        </div>
      </section>

      <section class="stats-grid history-lite-stats">
        <article class="stat-card accent-blue">
          <span>问答</span>
          <strong>{{ summary.chat_count || 0 }}</strong>
          <small>这段时间里问过的问题</small>
        </article>
        <article class="stat-card accent-red">
          <span>错题</span>
          <strong>{{ summary.wrong_count || 0 }}</strong>
          <small>新增到错题本的内容</small>
        </article>
        <article class="stat-card accent-green">
          <span>复习</span>
          <strong>{{ summary.review_count || 0 }}</strong>
          <small>安排过的复习任务</small>
        </article>
      </section>

      <section class="card panel-card history-focus-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">最近最该回看</p>
            <h2>先盯住这几个点</h2>
          </div>
        </div>
        <div v-if="!weakPoints.length" class="empty-inline">当前还没有明显的薄弱点。</div>
        <div v-else class="tag-row">
          <span v-for="item in weakPoints" :key="item" class="pill">{{ item }}</span>
        </div>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">按天回看</p>
            <h2>每一天你做了什么</h2>
          </div>
        </div>

        <div v-if="!days.length" class="empty-state">当前范围内还没有可展示的学习记录。</div>

        <div v-else class="history-timeline history-lite-timeline">
          <article v-for="day in days" :key="day.date" class="card history-day-card history-lite-day" :class="{ today: day.is_today }">
            <div class="history-day-head">
              <div>
                <p class="eyebrow">{{ dayTag(day.date) }}</p>
                <h2>{{ formatDateLabel(day.date) }}</h2>
                <p class="muted">{{ weekdayLabel(day.date) }}</p>
              </div>
              <div class="history-day-stats">
                <span class="pill">问答 {{ day.chat_count || 0 }}</span>
                <span class="pill">错题 {{ day.wrong_count || 0 }}</span>
                <span class="pill neutral">复习 {{ day.review_count || 0 }}</span>
              </div>
            </div>

            <div v-if="day.weak_points?.length" class="history-day-focus">
              <span class="muted">这一天值得回看的点：</span>
              <div class="tag-row">
                <span v-for="item in day.weak_points" :key="item" class="pill mini">{{ item }}</span>
              </div>
            </div>

            <div v-if="!day.items.length" class="empty-inline">这一天还没有学习记录。</div>
            <div v-else class="history-lite-list">
              <article v-for="item in day.items" :key="item.id" class="history-item history-lite-item">
                <div class="history-item-head">
                  <div>
                    <span class="pill" :class="{ neutral: item.type === 'review' }">{{ item.type_label }}</span>
                    <strong>{{ item.title }}</strong>
                  </div>
                  <span class="muted">{{ item.created_at }}</span>
                </div>
                <p>{{ item.summary }}</p>
                <small>{{ item.meta }}</small>
              </article>
            </div>
          </article>
        </div>
      </section>
    </div>
  `,
};
