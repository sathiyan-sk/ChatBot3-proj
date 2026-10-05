import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "@/api/client";
import {
  ArrowLeft, Database, MessageSquare, Settings, Play,
  Trash2, Copy, Check, UploadCloud, FileText,
  Sparkles, Sliders, Globe, Eye, Terminal, RefreshCw,
  Plus, Archive, RotateCcw, XCircle, KeyRound, Pencil, Power,
} from "lucide-react";
import { toast } from "sonner";
import ConversationsTab from "@/components/ConversationsTab";

import { Button, Badge, Card, Spinner, ErrorBanner } from "@/components/ui/Primitives";
import { PageShell, PageHeader, SectionHeader } from "@/components/ui/Layout";
import { EmptyState } from "@/components/ui/Stats";
import { Modal, ConfirmDialog } from "@/components/ui/Overlays";
import { Tabs } from "@/components/ui/Tabs";
import { Field, Input, Textarea, Select, CheckboxRow, InsetWell } from "@/components/ui/Form";
import { ColorPicker } from "@/components/ui/ColorPicker";
import { StarterPrompts } from "@/components/ui/StarterPrompts";
import { DEFAULT_WIDGET_ACCENT, readableTextOn } from "@/components/ui/colorUtils";

// Default starter prompts shown in the widget until the admin customises them.
const DEFAULT_STARTER_PROMPTS = [
  "How do I upgrade my plan?",
  "Reset my API key",
  "What is your refund policy?",
];

/* ============================================================
   APPLICATION DETAIL
   Six-tab workspace: General, Knowledge Base, Widget Config,
   Chat Sandbox, Conversations, Settings. Rebuilt on the shared
   UI kit (cards, tabs, form controls, confirm dialog) while
   keeping every backend interaction and data-testid intact.
   ============================================================ */

const TAB_ITEMS = [
  { key: "general", label: "General", icon: Sparkles, testId: "tab-general" },
  { key: "kb", label: "Knowledge Base", icon: Database, testId: "tab-kb" },
  { key: "widget", label: "Widget Config", icon: Globe, testId: "tab-widget" },
  { key: "chat", label: "Chat Testing", icon: MessageSquare, testId: "tab-chat" },
  { key: "conversations", label: "Conversations", icon: MessageSquare, testId: "tab-conversations" },
  { key: "settings", label: "Settings", icon: Settings, testId: "tab-settings" },
];

const DOC_STATUS = {
  ready: { variant: "success", label: "ready" },
  processing: { variant: "warning", label: "processing" },
  pending: { variant: "accent", label: "pending" },
  failed: { variant: "danger", label: "failed" },
  archived: { variant: "neutral", label: "archived" },
};

// Preview theme tokens mirroring the real widget.css CSS variables so the
// Live Preview reflects the ACTUAL light/dark appearance (panel background,
// bubbles, input, footer and launcher), not just the header colour.
const PREVIEW_THEMES = {
  light: {
    panelBg: "rgba(255,255,255,0.97)",
    panelBorder: "rgba(15,23,42,0.08)",
    headerBg: "#00D4FF",
    headerText: "#040914",
    bodyText: "#0f172a",
    mutedText: "#64748b",
    botBubbleBg: "#f1f5f9",
    botBubbleBorder: "rgba(15,23,42,0.06)",
    inputBg: "#f8fafc",
    inputBorder: "rgba(15,23,42,0.12)",
    footerBg: "#f8fafc",
    accent: "#00D4FF",
    accentContrast: "#040914",
  },
  dark: {
    panelBg: "rgba(11,18,33,0.96)",
    panelBorder: "rgba(255,255,255,0.08)",
    headerBg: "#1a1a1a",
    headerText: "#ffffff",
    bodyText: "#e2e8f0",
    mutedText: "#94a3b8",
    botBubbleBg: "rgba(255,255,255,0.04)",
    botBubbleBorder: "rgba(255,255,255,0.08)",
    inputBg: "rgba(4,9,20,0.6)",
    inputBorder: "rgba(255,255,255,0.08)",
    footerBg: "#0b1221",
    accent: "#00D4FF",
    accentContrast: "#040914",
  },
};

export default function ApplicationDetail() {
  const { id } = useParams();
  const [app, setApp] = useState(null);
  const [activeTab, setActiveTab] = useState("general");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

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
  const [sandboxApiKey, setSandboxApiKey] = useState(
    () => localStorage.getItem("oceanrag_sandbox_api_key") || ""
  );
  const [showSandboxKeyInput, setShowSandboxKeyInput] = useState(false);

  // Widget appearance configurations
  const [greetingMsg, setGreetingMsg] = useState("");
  // Theme is stored as the semantic value (light/dark) that the
  // backend persists - NOT a hex color. The preview maps theme -> color.
  const [widgetTheme, setWidgetTheme] = useState("light");
  const [launcherLabel, setLauncherLabel] = useState("Chat with us");
  const [placeholderText, setPlaceholderText] = useState("Type your message...");
  const [isWidgetEnabled, setIsWidgetEnabled] = useState(true);

  // Accent colour is loaded from and saved to the widgets API.
  const [widgetAccent, setWidgetAccent] = useState(DEFAULT_WIDGET_ACCENT);

  // Starter prompt chips. Persisted via the widgets API (starter_prompts).
  const [starterPrompts, setStarterPrompts] = useState(DEFAULT_STARTER_PROMPTS);

  // Ingestion upload states
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isRebuilding, setIsRebuilding] = useState(false);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [websiteTitle, setWebsiteTitle] = useState("");

  // Copy states
  const [copiedSnippet, setCopiedSnippet] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  // Delete confirmation (replaces window.confirm)
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [isDeleting, setIsDeleting] = useState(false);

  // Edit application modal
  const [showEditModal, setShowEditModal] = useState(false);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formClientType, setFormClientType] = useState("website");
  const [formOrigins, setFormOrigins] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const fetchAppData = async () => {
    setIsLoading(true);
    setLoadError(null);
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
          setWidgetTheme(widgetRes.data.theme === "dark" ? "dark" : "light");
          setLauncherLabel(widgetRes.data.launcher_label || "Chat with us");
          setPlaceholderText(widgetRes.data.placeholder_text || "Type your message...");
          setIsWidgetEnabled(widgetRes.data.is_enabled);
          setWidgetAccent(widgetRes.data.accent_color || DEFAULT_WIDGET_ACCENT);
          // Backend-persisted starter prompt chips.
          if (Array.isArray(widgetRes.data.starter_prompts)) {
            setStarterPrompts(widgetRes.data.starter_prompts);
          }
        } catch (error) {
          if (error.response?.status !== 404) {
            console.warn("Failed to load widget configuration for this application", error);
          }
          setWidgetCfg(null);
          setGreetingMsg("");
          setWidgetTheme("light");
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
        setLoadError("Application namespace not found.");
        toast.error("Application namespace not found.");
      }
    } catch (e) {
      console.error("Failed to load application profile.", e);
      setLoadError(
        e.response?.data?.detail || "Failed to load application profile."
      );
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

    const unfinished = documents.some(
      (d) => d.status === "pending" || d.status === "processing"
    );
    if (unfinished) {
      const interval = setInterval(async () => {
        try {
          const docsRes = await apiClient.get(
            `/admin/documents?knowledge_base_id=${knowledgeBase.id}`
          );
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
          llm_temperature: settings?.llm_temperature ?? "0.2",
          max_context_messages: settings?.max_context_messages ?? 12,
          inactivity_timeout_minutes: settings?.inactivity_timeout_minutes ?? 30,
          retention_days: settings?.retention_days ?? 30,
          prompt_system_template: settings?.prompt_system_template ?? null,
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
          theme: widgetTheme,
          launcher_label: launcherLabel,
          welcome_message: greetingMsg,
          placeholder_text: placeholderText,
          accent_color: widgetAccent,
          starter_prompts: starterPrompts,
          is_enabled: isWidgetEnabled,
        });
      } else {
        try {
          // Create new widget
          await apiClient.post("/admin/widgets", {
            application_id: id,
            display_name: app?.name || "Support Widget",
            theme: widgetTheme,
            launcher_label: launcherLabel,
            welcome_message: greetingMsg,
            placeholder_text: placeholderText,
            accent_color: widgetAccent,
            starter_prompts: starterPrompts,
            is_enabled: isWidgetEnabled,
          });
        } catch (error) {
          if (error.response?.status === 409) {
            const existing = await apiClient.get(`/admin/widgets/application/${id}`);
            await apiClient.put(`/admin/widgets/${existing.data.id}`, {
              display_name: existing.data.display_name || app?.name || "Support Widget",
              theme: widgetTheme,
              launcher_label: launcherLabel,
              welcome_message: greetingMsg,
              placeholder_text: placeholderText,
              accent_color: widgetAccent,
              starter_prompts: starterPrompts,
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
  const getDocumentActionError = (error, fallback) => {
    const detail =
      error.response?.data?.error?.message ||
      error.response?.data?.detail?.message ||
      error.response?.data?.detail;
    return typeof detail === "string" ? detail : fallback;
  };

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
      await apiClient.post("/admin/documents/upload", form);
      toast.success(`"${file.name}" uploaded; ingestion has been queued.`);
      // Refresh documents
      const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
      setDocuments(docsRes.data);
    } catch (e) {
      console.error(e);
      toast.error(getDocumentActionError(e, "File upload or ingestion scheduling failed."));
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

  // Opens the styled confirmation dialog instead of window.confirm
  const handleDeleteDoc = (docId, name) => {
    setDeleteTarget({ id: docId, name });
  };

  const performDeleteDoc = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await apiClient.delete(`/admin/documents/${deleteTarget.id}`);
      toast.success(`Removed "${deleteTarget.name}" from directory.`);
      setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      setDeleteTarget(null);
    } catch (e) {
      console.error(e);
      toast.error("Un-indexing file failed.");
    } finally {
      setIsDeleting(false);
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
      let alreadyProcessing = 0;
      let failed = 0;
      for (const doc of targets) {
        try {
          await apiClient.post("/admin/ingestion/start", {
            document_id: doc.id,
          });
          queued += 1;
        } catch (docErr) {
          if (docErr.response?.status === 409) {
            alreadyProcessing += 1;
          } else {
            failed += 1;
          }
          console.error(`Reindex failed for document ${doc.id}`, docErr);
        }
      }
      if (queued > 0) {
        const details = [
          alreadyProcessing ? `${alreadyProcessing} already processing` : null,
          failed ? `${failed} could not be queued` : null,
        ].filter(Boolean).join("; ");
        toast.success(`Vector rebuild queued for ${queued} document(s)!`, {
          description: details || undefined,
        });
      } else if (alreadyProcessing > 0 || failed > 0) {
        toast.error("No documents were queued for rebuild.", {
          description: [
            alreadyProcessing ? `${alreadyProcessing} already processing` : null,
            failed ? `${failed} failed to queue` : null,
          ].filter(Boolean).join("; "),
        });
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
      if (action === "processing") {
        await apiClient.post("/admin/ingestion/start", {
          document_id: docId,
        });
        toast.success("Document reprocessing started.");
      } else {
        await apiClient.post(`/admin/documents/${docId}/${action}`, extra);
        toast.success(`Document marked as ${action}.`);
      }
      if (knowledgeBase?.id) {
        const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
        setDocuments(docsRes.data);
      }
    } catch (e) {
      console.error(e);
      toast.error(getDocumentActionError(e, `Failed to ${action} document.`));
    }
  };

  // Accent changes preview immediately and are persisted when the form is saved.
  const handleAccentChange = (hex) => {
    setWidgetAccent(hex);
  };

  // Open the edit modal pre-filled from the loaded application
  const openEditModal = () => {
    setFormName(app.name || "");
    setFormDesc(app.description || "");
    setFormClientType(app.client_type || "website");
    setFormOrigins((app.allowed_origins || []).join(", "));
    setShowEditModal(true);
  };

  const handleEditSubmit = async (e) => {
    e.preventDefault();
    if (!formName.trim() || isSaving) return;
    setIsSaving(true);
    try {
      const originsArray = formOrigins
        .split(",")
        .map((o) => o.trim())
        .filter(Boolean);
      await apiClient.put(`/admin/applications/${id}`, {
        name: formName.trim(),
        description: formDesc.trim() || null,
        client_type: formClientType,
        allowed_origins: originsArray,
        is_active: app.is_active,
      });
      toast.success(`Application "${formName.trim()}" updated.`);
      setShowEditModal(false);
      fetchAppData();
    } catch (e) {
      console.error(e);
      toast.error(e.response?.data?.detail || "Failed to update application.");
    } finally {
      setIsSaving(false);
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
      timestamp: new Date().toISOString(),
    };
    setSandboxHistory((prev) => [...prev, userMsg]);
    setSandboxQuestion("");
    setIsChatLoading(true);

    try {
      const response = await apiClient.post(
        "/client/chat/messages",
        {
          conversation_identity: `sandbox-${id}`,
          message: userMsg.content,
          conversation_title: "Admin Sandbox Test",
          top_k: chatTopK,
        },
        {
          headers: {
            "X-API-Key": sandboxApiKey || "",
          },
        }
      );

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
      const detail =
        e.response?.data?.error?.message ||
        e.response?.data?.detail?.message ||
        e.response?.data?.detail;
      toast.error(
        typeof detail === "string"
          ? detail
          : "RAG chat connection failed. Check the API key, application status, and backend logs."
      );
    } finally {
      setIsChatLoading(false);
    }
  };

  // Embed Snippet
  // Widget script is served from FRONTEND (at /widget) for better separation of concerns
  // Backend URL is used for API calls (configuration + chat messages + CORS validation)
  const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
  // Widget URL - for development use localhost:5173, for production use the same origin as the admin page
  const FRONTEND_URL =
    import.meta.env.VITE_FRONTEND_URL ||
    (typeof window !== "undefined"
      ? `${window.location.protocol}//${window.location.host}`
      : "http://localhost:5173");

  // Resolve the full preview palette from the selected theme so the
  // Live Preview visibly switches between light and dark.
  const pv = PREVIEW_THEMES[widgetTheme === "dark" ? "dark" : "light"];

  // The accent colour drives the launcher + send button in BOTH themes, and
  // the header background in light theme (matching the real widget.css).
  const accentColor = widgetAccent || pv.accent;
  const accentContrast = readableTextOn(accentColor);
  const previewColor = widgetTheme === "dark" ? pv.headerBg : accentColor;
  const previewHeaderTextColor = widgetTheme === "dark" ? pv.headerText : accentContrast;

  const embedSnippetHtml = widgetCfg
    ? `<!-- OceanRAG Embeddable Widget Snippet -->
<script>
  // SECURITY: widgetKey is the only credential needed for authentication
  // Backend resolves the application from the widget key - appId is for reference only
  window.OceanRAGWidgetConfig = {
    widgetKey: "${widgetCfg.public_key || "wk_xxxxxxxx"}",
    appId: "${id}",  // Reference only - NOT used for security/authorization
    backendUrl: "${BACKEND_URL}"
  };
</script>
<script src="${FRONTEND_URL}/widget/widget.js?v=4" async></script>`
    : "";

  const copyToClipboard = (text, type) => {
    if (!text) {
      toast.error("Nothing to copy yet.");
      return;
    }
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

  /* ---------------- loading / error states ---------------- */

  if (isLoading) {
    return (
      <PageShell>
        <div className="flex items-center justify-center min-h-[420px]">
          <Spinner className="h-9 w-9" />
        </div>
      </PageShell>
    );
  }

  if (!app) {
    return (
      <PageShell className="space-y-6">
        <Link
          to="/admin/applications"
          className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-slate-400 hover:text-[#00D4FF] transition"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to applications</span>
        </Link>
        <ErrorBanner
          title="Application not found"
          message={loadError || "This application namespace does not exist or was removed."}
          onRetry={fetchAppData}
        />
      </PageShell>
    );
  }

  const readyCount = documents.filter((d) => d.status === "ready").length;

  return (
    <PageShell className="space-y-6">
      <PageHeader
        breadcrumb={[
          { label: "Applications", to: "/admin/applications" },
          { label: app.name },
        ]}
        eyebrow="Application Workspace"
        title={app.name}
        subtitle={app.description || "No description provided for this namespace."}
        actions={
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={handleToggleActive}
              data-testid="toggle-active-btn"
              title={app.is_active ? "Deactivate" : "Activate"}
            >
              <Power className="h-3.5 w-3.5" />
              <span>{app.is_active ? "Deactivate" : "Activate"}</span>
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={openEditModal}
              data-testid="edit-app-btn"
            >
              <Pencil className="h-3.5 w-3.5" />
              <span>Edit</span>
            </Button>
          </>
        }
      />

      <Tabs tabs={TAB_ITEMS} value={activeTab} onChange={setActiveTab} />

      <div className="w-full">
        {/* ======================= TAB: GENERAL ======================= */}
        {activeTab === "general" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-fadeIn" data-testid="view-general">
            <Card className="lg:col-span-2 p-6">
              <SectionHeader title="Application Summary" className="mb-4" />
              <p className="text-body text-slate-400">
                {app.description || "No description provided."}
              </p>

              {/* API Key Prefix section */}
              <div className="mt-5 pt-4 border-t border-white/[0.06]">
                <div className="flex items-center gap-2 mb-2">
                  <KeyRound className="h-3.5 w-3.5 text-slate-500" aria-hidden="true" />
                  <span className="text-eyebrow text-slate-400">API Key Prefix</span>
                </div>
                <div className="flex items-center gap-2.5">
                  <code
                    className="text-slate-300 font-mono text-[12px] break-all"
                    data-testid="api-key-prefix-display"
                  >
                    {app.api_key_prefix ? app.api_key_prefix : "akp_••••••••••"}
                  </code>
                  <button
                    onClick={() => copyToClipboard(app.api_key_prefix || "akp_••••••••••")}
                    className="text-slate-400 hover:text-white transition p-1 rounded-[8px] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
                    title="Copy API key prefix"
                    data-testid="copy-key-prefix-btn"
                  >
                    {copiedKey ? (
                      <Check className="h-3.5 w-3.5 text-emerald-400" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </button>
                </div>
                <p className="text-[10px] text-slate-500 mt-2">
                  The full API key was shown only at creation time. This is a read-only reference prefix.
                </p>
              </div>

              <div className="mt-6 pt-5 border-t border-white/[0.06] grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
                <div>
                  <span className="block text-slate-500 font-medium text-[10px] uppercase tracking-wider">Slug</span>
                  <span className="block text-slate-300 font-mono mt-1 truncate">{app.slug}</span>
                </div>
                <div>
                  <span className="block text-slate-500 font-medium text-[10px] uppercase tracking-wider">Client Type</span>
                  <span className="block text-[#00D4FF] font-mono mt-1 capitalize">{app.client_type}</span>
                </div>
                <div>
                  <span className="block text-slate-500 font-medium text-[10px] uppercase tracking-wider">Status</span>
                  <span className={`block font-mono mt-1 ${app.is_active ? "text-emerald-400" : "text-red-400"}`}>
                    {app.is_active ? "Active" : "Inactive"}
                  </span>
                </div>
                <div>
                  <span className="block text-slate-500 font-medium text-[10px] uppercase tracking-wider">Created</span>
                  <span className="block text-slate-300 font-mono mt-1">
                    {new Date(app.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div>
                  <span className="block text-slate-500 font-medium text-[10px] uppercase tracking-wider">Updated</span>
                  <span className="block text-slate-300 font-mono mt-1">
                    {new Date(app.updated_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="md:col-span-3">
                  <span className="block text-slate-500 font-medium text-[10px] uppercase tracking-wider">Allowed Origins</span>
                  <span className="block text-slate-300 font-mono mt-1 break-all">
                    {(app.allowed_origins || []).length > 0
                      ? app.allowed_origins.join(", ")
                      : "All origins allowed"}
                  </span>
                </div>
              </div>
            </Card>

            {/* Status Health Widget */}
            <Card className="p-6 flex flex-col justify-between">
              <div>
                <SectionHeader title="Ingestion Pipelines" className="mb-4" />
                <div className="space-y-3 text-xs">
                  <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                    <span className="text-slate-400">Total documents</span>
                    <span className="font-bold text-white font-mono">{documents.length}</span>
                  </div>
                  <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                    <span className="text-emerald-400">Indexed (RAG ground)</span>
                    <span className="font-bold text-emerald-400 font-mono">{readyCount}</span>
                  </div>
                </div>
              </div>

              <div className="pt-4 border-t border-white/[0.06] text-[10px] text-slate-500 font-mono flex items-center gap-1.5 mt-4">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span>Isolated FAISS database: active</span>
              </div>
            </Card>
          </div>
        )}

        {/* ======================= TAB: KNOWLEDGE BASE ======================= */}
        {activeTab === "kb" && (
          <div className="space-y-6 animate-fadeIn" data-testid="view-kb">
            {!knowledgeBase ? (
              <EmptyState
                icon={Database}
                title="No knowledge base found"
                message="Create a knowledge base for this application before uploading documents."
                action={
                  <Button onClick={handleCreateKB} data-testid="create-kb-btn">
                    <Plus className="h-4 w-4" />
                    <span>Create Knowledge Base</span>
                  </Button>
                }
              />
            ) : (
              <>
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <SectionHeader
                      title="Document Source Registry"
                      hint="PDF guides, text rules and FAQs"
                    />
                    <span role="status" aria-live="polite" className="sr-only">
                      {documents.length} documents,{" "}
                      {
                        documents.filter(
                          (d) => d.status === "pending" || d.status === "processing"
                        ).length
                      }{" "}
                      processing
                    </span>
                  </div>
                  <Button
                    onClick={handleReindex}
                    disabled={isRebuilding || documents.length === 0}
                    loading={isRebuilding}
                    className="uppercase tracking-wider self-start md:self-auto"
                    data-testid="reindex-btn"
                  >
                    {isRebuilding ? (
                      <span>Syncing FAISS database...</span>
                    ) : (
                      <>
                        <RefreshCw className="h-3.5 w-3.5" />
                        <span>Rebuild Vector Space</span>
                      </>
                    )}
                  </Button>
                </div>

                {/* Ingestion Matrix Layout */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
                  {/* Drag and Drop Zone + Website Source */}
                  <div className="lg:col-span-1 space-y-5">
                    <div
                      onDragOver={(e) => {
                        e.preventDefault();
                        setIsDragging(true);
                      }}
                      onDragLeave={() => setIsDragging(false)}
                      onDrop={(e) => {
                        e.preventDefault();
                        setIsDragging(false);
                        if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
                      }}
                      onClick={() => document.getElementById("doc-uploader-picker").click()}
                      className={`border-2 border-dashed rounded-card p-8 flex flex-col items-center justify-center text-center cursor-pointer transition duration-300 h-56 ${
                        isDragging
                          ? "border-[#00D4FF] bg-[#00D4FF]/5"
                          : "border-white/[0.10] hover:border-white/[0.20] hover:bg-white/[0.04] bg-[#0B1221]/30"
                      }`}
                      data-testid="file-upload-zone"
                    >
                      <input
                        id="doc-uploader-picker"
                        type="file"
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files.length) handleUpload(e.target.files[0]);
                        }}
                        accept=".pdf,.txt,.docx,.csv,.json,.md"
                        data-testid="file-upload-input"
                      />
                      {isUploading ? (
                        <div className="space-y-3">
                          <Spinner className="h-9 w-9 mx-auto" />
                          <p className="text-[11px] text-slate-300 font-mono animate-pulse">
                            INGESTING BYTES...
                          </p>
                        </div>
                      ) : (
                        <div className="space-y-4">
                          <div className="p-3.5 bg-white/[0.04] rounded-full border border-white/[0.10] inline-block">
                            <UploadCloud className="h-6 w-6 text-[#00D4FF]" />
                          </div>
                          <div>
                            <p className="text-[12px] text-slate-200 font-semibold">
                              Upload Documentation
                            </p>
                            <p className="text-[10px] text-slate-500 mt-1 leading-relaxed">
                              Drag & Drop or browse files.
                              <br />
                              PDF, TXT, DOCX, CSV, MD or JSON.
                            </p>
                          </div>
                        </div>
                      )}
                    </div>

                    <Card className="p-4 space-y-3">
                      <div className="flex items-center gap-2 text-[12px] font-semibold text-slate-200">
                        <Globe className="h-3.5 w-3.5 text-[#00D4FF]" aria-hidden="true" />
                        <span>Website Source</span>
                      </div>

                      <Field label="Website URL" htmlFor="website-url" className="text-[10px]">
                        <Input
                          id="website-url"
                          type="url"
                          value={websiteUrl}
                          onChange={(e) => setWebsiteUrl(e.target.value)}
                          placeholder="https://example.com"
                          data-testid="website-url-input"
                        />
                      </Field>

                      <Field label="Title (optional)" htmlFor="website-title" className="text-[10px]">
                        <Input
                          id="website-title"
                          type="text"
                          value={websiteTitle}
                          onChange={(e) => setWebsiteTitle(e.target.value)}
                          placeholder="Example Docs"
                          data-testid="website-title-input"
                        />
                      </Field>

                      <form onSubmit={handleCreateWebsiteDocument}>
                        <Button
                          type="submit"
                          className="w-full uppercase tracking-wider"
                          data-testid="website-document-submit"
                        >
                          <Globe className="h-3.5 w-3.5" />
                          <span>Ingest Website</span>
                        </Button>
                      </form>
                    </Card>
                  </div>

                  {/* Documents Table */}
                  <Card className="lg:col-span-2 p-6">
                    {documents.length === 0 ? (
                      <EmptyState
                        icon={FileText}
                        title="No documents yet"
                        message="Upload files on the left to start building this application's knowledge base."
                      />
                    ) : (
                      <div className="overflow-x-auto max-h-[560px] overflow-y-auto" data-testid="document-table">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="sticky top-0 z-10 bg-[#0D1526] border-b border-white/[0.08] text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                              <th className="py-3 px-4">Filename</th>
                              <th className="py-3 px-4">Size</th>
                              <th className="py-3 px-4">Status</th>
                              <th className="py-3 px-4 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {documents.map((doc) => {
                              const meta = DOC_STATUS[doc.status] || {
                                variant: "neutral",
                                label: doc.status,
                              };
                              return (
                                <tr
                                  key={doc.id}
                                  className="border-b border-white/[0.05] hover:bg-white/[0.03] transition duration-200"
                                  data-testid={`document-row-${doc.id}`}
                                >
                                  <td className="py-3 px-4 font-semibold text-slate-200">
                                    <div className="flex items-center gap-2.5 max-w-[200px] md:max-w-[280px]">
                                      <FileText className="h-4 w-4 text-[#00D4FF] flex-shrink-0" aria-hidden="true" />
                                      <span className="truncate" title={doc.title}>
                                        {doc.title}
                                      </span>
                                    </div>
                                  </td>
                                  <td className="py-3 px-4 text-slate-400 font-mono">
                                    {doc.file_size_bytes
                                      ? `${(doc.file_size_bytes / 1024).toFixed(1)} KB`
                                      : "N/A"}
                                  </td>
                                  <td className="py-3 px-4" data-testid={`document-status-${doc.id}`}>
                                    <Badge
                                      variant={meta.variant}
                                      title={doc.failure_reason || doc.error_message}
                                    >
                                      {(doc.status === "processing" || doc.status === "pending") && (
                                        <span className="h-2.5 w-2.5 rounded-full border-2 border-current border-t-transparent animate-spin" />
                                      )}
                                      {meta.label}
                                    </Badge>
                                    {doc.status === "failed" && doc.failure_reason && (
                                      <p
                                        className="mt-1 max-w-[220px] truncate text-[10px] text-rose-300"
                                        title={doc.failure_reason}
                                      >
                                        {doc.failure_reason}
                                      </p>
                                    )}
                                  </td>
                                  <td className="py-3 px-4">
                                    <div className="flex items-center justify-end gap-1.5">
                                      {doc.status === "failed" && (
                                        <button
                                          onClick={() => handleDocAction(doc.id, "processing")}
                                          className="p-1.5 border border-amber-500/15 hover:border-amber-500/40 rounded-[8px] hover:bg-amber-500/10 text-amber-400 hover:text-amber-300 transition focus:outline-none"
                                          title="Re-process"
                                          data-testid={`reprocess-btn-${doc.id}`}
                                        >
                                          <RotateCcw className="h-3.5 w-3.5" />
                                        </button>
                                      )}
                                      {doc.status === "pending" && (
                                        <button
                                          onClick={() =>
                                            handleDocAction(doc.id, "failed", {
                                              failure_reason: "Manually marked failed by admin",
                                            })
                                          }
                                          className="p-1.5 border border-red-500/15 hover:border-red-500/40 rounded-[8px] hover:bg-red-500/10 text-red-400 hover:text-red-300 transition focus:outline-none"
                                          title="Mark failed"
                                          data-testid={`fail-btn-${doc.id}`}
                                        >
                                          <XCircle className="h-3.5 w-3.5" />
                                        </button>
                                      )}
                                      {doc.status !== "archived" && (
                                        <button
                                          onClick={() => handleDocAction(doc.id, "archive")}
                                          className="p-1.5 border border-slate-500/15 hover:border-slate-500/40 rounded-[8px] hover:bg-slate-500/10 text-slate-400 hover:text-slate-200 transition focus:outline-none"
                                          title="Archive"
                                          data-testid={`archive-btn-${doc.id}`}
                                        >
                                          <Archive className="h-3.5 w-3.5" />
                                        </button>
                                      )}
                                      <button
                                        onClick={() => handleDeleteDoc(doc.id, doc.title)}
                                        className="p-1.5 border border-red-500/15 hover:border-red-500/40 rounded-[8px] hover:bg-red-500/10 text-red-400 hover:text-red-300 transition focus:outline-none"
                                        title="Delete"
                                        data-testid={`delete-btn-${doc.id}`}
                                      >
                                        <Trash2 className="h-3.5 w-3.5" />
                                      </button>
                                    </div>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </Card>
                </div>
              </>
            )}
          </div>
        )}

        {/* ======================= TAB: WIDGET CONFIG ======================= */}
        {activeTab === "widget" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start animate-fadeIn" data-testid="view-widget">
            {/* Properties form */}
            <div className="lg:col-span-2 space-y-6">
              <form onSubmit={handleUpdateWidget}>
                <Card className="p-6 space-y-5">
                  <div className="flex items-center gap-2">
                    <Sliders className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
                    <span className="text-card-title text-white">Widget Appearance</span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="Greeting Prompt" htmlFor="widget-greeting">
                      <Input
                        id="widget-greeting"
                        type="text"
                        value={greetingMsg}
                        onChange={(e) => setGreetingMsg(e.target.value)}
                        data-testid="widget-greeting-input"
                      />
                    </Field>

                    <Field label="Theme" htmlFor="widget-theme">
                      <Select
                        id="widget-theme"
                        value={widgetTheme}
                        onChange={(e) => setWidgetTheme(e.target.value)}
                      >
                        <option value="light">Light</option>
                        <option value="dark">Dark</option>
                      </Select>
                    </Field>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field label="Launcher Label" htmlFor="widget-launcher">
                      <Input
                        id="widget-launcher"
                        type="text"
                        value={launcherLabel}
                        onChange={(e) => setLauncherLabel(e.target.value)}
                        data-testid="widget-launcher-label"
                      />
                    </Field>

                    <Field label="Placeholder Text" htmlFor="widget-placeholder">
                      <Input
                        id="widget-placeholder"
                        type="text"
                        value={placeholderText}
                        onChange={(e) => setPlaceholderText(e.target.value)}
                      />
                    </Field>
                  </div>

                  {/* Accent colour - presets + custom picker */}
                  <div className="pt-4 border-t border-white/[0.06]">
                    <div className="flex items-center justify-between gap-3 mb-2.5">
                      <span className="text-meta text-slate-300">Accent Colour</span>
                      <span className="text-[10px] text-slate-500 font-mono uppercase">
                        {accentColor}
                      </span>
                    </div>
                    <ColorPicker
                      value={widgetAccent}
                      onChange={handleAccentChange}
                      defaultValue={DEFAULT_WIDGET_ACCENT}
                    />
                    <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">
                      Applied to the launcher and send button (and the header in light theme).
                      Choose a preset or pick a custom colour.
                    </p>
                  </div>

                  {/* Starter prompts & FAQs */}
                  <div className="pt-4 border-t border-white/[0.06]">
                    <div className="flex items-center gap-2 mb-1">
                      <MessageSquare className="h-3.5 w-3.5 text-[#00D4FF]" aria-hidden="true" />
                      <span className="text-card-title text-white text-[14px]">
                        Starter prompts & FAQs
                      </span>
                    </div>
                    <span className="block text-eyebrow text-slate-500 mb-3">
                      Starter prompt chips
                    </span>
                    <StarterPrompts
                      value={starterPrompts}
                      onChange={setStarterPrompts}
                    />
                    <p className="text-[10px] text-slate-500 mt-2 leading-relaxed">
                      Drag to reorder. These chips are shown above the input to help users start a
                      conversation.
                    </p>
                  </div>

                  <CheckboxRow
                    id="widget-enabled"
                    checked={isWidgetEnabled}
                    onChange={(e) => setIsWidgetEnabled(e.target.checked)}
                    label="Widget is enabled and visible"
                  />

                  <div className="pt-4 border-t border-white/[0.06] flex items-center justify-end">
                    <Button
                      type="submit"
                      className="uppercase tracking-wider"
                      data-testid="widget-save-btn"
                    >
                      Save Appearance Contract
                    </Button>
                  </div>
                </Card>
              </form>

              {/* Embed Credentials */}
              <Card className="p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
                  <span className="text-card-title text-white">Widget Embed Credentials</span>
                </div>

                <Field label="Generated Widget Public Key" hint="Public widget keys are safe to embed on client sites.">
                  <InsetWell className="flex items-center gap-3">
                    <code
                      className="text-slate-300 font-mono text-[12px] select-all flex-1 break-all"
                      data-testid="widget-api-key"
                    >
                      {widgetCfg?.public_key || "wk_xxxxxxxxxxxxxxxx"}
                    </code>
                    <button
                      onClick={() => copyToClipboard(widgetCfg?.public_key, "key")}
                      className="text-slate-400 hover:text-white transition p-1.5 hover:bg-white/[0.06] rounded-[8px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
                      title="Copy widget key"
                      disabled={!widgetCfg}
                    >
                      {copiedKey ? (
                        <Check className="h-4 w-4 text-emerald-400" />
                      ) : (
                        <Copy className="h-4 w-4" />
                      )}
                    </button>
                  </InsetWell>
                </Field>

                <Field label="Embed Script Tag">
                  <div className="relative">
                    <pre
                      className="surface-inset rounded-control p-4 text-[11px] text-slate-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed select-all"
                      data-testid="widget-snippet"
                    >
                      {embedSnippetHtml || "Create a widget to generate the embed snippet."}
                    </pre>
                    {embedSnippetHtml && (
                      <button
                        onClick={() => copyToClipboard(embedSnippetHtml, "snippet")}
                        className="absolute top-3 right-3 text-slate-400 hover:text-white transition p-1.5 bg-white/[0.05] hover:bg-white/[0.10] rounded-[8px] border border-white/[0.10] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
                        title="Copy code snippet"
                      >
                        {copiedSnippet ? (
                          <Check className="h-3.5 w-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="h-3.5 w-3.5" />
                        )}
                      </button>
                    )}
                  </div>
                </Field>
              </Card>
            </div>

            {/* Live Preview */}
            <Card className="lg:col-span-1 p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Eye className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
                <span className="text-card-title text-white">Interactive Live Preview</span>
              </div>

              {/* Chat panel - mirrors the real widget theme tokens */}
              <div
                className="rounded-card overflow-hidden shadow-inner h-72 flex flex-col border"
                style={{ backgroundColor: pv.panelBg, borderColor: pv.panelBorder }}
              >
                <div
                  className="p-3 text-xs font-bold flex items-center justify-between"
                  style={{ backgroundColor: previewColor, color: previewHeaderTextColor }}
                >
                  <span className="tracking-tight truncate">{app.name}</span>
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
                </div>

                <div className="flex-1 p-4 space-y-3 overflow-y-auto">
                  <div className="flex gap-2">
                    <div
                      className="h-6 w-6 rounded-full flex items-center justify-center text-[10px] flex-shrink-0"
                      style={{ backgroundColor: pv.botBubbleBg, color: pv.bodyText }}
                    >
                      🤖
                    </div>
                    <div
                      className="rounded-card px-3 py-2 text-[10px] leading-relaxed max-w-[80%] border"
                      style={{
                        backgroundColor: pv.botBubbleBg,
                        borderColor: pv.botBubbleBorder,
                        color: pv.bodyText,
                      }}
                    >
                      {greetingMsg || "Hello! Ask me anything."}
                    </div>
                  </div>

                  {/* Starter prompt chips (shown to help users begin) */}
                  {starterPrompts.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pl-8">
                      {starterPrompts.slice(0, 4).map((prompt, i) => (
                        <span
                          key={i}
                          className="rounded-full px-2.5 py-1 text-[9px] border truncate max-w-[160px]"
                          style={{
                            backgroundColor: pv.botBubbleBg,
                            borderColor: accentColor,
                            color: pv.bodyText,
                          }}
                        >
                          {prompt}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div
                  className="p-3 border-t flex items-center gap-2"
                  style={{ backgroundColor: pv.footerBg, borderColor: pv.panelBorder }}
                >
                  <div
                    className="flex-1 rounded-[8px] px-2.5 py-1.5 text-[9px] truncate border"
                    style={{
                      backgroundColor: pv.inputBg,
                      borderColor: pv.inputBorder,
                      color: pv.mutedText,
                    }}
                  >
                    {placeholderText}
                  </div>
                  <div
                    className="h-6 w-12 rounded-[8px] flex items-center justify-center text-[9px] font-bold flex-shrink-0"
                    style={{ backgroundColor: accentColor, color: accentContrast }}
                  >
                    SEND
                  </div>
                </div>
              </div>

              {/* Launcher orb sits below the panel (mirrors the real widget),
                  so it never overlaps the input controls. */}
              <div className="flex items-center justify-between gap-3 pt-1">
                <span className="text-[10px] text-slate-500">Launcher preview</span>
                <div
                  className="h-11 w-11 rounded-full flex items-center justify-center text-lg shadow-xl border border-white/[0.10] flex-shrink-0"
                  style={{ backgroundColor: accentColor, color: accentContrast }}
                  title={launcherLabel}
                >
                  💬
                </div>
              </div>
            </Card>
          </div>
        )}

        {/* ======================= TAB: CHAT SANDBOX ======================= */}
        {activeTab === "chat" && (
          <div className="space-y-6 animate-fadeIn" data-testid="view-chat">
            {/* Context status */}
            <Card className="p-4 flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-2 text-xs">
                <Terminal className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
                <span className="font-semibold text-slate-200">Sandbox Testing Layer</span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-400 font-mono text-[11px]">POST /api/client/chat/messages</span>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                {/* API Key input for sandbox */}
                <div className="flex items-center gap-1.5">
                  <Button
                    variant={sandboxApiKey ? "secondary" : "outline"}
                    size="sm"
                    onClick={() => setShowSandboxKeyInput(!showSandboxKeyInput)}
                    title={sandboxApiKey ? "API key configured" : "Set API key (akp_...)"}
                    data-testid="sandbox-api-key-toggle"
                  >
                    <KeyRound className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">{sandboxApiKey ? "Key Set" : "Set API Key"}</span>
                  </Button>
                  {showSandboxKeyInput && (
                    <Input
                      type="text"
                      value={sandboxApiKey}
                      onChange={(e) => {
                        setSandboxApiKey(e.target.value);
                        localStorage.setItem("oceanrag_sandbox_api_key", e.target.value);
                      }}
                      placeholder="akp_..."
                      className="w-44 h-8 py-0 font-mono text-[10px]"
                      data-testid="sandbox-api-key-input"
                    />
                  )}
                </div>

                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <span>top_k</span>
                  <Select
                    value={chatTopK}
                    onChange={(e) => setChatTopK(Number(e.target.value))}
                    className="w-16 h-8 py-0 text-[11px]"
                    aria-label="Retrieve top_k chunks"
                  >
                    <option value={2}>2</option>
                    <option value={4}>4</option>
                    <option value={6}>6</option>
                  </Select>
                </div>

                <Button
                  variant="danger"
                  size="sm"
                  onClick={() => {
                    setSandboxHistory([]);
                    toast.success("Sandbox history reset.");
                  }}
                  data-testid="chat-sandbox-clear"
                >
                  Clear Sandbox
                </Button>
              </div>
            </Card>

            {/* Simulated Chat Interface */}
            <Card className="h-[450px] flex flex-col justify-between overflow-hidden p-0">
              <div className="flex-1 p-5 overflow-y-auto space-y-4">
                {sandboxHistory.length === 0 ? (
                  <div className="h-full flex flex-col items-center justify-center text-center py-10">
                    <div className="h-10 w-10 rounded-full bg-white/[0.05] border border-white/[0.10] flex items-center justify-center text-slate-500 mb-3 animate-pulse">
                      ⚡
                    </div>
                    <h4 className="font-semibold text-slate-300 text-xs">Awaiting Query Input</h4>
                    <p className="text-[10px] text-slate-500 max-w-sm mt-1">
                      Execute testing prompts to query matching vector chunks from active document matrices.
                    </p>
                  </div>
                ) : (
                  sandboxHistory.map((m, idx) => (
                    <div
                      key={idx}
                      className={`flex flex-col ${m.role === "user" ? "items-end" : "items-start"}`}
                    >
                      <div className="flex items-center gap-2 mb-1 text-[10px] text-slate-500 px-1">
                        <span>{m.role === "user" ? "Client" : "API Response"}</span>
                        <span>•</span>
                        <span>
                          {new Date(m.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>

                      <div className="flex gap-2 max-w-[85%]">
                        <div
                          className={`rounded-card px-4 py-3 text-[12px] leading-relaxed ${
                            m.role === "user"
                              ? "bg-[#2563EB] text-white rounded-tr-none border border-white/[0.06]"
                              : "surface-card rounded-tl-none text-slate-200"
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{m.content}</p>
                        </div>
                      </div>

                      {/* Display Matching Groundings */}
                      {m.role === "bot" && m.sources && m.sources.length > 0 && (
                        <div className="mt-2 pl-4 max-w-[85%] space-y-2">
                          <span className="block text-[9px] text-[#00D4FF] font-semibold uppercase tracking-wider">
                            Matched Chunk Sources
                          </span>
                          {m.sources.map((s, sIdx) => (
                            <div
                              key={sIdx}
                              className="bg-[#040914]/80 border border-white/[0.06] rounded-card p-2.5 text-[10px] text-slate-400"
                            >
                              <div className="flex justify-between items-center mb-1 text-[9px] text-slate-500 font-semibold font-mono border-b border-white/[0.06] pb-1">
                                <span className="truncate">{s.document_id}</span>
                                <span className="text-[#00D4FF] flex-shrink-0">Chunk: {s.chunk_id}</span>
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
                    <div className="surface-card rounded-card rounded-tl-none px-4 py-3 flex items-center gap-2">
                      <Spinner className="h-3.5 w-3.5" />
                      <span className="text-[10px] text-slate-400 font-mono">
                        Retrieving high-dimensional match dimensions...
                      </span>
                    </div>
                  </div>
                )}
              </div>

              {/* Sandbox Input Form */}
              <form
                onSubmit={handleChatTest}
                className="p-3 border-t border-white/[0.08] bg-[#0B1221] flex items-center gap-3"
              >
                <input
                  type="text"
                  value={sandboxQuestion}
                  onChange={(e) => setSandboxQuestion(e.target.value)}
                  placeholder="Ask testing questions about indexed documents..."
                  className="flex-1 bg-[#040914]/50 border border-white/[0.10] focus:border-[#00D4FF] text-white text-[12px] rounded-control px-4 py-3 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                  data-testid="chat-sandbox-input"
                  required
                />
                <Button
                  type="submit"
                  disabled={isChatLoading || !sandboxQuestion.trim()}
                  className="h-11 px-5"
                  data-testid="chat-sandbox-submit"
                >
                  <span>Verify</span>
                  <Play className="h-3.5 w-3.5" />
                </Button>
              </form>
            </Card>
          </div>
        )}

        {/* ======================= TAB: CONVERSATIONS ======================= */}
        {activeTab === "conversations" && <ConversationsTab applicationId={id} />}

        {/* ======================= TAB: SETTINGS ======================= */}
        {activeTab === "settings" && (
          <form onSubmit={handleUpdateSettings} className="animate-fadeIn" data-testid="view-settings">
            <Card className="p-6 space-y-6">
              <div className="flex items-center gap-2">
                <Sliders className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
                <span className="text-card-title text-white">RAG Settings & Parameter Core</span>
              </div>

              {!settings && (
                <div className="text-center py-6 text-slate-400 text-[12px] border border-dashed border-white/[0.08] rounded-card">
                  No settings configured yet. Create settings by submitting this form.
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Field label="LLM Temperature" htmlFor="settings-temperature">
                  <Input
                    id="settings-temperature"
                    type="number"
                    value={settings?.llm_temperature ?? "0.2"}
                    onChange={(e) => setSettings({ ...settings, llm_temperature: e.target.value })}
                    min="0"
                    max="2"
                    step="0.1"
                    data-testid="settings-temperature"
                  />
                </Field>

                <Field label="Max Context Messages" htmlFor="settings-context">
                  <Input
                    id="settings-context"
                    type="number"
                    value={settings?.max_context_messages ?? 12}
                    onChange={(e) =>
                      setSettings({ ...settings, max_context_messages: parseInt(e.target.value) })
                    }
                    min="1"
                    max="100"
                  />
                </Field>

                <Field label="Inactivity Timeout (minutes)" htmlFor="settings-timeout">
                  <Input
                    id="settings-timeout"
                    type="number"
                    value={settings?.inactivity_timeout_minutes ?? 30}
                    onChange={(e) =>
                      setSettings({
                        ...settings,
                        inactivity_timeout_minutes: parseInt(e.target.value),
                      })
                    }
                    min="1"
                    max="10080"
                  />
                </Field>

                <Field label="Retention Days" htmlFor="settings-retention">
                  <Input
                    id="settings-retention"
                    type="number"
                    value={settings?.retention_days ?? 30}
                    onChange={(e) =>
                      setSettings({ ...settings, retention_days: parseInt(e.target.value) })
                    }
                    min="1"
                    max="3650"
                  />
                </Field>
              </div>

              <Field
                label="System Grounding Prompt Instructions"
                htmlFor="settings-system-prompt"
              >
                <Textarea
                  id="settings-system-prompt"
                  value={settings?.prompt_system_template || ""}
                  onChange={(e) =>
                    setSettings({ ...settings, prompt_system_template: e.target.value })
                  }
                  rows={5}
                  className="font-mono"
                  data-testid="settings-system-prompt"
                />
              </Field>

              <div className="pt-4 border-t border-white/[0.06] flex items-center justify-end">
                <Button
                  type="submit"
                  className="uppercase tracking-wider"
                  data-testid="settings-save-btn"
                >
                  Save Parameter Core
                </Button>
              </div>
            </Card>
          </form>
        )}
      </div>

      {/* Edit application modal */}
      <Modal
        open={showEditModal}
        onClose={() => (isSaving ? null : setShowEditModal(false))}
        title="Edit Application"
        description={app ? `Update the configuration for "${app.name}".` : undefined}
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowEditModal(false)} disabled={isSaving}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="app-edit-form"
              loading={isSaving}
              disabled={!formName.trim()}
            >
              Save Changes
            </Button>
          </>
        }
      >
        <form id="app-edit-form" onSubmit={handleEditSubmit} className="space-y-4">
          <Field label="Name" htmlFor="edit-name" required>
            <Input
              id="edit-name"
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. FAQ Support Assistant"
              required
            />
          </Field>

          <Field label="Description" htmlFor="edit-desc">
            <Textarea
              id="edit-desc"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="Describe the application scope..."
              rows={3}
            />
          </Field>

          <Field label="Client Type" htmlFor="edit-client" required>
            <Select
              id="edit-client"
              value={formClientType}
              onChange={(e) => setFormClientType(e.target.value)}
              required
            >
              <option value="website">Website</option>
              <option value="mobile">Mobile App</option>
              <option value="desktop">Desktop App</option>
              <option value="api">API Integration</option>
            </Select>
          </Field>

          <Field
            label="Allowed Origins"
            htmlFor="edit-origins"
            hint="Comma separated. Leave empty to allow all origins."
          >
            <Input
              id="edit-origins"
              type="text"
              value={formOrigins}
              onChange={(e) => setFormOrigins(e.target.value)}
              placeholder="https://example.com, https://app.example.com"
              className="font-mono"
            />
          </Field>
        </form>
      </Modal>

      {/* Delete confirmation (styled replacement for window.confirm) */}
      <ConfirmDialog
        open={!!deleteTarget}
        onCancel={() => setDeleteTarget(null)}
        onConfirm={performDeleteDoc}
        title="Delete document"
        message={
          deleteTarget
            ? `Are you sure you want to delete and un-index "${deleteTarget.name}"? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        pending={isDeleting}
      />
    </PageShell>
  );
}
