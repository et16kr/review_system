# Altibase Coding Convention Quick Reference

This file is a repository-local Markdown digest of the following source document:

- `/home/et16/qa-30.CodingConventionAllInOne-240326-1217-62.pdf`

The goal is to make the Altibase coding rules easy to browse from inside the
`altidev4` tree. For full rationale, defect priority, and all original examples,
refer to the PDF.

## Quick checklist

- Use the Altibase prefix system consistently for modules, files, functions, and types.
- Name globals with `g`, locals with `s`, arguments with `a`, and members with `m`.
- Do not use `_` in variable names or user-defined type names.
- Keep lines at `<= 120` characters, use 4 spaces, and never use tabs.
- Put braces on separate lines and never omit them.
- Allow only one statement per line.
- Use only `/* ... */` comments, and comment every file and every function.
- Prefer Altibase and ID layer types such as `SInt`, `UInt`, `ULong`, and `idBool`.
- Do not include system headers directly; use Altibase or Alticore wrappers.
- Use `idlOS::*`, `IDL_FILE_SEPARATOR(S)`, `IDL_INVALID_HANDLE`, and `ID_*_FMT`.
- Avoid side effects inside macros, logical operators, and `sizeof`.
- Keep control flow simple: no `continue`, always add `default`, keep nesting low.
- Use `IDE_RC`, `IDE_TEST`, `IDE_TEST_RAISE`, and `IDE_EXCEPTION` consistently.
- Set error codes at the point of failure and preserve older errors with `IDE_PUSH()`
  and `IDE_POP()` when needed.
- Allocate and free memory at the same abstraction level, and null out pointers after
  `free()`.

## Root prefixes

The PDF defines the following Altibase HDB root prefixes:

| Prefix | Meaning |
| --- | --- |
| `pd` | Platform Dependent Layer |
| `id` | Independent Layer |
| `sm` | Storage Manager |
| `qp` | Query Processing Manager |
| `mt` | Mathematics Layer |
| `rp` | Replication Manager |
| `dk` | Database Link Module |
| `st` | Spatial Module |
| `sd` | Sharding |
| `mm` | Main Module |
| `cm` | Communication Module |
| `ut` | Utility Layer |
| `ul` | Utility Library Layer |

File names follow this basic shape:

```text
RootPrefix + [SubPrefix] + GivenName + Extension
```

Examples from the PDF:

- `iduProperty.cpp`
- `smntModules.cpp`
- `smnbModules.cpp`

## Naming rules

- Function names follow the prefix of the file that defines them.
- Class and struct type names also follow the file prefix.
- Global variables start with `g`.
- Local variables start with `s`.
- Function arguments start with `a`.
- Struct and class members start with `m`.
- Enum members must be uppercase.
- Parameter names in declarations and definitions must match.
- User-defined identifiers should stay meaningful and should not rely on significance
  beyond 64 characters.

Example:

```cpp
static SInt smlDoWork(SInt aArg)
{
    SInt sResult = 0;

    return sResult;
}

typedef struct smlThing
{
    UInt mCount;
} smlThing;
```

## File and layout rules

The PDF recommends keeping headers and source files managed independently:

- Header files under the module include directory
- Source files under the module source directory

Representative source layout:

```cpp
/*******************************************************************************
* Copyright 1999-2012, ALTIBASE Corporation or its subsidiaries.
* All rights reserved.
*******************************************************************************/
/*******************************************************************************
* $Id$
*
* Description :
* the explanation of this file.
*
*******************************************************************************/

#include <idl.h>
#include <sm.h>

extern smxTransMgr *smg_trans_mgr;
extern smrLogMgr   *smg_log_mgr;

SInt smlMyFunction(void)
{
    return 0;
}
```

Representative header layout:

```cpp
#ifndef _O_QDN_H_
#define _O_QDN_H_ 1

#include <iduMemory.h>
#include <qc.h>
#include <qdParseTree.h>

typedef struct qdnHeader
{
    UInt mCount;
} qdnHeader;

#endif /* _O_QDN_H_ */
```

Formatting expectations:

- First column must not begin with stray whitespace.
- Line length must be `<= 120` characters. The PDF recommends staying under `80`
  when practical.
- Indent with 4 spaces only.
- Braces go on their own lines.
- Every block uses braces, even for a single statement.
- No whitespace between a unary operator and its operand.
- Use one ASCII space between symbols and tokens where spacing is expected.
- No whitespace after `.` or `->`.
- Do not align multiple local variable declarations on the same line.
- One statement per line.
- Avoid line splicing.
- A function should be `<= 200` logical SLOCs.
- If a function has more than 2 parameters, keep the first parameter on the same
  line as the function name and put each additional parameter on its own line.
- Keep the return type on the same line as the function name.

Example:

```cpp
static
IDE_RC qdFunc(UInt aApple,
              UInt aBanana,
              UInt aGrape)
{
    return IDE_SUCCESS;
}
```

## Comments

- Only `/* ... */` style comments are allowed.
- Every file should have a file header comment.
- Every function should have a descriptive comment.
- Do not leave dead code commented out.

## Types, declarations, and expressions

Key reminders from the PDF:

- Do not use bit-fields.
- When using `typedef struct`, repeat the same type name at the end.
- Use `void` explicitly for functions that take no arguments.
- Do not use raw `i64`, `L`, or `ULL` suffixes directly. Use Altibase macros such as
  `ID_LONG(...)`.
- Prefer Altibase and ID layer typedefs over primitive C types.
- Avoid casts that narrow `double`, `long`, or `int` during function calls.
- Use portable conversion macros for risky conversions such as signed 64-bit to
  `double`.
- Prevent integer overflow in multiplication expressions.
- Do not use `register`.
- Never modify a string literal.
- Match every `printf` tag with the correct number and type of arguments.
- Do not call `sizeof` on constants.
- Do not use `sizeof` on expressions with side effects.
- Compare to zero explicitly unless the operand is effectively boolean.
- Test error information returned by functions.
- Do not use uninitialized memory.
- Ensure null pointers are not dereferenced.
- Do not compare floating-point values with direct `==` or `!=`.
- Avoid the ternary operator `?:`.

Examples:

```cpp
typedef struct myStruct
{
    SInt mVar1;
    SInt mVar2;
} myStruct;

void qdFunc(void)
{
    UInt  sInt;
    ULong sLong;
}
```

## Preprocessor and portability rules

- Prefer `#if defined(MY_MACRO)` and `#if !defined(MY_MACRO)` over `#ifdef` and
  `#ifndef`.
- Always use angle brackets for includes:

```cpp
#include <qdtest.h>
```

- Macro names must be uppercase.
- Do not include system headers directly. Use Altibase, Alticore, or ID layer
  headers such as `<acp.h>`, `<acl.h>`, and `<idl.h>`.
- Use include guards in the `_O_NAME_H_` style and define them to `1`.
- Preprocessor `#` directives start in column 1.
- Parenthesize each parameter occurrence in function-like macros.
- Avoid side effects in macro arguments.
- Keep macros to 10 lines or less when possible.
- Do not use more than 5 macro parameters.

Portable system access rules:

- Do not call system library functions directly.
- Use wrappers such as `idlOS::printf()` and `idlOS::exit()`.
- Do not embed directory separators directly. Use `IDL_FILE_SEPARATOR` or
  `IDL_FILE_SEPARATORS`.
- Do not compare file handles against `-1` or `0`; compare against
  `IDL_INVALID_HANDLE`.
- Do not use primitive format specifiers directly in portable code. Use macros such
  as `ID_INT32_FMT`, `ID_UINT32_FMT`, `ID_INT64_FMT`, `ID_xINT32_FMT`, and
  `ID_POINTER_FMT`.

Examples:

```cpp
idlOS::printf("32BIT Decimal is %"ID_INT32_FMT" and Hexa is 0x%"ID_xINT32_FMT"\n",
              1024,
              1024);

idlOS::printf("%s%s%s", IDU_LOG_DIR, IDL_FILE_SEPARATORS, "FileName");

if (sFd == IDL_INVALID_HANDLE)
{
    return IDE_FAILURE;
}
```

## Control flow rules

- Do not use `continue`.
- Always provide a `default` branch in every `switch`.
- Keep nested block depth at `<= 5`.
- Do not use assignment expressions in `if` conditions.
- Keep cyclomatic complexity at `<= 10`.
- Do not declare variables in the `for` statement itself.
- Do not use 64-bit integers as `switch` condition types.
- Do not modify the loop counter inside the loop body.
- Do not leave unreachable code after control flow statements.
- Prefer enum values for `case` labels.
- Avoid `switch` statements with more than 20 `case` labels.
- Every `case` and `default` branch should end with an explicit `break`, `return`,
  or `fall through` comment.

## Memory rules

- In `memcpy`, `strncpy`, and `memmove`, the third argument should not depend on the
  source buffer size.
- Do not perform zero-length allocations.
- Do not use `sizeof(pointer)` to compute allocation size for the pointed-to object.
- Null-terminate strings where required.
- Use `'\0'` for string termination.
- Allocate and free memory in the same module, and preferably at the same level of
  abstraction.
- Assign `NULL` immediately after `free()`.
- Do not use unbounded functions such as `strcpy()`.

Examples:

```cpp
idlOS::memcpy(sDestName, sSrcName, ID_SIZEOF(sDestName));

iduMemMgr::malloc(IDU_MEM_SM_SDN,
                  ID_SIZEOF(smiFetchColumnList),
                  (void **)&sHeader);

(void)iduMemMgr::free(sObject);
sObject = NULL;
```

## Altibase-specific error handling conventions

The PDF has a separate section for Altibase error handling, beyond the `ALTI-ERR-*`
rules.

Core guidance:

- Functions that can fail return `IDE_RC`.
- Functions that cannot fail may return their direct value instead.
- Prefer `IDE_ERROR` or `IDE_TEST` to `IDE_ASSERT` when actual error handling is
  needed.
- Do not place `IDE_TEST` under `IDE_EXCEPTION_END`; that can create a jump loop.
- Place `IDE_EXCEPTION(...)` blocks before `IDE_EXCEPTION_END`.
- Keep `IDE_FT`, `IDE_NOFT`, `IDE_FT_ROOT`, and `IDE_(NO)FT_EXCEPTION` begin/end
  pairs balanced.
- Try to keep one `IDE_SUCCESS` return and one `IDE_FAILURE` return path when
  practical.
- The function that detects the error is responsible for setting the error code.
- Use `IDE_SET(ideSetErrorCode(...))` when assigning an error code.
- Use `IDE_CLEAR` to clear thread-local error storage when required by the call flow.
- Use `IDE_PUSH()` and `IDE_POP()` if an exception handler must call another function
  that can also set an error code.
- Error priority is documented as:

```text
FATAL > REBUILD > RETRY > ABORT > IGNORE
```

Representative template:

```cpp
IDE_RC qdFunc(void)
{
    IDE_RC rc;

    rc = qdChild1();
    IDE_TEST_RAISE(rc != IDE_SUCCESS, Child1_error);

    return IDE_SUCCESS;

    IDE_EXCEPTION(Child1_error);
    {
        (void)qdRollback();
    }
    IDE_EXCEPTION_END;

    return IDE_FAILURE;
}
```

## Error code naming and message rules

The final pages of the PDF describe the Altibase error code system:

- Error code box: 8 nibbles / 32 bits
- Error code: 5 nibbles
- Index code: 3 nibbles
- Error code layout:

```text
[module:1 nibble] + [action:1 nibble] + [subcode:3 nibbles]
```

- Module code examples: `SM`, `QP`, `CM`, `MAIN`, `ID`
- Action code examples: `FATAL`, `ABORT`, `IGNORE`
- Suggested error code name shape:

```text
[MODULE]ERR_[ACTION][Description][NamingSpace]
```

Examples from the PDF:

- `[MODULE]`: `sm`, `qp`, `cm`, ...
- `[ACTION]`: `FATAL`, `ABORT`, `IGNORE`
- `[NamingSpace]`: `qpd`, `qpf`, `smd`, `smc`, ...

## Rule index

Page numbers below refer to the source PDF.

### Naming and prefixes (p.4-15)

- `ALTI-NAE-001` (p.4): Code prefix policy.
- `ALTI-NAE-002` (p.5): File name policy.
- `ALTI-NAE-003` (p.6): Function name policy.
- `ALTI-NAE-004` (p.6): Class name policy.
- `ALTI-NAE-005` (p.7): Begin global variable names with `g`.
- `ALTI-NAE-006` (p.8): Begin local variable names with `s`.
- `ALTI-NAE-007` (p.9): Begin argument names with `a`.
- `ALTI-NAE-008` (p.9): Begin struct or class member names with `m`.
- `ALTI-NAE-009` (p.10): Do not use `_` in variable names.
- `ALTI-NAE-010` (p.11): Do not use `_` in user-defined type names.
- `ALTI-NAE-011` (p.12): Enum members must be uppercase.
- `ALTI-NAE-012` (p.13): Parameter names in declarations and definitions must match.
- `ALTI-NAE-013` (p.14): Do not rely on significance beyond 64 characters.

### Formatting and layout (p.17-40)

- `ALTI-FOR-001` (p.17): Source code configuration.
- `ALTI-FOR-002` (p.20): Source directory configuration.
- `ALTI-FOR-003` (p.20): No leading whitespace at the beginning of source code.
- `ALTI-FOR-004` (p.21): Keep source lines at 120 characters or less.
- `ALTI-FOR-005` (p.22): Use 4 spaces instead of tabs.
- `ALTI-FOR-006` (p.23): Blocks begin at the expected 4-space indentation level.
- `ALTI-FOR-007` (p.23): Put braces on separate lines.
- `ALTI-FOR-008` (p.24): Do not omit braces.
- `ALTI-FOR-010` (p.27): No whitespace between a unary operator and its operand.
- `ALTI-FOR-011` (p.27): Use one ASCII space where required between symbols and
  tokens.
- `ALTI-FOR-012` (p.32): Do not define or align multiple local variables on one line.
- `ALTI-FOR-013` (p.33): Keep a function at 200 logical SLOCs or less.
- `ALTI-FOR-014` (p.34): Do not use line splicing.
- `ALTI-FOR-015` (p.35): One statement per line.
- `ALTI-FOR-016` (p.35): Split function parameters across lines after the first one.
- `ALTI-FOR-017` (p.39): Put `(` directly after the function name.
- `ALTI-FOR-018` (p.39): Keep the return type on the same line as the function name.
- `ALTI-FOR-019` (p.40): No whitespace after `.` or `->`.

### Comments (p.41-45)

- `ALTI-COM-001` (p.41): Use only `/* ... */` comments.
- `ALTI-COM-002` (p.42): Comment every file.
- `ALTI-COM-003` (p.44): Comment every function.
- `ALTI-COM-004` (p.44): Do not leave sections of code commented out.

### Declarations and function design (p.46-61)

- `ALTI-DCL-001` (p.46): Do not use bit-field data types.
- `ALTI-DCL-002` (p.47): Repeat the struct type name in `typedef struct`.
- `ALTI-DCL-003` (p.48): Use `void` for functions that take or return no values.
- `ALTI-DCL-004` (p.49): Do not use `i64` or `L` suffixes directly.
- `ALTI-DCL-005` (p.50): In enum lists, either initialize only the first item or
  initialize all items explicitly.
- `ALTI-DCL-006` (p.52): Avoid functions with more than 7 parameters.
- `ALTI-DCL-007` (p.54): Use a single exit point at the end of the function.
- `ALTI-DCL-008` (p.56): Match the number of format tags and `printf` arguments.
- `ALTI-DCL-009` (p.58): Repeat `static` in every redeclaration when a function has
  internal linkage.
- `ALTI-DCL-010` (p.60): Do not leave unused parameters in functions.
- `ALTI-DCL-011` (p.61): Do not leave unused local variables in functions.

### Types and casts (p.62-74)

- `ALTI-TYC-001` (p.62): Do not use primitive data types.
- `ALTI-TYC-002` (p.63): Do not cast signed 64-bit values to `double` directly.
- `ALTI-TYC-003` (p.64): Use `&` correctly.
- `ALTI-TYC-004` (p.66): Do not mismatch `printf` format specifiers and argument
  types.
- `ALTI-TYC-005` (p.68): Do not pass `int`, `long`, or `double` casted to `short`.
- `ALTI-TYC-006` (p.71): Do not pass `long` or `double` casted to `int`.
- `ALTI-TYC-007` (p.73): Avoid integer overflow in multiplication expressions.

### C string and storage rules (p.75-77)

- `ALTI-CSV-001` (p.75): Do not use `register`.
- `ALTI-CSV-002` (p.76): Do not modify string literals.

### Preprocessor (p.78-87)

- `ALTI-PRE-001` (p.78): Use `#if defined()` and `#if !defined()` instead of
  `#ifdef` and `#ifndef`.
- `ALTI-PRE-002` (p.79): Do not use double quotes in include definitions.
- `ALTI-PRE-003` (p.80): All `#define` constants must be uppercase.
- `ALTI-PRE-004` (p.80): Do not include system library header files directly.
- `ALTI-PRE-005` (p.81): Use `#ifndef` and `#endif` include guards.
- `ALTI-PRE-006` (p.82): Preprocessor `#` starts in the first column.
- `ALTI-PRE-007` (p.83): Parenthesize every parameter occurrence in function-like
  macros.
- `ALTI-PRE-008` (p.84): Avoid side effects in arguments to unsafe macros.
- `ALTI-PRE-009` (p.86): Keep macros within 10 lines.
- `ALTI-PRE-010` (p.87): Keep macro parameters to 5 or fewer.

### Operators and expressions (p.88-107)

- `ALTI-OPE-001` (p.88): Operands of `&&` and `||` must be primary expressions.
- `ALTI-OPE-002` (p.90): The right-hand side of `&&` and `||` must not contain side
  effects.
- `ALTI-OPE-003` (p.91): Do not assume `%` returns a positive remainder.
- `ALTI-OPE-004` (p.92): Do not call `sizeof` on constants.
- `ALTI-OPE-005` (p.93): Do not use `sizeof` on expressions with side effects.
- `ALTI-OPE-006` (p.94): Make tests against zero explicit unless the operand is
  effectively boolean.
- `ALTI-OPE-007` (p.96): Test error information generated by functions.
- `ALTI-OPE-008` (p.98): Do not reference uninitialized memory.
- `ALTI-OPE-009` (p.101): Ensure a null pointer is not dereferenced.
- `ALTI-OPE-010` (p.103): Do not test floating-point expressions for equality or
  inequality directly.
- `ALTI-OPE-011` (p.106): Avoid the ternary operator.

### Control flow (p.108-127)

- `ALTI-COF-000` (p.108): Control flow introduction.
- `ALTI-COF-001` (p.109): Do not use `continue`.
- `ALTI-COF-002` (p.111): Always provide a `default` branch for `switch`.
- `ALTI-COF-003` (p.112): Keep nested block depth at 5 or less.
- `ALTI-COF-004` (p.113): Do not use assignment expressions in `if` conditions.
- `ALTI-COF-005` (p.115): Keep cyclomatic complexity within 10.
- `ALTI-COF-006` (p.117): Do not declare variables in the `for` statement.
- `ALTI-COF-007` (p.118): Do not use 64-bit integers as `switch` condition types.
- `ALTI-COF-008` (p.120): Do not modify the `for` loop counter in the body.
- `ALTI-COF-009` (p.121): Do not leave unreachable code after control flow
  statements.
- `ALTI-COF-010` (p.122): Use enum types instead of integer types as `case` labels.
- `ALTI-COF-011` (p.123): Avoid `switch` statements with more than 20 `case` labels.
- `ALTI-COF-012` (p.125): Every `case` and `default` needs `break`, `return`, or a
  `fall through` comment.

### Altibase error macros (p.128-141)

- `ALTI-ERR-001` (p.129): Do not place `TEST` macros under `EXCEPTION_END`.
- `ALTI-ERR-002` (p.131): Consider `IDE_ERROR` or `IDE_TEST` instead of
  `IDE_ASSERT`.
- `ALTI-ERR-003` (p.133): `IDE_FT` macro usage.
- `ALTI-ERR-004` (p.137): `IDE_NOFT` macro usage.
- `ALTI-ERR-005` (p.140): `IDE_FT_ROOT` macro usage.
- `ALTI-ERR-006` (p.141): `IDE_(NO)FT_EXCEPTION` macro usage.

### Memory (p.142-160)

- `ALTI-MEM-001` (p.142): The third parameter to `memcpy`, `strncpy`, and `memmove`
  must not depend on the second buffer.
- `ALTI-MEM-002` (p.143): Do not perform zero-length allocations.
- `ALTI-MEM-003` (p.144): Do not use `sizeof(pointer)` as the allocation size for
  `malloc`, `calloc`, or `realloc`.
- `ALTI-MEM-004` (p.145): Null-terminate character strings as required.
- `ALTI-MEM-005` (p.147): Use `'\0'` as the null termination character.
- `ALTI-MEM-006` (p.150): Allocate and free memory in the same module and at the same
  abstraction level.
- `ALTI-MEM-007` (p.153): Assign `NULL` immediately after `free()`.
- `ALTI-MEM-008` (p.159): Do not use unbounded functions.

### Pointers and object lifetime (p.161)

- `ALTI-POA-001` (p.161): Never return a reference to a local object.

### Portability and compatibility (p.162-167)

- `ALTI-PCM-002` (p.162): Do not call system library functions directly.
- `ALTI-PCM-003` (p.164): Do not use directory separators directly.
- `ALTI-PCM-004` (p.165): Use `IDL_INVALID_HANDLE` for file and socket handle error
  checks.
- `ALTI-PCM-005` (p.166): Do not use primitive format specifiers directly.

### Error handling conventions (p.167-170)

- Rule-R1: Functions that can fail return `IDE_RC`.
- Rule-R2: Use `IDE_TEST_RAISE`, `IDE_TEST`, `IDE_RAISE`, `IDE_EXCEPTION`, and
  `IDE_EXCEPTION_END` consistently.
- Rule-R3: Set and propagate error codes with `IDE_CLEAR`, `IDE_SET`, `IDE_PUSH`,
  `IDE_POP`, `ideAllocErrorSpace()`, and `ideSetErrorCode()`.

### Error code and message rules (p.171-173)

- Error code writing rules
- Error message writing rules
- Error code box layout
- Error code naming rules
- Error message naming and generation rules
