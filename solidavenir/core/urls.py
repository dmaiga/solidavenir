from django.urls import path
from . import views

urlpatterns = [
    path('', views.accueil, name='accueil'),
    path('profil/', views.profil, name='profil'),
    path('projets/', views.liste_projets, name='liste_projets'),
    path('projet/<uuid:audit_uuid>/', views.detail_projet, name='detail_projet'),
    path('don/confirmation/<uuid:transaction_audit_uuid>/', views.confirmation_don, name='confirmation_don'),
    path('inscription/', views.inscription, name='inscription'),
    path('projet/creer/', views.creer_projet, name='creer_projet'),
    path('mes-projets/', views.mes_projets, name='mes_projets'),
    path('mes-dons/', views.mes_dons, name='mes_dons'),

    path('transparence/', views.transparence, name='transparence'),
    path('projet/valider/<uuid:audit_uuid>/', views.valider_projet, name='valider_projet'),
    path('contact/', views.contact, name='contact'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.deconnexion, name='deconnexion'),
    path('profil/hedera/', views.configurer_hedera, name='configurer_hedera'),
    path('profil/hedera/creer/', views.creer_compte_hedera, name='creer_compte_hedera'),
    path('profil/hedera/existant/', views.configurer_compte_existant, name='configurer_compte_existant'),
    path('profil/modifier/', views.modifier_profil, name='modifier_profil'),
    path('profil/mot-de-passe/', views.changer_mot_de_passe, name='changer_mot_de_passe'),

]