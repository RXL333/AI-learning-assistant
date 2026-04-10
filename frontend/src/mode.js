import { computed, reactive } from "vue";

const MODE_KEY = "ai_mode_key";

const DEFAULT_MODES = [
  { mode_key: "general", mode_name: "通用模式", description: "适合综合性、跨学科或暂时还没明确范围的问题。" },
  { mode_key: "computer", mode_name: "计算机模式", description: "偏代码、算法、调试和工程实践。" },
  { mode_key: "english", mode_name: "英语模式", description: "偏翻译、语法、表达和纠错。" },
  { mode_key: "math", mode_name: "数学模式", description: "偏推导、公式、证明和例题。" },
  { mode_key: "encourage", mode_name: "鼓励模式", description: "偏陪伴、安抚和低压力的下一步建议。" },
];

function readModeKey() {
  return localStorage.getItem(MODE_KEY) || "general";
}

export const modeState = reactive({
  modes: DEFAULT_MODES,
  selectedModeKey: readModeKey(),
});

export const selectedMode = computed(() => modeState.modes.find((item) => item.mode_key === modeState.selectedModeKey) || null);

export function setModes(modes) {
  modeState.modes = Array.isArray(modes) && modes.length ? modes : DEFAULT_MODES;
}

export function setSelectedModeKey(modeKey) {
  const nextKey = modeKey || "general";
  modeState.selectedModeKey = nextKey;
  localStorage.setItem(MODE_KEY, nextKey);
}

export function ensureSelectedMode() {
  if (!modeState.selectedModeKey) {
    setSelectedModeKey("general");
  }
}
