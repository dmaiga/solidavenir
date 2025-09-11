#!/bin/bash

# Chemin du dossier templates
TEMPLATES_DIR="templates/core"

# Créer le dossier s'il n'existe pas
mkdir -p $TEMPLATES_DIR

# Liste des templates à créer
TEMPLATES=(
    "accueil.html"
    "liste_projets.html"
    "detail_projet.html"
    "confirmation_don.html"
    "inscription.html"
    "contact.html"
    "creer_projet.html"
    "mes_projets.html"
    "mes_dons.html"
    "valider_projet.html"
    "tableau_de_bord.html"
    "modifier_profil.html"
    "transparence.html"
)

# Création des fichiers
for template in "${TEMPLATES[@]}"; do
    touch "$TEMPLATES_DIR/$template"
    echo "Créé: $TEMPLATES_DIR/$template"
done

echo "Tous les templates ont été créés avec succès !"
