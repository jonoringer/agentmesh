# Customer Support Stack

This example shows the shape of a practical AgentMesh deployment for a support organization.

## Agents

- `support-router`: classifies inbound tickets
- `account-researcher`: fetches account and billing context
- `resolution-drafter`: prepares a response draft
- `escalation-agent`: hands complex cases to a human queue

## Supporting resources

- `ToolMount/crm-api`
- `ToolMount/billing-db`
- `MemoryVolume/customer-history`
- `Workflow/support-ticket-resolution`

## Why this example matters

It demonstrates the core pitch of the platform:

- multiple agents cooperating on one workflow
- shared memory across steps
- runtime-attached tools
- observable handoffs and retries

## Future additions

- real example specs
- local dev bootstrap instructions
- screenshots of traces and workflow execution
