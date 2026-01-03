"""
Script de test pour les États Financiers SYSCOHADA
Avec État de Contrôle COMPLET de la Balance (N et N-1)
"""
import pandas as pd
import sys
sys.path.insert(0, '.')
from etats_financiers import EtatsFinanciersCalculator, BalanceData

# Charger la balance Excel
balance_df = pd.read_excel('Balance excel.xlsx')
print('=== BALANCE CHARGÉE ===')
print(f'Lignes: {len(balance_df)} - Colonnes: {list(balance_df.columns)}')

# Convertir en BalanceData
headers = [str(col).strip() for col in balance_df.columns.tolist()]
rows = []
for _, row in balance_df.iterrows():
    row_data = [str(val) if pd.notna(val) else '' for val in row.tolist()]
    rows.append(row_data)

balance_data = BalanceData(headers=headers, rows=rows)

# Calculer les états financiers
calc = EtatsFinanciersCalculator()
result = calc.calculate_etats_financiers(balance_data, 'N', 'N-1')

print()
print('=== RÉSULTATS ===')
print('Success:', result["success"])

# Résumé des états financiers
print()
print(f"BILAN ACTIF:  N = {result['bilan_actif']['total']['n']:>15,.0f} FCFA")
print(f"BILAN PASSIF: N = {result['bilan_passif']['total']['n']:>15,.0f} FCFA")
print(f"RÉSULTAT:     N = {result['compte_resultat']['resultat']['n']:>15,.0f} FCFA")

# ═══════════════════════════════════════════════════════════════════════════════
# ÉTAT DE CONTRÔLE COMPLET
# ═══════════════════════════════════════════════════════════════════════════════
print()
print('═' * 80)
print('                         ÉTAT DE CONTRÔLE DE LA BALANCE')
print('═' * 80)

if 'etat_controle' in result:
    ctrl = result['etat_controle']
    
    # ─────────────────────────────────────────────────────────────────────────
    # 1. CONTRÔLE DE LA BALANCE
    # ─────────────────────────────────────────────────────────────────────────
    print()
    print('┌' + '─' * 78 + '┐')
    print('│ 1. CONTRÔLE DE LA BALANCE (Total Débits = Total Crédits)' + ' ' * 20 + '│')
    print('├' + '─' * 78 + '┤')
    
    bal = ctrl.get('balance', {})
    status_bal = '✅ ÉQUILIBRÉE' if bal.get('equilibree', False) else '❌ DÉSÉQUILIBRÉE'
    print(f'│ Statut: {status_bal:66} │')
    print('│' + ' ' * 78 + '│')
    print(f"│   Total Débits:     {bal.get('total_debit', 0):>25,.0f} FCFA" + ' ' * 20 + '│')
    print(f"│   Total Crédits:    {bal.get('total_credit', 0):>25,.0f} FCFA" + ' ' * 20 + '│')
    print(f"│   Écart:            {bal.get('ecart', 0):>25,.0f} FCFA" + ' ' * 20 + '│')
    print(f"│   Nombre de comptes: {bal.get('nb_comptes', 0):>10}" + ' ' * 46 + '│')
    print('└' + '─' * 78 + '┘')
    
    # ─────────────────────────────────────────────────────────────────────────
    # 2. CONTRÔLE D'INTÉGRATION
    # ─────────────────────────────────────────────────────────────────────────
    print()
    print('┌' + '─' * 78 + '┐')
    print('│ 2. CONTRÔLE D\'INTÉGRATION' + ' ' * 52 + '│')
    print('├' + '─' * 78 + '┤')
    
    integ = ctrl.get('integration', {})
    taux = integ.get('taux_couverture', 0)
    status_taux = '✅' if taux >= 95 else '⚠️' if taux >= 80 else '❌'
    print(f'│ Taux de couverture: {status_taux} {taux:.1f}%' + ' ' * 50 + '│')
    print('│' + ' ' * 78 + '│')
    
    ci = integ.get('comptes_integres', {})
    cni = integ.get('comptes_non_integres', {})
    print(f"│   Comptes intégrés:     {ci.get('nombre', 0):>5} comptes" + ' ' * 45 + '│')
    print(f"│     → Solde N:          {ci.get('total_solde_n', ci.get('total_solde', 0)):>20,.0f} FCFA" + ' ' * 20 + '│')
    print(f"│     → Solde N-1:        {ci.get('total_solde_n1', 0):>20,.0f} FCFA" + ' ' * 20 + '│')
    print('│' + ' ' * 78 + '│')
    print(f"│   Comptes NON intégrés: {cni.get('nombre', 0):>5} comptes" + ' ' * 45 + '│')
    print(f"│     → Solde N:          {cni.get('total_solde_n', cni.get('total_solde', 0)):>20,.0f} FCFA" + ' ' * 20 + '│')
    print(f"│     → Solde N-1:        {cni.get('total_solde_n1', 0):>20,.0f} FCFA" + ' ' * 20 + '│')
    print('└' + '─' * 78 + '┘')
    
    # ─────────────────────────────────────────────────────────────────────────
    # 3. TABLEAU COMPLET DES COMPTES NON INTÉGRÉS - EXERCICE N
    # ─────────────────────────────────────────────────────────────────────────
    liste_n = cni.get('liste_complete_n', cni.get('liste', []))
    if liste_n:
        print()
        print('┌' + '─' * 78 + '┐')
        print('│ TABLEAU DES COMPTES NON INTÉGRÉS - EXERCICE N' + ' ' * 32 + '│')
        print('├' + '─' * 78 + '┤')
        print(f"│ {'N° Compte':<10} {'Intitulé':<35} {'Débit N':>12} {'Crédit N':>12} {'Solde N':>12} │")
        print('├' + '─' * 78 + '┤')
        
        total_deb = 0
        total_cred = 0
        total_solde = 0
        
        for c in liste_n:
            num = str(c.get('numero', ''))[:10]
            intit = str(c.get('intitule', ''))[:35]
            deb = c.get('debit_n', 0)
            cred = c.get('credit_n', 0)
            solde = c.get('solde_n', 0)
            total_deb += deb
            total_cred += cred
            total_solde += solde
            print(f"│ {num:<10} {intit:<35} {deb:>12,.0f} {cred:>12,.0f} {solde:>12,.0f} │")
        
        print('├' + '─' * 78 + '┤')
        print(f"│ {'TOTAL':<10} {'':<35} {total_deb:>12,.0f} {total_cred:>12,.0f} {total_solde:>12,.0f} │")
        print('└' + '─' * 78 + '┘')
    
    # ─────────────────────────────────────────────────────────────────────────
    # 4. TABLEAU COMPLET DES COMPTES NON INTÉGRÉS - EXERCICE N-1
    # ─────────────────────────────────────────────────────────────────────────
    liste_n1 = cni.get('liste_complete_n1', [])
    # Filtrer les comptes avec solde N-1 non nul
    liste_n1_non_nul = [c for c in liste_n1 if c.get('solde_n1', 0) != 0]
    
    if liste_n1_non_nul:
        print()
        print('┌' + '─' * 78 + '┐')
        print('│ TABLEAU DES COMPTES NON INTÉGRÉS - EXERCICE N-1' + ' ' * 30 + '│')
        print('├' + '─' * 78 + '┤')
        print(f"│ {'N° Compte':<10} {'Intitulé':<45} {'Solde N-1':>18} │")
        print('├' + '─' * 78 + '┤')
        
        total_solde_n1 = 0
        for c in liste_n1_non_nul:
            num = str(c.get('numero', ''))[:10]
            intit = str(c.get('intitule', ''))[:45]
            solde = c.get('solde_n1', 0)
            total_solde_n1 += solde
            print(f"│ {num:<10} {intit:<45} {solde:>18,.0f} │")
        
        print('├' + '─' * 78 + '┤')
        print(f"│ {'TOTAL':<10} {'':<45} {total_solde_n1:>18,.0f} │")
        print('└' + '─' * 78 + '┘')
    else:
        print()
        print('│ Aucun compte non intégré avec solde N-1 non nul' + ' ' * 30 + '│')
    
    # ─────────────────────────────────────────────────────────────────────────
    # 5. ANALYSE PAR CLASSE DE COMPTES NON INTÉGRÉS
    # ─────────────────────────────────────────────────────────────────────────
    par_classe = cni.get('par_classe', [])
    if par_classe:
        print()
        print('┌' + '─' * 78 + '┐')
        print('│ ANALYSE PAR CLASSE DE COMPTES NON INTÉGRÉS' + ' ' * 34 + '│')
        print('├' + '─' * 78 + '┤')
        print(f"│ {'Classe':<30} {'Nb':>5} {'Solde N':>18} {'Solde N-1':>18} │")
        print('├' + '─' * 78 + '┤')
        
        for cl in sorted(par_classe, key=lambda x: x.get('classe', '')):
            nom = cl.get('nom', '')[:30]
            nb = cl.get('nombre', 0)
            solde_n = cl.get('total_solde_n', cl.get('total_solde', 0))
            solde_n1 = cl.get('total_solde_n1', 0)
            print(f"│ {nom:<30} {nb:>5} {solde_n:>18,.0f} {solde_n1:>18,.0f} │")
        
        print('└' + '─' * 78 + '┘')
    
    # ─────────────────────────────────────────────────────────────────────────
    # 6. CONTRÔLE DES ÉTATS FINANCIERS
    # ─────────────────────────────────────────────────────────────────────────
    print()
    print('┌' + '─' * 78 + '┐')
    print('│ CONTRÔLE DES ÉTATS FINANCIERS (Actif = Passif + Résultat)' + ' ' * 19 + '│')
    print('├' + '─' * 78 + '┤')
    
    ef = ctrl.get('etats_financiers', ctrl.get('equilibre', {}))
    status_n = '✅ CONFORME' if ef.get('conforme_n', False) else '❌ NON CONFORME'
    status_n1 = '✅ CONFORME' if ef.get('conforme_n1', False) else '❌ NON CONFORME'
    
    print(f"│ {'':30} {'Exercice N':>20} {'Exercice N-1':>20} │")
    print('├' + '─' * 78 + '┤')
    print(f"│ {'Total Actif':<30} {ef.get('total_actif_n', 0):>20,.0f} {ef.get('total_actif_n1', 0):>20,.0f} │")
    print(f"│ {'Total Passif':<30} {ef.get('total_passif_n', 0):>20,.0f} {ef.get('total_passif_n1', 0):>20,.0f} │")
    print(f"│ {'Résultat Net':<30} {ef.get('resultat_n', 0):>20,.0f} {ef.get('resultat_n1', 0):>20,.0f} │")
    print('├' + '─' * 78 + '┤')
    eq_n = ef.get('equilibre_theorique_n', ef.get('total_passif_n', 0) + ef.get('resultat_n', 0))
    eq_n1 = ef.get('equilibre_theorique_n1', ef.get('total_passif_n1', 0) + ef.get('resultat_n1', 0))
    print(f"│ {'Passif + Résultat':<30} {eq_n:>20,.0f} {eq_n1:>20,.0f} │")
    print(f"│ {'Écart':<30} {ef.get('ecart_n', 0):>20,.0f} {ef.get('ecart_n1', 0):>20,.0f} │")
    print('├' + '─' * 78 + '┤')
    print(f"│ {'Statut':<30} {status_n:>20} {status_n1:>20} │")
    print('└' + '─' * 78 + '┘')
    
    # ─────────────────────────────────────────────────────────────────────────
    # 7. RECOMMANDATIONS
    # ─────────────────────────────────────────────────────────────────────────
    recommandations = ctrl.get('recommandations', [])
    if recommandations:
        print()
        print('┌' + '─' * 78 + '┐')
        print('│ RECOMMANDATIONS' + ' ' * 62 + '│')
        print('├' + '─' * 78 + '┤')
        for rec in recommandations:
            if isinstance(rec, dict):
                msg = rec.get('message', '')
            else:
                msg = str(rec)
            # Découper le message si trop long
            while len(msg) > 76:
                print(f'│ {msg[:76]} │')
                msg = '  ' + msg[76:]
            print(f'│ {msg:<76} │')
        print('└' + '─' * 78 + '┘')
    
    print()
    print('═' * 80)
    
else:
    print("   État de contrôle non disponible")
