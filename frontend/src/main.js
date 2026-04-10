import { createApp } from "vue";
import App from "./App.js";
import router from "./router.js";
import { initAuthSync } from "./auth.js";
import "../styles.css";

initAuthSync();

createApp(App).use(router).mount("#app");
