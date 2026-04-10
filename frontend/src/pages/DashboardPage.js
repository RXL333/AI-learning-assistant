import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { authState } from "../auth.js";

function formatDuration(minutes) {
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (!hrs) return `${mins} 分钟`;
  return `${hrs} 小时 ${mins} 分钟`;
}

export default {
  name: "DashboardPage",
  setup() {
    const stats = reactive({ study_time: 0, question_count: 0, wrong_count: 0, today_question_count: 0 });
    const calendar = ref([]);
    const monthLabel = ref("");
    const now = ref(Date.now());
    let timer = null;

    const sessionMinutes = computed(() => {
      if (!authState.loginAt) return 0;
      return Math.max(0, Math.floor((now.value - authState.loginAt) / 60000));
    });

    const calendarCells = computed(() => {
      if (!calendar.value.length) return [];
      const firstDate = new Date(`${calendar.value[0].date}T00:00:00`);
      const leading = (firstDate.getDay() + 6) % 7;
      const cells = [];
      for (let i = 0; i < leading; i += 1) cells.push({ empty: true, key: `empty-${i}` });
      calendar.value.forEach((item) => {
        const count = item.count || 0;
        cells.push({
          ...item,
          key: item.date,
          day: Number(item.date.slice(-2)),
          level: count >= 5 ? "high" : count >= 2 ? "mid" : count >= 1 ? "low" : "none",
        });
      });
      return cells;
    });

    const load = async () => {
      const [statsRes, calendarRes] = await Promise.all([api("/user/stats"), api("/user/activity-calendar")]);
      if (statsRes.code === 0) Object.assign(stats, statsRes.data);
      if (calendarRes.code === 0) {
        calendar.value = calendarRes.data.days || [];
        monthLabel.value = calendarRes.data.month || "";
      }
    };

    onMounted(() => {
      load();
      timer = window.setInterval(() => {
        now.value = Date.now();
      }, 1000);
    });

    onBeforeUnmount(() => {
      if (timer) window.clearInterval(timer);
    });

    return { stats, sessionMinutes, formatDuration, monthLabel, calendarCells };
  },
  template: `
    <div class="page dashboard-page">
      <section class="hero-card">
        <div>
          <p class="eyebrow">学习面板</p>
          <h1>今天继续把问题消灭掉</h1>
          <p class="hero-copy">这里会汇总你的学习数据和本月提问情况，方便你快速了解自己的学习节奏。</p>
        </div>
        <div class="hero-stat">
          <span>本次在线时长</span>
          <strong>{{ formatDuration(sessionMinutes) }}</strong>
          <small>从本次进入系统开始累计，关闭页面后会重新计算</small>
        </div>
      </section>

      <section class="stats-grid">
        <div class="stat-card accent-orange">
          <span>累计学习时长</span>
          <strong>{{ stats.study_time }} 分钟</strong>
          <small>历史学习记录总和</small>
        </div>
        <div class="stat-card accent-blue">
          <span>累计提问次数</span>
          <strong>{{ stats.question_count }}</strong>
          <small>所有 AI 问答记录</small>
        </div>
        <div class="stat-card accent-green">
          <span>今日提问次数</span>
          <strong>{{ stats.today_question_count }}</strong>
          <small>今天新产生的提问</small>
        </div>
        <div class="stat-card accent-red">
          <span>错题数量</span>
          <strong>{{ stats.wrong_count }}</strong>
          <small>当前错题本总数</small>
        </div>
      </section>

      <section class="calendar-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">学习日历</p>
            <h2>{{ monthLabel || '本月' }} 提问热力图</h2>
          </div>
          <p class="muted">日期下方标出当天提问次数</p>
        </div>
        <div class="calendar-weekdays">
          <span>一</span>
          <span>二</span>
          <span>三</span>
          <span>四</span>
          <span>五</span>
          <span>六</span>
          <span>日</span>
        </div>
        <div class="calendar-grid large-calendar">
          <div v-for="cell in calendarCells" :key="cell.key" class="calendar-cell" :class="cell.empty ? 'empty' : cell.level">
            <template v-if="!cell.empty">
              <span class="calendar-day">{{ cell.day }}</span>
              <span class="calendar-count">{{ cell.count }} 次提问</span>
            </template>
          </div>
        </div>
      </section>
    </div>
  `,
};
