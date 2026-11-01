# Figures

The figures every probityai README and the site show. One source per figure, one token set
([`tokens.toml`](tokens.toml)), IBM Plex embedded as subset WOFF, an opaque card in both themes.

| Figure | Shows | Data |
| --- | --- | --- |
| `f1-four-verdicts` | one sealed archive checked four ways (intact, a changed byte, a missing file, a changed verifier), with the receipt, verdict and exit code each prints | [`data/four-arms.toml`](data/four-arms.toml) |
| `f3-missing-not-clean` | a record with a passage missing: a reader of the record alone says fine; `probity-verify` pairs the record with the source capture, finds the unpaired passage and says contradicted | [`data/source-coverage.toml`](data/source-coverage.toml) |

Each figure is published at `figures/<figure>/<rev>/<layout>-<theme>.svg`, where layout is `wide` (1280 units)
or `narrow` (720) and theme is `auto` (follows the reader's colour scheme), `light` or `dark`. A published
revision is never rewritten: change a figure by raising `REV` in its source. Embed by absolute URL, for
example `https://raw.githubusercontent.com/probityai/probityai.github.io/main/figures/f1-four-verdicts/1/narrow-auto.svg`.

```sh
uv run --script figures/build.py   # write the current revision of every figure
uv run --script figures/check.py   # freshness, append-only, text size, fallback colours, contrast
```

Every data file names the command whose printed output it holds. The fonts come from the masters pinned in
[`fonts/SOURCES.toml`](fonts/SOURCES.toml), cut by [`fonts/subset.py`](fonts/subset.py).
