import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "@/api/client";
import {
  ArrowLeft, Database, MessageSquare, Settings, Play,
  Trash2, Copy, Check, UploadCloud, FileText, Loader2,
  AlertCircle, Sparkles, Sliders, Globe, Eye, Terminal, RefreshCw,
  Plus, Archive, RotateCcw, XCircle, KeyRound, Pencil, Power
} from "lucide-react";
import { toast } from "sonner";
import ConversationsTab from "@/components/ConversationsTab";

export default function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState(null);
  const [activeTab, setActiveTab] = useState("general");
  const [isLoading, setIsLoading] = useState(true);

  // General state
  const [documents, setDocuments] = useState([]);
  const [knowledgeBase, setKnowledgeBase] = useState(null);
  const [settings, setSettings] = useState(null);
  const [widgetCfg, setWidgetCfg] = useState(null);

  // Interaction sandbox testing states
  const [sandboxQuestion, setSandboxQuestion] = useState("");
  const [sandboxHistory, setSandboxHistory] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [chatTopK, setChatTopK] = useState(4);
  const [sandboxApiKey, setSandboxApiKey] = useState(() => localStorage.getItem("oceanrag_sandbox_api_key") || "");
  const [showSandboxKeyInput, setShowSandboxKeyInput] = useState(false);

  // Widget appearance configurations
  const [greetingMsg, setGreetingMsg] = useState("");
  const [themeColor, setThemeColor] = useState("#00D4FF");
  const [launcherLabel, setLauncherLabel] = useState("Chat with us");
  const [placeholderText, setPlaceholderText] = useState("Type your message...");
  const [isWidgetEnabled, setIsWidgetEnabled] = useState(true);

  // Ingestion upload states
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [websiteTitle, setWebsiteTitle] = useState("");

  // Copy states
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  const fetchAppData = async () => {
    try {
      // Fetch application details
      const appsRes = await apiClient.get("/admin/applications");
      const matched = appsRes.data.find((a) => a.id === id);
      if (matched) {
        setApp(matched);

        // Fetch knowledge base for this application
        let kbData = null;
        try {
          const kbRes = await apiClient.get(`/admin/knowledge-bases/by-application/${id}`);
          kbData = kbRes.data;
          setKnowledgeBase(kbData);
        } catch {
          console.warn("No knowledge base found for this application");
        }

        // Fetch documents if knowledge base exists using the freshly loaded value.
        if (kbData?.id) {
          const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${kbData.id}`);
          setDocuments(docsRes.data);
        }

        // Fetch widget configuration.
        // New applications may legitimately not have a widget yet; in that case
        // we keep the page quiet and let the admin create one from the form below.
        try {
          const widgetRes = await apiClient.get(`/admin/widgets/application/${id}`);
          setWidgetCfg(widgetRes.data);
          setGreetingMsg(widgetRes.data.welcome_message || "");
          setThemeColor(widgetRes.data.theme === "dark" ? "#1a1a1a" : "#00D4FF");
          setLauncherLabel(widgetRes.data.launcher_label || "Chat with us");
          setPlaceholderText(widgetRes.data.placeholder_text || "Type your message...");
          setIsWidgetEnabled(widgetRes.data.is_enabled);
        } catch (error) {
          if (error.response?.status !== 404) {
            console.warn("Failed to load widget configuration for this application", error);
          }
          setWidgetCfg(null);
          setGreetingMsg("");
          setThemeColor("#00D4FF");
          setLauncherLabel("Chat with us");
          setPlaceholderText("Type your message...");
          setIsWidgetEnabled(true);
        }

        // Fetch settings
        try {
          const settingsRes = await apiClient.get(`/admin/settings/by-application/${id}`);
          setSettings(settingsRes.data);
        } catch {
          console.warn("No settings found for this application");
        }
      } else {
        toast.error("Application namespace not found.");
      }
    } catch {
      console.error("Failed to load application profile.");
      toast.error("Failed to load application profile.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      await fetchAppData();
    };

    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Document Auto polling for pending/processing states
  // (backend statuses: pending | processing | ready | failed | archived)
  useEffect(() => {
    if (!knowledgeBase?.id) return;
    
    const unfinished = documents.some((d) => d.status === "pending" || d.status === "processing");
    if (unfinished) {
      const interval = setInterval(async () => {
        try {
          const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
          setDocuments(docsRes.data);
        } catch (e) {
          console.warn("Polling documents failed", e);
        }
      }, 3000);
      return () => clearInterval(interval);
    }
  }, [documents, knowledgeBase]);

  const handleUpdateSettings = async (e) => {
    e.preventDefault();
    try {
      if (settings?.id) {
        // Update existing settings
        await apiClient.put(`/admin/settings/by-application/${id}`, {
          llm_temperature: settings.llm_temperature,
          max_context_messages: settings.max_context_messages,
          inactivity_timeout_minutes: settings.inactivity_timeout_minutes,
          retention_days: settings.retention_days,
          prompt_system_template: settings.prompt_system_template,
        });
      } else {
        // Create new settings
        await apiClient.post("/admin/settings", {
          application_id: id,
        });
      }
      toast.success("RAG Parameters and System Prompt saved securely!");
      fetchAppData(); // Refresh settings
    } catch (e) {
      console.error(e);
      toast.error("Failed to save settings.");
    }
  };

  const handleUpdateWidget = async (e) => {
    e.preventDefault();
    try {
      if (widgetCfg?.id) {
        // Update existing widget
        await apiClient.put(`/admin/widgets/${widgetCfg.id}`, {
          display_name: widgetCfg.display_name,
          theme: themeColor.startsWith("#") ? "light" : themeColor,
          launcher_label: launcherLabel,
          welcome_message: greetingMsg,
          placeholder_text: placeholderText,
          is_enabled: isWidgetEnabled,
        });
      } else {
        try {
          // Create new widget
          await apiClient.post("/admin/widgets", {
            application_id: id,
            display_name: app?.name || "Support Widget",
            theme: themeColor.startsWith("#") ? "light" : themeColor,
            launcher_label: launcherLabel,
            welcome_message: greetingMsg,
            placeholder_text: placeholderText,
            is_enabled: isWidgetEnabled,
          });
        } catch (error) {
          if (error.response?.status === 409) {
            const existing = await apiClient.get(`/admin/widgets/application/${id}`);
            await apiClient.put(`/admin/widgets/${existing.data.id}`, {
              display_name: existing.data.display_name || app?.name || "Support Widget",
              theme: themeColor.startsWith("#") ? "light" : themeColor,
              launcher_label: launcherLabel,
              welcome_message: greetingMsg,
              placeholder_text: placeholderText,
              is_enabled: isWidgetEnabled,
            });
          } else {
            throw error;
          }
        }
      }
      toast.success("Widget appearance and access contracts updated!");
      fetchAppData(); // Refresh widget config
    } catch (e) {
      console.error(e);
      toast.error("Failed to update widget credentials.");
    }
  };

  // Upload Actions
  const handleUpload = async (file) => {
    if (!knowledgeBase?.id) {
      toast.error("No knowledge base found. Please create one first.");
      return;
    }

    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    const allowed = [".pdf", ".txt", ".docx", ".csv", ".json", ".md"];
    if (!allowed.includes(ext)) {
      toast.error(`Unsupported format. Formats: ${allowed.join(", ")}`);
      return;
    }

    setIsUploading(true);
    const form = new FormData();
    form.append("file", file);
    form.append("knowledge_base_id", knowledgeBase.id);
    form.append("title", file.name);

    try {
      await apiClient.post("/admin/documents/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`"${file.name}" uploaded successfully! Real-time ingestion triggered.`);
      // Refresh documents
      const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
      setDocuments(docsRes.data);
    } catch (e) {
      console.error(e);
      const msg = e.response?.data?.detail || "Ingestion failed.";
      toast.error(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const handleCreateWebsiteDocument = async (e) => {
    e.preventDefault();
    if (!knowledgeBase?.id) {
      toast.error("No knowledge base found. Please create one first.");
      return;
    }

    const trimmedUrl = websiteUrl.trim();
    if (!trimmedUrl) {
      toast.error("Please enter a website URL.");
      return;
    }

    try {
      const url = new URL(trimmedUrl);
      if (!["http:", "https:"].includes(url.protocol)) {
        throw new Error("URL must use http or https");
      }

      await apiClient.post("/admin/documents", {
        knowledge_base_id: knowledgeBase.id,
        title: websiteTitle.trim() || url.hostname,
        description: `Website source: ${url.toString()}`,
        source_type: "website",
        source_uri: url.toString(),
      });

      toast.success(`Website source "${url.hostname}" queued for ingestion.`);
      setWebsiteUrl("");
      setWebsiteTitle("");
      const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
      setDocuments(docsRes.data);
    } catch (error) {
      console.error(error);
      toast.error("Website document creation failed. Please enter a valid http/https URL.");
    }
  };

  const handleDeleteDoc = async (docId, name) => {
    if (!window.confirm(`Are you sure you want to delete and un-index "${name}"?`)) return;
    try {
      await apiClient.delete(`/admin/documents/${docId}`);
      toast.success(`Removed "${name}" from directory.`);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
    } catch (e) {
      console.error(e);
      toast.error("Un-indexing file failed.");
    }
  };

  const handleReindex = async () => {
    if (!documents.length) return;
    setIsRebuilding(true);
    try {
      // Re-ingest every non-archived document (the old implementation
      // only re-ingested documents[0], which silently skipped the rest).
      const targets = documents.filter((d) => d.status !== "archived");
      let queued = 0;
      for (const doc of targets) {
        try {
          await apiClient.post("/admin/ingestion/start", {
            document_id: doc.id,
          });
          queued += 1;
        } catch (docErr) {
          console.error(`Reindex failed for document ${doc.id}`, docErr);
        }
      }
      if (queued > 0) {
        toast.success(`Vector rebuild queued for ${queued} document(s)!`);
      } else {
        toast.error("No documents could be queued for reindexing.");
      }
      // Refresh
      if (knowledgeBase?.id) {
        const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
        setDocuments(docsRes.data);
      }
    } catch (e) {
      console.error(e);
      toast.error("Reindexing vector space failed.");
    } finally {
      setIsRebuilding(false);
    }
  };

  // Create Knowledge Base
  const handleCreateKB = async () => {
    try {
      const res = await apiClient.post("/admin/knowledge-bases", {
        application_id: id,
        name: `${app?.name || "App"} Knowledge Base`,
      });
      setKnowledgeBase(res.data);
      toast.success("Knowledge base created!");
    } catch (e) {
      console.error(e);
      toast.error("Failed to create knowledge base.");
    }
  };

  // Document lifecycle actions
  const handleDocAction = async (docId, action, extra = {}) => {
    try {
      await apiClient.post(`/admin/documents/${docId}/${action}`, extra);
      toast.success(`Document marked as ${action}.`);
      if (knowledgeBase?.id) {
        const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
        setDocuments(docsRes.data);
      }
    } catch (e) {
      console.error(e);
      toast.error(`Failed to ${action} document.`);
    }
  };

  // Application activate/deactivate toggle
  const handleToggleActive = async () => {
    try {
      await apiClient.put(`/admin/applications/${id}`, {
        name: app.name,
        description: app.description,
        client_type: app.client_type,
        allowed_origins: app.allowed_origins,
        is_active: !app.is_active,
      });
      toast.success(`Application ${app.is_active ? "deactivated" : "activated"}.`);
      fetchAppData();
    } catch (e) {
      console.error(e);
      toast.error("Failed to update application status.");
    }
  };

  // Sandbox Chat testing
  const handleChatTest = async (e) => {
    e.preventDefault();
    if (!sandboxQuestion.trim() || isChatLoading || !app) return;

    const userMsg = {
      role: "user",
      content: sandboxQuestion,
      timestamp: new Date().toISOString()
    };
    setSandboxHistory((prev) => [...prev, userMsg]);
    setSandboxQuestion("");
    setIsChatLoading(true);

    try {
      const response = await apiClient.post("/client/chat/messages", {
        conversation_identity: `sandbox-${id}`,
        message: userMsg.content,
        conversation_title: "Admin Sandbox Test",
      }, {
        headers: {
          "X-API-Key": sandboxApiKey || "",
        },
      });

      const data = response.data;
      const botMsg = {
        role: "bot",
        content: data.answer,
        timestamp: new Date().toISOString(),
        sources: data.citations || [],
        conversation_id: data.conversation_id,
      };
      setSandboxHistory((prev) => [...prev, botMsg]);
    } catch (e) {
      console.error(e);
      toast.error("RAG chat connection failed.");
    } finally {
      setIsChatLoading(false);
    }
  };

  // Embed Snippet
  // Widget script is served from FRONTEND (at /widget) for better separation of concerns
  // Backend URL is used for API calls (configuration + chat messages + CORS validation)
  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
  // Widget URL - for development use localhost:5173, for production use the same origin as the admin page
  const FRONTEND_URL = import.meta.env.VITE_FRONTEND_URL || (typeof window !== 'undefined' ? `${window.location.protocol}//${window.location.host}` : "http://localhost:5173");
  
  const embedSnippetHtml = widgetCfg ? `<!-- OceanRAG Embeddable Widget Snippet -->
<script>
  // SECURITY: widgetKey is the only credential needed for authentication
  // Backend resolves the application from the widget key - appId is for reference only
  window.OceanRAGWidgetConfig = {
    widgetKey: "${widgetCfg.public_key || "wk_xxxxxxxx"}",
    appId: "${id}",  // Reference only - NOT used for security/authorization
    backendUrl: "${BACKEND_URL}"
  };
</script>
<script src="${FRONTEND_URL}/widget/widget.js" async></script>` : "";

  const copyToClipboard = (text, type) => {
    navigator.clipboard.writeText(text);
    if (type === "snippet") {
      setCopiedSnippet(true);
      setTimeout(() => setCopiedSnippet(false), 2000);
    } else {
      setCopiedKey(true);
      setTimeout(() => setCopiedKey(false), 2000);
    }
    toast.success("Copied to clipboard!");
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-200px)]">
        <Loader2 className="h-10 w-10 text-[#00D4FF] animate-spin" />
      </div>
    );
  }

  if (!app) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-12 text-center">
        <AlertCircle className="h-12 w-12 text-red-500 mx-auto mb-4 animate-bounce" />
        <h2 className="text-xl font-bold text-white">Application namespace not found</h2>
        <Link to="/dashboard" className="text-[#00D4FF] text-xs hover:underline mt-2 inline-block">
          Return to directory
        </Link>
      </div>
    );
  }

  return (
    <main className="max-w-6xl mx-auto px-4 md:px-8 py-8">
      {/* Return & Header block */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
        <div className="flex items-center gap-4">
          <Link
            to="/dashboard"
            className="p-2 bg-white/5 rounded-xl border border-white/10 text-slate-400 hover:text-white hover:bg-white/10 transition"
            title="Back to directory"
            data-testid="back-to-directory"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2.5">
              <span className="font-mono text-[9px] text-[#00D4FF] font-semibold bg-[#00D4FF]/10 border border-[#00D4FF]/20 px-2.5 py-0.5 rounded-full uppercase tracking-wide">
                APP NAMESPACE
              </span>
              <span className="text-[10px] text-slate-500 font-mono">ID: {app.id}</span>
            </div>
            <h2 className="text-2xl md:text-3xl font-bold text-white mt-1">
              {app.name}
            </h2>
          </div>
        </div>

      </div>

      {/* Modern High Density Pills Navigation Tabs */}
      <div className="flex items-center gap-2 p-1.5 bg-[#0B1221] rounded-2xl border border-white/5 mb-8 overflow-x-auto w-full shadow-lg">
        <button
          onClick={() => setActiveTab("general")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex-shrink-0 ${
            activeTab === "general"
              ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.3)] font-bold"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          data-testid="tab-general"
        >
          <Sparkles className="h-3.5 w-3.5" />
          <span>General</span>
        </button>

        <button
          onClick={() => setActiveTab("kb")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex-shrink-0 ${
            activeTab === "kb"
              ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.3)] font-bold"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          data-testid="tab-kb"
        >
          <Database className="h-3.5 w-3.5" />
          <span>Knowledge Base</span>
        </button>

        <button
          onClick={() => setActiveTab("widget")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex-shrink-0 ${
            activeTab === "widget"
              ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.3)] font-bold"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          data-testid="tab-widget"
        >
          <Globe className="h-3.5 w-3.5" />
          <span>Widget Config</span>
        </button>

        <button
          onClick={() => setActiveTab("chat")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex-shrink-0 ${
            activeTab === "chat"
              ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.3)] font-bold"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          data-testid="tab-chat"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          <span>Chat Testing</span>
        </button>

        <button
          onClick={() => setActiveTab("conversations")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex-shrink-0 ${
            activeTab === "conversations"
              ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.3)] font-bold"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          data-testid="tab-conversations"
        >
          <MessageSquare className="h-3.5 w-3.5" />
          <span>Conversations</span>
        </button>

        <button
          onClick={() => setActiveTab("settings")}
          className={`flex items-center gap-2 px-5 py-2.5 rounded-xl text-xs font-semibold tracking-wider uppercase transition-all duration-300 flex-shrink-0 ${
            activeTab === "settings"
              ? "bg-[#00D4FF] text-[#040914] shadow-[0_0_12px_rgba(0,212,255,0.3)] font-bold"
              : "text-slate-400 hover:text-white hover:bg-white/5"
          }`}
          data-testid="tab-settings"
        >
          <Settings className="h-3.5 w-3.5" />
          <span>Settings</span>
        </button>
      </div>

      {/* Tabs Pages Views */}
      <div className="w-full">
        {/* TABS 1: GENERAL */}
        {activeTab === "general" && (
          <div className="space-y-6 animate-fadeIn" data-testid="view-general">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {/* Context Summary */}
                <div className="md:col-span-2 glassmorphism rounded-2xl p-6 border-white/10">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="font-semibold text-sm text-white">Application Summary</h3>
                    <div className="flex items-center gap-2.5">
                      <Link
                        to={`/admin/applications/${id}/edit`}
                        className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-amber-500/30 text-amber-400 hover:bg-amber-500/10 transition text-xs font-semibold focus:outline-none"
                        title="Edit Application"
                        data-testid="edit-app-btn"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        <span>Edit</span>
                      </Link>
                      <button
                        onClick={handleToggleActive}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border font-semibold text-xs transition focus:outline-none ${
                          app.is_active
                            ? "border-red-500/30 text-red-400 hover:bg-red-500/10"
                            : "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                        }`}
                        title={app.is_active ? "Deactivate" : "Activate"}
                        data-testid="toggle-active-btn"
                      >
                        <Power className="h-3.5 w-3.5" />
                        <span>{app.is_active ? "Deactivate" : "Activate"}</span>
                      </button>
                    </div>
                  </div>
                  <p className="text-slate-300 text-xs leading-relaxed">
                    {app.description || "No description provided."}
                  </p>

                  {/* API Key Prefix section */}
                  <div className="mt-5 pt-4 border-t border-white/5">
                    <div className="flex items-center gap-2 mb-2">
                      <KeyRound className="h-3.5 w-3.5 text-slate-500" />
                      <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">API Key Prefix</span>
                    </div>
                    <div className="flex items-center gap-2.5">
                      <code className="text-slate-300 font-mono text-xs break-all" data-testid="api-key-prefix-display">
                        {app.api_key_prefix || app.api_key_prefix === "" ? app.api_key_prefix : "akp_••••••••••"}
                      </code>
                      <button
                        onClick={() => copyToClipboard(app.api_key_prefix || "akp_••••••••••")}
                        className="text-slate-400 hover:text-white transition p-1 rounded hover:bg-white/5"
                        title="Copy API key prefix"
                        data-testid="copy-key-prefix-btn"
                      >
                        {copiedKey ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                    <p className="text-[10px] text-slate-500 mt-1.5">
                      The full API key was shown only at creation time. This is a read-only reference prefix.
                    </p>
                  </div>

                  <div className="mt-6 pt-5 border-t border-white/5 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                  <div>
                    <span className="block text-slate-500 font-medium text-[10px] uppercase">Slug</span>
                    <span className="block text-slate-300 font-mono mt-0.5">{app.slug}</span>
                  </div>
                  <div>
                    <span className="block text-slate-500 font-medium text-[10px] uppercase">Client Type</span>
                    <span className="block text-[#00D4FF] font-mono mt-0.5 capitalize">{app.client_type}</span>
                  </div>
                  <div>
                    <span className="block text-slate-500 font-medium text-[10px] uppercase">Status</span>
                    <span className={`block font-mono mt-0.5 ${app.is_active ? "text-emerald-400" : "text-red-400"}`}>
                      {app.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <div>
                    <span className="block text-slate-500 font-medium text-[10px] uppercase">Created</span>
                    <span className="block text-slate-300 font-mono mt-0.5">
                      {new Date(app.created_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div>
                    <span className="block text-slate-500 font-medium text-[10px] uppercase">Updated</span>
                    <span className="block text-slate-300 font-mono mt-0.5">
                      {new Date(app.updated_at).toLocaleDateString()}
                    </span>
                  </div>
                  <div className="md:col-span-3">
                    <span className="block text-slate-500 font-medium text-[10px] uppercase">Allowed Origins</span>
                    <span className="block text-slate-300 font-mono mt-0.5 break-all">
                      {(app.allowed_origins || []).length > 0
                        ? app.allowed_origins.join(", ")
                        : "All origins allowed"}
                    </span>
                  </div>
                </div>
              </div>

              {/* Status Health Widget */}
              <div className="glassmorphism rounded-2xl p-6 border-white/10 flex flex-col justify-between">
                <div>
                  <h3 className="font-semibold text-sm text-white mb-4">Ingestion Pipelines</h3>
                  <div className="space-y-3 text-xs">
                    <div className="flex justify-between items-center bg-white/2 p-2 rounded-lg border border-white/5">
                      <span className="text-slate-400">Total documents:</span>
                      <span className="font-bold text-white font-mono">{documents.length}</span>
                    </div>
                    <div className="flex justify-between items-center bg-white/2 p-2 rounded-lg border border-white/5">
                      <span className="text-emerald-400">Indexed (RAG ground):</span>
                      <span className="font-bold text-emerald-400 font-mono">
                        {documents.filter((d) => d.status === "ready").length}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="pt-4 border-t border-white/5 text-[10px] text-slate-500 font-mono flex items-center gap-1.5 mt-4">
                  <div className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></div>
                  <span>Isolated FAISS database: active</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TABS 2: KNOWLEDGE BASE */}
        {activeTab === "kb" && (
          <div className="space-y-6 animate-fadeIn" data-testid="view-kb">
            {!knowledgeBase ? (
              <div className="text-center py-16 border border-dashed border-white/5 rounded-2xl">
                <Database className="h-10 w-10 text-slate-600 mx-auto mb-3" />
                <p className="text-slate-400 text-xs mb-4">No knowledge base found for this application.</p>
                <button
                  onClick={handleCreateKB}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#00D4FF] text-[#040914] font-bold text-xs tracking-wider uppercase hover:scale-[1.02] active:scale-[0.98] transition shadow-md cursor-pointer"
                  data-testid="create-kb-btn"
                >
                  <Plus className="h-3.5 w-3.5" />
                  <span>Create Knowledge Base</span>
                </button>
              </div>
            ) : (
              <>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div>
                    <h3 className="font-semibold text-base text-white">Document Source Registry</h3>
                    <p className="text-slate-400 text-xs mt-0.5">
                      Manage PDF configuration templates, manual text rules, and FAQs.
                    </p>
                  </div>

                  <button
                    onClick={handleReindex}
                    disabled={isRebuilding || documents.length === 0}
                    className={`flex items-center gap-2 px-5 py-3 rounded-xl font-semibold text-xs tracking-wider uppercase transition ${
                      isRebuilding || documents.length === 0
                        ? "bg-white/5 border border-white/5 text-slate-500 cursor-not-allowed"
                        : "bg-gradient-to-r from-[#00D4FF] to-[#2563EB] text-[#040914] hover:scale-103 active:scale-97 shadow-[0_0_15px_rgba(0,212,255,0.2)]"
                    }`}
                    data-testid="reindex-btn"
                  >
                    {isRebuilding ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        <span>Syncing FAISS database...</span>
                      </>
                    ) : (
                      <>
                        <RefreshCw className="h-3.5 w-3.5" />
                        <span>Rebuild Vector Space</span>
                      </>
                    )}
                  </button>
                </div>

                {/* Ingestion Matrix Layout */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                  {/* Drag and Drop Zone */}
                  <div className="lg:col-span-1 space-y-5">
                    <div
                      onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                      onDragLeave={() => setIsDragging(false)}
                      onDrop={(e) => { e.preventDefault(); setIsDragging(false); if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]); }}
                      onClick={() => document.getElementById("doc-uploader-picker").click()}
                      className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition duration-300 h-64 ${
                        isDragging
                          ? "border-[#00D4FF] bg-[#00D4FF]/5 scale-102"
                          : "border-white/10 hover:border-white/20 hover:bg-white/5 bg-[#0B1221]/30"
                      }`}
                      data-testid="file-upload-zone"
                    >
                      <input
                        id="doc-uploader-picker"
                        type="file"
                        className="hidden"
                        onChange={(e) => { if (e.target.files.length) handleUpload(e.target.files[0]); }}
                        accept=".pdf,.txt,.docx,.csv,.json,.md"
                        data-testid="file-upload-input"
                      />
                      {isUploading ? (
                        <div className="space-y-3">
                          <Loader2 className="h-10 w-10 text-[#00D4FF] animate-spin mx-auto" />
                          <p className="text-xs text-slate-300 font-mono animate-pulse">INGESTING BYTES...</p>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <div className="p-3.5 bg-white/5 rounded-full border border-white/10 inline-block">
                            <UploadCloud className="h-6 w-6 text-[#00D4FF]" />
                          </div>
                          <div>
                            <p className="text-xs text-slate-200 font-semibold">Upload Documentation</p>
                            <p className="text-[10px] text-slate-500 mt-1 leading-relaxed">
                              Drag & Drop or browse files.<br />
                              PDF, TXT, DOCX, CSV, MD or JSON.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>

                    <form onSubmit={handleCreateWebsiteDocument} className="glassmorphism rounded-2xl p-4 border border-white/10 space-y-3">
                      <div className="flex items-center gap-2 text-xs font-semibold text-slate-200">
                        <Globe className="h-3.5 w-3.5 text-[#00D4FF]" />
                        <span>Website Source</span>
                      </div>

                      <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Website URL</label>
                        <input
                          type="url"
                          value={websiteUrl}
                          onChange={(e) => setWebsiteUrl(e.target.value)}
                          placeholder="https://example.com"
                          className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-3 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                          data-testid="website-url-input"
                        />
                      </div>

                      <div>
                        <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Title (optional)</label>
                        <input
                          type="text"
                          value={websiteTitle}
                          onChange={(e) => setWebsiteTitle(e.target.value)}
                          placeholder="Example Docs"
                          className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-3 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                          data-testid="website-title-input"
                        />
                      </div>

                      <button
                        type="submit"
                        className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-[#00D4FF] to-[#2563EB] text-[#040914] font-semibold text-[10px] tracking-wider uppercase hover:scale-[1.01] active:scale-[0.98] transition shadow-[0_0_15px_rgba(0,212,255,0.2)] cursor-pointer"
                        data-testid="website-document-submit"
                      >
                        <Globe className="h-3.5 w-3.5" />
                        <span>Ingest Website</span>
                      </button>
                    </form>
                  </div>

                  {/* Table List (Right columns) */}
                  <div className="lg:col-span-2 glassmorphism rounded-2xl p-6 border-white/10">
                    {documents.length === 0 ? (
                      <div className="text-center py-16">
                        <FileText className="h-10 w-10 text-slate-600 mx-auto mb-3" />
                        <p className="text-slate-400 text-xs font-medium">No documents uploaded to this application yet</p>
                      </div>
                    ) : (
                      <div className="overflow-x-auto" data-testid="document-table">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="border-b border-white/10 text-slate-500 font-semibold uppercase tracking-wider text-[10px]">
                              <th className="py-3 px-4">Filename</th>
                              <th className="py-3 px-4">Size</th>
                              <th className="py-3 px-4">Status</th>
                              <th className="py-3 px-4 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {documents.map((doc) => (
                              <tr
                                key={doc.id}
                                className="border-b border-white/5 hover:bg-white/2.5 transition duration-200"
                                data-testid={`document-row-${doc.id}`}
                              >
                                <td className="py-3 px-4 font-semibold text-slate-200 flex items-center gap-2.5 max-w-[200px] md:max-w-[280px]">
                                  <FileText className="h-4 w-4 text-[#00D4FF] flex-shrink-0" />
                                  <span className="truncate" title={doc.title}>{doc.title}</span>
                                </td>
                                <td className="py-3 px-4 text-slate-400 font-mono">
                                  {doc.file_size_bytes
                                    ? `${(doc.file_size_bytes / 1024).toFixed(1)} KB`
                                    : "N/A"}
                                </td>
                                <td className="py-3 px-4" data-testid={`document-status-${doc.id}`}>
                                  {doc.status === "ready" && (
                                    <span className="bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 px-2 py-0.5 rounded-full text-[10px] font-medium font-mono uppercase">
                                      ready
                                    </span>
                                  )}
                                  {doc.status === "processing" && (
                                    <span className="bg-amber-500/10 border border-amber-500/20 text-amber-400 px-2 py-0.5 rounded-full text-[10px] font-medium font-mono uppercase inline-flex items-center gap-1">
                                      <Loader2 className="h-2.5 w-2.5 animate-spin" />
                                      processing
                                    </span>
                                  )}
                                  {doc.status === "pending" && (
                                    <span className="bg-blue-500/10 border border-blue-500/20 text-blue-400 px-2 py-0.5 rounded-full text-[10px] font-medium font-mono uppercase inline-flex items-center gap-1">
                                      <Loader2 className="h-2.5 w-2.5 animate-spin" />
                                      pending
                                    </span>
                                  )}
                                  {doc.status === "failed" && (
                                    <span className="bg-red-500/10 border border-red-500/20 text-red-400 px-2 py-0.5 rounded-full text-[10px] font-medium font-mono uppercase" title={doc.failure_reason || doc.error_message}>
                                      failed
                                    </span>
                                  )}
                                </td>
                                <td className="py-3 px-4">
                                  <div className="flex items-center justify-end gap-1.5">
                                    {doc.status === "failed" && (
                                      <button onClick={() => handleDocAction(doc.id, "processing")} className="p-1.5 border border-amber-500/10 hover:border-amber-500/30 rounded-lg hover:bg-amber-500/10 text-amber-400 hover:text-amber-300 transition focus:outline-none" title="Re-process" data-testid={`reprocess-btn-${doc.id}`}>
                                        <RotateCcw className="h-3.5 w-3.5" />
                                      </button>
                                    )}
                                    {doc.status === "pending" && (
                                      <button onClick={() => handleDocAction(doc.id, "failed", { failure_reason: "Manually marked failed by admin" })} className="p-1.5 border border-red-500/10 hover:border-red-500/30 rounded-lg hover:bg-red-500/10 text-red-400 hover:text-red-300 transition focus:outline-none" title="Mark failed" data-testid={`fail-btn-${doc.id}`}>
                                        <XCircle className="h-3.5 w-3.5" />
                                      </button>
                                    )}
                                    {doc.status !== "archived" && (
                                      <button onClick={() => handleDocAction(doc.id, "archive")} className="p-1.5 border border-slate-500/10 hover:border-slate-500/30 rounded-lg hover:bg-slate-500/10 text-slate-400 hover:text-slate-300 transition focus:outline-none" title="Archive" data-testid={`archive-btn-${doc.id}`}>
                                        <Archive className="h-3.5 w-3.5" />
                                      </button>
                                    )}
                                    <button onClick={() => handleDeleteDoc(doc.id, doc.title)} className="p-1.5 border border-red-500/10 hover:border-red-500/30 rounded-lg hover:bg-red-500/10 text-red-400 hover:text-red-300 transition focus:outline-none" title="Delete" data-testid={`delete-btn-${doc.id}`}>
                                      <Trash2 className="h-3.5 w-3.5" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* TABS 3: WIDGET CONFIG */}
        {activeTab === "widget" && (
          <div className="space-y-6 animate-fadeIn" data-testid="view-widget">
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
              {/* Properties Form (Left columns) */}
              <div className="lg:col-span-2 space-y-6">
                <form onSubmit={handleUpdateWidget} className="glassmorphism rounded-2xl p-6 border-white/10 space-y-5">
                  <h3 className="font-semibold text-sm text-white mb-2 flex items-center gap-2">
                    <Sliders className="h-4 w-4 text-[#00D4FF]" />
                    <span>Widget Appearance Settings</span>
                  </h3>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Greeting Prompt</label>
                      <input
                        type="text"
                        value={greetingMsg}
                        onChange={(e) => setGreetingMsg(e.target.value)}
                        className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                        data-testid="widget-greeting-input"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Theme</label>
                      <select
                        value={themeColor.startsWith("#") ? "light" : themeColor}
                        onChange={(e) => setThemeColor(e.target.value)}
                        className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                      >
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </select>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Launcher Label</label>
                      <input
                        type="text"
                        value={launcherLabel}
                        onChange={(e) => setLauncherLabel(e.target.value)}
                        className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                        data-testid="widget-launcher-label"
                      />
                    </div>

                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Placeholder Text</label>
                      <input
                        type="text"
                        value={placeholderText}
                        onChange={(e) => setPlaceholderText(e.target.value)}
                        className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                      />
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="widget-enabled"
                      checked={isWidgetEnabled}
                      onChange={(e) => setIsWidgetEnabled(e.target.checked)}
                      className="h-4 w-4 rounded border-white/10 bg-[#0B1221] text-[#00D4FF] focus:ring-[#00D4FF]"
                    />
                    <label htmlFor="widget-enabled" className="text-xs text-slate-300">
                      Widget is enabled and visible
                    </label>
                  </div>

                  <div className="pt-4 border-t border-white/5 flex items-center justify-end">
                    <button
                      type="submit"
                      className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#00D4FF] text-[#040914] font-bold text-xs tracking-wider uppercase hover:scale-[1.02] active:scale-[0.98] transition cursor-pointer"
                      data-testid="widget-save-btn"
                    >
                      Save Appearance Contract
                    </button>
                  </div>
                </form>

                {/* API Key Credentials snippet */}
                <div className="glassmorphism rounded-2xl p-6 border-white/10 space-y-4">
                  <h3 className="font-semibold text-sm text-white mb-2 flex items-center gap-2">
                    <Terminal className="h-4 w-4 text-[#00D4FF]" />
                    <span>Widget Embed Credentials</span>
                  </h3>

                  <div className="space-y-1">
                    <span className="block text-[10px] text-slate-400 uppercase font-bold">Generated Widget Public Key</span>
                    <div className="flex items-center gap-3 bg-[#0B1221] border border-white/10 rounded-xl p-3">
                      <code className="text-slate-300 font-mono text-xs select-all flex-1" data-testid="widget-api-key">
                        {widgetCfg?.public_key || "wk_xxxxxxxxxxxxxxxx"}
                      </code>
                      <button
                        onClick={() => copyToClipboard(widgetCfg?.public_key, "key")}
                        className="text-slate-400 hover:text-white transition p-1 hover:bg-white/5 rounded"
                      >
                        {copiedKey ? <Check className="h-4 w-4 text-emerald-400" /> : <Copy className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>

                  <div className="space-y-1">
                    <span className="block text-[10px] text-slate-400 uppercase font-bold">Copy Embedding script tag</span>
                    <div className="relative">
                      <pre
                        className="bg-[#0B1221] border border-white/10 rounded-xl p-4 text-[11px] text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed select-all"
                        data-testid="widget-snippet"
                      >
                        {embedSnippetHtml}
                      </pre>
                      <button
                        onClick={() => copyToClipboard(embedSnippetHtml, "snippet")}
                        className="absolute top-3 right-3 text-slate-400 hover:text-white transition p-1.5 bg-white/5 hover:bg-white/10 rounded-lg border border-white/10"
                        title="Copy code snippet"
                      >
                        {copiedSnippet ? <Check className="h-3.5 w-3.5 text-emerald-400" /> : <Copy className="h-3.5 w-3.5" />}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Live Preview (Right columns) */}
              <div className="lg:col-span-1 glassmorphism rounded-2xl p-6 border-white/10 space-y-4">
                <h3 className="font-semibold text-sm text-white mb-2 flex items-center gap-2">
                  <Eye className="h-4 w-4 text-[#00D4FF]" />
                  <span>Interactive Live Preview</span>
                </h3>

                <div className="border border-white/10 rounded-2xl overflow-hidden bg-[#040914] shadow-inner h-96 relative flex flex-col">
                  {/* Fake widget top bar */}
                  <div
                    className="p-3 text-xs text-[#040914] font-bold flex items-center justify-between"
                    style={{ backgroundColor: themeColor }}
                  >
                    <span className="tracking-tight truncate">{app.name}</span>
                    <div className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></div>
                  </div>

                  {/* Fake widget message body */}
                  <div className="flex-1 p-4 space-y-3 overflow-y-auto">
                    <div className="flex gap-2">
                      <div className="h-6 w-6 rounded-full bg-slate-800 flex items-center justify-center text-[10px] text-white flex-shrink-0">🤖</div>
                      <div className="bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-[10px] text-slate-300 leading-relaxed max-w-[80%]">
                        {greetingMsg || "Hello! Ask me anything."}
                      </div>
                    </div>
                  </div>

                  {/* Fake input form */}
                  <div className="p-3 border-t border-white/10 flex items-center gap-2 bg-[#0B1221]">
                    <div className="flex-1 bg-white/5 rounded-lg px-2.5 py-1.5 text-[9px] text-slate-500">
                      {placeholderText}
                    </div>
                    <div
                      className="h-6 w-12 rounded-lg flex items-center justify-center text-[9px] font-bold text-center"
                      style={{ backgroundColor: themeColor, color: "#040914" }}
                    >
                      SEND
                    </div>
                  </div>

                  {/* Widget Launch Circle */}
                  <div
                    className={`absolute bottom-4 right-4 h-11 w-11 rounded-full flex items-center justify-center text-lg shadow-xl border border-white/10`}
                    style={{ backgroundColor: themeColor, color: "#040914" }}
                  >
                    💬
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TABS 4: CHAT TESTING SANDBOX */}
        {activeTab === "chat" && (
          <div className="space-y-6 animate-fadeIn" data-testid="view-chat">
            {/* Context status */}
            <div className="glassmorphism rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4 text-xs">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-[#00D4FF]" />
                <span className="font-semibold text-slate-200">Sandbox Testing Layer</span>
                <span className="text-slate-500">•</span>
                <span className="text-slate-400">Target contract: `POST /api/client/chat/messages`</span>
              </div>

              <div className="flex items-center gap-4">
                {/* API Key input for sandbox */}
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => setShowSandboxKeyInput(!showSandboxKeyInput)}
                    className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border transition ${
                      sandboxApiKey
                        ? "border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/10"
                        : "border-amber-500/30 text-amber-400 hover:bg-amber-500/10"
                    }`}
                    title={sandboxApiKey ? "API key configured" : "Set API key (akp_...)"}
                    data-testid="sandbox-api-key-toggle"
                  >
                    <KeyRound className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline font-medium">{sandboxApiKey ? "Key Set" : "Set API Key"}</span>
                  </button>
                  {showSandboxKeyInput && (
                    <input
                      type="text"
                      value={sandboxApiKey}
                      onChange={(e) => {
                        setSandboxApiKey(e.target.value);
                        localStorage.setItem("oceanrag_sandbox_api_key", e.target.value);
                      }}
                      placeholder="akp_..."
                      className="w-40 bg-slate-900 border border-white/10 rounded-md py-1 px-2 text-white font-mono text-[10px] focus:ring-1 focus:ring-[#00D4FF] focus:outline-none"
                      data-testid="sandbox-api-key-input"
                    />
                  )}
                </div>

                <div className="flex items-center gap-1.5 text-xs text-slate-400">
                  <span>Retrieve top_k chunks:</span>
                  <select
                    value={chatTopK}
                    onChange={(e) => setChatTopK(Number(e.target.value))}
                    className="bg-slate-900 border border-white/10 rounded-md py-0.5 px-1.5 text-white font-medium text-xs focus:ring-1 focus:ring-[#00D4FF] focus:outline-none"
                  >
                    <option value={2}>2</option>
                    <option value={4}>4</option>
                    <option value={6}>6</option>
                  </select>
                </div>

                <button
                  onClick={() => { setSandboxHistory([]); toast.success("Sandbox history reset."); }}
                  className="text-red-400 hover:text-red-300 font-medium text-xs py-1"
                  data-testid="chat-sandbox-clear"
                >
                  Clear Sandbox
                </button>
              </div>
            </div>

            {/* Simulated Chat Interface */}
            <div className="border border-white/10 rounded-2xl h-[450px] bg-[#0B1221]/30 flex flex-col justify-between overflow-hidden shadow-xl">
              {/* Sandbox Logs */}
              <div className="flex-1 p-5 overflow-y-auto space-y-4">
                {sandboxHistory.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center py-10">
                    <div className="h-10 w-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-slate-500 mb-3 animate-pulse">
                      ⚡
                    </div>
                    <h4 className="font-semibold text-slate-300 text-xs">Awaiting Query Input</h4>
                    <p className="text-[10px] text-slate-500 max-w-sm mt-1">
                      Execute testing prompts to query matching vector chunks from active document matrices.
                    </p>
                  </div>
                ) : (
                  sandboxHistory.map((m, idx) => (
                    <div key={idx} className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}>
                      <div className="flex items-center gap-2 mb-1 text-[10px] text-slate-500 px-1">
                        <span>{m.role === "user" ? "Client" : "API Response"}</span>
                        <span>•</span>
                        <span>{new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                      </div>

                      <div className="flex gap-2 max-w-[85%]">
                        <div
                          className={`rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                            m.role === "user"
                              ? "bg-[#2563EB] text-white rounded-tr-none border border-white/5"
                              : "glassmorphism rounded-tl-none border-white/10"
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{m.content}</p>
                        </div>
                      </div>

                      {/* Display Matching Groundings */}
                      {m.role === "bot" && m.sources && m.sources.length > 0 && (
                        <div className="mt-2 pl-4 max-w-[85%] space-y-2">
                          <span className="block text-[9px] text-[#00D4FF] font-semibold uppercase tracking-wider">Matched Chunks Sources:</span>
                          {m.sources.map((s, sIdx) => (
                            <div key={sIdx} className="bg-[#040914]/80 border border-white/5 rounded-xl p-2.5 text-[10px] text-slate-400">
                              <div className="flex justify-between items-center mb-1 text-[9px] text-slate-500 font-semibold font-mono border-b border-white/5 pb-1">
                                <span>{s.document_id}</span>
                                <span className="text-[#00D4FF]">Chunk: {s.chunk_id}</span>
                              </div>
                              <p className="italic font-mono text-[9px] text-slate-300">{s.title}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  ))
                )}

                {isChatLoading && (
                  <div className="flex flex-col items-start">
                    <div className="flex items-center gap-2 mb-1 text-[10px] text-slate-500">
                      <span>RAG Engine</span>
                      <span>•</span>
                      <span className="italic">Searching indexes...</span>
                    </div>
                    <div className="glassmorphism rounded-2xl rounded-tl-none px-4 py-3 border-white/10 flex items-center gap-2">
                      <Loader2 className="h-3.5 w-3.5 text-[#00D4FF] animate-spin" />
                      <span className="text-[10px] text-slate-400 font-mono">Retrieving high-dimensional match dimensions...</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Sandbox Input Form */}
              <form
                onSubmit={handleChatTest}
                className="p-3 border-t border-white/10 bg-[#0B1221] flex items-center gap-3"
              >
                <input
                  type="text"
                  value={sandboxQuestion}
                  onChange={(e) => setSandboxQuestion(e.target.value)}
                  placeholder="Ask testing questions about indexed documents..."
                  className="flex-1 bg-[#040914]/50 border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-3 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                  data-testid="chat-sandbox-input"
                  required
                />
                <button
                  type="submit"
                  disabled={isChatLoading || !sandboxQuestion.trim()}
                  className={`h-11 px-5 rounded-xl flex items-center justify-center gap-2 transition duration-300 ${
                    isChatLoading || !sandboxQuestion.trim()
                      ? "bg-white/5 border border-white/5 text-slate-500 cursor-not-allowed"
                      : "bg-[#00D4FF] text-[#040914] hover:bg-white hover:text-[#040914] font-bold text-xs tracking-wider uppercase shadow-md cursor-pointer"
                  }`}
                  data-testid="chat-sandbox-submit"
                >
                  <span>Verify</span>
                  <Play className="h-3.5 w-3.5" />
                </button>
              </form>
            </div>
          </div>
        )}

        {/* TABS 5: CONVERSATIONS */}
        {activeTab === "conversations" && (
          <ConversationsTab applicationId={id} />
        )}

        {/* TABS 6: SETTINGS */}
        {activeTab === "settings" && (
          <form onSubmit={handleUpdateSettings} className="glassmorphism rounded-2xl p-6 border-white/10 space-y-6 animate-fadeIn" data-testid="view-settings">
            <h3 className="font-semibold text-sm text-white mb-2 flex items-center gap-2">
              <Sliders className="h-4 w-4 text-[#00D4FF]" />
              <span>RAG Settings & Parameter Core</span>
            </h3>

            {!settings && (
              <div className="text-center py-8 text-slate-400 text-xs">
                No settings configured yet. Create settings by submitting this form.
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">LLM Temperature</label>
                <input
                  type="text"
                  value={settings?.llm_temperature || "0.2"}
                  onChange={(e) => setSettings({ ...settings, llm_temperature: e.target.value })}
                  className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                  data-testid="settings-temperature"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Max Context Messages</label>
                <input
                  type="number"
                  value={settings?.max_context_messages || 12}
                  onChange={(e) => setSettings({ ...settings, max_context_messages: parseInt(e.target.value) })}
                  min="1"
                  max="100"
                  className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Inactivity Timeout (minutes)</label>
                <input
                  type="number"
                  value={settings?.inactivity_timeout_minutes || 30}
                  onChange={(e) => setSettings({ ...settings, inactivity_timeout_minutes: parseInt(e.target.value) })}
                  min="1"
                  max="10080"
                  className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">Retention Days</label>
                <input
                  type="number"
                  value={settings?.retention_days || 30}
                  onChange={(e) => setSettings({ ...settings, retention_days: parseInt(e.target.value) })}
                  min="1"
                  max="3650"
                  className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                />
              </div>
            </div>

            <div>
              <label className="block text-[10px] font-bold text-slate-400 uppercase mb-1.5">System Grounding Prompt Instructions</label>
              <textarea
                value={settings?.prompt_system_template || ""}
                onChange={(e) => setSettings({ ...settings, prompt_system_template: e.target.value })}
                rows={5}
                className="w-full bg-[#0B1221] border border-white/10 focus:border-[#00D4FF] text-white text-xs rounded-xl px-4 py-2.5 outline-none focus:ring-1 focus:ring-[#00D4FF] transition resize-none font-mono leading-relaxed"
                data-testid="settings-system-prompt"
              />
            </div>

            <div className="pt-4 border-t border-white/5 flex items-center justify-end">
              <button
                type="submit"
                className="px-5 py-2.5 rounded-xl bg-gradient-to-r from-[#2563EB] to-[#00D4FF] text-[#040914] font-bold text-xs tracking-wider uppercase hover:scale-[1.02] active:scale-[0.98] transition cursor-pointer"
                data-testid="settings-save-btn"
              >
                Save Parameter Core
              </button>
            </div>
          </form>
        )}
      </div>
    </main>
  );
}