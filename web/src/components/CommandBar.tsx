const SUGGESTIONS = ["NVDA", "AAPL", "TSLA", "MSFT", "AMZN"];

interface Props {
  value: string;
  onChange: (v: string) => void;
  onRun: () => void;
  disabled: boolean;
}

export default function CommandBar({ value, onChange, onRun, disabled }: Props) {
  return (
    <div className="command">
      <form
        className="command__row"
        onSubmit={(e) => {
          e.preventDefault();
          onRun();
        }}
      >
        <label className="command__field">
          <span className="command__prompt">$</span>
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="enter a ticker — e.g. NVDA"
            maxLength={12}
            autoFocus
            spellCheck={false}
            aria-label="Stock ticker"
          />
        </label>
        <button className="btn-run" type="submit" disabled={disabled || !value.trim()}>
          {disabled ? "Debating…" : "Run Debate"}
        </button>
      </form>
      <div className="quicks">
        {SUGGESTIONS.map((t) => (
          <button key={t} type="button" onClick={() => onChange(t)} disabled={disabled}>
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
