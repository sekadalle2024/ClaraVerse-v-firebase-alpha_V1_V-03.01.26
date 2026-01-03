"""
Agent Pandas pour ClaraVerse
Calcul automatique des écarts dans les tables HTML
Mode simple sans dépendance LLM externe
"""

import pandas as pd
import numpy as np
import json
import logging
import re
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bs4 import BeautifulSoup
import os

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pandas-agent")

# Mode simple activé par défaut (pas de dépendance LLM)
LANGCHAIN_AVAILABLE = False
logger.info("✅ Agent Pandas en mode calcul simple (sans LLM)")

# Clé API Gemini (pour utilisation future)
GEMINI_API_KEY = "AIzaSyDOSWlZ1r0BigvXX7yVmxaST6dodmVEiyw"

# Créer le router FastAPI
router = APIRouter(prefix="/pandas-agent", tags=["Pandas Agent"])

# ============================================
# MODÈLES PYDANTIC
# ============================================

class TableData(BaseModel):
    """Données d'une table HTML"""
    tableId: str
    outerHTML: str

class TablesRequest(BaseModel):
    """Requête contenant plusieurs tables"""
    tables: List[TableData]
    targetTableId: str
    action: str = "calculate_ecart"

# Nouveau modèle pour les données JSON
class TableJsonData(BaseModel):
    """Données d'une table en format JSON"""
    tableId: str
    headers: List[str]
    rows: List[List[str]]

class TablesJsonRequest(BaseModel):
    """Requête contenant les données en JSON"""
    tables: List[TableJsonData]
    targetTableId: str
    action: str = "calculate_ecart"
    # Colonnes optionnelles pour le calcul
    sourceColumn1: Optional[str] = None  # Colonne source 1 (ex: Solde Théorique)
    sourceColumn2: Optional[str] = None  # Colonne source 2 (ex: Solde Physique)
    targetColumn: Optional[str] = None   # Colonne cible (ex: Ecart)

class AgentResponse(BaseModel):
    """Réponse de l'agent"""
    success: bool
    targetTableId: str
    resultHTML: str
    message: str
    calculations: Optional[Dict[str, Any]] = None

class AgentJsonResponse(BaseModel):
    """Réponse de l'agent en format JSON"""
    success: bool
    targetTableId: str
    headers: List[str]
    rows: List[List[str]]
    message: str
    calculations: Optional[Dict[str, Any]] = None

class TableJsonOutput(BaseModel):
    """Table de sortie en format JSON"""
    tableId: str
    headers: List[str]
    rows: List[List[str]]

class AgentMultiTableResponse(BaseModel):
    """Réponse de l'agent avec TOUTES les tables"""
    success: bool
    tables: List[TableJsonOutput]
    targetTableId: str
    message: str
    calculations: Optional[Dict[str, Any]] = None

# ============================================
# FONCTIONS UTILITAIRES
# ============================================

def html_to_dataframe(html: str) -> pd.DataFrame:
    """Convertit une table HTML en DataFrame pandas"""
    try:
        logger.info("   🔄 [HTML->DF] Début de la conversion...")
        
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        
        if not table:
            logger.warning("   ⚠️ [HTML->DF] Aucune table trouvée dans le HTML")
            return pd.DataFrame()
        
        # Extraire les en-têtes
        headers = []
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                logger.info(f"   📋 [HTML->DF] En-têtes trouvés (thead): {headers}")
        
        # Si pas de thead, prendre la première ligne
        if not headers:
            first_row = table.find('tr')
            if first_row:
                headers = [cell.get_text(strip=True) for cell in first_row.find_all(['th', 'td'])]
                logger.info(f"   📋 [HTML->DF] En-têtes trouvés (1ère ligne): {headers}")
        
        # Extraire les données
        rows = []
        tbody = table.find('tbody')
        data_rows = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]
        
        logger.info(f"   📊 [HTML->DF] Nombre de lignes de données: {len(data_rows)}")
        
        for i, row in enumerate(data_rows):
            cells = row.find_all(['td', 'th'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data and any(cell.strip() for cell in row_data):
                rows.append(row_data)
                if i < 3:  # Log les 3 premières lignes
                    logger.info(f"      Ligne {i}: {row_data}")
        
        # Créer le DataFrame
        if headers and rows:
            # S'assurer que toutes les lignes ont le même nombre de colonnes
            max_cols = max(len(headers), max(len(row) for row in rows) if rows else 0)
            headers = headers + [''] * (max_cols - len(headers))
            rows = [row + [''] * (max_cols - len(row)) for row in rows]
            
            df = pd.DataFrame(rows, columns=headers)
            logger.info(f"   ✅ [HTML->DF] DataFrame créé: {len(df)} lignes, {len(df.columns)} colonnes")
            return df
        
        logger.warning("   ⚠️ [HTML->DF] Pas de données à convertir")
        return pd.DataFrame()
        
    except Exception as e:
        logger.error(f"   ❌ [HTML->DF] Erreur conversion: {e}")
        return pd.DataFrame()

def dataframe_to_html(df: pd.DataFrame, original_html: str = "") -> str:
    """Convertit un DataFrame en table HTML avec le style ClaraVerse"""
    try:
        logger.info("   🔄 [DF->HTML] Début de la conversion...")
        logger.info(f"   📊 [DF->HTML] DataFrame: {len(df)} lignes, colonnes: {list(df.columns)}")
        
        # Parser le HTML original pour récupérer les attributs
        soup = BeautifulSoup(original_html, 'html.parser') if original_html else None
        original_table = soup.find('table') if soup else None
        
        # Récupérer les attributs de la table originale
        table_attrs = {}
        if original_table:
            for attr in ['class', 'style', 'data-table-id', 'data-observer-installed']:
                if original_table.get(attr):
                    table_attrs[attr] = original_table.get(attr)
            logger.info(f"   📋 [DF->HTML] Attributs récupérés: {table_attrs}")
        
        # Construire le HTML
        html_parts = ['<table']
        
        # Ajouter les attributs
        if table_attrs.get('class'):
            html_parts.append(f' class="{table_attrs["class"]}"')
        else:
            html_parts.append(' class="min-w-full border border-gray-200 dark:border-gray-700 rounded-lg"')
        
        if table_attrs.get('data-table-id'):
            html_parts.append(f' data-table-id="{table_attrs["data-table-id"]}"')
        
        if table_attrs.get('data-observer-installed'):
            html_parts.append(' data-observer-installed="true"')
        
        html_parts.append('>')
        
        # En-tête
        html_parts.append('<thead><tr>')
        for col in df.columns:
            html_parts.append(f'<th>{col}</th>')
        html_parts.append('</tr></thead>')
        
        logger.info(f"   📋 [DF->HTML] En-têtes générés: {list(df.columns)}")
        
        # Corps
        html_parts.append('<tbody>')
        for idx, row in df.iterrows():
            html_parts.append('<tr>')
            row_values = []
            for col in df.columns:
                value = row[col]
                # Formater les nombres
                if isinstance(value, (int, float)) and not pd.isna(value):
                    if col.lower() == 'ecart':
                        # Colorer les écarts
                        color = 'green' if value >= 0 else 'red'
                        cell_html = f'<td style="color: {color}; font-weight: bold;">{value:,.2f}</td>'
                        row_values.append(f"{value:,.2f}")
                    else:
                        cell_html = f'<td>{value:,.2f}</td>'
                        row_values.append(f"{value:,.2f}")
                else:
                    cell_html = f'<td>{value if not pd.isna(value) else ""}</td>'
                    row_values.append(str(value) if not pd.isna(value) else "")
                html_parts.append(cell_html)
            html_parts.append('</tr>')
            
            if idx < 3:  # Log les 3 premières lignes
                logger.info(f"      Ligne {idx}: {row_values}")
        
        html_parts.append('</tbody>')
        html_parts.append('</table>')
        
        result = ''.join(html_parts)
        logger.info(f"   ✅ [DF->HTML] HTML généré: {len(result)} caractères")
        
        return result
        
    except Exception as e:
        logger.error(f"   ❌ [DF->HTML] Erreur conversion: {e}")
        return ""

def clean_numeric_value(value: str) -> float:
    """Nettoie et convertit une valeur en nombre"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    
    try:
        # Supprimer les espaces et caractères non numériques (sauf - et .)
        cleaned = str(value).replace(' ', '').replace(',', '.').replace('€', '').replace('%', '')
        cleaned = re.sub(r'[^\d.\-]', '', cleaned)
        
        if cleaned == '' or cleaned == '-':
            return 0.0
        
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def find_ecart_columns(df: pd.DataFrame) -> Dict[str, List[str]]:
    """Identifie les colonnes pour le calcul d'écart"""
    columns_lower = {col.lower().strip(): col for col in df.columns}
    
    result = {
        'ecart': None,
        'numeric_columns': [],
        'formula_columns': []
    }
    
    # Chercher la colonne Ecart (dernière colonne nommée Ecart sans autre qualificatif)
    ecart_variants = ['ecart', 'écart']
    for col_lower, col_original in columns_lower.items():
        # Ecart simple (pas "Ecart constaté" etc.)
        if col_lower in ecart_variants:
            result['ecart'] = col_original
            break
    
    # Si pas trouvé, chercher une colonne contenant "ecart" mais pas d'autres mots clés
    if not result['ecart']:
        for col_lower, col_original in columns_lower.items():
            if 'ecart' in col_lower or 'écart' in col_lower:
                # Éviter "Ecart constaté" qui est une donnée source
                if 'constat' not in col_lower:
                    result['ecart'] = col_original
                    break
    
    # Identifier les colonnes numériques potentielles pour le calcul
    numeric_keywords = ['solde', 'montant', 'valeur', 'total', 'somme', 'ouverture', 'cloture', 
                       'clôture', 'acquisition', 'theorique', 'théorique', 'final', 'physique']
    
    for col_lower, col_original in columns_lower.items():
        for keyword in numeric_keywords:
            if keyword in col_lower:
                result['numeric_columns'].append(col_original)
                break
    
    return result

def find_columns_with_numeric_values(df: pd.DataFrame) -> List[str]:
    """Trouve les colonnes qui contiennent des valeurs numériques non nulles"""
    numeric_cols = []
    
    for col in df.columns:
        # Vérifier si la colonne contient des valeurs numériques
        has_numeric = False
        for val in df[col]:
            cleaned = clean_numeric_value(val)
            if cleaned != 0.0:
                has_numeric = True
                break
        
        if has_numeric:
            numeric_cols.append(col)
    
    return numeric_cols

def calculate_ecart_smart(df: pd.DataFrame, source_col1: str = None, source_col2: str = None, target_col: str = None) -> pd.DataFrame:
    """
    Calcule les écarts de manière intelligente en analysant le contexte des données.
    L'agent détecte automatiquement les colonnes avec des valeurs numériques
    et détermine la meilleure formule de calcul.
    """
    try:
        logger.info("   ⚙️ [CALCUL SMART] Début du calcul intelligent des écarts...")
        
        df_result = df.copy()
        
        # Trouver la colonne Ecart cible
        ecart_col = target_col
        if not ecart_col:
            col_info = find_ecart_columns(df)
            ecart_col = col_info.get('ecart')
        
        if not ecart_col:
            logger.warning("   ⚠️ [CALCUL SMART] Colonne 'Ecart' non trouvée!")
            return df_result
        
        logger.info(f"   🎯 [CALCUL SMART] Colonne cible pour l'écart: {ecart_col}")
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 1: Analyser toutes les colonnes et leurs valeurs
        # ═══════════════════════════════════════════════════════════
        logger.info("   📊 [ANALYSE] Analyse des colonnes...")
        
        column_analysis = []
        for col in df.columns:
            if col.lower() in ['ecart', 'écart']:
                continue  # Ignorer la colonne cible
            
            values = []
            for val in df_result[col]:
                cleaned = clean_numeric_value(val)
                values.append(cleaned)
            
            non_zero_count = sum(1 for v in values if v != 0)
            has_values = non_zero_count > 0
            
            column_analysis.append({
                'name': col,
                'values': values,
                'has_values': has_values,
                'non_zero_count': non_zero_count,
                'is_numeric_name': any(kw in col.lower() for kw in ['solde', 'montant', 'valeur', 'total', 'physique', 'théorique', 'theorique'])
            })
            
            if has_values:
                logger.info(f"      ✅ '{col}': {values} (non-zéro: {non_zero_count})")
            else:
                logger.info(f"      ⚪ '{col}': toutes les valeurs sont nulles ou vides")
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 2: Identifier les colonnes candidates pour le calcul
        # ═══════════════════════════════════════════════════════════
        logger.info("   🔍 [DÉTECTION] Recherche des colonnes pour le calcul...")
        
        # Colonnes avec des valeurs réelles (non nulles)
        cols_with_values = [c for c in column_analysis if c['has_values']]
        
        logger.info(f"   📋 Colonnes avec valeurs: {[c['name'] for c in cols_with_values]}")
        
        if len(cols_with_values) < 2:
            logger.warning("   ⚠️ Pas assez de colonnes avec des valeurs pour calculer l'écart")
            return df_result
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 3: Déterminer les deux colonnes à utiliser
        # ═══════════════════════════════════════════════════════════
        
        # Priorité 1: Colonnes nommées explicitement (Solde Physique, Solde Théorique)
        # mais seulement si elles ont des valeurs
        col1_name = None
        col2_name = None
        
        for c in cols_with_values:
            name_lower = c['name'].lower()
            if 'théorique' in name_lower or 'theorique' in name_lower:
                col1_name = c['name']
            elif 'physique' in name_lower:
                col2_name = c['name']
        
        # Si les colonnes nommées n'ont pas de valeurs, utiliser les colonnes avec des valeurs
        if not col1_name or not col2_name:
            logger.info("   🔄 [FALLBACK] Utilisation des colonnes avec valeurs réelles...")
            
            # Prendre les deux dernières colonnes avec des valeurs avant "Ecart"
            # Car généralement les colonnes de calcul sont juste avant la colonne Ecart
            ecart_index = list(df.columns).index(ecart_col) if ecart_col in df.columns else len(df.columns)
            
            # Filtrer les colonnes avant Ecart qui ont des valeurs
            cols_before_ecart = []
            for c in cols_with_values:
                col_index = list(df.columns).index(c['name']) if c['name'] in df.columns else -1
                if col_index < ecart_index and col_index >= 0:
                    cols_before_ecart.append((col_index, c))
            
            # Trier par position (les plus proches de Ecart en premier)
            cols_before_ecart.sort(key=lambda x: x[0], reverse=True)
            
            if len(cols_before_ecart) >= 2:
                # Prendre les deux colonnes les plus proches de Ecart
                # col1 = avant-dernière colonne (ex: Statut Rapprochement)
                # col2 = dernière colonne avant Ecart (ex: Approbation Ecart)
                # Ecart = col1 - col2
                col1_name = cols_before_ecart[1][1]['name']  # Avant-dernière
                col2_name = cols_before_ecart[0][1]['name']  # Dernière avant Ecart
            elif len(cols_with_values) >= 2:
                # Fallback: prendre les deux premières colonnes avec des valeurs
                col1_name = cols_with_values[0]['name']
                col2_name = cols_with_values[1]['name']
        
        if not col1_name or not col2_name:
            logger.warning("   ⚠️ Impossible de déterminer les colonnes pour le calcul")
            return df_result
        
        logger.info(f"   ✅ [COLONNES SÉLECTIONNÉES]:")
        logger.info(f"      - Colonne 1: {col1_name}")
        logger.info(f"      - Colonne 2: {col2_name}")
        
        # ═══════════════════════════════════════════════════════════
        # ÉTAPE 4: Calculer l'écart
        # ═══════════════════════════════════════════════════════════
        logger.info("   🧮 [CALCUL] Calcul de l'écart...")
        
        # Convertir les colonnes en numérique
        df_result[col1_name] = df_result[col1_name].apply(clean_numeric_value)
        df_result[col2_name] = df_result[col2_name].apply(clean_numeric_value)
        
        # Calculer l'écart (col1 - col2)
        df_result[ecart_col] = df_result[col1_name] - df_result[col2_name]
        
        logger.info(f"   📊 [RÉSULTAT] Formule: {col1_name} - {col2_name}")
        logger.info(f"      - Valeurs {col1_name}: {df_result[col1_name].tolist()}")
        logger.info(f"      - Valeurs {col2_name}: {df_result[col2_name].tolist()}")
        logger.info(f"      - Écarts calculés: {df_result[ecart_col].tolist()}")
        
        return df_result
        
    except Exception as e:
        logger.error(f"   ❌ [CALCUL SMART] Erreur: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return df

def calculate_ecart_simple(df: pd.DataFrame) -> pd.DataFrame:
    """Calcule les écarts de manière simple sans LLM"""
    try:
        logger.info("   ⚙️ [CALCUL] Début du calcul des écarts...")
        
        df_result = df.copy()
        col_info = find_ecart_columns(df)
        
        logger.info(f"   📋 [CALCUL] Colonnes détectées: {col_info}")
        
        if not col_info['ecart']:
            logger.warning("   ⚠️ [CALCUL] Colonne 'Ecart' non trouvée!")
            return df_result
        
        ecart_col = col_info['ecart']
        numeric_cols = col_info['numeric_columns']
        
        logger.info(f"   📊 [CALCUL] Colonne écart: {ecart_col}")
        logger.info(f"   📊 [CALCUL] Colonnes numériques: {numeric_cols}")
        
        # Convertir les colonnes numériques
        for col in numeric_cols:
            logger.info(f"   🔢 [CALCUL] Conversion colonne '{col}':")
            original_values = df_result[col].tolist()[:3]
            df_result[col] = df_result[col].apply(clean_numeric_value)
            converted_values = df_result[col].tolist()[:3]
            logger.info(f"      Avant: {original_values}")
            logger.info(f"      Après: {converted_values}")
        
        # Logique de calcul d'écart
        # Chercher des paires logiques: Solde final théorique - Solde BG clôture
        solde_final = None
        solde_cloture = None
        
        for col in numeric_cols:
            col_lower = col.lower()
            if 'théorique' in col_lower or 'theorique' in col_lower or 'final' in col_lower:
                solde_final = col
            elif 'clôture' in col_lower or 'cloture' in col_lower or 'bg' in col_lower:
                solde_cloture = col
        
        logger.info(f"   🎯 [CALCUL] Colonnes identifiées pour le calcul:")
        logger.info(f"      - Solde final/théorique: {solde_final}")
        logger.info(f"      - Solde clôture/BG: {solde_cloture}")
        
        if solde_final and solde_cloture:
            logger.info(f"   ✅ [CALCUL] Formule: {solde_final} - {solde_cloture}")
            df_result[ecart_col] = df_result[solde_final] - df_result[solde_cloture]
        elif len(numeric_cols) >= 2:
            # Fallback: dernière colonne numérique - première colonne numérique
            logger.info(f"   ⚠️ [CALCUL] Fallback: {numeric_cols[-1]} - {numeric_cols[0]}")
            df_result[ecart_col] = df_result[numeric_cols[-1]] - df_result[numeric_cols[0]]
        else:
            logger.warning("   ⚠️ [CALCUL] Pas assez de colonnes numériques pour calculer l'écart")
        
        # Afficher les résultats
        logger.info(f"   📊 [CALCUL] Valeurs d'écart calculées:")
        for i, val in enumerate(df_result[ecart_col].tolist()[:5]):
            logger.info(f"      Ligne {i}: {val}")
        
        return df_result
        
    except Exception as e:
        logger.error(f"   ❌ [CALCUL] Erreur: {e}")
        return df

# ============================================
# AGENT PANDAS AVEC LANGCHAIN
# ============================================

class PandasAgentManager:
    """Gestionnaire de l'agent Pandas avec LangChain"""
    
    def __init__(self):
        self.llm = None
        self.initialized = False
        
    def initialize(self):
        """Initialise l'agent (mode simple)"""
        self.initialized = True
        logger.info("✅ Agent Pandas initialisé en mode calcul simple")
        return True
    
    def process_table(self, df: pd.DataFrame, action: str = "calculate_ecart", 
                     source_col1: str = None, source_col2: str = None, target_col: str = None) -> pd.DataFrame:
        """Traite une table avec calcul simple des écarts"""
        logger.info("Mode calcul smart activé")
        return calculate_ecart_smart(df, source_col1, source_col2, target_col)

# Instance globale de l'agent
pandas_agent = PandasAgentManager()

# ============================================
# ENDPOINTS API
# ============================================

@router.post("/process", response_model=AgentResponse)
async def process_tables(request: TablesRequest):
    """
    Traite les tables HTML avec l'agent Pandas.
    Calcule les écarts et retourne le HTML modifié.
    """
    try:
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🐼 [PANDAS AGENT BACKEND] DÉBUT DU TRAITEMENT")
        logger.info("═══════════════════════════════════════════════════════════")
        
        logger.info(f"\n📊 [ÉTAPE 1] DONNÉES REÇUES:")
        logger.info(f"   - Nombre de tables: {len(request.tables)}")
        logger.info(f"   - Table cible ID: {request.targetTableId}")
        logger.info(f"   - Action demandée: {request.action}")
        
        for i, table in enumerate(request.tables):
            logger.info(f"   - Table {i}: ID='{table.tableId}', HTML length={len(table.outerHTML)}")
        
        # Initialiser l'agent si nécessaire
        if not pandas_agent.initialized:
            pandas_agent.initialize()
        
        # Trouver la table cible
        logger.info(f"\n🔍 [ÉTAPE 2] RECHERCHE DE LA TABLE CIBLE")
        target_table = None
        for table in request.tables:
            if table.tableId == request.targetTableId:
                target_table = table
                logger.info(f"   ✅ Table cible trouvée: {table.tableId}")
                break
        
        if not target_table:
            logger.error(f"   ❌ Table cible '{request.targetTableId}' non trouvée!")
            raise HTTPException(status_code=404, detail=f"Table cible '{request.targetTableId}' non trouvée")
        
        # Convertir en DataFrame
        logger.info(f"\n📋 [ÉTAPE 3] CONVERSION HTML -> DATAFRAME")
        logger.info(f"   - HTML reçu (500 premiers chars): {target_table.outerHTML[:500]}")
        
        df = html_to_dataframe(target_table.outerHTML)
        
        if df.empty:
            logger.error("   ❌ DataFrame vide après conversion!")
            raise HTTPException(status_code=400, detail="La table est vide ou mal formatée")
        
        logger.info(f"   ✅ DataFrame créé:")
        logger.info(f"      - Lignes: {len(df)}")
        logger.info(f"      - Colonnes: {list(df.columns)}")
        logger.info(f"   📊 Aperçu des données:")
        logger.info(f"\n{df.to_string()}")
        
        # Traiter avec l'agent
        logger.info(f"\n⚙️ [ÉTAPE 4] CALCUL DES ÉCARTS")
        df_result = pandas_agent.process_table(df, request.action)
        
        logger.info(f"   ✅ Calculs effectués:")
        logger.info(f"      - Lignes résultat: {len(df_result)}")
        logger.info(f"      - Colonnes résultat: {list(df_result.columns)}")
        logger.info(f"   📊 Résultat:")
        logger.info(f"\n{df_result.to_string()}")
        
        # Convertir en HTML
        logger.info(f"\n📤 [ÉTAPE 5] CONVERSION DATAFRAME -> HTML")
        result_html = dataframe_to_html(df_result, target_table.outerHTML)
        
        logger.info(f"   - HTML généré: {len(result_html)} caractères")
        logger.info(f"   - HTML (500 premiers chars): {result_html[:500]}")
        
        # Préparer les informations de calcul
        calculations = {
            "rows_processed": len(df_result),
            "columns": list(df_result.columns),
            "ecart_column_found": any('ecart' in col.lower() for col in df_result.columns)
        }
        
        logger.info(f"\n📦 [ÉTAPE 6] PRÉPARATION DE LA RÉPONSE")
        logger.info(f"   - success: True")
        logger.info(f"   - targetTableId: {request.targetTableId}")
        logger.info(f"   - resultHTML length: {len(result_html)}")
        logger.info(f"   - calculations: {calculations}")
        
        response = AgentResponse(
            success=True,
            targetTableId=request.targetTableId,
            resultHTML=result_html,
            message=f"✅ Calculs effectués sur {len(df_result)} lignes",
            calculations=calculations
        )
        
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🐼 [PANDAS AGENT BACKEND] TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("═══════════════════════════════════════════════════════════\n")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("═══════════════════════════════════════════════════════════")
        logger.error(f"❌ [PANDAS AGENT BACKEND] ERREUR: {e}")
        logger.error("═══════════════════════════════════════════════════════════\n")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Vérifie le statut de l'agent Pandas"""
    return {
        "langchain_available": LANGCHAIN_AVAILABLE,
        "agent_initialized": pandas_agent.initialized,
        "gemini_configured": bool(GEMINI_API_KEY),
        "message": "Agent Pandas prêt" if pandas_agent.initialized else "Agent en mode simple"
    }

@router.post("/test")
async def test_agent():
    """Test de l'agent avec des données exemple"""
    try:
        # Données de test
        test_data = {
            'Compte': ['101', '102', '103'],
            'Libelle': ['Compte A', 'Compte B', 'Compte C'],
            'Solde BG clôture': [1000, 2000, 3000],
            'Solde final théorique': [1100, 1900, 3200],
            'Ecart': ['', '', '']
        }
        
        df = pd.DataFrame(test_data)
        
        # Initialiser et traiter
        if not pandas_agent.initialized:
            pandas_agent.initialize()
        
        df_result = pandas_agent.process_table(df)
        
        return {
            "success": True,
            "input": test_data,
            "output": df_result.to_dict(orient='records'),
            "message": "Test réussi"
        }
        
    except Exception as e:
        logger.error(f"❌ Erreur test: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.post("/process-json", response_model=AgentJsonResponse)
async def process_tables_json(request: TablesJsonRequest):
    """
    Traite les tables en format JSON avec l'agent Pandas.
    Calcule les écarts et retourne les données en JSON.
    """
    try:
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🐼 [PANDAS AGENT JSON] DÉBUT DU TRAITEMENT")
        logger.info("═══════════════════════════════════════════════════════════")
        
        logger.info(f"\n📊 [ÉTAPE 1] DONNÉES JSON REÇUES:")
        logger.info(f"   - Nombre de tables: {len(request.tables)}")
        logger.info(f"   - Table cible ID: {request.targetTableId}")
        logger.info(f"   - Action demandée: {request.action}")
        logger.info(f"   - Source Column 1: {request.sourceColumn1}")
        logger.info(f"   - Source Column 2: {request.sourceColumn2}")
        logger.info(f"   - Target Column: {request.targetColumn}")
        
        for i, table in enumerate(request.tables):
            logger.info(f"   - Table {i}: ID='{table.tableId}', headers={table.headers}, rows={len(table.rows)}")
        
        # Initialiser l'agent si nécessaire
        if not pandas_agent.initialized:
            pandas_agent.initialize()
        
        # Trouver la table cible
        logger.info(f"\n🔍 [ÉTAPE 2] RECHERCHE DE LA TABLE CIBLE")
        target_table = None
        for table in request.tables:
            if table.tableId == request.targetTableId:
                target_table = table
                logger.info(f"   ✅ Table cible trouvée: {table.tableId}")
                break
        
        if not target_table:
            logger.error(f"   ❌ Table cible '{request.targetTableId}' non trouvée!")
            raise HTTPException(status_code=404, detail=f"Table cible '{request.targetTableId}' non trouvée")
        
        # Créer le DataFrame directement depuis les données JSON
        logger.info(f"\n📋 [ÉTAPE 3] CRÉATION DU DATAFRAME DEPUIS JSON")
        logger.info(f"   - Headers: {target_table.headers}")
        logger.info(f"   - Nombre de lignes: {len(target_table.rows)}")
        
        for i, row in enumerate(target_table.rows[:3]):
            logger.info(f"   - Ligne {i}: {row}")
        
        df = pd.DataFrame(target_table.rows, columns=target_table.headers)
        
        if df.empty:
            logger.error("   ❌ DataFrame vide!")
            raise HTTPException(status_code=400, detail="La table est vide")
        
        logger.info(f"   ✅ DataFrame créé:")
        logger.info(f"      - Lignes: {len(df)}")
        logger.info(f"      - Colonnes: {list(df.columns)}")
        logger.info(f"   📊 Aperçu des données:")
        logger.info(f"\n{df.to_string()}")
        
        # Traiter avec l'agent
        logger.info(f"\n⚙️ [ÉTAPE 4] CALCUL DES ÉCARTS")
        df_result = pandas_agent.process_table(
            df, 
            request.action,
            source_col1=request.sourceColumn1,
            source_col2=request.sourceColumn2,
            target_col=request.targetColumn
        )
        
        logger.info(f"   ✅ Calculs effectués:")
        logger.info(f"      - Lignes résultat: {len(df_result)}")
        logger.info(f"      - Colonnes résultat: {list(df_result.columns)}")
        logger.info(f"   📊 Résultat:")
        logger.info(f"\n{df_result.to_string()}")
        
        # Convertir en listes pour la réponse JSON
        result_headers = list(df_result.columns)
        result_rows = []
        
        for _, row in df_result.iterrows():
            row_data = []
            for col in df_result.columns:
                value = row[col]
                if isinstance(value, (int, float)) and not pd.isna(value):
                    row_data.append(f"{value:,.2f}")
                else:
                    row_data.append(str(value) if not pd.isna(value) else "")
            result_rows.append(row_data)
        
        # Préparer les informations de calcul
        calculations = {
            "rows_processed": len(df_result),
            "columns": result_headers,
            "ecart_column_found": any('ecart' in col.lower() for col in df_result.columns),
            "source_columns_used": [request.sourceColumn1, request.sourceColumn2] if request.sourceColumn1 else "auto-detected"
        }
        
        logger.info(f"\n📦 [ÉTAPE 5] PRÉPARATION DE LA RÉPONSE JSON")
        logger.info(f"   - success: True")
        logger.info(f"   - headers: {result_headers}")
        logger.info(f"   - rows count: {len(result_rows)}")
        
        response = AgentJsonResponse(
            success=True,
            targetTableId=request.targetTableId,
            headers=result_headers,
            rows=result_rows,
            message=f"✅ Calculs effectués sur {len(df_result)} lignes",
            calculations=calculations
        )
        
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🐼 [PANDAS AGENT JSON] TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("═══════════════════════════════════════════════════════════\n")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("═══════════════════════════════════════════════════════════")
        logger.error(f"❌ [PANDAS AGENT JSON] ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("═══════════════════════════════════════════════════════════\n")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/process-all-tables", response_model=AgentMultiTableResponse)
async def process_all_tables(request: TablesJsonRequest):
    """
    Traite TOUTES les tables: modifie la DERNIÈRE table (modelized) et retourne l'ensemble.
    """
    try:
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🐼 [PANDAS AGENT ALL TABLES] DÉBUT DU TRAITEMENT")
        logger.info("═══════════════════════════════════════════════════════════")
        
        logger.info(f"\n📊 [ÉTAPE 1] DONNÉES REÇUES:")
        logger.info(f"   - Nombre de tables: {len(request.tables)}")
        logger.info(f"   - Action demandée: {request.action}")
        
        for i, table in enumerate(request.tables):
            logger.info(f"   - Table {i}: ID='{table.tableId}', headers={table.headers}, rows={len(table.rows)}")
        
        if len(request.tables) == 0:
            raise HTTPException(status_code=400, detail="Aucune table fournie")
        
        # Initialiser l'agent si nécessaire
        if not pandas_agent.initialized:
            pandas_agent.initialize()
        
        # La table cible est la DERNIÈRE table (modelized table)
        target_index = len(request.tables) - 1
        target_table = request.tables[target_index]
        
        logger.info(f"\n🎯 [ÉTAPE 2] TABLE CIBLE (DERNIÈRE): {target_table.tableId}")
        logger.info(f"   - Headers: {target_table.headers}")
        logger.info(f"   - Lignes: {len(target_table.rows)}")
        
        # Créer le DataFrame de la table cible
        df = pd.DataFrame(target_table.rows, columns=target_table.headers)
        
        if df.empty:
            logger.warning("   ⚠️ Table cible vide, pas de calcul")
        else:
            logger.info(f"   📊 Aperçu avant calcul:")
            logger.info(f"\n{df.to_string()}")
            
            # Traiter avec l'agent
            logger.info(f"\n⚙️ [ÉTAPE 3] CALCUL DES ÉCARTS SUR LA DERNIÈRE TABLE")
            df_result = pandas_agent.process_table(
                df, 
                request.action,
                source_col1=request.sourceColumn1,
                source_col2=request.sourceColumn2,
                target_col=request.targetColumn
            )
            
            logger.info(f"   ✅ Calculs effectués")
            logger.info(f"   📊 Résultat:")
            logger.info(f"\n{df_result.to_string()}")
        
        # Préparer la réponse avec TOUTES les tables
        logger.info(f"\n📦 [ÉTAPE 4] PRÉPARATION DE TOUTES LES TABLES")
        
        output_tables = []
        
        for i, table in enumerate(request.tables):
            if i == target_index and not df.empty:
                # Table modifiée (dernière)
                result_rows = []
                for _, row in df_result.iterrows():
                    row_data = []
                    for col in df_result.columns:
                        value = row[col]
                        if isinstance(value, (int, float)) and not pd.isna(value):
                            row_data.append(f"{value:,.2f}")
                        else:
                            row_data.append(str(value) if not pd.isna(value) else "")
                    result_rows.append(row_data)
                
                output_tables.append(TableJsonOutput(
                    tableId=table.tableId,
                    headers=list(df_result.columns),
                    rows=result_rows
                ))
                logger.info(f"   ✅ Table {i} (MODIFIÉE): {table.tableId}")
            else:
                # Tables non modifiées (retournées telles quelles)
                output_tables.append(TableJsonOutput(
                    tableId=table.tableId,
                    headers=table.headers,
                    rows=table.rows
                ))
                logger.info(f"   📋 Table {i} (inchangée): {table.tableId}")
        
        # Préparer les informations de calcul
        calculations = {
            "total_tables": len(request.tables),
            "modified_table_index": target_index,
            "modified_table_id": target_table.tableId,
            "rows_processed": len(df_result) if not df.empty else 0,
            "ecart_column_found": any('ecart' in col.lower() for col in df_result.columns) if not df.empty else False
        }
        
        response = AgentMultiTableResponse(
            success=True,
            tables=output_tables,
            targetTableId=target_table.tableId,
            message=f"✅ {len(output_tables)} tables retournées, table {target_index} modifiée",
            calculations=calculations
        )
        
        logger.info("═══════════════════════════════════════════════════════════")
        logger.info("🐼 [PANDAS AGENT ALL TABLES] TRAITEMENT TERMINÉ AVEC SUCCÈS")
        logger.info("═══════════════════════════════════════════════════════════\n")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("═══════════════════════════════════════════════════════════")
        logger.error(f"❌ [PANDAS AGENT ALL TABLES] ERREUR: {e}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("═══════════════════════════════════════════════════════════\n")
        raise HTTPException(status_code=500, detail=str(e))
