{{/*
Expand the name of the chart.
*/}}
{{- define "juris-ai-helper.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "juris-ai-helper.backend.name" -}}
{{- printf "backend" }}
{{- end }}

{{- define "juris-ai-helper.frontend.name" -}}
{{- printf "frontend" }}
{{- end }}

{{- define "juris-ai-helper.ollama.name" -}}
{{- printf "ollama" }}
{{- end }}

{{- define "juris-ai-helper.openwebui.name" -}}
{{- printf "openwebui" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "juris-ai-helper.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "juris-ai-helper.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "juris-ai-helper.labels" -}}
helm.sh/chart: {{ include "juris-ai-helper.chart" . }}
{{ include "juris-ai-helper.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
    Backend
*/}}
{{- define "juris-ai-helper.backend.labels" -}}
helm.sh/chart: {{ include "juris-ai-helper.chart" . }}
{{ include "juris-ai-helper.backend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
    Frontend
*/}}
{{- define "juris-ai-helper.frontend.labels" -}}
helm.sh/chart: {{ include "juris-ai-helper.chart" . }}
{{ include "juris-ai-helper.frontend.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
    Ollama
*/}}
{{- define "juris-ai-helper.ollama.labels" -}}
helm.sh/chart: {{ include "juris-ai-helper.chart" . }}
{{ include "juris-ai-helper.ollama.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
    Openweb-ui
*/}}
{{- define "juris-ai-helper.openwebui.labels" -}}
helm.sh/chart: {{ include "juris-ai-helper.chart" . }}
{{ include "juris-ai-helper.openwebui.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "juris-ai-helper.selectorLabels" -}}
app.kubernetes.io/name: {{ include "juris-ai-helper.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "juris-ai-helper.backend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "juris-ai-helper.backend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "juris-ai-helper.frontend.selectorLabels" -}}
app.kubernetes.io/name: {{ include "juris-ai-helper.frontend.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "juris-ai-helper.ollama.selectorLabels" -}}
app.kubernetes.io/name: {{ include "juris-ai-helper.ollama.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "juris-ai-helper.openwebui.selectorLabels" -}}
app.kubernetes.io/name: {{ include "juris-ai-helper.openwebui.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "juris-ai-helper.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "juris-ai-helper.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
