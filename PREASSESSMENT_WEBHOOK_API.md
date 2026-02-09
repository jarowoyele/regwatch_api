# Pre-assessment Webhook API

## Overview
The RegWatch AI API now includes webhook endpoints to receive pre-assessment notifications from external systems.

## Endpoints

### 1. Receive Pre-assessment Webhook
**POST** `/webhook/preassessment`

Receives pre-assessment webhook notifications with organization, pre-assessment, and regulation IDs.

**Request Body:**
```json
{
  "organization_id": "682ae94fa2e778c597d09b57",
  "preassessment_id": "507f1f77bcf86cd799439011",
  "regulation_id": "6981ea4cb358c36d4be852be"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Webhook received successfully",
  "received_at": "2026-02-09T10:30:00.000000",
  "payload": {
    "organization_id": "682ae94fa2e778c597d09b57",
    "preassessment_id": "507f1f77bcf86cd799439011",
    "regulation_id": "6981ea4cb358c36d4be852be"
  }
}
```

### 2. View Received Webhooks
**GET** `/webhook/received`

Returns all received pre-assessment webhooks (stored in memory).

**Response:**
```json
{
  "total_received": 5,
  "webhooks": [
    {
      "timestamp": "2026-02-09T10:30:00.000000",
      "organization_id": "682ae94fa2e778c597d09b57",
      "preassessment_id": "507f1f77bcf86cd799439011",
      "regulation_id": "6981ea4cb358c36d4be852be"
    }
  ]
}
```

### 3. Clear Received Webhooks
**DELETE** `/webhook/received`

Clears all received webhooks from memory.

**Response:**
```json
{
  "status": "success",
  "message": "Cleared 5 webhooks"
}
```

## Testing

### Start the API
```bash
python -m uvicorn app.main:app --reload
```

### Run Test Script
```bash
python test_preassessment_webhook.py
```

### Manual Testing with cURL
```bash
# Send webhook
curl -X POST http://localhost:8000/webhook/preassessment \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "682ae94fa2e778c597d09b57",
    "preassessment_id": "507f1f77bcf86cd799439011",
    "regulation_id": "6981ea4cb358c36d4be852be"
  }'

# View received webhooks
curl http://localhost:8000/webhook/received

# Clear webhooks
curl -X DELETE http://localhost:8000/webhook/received
```

## Database Changes

### Pre-assessments Collection
The `circular_id` field has been renamed to `regulation_id` across all 1,728 documents in the `pre-assessments` collection.

**Updated Structure:**
```python
{
  "_id": ObjectId,
  "regulation_id": str,  # ✅ Renamed from circular_id
  "regulation_title": str,
  "assessment_date": str,
  "questions": [...],
  "assessment_score": str,
  "created_at": datetime,
  "batch_generated": bool
}
```

## Code Changes

### Updated Models
- `CircularIdRequest` → `RegulationIdRequest`
- `TaskGenerationRequest.circular_id` → `TaskGenerationRequest.regulation_id`
- Added `PreassessmentWebhookPayload` model

### Updated Endpoints
- `/api/v1/assessment/generate` - Now uses `regulation_id`
- `/api/v1/tasks/generate` - Now uses `regulation_id`
- `/webhook/preassessment` - New webhook receiver
- `/webhook/received` - View received webhooks
- `/webhook/received` (DELETE) - Clear webhooks

## Integration Notes

1. **Webhook Storage**: Webhooks are currently stored in memory. For production, consider persisting to database.

2. **Regulation ID**: The `regulation_id` field references documents in the `regulation_v3` collection.

3. **Organization ID**: Should match the organization ID from your RegComply system.

4. **Pre-assessment ID**: Should match the `_id` from the `pre-assessments` collection.
