/**
 * Menu Démarrer - E-audit Pro
 * 
 * Ce script gère le bouton [Démarrer] et son menu contextuel hiérarchique
 * pour automatiser les prompts dans la zone de saisie du chat.
 * 
 * @version 1.0.0
 * @author E-audit Team
 */

(function () {
    'use strict';

    // ============================================================
    // CONFIGURATION DU MENU
    // ============================================================

    const MENU_CONFIG = {
        // E-audit Pro
        'E-audit pro': {
            'Phase de préparation': {
                'Cartographie des risques': {
                    command: `[Command] = Cartographie des risques
[Processus] = inventaire de caisse
[Risques critiques] = fraude
[Objectif] = couvrir la fraude`,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Référentiel de contrôle interne': {
                    command: `[Command] = Référentiel de contrôle interne
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Questionnaire de contrôle interne': {
                    command: `[Command] = Questionnaire de contrôle interne
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Tableau des forces et faiblesses apparentes': {
                    command: `[Command] = Tableau des forces et faiblesses apparentes
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Rapport d\'orientation': {
                    command: `[Command] = Rapport d'orientation
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Programme de travail': {
                    command: `[Command] = Programme de travail
[Processus] = inventaire de caisse`,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            },
            'Phase de réalisation': {
                'Feuille couverture': {
                    command: `[Command] = Feuille couverture
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            },
            'Phase de conclusion': {
                'Frap': {
                    command: `[Command] = Frap
[Processus] = 
[Constat] = 
[Recommandation] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Synthèse des Frap': {
                    command: `[Command] = Synthèse des Frap
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Rapport provisoire': {
                    command: `[Command] = Rapport provisoire
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Réunion de clôture': {
                    command: `[Command] = Réunion de clôture
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Rapport final': {
                    command: `[Command] = Rapport final
[Processus] = 
[Objectif] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            }
        },
        // E-cartographie
        'E-cartographie': {
            'Analyse des risques': {
                'Identification des risques': {
                    command: `[Command] = Identification des risques
[Domaine] = 
[Périmètre] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Évaluation des risques': {
                    command: `[Command] = Évaluation des risques
[Domaine] = 
[Critères] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Matrice des risques': {
                    command: `[Command] = Matrice des risques
[Domaine] = 
[Format] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            }
        },
        // E-revision
        'E-revision': {
            'Contrôle des comptes': {
                'Revue analytique': {
                    command: `[Command] = Revue analytique
[Compte] = 
[Période] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Tests de détail': {
                    command: `[Command] = Tests de détail
[Compte] = 
[Échantillon] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            }
        },
        // Bibliothèque
        'Bibliothèque': {
            'Guides': {
                'Guide méthodologique': {
                    command: `[Command] = Guide méthodologique
[Thème] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                },
                'Bonnes pratiques': {
                    command: `[Command] = Bonnes pratiques
[Domaine] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            },
            'Commandes complémentaires': {
                'Aide contextuelle': {
                    command: `[Command] = Aide
[Sujet] = `,
                    submenu: ['Normal', 'Avancé', 'Intelligent', 'Manuel']
                }
            }
        }
    };

    // ============================================================
    // VARIABLES GLOBALES
    // ============================================================

    let menuContainer = null;
    let isMenuOpen = false;
    let demarrerButton = null;

    // ============================================================
    // STYLES CSS
    // ============================================================

    const MENU_STYLES = `
        /* Bouton Démarrer */
        .demarrer-btn {
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            background: linear-gradient(135deg, #ec4899 0%, #f472b6 100%);
            color: white;
            border: none;
            border-radius: 9999px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 2px 8px rgba(236, 72, 153, 0.3);
        }
        
        .demarrer-btn:hover {
            background: linear-gradient(135deg, #db2777 0%, #ec4899 100%);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(236, 72, 153, 0.4);
        }
        
        .demarrer-btn:active {
            transform: translateY(0);
        }
        
        .demarrer-btn.active {
            background: linear-gradient(135deg, #be185d 0%, #db2777 100%);
        }
        
        .demarrer-btn svg {
            width: 16px;
            height: 16px;
        }

        /* Container du menu */
        .demarrer-menu-container {
            position: fixed;
            z-index: 9999;
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15), 0 2px 10px rgba(0, 0, 0, 0.1);
            border: 1px solid rgba(0, 0, 0, 0.08);
            min-width: 280px;
            max-width: 350px;
            max-height: 70vh;
            overflow-y: auto;
            animation: menuSlideIn 0.2s ease-out;
        }
        
        .dark .demarrer-menu-container {
            background: #1f2937;
            border-color: rgba(255, 255, 255, 0.1);
            box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4);
        }
        
        @keyframes menuSlideIn {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        /* En-tête du menu */
        .demarrer-menu-header {
            padding: 12px 16px;
            border-bottom: 1px solid rgba(0, 0, 0, 0.08);
            font-weight: 600;
            font-size: 14px;
            color: #374151;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .dark .demarrer-menu-header {
            color: #f3f4f6;
            border-color: rgba(255, 255, 255, 0.1);
        }

        /* Section du menu (logiciel) */
        .demarrer-menu-section {
            border-bottom: 1px solid rgba(0, 0, 0, 0.05);
        }
        
        .dark .demarrer-menu-section {
            border-color: rgba(255, 255, 255, 0.05);
        }
        
        .demarrer-menu-section:last-child {
            border-bottom: none;
        }

        /* Titre de section (logiciel) */
        .demarrer-section-title {
            padding: 10px 16px;
            font-weight: 600;
            font-size: 13px;
            color: #ec4899;
            background: rgba(236, 72, 153, 0.05);
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: background 0.15s ease;
        }
        
        .demarrer-section-title:hover {
            background: rgba(236, 72, 153, 0.1);
        }
        
        .demarrer-section-title svg {
            width: 14px;
            height: 14px;
            transition: transform 0.2s ease;
        }
        
        .demarrer-section-title.expanded svg {
            transform: rotate(180deg);
        }

        /* Contenu de section */
        .demarrer-section-content {
            display: none;
            padding: 4px 0;
        }
        
        .demarrer-section-content.expanded {
            display: block;
        }

        /* Phase (sous-section) */
        .demarrer-phase {
            padding: 8px 16px 8px 24px;
            font-weight: 500;
            font-size: 12px;
            color: #6b7280;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .dark .demarrer-phase {
            color: #9ca3af;
        }

        /* Item du menu (étape de mission) */
        .demarrer-menu-item {
            padding: 8px 16px 8px 32px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 13px;
            color: #374151;
            transition: all 0.15s ease;
        }
        
        .dark .demarrer-menu-item {
            color: #e5e7eb;
        }
        
        .demarrer-menu-item:hover {
            background: rgba(236, 72, 153, 0.08);
            color: #ec4899;
        }
        
        .demarrer-menu-item svg {
            width: 12px;
            height: 12px;
            opacity: 0.5;
        }

        /* Sous-menu (Normal, Avancé, etc.) */
        .demarrer-submenu {
            display: none;
            padding: 4px 0 4px 40px;
            background: rgba(0, 0, 0, 0.02);
        }
        
        .dark .demarrer-submenu {
            background: rgba(255, 255, 255, 0.02);
        }
        
        .demarrer-submenu.expanded {
            display: block;
        }

        /* Item du sous-menu */
        .demarrer-submenu-item {
            padding: 6px 16px;
            cursor: pointer;
            font-size: 12px;
            color: #6b7280;
            border-radius: 4px;
            margin: 2px 8px;
            transition: all 0.15s ease;
        }
        
        .dark .demarrer-submenu-item {
            color: #9ca3af;
        }
        
        .demarrer-submenu-item:hover {
            background: rgba(236, 72, 153, 0.1);
            color: #ec4899;
        }
        
        .demarrer-submenu-item.active {
            background: #ec4899;
            color: white;
        }

        /* Scrollbar personnalisée */
        .demarrer-menu-container::-webkit-scrollbar {
            width: 6px;
        }
        
        .demarrer-menu-container::-webkit-scrollbar-track {
            background: transparent;
        }
        
        .demarrer-menu-container::-webkit-scrollbar-thumb {
            background: rgba(0, 0, 0, 0.2);
            border-radius: 3px;
        }
        
        .dark .demarrer-menu-container::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.2);
        }
    `;

    // ============================================================
    // FONCTIONS UTILITAIRES
    // ============================================================

    /**
     * Injecte les styles CSS dans le document
     */
    function injectStyles() {
        if (document.getElementById('demarrer-menu-styles')) return;

        const styleElement = document.createElement('style');
        styleElement.id = 'demarrer-menu-styles';
        styleElement.textContent = MENU_STYLES;
        document.head.appendChild(styleElement);
    }

    /**
     * Crée l'icône SVG pour le bouton
     */
    function createPlayIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>`;
    }

    /**
     * Crée l'icône chevron
     */
    function createChevronIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="6 9 12 15 18 9"></polyline>
        </svg>`;
    }

    /**
     * Crée l'icône flèche droite
     */
    function createArrowRightIcon() {
        return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="9 18 15 12 9 6"></polyline>
        </svg>`;
    }

    /**
     * Trouve la zone de saisie du chat
     */
    function findChatInput() {
        // Chercher par data attribute
        let input = document.querySelector('textarea[data-chat-input="true"]');
        if (input) return input;

        // Chercher par placeholder
        input = document.querySelector('textarea[placeholder*="Demarrer"]');
        if (input) return input;

        // Chercher dans le composant Clara
        input = document.querySelector('.clara-input textarea');
        if (input) return input;

        // Fallback: premier textarea visible
        const textareas = document.querySelectorAll('textarea');
        for (const ta of textareas) {
            if (ta.offsetParent !== null) return ta;
        }

        return null;
    }

    /**
     * Insère le texte dans la zone de saisie
     */
    function insertTextInChat(text) {
        const input = findChatInput();
        if (!input) {
            console.error('[Démarrer Menu] Zone de saisie non trouvée');
            return false;
        }

        // Définir la valeur
        input.value = text;

        // Déclencher les événements React
        const nativeInputValueSetter = Object.getOwnPropertyDescriptor(
            window.HTMLTextAreaElement.prototype, 'value'
        ).set;
        nativeInputValueSetter.call(input, text);

        // Événement input
        const inputEvent = new Event('input', { bubbles: true, cancelable: true });
        input.dispatchEvent(inputEvent);

        // Événement change
        const changeEvent = new Event('change', { bubbles: true, cancelable: true });
        input.dispatchEvent(changeEvent);

        // Focus sur l'input
        input.focus();

        // Ajuster la hauteur si nécessaire
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 200) + 'px';

        console.log('[Démarrer Menu] Texte inséré:', text);
        return true;
    }

    // ============================================================
    // CONSTRUCTION DU MENU
    // ============================================================

    /**
     * Construit le HTML du menu
     */
    function buildMenuHTML() {
        let html = `
            <div class="demarrer-menu-header">
                ${createPlayIcon()}
                <span>Menu Démarrer</span>
            </div>
        `;

        // Parcourir les logiciels
        for (const [software, phases] of Object.entries(MENU_CONFIG)) {
            html += `
                <div class="demarrer-menu-section" data-software="${software}">
                    <div class="demarrer-section-title" data-toggle="section">
                        <span>${software}</span>
                        ${createChevronIcon()}
                    </div>
                    <div class="demarrer-section-content">
            `;

            // Parcourir les phases
            for (const [phase, items] of Object.entries(phases)) {
                html += `<div class="demarrer-phase">${phase}</div>`;

                // Parcourir les items
                for (const [itemName, itemConfig] of Object.entries(items)) {
                    const itemId = `${software}-${phase}-${itemName}`.replace(/\s+/g, '-').toLowerCase();

                    html += `
                        <div class="demarrer-menu-item" data-item-id="${itemId}" data-command="${encodeURIComponent(itemConfig.command)}">
                            <span>${itemName}</span>
                            ${createArrowRightIcon()}
                        </div>
                        <div class="demarrer-submenu" data-submenu-for="${itemId}">
                    `;

                    // Sous-menu (Normal, Avancé, etc.)
                    for (const subItem of itemConfig.submenu) {
                        html += `
                            <div class="demarrer-submenu-item" data-mode="${subItem}" data-command="${encodeURIComponent(itemConfig.command)}">
                                ${subItem}
                            </div>
                        `;
                    }

                    html += `</div>`;
                }
            }

            html += `
                    </div>
                </div>
            `;
        }

        return html;
    }

    /**
     * Crée et affiche le menu
     */
    function showMenu() {
        if (menuContainer) {
            hideMenu();
            return;
        }

        // Créer le container
        menuContainer = document.createElement('div');
        menuContainer.className = 'demarrer-menu-container';
        menuContainer.innerHTML = buildMenuHTML();

        // Positionner le menu
        if (demarrerButton) {
            const rect = demarrerButton.getBoundingClientRect();
            menuContainer.style.bottom = (window.innerHeight - rect.top + 10) + 'px';
            menuContainer.style.left = rect.left + 'px';
        }

        // Ajouter au DOM
        document.body.appendChild(menuContainer);
        isMenuOpen = true;

        // Marquer le bouton comme actif
        if (demarrerButton) {
            demarrerButton.classList.add('active');
        }

        // Attacher les événements
        attachMenuEvents();
    }

    /**
     * Cache le menu
     */
    function hideMenu() {
        if (menuContainer) {
            menuContainer.remove();
            menuContainer = null;
        }
        isMenuOpen = false;

        if (demarrerButton) {
            demarrerButton.classList.remove('active');
        }
    }

    /**
     * Attache les événements au menu
     */
    function attachMenuEvents() {
        if (!menuContainer) return;

        // Toggle des sections
        menuContainer.querySelectorAll('.demarrer-section-title').forEach(title => {
            title.addEventListener('click', (e) => {
                e.stopPropagation();
                const section = title.closest('.demarrer-menu-section');
                const content = section.querySelector('.demarrer-section-content');

                title.classList.toggle('expanded');
                content.classList.toggle('expanded');
            });
        });

        // Click sur les items
        menuContainer.querySelectorAll('.demarrer-menu-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.stopPropagation();
                const itemId = item.dataset.itemId;
                const submenu = menuContainer.querySelector(`[data-submenu-for="${itemId}"]`);

                // Toggle le sous-menu
                if (submenu) {
                    submenu.classList.toggle('expanded');
                }

                // Si click direct sur l'item (pas sur le sous-menu), insérer la commande
                const command = decodeURIComponent(item.dataset.command);
                insertTextInChat(command);
                hideMenu();
            });
        });

        // Click sur les sous-items
        menuContainer.querySelectorAll('.demarrer-submenu-item').forEach(subItem => {
            subItem.addEventListener('click', (e) => {
                e.stopPropagation();
                const mode = subItem.dataset.mode;
                let command = decodeURIComponent(subItem.dataset.command);

                // Ajouter le mode si ce n'est pas "Normal"
                if (mode !== 'Normal') {
                    command = `[Mode] = ${mode}\n${command}`;
                }

                insertTextInChat(command);
                hideMenu();
            });
        });

        // Fermer le menu si click en dehors
        document.addEventListener('click', handleOutsideClick);
    }

    /**
     * Gère le click en dehors du menu
     */
    function handleOutsideClick(e) {
        if (!menuContainer) return;

        if (!menuContainer.contains(e.target) && !demarrerButton?.contains(e.target)) {
            hideMenu();
            document.removeEventListener('click', handleOutsideClick);
        }
    }

    // ============================================================
    // CRÉATION DU BOUTON
    // ============================================================

    /**
     * Crée le bouton Démarrer
     */
    function createDemarrerButton() {
        const button = document.createElement('button');
        button.className = 'demarrer-btn';
        button.innerHTML = `${createPlayIcon()}<span>Démarrer</span>`;
        button.title = 'Menu Démarrer E-audit';

        button.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (isMenuOpen) {
                hideMenu();
            } else {
                showMenu();
            }
        });

        return button;
    }

    /**
     * Insère le bouton dans l'interface
     */
    function insertButton() {
        // Chercher la zone des boutons (avant le bouton micro)
        const voiceButton = document.querySelector('button[class*="rounded-full"]');
        if (!voiceButton) {
            console.log('[Démarrer Menu] Bouton micro non trouvé, réessai...');
            return false;
        }

        // Chercher le container des options
        const optionsContainer = document.querySelector('.flex.flex-wrap.items-center.justify-center.gap-2');
        if (!optionsContainer) {
            console.log('[Démarrer Menu] Container des options non trouvé, réessai...');
            return false;
        }

        // Vérifier si le bouton existe déjà
        if (document.querySelector('.demarrer-btn')) {
            console.log('[Démarrer Menu] Bouton déjà présent');
            return true;
        }

        // Créer le bouton
        demarrerButton = createDemarrerButton();

        // Trouver le bouton micro pour insérer avant
        const micButton = optionsContainer.querySelector('button svg.w-4.h-4')?.closest('button');

        if (micButton) {
            // Insérer avant le bouton micro
            micButton.parentNode.insertBefore(demarrerButton, micButton);
        } else {
            // Sinon, ajouter au début
            optionsContainer.insertBefore(demarrerButton, optionsContainer.firstChild);
        }

        console.log('[Démarrer Menu] Bouton inséré avec succès');
        return true;
    }

    // ============================================================
    // INITIALISATION
    // ============================================================

    /**
     * Initialise le menu Démarrer
     */
    function init() {
        console.log('[Démarrer Menu] Initialisation...');

        // Injecter les styles
        injectStyles();

        // Essayer d'insérer le bouton
        if (!insertButton()) {
            // Réessayer après un délai
            setTimeout(() => {
                if (!insertButton()) {
                    // Observer les changements du DOM
                    const observer = new MutationObserver((mutations, obs) => {
                        if (insertButton()) {
                            obs.disconnect();
                        }
                    });

                    observer.observe(document.body, {
                        childList: true,
                        subtree: true
                    });

                    // Timeout de sécurité
                    setTimeout(() => observer.disconnect(), 30000);
                }
            }, 1000);
        }
    }

    // Démarrer l'initialisation
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Exposer l'API globale
    window.DemarrerMenu = {
        show: showMenu,
        hide: hideMenu,
        toggle: () => isMenuOpen ? hideMenu() : showMenu(),
        insertCommand: insertTextInChat,
        isOpen: () => isMenuOpen
    };

})();
