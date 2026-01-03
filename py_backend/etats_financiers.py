"""
États Financiers SYSCOHADA Révisé
Script de calcul du Bilan et Compte de Résultat à partir d'une Balance
Utilise le tableau de correspondance SYSCOHADA pour mapper les comptes aux rubriques
"""

import pandas as pd
import numpy as np
import json
import logging
import os
from typing import Dict, List, Any, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from io import BytesIO

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("etats-financiers")

# Créer le router FastAPI
router = APIRouter(prefix="/etats-financiers", tags=["États Financiers SYSCOHADA"])

# Chemin vers le fichier de correspondance
CORRESPONDANCE_FILE = os.path.join(os.path.dirname(__file__), "Tableau correspondance.xlsx")

# ============================================
# MODÈLES PYDANTIC
# ============================================

class BalanceData(BaseModel):
    """Données de balance en JSON"""
    headers: List[str]
    rows: List[List[str]]

class EtatsFinanciersRequest(BaseModel):
    """Requête pour calculer les états financiers"""
    balance: BalanceData
    exercice_n: Optional[str] = "N"
    exercice_n1: Optional[str] = "N-1"

class RubriqueResult(BaseModel):
    """Résultat d'une rubrique"""
    code: str
    libelle: str
    montant_n: float
    montant_n1: float

class EtatFinancierResult(BaseModel):
    """Résultat d'un état financier (Bilan ou Compte de Résultat)"""
    titre: str
    rubriques: List[RubriqueResult]
    total: Dict[str, float]

class EtatsFinanciersResponse(BaseModel):
    """Réponse complète des états financiers"""
    success: bool
    message: str
    bilan_actif: Optional[EtatFinancierResult] = None
    bilan_passif: Optional[EtatFinancierResult] = None
    compte_resultat: Optional[EtatFinancierResult] = None
    exercice_n: str
    exercice_n1: str

# ============================================
# CLASSE PRINCIPALE
# ============================================

class EtatsFinanciersCalculator:
    """Calculateur des états financiers SYSCOHADA révisé"""
    
    def __init__(self):
        self.correspondance_df = None
        self.balance_df = None
        self.load_correspondance()
    
    def load_correspondance(self):
        """Charge et parse le tableau de correspondance SYSCOHADA depuis Excel"""
        try:
            if os.path.exists(CORRESPONDANCE_FILE):
                # Lire le fichier Excel brut
                raw_df = pd.read_excel(CORRESPONDANCE_FILE, header=None)
                logger.info(f"📊 Fichier Excel lu: {len(raw_df)} lignes, {len(raw_df.columns)} colonnes")
                
                # Parser le tableau de correspondance SYSCOHADA
                self.correspondance_df = self._parse_correspondance_excel(raw_df)
                logger.info(f"✅ Tableau de correspondance parsé: {len(self.correspondance_df)} rubriques")
                
                # Afficher quelques exemples
                if len(self.correspondance_df) > 0:
                    logger.info(f"   Exemples de rubriques:")
                    for _, row in self.correspondance_df.head(5).iterrows():
                        logger.info(f"      {row['rubrique']}: {row['libelle'][:30]}... → {row['comptes'][:50]}...")
            else:
                logger.warning(f"⚠️ Fichier de correspondance non trouvé: {CORRESPONDANCE_FILE}")
                self.correspondance_df = self._create_default_correspondance()
        except Exception as e:
            logger.error(f"❌ Erreur chargement correspondance: {e}")
            import traceback
            logger.error(traceback.format_exc())
            self.correspondance_df = self._create_default_correspondance()
    
    def _parse_correspondance_excel(self, raw_df: pd.DataFrame) -> pd.DataFrame:
        """
        Parse le fichier Excel de correspondance SYSCOHADA.
        Structure attendue:
        - Colonne 0: Référence (AA, AB, AC, etc.) ou titre de section
        - Colonne 1: Libellé de la rubrique
        - Colonne 2: Numéros de comptes à incorporer
        """
        correspondances = []
        current_section = "ACTIF"  # Section par défaut
        
        for idx, row in raw_df.iterrows():
            col0 = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
            col1 = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else ""
            col2 = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else ""
            
            # Détecter les sections
            if "BILAN" in col0.upper() and "ACTIF" in col0.upper():
                current_section = "ACTIF"
                continue
            elif "BILAN" in col0.upper() and "PASSIF" in col0.upper():
                current_section = "PASSIF"
                continue
            elif "RÉSULTAT" in col0.upper() or "RESULTAT" in col0.upper():
                if "DÉBIT" in col0.upper() or "DEBIT" in col0.upper() or "CHARGES" in col0.upper():
                    current_section = "CHARGE"
                elif "CRÉDIT" in col0.upper() or "CREDIT" in col0.upper() or "PRODUITS" in col0.upper():
                    current_section = "PRODUIT"
                continue
            
            # Ignorer les lignes d'en-tête ou vides
            if not col0 or col0.startswith("📊") or col0.startswith("Réf") or "Tableau" in col0:
                continue
            
            # Vérifier si c'est une rubrique valide (2 lettres majuscules)
            if len(col0) == 2 and col0.isalpha() and col0.isupper():
                # C'est une rubrique (AA, AB, AC, etc.)
                rubrique_code = col0
                libelle = col1
                comptes_raw = col2
                
                # Si pas de comptes, c'est probablement un titre de section (AA, AD, AI, etc.)
                if not comptes_raw or comptes_raw == "nan" or comptes_raw == "NaN":
                    # C'est un titre de section, on le garde quand même pour référence
                    logger.debug(f"   Section: {rubrique_code} - {libelle}")
                    continue
                
                # Parser les numéros de comptes
                comptes_list = self._parse_comptes_string(comptes_raw)
                
                if comptes_list:
                    correspondances.append({
                        "rubrique": rubrique_code,
                        "libelle": libelle,
                        "comptes": ",".join(comptes_list),
                        "type": current_section
                    })
                    logger.debug(f"   ✓ {rubrique_code}: {libelle[:30]}... → {comptes_list[:5]}...")
        
        logger.info(f"   📊 Sections trouvées: ACTIF={sum(1 for c in correspondances if c['type']=='ACTIF')}, "
                   f"PASSIF={sum(1 for c in correspondances if c['type']=='PASSIF')}, "
                   f"PRODUIT={sum(1 for c in correspondances if c['type']=='PRODUIT')}, "
                   f"CHARGE={sum(1 for c in correspondances if c['type']=='CHARGE')}")
        
        return pd.DataFrame(correspondances)
    
    def _parse_comptes_string(self, comptes_raw: str) -> List[str]:
        """
        Parse une chaîne de comptes SYSCOHADA.
        Exemples:
        - "201, 202" → ["201", "202"]
        - "211, 2191 – 2811, 2919 p" → ["211", "2191", "2811", "2919"]
        - "22 – 282, 292" → ["22", "282", "292"]
        - "24 (sauf 245)" → ["24"] (on ignore les exclusions pour l'instant)
        """
        if not comptes_raw or comptes_raw == "nan":
            return []
        
        comptes = []
        
        # Nettoyer la chaîne
        cleaned = comptes_raw.replace("–", ",").replace("-", ",").replace("à", ",")
        
        # Supprimer les annotations (sauf ...), p, etc.
        import re
        cleaned = re.sub(r'\([^)]*\)', '', cleaned)  # Supprimer (sauf ...)
        cleaned = re.sub(r'\s+p\b', '', cleaned)     # Supprimer " p"
        
        # Séparer par virgule
        parts = cleaned.split(",")
        
        for part in parts:
            part = part.strip()
            # Extraire uniquement les chiffres
            compte = ''.join(c for c in part if c.isdigit())
            if compte and len(compte) >= 2:  # Au moins 2 chiffres
                comptes.append(compte)
        
        return comptes

    def _create_default_correspondance(self) -> pd.DataFrame:
        """Crée un tableau de correspondance par défaut SYSCOHADA révisé"""
        # Structure simplifiée du plan comptable SYSCOHADA
        data = [
            # BILAN ACTIF - Actif immobilisé
            {"rubrique": "AA", "libelle": "Immobilisations incorporelles", "comptes": "21", "type": "ACTIF"},
            {"rubrique": "AB", "libelle": "Immobilisations corporelles", "comptes": "22,23,24", "type": "ACTIF"},
            {"rubrique": "AC", "libelle": "Avances et acomptes versés", "comptes": "251,252", "type": "ACTIF"},
            {"rubrique": "AD", "libelle": "Immobilisations financières", "comptes": "26,27", "type": "ACTIF"},
            # BILAN ACTIF - Actif circulant
            {"rubrique": "BA", "libelle": "Stocks et en-cours", "comptes": "31,32,33,34,35,36,37,38", "type": "ACTIF"},
            {"rubrique": "BB", "libelle": "Créances clients", "comptes": "41", "type": "ACTIF"},
            {"rubrique": "BC", "libelle": "Autres créances", "comptes": "42,43,44,45,46,47", "type": "ACTIF"},
            {"rubrique": "BD", "libelle": "Trésorerie actif", "comptes": "51,52,53,54,57,58", "type": "ACTIF"},
            # BILAN PASSIF - Capitaux propres
            {"rubrique": "CA", "libelle": "Capital social", "comptes": "101,102,103,104,105", "type": "PASSIF"},
            {"rubrique": "CB", "libelle": "Réserves", "comptes": "11", "type": "PASSIF"},
            {"rubrique": "CC", "libelle": "Report à nouveau", "comptes": "12", "type": "PASSIF"},
            {"rubrique": "CD", "libelle": "Résultat de l'exercice", "comptes": "13", "type": "PASSIF"},
            # BILAN PASSIF - Dettes
            {"rubrique": "DA", "libelle": "Emprunts et dettes financières", "comptes": "16,17", "type": "PASSIF"},
            {"rubrique": "DB", "libelle": "Dettes fournisseurs", "comptes": "40", "type": "PASSIF"},
            {"rubrique": "DC", "libelle": "Dettes fiscales et sociales", "comptes": "42,43,44", "type": "PASSIF"},
            {"rubrique": "DD", "libelle": "Autres dettes", "comptes": "45,46,47,48", "type": "PASSIF"},
            {"rubrique": "DE", "libelle": "Trésorerie passif", "comptes": "56,59", "type": "PASSIF"},
            # COMPTE DE RÉSULTAT - Produits
            {"rubrique": "TA", "libelle": "Ventes de marchandises", "comptes": "701", "type": "PRODUIT"},
            {"rubrique": "TB", "libelle": "Ventes de produits fabriqués", "comptes": "702,703,704,705,706", "type": "PRODUIT"},
            {"rubrique": "TC", "libelle": "Travaux, services vendus", "comptes": "707,708", "type": "PRODUIT"},
            {"rubrique": "TD", "libelle": "Production stockée", "comptes": "73", "type": "PRODUIT"},
            {"rubrique": "TE", "libelle": "Production immobilisée", "comptes": "72", "type": "PRODUIT"},
            {"rubrique": "TF", "libelle": "Subventions d'exploitation", "comptes": "71", "type": "PRODUIT"},
            {"rubrique": "TG", "libelle": "Autres produits", "comptes": "75,77,78,79", "type": "PRODUIT"},
            # COMPTE DE RÉSULTAT - Charges
            {"rubrique": "RA", "libelle": "Achats de marchandises", "comptes": "601", "type": "CHARGE"},
            {"rubrique": "RB", "libelle": "Achats de matières premières", "comptes": "602,603,604,605,606,608", "type": "CHARGE"},
            {"rubrique": "RC", "libelle": "Variation de stocks", "comptes": "603", "type": "CHARGE"},
            {"rubrique": "RD", "libelle": "Transports", "comptes": "61", "type": "CHARGE"},
            {"rubrique": "RE", "libelle": "Services extérieurs", "comptes": "62,63", "type": "CHARGE"},
            {"rubrique": "RF", "libelle": "Impôts et taxes", "comptes": "64", "type": "CHARGE"},
            {"rubrique": "RG", "libelle": "Charges de personnel", "comptes": "66", "type": "CHARGE"},
            {"rubrique": "RH", "libelle": "Dotations amortissements", "comptes": "68,69", "type": "CHARGE"},
            {"rubrique": "RI", "libelle": "Autres charges", "comptes": "65,67", "type": "CHARGE"},
        ]
        return pd.DataFrame(data)

    def parse_balance(self, balance_data: BalanceData) -> pd.DataFrame:
        """Parse les données de balance JSON en DataFrame"""
        try:
            headers = balance_data.headers
            rows = balance_data.rows
            
            # Normaliser les en-têtes
            headers_normalized = [h.strip().lower() for h in headers]
            
            df = pd.DataFrame(rows, columns=headers)
            
            logger.info(f"📊 Balance parsée: {len(df)} lignes, colonnes: {list(df.columns)}")
            
            # Identifier les colonnes clés
            col_mapping = self._identify_columns(headers_normalized, headers)
            logger.info(f"   Mapping colonnes: {col_mapping}")
            
            return df, col_mapping
            
        except Exception as e:
            logger.error(f"❌ Erreur parsing balance: {e}")
            raise HTTPException(status_code=400, detail=f"Erreur parsing balance: {e}")
    
    def _identify_columns(self, headers_norm: List[str], headers_orig: List[str]) -> Dict[str, str]:
        """Identifie les colonnes de la balance"""
        mapping = {
            "numero": None,
            "intitule": None,
            "debit_n": None,
            "credit_n": None,
            "solde_debit_n": None,
            "solde_credit_n": None,
            "debit_n1": None,
            "credit_n1": None,
            "solde_debit_n1": None,
            "solde_credit_n1": None,
        }
        
        for i, h in enumerate(headers_norm):
            orig = headers_orig[i]
            
            # Numéro de compte
            if any(k in h for k in ["numéro", "numero", "compte", "n°"]):
                if mapping["numero"] is None:
                    mapping["numero"] = orig
            
            # Intitulé
            elif any(k in h for k in ["intitulé", "intitule", "libellé", "libelle", "désignation"]):
                if mapping["intitule"] is None:
                    mapping["intitule"] = orig
            
            # Colonnes N-1 (antérieur)
            elif "ant" in h:
                if "débit" in h or "debit" in h:
                    if "solde" in h:
                        mapping["solde_debit_n1"] = orig
                    else:
                        mapping["debit_n1"] = orig
                elif "crédit" in h or "credit" in h:
                    if "solde" in h:
                        mapping["solde_credit_n1"] = orig
                    else:
                        mapping["credit_n1"] = orig
            
            # Colonnes N (solde)
            elif "solde" in h:
                if "débit" in h or "debit" in h:
                    mapping["solde_debit_n"] = orig
                elif "crédit" in h or "credit" in h:
                    mapping["solde_credit_n"] = orig
            
            # Débit/Crédit N
            elif "débit" in h or "debit" in h:
                if mapping["debit_n"] is None:
                    mapping["debit_n"] = orig
            elif "crédit" in h or "credit" in h:
                if mapping["credit_n"] is None:
                    mapping["credit_n"] = orig
        
        return mapping

    def _clean_numeric(self, value) -> float:
        """Nettoie et convertit une valeur en nombre"""
        if pd.isna(value) or value == '' or value is None:
            return 0.0
        try:
            cleaned = str(value).replace(' ', '').replace(',', '.').replace('€', '').replace('%', '')
            cleaned = ''.join(c for c in cleaned if c.isdigit() or c in '.-')
            return float(cleaned) if cleaned and cleaned != '-' else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    def _get_compte_prefix(self, compte: str) -> str:
        """Extrait le préfixe du compte (2-3 premiers chiffres)"""
        compte_str = str(compte).strip()
        # Retourner les 2 ou 3 premiers caractères selon la longueur
        if len(compte_str) >= 3:
            return compte_str[:3]
        elif len(compte_str) >= 2:
            return compte_str[:2]
        return compte_str
    
    def _match_compte_to_rubrique(self, compte: str, correspondance: pd.DataFrame) -> Optional[Dict]:
        """
        Trouve la rubrique correspondant à un compte.
        Supporte les comptes de 2 à 8 chiffres en extrayant les préfixes.
        Ex: "101000" → teste "1010", "101", "10", "1"
            "411200" → teste "4112", "411", "41", "4"
        
        Logique de matching:
        - Le compte de la balance (ex: 101000) doit COMMENCER par un des codes de référence (ex: 101)
        """
        compte_str = str(compte).strip()
        
        # Nettoyer le numéro de compte (garder uniquement les chiffres)
        compte_clean = ''.join(c for c in compte_str if c.isdigit())
        
        if not compte_clean:
            return None
        
        # Chercher la meilleure correspondance (le préfixe le plus long qui match)
        best_match = None
        best_match_length = 0
        
        for _, row in correspondance.iterrows():
            comptes_ref = str(row.get('comptes', ''))
            if not comptes_ref or comptes_ref == 'nan':
                continue
                
            comptes_list = comptes_ref.split(',')
            
            for ref_code in comptes_list:
                ref_code = ref_code.strip()
                if not ref_code:
                    continue
                
                # Le compte de la balance doit commencer par le code de référence
                # Ex: "101000" commence par "101" → match
                # Ex: "101000" commence par "10" → match (mais moins précis)
                if compte_clean.startswith(ref_code):
                    if len(ref_code) > best_match_length:
                        best_match_length = len(ref_code)
                        best_match = {
                            "rubrique": row.get('rubrique', ''),
                            "libelle": row.get('libelle', ''),
                            "type": row.get('type', ''),
                            "matched_code": ref_code
                        }
        
        if best_match:
            logger.debug(f"   ✓ Match: {compte_str} → {best_match['matched_code']} (rubrique: {best_match['rubrique']})")
        else:
            logger.debug(f"   ✗ Pas de match pour: {compte_str}")
        
        return best_match
    
    def calculate_etats_financiers(self, balance_data: BalanceData, exercice_n: str = "N", exercice_n1: str = "N-1") -> Dict:
        """Calcule les états financiers à partir de la balance"""
        try:
            logger.info("═══════════════════════════════════════════════════════════")
            logger.info("📊 [ÉTATS FINANCIERS] DÉBUT DU CALCUL")
            logger.info("═══════════════════════════════════════════════════════════")
            
            # Parser la balance
            df, col_mapping = self.parse_balance(balance_data)
            
            # Initialiser les résultats par rubrique
            rubriques_results = {}
            comptes_non_trouves = []
            comptes_trouves = []
            comptes_details = []  # Pour l'état de contrôle
            
            # Parcourir chaque ligne de la balance
            for idx, row in df.iterrows():
                compte = row.get(col_mapping["numero"], "")
                if not compte or pd.isna(compte):
                    continue
                
                compte_str = str(compte).strip()
                intitule = str(row.get(col_mapping["intitule"], "")).strip() if col_mapping["intitule"] else ""
                
                # Calculer les montants N
                solde_n = 0.0
                debit_n = 0.0
                credit_n = 0.0
                if col_mapping["solde_debit_n"] and col_mapping["solde_credit_n"]:
                    debit_n = self._clean_numeric(row.get(col_mapping["solde_debit_n"], 0))
                    credit_n = self._clean_numeric(row.get(col_mapping["solde_credit_n"], 0))
                    solde_n = debit_n - credit_n
                elif col_mapping["debit_n"] and col_mapping["credit_n"]:
                    debit_n = self._clean_numeric(row.get(col_mapping["debit_n"], 0))
                    credit_n = self._clean_numeric(row.get(col_mapping["credit_n"], 0))
                    solde_n = debit_n - credit_n
                
                # Calculer les montants N-1
                solde_n1 = 0.0
                if col_mapping["solde_debit_n1"] and col_mapping["solde_credit_n1"]:
                    debit = self._clean_numeric(row.get(col_mapping["solde_debit_n1"], 0))
                    credit = self._clean_numeric(row.get(col_mapping["solde_credit_n1"], 0))
                    solde_n1 = debit - credit
                elif col_mapping["debit_n1"] and col_mapping["credit_n1"]:
                    debit = self._clean_numeric(row.get(col_mapping["debit_n1"], 0))
                    credit = self._clean_numeric(row.get(col_mapping["credit_n1"], 0))
                    solde_n1 = debit - credit
                
                # Stocker les détails du compte pour l'état de contrôle
                compte_detail = {
                    "numero": compte_str,
                    "intitule": intitule,
                    "debit_n": debit_n,
                    "credit_n": credit_n,
                    "solde_n": solde_n,
                    "solde_n1": solde_n1
                }
                comptes_details.append(compte_detail)
                
                # Trouver la rubrique correspondante
                rubrique_info = self._match_compte_to_rubrique(compte_str, self.correspondance_df)
                if not rubrique_info:
                    comptes_non_trouves.append(compte_detail)
                    continue
                
                comptes_trouves.append(compte_str)
                rubrique_code = rubrique_info["rubrique"]
                
                # Initialiser la rubrique si nécessaire
                if rubrique_code not in rubriques_results:
                    rubriques_results[rubrique_code] = {
                        "code": rubrique_code,
                        "libelle": rubrique_info["libelle"],
                        "type": rubrique_info["type"],
                        "montant_n": 0.0,
                        "montant_n1": 0.0
                    }
                
                # Ajuster le signe selon le type
                if rubrique_info["type"] in ["PASSIF", "PRODUIT"]:
                    solde_n = -solde_n
                    solde_n1 = -solde_n1
                
                rubriques_results[rubrique_code]["montant_n"] += solde_n
                rubriques_results[rubrique_code]["montant_n1"] += solde_n1
            
            # Log des résultats
            logger.info(f"📊 Comptes traités: {len(comptes_trouves)} trouvés, {len(comptes_non_trouves)} non trouvés")
            if comptes_non_trouves[:10]:
                logger.info(f"   Exemples non trouvés: {[c['numero'] for c in comptes_non_trouves[:10]]}")
            logger.info(f"   Rubriques générées: {len(rubriques_results)}")
            
            # Construire les états financiers
            result = self._build_etats_financiers(rubriques_results, exercice_n, exercice_n1)
            
            # Générer l'état de contrôle
            etat_controle = self._generate_etat_controle(
                result, 
                comptes_details, 
                comptes_trouves, 
                comptes_non_trouves
            )
            result["etat_controle"] = etat_controle
            
            logger.info("✅ [ÉTATS FINANCIERS] CALCUL TERMINÉ")
            return result
            
        except Exception as e:
            logger.error(f"❌ Erreur calcul états financiers: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=str(e))

    def _generate_etat_controle(self, etats_financiers: Dict, comptes_details: List[Dict], 
                                comptes_trouves: List[str], comptes_non_trouves: List[Dict]) -> Dict:
        """
        Génère l'état de contrôle COMPLET de la balance avec :
        1. CONTRÔLE DE LA BALANCE : Total Débits = Total Crédits (équilibre de base)
        2. CONTRÔLE D'INTÉGRATION : Comptes intégrés vs non intégrés
        3. CONTRÔLE DES ÉTATS FINANCIERS : Actif = Passif + Résultat
        """
        logger.info("📊 Génération de l'état de contrôle...")
        
        # ═══════════════════════════════════════════════════════════════════
        # 1. CONTRÔLE DE LA BALANCE (Total Débits = Total Crédits)
        # ═══════════════════════════════════════════════════════════════════
        
        # Calculer les totaux de la balance (TOUS les comptes)
        total_debit_balance_n = sum(c.get("debit_n", 0) for c in comptes_details)
        total_credit_balance_n = sum(c.get("credit_n", 0) for c in comptes_details)
        ecart_balance_n = total_debit_balance_n - total_credit_balance_n
        balance_equilibree_n = abs(ecart_balance_n) < 1  # Tolérance de 1 FCFA
        
        # Totaux des soldes
        total_solde_debiteur_n = sum(c.get("solde_n", 0) for c in comptes_details if c.get("solde_n", 0) > 0)
        total_solde_crediteur_n = sum(abs(c.get("solde_n", 0)) for c in comptes_details if c.get("solde_n", 0) < 0)
        
        # Détail par classe de comptes (pour la balance complète)
        balance_par_classe = {}
        noms_classes = {
            '1': 'Comptes de capitaux',
            '2': "Comptes d'immobilisations",
            '3': 'Comptes de stocks',
            '4': 'Comptes de tiers',
            '5': 'Comptes de trésorerie',
            '6': 'Comptes de charges',
            '7': 'Comptes de produits',
            '8': 'Comptes spéciaux',
            '9': 'Comptes analytiques'
        }
        
        for compte in comptes_details:
            numero = compte.get("numero", "")
            if numero and numero[0].isdigit():
                classe = numero[0]
                if classe not in balance_par_classe:
                    balance_par_classe[classe] = {
                        "classe": classe,
                        "nom": noms_classes.get(classe, f"Classe {classe}"),
                        "nb_comptes": 0,
                        "total_debit": 0,
                        "total_credit": 0,
                        "solde_net": 0
                    }
                balance_par_classe[classe]["nb_comptes"] += 1
                balance_par_classe[classe]["total_debit"] += compte.get("debit_n", 0)
                balance_par_classe[classe]["total_credit"] += compte.get("credit_n", 0)
                balance_par_classe[classe]["solde_net"] += compte.get("solde_n", 0)
        
        # ═══════════════════════════════════════════════════════════════════
        # 2. CONTRÔLE DES ÉTATS FINANCIERS (Actif = Passif + Résultat)
        # ═══════════════════════════════════════════════════════════════════
        
        total_actif_n = etats_financiers.get("bilan_actif", {}).get("total", {}).get("n", 0)
        total_actif_n1 = etats_financiers.get("bilan_actif", {}).get("total", {}).get("n1", 0)
        total_passif_n = etats_financiers.get("bilan_passif", {}).get("total", {}).get("n", 0)
        total_passif_n1 = etats_financiers.get("bilan_passif", {}).get("total", {}).get("n1", 0)
        resultat_n = etats_financiers.get("compte_resultat", {}).get("resultat", {}).get("n", 0)
        resultat_n1 = etats_financiers.get("compte_resultat", {}).get("resultat", {}).get("n1", 0)
        
        equilibre_theorique_n = total_passif_n + resultat_n
        equilibre_theorique_n1 = total_passif_n1 + resultat_n1
        ecart_n = total_actif_n - equilibre_theorique_n
        ecart_n1 = total_actif_n1 - equilibre_theorique_n1
        equilibre_conforme_n = abs(ecart_n) < 1
        equilibre_conforme_n1 = abs(ecart_n1) < 1
        
        # ═══════════════════════════════════════════════════════════════════
        # 3. CONTRÔLE D'INTÉGRATION (Comptes intégrés vs non intégrés)
        # ═══════════════════════════════════════════════════════════════════
        
        total_comptes = len(comptes_details)
        nb_comptes_integres = len(comptes_trouves)
        nb_comptes_non_integres = len(comptes_non_trouves)
        taux_couverture = (nb_comptes_integres / total_comptes * 100) if total_comptes > 0 else 0
        
        # Totaux des comptes intégrés
        comptes_integres_details = [c for c in comptes_details if c.get("numero") in comptes_trouves]
        total_integres_debit = sum(c.get("debit_n", 0) for c in comptes_integres_details)
        total_integres_credit = sum(c.get("credit_n", 0) for c in comptes_integres_details)
        total_integres_solde = sum(c.get("solde_n", 0) for c in comptes_integres_details)
        
        # Totaux des comptes non intégrés
        total_non_integres_debit = sum(c.get("debit_n", 0) for c in comptes_non_trouves)
        total_non_integres_credit = sum(c.get("credit_n", 0) for c in comptes_non_trouves)
        total_non_integres_solde = sum(c.get("solde_n", 0) for c in comptes_non_trouves)
        
        # Calculer les totaux N-1 pour les comptes non intégrés
        total_non_integres_solde_n1 = sum(c.get("solde_n1", 0) for c in comptes_non_trouves)
        total_integres_solde_n1 = sum(c.get("solde_n1", 0) for c in comptes_integres_details)
        
        # Trier les comptes non intégrés par solde N décroissant (en valeur absolue)
        comptes_non_trouves_tries_n = sorted(
            [c for c in comptes_non_trouves if c.get("numero")],  # Filtrer les lignes vides
            key=lambda x: abs(x.get("solde_n", 0)), 
            reverse=True
        )
        
        # Trier les comptes non intégrés par solde N-1 décroissant (en valeur absolue)
        comptes_non_trouves_tries_n1 = sorted(
            [c for c in comptes_non_trouves if c.get("numero")],  # Filtrer les lignes vides
            key=lambda x: abs(x.get("solde_n1", 0)), 
            reverse=True
        )
        
        # Analyse par classe de comptes non intégrés (avec N et N-1)
        classes_non_integrees = {}
        for compte in comptes_non_trouves:
            numero = compte.get("numero", "")
            if numero and numero[0].isdigit():
                classe = numero[0]
                if classe not in classes_non_integrees:
                    classes_non_integrees[classe] = {
                        "classe": classe,
                        "nom": noms_classes.get(classe, f"Classe {classe}"),
                        "nombre": 0,
                        "total_debit_n": 0,
                        "total_credit_n": 0,
                        "total_solde_n": 0,
                        "total_solde_n1": 0,
                        "comptes": []
                    }
                classes_non_integrees[classe]["nombre"] += 1
                classes_non_integrees[classe]["total_debit_n"] += compte.get("debit_n", 0)
                classes_non_integrees[classe]["total_credit_n"] += compte.get("credit_n", 0)
                classes_non_integrees[classe]["total_solde_n"] += compte.get("solde_n", 0)
                classes_non_integrees[classe]["total_solde_n1"] += compte.get("solde_n1", 0)
                classes_non_integrees[classe]["comptes"].append(numero)
        
        # ═══════════════════════════════════════════════════════════════════
        # 4. RECOMMANDATIONS
        # ═══════════════════════════════════════════════════════════════════
        
        recommandations = []
        
        # Vérifier l'équilibre de la balance
        if not balance_equilibree_n:
            recommandations.append({
                "type": "erreur",
                "message": f"❌ BALANCE DÉSÉQUILIBRÉE: Total Débits ({total_debit_balance_n:,.0f}) ≠ Total Crédits ({total_credit_balance_n:,.0f}). Écart: {ecart_balance_n:,.0f} FCFA",
                "action": "Vérifiez les écritures comptables. La balance doit être équilibrée avant de générer les états financiers."
            })
        
        # Vérifier l'équilibre des états financiers
        if not equilibre_conforme_n:
            recommandations.append({
                "type": "attention",
                "message": f"⚠️ ÉTATS FINANCIERS: Actif ({total_actif_n:,.0f}) ≠ Passif + Résultat ({equilibre_theorique_n:,.0f}). Écart: {ecart_n:,.0f} FCFA",
                "action": "L'écart provient probablement des comptes non intégrés. Vérifiez le tableau de correspondance."
            })
        
        # Vérifier le taux de couverture
        if taux_couverture < 90:
            recommandations.append({
                "type": "attention",
                "message": f"📊 Taux de couverture faible ({taux_couverture:.1f}%). {nb_comptes_non_integres} comptes non intégrés.",
                "action": "Ajoutez les comptes manquants au tableau de correspondance SYSCOHADA."
            })
        
        # Analyser les classes avec impact significatif
        for classe, info in classes_non_integrees.items():
            if abs(info["total_solde_n"]) > 1000000:
                recommandations.append({
                    "type": "attention",
                    "message": f"💰 {info['nom']} non intégrés: {info['total_solde_n']:,.0f} FCFA ({info['nombre']} comptes)",
                    "action": f"Vérifiez les comptes: {', '.join(info['comptes'][:5])}..."
                })
        
        if balance_equilibree_n and equilibre_conforme_n and taux_couverture >= 95:
            recommandations.append({
                "type": "succes",
                "message": "✅ Balance équilibrée, états financiers conformes, couverture élevée.",
                "action": ""
            })
        
        # ═══════════════════════════════════════════════════════════════════
        # CONSTRUCTION DE L'ÉTAT DE CONTRÔLE COMPLET
        # ═══════════════════════════════════════════════════════════════════
        
        etat_controle = {
            # 1. CONTRÔLE DE LA BALANCE
            "balance": {
                "equilibree": balance_equilibree_n,
                "total_debit": round(total_debit_balance_n, 2),
                "total_credit": round(total_credit_balance_n, 2),
                "ecart": round(ecart_balance_n, 2),
                "total_solde_debiteur": round(total_solde_debiteur_n, 2),
                "total_solde_crediteur": round(total_solde_crediteur_n, 2),
                "nb_comptes": total_comptes,
                "par_classe": list(balance_par_classe.values())
            },
            
            # 2. CONTRÔLE DES ÉTATS FINANCIERS
            "etats_financiers": {
                "conforme_n": equilibre_conforme_n,
                "conforme_n1": equilibre_conforme_n1,
                "total_actif_n": round(total_actif_n, 2),
                "total_actif_n1": round(total_actif_n1, 2),
                "total_passif_n": round(total_passif_n, 2),
                "total_passif_n1": round(total_passif_n1, 2),
                "resultat_n": round(resultat_n, 2),
                "resultat_n1": round(resultat_n1, 2),
                "equilibre_theorique_n": round(equilibre_theorique_n, 2),
                "equilibre_theorique_n1": round(equilibre_theorique_n1, 2),
                "ecart_n": round(ecart_n, 2),
                "ecart_n1": round(ecart_n1, 2),
                "formule": "Actif = Passif + Résultat"
            },
            
            # 3. CONTRÔLE D'INTÉGRATION
            "integration": {
                "taux_couverture": round(taux_couverture, 2),
                "comptes_integres": {
                    "nombre": nb_comptes_integres,
                    "total_debit": round(total_integres_debit, 2),
                    "total_credit": round(total_integres_credit, 2),
                    "total_solde_n": round(total_integres_solde, 2),
                    "total_solde_n1": round(total_integres_solde_n1, 2)
                },
                "comptes_non_integres": {
                    "nombre": nb_comptes_non_integres,
                    "total_debit": round(total_non_integres_debit, 2),
                    "total_credit": round(total_non_integres_credit, 2),
                    "total_solde_n": round(total_non_integres_solde, 2),
                    "total_solde_n1": round(total_non_integres_solde_n1, 2),
                    "liste_complete_n": comptes_non_trouves_tries_n,  # Liste COMPLÈTE triée par N
                    "liste_complete_n1": comptes_non_trouves_tries_n1,  # Liste COMPLÈTE triée par N-1
                    "par_classe": list(classes_non_integrees.values())
                }
            },
            
            # 4. RECOMMANDATIONS
            "recommandations": recommandations,
            
            # Rétrocompatibilité avec l'ancienne structure
            "equilibre": {
                "conforme_n": equilibre_conforme_n,
                "total_actif_n": round(total_actif_n, 2),
                "total_passif_n": round(total_passif_n, 2),
                "resultat_n": round(resultat_n, 2),
                "ecart_n": round(ecart_n, 2),
                "formule": "Actif = Passif + Résultat"
            },
            "couverture": {
                "taux": round(taux_couverture, 2),
                "comptes_integres": nb_comptes_integres,
                "comptes_non_integres": nb_comptes_non_integres,
                "comptes_total": total_comptes
            },
            "comptes_non_integres": {
                "liste": comptes_non_trouves_tries_n,  # Liste COMPLÈTE
                "total_debit": round(total_non_integres_debit, 2),
                "total_credit": round(total_non_integres_credit, 2),
                "total_solde": round(total_non_integres_solde, 2),
                "total_solde_n1": round(total_non_integres_solde_n1, 2),
                "par_classe": list(classes_non_integrees.values())
            }
        }
        
        # Logs
        logger.info(f"   Balance: {'✅ Équilibrée' if balance_equilibree_n else '❌ Déséquilibrée'} (D={total_debit_balance_n:,.0f} C={total_credit_balance_n:,.0f})")
        logger.info(f"   États financiers: {'✅ Conforme' if equilibre_conforme_n else '❌ Non conforme'} (écart: {ecart_n:,.0f})")
        logger.info(f"   Intégration: {taux_couverture:.1f}% ({nb_comptes_integres}/{total_comptes} comptes)")
        logger.info(f"   Impact non intégrés: {total_non_integres_solde:,.0f} FCFA")
        
        return etat_controle

    def _build_etats_financiers(self, rubriques: Dict, exercice_n: str, exercice_n1: str) -> Dict:
        """Construit les états financiers structurés"""
        
        # Séparer par type
        actif_rubriques = []
        passif_rubriques = []
        produit_rubriques = []
        charge_rubriques = []
        
        for code, data in rubriques.items():
            rubrique_data = {
                "code": data["code"],
                "libelle": data["libelle"],
                "montant_n": round(data["montant_n"], 2),
                "montant_n1": round(data["montant_n1"], 2)
            }
            
            if data["type"] == "ACTIF":
                actif_rubriques.append(rubrique_data)
            elif data["type"] == "PASSIF":
                passif_rubriques.append(rubrique_data)
            elif data["type"] == "PRODUIT":
                produit_rubriques.append(rubrique_data)
            elif data["type"] == "CHARGE":
                charge_rubriques.append(rubrique_data)
        
        # Calculer les totaux
        total_actif_n = sum(r["montant_n"] for r in actif_rubriques)
        total_actif_n1 = sum(r["montant_n1"] for r in actif_rubriques)
        total_passif_n = sum(r["montant_n"] for r in passif_rubriques)
        total_passif_n1 = sum(r["montant_n1"] for r in passif_rubriques)
        total_produits_n = sum(r["montant_n"] for r in produit_rubriques)
        total_produits_n1 = sum(r["montant_n1"] for r in produit_rubriques)
        total_charges_n = sum(r["montant_n"] for r in charge_rubriques)
        total_charges_n1 = sum(r["montant_n1"] for r in charge_rubriques)
        
        resultat_n = total_produits_n - total_charges_n
        resultat_n1 = total_produits_n1 - total_charges_n1
        
        return {
            "success": True,
            "message": "États financiers calculés avec succès",
            "exercice_n": exercice_n,
            "exercice_n1": exercice_n1,
            "bilan_actif": {
                "titre": "BILAN ACTIF",
                "rubriques": sorted(actif_rubriques, key=lambda x: x["code"]),
                "total": {"n": round(total_actif_n, 2), "n1": round(total_actif_n1, 2)}
            },
            "bilan_passif": {
                "titre": "BILAN PASSIF",
                "rubriques": sorted(passif_rubriques, key=lambda x: x["code"]),
                "total": {"n": round(total_passif_n, 2), "n1": round(total_passif_n1, 2)}
            },
            "compte_resultat": {
                "titre": "COMPTE DE RÉSULTAT",
                "produits": {
                    "rubriques": sorted(produit_rubriques, key=lambda x: x["code"]),
                    "total": {"n": round(total_produits_n, 2), "n1": round(total_produits_n1, 2)}
                },
                "charges": {
                    "rubriques": sorted(charge_rubriques, key=lambda x: x["code"]),
                    "total": {"n": round(total_charges_n, 2), "n1": round(total_charges_n1, 2)}
                },
                "resultat": {"n": round(resultat_n, 2), "n1": round(resultat_n1, 2)}
            }
        }

# Instance globale
etats_financiers_calculator = EtatsFinanciersCalculator()

# ============================================
# ENDPOINTS API
# ============================================

@router.post("/calculate")
async def calculate_etats_financiers(request: EtatsFinanciersRequest):
    """
    Calcule les états financiers SYSCOHADA à partir d'une balance.
    Retourne le Bilan (Actif/Passif) et le Compte de Résultat.
    """
    try:
        result = etats_financiers_calculator.calculate_etats_financiers(
            request.balance,
            request.exercice_n,
            request.exercice_n1
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur endpoint calculate: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_status():
    """Vérifie le statut du module États Financiers"""
    correspondance_loaded = etats_financiers_calculator.correspondance_df is not None
    return {
        "module": "États Financiers SYSCOHADA",
        "correspondance_loaded": correspondance_loaded,
        "correspondance_rows": len(etats_financiers_calculator.correspondance_df) if correspondance_loaded else 0,
        "message": "Module prêt" if correspondance_loaded else "Tableau de correspondance non chargé"
    }

@router.post("/upload-correspondance")
async def upload_correspondance(file: UploadFile = File(...)):
    """Upload un nouveau tableau de correspondance"""
    try:
        contents = await file.read()
        df = pd.read_excel(BytesIO(contents))
        etats_financiers_calculator.correspondance_df = df
        logger.info(f"✅ Nouveau tableau de correspondance chargé: {len(df)} lignes")
        return {"success": True, "message": f"Tableau chargé: {len(df)} lignes", "columns": list(df.columns)}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erreur lecture fichier: {e}")


@router.post("/calculate-from-excel")
async def calculate_from_excel(file_base64: str = None, filename: str = None):
    """
    Calcule les états financiers directement depuis un fichier Excel encodé en base64.
    """
    import base64
    
    try:
        if not file_base64:
            raise HTTPException(status_code=400, detail="Fichier base64 requis")
        
        # Décoder le fichier
        file_bytes = base64.b64decode(file_base64)
        
        # Lire le fichier Excel
        df = pd.read_excel(BytesIO(file_bytes))
        logger.info(f"📊 Fichier Excel lu: {len(df)} lignes, colonnes: {list(df.columns)}")
        
        # Convertir en format BalanceData
        headers = [str(col) for col in df.columns.tolist()]
        rows = []
        for _, row in df.iterrows():
            row_data = [str(val) if not pd.isna(val) else "" for val in row.tolist()]
            rows.append(row_data)
        
        balance_data = BalanceData(headers=headers, rows=rows)
        
        # Calculer les états financiers
        result = etats_financiers_calculator.calculate_etats_financiers(balance_data, "N", "N-1")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur calculate_from_excel: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ExcelUploadRequest(BaseModel):
    """Requête pour upload Excel"""
    file_base64: str
    filename: Optional[str] = "balance.xlsx"
    exercice_n: Optional[str] = "N"
    exercice_n1: Optional[str] = "N-1"


@router.post("/calculate-excel")
async def calculate_etats_from_excel(request: ExcelUploadRequest):
    """
    Calcule les états financiers depuis un fichier Excel encodé en base64.
    Endpoint principal pour l'import Excel.
    """
    import base64
    
    try:
        logger.info(f"📊 [États Financiers] Réception fichier: {request.filename}")
        
        # Décoder le fichier
        file_bytes = base64.b64decode(request.file_base64)
        
        # Lire le fichier Excel
        df = pd.read_excel(BytesIO(file_bytes))
        logger.info(f"   ✅ Fichier lu: {len(df)} lignes, colonnes: {list(df.columns)}")
        
        # Convertir en format BalanceData
        headers = [str(col) for col in df.columns.tolist()]
        rows = []
        for _, row in df.iterrows():
            row_data = [str(val) if not pd.isna(val) else "" for val in row.tolist()]
            rows.append(row_data)
        
        balance_data = BalanceData(headers=headers, rows=rows)
        
        # Calculer les états financiers
        result = etats_financiers_calculator.calculate_etats_financiers(
            balance_data, 
            request.exercice_n, 
            request.exercice_n1
        )
        
        logger.info("   ✅ États financiers calculés avec succès")
        return result
        
    except Exception as e:
        logger.error(f"❌ Erreur calculate_etats_from_excel: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
