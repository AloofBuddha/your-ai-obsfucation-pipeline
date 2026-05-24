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
import { Badge, Button, Card, CodeBlock, Switch } from './components';
import { HighlightedText } from './highlight';

const queryClient = new QueryClient();
type ResponseView = 'rendered' | 'markdown' | 'raw';

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
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [docFilename, setDocFilename] = useState<string | null>(null);
  const [query, setQuery] = useState(
    'Summarize this document and flag anything that warrants follow-up.',
  );
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [responseView, setResponseView] = useState<ResponseView>('rendered');
  const [devMode, setDevMode] = useDevMode();

  const startMut = useMutation({
    mutationFn: () => startSession(userId, strategy),
    onSuccess: (r) => setSessionId(r.session_id),
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

  return (
    <div className="flex h-screen bg-bg">
      <Sidebar
        userId={userId}
        setUserId={setUserId}
        strategy={strategy}
        setStrategy={setStrategy}
        sessionId={sessionId}
        onStart={() => startMut.mutate()}
        onEnd={() => endMut.mutate()}
        audit={audit.data ?? []}
        devMode={devMode}
        setDevMode={setDevMode}
      />
      <Main
        devMode={devMode}
        sessionId={sessionId}
        docFilename={docFilename}
        docId={docId}
        onFile={onFile}
        uploading={uploadMut.isPending}
        query={query}
        setQuery={setQuery}
        onRun={() => runMut.mutate()}
        running={runMut.isPending}
        result={result}
        responseView={responseView}
        setResponseView={setResponseView}
        error={runMut.error ?? uploadMut.error ?? startMut.error}
      />
    </div>
  );
}

function Sidebar(props: {
  userId: string;
  setUserId: (v: string) => void;
  strategy: Strategy;
  setStrategy: (v: Strategy) => void;
  sessionId: string | null;
  onStart: () => void;
  onEnd: () => void;
  audit: AuditEntry[];
  devMode: boolean;
  setDevMode: (v: boolean) => void;
}) {
  return (
    <aside className="flex w-72 shrink-0 flex-col border-r border-border bg-white">
      <div className="border-b border-border p-4">
        <h1 className="font-serif text-xl">Secure Context Pipeline</h1>
        <p className="mt-1 text-xs text-muted">PII obfuscation for external LLMs</p>
      </div>

      <div className="space-y-3 border-b border-border p-4 text-sm">
        <label className="block">
          <span className="text-xs uppercase tracking-wider text-muted">User</span>
          <input
            type="text"
            value={props.userId}
            onChange={(e) => props.setUserId(e.target.value)}
            disabled={!!props.sessionId}
            className="mt-1 w-full rounded border border-border bg-bg px-2 py-1 text-sm disabled:bg-surface"
          />
        </label>
        <p className="text-xs text-muted">
          A session owns the temporary vault key used to restore this run. The UI
          works with one active session at a time; the API can hold multiple.
        </p>
        <div>
          <span className="block text-xs uppercase tracking-wider text-muted">Strategy</span>
          <div className="mt-1 flex gap-3 text-sm">
            {(['tokenize', 'pseudonymize'] as const).map((s) => (
              <label key={s} className="flex items-center gap-1">
                <input
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
        </div>
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
        <Switch
          checked={props.devMode}
          onChange={props.setDevMode}
          label={
            <span className="text-xs">
              Dev mode <span className="text-muted">(?dev=false to hide)</span>
            </span>
          }
        />
      </div>

      <div className="flex-1 overflow-auto">
        <div className="border-b border-border bg-surface px-4 py-2">
          <h2 className="font-serif text-sm">Audit log</h2>
          <p className="text-[11px] text-muted">live · token IDs only, no values</p>
        </div>
        <div className="space-y-1 p-3 font-mono text-[11px]">
          {props.audit.length === 0 && <p className="text-muted">No events yet.</p>}
          {props.audit.slice(-30).reverse().map((e, i) => (
            <div key={i} className="border-b border-border/50 py-1">
              <span className="text-muted">{new Date(e.timestamp).toLocaleTimeString()}</span>
              <span className="ml-1 text-accent">{e.action}</span>
              {e.entity_type && <span className="ml-1 text-muted">{e.entity_type}</span>}
              {e.token_id && <div className="break-all pl-3 text-ink">{e.token_id}</div>}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}

function Main(props: {
  devMode: boolean;
  sessionId: string | null;
  docFilename: string | null;
  docId: string | null;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  uploading: boolean;
  query: string;
  setQuery: (v: string) => void;
  onRun: () => void;
  running: boolean;
  result: PipelineResult | null;
  responseView: ResponseView;
  setResponseView: (v: ResponseView) => void;
  error: unknown;
}) {
  if (!props.sessionId) {
    return (
      <main className="flex-1 p-12">
        <p className="text-muted">Start a session in the sidebar to begin.</p>
      </main>
    );
  }

  return (
    <main className="flex-1 overflow-auto p-6">
      <div className="mb-4 flex flex-wrap items-end gap-4">
        <label className="flex-1">
          <span className="block text-xs uppercase tracking-wider text-muted">Document</span>
          <input
            type="file"
            accept=".txt,.docx,.pdf,.png,.jpg,.jpeg"
            onChange={props.onFile}
            className="mt-1 block w-full text-sm"
          />
          {props.docFilename && (
            <p className="mt-1 text-xs text-muted">
              uploaded: <span className="text-ink">{props.docFilename}</span> ({props.docId})
            </p>
          )}
        </label>
        <label className="flex-1">
          <span className="block text-xs uppercase tracking-wider text-muted">Query</span>
          <input
            type="text"
            value={props.query}
            onChange={(e) => props.setQuery(e.target.value)}
            className="mt-1 w-full rounded border border-border bg-white px-2 py-1.5 text-sm"
          />
        </label>
        <Button onClick={props.onRun} disabled={!props.docId || props.running}>
          {props.running ? 'Running…' : 'Run pipeline →'}
        </Button>
      </div>

      {!!props.error && (
        <div className="mb-4 rounded border border-accent bg-accent-soft px-4 py-2 text-sm text-accent">
          {String((props.error as Error).message ?? props.error)}
        </div>
      )}

      {!props.result ? (
        <p className="text-muted">Upload a document and run the pipeline to see results.</p>
      ) : props.devMode ? (
        <DevPanels
          result={props.result}
          responseView={props.responseView}
          setResponseView={props.setResponseView}
        />
      ) : (
        <UserPanel
          result={props.result}
          responseView={props.responseView}
          setResponseView={props.setResponseView}
        />
      )}
    </main>
  );
}

function UserPanel({
  result,
  responseView,
  setResponseView,
}: {
  result: PipelineResult;
  responseView: ResponseView;
  setResponseView: (v: ResponseView) => void;
}) {
  return (
    <Card title="Response">
      <ResponseToolbar
        responseView={responseView}
        setResponseView={setResponseView}
        result={result}
      />
      <ResponseContent result={result} responseView={responseView} />
    </Card>
  );
}

function DevPanels({
  result,
  responseView,
  setResponseView,
}: {
  result: PipelineResult;
  responseView: ResponseView;
  setResponseView: (v: ResponseView) => void;
}) {
  const redactions = findRedactions(result.restored_response);
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card title="Source document" step={1}>
        <p className="mb-2 text-xs text-muted">
          Detected entities are color-coded. Hover for type + confidence.
        </p>
        <div className="font-mono text-[13px]">
          <HighlightedText
            text={result.document_text}
            entities={result.detected_entities}
          />
        </div>
      </Card>

      <Card title="Detected entities" step={2}>
        <p className="mb-2 text-xs text-muted">
          {result.detected_entities.length} entities,{' '}
          {Array.from(new Set(result.detected_entities.map((e) => e.type))).length} unique types.
          <span className="ml-1">Percentages are detector confidence scores.</span>
        </p>
        <ul className="space-y-1 text-sm">
          {result.detected_entities.map((e, i) => (
            <li key={i} className="flex items-center justify-between gap-2 border-b border-border/50 py-1">
              <span className="truncate font-mono text-[12px]">{e.text}</span>
              <span className="flex shrink-0 items-center gap-2">
                <Badge>{e.type}</Badge>
                <span className="font-mono text-[11px] text-muted">
                  {(e.confidence * 100).toFixed(0)}%
                </span>
              </span>
            </li>
          ))}
        </ul>
      </Card>

      <Card title="Obfuscated payload sent to LLM" step={3}>
        <p className="mb-2 text-xs text-muted">
          Strategy: <Badge variant="accent">{result.strategy_name}</Badge>
          <span className="ml-2">Verify: no original PII present.</span>
        </p>
        <CodeBlock className="max-h-72">{result.obfuscated_prompt}</CodeBlock>
      </Card>

      <Card title="Response (restored)" step={4}>
        <ResponseToolbar
          responseView={responseView}
          setResponseView={setResponseView}
          result={result}
        />
        {redactions.length > 0 && (
          <div className="mb-3 rounded border border-warn-soft bg-warn-soft px-3 py-2 text-xs text-warn">
            {redactions.length} redacted placeholder{redactions.length === 1 ? '' : 's'} remain.
            These markers were not backed by a vault token, so there is no local
            mapping to restore.
          </div>
        )}
        <ResponseContent result={result} responseView={responseView} />
      </Card>
    </div>
  );
}

function ResponseToolbar({
  responseView,
  setResponseView,
  result,
}: {
  responseView: ResponseView;
  setResponseView: (v: ResponseView) => void;
  result: PipelineResult;
}) {
  const redactions = findRedactions(result.restored_response);
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div className="flex items-center gap-2">
        <label className="text-xs uppercase tracking-wider text-muted" htmlFor="response-view">
          View
        </label>
        <select
          id="response-view"
          value={responseView}
          onChange={(e) => setResponseView(e.target.value as ResponseView)}
          className="rounded border border-border bg-white px-2 py-1 text-xs"
        >
          <option value="rendered">Rendered</option>
          <option value="markdown">Markdown source</option>
          <option value="raw">Raw LLM response</option>
        </select>
      </div>
      <div className="flex items-center gap-2 text-xs text-muted">
        <Badge variant={result.strategy_name === 'tokenize' ? 'good' : 'accent'}>
          {result.strategy_name}
        </Badge>
        {redactions.length > 0 && <Badge variant="warn">{redactions.length} redacted</Badge>}
      </div>
    </div>
  );
}

function ResponseContent({
  result,
  responseView,
}: {
  result: PipelineResult;
  responseView: ResponseView;
}) {
  if (responseView === 'raw') {
    return <CodeBlock className="max-h-96">{result.llm_response_raw}</CodeBlock>;
  }
  if (responseView === 'markdown') {
    return <CodeBlock className="max-h-96">{result.restored_response}</CodeBlock>;
  }
  return <MarkdownRenderer text={result.restored_response} />;
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
