/** Render text with entity spans visually highlighted. */
import { type Entity } from './api';

const TYPE_COLORS: Record<string, string> = {
  PII_NAME: 'bg-amber-100 text-amber-900',
  PII_SSN: 'bg-rose-100 text-rose-900',
  PII_EMAIL: 'bg-sky-100 text-sky-900',
  PII_PHONE: 'bg-cyan-100 text-cyan-900',
  PII_DOB: 'bg-violet-100 text-violet-900',
  PII_ADDRESS: 'bg-fuchsia-100 text-fuchsia-900',
  PHI_DIAGNOSIS: 'bg-emerald-100 text-emerald-900',
  PHI_MEDICATION: 'bg-teal-100 text-teal-900',
  PHI_MRN: 'bg-lime-100 text-lime-900',
  PHI_INSURANCE_ID: 'bg-green-100 text-green-900',
  FIN_ACCOUNT_NUMBER: 'bg-orange-100 text-orange-900',
  FIN_TAX_ID: 'bg-red-100 text-red-900',
  LEGAL_PRIVILEGE: 'bg-slate-200 text-slate-900',
};

const DEFAULT_COLOR = 'bg-gray-100 text-gray-900';

export function HighlightedText({ text, entities }: { text: string; entities: Entity[] }) {
  if (!entities.length) {
    return <span className="whitespace-pre-wrap">{text}</span>;
  }
  // Sort by start; render gaps + highlighted spans.
  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const parts: React.ReactNode[] = [];
  let cursor = 0;
  for (const e of sorted) {
    if (e.start > cursor) {
      parts.push(
        <span key={`gap-${cursor}`}>{text.slice(cursor, e.start)}</span>,
      );
    }
    const color = TYPE_COLORS[e.type] ?? DEFAULT_COLOR;
    parts.push(
      <span
        key={`e-${e.start}`}
        className={`rounded px-1 ${color}`}
        title={`${e.type} (${(e.confidence * 100).toFixed(0)}%)`}
      >
        {text.slice(e.start, e.end)}
      </span>,
    );
    cursor = e.end;
  }
  if (cursor < text.length) {
    parts.push(<span key="tail">{text.slice(cursor)}</span>);
  }
  return <span className="whitespace-pre-wrap">{parts}</span>;
}
