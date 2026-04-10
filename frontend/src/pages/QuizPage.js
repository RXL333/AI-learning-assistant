import { onMounted, reactive, ref } from "vue";
import { api } from "../api.js";
import { modeState } from "../mode.js";
import { showToast } from "../toast.js";
import { useRouter } from "vue-router";

export default {
  name: "QuizPage",
  setup() {
    const router = useRouter();
    const form = reactive({ subject: "操作系统", topic: "进程调度", count: 5 });
    const quizId = ref(null);
    const questions = ref([]);
    const answers = ref([]);
    const result = ref(null);
    const history = ref([]);
    const loading = ref(false);
    const message = ref("");

    const resetCurrentQuiz = () => {
      quizId.value = null;
      questions.value = [];
      answers.value = [];
      result.value = null;
    };

    const loadHistory = async () => {
      const r = await api("/quiz/history?page=1&page_size=10");
      if (r.code === 0) {
        history.value = r.data || [];
      } else {
        message.value = r.message || "加载历史试卷失败";
      }
    };

    const loadQuizDetail = async (id) => {
      const r = await api(`/quiz/${id}`);
      if (r.code === 0) {
        quizId.value = r.data.id;
        questions.value = r.data.questions || [];
        answers.value = new Array(questions.value.length).fill("");
        result.value =
          r.data.score === null
            ? null
            : {
                score: r.data.score,
                correct_rate: r.data.correct_rate || 0,
                wrong_added: 0,
              };
        form.subject = r.data.subject || form.subject;
        form.topic = r.data.topic || form.topic;
        showToast("已载入历史试卷");
      } else {
        resetCurrentQuiz();
        message.value = r.message || "试卷不存在";
      }
    };

    const generate = async () => {
      loading.value = true;
      message.value = "";
      result.value = null;
      const r = await api("/quiz/generate", {
        method: "POST",
        body: JSON.stringify({ ...form, mode_key: modeState.selectedModeKey || "general" }),
      });
      if (r.code === 0) {
        quizId.value = r.data.quiz_id;
        questions.value = r.data.questions || [];
        answers.value = new Array(questions.value.length).fill("");
        showToast("题目已生成");
        await loadHistory();
      } else {
        message.value = r.message || "生成失败";
      }
      loading.value = false;
    };

    const explanationText = (question) =>
      question.analysis?.trim() || "当前还没有生成讲解，可以点击“AI 追问”继续追问这道题。";

    const askAI = async (question) => {
      const prompt = [
        `请继续讲解这道${form.subject || "通用"}题。`,
        `知识点：${form.topic || "未指定"}`,
        `题目：${question.question}`,
        `选项：${(question.options || []).join("；") || "无"}`,
        `参考答案：${question.answer || "未提供"}`,
        "我还没完全听懂，请你用更容易理解的方式重新讲一遍，并给一个简短例子。",
      ].join("\n");
      await router.push({
        path: "/chat",
        query: {
          subject: form.subject || "通用",
          ask: prompt,
          auto: "1",
          mode_key: modeState.selectedModeKey || "general",
        },
      });
    };

    const removeQuiz = async (id) => {
      const r = await api(`/quiz/${id}`, { method: "DELETE" });
      if (r.code === 0) {
        if (quizId.value === id) resetCurrentQuiz();
        await loadHistory();
        showToast("试卷已删除");
      } else {
        message.value = r.message || "删除失败";
      }
    };

    const submit = async () => {
      if (!quizId.value) return;
      const r = await api("/quiz/submit", {
        method: "POST",
        body: JSON.stringify({ quiz_id: quizId.value, answers: answers.value }),
      });
      if (r.code === 0) {
        result.value = r.data;
        showToast("试卷已提交");
        await loadHistory();
      } else {
        message.value = r.message || "提交失败";
      }
    };

    onMounted(loadHistory);

    return {
      form,
      questions,
      answers,
      result,
      history,
      generate,
      submit,
      loadQuizDetail,
      removeQuiz,
      askAI,
      explanationText,
      loading,
      message,
    };
  },
  template: `
    <div class="page">
      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">AI 出题</p>
            <h2>按知识点快速生成练习题</h2>
          </div>
        </div>
        <div class="form-grid three-col">
          <input v-model="form.subject" placeholder="学科" />
          <input v-model="form.topic" placeholder="知识点" />
          <input type="number" min="1" max="20" v-model.number="form.count" placeholder="题目数量" />
        </div>
        <div class="actions">
          <button @click="generate" :disabled="loading">{{ loading ? "生成中..." : "生成题目" }}</button>
          <span class="muted">{{ message }}</span>
        </div>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">历史试卷</p>
            <h2>最近 10 次生成记录</h2>
          </div>
        </div>
        <div v-if="!history.length" class="empty-state">还没有历史试卷。</div>
        <div class="stack-list compact-list">
          <article v-for="item in history" :key="item.id" class="content-card compact-card">
            <div class="content-head">
              <div>
                <span class="pill">{{ item.subject }}</span>
                <span class="muted">{{ item.topic }} · {{ item.created_at }}</span>
              </div>
              <div class="actions">
                <button class="ghost small" @click="loadQuizDetail(item.id)">查看试卷</button>
                <button class="ghost small danger" @click="removeQuiz(item.id)">删除试卷</button>
              </div>
            </div>
            <div class="history-meta">
              <span>{{ item.question_count }} 题</span>
              <span>{{ item.completed ? "得分 " + item.score : "未提交" }}</span>
              <span>{{ item.completed ? "正确率 " + Math.round((item.correct_rate || 0) * 100) + "%" : "待作答" }}</span>
            </div>
          </article>
        </div>
      </section>

      <section class="card panel-card" v-if="questions.length">
        <div class="section-head">
          <div>
            <p class="eyebrow">做题区</p>
            <h2>共 {{ questions.length }} 题</h2>
          </div>
          <button @click="submit">提交答案</button>
        </div>
        <div class="stack-list">
          <article v-for="(q, i) in questions" :key="i" class="content-card">
            <h3>{{ i + 1 }}. {{ q.question }}</h3>
            <label v-for="(op, j) in q.options" :key="j" class="option-row">
              <input type="radio" :name="'q' + i" :value="op.trim()[0]" v-model="answers[i]" :disabled="!!result" />
              <span>{{ op }}</span>
            </label>
            <div v-if="result" class="analysis-inline">
              <span class="pill neutral">参考答案 {{ q.answer }}</span>
              <div class="explain-card">
                <strong>题目讲解</strong>
                <p>{{ explanationText(q) }}</p>
              </div>
              <div class="actions">
                <button class="ghost small" @click="askAI(q)">AI 追问</button>
              </div>
            </div>
          </article>
        </div>
        <div v-if="result" class="result-card">
          <strong>得分 {{ result.score }}</strong>
          <span>正确率 {{ Math.round(result.correct_rate * 100) }}%</span>
          <span>已加入错题本 {{ result.wrong_added }} 题</span>
        </div>
      </section>
    </div>
  `,
};
