# Frontend

Flutter Web client. This directory is a placeholder: the Flutter project has not been
created yet and its internal structure is up to the frontend owner.

## Creating the project

From this directory, with the Flutter SDK installed:

```bash
flutter create --platforms web --project-name orbitvitals .
```

The repository `.gitignore` already covers Flutter build output and keeps `lib/`
tracked.

## Working against the API

- The contract is described in [docs/api-contracts.md](../docs/api-contracts.md).
- Until an endpoint is implemented, use the payloads in
  [schemas/examples/](../schemas/examples/) as fixtures.
- [schemas/metric_catalog.json](../schemas/metric_catalog.json) lists every metric with
  its unit and domain.
- The backend runs on `http://localhost:8000` and accepts requests from any `localhost`
  port, so `flutter run -d chrome` works without extra CORS configuration.
- Keep the API base URL configurable, for example with
  `--dart-define=API_BASE_URL=http://localhost:8000/api/v1`.

Shared conventions are in [AGENTS.md](../AGENTS.md).
