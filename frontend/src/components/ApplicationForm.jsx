import { useState, useEffect } from "react";
import { X, Plus, Trash2, AlertCircle } from "lucide-react";
import { apiClient } from "@/api/client";
import { toast } from "sonner";

export default function ApplicationForm({ app, onClose, onSuccess }) {
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    client_type: "",
    allowed_origins: [],
    is_active: true,
  });
  const [newOrigin, setNewOrigin] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({});

  useEffect(() => {
    if (app) {
      setFormData({
        name: app.name || "",
        description: app.description || "",
        client_type: app.client_type || "",
        allowed_origins: app.allowed_origins || [],
        is_active: app.is_active !== false,
      });
    }
  }, [app]);

  const validateOrigin = (origin) => {
    try {
      new URL(origin);
      return true;
    } catch {
      return false;
    }
  };

  const addOrigin = () => {
    if (!newOrigin.trim()) {
      toast.error("Please enter an origin URL");
      return;
    }
    if (!validateOrigin(newOrigin.trim())) {
      toast.error("Invalid URL format. Example: https://example.com");
      return;
    }
    if (formData.allowed_origins.includes(newOrigin.trim())) {
      toast.error("This origin is already added");
      return;
    }
    setFormData({
      ...formData,
      allowed_origins: [...formData.allowed_origins, newOrigin.trim()],
    });
    setNewOrigin("");
  };

  const removeOrigin = (index) => {
    setFormData({
      ...formData,
      allowed_origins: formData.allowed_origins.filter((_, i) => i !== index),
    });
  };

  const validateForm = () => {
    const newErrors = {};
    if (!formData.name.trim()) newErrors.name = "Application name is required";
    if (!formData.client_type.trim()) newErrors.client_type = "Client type is required";
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    setIsLoading(true);
    try {
      if (app?.id) {
        // Update existing application
        await apiClient.put(`/admin/applications/${app.id}`, {
          name: formData.name,
          description: formData.description,
          client_type: formData.client_type,
          allowed_origins: formData.allowed_origins,
          is_active: formData.is_active,
        });
        toast.success("Application updated successfully!");
      } else {
        // Create new application
        await apiClient.post("/admin/applications", {
          name: formData.name,
          description: formData.description,
          client_type: formData.client_type,
          allowed_origins: formData.allowed_origins,
        });
        toast.success("Application created successfully!");
      }
      onSuccess?.();
      onClose?.();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to save application");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-900 rounded-2xl border border-white/10 max-w-2xl w-full max-h-96 overflow-y-auto">
        {/* Header */}
        <div className="sticky top-0 flex items-center justify-between p-6 border-b border-white/10 bg-slate-900">
          <h2 className="text-xl font-semibold text-white">
            {app?.id ? "Edit Application" : "Create New Application"}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-white transition"
            disabled={isLoading}
          >
            <X size={24} />
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Application Name *
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) =>
                setFormData({ ...formData, name: e.target.value })
              }
              placeholder="My App"
              className={`w-full px-4 py-2 bg-slate-800 border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 ${
                errors.name ? "border-red-500" : "border-white/10"
              }`}
              disabled={isLoading}
            />
            {errors.name && (
              <p className="text-red-500 text-xs mt-1">{errors.name}</p>
            )}
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Description
            </label>
            <textarea
              value={formData.description}
              onChange={(e) =>
                setFormData({ ...formData, description: e.target.value })
              }
              placeholder="Optional description..."
              rows="3"
              className="w-full px-4 py-2 bg-slate-800 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
              disabled={isLoading}
            />
          </div>

          {/* Client Type */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Client Type *
            </label>
            <input
              type="text"
              value={formData.client_type}
              onChange={(e) =>
                setFormData({ ...formData, client_type: e.target.value })
              }
              placeholder="e.g., web, mobile, api"
              className={`w-full px-4 py-2 bg-slate-800 border rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 ${
                errors.client_type ? "border-red-500" : "border-white/10"
              }`}
              disabled={isLoading}
            />
            {errors.client_type && (
              <p className="text-red-500 text-xs mt-1">{errors.client_type}</p>
            )}
          </div>

          {/* Allowed Origins */}
          <div>
            <label className="block text-sm font-medium text-slate-300 mb-2 flex items-center gap-2">
              Allowed Origins
              <span className="text-xs bg-amber-500/20 text-amber-300 px-2 py-1 rounded">
                Leave empty to allow all origins
              </span>
            </label>

            {/* Origin Input */}
            <div className="flex gap-2 mb-3">
              <input
                type="url"
                value={newOrigin}
                onChange={(e) => setNewOrigin(e.target.value)}
                onKeyPress={(e) => e.key === "Enter" && addOrigin()}
                placeholder="https://example.com"
                className="flex-1 px-4 py-2 bg-slate-800 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                disabled={isLoading}
              />
              <button
                type="button"
                onClick={addOrigin}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg flex items-center gap-2 transition disabled:opacity-50"
                disabled={isLoading}
              >
                <Plus size={18} />
              </button>
            </div>

            {/* Origins List */}
            {formData.allowed_origins.length > 0 ? (
              <div className="space-y-2">
                {formData.allowed_origins.map((origin, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between px-4 py-2 bg-slate-800 border border-white/10 rounded-lg"
                  >
                    <code className="text-sm text-cyan-400 break-all">
                      {origin}
                    </code>
                    <button
                      type="button"
                      onClick={() => removeOrigin(idx)}
                      className="text-slate-400 hover:text-red-500 transition"
                      disabled={isLoading}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="px-4 py-3 bg-slate-800/50 border border-dashed border-white/20 rounded-lg flex items-center gap-2 text-slate-400 text-sm">
                <AlertCircle size={16} />
                <span>No origins configured - all origins will be allowed</span>
              </div>
            )}
          </div>

          {/* Active Status */}
          {app?.id && (
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="is_active"
                checked={formData.is_active}
                onChange={(e) =>
                  setFormData({ ...formData, is_active: e.target.checked })
                }
                className="w-4 h-4 rounded bg-slate-800 border border-white/10 text-cyan-600 focus:ring-2 focus:ring-cyan-500"
                disabled={isLoading}
              />
              <label
                htmlFor="is_active"
                className="text-sm font-medium text-slate-300"
              >
                Active
              </label>
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3 pt-4 border-t border-white/10">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 px-4 py-2 border border-white/10 text-slate-300 rounded-lg hover:bg-white/5 transition disabled:opacity-50"
              disabled={isLoading}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex-1 px-4 py-2 bg-cyan-600 hover:bg-cyan-700 text-white rounded-lg transition disabled:opacity-50"
              disabled={isLoading}
            >
              {isLoading ? "Saving..." : app?.id ? "Update" : "Create"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
