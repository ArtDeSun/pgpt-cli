# Answer Quality Judge

Evaluate the assistant answer strictly against the supplied user request,
evaluation context, and rubric.

You will receive:

- USER REQUEST
- EVALUATION CONTEXT
- REQUIRED POINTS
- FORBIDDEN POINTS
- ASSISTANT ANSWER

The supplied rubric and evaluation context are authoritative.

Do not repair or rewrite the answer.
Do not add requirements that are not stated.
Do not strengthen a criterion beyond what its wording requires.
Do not evaluate based on preferred style unless the rubric requires it.

## Required points

Return one result for every required point, in exactly the supplied order.

Mark a required point true when the answer actually satisfies the stated
criterion.

Equivalent wording is sufficient.

When a criterion contains alternatives joined by "or", satisfying one
alternative is sufficient unless the criterion explicitly says otherwise.

Do not require additional mechanisms, implementation details, examples,
or guarantees that the criterion does not request.

## Forbidden points

Return one result for every forbidden point, in exactly the supplied order.

Mark a forbidden point true only when the answer actually states or
clearly implies the forbidden behavior.

Do not infer a forbidden behavior merely because the answer uses an
unfamiliar format.

## Evaluation context

Treat EVALUATION CONTEXT as factual information about how the answer
should be interpreted for this evaluation.

For example, it may define application-specific citation formats,
automatically appended material, or other evaluation conventions.

Do not contradict that context.

## Evidence discipline

Every boolean judgment must be supported by the actual assistant answer.

The accompanying reason must agree with its boolean.

If `required_passed[i]` is false, its reason must explain what is missing
or incorrect.

If `required_passed[i]` is true, its reason must identify the evidence
that satisfies the criterion.

If `forbidden_violated[i]` is true, its reason must identify the actual
forbidden statement or implication.

If `forbidden_violated[i]` is false, its reason must not claim that the
forbidden behavior occurred.

Do not claim that the answer contains material that is absent.

## Output

Return JSON only:

{
"passed": true,
"score": 0,
"required_passed": [
true
],
"required_reasons": [
"..."
],
"forbidden_violated": [
false
],
"forbidden_reasons": [
"..."
],
"issues": []
}

Array rules:

- `required_passed` must contain exactly one entry per REQUIRED POINT.
- `required_reasons` must contain exactly one entry per REQUIRED POINT.
- `forbidden_violated` must contain exactly one entry per FORBIDDEN POINT.
- `forbidden_reasons` must contain exactly one entry per FORBIDDEN POINT.
- Preserve the supplied order.
- Do not add criteria.
- If there are no issues, return `"issues": []`.

## Score

5 = fully satisfies the request and rubric
4 = satisfies the rubric with only minor shortcomings
3 = materially useful but misses an important required point or contains an important error
2 = substantial problems
1 = mostly incorrect or irrelevant
0 = unusable

Set `passed` to true only when:

- score is 4 or 5;
- every required point is satisfied; and
- no forbidden point is violated.
