import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { authState, updateUsername } from "../auth.js";

function formatDuration(minutes) {
  const hrs = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (!hrs) return `${mins} 分钟`;
  return `${hrs} 小时 ${mins} 分钟`;
}

export default {
  name: "ProfilePage",
  setup() {
    const profile = reactive({ username: "", email: "", created_at: "" });
    const stats = reactive({ study_time: 0, question_count: 0, wrong_count: 0, today_question_count: 0 });
    const form = reactive({ username: "", email: "" });
    const now = ref(Date.now());
    const message = ref("");
    let timer = null;

    const sessionMinutes = computed(() => {
      if (!authState.loginAt) return 0;
      return Math.max(0, Math.floor((now.value - authState.loginAt) / 60000));
    });

    const load = async () => {
      const [p, s] = await Promise.all([api("/user/profile"), api("/user/stats")]);
      if (p.code === 0) {
        Object.assign(profile, p.data);
        form.username = p.data.username || "";
        form.email = p.data.email || "";
      }
      if (s.code === 0) Object.assign(stats, s.data);
    };

    const save = async () => {
      message.value = "";
      const r = await api("/user/profile", { method: "PUT", body: JSON.stringify(form) });
      if (r.code === 0) {
        Object.assign(profile, r.data);
        updateUsername(r.data.username);
        message.value = "个人信息已更新";
      } else {
        message.value = r.message || "保存失败";
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

    return { profile, stats, form, save, message, sessionMinutes, formatDuration };
  },
  template: `
    <div class="page profile-page">
      <section class="profile-hero">
        <div class="profile-hero-main">
          <p class="eyebrow">个人中心</p>
          <h1>{{ profile.username || '学习者' }}</h1>
          <p class="hero-copy">你可以在这里查看账号信息、了解学习概况，并随时更新个人资料。</p>
        </div>
        <div class="profile-hero-side">
          <span>本次在线时长</span>
          <strong>{{ formatDuration(sessionMinutes) }}</strong>
          <small>注册时间：{{ profile.created_at || '-' }}</small>
        </div>
      </section>

      <section class="stats-grid">
        <div class="stat-card accent-orange">
          <span>累计学习时长</span>
          <strong>{{ stats.study_time }} 分钟</strong>
        </div>
        <div class="stat-card accent-blue">
          <span>累计提问</span>
          <strong>{{ stats.question_count }}</strong>
        </div>
        <div class="stat-card accent-green">
          <span>今日提问</span>
          <strong>{{ stats.today_question_count }}</strong>
        </div>
        <div class="stat-card accent-red">
          <span>错题总数</span>
          <strong>{{ stats.wrong_count }}</strong>
        </div>
      </section>

      <section class="profile-grid">
        <div class="card panel-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">资料编辑</p>
              <h2>更新账号信息</h2>
            </div>
          </div>
          <div class="form-grid two-col">
            <input v-model="form.username" placeholder="用户名" />
            <input v-model="form.email" placeholder="邮箱" />
          </div>
          <div class="actions">
            <button @click="save">保存修改</button>
            <span class="muted">{{ message }}</span>
          </div>
        </div>

        <div class="card panel-card">
          <div class="section-head">
            <div>
              <p class="eyebrow">账号概览</p>
              <h2>当前账号信息</h2>
            </div>
          </div>
          <div class="info-list">
            <div class="info-row"><span>用户名</span><strong>{{ profile.username || '-' }}</strong></div>
            <div class="info-row"><span>邮箱</span><strong>{{ profile.email || '-' }}</strong></div>
            <div class="info-row"><span>注册日期</span><strong>{{ profile.created_at || '-' }}</strong></div>
            <div class="info-row"><span>当前状态</span><strong>已登录</strong></div>
          </div>
        </div>
      </section>
    </div>
  `,
};
