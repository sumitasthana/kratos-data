"""Interviewer agent: talks to the human, then hands a Contract to the Builder.

Free conversation, no scripted questions and no boilerplate. It is domain-aware
(nudged to make sure it learns purpose, rough scale, and whether accounts revolve),
summarizes the plan, and only after the user confirms does it call the
submit_requirements tool. That tool call is the handoff: the graph runs the
Builder and returns the built spec.

Built on LangGraph. Claude via langchain (Bedrock in this project). If no model is
configured, OfflineInterviewer builds a sensible default so the pipeline still runs.
"""
from __future__ import annotations
from typing import Optional, TypedDict, Annotated

from langchain_core.tools import tool
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver

try:
    from .contract import Contract
    from .builder import Builder
except ImportError:
    from contract import Contract
    from builder import Builder


GREETING = (
    "Hi! I help you put together a synthetic credit-card dataset. Tell me what you're "
    "trying to do, in your own words, and we'll figure out the details together. "
    "There are no wrong answers, and I'll explain anything that needs it."
)

INTERVIEWER_SYSTEM = (
    "You are the interviewer for Cardinal Studio, which builds synthetic (fake but realistic) "
    "credit-card datasets. You are talking to someone who needs such data. Be concise, specific, "
    "and substantive. No filler and no cheerleading ('great project', 'you've come to the right "
    "place'), and never restate what the user just said.\n\n"
    "Read each message carefully and build directly on it. NEVER ask about something the user has "
    "already told you or clearly implied. If they have given their goal, acknowledge it specifically "
    "and move to the next genuinely useful unknown. Do not offer generic example menus.\n\n"
    "To build, you need the rough scale (how many accounts, how many months) and which credit-card "
    "behaviours the data must show to serve the goal (whether accounts revolve, interest/grace, fees, "
    "cash advances, minimum payments). The user's stated goal is sufficient context: do NOT "
    "interrogate them about why they need the data, and NEVER ask what it is 'for' as a "
    "multiple-choice menu (no 'training a model, a demo, or a pipeline?' style questions).\n\n"
    "Prefer proposing over asking. When the goal is clear, go straight to a concrete, sensible plan, "
    "a reasonable scale and the behaviours that fit the goal, say in one line why they fit, and ask "
    "the user to confirm or adjust. When the goal implies specific data, name the connection so they "
    "see you understand it (a KPI tree, say, needs metrics like delinquency, utilisation, revolve and "
    "charge-off rates, which depend on how accounts behave). Ask a question only when an important "
    "choice is genuinely missing and you cannot sensibly default it.\n\n"
    "Keep replies to roughly one to three sentences. When the user confirms the plan, call the "
    "submit_requirements tool. Never mention the tool, field names, or internal machinery."
)


@tool("submit_requirements", args_schema=Contract)
def submit_requirements(**kwargs) -> str:
    """Finalize the gathered requirements and build the dataset spec.
    Call this ONLY after the user has confirmed the summary."""
    return "submitted"  # never executed; the graph intercepts the call


class ChatState(TypedDict):
    messages: Annotated[list, add_messages]
    built: Optional[dict]
    contract: Optional[dict]


def _last_ai_text(messages) -> str:
    for m in reversed(messages):
        if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
            return m.content
    return ""


def _summary_text(contract: Contract, result: dict) -> str:
    n = len(result["fields"])
    mix = contract.revolver_mix.replace("_", " ")
    lines = [f"**Done.** I've drafted a spec with **{n} fields** for a {mix} portfolio."]
    if result["assumptions"]:
        lines += ["", "A few things I set up for you automatically:", ""]
        lines += [f"- {a}" for a in result["assumptions"]]
    v = result.get("validation", {})
    if v.get("ok"):
        lines += ["", f"It validates against the engine ({v['summary']})."]
    elif v:
        lines += ["", f"Note: it did not validate yet ({v['summary']})."]
    lines += ["", "The full spec is on the **Spec** tab and the design graph on the **Graph** "
              "tab. Use **Download spec** to get the runnable bundle. Tell me if you'd like to "
              "change anything."]
    return "\n".join(lines)


class Interviewer:
    def __init__(self, llm, builder: Builder, session_id: str):
        self.llm = llm
        self.builder = builder
        self.graph = self._build_graph()
        self.config = {"configurable": {"thread_id": session_id}}

    def _agent(self, state: ChatState) -> dict:
        model = self.llm.bind_tools([submit_requirements])
        resp = model.invoke([SystemMessage(content=INTERVIEWER_SYSTEM)] + state["messages"])
        return {"messages": [resp]}

    def _route(self, state: ChatState) -> str:
        last = state["messages"][-1]
        return "build" if getattr(last, "tool_calls", None) else END

    def _build_node(self, state: ChatState) -> dict:
        call = state["messages"][-1].tool_calls[0]
        contract = Contract(**call["args"])
        result = self.builder.build(contract)
        return {
            "messages": [ToolMessage(content="built", tool_call_id=call["id"]),
                         AIMessage(content=_summary_text(contract, result))],
            "built": result,
            "contract": contract.model_dump(),
        }

    def _build_graph(self):
        g = StateGraph(ChatState)
        g.add_node("agent", self._agent)
        g.add_node("build", self._build_node)
        g.add_edge(START, "agent")
        g.add_conditional_edges("agent", self._route, {"build": "build", END: END})
        g.add_edge("build", END)
        return g.compile(checkpointer=MemorySaver())

    def start(self) -> dict:
        return {"reply": GREETING, "phase": "interview", "done": False, "graph": [], "yaml": ""}

    def message(self, text: str) -> dict:
        state = self.graph.invoke({"messages": [HumanMessage(content=text)]}, self.config)
        reply = _last_ai_text(state["messages"])
        built = state.get("built")
        if built:
            return {"reply": reply, "phase": "built", "done": True,
                    "graph": built["graph"], "yaml": built["yaml"],
                    "assumptions": built["assumptions"], "contract": state.get("contract"),
                    "spec_files": built["spec_files"]}
        return {"reply": reply, "phase": "interview", "done": False, "graph": [], "yaml": ""}


class OfflineInterviewer:
    """No-model fallback: greet, then build a sensible default on the first reply."""
    def __init__(self, builder: Builder, session_id: str):
        self.builder = builder

    def start(self) -> dict:
        return {"reply": GREETING + "\n\n(Model offline: I'll build a standard portfolio from your first message.)",
                "phase": "interview", "done": False, "graph": [], "yaml": ""}

    def message(self, text: str) -> dict:
        contract = Contract(purpose=text, use_case="other", revolver_mix="mixed",
                            behaviors=["grace_period", "fees", "minimum_payment"])
        result = self.builder.build(contract)
        return {"reply": _summary_text(contract, result), "phase": "built", "done": True,
                "graph": result["graph"], "yaml": result["yaml"],
                "assumptions": result["assumptions"], "contract": contract.model_dump(),
                "spec_files": result["spec_files"]}


def make_interviewer(llm, builder: Builder, session_id: str):
    return Interviewer(llm, builder, session_id) if llm is not None \
        else OfflineInterviewer(builder, session_id)
