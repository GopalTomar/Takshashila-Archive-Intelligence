# RAG & citations

Implemented in `app/ai/rag.py`, `app/ai/prompts.py`, `app/ai/citations.py`.

## Flow

```
question → hybrid retrieval → (no evidence? → return "insufficient", DON'T call model)
        → build grounded prompt with delimited, untrusted evidence
        → provider.chat(response_format=json_object)
        → parse structured JSON
        → validate every citation against the DB
        → derive confidence from validation
        → persist ai_run + citations (audit trail)
        → return answer + validated citations + sources + transparency
```

## Grounding prompt (spec 29)

The system prompt instructs the model to answer only from supplied archival
evidence, never invent citations/quotations/page numbers, and state explicitly
when evidence is insufficient. In **Archive Only** mode (default) general
knowledge is disallowed; **Archive + Web** allows clearly-labelled general
knowledge but never blends it silently.

## Structured output (spec 85)

```json
{
  "answer": "… with inline [c1] citations",
  "claims": [{"text": "…", "citation_ids": ["c1"]}],
  "citations": [{"id":"c1","document_id":"ARPI-00001","page":17,"chunk_id":"…","quote":"…"}],
  "confidence": "supported | partially_supported | insufficient_evidence"
}
```

## Citation validation (spec 31)

For each returned citation `app/ai/citations.py` checks:

1. the `chunk_id` exists **and** was in the retrieved evidence set;
2. the `document_id` matches that chunk's document;
3. the cited page exists / is not impossible (≤ page_count);
4. any `quote` actually appears in the chunk or page text (whitespace-normalised).

Failing citations are flagged; **confidence is derived from validation**, not
the model's self-assessment:

- all valid → `supported`
- some valid → `partially_supported`
- none valid → `insufficient_evidence`

The UI shows verified/unverified badges per source and lists any warnings.

## No-result behaviour (spec 90)

If retrieval finds nothing relevant, the model is **not** asked to answer from
general knowledge — the API returns an explicit insufficient-evidence message
plus suggestions (broaden date range, remove filters, related terms).

## Model fallback (spec 68)

There is **no silent** model fallback. If the configured provider/model fails,
the error is surfaced and evidence is still shown — provenance is never altered
behind the researcher's back.

## Cost / tokens (spec 69)

Token usage is shown when the provider returns it; cost is shown as
"Cost unavailable" rather than invented.

## Prompt-injection defence (spec 106)

Retrieved document text is wrapped in explicit delimiters and declared untrusted
data in the system prompt. The model is instructed to ignore any instructions
embedded in evidence. Document text is treated as data, never as commands.
