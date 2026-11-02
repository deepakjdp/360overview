#!/usr/bin/env bash
# Adds readiness + liveness probes to every Deployment that lacks them, so a hung
# (running but not responding) pod is detected by OpenShift and by the alerts.
#
# Usage:   ./03-add-probes.sh <namespace> [health-path] [port]
# Example: ./03-add-probes.sh shop /actuator/health 8080
# Dry run: DRY_RUN=1 ./03-add-probes.sh shop
#
# Assumes every service exposes an HTTP health endpoint. Review per-service ports/paths;
# services with different ports should be patched individually.
set -euo pipefail

NS="${1:?namespace required}"
HPATH="${2:-/health}"
PORT="${3:-8080}"

for d in $(oc -n "$NS" get deploy -o name); do
  has_ready=$(oc -n "$NS" get "$d" -o jsonpath='{.spec.template.spec.containers[0].readinessProbe}')
  if [[ -n "$has_ready" ]]; then
    echo "skip   $d (readinessProbe already set)"
    continue
  fi
  patch=$(cat <<EOF
[
 {"op":"add","path":"/spec/template/spec/containers/0/readinessProbe",
  "value":{"httpGet":{"path":"$HPATH","port":$PORT},"initialDelaySeconds":10,"periodSeconds":10,"timeoutSeconds":2,"failureThreshold":3}},
 {"op":"add","path":"/spec/template/spec/containers/0/livenessProbe",
  "value":{"httpGet":{"path":"$HPATH","port":$PORT},"initialDelaySeconds":30,"periodSeconds":20,"timeoutSeconds":2,"failureThreshold":3}}
]
EOF
)
  if [[ "${DRY_RUN:-0}" == "1" ]]; then
    echo "dryrun $d"
  else
    oc -n "$NS" patch "$d" --type=json -p "$patch"
    echo "patched $d"
  fi
done
