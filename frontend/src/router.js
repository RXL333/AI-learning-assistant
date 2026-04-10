import { createRouter, createWebHashHistory } from "vue-router";
import { authState, restoreAuthSession, savePostLoginRedirect } from "./auth.js";
import LoginPage from "./pages/LoginPage.js";
import RegisterPage from "./pages/RegisterPage.js";
import DashboardPage from "./pages/DashboardPage.js";
import ChatPage from "./pages/ChatPage.js";
import WrongBookPage from "./pages/WrongBookPage.js";
import QuizPage from "./pages/QuizPage.js";
import ReviewPage from "./pages/ReviewPage.js";
import HistoryPage from "./pages/HistoryPage.js";
import MindMapPage from "./pages/MindMapPage.js";
import ProfilePage from "./pages/ProfilePage.js";

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: "/", redirect: "/dashboard" },
    { path: "/login", component: LoginPage, meta: { public: true } },
    { path: "/register", component: RegisterPage, meta: { public: true } },
    { path: "/dashboard", component: DashboardPage },
    { path: "/chat", component: ChatPage },
    { path: "/wrong-book", component: WrongBookPage },
    { path: "/quiz", component: QuizPage },
    { path: "/review", component: ReviewPage },
    { path: "/today-review", redirect: "/review" },
    { path: "/history", component: HistoryPage },
    { path: "/mindmap", component: MindMapPage },
    { path: "/profile", component: ProfilePage },
  ],
});

router.beforeEach((to) => {
  restoreAuthSession();
  if (to.meta.public) return true;
  if (!authState.token) {
    savePostLoginRedirect(to.fullPath);
    return "/login";
  }
  return true;
});

export default router;
