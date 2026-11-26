import { useState } from "react";
import { CalendarDays, ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/Primitives";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function toDateKey(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function fromDateKey(value) {
  if (!value) return null;
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, month - 1, day);
}

function displayDate(value) {
  const date = fromDateKey(value);
  return date?.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function DateRangePicker({
  dateFrom,
  dateTo,
  onChange,
  filterLabel = "date",
  helperText = "Filter by date",
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [visibleMonth, setVisibleMonth] = useState(() => {
    const initial = fromDateKey(dateFrom) || new Date();
    return new Date(initial.getFullYear(), initial.getMonth(), 1);
  });

  const currentYear = new Date().getFullYear();
  const firstWeekday = new Date(
    visibleMonth.getFullYear(),
    visibleMonth.getMonth(),
    1
  ).getDay();
  const daysInMonth = new Date(
    visibleMonth.getFullYear(),
    visibleMonth.getMonth() + 1,
    0
  ).getDate();
  const calendarCells = [
    ...Array(firstWeekday).fill(null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];

  const moveMonth = (difference) => {
    setVisibleMonth(
      (current) =>
        new Date(
          current.getFullYear(),
          current.getMonth() + difference,
          1
        )
    );
  };

  const selectDate = (dateKey) => {
    if (!dateFrom || dateTo) {
      onChange(dateKey, "");
      return;
    }
    if (dateKey < dateFrom) {
      onChange(dateKey, dateFrom);
    } else {
      onChange(dateFrom, dateKey);
    }
  };

  const rangeLabel = dateFrom
    ? `${displayDate(dateFrom)}${dateTo ? ` – ${displayDate(dateTo)}` : " – choose end"}`
    : "All dates";

  return (
    <div className="relative">
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="min-w-[210px] justify-start"
        aria-expanded={isOpen}
        aria-label={`Filter by ${filterLabel} range: ${rangeLabel}`}
        onClick={() => {
          if (!isOpen) {
            const initial = fromDateKey(dateFrom) || fromDateKey(dateTo) || new Date();
            setVisibleMonth(new Date(initial.getFullYear(), initial.getMonth(), 1));
          }
          setIsOpen((open) => !open);
        }}
      >
        <CalendarDays className="h-3.5 w-3.5" />
        <span>{rangeLabel}</span>
      </Button>

      {isOpen && (
        <div
          className="absolute left-0 top-full z-30 mt-2 w-[300px] rounded-card border border-white/[0.12] bg-[#0D1526] p-4 shadow-raised"
          role="dialog"
          aria-label={`Choose ${filterLabel} range`}
        >
          <div className="mb-3 flex items-center justify-between gap-2">
            <button
              type="button"
              onClick={() => moveMonth(-1)}
              className="rounded-control p-2 text-slate-400 hover:bg-white/[0.06] hover:text-white"
              aria-label="Previous month"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <div className="flex items-center gap-2">
              <select
                value={visibleMonth.getMonth()}
                onChange={(event) =>
                  setVisibleMonth(
                    new Date(
                      visibleMonth.getFullYear(),
                      Number(event.target.value),
                      1
                    )
                  )
                }
                className="rounded-control border border-white/[0.10] bg-[#0B1221] px-2 py-1 text-xs text-slate-200"
                aria-label="Calendar month"
              >
                {MONTHS.map((month, index) => (
                  <option key={month} value={index}>{month}</option>
                ))}
              </select>
              <select
                value={visibleMonth.getFullYear()}
                onChange={(event) =>
                  setVisibleMonth(
                    new Date(
                      Number(event.target.value),
                      visibleMonth.getMonth(),
                      1
                    )
                  )
                }
                className="rounded-control border border-white/[0.10] bg-[#0B1221] px-2 py-1 text-xs text-slate-200"
                aria-label="Calendar year"
              >
                {Array.from({ length: currentYear - 1900 + 2 }, (_, index) => 1900 + index)
                  .map((year) => (
                    <option key={year} value={year}>{year}</option>
                  ))}
              </select>
            </div>
            <button
              type="button"
              onClick={() => moveMonth(1)}
              className="rounded-control p-2 text-slate-400 hover:bg-white/[0.06] hover:text-white"
              aria-label="Next month"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>

          <div className="grid grid-cols-7 text-center text-[10px] font-semibold text-slate-500">
            {WEEKDAYS.map((day) => <span key={day} className="py-2">{day}</span>)}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {calendarCells.map((day, index) => {
              if (!day) return <span key={`blank-${index}`} />;
              const dateKey = toDateKey(
                new Date(
                  visibleMonth.getFullYear(),
                  visibleMonth.getMonth(),
                  day
                )
              );
              const isSelected = dateKey === dateFrom || dateKey === dateTo;
              const isInRange = dateFrom && dateTo
                && dateKey > dateFrom
                && dateKey < dateTo;
              return (
                <button
                  key={dateKey}
                  type="button"
                  onClick={() => selectDate(dateKey)}
                  aria-pressed={isSelected}
                  className={`h-8 rounded-control text-xs transition ${
                    isSelected
                      ? "bg-[#00D4FF] font-semibold text-[#040914]"
                      : isInRange
                        ? "bg-[#00D4FF]/15 text-[#9BEAFF]"
                        : "text-slate-300 hover:bg-white/[0.08]"
                  }`}
                >
                  {day}
                </button>
              );
            })}
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-white/[0.08] pt-3">
            <span className="text-[10px] text-slate-500">
              {dateFrom && !dateTo ? "Select an end date" : helperText}
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => onChange("", "")}
              >
                Clear
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setIsOpen(false)}
              >
                Done
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
