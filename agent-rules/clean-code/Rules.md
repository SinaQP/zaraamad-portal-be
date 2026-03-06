---
description: "Clean Code + SOLID: cohesive class-based classification, minimal scattering, readable conditions, and no unnecessary micro-functions."
alwaysApply: true
globs: ["app/**/*.py"]
---

# Clean Code + SOLID Rules (Mandatory)

## Classification and cohesion (mandatory)
- Code MUST be organized primarily around cohesive classes (not scattered free functions).
- Functions that share the same purpose/logic MUST live in the same class.
- A class MUST represent a clear responsibility (SRP) AND its methods MUST be strongly related (high cohesion).

### Forbidden
- Creating many small functions spread across files with no clear owning class.
- “Helper function dumping ground” patterns like `utils.py` with unrelated functions.

### Required
- Create a class per capability and place related methods inside it.
- Use private methods (`_method`) inside the class for internal steps if needed.

## SOLID (mandatory)
- SOLID principles MUST always be applied.
- **S = Single Responsibility Principle (SRP)**:
  - One class = one responsibility (one reason to change).
  - SRP does NOT mean “split everything into tiny functions”; it means “group related behavior under the correct abstraction”.

## Public surface area (mandatory)
- Keep the public API of a class small and intention-revealing.
- Prefer a few meaningful public methods over many granular public functions.
- Internal steps MUST be private methods on the same class (not free functions).

## When to use a function vs a class (mandatory)
- Use a CLASS when:
  - multiple operations share the same concept/config/constants/state, OR
  - methods are used together and form a “capability”.
- Use a pure FUNCTION only when:
  - it is a single, obvious operation AND
  - it does not belong to a broader capability class.

## Readability is the top priority
- Code MUST be readable at a glance.
- Prefer named abstractions over dense inline logic.

## Conditionals must be simple (mandatory)
- `if` conditions MUST NOT be long or hard to parse.
- Any non-trivial condition MUST be extracted into a well-named boolean variable or helper method.

## Constants and readability (mandatory)
- No dense inline lists/tuples inside logic.
- Non-trivial literals MUST be named constants and located near the owning class.

### Example requirement
Instead of:
`for fmt in ["...", "...", "..."]`

Use:
- a named constant: `SUPPORTED_TIMESTAMP_FORMATS`
- and readable loop variable names.

## Comments policy (strict)
- Comments SHOULD NOT exist.
- If a comment is needed to explain “what”, refactor to make the code self-explanatory.
- Allowed exceptions (rare): explaining “why” a business rule exists, or external constraints.

## Common/shared classes (mandatory)
- If a class is reused across multiple modules, it MUST live under `app/common/`:
  - `app/common/services/` for reusable capabilities
  - `app/common/parsers/` for parsing/normalization
  - `app/common/validators/` for validation logic
- Modules MUST NOT copy/paste shared logic; extract it into a common class and reuse it (composition).
