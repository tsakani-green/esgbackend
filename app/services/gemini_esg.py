from __future__ import annotations

from typing import Callable, Optional

from app.services.gemini_client import GEMINI_READY, get_gemini_model


def get_gemini_esg_service(model_name: Optional[str] = None) -> Callable[[str], str]:
    """
    Returns a callable(prompt) -> text for ESG usage.
    This matches the import pattern your API modules expect.
    """

    if not GEMINI_READY:
        raise RuntimeError("Gemini is not configured")

    model = get_gemini_model(model_name)

    def _ask(prompt: str) -> str:
        resp = model.generate_content(prompt or "")
        text = getattr(resp, "text", None) or ""
        return text.strip()

    return _ask
