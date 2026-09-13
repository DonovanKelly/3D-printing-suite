/** Keep partially typed dimensions local until Enter/blur; never export an unapplied edit. */
import { createContext, useContext, useEffect, useRef, useState } from "react";

export const NumericEditing = createContext<(editing: boolean) => void>(
  () => {},
);

export function Numeric({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  const [draft, setDraft] = useState(String(value));
  const editing = useContext(NumericEditing);
  const dirty = useRef(false);
  const cancel = useRef(false);
  useEffect(() => setDraft(String(value)), [value]);
  useEffect(
    () => () => {
      if (dirty.current) editing(false);
    },
    [editing],
  );

  return (
    <label className="field-row">
      <span>{label}</span>
      <input
        type="number"
        value={draft}
        min={min}
        max={max}
        step={step}
        title="Press Enter or leave the field to apply. Escape cancels."
        onChange={(event) => {
          setDraft(event.target.value);
          dirty.current = event.target.value !== String(value);
          editing(dirty.current);
        }}
        onBlur={(event) => {
          const next = event.target.valueAsNumber;
          dirty.current = false;
          editing(false);
          if (!cancel.current && Number.isFinite(next) && next !== value)
            onChange(next);
          else setDraft(String(value));
          cancel.current = false;
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === "Escape") {
            event.preventDefault();
            cancel.current = event.key === "Escape";
            event.currentTarget.blur();
          }
        }}
      />
    </label>
  );
}
