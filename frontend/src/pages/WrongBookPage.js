import { onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { showToast } from "../toast.js";

export default {
  name: "WrongBookPage",
  setup() {
    const form = reactive({ subject: "数据结构", question_text: "", question_image: "" });
    const filters = reactive({ subject: "", keyword: "", mastery_level: "" });
    const list = ref([]);
    const subjectOptions = ref([]);
    const loading = ref(false);
    const message = ref("");

    const load = async () => {
      const params = new URLSearchParams({ page: "1", page_size: "50" });
      if (filters.subject) params.set("subject", filters.subject);
      if (filters.keyword.trim()) params.set("keyword", filters.keyword.trim());
      if (filters.mastery_level !== "") params.set("mastery_level", String(filters.mastery_level));
      const r = await api(`/wrong-book?${params.toString()}`);
      if (r.code === 0) {
        list.value = r.data.items || [];
        subjectOptions.value = r.data.subject_options || [];
      } else {
        message.value = r.message || "加载失败";
      }
    };

    const create = async () => {
      if (!form.question_text.trim() || loading.value) return;
      loading.value = true;
      message.value = "";
      const payload = {
        subject: form.subject.trim() || "通用",
        question_text: form.question_text.trim(),
        question_image: form.question_image.trim() || null,
      };
      const r = await api("/wrong-book", { method: "POST", body: JSON.stringify(payload) });
      if (r.code === 0) {
        form.question_text = "";
        form.question_image = "";
        showToast("错题已保存并生成分析");
        await load();
      } else {
        message.value = r.message || "保存失败";
      }
      loading.value = false;
    };

    const updateLevel = async (item, level) => {
      const r = await api(`/wrong-book/${item.id}`, {
        method: "PUT",
        body: JSON.stringify({ mastery_level: level }),
      });
      if (r.code === 0) {
        item.mastery_level = r.data.mastery_level;
        item.next_review = r.data.next_review;
        showToast("掌握度已更新");
      } else {
        message.value = r.message || "更新失败";
      }
    };

    const remove = async (id) => {
      const r = await api(`/wrong-book/${id}`, { method: "DELETE" });
      if (r.code === 0) {
        list.value = list.value.filter((item) => item.id !== id);
        showToast("错题已删除");
      } else {
        message.value = r.message || "删除失败";
      }
    };

    const explanationText = (item) => item.analysis?.trim() || "当前还没有生成讲解，请重新录入或稍后再试。";

    onMounted(load);
    return { form, filters, list, subjectOptions, load, create, updateLevel, remove, explanationText, loading, message };
  },
  template: `
    <div class="page">
      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">错题本</p>
            <h2>录入错题后自动生成 AI 分析</h2>
          </div>
          <button class="ghost" @click="load">刷新列表</button>
        </div>
        <div class="form-grid three-col">
          <input v-model="form.subject" placeholder="学科" />
          <input v-model="form.question_image" placeholder="题目图片地址，可不填" />
          <button @click="create" :disabled="loading">{{ loading ? '分析中...' : '加入错题本' }}</button>
        </div>
        <textarea rows="4" v-model="form.question_text" placeholder="输入错题内容、题干、你的错误思路等"></textarea>
        <p class="muted">{{ message }}</p>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">错题筛选</p>
            <h2>支持关键词、学科、掌握度过滤</h2>
          </div>
        </div>
        <div class="form-grid filter-grid">
          <select v-model="filters.subject">
            <option value="">全部学科</option>
            <option v-for="subject in subjectOptions" :key="subject" :value="subject">{{ subject }}</option>
          </select>
          <input v-model="filters.keyword" placeholder="搜索题目关键词" />
          <select v-model="filters.mastery_level">
            <option value="">全部掌握度</option>
            <option v-for="level in 6" :key="level - 1" :value="String(level - 1)">{{ level - 1 }}/5</option>
          </select>
          <button @click="load">应用筛选</button>
        </div>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">错题列表</p>
            <h2>每条都可以直接调整掌握度</h2>
          </div>
        </div>
        <div v-if="!list.length" class="empty-state">当前筛选条件下没有错题。</div>
        <div class="stack-list">
          <article v-for="item in list" :key="item.id" class="content-card">
            <div class="content-head">
              <div>
                <span class="pill">{{ item.subject }}</span>
                <span class="muted">下次复习：{{ item.next_review }}</span>
              </div>
              <button class="ghost small danger" @click="remove(item.id)">删除</button>
            </div>
            <h3>{{ item.question_text }}</h3>
            <div v-if="item.options?.length" class="review-task-block">
              <strong>选项</strong>
              <div class="option-preview-list">
                <div v-for="(option, index) in item.options" :key="index" class="option-preview-item">{{ option }}</div>
              </div>
              <p v-if="item.correct_answer" class="muted">正确答案：{{ item.correct_answer }}</p>
            </div>
            <div class="explain-card">
              <strong>题目讲解</strong>
              <pre class="analysis-box">{{ explanationText(item) }}</pre>
            </div>
            <div class="level-row">
              <span class="muted">掌握度：{{ item.mastery_level }}/5</span>
              <div class="level-actions">
                <button class="ghost small" v-for="level in 6" :key="level" @click="updateLevel(item, level - 1)">{{ level - 1 }}</button>
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>
  `,
};
