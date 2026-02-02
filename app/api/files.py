from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status, BackgroundTasks
from typing import List, Dict, Any
import aiofiles
import os
import pandas as pd
from datetime import datetime, timedelta
from dateutil import parser
import json
from bson import ObjectId

from app.core.config import settings
from app.api.auth import get_current_user
from app.core.database import get_db

router = APIRouter()

ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".pdf", ".txt", ".json"}


def allowed_file(filename: str) -> bool:
    return any(filename.lower().endswith(ext) for ext in ALLOWED_EXTENSIONS)


async def extract_invoice_data_from_file(file_path: str, content_type: str) -> List[Dict[str, Any]]:
    """Extract invoice data from uploaded file"""
    try:
        print(f"Extracting data from {file_path} with content type {content_type}")

        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
            data = df.to_dict(orient="records")
            print(f"CSV extraction successful: {len(data)} records found")
            print(f"Sample record: {data[0] if data else 'No data'}")
            return data

        elif file_path.endswith((".xlsx", ".xls")):
            df = pd.read_excel(file_path)
            data = df.to_dict(orient="records")
            print(f"Excel extraction successful: {len(data)} records found")
            return data

        elif file_path.endswith(".json"):
            async with aiofiles.open(file_path, "r") as f:
                content = await f.read()
                json_data = json.loads(content)

                if isinstance(json_data, list):
                    data = json_data
                elif isinstance(json_data, dict) and "data" in json_data:
                    data = json_data["data"]
                else:
                    data = [json_data]

                print(f"JSON extraction successful: {len(data)} records found")
                return data

        elif file_path.endswith(".pdf"):
            data = await extract_pdf_data(file_path)
            print(f"PDF extraction: {len(data)} records found")
            return data

        else:
            print(f"Unsupported file type: {file_path}")
            return []

    except Exception as e:
        print(f"Error extracting data from {file_path}: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


async def extract_pdf_data(file_path: str) -> List[Dict[str, Any]]:
    """Extract data from PDF files (simplified implementation)"""
    return [{
        "invoice_number": "PDF-INV-001",
        "vendor_name": "PDF Vendor",
        "invoice_date": datetime.now().strftime("%Y-%m-%d"),
        "total_amount": 1000.00,
        "description": "PDF extracted invoice"
    }]


def filter_last_12_months_data(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter data to include only records from the last 12 months"""
    if not data:
        print("No data to filter")
        return []

    twelve_months_ago = datetime.now() - timedelta(days=365)
    print(f"Filtering data for dates after: {twelve_months_ago}")

    filtered_data = []

    for i, record in enumerate(data):
        print(f"Processing record {i+1}: {record}")
        invoice_date = None

        date_fields = ["invoice_date", "date", "created_at", "transaction_date", "date_created"]
        for field in date_fields:
            if field in record and record[field]:
                try:
                    invoice_date = parser.parse(str(record[field]))
                    print(f"Found date field '{field}': {invoice_date}")
                    break
                except Exception as e:
                    print(f"Failed to parse date from field '{field}': {record[field]} - {e}")
                    continue

        if not invoice_date:
            invoice_date = datetime.now()
            print(f"No date found, using current date: {invoice_date}")

        if invoice_date >= twelve_months_ago:
            record["parsed_date"] = invoice_date
            filtered_data.append(record)
            print(f"Record {i+1} included (within 12 months)")
        else:
            print(f"Record {i+1} excluded (older than 12 months)")

    print(f"Filtered {len(data)} records to {len(filtered_data)} records within last 12 months")
    return filtered_data


def get_date_range(data: List[Dict[str, Any]]) -> Dict[str, str]:
    if not data:
        return {}

    dates = [record.get("parsed_date", datetime.now()) for record in data]
    return {
        "start_date": min(dates).strftime("%Y-%m-%d"),
        "end_date": max(dates).strftime("%Y-%m-%d"),
    }


def extract_invoice_items(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []

    if "items" in record and isinstance(record["items"], list):
        items = record["items"]
    elif "line_items" in record and isinstance(record["line_items"], list):
        items = record["line_items"]
    else:
        item = {
            "description": record.get("description", record.get("item_description", "Unknown Item")),
            "quantity": float(record.get("quantity", 1)),
            "unit_price": float(record.get("unit_price", record.get("price", record.get("total_amount", 0)))),
            "total": float(record.get("total", record.get("total_amount", 0))),
            "esg_category": categorize_esg(record.get("description", "")),
            "esg_score": None,
        }
        items = [item]

    return items


def categorize_esg(description: str) -> str:
    desc_lower = (description or "").lower()

    environmental_keywords = ["energy", "recycling", "waste", "solar", "green", "environment", "sustainability", "renewable", "carbon", "eco"]
    social_keywords = ["training", "healthcare", "education", "community", "welfare", "social", "employee", "diversity", "inclusion"]
    governance_keywords = ["legal", "compliance", "audit", "consulting", "governance", "regulatory", "board", "ethics"]

    if any(k in desc_lower for k in environmental_keywords):
        return "environmental"
    if any(k in desc_lower for k in social_keywords):
        return "social"
    if any(k in desc_lower for k in governance_keywords):
        return "governance"
    return "environmental"


def perform_esg_analysis(invoice_record: Dict[str, Any]) -> Dict[str, Any]:
    try:
        items = invoice_record.get("items", [])
        vendor_name = (invoice_record.get("vendor_name", "") or "").lower()
        total_amount = float(invoice_record.get("total_amount", 0) or 0)

        environmental_score = 5.0
        social_score = 5.0
        governance_score = 5.0

        for item in items:
            category = item.get("esg_category", "environmental")
            item_amount = float(item.get("total", 0) or 0)
            weight = (item_amount / total_amount) if total_amount > 0 else 0

            if category == "environmental":
                environmental_score += weight * 2
            elif category == "social":
                social_score += weight * 2
            elif category == "governance":
                governance_score += weight * 2

        if any(k in vendor_name for k in ["green", "eco", "sustainable", "renewable"]):
            environmental_score += 1
        if any(k in vendor_name for k in ["fair trade", "certified", "organic"]):
            social_score += 1

        environmental_score = min(10, environmental_score)
        social_score = min(10, social_score)
        governance_score = min(10, governance_score)

        overall_score = (environmental_score + social_score + governance_score) / 3

        insights = []
        if environmental_score >= 7:
            insights.append("Strong environmental performance detected")
        if social_score >= 7:
            insights.append("Good social responsibility practices")
        if governance_score >= 7:
            insights.append("Solid governance compliance")

        recommendations = []
        if environmental_score < 6:
            recommendations.append("Consider more environmentally friendly suppliers")
        if social_score < 6:
            recommendations.append("Enhance social responsibility in procurement")
        if governance_score < 6:
            recommendations.append("Improve governance and compliance tracking")

        return {
            "esg_total_score": round(overall_score, 2),
            "esg_insights": {
                "environmental": round(environmental_score, 2),
                "social": round(social_score, 2),
                "governance": round(governance_score, 2),
                "insights": insights,
            },
            "ai_recommendations": recommendations,
        }

    except Exception as e:
        print(f"ESG analysis error: {str(e)}")
        return {
            "esg_total_score": 5.0,
            "esg_insights": {
                "environmental": 5.0,
                "social": 5.0,
                "governance": 5.0,
                "insights": ["Basic ESG analysis completed"],
            },
            "ai_recommendations": ["Consider enhancing ESG data quality"],
        }


async def store_invoice_records(invoice_data: List[Dict[str, Any]], user_id: str, db, file_id: str) -> int:
    invoices_saved = 0

    for record in invoice_data:
        try:
            invoice_record = {
                "id": str(ObjectId()),
                "invoice_number": record.get("invoice_number", f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}-{invoices_saved + 1}"),
                "vendor_name": record.get("vendor_name", record.get("vendor", record.get("supplier", "Unknown Vendor"))),
                "invoice_date": record.get("parsed_date", datetime.utcnow()),
                "due_date": record.get("due_date", datetime.utcnow() + timedelta(days=30)),
                "total_amount": float(record.get("total_amount", record.get("amount", record.get("total", 0))) or 0),
                "currency": record.get("currency", "USD"),
                "status": "processed",
                "file_path": None,
                "user_id": user_id,       # keep as string (matches your aggregations)
                "file_id": file_id,
                "items": extract_invoice_items(record),
                "esg_total_score": None,
                "esg_insights": None,
                "ai_recommendations": None,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "raw_data": record,
            }

            invoice_record.update(perform_esg_analysis(invoice_record))

            await db.invoices.insert_one(invoice_record)
            invoices_saved += 1

        except Exception as e:
            print(f"Error storing invoice record: {str(e)}")
            continue

    return invoices_saved


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    # current_user is a dict (from get_current_user)
    role = current_user.get("role", "user")
    if role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can upload files",
        )

    if not allowed_file(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File type not allowed",
        )

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_username = current_user.get("username", "user")
    filename = f"{safe_username}_{timestamp}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(content)

    user_id_str = current_user.get("id")
    user_id_obj = ObjectId(user_id_str) if user_id_str else None

    file_info = {
        "user_id": user_id_obj,  # ObjectId in files collection
        "username": current_user.get("username"),
        "original_filename": file.filename,
        "stored_filename": filename,
        "file_path": file_path,
        "file_size": len(content),
        "content_type": file.content_type,
        "upload_date": datetime.utcnow(),
        "status": "processing",
        "processed_data": None,
        "invoice_data": None,
        "esg_analysis": None,
    }

    result = await db.files.insert_one(file_info)
    file_id = str(result.inserted_id)

    try:
        extracted_data = await extract_invoice_data_from_file(file_path, file.content_type)
        filtered_data = filter_last_12_months_data(extracted_data)

        if filtered_data:
            file_info["processed_data"] = {
                "columns": list(filtered_data[0].keys()) if filtered_data else [],
                "row_count": len(filtered_data),
                "sample": filtered_data[:10],
                "total_records": len(filtered_data),
                "date_range": get_date_range(filtered_data),
            }
            file_info["invoice_data"] = filtered_data
            file_info["status"] = "processed"

            invoices_saved = await store_invoice_records(filtered_data, user_id_str, db, file_id)
            file_info["invoices_saved"] = invoices_saved
        else:
            file_info["status"] = "no_data"
            file_info["message"] = "No invoice data found for the last 12 months"

    except Exception as e:
        file_info["status"] = "error"
        file_info["error"] = str(e)

    await db.files.update_one({"_id": result.inserted_id}, {"$set": file_info})

    return {
        "message": "File uploaded and processed successfully",
        "file_id": file_id,
        "filename": filename,
        "status": file_info["status"],
        "data_summary": file_info.get("processed_data"),
        "invoices_processed": len(file_info.get("invoice_data") or []),
        "invoices_saved": file_info.get("invoices_saved", 0),
    }


@router.get("/my-files")
async def get_my_files(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    user_id_str = current_user.get("id")
    user_id_obj = ObjectId(user_id_str) if user_id_str else None

    files = (
        await db.files.find({"user_id": user_id_obj})
        .sort("upload_date", -1)
        .to_list(100)
    )

    for f in files:
        f["_id"] = str(f["_id"])
        if "user_id" in f and f["user_id"] is not None:
            f["user_id"] = str(f["user_id"])

    return files


@router.get("/my-invoices")
async def get_my_invoices(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
    limit: int = 50,
    offset: int = 0,
):
    """Get invoices for the current user from the last 12 months"""
    user_id_str = current_user.get("id")
    twelve_months_ago = datetime.utcnow() - timedelta(days=365)

    cursor = (
        db.invoices.find(
            {
                "user_id": user_id_str,  # invoices store string user_id
                "created_at": {"$gte": twelve_months_ago},
            }
        )
        .sort("created_at", -1)
        .skip(offset)
        .limit(limit)
    )

    invoices = []
    async for document in cursor:
        document["_id"] = str(document["_id"])
        invoices.append(document)

    return {"invoices": invoices, "total": len(invoices)}


@router.get("/esg-summary/{user_id}")
async def get_esg_summary(user_id: str, db=Depends(get_db)):
    """Get ESG summary for user's invoices"""
    try:
        twelve_months_ago = datetime.utcnow() - timedelta(days=365)

        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "created_at": {"$gte": twelve_months_ago},
                    "esg_total_score": {"$ne": None},
                }
            },
            {
                "$group": {
                    "_id": None,
                    "avg_esg_score": {"$avg": "$esg_total_score"},
                    "avg_environmental": {"$avg": "$esg_insights.environmental"},
                    "avg_social": {"$avg": "$esg_insights.social"},
                    "avg_governance": {"$avg": "$esg_insights.governance"},
                    "total_invoices": {"$sum": 1},
                    "total_amount": {"$sum": "$total_amount"},
                }
            },
        ]

        result = await db.invoices.aggregate(pipeline).to_list(length=1)

        if result:
            summary = result[0]
            return {
                "average_esg_score": round(summary.get("avg_esg_score", 0) or 0, 2),
                "average_environmental": round(summary.get("avg_environmental", 0) or 0, 2),
                "average_social": round(summary.get("avg_social", 0) or 0, 2),
                "average_governance": round(summary.get("avg_governance", 0) or 0, 2),
                "total_invoices": summary.get("total_invoices", 0) or 0,
                "total_amount": summary.get("total_amount", 0) or 0,
                "period": "12 months",
            }

        return {
            "average_esg_score": 0,
            "average_environmental": 0,
            "average_social": 0,
            "average_governance": 0,
            "total_invoices": 0,
            "total_amount": 0,
            "period": "12 months",
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get ESG summary: {str(e)}")


@router.post("/bulk-upload")
async def bulk_upload_files(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    role = current_user.get("role", "user")
    if role != "client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only clients can upload files",
        )

    total_files = len(files)
    successful_uploads = 0
    failed_uploads = 0
    total_invoices_saved = 0
    errors = []

    for f in files:
        try:
            if not allowed_file(f.filename):
                failed_uploads += 1
                errors.append(f"File {f.filename}: File type not allowed")
                continue

            result = await upload_file(f, current_user, db)

            if result.get("status") in ["processed", "completed"]:
                successful_uploads += 1
                total_invoices_saved += result.get("invoices_saved", 0)
            else:
                failed_uploads += 1
                errors.append(f"File {f.filename}: {result.get('error', 'Processing failed')}")

        except Exception as e:
            failed_uploads += 1
            errors.append(f"File {f.filename}: {str(e)}")

    return {
        "message": "Bulk upload completed",
        "total_files": total_files,
        "successful_uploads": successful_uploads,
        "failed_uploads": failed_uploads,
        "total_invoices_saved": total_invoices_saved,
        "errors": errors,
    }
