Analyze system boundaries, tradeoffs, migration order, and failure risks. For project-specific claims, use only retrieved project evidence.

If the design separates request handling from background work, state what stays synchronous, what moves to workers, how work is handed off, how to migrate incrementally, and how worker failures are recovered.

Do not assume every component should become a separate service.
