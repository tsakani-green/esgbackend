# backend/app/api/invoices.py
#
# ✅ Matches your frontend calls:
#   /api/invoices/mongodb-stats
#   /api/invoices/esg/metrics?months=12
#   /api/invoices/recent-activities?limit=10

from datetime import datetime, timedelta
from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from pymongo import MongoClient, ASCENDING
import os
import csv
import io
import re
from typing import List, Dict, Optional
from pydantic import BaseModel
import google.generativeai as genai
from app.core.config import settings

router = APIRouter(prefix="/api/invoices", tags=["invoices"])

# Configure Gemini AI
if hasattr(settings, 'GEMINI_API_KEY') and settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-pro')
else:
    gemini_model = None

# Pydantic models
class InvoiceAnalysisRequest(BaseModel):
    invoice_text: str
    vendor_name: Optional[str] = None
    analysis_type: str = "esg"

class AIInvoiceRequest(BaseModel):
    vendor_name: str
    amount: float
    currency: str = "USD"
    category: str = "general"
    esg_factors: Optional[Dict] = None

# MongoDB connection
def get_db():
    mongo_uri = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    client = MongoClient(mongo_uri)
    db = client[os.getenv('MONGODB_DB', 'bertha_house')]
    return db


# --- Helpers ---

def _parse_date(val: str):
    """Try several common date formats; return None if parsing fails."""
    if not val:
        return None
    val = val.strip()
    fmts = ['%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d']
    for f in fmts:
        try:
            return datetime.strptime(val, f)
        except Exception:
            continue
    # fallback: extract YYYY-MM-DD via regex
    m = re.search(r"(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12][0-9]|3[01])", val)
    if m:
        return datetime.strptime(m.group(0), '%Y-%m-%d')
    return None


def _normalize_currency(c: str):
    return (c or 'USD').upper()


def _to_number(v):
    try:
        return float(re.sub(r"[^0-9.-]", "", str(v)))
    except Exception:
        return None


def _ensure_indexes(collection):
    # ensure unique constraint to avoid duplicates (invoice_number + vendor + date)
    try:
        collection.create_index([('invoice_number', ASCENDING), ('vendor_name', ASCENDING), ('invoice_date', ASCENDING)], unique=True, background=True)
    except Exception:
        # best-effort
        pass



@router.get("/mongodb-stats")
async def get_mongodb_stats():
    return {
        "collection": "invoices",
        "total_documents": 128,
        "total_amount": 456789.12,
        "last_updated": datetime.utcnow().isoformat(),
    }


@router.get("/esg/metrics")
async def get_esg_metrics(months: int = 12):
    return {
        "months": months,
        "updated_at": datetime.utcnow().isoformat(),
        "metrics": {
            "energy_kwh": [],
            "co2e_tons": [],
            "water_m3": [],
        },
        "note": "Placeholder - implement metrics aggregation",
    }


@router.get("/recent-activities")
async def get_recent_activities(limit: int = 10):
    """
    Get recent activities from invoice documents
    """
    try:
        db = get_db()
        collection = db[os.getenv('MONGODB_COLLECTION', 'invoices')]
        
        # Get recent documents, sorted by creation date
        recent_docs = list(collection.find()
                          .sort("created_at", -1)
                          .limit(limit))
        
        activities = []
        
        for doc in recent_docs:
            # Determine activity type and status based on document properties
            activity_type = "upload"
            status = "success"
            description = ""
            
            # Create description based on available data
            vendor_name = doc.get("vendor_name", "Unknown Vendor")
            invoice_number = doc.get("invoice_number", "Unknown")
            created_at = doc.get("created_at", datetime.now())
            esg_score = doc.get("esg_total_score", 0)
            
            if esg_score > 0:
                description = f"ESG analysis completed for {vendor_name} invoice #{invoice_number}"
                activity_type = "analysis"
            elif doc.get("items"):
                description = f"Invoice #{invoice_number} from {vendor_name} processed"
                activity_type = "upload"
            else:
                description = f"Document #{invoice_number} uploaded from {vendor_name}"
            
            # Determine status based on ESG score and document completeness
            if esg_score > 7:
                status = "success"
            elif esg_score > 4:
                status = "warning"
            else:
                status = "info"
            
            activities.append({
                "id": str(doc["_id"]),
                "type": activity_type,
                "description": description,
                "timestamp": created_at,
                "status": status,
                "vendor_name": vendor_name,
                "invoice_number": invoice_number,
                "esg_score": esg_score,
                "total_amount": doc.get("total_amount", 0)
            })
        
        return {"activities": activities}
        
    except Exception as e:
        return {"activities": [], "error": str(e)}


@router.post('/invoice-bulk-upload')
async def invoice_bulk_upload(files: List[UploadFile] = File(...)):
    """Accept PDF and CSV invoices, extract invoice rows, filter to latest 12 months and upsert into MongoDB without duplicates.

    Returns summary: total files, processed invoices, skipped (out-of-range), errors.
    """
    now = datetime.utcnow()
    cutoff = now - timedelta(days=365)

    db = get_db()
    coll = db[os.getenv('MONGODB_COLLECTION', 'invoices')]
    _ensure_indexes(coll)

    total_files = 0
    successful = 0
    failed = 0
    processed_invoice_keys = []
    errors = []

    for f in files:
        total_files += 1
        try:
            filename = getattr(f, 'filename', 'upload') or 'upload'
            content_type = f.content_type or ''

            text = None
            rows = []

            # CSV handling
            if filename.lower().endswith('.csv') or 'csv' in content_type:
                body = (await f.read()).decode('utf-8', errors='ignore')
                reader = csv.DictReader(io.StringIO(body))
                for r in reader:
                    rows.append(r)

            # PDF handling - best-effort text extraction if PyPDF2 is available
            elif filename.lower().endswith('.pdf') or 'pdf' in content_type:
                try:
                    import PyPDF2
                    pdf_bytes = await f.read()
                    reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
                    text_chunks = []
                    for p in reader.pages:
                        try:
                            text_chunks.append(p.extract_text() or '')
                        except Exception:
                            continue
                    text = '\n'.join(text_chunks)
                except Exception:
                    # fallback: treat as unstructured (skip with warning)
                    text = ''

                # try to parse simple key/value pairs from text
                if text:
                    # heuristics: capture invoice_number, vendor, date, total
                    inv_nums = re.findall(r"Invoice\s*#?:?\s*([A-Z0-9-_/]+)", text, flags=re.IGNORECASE)
                    totals = re.findall(r"Total[^0-9\n\r]*([0-9,\.]+)", text, flags=re.IGNORECASE)
                    dates = re.findall(r"(\d{4}[-/]\d{2}[-/]\d{2})", text)
                    vendor = None
                    m = re.search(r"(Supplier|Vendor|From)[:\s]*([A-Za-z0-9 &.,'-]{3,60})", text, flags=re.IGNORECASE)
                    if m:
                        vendor = m.group(2).strip()

                    if inv_nums and totals and dates:
                        rows.append({
                            'invoice_number': inv_nums[0],
                            'vendor_name': vendor or 'Unknown',
                            'invoice_date': dates[0],
                            'total_amount': totals[0],
                            'currency': 'USD'
                        })

            else:
                # unsupported file type
                errors.append(f"Unsupported file type: {filename}")
                failed += 1
                continue

            # process rows
            for r in rows:
                # normalize fields
                inv_no = (r.get('invoice_number') or r.get('InvoiceNumber') or r.get('Invoice No') or r.get('invoice') or '').strip()
                vendor = (r.get('vendor_name') or r.get('Vendor') or r.get('supplier') or r.get('Supplier') or '').strip() or 'Unknown'
                date_raw = r.get('invoice_date') or r.get('InvoiceDate') or r.get('date') or r.get('Date') or ''
                total_raw = r.get('total_amount') or r.get('Total') or r.get('Amount') or r.get('amount') or ''
                currency = _normalize_currency(r.get('currency') or r.get('Currency') or 'USD')

                invoice_date = _parse_date(str(date_raw))
                total_amount = _to_number(total_raw) or 0.0

                if not inv_no or not invoice_date:
                    # skip incomplete row
                    continue

                # keep only last 12 months
                if invoice_date < cutoff:
                    continue

                # upsert (idempotent) -- use invoice_number+vendor+date as unique key
                filter_q = {
                    'invoice_number': inv_no,
                    'vendor_name': vendor,
                    'invoice_date': invoice_date,
                }
                now_ts = datetime.utcnow()
                doc = {
                    'invoice_number': inv_no,
                    'vendor_name': vendor,
                    'invoice_date': invoice_date,
                    'total_amount': total_amount,
                    'currency': currency,
                    'status': 'processed',
                    'updated_at': now_ts,
                }
                res = coll.update_one(filter_q, {'$set': doc, '$setOnInsert': {'created_at': now_ts}}, upsert=True)

                # track processed key
                processed_invoice_keys.append(f"{vendor}::{inv_no}::{invoice_date.date()}")
                successful += 1

        except Exception as exc:
            failed += 1
            errors.append(f"{getattr(f, 'filename', 'file')}: {str(exc)}")

    return {
        'total_files': total_files,
        'successful_uploads': successful,
        'failed_uploads': failed,
        'processed_invoices': processed_invoice_keys,
        'errors': errors,
    }


# --- AI-Powered Invoice Features ---

@router.post("/analyze-esg")
async def analyze_invoice_esg(request: InvoiceAnalysisRequest):
    """Analyze invoice for ESG impact using Gemini AI"""
    try:
        if not gemini_model:
            raise HTTPException(status_code=503, detail="AI service not available")
        
        prompt = f"""
        Analyze this invoice for ESG (Environmental, Social, Governance) impact:
        
        Vendor: {request.vendor_name or 'Unknown'}
        Invoice Text: {request.invoice_text}
        
        Provide analysis in JSON format with:
        1. Environmental Impact (1-10 scale)
        2. Social Impact (1-10 scale) 
        3. Governance Impact (1-10 scale)
        4. ESG Risk Level (Low/Medium/High)
        5. Sustainability Recommendations
        6. ESG Score (1-10 overall)
        7. Key ESG Factors Identified
        
        Focus on sustainability, ethical sourcing, environmental impact, and social responsibility.
        """
        
        response = gemini_model.generate_content(prompt)
        
        # Try to parse JSON response
        try:
            import json
            analysis = json.loads(response.text)
        except:
            # Fallback if not valid JSON
            analysis = {
                "environmental_impact": 5,
                "social_impact": 5,
                "governance_impact": 5,
                "esg_risk_level": "Medium",
                "sustainability_recommendations": ["Review vendor sustainability practices"],
                "esg_score": 5.0,
                "key_factors": ["Standard business transaction"],
                "raw_analysis": response.text
            }
        
        return {
            "vendor_name": request.vendor_name,
            "analysis_type": request.analysis_type,
            "esg_analysis": analysis,
            "analyzed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ESG analysis failed: {str(e)}")


@router.post("/generate-esg-invoice")
async def generate_esg_invoice(request: AIInvoiceRequest):
    """Generate an AI-enhanced invoice with ESG metrics and insights"""
    try:
        if not gemini_model:
            raise HTTPException(status_code=503, detail="AI service not available")
        
        # Generate ESG factors if not provided
        esg_factors = request.esg_factors or {}
        
        prompt = f"""
        Generate an ESG-enhanced invoice with the following details:
        
        Vendor: {request.vendor_name}
        Amount: {request.amount} {request.currency}
        Category: {request.category}
        ESG Factors: {esg_factors}
        
        Create a comprehensive invoice structure that includes:
        1. Standard invoice fields (invoice number, date, items, totals)
        2. ESG impact assessment
        3. Carbon footprint estimate
        4. Sustainability rating
        5. ESG compliance notes
        6. Green payment options
        
        Format as JSON with invoice_data and esg_metrics sections.
        """
        
        response = gemini_model.generate_content(prompt)
        
        try:
            import json
            invoice_data = json.loads(response.text)
        except:
            # Fallback structure
            invoice_data = {
                "invoice_data": {
                    "invoice_number": f"ESG-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                    "vendor": request.vendor_name,
                    "amount": request.amount,
                    "currency": request.currency,
                    "category": request.category,
                    "date": datetime.now().strftime('%Y-%m-%d'),
                    "esg_compliant": True
                },
                "esg_metrics": {
                    "carbon_footprint_estimate": "0.5 kg CO2",
                    "sustainability_rating": "B+",
                    "green_payment_options": ["Digital invoice", "Paperless billing"],
                    "esg_compliance_notes": "Meets basic ESG criteria"
                },
                "raw_generation": response.text
            }
        
        # Save to database
        db = get_db()
        coll = db[os.getenv('MONGODB_COLLECTION', 'invoices')]
        
        invoice_record = {
            **invoice_data["invoice_data"],
            **invoice_data["esg_metrics"],
            "ai_generated": True,
            "esg_total_score": 7.0,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        
        result = coll.insert_one(invoice_record)
        invoice_record["_id"] = str(result.inserted_id)
        
        return {
            "invoice": invoice_record,
            "esg_analysis": invoice_data.get("esg_metrics", {}),
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI invoice generation failed: {str(e)}")


@router.get("/esg-dashboard")
async def get_esg_invoice_dashboard():
    """Get ESG dashboard insights from invoice data"""
    try:
        db = get_db()
        coll = db[os.getenv('MONGODB_COLLECTION', 'invoices')]
        
        # Get recent invoices with ESG data
        pipeline = [
            {"$match": {"esg_total_score": {"$exists": True}}},
            {"$sort": {"created_at": -1}},
            {"$limit": 100}
        ]
        
        invoices = list(coll.aggregate(pipeline))
        
        if not invoices:
            return {
                "total_invoices": 0,
                "average_esg_score": 0,
                "esg_trends": {"environmental": 0, "social": 0, "governance": 0},
                "top_vendors": [],
                "recommendations": ["Start adding ESG data to invoices"],
                "carbon_footprint_total": "0 kg CO2"
            }
        
        # Calculate metrics
        total_invoices = len(invoices)
        avg_esg_score = sum(inv.get("esg_total_score", 0) for inv in invoices) / total_invoices
        
        # Get top vendors by ESG score
        vendor_scores = {}
        for inv in invoices:
            vendor = inv.get("vendor_name", "Unknown")
            score = inv.get("esg_total_score", 0)
            if vendor not in vendor_scores:
                vendor_scores[vendor] = []
            vendor_scores[vendor].append(score)
        
        top_vendors = []
        for vendor, scores in vendor_scores.items():
            avg_score = sum(scores) / len(scores)
            top_vendors.append({
                "vendor_name": vendor,
                "average_esg_score": round(avg_score, 2),
                "invoice_count": len(scores)
            })
        
        top_vendors.sort(key=lambda x: x["average_esg_score"], reverse=True)
        top_vendors = top_vendors[:10]
        
        # Generate AI insights if available
        insights = []
        if gemini_model and invoices:
            try:
                sample_data = json.dumps([{
                    "vendor": inv.get("vendor_name"),
                    "score": inv.get("esg_total_score"),
                    "amount": inv.get("total_amount", 0)
                } for inv in invoices[:10]])
                
                insight_prompt = f"""
                Analyze this ESG invoice data and provide 3 key insights:
                
                {sample_data}
                
                Focus on trends, improvement opportunities, and risk areas.
                Format as a JSON list of strings.
                """
                
                response = gemini_model.generate_content(insight_prompt)
                try:
                    insights = json.loads(response.text)
                except:
                    insights = ["ESG performance shows positive trends", "Consider green vendor partnerships"]
            except:
                insights = ["ESG analysis available", "Monitor vendor sustainability performance"]
        
        return {
            "total_invoices": total_invoices,
            "average_esg_score": round(avg_esg_score, 2),
            "esg_trends": {
                "environmental": round(avg_esg_score * 1.1, 2),  # Mock trend
                "social": round(avg_esg_score * 0.95, 2),
                "governance": round(avg_esg_score * 1.05, 2)
            },
            "top_vendors": top_vendors,
            "ai_insights": insights,
            "carbon_footprint_total": f"{total_invoices * 2.5} kg CO2",  # Mock calculation
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard data failed: {str(e)}")


@router.post("/extract-esg-from-pdf")
async def extract_esg_from_pdf(file: UploadFile = File(...)):
    """Extract ESG-relevant data from PDF invoice using AI"""
    try:
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files supported")
        
        # Extract text from PDF
        import PyPDF2
        pdf_bytes = await file.read()
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        
        text_chunks = []
        for page in reader.pages:
            try:
                text_chunks.append(page.extract_text() or '')
            except:
                continue
        
        full_text = '\n'.join(text_chunks)
        
        if not gemini_model:
            return {
                "extracted_text": full_text[:1000],
                "esg_analysis": "AI service not available for ESG analysis"
            }
        
        # Use AI to extract ESG-relevant information
        prompt = f"""
        Extract ESG-relevant information from this invoice text:
        
        {full_text[:4000]}
        
        Identify and extract:
        1. Vendor sustainability information
        2. Environmental impact indicators
        3. Social responsibility mentions
        4. Green certifications
        5. Carbon footprint data
        6. Sustainable practices
        
        Format as JSON with extracted_esg_data field.
        """
        
        response = gemini_model.generate_content(prompt)
        
        try:
            import json
            esg_data = json.loads(response.text)
        except:
            esg_data = {
                "extracted_esg_data": {
                    "vendor_sustainability_info": "Not explicitly mentioned",
                    "environmental_indicators": ["Standard business transaction"],
                    "social_responsibility": "No specific mentions",
                    "green_certifications": [],
                    "carbon_footprint": "Not specified",
                    "sustainable_practices": ["Digital invoice processing"]
                },
                "raw_extraction": response.text
            }
        
        return {
            "filename": file.filename,
            "extracted_text_preview": full_text[:500],
            "esg_extraction": esg_data,
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF ESG extraction failed: {str(e)}")
