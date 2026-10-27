import { GraduationCap, Menu, X } from "lucide-react";
import type { User } from "../../types/api";

interface TopbarProps {
  readonly user: User;
  readonly isOpen: boolean;
  readonly onToggle: () => void;
}

export function Topbar({ user, isOpen, onToggle }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <button
          type="button"
          className="icon-btn"
          onClick={onToggle}
          aria-label={isOpen ? "Close navigation menu" : "Open navigation menu"}
          aria-expanded={isOpen}
        >
          {isOpen ? <X size={20} /> : <Menu size={20} />}
        </button>

        <a href="#/dashboard" className="brand">
          <GraduationCap size={22} aria-hidden /> Pragya<span className="brand-x">X</span>
        </a>
      </div>

      <div
        className="avatar"
        style={{ width: 30, height: 30, fontSize: "0.8rem" }}
        title={`${user.name} (${user.email})`}
        aria-hidden
      >
        {user.name.charAt(0).toUpperCase()}
      </div>
    </header>
  );
}

export default Topbar;
