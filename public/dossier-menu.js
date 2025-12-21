// Menu Dossier - Barre latérale accordéon pour les tables des messages LLM
// Version 2.0 - VRAI accordéon avec signes + et affichage complet des tables

(function () {
    "use strict";

    class DossierMenuManager {
        constructor() {
            this.menuElement = null;
            this.isMenuVisible = false;
            this.initialized = false;
            this.openAccordions = new Set(); // Garder trace des accordéons ouverts

            // Configuration
            this.config = {
                menuWidth: "50%",
                animationDuration: 300,
                autoRefreshInterval: 2000,
            };
        }

        // Initialise le gestionnaire de menu Dossier
        init() {
            if (this.initialized) return;

            console.log("📁 Initialisation du menu Dossier v2.0");
            this.createMenuElement();
            this.attachEventListeners();
            this.observeNewMessages();
            this.initialized = true;

            console.log("✅ Menu Dossier v2.0 initialisé avec succès");
        }

        // Crée l'élément HTML du menu coulissant
        createMenuElement() {
            this.menuElement = document.createElement("div");
            this.menuElement.id = "dossier-menu";
            this.menuElement.className = "dossier-menu hidden";
            this.menuElement.style.cssText = `
        position: fixed;
        top: 0;
        right: 0;
        width: ${this.config.menuWidth};
        height: 100vh;
        background: #1f2937;
        border-left: 1px solid #374151;
        box-shadow: -4px 0 20px rgba(0, 0, 0, 0.3);
        z-index: 20000;
        display: flex;
        flex-direction: column;
        transform: translateX(100%);
        transition: transform ${this.config.animationDuration}ms cubic-bezier(0.175, 0.885, 0.32, 1.275);
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      `;

            // En-tête du menu
            const header = document.createElement("div");
            header.className = "dossier-menu-header";
            header.style.cssText = `
        padding: 20px;
        background: #111827;
        color: white;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 1px solid #374151;
      `;

            header.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
          <span style="font-size: 24px;">📁</span>
          <h2 style="margin: 0; font-size: 20px; font-weight: 600;">Dossier - Tables</h2>
        </div>
        <button id="dossier-close-btn" style="
          background: rgba(255, 255, 255, 0.1);
          border: none;
          color: white;
          width: 32px;
          height: 32px;
          border-radius: 50%;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          transition: all 0.2s ease;
        ">✕</button>
      `;

            // Zone de contenu avec accordéon
            const content = document.createElement("div");
            content.id = "dossier-menu-content";
            content.className = "dossier-menu-content";
            content.style.cssText = `
        flex: 1;
        overflow-y: auto;
        padding: 20px;
        background: #1f2937;
      `;

            this.menuElement.appendChild(header);
            this.menuElement.appendChild(content);
            document.body.appendChild(this.menuElement);

            // Événement de fermeture
            const closeBtn = header.querySelector("#dossier-close-btn");
            closeBtn.addEventListener("mouseenter", () => {
                closeBtn.style.background = "rgba(255, 255, 255, 0.2)";
                closeBtn.style.transform = "scale(1.1)";
            });
            closeBtn.addEventListener("mouseleave", () => {
                closeBtn.style.background = "rgba(255, 255, 255, 0.1)";
                closeBtn.style.transform = "scale(1)";
            });
            closeBtn.addEventListener("click", () => this.hideMenu());
        }

        // Attache les événements principaux
        attachEventListeners() {
            // Écouter les clics sur l'icône Dossier dans la sidebar
            document.addEventListener("click", (e) => {
                const dossierBtn = e.target.closest('[data-page="dossier"]');
                if (dossierBtn) {
                    e.preventDefault();
                    e.stopPropagation();
                    this.toggleMenu();
                }
            });

            // Fermer avec Escape
            document.addEventListener("keydown", (e) => {
                if (e.key === "Escape" && this.isMenuVisible) {
                    this.hideMenu();
                }
            });

            // Rafraîchissement automatique
            setInterval(() => {
                if (this.isMenuVisible) {
                    this.refreshAccordion();
                }
            }, this.config.autoRefreshInterval);
        }

        // Observer les nouveaux messages dans le chat
        observeNewMessages() {
            const observer = new MutationObserver(() => {
                if (this.isMenuVisible) {
                    this.refreshAccordion();
                }
            });

            // Observer le conteneur de chat
            const chatContainer = document.querySelector(".chat-messages, [data-clara-container]");
            if (chatContainer) {
                observer.observe(chatContainer, {
                    childList: true,
                    subtree: true,
                });
            }
        }

        // Affiche le menu
        showMenu() {
            this.isMenuVisible = true;
            this.menuElement.classList.remove("hidden");

            // Animation d'entrée
            requestAnimationFrame(() => {
                this.menuElement.style.transform = "translateX(0)";
            });

            this.refreshAccordion();
            console.log("📁 Menu Dossier affiché");
        }

        // Masque le menu
        hideMenu() {
            this.isMenuVisible = false;
            this.menuElement.style.transform = "translateX(100%)";

            setTimeout(() => {
                this.menuElement.classList.add("hidden");
            }, this.config.animationDuration);

            console.log("📁 Menu Dossier masqué");
        }

        // Bascule l'affichage du menu
        toggleMenu() {
            if (this.isMenuVisible) {
                this.hideMenu();
            } else {
                this.showMenu();
            }
        }

        // Rafraîchit le contenu de l'accordéon
        refreshAccordion() {
            const content = document.getElementById("dossier-menu-content");
            if (!content) return;

            // Récupérer tous les messages du système LLM avec des tables
            const llmMessages = this.getLLMMessagesWithTables();

            if (llmMessages.length === 0) {
                content.innerHTML = `
          <div style="
            text-align: center;
            padding: 40px 20px;
            color: #9ca3af;
          ">
            <div style="font-size: 48px; margin-bottom: 16px;">📭</div>
            <p style="font-size: 16px; margin: 0;">Aucune table trouvée</p>
            <p style="font-size: 14px; margin-top: 8px; opacity: 0.7;">
              Les tables des messages LLM apparaîtront ici
            </p>
          </div>
        `;
                return;
            }

            // Créer les éléments d'accordéon
            content.innerHTML = "";
            llmMessages.forEach((messageData, index) => {
                const accordionItem = this.createAccordionItem(messageData, index);
                content.appendChild(accordionItem);
            });

            console.log(`✅ Accordéon rafraîchi: ${llmMessages.length} messages avec tables`);
        }

        // Récupère tous les messages LLM contenant des tables
        getLLMMessagesWithTables() {
            const messages = [];

            // Sélecteur pour les messages de l'assistant (LLM)
            const assistantMessages = document.querySelectorAll(
                '.message-assistant, [data-role="assistant"], .prose.prose-base'
            );

            assistantMessages.forEach((messageDiv, index) => {
                // Chercher les tables dans ce message
                const tables = messageDiv.querySelectorAll(
                    'table.min-w-full.border.border-gray-200.dark\\:border-gray-700.rounded-lg, table'
                );

                if (tables.length > 0) {
                    // Extraire le titre de la première table (première ligne, colonne Description)
                    let title = `Message ${index + 1}`;

                    const firstTable = tables[0];
                    const firstRow = firstTable.querySelector("tbody tr, tr");
                    if (firstRow) {
                        const descriptionCell = firstRow.querySelector("td:first-child, th:first-child");
                        if (descriptionCell && descriptionCell.textContent.trim()) {
                            title = descriptionCell.textContent.trim().substring(0, 50);
                            if (descriptionCell.textContent.trim().length > 50) {
                                title += "...";
                            }
                        }
                    }

                    messages.push({
                        index,
                        title,
                        messageDiv,
                        tables: Array.from(tables),
                    });
                }
            });

            return messages;
        }

        // Crée un élément d'accordéon avec VRAI accordéon (signe +)
        createAccordionItem(messageData, index) {
            const item = document.createElement("div");
            item.className = "accordion-item";
            item.style.cssText = `
        margin-bottom: 12px;
        border: 1px solid #374151;
        border-radius: 8px;
        overflow: hidden;
        background: #374151;
        transition: all 0.2s ease;
      `;

            const accordionId = `accordion-${index}`;
            const isOpen = this.openAccordions.has(accordionId);

            // En-tête de l'accordéon avec signe +
            const header = document.createElement("div");
            header.className = "accordion-header";
            header.style.cssText = `
        padding: 16px;
        background: #374151;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
        transition: all 0.2s ease;
        user-select: none;
      `;

            header.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
          <span class="accordion-icon" style="
            font-size: 20px;
            font-weight: bold;
            color: #10b981;
            transition: transform 0.3s ease;
            transform: rotate(${isOpen ? '45deg' : '0deg'});
          ">${isOpen ? '✕' : '+'}</span>
          <div style="flex: 1;">
            <div style="font-weight: 600; color: #f9fafb; font-size: 14px;">
              ${messageData.title}
            </div>
            <div style="font-size: 12px; color: #9ca3af; margin-top: 4px;">
              ${messageData.tables.length} table${messageData.tables.length > 1 ? "s" : ""}
            </div>
          </div>
        </div>
      `;

            // Contenu de l'accordéon - AFFICHAGE COMPLET DES TABLES
            const content = document.createElement("div");
            content.className = "accordion-content";
            content.style.cssText = `
        max-height: ${isOpen ? '10000px' : '0'};
        overflow: hidden;
        transition: max-height 0.3s ease;
        background: #1f2937;
      `;

            const contentInner = document.createElement("div");
            contentInner.style.cssText = `
        padding: 16px;
      `;

            // Ajouter les TABLES COMPLÈTES (pas juste les miniatures)
            messageData.tables.forEach((table, tableIndex) => {
                const tableContainer = this.createFullTableDisplay(table, tableIndex, messageData.index);
                contentInner.appendChild(tableContainer);
            });

            content.appendChild(contentInner);

            // Événement de clic sur l'en-tête
            header.addEventListener("click", () => {
                const icon = header.querySelector(".accordion-icon");

                if (this.openAccordions.has(accordionId)) {
                    // Fermer
                    this.openAccordions.delete(accordionId);
                    content.style.maxHeight = "0";
                    icon.style.transform = "rotate(0deg)";
                    icon.textContent = "+";
                    item.style.background = "#374151";
                } else {
                    // Ouvrir
                    this.openAccordions.add(accordionId);
                    content.style.maxHeight = "10000px";
                    icon.style.transform = "rotate(45deg)";
                    icon.textContent = "✕";
                    item.style.background = "#1f2937";
                }
            });

            // Effets hover
            header.addEventListener("mouseenter", () => {
                header.style.background = "#4b5563";
            });
            header.addEventListener("mouseleave", () => {
                header.style.background = "#374151";
            });

            item.appendChild(header);
            item.appendChild(content);

            return item;
        }

        // Crée l'affichage COMPLET d'une table (pas une miniature)
        createFullTableDisplay(table, tableIndex, messageIndex) {
            const container = document.createElement("div");
            container.className = "table-full-display";
            container.style.cssText = `
        margin-bottom: 20px;
        padding: 16px;
        background: #111827;
        border: 1px solid #374151;
        border-radius: 8px;
      `;

            // Titre de la table
            const title = document.createElement("div");
            title.style.cssText = `
        font-weight: 600;
        color: #10b981;
        font-size: 14px;
        margin-bottom: 12px;
        display: flex;
        justify-content: space-between;
        align-items: center;
      `;

            const rows = table.querySelectorAll("tr");
            const rowCount = rows.length;
            const colCount = rows[0] ? rows[0].querySelectorAll("td, th").length : 0;

            title.innerHTML = `
        <span>📊 Table ${tableIndex + 1}</span>
        <span style="font-size: 11px; color: #6b7280; font-weight: normal;">
          ${rowCount} lignes × ${colCount} colonnes
        </span>
      `;

            container.appendChild(title);

            // Cloner la table complète
            const tableClone = table.cloneNode(true);
            tableClone.style.cssText = `
        width: 100%;
        border-collapse: collapse;
        font-size: 12px;
        background: #1f2937;
        border-radius: 6px;
        overflow: hidden;
      `;

            // Styler toutes les cellules
            const allCells = tableClone.querySelectorAll("td, th");
            allCells.forEach(cell => {
                cell.style.cssText = `
          border: 1px solid #374151;
          padding: 8px;
          color: #f9fafb;
          text-align: left;
        `;
            });

            // Styler les en-têtes
            const headers = tableClone.querySelectorAll("th");
            headers.forEach(header => {
                header.style.cssText = `
          border: 1px solid #374151;
          padding: 8px;
          background: #374151;
          color: #10b981;
          font-weight: 600;
          text-align: left;
        `;
            });

            // Wrapper avec scroll si nécessaire
            const tableWrapper = document.createElement("div");
            tableWrapper.style.cssText = `
        overflow-x: auto;
        max-height: 400px;
        overflow-y: auto;
      `;
            tableWrapper.appendChild(tableClone);

            container.appendChild(tableWrapper);

            // Bouton pour faire défiler vers la table originale
            const scrollBtn = document.createElement("button");
            scrollBtn.style.cssText = `
        margin-top: 12px;
        padding: 8px 16px;
        background: #10b981;
        color: white;
        border: none;
        border-radius: 6px;
        cursor: pointer;
        font-size: 12px;
        font-weight: 600;
        transition: all 0.2s ease;
        width: 100%;
      `;
            scrollBtn.textContent = "📍 Aller vers la table dans le chat";

            scrollBtn.addEventListener("mouseenter", () => {
                scrollBtn.style.background = "#059669";
                scrollBtn.style.transform = "translateY(-2px)";
            });
            scrollBtn.addEventListener("mouseleave", () => {
                scrollBtn.style.background = "#10b981";
                scrollBtn.style.transform = "translateY(0)";
            });

            scrollBtn.addEventListener("click", () => {
                this.scrollToTable(table);
            });

            container.appendChild(scrollBtn);

            return container;
        }

        // Fait défiler vers une table spécifique
        scrollToTable(table) {
            if (!table) return;

            // NE PAS fermer le menu - rester sur la page du chat
            // this.hideMenu(); // SUPPRIMÉ

            // Scroll vers la table
            table.scrollIntoView({
                behavior: "smooth",
                block: "center",
            });

            // Effet de surbrillance temporaire
            const originalBorder = table.style.border;
            const originalBoxShadow = table.style.boxShadow;

            table.style.border = "3px solid #10b981";
            table.style.boxShadow = "0 0 20px rgba(16, 185, 129, 0.5)";

            setTimeout(() => {
                table.style.border = originalBorder;
                table.style.boxShadow = originalBoxShadow;
            }, 2000);

            console.log("✅ Défilement vers la table effectué (menu reste ouvert)");
        }

        // Nettoyage
        destroy() {
            if (this.menuElement) {
                this.menuElement.remove();
            }
            this.initialized = false;
            console.log("🗑️ Menu Dossier détruit");
        }
    }

    // Initialisation automatique
    const dossierMenu = new DossierMenuManager();

    // Attendre que le DOM soit prêt
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => {
            dossierMenu.init();
        });
    } else {
        dossierMenu.init();
    }

    // Exposer globalement pour debug
    window.dossierMenu = dossierMenu;
})();
