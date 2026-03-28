# Workflow Spec

`Workflow` defines a multi-agent execution graph.

It should allow teams to coordinate multiple agents without hardcoding every handoff path inside agent prompts or application code.

## Responsibilities

- define DAG structure and execution order
- pass context between steps
- express retries, deadlines, and compensation paths
- support human approval gates where needed

## Draft shape

```yaml
apiVersion: agentmesh.dev/v1alpha1
kind: Workflow
metadata:
  name: incident-triage
spec:
  entrypoint: classify
  steps:
    - name: classify
      agentRef: triage-router
      onSuccess:
        - investigate
    - name: investigate
      agentRef: logs-specialist
      timeoutSeconds: 90
      retries: 2
      onSuccess:
        - summarize
    - name: summarize
      agentRef: incident-writer
      approval:
        required: true
```

## Runtime expectations

- each step emits trace spans
- step outputs are addressable and replayable
- failed branches can be retried from checkpoints
- shared workflow context is versioned
