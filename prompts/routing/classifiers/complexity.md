# Complexity Classification

Classify how much reasoning the assistant must perform to answer the user's request.

Return exactly one value:

simple
standard
complex

Judge the actual reasoning burden of the requested answer.

Do NOT judge complexity from:

- topic importance;
- whether the request uses the web;
- whether the request concerns code;
- whether the request concerns a project;
- technical vocabulary by itself;
- the length of the prompt.

The three classes must be meaningfully separated.

## simple

Use `simple` when the task is focused and can usually be answered directly with little decomposition.

Typical characteristics:

- one fact;
- one definition;
- one straightforward explanation;
- one focused lookup;
- one simple transformation;
- one small code operation;
- one obvious debugging explanation;
- little or no tradeoff analysis.

Examples:

"What is dependency injection?"
→ simple

"What is MongoDB?"
→ simple

"Explain caching."
→ simple

"Who won the most recent championship?"
→ simple

"What is the current stable version of React?"
→ simple

"Find the official Rust documentation."
→ simple

"Rewrite this paragraph professionally."
→ simple

"Give me five concise email subject lines."
→ simple

"Why does adding an integer to a string raise TypeError?"
→ simple

"Write a function that removes duplicate strings while preserving order."
→ simple

## standard

Use `standard` for normal tasks that require several connected reasoning steps,
inspection of implementation details, or a moderate amount of explanation.

Typical characteristics:

- ordinary code explanation;
- normal debugging with evidence;
- normal implementation/refactoring;
- project-specific reasoning;
- explaining a flow across a few components;
- a focused comparison;
- multiple ordinary constraints;
- some analysis, but not sustained multi-system reasoning.

Examples:

"Diagnose this traceback and identify the smallest likely fix."
→ standard

"Explain how authentication works in my project."
→ standard

"Find where user sessions are loaded in my repository and explain the flow."
→ standard

"Add retry logic with exponential backoff to this function."
→ standard

"Refactor this class so its database dependency is injected through the constructor."
→ standard

"Search the web for this npm error and explain the likely cause."
→ standard

"Look up the latest Next.js release and explain the main changes."
→ standard

## complex

Use `complex` when the task genuinely requires sustained reasoning,
multi-source synthesis, architecture-level tradeoffs, or several interacting systems or constraints.

Typical characteristics:

- multi-source research and evidence synthesis;
- architecture decisions;
- migrations across systems or services;
- competing architectural alternatives;
- substantial infrastructure design;
- several interacting constraints;
- reasoning across multiple components or systems;
- recommendations requiring significant tradeoff analysis.

Examples:

"Research current AI privacy approaches and compare several independent sources."
→ complex

"Compare current serverless database platforms using multiple recent sources."
→ complex

"Research current local LLM deployment approaches and compare the tradeoffs reported by several sources."
→ complex

"Compare a monolith, modular monolith, and microservices architecture for a SaaS application."
→ complex

"Design a staged migration from one application server to separate API and worker services."
→ complex

"Should this workload use a message queue or synchronous HTTP? Compare the architectural tradeoffs."
→ complex

"Compare current cloud services for running containerized web applications and recommend an architecture."
→ complex

## Boundary rules

When choosing between `simple` and `standard`:

Choose `simple` if the answer is mostly direct.

Choose `standard` only when meaningful intermediate reasoning or implementation analysis is required.

Do NOT default ordinary questions to `standard`.

When choosing between `standard` and `complex`:

Choose `complex` only when the task needs sustained synthesis, architecture-level reasoning,
multiple interacting constraints, or substantial tradeoff analysis.

A technically sophisticated topic is not automatically complex.

A web lookup is not automatically complex.

Code is not automatically standard or complex.

## Calibration

Use all three classes.

`standard` is not a safe fallback.

If the request clearly matches a direct definition, fact, focused lookup, small transformation,
or small self-contained operation, classify it as `simple`.

If the request clearly requires architecture-level reasoning, substantial migration planning,
multi-source synthesis, or sustained tradeoff analysis, classify it as `complex`.

Otherwise classify it as `standard`.

Return only:

simple

or:

standard

or:

complex
