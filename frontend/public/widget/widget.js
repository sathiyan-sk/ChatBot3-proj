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
   * 5. Conversation identity is browser-generated, stored in sessionStorage (per-tab)
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
  let greetingMessage = "Hello! Ask me any questions about our policies.";
  let placeholderText = "Type your message...";
  let headerTitle = "Chat Assistant";
  let conversationIdentity = null;
  let conversationId = null;
  let unreadCount = 0;

  // DOM references (populated once the widget is rendered)
  let launcher = null;
  let chatbox = null;
  let closeBtn = null;
  let textInput = null;
  let form = null;
  let messagesBox = null;
  let titleEl = null;
  let unreadBadge = null;

  // Generate or retrieve conversation identity from sessionStorage
  function getConversationIdentity() {
    let identity = sessionStorage.getItem("oceanrag_conversation_identity");
    if (!identity) {
      // SECURITY: appId is NOT included in identity - backend resolves application from widget key
      identity = "widget-" + Date.now() + "-" + Math.random().toString(36).substring(2, 15);
      sessionStorage.setItem("oceanrag_conversation_identity", identity);
    }
    return identity;
  }

  // Strip bracketed citation markers like [1], [4], [10] that the LLM
  // sometimes appends to answers - end users don't need them.
  function stripCitationMarkers(text) {
    return String(text || "").replace(/\s*\[\d+\]/g, "");
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
    let formattedText = stripCitationMarkers(text).replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    bubble.innerHTML = formattedText.split("\n").join("<br/>");

    const time = document.createElement("span");
    time.className = "oceanrag-msg-time";
    time.textContent = formatTime(new Date());
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

  function renderWidget() {
    const container = document.createElement("div");
    container.id = "oceanrag-widget-root";
    container.setAttribute("data-oceanrag-theme", widgetTheme);
    document.body.appendChild(container);

    container.innerHTML = `
      <!-- Floating Circular Launcher -->
      <button id="oceanrag-launcher" class="oceanrag-launcher" title="Chat with Assistant" aria-label="Open chat" aria-haspopup="dialog" aria-expanded="false" data-testid="widget-launcher-btn">
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
          <button id="oceanrag-close-btn" class="oceanrag-close-btn" title="Minimize Chat" aria-label="Close chat">&times;</button>
        </div>

        <div id="oceanrag-messages" class="oceanrag-messages" aria-live="polite" aria-relevant="additions"></div>

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
    textInput = document.getElementById("oceanrag-text-input");
    form = document.getElementById("oceanrag-input-form");
    messagesBox = document.getElementById("oceanrag-messages");
    titleEl = document.getElementById("oceanrag-title");
    unreadBadge = document.getElementById("oceanrag-unread-badge");

    // Launcher toggles the panel; the icon morphs between chat and close.
    launcher.addEventListener("click", () => {
      if (isChatboxOpen()) {
        closeChatbox();
      } else {
        openChatbox();
      }
    });

    closeBtn.addEventListener("click", () => {
      closeChatbox();
      launcher.focus();
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

  // Handle queries
  async function handleQuerySubmit(e) {
    e.preventDefault();
    const query = textInput.value.trim();
    if (!query) return;

    addMessage(query, "user");
    textInput.value = "";

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

        // Store conversation ID for subsequent messages
        if (data.conversation_id) {
          conversationId = data.conversation_id;
        }

        // Citations are intentionally NOT shown to end users.
        addMessage(data.answer, "bot");
      } else if (response.status === 403) {
        addMessage("⚠️ Access denied. This widget is not authorized for this domain.", "bot");
      } else if (response.status === 404) {
        addMessage("⚠️ Widget configuration not found. Please contact support.", "bot");
      } else {
        addMessage("⚠️ Failed to process your request. Please try again later.", "bot");
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
        greetingMessage = data.welcome_message || greetingMessage;
        placeholderText = data.placeholder_text || placeholderText;
        // Launcher label wins; fall back to the application display name.
        headerTitle = data.launcher_label || data.display_name || headerTitle;
      } else {
        console.warn("OceanRAG Widget: Failed to load configuration");
      }
    } catch (e) {
      console.warn("OceanRAG Widget: Could not sync widget settings.", e);
    }

    renderWidget();

    titleEl.textContent = headerTitle;
    textInput.placeholder = placeholderText;

    // Initialize conversation identity
    conversationIdentity = getConversationIdentity();

    // Welcome Greeting Prompt (silent: never triggers the unread badge)
    addMessage(greetingMessage, "bot", { silent: true });
  }

  loadWidgetSettings();

})();
