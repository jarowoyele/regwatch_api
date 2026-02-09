from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from pydantic import BaseModel
from bson import ObjectId
from openai import AzureOpenAI
from datetime import datetime
from app.database import db, get_ecosystem_companies, get_regulations, get_pre_assessments
from app.config import get_settings


def serialize_doc(doc):
    """Convert MongoDB document to JSON-serializable format"""
    if doc is None:
        return None
    if isinstance(doc, list):
        return [serialize_doc(item) for item in doc]
    if isinstance(doc, dict):
        return {key: serialize_doc(value) for key, value in doc.items()}
    if isinstance(doc, ObjectId):
        return str(doc)
    return doc


# Azure OpenAI client
_client = None


def get_azure_client():
    """Get or create Azure OpenAI client"""
    global _client
    if _client is None:
        settings = get_settings()
        _client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
    return _client


async def generate_pre_assessment_questions(regulation_data: dict) -> list[dict]:
    """
    Use AI to generate pre-assessment questions from circular text
    
    Args:
        regulation_data: Dictionary containing regulation information
        
    Returns:
        List of pre-assessment questions
    """
    import json
    import re
    
    # Extract circular text - limit to 15000 characters for faster processing
    circular_text = regulation_data.get("file_content", {}).get("extracted_text", "")
    title = regulation_data.get("title", "")
    summary = regulation_data.get("description", {}).get("summary", "")
    
    # Limit text for faster processing
    if len(circular_text) > 15000:
        circular_text = circular_text[:15000] + "\n\n[Text truncated]"
    
    prompt = f"""You are a regulatory compliance expert specializing in financial services. Create 6 clear, personalized compliance questions based on this regulatory circular.

**CIRCULAR INFORMATION:**

Title: {title}

Summary: {summary}

Circular Text:
{circular_text}

**INSTRUCTIONS:**

1. **Base questions ONLY on explicit requirements in the circular**
   - Do NOT add questions from general knowledge
   - Focus on what the circular actually requires

2. **Make questions personalized and direct**
   - Use "you" and "your organization" to make questions feel personal
   - Frame questions as if speaking directly to the compliance officer
   - Each question should be answerable with Yes/No
   - Focus on specific, measurable requirements

3. **Cover these areas (if mentioned in circular):**
   - Reporting requirements (what to report, when, to whom)
   - Calculations or ratios to maintain
   - Limits or thresholds
   - Deadlines and timelines
   - Documentation requirements
   - Governance requirements (appointments, committees, etc.)

4. **Question format:**
   - Direct and conversational
   - Use second person ("Have you...", "Does your organization...", "Do you...")
   - No ambiguous language
   - Focus on "what" and "when"

**EXAMPLES OF GOOD PERSONALIZED QUESTIONS:**
- "Have you appointed a Chief Compliance Officer for your organization?"
- "Does your organization submit quarterly returns to CBN within 7 days after quarter-end?"
- "Is your Capital Adequacy Ratio maintained at or above 10%?"
- "Do you maintain customer records for at least 5 years?"
- "Has your Board of Directors approved the AML/CFT policy within the last 12 months?"
- "Have all your customer-facing staff received compliance training in the last year?"

**OUTPUT FORMAT:**
Return ONLY a JSON array:
[
  {{
    "question_id": "Q1",
    "question_text": "Clear, personalized question using 'you' or 'your organization'"
  }},
  {{
    "question_id": "Q2",
    "question_text": "Another personalized question"
  }}
]

Generate exactly 6 questions. Return ONLY the JSON array, no other text."""

    try:
        client = get_azure_client()
        settings = get_settings()
        
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a financial regulatory compliance expert specializing in Central Bank of Nigeria (CBN) regulations. Generate compliance questions in valid JSON format only."},
                {"role": "user", "content": prompt}
            ]
            # Note: temperature and max_tokens removed - GPT-5 nano uses defaults
        )
        
        result = response.choices[0].message.content.strip()
        
        # Log the raw response for debugging
        print(f"AI Response (first 500 chars): {result[:500]}")
        
        # Try to extract JSON if wrapped in markdown code blocks
        # Remove markdown code blocks if present
        if "```json" in result:
            json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
            if json_match:
                result = json_match.group(1)
        elif "```" in result:
            json_match = re.search(r'```\s*(.*?)\s*```', result, re.DOTALL)
            if json_match:
                result = json_match.group(1)
        
        # Parse JSON response
        questions = json.loads(result.strip())
        
        # Validate structure
        if not isinstance(questions, list):
            raise ValueError("Response is not a JSON array")
        
        if len(questions) == 0:
            raise ValueError("No questions generated")
        
        # Ensure each question has required fields
        for q in questions:
            if "question_id" not in q or "question_text" not in q:
                raise ValueError("Question missing required fields")
        
        print(f"✅ Successfully generated {len(questions)} questions")
        return questions
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"Raw response: {result[:1000]}")
        # Fallback: return basic questions
        return [
            {
                "question_id": "Q1",
                "question_text": f"Does your company comply with all requirements outlined in: {title}?"
            },
            {
                "question_id": "Q2",
                "question_text": "Have you reviewed this circular and assessed its applicability to your operations?"
            },
            {
                "question_id": "Q3",
                "question_text": "Do you have documented policies and procedures to ensure compliance with this circular?"
            },
            {
                "question_id": "Q4",
                "question_text": "Have relevant staff been trained on the requirements of this circular?"
            },
            {
                "question_id": "Q5",
                "question_text": "Do you have a monitoring system to track ongoing compliance with this circular?"
            },
            {
                "question_id": "Q6",
                "question_text": "Are compliance records maintained and accessible for regulatory inspection?"
            }
        ]
    except Exception as e:
        print(f"❌ Error generating questions: {type(e).__name__}: {e}")
        # Fallback: return basic questions
        return [
            {
                "question_id": "Q1",
                "question_text": f"Does your company comply with all requirements outlined in: {title}?"
            },
            {
                "question_id": "Q2",
                "question_text": "Have you reviewed this circular and assessed its applicability to your operations?"
            },
            {
                "question_id": "Q3",
                "question_text": "Do you have documented policies and procedures to ensure compliance with this circular?"
            },
            {
                "question_id": "Q4",
                "question_text": "Have relevant staff been trained on the requirements of this circular?"
            },
            {
                "question_id": "Q5",
                "question_text": "Do you have a monitoring system to track ongoing compliance with this circular?"
            },
            {
                "question_id": "Q6",
                "question_text": "Are compliance records maintained and accessible for regulatory inspection?"
            }
        ]


async def generate_compliance_tasks(regulation_data: dict, company_profile: dict) -> list[dict]:
    """
    Use AI to generate compliance tasks from circular requirements
    
    Args:
        regulation_data: Dictionary containing regulation information
        company_profile: Dictionary containing company information
        
    Returns:
        List of compliance tasks with instructions
    """
    import json
    
    # Extract circular text - USE ALL OF IT
    circular_text = regulation_data.get("file_content", {}).get("extracted_text", "")
    title = regulation_data.get("title", "")
    summary = regulation_data.get("description", {}).get("summary", "")
    
    prompt = f"""You are a Nigerian regulatory compliance expert. Analyze this circular and generate 5-8 specific compliance tasks that a company must complete to achieve full compliance.

Circular Title: {title}

Summary: {summary}

Complete Circular Text:
{circular_text}

Company Profile:
- Name: {company_profile.get('name', 'N/A')}
- Industry: {company_profile.get('industry', 'N/A')}
- Business Category: {company_profile.get('businessCategory', 'N/A')}
- Services: {', '.join(company_profile.get('services', []))}

CRITICAL INSTRUCTIONS:
1. Generate 5-8 specific, actionable compliance tasks
2. Each task should address a major requirement from the circular
3. Prioritize tasks by risk level: "high", "medium", or "low"
4. Break down each task into 3-5 step-by-step instructions
5. Make instructions concrete and implementable
6. Include specific deadlines, thresholds, or requirements mentioned in the circular
7. Focus on what the company must DO to comply

TASK STRUCTURE:
- description: Clear description of what needs to be done
- risk: "high", "medium", or "low" based on regulatory importance
- instructions: Array of 3-5 steps with step number and description

EXAMPLES OF GOOD TASKS:

Task 1:
- description: "Appoint a Chief Compliance Officer with at least 5 years of AML/CFT experience"
- risk: "high"
- instructions:
  1. Review internal candidates or initiate external recruitment for CCO position
  2. Verify candidate has minimum 5 years AML/CFT experience and relevant certifications
  3. Obtain Board approval for CCO appointment
  4. Submit CCO appointment notification to CBN within 7 days
  5. Ensure CCO has direct reporting line to Board of Directors

Task 2:
- description: "Implement real-time transaction monitoring system to flag suspicious activities"
- risk: "high"
- instructions:
  1. Procure transaction monitoring software that meets CBN technical specifications
  2. Configure system to flag transactions above N5,000,000 for individuals
  3. Set up automated alerts for suspicious patterns (structuring, rapid movement)
  4. Train compliance team on system usage and alert investigation
  5. Conduct system testing and obtain CBN approval before go-live

Format your response as a JSON array:
[
  {{
    "description": "Task description here",
    "risk": "high",
    "instructions": [
      {{
        "step": "1",
        "description": "First step description"
      }},
      {{
        "step": "2",
        "description": "Second step description"
      }}
    ]
  }}
]

Return ONLY the JSON array, no additional text."""

    try:
        client = get_azure_client()
        settings = get_settings()
        
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a Nigerian regulatory compliance expert. Generate specific, actionable compliance tasks with step-by-step instructions. Respond only with valid JSON."},
                {"role": "user", "content": prompt}
            ]
            # Note: temperature and max_tokens removed - GPT-5 nano uses defaults
        )
        
        result = response.choices[0].message.content.strip()
        
        # Parse JSON response
        tasks = json.loads(result)
        
        return tasks
        
    except Exception as e:
        print(f"Error generating tasks: {e}")
        # Fallback: return basic task
        return [
            {
                "description": f"Review and implement all requirements outlined in: {title}",
                "risk": "high",
                "instructions": [
                    {
                        "step": "1",
                        "description": "Conduct comprehensive review of circular requirements"
                    },
                    {
                        "step": "2",
                        "description": "Identify gaps in current compliance status"
                    },
                    {
                        "step": "3",
                        "description": "Develop implementation plan with timelines"
                    },
                    {
                        "step": "4",
                        "description": "Execute compliance activities and document progress"
                    }
                ]
            }
        ]


async def send_tasks_to_regcomply(tasks_payload: dict) -> bool:
    """
    Send generated tasks to RegComply platform via webhook
    
    Args:
        tasks_payload: Dictionary containing task data for RegComply
        
    Returns:
        Boolean indicating success or failure
    """
    import httpx
    
    settings = get_settings()
    
    if not settings.REGCOMPLY_WEBHOOK_URL:
        print("⚠️ RegComply webhook URL not configured, skipping webhook")
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Content-Type": "application/json"
            }
            
            # Add secret if configured
            if settings.REGCOMPLY_WEBHOOK_SECRET:
                headers["X-Webhook-Secret"] = settings.REGCOMPLY_WEBHOOK_SECRET
            
            response = await client.post(
                settings.REGCOMPLY_WEBHOOK_URL,
                json=tasks_payload,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code in [200, 201, 202]:
                print(f"✅ Tasks sent to RegComply successfully")
                return True
            else:
                print(f"❌ RegComply webhook failed with status {response.status_code}: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Error sending tasks to RegComply: {e}")
        return False


async def ai_filter_circulars(company_profile: dict, circulars: list) -> list:
    """Use AI to filter circulars for relevance to company"""
    
    if not circulars:
        return []
    
    # Build a batch prompt for efficiency
    circulars_text = ""
    for idx, circular in enumerate(circulars):
        circulars_text += f"\n{idx + 1}. Title: {circular.get('title', 'N/A')}\n"
        circulars_text += f"   Summary: {circular.get('description', {}).get('summary', 'N/A')[:200]}...\n"
        circulars_text += f"   Affected Entities: {', '.join(circular.get('affected_entities', [])[:5])}\n"
        circulars_text += f"   Tags: {', '.join(circular.get('tags', [])[:10])}\n"
    
    prompt = f"""You are a Nigerian regulatory compliance expert. Analyze which circulars are relevant to this company.

Company Profile:
- Name: {company_profile.get('name', 'N/A')}
- Industry: {company_profile.get('industry', 'N/A')}
- Business Category: {company_profile.get('businessCategory', 'N/A')}
- Services: {', '.join(company_profile.get('services', []))}
- Description: {company_profile.get('description', 'N/A')[:200]}

Circulars to Analyze:
{circulars_text}

Instructions:
1. Determine which circulars are DIRECTLY relevant to this company's operations
2. Consider the company's industry, services, and business activities
3. Return ONLY the numbers of relevant circulars as a comma-separated list (e.g., "1, 3, 5, 7")
4. If none are relevant, return "NONE"
5. Do not include explanations

Response (comma-separated numbers only):"""

    try:
        client = get_azure_client()
        settings = get_settings()
        
        response = client.chat.completions.create(
            model=settings.AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": "You are a regulatory compliance expert. Respond only with comma-separated numbers."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=200
        )
        
        result = response.choices[0].message.content.strip()
        
        if result.upper() == "NONE":
            return []
        
        # Parse the numbers
        relevant_indices = [int(num.strip()) - 1 for num in result.split(',') if num.strip().isdigit()]
        
        # Return the relevant circulars
        return [circulars[idx] for idx in relevant_indices if 0 <= idx < len(circulars)]
        
    except Exception as e:
        print(f"Error in AI filtering: {e}")
        # Fallback: return all circulars if AI fails
        return circulars


async def suggest_regulators(company_profile: dict) -> list[str]:
    """Use Azure OpenAI to suggest relevant regulators based on company profile"""
    
    regulators = {
        "CBN": "Central Bank of Nigeria - Regulates banks, payment service providers, fintech, and financial institutions",
        "NDPC": "Nigeria Data Protection Commission - Regulates data protection and privacy compliance",
        "NDIC": "Nigeria Deposit Insurance Corporation - Regulates deposit-taking institutions",
        "SEC": "Securities and Exchange Commission - Regulates capital markets, investments, securities",
        "FCCPC": "Federal Competition and Consumer Protection Commission - Regulates consumer protection and fair competition",
        "EFCC": "Economic and Financial Crimes Commission - Regulates anti-money laundering and financial crimes prevention",
        "NAICOM": "National Insurance Commission - Regulates insurance companies and related services"
    }
    
    prompt = f"""You are a Nigerian regulatory compliance expert. Based on the company profile below, suggest which regulators are relevant.

Company Profile:
- Industry: {company_profile.get('industry', 'N/A')}
- Business Category: {company_profile.get('businessCategory', 'N/A')}
- Business Sub-Category: {company_profile.get('businessSubCategory', 'N/A')}
- Services: {', '.join(company_profile.get('services', []))}
- Category: {company_profile.get('category', 'N/A')}
- Description: {company_profile.get('description', 'N/A')}
- Country: {company_profile.get('country', 'N/A')}

Available Regulators:
{chr(10).join([f"- {code}: {desc}" for code, desc in regulators.items()])}

Instructions:
1. Analyze the company's industry, services, and business activities
2. Suggest ONLY the regulators that are directly relevant to this company
3. Return ONLY the regulator codes as a comma-separated list (e.g., "CBN, NDPC, FCCPC")
4. Do not include explanations or additional text
5. If the company operates in Nigeria and handles financial services, CBN is likely relevant
6. If they handle customer data, NDPC is relevant
7. If they take deposits, NDIC is relevant
8. If they deal with securities/investments, SEC is relevant
9. If they provide insurance, NAICOM is relevant

Response (comma-separated regulator codes only):"""

    client = get_azure_client()
    settings = get_settings()
    
    response = client.chat.completions.create(
        model=settings.AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You are a Nigerian regulatory compliance expert. Respond only with comma-separated regulator codes."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=100
    )
    
    suggested = response.choices[0].message.content.strip()
    regulator_codes = [code.strip() for code in suggested.split(',')]
    valid_codes = [code for code in regulator_codes if code in regulators]
    
    return valid_codes if valid_codes else []


# FastAPI app setup
@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    yield
    await db.close()


app = FastAPI(
    title="RegWatch AI API",
    description="AI-powered regulatory compliance platform",
    version="1.0.0",
    lifespan=lifespan
)


# Response models
class RegulatorSuggestionResponse(BaseModel):
    company_name: str
    suggested_regulators: list[str]


class CircularMatchResponse(BaseModel):
    company_name: str
    total_relevant_circulars: int
    circulars: list[dict]


class PreAssessmentQuestion(BaseModel):
    question_id: str
    question_text: str
    answer: str  # Empty initially, will be "Yes", "No", or "Not Applicable"


class PreAssessmentResponse(BaseModel):
    assessment_id: str
    regulation_title: str
    assessment_date: str
    total_questions: int
    questions: list[PreAssessmentQuestion]
    assessment_score: str  # Empty initially, will be calculated after answers


class CompanyIdRequest(BaseModel):
    company_id: str  # Only ecosystem company ID needed


class RegulationIdRequest(BaseModel):
    regulation_id: str  # The MongoDB _id from regulation_v3 collection


class TaskGenerationRequest(BaseModel):
    organization_id: str  # RegComply organization ID (from webhook)
    risk: str = "medium"  # Risk level: "high", "medium", or "low" (from webhook)
    regulation_id: str  # The MongoDB _id from regulation_v3 collection (from webhook)


class PreassessmentWebhookPayload(BaseModel):
    """Pre-assessment webhook payload structure"""
    organization_id: str
    preassessment_id: str
    regulation_id: str


class TaskInstruction(BaseModel):
    step: str
    description: str
    isCompleted: bool = False
    completedAt: str = None


class ComplianceTask(BaseModel):
    description: str
    risk: str
    instructions: list[TaskInstruction]


class TaskBreakdownResponse(BaseModel):
    company_name: str
    circular_title: str
    total_tasks: int
    tasks_sent_to_regcomply: bool
    tasks: list[ComplianceTask]


# Routes
@app.get("/")
async def root():
    return {
        "message": "RegWatch AI API",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "suggest_regulators": "/api/v1/regulators/suggest/{company_id}",
            "match_circulars": "/api/v1/circulars/match",
            "generate_assessment": "/api/v1/assessment/generate",
            "generate_tasks": "/api/v1/tasks/generate",
            "preassessment_webhook": "POST /webhook/preassessment",
            "view_webhooks": "GET /webhook/received",
            "clear_webhooks": "DELETE /webhook/received"
        }
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "databases": {
            "regwatch": "connected",
            "ecosystem": "connected"
        }
    }


@app.get("/test/regulations")
async def test_regulations():
    """Test endpoint to check regulation_v3 collection"""
    collection = get_regulations()
    
    # Get total count
    count = await collection.count_documents({})
    
    # Get first 2 documents as sample
    sample_docs = await collection.find().limit(2).to_list(length=2)
    
    # Get one document with all fields to see structure
    one_doc = await collection.find_one({})
    
    return {
        "collection": "regulation_v3",
        "database": "regwatch_staging",
        "total_documents": count,
        "sample_count": len(sample_docs),
        "sample_documents": serialize_doc(sample_docs),
        "document_structure": list(one_doc.keys()) if one_doc else []
    }


@app.post("/api/v1/assessment/generate", response_model=PreAssessmentResponse)
async def generate_assessment_questions(request: RegulationIdRequest):
    """
    Generate pre-assessment questions for a specific regulation and save to database
    
    Args:
        request: RegulationIdRequest with regulation_id (MongoDB _id)
        
    Returns:
        Pre-assessment questions saved to database
    """
    
    # Fetch regulation from database using _id
    regulations_collection = get_regulations()
    try:
        regulation = await regulations_collection.find_one({"_id": ObjectId(request.regulation_id)})
    except:
        regulation = await regulations_collection.find_one({"_id": request.regulation_id})
    
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found")
    
    # Generate questions using AI
    questions = await generate_pre_assessment_questions(regulation)
    
    # Format questions with empty answers
    formatted_questions = []
    for q in questions:
        formatted_questions.append({
            "question_id": q.get("question_id", ""),
            "question_text": q.get("question_text", ""),
            "answer": ""  # Empty answer initially
        })
    
    # Create assessment document
    assessment_doc = {
        "regulation_title": regulation.get("title", ""),
        "assessment_date": datetime.utcnow().isoformat() + "Z",
        "questions": formatted_questions,
        "assessment_score": ""  # Empty score initially
    }
    
    # Save to database
    pre_assessments_collection = get_pre_assessments()
    result = await pre_assessments_collection.insert_one(assessment_doc)
    
    # Add _id to response
    assessment_doc["_id"] = str(result.inserted_id)
    
    # Format response
    response_questions = []
    for q in formatted_questions:
        response_questions.append(PreAssessmentQuestion(
            question_id=q["question_id"],
            question_text=q["question_text"],
            answer=q["answer"]
        ))
    
    return PreAssessmentResponse(
        assessment_id=assessment_doc["_id"],
        regulation_title=assessment_doc["regulation_title"],
        assessment_date=assessment_doc["assessment_date"],
        total_questions=len(response_questions),
        questions=response_questions,
        assessment_score=assessment_doc["assessment_score"]
    )


@app.post("/api/v1/circulars/match", response_model=CircularMatchResponse)
async def match_circulars_for_company(request: CompanyIdRequest):
    """
    Match relevant circulars/regulations for a company using hybrid approach
    
    Args:
        request: CompanyIdRequest with company_id
        
    Returns:
        Company name and list of relevant circulars
    """
    
    # Fetch company data from ecosystem database
    ecosystem_collection = get_ecosystem_companies()
    try:
        ecosystem_data = await ecosystem_collection.find_one({"_id": ObjectId(request.company_id)})
    except:
        ecosystem_data = await ecosystem_collection.find_one({"_id": request.company_id})
    
    if not ecosystem_data:
        raise HTTPException(status_code=404, detail="Company not found in ecosystem database")
    
    # Build company profile
    company_profile = {
        "name": ecosystem_data.get("name", "Unknown Company"),
        "industry": ecosystem_data.get("industry", ""),
        "businessCategory": ecosystem_data.get("businessCategory", ""),
        "businessSubCategory": ecosystem_data.get("businessSubCategory", ""),
        "services": ecosystem_data.get("services", []),
        "description": ecosystem_data.get("description", ""),
        "country": ecosystem_data.get("country", {}).get("name", "Nigeria"),
    }
    
    # Get suggested regulators
    suggested_regulators = await suggest_regulators(company_profile)
    company_profile["suggested_regulators"] = suggested_regulators
    
    # STAGE 1: MongoDB Query (Fast Filter)
    regulations_collection = get_regulations()
    
    # Build search keywords from company profile
    search_keywords = []
    
    # Add industry keywords
    if company_profile.get("industry"):
        search_keywords.append(company_profile["industry"].lower())
    
    # Add business category keywords
    if company_profile.get("businessCategory"):
        search_keywords.append(company_profile["businessCategory"].lower())
    
    # Add service keywords
    for service in company_profile.get("services", []):
        search_keywords.extend(service.lower().split())
    
    # Remove duplicates and common words
    search_keywords = list(set([kw for kw in search_keywords if len(kw) > 3]))
    
    # Build MongoDB query
    mongo_query = {
        "$or": [
            # Match by regulator code
            {"regulator.code": {"$in": suggested_regulators}},
            
            # Match by tags (case-insensitive)
            {"tags": {"$in": search_keywords}},
            
            # Match by affected entities (regex for flexibility)
            {"affected_entities": {
                "$regex": "|".join(search_keywords[:5]),  # Limit to top 5 keywords
                "$options": "i"
            }} if search_keywords else {"affected_entities": {"$exists": True}}
        ]
    }
    
    # Execute MongoDB query
    candidate_circulars = await regulations_collection.find(mongo_query).to_list(length=None)
    
    print(f"Stage 1 (MongoDB): Found {len(candidate_circulars)} candidate circulars")
    
    # STAGE 2: AI Filter (Accurate)
    if len(candidate_circulars) > 0:
        relevant_circulars = await ai_filter_circulars(company_profile, candidate_circulars)
        print(f"Stage 2 (AI): Filtered to {len(relevant_circulars)} relevant circulars")
    else:
        relevant_circulars = []
    
    # Serialize and return
    return CircularMatchResponse(
        company_name=company_profile["name"],
        total_relevant_circulars=len(relevant_circulars),
        circulars=serialize_doc(relevant_circulars)
    )


@app.post("/api/v1/regulators/suggest", response_model=RegulatorSuggestionResponse)
async def suggest_regulators_for_company(request: CompanyIdRequest):
    """
    Suggest relevant regulators for a company based on their profile
    
    Args:
        request: CompanyIdRequest with company_id
        
    Returns:
        Company name and list of suggested regulator codes
    """
    
    # Fetch from ecosystem database
    ecosystem_collection = get_ecosystem_companies()
    try:
        ecosystem_data = await ecosystem_collection.find_one({"_id": ObjectId(request.company_id)})
    except:
        ecosystem_data = await ecosystem_collection.find_one({"_id": request.company_id})
    
    if not ecosystem_data:
        raise HTTPException(status_code=404, detail="Company not found in ecosystem database")
    
    # Build company profile for AI
    company_profile = {
        "industry": ecosystem_data.get("industry", ""),
        "businessCategory": ecosystem_data.get("businessCategory", ""),
        "businessSubCategory": ecosystem_data.get("businessSubCategory", ""),
        "services": ecosystem_data.get("services", []),
        "description": ecosystem_data.get("description", ""),
        "country": ecosystem_data.get("country", {}).get("name", "Nigeria"),
    }
    
    # Get AI suggestions
    suggested = await suggest_regulators(company_profile)
    
    return RegulatorSuggestionResponse(
        company_name=ecosystem_data.get("name", "Unknown Company"),
        suggested_regulators=suggested
    )


@app.post("/api/v1/tasks/generate", response_model=TaskBreakdownResponse)
async def generate_compliance_task_breakdown(request: TaskGenerationRequest):
    """
    Generate compliance tasks for a circular and send to RegComply
    
    Webhook receives: organization_id, risk, regulation_id
    Fetches from DB: title, dueDate, standards
    AI generates: description, instructions
    
    Args:
        request: TaskGenerationRequest with organization_id, risk, regulation_id
        
    Returns:
        Generated compliance tasks
    """
    
    # Fetch regulation from database using regulation_id
    regulations_collection = get_regulations()
    try:
        regulation = await regulations_collection.find_one({"_id": ObjectId(request.regulation_id)})
    except:
        regulation = await regulations_collection.find_one({"_id": request.regulation_id})
    
    if not regulation:
        raise HTTPException(status_code=404, detail="Regulation not found")
    
    # Extract data from regulation for task schema
    circular_title = regulation.get("title", "")
    regulation_id = str(regulation.get("_id"))
    
    # Get compliance deadline from regulation
    compliance_deadline = regulation.get("dates", {}).get("compliance_deadline")
    if compliance_deadline:
        # Convert to ISO format if it's a datetime object
        if hasattr(compliance_deadline, 'isoformat'):
            due_date = compliance_deadline.isoformat() + "Z"
        else:
            due_date = compliance_deadline
    else:
        # Default to 90 days from now if no deadline specified
        from datetime import timedelta
        default_deadline = datetime.utcnow() + timedelta(days=90)
        due_date = default_deadline.isoformat() + "Z"
    
    # Get standards from regulation obligations (extract from mapped_standards)
    standards = []
    obligations = regulation.get("obligations", [])
    for obligation in obligations:
        mapped_standards = obligation.get("mapped_standards", [])
        for standard in mapped_standards:
            standard_name = standard.get("standard_name", "")
            if standard_name and standard_name not in standards:
                standards.append(standard_name)
    
    # Build minimal profile for AI (no company data needed)
    company_profile = {
        "name": "Financial Institution",  # Generic since we don't have company data
        "industry": "Financial Services",
        "businessCategory": "Regulated Entity",
        "services": [],
        "description": ""
    }
    
    # Generate tasks using AI (description + instructions)
    ai_tasks = await generate_compliance_tasks(regulation, company_profile)
    
    # Format tasks for RegComply and response
    formatted_tasks = []
    regcomply_tasks = []
    
    for task in ai_tasks:
        # Format instructions
        instructions = []
        for inst in task.get("instructions", []):
            instructions.append({
                "step": inst.get("step", ""),
                "description": inst.get("description", ""),
                "isCompleted": False,
                "completedAt": None
            })
        
        # Add to response format
        formatted_tasks.append(ComplianceTask(
            description=task.get("description", ""),
            risk=request.risk,  # Use risk from webhook
            instructions=[TaskInstruction(**inst) for inst in instructions]
        ))
        
        # Add to RegComply format
        regcomply_tasks.append({
            "organization": request.organization_id,  # From webhook
            "title": circular_title,  # From regulation_v3
            "description": task.get("description", ""),  # From AI
            "status": "pending",
            "risk": request.risk,  # From webhook
            "dueDate": due_date,  # From regulation_v3
            "standards": standards,  # From regulation_v3
            "regulationId": regulation_id,  # From regulation_v3
            "instructions": instructions  # From AI
        })
    
    # Send to RegComply via webhook
    webhook_success = False
    if regcomply_tasks:
        # Send each task individually
        for task_payload in regcomply_tasks:
            success = await send_tasks_to_regcomply(task_payload)
            if success:
                webhook_success = True
    
    return TaskBreakdownResponse(
        company_name="Financial Institution",  # Generic since no company data
        circular_title=circular_title,
        total_tasks=len(formatted_tasks),
        tasks_sent_to_regcomply=webhook_success,
        tasks=formatted_tasks
    )



# ============================================================================
# PRE-ASSESSMENT WEBHOOK ENDPOINTS
# ============================================================================

# Store received webhooks in memory (for testing/debugging)
received_preassessment_webhooks = []


@app.post("/webhook/preassessment")
async def receive_preassessment_webhook(payload: PreassessmentWebhookPayload):
    """
    Receive webhook for pre-assessment
    
    Expected payload:
    {
        "organization_id": "682ae94fa2e778c597d09b57",
        "preassessment_id": "507f1f77bcf86cd799439011",
        "regulation_id": "6981ea4cb358c36d4be852be"
    }
    
    Returns:
        Confirmation of webhook receipt
    """
    try:
        print("=" * 80)
        print("PRE-ASSESSMENT WEBHOOK RECEIVED")
        print("=" * 80)
        print(f"Timestamp: {datetime.utcnow().isoformat()}")
        print(f"Organization ID: {payload.organization_id}")
        print(f"Pre-assessment ID: {payload.preassessment_id}")
        print(f"Regulation ID: {payload.regulation_id}")
        
        # Store webhook
        webhook_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "organization_id": payload.organization_id,
            "preassessment_id": payload.preassessment_id,
            "regulation_id": payload.regulation_id
        }
        received_preassessment_webhooks.append(webhook_data)
        
        print("=" * 80)
        print("WEBHOOK RECEIVED SUCCESSFULLY")
        print("=" * 80)
        
        return {
            "status": "success",
            "message": "Webhook received successfully",
            "received_at": datetime.utcnow().isoformat(),
            "payload": {
                "organization_id": payload.organization_id,
                "preassessment_id": payload.preassessment_id,
                "regulation_id": payload.regulation_id
            }
        }
        
    except Exception as e:
        print(f"❌ Error processing webhook: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process webhook: {str(e)}"
        )


@app.get("/webhook/received")
async def get_received_webhooks():
    """View all received pre-assessment webhooks"""
    return {
        "total_received": len(received_preassessment_webhooks),
        "webhooks": received_preassessment_webhooks
    }


@app.delete("/webhook/received")
async def clear_received_webhooks():
    """Clear all received pre-assessment webhooks"""
    global received_preassessment_webhooks
    count = len(received_preassessment_webhooks)
    received_preassessment_webhooks = []
    return {
        "status": "success",
        "message": f"Cleared {count} webhooks"
    }
