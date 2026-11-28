import { useState, useEffect, useRef } from "react";
import { useParams, Link } from "react-router-dom";
import { apiClient } from "@/api/client";
import {
  ArrowLeft, Database, MessageSquare, Settings, Play,
  Trash2, Copy, Check, UploadCloud, FileText,
  Sparkles, Sliders, Globe, Eye, Terminal, RefreshCw,
  Plus, RotateCcw, XCircle, KeyRound, Pencil, Power, Users, Star,
} from "lucide-react";
import { toast } from "sonner";
import ConversationsTab from "@/components/ConversationsTab";
import FeedbackTab from "@/components/FeedbackTab";
import LeadsTab from "@/components/LeadsTab";

import { Button, Badge, Card, Spinner, ErrorBanner } from "@/components/ui/Primitives";
import { PageShell, PageHeader, SectionHeader } from "@/components/ui/Layout";
import { EmptyState } from "@/components/ui/Stats";
import { Modal, ConfirmDialog } from "@/components/ui/Overlays";
import { Tabs } from "@/components/ui/Tabs";
import { Field, Input, Textarea, Select, CheckboxRow, InsetWell } from "@/components/ui/Form";
import { ColorPicker } from "@/components/ui/ColorPicker";
import { StarterPrompts } from "@/components/ui/StarterPrompts";
import {
  contrastRatio,
  DEFAULT_WIDGET_ACCENT,
  readableTextOn,
} from "@/components/ui/colorUtils";

// Default starter prompts shown in the widget until the admin customises them.
const DEFAULT_STARTER_PROMPTS = [
  "How do I upgrade my plan?",
  "Reset my API key",
  "What is your refund policy?",
];
const DEFAULT_WIDGET_GREETING = "Hello! Ask me any questions about our policies.";
const WIDGET_PANEL_SIZES = {
  compact: { width: 320, height: 480 },
  standard: { width: 360, height: 560 },
  wide: { width: 420, height: 640 },
};

/* ============================================================
   APPLICATION DETAIL
   Eight-tab workspace: General, Knowledge Base, Widget Config,
   Chat Sandbox, Conversations, Leads, Feedback, Settings. Rebuilt on the shared
   UI kit (cards, tabs, form controls, confirm dialog) while
   keeping every backend interaction and data-testid intact.
   ============================================================ */

const TAB_ITEMS = [
  { key: "general", label: "General", icon: Sparkles, testId: "tab-general" },
  { key: "kb", label: "Knowledge Base", icon: Database, testId: "tab-kb" },
  { key: "widget", label: "Widget Config", icon: Globe, testId: "tab-widget" },
  { key: "chat", label: "Chat Testing", icon: MessageSquare, testId: "tab-chat" },
  { key: "conversations", label: "Conversations", icon: MessageSquare, testId: "tab-conversations" },
  { key: "leads", label: "Leads", icon: Users, testId: "tab-leads" },
  { key: "feedback", label: "Feedback", icon: Star, testId: "tab-feedback" },
  { key: "settings", label: "Settings", icon: Settings, testId: "tab-settings" },
];

const DOC_STATUS = {
  ready: { variant: "success", label: "ready" },
  processing: { variant: "warning", label: "processing" },
  pending: { variant: "accent", label: "pending" },
  failed: { variant: "danger", label: "failed" },
  archived: { variant: "neutral", label: "archived" },
};

const providerChoices = (options = []) =>
  [...new Set(options.map((option) => option.provider))];

const providerLabel = (provider) =>
  ({
    gemini: "Google Gemini",
    openai: "OpenAI",
  })[provider] || provider;

function parseSandboxSources(citationPayload) {
  if (!citationPayload) return [];
  try {
    const citations = JSON.parse(citationPayload);
    if (!Array.isArray(citations)) return [];
    return citations.map((citation) => ({
      document_id: citation.document_id,
      title: citation.document_title || citation.title,
      chunk_id: citation.chunk_id,
      source_uri: citation.source_uri || null,
    }));
  } catch {
    return [];
  }
}

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
  const [conversationToOpen, setConversationToOpen] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // General state
  const [documents, setDocuments] = useState([]);
  const [usageSummary, setUsageSummary] = useState(null);
  const [usageSummaryError, setUsageSummaryError] = useState("");
  const [knowledgeBase, setKnowledgeBase] = useState(null);
  const [settings, setSettings] = useState(null);
  const [providerCatalog, setProviderCatalog] = useState(null);
  const [configurationValidation, setConfigurationValidation] = useState(null);
  const [isValidatingConfiguration, setIsValidatingConfiguration] = useState(false);
  const [settingsLoadError, setSettingsLoadError] = useState("");
  const [settingsSaveError, setSettingsSaveError] = useState("");
  const settingsLoadIdRef = useRef(0);
  const [widgetCfg, setWidgetCfg] = useState(null);
  const parserOptions = providerCatalog?.parsers || [];
  const embeddingOptions = providerCatalog?.embeddings || [];
  const llmOptions = providerCatalog?.llms || [];
  const embeddingProviders = providerChoices(embeddingOptions);
  const llmProviders = providerChoices(llmOptions);
  const selectedEmbeddingModels = embeddingOptions.filter(
    (option) => option.provider === settings?.embedding_provider
  );
  const selectedLlmModels = llmOptions.filter(
    (option) => option.provider === settings?.llm_provider
  );
  const isCurrentLlmSelectionAvailable = selectedLlmModels.some(
    (option) => option.model === settings?.llm_model
  );

  // Interaction sandbox testing states
  const [sandboxQuestion, setSandboxQuestion] = useState("");
  const [sandboxHistory, setSandboxHistory] = useState([]);
  const [isChatLoading, setIsChatLoading] = useState(false);
  const [sandboxLoadedApplicationId, setSandboxLoadedApplicationId] = useState(null);
  const isSandboxHistoryLoading = sandboxLoadedApplicationId !== id;
  const [chatTopK, setChatTopK] = useState(4);
  const [sandboxConversationId, setSandboxConversationId] = useState(null);
  const [sandboxApiKeys, setSandboxApiKeys] = useState(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("oceanrag_sandbox_api_keys") || "{}"
      );
      return saved && typeof saved === "object" ? saved : {};
    } catch {
      return {};
    }
  });
  const sandboxApiKey = sandboxApiKeys[id] || "";
  const [showSandboxKeyInput, setShowSandboxKeyInput] = useState(false);

  useEffect(() => {
    let cancelled = false;

    const restoreSandboxConversation = async () => {
      try {
        const { data: conversationPage } = await apiClient.get(
          `/admin/conversations/application/${id}`,
          {
            params: {
              status: "active",
              search: `sandbox-${id}`,
              limit: 1,
            },
          }
        );
        const activeConversation = (conversationPage.items || []).find(
          (conversation) =>
            conversation.is_active
            && conversation.conversation_identity === `sandbox-${id}`
        );
        if (!activeConversation) {
          if (!cancelled) {
            setSandboxHistory([]);
            setSandboxConversationId(null);
            setSandboxLoadedApplicationId(id);
          }
          return;
        }

        const { data: detail } = await apiClient.get(
          `/admin/conversations/application/${id}/${activeConversation.id}`
        );
        if (cancelled) return;

        setSandboxConversationId(activeConversation.id);
        setSandboxHistory(
          (detail.messages || []).map((message) => ({
            role: message.role === "assistant" ? "bot" : message.role,
            content: message.content,
            timestamp: message.created_at,
            sources: parseSandboxSources(message.citation_payload),
          }))
        );
        setSandboxLoadedApplicationId(id);
      } catch (error) {
        console.error(error);
        if (!cancelled) {
          setSandboxHistory([]);
          setSandboxConversationId(null);
          setSandboxLoadedApplicationId(id);
          toast.error("Failed to restore the application sandbox conversation.");
        }
      }
    };

    restoreSandboxConversation();
    return () => {
      cancelled = true;
    };
  }, [id]);

  // Widget appearance configurations
  const [greetingMsg, setGreetingMsg] = useState("");
  // Theme is stored as the semantic value (light/dark) that the
  // backend persists - NOT a hex color. The preview maps theme -> color.
  const [widgetTheme, setWidgetTheme] = useState("light");
  const [widgetPosition, setWidgetPosition] = useState("right");
  const [widgetPanelSize, setWidgetPanelSize] = useState("standard");
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
  const documentPollDelayRef = useRef(3000);
  const [websiteUrl, setWebsiteUrl] = useState("");
  const [websiteTitle, setWebsiteTitle] = useState("");
  const [websiteRefreshInterval, setWebsiteRefreshInterval] = useState("");
  const [documentSearch, setDocumentSearch] = useState("");
  const [documentStatusFilter, setDocumentStatusFilter] = useState("");
  const [documentSourceFilter, setDocumentSourceFilter] = useState("");
  const [documentCreatedFrom, setDocumentCreatedFrom] = useState("");
  const [documentCreatedTo, setDocumentCreatedTo] = useState("");
  const [documentSort, setDocumentSort] = useState("newest");
  const [documentPage, setDocumentPage] = useState(1);

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

  const loadUsageSummary = async () => {
    try {
      const { data } = await apiClient.get(
        `/admin/applications/${id}/usage-summary`
      );
      setUsageSummary(data);
      setUsageSummaryError("");
    } catch (error) {
      console.error("Failed to load application usage summary.", error);
      setUsageSummary(null);
      setUsageSummaryError("Usage summary is currently unavailable.");
    }
  };

  const fetchAppData = async () => {
    const settingsLoadId = ++settingsLoadIdRef.current;
    setIsLoading(true);
    setLoadError(null);
    setSettings(null);
    setSettingsLoadError("");
    setSettingsSaveError("");
    try {
      // Fetch application details
      const appsRes = await apiClient.get("/admin/applications");
      const matched = appsRes.data.find((a) => a.id === id);
      if (matched) {
        setApp(matched);
        await loadUsageSummary();

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
          setWidgetPosition(widgetRes.data.launcher_position === "left" ? "left" : "right");
          setWidgetPanelSize(
            WIDGET_PANEL_SIZES[widgetRes.data.panel_size]
              ? widgetRes.data.panel_size
              : "standard"
          );
          setLauncherLabel(
            widgetRes.data.launcher_label || widgetRes.data.display_name || "Chat with us"
          );
          setPlaceholderText(widgetRes.data.placeholder_text || "Type your message...");
          setIsWidgetEnabled(widgetRes.data.is_enabled);
          setWidgetAccent(widgetRes.data.accent_color || DEFAULT_WIDGET_ACCENT);
          // Backend-persisted starter prompt chips.
          setStarterPrompts(
            Array.isArray(widgetRes.data.starter_prompts)
              ? widgetRes.data.starter_prompts
              : DEFAULT_STARTER_PROMPTS
          );
        } catch (error) {
          if (error.response?.status !== 404) {
            console.warn("Failed to load widget configuration for this application", error);
          }
          setWidgetCfg(null);
          setGreetingMsg("");
          setWidgetTheme("light");
          setWidgetPosition("right");
          setWidgetPanelSize("standard");
          setLauncherLabel("Chat with us");
          setPlaceholderText("Type your message...");
          setIsWidgetEnabled(true);
          setWidgetAccent(DEFAULT_WIDGET_ACCENT);
          setStarterPrompts(DEFAULT_STARTER_PROMPTS);
        }

        // Fetch settings
        try {
          const catalogRes = await apiClient.get("/admin/settings/provider-catalog");
          setProviderCatalog(catalogRes.data);
        } catch (error) {
          console.error("Failed to load provider catalog.", error);
          setProviderCatalog(null);
          toast.error("Failed to load provider and model options.");
        }

        try {
          const settingsRes = await apiClient.get(`/admin/settings/by-application/${id}`);
          if (settingsLoadId === settingsLoadIdRef.current) {
            setSettings(settingsRes.data);
          }
        } catch (error) {
          if (settingsLoadId !== settingsLoadIdRef.current) return;
          setSettings(null);
          if (error.response?.status === 404) {
            console.info("No settings found for this application.");
          } else {
            console.error("Failed to load application settings.", error);
            const message =
              error.response?.data?.detail ||
              "Failed to load application settings. Refresh and try again.";
            setSettingsLoadError(
              typeof message === "string" ? message : "Failed to load application settings."
            );
            toast.error("Failed to load application settings.");
          }
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

  // Poll sequentially with backoff while document ingestion is unfinished.
  useEffect(() => {
    if (!knowledgeBase?.id) return;

    const unfinished = documents.some(
      (d) => d.status === "pending" || d.status === "processing"
    );
    if (!unfinished) {
      documentPollDelayRef.current = 3000;
      return;
    }

    let timeoutId;
    let cancelled = false;
    const pollDocuments = async () => {
      try {
        const docsRes = await apiClient.get(
          `/admin/documents?knowledge_base_id=${knowledgeBase.id}`
        );
        if (cancelled) return;

        setDocuments(docsRes.data);
        const stillUnfinished = docsRes.data.some(
          (doc) => doc.status === "pending" || doc.status === "processing"
        );
        if (!stillUnfinished) {
          documentPollDelayRef.current = 3000;
          return;
        }
        documentPollDelayRef.current = Math.min(
          Math.round(documentPollDelayRef.current * 1.5),
          15000
        );
      } catch (e) {
        console.warn("Polling documents failed", e);
        documentPollDelayRef.current = Math.min(
          documentPollDelayRef.current * 2,
          30000
        );
      }

      if (!cancelled) {
        timeoutId = setTimeout(pollDocuments, documentPollDelayRef.current);
      }
    };

    timeoutId = setTimeout(pollDocuments, documentPollDelayRef.current);
    return () => {
      cancelled = true;
      clearTimeout(timeoutId);
    };
  }, [documents, knowledgeBase?.id]);

  const handleUpdateSettings = async (e) => {
    e.preventDefault();
    setSettingsSaveError("");
    try {
      if (settings?.id) {
        // Update existing settings
        const { data } = await apiClient.put(`/admin/settings/by-application/${id}`, {
          llm_temperature: settings.llm_temperature,
          max_context_messages: settings.max_context_messages,
          inactivity_timeout_minutes: settings.inactivity_timeout_minutes,
          retention_days: settings.retention_days,
          prompt_system_template: settings.prompt_system_template,
          parser_provider: settings.parser_provider,
          embedding_provider: settings.embedding_provider,
          embedding_model: settings.embedding_model,
          llm_provider: settings.llm_provider,
          llm_model: settings.llm_model,
        });
        setSettings(data);
      } else {
        // Create new settings
        const { data } = await apiClient.post("/admin/settings", {
          application_id: id,
          llm_temperature: settings?.llm_temperature ?? "0.2",
          max_context_messages: settings?.max_context_messages ?? 12,
          inactivity_timeout_minutes: settings?.inactivity_timeout_minutes ?? 30,
          retention_days: settings?.retention_days ?? 30,
          prompt_system_template: settings?.prompt_system_template ?? null,
          parser_provider: settings?.parser_provider,
          embedding_provider: settings?.embedding_provider,
          embedding_model: settings?.embedding_model,
          llm_provider: settings?.llm_provider,
          llm_model: settings?.llm_model,
        });
        setSettings(data);
      }
      setSettingsLoadError("");
      setConfigurationValidation(null);
      toast.success("RAG Parameters and System Prompt saved securely!");
      fetchAppData(); // Refresh settings
    } catch (e) {
      console.error(e);
      const message =
        e.response?.data?.error?.message ||
        e.response?.data?.detail ||
        "Failed to save settings.";
      setSettingsSaveError(message);
      toast.error(message);
    }
  };

  const handleValidateConfiguration = async () => {
    setIsValidatingConfiguration(true);
    try {
      const { data } = await apiClient.post(
        `/admin/settings/by-application/${id}/validate`
      );
      setConfigurationValidation(data);
      if (data.ready) {
        toast.success("AI configuration is enabled by the platform.");
      } else {
        toast.error("Some AI configuration selections are unavailable.");
      }
    } catch (error) {
      console.error(error);
      toast.error(
        error.response?.data?.error?.message ||
        error.response?.data?.detail ||
        "Could not validate AI configuration."
      );
    } finally {
      setIsValidatingConfiguration(false);
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
          launcher_position: widgetPosition,
          panel_size: widgetPanelSize,
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
            launcher_position: widgetPosition,
            panel_size: widgetPanelSize,
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
              launcher_position: widgetPosition,
              panel_size: widgetPanelSize,
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
    const responseData = error.response?.data;
    const errorBody = responseData?.error;
    const detail = errorBody?.message || responseData?.detail?.message || responseData?.detail;
    const validationDetails = errorBody?.details || responseData?.detail?.details;
    const formattedDetails = Array.isArray(validationDetails)
      ? validationDetails
          .map((item) => {
            const field = Array.isArray(item.loc) ? item.loc.slice(1).join(".") : "";
            return [field, item.msg].filter(Boolean).join(": ");
          })
          .filter(Boolean)
          .join("; ")
      : "";

    if (typeof detail === "string") {
      return formattedDetails ? `${detail} ${formattedDetails}` : detail;
    }
    return fallback;
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
      await apiClient.post("/admin/documents/upload", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`"${file.name}" uploaded; ingestion has been queued.`);
      // Refresh documents
      const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
      setDocuments(docsRes.data);
      await loadUsageSummary();
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
        refresh_interval_hours: websiteRefreshInterval
          ? Number(websiteRefreshInterval)
          : null,
      });

      toast.success(`Website source "${url.hostname}" queued for ingestion.`);
      setWebsiteUrl("");
      setWebsiteTitle("");
      setWebsiteRefreshInterval("");
      const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
      setDocuments(docsRes.data);
      await loadUsageSummary();
    } catch (error) {
      console.error(error);
      toast.error("Website document creation failed. Please enter a valid http/https URL.");
    }
  };

  // Opens the styled confirmation dialog instead of window.confirm
  const handleDeleteDoc = (document) => {
    setDeleteTarget({
      id: document.id,
      name: document.title,
      hasStoredSource: Boolean(document.storage_path),
    });
  };

  const performDeleteDoc = async () => {
    if (!deleteTarget) return;
    setIsDeleting(true);
    try {
      await apiClient.delete(`/admin/documents/${deleteTarget.id}`);
      toast.success(`Removed "${deleteTarget.name}" from directory.`);
      setDocuments((prev) => prev.filter((d) => d.id !== deleteTarget.id));
      await loadUsageSummary();
      setDeleteTarget(null);
    } catch (e) {
      console.error(e);
      toast.error(getDocumentActionError(e, "Un-indexing file failed."));
    } finally {
      setIsDeleting(false);
    }
  };

  const updateWebsiteRefreshSchedule = async (document, value) => {
    const refreshInterval = value ? Number(value) : null;
    try {
      const { data } = await apiClient.put(
        `/admin/documents/${document.id}/refresh-schedule`,
        { refresh_interval_hours: refreshInterval }
      );
      setDocuments((previous) =>
        previous.map((item) => item.id === document.id ? data : item)
      );
      toast.success(
        refreshInterval
          ? `Website refresh set to every ${refreshInterval} hours.`
          : "Automatic website refresh disabled."
      );
    } catch (error) {
      console.error(error);
      toast.error(getDocumentActionError(error, "Could not update website refresh schedule."));
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
          alreadyProcessing
            ? `${alreadyProcessing} already queued or processing`
            : null,
          failed ? `${failed} could not be queued` : null,
        ].filter(Boolean).join("; ");
        toast.success(`Vector rebuild queued for ${queued} document(s)!`, {
          description: details || undefined,
        });
      } else if (alreadyProcessing > 0 || failed > 0) {
        toast.error("No documents were queued for rebuild.", {
          description: [
            alreadyProcessing
              ? `${alreadyProcessing} already queued or processing`
              : null,
            failed ? `${failed} failed to queue` : null,
          ].filter(Boolean).join("; "),
        });
      } else {
        toast.error("No documents could be queued for reindexing.");
      }
      // Refresh
      if (knowledgeBase?.id) {
        try {
          const docsRes = await apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`);
          setDocuments(docsRes.data);
          await loadUsageSummary();
        } catch (refreshError) {
          console.error("Could not refresh document status after queuing re-index jobs.", refreshError);
          toast.error("Index rebuild requests were handled, but document status could not be refreshed.");
        }
      }
    } catch (e) {
      console.error(e);
      toast.error("Could not request the document index rebuild.");
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
    if (
      !sandboxQuestion.trim()
      || isChatLoading
      || isSandboxHistoryLoading
      || !app
    ) return;

    const userMsg = {
      role: "user",
      content: sandboxQuestion,
      timestamp: new Date().toISOString(),
    };
    const previousConversationId = sandboxConversationId;
    setSandboxHistory((prev) => [...prev, userMsg]);
    setSandboxQuestion("");
    setIsChatLoading(true);

    try {
      const response = await apiClient.post(
        `/admin/conversations/application/${id}/sandbox/messages`,
        {
          conversation_identity: `sandbox-${id}`,
          message: userMsg.content,
          top_k: chatTopK,
          application_id: id,
        },
        {
          headers: {
            "X-API-Key": sandboxApiKey || "",
          },
        }
      );

      const data = response.data;
      if (data.conversation_id) setSandboxConversationId(data.conversation_id);
      const botMsg = {
        role: "bot",
        content: data.answer,
        timestamp: new Date().toISOString(),
        sources: data.citations || [],
        conversation_id: data.conversation_id,
      };
      setSandboxHistory((prev) => [
        ...(previousConversationId
          && data.conversation_id !== previousConversationId
          ? [userMsg]
          : prev),
        botMsg,
      ]);
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
  const accentContrastRatio = contrastRatio(accentContrast, accentColor);
  const panelPreviewSize =
    WIDGET_PANEL_SIZES[widgetPanelSize] || WIDGET_PANEL_SIZES.standard;
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
<script src="${FRONTEND_URL}/widget/widget.js?v=6" async></script>`
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

  const indexedCount = documents.filter((document) => document.ready_version != null).length;
  const filteredDocuments = documents
    .filter((document) => {
      const search = documentSearch.trim().toLowerCase();
      const searchableText = [
        document.title,
        document.description,
        document.source_uri,
      ].filter(Boolean).join(" ").toLowerCase();
      const createdDate = document.created_at
        ? new Date(document.created_at).toISOString().slice(0, 10)
        : "";
      return (
        (!search || searchableText.includes(search)) &&
        (!documentStatusFilter || document.status === documentStatusFilter) &&
        (!documentSourceFilter || document.source_type === documentSourceFilter) &&
        (!documentCreatedFrom || createdDate >= documentCreatedFrom) &&
        (!documentCreatedTo || createdDate <= documentCreatedTo)
      );
    })
    .sort((left, right) => {
      if (documentSort === "oldest") {
        return new Date(left.created_at) - new Date(right.created_at);
      }
      if (documentSort === "title") {
        return left.title.localeCompare(right.title);
      }
      if (documentSort === "status") {
        return left.status.localeCompare(right.status) ||
          left.title.localeCompare(right.title);
      }
      return new Date(right.created_at) - new Date(left.created_at);
    });
  const documentsPerPage = 10;
  const documentPageCount = Math.max(
    1,
    Math.ceil(filteredDocuments.length / documentsPerPage)
  );
  const visibleDocumentPage = Math.min(documentPage, documentPageCount);
  const visibleDocuments = filteredDocuments.slice(
    (visibleDocumentPage - 1) * documentsPerPage,
    visibleDocumentPage * documentsPerPage
  );

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
                    <span className="text-emerald-400">Searchable in RAG</span>
                    <span className="font-bold text-emerald-400 font-mono">{indexedCount}</span>
                  </div>
                  {usageSummary && (
                    <>
                      <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                        <span className="text-slate-400">Pending / processing</span>
                        <span className="font-bold text-white font-mono">
                          {usageSummary.documents_processing}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                        <span className="text-slate-400">Conversations (30 days)</span>
                        <span className="font-bold text-white font-mono">
                          {usageSummary.conversations_recent}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                        <span className="text-slate-400">User messages (30 days)</span>
                        <span className="font-bold text-white font-mono">
                          {usageSummary.user_messages_recent}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                        <span className="text-slate-400">Ingestion failures</span>
                        <span className={`font-bold font-mono ${
                          usageSummary.documents_failed ? "text-amber-300" : "text-white"
                        }`}>
                          {usageSummary.documents_failed}
                        </span>
                      </div>
                      <div className="flex justify-between items-center bg-white/[0.03] p-2.5 rounded-[10px] border border-white/[0.06]">
                        <span className="text-slate-400">Leads / feedback</span>
                        <span className="font-bold text-white font-mono">
                          {usageSummary.leads_total} / {usageSummary.feedback_total}
                        </span>
                      </div>
                    </>
                  )}
                  {usageSummaryError && (
                    <p className="text-[10px] text-amber-300">{usageSummaryError}</p>
                  )}
                </div>
              </div>

              <div className="pt-4 border-t border-white/[0.06] text-[10px] text-slate-500 font-mono mt-4">
                <span>Vector index backend: PostgreSQL / pgvector</span>
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
                      <span>Queueing index rebuild...</span>
                    ) : (
                      <>
                        <RefreshCw className="h-3.5 w-3.5" />
                        <span>Rebuild pgvector index</span>
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

                      <Field
                        label="Automatic refresh"
                        htmlFor="website-refresh-interval"
                        hint="Refresh only this URL; no linked pages are crawled."
                        className="text-[10px]"
                      >
                        <Select
                          id="website-refresh-interval"
                          value={websiteRefreshInterval}
                          onChange={(event) => setWebsiteRefreshInterval(event.target.value)}
                          data-testid="website-refresh-interval"
                        >
                          <option value="">Off</option>
                          <option value="24">Daily</option>
                          <option value="168">Weekly</option>
                          <option value="720">Every 30 days</option>
                        </Select>
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
                      <div className="space-y-3" data-testid="document-table">
                        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-3">
                          <Input
                            type="search"
                            value={documentSearch}
                            onChange={(event) => {
                              setDocumentSearch(event.target.value);
                              setDocumentPage(1);
                            }}
                            placeholder="Search title, description, or URL"
                            aria-label="Search documents"
                            data-testid="document-search"
                          />
                          <Select
                            value={documentStatusFilter}
                            onChange={(event) => {
                              setDocumentStatusFilter(event.target.value);
                              setDocumentPage(1);
                            }}
                            aria-label="Filter by document status"
                            data-testid="document-status-filter"
                          >
                            <option value="">All statuses</option>
                            {Object.keys(DOC_STATUS).map((status) => (
                              <option key={status} value={status}>{status}</option>
                            ))}
                          </Select>
                          <Select
                            value={documentSourceFilter}
                            onChange={(event) => {
                              setDocumentSourceFilter(event.target.value);
                              setDocumentPage(1);
                            }}
                            aria-label="Filter by source type"
                            data-testid="document-source-filter"
                          >
                            <option value="">All source types</option>
                            {[...new Set(documents.map((document) => document.source_type))]
                              .sort()
                              .map((sourceType) => (
                                <option key={sourceType} value={sourceType}>
                                  {sourceType}
                                </option>
                              ))}
                          </Select>
                          <Input
                            type="date"
                            value={documentCreatedFrom}
                            onChange={(event) => {
                              setDocumentCreatedFrom(event.target.value);
                              setDocumentPage(1);
                            }}
                            aria-label="Created from date"
                            data-testid="document-created-from"
                          />
                          <Input
                            type="date"
                            value={documentCreatedTo}
                            onChange={(event) => {
                              setDocumentCreatedTo(event.target.value);
                              setDocumentPage(1);
                            }}
                            aria-label="Created through date"
                            data-testid="document-created-to"
                          />
                          <Select
                            value={documentSort}
                            onChange={(event) => {
                              setDocumentSort(event.target.value);
                              setDocumentPage(1);
                            }}
                            aria-label="Sort documents"
                            data-testid="document-sort"
                          >
                            <option value="newest">Newest first</option>
                            <option value="oldest">Oldest first</option>
                            <option value="title">Title A–Z</option>
                            <option value="status">Status</option>
                          </Select>
                        </div>
                        <div className="flex items-center justify-between gap-3 text-[10px] text-slate-400">
                          <span>
                            {filteredDocuments.length
                              ? `Showing ${(visibleDocumentPage - 1) * documentsPerPage + 1}–${Math.min(visibleDocumentPage * documentsPerPage, filteredDocuments.length)} of ${filteredDocuments.length}`
                              : "No documents match these filters"}
                          </span>
                          <button
                            type="button"
                            className="text-[#00D4FF] hover:text-white disabled:text-slate-600"
                            onClick={() => {
                              setDocumentSearch("");
                              setDocumentStatusFilter("");
                              setDocumentSourceFilter("");
                              setDocumentCreatedFrom("");
                              setDocumentCreatedTo("");
                              setDocumentSort("newest");
                              setDocumentPage(1);
                            }}
                          >
                            Clear filters
                          </button>
                        </div>
                        <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
                        <table className="w-full text-left border-collapse text-xs">
                          <thead>
                            <tr className="sticky top-0 z-10 bg-[#0D1526] border-b border-white/[0.08] text-slate-400 font-semibold uppercase tracking-wider text-[10px]">
                              <th className="py-3 px-4">Filename</th>
                              <th className="py-3 px-4">Source</th>
                              <th className="py-3 px-4">Size</th>
                              <th className="py-3 px-4">Status</th>
                              <th className="py-3 px-4">Refresh schedule</th>
                              <th className="py-3 px-4 text-right">Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {visibleDocuments.length === 0 ? (
                              <tr>
                                <td colSpan={6} className="py-8 text-center text-slate-500">
                                  No documents match these filters.
                                </td>
                              </tr>
                            ) : visibleDocuments.map((doc) => {
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
                                  <td className="py-3 px-4 text-slate-400">
                                    <span className="capitalize">{doc.source_type}</span>
                                    {doc.source_type === "website" && doc.source_uri && (
                                      <a
                                        href={doc.source_uri}
                                        target="_blank"
                                        rel="noreferrer"
                                        className="mt-1 block max-w-[180px] truncate text-[10px] text-[#00D4FF] hover:text-white"
                                        title={doc.source_uri}
                                      >
                                        {doc.source_uri}
                                      </a>
                                    )}
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
                                    {doc.status === "failed" && doc.ready_version != null && (
                                      <p className="mt-1 text-[10px] text-emerald-300">
                                        Serving last published version {doc.ready_version}
                                      </p>
                                    )}
                                    <p className="mt-1 text-[10px] text-slate-500">
                                      Attempt {doc.ingestion_attempt_count || 0}
                                      {doc.updated_at && ` · ${new Date(doc.updated_at).toLocaleString()}`}
                                    </p>
                                  </td>
                                  <td className="py-3 px-4">
                                    {doc.source_type === "website" ? (
                                      <div className="min-w-[150px]">
                                        <Select
                                          value={doc.refresh_interval_hours || ""}
                                          onChange={(event) =>
                                            updateWebsiteRefreshSchedule(doc, event.target.value)
                                          }
                                          disabled={doc.status === "processing"}
                                          aria-label={`Refresh schedule for ${doc.title}`}
                                          data-testid={`document-refresh-schedule-${doc.id}`}
                                        >
                                          <option value="">Off</option>
                                          <option value="24">Daily</option>
                                          <option value="168">Weekly</option>
                                          <option value="720">Every 30 days</option>
                                        </Select>
                                        {doc.next_refresh_at && (
                                          <p className="mt-1 text-[10px] text-slate-500">
                                            Next: {new Date(doc.next_refresh_at).toLocaleString()}
                                          </p>
                                        )}
                                      </div>
                                    ) : (
                                      <span className="text-slate-600">—</span>
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
                                      <button
                                        onClick={() => handleDeleteDoc(doc)}
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
                        {documentPageCount > 1 && (
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={visibleDocumentPage <= 1}
                              onClick={() => setDocumentPage(visibleDocumentPage - 1)}
                            >
                              Previous
                            </Button>
                            <span className="text-[10px] text-slate-400">
                              Page {visibleDocumentPage} of {documentPageCount}
                            </span>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={visibleDocumentPage >= documentPageCount}
                              onClick={() => setDocumentPage(visibleDocumentPage + 1)}
                            >
                              Next
                            </Button>
                          </div>
                        )}
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
                    <Field
                      label="Greeting Message"
                      htmlFor="widget-greeting"
                      hint="Shown as the first assistant message. Up to 1,000 characters."
                    >
                      <Textarea
                        id="widget-greeting"
                        value={greetingMsg}
                        onChange={(e) => setGreetingMsg(e.target.value)}
                        maxLength={1000}
                        rows={3}
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
                    <Field
                      label="Launcher Position"
                      htmlFor="widget-position"
                      hint="Choose which lower corner holds the launcher."
                    >
                      <Select
                        id="widget-position"
                        value={widgetPosition}
                        onChange={(event) => setWidgetPosition(event.target.value)}
                        data-testid="widget-position"
                      >
                        <option value="right">Bottom right</option>
                        <option value="left">Bottom left</option>
                      </Select>
                    </Field>
                    <Field
                      label="Panel Size"
                      htmlFor="widget-panel-size"
                      hint="Desktop preset; mobile uses a full-screen panel."
                    >
                      <Select
                        id="widget-panel-size"
                        value={widgetPanelSize}
                        onChange={(event) => setWidgetPanelSize(event.target.value)}
                        data-testid="widget-panel-size"
                      >
                        <option value="compact">Compact (320 × 480)</option>
                        <option value="standard">Standard (360 × 560)</option>
                        <option value="wide">Wide (420 × 640)</option>
                      </Select>
                    </Field>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <Field
                      label="Chat Header Title"
                      htmlFor="widget-launcher"
                      hint="Shown in the chat panel header and announced by the launcher."
                    >
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
                    {accentContrastRatio < 4.5 && (
                      <p
                        className="text-[10px] text-amber-300 mt-2 leading-relaxed"
                        role="status"
                      >
                        Text contrast is {accentContrastRatio.toFixed(2)}:1. Choose a color
                        with at least 4.5:1 contrast for readable text.
                      </p>
                    )}
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
                      Save Widget Appearance
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
                className="rounded-card overflow-hidden shadow-inner flex flex-col border transition-[width,height]"
                style={{
                  backgroundColor: pv.panelBg,
                  borderColor: pv.panelBorder,
                  width: `${panelPreviewSize.width}px`,
                  maxWidth: "100%",
                  height: `${panelPreviewSize.height}px`,
                  marginLeft: widgetPosition === "left" ? 0 : "auto",
                  marginRight: widgetPosition === "left" ? "auto" : 0,
                }}
              >
                <div
                  className="p-3 text-xs font-bold flex items-center justify-between"
                  style={{ backgroundColor: previewColor, color: previewHeaderTextColor }}
                >
                  <span className="tracking-tight truncate">
                    {launcherLabel || app?.name || "Chat Assistant"}
                  </span>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-current/30 px-2 py-1 text-[8px] font-semibold">
                      Contact us
                    </span>
                    <span aria-hidden="true" className="text-sm leading-none">×</span>
                  </div>
                </div>

                <div className="flex-1 p-4 space-y-3 overflow-y-auto">
                  <div className="flex gap-2">
                    <div
                      className="rounded-card px-3 py-2 text-[10px] leading-relaxed max-w-[80%] border"
                      style={{
                        backgroundColor: pv.botBubbleBg,
                        borderColor: pv.botBubbleBorder,
                        color: pv.bodyText,
                      }}
                    >
                      {greetingMsg || DEFAULT_WIDGET_GREETING}
                    </div>
                  </div>

                  {/* Starter prompt chips (shown to help users begin) */}
                  {starterPrompts.length > 0 && (
                    <div className="flex flex-wrap gap-1.5">
                      {starterPrompts.map((prompt, i) => (
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
              <div
                className={`flex items-center gap-3 pt-1 ${
                  widgetPosition === "left"
                    ? "flex-row-reverse justify-end"
                    : "justify-end"
                }`}
              >
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
                <span className="font-semibold text-slate-200">Application Chat Sandbox</span>
                <span className="text-slate-600">•</span>
                <span className="text-slate-400 font-mono text-[11px]">
                  POST /api/admin/conversations/application/{id}/sandbox/messages
                </span>
                <Badge variant="neutral" className="ml-1">
                  {app.name}
                </Badge>
              </div>

              <p className="w-full text-[10px] text-slate-500">
                This application-scoped test conversation restores after refresh
                and stays active until closed. Inactivity timeout applies to visitor
                chats; retention still applies to stored conversations.
              </p>

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
                        const value = e.target.value;
                        setSandboxApiKeys((current) => ({
                          ...current,
                          [id]: value,
                        }));
                        try {
                          const savedKeys = JSON.parse(
                            localStorage.getItem("oceanrag_sandbox_api_keys") || "{}"
                          );
                          savedKeys[id] = value;
                          localStorage.setItem(
                            "oceanrag_sandbox_api_keys",
                            JSON.stringify(savedKeys)
                          );
                        } catch {
                          localStorage.setItem(
                            "oceanrag_sandbox_api_keys",
                            JSON.stringify({ [id]: value })
                          );
                        }
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
                  disabled={isSandboxHistoryLoading || isChatLoading}
                  onClick={async () => {
                    if (sandboxConversationId) {
                      try {
                        await apiClient.delete(
                          `/admin/conversations/application/${id}/${sandboxConversationId}`
                        );
                      } catch (error) {
                        console.error(error);
                        toast.error("Failed to close the sandbox conversation.");
                        return;
                      }
                    }
                    setSandboxHistory([]);
                    setSandboxConversationId(null);
                    toast.success("Sandbox conversation closed.");
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
                {isSandboxHistoryLoading ? (
                  <div className="flex h-full items-center justify-center">
                    <Spinner className="h-6 w-6" />
                  </div>
                ) : sandboxHistory.length === 0 ? (
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
                  disabled={isSandboxHistoryLoading || isChatLoading}
                  className="flex-1 bg-[#040914]/50 border border-white/[0.10] focus:border-[#00D4FF] text-white text-[12px] rounded-control px-4 py-3 outline-none focus:ring-1 focus:ring-[#00D4FF] transition"
                  data-testid="chat-sandbox-input"
                  required
                />
                <Button
                  type="submit"
                  disabled={isSandboxHistoryLoading || isChatLoading || !sandboxQuestion.trim()}
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
        {activeTab === "conversations" && (
          <ConversationsTab
            applicationId={id}
            initialConversationId={conversationToOpen}
            onConversationClosed={(conversation) => {
              if (conversation.id === sandboxConversationId) {
                setSandboxHistory([]);
                setSandboxConversationId(null);
              }
            }}
          />
        )}
        {activeTab === "leads" && (
          <LeadsTab
            applicationId={id}
            onViewConversation={(conversationId) => {
              setConversationToOpen(conversationId);
              setActiveTab("conversations");
            }}
          />
        )}
        {activeTab === "feedback" && (
          <FeedbackTab
            applicationId={id}
            onViewConversation={(conversationId) => {
              setConversationToOpen(conversationId);
              setActiveTab("conversations");
            }}
          />
        )}

        {/* ======================= TAB: SETTINGS ======================= */}
        {activeTab === "settings" && (
          <form onSubmit={handleUpdateSettings} className="animate-fadeIn" data-testid="view-settings">
            <Card className="p-6 space-y-6">
              <div className="flex items-center gap-2">
                <Sliders className="h-4 w-4 text-[#00D4FF]" aria-hidden="true" />
                <span className="text-card-title text-white">RAG Settings & Parameter Core</span>
              </div>

              {!settings && !settingsLoadError && (
                <div className="text-center py-6 text-slate-400 text-[12px] border border-dashed border-white/[0.08] rounded-card">
                  No settings configured yet. Create settings by submitting this form.
                </div>
              )}

              {settingsLoadError && (
                <div
                  role="alert"
                  className="rounded-control border border-red-500/25 bg-red-500/[0.07] p-3 text-[12px] text-red-300"
                >
                  {settingsLoadError}
                </div>
              )}

              {settingsSaveError && (
                <div
                  role="alert"
                  className="rounded-control border border-red-500/25 bg-red-500/[0.07] p-3 text-[12px] text-red-300"
                >
                  {settingsSaveError}
                </div>
              )}

              {providerCatalog && (
                <div className="space-y-5 rounded-card border border-white/[0.06] p-4">
                  <div>
                    <h3 className="text-[13px] font-semibold text-white">AI Providers and Models</h3>
                    <p className="mt-1 text-[11px] text-slate-400">
                      Choices are limited to providers and models enabled by the platform.
                    </p>
                    <p className="mt-1 text-[11px] text-slate-500">
                      Hugging Face and NVIDIA inference require platform credentials. Model availability, free limits, and rates depend on each provider account.
                    </p>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <Field
                      label="Document Parser"
                      htmlFor="settings-parser-provider"
                      hint="Parser selection applies to supported PDF/DOCX modes; other source types keep their dedicated parsers."
                    >
                      <Select
                        id="settings-parser-provider"
                        value={settings?.parser_provider || ""}
                        onChange={(e) => {
                          setConfigurationValidation(null);
                          setSettings({ ...settings, parser_provider: e.target.value })
                        }}
                        data-testid="settings-parser-provider"
                      >
                        {parserOptions.map((option) => (
                          <option key={option.provider} value={option.provider}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </Field>

                    <Field label="Embedding Provider" htmlFor="settings-embedding-provider">
                      <Select
                        id="settings-embedding-provider"
                        value={settings?.embedding_provider || ""}
                        disabled={settings?.embedding_change_allowed === false}
                        onChange={(e) => {
                          setConfigurationValidation(null);
                          const nextModel = embeddingOptions.find(
                            (option) => option.provider === e.target.value
                          )?.model;
                          setSettings({
                            ...settings,
                            embedding_provider: e.target.value,
                            embedding_model: nextModel || "",
                          });
                        }}
                        data-testid="settings-embedding-provider"
                      >
                        {!embeddingProviders.includes(settings?.embedding_provider) &&
                          settings?.embedding_provider && (
                            <option value={settings.embedding_provider}>
                              {settings.embedding_provider} (legacy selection)
                            </option>
                          )}
                        {embeddingProviders.map((provider) => (
                          <option key={provider} value={provider}>
                            {providerLabel(provider)}
                          </option>
                        ))}
                      </Select>
                    </Field>

                    <Field label="Embedding Model" htmlFor="settings-embedding-model">
                      <Select
                        id="settings-embedding-model"
                        value={settings?.embedding_model || ""}
                        disabled={settings?.embedding_change_allowed === false}
                        onChange={(e) => {
                          setConfigurationValidation(null);
                          setSettings({ ...settings, embedding_model: e.target.value })
                        }}
                        data-testid="settings-embedding-model"
                      >
                        {!selectedEmbeddingModels.some(
                          (option) => option.model === settings?.embedding_model
                        ) &&
                          settings?.embedding_model && (
                            <option value={settings.embedding_model}>
                              {settings.embedding_model} (legacy selection)
                            </option>
                          )}
                        {selectedEmbeddingModels.map((option) => (
                          <option
                            key={`${option.provider}:${option.model}`}
                            value={option.model}
                          >
                            {option.label} ({option.embedding_dimensions} dimensions)
                          </option>
                        ))}
                      </Select>
                    </Field>

                    <Field label="LLM Provider" htmlFor="settings-llm-provider">
                      <Select
                        id="settings-llm-provider"
                        value={
                          llmProviders.includes(settings?.llm_provider)
                            ? settings.llm_provider
                            : ""
                        }
                        disabled={!llmProviders.length}
                        onChange={(e) => {
                          setConfigurationValidation(null);
                          const nextModel = llmOptions.find(
                            (option) => option.provider === e.target.value
                          )?.model;
                          setSettings({
                            ...settings,
                            llm_provider: e.target.value,
                            llm_model: nextModel || "",
                          });
                        }}
                        data-testid="settings-llm-provider"
                      >
                        <option value="" disabled>
                          Choose an enabled provider
                        </option>
                        {llmProviders.map((provider) => (
                          <option key={provider} value={provider}>
                            {providerLabel(provider)}
                          </option>
                        ))}
                      </Select>
                    </Field>

                    <Field label="Generation Model" htmlFor="settings-llm-model">
                      <Select
                        id="settings-llm-model"
                        value={
                          isCurrentLlmSelectionAvailable
                            ? settings.llm_model
                            : ""
                        }
                        disabled={!selectedLlmModels.length}
                        onChange={(e) => {
                          setConfigurationValidation(null);
                          setSettings({ ...settings, llm_model: e.target.value })
                        }}
                        data-testid="settings-llm-model"
                      >
                        <option value="" disabled>
                          Choose an enabled model
                        </option>
                        {selectedLlmModels.map((option) => (
                          <option
                            key={`${option.provider}:${option.model}`}
                            value={option.model}
                          >
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>

                  {providerCatalog && !isCurrentLlmSelectionAvailable && (
                    <p
                      role="status"
                      className="rounded-control border border-amber-500/25 bg-amber-500/[0.07] p-3 text-[11px] text-amber-200"
                      data-testid="llm-model-unavailable-warning"
                    >
                      The saved LLM provider or model is not enabled in the
                      backend catalog. Choose an available provider and model
                      before saving these settings.
                    </p>
                  )}

                  {settings?.embedding_change_allowed === false && (
                    <p
                      role="status"
                      className="rounded-control border border-amber-500/25 bg-amber-500/[0.07] p-3 text-[11px] text-amber-200"
                      data-testid="embedding-change-warning"
                    >
                      This application has published document vectors. Its embedding provider and model
                      cannot be changed until application-wide re-embedding support is available.
                    </p>
                  )}

                  <div className="space-y-3 border-t border-white/[0.06] pt-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                      <p className="max-w-2xl text-[11px] text-slate-400">
                        Validate saved selections against platform enablement and backend credential configuration.
                        This does not send provider requests or verify network connectivity.
                      </p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={handleValidateConfiguration}
                        loading={isValidatingConfiguration}
                        disabled={!settings?.id || isValidatingConfiguration}
                        data-testid="validate-ai-configuration"
                      >
                        Check configuration
                      </Button>
                    </div>
                    {configurationValidation && (
                      <div
                        role="status"
                        className="grid gap-2 sm:grid-cols-3"
                        data-testid="configuration-validation-results"
                      >
                        {configurationValidation.checks.map((check) => (
                          <div
                            key={check.capability}
                            className={`rounded-control border p-3 ${
                              check.ready
                                ? "border-emerald-500/20 bg-emerald-500/[0.05]"
                                : "border-amber-500/25 bg-amber-500/[0.07]"
                            }`}
                          >
                            <p className={`text-[11px] font-semibold ${
                              check.ready ? "text-emerald-300" : "text-amber-200"
                            }`}>
                              {check.capability}: {check.ready ? "Ready" : "Needs attention"}
                            </p>
                            <p className="mt-1 break-all text-[10px] text-slate-400">
                              {[check.provider, check.model].filter(Boolean).join(" / ")}
                            </p>
                            <p className="mt-1 text-[10px] text-slate-500">{check.message}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
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
                  <p className="mt-1 text-[10px] text-slate-500">
                    Closes idle visitor/widget conversations on their next
                    session or message. Admin sandbox conversations stay active
                    until closed.
                  </p>
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
                  <p className="mt-1 text-[10px] text-slate-500">
                    Deletes conversations after this many days without a message.
                    For closed conversations, the countdown starts when closed.
                    Active admin sandbox conversations are retained until closed.
                    Cleanup runs hourly.
                  </p>
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
                  disabled={
                    Boolean(settingsLoadError) ||
                    (Boolean(providerCatalog) && !isCurrentLlmSelectionAvailable)
                  }
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
            ? `Delete "${deleteTarget.name}"${deleteTarget.hasStoredSource ? ", its stored source file" : ""}, its database record, and indexed content? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        pending={isDeleting}
      />
    </PageShell>
  );
}
