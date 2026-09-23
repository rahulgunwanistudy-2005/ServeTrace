# Sample documents

**Synthetic. Nothing here is a real case, a real person or a real filing.**

Both files were produced by the committed demo case `maria_contradicted` going through
exactly the code path a download takes — `app.documents.packet.build_packet` and
`app.documents.affidavit.build_draft_affidavit`, rendered by WeasyPrint from the templates
in `backend/app/documents/templates/`. Nothing was edited afterwards, and no LLM was
involved in either one (bible §15).

| file | what it is |
|---|---|
| `evidence-packet.pdf` | the Evidence Packet: verdict, each sworn moment, the findings with the provision each encodes, the nineteen location records the check ran over, the thresholds it ran under, and a SHA-256 of both inputs |
| `draft-affidavit.pdf` | the Draft Supporting Affidavit, to attach to the court's own Order to Show Cause form — fourteen numbered paragraphs, each built from a confirmed field or a finding, with the signature and notary block left blank |

Everyone named in them is invented. The addresses are real public NYC street addresses,
used as geography only, from the pool in `fixtures/addresses_nyc.json` (bible §16).

Regenerate after changing a template or any sentence in `documents/copy.py`:

```bash
cd backend && DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib \
    PYTHONPATH=.. uv run python -m tests.documents.build_samples
```

## What is not in them yet

The packet's map section prints its text alternative rather than a map. The image is
captured client-side from the result map's canvas (bible §15), and the defendant result
page is session 8's work — the embedding path itself is covered by tests. The table of
coordinates underneath is the same data either way, which is why the section reads
correctly without it.
