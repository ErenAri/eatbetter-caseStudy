# Real-world manifest contract

`manifest.example.json` is illustrative and deliberately not runnable: it contains no image and no
verified FDC label. The executable schema is the strict Pydantic model in `evals/dataset.py`; its JSON
Schema can be exported with:

```powershell
..\backend\.venv\Scripts\python.exe -c "from evals.dataset import schema_json; print(schema_json())"
```

Put real image bytes and their manifest under `evals/private/`, which Git ignores. Do not convert the
example into an accuracy claim.
