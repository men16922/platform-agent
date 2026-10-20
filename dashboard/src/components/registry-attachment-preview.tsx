'use client';

import { useEffect, useRef, useState, type FormEvent } from 'react';
import { decodeAttachmentStatus, decodePreparation, type AttachmentStatus,
  type AttachmentPreview, type AttachmentRequest } from '@/lib/registry-preview-contract';

const INITIAL: AttachmentRequest = {tenant:'', env:'', capability:'', version:''};
const MESSAGES: Record<string,string> = {
  session_required: 'Sign in to preview an add-on attachment.',
  registry_write_forbidden: 'You need explicit write access to this tenant.',
  planner_not_configured: 'Preview is not connected. Ask the operator to configure the planner.',
  planner_invoke_failed: 'The planner could not complete the request. Try again shortly.',
  planner_unavailable: 'The planner is unavailable. Try again shortly.',
  user_store_unavailable: 'Current permissions could not be checked. Try again shortly.',
  snapshot_unavailable: 'The registry could not be read. Try again shortly.',
  already_attached: 'This add-on is already attached. A version upgrade needs a separate review.',
  invalid_registry: 'The registry does not support this attachment. Check the environment, capability and version.',
  invalid_request: 'Check the tenant, environment, capability and version.',
  plan_expired: 'This preview has expired. Create a new preview.',
  stored_plan_not_found: 'This request is unavailable for your account.',
  plan_store_unavailable: 'The request store is unavailable. Keep your request ID and check its status later.',
  invalid_stored_plan: 'This request could not be verified. Keep its ID for the operator.',
  plan_changed_during_read: 'The request changed while being checked. Check its status again.',
};

export function RegistryAttachmentPreview({preparationEnabled = false}: {preparationEnabled?: boolean}) {
  const [input,setInput] = useState(INITIAL);
  const [plan,setPlan] = useState<AttachmentPreview | null>(null);
  const [pending,setPending] = useState(false);
  const [error,setError] = useState('');
  const [now,setNow] = useState(0);
  const active = useRef<AbortController | null>(null);
  const attempted = useRef(new Set<string>());
  const [requestId,setRequestId] = useState('');
  const [observation,setObservation] = useState<AttachmentStatus | null>(null);
  const [preparation,setPreparation] = useState<{id:string; state:'unknown'|'claimed'} | null>(null);
  useEffect(() => () => active.current?.abort(), []);
  useEffect(() => {
    if (!plan) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()),1000);
    return () => clearInterval(timer);
  },[plan]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setPending(true); setPlan(null); setError('');
    try {
      const response = await fetch('/api/dashboard/platform/attach/preview', {
        method:'POST', credentials:'same-origin', signal:controller.signal,
        headers:{'Content-Type':'application/json','X-Registry-Preview':'1'},
        body:JSON.stringify(input),
      });
      const body = await response.json();
      if (controller.signal.aborted || active.current !== controller) return;
      if (!response.ok || body.ok !== true) {
        setError(MESSAGES[body.error] || 'The preview could not be created. Check your request and try again.');
      } else {
        setNow(Date.now()); setPlan(body.plan); setRequestId(body.plan.request_id);
        setObservation(null); setPreparation(null);
      }
    } catch {
      if (!controller.signal.aborted) setError('Could not reach the preview service. Try again shortly.');
    } finally { if (!controller.signal.aborted) setPending(false); }
  }
  async function inspectOrPrepare(operation: 'status'|'prepare') {
    const id = operation === 'prepare' ? plan?.request_id : requestId;
    if (pending || !id || !/^[A-Za-z0-9_-]{1,128}$/.test(id)) return;
    if (operation === 'prepare') {
      if (!plan || Date.now() >= Date.parse(plan.expires_at) || attempted.current.has(id)
          || (observation?.request_id === id && observation.state === 'CLAIMED')) return;
      // Once sent, an uncertain preparation is reconciled by status only.
      attempted.current.add(id); setPreparation({id,state:'unknown'});
    }
    active.current?.abort();
    const controller = new AbortController(); active.current = controller;
    setPending(true); setError(''); setObservation(null);
    try {
      const response = await fetch(`/api/dashboard/platform/attach/${operation}`, {
        method:'POST', credentials:'same-origin', signal:controller.signal,
        headers:{'Content-Type':'application/json','X-Registry-Preview':'1'},
        body:JSON.stringify({request_id:id}),
      });
      const body = await response.json();
      if (controller.signal.aborted || active.current !== controller) return;
      const output = JSON.stringify({...body,status:response.status});
      if (operation === 'status') {
        const result = decodeAttachmentStatus(output,id);
        setObservation(result);
        if (result.state === 'CLAIMED') setPreparation({id,state:'claimed'});
      } else {
        decodePreparation(output,id); setPreparation({id,state:'claimed'}); setRequestId(id);
      }
    } catch (error) {
      if (!controller.signal.aborted && active.current === controller) {
        const code = error && typeof error === 'object' && 'code' in error ? String(error.code) : '';
        setError(operation === 'prepare'
          ? 'Preparation could not be confirmed. Check this request’s status before taking another action.'
          : MESSAGES[code] || 'Status could not be verified. Keep this request ID and check again later.');
      }
    } finally { if (!controller.signal.aborted && active.current === controller) setPending(false); }
  }
  const expired = plan && now >= Date.parse(plan.expires_at);
  return (
    <section className="surface space-y-4 p-5" aria-labelledby="attachment-title">
      <div>
        <h3 id="attachment-title" className="text-base font-semibold">Preview add-on attachment</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">Review one tenant environment’s registry change. Requires explicit tenant write access.</p>
      </div>
      <form onSubmit={submit}>
        <fieldset disabled={pending} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {(['tenant','env','capability','version'] as const).map((key,index) => (
            <label key={key} className="space-y-1 text-xs text-[var(--muted)]">
              <span>{['Tenant','Environment','Capability','Chart version'][index]}</span>
              <input required name={key} value={input[key]} maxLength={key === 'version' ? 128 : 63}
                placeholder={['acme','prod','logging','7.1.0'][index]} autoComplete="off"
                onChange={event => {setInput({...input,[key]:event.target.value}); setPlan(null); setError('');}}
                className="w-full rounded-md border border-white/15 bg-black/20 px-3 py-2 text-sm text-[#e6edf7] focus:border-[#79b8ff] focus:outline-none" />
            </label>
          ))}
          <button type="submit" className="rounded-md bg-[#a9c7ff] px-4 py-2 text-sm font-semibold text-[#142238] disabled:opacity-50 sm:col-span-2 lg:col-span-1">
            {pending ? 'Creating preview…' : 'Create preview'}
          </button>
        </fieldset>
      </form>
      <p className="text-xs text-[var(--muted)]">Preview only · applying changes requires a reviewed pull request.</p>
      {error && <p role="alert" className="text-sm text-[#ffb4a9]">{error}</p>}
      {plan && <div className="space-y-3" aria-live="polite">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className={`rounded border px-2 py-1 ${expired ? 'border-[#ffb4a9] text-[#ffb4a9]' : 'border-[#79d9ae] text-[#79d9ae]'}`}>
            {expired ? 'Expired · create a new preview' : 'Preview ready'}
          </span>
          <span className="text-[var(--muted)]">Expires {new Date(plan.expires_at).toLocaleTimeString()}</span>
        </div>
        <p className="break-all text-xs text-[var(--muted)]">Base revision <code className="text-[#cbd6e9]">{plan.base_commit}</code></p>
        <p className="break-all text-xs font-medium">{plan.path}</p>
        <pre className="max-h-96 overflow-auto rounded-md border border-white/10 bg-black/25 p-3 text-xs leading-6 text-[#b4e7cb]">{plan.diff}</pre>
        {preparationEnabled && <button type="button" onClick={() => void inspectOrPrepare('prepare')}
          disabled={pending || !!expired || attempted.current.has(plan.request_id)
            || (observation?.request_id === plan.request_id && observation.state === 'CLAIMED')}
          className="rounded-md bg-[#a9c7ff] px-4 py-2 text-sm font-semibold text-[#142238] disabled:opacity-50">
          Prepare reviewed change
        </button>}
      </div>}
      {preparationEnabled && <div className="space-y-3 border-t border-white/10 pt-4">
        <p className="text-xs text-[var(--muted)]">Preparing reserves the reviewed change. Publication requires a separate step.</p>
        <form onSubmit={event => {event.preventDefault(); void inspectOrPrepare('status');}} className="flex flex-wrap items-end gap-2">
          <label className="min-w-0 flex-1 space-y-1 text-xs text-[var(--muted)]">
            <span>Request ID</span>
            <input value={requestId} maxLength={128} disabled={pending} autoComplete="off"
              onChange={event => {setRequestId(event.target.value); setObservation(null); setError('');}}
              className="w-full rounded-md border border-white/15 bg-black/20 px-3 py-2 text-sm text-[#e6edf7]"
              placeholder="Enter an existing request ID" />
          </label>
          <button type="submit" disabled={pending || !/^[A-Za-z0-9_-]{1,128}$/.test(requestId)}
            className="rounded-md border border-white/20 px-4 py-2 text-sm disabled:opacity-50">Check request status</button>
        </form>
        <div aria-live="polite" className="text-sm">
          {preparation?.id === requestId && <p>{preparation.state === 'claimed'
            ? 'Prepared · not published.' : 'Preparation outcome unknown. Check this request’s status.'}</p>}
          {observation && <p>{observation.state === 'CLAIMED'
            ? 'The request is prepared and retained. Publication is not verified.'
            : observation.expired ? 'This preview has expired.' : 'This request is still a preview.'}</p>}
        </div>
      </div>}
    </section>
  );
}
