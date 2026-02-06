# Task Generation API - Technical Report

## Executive Summary

This document provides a comprehensive technical overview of the Compliance Task Generation API endpoint, which automatically generates actionable compliance tasks from regulatory circulars using AI and sends them to the RegComply platform via webhook integration.

---

## 1. Overview

### 1.1 Purpose
The Task Generation API serves as a middleware service that:
- Receives webhook requests from RegWatch platform
- Fetches regulatory circular data from MongoDB
- Uses Azure OpenAI to generate compliance tasks
- Sends structured tasks to RegComply platform via webhook

### 1.2 Technology Stack
- **Framework:** FastAPI (Python)
- **Database:** MongoDB (Motor async driver)
- **AI Service:** Azure OpenAI (GPT-5 nano)
- **HTTP Client:** httpx (async)
- **Deployment:** Render.com (recommended)

---

## 2. API Endpoint Specification

### 2.1 Endpoint Details

**URL:** `POST /api/v1/tasks/generate`

**Content-Type:** `application/json`

**Authentication:** None (can be added if needed)

### 2.2 Request Schema

```json
{
  "organization_id": "string (required)",
  "risk": "string (optional, default: 'medium')",
  "circular_id": "string (required)"
}
```

**Field Descriptions:**

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| organization_id | string | Yes | RegComply organization identifier | "ORG-12345" |
| risk | string | No | Task risk level: "high", "medium", or "low" | "high" |
| circular_id | string | Yes | MongoDB ObjectId of the circular from regulation_v3 collection | "65a2b3c4d5e6f7g8h9i0j1k2" |

### 2.3 Response Schema

```json
{
  "company_name": "string",
  "circular_title": "string",
  "total_tasks": "integer",
  "tasks_sent_to_regcomply": "boolean",
  "tasks": [
    {
      "description": "string",
      "risk": "string",
      "instructions": [
        {
          "step": "string",
          "description": "string",
          "isCompleted": "boolean",
          "completedAt": "string|null"
        }
      ]
    }
  ]
}
```

### 2.4 HTTP Status Codes

| Code | Description |
|------|-------------|
| 200 | Success - Tasks generated and sent |
| 404 | Regulation not found |
| 500 | Internal server error |

---

## 3. System Architecture

### 3.1 Data Flow Diagram

```
┌─────────────────┐
│  RegWatch       │
│  Platform       │
└────────┬────────┘
         │ 1. Webhook Request
         │ (organization_id, risk, circular_id)
         ▼
┌─────────────────────────────────────────┐
│  Task Generation API                    │
│  (Your FastAPI Service)                 │
│                                         │
│  ┌─────────────────────────────────┐  │
│  │ 2. Fetch Circular Data          │  │
│  │    - title                       │  │
│  │    - compliance_deadline         │  │
│  │    - standards                   │  │
│  │    - extracted_text              │  │
│  └──────────┬──────────────────────┘  │
│             │                          │
│             ▼                          │
│  ┌─────────────────────────────────┐  │
│  │ 3. AI Task Generation           │  │
│  │    (Azure OpenAI GPT-5 nano)    │  │
│  │    - Analyze circular text      │  │
│  │    - Generate task descriptions │  │
│  │    - Create step-by-step        │  │
│  │      instructions               │  │
│  └──────────┬──────────────────────┘  │
│             │                          │
│             ▼                          │
│  ┌─────────────────────────────────┐  │
│  │ 4. Format Task Schema           │  │
│  │    - Combine DB data + AI data  │  │
│  │    - Structure for RegComply    │  │
│  └──────────┬──────────────────────┘  │
└─────────────┼──────────────────────────┘
              │ 5. Webhook POST
              │ (Task payload)
              ▼
┌─────────────────────────────────────────┐
│  RegComply Platform                     │
│  (Task Management System)               │
└─────────────────────────────────────────┘
```

### 3.2 Component Breakdown

#### 3.2.1 Webhook Receiver
- Validates incoming request
- Extracts organization_id, risk, and circular_id
- Returns 404 if circular not found

#### 3.2.2 Database Layer
- Connects to MongoDB (regulation_v3 collection)
- Fetches circular data using circular_id
- Extracts: title, compliance_deadline, standards, extracted_text

#### 3.2.3 AI Processing Layer
- Sends circular text to Azure OpenAI
- Generates 5-8 compliance tasks
- Each task includes:
  - Description (what needs to be done)
  - Instructions (3-5 step-by-step actions)

#### 3.2.4 Task Formatter
- Combines data from multiple sources:
  - organization_id (from webhook)
  - risk (from webhook)
  - title, dueDate, standards (from database)
  - description, instructions (from AI)
- Formats into RegComply schema

#### 3.2.5 Webhook Sender
- Sends each task to RegComply endpoint
- Includes authentication header if configured
- Handles errors gracefully

---

## 4. Database Schema

### 4.1 Source Collection: regulation_v3

**Database:** regwatch_staging

**Collection:** regulation_v3

**Relevant Fields:**

```javascript
{
  "_id": ObjectId,                    // Used as regulationId
  "title": String,                    // Used as task title
  "dates": {
    "compliance_deadline": Date       // Used as dueDate
  },
  "obligations": {
    "standards": [String]             // Used as standards array
  },
  "file_content": {
    "extracted_text": String          // Sent to AI for task generation
  }
}
```

---

## 5. RegComply Task Schema

### 5.1 Output Format

Each generated task is sent to RegComply with this structure:

```javascript
{
  "organization": String,        // From webhook input
  "title": String,               // From regulation_v3.title
  "description": String,         // Generated by AI
  "status": "pending",           // Hardcoded
  "risk": String,                // From webhook input
  "dueDate": Date,               // From regulation_v3.dates.compliance_deadline
  "standards": [String],         // From regulation_v3.obligations.standards
  "regulationId": String,        // From regulation_v3._id
  "instructions": [              // Generated by AI
    {
      "step": String,            // Step number (e.g., "1", "2")
      "description": String,     // What to do in this step
      "isCompleted": false,      // Default value
      "completedAt": null        // Default value
    }
  ]
}
```

### 5.2 Data Source Mapping

| Field | Source | Example |
|-------|--------|---------|
| organization | Webhook input | "ORG-12345" |
| title | regulation_v3.title | "AML/CFT Guidelines for PSPs" |
| description | AI Generated | "Implement transaction monitoring system" |
| status | Hardcoded | "pending" |
| risk | Webhook input | "high" |
| dueDate | regulation_v3.dates.compliance_deadline | "2026-06-30T00:00:00Z" |
| standards | regulation_v3.obligations.standards | ["ISO-27001", "PCI-DSS"] |
| regulationId | regulation_v3._id | "65a2b3c4d5e6f7g8h9i0j1k2" |
| instructions | AI Generated | [{"step": "1", "description": "..."}] |

---

## 6. AI Task Generation

### 6.1 AI Model Configuration

**Model:** Azure OpenAI GPT-5 nano
**Deployment:** regtech365-gpt-5-nano-prod
**API Version:** 2024-08-01-preview

### 6.2 AI Prompt Structure

The AI receives:
- Circular title
- Circular summary
- Complete circular text (extracted_text)
- Generic company profile (since no company data is provided)

The AI generates:
- 5-8 specific compliance tasks
- Each task has a description
- Each task has 3-5 step-by-step instructions
- Tasks are prioritized by regulatory importance

### 6.3 AI Response Format

```json
[
  {
    "description": "Appoint a Chief Compliance Officer with at least 5 years of AML/CFT experience",
    "risk": "high",
    "instructions": [
      {
        "step": "1",
        "description": "Review internal candidates or initiate external recruitment"
      },
      {
        "step": "2",
        "description": "Verify candidate has minimum 5 years AML/CFT experience"
      },
      {
        "step": "3",
        "description": "Obtain Board approval for CCO appointment"
      }
    ]
  }
]
```

### 6.4 AI Limitations

- **No temperature control:** GPT-5 nano only supports default temperature (1)
- **No max_tokens:** Parameter not supported, model decides response length
- **Text length:** Circular text limited to 15,000 characters for faster processing

---

## 7. Webhook Integration

### 7.1 Outgoing Webhook Configuration

**Environment Variables:**

```env
REGCOMPLY_WEBHOOK_URL=https://regcomply.example.com/api/webhooks/tasks
REGCOMPLY_WEBHOOK_SECRET=your_secret_key_here
```

### 7.2 Webhook Request

**Method:** POST
**Content-Type:** application/json
**Headers:**
```
Content-Type: application/json
X-Webhook-Secret: {REGCOMPLY_WEBHOOK_SECRET}
```

**Body:** Single task object (see section 5.1)

### 7.3 Webhook Behavior

- Each task is sent individually (not batched)
- If webhook URL is not configured, tasks are still generated but not sent
- Errors are logged but don't fail the main request
- Response indicates if tasks were successfully sent

---

## 8. Error Handling

### 8.1 Error Scenarios

| Scenario | HTTP Code | Response | Action |
|----------|-----------|----------|--------|
| Circular not found | 404 | `{"detail": "Regulation not found"}` | Check circular_id |
| Invalid circular_id format | 404 | `{"detail": "Regulation not found"}` | Verify ObjectId format |
| AI generation fails | 200 | Returns fallback tasks | Check AI service logs |
| Webhook send fails | 200 | `tasks_sent_to_regcomply: false` | Check webhook URL |
| Database connection fails | 500 | Internal server error | Check MongoDB connection |

### 8.2 Fallback Mechanism

If AI generation fails, the system returns a basic fallback task:

```json
{
  "description": "Review and implement all requirements outlined in: {circular_title}",
  "risk": "high",
  "instructions": [
    {"step": "1", "description": "Conduct comprehensive review of circular requirements"},
    {"step": "2", "description": "Identify gaps in current compliance status"},
    {"step": "3", "description": "Develop implementation plan with timelines"},
    {"step": "4", "description": "Execute compliance activities and document progress"}
  ]
}
```

---

## 9. Performance Considerations

### 9.1 Response Time

**Typical Response Time:** 5-15 seconds

**Breakdown:**
- Database query: 100-500ms
- AI generation: 3-10 seconds
- Webhook sending: 500-2000ms per task
- Total: 5-15 seconds (depending on number of tasks)

### 9.2 Optimization Strategies

1. **Text Truncation:** Circular text limited to 15,000 characters
2. **Async Operations:** All I/O operations are asynchronous
3. **Connection Pooling:** MongoDB uses connection pooling
4. **Parallel Webhook Sends:** Tasks sent concurrently (if needed)

### 9.3 Scalability

**Current Limitations:**
- AI generation is sequential (one circular at a time)
- Free tier on Render has limited resources
- Cold starts on Render free tier: 30-60 seconds

**Scaling Options:**
- Upgrade to paid Render plan for better performance
- Implement task queue (Celery/Redis) for async processing
- Cache frequently accessed circulars
- Batch webhook sends

---

## 10. Security Considerations

### 10.1 Current Security Measures

1. **Environment Variables:** Sensitive data stored in .env (not in code)
2. **Webhook Secret:** Optional authentication header for RegComply
3. **Input Validation:** Pydantic models validate all inputs
4. **HTTPS:** Enforced on Render deployment

### 10.2 Recommended Enhancements

1. **API Key Authentication:** Add API key requirement for webhook endpoint
2. **Rate Limiting:** Implement rate limiting to prevent abuse
3. **Request Signing:** Sign webhook requests for verification
4. **IP Whitelisting:** Restrict access to known IPs
5. **Audit Logging:** Log all task generation requests

---

## 11. Monitoring & Logging

### 11.1 Current Logging

The system logs:
- Database connection status
- AI generation errors
- Webhook send success/failure
- Task generation count

### 11.2 Recommended Monitoring

1. **Application Metrics:**
   - Request count
   - Response time
   - Error rate
   - AI generation success rate

2. **Infrastructure Metrics:**
   - CPU usage
   - Memory usage
   - Database connection pool

3. **Business Metrics:**
   - Tasks generated per day
   - Average tasks per circular
   - Webhook success rate

### 11.3 Logging Tools

- **Render Logs:** Built-in logging on Render dashboard
- **External:** Sentry, LogRocket, or Datadog (recommended for production)

---

## 12. Testing

### 12.1 Manual Testing

**Test Request:**

```bash
curl -X POST https://your-api.onrender.com/api/v1/tasks/generate \
  -H "Content-Type: application/json" \
  -d '{
    "organization_id": "ORG-12345",
    "risk": "high",
    "circular_id": "65a2b3c4d5e6f7g8h9i0j1k2"
  }'
```

**Expected Response:**

```json
{
  "company_name": "Financial Institution",
  "circular_title": "AML/CFT Guidelines for Payment Service Providers",
  "total_tasks": 6,
  "tasks_sent_to_regcomply": true,
  "tasks": [...]
}
```

### 12.2 Test Scenarios

| Test Case | Input | Expected Output |
|-----------|-------|-----------------|
| Valid request | Valid IDs | 200, tasks generated |
| Invalid circular_id | Non-existent ID | 404, regulation not found |
| Missing organization_id | No org ID | 422, validation error |
| Webhook disabled | No webhook URL | 200, tasks_sent_to_regcomply: false |

### 12.3 Integration Testing

1. **Database Test:** Verify circular data is fetched correctly
2. **AI Test:** Verify tasks are generated with proper structure
3. **Webhook Test:** Verify tasks are sent to RegComply
4. **End-to-End Test:** Complete flow from webhook input to RegComply

---

## 13. Deployment

### 13.1 Deployment Platform: Render.com

**Configuration:**

```yaml
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

**Environment Variables:**
- REGWATCH_MONGODB_URI
- ECOSYSTEM_MONGODB_URI
- AZURE_OPENAI_API_KEY
- AZURE_OPENAI_ENDPOINT
- AZURE_OPENAI_DEPLOYMENT
- AZURE_OPENAI_API_VERSION
- REGCOMPLY_WEBHOOK_URL
- REGCOMPLY_WEBHOOK_SECRET

### 13.2 Deployment URL

**Production:** `https://regwatch-ai-api.onrender.com/api/v1/tasks/generate`

**API Docs:** `https://regwatch-ai-api.onrender.com/docs`

### 13.3 Deployment Checklist

- [ ] Push code to GitHub
- [ ] Create Render web service
- [ ] Configure environment variables
- [ ] Set build and start commands
- [ ] Deploy and verify
- [ ] Test all endpoints
- [ ] Configure RegComply webhook URL
- [ ] Update RegWatch with webhook URL

---

## 14. Maintenance & Support

### 14.1 Regular Maintenance Tasks

1. **Weekly:**
   - Review error logs
   - Check webhook success rate
   - Monitor response times

2. **Monthly:**
   - Review AI prompt effectiveness
   - Update dependencies
   - Analyze task generation patterns

3. **Quarterly:**
   - Security audit
   - Performance optimization
   - Cost analysis

### 14.2 Troubleshooting Guide

**Issue:** Tasks not being sent to RegComply
- Check REGCOMPLY_WEBHOOK_URL is configured
- Verify webhook secret is correct
- Check RegComply endpoint is accessible
- Review webhook send logs

**Issue:** AI generating poor quality tasks
- Review circular text quality
- Check if text is truncated
- Adjust AI prompt if needed
- Verify AI model is responding

**Issue:** Slow response times
- Check database query performance
- Monitor AI generation time
- Verify webhook endpoint response time
- Consider upgrading Render plan

---

## 15. Future Enhancements

### 15.1 Short-term (1-3 months)

1. **Batch Processing:** Generate tasks for multiple circulars at once
2. **Task Prioritization:** AI-driven task priority ranking
3. **Webhook Retry Logic:** Automatic retry on webhook failure
4. **Caching:** Cache circular data for faster processing

### 15.2 Medium-term (3-6 months)

1. **Company-Specific Tasks:** Use company profile for tailored tasks
2. **Task Templates:** Pre-defined templates for common requirements
3. **Progress Tracking:** Track task completion status
4. **Analytics Dashboard:** Visualize task generation metrics

### 15.3 Long-term (6-12 months)

1. **Machine Learning:** Learn from task completion patterns
2. **Multi-language Support:** Support circulars in multiple languages
3. **Automated Testing:** Comprehensive test suite
4. **API Versioning:** Support multiple API versions

---

## 16. Conclusion

The Task Generation API successfully automates the creation of compliance tasks from regulatory circulars, reducing manual effort and ensuring comprehensive coverage of regulatory requirements. The system leverages AI to generate actionable, step-by-step tasks that are automatically delivered to the RegComply platform for execution and tracking.

### 16.1 Key Benefits

- **Automation:** Eliminates manual task creation
- **Consistency:** Ensures all requirements are covered
- **Speed:** Generates tasks in seconds
- **Integration:** Seamless webhook-based integration
- **Scalability:** Can handle multiple circulars and organizations

### 16.2 Success Metrics

- **Task Generation Time:** < 15 seconds per circular
- **AI Success Rate:** > 95%
- **Webhook Delivery Rate:** > 98%
- **System Uptime:** > 99%

---

## Appendix A: API Reference

### Complete Endpoint List

1. **POST /api/v1/tasks/generate** - Generate compliance tasks
2. **GET /health** - Health check
3. **GET /docs** - API documentation
4. **GET /** - API info

---

## Appendix B: Environment Variables

```env
# MongoDB Connections
REGWATCH_MONGODB_URI=mongodb+srv://...
ECOSYSTEM_MONGODB_URI=mongodb+srv://...

# Azure OpenAI
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_DEPLOYMENT=regtech365-gpt-5-nano-prod
AZURE_OPENAI_API_VERSION=2024-08-01-preview

# RegComply Webhook
REGCOMPLY_WEBHOOK_URL=https://regcomply.example.com/api/webhooks/tasks
REGCOMPLY_WEBHOOK_SECRET=...
```

---

## Appendix C: Code Structure

```
regwatch-ai-api/
├── app/
│   ├── __init__.py
│   ├── main.py              # Main API endpoints
│   ├── config.py            # Configuration management
│   └── database.py          # Database connections
├── .env                     # Environment variables (not in git)
├── .gitignore              # Git ignore rules
├── requirements.txt         # Python dependencies
└── TASK_GENERATION_TECHNICAL_REPORT.md
```

---

**Document Version:** 1.0  
**Last Updated:** February 2026  
**Author:** RegWatch AI Development Team  
**Status:** Production Ready
