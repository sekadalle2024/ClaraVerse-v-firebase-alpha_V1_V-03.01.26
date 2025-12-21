"""
API Pandas pour l'analyse de données des arrondissements de Paris
Case 10 - Modelisation_template_v2.js
"""

import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import logging

logger = logging.getLogger("pandas-api")

# Créer le router FastAPI
router = APIRouter(prefix="/pandas", tags=["Pandas Analysis"])

# ============================================
# DONNÉES STATIQUES - Arrondissements de Paris
# ============================================

DATA_ARRONDISSEMENTS = {
    'arrondissement': [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20],
    'population': [16266, 21533, 34248, 27887, 58850, 41100, 51367, 36051, 59555, 83459, 
                   143202, 139866, 178907, 131445, 232554, 165446, 168654, 189966, 184991, 194668],
    'surface_km2': [1.83, 0.99, 1.17, 1.60, 2.54, 2.15, 4.09, 3.88, 2.18, 2.89, 
                    3.67, 16.32, 7.15, 5.64, 8.50, 7.91, 5.67, 6.01, 6.79, 5.98],
    'prix_m2_moyen': [11500, 11200, 10800, 11000, 10500, 12500, 13000, 12800, 9800, 9500, 
                      9200, 8500, 7800, 8900, 9100, 10500, 9600, 8700, 8200, 8400],
    'nb_restaurants': [245, 198, 287, 312, 456, 398, 234, 421, 312, 398, 
                       523, 412, 345, 298, 456, 367, 398, 445, 378, 412],
    'nb_metro': [8, 6, 7, 5, 9, 8, 6, 10, 7, 8, 9, 12, 8, 7, 10, 9, 8, 11, 9, 10]
}

# ============================================
# MODÈLES PYDANTIC
# ============================================

class ArrondissementData(BaseModel):
    arrondissement: int
    population: int
    surface_km2: float
    prix_m2_moyen: int
    nb_restaurants: int
    nb_metro: int
    densite: Optional[float] = None
    categorie_prix: Optional[str] = None

class AnalysisResponse(BaseModel):
    success: bool
    data: Any
    message: str = ""

class FilterRequest(BaseModel):
    column: str
    operator: str  # 'gt', 'lt', 'eq', 'gte', 'lte'
    value: float

# ============================================
# FONCTIONS UTILITAIRES PANDAS
# ============================================

def get_dataframe() -> pd.DataFrame:
    """Créer et retourner le DataFrame principal avec colonnes dérivées"""
    df = pd.DataFrame(DATA_ARRONDISSEMENTS)
    
    # Calcul de la densité
    df['densite'] = (df['population'] / df['surface_km2']).round(0).astype(int)
    
    # Catégorisation des prix
    df['categorie_prix'] = pd.cut(
        df['prix_m2_moyen'],
        bins=[0, 8500, 10000, 15000],
        labels=['Abordable', 'Moyen', 'Cher']
    )
    
    return df

def df_to_dict_list(df: pd.DataFrame) -> List[Dict]:
    """Convertir DataFrame en liste de dictionnaires JSON-serializable"""
    result = df.copy()
    # Convertir les catégories en strings
    for col in result.columns:
        if result[col].dtype.name == 'category':
            result[col] = result[col].astype(str)
    return result.to_dict(orient='records')

# ============================================
# ENDPOINTS API
# ============================================

@router.get("/data", response_model=AnalysisResponse)
async def get_all_data():
    """Récupérer toutes les données des arrondissements avec colonnes dérivées"""
    try:
        df = get_dataframe()
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(df),
            message=f"✅ {len(df)} arrondissements chargés"
        )
    except Exception as e:
        logger.error(f"Erreur get_all_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats", response_model=AnalysisResponse)
async def get_statistics():
    """Obtenir les statistiques descriptives (équivalent df.describe())"""
    try:
        df = get_dataframe()
        stats = df.describe().round(2)
        return AnalysisResponse(
            success=True,
            data=stats.to_dict(),
            message="📊 Statistiques descriptives calculées"
        )
    except Exception as e:
        logger.error(f"Erreur get_statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/top/{column}/{n}", response_model=AnalysisResponse)
async def get_top_n(column: str, n: int = 5):
    """Obtenir les N premiers arrondissements selon une colonne (équivalent nlargest)"""
    try:
        df = get_dataframe()
        
        if column not in df.columns:
            raise HTTPException(status_code=400, detail=f"Colonne '{column}' non trouvée")
        
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise HTTPException(status_code=400, detail=f"Colonne '{column}' n'est pas numérique")
        
        top_df = df.nlargest(n, column)[['arrondissement', column]]
        
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(top_df),
            message=f"🏆 Top {n} par {column}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_top_n: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/bottom/{column}/{n}", response_model=AnalysisResponse)
async def get_bottom_n(column: str, n: int = 5):
    """Obtenir les N derniers arrondissements selon une colonne (équivalent nsmallest)"""
    try:
        df = get_dataframe()
        
        if column not in df.columns:
            raise HTTPException(status_code=400, detail=f"Colonne '{column}' non trouvée")
        
        if not pd.api.types.is_numeric_dtype(df[column]):
            raise HTTPException(status_code=400, detail=f"Colonne '{column}' n'est pas numérique")
        
        bottom_df = df.nsmallest(n, column)[['arrondissement', column]]
        
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(bottom_df),
            message=f"📉 Bottom {n} par {column}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_bottom_n: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/groupby/categorie_prix", response_model=AnalysisResponse)
async def get_stats_by_category():
    """Statistiques groupées par catégorie de prix (équivalent groupby)"""
    try:
        df = get_dataframe()
        
        stats = df.groupby('categorie_prix', observed=True).agg({
            'population': ['sum', 'mean'],
            'prix_m2_moyen': ['mean', 'min', 'max'],
            'nb_restaurants': 'sum',
            'arrondissement': 'count'
        }).round(0)
        
        # Aplatir les colonnes multi-index
        stats.columns = ['_'.join(col).strip() for col in stats.columns.values]
        stats = stats.reset_index()
        stats['categorie_prix'] = stats['categorie_prix'].astype(str)
        
        return AnalysisResponse(
            success=True,
            data=stats.to_dict(orient='records'),
            message="📊 Statistiques par catégorie de prix"
        )
    except Exception as e:
        logger.error(f"Erreur get_stats_by_category: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/filter", response_model=AnalysisResponse)
async def filter_data(filter_req: FilterRequest):
    """Filtrer les données selon un critère"""
    try:
        df = get_dataframe()
        
        if filter_req.column not in df.columns:
            raise HTTPException(status_code=400, detail=f"Colonne '{filter_req.column}' non trouvée")
        
        col = df[filter_req.column]
        
        if filter_req.operator == 'gt':
            mask = col > filter_req.value
        elif filter_req.operator == 'lt':
            mask = col < filter_req.value
        elif filter_req.operator == 'eq':
            mask = col == filter_req.value
        elif filter_req.operator == 'gte':
            mask = col >= filter_req.value
        elif filter_req.operator == 'lte':
            mask = col <= filter_req.value
        else:
            raise HTTPException(status_code=400, detail=f"Opérateur '{filter_req.operator}' non supporté")
        
        filtered_df = df[mask]
        
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(filtered_df),
            message=f"🔍 {len(filtered_df)} résultats pour {filter_req.column} {filter_req.operator} {filter_req.value}"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur filter_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/correlation", response_model=AnalysisResponse)
async def get_correlation():
    """Matrice de corrélation entre variables numériques"""
    try:
        df = get_dataframe()
        
        numeric_cols = ['population', 'surface_km2', 'prix_m2_moyen', 'nb_restaurants', 'nb_metro', 'densite']
        corr_matrix = df[numeric_cols].corr().round(3)
        
        return AnalysisResponse(
            success=True,
            data=corr_matrix.to_dict(),
            message="📈 Matrice de corrélation calculée"
        )
    except Exception as e:
        logger.error(f"Erreur get_correlation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/arrondissement/{arr_id}", response_model=AnalysisResponse)
async def get_arrondissement(arr_id: int):
    """Obtenir les données d'un arrondissement spécifique"""
    try:
        df = get_dataframe()
        
        if arr_id < 1 or arr_id > 20:
            raise HTTPException(status_code=400, detail="Arrondissement doit être entre 1 et 20")
        
        arr_data = df[df['arrondissement'] == arr_id]
        
        if arr_data.empty:
            raise HTTPException(status_code=404, detail=f"Arrondissement {arr_id} non trouvé")
        
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(arr_data)[0],
            message=f"📍 Données du {arr_id}e arrondissement"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur get_arrondissement: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chers", response_model=AnalysisResponse)
async def get_arrondissements_chers():
    """Arrondissements avec prix > 10000€/m²"""
    try:
        df = get_dataframe()
        chers = df[df['prix_m2_moyen'] > 10000][['arrondissement', 'prix_m2_moyen']]
        chers = chers.sort_values('prix_m2_moyen', ascending=False)
        
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(chers),
            message=f"💰 {len(chers)} arrondissements chers (> 10000€/m²)"
        )
    except Exception as e:
        logger.error(f"Erreur get_arrondissements_chers: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/denses", response_model=AnalysisResponse)
async def get_arrondissements_denses():
    """Arrondissements avec densité > 30000 hab/km²"""
    try:
        df = get_dataframe()
        denses = df[df['densite'] > 30000][['arrondissement', 'densite', 'population', 'surface_km2']]
        denses = denses.sort_values('densite', ascending=False)
        
        return AnalysisResponse(
            success=True,
            data=df_to_dict_list(denses),
            message=f"🏙️ {len(denses)} arrondissements très denses (> 30000 hab/km²)"
        )
    except Exception as e:
        logger.error(f"Erreur get_arrondissements_denses: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/export/csv")
async def export_csv():
    """Exporter les données en CSV"""
    try:
        df = get_dataframe()
        csv_content = df.to_csv(index=False)
        
        return {
            "success": True,
            "csv": csv_content,
            "message": "📄 Export CSV généré"
        }
    except Exception as e:
        logger.error(f"Erreur export_csv: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pivot", response_model=AnalysisResponse)
async def get_pivot_table():
    """Tableau pivot - Population et prix par catégorie"""
    try:
        df = get_dataframe()
        
        pivot = df.pivot_table(
            values=['population', 'prix_m2_moyen'],
            index='categorie_prix',
            aggfunc={'population': 'sum', 'prix_m2_moyen': 'mean'}
        ).round(0)
        
        pivot = pivot.reset_index()
        pivot['categorie_prix'] = pivot['categorie_prix'].astype(str)
        
        return AnalysisResponse(
            success=True,
            data=pivot.to_dict(orient='records'),
            message="📊 Tableau pivot généré"
        )
    except Exception as e:
        logger.error(f"Erreur get_pivot_table: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# ============================================
# ENDPOINT COMPLET POUR LE FRONTEND
# ============================================

@router.get("/analysis/complete", response_model=AnalysisResponse)
async def get_complete_analysis():
    """
    Analyse complète pour le Case 10 du frontend.
    Retourne toutes les données et analyses en une seule requête.
    """
    try:
        df = get_dataframe()
        
        # Données complètes
        all_data = df_to_dict_list(df)
        
        # Top 5 population
        top5_pop = df.nlargest(5, 'population')[['arrondissement', 'population']].to_dict(orient='records')
        
        # Top 5 restaurants
        top5_resto = df.nlargest(5, 'nb_restaurants')[['arrondissement', 'nb_restaurants']].to_dict(orient='records')
        
        # Arrondissements chers
        chers = df[df['prix_m2_moyen'] > 10000][['arrondissement', 'prix_m2_moyen']].to_dict(orient='records')
        
        # Stats par catégorie
        stats_cat = df.groupby('categorie_prix', observed=True).agg({
            'arrondissement': 'count',
            'population': 'sum',
            'prix_m2_moyen': 'mean'
        }).round(0).reset_index()
        stats_cat['categorie_prix'] = stats_cat['categorie_prix'].astype(str)
        stats_cat = stats_cat.to_dict(orient='records')
        
        # Corrélation
        numeric_cols = ['population', 'prix_m2_moyen', 'nb_restaurants', 'nb_metro']
        correlation = df[numeric_cols].corr().round(3).to_dict()
        
        # Statistiques descriptives
        stats_desc = df.describe().round(2).to_dict()
        
        return AnalysisResponse(
            success=True,
            data={
                "arrondissements": all_data,
                "top5_population": top5_pop,
                "top5_restaurants": top5_resto,
                "arrondissements_chers": chers,
                "stats_par_categorie": stats_cat,
                "correlation": correlation,
                "statistiques": stats_desc,
                "total_population": int(df['population'].sum()),
                "prix_moyen_global": round(df['prix_m2_moyen'].mean(), 0),
                "densite_moyenne": round(df['densite'].mean(), 0)
            },
            message="🐼 Analyse Pandas complète"
        )
    except Exception as e:
        logger.error(f"Erreur get_complete_analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
