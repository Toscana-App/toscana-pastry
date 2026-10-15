# API Conventions

## General
- **Protocol:** RESTful.
- **Version:** `/api/v1/...`
- **Format:** `application/json`.
- **Error Handling:** Use `problem+json` (RFC 7807).

## Standards
- **Pagination:** `?page={number}&page_size={size}` (Default 50, Max 200).
- **Rate Limiting:** Enforced via middleware (headers: `X-RateLimit-*`).
- **Authentication:** JWT in `HttpOnly`, `Secure`, `SameSite=Strict` cookies.
- **Concurrency:** All endpoints must be `async`.
