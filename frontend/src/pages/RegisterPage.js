import { reactive, ref } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { api } from "../api.js";

export default {
  name: "RegisterPage",
  components: { RouterLink },
  setup() {
    const router = useRouter();
    const form = reactive({ username: "", email: "", password: "" });
    const msg = ref("");
    const loading = ref(false);

    const submit = async () => {
      if (loading.value) return;
      loading.value = true;
      const r = await api("/auth/register", { method: "POST", body: JSON.stringify(form) });
      msg.value = r.message || "";
      if (r.code === 0) setTimeout(() => router.push("/login"), 600);
      loading.value = false;
    };
    return { form, msg, submit, loading };
  },
  template: `
    <div class="auth-wrap">
      <div class="auth-panel">
        <div>
          <p class="eyebrow">创建账号</p>
          <h2>注册 AI 学习助手</h2>
          <p class="muted">注册完成后直接登录即可开始使用问答、错题本、出题和复习模块。</p>
        </div>
        <div class="auth-form">
          <input v-model="form.username" placeholder="用户名" />
          <input v-model="form.email" placeholder="邮箱" />
          <input v-model="form.password" type="password" placeholder="密码" />
          <button @click="submit" :disabled="loading">{{ loading ? '注册中...' : '注册' }}</button>
          <p class="muted">{{ msg }}</p>
          <RouterLink class="tab-link" to="/login">已有账号？去登录</RouterLink>
        </div>
      </div>
    </div>
  `,
};
