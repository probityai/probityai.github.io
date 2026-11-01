# probityai.github.io

The public site of the Probity AI organization on GitHub Pages: the landing page, the Atlas of agent assurance mechanisms and the pages the conformance tools publish.

For people choosing an agent-evidence tool, reading a retained run, or following a persistent link into the predicate and vocabulary pages.

## View it

Browse the published site at [probityai.github.io](https://probityai.github.io/). To serve this tree locally and run the checks the site CI runs:

```sh
git clone https://github.com/probityai/probityai.github.io
cd probityai.github.io
python3 -m http.server 8000
python3 -m unittest discover -s tests -v
python3 scripts/readme-lint.py README.md
```

```text
Serving HTTP on :: port 8000 (http://[::]:8000/) ...
Ran 6 tests in 0.0s
OK
```

Open `http://localhost:8000/` to see the landing page.

## Status

Live. `main` is published as the site; every pull request runs the route, keyboard and mobile-layout check.

## Docs

| Path | What it holds |
| --- | --- |
| [`index.html`](index.html) | The landing page |
| [`atlas/`](atlas/README.md) | Source of the Atlas, its cases and its checks |
| [`agent-evidence/`](agent-evidence/index.html) | Predicate, vocabulary and interoperability pages behind persistent identifiers |
| [`agent-evidence-observer/`](agent-evidence-observer/README.md) | Observer notes and architecture |
| [`scripts/`](scripts/check_served.py) | The served-bytes check and the README shape check |
| [Contributing](https://github.com/probityai/.github/blob/main/CONTRIBUTING.md) | Commit sign-off, commit format and checks |
| [Security](https://github.com/probityai/.github/blob/main/SECURITY.md) | Private vulnerability reporting |
