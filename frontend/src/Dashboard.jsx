import React, {useEffect, useState} from 'react';
import {Users, PhoneCall, Clock3, Headphones, RefreshCw, Phone} from 'lucide-react';

const metrics = [
  ['totalLeads', 'Total leads', 'People saved in the lead queue', Users, 'blue'],
  ['aiCallsDone', 'AI calls done', 'Finished AI sessions, including handoffs', PhoneCall, 'green'],
  ['remainingToCall', 'People remaining to call', 'Callable leads with no call started', Clock3, 'amber'],
  ['humanHandoffs', 'Human handoffs', 'Handovers accepted by a human', Headphones, 'purple'],
];
const handoffLabels = {not_requested: 'Not requested', awaiting_acceptance: 'Pending', accepted: 'Accepted', unavailable: 'Unavailable', cancelled: 'Cancelled'};
const callLabels = {consent: 'In progress', collecting: 'In progress', confirming: 'In progress', review: 'In progress', handoff_pending: 'Awaiting human', completed: 'Completed', declined: 'Declined', suppressed: 'Do not call', human: 'Handed off', callback: 'Callback', ended: 'Ended'};

export default function Dashboard({token, sessionId, revision, onCallLead, busy}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [refresh, setRefresh] = useState(0);

  useEffect(() => { setData(null); setError(''); }, [token]);

  useEffect(() => {
    let active = true;
    let controller;
    let timer;
    async function load() {
      controller = new AbortController();
      setLoading(true);
      try {
        const response = await fetch('/api/dashboard', {
          headers: {Authorization: `Bearer ${token}`}, signal: controller.signal,
        });
        if (!response.ok) throw new Error(response.status === 401 ? 'Check your API token.' : 'Please try again.');
        const result = await response.json();
        if (active) { setData(result); setError(''); }
      } catch (err) {
        if (active) setError(`Dashboard could not be updated. ${err.message}`);
      } finally {
        if (active) { setLoading(false); timer = setTimeout(load, 15000); }
      }
    }
    load();
    return () => { active = false; controller?.abort(); clearTimeout(timer); };
  }, [token, sessionId, revision, refresh]);

  return <section className="dashboard" aria-label="Lead and call overview">
    <div className="dashboard-heading">
      <p>{error ? (data ? 'Last available totals' : 'Totals unavailable') : 'Lead queue · All time · Updates automatically'}</p>
      <button onClick={() => setRefresh(value => value + 1)} disabled={loading} aria-label="Refresh dashboard">
        <RefreshCw size={15}/>{loading ? 'Updating…' : 'Refresh'}
      </button>
    </div>
    <dl className="metric-grid" aria-busy={loading}>
      {metrics.map(([key, label, description, Icon, color]) => <div className={`metric-card ${color}`} key={key}>
        <dt><span>{label}</span><span className="metric-icon"><Icon size={20} aria-hidden="true"/></span></dt>
        <dd>{data ? data[key].toLocaleString() : '—'}</dd>
        <p>{description}</p>
      </div>)}
    </dl>
    {error && <p className="dashboard-error" role="status">{error}</p>}
    <section className="panel lead-panel" aria-labelledby="lead-queue-title">
      <div className="panel-heading"><div><h2 id="lead-queue-title">Lead queue</h2><p>Call history and handoff outcomes for your saved leads.</p></div><span className="badge">{data ? `${data.leads.length} leads` : 'Loading…'}</span></div>
      <div className="lead-table-scroll"><table className="lead-table">
        <thead><tr><th scope="col">Lead</th><th scope="col">AI call</th><th scope="col">Human handoff</th><th scope="col">Latest call</th><th scope="col"><span className="sr-only">Action</span></th></tr></thead>
        <tbody>{data?.leads.map(lead => <tr key={lead.id}>
          <th scope="row"><span className="lead-person">{lead.name}</span><span className="lead-detail">{lead.phone || 'No phone saved'}</span></th>
          <td><span className={`lead-status ${lead.aiCallDone ? 'done' : lead.aiCalled ? 'pending' : ''}`}>{lead.aiCallDone ? 'Done' : lead.aiCalled ? 'Started' : 'Not called'}</span><span className="lead-detail">{lead.callsDone} done · {lead.callsStarted} started</span></td>
          <td><span className={`lead-status ${lead.humanHandoffDone ? 'done' : lead.latestHandoffStatus === 'awaiting_acceptance' ? 'pending' : ''}`}>{lead.humanHandoffDone ? 'Done' : handoffLabels[lead.latestHandoffStatus] || lead.latestHandoffStatus}</span><span className="lead-detail">{lead.handoffsDone} accepted · {lead.handoffsRequested} requested</span></td>
          <td><span>{callLabels[lead.latestCallState] || lead.latestCallState || 'Not started'}</span>{lead.aiCalled && <span className="lead-detail">Handoff: {handoffLabels[lead.latestHandoffStatus] || lead.latestHandoffStatus}</span>}</td>
          <td><button disabled={busy || !!error || lead.suppressed} onClick={() => onCallLead(lead)} aria-label={`Call ${lead.name}`}><Phone size={15}/>{lead.suppressed ? 'Do not call' : 'Call'}</button></td>
        </tr>)}</tbody>
      </table></div>
      {!data && <p className="lead-empty" role="status">{error ? 'Lead data is unavailable. Refresh to try again.' : 'Loading saved leads…'}</p>}
      {data?.leads.length === 0 && <p className="lead-empty">No leads in the queue yet.</p>}
    </section>
  </section>;
}
