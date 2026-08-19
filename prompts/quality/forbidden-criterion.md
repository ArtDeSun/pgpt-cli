Evaluate one forbidden criterion against the assistant answer.

Set `violated` to true only when the answer states or clearly implies the forbidden meaning. Evidence may be used to check whether a claim is unsupported or contradicted, but is not something the answer itself claimed.

Otherwise set `violated` to false. Judge only this criterion and return only the JSON required by the schema.
