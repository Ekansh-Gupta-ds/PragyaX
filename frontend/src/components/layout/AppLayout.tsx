import { useEffect, useState, type ReactNode } from "react";
import type { User } from "../../types/api";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

interface AppLayoutProps {
  readonly user: User;
  readonly active: string;
  readonly aiIsMock: boolean;
  readonly onLogout: () => void;
  readonly children: ReactNode;
}

export function AppLayout({
  user,
  active,
  aiIsMock,
  onLogout,
  children,
}: AppLayoutProps) {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  // Close mobile drawer on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isMobileMenuOpen) {
        setIsMobileMenuOpen(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMobileMenuOpen]);

  // Lock body scroll when mobile drawer is open
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [isMobileMenuOpen]);

  return (
    <div className="shell">
      <Topbar
        user={user}
        isOpen={isMobileMenuOpen}
        onToggle={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
      />

      <Sidebar
        user={user}
        activeRoute={active}
        aiIsMock={aiIsMock}
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
        onLogout={onLogout}
      />

      {isMobileMenuOpen && (
        <div
          className="scrim"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      <main className="content" id="main-content" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}

export default AppLayout;
