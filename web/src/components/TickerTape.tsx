const MESSAGES = [
  "EDUCATIONAL ONLY — NOT FINANCIAL ADVICE",
  "POWERED BY GEMINI + GOOGLE ADK",
  "TRACED & SCORED BY ARIZE PHOENIX",
  "THE MARKET IS A DEBATE",
];

function Line({ k }: { k: string }) {
  return (
    <>
      {MESSAGES.map((m, i) => (
        <span key={`${k}-${i}`} className={m.includes("NOT FINANCIAL") ? "hot" : ""}>
          {m} &nbsp;◆
        </span>
      ))}
    </>
  );
}

export default function TickerTape() {
  return (
    <div className="tape" role="note" aria-label="Disclaimer">
      <div className="tape__track">
        <Line k="a" />
        <Line k="b" />
      </div>
    </div>
  );
}
