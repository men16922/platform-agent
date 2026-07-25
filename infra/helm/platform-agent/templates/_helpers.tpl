{{- define "platform-agent.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "platform-agent.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "platform-agent.labels" -}}
app.kubernetes.io/name: {{ include "platform-agent.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* Shared JSONL-store env, mounted from the chart PVC. */}}
{{- define "platform-agent.storeEnv" -}}
- name: PLATFORM_ACTIVITY_FILE
  value: {{ printf "%s/activity.jsonl" .Values.persistence.mountPath | quote }}
- name: PLATFORM_APPROVALS_FILE
  value: {{ printf "%s/pending-approvals.jsonl" .Values.persistence.mountPath | quote }}
- name: PLATFORM_INCIDENT_FILE
  value: {{ printf "%s/incidents.jsonl" .Values.persistence.mountPath | quote }}
{{- end -}}

{{/* Opt-in SQL State Store env (roadmap ④). Secret ref wins over the plain DSN. */}}
{{- define "platform-agent.stateStoreEnv" -}}
{{- if .Values.stateStore.existingSecret }}
- name: PLATFORM_STATE_DSN
  valueFrom:
    secretKeyRef:
      name: {{ .Values.stateStore.existingSecret }}
      key: {{ .Values.stateStore.secretKey }}
{{- else if .Values.stateStore.dsn }}
- name: PLATFORM_STATE_DSN
  value: {{ .Values.stateStore.dsn | quote }}
{{- end }}
{{- end -}}

{{/*
Image reference. `image.digest` wins over `image.tag` when set.

A tag is a mutable pointer; a cosign signature covers a DIGEST. Verified live:
re-pointing a tag at a different image makes `cosign verify` fail with "no
signatures found", and two tags on one digest both verify. So verifying a tag
and then deploying that tag leaves a window where they are no longer the same
bytes. Pin the digest and the thing you verified is the thing that runs.
*/}}
{{- define "platform-agent.image" -}}
{{- if .Values.image.digest -}}
{{ .Values.image.repository }}@{{ .Values.image.digest }}
{{- else -}}
{{ .Values.image.repository }}:{{ .Values.image.tag }}
{{- end -}}
{{- end -}}

{{/*
Pod Security Standards `restricted` — the pod half.

Kept as helpers rather than inlined so every workload this chart ships (webhook,
router, sweeper CronJob) is provably identical. A single uncovered pod is enough
to make a namespace-level `enforce: restricted` label reject the release at the
worst possible moment, i.e. the next rollout rather than the change that broke it.

fsGroup matches the image's UID/GID so the JSONL PVC stays writable by a
non-root process. Drop the image's USER and this silently breaks instead.
*/}}
{{- define "platform-agent.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .Values.securityContext.runAsUser }}
runAsGroup: {{ .Values.securityContext.runAsGroup }}
fsGroup: {{ .Values.securityContext.fsGroup }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/* PSS `restricted` — the container half. */}}
{{- define "platform-agent.containerSecurityContext" -}}
allowPrivilegeEscalation: false
capabilities:
  drop:
    - ALL
{{- end -}}

{{/* Recreate is only forced by the RWO JSONL volume; DSN-mode rolls normally. */}}
{{- define "platform-agent.strategy" -}}
{{- if .Values.persistence.enabled -}}
type: Recreate
{{- else -}}
type: RollingUpdate
{{- end -}}
{{- end -}}
