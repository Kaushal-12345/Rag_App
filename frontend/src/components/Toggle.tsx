type Props = {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
  title?: string;
};

/** Small switch used for "Web search" and "Compare models". */
export function Toggle({ label, checked, onChange, title }: Props) {
  return (
    <label className="flex cursor-pointer select-none items-center gap-2 text-sm" title={title}>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition ${checked ? "bg-indigo-600" : "bg-neutral-300 dark:bg-neutral-700"}`}
      >
        <span
          className={`absolute top-0.5 h-4 w-4 rounded-full bg-white transition-all ${checked ? "left-[1.1rem]" : "left-0.5"}`}
        />
      </button>
      <span>{label}</span>
    </label>
  );
}
