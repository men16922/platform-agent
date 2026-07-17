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

{{/* Recreate is only forced by the RWO JSONL volume; DSN-mode rolls normally. */}}
{{- define "platform-agent.strategy" -}}
{{- if .Values.persistence.enabled -}}
type: Recreate
{{- else -}}
type: RollingUpdate
{{- end -}}
{{- end -}}
