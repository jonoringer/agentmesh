# AgentSet Spec

`AgentSet` manages a fleet of equivalent `AgentPod` replicas.

It exists to separate agent definition from scale policy.

## Responsibilities

- maintain desired replica count
- autoscale based on queue depth, latency, or token pressure
- roll out updates safely
- replace unhealthy replicas

## Draft shape

```yaml
apiVersion: agentmesh.dev/v1alpha1
kind: AgentSet
metadata:
  name: support-router
spec:
  selector:
    matchLabels:
      app: support-router
  template:
    ref: support-router-pod
  replicas:
    min: 2
    max: 20
  autoscaling:
    metrics:
      - type: queueDepth
        targetAverage: 25
      - type: p95LatencyMs
        targetAverage: 1800
  rollout:
    strategy: rolling
    maxUnavailable: 1
```

## Open questions

- Should `AgentSet` own the pod template inline or always reference an `AgentPod`?
- How much scaling logic belongs in the core versus pluggable policy modules?
- Should token budget be a first-class autoscaling signal from v1alpha1?
