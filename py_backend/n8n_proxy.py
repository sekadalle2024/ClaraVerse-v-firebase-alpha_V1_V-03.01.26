"""
Proxy pour n8n - Permet d'intégrer les formulaires n8n dans une iframe
en contournant les restrictions X-Frame-Options
"""

import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import HTMLResponse
import logging
from typing import Optional

logger = logging.getLogger("n8n-proxy")

router = APIRouter(prefix="/n8n-proxy", tags=["n8n-proxy"])

# Configuration
N8N_FORM_BASE_URL = "https://barow52161.app.n8n.cloud"
TIMEOUT = 30.0

@router.get("/form/{form_id}")
async def proxy_n8n_form(form_id: str, request: Request):
    """
    Proxy pour les formulaires n8n.
    Récupère le formulaire et le renvoie sans les headers restrictifs.
    """
    try:
        target_url = f"{N8N_FORM_BASE_URL}/form/{form_id}"
        logger.info(f"Proxying n8n form: {target_url}")
        
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            # Récupérer le formulaire n8n
            response = await client.get(
                target_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                }
            )
            
            if response.status_code != 200:
                logger.error(f"n8n returned status {response.status_code}")
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch n8n form")
            
            content = response.text
            
            # Modifier les URLs relatives pour pointer vers le proxy
            # Remplacer les références aux assets n8n
            content = content.replace('href="/', f'href="{N8N_FORM_BASE_URL}/')
            content = content.replace('src="/', f'src="{N8N_FORM_BASE_URL}/')
            content = content.replace("href='/", f"href='{N8N_FORM_BASE_URL}/")
            content = content.replace("src='/", f"src='{N8N_FORM_BASE_URL}/")
            
            # Ajouter une base URL pour les ressources relatives
            if '<head>' in content:
                base_tag = f'<base href="{N8N_FORM_BASE_URL}/">'
                content = content.replace('<head>', f'<head>\n{base_tag}')
            
            # Retourner le HTML sans les headers restrictifs
            return HTMLResponse(
                content=content,
                status_code=200,
                headers={
                    "Content-Type": "text/html; charset=utf-8",
                    "X-Frame-Options": "ALLOWALL",
                    "Content-Security-Policy": "frame-ancestors *",
                    "Access-Control-Allow-Origin": "*",
                }
            )
            
    except httpx.TimeoutException:
        logger.error("Timeout while fetching n8n form")
        raise HTTPException(status_code=504, detail="Timeout while fetching n8n form")
    except Exception as e:
        logger.error(f"Error proxying n8n form: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/form/{form_id}")
async def proxy_n8n_form_submit(form_id: str, request: Request):
    """
    Proxy pour soumettre les formulaires n8n.
    """
    try:
        target_url = f"{N8N_FORM_BASE_URL}/form/{form_id}"
        logger.info(f"Proxying n8n form submission: {target_url}")
        
        # Récupérer le body de la requête
        body = await request.body()
        content_type = request.headers.get("content-type", "application/x-www-form-urlencoded")
        
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.post(
                target_url,
                content=body,
                headers={
                    "Content-Type": content_type,
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                }
            )
            
            # Retourner la réponse
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": response.headers.get("content-type", "text/html"),
                    "X-Frame-Options": "ALLOWALL",
                    "Access-Control-Allow-Origin": "*",
                }
            )
            
    except Exception as e:
        logger.error(f"Error submitting n8n form: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.api_route("/form/{form_id}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy_n8n_form_assets(form_id: str, path: str, request: Request):
    """
    Proxy pour les assets et sous-routes des formulaires n8n.
    """
    try:
        target_url = f"{N8N_FORM_BASE_URL}/form/{form_id}/{path}"
        logger.info(f"Proxying n8n asset: {target_url}")
        
        async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
            if request.method == "GET":
                response = await client.get(target_url)
            elif request.method == "POST":
                body = await request.body()
                response = await client.post(target_url, content=body)
            else:
                response = await client.request(request.method, target_url)
            
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers={
                    "Content-Type": response.headers.get("content-type", "application/octet-stream"),
                    "Access-Control-Allow-Origin": "*",
                }
            )
            
    except Exception as e:
        logger.error(f"Error proxying n8n asset: {e}")
        raise HTTPException(status_code=500, detail=str(e))
