{{/*
Expand the name of the chart.
*/}}
{{- define "clubcore.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "clubcore.fullname" -}}
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
{{- define "clubcore.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to all resources in this chart.
*/}}
{{- define "clubcore.labels" -}}
helm.sh/chart: {{ include "clubcore.chart" . }}
{{ include "clubcore.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — used for pod selectors and service selectors.
*/}}
{{- define "clubcore.selectorLabels" -}}
app.kubernetes.io/name: {{ include "clubcore.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use.
*/}}
{{- define "clubcore.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "clubcore.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
StorageClass name — used by Postgres PVC, Redis PVC, SeaweedFS PVCs.
Encodes the DATA-04 / P1 invariant: always use the Retain StorageClass.
*/}}
{{- define "clubcore.storageClassName" -}}
{{- .Values.storageClass.name | default "clubcore-retain" }}
{{- end }}

{{/*
Fully-qualified image reference for the shared backend image.
WR-02: image.tag is intentionally empty in values.yaml — it MUST be supplied at
deploy time (e.g. --set image.tag=$(git rev-parse --short HEAD)). The `required`
guard makes `helm install`/`helm template` fail loudly with a clear message when
the tag is missing, rather than silently rendering a stale or empty tag and then
pulling/failing on a non-existent image.
*/}}
{{- define "clubcore.image" -}}
{{- $tag := .Values.image.tag | required "image.tag is required — pass --set image.tag=<git-short-sha> (see infra/scripts/build-images.sh / deploy-local.sh)" -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end }}
