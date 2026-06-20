# The Model-Swap Test

A system passes the Model-Swap Test when the underlying model or endpoint can be replaced while preserving the business capability within an acceptable recovery window.

The test is not instant portability and does not assume all models are equivalent. It asks whether the organization owns the assets required to requalify a substitute:

- Prompt and system instructions
- Policy constraints
- Eval set
- Acceptance criteria
- Tool contracts
- Fallback procedure
- State and evidence capture

If a capability has no eval set, this harness returns `NOT_SWAPPABLE` with a non-zero exit code. Without acceptance evidence, a substitute cannot be requalified.
