import { useState, useEffect, useMemo, useCallback } from "react";
import { Link } from "react-router-dom";
import { apiClient } from "@/api/client";
import {
  Plus, Database, Cpu, Eye, Pencil, Power, Copy, Check,
  AlertTriangle, Search, FileText, BookOpen, Puzzle, Inbox, X,
} from "lucide-react";
import { toast } from "sonner";

import {
  Button, Badge, Card, SkeletonCard, SkeletonStatCard,
  ErrorBanner, StatusDot, Spinner,
} from "@/components/ui/Primitives";
import { PageShell, PageHeader, SectionHeader, Toolbar } from "@/components/ui/Layout";
import { StatCard, EmptyState } from "@/components/ui/Stats";
import { Modal, ConfirmDialog } from "@/components/ui/Overlays";
import { OverflowMenu } from "@/components/ui/OverflowMenu";

/* ============================================================
   DASHBOARD - Applications grid
   Layout: page header -> metrics band -> toolbar -> card grid.
   All metrics are derived from real API data (no placeholders).
   ============================================================ */

const CLIENT_LABELS = {
  website: "Website",
  mobile: "Mobile",
  desktop: "Desktop",
  api: "API",
};

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "—";
  }
}

export default function Dashboard() {
  const [apps, setApps] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Per-application metadata (document / KB / widget counts)
  const [meta, setMeta] = useState({});
  const [metaLoading, setMetaLoading] = useState(false);

  // Toolbar state
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [sortBy, setSortBy] = useState("newest");

  // Create / edit modal
  const [showModal, setShowModal] = useState(false);
  const [editingApp, setEditingApp] = useState(null);
  const [formName, setFormName] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formClientType, setFormClientType] = useState("website");
  const [formOrigins, setFormOrigins] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  // API key reveal
  const [keyModal, setKeyModal] = useState(null);
  const [copiedKey, setCopiedKey] = useState(false);

  // Styled deactivate confirmation
  const [confirmApp, setConfirmApp] = useState(null);
  const [isDeactivating, setIsDeactivating] = useState(false);

  /* ---------------- data loading ---------------- */

  const loadMeta = useCallback(async (list) => {
    if (!list.length) {
      setMeta({});
      return;
    }
    setMetaLoading(true);

    const results = await Promise.allSettled(
      list.map(async (app) => {
        const [kbsRes, widgetRes] = await Promise.allSettled([
          apiClient.get(`/admin/knowledge-bases/by-application/${app.id}`),
          apiClient.get(`/admin/widgets/application/${app.id}`),
        ]);

        const knowledgeBaseResponse =
          kbsRes.status === "fulfilled" ? kbsRes.value.data : null;
        const knowledgeBases = knowledgeBaseResponse
          ? Array.isArray(knowledgeBaseResponse)
            ? knowledgeBaseResponse
            : [knowledgeBaseResponse]
          : [];

        const docResults = await Promise.allSettled(
          knowledgeBases.map((knowledgeBase) =>
            apiClient.get(`/admin/documents?knowledge_base_id=${knowledgeBase.id}`)
          )
        );
        const docs = docResults.reduce(
          (sum, r) => sum + (r.status === "fulfilled" ? (r.value.data?.length || 0) : 0),
          0
        );

        return {
          id: app.id,
          kbs: knowledgeBases.length,
          docs,
          hasWidget: widgetRes.status === "fulfilled" && !!widgetRes.value.data,
        };
      })
    );

    const next = {};
    results.forEach((r) => {
      if (r.status === "fulfilled") next[r.value.id] = r.value;
    });
    setMeta(next);
    setMetaLoading(false);
  }, []);

  const loadApps = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const response = await apiClient.get("/admin/applications");
      setApps(response.data || []);
      loadMeta(response.data || []);
    } catch (e) {
      console.error(e);
      setLoadError(
        e.response?.data?.detail || "Could not reach the backend to load applications."
      );
    } finally {
      setIsLoading(false);
    }
  }, [loadMeta]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadApps();
  }, [loadApps]);

  /* ---------------- derived data ---------------- */

  const metrics = useMemo(() => {
    const values = Object.values(meta);
    return {
      applications: apps.length,
      active: apps.filter((a) => a.is_active).length,
      knowledgeBases: values.reduce((s, m) => s + (m.kbs || 0), 0),
      documents: values.reduce((s, m) => s + (m.docs || 0), 0),
      widgets: values.filter((m) => m.hasWidget).length,
    };
  }, [apps, meta]);

  const visibleApps = useMemo(() => {
    const term = search.trim().toLowerCase();

    let list = apps.filter((app) => {
      if (statusFilter === "active" && !app.is_active) return false;
      if (statusFilter === "inactive" && app.is_active) return false;
      if (!term) return true;
      return (
        app.name?.toLowerCase().includes(term) ||
        app.slug?.toLowerCase().includes(term) ||
        app.description?.toLowerCase().includes(term)
      );
    });

    list = [...list].sort((a, b) => {
      if (sortBy === "name") return (a.name || "").localeCompare(b.name || "");
      if (sortBy === "oldest")
        return new Date(a.created_at || 0) - new Date(b.created_at || 0);
      return new Date(b.created_at || 0) - new Date(a.created_at || 0);
    });

    return list;
  }, [apps, search, statusFilter, sortBy]);

  const isFiltered = search.trim() !== "" || statusFilter !== "all";

  /* ---------------- modal handlers ---------------- */

  const openCreateModal = () => {
    setEditingApp(null);
    setFormName("");
    setFormDesc("");
    setFormClientType("website");
    setFormOrigins("");
    setShowModal(true);
  };

  const openEditModal = (app) => {
    setEditingApp(app);
    setFormName(app.name);
    setFormDesc(app.description || "");
    setFormClientType(app.client_type);
    setFormOrigins((app.allowed_origins || []).join(", "));
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formName.trim() || isSubmitting) return;

    setIsSubmitting(true);
    const originsArray = formOrigins
      .split(",")
      .map((o) => o.trim())
      .filter(Boolean);

    try {
      if (editingApp) {
        await apiClient.put(`/admin/applications/${editingApp.id}`, {
          name: formName.trim(),
          description: formDesc.trim() || null,
          client_type: formClientType,
          allowed_origins: originsArray,
          is_active: editingApp.is_active,
        });
        toast.success(`Application "${formName}" updated!`);
        setShowModal(false);
        await loadApps();
      } else {
        const response = await apiClient.post("/admin/applications", {
          name: formName.trim(),
          description: formDesc.trim() || null,
          client_type: formClientType,
          allowed_origins: originsArray,
        });

        setShowModal(false);
        setKeyModal({
          key: response.data.api_key,
          prefix: response.data.api_key_prefix,
          name: response.data.application.name,
        });
        toast.success(`Application "${formName}" created!`, {
          description: "Save your API key now - it will not be shown again.",
        });
        await loadApps();
      }
    } catch (e) {
      console.error(e);
      toast.error(e.response?.data?.detail || "Operation failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeactivate = async () => {
    if (!confirmApp) return;
    setIsDeactivating(true);
    try {
      await apiClient.delete(`/admin/applications/${confirmApp.id}`);
      toast.success(`Application "${confirmApp.name}" deactivated.`);
      setConfirmApp(null);
      await loadApps();
    } catch (e) {
      console.error(e);
      toast.error("Failed to deactivate application.");
    } finally {
      setIsDeactivating(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
    toast.success("API key copied!");
  };

  /* ---------------- render ---------------- */

  return (
    <PageShell className="space-y-7">
      <PageHeader
        eyebrow="Workspace"
        title="Applications"
        subtitle="Register namespaces, provision embeddable widgets, and synchronise document indices within isolated application contexts."
        actions={
          <Button onClick={openCreateModal} data-testid="create-app-trigger">
            <Plus className="h-4 w-4" />
            <span>New Application</span>
          </Button>
        }
      />

      {/* Metrics band - all values derive from real API responses */}
      <section
        aria-label="Workspace metrics"
        className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
      >
        {isLoading ? (
          <>
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
            <SkeletonStatCard />
          </>
        ) : (
          <>
            <StatCard
              label="Applications"
              value={metrics.applications}
              hint={`${metrics.active} active`}
              icon={Database}
              tone="accent"
            />
            <StatCard
              label="Knowledge Bases"
              value={metaLoading ? "—" : metrics.knowledgeBases}
              hint="Across all namespaces"
              icon={BookOpen}
            />
            <StatCard
              label="Documents"
              value={metaLoading ? "—" : metrics.documents}
              hint="Indexed sources"
              icon={FileText}
            />
            <StatCard
              label="Widgets"
              value={metaLoading ? "—" : metrics.widgets}
              hint={`of ${metrics.applications} provisioned`}
              icon={Puzzle}
            />
          </>
        )}
      </section>

      {/* Toolbar: search, status filter, sort */}
      <div className="space-y-4">
        <Toolbar>
          <div className="relative flex-1 min-w-[200px]">
            <Search
              className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-500 pointer-events-none"
              aria-hidden="true"
            />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search applications..."
              aria-label="Search applications"
              className="w-full h-9 pl-9 pr-3 bg-surface border border-white/[0.08] rounded-[10px] text-[12px] text-white placeholder:text-slate-500 outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] transition"
              data-testid="app-search-input"
            />
          </div>

          <div className="flex items-center gap-1 p-0.5 bg-white/[0.03] border border-white/[0.07] rounded-[10px]">
            {[
              { key: "all", label: "All" },
              { key: "active", label: "Active" },
              { key: "inactive", label: "Inactive" },
            ].map((opt) => (
              <button
                key={opt.key}
                onClick={() => setStatusFilter(opt.key)}
                aria-pressed={statusFilter === opt.key}
                className={`px-3 h-8 rounded-[8px] text-[11px] font-semibold transition ${
                  statusFilter === opt.key
                    ? "bg-[#00D4FF] text-[#040914]"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>

          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            aria-label="Sort applications"
            className="h-9 px-3 bg-surface border border-white/[0.08] rounded-[10px] text-[12px] text-slate-300 outline-none focus:border-[#00D4FF] transition cursor-pointer"
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Name (A-Z)</option>
          </select>

          {isFiltered && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSearch("");
                setStatusFilter("all");
              }}
            >
              <X className="h-3.5 w-3.5" />
              Clear
            </Button>
          )}
        </Toolbar>

        <SectionHeader
          title="All Applications"
          count={`${visibleApps.length} shown`}
          actions={
            metaLoading ? (
              <span className="flex items-center gap-2 text-meta text-slate-500">
                <Spinner className="h-3 w-3" />
                Loading metrics
              </span>
            ) : null
          }
        />
      </div>

      {/* Body states */}
      {loadError ? (
        <ErrorBanner
          title="Could not load applications"
          message={loadError}
          onRetry={loadApps}
        />
      ) : isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : apps.length === 0 ? (
        <EmptyState
          icon={Database}
          title="No applications yet"
          message="Create an isolated namespace to begin uploading documents, styling the widget, and testing retrieval augmented generation."
          action={
            <Button onClick={openCreateModal}>
              <Plus className="h-4 w-4" />
              Create your first application
            </Button>
          }
        />
      ) : visibleApps.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No matching applications"
          message={
            search.trim()
              ? `Nothing matches "${search.trim()}". Try a different term or clear the filters.`
              : "No applications match the selected status filter."
          }
          action={
            <Button
              variant="outline"
              onClick={() => {
                setSearch("");
                setStatusFilter("all");
              }}
            >
              Clear filters
            </Button>
          }
        />
      ) : (
        <div
          className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4 gap-5"
          data-testid="applications-grid"
        >
          {visibleApps.map((app) => {
            const info = meta[app.id];
            return (
              <Card
                key={app.id}
                interactive
                className={`p-5 flex flex-col min-h-[200px] ${
                  app.is_active ? "" : "opacity-65"
                }`}
                data-testid={`app-card-${app.id}`}
              >
                {/* header zone */}
                <div className="flex items-start justify-between gap-3">
                  <Link
                    to={`/admin/applications/${app.id}`}
                    className="flex items-center gap-3 min-w-0 group"
                    data-testid={`app-link-${app.id}`}
                  >
                    <span className="p-2 rounded-[10px] bg-white/[0.04] border border-white/[0.07] text-[#00D4FF] flex-shrink-0">
                      <Database className="h-4 w-4" aria-hidden="true" />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-card-title text-slate-100 group-hover:text-[#00D4FF] transition truncate">
                        {app.name}
                      </span>
                      <span className="block text-[10px] font-mono text-slate-500 truncate">
                        {app.slug}
                      </span>
                    </span>
                  </Link>

                  <OverflowMenu
                    items={[
                      {
                        label: "Open",
                        icon: Eye,
                        onSelect: () => {
                          window.location.href = `/admin/applications/${app.id}`;
                        },
                      },
                      {
                        label: "Edit details",
                        icon: Pencil,
                        onSelect: () => openEditModal(app),
                      },
                      {
                        label: "Deactivate",
                        icon: Power,
                        danger: true,
                        disabled: !app.is_active,
                        onSelect: () => setConfirmApp(app),
                      },
                    ]}
                  />
                </div>

                {/* description */}
                <p className="text-body text-slate-500 mt-3 line-clamp-2 min-h-[34px]">
                  {app.description || "No description provided for this namespace."}
                </p>

                {/* metadata zone */}
                <div className="mt-auto pt-4 border-t border-white/[0.06] space-y-2.5">
                  <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 text-meta text-slate-400">
                    <span className="flex items-center gap-1.5">
                      <FileText className="h-3 w-3 text-slate-500" aria-hidden="true" />
                      {info ? `${info.docs} docs` : "—"}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <BookOpen className="h-3 w-3 text-slate-500" aria-hidden="true" />
                      {info ? `${info.kbs} KB` : "—"}
                    </span>
                    <span className="flex items-center gap-1.5">
                      <Cpu className="h-3 w-3 text-slate-500" aria-hidden="true" />
                      {CLIENT_LABELS[app.client_type] || app.client_type}
                    </span>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-1.5 text-[10px] font-mono text-slate-500">
                      {app.is_active ? (
                        <>
                          <StatusDot variant="success" />
                          {formatDate(app.created_at)}
                        </>
                      ) : (
                        <>
                          <StatusDot variant="danger" />
                          Deactivated
                        </>
                      )}
                    </span>

                    {app.is_active ? (
                      <Badge variant="success">Active</Badge>
                    ) : (
                      <Badge variant="danger">Inactive</Badge>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create / Edit modal */}
      <Modal
        open={showModal}
        onClose={() => (isSubmitting ? null : setShowModal(false))}
        title={editingApp ? "Edit Application" : "Create Application"}
        description={
          editingApp
            ? `Update the configuration for "${editingApp.name}".`
            : "Isolated context mapping a specific knowledge base."
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setShowModal(false)} disabled={isSubmitting}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="app-form"
              loading={isSubmitting}
              disabled={!formName.trim()}
              data-testid="app-form-submit"
            >
              {editingApp ? "Save Changes" : "Create Application"}
            </Button>
          </>
        }
      >
        <form id="app-form" onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label htmlFor="app-name" className="block text-meta text-slate-300 mb-1.5">
              Name <span className="text-red-400">*</span>
            </label>
            <input
              id="app-name"
              type="text"
              value={formName}
              onChange={(e) => setFormName(e.target.value)}
              placeholder="e.g. FAQ Support Assistant"
              className="w-full h-10 px-3.5 bg-surface border border-white/[0.08] rounded-control text-[12px] text-white placeholder:text-slate-600 outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] transition"
              required
              data-testid="app-form-name"
            />
          </div>

          <div>
            <label htmlFor="app-desc" className="block text-meta text-slate-300 mb-1.5">
              Description
            </label>
            <textarea
              id="app-desc"
              value={formDesc}
              onChange={(e) => setFormDesc(e.target.value)}
              placeholder="Describe the application scope..."
              rows={3}
              className="w-full px-3.5 py-2.5 bg-surface border border-white/[0.08] rounded-control text-[12px] text-white placeholder:text-slate-600 outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] transition resize-none"
              data-testid="app-form-desc"
            />
          </div>

          <div>
            <label htmlFor="app-client" className="block text-meta text-slate-300 mb-1.5">
              Client Type <span className="text-red-400">*</span>
            </label>
            <select
              id="app-client"
              value={formClientType}
              onChange={(e) => setFormClientType(e.target.value)}
              className="w-full h-10 px-3.5 bg-surface border border-white/[0.08] rounded-control text-[12px] text-white outline-none focus:border-[#00D4FF] transition cursor-pointer"
              required
              data-testid="app-form-client-type"
            >
              <option value="website">Website</option>
              <option value="mobile">Mobile App</option>
              <option value="desktop">Desktop App</option>
              <option value="api">API Integration</option>
            </select>
          </div>

          <div>
            <label htmlFor="app-origins" className="block text-meta text-slate-300 mb-1.5">
              Allowed Origins
            </label>
            <input
              id="app-origins"
              type="text"
              value={formOrigins}
              onChange={(e) => setFormOrigins(e.target.value)}
              placeholder="https://example.com, https://app.example.com"
              className="w-full h-10 px-3.5 bg-surface border border-white/[0.08] rounded-control text-[12px] text-white placeholder:text-slate-600 outline-none focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF] transition font-mono"
              data-testid="app-form-origins"
            />
            <p className="text-[10px] text-slate-500 mt-1.5">
              Comma separated. Leave empty to allow all origins.
            </p>
          </div>
        </form>
      </Modal>

      {/* API key reveal - shown once on create */}
      <Modal
        open={!!keyModal}
        onClose={() => setKeyModal(null)}
        title="API Key Generated"
        description={keyModal ? `For application: ${keyModal.name}` : undefined}
        footer={
          <Button className="w-full" onClick={() => setKeyModal(null)} data-testid="api-key-close-btn">
            I have saved my key
          </Button>
        }
      >
        {keyModal && (
          <div className="space-y-4">
            <div className="flex items-start gap-2.5 p-3 bg-amber-500/10 border border-amber-500/20 rounded-[10px]">
              <AlertTriangle className="h-4 w-4 text-amber-400 flex-shrink-0 mt-0.5" aria-hidden="true" />
              <div>
                <p className="text-[11px] font-semibold text-amber-300">
                  This key will not be shown again
                </p>
                <p className="text-[10px] text-amber-400/80 mt-0.5 leading-relaxed">
                  Copy it now and store it securely. The backend only returns the full API key
                  once, at creation time.
                </p>
              </div>
            </div>

            <div>
              <span className="block text-eyebrow text-slate-500 mb-1.5">Full API Key</span>
              <div className="flex items-center gap-2 surface-inset rounded-[10px] p-3">
                <code
                  className="flex-1 text-slate-200 font-mono text-[11px] select-all break-all leading-relaxed"
                  data-testid="api-key-value"
                >
                  {keyModal.key}
                </code>
                <button
                  onClick={() => copyToClipboard(keyModal.key)}
                  aria-label="Copy API key"
                  className="shrink-0 p-2 rounded-[8px] border border-white/[0.10] text-slate-300 hover:text-[#00D4FF] hover:border-[#00D4FF]/30 transition"
                  data-testid="api-key-copy-btn"
                >
                  {copiedKey ? (
                    <Check className="h-4 w-4 text-emerald-400" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <div>
              <span className="block text-eyebrow text-slate-500 mb-1.5">Key Prefix</span>
              <code className="text-slate-300 font-mono text-[11px]">{keyModal.prefix}</code>
            </div>
          </div>
        )}
      </Modal>

      {/* Deactivate confirmation */}
      <ConfirmDialog
        open={!!confirmApp}
        onCancel={() => setConfirmApp(null)}
        onConfirm={handleDeactivate}
        title="Deactivate application"
        message={
          confirmApp
            ? `Are you sure you want to deactivate "${confirmApp.name}"? Its API key will stop working until the application is reactivated.`
            : ""
        }
        confirmLabel="Deactivate"
        pending={isDeactivating}
      />
    </PageShell>
  );
}
