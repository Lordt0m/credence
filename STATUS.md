# Project status: Credence

## Repository checkpoint
- Phase: Public build complete; independent review repairs open.
- Repository: repository root on branch `main`.
- Remote: `https://github.com/Lordt0m/credence`.

## Last verified result
- 27 automated unit, integration, and demonstration tests passing locally and in public CI.
- GitHub Actions CI matrix (Python 3.13 on `ubuntu-latest` and `windows-latest`) passing green (Run ID: 35417227728).
- Complete MVP acceptance gate met:
  1. Standard library runtime with zero external runtime dependencies.
  2. Strict header contract validation, column permutation tolerance, and physical line tracking.
  3. All field validations (ISO date, type normalization, positive decimal amounts, required strings, optional reference) and whole-file duplicate rejection verified.
  4. Staged output safety, collision prevention (exit code 2), and simulated write cleanup verified.
  5. Deterministic outputs (`clean-transactions.csv`, `validation-errors.csv`, `summary.json`) matching canonical fixtures byte-for-byte.
  6. Clean CLI exit codes (0, 1, 2) without Python tracebacks.
  7. Public documentation, specifications, ADRs, workflows, and demonstration datasets aligned.

## Known risks
- Independent review found that sequential artifact publication can leave partial output if a later move fails.
- Broad CLI exception handling hides unexpected programming defects.
- Malformed CSV quoting and whitespace-decorated headers do not yet follow the exact file contract.
- Public CI passes but its action versions emit Node.js deprecation warnings.

## Next safe action
- Repair the independent review findings test-first, align documentation with actual guarantees, and obtain a fresh green public CI run.
