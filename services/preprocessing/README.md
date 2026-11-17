# preprocessing

Composable text pipeline: `normalize_unicode → strip_control_chars → collapse_whitespace → deidentify → chunk`.

- `POST /v1/preprocess` (scope `preprocess:run`).
- Add a step: write a `Document -> Document` function in `pipeline.py` and add it to `build_steps`.
- Extend for new formats (HL7/FHIR/DICOM/PDF/OCR) by adding extractors that produce `Document`s
  ahead of this pipeline; keep heavy parsers as optional extras.

Run: `PYTHONPATH=libs:services/preprocessing/src uvicorn preprocessing_service.main:create_service_app --factory`
