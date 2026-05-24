import { type ReactNode, useCallback, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query';
import {
  type AuditEntry,
  type PipelineResult,
  type Strategy,
  endSession,
  fetchAudit,
  runPipeline,
  startSession,
  uploadDocument,
} from './api';
import { Badge, Button, CodeBlock } from './components';
import { HighlightedText } from './highlight';

const queryClient = new QueryClient();
type ResponseView = 'rendered' | 'markdown' | 'raw';
type InspectorView = 'source' | 'entities';
type TrustView = ResponseView | 'payload';

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Page />
    </QueryClientProvider>
  );
}

function useDevMode(): [boolean, (v: boolean) => void] {
  const initial = useMemo(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('dev') !== 'false';
  }, []);
  const [dev, setDev] = useState(initial);
  return [dev, setDev];
}

function Page() {
  const [userId, setUserId] = useState('demo_user');
  const [strategy, setStrategy] = useState<Strategy>('tokenize');
  const [inspectorView, setInspectorView] = useState<InspectorView>('source');
  const [trustView, setTrustView] = useState<TrustView>('rendered');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [docFilename, setDocFilename] = useState<string | null>(null);
  const [query, setQuery] = useState(
    'Summarize this document and flag anything that warrants follow-up.',
  );
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [devMode, setDevMode] = useDevMode();

  const startMut = useMutation({
    mutationFn: () => startSession(userId, strategy),
    onSuccess: (r) => {
      setSessionId(r.session_id);
      setResult(null);
      setDocId(null);
      setDocFilename(null);
    },
  });

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      if (!sessionId) throw new Error('No active session');
      return uploadDocument(sessionId, file);
    },
    onSuccess: (r) => {
      setDocId(r.doc_id);
      setDocFilename(r.filename);
    },
  });

  const runMut = useMutation({
    mutationFn: async () => {
      if (!sessionId || !docId) throw new Error('Need session + document');
      return runPipeline(sessionId, docId, query);
    },
    onSuccess: (r) => setResult(r),
  });

  const endMut = useMutation({
    mutationFn: () => {
      if (!sessionId) return Promise.resolve();
      return endSession(sessionId);
    },
    onSuccess: () => {
      setSessionId(null);
      setDocId(null);
      setDocFilename(null);
      setResult(null);
    },
  });

  const audit = useQuery({
    queryKey: ['audit', sessionId],
    queryFn: () => (sessionId ? fetchAudit(sessionId) : Promise.resolve([])),
    enabled: !!sessionId,
    refetchInterval: 3000,
  });

  const onFile = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) uploadMut.mutate(file);
    },
    [uploadMut],
  );

  const auditEvents = audit.data ?? [];
  const activeError = runMut.error ?? uploadMut.error ?? startMut.error;
  const canRun = !!sessionId && !!docId && !runMut.isPending;

  return (
    <div className="flex h-screen flex-col bg-bg text-ink">
      <Header
        sessionId={sessionId}
        docFilename={docFilename}
        result={result}
        auditCount={auditEvents.length}
      />

      <main className="grid min-h-0 flex-1 grid-cols-1 gap-4 p-4 xl:grid-cols-[320px_minmax(0,1fr)_minmax(420px,0.9fr)]">
        <RunSetup
        userId={userId}
        setUserId={setUserId}
        strategy={strategy}
        setStrategy={setStrategy}
        sessionId={sessionId}
        onStart={() => startMut.mutate()}
        onEnd={() => endMut.mutate()}
        devMode={devMode}
        setDevMode={setDevMode}
          docFilename={docFilename}
          docId={docId}
          onFile={onFile}
          uploading={uploadMut.isPending}
          query={query}
          setQuery={setQuery}
          onRun={() => runMut.mutate()}
          running={runMut.isPending}
          canRun={canRun}
          error={activeError}
      />

        <SourceInspector
          result={result}
          inspectorView={inspectorView}
          setInspectorView={setInspectorView}
          sessionId={sessionId}
        />

        <TrustConsole
        devMode={devMode}
        result={result}
          trustView={trustView}
          setTrustView={setTrustView}
          audit={auditEvents}
      />
      </main>
    </div>
  );
}

function Header({
  sessionId,
  docFilename,
  result,
  auditCount,
}: {
  sessionId: string | null;
  docFilename: string | null;
  result: PipelineResult | null;
  auditCount: number;
}) {
  const entityCount = result?.detected_entities.length ?? 0;
  const typeCount = result
    ? new Set(result.detected_entities.map((entity) => entity.type)).size
    : 0;
  return (
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-white px-5">
      <div>
        <h1 className="font-serif text-xl leading-none">Secure Context Pipeline</h1>
        <p className="mt-1 text-xs text-muted">
          Local vault restoration with an inspectable LLM trust boundary
        </p>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <StatusPill label="Session" value={sessionId ? sessionId.slice(0, 8) : 'none'} active={!!sessionId} />
        <StatusPill label="Document" value={docFilename ?? 'none'} active={!!docFilename} />
        <StatusPill label="Entities" value={`${entityCount}/${typeCount}`} active={entityCount > 0} />
        <StatusPill label="Audit" value={String(auditCount)} active={auditCount > 0} />
      </div>
    </header>
  );
}

function StatusPill({
  label,
  value,
  active,
}: {
  label: string;
  value: string;
  active: boolean;
}) {
  return (
    <div className="rounded border border-border bg-bg px-3 py-1.5">
      <span className="mr-1 text-muted">{label}</span>
      <span className={active ? 'font-mono text-good' : 'font-mono text-muted'}>{value}</span>
    </div>
  );
}

function Panel({
  title,
  subtitle,
  actions,
  children,
  className,
}: {
  title: string;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded border border-border bg-white shadow-sm ${className ?? ''}`}>
      <div className="flex min-h-14 items-center justify-between gap-3 border-b border-border bg-surface px-4 py-3">
        <div>
          <h2 className="font-serif text-base leading-tight">{title}</h2>
          {subtitle && <p className="mt-0.5 text-xs text-muted">{subtitle}</p>}
        </div>
        {actions}
      </div>
      <div className="min-h-0 flex-1 overflow-auto p-4">{children}</div>
    </section>
  );
}

function RunSetup(props: {
  userId: string;
  setUserId: (v: string) => void;
  strategy: Strategy;
  setStrategy: (v: Strategy) => void;
  sessionId: string | null;
  onStart: () => void;
  onEnd: () => void;
  devMode: boolean;
  setDevMode: (v: boolean) => void;
  docFilename: string | null;
  docId: string | null;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  uploading: boolean;
  query: string;
  setQuery: (v: string) => void;
  onRun: () => void;
  running: boolean;
  canRun: boolean;
  error: unknown;
}) {
  return (
    <Panel
      title="Run Setup"
      subtitle="Create a vault-backed session, upload a fixture, then run the prompt."
    >
      <div className="space-y-5 text-sm">
        <label className="block">
          <span className="text-xs uppercase tracking-wider text-muted">User</span>
          <input
            type="text"
            value={props.userId}
            onChange={(e) => props.setUserId(e.target.value)}
            disabled={!!props.sessionId}
            className="mt-1 w-full rounded border border-border bg-bg px-3 py-2 text-sm disabled:bg-surface"
          />
        </label>

        <div className="rounded border border-border bg-bg p-3 text-xs text-muted">
          A session owns the temporary vault key. Ending it destroys local restoration
          state for this run.
        </div>

        <fieldset disabled={!!props.sessionId}>
          <span className="block text-xs uppercase tracking-wider text-muted">Strategy</span>
          <div className="mt-2 grid grid-cols-2 gap-2">
            {(['tokenize', 'pseudonymize'] as const).map((s) => (
              <label
                key={s}
                className={`cursor-pointer rounded border px-3 py-2 text-center text-xs transition ${
                  props.strategy === s
                    ? 'border-accent bg-accent-soft text-accent'
                    : 'border-border bg-white text-muted'
                } ${props.sessionId ? 'cursor-not-allowed opacity-60' : ''}`}
              >
                <input
                  className="sr-only"
                  type="radio"
                  name="strategy"
                  checked={props.strategy === s}
                  onChange={() => props.setStrategy(s)}
                  disabled={!!props.sessionId}
                />
                {s}
              </label>
            ))}
          </div>
        </fieldset>

        {!props.sessionId ? (
          <Button onClick={props.onStart} className="w-full">
            Start session
          </Button>
        ) : (
          <div className="space-y-2">
            <div className="rounded border border-good-soft bg-good-soft px-2 py-1 text-[11px] text-good">
              Session: <span className="font-mono">{props.sessionId.slice(0, 8)}…</span>
            </div>
            <Button variant="secondary" onClick={props.onEnd} className="w-full">
              End session
            </Button>
          </div>
        )}

        <label className="block">
          <span className="text-xs uppercase tracking-wider text-muted">Document</span>
          <input
            type="file"
            accept=".txt,.docx,.pdf,.png,.jpg,.jpeg"
            onChange={props.onFile}
            disabled={!props.sessionId || props.uploading}
            className="mt-2 block w-full text-xs file:mr-3 file:rounded file:border-0 file:bg-accent file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-white disabled:opacity-50"
          />
          {props.docFilename && (
            <p className="mt-2 truncate text-xs text-muted">
              {props.docFilename} <span className="font-mono">({props.docId})</span>
            </p>
          )}
        </label>

        <label className="block">
          <span className="text-xs uppercase tracking-wider text-muted">Prompt</span>
          <textarea
            value={props.query}
            onChange={(e) => props.setQuery(e.target.value)}
            rows={5}
            className="mt-2 w-full resize-none rounded border border-border bg-bg px-3 py-2 text-sm"
          />
        </label>

        <Button onClick={props.onRun} disabled={!props.canRun} className="w-full">
          {props.running ? 'Running pipeline...' : 'Run pipeline'}
        </Button>

        <label className="flex items-center justify-between rounded border border-border bg-bg px-3 py-2 text-xs">
          <span className="text-muted">Dev evidence panels</span>
          <input
            type="checkbox"
            checked={props.devMode}
            onChange={(e) => props.setDevMode(e.target.checked)}
          />
        </label>

        {!!props.error && (
          <div className="rounded border border-accent bg-accent-soft px-3 py-2 text-xs text-accent">
            {String((props.error as Error).message ?? props.error)}
          </div>
        )}
      </div>
    </Panel>
  );
}

function SourceInspector({
  result,
  inspectorView,
  setInspectorView,
  sessionId,
}: {
  result: PipelineResult | null;
  inspectorView: InspectorView;
  setInspectorView: (v: InspectorView) => void;
  sessionId: string | null;
}) {
  return (
    <Panel
      title="Local Inspection"
      subtitle="Plaintext never leaves this side of the boundary."
      actions={
        <SegmentedControl
          value={inspectorView}
          onChange={(value) => setInspectorView(value as InspectorView)}
          options={[
            ['source', 'Source'],
            ['entities', 'Entities'],
          ]}
        />
      }
    >
      {!sessionId ? (
        <EmptyState title="No active vault" body="Start a session to create a temporary key for restoration." />
      ) : !result ? (
        <EmptyState title="Waiting for a run" body="Upload a document and run the pipeline to inspect detected values." />
      ) : inspectorView === 'source' ? (
        <div className="font-mono text-[13px] leading-6">
          <HighlightedText text={result.document_text} entities={result.detected_entities} />
        </div>
      ) : (
        <EntityTable result={result} />
      )}
    </Panel>
  );
}

function TrustConsole({
  devMode,
  result,
  trustView,
  setTrustView,
  audit,
}: {
  devMode: boolean;
  result: PipelineResult | null;
  trustView: TrustView;
  setTrustView: (v: TrustView) => void;
  audit: AuditEntry[];
}) {
  const options: Array<[TrustView, string]> = devMode
    ? [
        ['rendered', 'Rendered'],
        ['markdown', 'Markdown'],
        ['raw', 'Raw'],
        ['payload', 'Outbound'],
      ]
    : [
        ['rendered', 'Rendered'],
        ['markdown', 'Markdown'],
      ];
  const visibleTrustView =
    devMode || (trustView !== 'raw' && trustView !== 'payload')
      ? trustView
      : 'rendered';

  return (
    <div className="flex min-h-0 flex-col gap-4">
      <Panel
        title="Trust Boundary"
        subtitle="The outbound tab is the provider-visible payload."
        actions={
          <SegmentedControl
            value={visibleTrustView}
            onChange={(value) => setTrustView(value as TrustView)}
            options={options}
          />
        }
        className="flex-[1.25]"
      >
        {!result ? (
          <EmptyState title="No response yet" body="Run the pipeline to inspect the sanitized payload and restored answer." />
        ) : (
          <TrustContent result={result} trustView={visibleTrustView} />
        )}
      </Panel>
      <AuditConsole audit={audit} />
    </div>
  );
}

function EntityTable({ result }: { result: PipelineResult }) {
  const byType = new Map<string, number>();
  result.detected_entities.forEach((entity) => {
    byType.set(entity.type, (byType.get(entity.type) ?? 0) + 1);
  });
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 text-xs">
        <Metric label="Entities" value={String(result.detected_entities.length)} />
        <Metric label="Types" value={String(byType.size)} />
      </div>
      <div className="overflow-hidden rounded border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-surface text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-3 py-2">Value</th>
              <th className="px-3 py-2">Type</th>
              <th className="px-3 py-2 text-right">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {result.detected_entities.map((entity, index) => (
              <tr key={`${entity.start}-${index}`} className="border-t border-border/60">
                <td className="max-w-[280px] truncate px-3 py-2 font-mono text-xs">{entity.text}</td>
                <td className="px-3 py-2"><Badge>{entity.type}</Badge></td>
                <td className="px-3 py-2 text-right font-mono text-xs text-muted">
                  {(entity.confidence * 100).toFixed(0)}%
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TrustContent({
  result,
  trustView,
}: {
  result: PipelineResult;
  trustView: TrustView;
}) {
  const redactions = findRedactions(result.restored_response);

  if (trustView === 'payload') {
    return (
      <div className="space-y-3">
        <BoundarySummary result={result} />
        <CodeBlock className="max-h-[58vh]">{result.obfuscated_prompt}</CodeBlock>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant={result.strategy_name === 'tokenize' ? 'good' : 'accent'}>{result.strategy_name}</Badge>
        {redactions.length > 0 && <Badge variant="warn">{redactions.length} redacted</Badge>}
      </div>
      {redactions.length > 0 && (
        <div className="rounded border border-warn-soft bg-warn-soft px-3 py-2 text-xs text-warn">
          {redactions.length} unbacked redaction marker{redactions.length === 1 ? '' : 's'} remain.
        </div>
      )}
      {trustView === 'raw' ? (
        <CodeBlock className="max-h-[58vh]">{result.llm_response_raw}</CodeBlock>
      ) : trustView === 'markdown' ? (
        <CodeBlock className="max-h-[58vh]">{result.restored_response}</CodeBlock>
      ) : (
        <MarkdownRenderer text={result.restored_response} />
      )}
    </div>
  );
}

function BoundarySummary({ result }: { result: PipelineResult }) {
  return (
    <div className="grid grid-cols-3 gap-2 text-xs">
      <Metric label="Strategy" value={result.strategy_name} />
      <Metric label="Prompt chars" value={String(result.obfuscated_prompt.length)} />
      <Metric label="Entities" value={String(result.detected_entities.length)} />
    </div>
  );
}

function AuditConsole({ audit }: { audit: AuditEntry[] }) {
  return (
    <Panel title="Audit Console" subtitle="Append-only events; token IDs only." className="min-h-44 flex-[0.75]">
      <div className="space-y-1 font-mono text-[11px]">
        {audit.length === 0 && <p className="text-muted">No events yet.</p>}
        {audit.slice(-18).reverse().map((event, index) => (
          <div key={index} className="grid grid-cols-[72px_1fr] gap-2 border-b border-border/50 py-1">
            <span className="text-muted">{new Date(event.timestamp).toLocaleTimeString()}</span>
            <div className="min-w-0">
              <span className="text-accent">{event.action}</span>
              {event.entity_type && <span className="ml-2 text-muted">{event.entity_type}</span>}
              {event.token_id && <div className="truncate text-ink">{event.token_id}</div>}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-border bg-bg px-3 py-2">
      <div className="text-[10px] uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-1 truncate font-mono text-sm">{value}</div>
    </div>
  );
}

function SegmentedControl({
  value,
  onChange,
  options,
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<[string, string]>;
}) {
  return (
    <div className="flex rounded border border-border bg-white p-0.5 text-xs">
      {options.map(([optionValue, label]) => (
        <button
          key={optionValue}
          type="button"
          onClick={() => onChange(optionValue)}
          className={`rounded px-2 py-1 transition ${
            value === optionValue ? 'bg-accent text-white' : 'text-muted hover:bg-surface hover:text-ink'
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return (
    <div className="flex h-full min-h-64 items-center justify-center rounded border border-dashed border-border bg-bg p-6 text-center">
      <div>
        <h3 className="font-serif text-lg">{title}</h3>
        <p className="mt-2 max-w-sm text-sm text-muted">{body}</p>
      </div>
    </div>
  );
}

function findRedactions(text: string): string[] {
  return text.match(/\[REDACTED_[A-Z_]+\]/g) ?? [];
}

function MarkdownRenderer({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  const lines = text.split('\n');
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) {
      i += 1;
      continue;
    }

    if (line.startsWith('```')) {
      const code: string[] = [];
      i += 1;
      while (i < lines.length && !lines[i].startsWith('```')) {
        code.push(lines[i]);
        i += 1;
      }
      i += 1;
      blocks.push(<CodeBlock key={blocks.length}>{code.join('\n')}</CodeBlock>);
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1].length;
      const className =
        level === 1
          ? 'font-serif text-xl'
          : level === 2
            ? 'font-serif text-lg'
            : 'font-serif text-base';
      blocks.push(
        <h4 key={blocks.length} className={className}>
          {renderInline(heading[2])}
        </h4>,
      );
      i += 1;
      continue;
    }

    if (/^\s*[-*]\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*[-*]\s+/.test(lines[i])) {
        items.push(
          <li key={i}>{renderInline(lines[i].replace(/^\s*[-*]\s+/, ''))}</li>,
        );
        i += 1;
      }
      blocks.push(
        <ul key={blocks.length} className="list-disc space-y-1 pl-5">
          {items}
        </ul>,
      );
      continue;
    }

    if (/^\s*\d+\.\s+/.test(line)) {
      const items: ReactNode[] = [];
      while (i < lines.length && /^\s*\d+\.\s+/.test(lines[i])) {
        items.push(
          <li key={i}>{renderInline(lines[i].replace(/^\s*\d+\.\s+/, ''))}</li>,
        );
        i += 1;
      }
      blocks.push(
        <ol key={blocks.length} className="list-decimal space-y-1 pl-5">
          {items}
        </ol>,
      );
      continue;
    }

    if (isMarkdownTableStart(lines, i) || isPipeTableRun(lines, i)) {
      const table = parseMarkdownTable(lines, i);
      blocks.push(<MarkdownTable key={blocks.length} table={table} />);
      i = table.nextIndex;
      continue;
    }

    const paragraph = [line];
    i += 1;
    while (i < lines.length && lines[i].trim() && !/^(#{1,3})\s+/.test(lines[i])) {
      if (/^\s*([-*]|\d+\.)\s+/.test(lines[i]) || lines[i].startsWith('```')) break;
      paragraph.push(lines[i]);
      i += 1;
    }
    blocks.push(
      <p key={blocks.length} className="whitespace-pre-wrap">
        {renderInline(paragraph.join('\n'))}
      </p>,
    );
  }

  return <div className="space-y-3 text-sm leading-6">{blocks}</div>;
}

interface ParsedTable {
  headers: string[];
  rows: string[][];
  aligns: Array<'left' | 'center' | 'right'>;
  nextIndex: number;
  hasHeader: boolean;
}

function isMarkdownTableStart(lines: string[], index: number): boolean {
  return (
    index + 1 < lines.length &&
    splitTableRow(lines[index]).length > 1 &&
    isTableSeparator(lines[index + 1])
  );
}

function isPipeTableRun(lines: string[], index: number): boolean {
  return (
    splitTableRow(lines[index]).length > 1 &&
    index + 1 < lines.length &&
    splitTableRow(lines[index + 1]).length > 1
  );
}

function parseMarkdownTable(lines: string[], start: number): ParsedTable {
  const hasHeader = isMarkdownTableStart(lines, start);
  const firstRow = splitTableRow(lines[start]);
  const separator = hasHeader ? splitTableRow(lines[start + 1]) : [];
  const headers = hasHeader
    ? firstRow
    : firstRow.map((_, index) => `Column ${index + 1}`);
  const aligns = hasHeader
    ? separator.map((cell) => {
        const trimmed = cell.trim();
        if (trimmed.startsWith(':') && trimmed.endsWith(':')) return 'center';
        if (trimmed.endsWith(':')) return 'right';
        return 'left';
      })
    : firstRow.map(() => 'left' as const);
  const rows: string[][] = [];
  let i = hasHeader ? start + 2 : start;
  while (i < lines.length && splitTableRow(lines[i]).length > 1) {
    const cells = splitTableRow(lines[i]);
    if (rows.length > 0 && cells.length < headers.length) {
      rows[rows.length - 1] = mergeTableContinuation(
        rows[rows.length - 1],
        cells,
      );
    } else {
      rows.push(normalizeTableRow(cells, headers.length));
    }
    i += 1;
  }
  return {
    headers,
    rows,
    aligns: normalizeTableRow(aligns, headers.length) as ParsedTable['aligns'],
    nextIndex: i,
    hasHeader,
  };
}

function splitTableRow(line: string): string[] {
  const trimmed = line.trim();
  if (!trimmed.includes('|')) return [];
  const withoutOuter = trimmed.replace(/^\|/, '').replace(/\|$/, '');
  return withoutOuter.split('|').map((cell) => cell.trim());
}

function isTableSeparator(line: string): boolean {
  const cells = splitTableRow(line);
  return (
    cells.length > 1 &&
    cells.every((cell) => /^:?-{3,}:?$/.test(cell.trim()))
  );
}

function normalizeTableRow<T>(cells: T[], length: number): T[] {
  if (cells.length >= length) return cells.slice(0, length);
  return [...cells, ...Array<T>(length - cells.length).fill('' as T)];
}

function mergeTableContinuation(row: string[], continuation: string[]): string[] {
  const merged = [...row];
  const start = Math.max(0, row.length - continuation.length);
  continuation.forEach((cell, index) => {
    const target = start + index;
    merged[target] = [merged[target], cell].filter(Boolean).join(' ');
  });
  return merged;
}

function MarkdownTable({ table }: { table: ParsedTable }) {
  const alignmentClass = (align: 'left' | 'center' | 'right') =>
    align === 'center' ? 'text-center' : align === 'right' ? 'text-right' : 'text-left';

  return (
    <div className="overflow-x-auto rounded border border-border">
      <table className="min-w-full border-collapse text-sm">
        {table.hasHeader && (
          <thead className="bg-surface">
            <tr>
              {table.headers.map((header, index) => (
                <th
                  key={index}
                  className={`border-b border-border px-3 py-2 font-semibold ${alignmentClass(table.aligns[index])}`}
                >
                  {renderInline(header)}
                </th>
              ))}
            </tr>
          </thead>
        )}
        <tbody>
          {table.rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-t border-border/60">
              {row.map((cell, cellIndex) => (
                <td
                  key={cellIndex}
                  className={`px-3 py-2 align-top ${alignmentClass(table.aligns[cellIndex])}`}
                >
                  {renderInline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderInline(text: string): ReactNode[] {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[REDACTED_[A-Z_]+\])/g).map((part, index) => {
    if (!part) return null;
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code key={index} className="rounded bg-surface px-1 py-0.5 font-mono text-[12px]">
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    if (/^\[REDACTED_[A-Z_]+\]$/.test(part)) {
      return (
        <span key={index} className="rounded bg-warn-soft px-1 py-0.5 font-mono text-[12px] text-warn">
          {part}
        </span>
      );
    }
    return part;
  });
}
