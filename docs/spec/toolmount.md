# ToolMount Spec

`ToolMount` standardizes how external capabilities attach to agent workloads.

The same agent code should be able to run against different implementations of a tool contract without changing application logic.

## Supported classes

- HTTP APIs
- MCP servers
- databases
- queues
- file systems
- secrets-backed credentials

## Draft shape

```yaml
apiVersion: agentmesh.dev/v1alpha1
kind: ToolMount
metadata:
  name: crm-api
spec:
  type: http
  endpoint: https://api.example.com
  auth:
    secretRef: crm-api-token
  contract:
    schemaRef: ./schemas/crm.json
  limits:
    ratePerMinute: 600
```

## Goals

- stable runtime attachment model
- environment-specific configuration without code changes
- observability hooks around every invocation
