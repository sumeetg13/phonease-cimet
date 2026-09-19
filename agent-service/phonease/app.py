"""Internal LangGraph decision service; no durable state or public credentials."""
import os
import secrets
from typing import Any, Literal, TypedDict
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from .core import Store, Supervisor, TERMINAL
from .model import OpenAIExtractor
from .script_registry import SCRIPTS
from .telephony import Twilio
from .speech import synthesize

app = FastAPI(title='Phonease agent service', docs_url=None, redoc_url=None)

def authorize(authorization: str = Header(default='')):
    token = os.environ.get('AGENT_SERVICE_TOKEN', '')
    if not token or not secrets.compare_digest(authorization, 'Bearer '+token):
        raise HTTPException(401, 'Invalid service credentials')

class Decision(BaseModel):
    operation: Literal['start', 'turn', 'accept', 'unavailable', 'close', 'end']
    session: dict[str, Any] | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    suppressed: bool = False
    receipt: dict[str, Any] | None = None

class GraphState(TypedDict, total=False):
    request: Decision
    supervisor: Supervisor
    session: dict

def hydrate(state):
    request = state['request']
    store = Store()
    lead = request.session['lead_id'] if request.session else request.payload.get('lead_id')
    if request.session: store.save(request.session)
    if request.suppressed: store.suppress(lead)
    if request.receipt: store.receipts[lead] = request.receipt
    model = OpenAIExtractor() if os.getenv('OPENAI_API_KEY') else None
    return {'supervisor': Supervisor(store, model)}

def execute(state):
    r, supervisor = state['request'], state['supervisor']
    p = r.payload
    if r.operation == 'start':
        session = supervisor.start(p.get('lead_id'), p.get('seed'))
    else:
        if not r.session: raise ValueError('Session required')
        sid = r.session['id']
        if r.operation == 'turn':
            session = supervisor.turn(sid, p['text'], p['event_id'], p.get('confidence'), p.get('revision'))
        elif r.operation == 'accept':
            session = supervisor.accept(sid, p.get('agent', 'browser-demo-human'))
        elif r.operation == 'unavailable':
            session = supervisor.unavailable(sid)
        elif r.operation == 'end':
            session = supervisor.store.get(sid)
            if session['state'] not in TERMINAL:
                if (session.get('handoff') or {}).get('status') == 'awaiting_acceptance':
                    session['handoff']['status'] = 'cancelled'
                session['revision'] += 1
                supervisor.close(session, 'ended', 'Call ended by the operator.', 'Operator ended the call. Nothing was submitted.')
        else:
            session = supervisor.store.get(sid)
            supervisor.close(session, 'suppressed', SCRIPTS['messages']['suppressed'])
    return {'session': session}

builder = StateGraph(GraphState)
builder.add_node('hydrate_context', hydrate)
builder.add_node('supervisor_policy', execute)
builder.add_edge(START, 'hydrate_context')
builder.add_edge('hydrate_context', 'supervisor_policy')
builder.add_edge('supervisor_policy', END)
graph = builder.compile()

@app.get('/health')
def health(): return {'status': 'ok'}

@app.get('/scripts', dependencies=[Depends(authorize)])
def scripts(): return SCRIPTS

@app.post('/decide', dependencies=[Depends(authorize)])
def decide(request: Decision):
    try:
        return graph.invoke({'request': request})['session']
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(400, str(exc)) from None

class RenderRequest(BaseModel):
    session: dict[str, Any]
    whisper: bool = False

@app.post('/twiml', dependencies=[Depends(authorize)])
def twiml(request: RenderRequest):
    adapter = Twilio()
    return {'xml': adapter.whisper(request.session) if request.whisper else adapter.response(request.session)}

class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4096)

@app.post('/speech', dependencies=[Depends(authorize)])
def speech(request: SpeechRequest):
    if not request.text.strip(): raise HTTPException(400, 'Speech text is empty')
    return Response(synthesize(request.text), media_type='audio/mpeg', headers={'Cache-Control':'no-store'})
