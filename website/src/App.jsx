import React, { useEffect, useRef, useState } from "react";
import {
  Waveform,
  Play,
  Pause,
  ArrowRight,
  ArrowUpRight,
  X,
  List,
  Check,
  DownloadSimple,
  Headphones,
  Microphone,
  MusicNotes,
  Sparkle,
  SignOut,
  CaretDown,
} from "@phosphor-icons/react";
import WaveSurfer from "wavesurfer.js";
import "@fontsource/anton/400.css";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";

const DEMOS = [
  {
    title: "Podcast intro",
    type: "INTRO MUSIC",
    file: "/assets/intro-demo.wav",
    duration: "0:12",
    description: "A bright, rhythmic opening cue.",
  },
  {
    title: "Episode transition",
    type: "TRANSITION",
    file: "/assets/transition-demo.wav",
    duration: "0:03",
    description: "A short musical change of scene.",
  },
  {
    title: "Under the story",
    type: "MUSIC BED",
    file: "/assets/bed-demo.wav",
    duration: "0:16",
    description: "A restrained bed for your narrative.",
  },
];
const PLAN_DETAILS = [
  {
    id: "creator",
    name: "Creator",
    for: "FOR YOUR NEXT BIG IDEA",
    image: "/assets/creator-headphones.png",
    copy: "Find a signature sound for your podcast, videos or personal brand.",
    features: [
      "Voiceovers, music & effects",
      "Editable scripts and prompts",
      "Audio playback & downloads",
    ],
  },
  {
    id: "studio",
    name: "Studio",
    for: "FOR PODCASTS & CHANNELS",
    image: "/assets/creator-hero.png",
    copy: "Bring a consistent sonic identity to the content you make every week.",
    features: [
      "Everything in Creator",
      "A plan for regular production",
      "More room to create",
    ],
  },
  {
    id: "team",
    name: "Team",
    for: "FOR CREATIVE TEAMS",
    image: "/assets/creator-team.png",
    copy: "A future home for creators producing across multiple shows and brands.",
    features: [
      "A plan for larger workloads",
      "Subscription self-service",
      "Team features planned",
    ],
  },
];

function Player({ demo, compact = false }) {
  const container = useRef(null),
    instance = useRef(null);
  const [playing, setPlaying] = useState(false),
    [ready, setReady] = useState(false),
    [elapsed, setElapsed] = useState("0:00");
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    setReady(false);
    setFailed(false);
    setPlaying(false);
    const ws = WaveSurfer.create({
      container: container.current,
      url: demo.file,
      waveColor: "#6c7271",
      progressColor: "#c9fb62",
      cursorWidth: 0,
      height: compact ? 38 : 44,
      barWidth: 2,
      barGap: 2,
      barRadius: 1,
      normalize: true,
      interact: true,
    });
    instance.current = ws;
    ws.on("ready", () => setReady(true));
    const pauseOthers = (event) => {
      if (event.detail !== ws) ws.pause();
    };
    window.addEventListener("studio-audio-play", pauseOthers);
    ws.on("play", () => {
      setPlaying(true);
      window.dispatchEvent(
        new CustomEvent("studio-audio-play", { detail: ws }),
      );
    });
    ws.on("pause", () => setPlaying(false));
    ws.on("finish", () => {
      setPlaying(false);
      ws.setTime(0);
    });
    ws.on("timeupdate", (t) =>
      setElapsed(
        `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, "0")}`,
      ),
    );
    ws.on("error", () => setFailed(true));
    return () => {
      window.removeEventListener("studio-audio-play", pauseOthers);
      ws.destroy();
      instance.current = null;
    };
  }, [demo.file, compact]);
  return (
    <div className={`audio-player ${compact ? "compact" : ""}`}>
      <button
        className="play-button"
        aria-label={`${playing ? "Pause" : "Play"} ${demo.title}`}
        disabled={!ready || failed}
        onClick={() => instance.current?.playPause()}
      >
        {playing ? (
          <Pause weight="fill" size={23} />
        ) : (
          <Play weight="fill" size={23} />
        )}
      </button>
      <div className="player-title">
        {demo.title}
        <span> • Demo</span>
      </div>
      <div className="wave" ref={container} />
      <span className="player-time">
        {failed ? "Unavailable" : `${elapsed} / ${demo.duration}`}
      </span>
    </div>
  );
}

function Dialog({ title, children, onClose, wide = false }) {
  const ref = useRef(null);
  useEffect(() => {
    const dialog = ref.current;
    dialog.showModal();
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`dialog ${wide ? "wide" : ""}`}
      onCancel={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
    >
      <div className="dialog-heading">
        <h2>{title}</h2>
        <button
          className="icon-button"
          aria-label="Close dialog"
          onClick={onClose}
        >
          <X size={24} />
        </button>
      </div>
      {children}
    </dialog>
  );
}

export function App() {
  const [config, setConfig] = useState({ models: [], plans: [], user: null }),
    [csrf, setCsrf] = useState("");
  const [modal, setModal] = useState(null),
    [menu, setMenu] = useState(false),
    [authMode, setAuthMode] = useState("signin");
  const [authEmail, setAuthEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  const [task, setTask] = useState("Speech"),
    [modelId, setModelId] = useState(""),
    [voice, setVoice] = useState("coral");
  const [scripts, setScripts] = useState({
    Speech:
      "Welcome to the next chapter. Fresh ideas, honest conversations, and stories worth your time. Let’s get into it.",
    Music:
      "A warm, minimal electronic bed for a thoughtful podcast. Soft keys and a gentle pulse. No vocals.",
    "Sound effects":
      "A short, shimmering transition that rises gently and resolves softly.",
  });
  const script = scripts[task];
  const setScript = (value) =>
    setScripts((previous) => ({ ...previous, [task]: value }));
  const [style, setStyle] = useState("Warm, confident and conversational."),
    [seconds, setSeconds] = useState(10),
    [instrumental, setInstrumental] = useState(true);
  const [result, setResult] = useState(null),
    [selectedPlan, setSelectedPlan] = useState("creator");
  const models = config.models.filter((m) => m.task === task);
  const model = models.find((m) => m.model === modelId) || models[0];
  const user = config.user;
  async function refresh() {
    try {
      const response = await fetch("/api/bootstrap", {
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error();
      const data = await response.json();
      setConfig(data);
      setCsrf(data.csrf);
    } catch {
      setMessage(
        "The studio connection is unavailable. You can still listen to the examples.",
      );
    }
  }
  useEffect(() => {
    refresh();
    if (
      new URLSearchParams(window.location.search).get("checkout") === "returned"
    ) {
      setModal("studio");
      setMessage(
        "Your checkout has returned. Access appears after payment is confirmed securely.",
      );
    }
  }, []);
  useEffect(() => {
    if (model) {
      setModelId(model.model);
      setVoice(
        model.voices?.includes("coral") ? "coral" : model.voices?.[0] || "",
      );
    }
  }, [task, model?.model]);
  useEffect(
    () => () => {
      if (result) URL.revokeObjectURL(result.url);
    },
    [result],
  );
  async function api(path, data = {}) {
    const response = await fetch(`/api/${path}`, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf },
      body: JSON.stringify(data),
    });
    if (!response.ok) {
      let text = "This request could not be completed. Please try again.";
      try {
        const body = await response.json();
        if (body.error) text = body.error;
      } catch {}
      throw new Error(text);
    }
    return response;
  }
  function open(next) {
    window.dispatchEvent(
      new CustomEvent("studio-audio-play", { detail: null }),
    );
    setMenu(false);
    setMessage("");
    setModal(next);
  }
  function moveTo(id) {
    setMenu(false);
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  }
  async function authenticate(event) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const response = await api(authMode, { email: authEmail, password });
      const data = await response.json();
      setCsrf(data.csrf);
      setConfig((c) => ({ ...c, user: data.user }));
      setPassword("");
      setModal("studio");
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function logout() {
    try {
      const response = await api("signout");
      const data = await response.json();
      setCsrf(data.csrf);
      setConfig((c) => ({ ...c, user: null }));
      setResult(null);
      setScripts({ Speech: "", Music: "", "Sound effects": "" });
      setStyle("");
      setAuthEmail("");
      setModal(null);
    } catch (error) {
      setMessage(error.message);
    }
  }
  async function checkout(plan) {
    setSelectedPlan(plan);
    setMessage("");
    if (!user) {
      setAuthMode("signup");
      setModal("auth");
      return;
    }
    if (!config.plans.find((p) => p.id === plan)?.enabled) {
      setModal("plan");
      return;
    }
    setBusy(true);
    try {
      const response = await api("checkout", {
        plan,
        requestId: crypto.randomUUID(),
      });
      const data = await response.json();
      const url = new URL(data.url);
      if (url.origin !== "https://checkout.stripe.com")
        throw new Error("Invalid checkout destination.");
      window.location.assign(url.href);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function manageBilling() {
    setBusy(true);
    setMessage("");
    try {
      const response = await api("portal");
      const data = await response.json();
      const url = new URL(data.url);
      if (url.origin !== "https://billing.stripe.com")
        throw new Error("Invalid billing destination.");
      window.location.assign(url.href);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function produce(event) {
    event.preventDefault();
    setMessage("");
    if (!user) {
      setAuthMode("signup");
      setModal("auth");
      return;
    }
    if (!user.active) {
      setSelectedPlan("creator");
      setModal("plan");
      return;
    }
    if (!model) {
      setMessage(
        "This audio type is not enabled yet. Try a voiceover or listen to the demos.",
      );
      return;
    }
    setBusy(true);
    try {
      const response = await api("audio", {
        model: model.model,
        text: script,
        voice,
        style: model.style ? style : "",
        seconds: Number(seconds),
        instrumental: model.instrumental ? instrumental : false,
        requestId: crypto.randomUUID(),
      });
      const blob = await response.blob();
      setResult({
        url: URL.createObjectURL(blob),
        ext: blob.type.includes("wav") ? "wav" : "mp3",
      });
      await refresh();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="site-header shell">
        <a className="brand" href="#" aria-label="Creator Imaging Studio home">
          <Waveform size={49} weight="bold" />
          <span>
            Creator Imaging Studio<small>AUDIO FOR PODCASTERS & CREATORS</small>
          </span>
        </a>
        <nav aria-label="Main navigation" className={menu ? "open" : ""}>
          <a href="#examples" onClick={() => setMenu(false)}>
            Examples
          </a>
          <a href="#how-it-works" onClick={() => setMenu(false)}>
            How it works
          </a>
          <a href="#plans" onClick={() => setMenu(false)}>
            Plans
          </a>
        </nav>
        <div className="header-actions">
          <button
            className="signin"
            onClick={() => {
              setAuthMode("signin");
              open(user ? "studio" : "auth");
            }}
          >
            {user ? "My studio" : "Sign in"}
          </button>
          <button className="button small lime" onClick={() => open("studio")}>
            Get started <ArrowUpRight size={16} />
          </button>
          <button
            className="icon-button mobile-menu"
            aria-label="Toggle navigation"
            aria-expanded={menu}
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X size={25} /> : <List size={25} />}
          </button>
        </div>
      </header>
      <main>
        <section className="hero" aria-labelledby="hero-title">
          <img
            className="hero-image"
            src="/assets/creator-hero.png"
            alt="A professional podcast microphone above a warmly lit mixing desk"
            fetchPriority="high"
          />
          <div className="hero-content shell">
            <p className="eyebrow hero-eyebrow">
              SOUND LIKE YOURSELF. ONLY BIGGER.
            </p>
            <h1 id="hero-title">
              Your content.
              <br />
              An unmistakable sound.
            </h1>
            <p className="hero-copy">
              Create voiceovers, intros, music beds and sound effects
              <br className="desktop-break" /> for your next episode, video or
              big idea.
            </p>
            <div className="hero-buttons">
              <button
                className="button lime"
                onClick={() => moveTo("examples")}
              >
                <Play weight="fill" size={21} />
                Hear what you can make
              </button>
              <button className="button outline" onClick={() => open("studio")}>
                Explore the studio <ArrowRight size={24} />
              </button>
            </div>
            <Player demo={DEMOS[0]} />
            <p className="demo-note">
              Original synthesized music demo. No account needed to listen.
            </p>
          </div>
          <p className="hero-side-label">
            PODCASTS
            <br />
            YOUTUBE
            <br />
            VOICEOVERS
            <br />
            MUSIC
            <br />
            SOUND EFFECTS
            <br />
            YOUR NEXT IDEA
          </p>
        </section>
        <section
          className="steps shell"
          id="how-it-works"
          aria-label="How it works"
        >
          {[
            [
              "01",
              "Write.",
              "Describe your idea. Write your script. Set the tone.",
            ],
            [
              "02",
              "Produce.",
              "Create the voice, music and little details that make it land.",
            ],
            [
              "03",
              "Make it yours.",
              "Listen, refine and download for your next episode or video.",
            ],
          ].map(([number, title, text]) => (
            <div className="step" key={number}>
              <span>{number}</span>
              <h2>{title}</h2>
              <p>{text}</p>
            </div>
          ))}
        </section>
        <section className="plans shell section" id="plans">
          <div className="section-heading">
            <div>
              <p className="eyebrow">MAKE ROOM TO CREATE</p>
              <h2>A studio that grows with your creativity.</h2>
            </div>
            <p>
              One place for your next signature sound.
              <br />
              Subscription details are being finalized.
            </p>
          </div>
          <div className="plan-grid">
            {PLAN_DETAILS.map((plan) => (
              <article className="plan" key={plan.id}>
                <div className={`plan-image ${plan.id}`}>
                  <img src={plan.image} alt="" loading="lazy" />
                  <h3>{plan.name}</h3>
                  <span>{plan.for}</span>
                </div>
                <p>{plan.copy}</p>
                <ul>
                  {plan.features.map((feature) => (
                    <li key={feature}>
                      <Check size={17} />
                      {feature}
                    </li>
                  ))}
                </ul>
                <div className="plan-price">
                  {config.plans.find((p) => p.id === plan.id)?.enabled
                    ? "View price at checkout"
                    : "Plans in development"}
                </div>
                <button
                  className={`button ${plan.id === "studio" ? "lime" : "outline"}`}
                  onClick={() =>
                    config.plans.find((p) => p.id === plan.id)?.enabled
                      ? checkout(plan.id)
                      : (setSelectedPlan(plan.id), open("plan"))
                  }
                >
                  {config.plans.find((p) => p.id === plan.id)?.enabled
                    ? "Choose " + plan.name
                    : "Explore " + plan.name}
                  <ArrowRight size={21} />
                </button>
              </article>
            ))}
          </div>
          <p className="pricing-note">
            No charges or paid generation until subscriptions are configured.
            Provider and model usage terms apply.
          </p>
        </section>
        <section className="examples shell section" id="examples">
          <div className="section-heading">
            <div>
              <p className="eyebrow">LET YOUR EARS DECIDE</p>
              <h2>Give your ideas an entrance.</h2>
            </div>
            <p>
              A little sonic craft goes a long way.
              <br />
              Start with a few original music cues.
            </p>
          </div>
          <div className="demo-list">
            {DEMOS.map((demo) => (
              <div className="demo-row" key={demo.file}>
                <div>
                  <span className="eyebrow">{demo.type}</span>
                  <p>{demo.description}</p>
                </div>
                <Player compact demo={demo} />
                <a
                  href={demo.file}
                  download
                  aria-label={`Download ${demo.title} demo`}
                  className="icon-button"
                >
                  <DownloadSimple size={22} />
                </a>
              </div>
            ))}
          </div>
        </section>
        <section className="closing shell">
          <p className="eyebrow">THE NEXT GREAT THING YOU MAKE</p>
          <h2>Let it sound like you.</h2>
          <button className="button lime" onClick={() => open("studio")}>
            Step into the studio <ArrowRight size={23} />
          </button>
        </section>
      </main>
      <footer className="shell">
        <a className="brand footer-brand" href="#">
          <Waveform size={34} weight="bold" />
          <span>
            Creator Imaging Studio<small>BUILT FOR THE WAY YOU CREATE.</small>
          </span>
        </a>
        <p>
          Inspired by the craft of radio imaging.
          <br />
          Made for podcasters & content creators.
        </p>
        <button className="text-button" onClick={() => open("about")}>
          About this preview <ArrowUpRight size={16} />
        </button>
      </footer>
      {modal === "auth" && (
        <Dialog
          title={
            authMode === "signup"
              ? "Make yourself at home."
              : "Back to your studio."
          }
          onClose={() => setModal(null)}
        >
          <p className="muted">
            {authMode === "signup"
              ? "Create your account. Subscriptions and paid generation will be available once launch setup is complete."
              : "Sign in to access your studio and subscription."}
          </p>
          <form className="auth-form" onSubmit={authenticate}>
            <label>
              Email
              <input
                type="email"
                value={authEmail}
                onChange={(e) => setAuthEmail(e.target.value)}
                autoComplete="email"
                maxLength={150}
                required
              />
            </label>
            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete={
                  authMode === "signup" ? "new-password" : "current-password"
                }
                minLength={authMode === "signup" ? 12 : 1}
                maxLength={128}
                required
              />
            </label>
            {authMode === "signup" && (
              <p className="field-help">
                At least 12 characters. Use a unique password.
              </p>
            )}
            <Message message={message} />
            <button className="button lime full" disabled={busy}>
              {busy
                ? "Connecting…"
                : authMode === "signup"
                  ? "Create account"
                  : "Sign in"}
              <ArrowRight size={20} />
            </button>
          </form>
          <button
            className="text-button auth-switch"
            onClick={() => {
              setAuthMode(authMode === "signup" ? "signin" : "signup");
              setMessage("");
            }}
          >
            {authMode === "signup"
              ? "Already have an account? Sign in"
              : "New here? Create an account"}
          </button>
        </Dialog>
      )}
      {modal === "studio" && (
        <Dialog
          wide
          title="Your next idea starts here."
          onClose={() => setModal(null)}
        >
          <div className="studio-topline">
            <p className="muted">
              {user
                ? `${user.email} · ${user.active ? `${user.credits} credits` : "No active subscription"}`
                : "Explore the workspace. Sign in when you’re ready to create."}
            </p>
            {user && (
              <div>
                <button
                  className="text-button"
                  onClick={manageBilling}
                  disabled={busy}
                >
                  Manage billing
                </button>
                <button
                  className="icon-button"
                  aria-label="Sign out"
                  onClick={logout}
                >
                  <SignOut size={21} />
                </button>
              </div>
            )}
          </div>
          <div className="studio-tabs" role="tablist" aria-label="Audio type">
            {[
              ["Speech", "Voiceover", Microphone],
              ["Music", "Music bed", MusicNotes],
              ["Sound effects", "Sound effect", Sparkle],
            ].map(([value, label, Icon]) => (
              <button
                role="tab"
                aria-selected={task === value}
                key={value}
                className={task === value ? "active" : ""}
                onClick={() => {
                  setTask(value);
                  setMessage("");
                }}
              >
                <Icon size={19} />
                {label}
              </button>
            ))}
          </div>
          <form className="studio-grid" onSubmit={produce}>
            <div className="studio-main">
              <label>
                {task === "Speech"
                  ? "Your script, in your words"
                  : "Describe the sound"}
                <textarea
                  value={script}
                  onChange={(e) => setScript(e.target.value)}
                  maxLength={model?.maxChars || 4000}
                  rows={7}
                  required
                />
              </label>
              <div className="script-foot">
                <span>
                  {script.length} / {model?.maxChars || 4000}
                </span>
                <button
                  type="button"
                  className="text-button"
                  onClick={() =>
                    setScript(
                      task === "Speech"
                        ? "You’re listening to The Next Chapter. Curious minds, fresh perspectives, and stories that stay with you. Let’s begin."
                        : task === "Music"
                          ? "A warm, minimal electronic music bed for a thoughtful podcast. Soft keys, gentle pulse, no vocals."
                          : "A short, clean shimmering transition, rising gently and resolving softly.",
                    )
                  }
                >
                  <Sparkle size={16} />
                  Try a starter
                </button>
              </div>
              {model?.style && (
                <label>
                  Delivery direction
                  <textarea
                    rows={2}
                    value={style}
                    onChange={(e) => setStyle(e.target.value)}
                    maxLength={1000}
                  />
                </label>
              )}
              <Message message={message} />
              {result && (
                <div className="generated-result">
                  <p>
                    <Check size={17} />
                    Your audio is ready
                  </p>
                  <audio src={result.url} controls />
                  <a
                    className="text-button"
                    href={result.url}
                    download={`creator-audio.${result.ext}`}
                  >
                    <DownloadSimple size={18} />
                    Download audio
                  </a>
                </div>
              )}
            </div>
            <aside className="studio-settings">
              <label>
                Audio engine
                <select
                  value={model?.model || ""}
                  onChange={(e) => setModelId(e.target.value)}
                >
                  {models.length ? (
                    models.map((m) => (
                      <option key={m.model} value={m.model}>
                        {m.provider} ·{" "}
                        {m.model === "gpt-4o-mini-tts"
                          ? "Expressive voice"
                          : m.model}
                      </option>
                    ))
                  ) : (
                    <option value="">Not enabled yet</option>
                  )}
                </select>
              </label>
              {task === "Speech" && (
                <label>
                  Voice
                  {model?.voices?.length ? (
                    <select
                      value={voice}
                      onChange={(e) => setVoice(e.target.value)}
                    >
                      {model.voices.map((v) => (
                        <option key={v}>{v}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      value={voice}
                      onChange={(e) => setVoice(e.target.value)}
                      maxLength={100}
                      placeholder="Provider voice ID"
                    />
                  )}
                </label>
              )}
              {!!model?.maxSeconds && (
                <label>
                  Length · {seconds}s
                  <input
                    type="range"
                    value={seconds}
                    onChange={(e) => setSeconds(Number(e.target.value))}
                    min={model.minSeconds}
                    max={model.maxSeconds}
                    step="0.5"
                  />
                </label>
              )}
              {model?.instrumental && (
                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={instrumental}
                    onChange={(e) => setInstrumental(e.target.checked)}
                  />
                  Instrumental only
                </label>
              )}
              <p className="field-help">
                {task === "Speech"
                  ? "AI-generated speech. Let your audience know."
                  : "Generation availability depends on enabled providers and their usage terms."}
              </p>
              <button className="button lime full" disabled={busy}>
                {busy
                  ? "Creating your audio…"
                  : user
                    ? user.active
                      ? "Generate audio"
                      : "Explore plans"
                    : "Sign in to create"}
                <ArrowRight size={19} />
              </button>
              <p className="field-help">
                Paid generation requires an active plan. No automatic retries.
              </p>
            </aside>
          </form>
        </Dialog>
      )}
      {modal === "plan" && (
        <Dialog
          title={`${PLAN_DETAILS.find((p) => p.id === selectedPlan)?.name} is taking shape.`}
          onClose={() => setModal(null)}
        >
          <p className="muted">
            We’re finalizing subscription pricing and included generation
            credits. Checkout is not active in this preview, and you won’t be
            charged.
          </p>
          <p>
            In the meantime, take a look around the studio or listen to the
            original demo cues.
          </p>
          <button className="button lime full" onClick={() => open("studio")}>
            Explore the studio
            <ArrowRight size={21} />
          </button>
        </Dialog>
      )}
      {modal === "about" && (
        <Dialog
          title="A new sound for creators."
          onClose={() => setModal(null)}
        >
          <p>
            Creator Imaging Studio brings the sonic craft of radio imaging to
            podcasts, videos and creator brands.
          </p>
          <p className="muted">
            This local build includes a working studio interface, original
            synthesized demos and account/subscription infrastructure. Live
            billing, provider access, final branding and pricing still need
            launch configuration. Team collaboration is planned.
          </p>
          <p className="muted">
            The original open-source project was created by Bilsimaging. Model
            and provider rights are separate from the application’s MIT license.
          </p>
        </Dialog>
      )}
    </>
  );
}
function Message({ message }) {
  return message ? (
    <p className="status-message" role="status">
      {message}
    </p>
  ) : null;
}
