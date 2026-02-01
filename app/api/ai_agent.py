from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from typing import Optional, List
import google.generativeai as genai
import asyncio
import json
from datetime import datetime
from app.core.config import settings
from app.api.auth import get_current_user
from app.core.database import get_db
from bson import ObjectId
import pandas as pd
from pydantic import BaseModel

# allow using the shared Gemini ESG service for orchestrated actions
from app.services.gemini_esg import get_gemini_esg_service

router = APIRouter()

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

class ReportRequest(BaseModel):
    file_ids: List[str]
    report_type: str
    custom_prompt: Optional[str] = None
    timeframe: Optional[str] = None


class AssistantRequest(BaseModel):
    instruction: Optional[str] = None
    template_key: Optional[str] = None
    template_prompt: Optional[str] = None
    clientId: Optional[str] = None
    companyProfile: Optional[dict] = None
    runActions: Optional[bool] = True


async def _render_template(template_text: str, ctx: dict) -> str:
    # very small, safe placeholder replacement — do NOT exec arbitrary code
    out = template_text
    for k, v in ctx.items():
        out = out.replace(f"{{{{{k}}}}}", str(v or ''))
    return out



@router.get('/templates/{portfolio_id}')
async def list_templates(portfolio_id: str, current_user = Depends(get_current_user), db = Depends(get_db)):
    """Return public AI prompt templates for a portfolio and any user-specific drafts."""
    try:
        public_templates = await db.ai_templates.find({'portfolio_id': portfolio_id, 'is_public': True}).to_list(50)
        user_templates = []
        if current_user:
            user_templates = await db.ai_templates.find({'portfolio_id': portfolio_id, 'created_by': getattr(current_user, 'username', None)}).to_list(50)
        # merge, prefer user templates with same key
        combined = {t['key']: t for t in public_templates}
        for t in user_templates:
            combined[t['key']] = t
        return {'templates': [_json_safe(t) for t in combined.values()]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get('/templates/{portfolio_id}/public')
async def list_templates_public(portfolio_id: str, db = Depends(get_db)):
    """Return public AI prompt templates for a portfolio (no auth required)."""
    try:
        public_templates = await db.ai_templates.find({'portfolio_id': portfolio_id, 'is_public': True}).to_list(50)
        return {'templates': [_json_safe(t) for t in public_templates]}
    except Exception as e:
        # Return empty templates list on error to avoid breaking frontend
        return {'templates': []}

@router.get('/status')
async def ai_status(db: any = Depends(get_db), probe: Optional[bool] = False):
    """Return AI status for the frontend.

    - If `probe=true` the handler will attempt a lightweight Gemini call to verify connectivity
      and return `probe_ok` and an optional `probe_error` (safe for debugging).
    - The probe only runs when a key is configured to avoid unnecessary external calls.
    """
    try:
        gemini = get_gemini_esg_service()
        enabled = not getattr(gemini, 'mock_mode', True)
        model = getattr(gemini, 'model_name', None) or (settings.GEMINI_MODEL_ESG if getattr(settings, 'GEMINI_API_KEY', None) else None)

        templates_count = 0
        try:
            templates_count = await db.ai_templates.count_documents({})
        except Exception:
            templates_count = 0

        resp = {
            'enabled': bool(enabled),
            'model': model,
            'templates_count': int(templates_count),
            'probe_ok': None,
            'probe_error': None,
        }

        # Only run an external probe when explicitly requested (or when DEBUG and enabled)
        do_probe = bool(probe) or (settings.DEBUG and enabled)
        if do_probe and enabled:
            try:
                # lightweight prompt that should be safe and fast
                test_prompt = 'Provide the single word: READY'
                result = await gemini.model.generate_content(test_prompt)
                text = getattr(result, 'text', '') or str(result)
                resp['probe_ok'] = 'READY' in text.upper() or len(text.strip()) > 0
            except Exception as e:
                resp['probe_ok'] = False
                resp['probe_error'] = str(e)

        return resp
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/assistant')
async def run_ai_assistant(request: AssistantRequest, current_user = Depends(get_current_user), db = Depends(get_db)):
    """Lightweight AI agent — supports templates and direct instructions.

    Priority: template_key -> template_prompt -> instruction
    """
    gemini = get_gemini_esg_service()

    # Resolve instruction from template if provided
    instruction = (request.instruction or '')
    used_template = None

    if request.template_key and request.clientId:
        # try to load template for portfolio (template_key is a short slug)
        tmpl = await db.ai_templates.find_one({
            'portfolio_id': request.clientId,
            'key': request.template_key,
            'is_public': True
        })
        if tmpl:
            used_template = tmpl
            instruction = await _render_template(tmpl.get('prompt', ''), {
                'portfolio_name': tmpl.get('portfolio_id'),
                'user': getattr(current_user, 'username', None),
            })

    # template_prompt overrides
    if request.template_prompt:
        instruction = request.template_prompt

    # fallback to the simple instruction field
    if not instruction and request.instruction:
        instruction = request.instruction

    instr = (instruction or '').lower()

    # Try to enrich company profile from DB when clientId provided
    company_profile = request.companyProfile or {}
    if request.clientId and not company_profile:
        client = await db.users.find_one({'username': request.clientId})
        if client:
            company_profile = client.get('company') or {
                'name': client.get('full_name') or client.get('username')
            }

    # Intent: generate report
    if 'report' in instr or 'generate report' in instr or 'create report' in instr:
        report_type = 'comprehensive'
        if 'environment' in instr or 'carbon' in instr:
            report_type = 'environmental'

        result = await gemini.generate_ai_report(company_profile or {'name': request.clientId or 'unknown'}, report_type)
        return {
            'action': 'generate_report',
            'report_type': report_type,
            'used_template': used_template and used_template.get('key'),
            'result': result
        }

    # Intent: recommendations / improve
    if 'recommend' in instr or 'improv' in instr or 'optimization' in instr:
        result = await gemini.generate_recommendations(company_profile or {'name': request.clientId or 'unknown'})
        return {
            'action': 'recommendations',
            'used_template': used_template and used_template.get('key'),
            'result': result
        }

    # Fallback: chat / clarification
    try:
        chat_response = await gemini.chat(instruction)
        return {
            'action': 'chat',
            'used_template': used_template and used_template.get('key'),
            'result': chat_response
        }
    except Exception:
        # If Gemini not available, return a helpful mock
        return {
            'action': 'chat',
            'result': {
                'answer': "I'm unable to reach the AI service — try: 'generate report for <clientId>' or 'recommendations for reducing carbon'.",
                'model': 'mock',
                'confidence': 0.5
            }
        }

@router.post('/assistant-public')
async def run_ai_assistant_public(request: AssistantRequest, db = Depends(get_db)):
    """Public AI assistant endpoint (no auth required)"""
    # This allows the frontend to work without authentication
    gemini = get_gemini_esg_service()

    # Resolve instruction from template if provided
    instruction = (request.instruction or '')
    used_template = None

    if request.template_key and request.clientId:
        # try to load template for portfolio (template_key is a short slug)
        tmpl = await db.ai_templates.find_one({
            'portfolio_id': request.clientId,
            'key': request.template_key,
            'is_public': True
        })
        if tmpl:
            used_template = tmpl
            instruction = await _render_template(tmpl.get('prompt', ''), {
                'portfolio_name': tmpl.get('portfolio_id'),
                'user': 'public',
            })

    # template_prompt overrides
    if request.template_prompt:
        instruction = request.template_prompt

    # fallback to the simple instruction field
    if not instruction and request.instruction:
        instruction = request.instruction

    instr = (instruction or '').lower()

    # Use default company profile if not provided
    company_profile = request.companyProfile or {'name': request.clientId or 'Bertha House'}

    # Intent: generate report
    if 'report' in instr or 'generate report' in instr or 'create report' in instr:
        report_type = 'comprehensive'
        if 'environment' in instr or 'carbon' in instr:
            report_type = 'environmental'

        result = await gemini.generate_ai_report(company_profile, report_type)
        return {
            'action': 'generate_report',
            'report_type': report_type,
            'used_template': used_template and used_template.get('key'),
            'result': result
        }

    # Intent: recommendations / improve
    if 'recommend' in instr or 'improv' in instr or 'optimization' in instr:
        result = await gemini.generate_recommendations(company_profile)
        return {
            'action': 'recommendations',
            'used_template': used_template and used_template.get('key'),
            'result': result
        }

    # Fallback: chat / clarification
    try:
        chat_response = await gemini.chat(instruction)
        return {
            'action': 'chat',
            'used_template': used_template and used_template.get('key'),
            'result': chat_response
        }
    except Exception:
        # If Gemini not available, return a helpful mock
        return {
            'action': 'chat',
            'result': {
                'answer': "I'm unable to reach the AI service — try: 'generate report for <clientId>' or 'recommendations for reducing carbon'.",
                'model': 'mock',
                'confidence': 0.5
            }
        }

async def analyze_esg_data(file_data: List[dict]) -> dict:
    """Analyze uploaded files for ESG data"""
    all_data = []
    
    for file_info in file_data:
        if file_info.get("processed_data"):
            if isinstance(file_info["processed_data"], dict) and "sample" in file_info["processed_data"]:
                all_data.extend(file_info["processed_data"]["sample"])
    
    if not all_data:
        return {"error": "No analyzable data found"}
    
    # Create analysis prompt
    prompt = f"""
    Analyze the following ESG data and provide insights:
    
    Data: {json.dumps(all_data[:20], indent=2)}
    
    Please provide:
    1. Key ESG metrics identified
    2. Trends and patterns
    3. Risk areas
    4. Improvement recommendations
    5. Summary score (1-100)
    
    Format as JSON with these sections.
    """
    
    try:
        response = model.generate_content(prompt)
        return json.loads(response.text)
    except Exception as e:
        return {"error": str(e), "analysis": "Failed to generate AI analysis"}

@router.post("/generate-report")
async def generate_report(
    request: ReportRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Generate ESG report using AI"""
    
    # Get file data
    file_objects = []
    for file_id in request.file_ids:
        file_data = await db.files.find_one({"_id": ObjectId(file_id)})
        if file_data:
            file_objects.append(file_data)
    
    if not file_objects:
        raise HTTPException(status_code=404, detail="No files found")
    
    # Generate report with AI
    report_prompt = f"""
    Generate a comprehensive {request.report_type} ESG report based on the uploaded data.
    
    Report Requirements:
    - Executive Summary
    - Environmental Performance
    - Social Impact
    - Governance Metrics
    - Risk Assessment
    - Recommendations
    - Overall ESG Score
    
    Timeframe: {request.timeframe or 'Annual'}
    Custom Requirements: {request.custom_prompt or 'None'}
    
    Provide detailed analysis and actionable insights.
    """
    
    try:
        # Get AI analysis
        ai_analysis = await analyze_esg_data(file_objects)
        
        # Generate full report
        full_prompt = f"{report_prompt}\n\nInitial Analysis: {json.dumps(ai_analysis)}"
        response = model.generate_content(full_prompt)
        
        # Save report to database
        report_data = {
            "user_id": ObjectId(current_user.id) if hasattr(current_user, 'id') else None,
            "username": current_user.username,
            "report_type": request.report_type,
            "file_ids": request.file_ids,
            "ai_analysis": ai_analysis,
            "full_report": response.text,
            "generated_at": datetime.utcnow(),
            "status": "completed"
        }
        
        result = await db.reports.insert_one(report_data)
        report_data["_id"] = str(result.inserted_id)
        
        return {
            "report_id": str(result.inserted_id),
            "analysis": ai_analysis,
            "full_report": response.text,
            "status": "completed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

@router.websocket("/ws/generate-live/{client_id}")
async def websocket_generate_report(websocket: WebSocket, client_id: str):
    """WebSocket endpoint for live AI report generation"""
    await websocket.accept()
    
    try:
        while True:
            # Receive data from client
            data = await websocket.receive_json()
            file_ids = data.get("file_ids", [])
            report_type = data.get("report_type", "Standard ESG Report")
            
            # Send initial response
            await websocket.send_json({
                "status": "processing",
                "message": "Starting AI analysis...",
                "step": 1,
                "total_steps": 5
            })
            
            await asyncio.sleep(1)
            
            # Simulate processing steps
            steps = [
                "Analyzing uploaded files...",
                "Extracting ESG metrics...",
                "Identifying trends and patterns...",
                "Generating recommendations...",
                "Compiling final report..."
            ]
            
            for i, step in enumerate(steps, 2):
                await websocket.send_json({
                    "status": "processing",
                    "message": step,
                    "step": i,
                    "total_steps": 5
                })
                await asyncio.sleep(2)
            
            # Generate final report
            prompt = f"Generate a comprehensive {report_type} with live updates."
            response = model.generate_content(prompt)
            
            await websocket.send_json({
                "status": "completed",
                "message": "Report generated successfully!",
                "report": response.text,
                "step": 5,
                "total_steps": 5
            })
            
    except WebSocketDisconnect:
        print(f"Client {client_id} disconnected")
    except Exception as e:
        await websocket.send_json({
            "status": "error",
            "message": f"Error: {str(e)}"
        })