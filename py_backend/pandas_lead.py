import pandas as pd
import numpy as np
import os
import json
import base64
import io
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging

# Configuration du logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pandas_lead")

# Router FastAPI pour l'API Lead Balance
router = APIRouter(prefix="/lead-balance", tags=["Lead Balance"])


# ==================== MODÈLES PYDANTIC ====================

class ExcelUploadRequest(BaseModel):
    """Requête avec fichier Excel encodé en base64"""
    file_base64: str
    filename: str

class LeadBalanceResponse(BaseModel):
    success: bool
    message: str
    results: Optional[Dict[str, Any]] = None
    html: Optional[str] = None


# ==================== FONCTIONS UTILITAIRES ====================

def clean_number(value) -> float:
    """Nettoie et convertit une valeur en float"""
    if pd.isna(value) or value == '' or value is None:
        return 0.0
    try:
        # Gérer les formats avec espaces et virgules
        cleaned = str(value).replace(' ', '').replace(',', '.')
        return float(cleaned)
    except (ValueError, TypeError):
        return 0.0

def format_number(x: float) -> str:
    """Formate un nombre avec séparateurs de milliers"""
    try:
        return f"{x:,.2f}".replace(',', ' ').replace('.', ',')
    except:
        return str(x)


def calculate_variation(solde_n: float, solde_n_1: float) -> float:
    """Calcule la variation en pourcentage"""
    if solde_n_1 == 0:
        return np.inf if solde_n != 0 else 0
    return ((solde_n - solde_n_1) / abs(solde_n_1)) * 100


def detect_balance_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Détecte automatiquement les colonnes de balance.
    Format attendu: Numéro, Intitulé, Ant Débit, Ant Crédit, Débit, Crédit, Solde Débit, Solde Crédit
    """
    columns = df.columns.tolist()
    columns_lower = [str(c).lower().strip() for c in columns]
    
    mapping = {
        'numero': None,
        'intitule': None,
        'solde_debit': None,
        'solde_credit': None
    }
    
    for idx, col in enumerate(columns_lower):
        original_col = columns[idx]
        
        # Détection du numéro de compte
        if 'numéro' in col or 'numero' in col or col == 'n°' or 'compte' in col:
            if mapping['numero'] is None:
                mapping['numero'] = original_col
        
        # Détection de l'intitulé
        if 'intitulé' in col or 'intitule' in col or 'libellé' in col or 'libelle' in col:
            if mapping['intitule'] is None:
                mapping['intitule'] = original_col
        
        # Détection Solde Débit (priorité aux colonnes "Solde")
        if 'solde' in col and 'débit' in col:
            mapping['solde_debit'] = original_col
        elif 'solde' in col and 'debit' in col:
            mapping['solde_debit'] = original_col
        
        # Détection Solde Crédit
        if 'solde' in col and 'crédit' in col:
            mapping['solde_credit'] = original_col
        elif 'solde' in col and 'credit' in col:
            mapping['solde_credit'] = original_col
    
    logger.info(f"🔍 Colonnes détectées: {mapping}")
    return mapping


def process_balance_sheet(df: pd.DataFrame, period_name: str) -> pd.DataFrame:
    """
    Traite un onglet de balance et calcule le solde net (Débit - Crédit).
    """
    logger.info(f"📊 Traitement de la balance {period_name}: {len(df)} lignes")
    logger.info(f"📋 Colonnes disponibles: {df.columns.tolist()}")
    
    # Détecter les colonnes
    col_map = detect_balance_columns(df)
    
    if col_map['numero'] is None:
        raise ValueError(f"Colonne 'Numéro' non trouvée dans l'onglet {period_name}")
    
    # Créer le DataFrame résultat
    result_data = []
    
    for _, row in df.iterrows():
        numero = str(row.get(col_map['numero'], '')).strip()
        if not numero or numero == 'nan':
            continue
        
        intitule = str(row.get(col_map['intitule'], '')).strip() if col_map['intitule'] else ''
        
        # Récupérer Solde Débit et Solde Crédit
        solde_debit = clean_number(row.get(col_map['solde_debit'], 0)) if col_map['solde_debit'] else 0
        solde_credit = clean_number(row.get(col_map['solde_credit'], 0)) if col_map['solde_credit'] else 0
        
        # Calculer le solde net = Solde Débit - Solde Crédit
        solde_net = solde_debit - solde_credit
        
        result_data.append({
            'Compte': numero,
            'Intitule': intitule,
            'Solde_Debit': solde_debit,
            'Solde_Credit': solde_credit,
            'Solde_Net': solde_net
        })
    
    result_df = pd.DataFrame(result_data)
    logger.info(f"✅ {len(result_df)} comptes traités pour {period_name}")
    return result_df


def create_lead_balance_from_excel(file_content: bytes) -> Dict[str, Any]:
    """
    Crée les lead balances à partir d'un fichier Excel avec 2 onglets.
    Onglet 1 = Balance N (période actuelle)
    Onglet 2 = Balance N-1 (période précédente)
    """
    logger.info("📂 Lecture du fichier Excel...")
    
    # Lire le fichier Excel
    excel_file = io.BytesIO(file_content)
    xl = pd.ExcelFile(excel_file)
    
    sheet_names = xl.sheet_names
    logger.info(f"📑 Onglets trouvés: {sheet_names}")
    
    if len(sheet_names) < 2:
        raise ValueError(f"Le fichier doit contenir au moins 2 onglets. Trouvé: {len(sheet_names)}")
    
    # Lire les deux premiers onglets
    df_n = pd.read_excel(xl, sheet_name=sheet_names[0])
    df_n_1 = pd.read_excel(xl, sheet_name=sheet_names[1])
    
    logger.info(f"📊 Onglet 1 ({sheet_names[0]}): {len(df_n)} lignes")
    logger.info(f"📊 Onglet 2 ({sheet_names[1]}): {len(df_n_1)} lignes")
    
    # Traiter chaque balance
    balance_n = process_balance_sheet(df_n, "N")
    balance_n_1 = process_balance_sheet(df_n_1, "N-1")
    
    # Identifier les comptes par période
    comptes_n = set(balance_n['Compte'].unique())
    comptes_n_1 = set(balance_n_1['Compte'].unique())
    
    logger.info(f"📈 Comptes en N: {len(comptes_n)}")
    logger.info(f"📉 Comptes en N-1: {len(comptes_n_1)}")
    
    # 1. Comptes communs aux deux périodes
    comptes_communs = comptes_n & comptes_n_1
    common_data = []
    
    for compte in comptes_communs:
        row_n = balance_n[balance_n['Compte'] == compte].iloc[0]
        row_n_1 = balance_n_1[balance_n_1['Compte'] == compte].iloc[0]
        
        solde_n = row_n['Solde_Net']
        solde_n_1 = row_n_1['Solde_Net']
        ecart = solde_n - solde_n_1
        variation = calculate_variation(solde_n, solde_n_1)
        
        common_data.append({
            'Compte': compte,
            'Intitule_N': row_n['Intitule'],
            'Intitule_N_1': row_n_1['Intitule'],
            'Solde_Debit_N': row_n['Solde_Debit'],
            'Solde_Credit_N': row_n['Solde_Credit'],
            'Solde_N': solde_n,
            'Solde_Debit_N_1': row_n_1['Solde_Debit'],
            'Solde_Credit_N_1': row_n_1['Solde_Credit'],
            'Solde_N_1': solde_n_1,
            'Ecart': ecart,
            'Variation': variation
        })
    
    common_df = pd.DataFrame(common_data)
    if not common_df.empty:
        common_df = common_df.sort_values('Compte')

    
    # 2. Comptes uniquement en N (nouveaux)
    comptes_only_n = comptes_n - comptes_n_1
    only_n_data = []
    
    for compte in comptes_only_n:
        row = balance_n[balance_n['Compte'] == compte].iloc[0]
        only_n_data.append({
            'Compte': compte,
            'Intitule': row['Intitule'],
            'Solde_Debit': row['Solde_Debit'],
            'Solde_Credit': row['Solde_Credit'],
            'Solde_Net': row['Solde_Net']
        })
    
    only_n_df = pd.DataFrame(only_n_data)
    if not only_n_df.empty:
        only_n_df = only_n_df.sort_values('Compte')
    
    # 3. Comptes uniquement en N-1 (supprimés)
    comptes_only_n_1 = comptes_n_1 - comptes_n
    only_n_1_data = []
    
    for compte in comptes_only_n_1:
        row = balance_n_1[balance_n_1['Compte'] == compte].iloc[0]
        only_n_1_data.append({
            'Compte': compte,
            'Intitule': row['Intitule'],
            'Solde_Debit': row['Solde_Debit'],
            'Solde_Credit': row['Solde_Credit'],
            'Solde_Net': row['Solde_Net']
        })
    
    only_n_1_df = pd.DataFrame(only_n_1_data)
    if not only_n_1_df.empty:
        only_n_1_df = only_n_1_df.sort_values('Compte')
    
    # Calculer les totaux
    totals = {
        'common': {
            'solde_n': common_df['Solde_N'].sum() if not common_df.empty else 0,
            'solde_n_1': common_df['Solde_N_1'].sum() if not common_df.empty else 0,
            'ecart': common_df['Ecart'].sum() if not common_df.empty else 0,
            'count': len(common_df)
        },
        'only_n': {
            'solde': only_n_df['Solde_Net'].sum() if not only_n_df.empty else 0,
            'count': len(only_n_df)
        },
        'only_n_1': {
            'solde': only_n_1_df['Solde_Net'].sum() if not only_n_1_df.empty else 0,
            'count': len(only_n_1_df)
        },
        'sheet_names': {
            'n': sheet_names[0],
            'n_1': sheet_names[1]
        }
    }
    
    return {
        'common_accounts': common_df.to_dict('records') if not common_df.empty else [],
        'only_n': only_n_df.to_dict('records') if not only_n_df.empty else [],
        'only_n_1': only_n_1_df.to_dict('records') if not only_n_1_df.empty else [],
        'totals': totals
    }


def get_syscohada_sections():
    """
    Retourne la configuration des sections SYSCOHADA révisé
    """
    return {
        # BILAN - ACTIF
        'actif_immobilise': {
            'title': 'Actif Immobilisé',
            'icon': '🏢',
            'type': 'bilan',
            'nature': 'actif',
            'prefixes': ['20', '21', '22', '23', '24', '25', '26', '27']
        },
        'actif_circulant': {
            'title': 'Actif Circulant',
            'icon': '🔄',
            'type': 'bilan',
            'nature': 'actif',
            'prefixes': ['31', '32', '33', '34', '35', '36', '37', '38', '41', '42', '43', '44', '45', '46', '47', '48']
        },
        'tresorerie_actif': {
            'title': 'Trésorerie Actif',
            'icon': '💵',
            'type': 'bilan',
            'nature': 'actif',
            'prefixes': ['50', '51', '52', '53', '54', '57', '58']
        },
        # BILAN - PASSIF
        'capitaux_propres': {
            'title': 'Capitaux Propres',
            'icon': '🏛️',
            'type': 'bilan',
            'nature': 'passif',
            'prefixes': ['10', '11', '12', '13', '14', '15']
        },
        'dettes_financieres': {
            'title': 'Dettes Financières',
            'icon': '🏦',
            'type': 'bilan',
            'nature': 'passif',
            'prefixes': ['16', '17', '18', '19']
        },
        'dettes_fournisseurs': {
            'title': 'Dettes Fournisseurs',
            'icon': '📋',
            'type': 'bilan',
            'nature': 'passif',
            'prefixes': ['40']
        },
        'dettes_fiscales_sociales': {
            'title': 'Dettes Fiscales et Sociales',
            'icon': '🏛️',
            'type': 'bilan',
            'nature': 'passif',
            'prefixes': ['42', '43', '44', '45']
        },
        'autres_dettes': {
            'title': 'Autres Dettes',
            'icon': '📝',
            'type': 'bilan',
            'nature': 'passif',
            'prefixes': ['46', '47', '48']
        },
        'tresorerie_passif': {
            'title': 'Trésorerie Passif',
            'icon': '💳',
            'type': 'bilan',
            'nature': 'passif',
            'prefixes': ['56']
        },
        # RÉSULTAT - CHARGES
        'achats_marchandises': {
            'title': 'Achats et Variations de Stocks',
            'icon': '🛒',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['60']
        },
        'transports': {
            'title': 'Transports',
            'icon': '🚚',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['61']
        },
        'services_exterieurs_a': {
            'title': 'Services Extérieurs A',
            'icon': '🔧',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['62']
        },
        'services_exterieurs_b': {
            'title': 'Services Extérieurs B',
            'icon': '📞',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['63']
        },
        'impots_taxes': {
            'title': 'Impôts et Taxes',
            'icon': '🏛️',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['64']
        },
        'autres_charges': {
            'title': 'Autres Charges',
            'icon': '📊',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['65']
        },
        'charges_personnel': {
            'title': 'Charges de Personnel',
            'icon': '👥',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['66']
        },
        'charges_financieres': {
            'title': 'Charges Financières',
            'icon': '💹',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['67']
        },
        'dotations_amortissements': {
            'title': 'Dotations aux Amortissements',
            'icon': '📉',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['68']
        },
        'dotations_provisions': {
            'title': 'Dotations aux Provisions',
            'icon': '🔒',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['69']
        },
        # RÉSULTAT - PRODUITS
        'ventes': {
            'title': 'Ventes',
            'icon': '💰',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['70']
        },
        'subventions_exploitation': {
            'title': 'Subventions d\'Exploitation',
            'icon': '🎁',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['71']
        },
        'production_immobilisee': {
            'title': 'Production Immobilisée',
            'icon': '🏭',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['72']
        },
        'variations_stocks_produits': {
            'title': 'Variations de Stocks de Produits',
            'icon': '📦',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['73']
        },
        'produits_accessoires': {
            'title': 'Produits Accessoires',
            'icon': '➕',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['74']
        },
        'autres_produits': {
            'title': 'Autres Produits',
            'icon': '📈',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['75']
        },
        'produits_financiers': {
            'title': 'Produits Financiers',
            'icon': '💵',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['76', '77']
        },
        'transferts_charges': {
            'title': 'Transferts de Charges',
            'icon': '🔄',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['78']
        },
        'reprises_provisions': {
            'title': 'Reprises de Provisions',
            'icon': '🔓',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['79']
        },
        # HAO
        'charges_hao': {
            'title': 'Charges HAO',
            'icon': '⚡',
            'type': 'resultat',
            'nature': 'charge',
            'prefixes': ['81', '83', '85', '87', '89']
        },
        'produits_hao': {
            'title': 'Produits HAO',
            'icon': '✨',
            'type': 'resultat',
            'nature': 'produit',
            'prefixes': ['82', '84', '86', '88']
        }
    }


def filter_accounts_by_section(accounts: List[Dict], section_config: Dict) -> List[Dict]:
    """Filtre les comptes par section SYSCOHADA"""
    prefixes = section_config.get('prefixes', [])
    return [
        acc for acc in accounts
        if any(str(acc.get('Compte', '')).startswith(prefix) for prefix in prefixes)
    ]


def generate_section_html(section_id: str, section_config: Dict, accounts: List[Dict], sheet_names: Dict) -> str:
    """Génère le HTML pour une section de lead SYSCOHADA"""
    if not accounts:
        return ''
    
    sheet_n = sheet_names.get('n', 'N')
    sheet_n_1 = sheet_names.get('n_1', 'N-1')
    
    # Calcul des totaux
    total_n = sum(acc.get('Solde_N', 0) for acc in accounts)
    total_n_1 = sum(acc.get('Solde_N_1', 0) for acc in accounts)
    total_ecart = sum(acc.get('Ecart', 0) for acc in accounts)
    ecart_class = 'positive' if total_ecart >= 0 else 'negative'
    
    html = f'''
    <div class="lead-syscohada-section" data-section="{section_id}">
        <div class="section-header" onclick="this.classList.toggle('active'); this.nextElementSibling.classList.toggle('active');">
            <span>{section_config['icon']} {section_config['title']} ({len(accounts)} comptes)</span>
            <span class="arrow">›</span>
        </div>
        <div class="section-content">
            <div class="section-summary">
                <span><strong>Total {sheet_n}:</strong> {format_number(total_n)}</span>
                <span><strong>Total {sheet_n_1}:</strong> {format_number(total_n_1)}</span>
                <span class="{ecart_class}"><strong>Écart:</strong> {format_number(total_ecart)}</span>
            </div>
            <div class="section-table-wrapper">
                <table class="lead-table">
                    <thead>
                        <tr>
                            <th>Compte</th>
                            <th>Intitulé</th>
                            <th>Solde {sheet_n}</th>
                            <th>Solde {sheet_n_1}</th>
                            <th>Écart</th>
                            <th>Var %</th>
                        </tr>
                    </thead>
                    <tbody>'''
    
    for acc in accounts:
        ecart = acc.get('Ecart', 0)
        variation = acc.get('Variation', 0)
        row_class = 'positive' if ecart >= 0 else 'negative'
        var_str = f"{variation:.2f}%" if variation != np.inf else "N/A"
        
        html += f'''
                        <tr>
                            <td>{acc.get('Compte', '')}</td>
                            <td>{acc.get('Intitule_N', '')}</td>
                            <td class="number">{format_number(acc.get('Solde_N', 0))}</td>
                            <td class="number">{format_number(acc.get('Solde_N_1', 0))}</td>
                            <td class="number {row_class}">{format_number(ecart)}</td>
                            <td class="number {row_class}">{var_str}</td>
                        </tr>'''
    
    html += f'''
                    </tbody>
                    <tfoot>
                        <tr class="total-row">
                            <td colspan="2"><strong>TOTAL {section_config['title']}</strong></td>
                            <td class="number"><strong>{format_number(total_n)}</strong></td>
                            <td class="number"><strong>{format_number(total_n_1)}</strong></td>
                            <td class="number {ecart_class}"><strong>{format_number(total_ecart)}</strong></td>
                            <td></td>
                        </tr>
                    </tfoot>
                </table>
            </div>
        </div>
    </div>'''
    
    return html


def generate_accordion_html(results: Dict[str, Any]) -> str:
    """
    Génère le HTML des accordéons pour afficher les lead balances par section SYSCOHADA.
    """
    totals = results['totals']
    sheet_n = totals.get('sheet_names', {}).get('n', 'N')
    sheet_n_1 = totals.get('sheet_names', {}).get('n_1', 'N-1')
    
    # Style CSS pour les accordéons SYSCOHADA
    accordion_style = """
    <style>
    .lead-syscohada-container {
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, sans-serif;
        max-width: 100%;
        margin: 16px 0;
    }
    .lead-header {
        background: linear-gradient(135deg, #800020, #600018);
        color: white;
        padding: 20px;
        border-radius: 12px 12px 0 0;
        text-align: center;
    }
    .lead-header h2 { margin: 0 0 8px 0; font-size: 18px; }
    .lead-header p { margin: 0; opacity: 0.9; font-size: 14px; }

    .lead-category {
        margin-bottom: 16px;
        border: 1px solid #dee2e6;
        border-radius: 8px;
        overflow: hidden;
    }
    .category-header {
        padding: 14px 18px;
        font-weight: 700;
        font-size: 15px;
        color: white;
    }
    .category-header.bilan { background: linear-gradient(135deg, #2c3e50, #34495e); }
    .category-header.resultat { background: linear-gradient(135deg, #27ae60, #2ecc71); }

    .subcategory { margin: 8px; }
    .subcategory-header {
        padding: 10px 16px;
        font-weight: 600;
        font-size: 14px;
        border-radius: 6px;
        margin-bottom: 8px;
    }
    .subcategory-header.actif { background: #e3f2fd; color: #1565c0; }
    .subcategory-header.passif { background: #fce4ec; color: #c2185b; }
    .subcategory-header.charges { background: #ffebee; color: #c62828; }
    .subcategory-header.produits { background: #e8f5e9; color: #2e7d32; }

    .lead-syscohada-section {
        margin: 8px 0;
        border: 1px solid #e0e0e0;
        border-radius: 6px;
        overflow: hidden;
    }
    .section-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: #f8f9fa;
        cursor: pointer;
        font-weight: 500;
        font-size: 13px;
        transition: background 0.2s;
    }
    .section-header:hover { background: #e9ecef; }
    .section-header.active { background: #dee2e6; }
    .section-header .arrow {
        transition: transform 0.3s;
        font-size: 14px;
    }
    .section-header.active .arrow { transform: rotate(90deg); }

    .section-content {
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.3s ease-out;
        background: white;
    }
    .section-content.active { max-height: 3000px; }

    .section-summary {
        display: flex;
        gap: 24px;
        padding: 12px 16px;
        background: #f8f9fa;
        border-bottom: 1px solid #e0e0e0;
        font-size: 12px;
        flex-wrap: wrap;
    }
    .section-table-wrapper { overflow-x: auto; }

    .lead-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 11px;
    }
    .lead-table th {
        background: #343a40;
        color: white;
        padding: 8px 10px;
        text-align: left;
        font-weight: 600;
        white-space: nowrap;
    }
    .lead-table th:nth-child(n+3) { text-align: right; }
    .lead-table td {
        padding: 6px 10px;
        border-bottom: 1px solid #e9ecef;
    }
    .lead-table td.number { text-align: right; font-family: 'Consolas', monospace; }
    .lead-table tr:hover td { background: #f8f9fa; }
    .lead-table .total-row td {
        background: #e9ecef;
        font-weight: 600;
        border-top: 2px solid #343a40;
    }

    .positive { color: #28a745; font-weight: bold; }
    .negative { color: #dc3545; font-weight: bold; }
    
    /* Ancien style pour compatibilité */
    .lead-balance-accordion {
        margin: 16px 0;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .accordion-header {
        background: linear-gradient(135deg, #800020, #600018);
        color: white;
        padding: 14px 18px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-weight: 600;
        transition: background 0.3s;
    }
    .accordion-header:hover { background: linear-gradient(135deg, #900030, #700028); }
    .accordion-header .arrow { transition: transform 0.3s; }
    .accordion-header.active .arrow { transform: rotate(90deg); }
    .accordion-content {
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.3s ease-out;
        background: #f8f9fa;
    }
    .accordion-content.active { max-height: 5000px; }
    .lead-balance-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
    }
    .lead-balance-table th {
        background: #343a40;
        color: white;
        padding: 10px 8px;
        text-align: right;
        border: 1px solid #dee2e6;
        font-weight: 600;
        white-space: nowrap;
    }
    .lead-balance-table th:first-child,
    .lead-balance-table th:nth-child(2),
    .lead-balance-table th:nth-child(3) { text-align: left; }
    .lead-balance-table td {
        padding: 6px 8px;
        border: 1px solid #dee2e6;
        background: white;
        text-align: right;
    }
    .lead-balance-table td:first-child,
    .lead-balance-table td:nth-child(2),
    .lead-balance-table td:nth-child(3) { text-align: left; }
    .lead-balance-table tr:nth-child(even) td { background: #f8f9fa; }
    .summary-box {
        padding: 12px 18px;
        background: #e8f5e9;
        border-left: 4px solid #28a745;
        margin: 8px;
        font-size: 13px;
    }
    .summary-box.warning {
        background: #fff3cd;
        border-left-color: #ffc107;
    }
    </style>
    """
    
    html = accordion_style
    
    # ==================== GÉNÉRATION DES SECTIONS SYSCOHADA ====================
    common_accounts = results.get('common_accounts', [])
    sheet_names = {'n': sheet_n, 'n_1': sheet_n_1}
    syscohada_sections = get_syscohada_sections()
    
    # Titre principal
    html += f'''
    <div class="lead-syscohada-container">
        <div class="lead-header">
            <h2>📊 Lead par Section Comptable - SYSCOHADA Révisé</h2>
            <p>Analyse comparative {sheet_n} vs {sheet_n_1}</p>
        </div>

        <!-- SECTION BILAN -->
        <div class="lead-category">
            <div class="category-header bilan">
                <span>🏛️ COMPTES DE BILAN</span>
            </div>

            <!-- ACTIF -->
            <div class="subcategory">
                <div class="subcategory-header actif">ACTIF</div>'''
    
    # Sections Actif
    for section_id in ['actif_immobilise', 'actif_circulant', 'tresorerie_actif']:
        if section_id in syscohada_sections:
            section_accounts = filter_accounts_by_section(common_accounts, syscohada_sections[section_id])
            if section_accounts:
                html += generate_section_html(section_id, syscohada_sections[section_id], section_accounts, sheet_names)
    
    html += '''
            </div>

            <!-- PASSIF -->
            <div class="subcategory">
                <div class="subcategory-header passif">PASSIF</div>'''
    
    # Sections Passif
    for section_id in ['capitaux_propres', 'dettes_financieres', 'dettes_fournisseurs', 
                       'dettes_fiscales_sociales', 'autres_dettes', 'tresorerie_passif']:
        if section_id in syscohada_sections:
            section_accounts = filter_accounts_by_section(common_accounts, syscohada_sections[section_id])
            if section_accounts:
                html += generate_section_html(section_id, syscohada_sections[section_id], section_accounts, sheet_names)
    
    html += '''
            </div>
        </div>

        <!-- SECTION COMPTE DE RÉSULTAT -->
        <div class="lead-category">
            <div class="category-header resultat">
                <span>📈 COMPTE DE RÉSULTAT</span>
            </div>

            <!-- CHARGES -->
            <div class="subcategory">
                <div class="subcategory-header charges">CHARGES</div>'''
    
    # Sections Charges
    for section_id in ['achats_marchandises', 'transports', 'services_exterieurs_a', 'services_exterieurs_b',
                       'impots_taxes', 'autres_charges', 'charges_personnel', 'charges_financieres',
                       'dotations_amortissements', 'dotations_provisions', 'charges_hao']:
        if section_id in syscohada_sections:
            section_accounts = filter_accounts_by_section(common_accounts, syscohada_sections[section_id])
            if section_accounts:
                html += generate_section_html(section_id, syscohada_sections[section_id], section_accounts, sheet_names)
    
    html += '''
            </div>

            <!-- PRODUITS -->
            <div class="subcategory">
                <div class="subcategory-header produits">PRODUITS</div>'''
    
    # Sections Produits
    for section_id in ['ventes', 'subventions_exploitation', 'production_immobilisee', 'variations_stocks_produits',
                       'produits_accessoires', 'autres_produits', 'produits_financiers', 
                       'transferts_charges', 'reprises_provisions', 'produits_hao']:
        if section_id in syscohada_sections:
            section_accounts = filter_accounts_by_section(common_accounts, syscohada_sections[section_id])
            if section_accounts:
                html += generate_section_html(section_id, syscohada_sections[section_id], section_accounts, sheet_names)
    
    html += '''
            </div>
        </div>
    </div>
    
    <!-- SECTION RÉCAPITULATIVE (ANCIEN FORMAT) -->'''

    
    # Accordéon 1: Comptes communs
    common_count = totals['common']['count']
    common_total_n = format_number(totals['common']['solde_n'])
    common_total_n_1 = format_number(totals['common']['solde_n_1'])
    common_ecart = format_number(totals['common']['ecart'])
    ecart_class = 'positive' if totals['common']['ecart'] >= 0 else 'negative'
    
    html += f"""
    <div class="lead-balance-accordion">
        <div class="accordion-header" onclick="this.classList.toggle('active'); this.nextElementSibling.classList.toggle('active');">
            <span>📊 1. Comptes communs aux deux périodes ({common_count} comptes)</span>
            <span class="arrow">›</span>
        </div>
        <div class="accordion-content">
            <div class="summary-box">
                <strong>Total Solde {sheet_n}:</strong> {common_total_n} | 
                <strong>Total Solde {sheet_n_1}:</strong> {common_total_n_1} | 
                <strong>Écart:</strong> <span class="{ecart_class}">{common_ecart}</span>
            </div>
            <div style="overflow-x: auto;">
            <table class="lead-balance-table">
                <thead>
                    <tr>
                        <th>Compte</th>
                        <th>Intitulé {sheet_n}</th>
                        <th>Intitulé {sheet_n_1}</th>
                        <th>Solde Débit {sheet_n}</th>
                        <th>Solde Crédit {sheet_n}</th>
                        <th>Solde Net {sheet_n}</th>
                        <th>Solde Débit {sheet_n_1}</th>
                        <th>Solde Crédit {sheet_n_1}</th>
                        <th>Solde Net {sheet_n_1}</th>
                        <th>Écart</th>
                        <th>Variation %</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for row in results['common_accounts']:
        ecart = row.get('Ecart', 0)
        variation = row.get('Variation', 0)
        ecart_class = 'positive' if ecart >= 0 else 'negative'
        var_str = f"{variation:.2f}%" if variation != np.inf else "N/A"
        
        html += f"""
                    <tr>
                        <td>{row.get('Compte', '')}</td>
                        <td>{row.get('Intitule_N', '')}</td>
                        <td>{row.get('Intitule_N_1', '')}</td>
                        <td>{format_number(row.get('Solde_Debit_N', 0))}</td>
                        <td>{format_number(row.get('Solde_Credit_N', 0))}</td>
                        <td><strong>{format_number(row.get('Solde_N', 0))}</strong></td>
                        <td>{format_number(row.get('Solde_Debit_N_1', 0))}</td>
                        <td>{format_number(row.get('Solde_Credit_N_1', 0))}</td>
                        <td><strong>{format_number(row.get('Solde_N_1', 0))}</strong></td>
                        <td class="{ecart_class}">{format_number(ecart)}</td>
                        <td class="{ecart_class}">{var_str}</td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            </div>
        </div>
    </div>
    """

    
    # Accordéon 2: Comptes uniquement en N (nouveaux)
    only_n_count = totals['only_n']['count']
    only_n_total = format_number(totals['only_n']['solde'])
    
    html += f"""
    <div class="lead-balance-accordion">
        <div class="accordion-header" onclick="this.classList.toggle('active'); this.nextElementSibling.classList.toggle('active');">
            <span>🆕 2. Comptes uniquement en {sheet_n} - Nouveaux ({only_n_count} comptes)</span>
            <span class="arrow">›</span>
        </div>
        <div class="accordion-content">
            <div class="summary-box warning">
                <strong>Total Solde Net:</strong> {only_n_total}
            </div>
            <div style="overflow-x: auto;">
            <table class="lead-balance-table">
                <thead>
                    <tr>
                        <th>Compte</th>
                        <th>Intitulé</th>
                        <th>Solde Débit</th>
                        <th>Solde Crédit</th>
                        <th>Solde Net</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for row in results['only_n']:
        html += f"""
                    <tr>
                        <td>{row.get('Compte', '')}</td>
                        <td>{row.get('Intitule', '')}</td>
                        <td>{format_number(row.get('Solde_Debit', 0))}</td>
                        <td>{format_number(row.get('Solde_Credit', 0))}</td>
                        <td><strong>{format_number(row.get('Solde_Net', 0))}</strong></td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            </div>
        </div>
    </div>
    """
    
    # Accordéon 3: Comptes uniquement en N-1 (supprimés)
    only_n_1_count = totals['only_n_1']['count']
    only_n_1_total = format_number(totals['only_n_1']['solde'])
    
    html += f"""
    <div class="lead-balance-accordion">
        <div class="accordion-header" onclick="this.classList.toggle('active'); this.nextElementSibling.classList.toggle('active');">
            <span>🗑️ 3. Comptes uniquement en {sheet_n_1} - Supprimés ({only_n_1_count} comptes)</span>
            <span class="arrow">›</span>
        </div>
        <div class="accordion-content">
            <div class="summary-box warning">
                <strong>Total Solde Net:</strong> {only_n_1_total}
            </div>
            <div style="overflow-x: auto;">
            <table class="lead-balance-table">
                <thead>
                    <tr>
                        <th>Compte</th>
                        <th>Intitulé</th>
                        <th>Solde Débit</th>
                        <th>Solde Crédit</th>
                        <th>Solde Net</th>
                    </tr>
                </thead>
                <tbody>
    """
    
    for row in results['only_n_1']:
        html += f"""
                    <tr>
                        <td>{row.get('Compte', '')}</td>
                        <td>{row.get('Intitule', '')}</td>
                        <td>{format_number(row.get('Solde_Debit', 0))}</td>
                        <td>{format_number(row.get('Solde_Credit', 0))}</td>
                        <td><strong>{format_number(row.get('Solde_Net', 0))}</strong></td>
                    </tr>
        """
    
    html += """
                </tbody>
            </table>
            </div>
        </div>
    </div>
    """
    
    return html


# ==================== API ENDPOINTS ====================

@router.post("/process-excel", response_model=LeadBalanceResponse)
async def process_lead_balance_excel(request: ExcelUploadRequest):
    """
    Endpoint API pour calculer les lead balances à partir d'un fichier Excel.
    
    Le fichier Excel doit contenir au moins 2 onglets:
    - Onglet 1: Balance N (période actuelle)
    - Onglet 2: Balance N-1 (période précédente)
    
    Colonnes attendues: Numéro, Intitulé, Solde Débit, Solde Crédit
    Le solde net est calculé: Solde Débit - Solde Crédit
    """
    try:
        logger.info(f"📥 Requête Lead Balance Excel reçue: {request.filename}")
        
        # Décoder le fichier base64
        try:
            file_content = base64.b64decode(request.file_base64)
            logger.info(f"📂 Fichier décodé: {len(file_content)} bytes")
        except Exception as e:
            raise ValueError(f"Erreur de décodage du fichier: {str(e)}")
        
        # Traiter le fichier Excel
        results = create_lead_balance_from_excel(file_content)
        
        # Générer le HTML des accordéons
        html_output = generate_accordion_html(results)
        
        # Préparer le message de résumé
        totals = results['totals']
        message = (
            f"✅ Lead Balance calculée depuis '{request.filename}': "
            f"{totals['common']['count']} comptes communs, "
            f"{totals['only_n']['count']} nouveaux comptes, "
            f"{totals['only_n_1']['count']} comptes supprimés"
        )
        
        logger.info(f"✅ {message}")
        
        return LeadBalanceResponse(
            success=True,
            message=message,
            results=results,
            html=html_output
        )
        
    except ValueError as e:
        logger.error(f"❌ Erreur de validation: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"❌ Erreur inattendue: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur serveur: {str(e)}")


@router.get("/health")
async def health_check():
    """Vérification de l'état du service Lead Balance"""
    return {"status": "ok", "service": "lead-balance"}
