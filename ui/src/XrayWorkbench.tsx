/** X-Ray Workbench — a forensics-style inspector of the secure pipeline.
 *
 * The pipeline is a compact mini-map at the top with the trust boundary as
 * the visual centerpiece. Below, each selected stage shows its own three-column
 * x-ray: source (what came in) | transform (what happened) | output (what's exposed forward).
 */
import { Children, type ReactNode, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  type AuditEntry,
  type AuditStage,
  type Entity,
  type PipelineResult,
  type Strategy,
} from './api';
import {
  type EntitySwatch,
  type SurrogateMapping,
  deriveSurrogates,
  entityColor,
  fmtTime,
  summarizeEntities,
  uniqueSurrogates,
} from './xrayPalette';

export type RunState = 'idle' | 'running' | 'complete' | 'error';
type StageId = 'document' | 'detect' | 'obfuscate' | 'llm' | 'restore';
type StageStatus = 'done' | 'running' | 'errored' | 'pending';

const STAGES: StageId[] = ['document', 'detect', 'obfuscate', 'llm', 'restore'];

const LOCAL_STAGES: StageId[] = ['document', 'detect', 'obfuscate'];
const CROSSED_STAGES: StageId[] = ['llm', 'restore'];

export interface XrayWorkbenchProps {
  runState: RunState;
  strategy: Strategy;
  result: PipelineResult | null;
  audit: AuditEntry[];
  sessionId: string | null;
  docFilename: string | null;
  errorMessage: string | null;
  initialStage?: StageId;
  onStrategyChange: (next: Strategy) => void;
  onRerun: () => void;
  onWipeVault: () => void;
  canRerun: boolean;
}

export function XrayWorkbench({
  runState,
  strategy,
  result,
  audit,
  sessionId,
  docFilename,
  errorMessage,
  initialStage = 'document',
  onStrategyChange,
  onRerun,
  onWipeVault,
  canRerun,
}: XrayWorkbenchProps) {
  const [selected, setSelected] = useState<StageId>(initialStage);
  const [hovered, setHovered] = useState<string | null>(null);
  const [minimapExpanded, setMinimapExpanded] = useState(false);
  const [bannerExpanded, setBannerExpanded] = useState(false);

  const surrogates = useMemo(() => {
    if (!result) return [];
    return deriveSurrogates(
      result.detected_entities,
      result.document_text,
      result.obfuscated_document,
    );
  }, [result]);
  const uniqueMap = useMemo(() => uniqueSurrogates(surrogates), [surrogates]);
  const tokenCount = uniqueMap.length;
  const entityCount = result?.detected_entities.length ?? 0;

  const progress = runState === 'complete' ? 5 : 0;
  const stageIndex = STAGES.indexOf(selected);
  const stageStatusFor = (i: number): StageStatus => {
    if (i < progress) return 'done';
    if (i === progress && runState === 'running') return 'running';
    if (i === progress && runState === 'error') return 'errored';
    return 'pending';
  };

  const STAGE_TO_INDEX: Record<AuditStage, number> = {
    vault: 0,
    detect: 1,
    obfuscate: 2,
    llm: 3,
    restore: 4,
  };
  const visibleAudit = audit.filter((e) => {
    const idx = STAGE_TO_INDEX[e.stage] ?? 0;
    if (runState === 'idle') return false;
    if (runState === 'running' && idx >= progress) return false;
    if (runState === 'error' && idx > progress) return false;
    return true;
  });

  const stageStatus = stageStatusFor(stageIndex);

  return (
    <div className="flex h-full w-full flex-col overflow-hidden bg-xray-bg text-[15px] text-xray-ink"
         style={{ fontFamily: 'ui-monospace,Menlo,"SF Mono",monospace' }}>
      <XrayHeader
        strategy={strategy}
        onStrategyChange={onStrategyChange}
        runState={runState}
        progress={progress}
        sessionId={sessionId}
        docFilename={docFilename}
        onRerun={onRerun}
        onWipeVault={onWipeVault}
        canRerun={canRerun}
      />
      <XrayMinimap
        selected={selected}
        setSelected={setSelected}
        result={result}
        tokenCount={tokenCount}
        entityCount={entityCount}
        stageStatusFor={stageStatusFor}
        runState={runState}
        expanded={minimapExpanded}
        onToggleExpanded={() => setMinimapExpanded((v) => !v)}
      />
      <XrayInspector
        selected={selected}
        result={result}
        strategy={strategy}
        audit={visibleAudit}
        hovered={hovered}
        setHovered={setHovered}
        stageStatus={stageStatus}
        runState={runState}
        uniqueMap={uniqueMap}
        errorMessage={errorMessage}
        bannerExpanded={bannerExpanded}
        onToggleBannerExpanded={() => setBannerExpanded((v) => !v)}
      />
    </div>
  );
}

// ─── Header ────────────────────────────────────────────────────────────────

interface HeaderProps {
  strategy: Strategy;
  onStrategyChange: (next: Strategy) => void;
  runState: RunState;
  progress: number;
  sessionId: string | null;
  docFilename: string | null;
  onRerun: () => void;
  onWipeVault: () => void;
  canRerun: boolean;
}

function XrayHeader({
  strategy,
  onStrategyChange,
  runState,
  progress,
  sessionId,
  docFilename,
  onRerun,
  onWipeVault,
  canRerun,
}: HeaderProps) {
  const stateMeta: Record<RunState, { label: string; detail: string; color: string; pulse: boolean }> = {
    idle:     { label: 'idle',     detail: 'awaiting upload',                  color: '#7a766a', pulse: false },
    running:  { label: 'running',  detail: `stage ${progress + 1}/5 in flight`, color: '#c08070', pulse: true  },
    complete: { label: 'complete', detail: 'ready',                            color: '#2d6e3e', pulse: false },
    error:    { label: 'errored',  detail: `failed at stage ${progress + 1}/5`, color: '#b85450', pulse: false },
  };
  const m = stateMeta[runState];
  const sessionShort = sessionId ? `s_${sessionId.slice(0, 8)}` : 's_—';
  const strategyLocked = runState !== 'idle' && runState !== 'complete';

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-xray-border bg-xray-header px-5">
      <div className="flex items-center gap-4 text-[14px]">
        <span
          className={m.pulse ? 'animate-xray-pulse' : ''}
          style={{
            width: 7,
            height: 7,
            borderRadius: 4,
            background: m.color,
            boxShadow: `0 0 0 2px ${m.color}44`,
            display: 'inline-block',
          }}
        />
        <span className="font-serif text-[18px] text-[#f3f0e8]">X-Ray Workbench</span>
        <span className="text-xray-fade">·</span>
        <span className="font-semibold" style={{ color: m.color }}>{m.label}</span>
        <span className="text-xray-fade">{m.detail}</span>
        <span className="text-xray-border-soft">│</span>
        <span className="text-xray-muted">session</span>
        <span>{sessionShort}</span>
        {runState !== 'idle' && docFilename && (
          <>
            <span className="text-xray-fade">·</span>
            <span className="text-xray-muted">doc</span>
            <span>{docFilename}</span>
          </>
        )}
        {runState === 'idle' && <span className="italic text-xray-fade">no document yet</span>}
      </div>
      <div className="flex items-center gap-3">
        <span className="text-[12px] uppercase tracking-[0.12em] text-xray-muted">strategy</span>
        <div className="inline-flex rounded-[3px] border border-xray-border bg-xray-inset-deep p-0.5">
          {(['tokenize', 'pseudonymize'] as Strategy[]).map((s) => (
            <button
              key={s}
              onClick={() => onStrategyChange(s)}
              disabled={strategyLocked}
              className={`rounded-[2px] px-2.5 py-1 text-[14px] tracking-wide transition disabled:cursor-not-allowed ${
                strategy === s
                  ? 'bg-accent text-white'
                  : 'text-xray-muted hover:text-xray-ink'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
        <span className="mx-1 h-[24px] w-px bg-xray-border" />
        <button
          onClick={onRerun}
          disabled={!canRerun}
          className="rounded-[3px] border border-xray-border-strong px-4 py-2.5 text-[14px] text-xray-ink transition hover:bg-xray-inset-deep disabled:cursor-not-allowed disabled:opacity-40"
        >
          {runState === 'running' ? 'Running…' : 'Re-run'}
        </button>
        <button
          onClick={onWipeVault}
          disabled={!sessionId}
          className="rounded-[3px] border border-[#6a3530] px-4 py-2.5 text-[14px] text-xray-warm transition hover:bg-[#2a181a] disabled:cursor-not-allowed disabled:opacity-40"
        >
          Wipe vault
        </button>
      </div>
    </header>
  );
}

// ─── Minimap ───────────────────────────────────────────────────────────────

interface MinimapProps {
  selected: StageId;
  setSelected: (s: StageId) => void;
  result: PipelineResult | null;
  tokenCount: number;
  entityCount: number;
  stageStatusFor: (i: number) => StageStatus;
  runState: RunState;
  expanded: boolean;
  onToggleExpanded: () => void;
}

function XrayMinimap({
  selected,
  setSelected,
  result,
  tokenCount,
  entityCount,
  stageStatusFor,
  expanded,
  onToggleExpanded,
}: MinimapProps) {
  const stageMetrics: Record<StageId, string> = {
    document:  result ? `${result.document_text.length} B` : '—',
    detect:    `${entityCount} ent`,
    obfuscate: `${tokenCount} tok`,
    llm:       '—',
    restore:   tokenCount > 0 ? `${tokenCount} resolved` : '—',
  };
  const metricFor = (id: StageId, idx: number) => {
    const status = stageStatusFor(idx);
    if (status === 'pending') return '—';
    if (status === 'running') return 'in flight…';
    if (status === 'errored') return 'errored';
    return stageMetrics[id];
  };

  if (!expanded) {
    return (
      <div className="shrink-0 border-b border-xray-border bg-xray-minimap px-5 py-2">
        <div className="flex h-9 items-center gap-3">
          <div className="flex min-w-0 flex-1 items-center gap-2">
            {STAGES.map((id, i) => (
              <button
                key={id}
                onClick={() => setSelected(id)}
                className={`flex min-w-0 items-center gap-2 rounded-[3px] border px-3 py-1.5 text-[13px] transition ${
                  selected === id ? 'bg-xray-inset-deep text-white' : 'text-xray-muted hover:text-xray-ink'
                }`}
                style={{ borderColor: selected === id ? '#b85450' : '#3a352b' }}
              >
                <span
                  className={stageStatusFor(i) === 'running' ? 'animate-xray-pulse' : ''}
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: 3,
                    background: statusDotColor(stageStatusFor(i)),
                    display: 'inline-block',
                    flexShrink: 0,
                  }}
                />
                <span className="truncate">{id}</span>
                <span className="text-xray-fade">{metricFor(id, i)}</span>
              </button>
            ))}
          </div>
          <div className="h-7 w-px bg-accent/70" />
          <div className="shrink-0 text-[12px] uppercase tracking-[0.12em] text-xray-warm">
            provider boundary
          </div>
          <button
            onClick={onToggleExpanded}
            className="rounded-[3px] border border-xray-border-strong px-3 py-1.5 text-[13px] text-xray-muted transition hover:bg-xray-inset-deep hover:text-xray-ink"
          >
            Expand pipeline
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="shrink-0 border-b border-xray-border bg-xray-minimap">
      <div className="flex items-center justify-between px-5 pt-2">
        <div className="text-[12px] uppercase tracking-[0.14em] text-xray-muted">pipeline</div>
        <button
          onClick={onToggleExpanded}
          className="rounded-[3px] border border-xray-border-strong px-3 py-1 text-[13px] text-xray-muted transition hover:bg-xray-inset-deep hover:text-xray-ink"
        >
          Collapse pipeline
        </button>
      </div>
      <div className="grid items-baseline px-5 pt-2"
           style={{ gridTemplateColumns: '1fr 56px 1fr' }}>
        <div className="text-[12px] tracking-[0.16em] text-xray-muted">
          YOUR INFRASTRUCTURE · plaintext + vault key in memory
        </div>
        <div />
        <div className="text-right text-[12px] tracking-[0.16em] text-xray-warm">
          ANTHROPIC PROVIDER · sees surrogates only
        </div>
      </div>
      <div className="grid items-stretch px-5 pb-4 pt-2"
           style={{ gridTemplateColumns: '1fr 56px 1fr' }}>
        <div className="flex gap-3">
          {LOCAL_STAGES.map((id, i) => (
            <XrayStageButton
              key={id}
              id={id}
              label={id}
              metric={metricFor(id, i)}
              num={i + 1}
              zone="local"
              selected={selected === id}
              status={stageStatusFor(i)}
              onClick={() => setSelected(id)}
            />
          ))}
        </div>
        <XrayBoundaryDivider />
        <div className="flex gap-3">
          {CROSSED_STAGES.map((id, i) => (
            <XrayStageButton
              key={id}
              id={id}
              label={id}
              metric={metricFor(id, i + 3)}
              num={i + 4}
              zone="crossed"
              selected={selected === id}
              status={stageStatusFor(i + 3)}
              onClick={() => setSelected(id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function statusDotColor(status: StageStatus) {
  return status === 'done' ? '#2d6e3e'
    : status === 'running' ? '#c08070'
    : status === 'errored' ? '#b85450'
    : '#4a4438';
}

function XrayStageButton({
  label,
  metric,
  num,
  zone,
  selected,
  status,
  onClick,
}: {
  id: StageId;
  label: string;
  metric: string;
  num: number;
  zone: 'local' | 'crossed';
  selected: boolean;
  status: StageStatus;
  onClick: () => void;
}) {
  const isLocal = zone === 'local';
  const dim = status === 'pending';
  const dotColor = statusDotColor(status);
  const statusLabel =
    status === 'pending' ? 'pending'
      : status === 'running' ? 'in flight'
      : status === 'errored' ? 'errored'
      : 'done';
  const borderColor = selected
    ? status === 'errored'
      ? '#b85450'
      : isLocal
        ? '#b85450'
        : '#c08070'
    : '#3a352b';
  const bgColor = selected
    ? isLocal ? '#2a261d' : '#2a201b'
    : isLocal ? 'transparent' : '#1f1c17';

  return (
    <button
      onClick={onClick}
      className={`flex-1 cursor-pointer rounded-[3px] border px-4 py-3 text-left transition ${
        dim ? 'opacity-55' : 'opacity-100'
      }`}
      style={{
        background: bgColor,
        borderColor,
        color: dim ? '#7a766a' : '#e8e4d8',
      }}
    >
      <div className="flex items-center gap-1.5">
        <span
          className={status === 'running' ? 'animate-xray-pulse' : ''}
          style={{
            width: 6,
            height: 6,
            borderRadius: 3,
            background: dotColor,
            display: 'inline-block',
          }}
        />
        <span
          className="text-[15px]"
          style={{ color: selected ? '#fff' : dim ? '#a59f8d' : '#e8e4d8' }}
        >
          {label}
        </span>
        <span
          className="ml-auto text-[14px]"
          style={{ color: dim ? '#5a564d' : '#a59f8d' }}
        >
          {metric}
        </span>
      </div>
      <div className="mt-2 text-[12px] uppercase tracking-[0.1em] text-xray-fade">
        stage {String(num).padStart(2, '0')} · {isLocal ? 'local' : 'crossed'} · {statusLabel}
      </div>
    </button>
  );
}

function XrayBoundaryDivider() {
  const accent = '#b85450';
  return (
    <div className="relative flex flex-col items-center justify-between" style={{ margin: '0 -2px', height: 84, padding: '2px 0' }}>
      <div
        style={{
          position: 'absolute', top: 14, bottom: 14, left: '50%', transform: 'translateX(-50%)',
          width: 6,
          background: `repeating-linear-gradient(180deg, ${accent} 0 4px, transparent 4px 9px)`,
          opacity: 0.55,
        }}
      />
      <div
        className="relative z-10 font-bold tracking-[0.16em]"
        style={{
          fontSize: 6.5, color: accent, background: '#1a1815', padding: '1px 3px',
          fontFamily: 'ui-monospace,Menlo,monospace', lineHeight: 1,
        }}
      >BOUNDARY</div>
      <div
        style={{
          position: 'relative', zIndex: 1, width: 38, height: 38, borderRadius: 19,
          background: 'radial-gradient(circle at 30% 30%, #2e2620, #1a1612 70%)',
          border: `1.5px solid ${accent}`,
          display: 'grid', placeItems: 'center',
          boxShadow: `0 0 0 3px #1a1815, 0 0 10px ${accent}55`,
        }}
      >
        <svg width="20" height="20" viewBox="0 0 22 22" fill="none">
          <rect x="6" y="9" width="10" height="9" rx="1.5" stroke={accent} strokeWidth="1.3" />
          <path d="M8 9V6.5a3 3 0 016 0V9" stroke={accent} strokeWidth="1.3" fill="none" />
          <circle cx="11" cy="13.5" r="1.3" fill={accent} />
        </svg>
      </div>
      <div
        className="relative z-10 tracking-[0.16em] text-xray-muted"
        style={{
          fontSize: 8, background: '#1a1815', padding: '1px 6px',
          fontFamily: 'ui-monospace,Menlo,monospace', lineHeight: 1,
        }}
      >TLS 1.3</div>
    </div>
  );
}

// ─── Inspector ─────────────────────────────────────────────────────────────

interface InspectorProps {
  selected: StageId;
  result: PipelineResult | null;
  strategy: Strategy;
  audit: AuditEntry[];
  hovered: string | null;
  setHovered: (next: string | null) => void;
  stageStatus: StageStatus;
  runState: RunState;
  uniqueMap: SurrogateMapping[];
  errorMessage: string | null;
  bannerExpanded: boolean;
  onToggleBannerExpanded: () => void;
}

function XrayInspector({
  selected,
  result,
  strategy,
  audit,
  hovered,
  setHovered,
  stageStatus,
  runState,
  uniqueMap,
  errorMessage,
  bannerExpanded,
  onToggleBannerExpanded,
}: InspectorProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 p-4">
      <XrayStageBanner
        selected={selected}
        result={result}
        strategy={strategy}
        stageStatus={stageStatus}
        tokenCount={uniqueMap.length}
        expanded={bannerExpanded}
        onToggleExpanded={onToggleBannerExpanded}
      />
      <div className="grid min-h-0 flex-1 gap-4"
           style={{ gridTemplateColumns: '1fr 320px 1fr' }}>
        {stageStatus === 'pending' ? (
          <XrayPendingPlaceholder runState={runState} />
        ) : stageStatus === 'running' ? (
          <XrayInFlightPlaceholder result={result} />
        ) : stageStatus === 'errored' ? (
          <XrayErroredPlaceholder result={result} audit={audit} errorMessage={errorMessage} />
        ) : !result ? (
          <XrayPendingPlaceholder runState="idle" />
        ) : (
          <>
            {selected === 'document' && (
              <XrayDocument result={result} hovered={hovered} setHovered={setHovered} audit={audit} />
            )}
            {selected === 'detect' && (
              <XrayDetect result={result} hovered={hovered} setHovered={setHovered} audit={audit} />
            )}
            {selected === 'obfuscate' && (
              <XrayObfuscate
                result={result}
                strategy={strategy}
                hovered={hovered}
                setHovered={setHovered}
                uniqueMap={uniqueMap}
              />
            )}
            {selected === 'llm' && <XrayLlm result={result} />}
            {selected === 'restore' && (
              <XrayRestore
                result={result}
                hovered={hovered}
                setHovered={setHovered}
                uniqueMap={uniqueMap}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ─── Stage banner ──────────────────────────────────────────────────────────

function XrayStageBanner({
  selected,
  result,
  strategy,
  stageStatus,
  tokenCount,
  expanded,
  onToggleExpanded,
}: {
  selected: StageId;
  result: PipelineResult | null;
  strategy: Strategy;
  stageStatus: StageStatus;
  tokenCount: number;
  expanded: boolean;
  onToggleExpanded: () => void;
}) {
  const entities = result?.detected_entities ?? [];
  const types = new Set(entities.map((e) => e.type)).size;
  const banners: Record<StageId, {
    title: string;
    meta: Array<[string, string | number]>;
    claim: string;
    tone: 'local' | 'pivot' | 'crossed';
  }> = {
    document: {
      title: 'document_ingest',
      meta: [
        ['bytes', result?.document_text.length ?? 0],
        ['encrypted_at', 'aes-256-gcm (vault key)'],
      ],
      claim:
        'Cleartext lives in per-user vault only. This panel is the only surface where originals exist.',
      tone: 'local',
    },
    detect: {
      title: 'entity_detection',
      meta: [
        ['recognizers', 13],
        ['entities', entities.length],
        ['types', types],
        ['threshold', '0.50'],
      ],
      claim:
        'Presidio + custom recognizers. No span leaves this stage; offsets only feed the obfuscator.',
      tone: 'local',
    },
    obfuscate: {
      title: 'obfuscate · ' + strategy,
      meta: [
        ['strategy', strategy],
        ['tokens_minted', tokenCount],
        ['vault_writes', tokenCount],
        ['reversible_in_session', 'true'],
      ],
      claim:
        'Every original is replaced with a vault-mapped surrogate. The string on the right is the exact bytes that cross.',
      tone: 'pivot',
    },
    llm: {
      title: 'provider_call',
      meta: [
        ['provider', 'anthropic'],
        ['model', 'claude-haiku-4-5'],
        ['prompt_chars', result?.obfuscated_prompt.length ?? 0],
      ],
      claim:
        'Outbound payload is post-obfuscation. Inbound response is a verbatim provider string with token IDs intact.',
      tone: 'crossed',
    },
    restore: {
      title: 'deobfuscate',
      meta: [
        ['tokens_resolved', tokenCount],
        ['unresolved', 0],
        ['source', 'session vault'],
      ],
      claim:
        'Vault lookup is in-process. Originals never enter logs or analytics — only the user sees them.',
      tone: 'local',
    },
  };

  const b = banners[selected];
  const isDone = stageStatus === 'done';
  const statusBadge =
    stageStatus === 'pending' ? 'NOT YET RUN'
      : stageStatus === 'running' ? 'IN FLIGHT'
      : stageStatus === 'errored' ? 'ERRORED'
      : null;
  const effectiveMeta = isDone
    ? b.meta
    : b.meta.map(([k]) => [k, stageStatus === 'errored' ? '—' : stageStatus === 'running' ? '…' : '—'] as [string, string]);
  const effectiveClaim = isDone
    ? b.claim
    : stageStatus === 'pending'
      ? 'This stage has not executed in the current run. The claim above will hold once it does.'
      : stageStatus === 'running'
        ? 'Stage is in flight. Values shown when complete.'
        : 'Stage failed. Vault remains intact — originals were never released.';
  const bg = !isDone && stageStatus === 'errored'
    ? 'bg-xray-banner-error'
    : b.tone === 'crossed' ? 'bg-xray-banner-crossed'
    : b.tone === 'pivot' ? 'bg-xray-banner-pivot'
    : 'bg-xray-banner';
  const acc = !isDone && stageStatus === 'errored'
    ? '#b85450'
    : !isDone && stageStatus === 'running'
      ? '#c08070'
      : !isDone
        ? '#7a766a'
        : b.tone === 'crossed' ? '#b85450'
        : b.tone === 'pivot' ? '#c08070'
        : '#2d6e3e';
  const surfaceBadge = b.tone === 'crossed' ? 'provider surface' : b.tone === 'pivot' ? 'boundary transform' : 'local only';

  if (!expanded) {
    return (
      <div className={`rounded-[3px] border border-xray-border px-4 py-2 ${bg}`}
           style={{ borderLeft: `3px solid ${acc}` }}>
        <div className="flex min-w-0 items-center gap-4">
          <span className="font-serif text-[16px] text-white">{b.title}</span>
          <span className="shrink-0 text-[12px] font-semibold uppercase tracking-[0.14em]"
                style={{ color: acc }}>
            {statusBadge ?? surfaceBadge}
          </span>
          <div className="flex min-w-0 flex-1 gap-4 overflow-hidden text-[13px]">
            {effectiveMeta.slice(0, 4).map(([k, v]) => (
              <div key={k} className="min-w-0 truncate">
                <span className="text-xray-fade">{k}=</span>
                <span style={{ color: isDone ? '#e8e4d8' : '#7a766a' }}>{String(v)}</span>
              </div>
            ))}
          </div>
          <button
            onClick={onToggleExpanded}
            className="shrink-0 rounded-[3px] border border-xray-border-strong px-3 py-1 text-[13px] text-xray-muted transition hover:bg-xray-inset-deep hover:text-xray-ink"
          >
            Details
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className={`rounded-[3px] border border-xray-border px-4 py-3.5 ${bg}`}
         style={{ borderLeft: `3px solid ${acc}` }}>
      <div className="flex items-baseline gap-4">
        <span className="font-serif text-[18px] text-white">{b.title}</span>
        <span className="text-[12px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: acc }}>
          {statusBadge ?? surfaceBadge}
        </span>
        <button
          onClick={onToggleExpanded}
          className="ml-auto rounded-[3px] border border-xray-border-strong px-3 py-1 text-[13px] text-xray-muted transition hover:bg-xray-inset-deep hover:text-xray-ink"
        >
          Collapse details
        </button>
      </div>
      <div className="mt-2 flex gap-4 text-[14px]">
        {effectiveMeta.map(([k, v]) => (
          <div key={k}>
            <span className="text-xray-fade">{k}=</span>
            <span style={{ color: isDone ? '#e8e4d8' : '#7a766a' }}>{String(v)}</span>
          </div>
        ))}
      </div>
      <div className="mt-2 font-serif italic text-[14px] text-xray-text">
        {effectiveClaim}
      </div>
    </div>
  );
}

// ─── Placeholders ──────────────────────────────────────────────────────────

function XrayHollowColumn({
  title,
  hint,
  icon,
  accent = '#3a352b',
}: {
  title: string;
  hint: string;
  icon: ReactNode;
  accent?: string;
}) {
  return (
    <div
      className="flex flex-col items-center justify-center gap-3 rounded-[3px] p-6 text-center text-xray-muted"
      style={{ background: '#1c1a17', border: `1px dashed ${accent}` }}
    >
      {icon}
      <div className="text-[12px] uppercase tracking-[0.14em]" style={{ color: accent }}>
        {title}
      </div>
      <div className="max-w-[240px] text-[14px] leading-[1.5] text-xray-fade">{hint}</div>
    </div>
  );
}

function XrayPendingPlaceholder({ runState }: { runState: RunState }) {
  const isIdle = runState === 'idle';
  return (
    <>
      <XrayHollowColumn
        title="not yet run"
        hint={
          isIdle
            ? 'Upload a document and trigger the run. The source pane will populate as the pipeline ingests.'
            : 'Waiting for earlier stages to complete. This pane will populate when the pipeline reaches it.'
        }
        icon={
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="6" y="3" width="16" height="22" rx="2" stroke="#4a4438" strokeWidth="1.4" strokeDasharray="3 3" />
          </svg>
        }
      />
      <XrayHollowColumn
        title="awaiting input"
        hint={
          isIdle
            ? 'No transform has executed. The vault key has not been minted yet.'
            : 'This stage runs after the previous stages complete.'
        }
        icon={
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="14" r="10" stroke="#4a4438" strokeWidth="1.4" strokeDasharray="3 3" />
          </svg>
        }
      />
      <XrayHollowColumn
        title="no output"
        hint={
          isIdle
            ? 'Nothing has crossed the boundary. Nothing has been written to audit.'
            : 'Output will materialise once this stage runs.'
        }
        icon={
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <path d="M4 14h20M18 8l6 6-6 6" stroke="#4a4438" strokeWidth="1.4" strokeDasharray="3 3" fill="none" />
          </svg>
        }
      />
    </>
  );
}

function XrayInFlightPlaceholder({ result }: { result: PipelineResult | null }) {
  const [hovered, setHovered] = useState<string | null>(null);
  return (
    <>
      <XrayPane label="outbound · obfuscated_prompt (sent, awaiting response)" tone="crossed">
        {result ? <XrayTokens text={result.obfuscated_prompt} hovered={hovered} setHovered={setHovered} /> : null}
      </XrayPane>
      <div className="flex flex-col items-center justify-center gap-4 rounded-[3px] p-6"
           style={{ background: '#22201b', border: '1px solid #b8545055' }}>
        <div
          className="animate-xray-spin"
          style={{
            width: 44,
            height: 44,
            borderRadius: 22,
            border: '2px solid #b8545033',
            borderTopColor: '#b85450',
          }}
        />
        <div className="text-[12px] uppercase tracking-[0.16em] text-xray-warm">llm call in flight</div>
        <div className="max-w-[240px] text-center text-[14px] leading-[1.55] text-xray-muted">
          Payload sealed at boundary. Awaiting response from{' '}
          <strong className="text-xray-ink">claude-haiku-4-5</strong>.
        </div>
        <div className="flex gap-4 text-[14px] text-xray-fade"
             style={{ fontFamily: 'ui-monospace,Menlo,monospace' }}>
          <span>p50 ~2.4 s</span>
          <span>·</span>
          <span>timeout 30 s</span>
        </div>
      </div>
      <XrayHollowColumn
        title="response not received"
        hint="The provider has not yet returned. When it does, the raw response will appear here with token IDs intact — ready for vault lookup at stage 5."
        accent="#c08070"
        icon={
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <path d="M24 14H4M10 20l-6-6 6-6" stroke="#c08070" strokeWidth="1.4" strokeDasharray="3 3" fill="none" />
          </svg>
        }
      />
    </>
  );
}

function XrayErroredPlaceholder({
  result,
  audit,
  errorMessage,
}: {
  result: PipelineResult | null;
  audit: AuditEntry[];
  errorMessage: string | null;
}) {
  const [hovered, setHovered] = useState<string | null>(null);
  const errorEvent = audit.find((e) => e.action.includes('ERROR'));
  return (
    <>
      <XrayPane label="outbound · obfuscated_prompt (was sent)" tone="crossed">
        {result ? <XrayTokens text={result.obfuscated_prompt} hovered={hovered} setHovered={setHovered} /> : null}
      </XrayPane>
      <div className="flex flex-col gap-3 rounded-[3px] p-4"
           style={{ background: '#22181a', border: '1px solid #b85450' }}>
        <div className="flex items-center gap-3">
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <circle cx="10" cy="10" r="8" stroke="#b85450" strokeWidth="1.5" />
            <path d="M7 7l6 6M13 7l-6 6" stroke="#b85450" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <div className="text-[15px] font-semibold tracking-wide text-accent">Provider call failed</div>
        </div>
        <div className="text-[14px] leading-[1.55] text-xray-text">
          Outbound payload was sealed and transmitted. No response received within the retry window.
          Vault remains intact — originals never left.
        </div>
        <div className="rounded-[3px] border border-xray-border-soft bg-xray-inset p-3 text-[14px]">
          <KV k="status" v={String(errorEvent?.metadata.status ?? 503)} />
          <KV k="message" v={errorMessage ?? String(errorEvent?.metadata.message ?? 'provider unavailable')} />
          <KV k="vault" v="intact · no leak" />
        </div>
      </div>
      <XrayHollowColumn
        title="no response"
        hint="Stage 5 (restore) was never reached. The user has not seen any LLM output. No surrogates leaked to logs or analytics."
        accent="#b85450"
        icon={
          <svg width="28" height="28" viewBox="0 0 28 28" fill="none">
            <rect x="5" y="6" width="18" height="16" rx="2" stroke="#b85450" strokeWidth="1.4" strokeDasharray="3 3" />
            <path d="M9 14h10" stroke="#b85450" strokeWidth="1.4" />
          </svg>
        }
      />
    </>
  );
}

// ─── Pane + highlighters ───────────────────────────────────────────────────

function XrayPane({
  label,
  tone,
  children,
  scroll = true,
}: {
  label: string;
  tone: 'local' | 'crossed';
  children: ReactNode;
  scroll?: boolean;
}) {
  const bg = tone === 'crossed' ? 'bg-xray-panel-crossed' : 'bg-xray-panel';
  const borderClass = tone === 'crossed' ? 'border-[#3a2e26]' : 'border-xray-border';
  const labelColor = tone === 'crossed' ? 'text-xray-warm' : 'text-xray-muted';
  return (
    <div className={`flex min-h-0 flex-col rounded-[3px] border ${borderClass} ${bg}`}>
      <div className={`border-b ${borderClass} px-4 py-2.5 text-[14px] uppercase tracking-[0.14em] ${labelColor}`}>
        {label}
      </div>
      <div
        className={`flex-1 p-3 text-[15px] leading-[1.6] ${scroll ? 'overflow-auto' : ''}`}
      >
        {children}
      </div>
    </div>
  );
}

function XrayHighlight({
  text,
  entities,
  hovered,
  setHovered,
}: {
  text: string;
  entities: Entity[];
  hovered: string | null;
  setHovered: (next: string | null) => void;
}) {
  if (!entities.length) return <span className="whitespace-pre-wrap text-xray-ink">{text}</span>;
  const sorted = [...entities].sort((a, b) => a.start - b.start);
  const out: ReactNode[] = [];
  let cur = 0;
  for (let i = 0; i < sorted.length; i += 1) {
    const e = sorted[i];
    if (e.start > cur) {
      out.push(
        <span key={`g${cur}`} style={{ color: '#c8c2b1' }}>{text.slice(cur, e.start)}</span>,
      );
    }
    const c = entityColor(e.type);
    const isH = hovered === e.type;
    out.push(
      <span
        key={`e${e.start}`}
        onMouseEnter={() => setHovered(e.type)}
        onMouseLeave={() => setHovered(null)}
        style={{
          background: isH ? c.dot : c.bg + '33',
          color: isH ? '#fff' : c.dot,
          padding: '0 3px',
          borderRadius: 2,
          transition: 'all .12s',
          boxShadow: isH ? 'none' : `inset 0 -1px 0 ${c.dot}88`,
        }}
      >
        {text.slice(e.start, e.end)}
      </span>,
    );
    cur = e.end;
  }
  if (cur < text.length) {
    out.push(
      <span key="tail" style={{ color: '#c8c2b1' }}>{text.slice(cur)}</span>,
    );
  }
  return <span className="whitespace-pre-wrap">{out}</span>;
}

function XrayTokens({
  text,
  hovered,
  setHovered,
}: {
  text: string;
  hovered: string | null;
  setHovered: (next: string | null) => void;
}) {
  const matches = Array.from(text.matchAll(/\[([A-Z_]+)_[a-zA-Z0-9]+\]/g));
  if (matches.length === 0) {
    return <span className="whitespace-pre-wrap" style={{ color: '#c8c2b1' }}>{text}</span>;
  }
  const parts: ReactNode[] = [];
  let last = 0;
  matches.forEach((m, idx) => {
    const start = m.index ?? 0;
    if (start > last) {
      parts.push(
        <span key={`g${idx}`} style={{ color: '#c8c2b1' }}>{text.slice(last, start)}</span>,
      );
    }
    const c = entityColor(m[1]);
    const token = m[0];
    const isH = hovered === token;
    parts.push(
      <span
        key={`t${idx}`}
        onMouseEnter={() => setHovered(token)}
        onMouseLeave={() => setHovered(null)}
        style={{
          background: isH ? c.dot : c.bg + '22',
          color: isH ? '#fff' : c.dot,
          padding: '0 3px',
          borderRadius: 2,
          fontSize: '0.92em',
        }}
      >
        {token}
      </span>,
    );
    last = start + token.length;
  });
  if (last < text.length) {
    parts.push(<span key="tail" style={{ color: '#c8c2b1' }}>{text.slice(last)}</span>);
  }
  return <span className="whitespace-pre-wrap">{parts}</span>;
}

function PseudonymInDark({
  text,
  surrogates,
  hovered,
  setHovered,
}: {
  text: string;
  surrogates: SurrogateMapping[];
  hovered: string | null;
  setHovered: (next: string | null) => void;
}) {
  const valueToSwatch = new Map<string, EntitySwatch>();
  for (const s of surrogates) {
    if (s.surrogate && s.surrogate !== s.entity.text) {
      valueToSwatch.set(s.surrogate, entityColor(s.entity.type));
    }
  }
  const values = Array.from(valueToSwatch.keys());
  if (values.length === 0) return <span className="whitespace-pre-wrap" style={{ color: '#c8c2b1' }}>{text}</span>;
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp('(' + values.map(esc).join('|') + ')', 'g');
  const matches = Array.from(text.matchAll(re));
  if (matches.length === 0) {
    return <span className="whitespace-pre-wrap" style={{ color: '#c8c2b1' }}>{text}</span>;
  }
  const parts: ReactNode[] = [];
  let last = 0;
  matches.forEach((m, idx) => {
    const start = m.index ?? 0;
    if (start > last) {
      parts.push(
        <span key={`g${idx}`} style={{ color: '#c8c2b1' }}>{text.slice(last, start)}</span>,
      );
    }
    const value = m[0];
    const c = valueToSwatch.get(value)!;
    const isH = hovered === value;
    parts.push(
      <span
        key={`p${idx}`}
        onMouseEnter={() => setHovered(value)}
        onMouseLeave={() => setHovered(null)}
        style={{
          background: isH ? c.dot : c.bg + '22',
          color: isH ? '#fff' : c.dot,
          padding: '0 3px',
          borderRadius: 2,
          fontStyle: 'italic',
        }}
      >
        {value}
      </span>,
    );
    last = start + value.length;
  });
  if (last < text.length) {
    parts.push(<span key="tail" style={{ color: '#c8c2b1' }}>{text.slice(last)}</span>);
  }
  return <span className="whitespace-pre-wrap">{parts}</span>;
}

// ─── Stage panels ──────────────────────────────────────────────────────────

function XrayDocument({
  result,
  hovered,
  setHovered,
  audit,
}: {
  result: PipelineResult;
  hovered: string | null;
  setHovered: (next: string | null) => void;
  audit: AuditEntry[];
}) {
  return (
    <>
      <XrayPane label="source · plaintext (local vault)" tone="local">
        <XrayHighlight
          text={result.document_text}
          entities={result.detected_entities}
          hovered={hovered}
          setHovered={setHovered}
        />
      </XrayPane>
      <XrayPane label="transform · ingest" tone="local" scroll={false}>
        <div className="text-[14px]">
          <KV k="bytes" v={String(result.document_text.length)} />
          <KV k="encryption" v="aes-256-gcm" />
          <KV k="vault_key" v="in-memory · per session" />
          <KV k="status" v="encrypted locally" />
        </div>
      </XrayPane>
      <XrayEvidence audit={audit} filterStages={['vault']} title="audit · ingest" />
    </>
  );
}

function XrayDetect({
  result,
  hovered,
  setHovered,
  audit,
}: {
  result: PipelineResult;
  hovered: string | null;
  setHovered: (next: string | null) => void;
  audit: AuditEntry[];
}) {
  const summary = summarizeEntities(result.detected_entities);
  return (
    <>
      <XrayPane label="source · plaintext (highlighted)" tone="local">
        <XrayHighlight
          text={result.document_text}
          entities={result.detected_entities}
          hovered={hovered}
          setHovered={setHovered}
        />
      </XrayPane>
      <XrayPane label="transform · presidio analyze" tone="local">
        <div className="flex flex-col gap-1">
          {summary.map((s) => {
            const c = entityColor(s.type);
            const isH = hovered === s.type;
            return (
              <div
                key={s.type}
                onMouseEnter={() => setHovered(s.type)}
                onMouseLeave={() => setHovered(null)}
                className="rounded-[3px] px-4 py-2.5"
                style={{
                  border: `1px solid ${isH ? c.dot : '#2e2a22'}`,
                  background: isH ? c.dot + '22' : '#181613',
                }}
              >
                <div className="flex items-center gap-3">
                  <span style={{ width: 8, height: 8, borderRadius: 4, background: c.dot, display: 'inline-block' }} />
                  <span className="text-[14px] text-xray-ink">{s.type}</span>
                  <span className="ml-auto text-[14px] text-xray-muted">×{s.count}</span>
                </div>
                <div className="mt-1 truncate text-[14px] text-xray-muted">
                  {s.samples.join(' · ')}
                </div>
              </div>
            );
          })}
        </div>
      </XrayPane>
      <XrayEvidence audit={audit} filterStages={['vault', 'detect']} title="audit · detect" />
    </>
  );
}

function XrayObfuscate({
  result,
  strategy,
  hovered,
  setHovered,
  uniqueMap,
}: {
  result: PipelineResult;
  strategy: Strategy;
  hovered: string | null;
  setHovered: (next: string | null) => void;
  uniqueMap: SurrogateMapping[];
}) {
  return (
    <>
      <XrayPane label="source · plaintext (local only)" tone="local">
        <XrayHighlight
          text={result.document_text}
          entities={result.detected_entities}
          hovered={hovered}
          setHovered={setHovered}
        />
      </XrayPane>
      <XrayPane label={`transform · ${strategy} (vault-mapped)`} tone="local">
        <ObfTokenMap
          uniqueMap={uniqueMap}
          strategy={strategy}
          hovered={hovered}
          setHovered={setHovered}
        />
      </XrayPane>
      <XrayPane label="output · obfuscated_document (provider-visible)" tone="crossed">
        {strategy === 'tokenize' ? (
          <XrayTokens text={result.obfuscated_document} hovered={hovered} setHovered={setHovered} />
        ) : (
          <PseudonymInDark
            text={result.obfuscated_document}
            surrogates={uniqueMap}
            hovered={hovered}
            setHovered={setHovered}
          />
        )}
      </XrayPane>
    </>
  );
}

function ObfTokenMap({
  uniqueMap,
  strategy,
  hovered,
  setHovered,
}: {
  uniqueMap: SurrogateMapping[];
  strategy: Strategy;
  hovered: string | null;
  setHovered: (next: string | null) => void;
}) {
  return (
    <div className="text-[14px]">
      <div
        className="grid items-center gap-3 border-b border-xray-border pb-2 text-[12px] uppercase tracking-[0.12em] text-xray-fade"
        style={{ gridTemplateColumns: '1fr 14px 1fr' }}
      >
        <span>original (local)</span>
        <span />
        <span>surrogate</span>
      </div>
      <div className="mt-2 flex flex-col gap-0.5">
        {uniqueMap.map((r) => {
          const c = entityColor(r.entity.type);
          const isH = hovered === r.entity.type;
          return (
            <div
              key={r.key}
              onMouseEnter={() => setHovered(r.entity.type)}
              onMouseLeave={() => setHovered(null)}
              className="grid items-center gap-3 rounded-[2px] px-1 py-1"
              style={{
                gridTemplateColumns: '1fr 14px 1fr',
                background: isH ? c.dot + '22' : 'transparent',
              }}
            >
              <span className="truncate whitespace-nowrap" style={{ color: c.dot }}>
                {r.entity.text}
              </span>
              <svg width="14" height="8" viewBox="0 0 14 8" fill="none" style={{ opacity: 0.6 }}>
                <path d="M0 4h12M9 1l3 3-3 3" stroke="#7a766a" strokeWidth="1" fill="none" strokeLinecap="round" />
              </svg>
              <span
                className="truncate whitespace-nowrap text-xray-ink"
                style={{ fontStyle: strategy === 'pseudonymize' ? 'italic' : 'normal' }}
              >
                {r.surrogate}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function XrayLlm({ result }: { result: PipelineResult }) {
  const [hovered, setHovered] = useState<string | null>(null);
  return (
    <>
      <XrayPane label="outbound · obfuscated_prompt (provider receives)" tone="crossed">
        <XrayTokens text={result.obfuscated_prompt} hovered={hovered} setHovered={setHovered} />
      </XrayPane>
      <XrayPane label="transit · provider call" tone="crossed">
        <div className="text-[14px]">
          <KV k="provider" v="anthropic" />
          <KV k="model" v="claude-haiku-4-5" />
          <KV k="endpoint" v="api.anthropic.com" />
          <KV k="tls" v="1.3 · sha256_rsa" />
          <KV k="prompt_chars" v={String(result.obfuscated_prompt.length)} />
          <div className="mt-3.5 rounded-[3px] border border-[#b8545055] bg-xray-inset p-3">
            <div className="mb-1 text-[12px] uppercase tracking-[0.13em] text-accent">provider can see</div>
            <div className="text-[14px] leading-[1.7] text-xray-ink">
              ✓ obfuscated_prompt (token IDs)<br />
              ✓ session_id (opaque)<br />
              ✗ originals · vault stays local<br />
              ✗ vault key · in-memory only
            </div>
          </div>
        </div>
      </XrayPane>
      <XrayPane label="inbound · llm_response_raw (returns with tokens)" tone="crossed">
        <XrayTokens text={result.llm_response_raw} hovered={hovered} setHovered={setHovered} />
      </XrayPane>
    </>
  );
}

function XrayRestore({
  result,
  hovered,
  setHovered,
  uniqueMap,
}: {
  result: PipelineResult;
  hovered: string | null;
  setHovered: (next: string | null) => void;
  uniqueMap: SurrogateMapping[];
}) {
  const hitCount = uniqueMap.filter((s) => result.llm_response_raw.includes(s.surrogate)).length;
  return (
    <>
      <XrayPane label="input · llm_response_raw (with tokens)" tone="crossed">
        <XrayTokens text={result.llm_response_raw} hovered={hovered} setHovered={setHovered} />
      </XrayPane>
      <XrayPane label="transform · vault lookup" tone="local">
        <ResolutionList
          result={result}
          uniqueMap={uniqueMap}
          hovered={hovered}
          setHovered={setHovered}
        />
        <div className="mt-2.5 rounded-[3px] border border-xray-border bg-xray-inset p-3 text-[14px]">
          <div className="text-good">✓ all tokens resolved</div>
          <div className="mt-0.5 text-xray-muted">unresolved markers: 0</div>
          <div className="text-xray-muted">vault hits: {hitCount} / {uniqueMap.length}</div>
        </div>
      </XrayPane>
      <XrayPane label="output · restored_response (user-facing)" tone="local">
        <MiniMarkdown text={result.restored_response} entities={result.detected_entities} />
      </XrayPane>
    </>
  );
}

function ResolutionList({
  result,
  uniqueMap,
  hovered,
  setHovered,
}: {
  result: PipelineResult;
  uniqueMap: SurrogateMapping[];
  hovered: string | null;
  setHovered: (next: string | null) => void;
}) {
  const rows = uniqueMap.map((r) => ({
    ...r,
    inResponse: result.llm_response_raw.includes(r.surrogate),
  }));
  rows.sort((a, b) => Number(b.inResponse) - Number(a.inResponse));
  return (
    <div className="text-[14px]">
      <div
        className="grid items-center gap-1.5 border-b border-xray-border pb-2 text-[12px] uppercase tracking-[0.12em] text-xray-fade"
        style={{ gridTemplateColumns: '1fr 14px 1fr 14px' }}
      >
        <span>token (from llm)</span>
        <span />
        <span>original (vault)</span>
        <span />
      </div>
      <div className="mt-2 flex max-h-80 flex-col gap-0.5 overflow-auto">
        {rows.map((r) => {
          const c = entityColor(r.entity.type);
          const isH = hovered === r.entity.type;
          return (
            <div
              key={r.key}
              onMouseEnter={() => setHovered(r.entity.type)}
              onMouseLeave={() => setHovered(null)}
              className="grid items-center gap-1.5 rounded-[2px] px-1 py-1"
              style={{
                gridTemplateColumns: '1fr 14px 1fr 14px',
                background: isH ? c.dot + '22' : 'transparent',
                opacity: r.inResponse ? 1 : 0.4,
              }}
            >
              <span
                className="truncate whitespace-nowrap"
                style={{ color: c.dot, fontFamily: 'ui-monospace,Menlo,monospace', fontSize: 10.5 }}
              >
                {r.surrogate}
              </span>
              <svg width="14" height="8" viewBox="0 0 14 8" fill="none" style={{ opacity: 0.6 }}>
                <path d="M0 4h12M9 1l3 3-3 3" stroke="#7a766a" strokeWidth="1" fill="none" strokeLinecap="round" />
              </svg>
              <span className="truncate whitespace-nowrap text-xray-ink">{r.entity.text}</span>
              <span
                className="text-center text-[14px]"
                style={{ color: r.inResponse ? '#2d6e3e' : '#4a4438' }}
              >
                {r.inResponse ? '✓' : '·'}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Evidence pane ─────────────────────────────────────────────────────────

function XrayEvidence({
  audit,
  filterStages,
  title,
}: {
  audit: AuditEntry[];
  filterStages: AuditStage[];
  title: string;
}) {
  const events = audit.filter((e) => filterStages.includes(e.stage));
  return (
    <div className="flex min-h-0 flex-col rounded-[3px] border border-xray-border bg-xray-panel">
      <div className="flex justify-between border-b border-xray-border px-4 py-2.5 text-[14px] uppercase tracking-[0.14em] text-xray-muted">
        <span>{title}</span>
        <span className="text-xray-fade">{events.length} events</span>
      </div>
      <div className="flex-1 overflow-auto p-3 text-[14px]">
        {events.length === 0 && (
          <div className="px-1.5 py-1 text-xray-fade">no audit events yet for this stage.</div>
        )}
        {events.map((e, i) => (
          <div key={i} className="mb-0.5 border-l-2 border-xray-border-soft px-1.5 py-1">
            <div className="text-[14px] text-xray-fade">{fmtTime(e.timestamp).slice(0, 12)}</div>
            <div className="text-xray-ink">{e.action}</div>
            {e.token_id && <div className="text-[14px] text-xray-warm">{e.token_id}</div>}
            {e.entity_type && !e.token_id && (
              <div className="text-[14px] text-xray-muted">{e.entity_type}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── Markdown rendering ────────────────────────────────────────────────────
// Uses react-markdown + remark-gfm so tables, task lists, strikethrough etc.
// render correctly. Entity highlighting is layered on top by walking the
// rendered children of each text-bearing component and wrapping string
// matches in entity-colored spans.

function MiniMarkdown({ text, entities }: { text: string; entities: Entity[] }) {
  const distinct = useMemo(
    () => Array.from(new Set(entities.map((e) => e.text))).filter((s) => s.length > 2),
    [entities],
  );
  const typeByText = useMemo(() => {
    const m = new Map<string, string>();
    for (const e of entities) if (!m.has(e.text)) m.set(e.text, e.type);
    return m;
  }, [entities]);

  const highlight = (children: ReactNode): ReactNode =>
    Children.map(children, (child) => {
      if (typeof child === 'string') return highlightString(child, distinct, typeByText);
      return child;
    });

  return (
    <div className="text-[14px] leading-[1.6] text-xray-ink">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h2 className="mb-2 mt-3 font-serif text-[22px] text-xray-ink">{highlight(children)}</h2>
          ),
          h2: ({ children }) => (
            <h3 className="mb-2 mt-3 font-serif text-[18px] text-xray-ink">{highlight(children)}</h3>
          ),
          h3: ({ children }) => (
            <h4 className="mb-2 mt-2.5 font-serif text-[14px] text-xray-ink">{highlight(children)}</h4>
          ),
          p: ({ children }) => <p className="my-2 leading-[1.6]">{highlight(children)}</p>,
          ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
          ol: ({ children }) => <ol className="my-2 list-decimal space-y-1 pl-5">{children}</ol>,
          li: ({ children }) => <li>{highlight(children)}</li>,
          strong: ({ children }) => (
            <strong className="font-semibold text-white">{highlight(children)}</strong>
          ),
          em: ({ children }) => <em>{highlight(children)}</em>,
          a: ({ children, href }) => (
            <a href={href} className="text-xray-warm underline" target="_blank" rel="noreferrer">
              {highlight(children)}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded bg-xray-inset px-1 py-1 font-mono text-[15px] text-xray-text">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-2 overflow-auto rounded bg-xray-inset p-3 text-[15px] text-xray-text">
              {children}
            </pre>
          ),
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-xray-border-soft pl-3 italic text-xray-text">
              {children}
            </blockquote>
          ),
          table: ({ children }) => (
            <div className="my-2 overflow-x-auto">
              <table className="w-full border-collapse border border-xray-border text-[15px]">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-xray-inset-deep">{children}</thead>,
          tbody: ({ children }) => <tbody>{children}</tbody>,
          tr: ({ children }) => <tr className="border-b border-xray-border">{children}</tr>,
          th: ({ children }) => (
            <th className="border border-xray-border px-4 py-2.5 text-left font-semibold text-xray-ink">
              {highlight(children)}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-xray-border px-4 py-2.5 align-top">{highlight(children)}</td>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function highlightString(
  text: string,
  distinct: string[],
  typeByText: Map<string, string>,
): ReactNode {
  if (distinct.length === 0) return text;
  const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const re = new RegExp('(' + distinct.map(esc).join('|') + ')', 'g');
  const matches = Array.from(text.matchAll(re));
  if (matches.length === 0) return text;
  const parts: ReactNode[] = [];
  let last = 0;
  matches.forEach((m, idx) => {
    const start = m.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    const value = m[0];
    const c = entityColor(typeByText.get(value) ?? 'PII_NAME');
    parts.push(
      <span key={`h${idx}`} style={{ color: c.dot, fontWeight: 500 }}>
        {value}
      </span>,
    );
    last = start + value.length;
  });
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}

function KV({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-1.5 border-b border-dashed border-xray-border-soft py-1">
      <span className="min-w-[110px] text-[14px] text-xray-fade">{k}</span>
      <span className="text-[14px] text-xray-ink">{v}</span>
    </div>
  );
}
