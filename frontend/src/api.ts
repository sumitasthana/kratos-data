// Client for the Cardinal two-agent session backend. Vite proxies /api -> :8000.

export interface GraphEl {
  data: { id: string; label?: string; kind?: string; priority?: string;
          source?: string; target?: string; lag?: number; mechanism?: string };
}

export interface SessionTurn {
  session_id: string;
  reply: string;
  phase: 'interview' | 'built';
  done: boolean;
  graph: GraphEl[];
  yaml: string;
  assumptions?: string[];
  llm_enabled?: boolean;
}

async function post(path: string, body?: unknown): Promise<SessionTurn> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`${path} failed: ${res.status}`);
  return res.json();
}

export const startSession = () => post('/api/session/start');
export const sendMessage = (session_id: string, text: string) =>
  post('/api/session/message', { session_id, text });

export interface Sample {
  kpis: Record<string, number>;
  columns: string[];
  rows: Record<string, any>[];
  n_accounts: number;
  n_cycles: number;
}
export async function generateSample(session_id: string): Promise<Sample> {
  const res = await fetch(`/api/session/${session_id}/generate`, { method: 'POST' });
  if (!res.ok) throw new Error(`generate failed: ${res.status}`);
  return res.json();
}
