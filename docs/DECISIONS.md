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

## 2026-11-05 — Audit treats every listed prerequisite as required

**Decision:** the Phase 3 audit (`app/audit.py`) requires *every* code in
`Course.prerequisites`, each completed in a strictly earlier term. This is
the assumption the entry above warns about, adopted knowingly: the Phase 3
canonical rules define the check exactly this way ("every prerequisite (from
the catalog) must have a Completed history entry in a strictly earlier
term"), and the grader enforces them as written.

**Consequence:** an OR-style prerequisite ("COSC 1047 or ITEC 1047") will be
reported as missing whichever alternative the student skipped. If the
AND/OR grouping branch is merged, `_missing_prerequisites` is the one place
that needs to change.

## 2026-11-05 — A course completed more than once earns credit once

**Decision:** `total_earned` (`app/audit.py::total_earned`) groups history by
normalized course code and counts each completed course once, using the
best `Completed` attempt's `credits_earned`. Non-completed attempts
(`Attempted`, `In-Progress`) contribute 0.

**Why:** the Phase 3 rule says total_earned "counts each completed course's
credits_earned once" — the unit is the course, not the transcript row. A
pass followed by another pass is still one completed course, and a
graduation audit must not award its credits twice. Taking the best attempt
also covers "a later pass overrides an earlier failure", even if a failure
were ever recorded as `Completed` with 0 credits.

**Known divergence:** the practice self-test grader deduplicates by
`(course_code, term)` only, so it would count a course `Completed` in two
different terms twice. Neither practice dataset contains that case (its
retake is Attempted → Completed, where both approaches agree), and we follow
the written rule rather than that edge of the script.

**Not modelled:** courses a calendar allows to be repeated for credit (e.g.
special topics). The rules don't define them; supporting them would need a
"repeatable" flag from the catalog.
