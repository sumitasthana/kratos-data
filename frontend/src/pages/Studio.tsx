import { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useInterview } from '../interviewStore';
import { Graph } from '../components/Graph';

type Tab = 'Graph' | 'Spec' | 'Data';

export function Studio(): JSX.Element {
  const { sessionId, messages, graph, yaml, phase, loading, llmEnabled, error,
          sample, generating, begin, respond, generate } = useInterview();
  const [tab, setTab] = useState<Tab>('Graph');
  const [text, setText] = useState('');
  const scroller = useRef<HTMLDivElement>(null);

  useEffect(() => { begin(); }, [begin]);
  // when the Builder finishes, jump to the graph so the result is visible
  useEffect(() => { if (phase === 'built') setTab('Graph'); }, [phase]);
  useEffect(() => { scroller.current?.scrollTo(0, scroller.current.scrollHeight); }, [messages, loading]);

  const send = () => { if (text.trim()) { respond(text); setText(''); } };

  return (
    <div className="h-screen flex overflow-hidden bg-white text-gray-900">
      {/* Left: conversation */}
      <div className="w-96 border-r border-gray-200 flex flex-col bg-gray-50">
        <div className="p-4 border-b border-gray-200 flex items-center justify-between">
          <h1 className="text-lg font-bold">Cardinal Studio</h1>
          <span className={`text-xs px-2 py-0.5 rounded-full ${llmEnabled
            ? 'bg-purple-100 text-purple-700' : 'bg-gray-200 text-gray-600'}`}>
            {llmEnabled ? 'Claude' : 'offline'}
          </span>
        </div>

        <div ref={scroller} className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div key={i} className={m.role === 'you' ? 'text-right' : 'text-left'}>
              <div className={`inline-block px-3 py-2 rounded-2xl text-sm max-w-[88%] text-left ${
                m.role === 'you'
                  ? 'bg-blue-600 text-white rounded-br-sm whitespace-pre-line'
                  : 'bg-white border border-gray-200 rounded-bl-sm md'}`}>
                {m.role === 'app' ? <ReactMarkdown>{m.text}</ReactMarkdown> : m.text}
              </div>
            </div>
          ))}
          {loading && <div className="text-xs text-gray-400">thinking…</div>}
          {error && <div className="text-xs text-red-600">Error: {error}</div>}
        </div>

        <div className="p-3 border-t border-gray-200">
          <div className="flex gap-2">
            <input
              className="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm disabled:bg-gray-100"
              placeholder={loading ? 'thinking…' : 'Type a message…'}
              value={text}
              disabled={loading}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
            />
            <button
              className="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium disabled:bg-gray-300"
              onClick={send} disabled={loading || !text.trim()}
            >Send</button>
          </div>
        </div>
      </div>

      {/* Right: results */}
      <div className="flex-1 flex flex-col overflow-hidden">
        <div className="border-b border-gray-200 flex items-center justify-between pr-3">
          <div className="flex">
            {(['Graph', 'Spec', 'Data'] as Tab[]).map((t) => (
              <button key={t} onClick={() => setTab(t)}
                className={`px-4 py-3 text-sm font-medium border-b-2 ${
                  tab === t ? 'border-blue-500 text-blue-600'
                            : 'border-transparent text-gray-600 hover:text-gray-900'}`}>
                {t}
              </button>
            ))}
          </div>
          {phase === 'built' && sessionId && (
            <div className="flex items-center gap-2">
              <button
                onClick={() => { generate(); setTab('Data'); }}
                disabled={generating}
                className="text-sm font-medium px-3 py-1.5 rounded-lg bg-emerald-600 text-white
                           hover:bg-emerald-700 disabled:bg-gray-300">
                {generating ? 'Generating…' : 'Generate sample'}
              </button>
              <a href={`/api/session/${sessionId}/spec.zip`} download
                 className="text-sm font-medium px-3 py-1.5 rounded-lg bg-blue-600 text-white
                            hover:bg-blue-700">
                Download spec
              </a>
            </div>
          )}
        </div>
        <div className="flex-1 overflow-hidden bg-white">
          {tab === 'Graph' && (graph.length
            ? <Graph elements={graph} />
            : <div className="h-full flex items-center justify-center text-gray-400 text-sm px-8 text-center">
                Tell me what you need on the left. Once we agree on a plan, the design graph appears here.
              </div>)}
          {tab === 'Spec' && (
            <pre className="h-full overflow-auto p-4 text-xs font-mono bg-gray-50">
              {yaml || '# The Cardinal spec appears here once we build it.'}
            </pre>)}
          {tab === 'Data' && (
            <div className="h-full overflow-auto p-4">
              {generating && <div className="text-sm text-gray-500">Generating a sample…</div>}
              {!generating && !sample && (
                <div className="h-full flex items-center justify-center text-gray-400 text-sm px-8 text-center">
                  Build a spec, then click <span className="font-medium mx-1">Generate sample</span> to preview data.
                </div>)}
              {sample && (
                <>
                  <div className="text-xs text-gray-500 mb-2">
                    Sample: {sample.n_accounts} accounts × {sample.n_cycles} cycles (demo economics).
                  </div>
                  <div className="flex flex-wrap gap-2 mb-4">
                    {Object.entries(sample.kpis).filter(([k]) => k !== 'account_cycles').map(([k, v]) => (
                      <div key={k} className="border border-gray-200 rounded-lg px-3 py-2 min-w-[120px]">
                        <div className="text-[11px] uppercase tracking-wide text-gray-500">{k.replace(/_/g, ' ')}</div>
                        <div className="text-lg font-semibold">{v}</div>
                      </div>
                    ))}
                  </div>
                  <div className="overflow-auto border border-gray-200 rounded-lg">
                    <table className="text-xs w-full">
                      <thead className="bg-gray-50 sticky top-0">
                        <tr>{sample.columns.map((c) => (
                          <th key={c} className="text-left px-2 py-1.5 font-medium text-gray-600 whitespace-nowrap">
                            {c.replace(/_/g, ' ')}</th>))}</tr>
                      </thead>
                      <tbody>
                        {sample.rows.map((row, i) => (
                          <tr key={i} className="border-t border-gray-100">
                            {sample.columns.map((c) => (
                              <td key={c} className="px-2 py-1 whitespace-nowrap">{String(row[c])}</td>))}
                          </tr>))}
                      </tbody>
                    </table>
                  </div>
                </>
              )}
            </div>)}
        </div>
      </div>
    </div>
  );
}
