import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "../api.js";
import { showToast } from "../toast.js";

export default {
  name: "ReviewPage",
  setup() {
    const router = useRouter();
    const plan = ref(null);
    const loading = ref(false);
    const message = ref("");

    const summary = computed(() => plan.value?.summary || {});
    const todayTasks = computed(() => plan.value?.today_tasks || []);
    const weekRoute = computed(() => plan.value?.week_route || []);
    const weakSpots = computed(() => plan.value?.weak_spots || []);

    const load = async () => {
      loading.value = true;
      message.value = "";
      const r = await api("/review");
      if (r.code === 0) {
        plan.value = r.data || null;
      } else {
        message.value = r.message || "加载失败";
      }
      loading.value = false;
    };

    const done = async (task) => {
      if (!task?.can_complete || !task.id) return;
      const r = await api("/review/complete", { method: "POST", body: JSON.stringify({ review_id: task.id }) });
      if (r.code === 0) {
        showToast("这项复习已完成");
        await load();
      } else {
        message.value = r.message || "操作失败";
      }
    };

    const askAI = async (task) => {
      if (!task?.ai_prompt) return;
      await router.push({
        path: "/chat",
        query: {
          subject: task.subject || "通用",
          ask: task.ai_prompt,
          auto: "1",
        },
      });
    };

    onMounted(load);

    return {
      summary,
      todayTasks,
      weekRoute,
      weakSpots,
      loading,
      message,
      load,
      done,
      askAI,
    };
  },
  template: `
    <div class="page review-page">
      <section class="review-hero">
        <div class="review-hero-main">
          <p class="eyebrow">复习中心</p>
          <h1>今天先补 {{ summary.today_focus || "当前最薄弱的内容" }}</h1>
          <p class="hero-copy">这里只保留真正会用到的内容：今天该做什么、为什么先做、做完后怎么继续。</p>
          <div class="review-hero-actions">
            <button class="ghost" @click="load" :disabled="loading">{{ loading ? "刷新中..." : "刷新任务" }}</button>
            <span class="muted">{{ message || ("更新时间：" + (summary.today_task_count !== undefined ? "已生成" : "")) }}</span>
          </div>
        </div>
        <div class="review-hero-side">
          <div class="review-kpi-grid">
            <article class="review-kpi accent-orange">
              <small>今日任务</small>
              <strong>{{ summary.today_task_count || 0 }}</strong>
            </article>
            <article class="review-kpi accent-blue">
              <small>到期复习</small>
              <strong>{{ summary.due_now_count || 0 }}</strong>
            </article>
            <article class="review-kpi accent-green">
              <small>近 7 天学习</small>
              <strong>{{ summary.study_minutes_7d || 0 }} 分钟</strong>
            </article>
            <article class="review-kpi accent-red">
              <small>薄弱学科</small>
              <strong>{{ summary.weak_subject_count || 0 }}</strong>
            </article>
          </div>
        </div>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">今天先做这些</p>
            <h2>从最该补的任务开始</h2>
          </div>
        </div>
        <div v-if="!todayTasks.length" class="empty-state">当前还没有需要优先处理的复习任务。</div>
        <div class="stack-list review-task-list">
          <article v-for="task in todayTasks" :key="task.id || task.title" class="content-card review-task-card">
            <div class="content-head">
              <div>
                <span class="pill">{{ task.subject }}</span>
                <span class="muted">{{ task.priority }} · 预计 {{ task.eta_minutes }} 分钟</span>
              </div>
              <span class="pill neutral" v-if="task.mastery_level !== null && task.mastery_level !== undefined">掌握度 {{ task.mastery_level }}/5</span>
            </div>
            <h3>{{ task.title }}</h3>
            <div class="review-task-block">
              <strong>为什么先做</strong>
              <p>{{ task.reason }}</p>
            </div>
            <div class="review-task-block">
              <strong>复习内容</strong>
              <p>{{ task.question_text }}</p>
            </div>
            <div class="review-task-block" v-if="task.explanation">
              <strong>讲解</strong>
              <pre class="analysis-box">{{ task.explanation }}</pre>
            </div>
            <div class="actions">
              <button v-if="task.can_complete" @click="done(task)">完成复习</button>
              <button class="ghost" @click="askAI(task)">AI 带我复习</button>
            </div>
          </article>
        </div>
      </section>

      <section class="review-two-col">
        <section class="card panel-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">接下来几天</p>
              <h2>简单看一下后面的安排</h2>
            </div>
          </div>
          <div class="review-route-list">
            <article v-for="day in weekRoute" :key="day.date" class="route-card">
              <div class="content-head">
                <div>
                  <strong>{{ day.label }}</strong>
                  <p class="muted">{{ day.date }} · {{ day.subject }}</p>
                </div>
                <span class="pill neutral">{{ day.task_count }} 项</span>
              </div>
              <h3>{{ day.theme }}</h3>
            </article>
          </div>
        </section>

        <section class="card panel-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">当前薄弱点</p>
              <h2>先盯住最需要补的 3 个方向</h2>
            </div>
          </div>
          <div v-if="!weakSpots.length" class="empty-state">当前数据还不够，继续做题和提问后这里会更准确。</div>
          <div class="review-weak-list">
            <article v-for="item in weakSpots" :key="item.subject" class="weak-card">
              <div class="content-head">
                <div>
                  <span class="pill">{{ item.subject }}</span>
                  <span class="muted">优先级 {{ item.priority }}</span>
                </div>
                <span class="pill neutral">掌握度 {{ item.avg_mastery }}</span>
              </div>
              <p>{{ item.reason }}</p>
            </article>
          </div>
        </section>
      </section>
    </div>
  `,
};
