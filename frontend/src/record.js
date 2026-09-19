/* The call record the operator keeps: live notes, and the receipt shown once the call ends.
   Formatting only — the agent service writes the notes, transcript and receipt. */
export const NOTE_LABELS = {call:'Call', consent:'Consent', detail:'Detail',
  concern:'Raised', escalation:'Handover', outcome:'Outcome'};

export function clock(at, base) {
  // A call clock, not a wall clock: seconds since the first line of this call.
  const seconds = Math.max(0, Math.round((at || 0) - (base || 0)));
  return String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0');
}

export function started(summary) {
  const times = [...(summary?.transcript || []), ...(summary?.notes || [])].map(item => item.at).filter(Boolean);
  return times.length ? Math.min(...times) : 0;
}

export function receiptText(summary) {
  if (!summary) return '';
  const base = started(summary), out = [];
  const receipt = summary.receipt;
  out.push('Phonease call record — synthetic demo');
  out.push('Session: ' + summary.session_id);
  out.push('Lead: ' + summary.lead_id);
  out.push('Outcome: ' + String(summary.outcome || '').replaceAll('_', ' '));
  if (summary.handoff_reason) out.push('Handover reason: ' + summary.handoff_reason.replaceAll('_', ' '));
  out.push('Script: ' + (summary.script_version || 'unknown'));
  out.push('Consent: ' + (summary.consent ? 'given' : 'not given'));
  out.push(receipt
    ? 'Submitted for further processing: receipt ' + receipt.id + ' (' + receipt.adapter + ')'
    : 'Not submitted: no receipt was issued.');
  const fields = summary.fields || [];
  out.push('', fields.length ? 'DETAILS' : 'DETAILS: none confirmed.');
  fields.forEach(field => out.push('- ' + field.label + ': ' + field.value));
  out.push('', (summary.notes || []).length ? 'CALL NOTES' : 'CALL NOTES: none.');
  (summary.notes || []).forEach(note =>
    out.push('[' + clock(note.at, base) + '] ' + (NOTE_LABELS[note.kind] || note.kind) + ': ' + note.text));
  out.push('', (summary.transcript || []).length ? 'TRANSCRIPT' : 'TRANSCRIPT: nothing was stored.');
  (summary.transcript || []).forEach(line =>
    out.push('[' + clock(line.at, base) + '] ' + (line.role === 'caller' ? 'Caller' : 'Assistant') + ': ' + line.text));
  out.push('', 'AI-generated conversation. Caller audio is not recorded; only the text above is kept.');
  return out.join('\n');
}

export function filename(summary) {
  return 'phonease-call-' + String(summary?.session_id || 'session').slice(0, 12) + '.txt';
}
