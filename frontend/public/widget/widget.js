(function() {
  // Prevent duplicate load
  if (window.OceanRAGWidgetLoaded) return;
  window.OceanRAGWidgetLoaded = true;

  /*
   * SECURITY MODEL
   * ==============
   * 1. Widget Public Key (wgt_pub_xxx) is NOT a secret - it's designed for browser exposure
   * 2. Backend resolves application from widget key via X-Widget-Key header
   * 3. Backend enforces origin validation (Origin header check against allowed_origins)
   * 4. Backend enforces rate limiting
  * 5. Conversation identity is browser-generated and stored per widget in client-site localStorage
   * 6. Widget key visibility in DevTools/network requests is expected and secure
   * 7. appId is for reference/debugging only - NOT used for security/authorization
   * 8. Secret application credentials (akp_xxx) NEVER exposed to browser
   */

  // Retrieve embed configurations
  const config = window.OceanRAGWidgetConfig || {
    widgetKey: "",
    appId: "default-app",  // Reference only - not used for security
    backendUrl: window.location.origin
  };

  const API_URL = config.backendUrl || window.location.origin;
  const WIDGET_PUBLIC_KEY = config.widgetKey || config.apiKey || "";

  if (!WIDGET_PUBLIC_KEY) {
    console.error("OceanRAG Widget: Missing widgetKey in configuration");
    return;
  }

  // Load css stylesheet dynamically from the same origin that served this script
  // (the frontend host), NOT the backend - the backend only serves API endpoints.
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = new URL("widget.css", document.currentScript?.src || window.location.href).href;
  document.head.appendChild(link);

  // Widget state
  let widgetTheme = "light";
  let launcherPosition = "right";
  let panelSize = "standard";
  const defaultGreetingMessage = "Hello! Ask me any questions about our policies.";
  let greetingMessage = defaultGreetingMessage;
  let placeholderText = "Type your message...";
  let headerTitle = "Chat Assistant";
  let accentColor = null;
  let starterPrompts = [];
  let leadConsentText = "";
  let leadConsentTextVersion = "";
  let conversationIdentity = null;
  let conversationId = null;
  let unreadCount = 0;

  // DOM references (populated once the widget is rendered)
  let launcher = null;
  let chatbox = null;
  let closeBtn = null;
  let contactBtn = null;
  let textInput = null;
  let form = null;
  let messagesBox = null;
  let titleEl = null;
  let unreadBadge = null;
  let starterPromptsBox = null;

  function relativeLuminance(hex) {
    const safe = String(hex || "").trim().replace(/^#/, "");
    const expanded = safe.length === 3
      ? safe.split("").map((c) => c + c).join("")
      : safe;
    if (!/^[0-9a-fA-F]{6}$/.test(expanded)) return 0;
    const r = parseInt(expanded.slice(0, 2), 16) / 255;
    const g = parseInt(expanded.slice(2, 4), 16) / 255;
    const b = parseInt(expanded.slice(4, 6), 16) / 255;
    const lin = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  }

  // Return the dark or light text colour with the better WCAG contrast.
  function readableTextOn(hex) {
    const luminance = relativeLuminance(hex);
    const darkContrast = (luminance + 0.05) / (relativeLuminance("#040914") + 0.05);
    const lightContrast = 1.05 / (luminance + 0.05);
    return darkContrast >= lightContrast ? "#040914" : "#FFFFFF";
  }

  // Apply the admin's custom accent colour by overriding the theme CSS
  // variables on the widget root. Falls back to the theme defaults when unset.
  function applyAccentColor() {
    const root = document.getElementById("oceanrag-widget-root");
    if (!root || !accentColor) return;
    const contrast = readableTextOn(accentColor);
    root.style.setProperty("--oceanrag-accent", accentColor);
    root.style.setProperty("--oceanrag-accent-contrast", contrast);
    // In light theme the header uses the accent as its background; mirror the
    // admin preview. Dark theme keeps its dark header for contrast.
    if (widgetTheme !== "dark") {
      root.style.setProperty("--oceanrag-header-bg", accentColor);
      root.style.setProperty("--oceanrag-header-text", contrast);
    }
  }

  // Keep a stable visitor identity across visits, scoped to this widget.
  function getConversationIdentity() {
    const storageKey = `oceanrag_conversation_identity:${WIDGET_PUBLIC_KEY}`;
    try {
      let identity = localStorage.getItem(storageKey);
      if (!identity) {
        identity = `widget-${window.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`}`;
      }
      localStorage.setItem(storageKey, identity);
      return identity;
    } catch {
      try {
        let identity = sessionStorage.getItem(storageKey);
        if (!identity) {
          identity = `widget-${Date.now()}-${Math.random().toString(36).slice(2)}`;
          sessionStorage.setItem(storageKey, identity);
        }
        return identity;
      } catch {
        return `widget-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      }
    }
  }

  // Strip bracketed citation markers like [1], [4], [10] that the LLM
  // sometimes appends to answers - end users don't need them.
  function stripCitationMarkers(text) {
    return String(text || "").replace(/\s*\[\d+\]/g, "");
  }

  function escapeHtml(text) {
    return String(text || "").replace(/[&<>"']/g, (character) => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    })[character]);
  }

  function formatTime(date) {
    try {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  function isChatboxOpen() {
    return !!(chatbox && !chatbox.classList.contains("oceanrag-hidden"));
  }

  function updateUnreadBadge() {
    if (!unreadBadge) return;
    if (isChatboxOpen()) {
      unreadCount = 0;
    }
    if (unreadCount > 0) {
      unreadBadge.textContent = unreadCount > 9 ? "9+" : String(unreadCount);
      unreadBadge.classList.remove("oceanrag-hidden");
    } else {
      unreadBadge.classList.add("oceanrag-hidden");
    }
  }

  function openChatbox() {
    chatbox.classList.remove("oceanrag-hidden");
    launcher.classList.add("oceanrag-launcher-open");
    launcher.setAttribute("aria-expanded", "true");
    unreadCount = 0;
    updateUnreadBadge();
    // Move focus into the panel for keyboard / screen-reader users.
    window.setTimeout(() => textInput.focus(), 180);
  }

  function closeChatbox() {
    chatbox.classList.add("oceanrag-hidden");
    launcher.classList.remove("oceanrag-launcher-open");
    launcher.setAttribute("aria-expanded", "false");
  }

  // Render one message row. Citations are intentionally NOT shown to end
  // users, and residual [n] markers are stripped from the answer text.
  function addMessage(text, sender, options) {
    if (!messagesBox) return;

    const opts = options || {};
    const row = document.createElement("div");
    row.className = `oceanrag-msg-row oceanrag-msg-${sender}`;

    const bubble = document.createElement("div");
    bubble.className = "oceanrag-bubble";

    // Simulate formatting: **bold** then newlines
    let formattedText = escapeHtml(stripCitationMarkers(text))
      .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    bubble.innerHTML = formattedText.split("\n").join("<br/>");

    const time = document.createElement("span");
    time.className = "oceanrag-msg-time";
    time.textContent = formatTime(opts.createdAt ? new Date(opts.createdAt) : new Date());
    time.setAttribute("aria-hidden", "true");

    row.appendChild(bubble);
    row.appendChild(time);
    messagesBox.appendChild(row);
    messagesBox.scrollTop = messagesBox.scrollHeight;

    // Unread indicator when a bot reply arrives while the panel is closed.
    // The initial greeting is silent so the badge does not nag on load.
    if (sender === "bot" && !opts.silent && !isChatboxOpen()) {
      unreadCount += 1;
      updateUnreadBadge();
    }
  }

  function showContactForm(action) {
    if (!messagesBox || !conversationId) return;
    const existing = messagesBox.querySelector(".oceanrag-lead-card");
    if (existing) {
      existing.scrollIntoView({ block: "nearest" });
      return;
    }

    const formElement = document.createElement("form");
    formElement.className = "oceanrag-lead-card";
    formElement.innerHTML = `
      <h3>Send an enquiry</h3>
      <p>Share your details and the business team can follow up with you.</p>
      <label>Name <input name="name" maxlength="120" required autocomplete="name" /></label>
      <label>Email <input name="email" type="email" maxlength="254" autocomplete="email" /></label>
      <label>Phone <input name="phone" type="tel" maxlength="32" autocomplete="tel" /></label>
      <label>What would you like to discuss? <textarea name="message" maxlength="2000" rows="3"></textarea></label>
      <label class="oceanrag-lead-consent">
        <input name="consent" type="checkbox" required />
        <span class="oceanrag-lead-consent-text"></span>
      </label>
      <button type="submit">Review and submit enquiry</button>
      <div class="oceanrag-lead-error" role="alert"></div>
    `;
    const consentText = formElement.querySelector(".oceanrag-lead-consent-text");
    consentText.textContent = action?.consent_text || leadConsentText;
    const idempotencyKey = () => (
      window.crypto?.randomUUID?.()
      || "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (character) => {
        const random = Math.random() * 16 | 0;
        const value = character === "x" ? random : (random & 0x3 | 0x8);
        return value.toString(16);
      })
    );
    let submissionKey = idempotencyKey();

    formElement.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = new FormData(formElement);
      const email = String(values.get("email") || "").trim();
      const phone = String(values.get("phone") || "").trim();
      const errorElement = formElement.querySelector(".oceanrag-lead-error");
      const submitButton = formElement.querySelector('button[type="submit"]');
      if (!email && !phone) {
        errorElement.textContent = "Enter an email address or phone number.";
        return;
      }

      submitButton.disabled = true;
      submitButton.textContent = "Submitting...";
      errorElement.textContent = "";
      try {
        const response = await fetch(`${API_URL}/api/client/widget/leads`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Widget-Key": WIDGET_PUBLIC_KEY,
          },
          body: JSON.stringify({
            conversation_id: conversationId,
            idempotency_key: submissionKey,
            name: String(values.get("name") || "").trim(),
            email: email || null,
            phone: phone || null,
            message: String(values.get("message") || "").trim() || null,
            consent: values.get("consent") === "on",
            consent_text_version: action?.consent_text_version || leadConsentTextVersion,
          }),
        });
        if (!response.ok) {
          const error = await response.json().catch(() => ({}));
          const detail = error?.error?.message || error?.detail?.message || error?.detail;
          throw new Error(typeof detail === "string" ? detail : "Could not submit the enquiry.");
        }

        formElement.remove();
        addMessage(
          "Your enquiry has been submitted. The business team can review it and contact you.",
          "bot",
        );
        showConversationRating();
      } catch (error) {
        errorElement.textContent = error.message || "Could not submit the enquiry. Please try again.";
        submitButton.disabled = false;
        submitButton.textContent = "Review and submit enquiry";
      }
    });

    messagesBox.appendChild(formElement);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function showConversationRating() {
    if (!messagesBox || !conversationId) return;
    if (messagesBox.querySelector(".oceanrag-feedback-card")) return;
    const card = document.createElement("div");
    card.className = "oceanrag-feedback-card";
    const prompt = document.createElement("p");
    prompt.textContent = "How was your experience with this assistant?";
    card.appendChild(prompt);
    const stars = document.createElement("div");
    stars.className = "oceanrag-feedback-stars";
    stars.setAttribute("role", "group");
    stars.setAttribute("aria-label", "Rate your experience from 1 to 5 stars");
    for (let rating = 1; rating <= 5; rating += 1) {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "★";
      button.setAttribute("aria-label", `${rating} star${rating === 1 ? "" : "s"}`);
      button.addEventListener("click", async () => {
        stars.querySelectorAll("button").forEach((item) => { item.disabled = true; });
        try {
          const response = await fetch(
            `${API_URL}/api/client/widget/conversations/${encodeURIComponent(conversationId)}/feedback`,
            {
              method: "POST",
              headers: {
                "Content-Type": "application/json",
                "X-Widget-Key": WIDGET_PUBLIC_KEY,
              },
              body: JSON.stringify({ rating }),
            },
          );
          if (!response.ok) throw new Error("Rating was not accepted.");
          prompt.textContent = "Thank you for your feedback.";
          stars.remove();
        } catch {
          prompt.textContent = "Could not save your rating. Please try again.";
          stars.querySelectorAll("button").forEach((item) => { item.disabled = false; });
        }
      });
      stars.appendChild(button);
    }
    card.append(prompt, stars);
    messagesBox.appendChild(card);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  function renderWidget() {
    const container = document.createElement("div");
    container.id = "oceanrag-widget-root";
    container.setAttribute("data-oceanrag-theme", widgetTheme);
    container.setAttribute("data-launcher-position", launcherPosition);
    container.setAttribute("data-panel-size", panelSize);
    document.body.appendChild(container);

    container.innerHTML = `
      <!-- Floating Circular Launcher -->
      <button id="oceanrag-launcher" class="oceanrag-launcher" title="Open chat" aria-label="Open chat" aria-haspopup="dialog" aria-expanded="false" data-testid="widget-launcher-btn">
        <svg class="oceanrag-icon-chat" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
        <svg class="oceanrag-icon-close" xmlns="http://www.w3.org/2000/svg" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        <span id="oceanrag-unread-badge" class="oceanrag-unread-badge oceanrag-hidden" aria-hidden="true"></span>
      </button>

      <!-- Chat Box Window panel -->
      <div id="oceanrag-chatbox" class="oceanrag-chatbox oceanrag-hidden" role="dialog" aria-label="Chat window" data-testid="widget-chatbox">
        <div id="oceanrag-header" class="oceanrag-header">
          <div class="oceanrag-header-brand">
            <span class="oceanrag-pulse-dot" aria-hidden="true"></span>
            <span id="oceanrag-title" class="oceanrag-title">Chat Assistant</span>
          </div>
          <button id="oceanrag-contact-btn" class="oceanrag-contact-btn" type="button">Contact us</button>
          <button id="oceanrag-close-btn" class="oceanrag-close-btn" title="Minimize Chat" aria-label="Close chat">&times;</button>
        </div>

        <div id="oceanrag-messages" class="oceanrag-messages" aria-live="polite" aria-relevant="additions"></div>

        <div id="oceanrag-starters" class="oceanrag-starters" role="group" aria-label="Suggested questions"></div>

        <form id="oceanrag-input-form" class="oceanrag-input-form">
          <input type="text" id="oceanrag-text-input" placeholder="Type your message..." required aria-label="Type your message" autocomplete="off" data-testid="widget-chat-input" />
          <button type="submit" id="oceanrag-send-btn" class="oceanrag-send-btn" aria-label="Send message" data-testid="widget-chat-submit">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          </button>
        </form>
      </div>
    `;

    launcher = document.getElementById("oceanrag-launcher");
    chatbox = document.getElementById("oceanrag-chatbox");
    closeBtn = document.getElementById("oceanrag-close-btn");
    contactBtn = document.getElementById("oceanrag-contact-btn");
    contactBtn.disabled = true;
    textInput = document.getElementById("oceanrag-text-input");
    form = document.getElementById("oceanrag-input-form");
    messagesBox = document.getElementById("oceanrag-messages");
    titleEl = document.getElementById("oceanrag-title");
    unreadBadge = document.getElementById("oceanrag-unread-badge");
    starterPromptsBox = document.getElementById("oceanrag-starters");

    // Launcher toggles the panel; the icon morphs between chat and close.
    launcher.addEventListener("click", () => {
      if (isChatboxOpen()) {
        closeChatbox();
      } else {
        openChatbox();
      }
    });
    if (window.matchMedia?.("(hover: hover) and (pointer: fine)").matches) {
      launcher.addEventListener("pointerenter", openChatbox);
    }

    document.addEventListener(
      "pointerdown",
      (event) => {
        if (isChatboxOpen() && !container.contains(event.target)) {
          closeChatbox();
        }
      },
      true,
    );

    closeBtn.addEventListener("click", () => {
      closeChatbox();
      launcher.focus();
    });
    contactBtn.addEventListener("click", () => {
      showContactForm();
    });

    // Escape closes the panel (accessibility).
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && isChatboxOpen()) {
        closeChatbox();
        launcher.focus();
      }
    });

    form.addEventListener("submit", handleQuerySubmit);
  }

  // Render the admin-configured starter prompt chips. Clicking a chip fills
  // the input and immediately submits the question.
  function hideStarterPrompts() {
    if (!starterPromptsBox) return;
    starterPromptsBox.innerHTML = "";
    starterPromptsBox.style.display = "none";
  }

  function renderStarterPrompts() {
    if (!starterPromptsBox) return;
    const prompts = Array.isArray(starterPrompts)
      ? starterPrompts.filter((p) => typeof p === "string" && p.trim())
      : [];
    if (!prompts.length) {
      hideStarterPrompts();
      return;
    }
    starterPromptsBox.innerHTML = "";
    starterPromptsBox.style.display = "";

    const heading = document.createElement("div");
    heading.className = "oceanrag-starters-heading";
    const title = document.createElement("strong");
    title.textContent = "Try asking";
    const hint = document.createElement("span");
    hint.textContent = "Select a question to send";
    heading.append(title, hint);

    const promptList = document.createElement("div");
    promptList.className = "oceanrag-starter-list";
    prompts.forEach((prompt) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "oceanrag-starter-chip";
      chip.textContent = prompt;
      chip.setAttribute("aria-label", `Send suggested question: ${prompt}`);
      chip.setAttribute("data-testid", "widget-starter-chip");
      chip.addEventListener("click", () => {
        if (!textInput || textInput.disabled) return;
        hideStarterPrompts();
        textInput.value = prompt;
        if (typeof form.requestSubmit === "function") {
          form.requestSubmit();
        } else {
          handleQuerySubmit(new Event("submit", { cancelable: true }));
        }
      });
      promptList.appendChild(chip);
    });
    starterPromptsBox.append(heading, promptList);
  }

  // Handle queries
  async function handleQuerySubmit(e) {
    e.preventDefault();
    const query = textInput.value.trim();
    if (!query) return;

    hideStarterPrompts();
    addMessage(query, "user");
    textInput.value = "";
    const previousConversationId = conversationId;

    // Show searching bubble
    const thinkingRow = document.createElement("div");
    thinkingRow.className = "oceanrag-msg-row oceanrag-msg-bot oceanrag-thinking-row";
    thinkingRow.innerHTML = `
      <div class="oceanrag-bubble typing" role="status" aria-label="Assistant is typing">
        <span class="dot"></span>
        <span class="dot"></span>
        <span class="dot"></span>
      </div>
    `;
    messagesBox.appendChild(thinkingRow);
    messagesBox.scrollTop = messagesBox.scrollHeight;

    try {
      const requestBody = {
        conversation_identity: conversationIdentity,
        message: query,
      };

      // Include conversation_id if we have one (for context continuity)
      if (conversationId) {
        requestBody.conversation_id = conversationId;
      }

      const response = await fetch(`${API_URL}/api/client/chat/widget/messages`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Widget-Key": WIDGET_PUBLIC_KEY,
        },
        body: JSON.stringify(requestBody),
      });

      // Remove thinking
      thinkingRow.remove();

      if (response.ok) {
        const data = await response.json();

        if (
          previousConversationId
          && data.conversation_id
          && data.conversation_id !== previousConversationId
        ) {
          messagesBox.replaceChildren();
          addMessage(query, "user");
        }

        // Store conversation ID for subsequent messages
        if (data.conversation_id) {
          conversationId = data.conversation_id;
        }

        // Citations are intentionally NOT shown to end users.
        addMessage(data.answer, "bot");
        if (Array.isArray(data.actions)) {
          const contactAction = data.actions.find(
            (action) => action.type === "contact_enquiry",
          );
          if (contactAction) showContactForm(contactAction);
        }
      } else {
        let fallback = "⚠️ Failed to process your request. Please try again later.";
        if (response.status === 403) {
          fallback = "⚠️ Access denied. This widget is not authorized for this domain.";
        } else if (response.status === 404) {
          fallback = "⚠️ Widget configuration not found. Please contact support.";
        } else if (response.status === 409) {
          fallback = "⚠️ No ready knowledge is available yet. Please try again later.";
        }

        try {
          const data = await response.json();
          const detail = data?.error?.message || data?.detail?.message || data?.detail || fallback;
          addMessage(typeof detail === "string" ? detail : fallback, "bot");
        } catch {
          addMessage(fallback, "bot");
        }
      }
    } catch {
      thinkingRow.remove();
      addMessage("⚠️ Connection error. Please check your internet connection.", "bot");
    }
  }

  // Fetch widget configuration from backend, THEN render the widget.
  // Rendering after the config check lets us honour is_enabled=false by
  // not rendering anything at all (previously a disabled widget still
  // showed its launcher and chat window on the host page).
  async function loadWidgetSettings() {
    try {
      const response = await fetch(`${API_URL}/api/client/widget/configuration`, {
        cache: "no-store",
        headers: {
          "X-Widget-Key": WIDGET_PUBLIC_KEY,
        },
      });

      if (response.ok) {
        const data = await response.json();

        // Respect the enabled flag: a disabled widget must not appear.
        if (data.is_enabled === false) {
          console.info("OceanRAG Widget: widget is disabled for this application.");
          return;
        }

        widgetTheme = data.theme === "dark" ? "dark" : "light";
        launcherPosition = data.launcher_position === "left" ? "left" : "right";
        panelSize = ["compact", "standard", "wide"].includes(data.panel_size)
          ? data.panel_size
          : "standard";
        greetingMessage = data.welcome_message || greetingMessage;
        placeholderText = data.placeholder_text || placeholderText;
        // Launcher label wins; fall back to the application display name.
        headerTitle = data.launcher_label || data.display_name || headerTitle;
        accentColor = data.accent_color || null;
        starterPrompts = Array.isArray(data.starter_prompts) ? data.starter_prompts : [];
        leadConsentText = data.lead_consent_text || "";
        leadConsentTextVersion = data.lead_consent_text_version || "";
      } else {
        console.warn("OceanRAG Widget: Failed to load configuration");
        return;
      }
    } catch (e) {
      console.warn("OceanRAG Widget: Could not sync widget settings.", e);
      return;
    }

    renderWidget();
    applyAccentColor();

    titleEl.textContent = headerTitle;
    launcher.title = `Open ${headerTitle}`;
    launcher.setAttribute("aria-label", `Open chat with ${headerTitle}`);
    textInput.placeholder = placeholderText;

    // Restore retained visitor history or create the visitor's first conversation.
    conversationIdentity = getConversationIdentity();
    textInput.disabled = true;
    const sendButton = document.getElementById("oceanrag-send-btn");
    if (sendButton) sendButton.disabled = true;

    try {
      const sessionResponse = await fetch(`${API_URL}/api/client/widget/session`, {
        method: "POST",
        cache: "no-store",
        headers: {
          "Content-Type": "application/json",
          "X-Widget-Key": WIDGET_PUBLIC_KEY,
        },
        body: JSON.stringify({ conversation_identity: conversationIdentity }),
      });

      if (sessionResponse.ok) {
        const session = await sessionResponse.json();
        conversationId = session.conversation_id || null;
        if (Array.isArray(session.messages) && session.messages.length > 0) {
          hideStarterPrompts();
          for (const message of session.messages) {
            addMessage(message.content, message.role === "user" ? "user" : "bot", {
              createdAt: message.created_at,
              silent: true,
            });
          }
        } else {
          renderStarterPrompts();
        }
      } else {
        hideStarterPrompts();
        console.warn("OceanRAG Widget: Could not restore conversation history.");
      }
    } catch (error) {
      hideStarterPrompts();
      console.warn("OceanRAG Widget: Could not restore conversation history.", error);
    }

    if (!messagesBox.children.length) {
      addMessage(greetingMessage, "bot", { silent: true });
    }
    textInput.disabled = false;
    if (sendButton) sendButton.disabled = false;
    if (contactBtn) contactBtn.disabled = !conversationId;
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  loadWidgetSettings();

})();
