import { useEffect, useRef, useState } from "react";
import { GripVertical, Plus, Trash2 } from "lucide-react";

/* ============================================================
   STARTER PROMPTS
   Editable list of "starter prompt" chips shown to end users in
   the widget. Controlled: `value` is an array of strings.
   Supports add (auto-focused for immediate typing), inline edit,
  remove and drag-to-reorder (drag via the grip handle only, so
  text selection in the fields keeps working normally). The parent
  persists the controlled list through the widget settings API.
   ============================================================ */

export function StarterPrompts({ value = [], onChange, className = "" }) {
  const dragIndex = useRef(null);
  const inputRefs = useRef([]);
  const focusIndexRef = useRef(null);
  const [dragOver, setDragOver] = useState(null);

  const update = (next) => onChange(next);

  // After adding a row, focus + select its text so the admin can type
  // the question straight away without an extra click.
  useEffect(() => {
    const idx = focusIndexRef.current;
    if (idx === null) return;
    const el = inputRefs.current[idx];
    if (el) {
      el.focus();
      el.select();
    }
    focusIndexRef.current = null;
  }, [value]);

  const addPrompt = () => {
    focusIndexRef.current = value.length;
    update([...value, "New question"]);
  };

  const editPrompt = (index, text) => {
    const next = value.map((p, i) => (i === index ? text : p));
    update(next);
  };

  const removePrompt = (index) => {
    update(value.filter((_, i) => i !== index));
  };

  const handleDragStart = (index) => (e) => {
    dragIndex.current = index;
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e, index) => {
    e.preventDefault();
    if (dragOver !== index) setDragOver(index);
  };

  const handleDrop = (index) => {
    const from = dragIndex.current;
    dragIndex.current = null;
    setDragOver(null);
    if (from === null || from === index) return;
    const next = [...value];
    const [moved] = next.splice(from, 1);
    next.splice(index, 0, moved);
    update(next);
  };

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="space-y-2.5">
        {value.length === 0 && (
          <p className="text-[11px] text-slate-500 italic py-1">
            No starter prompts yet. Add one to guide users with suggested questions.
          </p>
        )}

        {value.map((prompt, index) => (
          <div
            key={index}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragLeave={() => setDragOver((v) => (v === index ? null : v))}
            onDrop={() => handleDrop(index)}
            className={`flex items-center gap-2 rounded-card border px-3 py-2 transition ${
              dragOver === index
                ? "border-[#00D4FF]/50 bg-[#00D4FF]/5"
                : "border-white/[0.08] bg-white/[0.02] hover:border-white/[0.16]"
            }`}
          >
            <span
              draggable
              onDragStart={handleDragStart(index)}
              onDragEnd={() => {
                dragIndex.current = null;
                setDragOver(null);
              }}
              className="text-slate-500 cursor-grab active:cursor-grabbing flex-shrink-0"
              aria-hidden="true"
              title="Drag to reorder"
            >
              <GripVertical className="h-4 w-4" />
            </span>

            <input
              ref={(el) => (inputRefs.current[index] = el)}
              type="text"
              value={prompt}
              onChange={(e) => editPrompt(index, e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  addPrompt();
                }
              }}
              placeholder="Type the question users can start with..."
              aria-label={`Starter prompt ${index + 1}`}
              className="flex-1 min-w-0 bg-transparent border-0 outline-none text-[12px] font-semibold text-slate-100 placeholder:text-slate-600 focus:ring-0"
            />

            <button
              type="button"
              onClick={() => removePrompt(index)}
              title="Remove starter prompt"
              aria-label={`Remove starter prompt ${index + 1}`}
              className="flex-shrink-0 p-1.5 rounded-[8px] border border-red-500/15 hover:border-red-500/40 hover:bg-red-500/10 text-red-400 hover:text-red-300 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500/40"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={addPrompt}
        className="inline-flex items-center gap-2 px-3.5 h-9 rounded-[10px] border border-white/[0.12] text-[12px] font-semibold text-slate-300 hover:border-[#00D4FF]/40 hover:text-[#00D4FF] hover:bg-[#00D4FF]/5 transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00D4FF]"
      >
        <Plus className="h-3.5 w-3.5" />
        <span>Add starter prompt</span>
      </button>
    </div>
  );
}