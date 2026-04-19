# Altibase Sample Convention

## Comments

- Only `/* ... */` comments are allowed.
- Every file should have a file header comment.

## Memory rules

- Allocate and free memory in the same module.
- Assign `NULL` immediately after `free()`.

## Altibase-specific error handling conventions

- Functions that can fail return `IDE_RC`.
- Use `IDE_TEST` and `IDE_EXCEPTION` consistently.

## Rule index

### Comments (p.1-2)

- `ALTI-COM-001` (p.1): Use only `/* ... */` comments.

### Memory (p.3-4)

- `ALTI-MEM-006` (p.3): Allocate and free memory in the same module and at the same
  abstraction level.
- `ALTI-MEM-007` (p.4): Assign `NULL` immediately after `free()`.

### Error handling conventions (p.5-6)

- Rule-R1: Functions that can fail return `IDE_RC`.
