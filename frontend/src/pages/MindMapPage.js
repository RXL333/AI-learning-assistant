import { onMounted, ref } from "vue";
import { api } from "../api.js";
import { modeState } from "../mode.js";
import { showToast } from "../toast.js";

export default {
  name: "MindMapPage",
  setup() {
    const recordId = ref(null);
    const topic = ref("操作系统");
    const textTree = ref("");
    const nodes = ref([]);
    const loading = ref(false);
    const saving = ref(false);
    const message = ref("");
    const saveMessage = ref("");

    const applyRecord = (data, tips = "") => {
      if (!data) return;
      recordId.value = data.id || null;
      topic.value = data.topic || topic.value;
      textTree.value = data.text_tree || "";
      nodes.value = data.nodes || [];
      saveMessage.value = tips || (data.updated_at ? `宸蹭繚瀛樹簬 ${data.updated_at}` : "");
    };

    const loadLatest = async () => {
      const r = await api("/mindmap/latest");
      if (r.code === 0 && r.data) {
        applyRecord(r.data, `已加载上次保存内容，更新时间 ${r.data.updated_at}`);
      }
    };

    const copyTextTree = async () => {
      if (!textTree.value) return;
      await navigator.clipboard.writeText(textTree.value);
      showToast("思维导图已复制到剪贴板");
    };

    const save = async () => {
      if (!topic.value.trim() || !textTree.value.trim() || saving.value) return;
      saving.value = true;
      saveMessage.value = "";
      const r = await api("/mindmap/save", {
        method: "PUT",
        body: JSON.stringify({
          id: recordId.value,
          topic: topic.value.trim(),
          text_tree: textTree.value,
          nodes: nodes.value,
          mode_key: modeState.selectedModeKey || "general",
        }),
      });
      if (r.code === 0) {
        applyRecord(r.data, `已保存，更新时间 ${r.data.updated_at}`);
        showToast("思维导图已保存");
      } else {
        saveMessage.value = r.message || "保存失败";
      }
      saving.value = false;
    };

    const generate = async () => {
      if (!topic.value.trim() || loading.value) return;
      loading.value = true;
      message.value = "";
      const r = await api("/mindmap", { method: "POST", body: JSON.stringify({ topic: topic.value.trim(), mode_key: modeState.selectedModeKey || "general" }) });
      if (r.code === 0) {
        applyRecord(r.data, `已自动保存，更新时间 ${r.data.updated_at}`);
        showToast("鎬濈淮瀵煎浘宸茬敓鎴愬苟淇濆瓨");
        if (!textTree.value) {
          message.value = "已生成结构数据，但没有可显示的文本导图。";
        }
      } else {
        message.value = r.message || "生成失败";
      }
      loading.value = false;
    };

    onMounted(loadLatest);

    return { recordId, topic, textTree, nodes, generate, copyTextTree, loadLatest, save, loading, saving, message, saveMessage };
  },
  template: `
    <div class="page">
      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">思维导图</p>
            <h2>优先展示文本箭头版导图</h2>
          </div>
          <div class="actions">
            <button class="ghost" @click="loadLatest">读取上次保存</button>
            <button class="ghost" @click="save" :disabled="saving || !textTree">{{ saving ? '保存中...' : '保存当前导图' }}</button>
          </div>
        </div>
        <div class="form-row">
          <input v-model="topic" placeholder="输入主题，例如：数据库事务" />
          <button @click="generate" :disabled="loading">{{ loading ? '生成中...' : '生成导图' }}</button>
        </div>
        <p class="muted">如果图形导图暂时不可用，这里会直接输出文本结构，便于立即使用。</p>
        <p class="muted">{{ message || saveMessage }}</p>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">文本导图</p>
            <h2>现在支持编辑后保存</h2>
          </div>
          <button class="ghost" @click="copyTextTree" :disabled="!textTree">复制文本导图</button>
        </div>
        <textarea class="mindmap-editor" rows="18" v-model="textTree" placeholder="生成后会在这里显示文本导图，也可以直接修改后保存"></textarea>
      </section>

      <section class="card panel-card">
        <div class="section-head">
          <div>
            <p class="eyebrow">原始结构</p>
            <h2>便于后续继续扩展成图片导图</h2>
          </div>
          <span class="muted">记录 ID：{{ recordId || '-' }}</span>
        </div>
        <pre class="json">{{ JSON.stringify(nodes, null, 2) }}</pre>
      </section>
    </div>
  `,
};

