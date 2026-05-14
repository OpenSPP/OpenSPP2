### 19.0.2.0.4

- feat(invalid-values): each `spp.scoring.invalid.value` entry now carries a `match_type` selection (`exact` / `regex`). Regex entries let you catch a *range* of sentinel values with one pattern (e.g. `^N/A.*$` covers `N/A`, `N/A!`, `N/A — missing`) instead of enumerating every variation. Engine matches via `re.fullmatch`; bad patterns fail at `@api.constrains` time, never at scoring time.
- chore(tooltips): rewrite the `Default Value` and `Default Score` field help on `spp.scoring.indicator` so the relationship between **Required**, **Default Value**, **Default Value → coerced → mapping**, and **Default Score** is explicit instead of one-liner-vague.

### 19.0.2.0.0

- Initial migration to OpenSPP2
