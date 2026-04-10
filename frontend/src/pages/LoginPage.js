import { reactive, ref } from "vue";
import { useRouter, RouterLink } from "vue-router";
import { api } from "../api.js";
import { consumePostLoginRedirect, setAuth } from "../auth.js";

export default {
  name: "LoginPage",
  components: { RouterLink },
  setup() {
    const router = useRouter();
    const form = reactive({ username: "", password: "" });
    const msg = ref("");
    const loading = ref(false);

    const submit = async () => {
      if (loading.value) return;
      loading.value = true;
      msg.value = "";
      const r = await api("/auth/login", { method: "POST", body: JSON.stringify(form) });
      if (r.code === 0) {
        setAuth(r.data.token, r.data.user.username);
        router.push(consumePostLoginRedirect());
      } else {
        msg.value = r.message || "登录失败";
      }
      loading.value = false;
    };
    return { form, msg, submit, loading };
  },
  template: `
    <div class="auth-wrap">
      <div class="auth-panel">
        <div>
          <p class="eyebrow">欢迎回来</p>
          <h2>登录 AI 学习助手</h2>
          <p class="muted">登录状态会持久保留，刷新页面不会丢失会话。</p>
        </div>
        <div class="auth-form">
          <input v-model="form.username" placeholder="用户名" />
          <input v-model="form.password" type="password" placeholder="密码" />
          <button @click="submit" :disabled="loading">{{ loading ? '登录中...' : '登录' }}</button>
          <p class="muted">{{ msg }}</p>
          <RouterLink class="tab-link" to="/register">没有账号？去注册</RouterLink>
        </div>
      </div>
    </div>
  `,
};
