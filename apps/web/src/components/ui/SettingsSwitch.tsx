import { useId } from "react";

/** A labelled native checkbox with switch semantics and a non-shrinking visible track. */
export function SettingsSwitch({ label, description, checked, onChange, disabled = false }: {
  label: string;
  description?: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}) {
  const id = useId();
  return (
    <label className="settings-switch">
      <span className="settings-switch-copy">
        <span>{label}</span>
        {description && <small id={`${id}-help`}>{description}</small>}
      </span>
      <span className="settings-switch-control">
        <input type="checkbox" role="switch" aria-label={label}
          aria-describedby={description ? `${id}-help` : undefined}
          checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />
        <span className="settings-switch-track" aria-hidden="true" />
      </span>
    </label>
  );
}
