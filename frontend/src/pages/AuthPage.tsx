import { useRef, useState, type FormEvent } from "react";
import {
  ArrowDown,
  Award,
  Bot,
  BrainCircuit,
  Compass,
  FileCode2,
  GraduationCap,
  Lock,
  Sparkles,
  Target,
  Trophy,
  Zap,
} from "lucide-react";
import { api } from "../api/client";
import type { User } from "../api/types";
import { Alert } from "../components/ui/Alert";
import { Button } from "../components/ui/Button";
import { HeroArtwork } from "../components/ui/HeroArtwork";

const EMAIL_RE = /^[\w.+-]+@[\w-]+(\.[\w-]+)+$/;

export default function AuthPage({
  onAuth,
}: {
  readonly onAuth: (u: User, token: string, isNew: boolean) => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("register");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const accountRef = useRef<HTMLDivElement>(null);
  const journeyRef = useRef<HTMLElement>(null);
  const philosophyRef = useRef<HTMLElement>(null);
  const nameInputRef = useRef<HTMLInputElement>(null);
  const emailInputRef = useRef<HTMLInputElement>(null);

  const validate = () => {
    if (mode === "register" && name.trim().length < 2) {
      return "Please enter your full name (at least 2 characters).";
    }
    if (!EMAIL_RE.test(email.trim())) {
      return "Please enter a valid academic or personal email address.";
    }
    if (mode === "register" && password.length < 6) {
      return "Password must be at least 6 characters.";
    }
    if (!password) {
      return "Please enter your password.";
    }
    return null;
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const problem = validate();
    if (problem) return setError(problem);
    setBusy(true);
    setError(null);
    try {
      const res =
        mode === "register"
          ? await api.register(name.trim(), email.trim(), password)
          : await api.login(email.trim(), password);
      onAuth(res.user, res.token, mode === "register");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const switchMode = (m: "login" | "register") => {
    setMode(m);
    setError(null);
    setTimeout(() => {
      if (m === "register") {
        nameInputRef.current?.focus();
      } else {
        emailInputRef.current?.focus();
      }
    }, 50);
  };

  const focusAuth = (preferredMode: "login" | "register" = "register") => {
    switchMode(preferredMode);
    accountRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const scrollToPhilosophy = () => {
    philosophyRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const scrollToJourney = () => {
    journeyRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div className="landing-shell">
      {/* Subtle Architectural Grid Lines Overlay */}
      <div className="grid-lines-bg" aria-hidden="true" />

      {/* Top Editorial Navigation */}
      <header className="landing-nav">
        <a href="#/" className="brand">
          <GraduationCap size={26} aria-hidden /> Pragya<span className="brand-x">X</span>
        </a>

        <nav className="landing-nav-links" aria-label="Landing Navigation">
          <a href="#philosophy" onClick={(e) => { e.preventDefault(); scrollToPhilosophy(); }}>
            Philosophy
          </a>
          <a href="#journey" onClick={(e) => { e.preventDefault(); scrollToJourney(); }}>
            Journey
          </a>
          <a href="#capabilities">Capabilities</a>
          <button
            type="button"
            className="nav-text-btn"
            onClick={() => focusAuth("login")}
          >
            Sign in
          </button>
        </nav>

        <div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => focusAuth("register")}
          >
            Create Account
          </Button>
        </div>
      </header>

      {/* Hero Section — Prominent Artwork & Upper-Viewport Authentication */}
      <section className="hero-section" id="hero">
        <div className="hero-text-block">
          <div className="eyebrow">AI-POWERED GAMIFIED LEARNING</div>

          <h1 className="hero-headline">
            Learn by doing. <br />
            Grow by <em>proving.</em>
          </h1>

          <p className="hero-lead">
            Turn theoretical knowledge into real skills with personalized learning,
            adaptive assessments, and verifiable skill scorecards.
          </p>

          {/* Authentication Card Positioned Directly in Upper Viewport */}
          <div className="auth-card hero-auth-card" ref={accountRef} id="account">
            <div className="tabs" role="tablist" aria-label="Account Mode">
              <button
                type="button"
                role="tab"
                aria-selected={mode === "register"}
                className={mode === "register" ? "tab active" : "tab"}
                onClick={() => switchMode("register")}
              >
                Create account
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={mode === "login"}
                className={mode === "login" ? "tab active" : "tab"}
                onClick={() => switchMode("login")}
              >
                Log in
              </button>
            </div>

            <form onSubmit={submit} noValidate>
              {mode === "register" && (
                <label className="field">
                  <span>Full name</span>
                  <input
                    ref={nameInputRef}
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    autoComplete="name"
                    placeholder="e.g. Asha Sharma"
                  />
                </label>
              )}

              <label className="field">
                <span>Email address</span>
                <input
                  ref={emailInputRef}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  placeholder="you@college.edu"
                />
              </label>

              <label className="field">
                <span>Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  placeholder={mode === "register" ? "At least 6 characters" : "Your password"}
                />
              </label>

              {error && <Alert variant="error" message={error} />}

              <Button
                type="submit"
                variant="primary"
                block
                disabled={busy}
                loading={busy}
              >
                {mode === "register" ? "Create Account & Start Learning" : "Log In to Your Account"}
              </Button>
            </form>

            <div className="auth-card-footer">
              <span className="fine">
                <Lock size={12} aria-hidden /> Session restored automatically
              </span>
              <button
                type="button"
                className="scroll-peek-link"
                onClick={scrollToJourney}
              >
                Explore method & curriculum <ArrowDown size={13} aria-hidden />
              </button>
            </div>
          </div>
        </div>

        {/* Sculptural Knowledge Metaphor Artwork Column */}
        <div className="hero-artwork-column">
          <HeroArtwork />

          {/* Core Foundation Highlights Aligned Below Artwork */}
          <div className="hero-meta-points">
            <div className="hero-meta-item">
              <strong>01 / Assess</strong>
              <span>5-Question Diagnostics</span>
            </div>
            <div className="hero-meta-item">
              <strong>02 / Tutor</strong>
              <span>Interactive AI Chat</span>
            </div>
            <div className="hero-meta-item">
              <strong>03 / Master</strong>
              <span>Verified Skill Scorecards</span>
            </div>
          </div>
        </div>
      </section>

      {/* Section A: Learning Philosophy */}
      <section id="philosophy" ref={philosophyRef} className="editorial-section">
        <div className="section-header">
          <div className="eyebrow">THE PRAGYAX METHOD</div>
          <h2>Moving beyond passive memorization into verifiable ability.</h2>
          <p className="muted">
            College learning shouldn't stop at reading textbooks. PragyaX combines
            interactive dialogue, objective testing, and real coding practice.
          </p>
        </div>

        <div className="philosophy-grid">
          <article className="philosophy-card">
            <span className="philosophy-num">PHASE // 01</span>
            <div className="capability-icon">
              <Compass size={22} aria-hidden />
            </div>
            <h3 className="philosophy-title">DISCOVER</h3>
            <p className="philosophy-desc">
              Understand what you already know. Uncover your precise baseline and
              knowledge boundaries with rapid diagnostic challenges.
            </p>
          </article>

          <article className="philosophy-card">
            <span className="philosophy-num">PHASE // 02</span>
            <div className="capability-icon">
              <Sparkles size={22} aria-hidden />
            </div>
            <h3 className="philosophy-title">PRACTICE</h3>
            <p className="philosophy-desc">
              Build knowledge through conversational AI tutoring, contextual follow-ups,
              and bite-sized daily code breaker puzzles.
            </p>
          </article>

          <article className="philosophy-card">
            <span className="philosophy-num">PHASE // 03</span>
            <div className="capability-icon">
              <Trophy size={22} aria-hidden />
            </div>
            <h3 className="philosophy-title">PROVE</h3>
            <p className="philosophy-desc">
              Demonstrate genuine progress. Server-evaluated assessments award verified
              proficiency ratings, points, and unlockable achievement badges.
            </p>
          </article>
        </div>
      </section>

      {/* Section B: The Learning Journey */}
      <section id="journey" ref={journeyRef} className="editorial-section">
        <div className="section-header">
          <div className="eyebrow">STEP-BY-STEP PROGRESSION</div>
          <h2>The Journey: From theory to practical skill.</h2>
          <p className="muted">
            Each learning cycle takes you from concept exploration to objective evaluation.
          </p>
        </div>

        <div className="journey-sequence">
          <div className="journey-step active">
            <span className="journey-step-badge">1</span>
            <h3>Subject Selection</h3>
            <p>
              Choose from specialized curriculum tracks. Start with Python Programming
              foundation concepts.
            </p>
          </div>

          <div className="journey-step">
            <span className="journey-step-badge">2</span>
            <h3>Server Assessment</h3>
            <p>
              Complete a focused 5-question evaluation graded by server-side logic
              with real-time feedback.
            </p>
          </div>

          <div className="journey-step">
            <span className="journey-step-badge">3</span>
            <h3>Personalized Chat</h3>
            <p>
              Deep-dive into weak areas. Ask the learning assistant questions with
              curated follow-up prompts.
            </p>
          </div>

          <div className="journey-step">
            <span className="journey-step-badge">4</span>
            <h3>Skill Progress</h3>
            <p>
              Review your score percentage, unlock achievements, and climb from
              Beginner to Advanced mastery.
            </p>
          </div>
        </div>
      </section>

      {/* Section C: Product Capabilities */}
      <section id="capabilities" className="editorial-section">
        <div className="section-header">
          <div className="eyebrow">PLATFORM CAPABILITIES</div>
          <h2>Everything you need to master practical skills.</h2>
        </div>

        <div className="capabilities-grid">
          <div className="capability-card">
            <div className="capability-icon">
              <Target size={20} aria-hidden />
            </div>
            <h3>Adaptive Assessments</h3>
            <p>
              Server-evaluated assessments test core conceptual mechanics including
              Python scope (LEGB), mutability, and list comprehensions.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <Bot size={20} aria-hidden />
            </div>
            <h3>AI Learning Assistant</h3>
            <p>
              Trained learning chat with safe Markdown code rendering, intelligent
              suggested follow-ups, and session persistence.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <BrainCircuit size={20} aria-hidden />
            </div>
            <h3>Diagnostic Roadmaps</h3>
            <p>
              Targeted topic recommendations derived dynamically from the questions
              you missed during assessments.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <Zap size={20} aria-hidden />
            </div>
            <h3>Daily Code Breaker</h3>
            <p>
              Solve a daily bite-sized code snippet puzzle to earn instant bonus
              points and the Daily Code Breaker badge.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <Award size={20} aria-hidden />
            </div>
            <h3>Verifiable Badges</h3>
            <p>
              Earn tangible digital badges as you hit learning milestones, complete
              assessments, and maintain study momentum.
            </p>
          </div>

          <div className="capability-card">
            <div className="capability-icon">
              <FileCode2 size={20} aria-hidden />
            </div>
            <h3>Offline Deterministic Mode</h3>
            <p>
              Runs fully offline with file-backed SQLite persistence and deterministic
              mock AI providers for zero setup friction.
            </p>
          </div>
        </div>
      </section>

      {/* Section D: Bottom Closing Section with Quick Action to Return to Form */}
      <section className="landing-closing-banner">
        <div className="closing-banner-inner">
          <div className="eyebrow">READY TO PROVE YOUR SKILLS?</div>
          <h2>Begin your learning journey today.</h2>
          <p className="muted">
            Free diagnostic evaluation, real-time AI tutor dialogues, and verified badges.
          </p>
          <div style={{ marginTop: 20 }}>
            <Button
              variant="primary"
              size="lg"
              onClick={() => focusAuth("register")}
            >
              Start Learning Now
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}
