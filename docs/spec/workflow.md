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

## Local alpha behavior

- `entrypoint` selects the first step to execute
- `onSuccess` declares explicit successor steps for DAG-style fan-out
- if `onSuccess` is omitted, the local runtime falls back to the next listed step for backwards compatibility
- workflows fail validation when they reference unknown steps, contain unreachable steps, or introduce cycles
- workflow admission also validates that every `agentRef` points to an applied `AgentPod`
- reruns can restart from a checkpoint step with `rerun workflow-run <run-id> --from-step <name>`
