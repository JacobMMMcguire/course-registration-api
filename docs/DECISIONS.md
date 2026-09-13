# Design Decisions

## 2026-09-13 — Prerequisites/Cross-listed are flat arrays, not AND/OR trees

**Decision:** `Course.prerequisites` and `Course.cross_listed` are flat
`List[str]` of course codes, extracted from free text with a regex
(`app/parsers/catalog_parser.py::_extract_codes`). Logical relationships
between codes (AND vs. OR) are **not** preserved.

**Example:**

```
Source text:  "Requires COSC 1046 and either COSC 1047 or ITEC 1047"
Actual output: ["COSC 1046", "COSC 1047", "ITEC 1047"]
```

The true meaning is `COSC 1046 AND (COSC 1047 OR ITEC 1047)`. The flat array
loses that distinction — it reads as "all three required," which is
incorrect for the OR case.

**Why this was accepted for now:** implementing an AND/OR-aware structure
(e.g. representing an OR-group as a nested array:
`["COSC 1046", ["COSC 1047", "ITEC 1047"]]`) is a real schema change that
affects the `POST /api/v1/admin/catalog/import` response, the `Course`
model, and every consumer of `prerequisites`/`cross_listed`. Whether it's
worth doing depends on how the data will actually be used downstream
(registration eligibility checks need real AND/OR logic; a course browser
display might not). That's a product call, not a parsing call, and it
needs stakeholder input before committing to a shape.

**Status:** open. Do not build features on top of `prerequisites` that
assume "all codes in the array are individually required" without checking
back here first — that assumption is known to be wrong for OR-style
prerequisites and is only correct by coincidence for AND-only ones.

**Revisit plan:** an AND/OR-preserving version will be built on a separate
branch once the requirement is confirmed, and merged back if adopted. See
git branch `feature/prereq-and-or-grouping` (or check `git branch -a` if
that name has since changed).
