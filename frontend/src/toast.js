import { reactive } from "vue";

let seed = 1;

export const toastState = reactive({
  items: [],
});

export function showToast(message, type = "success", duration = 2600) {
  if (!message) return;
  const id = seed++;
  toastState.items.push({ id, message, type });
  window.setTimeout(() => {
    const index = toastState.items.findIndex((item) => item.id === id);
    if (index >= 0) toastState.items.splice(index, 1);
  }, duration);
}
