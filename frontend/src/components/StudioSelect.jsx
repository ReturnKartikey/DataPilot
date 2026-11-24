import { useEffect, useRef, useState } from "react";

export default function StudioSelect({
  id,
  value,
  onChange,
  options = [],
  disabled = false,
  placeholder = "Select an option",
}) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef(null);
  const triggerRef = useRef(null);

  const selectedOption = options.find((opt) => opt.value === value) || options[0];

  useEffect(() => {
    const idx = options.findIndex((opt) => opt.value === value);
    if (idx >= 0) setActiveIndex(idx);
  }, [value, options, open]);

  useEffect(() => {
    if (!open) return undefined;
    function handleOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, [open]);

  function selectOption(opt) {
    if (!opt || disabled) return;
    onChange(opt.value);
    setOpen(false);
    triggerRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (disabled || !options.length) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
      } else {
        setActiveIndex((i) => (i + 1) % options.length);
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
      } else {
        setActiveIndex((i) => (i - 1 + options.length) % options.length);
      }
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
      } else if (options[activeIndex]) {
        selectOption(options[activeIndex]);
      }
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
    }
  }

  return (
    <div className="studio-select" ref={containerRef}>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        className={`studio-select-trigger ${open ? "open" : ""}`}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        onMouseDown={(e) => {
          if (disabled) return;
          e.preventDefault();
          triggerRef.current?.focus();
          setOpen((prev) => !prev);
        }}
        onKeyDown={handleKeyDown}
      >
        <span className="studio-select-value">
          <span className="studio-select-label">{selectedOption ? selectedOption.label : placeholder}</span>
          {selectedOption?.badge && <span className="studio-select-badge">{selectedOption.badge}</span>}
        </span>
        <span className={`studio-select-chevron ${open ? "open" : ""}`} aria-hidden="true">
          ▾
        </span>
      </button>

      {open && (
        <div className="studio-select-menu" role="listbox" aria-labelledby={id}>
          {options.map((opt, idx) => {
            const selected = opt.value === value;
            const highlighted = idx === activeIndex;
            return (
              <button
                key={String(opt.value)}
                type="button"
                role="option"
                aria-selected={selected}
                className={`studio-select-option ${selected ? "selected" : ""} ${highlighted ? "highlighted" : ""}`}
                onMouseEnter={() => setActiveIndex(idx)}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectOption(opt);
                }}
              >
                <span className="studio-select-opt-main">
                  <span>{opt.label}</span>
                  {opt.meta && <span className="studio-select-opt-meta">{opt.meta}</span>}
                </span>
                {opt.badge && <span className="studio-select-badge">{opt.badge}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
