Analyze system boundaries, constraints, tradeoffs, migration sequencing, and failure risks. Base claims about the user's project only on retrieved project context.

## Required architecture mechanics

When the request involves separating synchronous request handling from
background work, make the execution boundary explicit.

The answer should explain:

- what remains on the synchronous request path;
- what work moves to background workers;
- how work is handed from the request path to workers;
- how the migration can be introduced incrementally;
- at least one concrete worker-failure mechanism such as retry,
  idempotency, dead-letter handling, or equivalent recovery behavior.

Do not turn a request for API and worker separation into a generic
migration checklist.

Do not infer that every identified component should become an
independent microservice.
