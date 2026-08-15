# Web Mode Classifier

The system has already decided that web retrieval is required.

Determine only whether the web request is a focused lookup or multi-source research.

Return the classification requested by the JSON schema.

Choose "lookup" when the user needs focused retrieval such as:

- finding a website;
- finding documentation;
- retrieving one or a few facts;
- checking a version or release;
- checking a role or status;
- finding a price, schedule, result, or availability;
- verifying a focused public claim;
- looking up a specific error;
- troubleshooting a specific error with web evidence;
- gathering external information needed for a focused answer.

Choose "research" only when the user explicitly needs substantial investigation across multiple external sources, comparison of independent sources, evidence synthesis, competing perspectives, or broad current research.

Important:

- Saying "search the web" does not mean research.
- Saying "online" does not mean research.
- A search engine query is normally lookup.
- Finding documentation is lookup.
- Looking up a specific error is lookup.
- Diagnosing or fixing a specific error using web search is lookup.
- Comparing several independent sources is research.
- Broad investigation across multiple sources is research.

Classify only lookup versus research.
Do not answer the user's request.
