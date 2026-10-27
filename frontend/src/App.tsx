import { useEffect, useState, type ReactNode } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "./api/client";
import type { User } from "./types/api";
import type { RoutePath } from "./types/routes";
import { AppLayout } from "./components/layout";
import { LoadingState } from "./components/ui";
import { navigate, useAppRouter } from "./routes/router";
import AuthPage from "./pages/AuthPage";
import DashboardPage from "./pages/DashboardPage";
import ChatPage from "./pages/ChatPage";
import SubjectsPage from "./pages/SubjectsPage";
import AssessmentPage from "./pages/AssessmentPage";
import ResultPage from "./pages/ResultPage";
import HistoryPage from "./pages/HistoryPage";
import ChallengePage from "./pages/ChallengePage";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(!!tokenStore.get());
  const [aiIsMock, setAiIsMock] = useState(true);
  const { route, param } = useAppRouter();

  useEffect(() => {
    setUnauthorizedHandler(() => {
      tokenStore.clear();
      setUser(null);
    });

    api
      .health()
      .then((h) => setAiIsMock(h.ai_is_mock))
      .catch(() => {});

    if (tokenStore.get()) {
      api
        .me()
        .then(setUser)
        .catch(() => tokenStore.clear())
        .finally(() => setChecking(false));
    }
  }, []);

  const onAuth = (u: User, token: string, isNew: boolean) => {
    tokenStore.set(token);
    setUser(u);
    // Guided flow: new learners start in chat, returning learners land on dashboard
    navigate(isNew ? "chat" : "dashboard");
  };

  const onLogout = async () => {
    await api.logout().catch(() => {});
    tokenStore.clear();
    setUser(null);
  };

  if (checking) {
    return <LoadingState label="Restoring your session…" fullPage />;
  }

  if (!user) {
    return <AuthPage onAuth={onAuth} />;
  }

  const renderCurrentPage = (currentRoute: RoutePath): ReactNode => {
    switch (currentRoute) {
      case "dashboard":
        return <DashboardPage />;
      case "chat":
        return <ChatPage />;
      case "subjects":
        return <SubjectsPage />;
      case "assessment":
        return <AssessmentPage />;
      case "results":
        return <HistoryPage />;
      case "result":
        return <ResultPage id={param ?? ""} />;
      case "challenge":
        return <ChallengePage />;
      default:
        return <DashboardPage />;
    }
  };

  return (
    <AppLayout
      user={user}
      active={route}
      aiIsMock={aiIsMock}
      onLogout={onLogout}
    >
      {renderCurrentPage(route)}
    </AppLayout>
  );
}
