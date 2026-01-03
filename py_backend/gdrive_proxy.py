"""
Google Drive PDF Proxy
Télécharge les PDF depuis Google Drive et les sert localement
pour contourner les restrictions X-Frame-Options
"""

import logging
import httpx
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
import io

logger = logging.getLogger("gdrive-proxy")

router = APIRouter(prefix="/api/gdrive", tags=["Google Drive Proxy"])

# Cache simple en mémoire pour les PDF (limité à 50 fichiers)
pdf_cache = {}
MAX_CACHE_SIZE = 50

@router.get("/pdf/{file_id}")
async def proxy_pdf(file_id: str):
    """
    Proxy pour télécharger et servir un PDF depuis Google Drive.
    Contourne les restrictions X-Frame-Options de Google.
    """
    logger.info(f"📥 Demande de proxy PDF pour: {file_id}")
    
    # Vérifier le cache
    if file_id in pdf_cache:
        logger.info(f"✅ PDF trouvé dans le cache: {file_id}")
        pdf_data = pdf_cache[file_id]
        return Response(
            content=pdf_data,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"inline; filename={file_id}.pdf",
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*"
            }
        )
    
    # URL de téléchargement direct Google Drive
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            logger.info(f"📡 Téléchargement depuis Google Drive: {download_url}")
            
            response = await client.get(download_url)
            
            # Vérifier si c'est une page de confirmation (fichiers volumineux)
            if response.status_code == 200 and b'confirm=' in response.content:
                # Extraire le token de confirmation
                content_str = response.content.decode('utf-8', errors='ignore')
                if 'confirm=' in content_str:
                    import re
                    match = re.search(r'confirm=([^&"]+)', content_str)
                    if match:
                        confirm_token = match.group(1)
                        confirm_url = f"{download_url}&confirm={confirm_token}"
                        logger.info(f"📡 Fichier volumineux, utilisation du token de confirmation")
                        response = await client.get(confirm_url)
            
            if response.status_code != 200:
                logger.error(f"❌ Erreur téléchargement: HTTP {response.status_code}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Erreur lors du téléchargement depuis Google Drive: {response.status_code}"
                )
            
            # Vérifier que c'est bien un PDF
            content_type = response.headers.get('content-type', '')
            if 'application/pdf' not in content_type and not response.content[:4] == b'%PDF':
                # Vérifier si c'est une page HTML d'erreur
                if b'<html' in response.content[:100].lower():
                    logger.error(f"❌ Réponse HTML au lieu de PDF - fichier non accessible")
                    raise HTTPException(
                        status_code=403,
                        detail="Le fichier n'est pas accessible. Vérifiez qu'il est partagé publiquement."
                    )
            
            pdf_data = response.content
            
            # Vérifier la taille minimale
            if len(pdf_data) < 1000:
                logger.error(f"❌ Fichier trop petit: {len(pdf_data)} bytes")
                raise HTTPException(
                    status_code=400,
                    detail="Le fichier téléchargé est trop petit ou invalide"
                )
            
            logger.info(f"✅ PDF téléchargé: {len(pdf_data)} bytes")
            
            # Mettre en cache (avec limite de taille)
            if len(pdf_cache) >= MAX_CACHE_SIZE:
                # Supprimer le premier élément (FIFO)
                oldest_key = next(iter(pdf_cache))
                del pdf_cache[oldest_key]
            pdf_cache[file_id] = pdf_data
            
            return Response(
                content=pdf_data,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"inline; filename={file_id}.pdf",
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*"
                }
            )
            
    except httpx.TimeoutException:
        logger.error(f"❌ Timeout lors du téléchargement")
        raise HTTPException(
            status_code=504,
            detail="Timeout lors du téléchargement depuis Google Drive"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors du téléchargement: {str(e)}"
        )


@router.delete("/cache/{file_id}")
async def clear_cache(file_id: str):
    """Vider le cache pour un fichier spécifique"""
    if file_id in pdf_cache:
        del pdf_cache[file_id]
        return {"status": "ok", "message": f"Cache vidé pour {file_id}"}
    return {"status": "ok", "message": "Fichier non trouvé dans le cache"}


@router.delete("/cache")
async def clear_all_cache():
    """Vider tout le cache PDF"""
    pdf_cache.clear()
    return {"status": "ok", "message": "Cache entièrement vidé"}
