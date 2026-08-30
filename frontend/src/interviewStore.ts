import { create } from 'zustand';
import { startSession, sendMessage, generateSample, type GraphEl, type Sample } from './api';

export interface Msg { role: 'app' | 'you'; text: string }

interface SessionState {
  sessionId: string | null;
  messages: Msg[];
  graph: GraphEl[];
  yaml: string;
  phase: 'interview' | 'built';
  llmEnabled: boolean;
  loading: boolean;
  error: string | null;
  sample: Sample | null;
  generating: boolean;
  begin: () => Promise<void>;
  respond: (text: string) => Promise<void>;
  generate: () => Promise<void>;
}

export const useInterview = create<SessionState>((set, get) => ({
  sessionId: null,
  messages: [],
  graph: [],
  yaml: '',
  phase: 'interview',
  llmEnabled: false,
  loading: false,
  error: null,
  sample: null,
  generating: false,

  begin: async () => {
    if (get().loading || get().sessionId) return;
    set({ loading: true, error: null });
    try {
      const r = await startSession();
      set({
        sessionId: r.session_id,
        llmEnabled: !!r.llm_enabled,
        phase: r.phase,
        messages: r.reply ? [{ role: 'app', text: r.reply }] : [],
        loading: false,
      });
    } catch (e: any) {
      set({ loading: false, error: String(e?.message ?? e) });
    }
  },

  respond: async (text: string) => {
    const { sessionId, loading } = get();
    if (!sessionId || loading || !text.trim()) return;
    set((s) => ({ messages: [...s.messages, { role: 'you', text }], loading: true, error: null }));
    try {
      const r = await sendMessage(sessionId, text);
      set((s) => ({
        messages: [...s.messages, { role: 'app', text: r.reply }],
        graph: r.graph.length ? r.graph : s.graph,
        yaml: r.yaml || s.yaml,
        phase: r.phase,
        loading: false,
      }));
    } catch (e: any) {
      set({ loading: false, error: String(e?.message ?? e) });
    }
  },

  generate: async () => {
    const { sessionId, generating } = get();
    if (!sessionId || generating) return;
    set({ generating: true, error: null });
    try {
      const sample = await generateSample(sessionId);
      set({ sample, generating: false });
    } catch (e: any) {
      set({ generating: false, error: String(e?.message ?? e) });
    }
  },
}));
