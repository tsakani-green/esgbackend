# backend/app/api/admin.py

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel

from bson import ObjectId

from app.api.auth import get_current_user
from app.core.database import db  # ✅ Option A: use db proxy, NOT get_db

router = APIRouter()


# -----------------------------
# Helpers
# -----------------------------
def _to_object_id(value: Any, field_name: str = "id") -> ObjectId:
    """Convert a value into ObjectId safely."""
    try:
        if isinstance(value, ObjectId):
            return value
        return ObjectId(str(value))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name}: '{value}'",
        )


def _json_safe(doc: Any) -> Any:
    """Recursively convert ObjectId values inside dict/list to strings."""
    if isinstance(doc, ObjectId):
        return str(doc)
    if isinstance(doc, list):
        return [_json_safe(x) for x in doc]
    if isinstance(doc, dict):
        return {k: _json_safe(v) for k, v in doc.items()}
    return doc


def _require_admin(current_user: dict):
    # ✅ get_current_user returns dict (not object)
    if not current_user or current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )


# -----------------------------
# Models
# -----------------------------
class PortfolioCreate(BaseModel):
    name: str
    client_id: str
    description: Optional[str] = ""
    status: str = "active"


class AITemplateIn(BaseModel):
    key: str
    name: str
    prompt: str
    is_public: Optional[bool] = True


# -----------------------------
# Routes
# -----------------------------
@router.get("/clients")
async def get_all_clients(
    current_user=Depends(get_current_user),
    skip: int = 0,
    limit: int = 100,
):
    _require_admin(current_user)

    try:
        # Fetch client users
        clients = (
            await db.users.find({"role": "client"})
            .skip(skip)
            .limit(limit)
            .to_list(limit)
        )

        enriched_clients = []

        for client in clients:
            client_oid = client.get("_id")
            if not client_oid:
                continue

            client_oid = _to_object_id(client_oid, field_name="client_id")

            # Stats
            file_count = await db.files.count_documents({"user_id": client_oid})
            report_count = await db.reports.count_documents({"user_id": client_oid})

            # Portfolios / Projects for client
            portfolios = await db.projects.find({"user_id": client_oid}).to_list(100)

            total_assets = 0
            cleaned_portfolios = []

            for portfolio in portfolios:
                portfolio_oid = _to_object_id(portfolio.get("_id"), field_name="portfolio_id")

                # Assets for this portfolio
                assets = await db.assets.find({"project_id": portfolio_oid}).to_list(100)
                assets = [_json_safe(a) for a in assets]

                portfolio_clean = _json_safe(portfolio)
                portfolio_clean["assets"] = assets
                portfolio_clean["asset_count"] = len(assets)

                total_assets += len(assets)
                cleaned_portfolios.append(portfolio_clean)

            client_clean = _json_safe(client)
            client_clean["stats"] = {
                "files": file_count,
                "reports": report_count,
                "portfolios": len(cleaned_portfolios),
                "total_assets": total_assets,
            }
            client_clean["portfolios"] = cleaned_portfolios

            enriched_clients.append(client_clean)

        total = await db.users.count_documents({"role": "client"})

        return {
            "clients": enriched_clients,
            "total": total,
            "skip": skip,
            "limit": limit,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading clients: {str(e)}",
        )


@router.post("/portfolios/{portfolio_id}/ai-templates")
async def upsert_portfolio_template(
    portfolio_id: str,
    template: AITemplateIn,
    current_user=Depends(get_current_user),
):
    """Create or update an AI prompt template for a portfolio (admin only)."""
    _require_admin(current_user)
    try:
        now = datetime.utcnow()
        doc = {
            "portfolio_id": portfolio_id,
            "key": template.key,
            "name": template.name,
            "prompt": template.prompt,
            "is_public": bool(template.is_public),
            "updated_at": now,
            "created_by": current_user.get("username"),
        }

        await db.ai_templates.update_one(
            {"portfolio_id": portfolio_id, "key": template.key},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

        # ensure index (best-effort)
        try:
            await db.ai_templates.create_index([("portfolio_id", 1), ("key", 1)], unique=True)
        except Exception:
            pass

        return {"ok": True, "template": doc}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unable to save template: {str(e)}")


@router.delete("/portfolios/{portfolio_id}/ai-templates/{key}")
async def delete_portfolio_template(
    portfolio_id: str,
    key: str,
    current_user=Depends(get_current_user),
):
    """Delete an AI template by portfolio and key (admin only)."""
    _require_admin(current_user)
    try:
        res = await db.ai_templates.delete_one({"portfolio_id": portfolio_id, "key": key})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Template not found")
        return {"ok": True, "deleted": res.deleted_count}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unable to delete template: {str(e)}")


@router.get("/client/{client_id}")
async def get_client_details(
    client_id: str,
    current_user=Depends(get_current_user),
):
    _require_admin(current_user)

    try:
        client_oid = _to_object_id(client_id, field_name="client_id")

        client = await db.users.find_one({"_id": client_oid, "role": "client"})
        if not client:
            raise HTTPException(status_code=404, detail="Client not found")

        files = await db.files.find({"user_id": client_oid}).to_list(100)
        reports = await db.reports.find({"user_id": client_oid}).to_list(100)

        return {
            "client": _json_safe(client),
            "files": _json_safe(files),
            "reports": _json_safe(reports),
            "stats": {
                "file_count": len(files),
                "report_count": len(reports),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading client details: {str(e)}",
        )


@router.get("/dashboard-stats")
async def get_dashboard_stats(
    current_user=Depends(get_current_user),
):
    _require_admin(current_user)

    try:
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)

        total_clients = await db.users.count_documents({"role": "client"})
        total_files = await db.files.count_documents({})
        total_reports = await db.reports.count_documents({})

        new_clients = await db.users.count_documents(
            {"role": "client", "created_at": {"$gte": thirty_days_ago}}
        )

        recent_files = (
            await db.files.find({"upload_date": {"$gte": thirty_days_ago}})
            .sort("upload_date", -1)
            .to_list(50)
        )

        return {
            "total_clients": total_clients,
            "total_files": total_files,
            "total_reports": total_reports,
            "new_clients_30d": new_clients,
            "recent_files": _json_safe(recent_files),
            "esg_scores": {
                "average": 75,
                "min": 45,
                "max": 95,
                "trend": "improving",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error loading dashboard stats: {str(e)}",
        )


@router.post("/portfolios")
async def create_portfolio(
    portfolio_data: PortfolioCreate,
    current_user=Depends(get_current_user),
):
    _require_admin(current_user)

    try:
        # Verify client exists (you are using username as client_id)
        client = await db.users.find_one({"username": portfolio_data.client_id, "role": "client"})
        if not client:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Client '{portfolio_data.client_id}' not found",
            )

        client_oid = _to_object_id(client.get("_id"), field_name="client_id")

        existing_portfolio = await db.projects.find_one(
            {"user_id": client_oid, "name": portfolio_data.name}
        )
        if existing_portfolio:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Portfolio '{portfolio_data.name}' already exists for this client",
            )

        portfolio = {
            "name": portfolio_data.name,
            "description": portfolio_data.description,
            "status": portfolio_data.status,
            "user_id": client_oid,  # ObjectId
            "client_id": portfolio_data.client_id,
            "type": "Portfolio",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "hasMeterData": True,
            "vendor": "eGauge",
            "meterName": "Local Mains",
        }

        result = await db.projects.insert_one(portfolio)
        portfolio["_id"] = result.inserted_id

        # Update client's portfolio_access if not already included
        portfolio_slug = portfolio_data.name.lower().replace(" ", "-")
        if portfolio_slug not in client.get("portfolio_access", []):
            await db.users.update_one(
                {"_id": client_oid},
                {"$addToSet": {"portfolio_access": portfolio_slug}},
            )

        return {
            "success": True,
            "portfolio": _json_safe(portfolio),
            "message": f"Portfolio '{portfolio_data.name}' created successfully for {client.get('full_name', portfolio_data.client_id)}",
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating portfolio: {str(e)}",
        )


@router.delete("/clients/{username}")
async def delete_client(
    username: str,
    current_user=Depends(get_current_user),
):
    _require_admin(current_user)

    client = await db.users.find_one({"username": username, "role": "client"})
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{username}' not found",
        )

    client_oid = _to_object_id(client.get("_id"), field_name="client_id")

    try:
        await db.files.delete_many({"user_id": client_oid})
        await db.reports.delete_many({"user_id": client_oid})

        portfolios = await db.projects.find({"user_id": client_oid}).to_list(100)
        for portfolio in portfolios:
            portfolio_oid = _to_object_id(portfolio.get("_id"), field_name="portfolio_id")
            await db.assets.delete_many({"project_id": portfolio_oid})
            await db.projects.delete_one({"_id": portfolio_oid})

        result = await db.users.delete_one({"_id": client_oid})

        if result.deleted_count > 0:
            return {
                "success": True,
                "message": f"Client '{username}' and all associated data deleted successfully",
            }

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete client",
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting client: {str(e)}",
        )


@router.put("/clients/{username}")
async def update_client(
    username: str,
    update_data: Dict[str, Any],
    current_user=Depends(get_current_user),
):
    _require_admin(current_user)

    client = await db.users.find_one({"username": username, "role": "client"})
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Client '{username}' not found",
        )

    client_oid = _to_object_id(client.get("_id"), field_name="client_id")

    try:
        allowed_fields = ["full_name", "email", "phone", "address", "status", "subscription", "company"]
        update_dict = {k: v for k, v in update_data.items() if k in allowed_fields}
        update_dict["updated_at"] = datetime.utcnow()

        result = await db.users.update_one({"_id": client_oid}, {"$set": update_dict})

        if result.modified_count > 0:
            updated_client = await db.users.find_one({"_id": client_oid})
            return {
                "success": True,
                "client": _json_safe(updated_client),
                "message": f"Client '{username}' updated successfully",
            }

        return {"success": True, "message": "No changes made to client"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating client: {str(e)}",
        )
