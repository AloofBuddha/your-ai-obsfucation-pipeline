import { useCallback, useState } from 'react';
import { QueryClient, QueryClientProvider, useMutation, useQuery } from '@tanstack/react-query';
import {
  type PipelineResult,
  type Strategy,
  endSession,
  fetchAudit,
  runPipeline,
  startSession,
  uploadDocument,
} from './api';
import { type RunState, XrayWorkbench } from './XrayWorkbench';

const queryClient = new QueryClient();

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <Page />
    </QueryClientProvider>
  );
}

function Page() {
  const [strategy, setStrategy] = useState<Strategy>('tokenize');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [docId, setDocId] = useState<string | null>(null);
  const [docFilename, setDocFilename] = useState<string | null>(null);
  const [query, setQuery] = useState(
    'Summarize this document and flag anything that warrants follow-up.',
  );
  const [result, setResult] = useState<PipelineResult | null>(null);

  const uploadMut = useMutation({
    mutationFn: async (file: File) => {
      let activeSession = sessionId;
      if (!activeSession) {
        const session = await startSession('demo_user', strategy);
        activeSession = session.session_id;
        setSessionId(session.session_id);
      }
      return uploadDocument(activeSession, file);
    },
    onSuccess: (r) => {
      setDocId(r.doc_id);
      setDocFilename(r.filename);
      setResult(null);
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
    mutationFn: async () => {
      if (!sessionId) return;
      await endSession(sessionId);
    },
    onSuccess: () => {
      setSessionId(null);
      setDocId(null);
      setDocFilename(null);
      setResult(null);
      runMut.reset();
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

  const runState: RunState =
    runMut.isPending ? 'running'
      : runMut.isError ? 'error'
      : result ? 'complete'
      : 'idle';

  const auditEvents = audit.data ?? [];
  const errorMessage =
    (runMut.error as Error | undefined)?.message
    ?? (uploadMut.error as Error | undefined)?.message
    ?? null;
  const canRerun = !!sessionId && !!docId && !runMut.isPending;
  const canUpload = !uploadMut.isPending;

  return (
    <div className="flex h-screen flex-col bg-xray-bg">
      <Launcher
        docFilename={docFilename}
        uploading={uploadMut.isPending}
        running={runMut.isPending}
        canRun={canRerun}
        canUpload={canUpload}
        query={query}
        onQueryChange={setQuery}
        onFile={onFile}
        onRun={() => runMut.mutate()}
        runState={runState}
        errorMessage={errorMessage}
      />
      <div className="min-h-0 flex-1">
        <XrayWorkbench
          runState={runState}
          strategy={strategy}
          result={result}
          audit={auditEvents}
          sessionId={sessionId}
          docFilename={docFilename}
          errorMessage={errorMessage}
          onStrategyChange={setStrategy}
          onRerun={() => runMut.mutate()}
          onWipeVault={() => endMut.mutate()}
          canRerun={canRerun}
        />
      </div>
    </div>
  );
}

function Launcher({
  docFilename,
  uploading,
  running,
  canRun,
  canUpload,
  query,
  onQueryChange,
  onFile,
  onRun,
  runState,
  errorMessage,
}: {
  docFilename: string | null;
  uploading: boolean;
  running: boolean;
  canRun: boolean;
  canUpload: boolean;
  query: string;
  onQueryChange: (next: string) => void;
  onFile: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onRun: () => void;
  runState: RunState;
  errorMessage: string | null;
}) {
  return (
    <div className="shrink-0 border-b border-xray-border bg-xray-header px-5 py-3"
         style={{ fontFamily: 'ui-monospace,Menlo,"SF Mono",monospace' }}>
      <div className="flex items-center gap-4 text-[14px]">
        <label className="flex items-center gap-3">
          <span className="text-[12px] uppercase tracking-[0.12em] text-xray-muted">document</span>
          <input
            type="file"
            accept=".txt,.docx,.pdf,.png,.jpg,.jpeg"
            onChange={onFile}
            disabled={!canUpload}
            className="block w-56 text-[14px] text-xray-text file:mr-2 file:rounded-[3px] file:border-0 file:bg-accent file:px-2 file:py-1 file:text-[14px] file:font-medium file:text-white disabled:opacity-50"
          />
          {docFilename && (
            <span className="truncate text-[14px] text-xray-muted" title={docFilename}>
              {docFilename}
            </span>
          )}
        </label>
        <span className="h-[18px] w-px bg-xray-border" />
        <label className="flex flex-1 items-center gap-3">
          <span className="text-[12px] uppercase tracking-[0.12em] text-xray-muted">prompt</span>
          <input
            type="text"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            className="flex-1 rounded-[3px] border border-xray-border bg-xray-inset-deep px-4 py-2.5 text-[14px] text-xray-ink focus:border-accent focus:outline-none"
          />
        </label>
        <button
          onClick={onRun}
          disabled={!canRun}
          className="rounded-[3px] bg-accent px-4 py-2 text-[14px] font-medium text-white transition hover:bg-accent/90 disabled:cursor-not-allowed disabled:bg-accent/40"
        >
          {running ? 'Running…' : uploading ? 'Uploading…' : 'Run pipeline'}
        </button>
      </div>
      {runState === 'error' && errorMessage && (
        <div className="mt-2 rounded-[3px] border border-accent bg-[#22181a] px-4 py-2.5 text-[14px] text-accent">
          {errorMessage}
        </div>
      )}
    </div>
  );
}
