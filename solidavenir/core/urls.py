from django.urls import path
from . import views

urlpatterns = [
    # -------------------------
    # Public / general pages
    # -------------------------
    path('', views.accueil, name='accueil'),  # Home page
    path('about/', views.about, name='about'),  # About page
    path('contact/', views.contact, name='contact'),  # Contact page
    path('savoir_plus/', views.savoir_plus, name='savoir_plus'),  # Learn more
    path('transparence/', views.transparence, name='transparence'),  # Transparency info
    path('inscription/', views.inscription, name='inscription'),  # User registration
    path('connexion/', views.connexion, name='connexion'),  # Login
    path('deconnexion/', views.deconnexion, name='deconnexion'),  # Logout
    path('project-policy/', views.policy_view, name='project_policy'),

    # -------------------------
    # User profile
    # -------------------------
    path('profil/', views.profil, name='profil'),  # User profile view
    path('profil/modifier/', views.modifier_profil, name='modifier_profil'),  # Edit profile
    path('profil/mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),  # Change password

    # -------------------------
    # Dashboard / Transactions
    # -------------------------
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),  # Dashboard
    path('mes-dons/', views.mes_dons, name='mes_dons'),  # My donations
    path('mes-dons-recus/', views.dons_recus, name='dons_recus'),  # Received donations
    path('transactions/validation/', views.liste_transactions_validation, name='liste_transactions_validation'),  # Transactions to validate
    path('valider/<uuid:audit_uuid>/', views.valider_projet, name='valider_projet'),  # Validate project
    path('donation/<int:project_id>/process/', views.process_donation, name='process_donation'),  # Process donation

    # -------------------------
    # Projects
    # -------------------------
    path('projets/', views.liste_projets, name='liste_projets'),  # List all projects
    path('mes-projets/', views.mes_projets, name='mes_projets'),  # My projects
    path('projet/creer/', views.creer_projet, name='creer_projet'),  # Create project
    path('projet/<uuid:audit_uuid>/', views.detail_projet, name='detail_projet'),  # Project details
    path('projet/<uuid:uuid>/modifier/', views.modifier_projet, name='modifier_projet'),  # Edit project
    path('projet/<uuid:uuid>/supprimer/', views.supprimer_projet, name='supprimer_projet'),  # Delete project
    path('utilisateur/<int:user_id>/projets/', views.projets_utilisateur, name='projets_utilisateur'),  # Projects by user

    # -------------------------
    # Project media / images
    # -------------------------
    path('projet/<uuid:uuid>/ajouter-images/', views.ajouter_images_projet, name='ajouter_images_projet'),  # Add images to project
    path('<slug:slug>/galerie/upload/', views.upload_association_image, name='upload_association_image'),  # Upload images for association
    path('<slug:slug>/galerie/', views.association_images_list, name='association_images_list'),  # View association gallery

    # -------------------------
    # Project milestones / palier
    # -------------------------
    path('projet/<int:projet_id>/paliers/', views.gerer_paliers, name='gerer_paliers'),  # Manage project milestones
    path('projet/<int:projet_id>/paliers/ajouter/', views.ajouter_palier, name='ajouter_palier'),  # Add milestone
    path('palier/<int:palier_id>/modifier/', views.modifier_palier, name='modifier_palier'),  # Edit milestone
    path('palier/<int:palier_id>/supprimer/', views.supprimer_palier, name='supprimer_palier'),  # Delete milestone
    path('projet/palier/<int:palier_id>/soumettre-preuves/', views.soumettre_preuves_palier, name='soumettre_preuves_palier'),  # Submit proofs
    path('palier/<int:palier_id>/verifier-preuves/', views.verifier_preuves_palier, name='verifier_preuves_palier'),  # Verify proofs

    # -------------------------
    # Associations
    # -------------------------
    path('associations/', views.liste_associations, name='liste_associations'),  # List all associations
    path('association/<slug:slug>/', views.detail_association, name='detail_association'),  # Association details
    path('espace-association/', views.espace_association, name='espace_association'),  # Association dashboard
    path('espace-association/modifier/', views.modifier_profil_association, name='modifier_profil_association'),  # Edit association profile
    path('transfer-direct/', views.transfer_direct_association, name='transfer_direct'),  # Direct transfer to association

    # -------------------------
    # Wallet
    # -------------------------
    path('configurer_wallet/', views.configurer_wallet, name='configurer_wallet'),  # Configure wallet
    path('wallet/', views.voir_wallet, name='voir_wallet'),  # View wallet

    # -------------------------
    # Email / messaging
    # -------------------------
    path('envoyer-email/', views.envoyer_email_view, name='envoyer_email'),  # Send email
    path('liste-emails/', views.liste_emails_view, name='liste_emails'),  # Email list

    # -------------------------
    # Members
    # -------------------------
    path('membres/', views.liste_membres, name='liste_membres'),  # List members
    path('membres/<int:user_id>/', views.detail_membre, name='detail_membre'),  # Member details

    # -------------------------
    # Administration / Admin
    # -------------------------
    path('associations_admin/', views.liste_associations_admin, name='liste_associations_admin'),  # Admin: list associations
    path('projets_admin/', views.liste_projets_admin, name='liste_projets_admin'),
    path('projets/en-attente/', views.liste_projets_attente, name='projets_attente'),  # Pending projects
    path('association/<int:association_id>/preview/', views.preview_association_admin, name='preview_association_admin'),  # Preview association (admin)
    path('association/<int:association_id>/valider/', views.valider_association, name='valider_association'),  # Validate association
    path('association/<int:association_id>/rejeter/', views.rejeter_association, name='rejeter_association'),  # Reject association
    path('gerer_distributions/', views.gerer_distributions, name='gerer_distributions'),  # Manage distributions
    path('logs_distributions/', views.logs_distributions, name='logs_distributions'),  # Distribution logs
    path('logs-audit/', views.logs_audit, name='logs_audit'),  # Audit logs

    # -------------------------
    # Utility
    # -------------------------
    path('clear-session-messages/', views.clear_session_messages, name='clear_session_messages'),  # Clear flash messages
]
