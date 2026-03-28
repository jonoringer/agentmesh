# MemoryVolume Spec

`MemoryVolume` provides a portable abstraction for agent memory.

The core system should distinguish between memory semantics, not just storage backends.

## Memory classes

- conversation memory
- knowledge memory
- episodic memory
- shared team memory

## Draft shape

```yaml
apiVersion: agentmesh.dev/v1alpha1
kind: MemoryVolume
metadata:
  name: customer-history
spec:
  class: knowledge
  backend:
    type: postgres-pgvector
    connectionRef: customer-history-db
  retention:
    policy: rolling
    maxAgeDays: 90
  access:
    mode: readWrite
    shareScope: team
```

## Goals

- make memory lifecycle explicit
- allow runtime portability across storage providers
- support isolation and sharing policies at the platform layer
