# ADR 0001: Modular monolith

## Context

The case study has a seven-day delivery window and needs mobile, API, domain, provider, persistence,
testing, and observability boundaries. Operational complexity does not demonstrate meal-logging
accuracy and would reduce time available for validation.

## Decision

Use one FastAPI deployable organized as a modular monolith. Domain and application modules depend on
protocols. Vendor SDKs and storage/database implementations remain infrastructure adapters.

## Alternatives

- **Single unstructured backend:** fastest initial file count, but mixes transport, vendor, and
  business rules and makes accuracy behavior difficult to test.
- **Microservices:** provides independent deployment boundaries, but introduces network failure,
  distributed tracing, local orchestration, and consistency work without current scale evidence.

## Consequences

Local development and tests stay simple, state changes can remain transactional, and observability
has one request boundary. Module discipline must be maintained in code review. A provider or worker
can later be extracted if throughput, reliability isolation, or team ownership provides evidence for
that cost.
