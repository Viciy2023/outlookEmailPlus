# Registration Worker Integration and Mail Pool API

[中文文档](./注册与邮箱池接口文档.md) | [English Version](./registration-mail-pool-api.en.md)

## Overview

This document describes the public APIs of the mail pool management system for registration workers and script-based integrations.

**Service purpose**: provide mailbox claiming, result callbacks, and pool management capabilities for registration workflows.

**Data format**: all requests and responses use JSON.

**CORS**: cross-origin requests are supported.

---

## Authentication and General Rules

### Getting an API Key

Contact the system administrator to obtain an API key and send it in the request header:

```text
Authorization: Bearer YOUR_API_KEY
```

**Test environment**: contact the administrator for a test key. Rate limit: 100 requests per minute.

### Standard Response Format

All endpoints follow the same response structure:

```json
{
  "success": true,
  "data": { "...": "..." },
  "message": "Operation completed successfully"
}
```

Failure response:

```json
{
  "success": false,
  "error": "error_code",
  "message": "Error description"
}
```

### Time Field Format

All time fields use ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`

---

## API Endpoint List

### Quick Start

Registration worker integrations only need to focus on these three core endpoints:

| Endpoint | Purpose | Required |
| --- | --- | --- |
| `POST /api/pool/claim-random` | Claim a mailbox | Yes |
| `POST /api/pool/claim-complete` | Submit task completion | Yes |
| `POST /api/pool/claim-release` | Release a mailbox | Yes |
| `GET /api/pool/stats` | View pool status | Optional |

---

## 1. Claim a Mailbox

### Basics

```text
POST /api/pool/claim-random
Authentication required: Yes
```

### Request Example

```bash
curl -X POST https://api.example.com/api/pool/claim-random \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "caller_id": "register-worker-1",
    "task_id": "job-20260317-0001",
    "provider": "outlook"
  }'
```

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `caller_id` | string | Yes | Caller identifier. Use a stable business or machine identifier such as `register-worker-1` or `register-cluster-a`. |
| `task_id` | string | Yes | Unique ID of the current registration task, such as `job-20260317-0001` or `order-928371`. |
| `provider` | string | No | Mail provider filter. Set `outlook` to claim Outlook mailboxes only. |

### Success Response Example

```json
{
  "success": true,
  "data": {
    "account_id": 12,
    "email": "demo@outlook.com",
    "claim_token": "clm_xxxxx",
    "lease_expires_at": "2026-03-17T10:00:00Z"
  },
  "message": "Mailbox claimed successfully"
}
```

### Response Fields

| Field | Type | Description |
| --- | --- | --- |
| `account_id` | integer | Account ID. Required when reporting completion or release. |
| `email` | string | Mailbox address. |
| `claim_token` | string | Claim token. Required in follow-up callbacks. |
| `lease_expires_at` | string | Lease expiration time. Submit completion or release before it expires. |

### Failure Response Example

```json
{
  "success": false,
  "error": "no_available_account",
  "message": "No eligible mailbox is currently available in the pool"
}
```

---

## 2. Complete a Task and Submit the Result

### Basics

```text
POST /api/pool/claim-complete
Authentication required: Yes
```

### Request Example

```bash
curl -X POST https://api.example.com/api/pool/claim-complete \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 12,
    "claim_token": "clm_xxxxx",
    "caller_id": "register-worker-1",
    "task_id": "job-20260317-0001",
    "result": "success",
    "detail": "Registration completed successfully"
  }'
```

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `account_id` | integer | Yes | Account ID returned by the claim operation. |
| `claim_token` | string | Yes | Claim token returned by the claim operation. |
| `caller_id` | string | Yes | Must match the `caller_id` used when claiming. |
| `task_id` | string | Yes | Must match the `task_id` used when claiming. |
| `result` | string | Yes | Task result. See the available values below. |
| `detail` | string | No | Additional details such as failure reason, target site, or risk-control behavior. |

### Allowed `result` Values and Final Status Mapping

| `result` value | Meaning | Final mailbox status | Typical use case |
| --- | --- | --- | --- |
| `success` | Registration succeeded and the account was consumed | `used` | Task completed successfully |
| `verification_timeout` | Verification code was never received | `cooldown` | No code arrived for a long time; retry later |
| `provider_blocked` | The provider blocked or restricted the account | `frozen` | Provider risk control, suspension, or limitation |
| `credential_invalid` | Credentials are no longer valid | `retired` | Mailbox password or credentials are invalid |
| `network_error` | Temporary network or infrastructure problem | `available` | Safe to return to the pool and retry quickly |

### Success Response Example

```json
{
  "success": true,
  "data": {
    "account_id": 12,
    "pool_status": "used"
  },
  "message": "Task result submitted successfully"
}
```

### Failure Response Example

```json
{
  "success": false,
  "error": "invalid_claim",
  "message": "The claim_token is invalid or does not match account_id"
}
```

---

## 3. Release a Mailbox

### Basics

```text
POST /api/pool/claim-release
Authentication required: Yes
```

### Request Example

```bash
curl -X POST https://api.example.com/api/pool/claim-release \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "account_id": 12,
    "claim_token": "clm_xxxxx",
    "caller_id": "register-worker-1",
    "task_id": "job-20260317-0001",
    "reason": "Task cancelled"
  }'
```

### Parameters

| Parameter | Type | Required | Description |
| --- | --- | --- | --- |
| `account_id` | integer | Yes | Account ID returned by the claim operation. |
| `claim_token` | string | Yes | Claim token returned by the claim operation. |
| `caller_id` | string | Yes | Must match the original claim request. |
| `task_id` | string | Yes | Must match the original claim request. |
| `reason` | string | No | Reason for releasing the mailbox. |

### Success Response Example

```json
{
  "success": true,
  "data": {
    "account_id": 12,
    "pool_status": "available"
  },
  "message": "Mailbox released back to the pool"
}
```

---

## 4. View Pool Status

### Basics

```text
GET /api/pool/stats
Authentication required: Yes
```

### Request Example

```bash
curl -X GET https://api.example.com/api/pool/stats \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Success Response Example

```json
{
  "success": true,
  "data": {
    "total": 1000,
    "available": 850,
    "claimed": 120,
    "used": 20,
    "cooldown": 5,
    "frozen": 3,
    "retired": 2
  },
  "message": "Query completed successfully"
}
```

---

## Error Handling

### HTTP Status Codes

| Status Code | Description |
| --- | --- |
| 200 | Request succeeded |
| 400 | Invalid request parameters |
| 401 | Unauthorized, missing or invalid API key |
| 403 | Forbidden |
| 404 | Resource not found |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

### Common Error Responses

#### Missing API Key

```json
{
  "success": false,
  "error": "missing_api_key",
  "message": "Send Authorization: Bearer YOUR_API_KEY in the request header"
}
```

#### Rate Limit Exceeded

```json
{
  "success": false,
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Please retry later"
}
```

#### No Mailbox Available

```json
{
  "success": false,
  "error": "no_available_account",
  "message": "No eligible mailbox is currently available in the pool"
}
```

#### `claim_token` Does Not Match

```json
{
  "success": false,
  "error": "invalid_claim",
  "message": "The claim_token is invalid or does not match account_id"
}
```

---

## Usage Limits

### Rate Limits

- Claim mailbox: 60 requests per minute
- Submit result: 120 requests per minute
- Query status: 300 requests per minute

### Lease Timeout

After claiming a mailbox, you must submit a completion or release request before `lease_expires_at`. Expired claims are automatically returned to the pool.

### Recommended Retry Strategy

- When receiving `429`, wait 1 second before retrying
- When receiving `no_available_account`, wait 5 to 10 seconds before retrying
- Exponential backoff is recommended

---

## Business Flow

```text
Import mailbox (add_to_pool=true)
         ↓
Mailbox enters the pool (status=available)
         ↓
Registration worker calls claim-random
         ↓
Registration worker performs the task
         ↓
    ┌────┴────┐
    ↓         ↓
Success/Fail  Abort midway
    ↓         ↓
claim-complete  claim-release
    ↓         ↓
Status updated   Mailbox returns to pool
```

---

## FAQ

### Q1: The account was imported, but the registration worker cannot claim it

**Possible reasons**:

1. `add_to_pool=true` was not set during import.
2. The account status is not `active` or it is not in `available`.

**Solution**: check the import parameters and make sure the account was added to the pool correctly.

### Q2: Why do I get a parameter mismatch error during callback

**Reason**: `account_id`, `claim_token`, `caller_id`, and `task_id` must exactly match the values returned by the claim operation.

**Solution**: the registration worker must store the original claim response and send it back without modification.

### Q3: What happens if I forget to submit a callback after claiming

**Impact**: the mailbox remains in `claimed` status and cannot be allocated to other tasks until the lease expires or it is released.

**Recommendation**:

- Call `claim-complete` for both successful and failed tasks.
- Call `claim-release` when abandoning the task midway.

### Q4: What happens if all failures are reported as `network_error`

**Impact**: invalid mailboxes may keep returning to the pool and get assigned repeatedly, wasting resources.

**Recommendation**: choose the correct `result` value based on the real failure reason.

---

## Contact

- Feedback: [Submit an Issue]

---

## Changelog

### v1.0.0 (2026-03-17)

- Initial release
- Support for mailbox claim, completion callback, release, and status query

---

## External Interface Paths

When using the controlled external API, the corresponding paths are:

- `/api/external/pool/claim-random`
- `/api/external/pool/claim-complete`
- `/api/external/pool/claim-release`
- `/api/external/pool/stats`

The business semantics are identical to the internal endpoints.
