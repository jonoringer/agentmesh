# AgentPod Spec

`AgentPod` is the smallest deployable unit in AgentMesh.

It packages everything required to run one agent instance:

- model and inference settings
- system prompt and runtime instructions
- tool attachments
- memory bindings
- resource constraints
- health and retry policy

## Design goals

- make agent configuration portable
- isolate runtime concerns from business logic
- support deterministic rollout and restart behavior

## Draft shape

```yaml
apiVersion: agentmesh.dev/v1alpha1
kind: AgentPod
metadata:
  name: support-router
spec:
  runtime:
    framework: bare
    entrypoint: ./agents/support_router.py
  model:
    provider: openai
    name: gpt-5.4
    maxTokens: 4000
    temperature: 0.2
  prompt:
    systemRef: ./prompts/support-router.md
  tools:
    - ref: crm-api
    - ref: billing-db
  memory:
    - ref: customer-history
  resources:
    maxConcurrency: 8
    tokenBudgetPerMinute: 120000
  health:
    readinessProbe:
      type: tool
      toolRef: crm-api
```

## Status model

An `AgentPod` should expose status fields for:

- phase
- ready condition
- currently attached tools and memory
- current runtime target
- last model error
- observed token rate
