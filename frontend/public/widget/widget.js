(function() {
  // Prevent duplicate load
  if (window.OceanRAGWidgetLoaded) return;
  window.OceanRAGWidgetLoaded = true;

  /*
   * SECURITY MODEL
   * ==============
   * 1. Widget Public Key (wk_xxx) is NOT a secret - it's designed for browser exposure
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
  let widgetTheme = "#00D4FF";
  let greetingMessage = "Hello! Ask me any questions about our policies.";
  let conversationIdentity = null;
  let conversationId = null;

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

  // Setup widget container
  const container = document.createElement("div");
  container.id = "oceanrag-widget-root";
  document.body.appendChild(container);

  // Inject HTML Elements
  container.innerHTML = `
    <!-- Floating Circular Launcher -->
    <button id="oceanrag-launcher" class="oceanrag-launcher" title="Chat with Assistant" data-testid="widget-launcher-btn">
      <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" class="oceanrag-icon"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
    </button>

    <!-- Chat Box Window panel -->
    <div id="oceanrag-chatbox" class="oceanrag-chatbox oceanrag-hidden" data-testid="widget-chatbox">
      <div id="oceanrag-header" class="oceanrag-header">
        <div class="oceanrag-header-brand">
          <span class="oceanrag-pulse-dot"></span>
          <span id="oceanrag-title" class="oceanrag-title">Chat Assistant</span>
        </div>
        <button id="oceanrag-close-btn" class="oceanrag-close-btn" title="Minimize Chat">&times;</button>
      </div>

      <div id="oceanrag-messages" class="oceanrag-messages"></div>

      <form id="oceanrag-input-form" class="oceanrag-input-form">
        <input type="text" id="oceanrag-text-input" placeholder="Type your message..." required data-testid="widget-chat-input" />
        <button type="submit" id="oceanrag-send-btn" class="oceanrag-send-btn" data-testid="widget-chat-submit">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
        </button>
      </form>
    </div>
  `;

  // Grab nodes
  const launcher = document.getElementById("oceanrag-launcher");
  const chatbox = document.getElementById("oceanrag-chatbox");
  const closeBtn = document.getElementById("oceanrag-close-btn");
  const textInput = document.getElementById("oceanrag-text-input");
  const form = document.getElementById("oceanrag-input-form");
  const messagesBox = document.getElementById("oceanrag-messages");
  const header = document.getElementById("oceanrag-header");
  const titleEl = document.getElementById("oceanrag-title");

  // Fetch widget configuration from backend
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
        
        // Apply configuration
        widgetTheme = data.theme === "dark" ? "#1a1a1a" : "#00D4FF";
        greetingMessage = data.welcome_message || "Hello! Ask me anything.";
        
        if (data.launcher_label) {
          titleEl.textContent = data.launcher_label;
        }
        
        if (data.placeholder_text) {
          textInput.placeholder = data.placeholder_text;
        }

        // Apply styling
        launcher.style.backgroundColor = widgetTheme;
        header.style.backgroundColor = widgetTheme;
      } else {
        console.warn("OceanRAG Widget: Failed to load configuration");
      }
    } catch (e) {
      console.warn("OceanRAG Widget: Could not sync widget settings.", e);
    }
    
    // Initialize conversation identity
    conversationIdentity = getConversationIdentity();
    
    // Welcome Greeting Prompt
    addMessage(greetingMessage, "bot");
  }

  loadWidgetSettings();

  // Launcher Events
  launcher.addEventListener("click", () => {
    chatbox.classList.toggle("oceanrag-hidden");
    if (!chatbox.classList.contains("oceanrag-hidden")) {
      textInput.focus();
    }
  });

  closeBtn.addEventListener("click", () => {
    chatbox.classList.add("oceanrag-hidden");
  });

  // Render text bubble
  function addMessage(text, sender, sources = []) {
    const bubble = document.createElement("div");
    bubble.className = `oceanrag-msg-row oceanrag-msg-${sender}`;
    
    // Simulate formatting
    let formattedText = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formattedText = formattedText.split('\n').join('<br/>');

    bubble.innerHTML = `
      <div class="oceanrag-bubble">
        ${formattedText}
      </div>
    `;

    // Render source segments
    if (sources && sources.length > 0) {
      const sourcesDiv = document.createElement("div");
      sourcesDiv.className = "oceanrag-sources-list";
      sourcesDiv.innerHTML = `<span class="sources-title">Verified citations:</span>`;
      sources.forEach(src => {
        const item = document.createElement("div");
        item.className = "source-item";
        item.innerHTML = `
          <div class="source-item-meta">Document: ${src.document_id || "Context"} • Chunk ${src.chunk_id}</div>
          <div class="source-item-text">"${src.title || ""}"</div>
        `;
        sourcesDiv.appendChild(item);
      });
      bubble.appendChild(sourcesDiv);
    }

    messagesBox.appendChild(bubble);
    messagesBox.scrollTop = messagesBox.scrollHeight;
  }

  // Handle queries
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = textInput.value.trim();
    if (!query) return;

    addMessage(query, "user");
    textInput.value = "";

    // Show searching bubble
    const thinkingRow = document.createElement("div");
    thinkingRow.className = "oceanrag-msg-row oceanrag-msg-bot oceanrag-thinking-row";
    thinkingRow.innerHTML = `
      <div class="oceanrag-bubble typing">
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
        
        addMessage(data.answer, "bot", data.citations || []);
      } else if (response.status === 403) {
        addMessage("⚠️ Access denied. This widget is not authorized for this domain.", "bot");
      } else if (response.status === 404) {
        addMessage("⚠️ Widget configuration not found. Please contact support.", "bot");
      } else {
        addMessage("⚠️ Failed to process your request. Please try again later.", "bot");
      }
    } catch {
      thinkingRow.remove();
      addMessage("⚠️ Connectivity error. Please check on connection Establishion.", "bot");
    }
  });

})();