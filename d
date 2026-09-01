/* ============================================================
   OceanRAG Embeddable Widget Stylesheet
   Themes: [data-oceanrag-theme="light"] (default) | "dark"
   Responsive: full-bleed panel on small screens (<480px)
   ============================================================ */

#oceanrag-widget-root {
  font-family: 'Manrope', 'Outfit', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  z-index: 999999;
  position: relative;
  /* Expose theme colors as CSS variables so both themes stay in sync */
  --oceanrag-accent: #00D4FF;
  --oceanrag-accent-contrast: #040914;
  --oceanrag-panel-bg: rgba(255, 255, 255, 0.97);
  --oceanrag-panel-border: rgba(15, 23, 42, 0.08);
  --oceanrag-panel-shadow: 0 12px 40px rgba(2, 8, 23, 0.18);
  --oceanrag-header-bg: #00D4FF;
  --oceanrag-header-text: #040914;
  --oceanrag-body-text: #0f172a;
  --oceanrag-muted-text: #64748b;
  --oceanrag-bot-bubble-bg: #f1f5f9;
  --oceanrag-bot-bubble-border: rgba(15, 23, 42, 0.06);
  --oceanrag-user-bubble-bg: linear-gradient(135deg, #2563EB, #1D4ED8);
  --oceanrag-user-bubble-text: #ffffff;
  --oceanrag-input-bg: #f8fafc;
  --oceanrag-input-border: rgba(15, 23, 42, 0.12);
  --oceanrag-footer-bg: #f8fafc;
  --oceanrag-time-text: #94a3b8;
}

#oceanrag-widget-root[data-oceanrag-theme="dark"] {
  --oceanrag-accent: #00D4FF;
  --oceanrag-accent-contrast: #040914;
  --oceanrag-panel-bg: rgba(11, 18, 33, 0.96);
  --oceanrag-panel-border: rgba(255, 255, 255, 0.08);
  --oceanrag-panel-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
  --oceanrag-header-bg: #1a1a1a;
  --oceanrag-header-text: #ffffff;
  --oceanrag-body-text: #e2e8f0;
  --oceanrag-muted-text: #94a3b8;
  --oceanrag-bot-bubble-bg: rgba(255, 255, 255, 0.04);
  --oceanrag-bot-bubble-border: rgba(255, 255, 255, 0.08);
  --oceanrag-user-bubble-bg: linear-gradient(135deg, #2563EB, #1E40AF);
  --oceanrag-user-bubble-text: #ffffff;
  --oceanrag-input-bg: rgba(4, 9, 20, 0.6);
  --oceanrag-input-border: rgba(255, 255, 255, 0.08);
  --oceanrag-footer-bg: #0b1221;
  --oceanrag-time-text: #64748b;
}

/* ---------- Floating circular launcher ---------- */
.oceanrag-launcher {
  position: fixed;
  bottom: 24px;
  right: 24px;
  height: 56px;
  width: 56px;
  border-radius: 9999px;
  background-color: var(--oceanrag-accent);
  color: var(--oceanrag-accent-contrast);
  border: 1px solid rgba(255, 255, 255, 0.15);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(0, 212, 255, 0.4);
  transition: transform 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275),
              box-shadow 0.3s ease, background-color 0.3s ease;
  z-index: 999999;
  padding: 0;
}
.oceanrag-launcher:hover {
  transform: scale(1.08) translateY(-3px);
  box-shadow: 0 8px 30px rgba(0, 212, 255, 0.5);
}
.oceanrag-launcher:focus-visible {
  outline: 3px solid var(--oceanrag-accent);
  outline-offset: 3px;
}
.oceanrag-launcher:active {
  transform: scale(0.95);
}

/* Icon morph: chat icon visible by default, close icon when open */
.oceanrag-launcher .oceanrag-icon-close {
  display: none;
  position: absolute;
}
.oceanrag-launcher .oceanrag-icon-chat {
  display: block;
}
.oceanrag-launcher.oceanrag-launcher-open {
  transform: rotate(90deg);
}
.oceanrag-launcher.oceanrag-launcher-open .oceanrag-icon-chat {
  display: none;
}
.oceanrag-launcher.oceanrag-launcher-open .oceanrag-icon-close {
  display: block;
}

/* Unread message badge on the launcher */
.oceanrag-unread-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 9999px;
  background-color: #ef4444;
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  line-height: 20px;
  text-align: center;
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.5);
  border: 2px solid #ffffff;
}
#oceanrag-widget-root[data-oceanrag-theme="dark"] .oceanrag-unread-badge {
  border-color: #0b1221;
}

/* ---------- Chat window panel ---------- */
.oceanrag-chatbox {
  position: fixed;
  bottom: 96px;
  right: 24px;
  width: 360px;
  height: min(560px, calc(100vh - 130px));
  border-radius: 20px;
  background-color: var(--oceanrag-panel-bg);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid var(--oceanrag-panel-border);
  box-shadow: var(--oceanrag-panel-shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transform-origin: bottom right;
  transition: opacity 0.28s cubic-bezier(0.075, 0.82, 0.165, 1),
              transform 0.28s cubic-bezier(0.075, 0.82, 0.165, 1);
  z-index: 999998;
}
.oceanrag-hidden {
  opacity: 0;
  transform: scale(0.92) translateY(24px);
  pointer-events: none;
}

/* ---------- Header ---------- */
.oceanrag-header {
  padding: 14px 18px;
  background-color: var(--oceanrag-header-bg);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--oceanrag-panel-border);
  flex-shrink: 0;
}
.oceanrag-header-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.oceanrag-title {
  font-family: 'Outfit', 'Manrope', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: var(--oceanrag-header-text);
  letter-spacing: -0.01em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.oceanrag-pulse-dot {
  height: 8px;
  width: 8px;
  border-radius: 9999px;
  background-color: #10b981;
  display: inline-block;
  box-shadow: 0 0 8px #10b981;
  flex-shrink: 0;
}
.oceanrag-close-btn {
  background: none;
  border: none;
  font-size: 22px;
  color: var(--oceanrag-header-text);
  cursor: pointer;
  padding: 0 4px;
  line-height: 1;
  opacity: 0.75;
  transition: opacity 0.2s, transform 0.2s;
}
.oceanrag-close-btn:hover {
  opacity: 1;
  transform: scale(1.1);
}
.oceanrag-close-btn:focus-visible {
  outline: 2px solid currentColor;
  outline-offset: 2px;
  opacity: 1;
}

/* ---------- Messages ---------- */
.oceanrag-messages {
  flex: 1;
  padding: 16px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  color: var(--oceanrag-body-text);
  scroll-behavior: smooth;
  overscroll-behavior: contain;
}
.oceanrag-msg-row {
  display: flex;
  flex-direction: column;
  max-width: 85%;
}
.oceanrag-msg-user {
  align-self: flex-end;
  align-items: flex-end;
}
.oceanrag-msg-bot {
  align-self: flex-start;
  align-items: flex-start;
}
.oceanrag-bubble {
  padding: 10px 14px;
  border-radius: 14px;
  font-size: 13px;
  line-height: 1.55;
  word-break: break-word;
}
.oceanrag-msg-user .oceanrag-bubble {
  background: var(--oceanrag-user-bubble-bg);
  color: var(--oceanrag-user-bubble-text);
  border-top-right-radius: 4px;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}
.oceanrag-msg-bot .oceanrag-bubble {
  background-color: var(--oceanrag-bot-bubble-bg);
  border: 1px solid var(--oceanrag-bot-bubble-border);
  color: var(--oceanrag-body-text);
  border-top-left-radius: 4px;
}
.oceanrag-msg-user .oceanrag-bubble strong {
  color: #ffffff;
  font-weight: 700;
}
.oceanrag-msg-bot .oceanrag-bubble strong {
  color: var(--oceanrag-accent);
  font-weight: 700;
}

/* Per-message timestamp */
.oceanrag-msg-time {
  font-size: 9.5px;
  color: var(--oceanrag-time-text);
  margin-top: 4px;
  padding: 0 4px;
  user-select: none;
}

/* Custom scrollbar (WebKit) */
.oceanrag-messages::-webkit-scrollbar {
  width: 6px;
}
.oceanrag-messages::-webkit-scrollbar-track {
  background: transparent;
}
.oceanrag-messages::-webkit-scrollbar-thumb {
  background-color: var(--oceanrag-time-text);
  opacity: 0.4;
  border-radius: 9999px;
}

/* ---------- Input form ---------- */
.oceanrag-input-form {
  padding: 12px 14px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom, 0px));
  background-color: var(--oceanrag-footer-bg);
  border-top: 1px solid var(--oceanrag-panel-border);
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}
#oceanrag-text-input {
  flex: 1;
  min-width: 0;
  background-color: var(--oceanrag-input-bg);
  border: 1px solid var(--oceanrag-input-border);
  border-radius: 12px;
  padding: 10px 14px;
  color: var(--oceanrag-body-text);
  font-size: 13px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}
#oceanrag-text-input::placeholder {
  color: var(--oceanrag-muted-text);
}
#oceanrag-text-input:focus {
  border-color: var(--oceanrag-accent);
  box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.15);
}
.oceanrag-send-btn {
  height: 40px;
  width: 40px;
  flex-shrink: 0;
  border-radius: 12px;
  background-color: var(--oceanrag-accent);
  color: var(--oceanrag-accent-contrast);
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: transform 0.2s, background-color 0.2s, box-shadow 0.2s;
}
.oceanrag-send-btn:hover {
  transform: scale(1.06);
  box-shadow: 0 4px 12px rgba(0, 212, 255, 0.35);
}
.oceanrag-send-btn:active {
  transform: scale(0.94);
}
.oceanrag-send-btn:focus-visible {
  outline: 3px solid var(--oceanrag-accent);
  outline-offset: 2px;
}

/* ---------- Typing indicator ---------- */
.oceanrag-bubble.typing {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 12px 14px;
}
.oceanrag-bubble.typing .dot {
  height: 6px;
  width: 6px;
  background-color: var(--oceanrag-accent);
  border-radius: 9999px;
  display: inline-block;
  animation: oceanrag-bounce 1.4s infinite ease-in-out both;
}
.oceanrag-bubble.typing .dot:nth-child(1) { animation-delay: -0.32s; }
.oceanrag-bubble.typing .dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes oceanrag-bounce {
  0%, 80%, 100% { transform: scale(0.4); opacity: 0.5; }
  40% { transform: scale(1); opacity: 1; }
}

/* Message entrance animation */
.oceanrag-msg-row {
  animation: oceanrag-msg-in 0.25s ease both;
}
@keyframes oceanrag-msg-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

/* Respect users who prefer reduced motion */
@media (prefers-reduced-motion: reduce) {
  .oceanrag-chatbox,
  .oceanrag-launcher,
  .oceanrag-msg-row,
  .oceanrag-send-btn {
    animation: none !important;
    transition: none !important;
  }
}

/* ============================================================
   RESPONSIVE — small screens / mobile
   ============================================================ */
@media (max-width: 480px) {
  .oceanrag-launcher {
    bottom: 16px;
    right: 16px;
    /* 44px minimum touch target */
    height: 52px;
    width: 52px;
  }

  .oceanrag-chatbox {
    /* Near-fullscreen sheet with safe-area insets for notched phones */
    bottom: 0;
    right: 0;
    left: 0;
    width: 100%;
    height: 100dvh;
    max-height: 100dvh;
    border-radius: 20px 20px 0 0;
    border-left: none;
    border-right: none;
    border-bottom: none;
  }

  .oceanrag-hidden {
    transform: translateY(40px);
  }

  .oceanrag-header {
    padding: calc(12px + env(safe-area-inset-top, 0px)) 16px 12px;
  }

  .oceanrag-messages {
    padding: 14px;
  }

  .oceanrag-msg-row {
    max-width: 92%;
  }

  .oceanrag-bubble {
    font-size: 14px;
    padding: 11px 14px;
  }

  #oceanrag-text-input {
    font-size: 16px; /* prevents iOS Safari zoom-on-focus */
    padding: 11px 14px;
  }

  .oceanrag-send-btn {
    height: 44px;
    width: 44px;
  }
}

/* Very short landscape phones: keep the panel usable */
@media (max-width: 480px) and (orientation: landscape) {
  .oceanrag-chatbox {
    height: 100dvh;
  }
}
