"""
Agent d'Échantillonnage pour ClaraVerse
Méthodes d'échantillonnage en audit (ACL, IDEA, TeamMate Analytics)
Version 1.0 - Échantillonnage statistique pour audit
"""

import pandas as pd
import numpy as np
import json
import logging
import math
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("echantillonnage-agent")

# Créer le router FastAPI
router = APIRouter(prefix="/echantillonnage", tags=["Échantillonnage Audit"])

# ============================================
# MODÈLES PYDANTIC
# ============================================

class TableJsonData(BaseModel):
    """Données d'une table en format JSON"""
    tableId: str
    headers: List[str]
    rows: List[List[str]]

class EchantillonnageRequest(BaseModel):
    """Requête d'échantillonnage"""
    tables: List[TableJsonData]
    targetTableId: str
    method: str  # random, systematic, monetary, stratified, fixed, with_replacement
    # Paramètres optionnels selon la méthode
    sampleSize: Optional[int] = None  # Taille de l'échantillon
    interval: Optional[int] = None  # Intervalle pour systématique
    confidenceLevel: Optional[float] = 0.95  # Niveau de confiance
    tolerableError: Optional[float] = 0.05  # Erreur tolérable
    expectedError: Optional[float] = 0.01  # Erreur attendue
    populationValue: Optional[float] = None  # Valeur totale population (MUS)
    monetaryColumn: Optional[str] = None  # Colonne montant pour MUS
    stratifyColumn: Optional[str] = None  # Colonne de stratification
    fixedRecords: Optional[List[int]] = None  # Indices des enregistrements fixes

class SampleResult(BaseModel):
    """Résultat d'un échantillon"""
    tableId: str
    headers: List[str]
    rows: List[List[str]]
    sampleSize: int
    method: str
    statistics: Optional[Dict[str, Any]] = None

class EchantillonnageResponse(BaseModel):
    """Réponse de l'agent d'échantillonnage"""
    success: bool
    originalTable: SampleResult
    sampleTable: SampleResult
    message: str
    statistics: Optional[Dict[str, Any]] = None

class SampleSizeRequest(BaseModel):
    """Requête pour calculer la taille d'échantillon"""
    populationSize: int
    confidenceLevel: float = 0.95
    tolerableError: float = 0.05
    expectedError: float = 0.01

class SampleSizeResponse(BaseModel):
    """Réponse du calcul de taille d'échantillon"""
    success: bool
    sampleSize: int
    populationSize: int
    confidenceLevel: float
    tolerableError: float
    expectedError: float
    formula: str
    message: str

# ============================================
# FONCTIONS D'ÉCHANTILLONNAGE
# ============================================

def clean_numeric_value(value: str) -> float:
    """Nettoie et convertit une valeur en nombre"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    try:
        cleaned = str(value).replace(' ', '').replace(',', '.').replace('€', '').replace('FCFA', '')
        cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
        if cleaned == '' or cleaned == '-':
            return 0.0
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def calculate_sample_size(population_size: int, confidence_level: float = 0.95, 
                         tolerable_error: float = 0.05, expected_error: float = 0.01) -> int:
    """
    Calcule la taille d'échantillon selon les normes ISA
    Formule: n = (Z² × p × (1-p)) / E² ajusté pour population finie
    """
    # Z-score pour le niveau de confiance
    z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_scores.get(confidence_level, 1.96)
    
    # p = proportion attendue d'erreurs
    p = expected_error if expected_error > 0 else 0.5
    
    # E = erreur tolérable
    E = tolerable_error
    
    # Taille d'échantillon initiale (population infinie)
    n0 = (z ** 2 * p * (1 - p)) / (E ** 2)
    
    # Ajustement pour population finie
    n = n0 / (1 + (n0 - 1) / population_size)
    
    return max(1, int(math.ceil(n)))

def random_sample(df: pd.DataFrame, sample_size: int, seed: int = None) -> pd.DataFrame:
    """
    Échantillonnage aléatoire simple (SAMPLE RANDOM)
    Sélection aléatoire de X enregistrements
    """
    logger.info(f"🎲 Échantillonnage aléatoire simple: {sample_size} sur {len(df)}")
    
    if seed is not None:
        np.random.seed(seed)
    
    actual_size = min(sample_size, len(df))
    sample_indices = np.random.choice(len(df), size=actual_size, replace=False)
    sample_indices.sort()
    
    return df.iloc[sample_indices].copy()

def systematic_sample(df: pd.DataFrame, interval: int = None, sample_size: int = None) -> pd.DataFrame:
    """
    Échantillonnage systématique (SAMPLE INTERVAL)
    Sélection tous les N enregistrements
    """
    n = len(df)
    
    if interval is None and sample_size is not None:
        interval = max(1, n // sample_size)
    elif interval is None:
        interval = 10  # Défaut
    
    logger.info(f"📏 Échantillonnage systématique: intervalle={interval} sur {n}")
    
    # Point de départ aléatoire dans le premier intervalle
    start = np.random.randint(0, min(interval, n))
    
    indices = list(range(start, n, interval))
    return df.iloc[indices].copy()

def monetary_unit_sample(df: pd.DataFrame, monetary_column: str, sample_size: int,
                        population_value: float = None) -> pd.DataFrame:
    """
    Échantillonnage par unité monétaire (MUS - Monetary Unit Sampling)
    Échantillonnage proportionnel aux montants
    """
    logger.info(f"💰 Échantillonnage MUS: colonne={monetary_column}, taille={sample_size}")
    
    # Convertir la colonne monétaire en numérique
    df_work = df.copy()
    df_work['_monetary_value'] = df_work[monetary_column].apply(clean_numeric_value)
    df_work['_monetary_value'] = df_work['_monetary_value'].abs()  # Valeurs absolues
    
    # Calculer la valeur totale si non fournie
    total_value = population_value if population_value else df_work['_monetary_value'].sum()
    
    if total_value == 0:
        logger.warning("⚠️ Valeur totale = 0, fallback vers échantillonnage aléatoire")
        return random_sample(df, sample_size)
    
    # Intervalle d'échantillonnage
    sampling_interval = total_value / sample_size
    
    # Calculer les valeurs cumulées
    df_work['_cumulative'] = df_work['_monetary_value'].cumsum()
    
    # Point de départ aléatoire
    start = np.random.uniform(0, sampling_interval)
    
    # Sélectionner les enregistrements
    selected_indices = []
    current_value = start
    
    for i in range(sample_size):
        # Trouver l'enregistrement contenant cette valeur monétaire
        mask = df_work['_cumulative'] >= current_value
        if mask.any():
            idx = mask.idxmax()
            if idx not in selected_indices:
                selected_indices.append(idx)
        current_value += sampling_interval
    
    # Nettoyer les colonnes temporaires
    result = df.loc[selected_indices].copy()
    
    return result

def stratified_sample(df: pd.DataFrame, stratify_column: str, sample_size: int) -> pd.DataFrame:
    """
    Échantillonnage stratifié (SAMPLE par strates)
    Échantillon par sous-groupes pour représentativité
    """
    logger.info(f"📊 Échantillonnage stratifié: colonne={stratify_column}, taille={sample_size}")
    
    # Identifier les strates
    strata = df[stratify_column].unique()
    n_strata = len(strata)
    
    if n_strata == 0:
        return random_sample(df, sample_size)
    
    # Calculer la taille par strate (proportionnelle)
    samples = []
    
    for stratum in strata:
        stratum_df = df[df[stratify_column] == stratum]
        stratum_proportion = len(stratum_df) / len(df)
        stratum_sample_size = max(1, int(round(sample_size * stratum_proportion)))
        
        if len(stratum_df) > 0:
            stratum_sample = stratum_df.sample(n=min(stratum_sample_size, len(stratum_df)))
            samples.append(stratum_sample)
            logger.info(f"   Strate '{stratum}': {len(stratum_sample)} sur {len(stratum_df)}")
    
    if samples:
        return pd.concat(samples, ignore_index=True)
    return df.head(sample_size)

def fixed_record_sample(df: pd.DataFrame, record_indices: List[int]) -> pd.DataFrame:
    """
    Échantillonnage d'enregistrements fixes (SAMPLE RECORD)
    Sélection d'enregistrements spécifiques
    """
    logger.info(f"📌 Échantillonnage fixe: {len(record_indices)} enregistrements")
    
    valid_indices = [i for i in record_indices if 0 <= i < len(df)]
    return df.iloc[valid_indices].copy()

def sample_with_replacement(df: pd.DataFrame, sample_size: int, seed: int = None) -> pd.DataFrame:
    """
    Échantillonnage aléatoire avec remise
    Tirage avec possibilité de répétition
    """
    logger.info(f"🔄 Échantillonnage avec remise: {sample_size} tirages")
    
    if seed is not None:
        np.random.seed(seed)
    
    indices = np.random.choice(len(df), size=sample_size, replace=True)
    return df.iloc[indices].copy()

def calculate_sample_statistics(original_df: pd.DataFrame, sample_df: pd.DataFrame, 
                               monetary_column: str = None) -> Dict[str, Any]:
    """
    Calcule les statistiques de l'échantillon
    """
    stats = {
        "population_size": len(original_df),
        "sample_size": len(sample_df),
        "sampling_rate": round(len(sample_df) / len(original_df) * 100, 2) if len(original_df) > 0 else 0
    }
    
    if monetary_column and monetary_column in original_df.columns:
        pop_values = original_df[monetary_column].apply(clean_numeric_value)
        sample_values = sample_df[monetary_column].apply(clean_numeric_value)
        
        stats["population_total"] = round(pop_values.sum(), 2)
        stats["sample_total"] = round(sample_values.sum(), 2)
        stats["population_mean"] = round(pop_values.mean(), 2)
        stats["sample_mean"] = round(sample_values.mean(), 2)
        stats["population_std"] = round(pop_values.std(), 2)
        stats["sample_std"] = round(sample_values.std(), 2)
        
        # Estimation de la valeur totale à partir de l'échantillon
        if len(sample_df) > 0:
            expansion_factor = len(original_df) / len(sample_df)
            stats["estimated_total"] = round(sample_values.sum() * expansion_factor, 2)
    
    return stats

# ============================================
# ENDPOINTS API
# ============================================

@router.post("/sample", response_model=EchantillonnageResponse)
async def perform_sampling(request: EchantillonnageRequest):
    """
    Effectue un échantillonnage selon la méthode spécifiée
    """
    try:
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🎯 [ÉCHANTILLONNAGE] DÉBUT DU TRAITEMENT")
        logger.info("═══════════════════════════════════════════════════════════")
        
        logger.info(f"📊 Méthode: {request.method}")
        logger.info(f"📊 Taille demandée: {request.sampleSize}")
        logger.info(f"📊 Tables reçues: {len(request.tables)}")
        
        # Trouver la table cible
        target_table = None
        for table in request.tables:
            if table.tableId == request.targetTableId:
                target_table = table
                break
        
        if not target_table:
            raise HTTPException(status_code=404, detail=f"Table '{request.targetTableId}' non trouvée")
        
        # Créer le DataFrame
        df = pd.DataFrame(target_table.rows, columns=target_table.headers)
        logger.info(f"📋 DataFrame créé: {len(df)} lignes, {len(df.columns)} colonnes")
        
        # Calculer la taille d'échantillon si non spécifiée
        sample_size = request.sampleSize
        if sample_size is None or sample_size <= 0:
            sample_size = calculate_sample_size(
                len(df),
                request.confidenceLevel,
                request.tolerableError,
                request.expectedError
            )
            logger.info(f"📐 Taille calculée automatiquement: {sample_size}")
        
        # Effectuer l'échantillonnage selon la méthode
        method = request.method.lower()
        
        if method == "random":
            sample_df = random_sample(df, sample_size)
        elif method == "systematic":
            sample_df = systematic_sample(df, request.interval, sample_size)
        elif method == "monetary" or method == "mus":
            if not request.monetaryColumn:
                # Chercher une colonne monétaire automatiquement
                monetary_cols = [c for c in df.columns if any(kw in c.lower() for kw in ['montant', 'solde', 'valeur', 'amount', 'total'])]
                if monetary_cols:
                    request.monetaryColumn = monetary_cols[0]
                else:
                    raise HTTPException(status_code=400, detail="Colonne monétaire non spécifiée pour MUS")
            sample_df = monetary_unit_sample(df, request.monetaryColumn, sample_size, request.populationValue)
        elif method == "stratified":
            if not request.stratifyColumn:
                raise HTTPException(status_code=400, detail="Colonne de stratification non spécifiée")
            sample_df = stratified_sample(df, request.stratifyColumn, sample_size)
        elif method == "fixed":
            if not request.fixedRecords:
                raise HTTPException(status_code=400, detail="Indices des enregistrements non spécifiés")
            sample_df = fixed_record_sample(df, request.fixedRecords)
        elif method == "with_replacement":
            sample_df = sample_with_replacement(df, sample_size)
        else:
            raise HTTPException(status_code=400, detail=f"Méthode '{method}' non reconnue")
        
        # Calculer les statistiques
        statistics = calculate_sample_statistics(df, sample_df, request.monetaryColumn)
        
        # Préparer la réponse
        original_result = SampleResult(
            tableId=target_table.tableId,
            headers=target_table.headers,
            rows=target_table.rows,
            sampleSize=len(df),
            method="original"
        )
        
        sample_rows = sample_df.values.tolist()
        sample_rows = [[str(cell) if not pd.isna(cell) else "" for cell in row] for row in sample_rows]
        
        sample_result = SampleResult(
            tableId=f"{target_table.tableId}_sample",
            headers=list(sample_df.columns),
            rows=sample_rows,
            sampleSize=len(sample_df),
            method=method,
            statistics=statistics
        )
        
        response = EchantillonnageResponse(
            success=True,
            originalTable=original_result,
            sampleTable=sample_result,
            message=f"✅ Échantillonnage {method}: {len(sample_df)} enregistrements sélectionnés sur {len(df)}",
            statistics=statistics
        )
        
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🎯 [ÉCHANTILLONNAGE] TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("═══════════════════════════════════════════════════════════")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [ÉCHANTILLONNAGE] Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calculate-size", response_model=SampleSizeResponse)
async def calculate_sample_size_endpoint(request: SampleSizeRequest):
    """
    Calcule la taille d'échantillon optimale selon les paramètres statistiques
    """
    try:
        logger.info("📐 [TAILLE ÉCHANTILLON] Calcul en cours...")
        
        sample_size = calculate_sample_size(
            request.populationSize,
            request.confidenceLevel,
            request.tolerableError,
            request.expectedError
        )
        
        formula = f"n = (Z² × p × (1-p)) / E² ajusté pour N={request.populationSize}"
        
        return SampleSizeResponse(
            success=True,
            sampleSize=sample_size,
            populationSize=request.populationSize,
            confidenceLevel=request.confidenceLevel,
            tolerableError=request.tolerableError,
            expectedError=request.expectedError,
            formula=formula,
            message=f"✅ Taille d'échantillon recommandée: {sample_size} pour une population de {request.populationSize}"
        )
        
    except Exception as e:
        logger.error(f"❌ [TAILLE ÉCHANTILLON] Erreur: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Vérifie le statut de l'agent d'échantillonnage"""
    return {
        "status": "ready",
        "methods_available": [
            "random",
            "systematic", 
            "monetary",
            "stratified",
            "fixed",
            "with_replacement"
        ],
        "message": "Agent d'échantillonnage prêt"
    }

@router.post("/test")
async def test_sampling():
    """Test de l'agent avec des données exemple"""
    try:
        # Données de test
        test_data = {
            'Compte': ['101', '102', '103', '104', '105', '106', '107', '108', '109', '110'],
            'Libelle': ['Compte A', 'Compte B', 'Compte C', 'Compte D', 'Compte E', 
                       'Compte F', 'Compte G', 'Compte H', 'Compte I', 'Compte J'],
            'Montant': [1000, 2500, 500, 7500, 3000, 1500, 4000, 2000, 6000, 8000],
            'Categorie': ['A', 'B', 'A', 'C', 'B', 'A', 'C', 'B', 'A', 'C']
        }
        
        df = pd.DataFrame(test_data)
        
        # Test échantillonnage aléatoire
        sample_random = random_sample(df, 3)
        
        # Test échantillonnage systématique
        sample_systematic = systematic_sample(df, interval=3)
        
        # Test MUS
        sample_mus = monetary_unit_sample(df, 'Montant', 4)
        
        # Test stratifié
        sample_stratified = stratified_sample(df, 'Categorie', 5)
        
        return {
            "success": True,
            "tests": {
                "random": {
                    "size": len(sample_random),
                    "indices": sample_random.index.tolist()
                },
                "systematic": {
                    "size": len(sample_systematic),
                    "indices": sample_systematic.index.tolist()
                },
                "mus": {
                    "size": len(sample_mus),
                    "indices": sample_mus.index.tolist()
                },
                "stratified": {
                    "size": len(sample_stratified),
                    "categories": sample_stratified['Categorie'].value_counts().to_dict()
                }
            },
            "message": "Tests réussis"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur test: {e}")
        return {
            "success": False,
            "error": str(e)
        }

# ============================================
# ANALYSE DE DONNÉES - DÉTECTION DE FRAUDE
# ============================================

class AnalyseRequest(BaseModel):
    """Requête d'analyse de données"""
    tables: List[TableJsonData]
    targetTableId: str
    method: str  # duplicates, gaps, benford, threshold, weekend, round_amounts, outliers, period_changes
    # Paramètres optionnels
    columns: Optional[List[str]] = None  # Colonnes à analyser
    sequenceColumn: Optional[str] = None  # Colonne de séquence (pour gaps)
    amountColumn: Optional[str] = None  # Colonne montant
    dateColumn: Optional[str] = None  # Colonne date
    threshold: Optional[float] = None  # Seuil pour filtrage
    zScoreThreshold: Optional[float] = 3.0  # Seuil Z-score pour outliers

class AnalyseResult(BaseModel):
    """Résultat d'analyse"""
    tableId: str
    headers: List[str]
    rows: List[List[str]]
    count: int
    method: str
    details: Optional[Dict[str, Any]] = None

class AnalyseResponse(BaseModel):
    """Réponse d'analyse"""
    success: bool
    result: AnalyseResult
    message: str
    statistics: Optional[Dict[str, Any]] = None

# --- Fonctions d'analyse ---

def detect_duplicates(df: pd.DataFrame, columns: List[str] = None) -> tuple:
    """
    Détection des doublons (DUPLICATES)
    Identification des enregistrements dupliqués
    """
    logger.info(f"🔍 Détection doublons sur colonnes: {columns}")
    
    if columns:
        # Vérifier que les colonnes existent
        valid_cols = [c for c in columns if c in df.columns]
        if not valid_cols:
            valid_cols = df.columns.tolist()
    else:
        valid_cols = df.columns.tolist()
    
    # Trouver les doublons
    duplicates_mask = df.duplicated(subset=valid_cols, keep=False)
    duplicates_df = df[duplicates_mask].copy()
    
    # Ajouter une colonne indiquant le groupe de doublons
    if len(duplicates_df) > 0:
        duplicates_df['_groupe_doublon'] = duplicates_df.groupby(valid_cols).ngroup() + 1
    
    stats = {
        "total_records": len(df),
        "duplicate_records": len(duplicates_df),
        "unique_duplicate_groups": duplicates_df['_groupe_doublon'].nunique() if len(duplicates_df) > 0 else 0,
        "columns_checked": valid_cols
    }
    
    return duplicates_df, stats

def detect_sequence_gaps(df: pd.DataFrame, sequence_column: str) -> tuple:
    """
    Détection des trous de séquence (GAPS)
    Identification des numéros manquants dans une séquence
    """
    logger.info(f"🔢 Détection trous séquence: colonne={sequence_column}")
    
    if sequence_column not in df.columns:
        raise ValueError(f"Colonne '{sequence_column}' non trouvée")
    
    # Convertir en numérique
    sequence_values = pd.to_numeric(df[sequence_column], errors='coerce').dropna().astype(int)
    
    if len(sequence_values) == 0:
        return pd.DataFrame(), {"error": "Aucune valeur numérique trouvée"}
    
    min_val = sequence_values.min()
    max_val = sequence_values.max()
    
    # Trouver les valeurs manquantes
    expected_sequence = set(range(min_val, max_val + 1))
    actual_sequence = set(sequence_values)
    missing_values = sorted(expected_sequence - actual_sequence)
    
    # Créer un DataFrame des valeurs manquantes
    gaps_df = pd.DataFrame({
        sequence_column: missing_values,
        'Statut': ['MANQUANT'] * len(missing_values)
    })
    
    stats = {
        "sequence_start": min_val,
        "sequence_end": max_val,
        "expected_count": len(expected_sequence),
        "actual_count": len(actual_sequence),
        "missing_count": len(missing_values),
        "missing_values": missing_values[:50]  # Limiter à 50 pour l'affichage
    }
    
    return gaps_df, stats

def benford_analysis(df: pd.DataFrame, amount_column: str) -> tuple:
    """
    Analyse de la loi de Benford (BENFORD)
    Test de conformité de la distribution des premiers chiffres
    """
    logger.info(f"📊 Analyse Benford: colonne={amount_column}")
    
    if amount_column not in df.columns:
        raise ValueError(f"Colonne '{amount_column}' non trouvée")
    
    # Distribution théorique de Benford
    benford_expected = {
        1: 30.1, 2: 17.6, 3: 12.5, 4: 9.7, 5: 7.9,
        6: 6.7, 7: 5.8, 8: 5.1, 9: 4.6
    }
    
    # Extraire les premiers chiffres
    values = df[amount_column].apply(clean_numeric_value)
    values = values[values > 0]  # Exclure les valeurs nulles ou négatives
    
    first_digits = values.apply(lambda x: int(str(abs(x))[0]) if x != 0 else 0)
    first_digits = first_digits[first_digits > 0]
    
    # Calculer la distribution observée
    observed_counts = first_digits.value_counts().sort_index()
    total = len(first_digits)
    
    results = []
    chi_square = 0
    
    for digit in range(1, 10):
        observed = observed_counts.get(digit, 0)
        observed_pct = (observed / total * 100) if total > 0 else 0
        expected_pct = benford_expected[digit]
        deviation = observed_pct - expected_pct
        
        # Chi-carré
        expected_count = total * expected_pct / 100
        if expected_count > 0:
            chi_square += ((observed - expected_count) ** 2) / expected_count
        
        # Alerte si écart > 5%
        alert = "⚠️ SUSPECT" if abs(deviation) > 5 else "✓ OK"
        
        results.append({
            'Chiffre': digit,
            'Observé (%)': round(observed_pct, 1),
            'Attendu (%)': expected_pct,
            'Écart (%)': round(deviation, 1),
            'Statut': alert
        })
    
    result_df = pd.DataFrame(results)
    
    # Seuil critique chi-carré (8 degrés de liberté, alpha=0.05) = 15.51
    conformity = "CONFORME" if chi_square < 15.51 else "NON CONFORME - Manipulation possible"
    
    stats = {
        "total_values": total,
        "chi_square": round(chi_square, 2),
        "critical_value": 15.51,
        "conformity": conformity,
        "suspicious_digits": [r['Chiffre'] for r in results if '⚠️' in r['Statut']]
    }
    
    return result_df, stats

def detect_threshold_transactions(df: pd.DataFrame, amount_column: str, threshold: float) -> tuple:
    """
    Détection des transactions juste sous un seuil (FILTER)
    Identification du fractionnement frauduleux
    """
    logger.info(f"🎯 Détection seuil: colonne={amount_column}, seuil={threshold}")
    
    if amount_column not in df.columns:
        raise ValueError(f"Colonne '{amount_column}' non trouvée")
    
    df_work = df.copy()
    df_work['_montant_num'] = df_work[amount_column].apply(clean_numeric_value)
    
    # Transactions entre 80% et 100% du seuil
    lower_bound = threshold * 0.80
    upper_bound = threshold
    
    suspicious_mask = (df_work['_montant_num'] >= lower_bound) & (df_work['_montant_num'] < upper_bound)
    suspicious_df = df[suspicious_mask].copy()
    
    # Ajouter le pourcentage du seuil
    suspicious_df['% du seuil'] = df_work.loc[suspicious_mask, '_montant_num'].apply(
        lambda x: f"{round(x/threshold*100, 1)}%"
    )
    
    stats = {
        "threshold": threshold,
        "range_checked": f"{lower_bound:.2f} - {upper_bound:.2f}",
        "suspicious_count": len(suspicious_df),
        "total_suspicious_amount": round(df_work.loc[suspicious_mask, '_montant_num'].sum(), 2)
    }
    
    return suspicious_df, stats

def detect_weekend_transactions(df: pd.DataFrame, date_column: str) -> tuple:
    """
    Détection des transactions week-end (DOW)
    Opérations hors jours ouvrables
    """
    logger.info(f"📅 Détection week-end: colonne={date_column}")
    
    if date_column not in df.columns:
        raise ValueError(f"Colonne '{date_column}' non trouvée")
    
    df_work = df.copy()
    
    # Parser les dates
    df_work['_date_parsed'] = pd.to_datetime(df_work[date_column], errors='coerce', dayfirst=True)
    
    # Filtrer les dates valides
    valid_dates = df_work['_date_parsed'].notna()
    
    # Identifier les week-ends (5=samedi, 6=dimanche)
    df_work['_day_of_week'] = df_work['_date_parsed'].dt.dayofweek
    weekend_mask = valid_dates & (df_work['_day_of_week'] >= 5)
    
    weekend_df = df[weekend_mask].copy()
    weekend_df['Jour'] = df_work.loc[weekend_mask, '_date_parsed'].dt.day_name()
    
    stats = {
        "total_records": len(df),
        "valid_dates": valid_dates.sum(),
        "weekend_transactions": len(weekend_df),
        "saturday_count": (df_work['_day_of_week'] == 5).sum(),
        "sunday_count": (df_work['_day_of_week'] == 6).sum()
    }
    
    return weekend_df, stats

def detect_round_amounts(df: pd.DataFrame, amount_column: str) -> tuple:
    """
    Détection des montants ronds (MOD)
    Montants arrondis suspects (factures fictives, estimations)
    """
    logger.info(f"🔵 Détection montants ronds: colonne={amount_column}")
    
    if amount_column not in df.columns:
        raise ValueError(f"Colonne '{amount_column}' non trouvée")
    
    df_work = df.copy()
    df_work['_montant_num'] = df_work[amount_column].apply(clean_numeric_value)
    
    # Définir les critères de "montant rond"
    def is_round_amount(x):
        if x == 0:
            return False
        # Divisible par 1000, 500, 100
        if x % 1000 == 0:
            return "Multiple de 1000"
        if x % 500 == 0:
            return "Multiple de 500"
        if x % 100 == 0:
            return "Multiple de 100"
        return None
    
    df_work['_round_type'] = df_work['_montant_num'].apply(is_round_amount)
    round_mask = df_work['_round_type'].notna()
    
    round_df = df[round_mask].copy()
    round_df['Type arrondi'] = df_work.loc[round_mask, '_round_type']
    
    # Statistiques par type
    round_types = df_work.loc[round_mask, '_round_type'].value_counts().to_dict()
    
    stats = {
        "total_records": len(df),
        "round_amounts_count": len(round_df),
        "round_percentage": round(len(round_df) / len(df) * 100, 1) if len(df) > 0 else 0,
        "by_type": round_types
    }
    
    return round_df, stats

def detect_outliers(df: pd.DataFrame, amount_column: str, z_threshold: float = 3.0) -> tuple:
    """
    Détection des valeurs aberrantes (Z-score)
    Écarts significatifs à la moyenne
    """
    logger.info(f"📈 Détection outliers: colonne={amount_column}, z_threshold={z_threshold}")
    
    if amount_column not in df.columns:
        raise ValueError(f"Colonne '{amount_column}' non trouvée")
    
    df_work = df.copy()
    df_work['_montant_num'] = df_work[amount_column].apply(clean_numeric_value)
    
    # Calculer moyenne et écart-type
    mean_val = df_work['_montant_num'].mean()
    std_val = df_work['_montant_num'].std()
    
    if std_val == 0:
        return pd.DataFrame(), {"error": "Écart-type nul, pas de variation"}
    
    # Calculer Z-score
    df_work['_z_score'] = (df_work['_montant_num'] - mean_val) / std_val
    
    # Identifier les outliers
    outlier_mask = df_work['_z_score'].abs() > z_threshold
    outliers_df = df[outlier_mask].copy()
    outliers_df['Z-Score'] = df_work.loc[outlier_mask, '_z_score'].round(2)
    outliers_df['Écart à moyenne'] = (df_work.loc[outlier_mask, '_montant_num'] - mean_val).round(2)
    
    stats = {
        "mean": round(mean_val, 2),
        "std": round(std_val, 2),
        "z_threshold": z_threshold,
        "outliers_count": len(outliers_df),
        "outliers_high": (df_work['_z_score'] > z_threshold).sum(),
        "outliers_low": (df_work['_z_score'] < -z_threshold).sum()
    }
    
    return outliers_df, stats

def detect_period_changes(df: pd.DataFrame, amount_column: str, date_column: str) -> tuple:
    """
    Détection des changements brutaux entre périodes
    Variations anormales entre périodes
    """
    logger.info(f"📊 Détection variations: montant={amount_column}, date={date_column}")
    
    if amount_column not in df.columns or date_column not in df.columns:
        raise ValueError("Colonnes requises non trouvées")
    
    df_work = df.copy()
    df_work['_montant_num'] = df_work[amount_column].apply(clean_numeric_value)
    df_work['_date_parsed'] = pd.to_datetime(df_work[date_column], errors='coerce', dayfirst=True)
    
    # Grouper par mois
    df_work['_period'] = df_work['_date_parsed'].dt.to_period('M')
    
    # Agréger par période
    period_totals = df_work.groupby('_period')['_montant_num'].agg(['sum', 'count', 'mean']).reset_index()
    period_totals.columns = ['Période', 'Total', 'Nb transactions', 'Moyenne']
    
    # Calculer les variations
    period_totals['Variation %'] = period_totals['Total'].pct_change() * 100
    period_totals['Variation %'] = period_totals['Variation %'].round(1)
    
    # Identifier les variations anormales (> 50%)
    period_totals['Alerte'] = period_totals['Variation %'].apply(
        lambda x: '⚠️ SUSPECT' if pd.notna(x) and abs(x) > 50 else '✓ OK'
    )
    
    # Convertir période en string pour JSON
    period_totals['Période'] = period_totals['Période'].astype(str)
    
    suspicious_periods = period_totals[period_totals['Alerte'].str.contains('SUSPECT')]
    
    stats = {
        "periods_analyzed": len(period_totals),
        "suspicious_periods": len(suspicious_periods),
        "max_variation": period_totals['Variation %'].max(),
        "min_variation": period_totals['Variation %'].min()
    }
    
    return period_totals, stats

# --- Endpoint d'analyse ---

@router.post("/analyze", response_model=AnalyseResponse)
async def perform_analysis(request: AnalyseRequest):
    """
    Effectue une analyse de données selon la méthode spécifiée
    """
    try:
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🔍 [ANALYSE] DÉBUT DU TRAITEMENT")
        logger.info(f"📊 Méthode: {request.method}")
        logger.info("═══════════════════════════════════════════════════════════")
        
        # Trouver la table cible
        target_table = None
        for table in request.tables:
            if table.tableId == request.targetTableId:
                target_table = table
                break
        
        if not target_table:
            raise HTTPException(status_code=404, detail=f"Table '{request.targetTableId}' non trouvée")
        
        # Créer le DataFrame
        df = pd.DataFrame(target_table.rows, columns=target_table.headers)
        logger.info(f"📋 DataFrame: {len(df)} lignes, {len(df.columns)} colonnes")
        
        method = request.method.lower()
        result_df = pd.DataFrame()
        stats = {}
        
        if method == "duplicates":
            result_df, stats = detect_duplicates(df, request.columns)
        
        elif method == "gaps":
            if not request.sequenceColumn:
                raise HTTPException(status_code=400, detail="Colonne de séquence requise")
            result_df, stats = detect_sequence_gaps(df, request.sequenceColumn)
        
        elif method == "benford":
            if not request.amountColumn:
                # Auto-détection
                amount_cols = [c for c in df.columns if any(kw in c.lower() for kw in ['montant', 'amount', 'total', 'solde'])]
                request.amountColumn = amount_cols[0] if amount_cols else df.columns[0]
            result_df, stats = benford_analysis(df, request.amountColumn)
        
        elif method == "threshold":
            if not request.amountColumn or not request.threshold:
                raise HTTPException(status_code=400, detail="Colonne montant et seuil requis")
            result_df, stats = detect_threshold_transactions(df, request.amountColumn, request.threshold)
        
        elif method == "weekend":
            if not request.dateColumn:
                # Auto-détection
                date_cols = [c for c in df.columns if any(kw in c.lower() for kw in ['date', 'jour', 'day'])]
                request.dateColumn = date_cols[0] if date_cols else df.columns[0]
            result_df, stats = detect_weekend_transactions(df, request.dateColumn)
        
        elif method == "round_amounts":
            if not request.amountColumn:
                amount_cols = [c for c in df.columns if any(kw in c.lower() for kw in ['montant', 'amount', 'total', 'solde'])]
                request.amountColumn = amount_cols[0] if amount_cols else df.columns[0]
            result_df, stats = detect_round_amounts(df, request.amountColumn)
        
        elif method == "outliers":
            if not request.amountColumn:
                amount_cols = [c for c in df.columns if any(kw in c.lower() for kw in ['montant', 'amount', 'total', 'solde'])]
                request.amountColumn = amount_cols[0] if amount_cols else df.columns[0]
            result_df, stats = detect_outliers(df, request.amountColumn, request.zScoreThreshold or 3.0)
        
        elif method == "period_changes":
            if not request.amountColumn or not request.dateColumn:
                raise HTTPException(status_code=400, detail="Colonnes montant et date requises")
            result_df, stats = detect_period_changes(df, request.amountColumn, request.dateColumn)
        
        else:
            raise HTTPException(status_code=400, detail=f"Méthode '{method}' non reconnue")
        
        # Préparer la réponse
        result_rows = result_df.values.tolist() if len(result_df) > 0 else []
        result_rows = [[str(cell) if not pd.isna(cell) else "" for cell in row] for row in result_rows]
        
        result = AnalyseResult(
            tableId=f"{target_table.tableId}_{method}",
            headers=list(result_df.columns) if len(result_df) > 0 else [],
            rows=result_rows,
            count=len(result_df),
            method=method,
            details=stats
        )
        
        response = AnalyseResponse(
            success=True,
            result=result,
            message=f"✅ Analyse {method}: {len(result_df)} résultats trouvés",
            statistics=stats
        )
        
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info(f"🔍 [ANALYSE] TERMINÉ - {len(result_df)} résultats")
        logger.info("═══════════════════════════════════════════════════════════")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ [ANALYSE] Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
