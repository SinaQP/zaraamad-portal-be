## DTO inheritance pattern (mandatory)
For every API model `<Model>` defined in `dtos.py`:

- You MUST define a `<Model>Base` DTO containing all shared fields.
- `<Model>Create` MUST inherit from `<Model>Base` and MUST NOT redeclare shared fields.
- `<Model>Out` MUST inherit from `WithId` and `<Model>Base` and MUST NOT redeclare shared fields.
- Nested DTOs (e.g., `<Model>Stats`) MUST inherit from `MongoDTO` (or the project’s shared base DTO) to keep encoders/config consistent.
- `dtos.py` MUST import and use shared DTO bases from `app.common.dtos`:
  - `MongoDTO` (project-wide BaseModel config)
  - `WithId` (id alias/encoding)
- Violations (duplicating fields across Create/Out, not using `<Model>Base`, or not using shared bases) MUST be refactored.

### Example (required structure)
- `IngestionBase(MongoDTO)`
- `IngestionCreate(IngestionBase)`
- `IngestionOut(WithId, IngestionBase)`
