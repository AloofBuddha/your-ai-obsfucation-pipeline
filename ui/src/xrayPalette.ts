/** Entity color palette + derivations used by the X-Ray workbench.
 *
 * Tailwind cannot dynamically resolve a class name from a runtime entity type,
 * so entity-type colors live as inline-style objects (fg/bg/dot) and get applied
 * via `style={{ ... }}` in the highlight + token components.
 */
import { type Entity } from './api';

export interface EntitySwatch {
  fg: string;
  bg: string;
  dot: string;
}

const ENTITY_COLORS: Record<string, EntitySwatch> = {
  PII_NAME:           { fg: '#7a3f1a', bg: '#f4e1cb', dot: '#c08a4a' },
  PII_DOB:            { fg: '#3f2a6e', bg: '#e4dff2', dot: '#6e57b4' },
  PII_ADDRESS:        { fg: '#6e1f59', bg: '#f2dbeb', dot: '#b04c93' },
  PII_PHONE:          { fg: '#1d4f63', bg: '#d5e8ee', dot: '#3a8aa6' },
  PII_EMAIL:          { fg: '#1d4f63', bg: '#d5e8ee', dot: '#3a8aa6' },
  PII_SSN:            { fg: '#7a1f23', bg: '#f1d3d4', dot: '#b8514e' },
  PHI_DIAGNOSIS:      { fg: '#1f5230', bg: '#dceadf', dot: '#3f8a5a' },
  PHI_MEDICATION:     { fg: '#175249', bg: '#d4e8e3', dot: '#3c8a7a' },
  PHI_MRN:            { fg: '#4a5a1f', bg: '#e5e8cf', dot: '#7e9335' },
  PHI_INSURANCE_ID:   { fg: '#3a5a1f', bg: '#dee8cf', dot: '#6c8c35' },
  FIN_ACCOUNT_NUMBER: { fg: '#7a3a0e', bg: '#f2dbc6', dot: '#b07033' },
  FIN_TAX_ID:         { fg: '#7a1f1f', bg: '#f1d3d3', dot: '#b85050' },
  LEGAL_PRIVILEGE:    { fg: '#3a3a3a', bg: '#dcdcd4', dot: '#6a6a64' },
};

const DEFAULT_SWATCH: EntitySwatch = { fg: '#3a3a3a', bg: '#e4e0d4', dot: '#7a7468' };

export function entityColor(type: string): EntitySwatch {
  return ENTITY_COLORS[type] ?? DEFAULT_SWATCH;
}

export interface EntitySummary {
  type: string;
  count: number;
  samples: string[];
}

export function summarizeEntities(entities: Entity[]): EntitySummary[] {
  const map = new Map<string, { count: number; samples: Set<string> }>();
  for (const e of entities) {
    if (!map.has(e.type)) map.set(e.type, { count: 0, samples: new Set() });
    const row = map.get(e.type)!;
    row.count += 1;
    row.samples.add(e.text);
  }
  return Array.from(map.entries())
    .map(([type, row]) => ({
      type,
      count: row.count,
      samples: Array.from(row.samples).slice(0, 5),
    }))
    .sort((a, b) => b.count - a.count);
}

export function fmtTime(iso: string): string {
  const d = new Date(iso);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  const ms = String(d.getMilliseconds()).padStart(3, '0');
  return `${hh}:${mm}:${ss}.${ms}`;
}

export interface SurrogateMapping {
  entity: Entity;
  surrogate: string;
  key: string;
}

/** Derive the original→surrogate mapping by walking source and obfuscated
 * documents in parallel. The backend produces `obfuscated_document` by replacing
 * each entity span with either a `[TYPE_xxxx]` token (tokenize) or a realistic
 * substitute (pseudonymize); we recover the surrogate by tracking the running
 * offset between the two strings. */
export function deriveSurrogates(
  entities: Entity[],
  documentText: string,
  obfuscatedDocument: string,
): SurrogateMapping[] {
  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const out: SurrogateMapping[] = [];
  let offset = 0;
  const tokenRe = /^\[[A-Z_]+_[a-zA-Z0-9]+\]/;
  for (let i = 0; i < sorted.length; i += 1) {
    const e = sorted[i];
    const start = e.start + offset;
    const remaining = obfuscatedDocument.slice(start);
    const tokMatch = tokenRe.exec(remaining);
    let surrogate: string;
    if (tokMatch) {
      surrogate = tokMatch[0];
    } else {
      const next = sorted[i + 1];
      let endBoundary: number;
      if (next) {
        const gap = documentText.slice(e.end, next.start);
        const found = gap.length > 0 ? obfuscatedDocument.indexOf(gap, start) : -1;
        endBoundary = found >= 0 ? found : start + (e.end - e.start);
      } else {
        const trail = documentText.slice(e.end);
        endBoundary = obfuscatedDocument.endsWith(trail)
          ? obfuscatedDocument.length - trail.length
          : obfuscatedDocument.length;
      }
      surrogate = obfuscatedDocument.slice(start, endBoundary);
    }
    out.push({ entity: e, surrogate, key: `${e.type}::${e.text}` });
    offset += surrogate.length - (e.end - e.start);
  }
  return out;
}

/** Unique original→surrogate pairs, first occurrence wins. Same entity text
 * always maps to the same surrogate within a session. */
export function uniqueSurrogates(mappings: SurrogateMapping[]): SurrogateMapping[] {
  const seen = new Set<string>();
  const out: SurrogateMapping[] = [];
  for (const m of mappings) {
    if (seen.has(m.key)) continue;
    seen.add(m.key);
    out.push(m);
  }
  return out;
}
