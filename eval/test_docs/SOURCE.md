# Test Document Sources

Real, public technical documentation — chosen because it's exactly the
kind of material an internal engineering knowledge base holds (library
guides, how-tos, reference pages), and anyone can re-download it to
reproduce the eval.

| File | Source | Retrieved | Notes |
|---|---|---|---|
| `requests-docs.pdf` | https://requests.readthedocs.io/_/downloads/en/stable/pdf/ (Requests 2.34.2) | 2026-08-03 | 125 pages, used as-is |
| `pytest-docs-p1-100.pdf` | https://pytest.readthedocs.io/_/downloads/en/stable/pdf/ | 2026-08-03 | First 100 of 563 pages (project's 100-page doc limit); covers get-started, fixtures, marks, parametrize |
| `mypy-docs-p1-100.pdf` | https://mypy.readthedocs.io/_/downloads/en/stable/pdf/ (mypy 2.3.0) | 2026-08-03 | First 100 of 370 pages (project's 100-page doc limit) |

> Note: an earlier candidate from `click.readthedocs.io` turned out to be
> Ubuntu's "Click Packages" docs, not the Python click library — caught by
> validating eval substrings against the ingested corpus. Replaced with mypy.

All three are BSD/MIT-family licensed open-source project docs,
redistributed here unmodified (except the pytest page trim) for
evaluation purposes with attribution.
