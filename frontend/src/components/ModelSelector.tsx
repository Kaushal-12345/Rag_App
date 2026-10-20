import { shortModelName } from "@/lib/api";

type Props = {
  models: string[];
  value: string;
  onChange: (model: string) => void;
  disabled?: boolean;
};

export function ModelSelector({ models, value, onChange, disabled }: Props) {
  return (
    <label className={`flex items-center gap-2 text-sm ${disabled ? "opacity-50" : ""}`}>
      <span className="text-neutral-500">Model</span>
      <select
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-lg border border-neutral-300 bg-white px-2 py-1.5 text-sm dark:border-neutral-700 dark:bg-neutral-900"
      >
        {models.map((model) => (
          <option key={model} value={model}>
            {shortModelName(model)}
          </option>
        ))}
      </select>
    </label>
  );
}
