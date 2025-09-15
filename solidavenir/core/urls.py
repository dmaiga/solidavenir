from django.urls import path
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('profil/', views.profil, name='profil'),
    path('projets/', views.liste_projets, name='liste_projets'),
    path('inscription/', views.inscription, name='inscription'),
    path('mes-dons/', views.mes_dons, name='mes_dons'),
    path('transparence/', views.transparence, name='transparence'),
    path('contact/', views.contact, name='contact'),
    path('about/', views.about, name='about'),
    path('savoir_plus/', views.savoir_plus, name='savoir_plus'),

   path('projet/creer/', views.creer_projet, name='creer_projet'),
   path('mes-projets/', views.mes_projets, name='mes_projets'),
   path('projet/<uuid:audit_uuid>/', views.detail_projet, name='detail_projet'),
   path('configurer_wallet/', views.configurer_wallet, name='configurer_wallet'),
   path('projet/<uuid:uuid>/modifier/', views.modifier_projet, name='modifier_projet'),
   path('projet/<uuid:uuid>/supprimer/', views.supprimer_projet, name='supprimer_projet'),
   path('utilisateur/<int:user_id>/projets/', views.projets_utilisateur, name='projets_utilisateur'),

    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
   
    path('profil/modifier/', views.modifier_profil, name='modifier_profil'),
    path('profil/mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),

 path('envoyer-email/', views.envoyer_email_view, name='envoyer_email'),
    path('liste-emails/', views.liste_emails_view, name='liste_emails'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),
    path('transactions/validation/', views.liste_transactions_validation, name='liste_transactions_validation'),
    path('valider/<uuid:audit_uuid>/', views.valider_projet, name='valider_projet'),
    path('membres/', views.liste_membres, name='liste_membres'),
    path('membres/<int:user_id>/', views.detail_membre, name='detail_membre'),
    path('logs-audit/', views.logs_audit, name='logs_audit'),

    path('associations/', views.liste_associations, name='liste_associations'),
    path('association/<slug:slug>/', views.detail_association, name='detail_association'),
    path('espace-association/', views.espace_association, name='espace_association'),
    path('espace-association/modifier/', views.modifier_profil_association, name='modifier_profil_association'),
    # URLs administration
    path('associations_admin/', views.liste_associations_admin, name='liste_associations_admin'),
    path('projets/en-attente/', views.liste_projets_attente, name='projets_attente'),
    path('association/<int:association_id>/preview/', views.preview_association_admin, name='preview_association_admin'),
    path('association/<int:association_id>/valider/', views.valider_association, name='valider_association'),
    path('association/<int:association_id>/rejeter/', views.rejeter_association, name='rejeter_association'),

    path('envoyer-email/', views.envoyer_email_view, name='envoyer_email'),
    path('liste-emails/', views.liste_emails_view, name='liste_emails'),

]