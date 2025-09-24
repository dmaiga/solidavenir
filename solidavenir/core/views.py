# Standard library
import os
import json
import logging
import requests
from mimetypes import MimeTypes
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlencode

# Django imports
from django.conf import settings
from django.contrib import messages
from django.db import transaction 
from django.contrib.auth import (
    login, authenticate, logout, update_session_auth_hash
)
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.mixins import PermissionRequiredMixin
from django.contrib.humanize.templatetags.humanize import intcomma
from django.core.cache import cache
from django.core.mail import send_mail, EmailMessage
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction as db_transaction
from django.db.models import (
    Sum, Count, Q, Avg, Max, Min, F, DecimalField, Prefetch
)
from django.db.models.functions import Coalesce, TruncMonth
from django.http import (
    JsonResponse, HttpResponseForbidden, HttpResponseRedirect
)
from django.shortcuts import (
    render, redirect, get_object_or_404
)
from django.urls import reverse
from django.utils import timezone
from django.utils.http import urlencode
from django.views.decorators.csrf import csrf_protect, csrf_exempt

# Local apps imports
from .models import (
    Projet, Transaction, User, AuditLog, Association,
    Palier, PreuvePalier, FichierPreuve, EmailLog, TransactionAdmin
)
from .forms import (
    InscriptionFormSimplifiee, CreationProjetForm, ValidationProjetForm,
    ProfilUtilisateurForm, ContactForm, Transfer_fond, AssociationForm,
    FiltreMembresForm, FiltreTransactionsForm, FiltreAuditForm,
    EmailFormSimple, PreuveForm, VerificationPreuveForm
)

logger = logging.getLogger(__name__)

#
#   SITE
#
def accueil(request):
    """Page d'accueil avec projets populaires et statistiques"""
    """Homepage with popular projects and statistics"""
    # Récupérer les projets actifs les plus populaires
    # Get the most popular active projects
    projets_populaires = Projet.objects.filter(
        statut='actif'
    ).annotate(
        total_collecte=Sum('transaction__montant', filter=Q(transaction__statut='confirme'))
    ).order_by('-total_collecte')[:3]
    
    # Statistiques globales
    # Global statistics
    projets_total = Projet.objects.filter(statut='termine').count()
    donateurs_total = User.objects.filter(user_type='donateur').count()
    dons_total = Transaction.objects.filter(
        statut='confirme'
    ).aggregate(total=Sum('montant'))['total'] or 0
    
    context = {
        'projets_populaires': projets_populaires,
        'projets_total': projets_total,
        'donateurs_total': donateurs_total,
        'dons_total': int(dons_total) if dons_total else 0,
    }
    
    return render(request, 'core/site/accueil.html', context)

def about(request):
    """Page À propos"""
    """About page"""
    return render(request, 'core/site/about.html')

def savoir_plus(request):
    """Page En savoir plus"""
    """Learn more page"""
    return render(request, 'core/site/savoir_plus.html')

def contact(request):
    """Page de contact"""
    """Contact page"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Créer l'instance du modèle mais ne pas sauvegarder tout de suite
            # Create the model instance but don't save immediately
            submission = form.save(commit=False)
            # Vous pouvez ajouter des informations supplémentaires ici si nécessaire
            # You can add additional information here if needed
            submission.save()  # Sauvegarder dans la base de données
                     # Save to the database
            
            # Ici vous pourriez également envoyer un email
            # Here you could also send an email
            messages.success(request, "Votre message a été envoyé avec succès!")
            return redirect('contact')
    else:
        form = ContactForm()
    
    return render(request, 'core/site/contact.html', {'form': form})
from django.db.models import Sum, Count, Avg
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.db.models.functions import TruncMonth
from datetime import timedelta
from django.utils import timezone

def transparence(request):
    projet_filter = request.GET.get('projet')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    # --- Transactions classiques (dons) ---
    transactions = Transaction.objects.filter(statut='confirme').select_related(
        'projet', 'contributeur', 'verifie_par'
    )

    # --- Transactions administratives (distributions + commissions) ---
    transactions_admin = TransactionAdmin.objects.select_related(
        'projet', 'beneficiaire', 'initiateur'
    )

    # --- Filtres ---
    if projet_filter:
        transactions = transactions.filter(projet__audit_uuid=projet_filter)
        transactions_admin = transactions_admin.filter(projet__audit_uuid=projet_filter)

    if date_debut:
        try:
            date_debut_dt = timezone.datetime.strptime(date_debut, '%Y-%m-%d').date()
            transactions = transactions.filter(date_transaction__date__gte=date_debut_dt)
            transactions_admin = transactions_admin.filter(date_creation__date__gte=date_debut_dt)
        except ValueError:
            pass

    if date_fin:
        try:
            date_fin_dt = timezone.datetime.strptime(date_fin, '%Y-%m-%d').date()
            transactions = transactions.filter(date_transaction__date__lte=date_fin_dt)
            transactions_admin = transactions_admin.filter(date_creation__date__lte=date_fin_dt)
        except ValueError:
            pass

    # --- Statistiques ---
    stats = {
        'total_dons': transactions.aggregate(total=Sum('montant'))['total'] or 0,
        'total_transactions': transactions.count(),
        'total_distributions': transactions_admin.aggregate(total=Sum('montant_net'))['total'] or 0,
        'total_commissions': transactions_admin.filter(type_transaction='commission').aggregate(total=Sum('commission'))['total'] or 0,
        'projets_finances': transactions.values('projet').distinct().count(),
        'donateurs_uniques': transactions.values('contributeur').distinct().count(),
        'moyenne_don': transactions.aggregate(moyenne=Avg('montant'))['moyenne'] or 0,
    }

    # --- Top projets et donateurs ---
    top_projets = Projet.objects.filter(transaction__statut='confirme').annotate(
        total_collecte=Sum('transaction__montant'),
        nombre_dons=Count('transaction')
    ).order_by('-total_collecte')[:5]

    top_donateurs = User.objects.filter(transaction__statut='confirme').annotate(
        total_dons=Sum('transaction__montant'),
        nombre_dons=Count('transaction')
    ).order_by('-total_dons')[:5]

    # --- Évolution mensuelle des dons ---
    donations_mensuelles = Transaction.objects.filter(
        statut='confirme',
        date_transaction__gte=timezone.now() - timedelta(days=365)
    ).annotate(
        mois=TruncMonth('date_transaction')
    ).values('mois').annotate(
        total=Sum('montant'),
        count=Count('id')
    ).order_by('-mois')

    # --- Projets actifs pour filtres ---
    projets_actifs = Projet.objects.filter(statut='actif').values('audit_uuid', 'titre')

    # --- Transactions classiques (dons) ---
    transactions = (
        Transaction.objects.filter(statut='confirme')
        .select_related('projet', 'contributeur', 'verifie_par')
        .order_by('-date_transaction')   # ✅ trié avant la pagination
    )

    # --- Transactions administratives ---
    transactions_admin = (
        TransactionAdmin.objects
        .select_related('projet', 'beneficiaire', 'initiateur')
        .order_by('-date_creation')  # ✅ dernier en haut
    )


    # --- Pagination (dons uniquement) ---
    paginator = Paginator(transactions, 25)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    
    context = {
        'transactions': page_obj,
        'transactions_admin': transactions_admin,  # ✅ Toutes les infos admin y compris HCS
        'stats': stats,
        'top_projets': top_projets,
        'top_donateurs': top_donateurs,
        'donations_mensuelles': list(donations_mensuelles),
        'projets_actifs': projets_actifs,
        'filters': {
            'projet': projet_filter,
            'date_debut': date_debut,
            'date_fin': date_fin,
        }
    }

    return render(request, 'core/site/transparence.html', context)


@login_required
def mes_dons(request):
    """Historique des contributions de l'utilisateur connecté"""
    
    # Contributions de l'utilisateur
    contributions = Transaction.objects.filter(contributeur=request.user).select_related('projet').order_by('-date_transaction')
    total_contributions = sum(contrib.montant for contrib in contributions)
    
    # Statistiques par projet
    projets_stats = Transaction.objects.filter(
        contributeur=request.user, 
        statut='confirme'
    ).values(
        'projet__titre'
    ).annotate(
        total=Sum('montant')
    ).order_by('-total')
    
    # Contributions mensuelles (6 derniers mois) - Compatible SQLite
    six_mois = timezone.now() - timedelta(days=180)
    contributions_mensuelles = Transaction.objects.filter(
        contributeur=request.user,
        statut='confirme',
        date_transaction__gte=six_mois
    ).annotate(
        mois=TruncMonth('date_transaction')
    ).values('mois').annotate(
        total=Sum('montant')
    ).order_by('mois')
    
    context = {
        'contributions': contributions,
        'total_contributions': total_contributions,
        'projets_count': projets_stats.count(),
        'projets_stats': projets_stats,
        'contributions_mensuelles': contributions_mensuelles
    }
    
    return render(request, 'core/site/mes_dons.html', context)

#===========
# END SITE
#===========
#-----------------------------------
#users
#===================================
def inscription(request):
    """Inscription simplifiée pour le MVP avec formulaire allégé"""
    # Rediriger les utilisateurs déjà connectés
    if request.user.is_authenticated:
        messages.info(request, "Vous êtes déjà connecté.")
        return redirect('accueil')
    
    if request.method == 'POST':
        form = InscriptionFormSimplifiee(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                
                # Connexion automatique
                login(request, user)
                
                # Message de bienvenue personnalisé selon le type d'utilisateur
                user_type_display = dict(User.USER_TYPES).get(user.user_type, 'utilisateur')
                messages.success(
                    request, 
                    f"Bienvenue {user.get_full_name_or_username()} ! "
                    f"Votre compte {user_type_display.lower()} a été créé avec succès."
                )
                
                # Redirection selon le type d'utilisateur
                if user.user_type == 'association':
                    return redirect('espace_association')
                else:
                    return redirect('accueil')
                
            except Exception as e:
                messages.error(
                    request, 
                    "Une erreur s'est produite lors de la création du compte. "
                    "Veuillez réessayer ou nous contacter si le problème persiste."
                )
                logger.error(f"Erreur inscription: {str(e)}")
                logger.exception("Détails de l'erreur d'inscription:")
        else:
            # Afficher les erreurs de manière conviviale
            for field, errors in form.errors.items():
                field_label = form.fields[field].label if field in form.fields else field.replace('_', ' ').title()
                for error in errors:
                    messages.error(request, f"{field_label}: {error}")
    else:
        form = InscriptionFormSimplifiee()
    
    # Types d'utilisateurs sans admin
    user_types_without_admin = [choice for choice in User.USER_TYPES if choice[0] != 'admin']
    
    context = {
        'form': form,
        'user_types': user_types_without_admin,
        'title': 'Rejoignez notre communauté solidaire',
        'description': 'Une plateforme transparente pour financer des projets qui changent le monde'
    }
    
    return render(request, 'core/users/inscription.html', context)
from django.contrib.auth import get_user_model

@csrf_protect
def connexion(request):
    """Page de connexion"""
    if request.user.is_authenticated:
        if request.user.user_type == 'admin':
            return redirect('tableau_de_bord')
        return redirect('accueil')
    
    if request.method == 'POST':
        login_input = request.POST.get('username')  # peut être email ou username
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')

        User = get_user_model()
        user = None

        # 🔹 Cherche par username
        try:
            user_obj = User.objects.get(username=login_input)
            user = authenticate(request, username=user_obj.username, password=password)
        except User.DoesNotExist:
            # 🔹 Cherche par email si username non trouvé
            try:
                user_obj = User.objects.get(email=login_input)
                user = authenticate(request, username=user_obj.username, password=password)
            except User.DoesNotExist:
                user = None

        if user is not None:
            login(request, user)
            
            # Audit log
            AuditLog.objects.create(
                utilisateur=user,
                action='login',
                modele='User',
                objet_id=str(user.audit_uuid),
                details={'method': 'form', 'remember_me': bool(remember_me)},
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            # Gestion "remember me"
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 jours
            
            # Redirection
            if user.user_type == 'admin':
                return redirect('tableau_de_bord')
            
            next_url = request.GET.get('next')
            if next_url:
                return redirect(next_url)
            
            return redirect('accueil')
        else:
            messages.error(request, "Identifiant ou mot de passe incorrect.")
    
    return render(request, 'core/users/connexion.html')

@login_required
def deconnexion(request):
    """Déconnexion de l'utilisateur"""
    # Journalisation avant déconnexion
    AuditLog.objects.create(
        utilisateur=request.user,
        action='logout',
        modele='User',
        objet_id=str(request.user.audit_uuid),
        details={},
        adresse_ip=request.META.get('REMOTE_ADDR')
    )
    
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('accueil')

@login_required
def changer_mot_de_passe(request):
    """Changer le mot de passe de l'utilisateur"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Garder l'utilisateur connecté
            
            # Journalisation audit
            AuditLog.objects.create(
                utilisateur=request.user,
                action='update',
                modele='User',
                objet_id=str(request.user.audit_uuid),
                details={'action': 'password_change'},
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, "Votre mot de passe a été changé avec succès.")
            return redirect('accueil')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'core/users/changer_mot_de_passe.html', {'form': form})


@login_required
def modifier_profil(request):
    """Modification du profil utilisateur avec support de la photo de profil"""
    if request.method == 'POST':
        form = ProfilUtilisateurForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save()
            
            # Journalisation audit
            AuditLog.objects.create(
                utilisateur=request.user,
                action='update',
                modele='User',
                objet_id=str(request.user.audit_uuid),
                details={
                    'champs_modifies': list(form.changed_data),
                    'type_utilisateur': user.user_type
                },
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('modifier_profil')
    else:
        form = ProfilUtilisateurForm(instance=request.user)
    
    context = {
        'form': form,
        'profile_completion': request.user.get_profile_completion()
    }
    
    return render(request, 'core/users/modifier_profil.html', context)


@login_required
def profil(request):
    """Page de profil utilisateur"""
    
    # Récupérer le solde Hedera si le wallet est configuré
    solde = None
    if request.user.hedera_account_id:
        try:
            response = requests.get(
                f'http://hedera_service:3001/balance/{request.user.hedera_account_id}',
                timeout=5
            )
            if response.status_code == 200:
                solde = response.json().get('balance')
        except Exception as e:
            print(f"Erreur récupération solde: {e}")

    context = {'user': request.user,
               'solde': solde
               }

    # Statistiques pour les donateurs
    if request.user.user_type == 'contributeur':
        dons = Transaction.objects.filter(
            donateur=request.user, 
            statut='confirme'
        )
        context['dons_count'] = dons.count()
        context['projets_soutenus_count'] = dons.values('projet').distinct().count()
    
    # Statistiques pour les porteurs de projet
    elif request.user.user_type == 'porteur':
        projets = Projet.objects.filter(porteur=request.user)
        context['projets_count'] = projets.count()
        context['total_collecte'] = projets.aggregate(
            total=Sum('montant_collecte')
        )['total'] or 0

    # Activités récentes (30 derniers jours)
    activites_recentes = AuditLog.objects.filter(
        utilisateur=request.user,
        date_action__gte=timezone.now() - timedelta(days=30)
    ).order_by('-date_action')[:10]
    
    context['activites_recentes'] = activites_recentes
    
    return render(request, 'core/users/profil.html', context)


#===================
# END SITE
#===================

#===================
# ASSOCIATION
#===================


def liste_associations(request):
    """Liste toutes les associations avec filtres"""
    associations = Association.objects.filter(valide=True)
    
    # Filtres
    domaine = request.GET.get('domaine')
    ville = request.GET.get('ville')
    recherche = request.GET.get('recherche')
    
    if domaine:
        associations = associations.filter(domaine_principal=domaine)
    if ville:
        associations = associations.filter(ville__icontains=ville)
    if recherche:
        associations = associations.filter(
            Q(nom__icontains=recherche) |
            Q(description_courte__icontains=recherche) |
            Q(causes_defendues__icontains=recherche)
        )
    
    # Statistiques
    total_adherents = associations.aggregate(Sum('nombre_adherents'))['nombre_adherents__sum'] or 0
    total_projets = sum(assoc.get_projets_actifs().count() for assoc in associations)
    total_villes = associations.values('ville').distinct().count()
    
    # Mettre en avant les associations featured
    featured = associations.filter(featured=True)
    autres = associations.filter(featured=False)
    
    context = {
        'featured_associations': featured,
        'autres_associations': autres,
        'domaines': Association.DOMAINES_ACTION,
        'total_adherents': total_adherents,
        'total_projets': total_projets,
        'total_villes': total_villes,
        'has_filters': any([domaine, ville, recherche])
    }
    return render(request, 'core/associations/liste_associations.html', context)

def detail_association(request, slug):
    """Détail d'une association"""
    association = get_object_or_404(Association, slug=slug, valide=True)
    
    context = {
        'association': association,
        'projets_actifs': association.get_projets_actifs(),
    }
    return render(request, 'core/associations/detail_association.html', context)


@login_required
def modifier_profil_association(request):
    """Modifier le profil de l'association"""
    if not request.user.is_association():
        messages.error(request, "Accès réservé aux associations.")
        return redirect('accueil')
    
    association = get_object_or_404(Association, user=request.user)
    
    if request.method == 'POST':
        form = AssociationForm(request.POST, request.FILES, instance=association)
        if form.is_valid():
            form.save()
            messages.success(request, "Profil mis à jour avec succès !")
            return redirect('espace_association')
    else:
        form = AssociationForm(instance=association)
    
    context = {
        'form': form,
        'association': association,
    }
    return render(request, 'core/associations/modifier_profil.html', context)
@login_required
def espace_association(request):
    """Espace personnel pour les associations"""
    if not request.user.is_association():
        messages.error(request, "Accès réservé aux associations.")
        return redirect('accueil')
    
    try:
        association = request.user.association_profile
    except Association.DoesNotExist:
        # Créer le profil si il n'existe pas
        association = Association.objects.create(
            user=request.user,
            nom=request.user.nom_association or f"Association {request.user.username}",
            domaine_principal='autre',
            causes_defendues="Causes à définir",
            statut_juridique='association',
            adresse_siege=request.user.adresse or "Adresse à compléter",
            ville=request.user.ville or "Ville à compléter",
            code_postal=request.user.code_postal or "00000",
            telephone=request.user.telephone or "0000000000",
            email_contact=request.user.email,
            date_creation=timezone.now().date()
        )
    
    # Récupérer les projets de l'association
    projets_association = association.projets.all()
    
    # Statistiques de l'association
    stats = {
        'projets_actifs': association.get_projets_actifs().count(),
        'projets_total': projets_association.count(),
        'montant_total': association.get_total_collecte(),
        'contributeurs_total': association.get_nombre_contributeurs(),
    }
    
    # Projets récents (5 derniers)
    projets_recents = projets_association.order_by('-date_creation')[:5]
    
    context = {
        'association': association,
        'stats': stats,
        'projets_recents': projets_recents,
    }
    return render(request, 'core/associations/espace_association.html', context)



#===================
# END ASSOCIATION
#===================

#===================
# PROJETS
#===================

@login_required
def creer_projet(request):
    """Création d'un nouveau projet avec description des récompenses"""

    est_association = hasattr(request.user, 'association_profile')
    association = getattr(request.user, 'association_profile', None)

    if request.method == 'POST':
        form = CreationProjetForm(request.POST, request.FILES, porteur=request.user)

        if form.is_valid():
            try:
                with transaction.atomic():
                    projet = form.save(commit=False)

                    # Lier l'association si applicable
                    if est_association and association:
                        projet.association = association

                    # 🔑 Création du wallet Hedera pour ce projet
                    try:
                        
                        response = requests.post("http://hedera_service:3001/create-wallet", timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            projet.hedera_account_id = data.get("accountId")
                            projet.hedera_private_key = data.get("privateKey")
                        else:
                            raise Exception("Échec de création wallet Hedera")
                    except Exception as e:
                        logger.error(f"Erreur wallet Hedera: {str(e)}")
                        messages.error(request, "Le projet a été créé mais sans compte Hedera.")
                    # 🔑 Génération de l'identifiant unique incluant le porteur
                    projet.save()
                    projet.identifiant_unique = f"SOLID{projet.id:06d}-{request.user.id}-{timezone.now().strftime('%Y%m%d')}"
                    projet.save(update_fields=['identifiant_unique'])
                    for pct in [40, 30, 30]:
                        Palier.objects.create(projet=projet, pourcentage=pct)
                     # Journalisation complète
                    AuditLog.objects.create(
                        utilisateur=request.user,
                        action='create',
                        modele='Projet',
                        objet_id=str(projet.audit_uuid),
                        details={
                            'titre': projet.titre,
                            'montant': float(projet.montant_demande),
                            'statut': projet.statut,
                            'wallet': projet.hedera_account_id,
                            'porteur_id': request.user.id,
                            'porteur_nom': request.user.get_full_name(),
                            'association': str(projet.association.id) if projet.association else None,
                        },
                        adresse_ip=request.META.get('REMOTE_ADDR')
                    )


                messages.success(
                    request,
                    "Votre projet a été créé avec succès avec un compte Hedera dédié !"
                )
                return redirect('mes_projets')

            except Exception as e:
                logger.error(f"Erreur création projet: {str(e)}", exc_info=True)
                messages.error(request, "Une erreur est survenue lors de la création du projet. Veuillez réessayer.")
    else:
        form = CreationProjetForm(porteur=request.user)

    context = {
        'form': form,
        'est_association': est_association,
        'association': association
    }
    return render(request, 'core/projets/creer_projet.html', context)


@login_required
def modifier_projet(request, uuid):
    """Modification d'un projet existant avec description des récompenses"""
    try:
        projet = Projet.objects.get(audit_uuid=uuid, porteur=request.user)
        
        if not projet.peut_etre_modifie_par(request.user):
            messages.error(request, "Ce projet ne peut plus être modifié.")
            return redirect('detail_projet', uuid=uuid)
        
        if request.method == 'POST':
            form = CreationProjetForm(request.POST, request.FILES, instance=projet, porteur=request.user)
            
            if form.is_valid():
                try:
                    with transaction.atomic():
                        projet_modifie = form.save()
                        
                        # Journalisation
                        AuditLog.objects.create(
                            utilisateur=request.user,
                            action='update',
                            modele='Projet',
                            objet_id=str(projet.audit_uuid),
                            details={
                                'modifications': 'Mise à jour du projet', 
                                'has_recompenses': projet_modifie.has_recompenses,
                                'recompenses_description': projet_modifie.recompenses_description
                            },
                            adresse_ip=request.META.get('REMOTE_ADDR')
                        )

                    messages.success(request, "Votre projet a été modifié avec succès !")
                    return redirect('detail_projet', uuid=uuid)

                except Exception as e:
                    logger.error(f"Erreur modification projet: {str(e)}", exc_info=True)
                    messages.error(request, "Une erreur est survenue lors de la modification.")
        
        else:
            form = CreationProjetForm(instance=projet, porteur=request.user)

        context = {
            'form': form,
            'projet': projet,
            'action': 'modifier'
        }
        
        return render(request, 'core/projets/creer_projet.html', context)
        
    except Projet.DoesNotExist:
        messages.error(request, "Projet non trouvé.")
        return redirect('mes_projets')


@login_required
def supprimer_projet(request, uuid):
    """Suppression d'un projet"""
    try:
        projet = Projet.objects.get(audit_uuid=uuid, porteur=request.user)
        
        # Vérifier que le projet peut être supprimé (seulement brouillon ou rejeté)
        if projet.statut not in ['brouillon', 'rejete']:
            messages.error(
                request, 
                "Seuls les projets en brouillon ou rejetés peuvent être supprimés."
            )
            return redirect('detail_projet', uuid=uuid)
        
        if request.method == 'POST':
            try:
                # Journalisation avant suppression
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='delete',
                    modele='Projet',
                    objet_id=str(projet.audit_uuid),
                    details={
                        'titre': projet.titre,
                        'statut': projet.statut,
                        'montant': float(projet.montant_demande)
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )
                
                projet.delete()
                messages.success(request, "Votre projet a été supprimé avec succès!")
                return redirect('mes_projets')
                
            except Exception as e:
                logger.error(f"Erreur suppression projet: {str(e)}", exc_info=True)
                messages.error(request, "Une erreur est survenue lors de la suppression.")
                return redirect('detail_projet', uuid=uuid)
        
        # GET request - afficher la confirmation
        return render(request, 'core/projets/supprimer_projet.html', {'projet': projet})
        
    except Projet.DoesNotExist:
        messages.error(request, "Projet non trouvé.")
        return redirect('mes_projets')


def detail_projet(request, audit_uuid):
    """Détail d'un projet spécifique avec possibilité de contribution"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    # 🔍 Incrémenter le compteur de vues
    projet.incrementer_vues()
    
    # 📊 Statistiques avancées
    stats_transactions = Transaction.objects.filter(
        projet=projet, 
        statut='confirme',
        destination='operator'
    ).aggregate(
        total_contributeurs=Count('contributeur', distinct=True),
        montant_total=Sum('montant'),
        don_moyen=Avg('montant'),
        don_max=Max('montant'),
        dernier_don=Max('date_transaction')
    )
    
    contributeurs_count = stats_transactions['total_contributeurs'] or 0
    montant_total_collecte = stats_transactions['montant_total'] or 0
    
    # 📈 Paliers avec statut
    paliers_avec_statut = []
    for palier in projet.paliers.all().order_by('pourcentage'):
        try:
            preuve = PreuvePalier.objects.get(palier=palier)
            statut_preuve = preuve.statut
            date_soumission = preuve.date_soumission
        except PreuvePalier.DoesNotExist:
            statut_preuve = 'non_soumis'
            date_soumission = None
            
        paliers_avec_statut.append({
            'palier': palier,
            'statut_preuve': statut_preuve,
            'date_soumission': date_soumission,
            'distribue': palier.transfere,
            'montant_fcfa': palier.montant_fcfa if hasattr(palier, 'montant_fcfa') else Decimal('0')
        })
    
    # 💰 Conversions de devise
    try:
        from .models import convert_hbar_to_fcfa
        conversions = {
            'hbar_to_fcfa_rate': Decimal('0.07') * Decimal('600'),  # Taux simplifié
            'montant_demande_fcfa': projet.montant_demande_fcfa,
            'montant_engage_fcfa': projet.montant_engage_fcfa,
            'montant_restant_fcfa': projet.montant_restant_fcfa,
            'montant_distribue_fcfa': projet.montant_distribue_fcfa,
        }
    except Exception as e:
        logger.error(f"Erreur conversion devise: {e}")
        conversions = {
            'hbar_to_fcfa_rate': Decimal('42'),
            'montant_demande_fcfa': Decimal('0'),
            'montant_engage_fcfa': Decimal('0'),
            'montant_restant_fcfa': Decimal('0'),
            'montant_distribue_fcfa': Decimal('0'),
        }
    
    # 👥 Vérification des permissions de visualisation
    user_can_preview = (
        request.user == projet.porteur or
        request.user.is_staff or
        (hasattr(request.user, 'association_profile') and 
         request.user.association_profile == projet.association)
    )
    
    if projet.statut not in ['actif', 'termine'] and not user_can_preview:
        messages.error(request, "Ce projet n'est pas accessible.")
        return redirect('liste_projets')
    
    # 🔍 Projets similaires
    projets_similaires = Projet.objects.filter(
        statut='actif',
        categorie=projet.categorie
    ).exclude(audit_uuid=audit_uuid).order_by('?')[:3]  # Random order for variety
    
    # 💳 Transactions récentes
    transactions_recentes = Transaction.objects.filter(
        projet=projet, 
        statut='confirme',
        destination='operator'
    ).select_related('contributeur').order_by('-date_transaction')[:10]
    
    # 👛 Vérification wallet utilisateur
    user_has_wallet = False
    if request.user.is_authenticated:
        user_has_wallet = (
            hasattr(request.user, 'hedera_account_id') and 
            request.user.hedera_account_id and
            hasattr(request.user, 'hedera_private_key') and 
            request.user.hedera_private_key
        )
    
    # 📝 Gestion des contributions (POST)
    if request.method == 'POST':
        return handle_contribution(request, projet, user_has_wallet)
    
    # 📋 Formulaire de contribution
    form = Transfer_fond(projet=projet, contributeur=request.user if request.user.is_authenticated else None)
    
    # 🎯 Context pour le template
    context = {
        'projet': projet,
        'transactions': transactions_recentes,
        'contributeurs_count': contributeurs_count,
        'montant_total_collecte': montant_total_collecte,
        'form': form,
        'projets_similaires': projets_similaires,
        'pourcentage_financement': projet.pourcentage_financement,
        'pourcentage_distribue': projet.pourcentage_distribue,
        'user_has_wallet': user_has_wallet,
        'recompenses': projet.recompenses_description if projet.has_recompenses else None,
        'can_edit': projet.peut_etre_modifie_par(request.user),
        'is_preview': projet.statut not in ['actif', 'termine'] and user_can_preview,
        'paliers': paliers_avec_statut,
        'conversions': conversions,
        'stats': {
            'vues': projet.vues,
            'partages': projet.partages,
            'taux_conversion': projet.taux_conversion,
            'don_moyen': stats_transactions['don_moyen'] or 0,
            'don_max': stats_transactions['don_max'] or 0,
            'dernier_don': stats_transactions['dernier_don'],
        }
    }
    
    return render(request, 'core/projets/detail_projet.html', context)



def liste_projets(request):
    """Liste de tous les projets actifs avec pagination et filtres"""
    # Récupérer tous les projets actifs
    projets_list = Projet.objects.filter(statut='actif').annotate(
    montant_collectes=Coalesce(
        Sum('transaction__montant', filter=Q(transaction__statut='confirme')),
        0,
        output_field=DecimalField()
    ),
    nombre_donateurs=Count('transaction__contributeur', filter=Q(transaction__statut='confirme'), distinct=True)
    ).order_by('-date_creation')
    
    # Appliquer les filtres
    recherche = request.GET.get('recherche')
    categorie = request.GET.get('categorie')
    type_financement = request.GET.get('type_financement')
    
    if recherche:
        projets_list = projets_list.filter(
            Q(titre__icontains=recherche) |
            Q(description__icontains=recherche) |
            Q(description_courte__icontains=recherche) |
            Q(tags__icontains=recherche)
        )
    
    if categorie and categorie != 'tous':
        projets_list = projets_list.filter(categorie=categorie)
    
    if type_financement and type_financement != 'tous':
        projets_list = projets_list.filter(type_financement=type_financement)
    
    # Préparer les options pour les filtres
    categories = Projet.CATEGORIES
    types_financement = Projet.TYPES_FINANCEMENT
    
    # Pagination - 9 projets par page
    paginator = Paginator(projets_list, 9)
    page_number = request.GET.get('page')
    projets = paginator.get_page(page_number)
    
    context = {
        'projets': projets,
        'categories': categories,
        'types_financement': types_financement,
        'recherche': recherche,
        'categorie_filter': categorie,
        'type_filter': type_financement
    }
    
    return render(request, 'core/projets/liste_projets.html', context)

@login_required
def mes_projets(request):
    """Liste des projets de l'utilisateur connecté avec statistiques et paliers"""
    
    # Récupérer tous les projets du porteur avec annotations et préchargement
    projets = Projet.objects.filter(porteur=request.user).annotate(
        nombre_donateurs=Count('transaction__contributeur', filter=Q(transaction__statut='confirme'), distinct=True),
        derniere_transaction=Max('transaction__date_transaction', filter=Q(transaction__statut='confirme'))
    ).prefetch_related(
        Prefetch('paliers', queryset=Palier.objects.order_by('pourcentage')),
        Prefetch('paliers__preuves', queryset=PreuvePalier.objects.order_by('-date_soumission'))
    ).order_by('-date_creation')
    
    # Calculer les statistiques globales
    stats = {
        'total_projets': projets.count(),
        'projets_actifs': projets.filter(statut='actif').count(),
        'projets_en_attente': projets.filter(statut='en_attente').count(),
        'projets_termines': projets.filter(statut='termine').count(),
        'total_collecte': projets.aggregate(
            total=Sum('montant_collecte')
        )['total'] or 0,
        'total_demande': projets.aggregate(
            total=Sum('montant_demande')
        )['total'] or 0,
    }
    
    # Pourcentage global de financement
    if stats['total_demande'] > 0:
        stats['pourcentage_global'] = round((stats['total_collecte'] / stats['total_demande']) * 100, 1)
    else:
        stats['pourcentage_global'] = 0
    
    # Gestion des actions (changement de statut)
    if request.method == 'POST':
        projet_id = request.POST.get('projet_id')
        action = request.POST.get('action')
        
        try:
            projet = Projet.objects.get(id=projet_id, porteur=request.user)
            
            if action == 'soumettre' and projet.statut == 'brouillon':
                projet.statut = 'en_attente'
                projet.save()
                
                # Journalisation
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='update',
                    modele='Projet',
                    objet_id=str(projet.audit_uuid),
                    details={'ancien_statut': 'brouillon', 'nouveau_statut': 'en_attente'},
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"Le projet '{projet.titre}' a été soumis pour validation.")
            
            elif action == 'annuler' and projet.statut == 'en_attente':
                projet.statut = 'brouillon'
                projet.save()
                
                # Journalisation
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='update',
                    modele='Projet',
                    objet_id=str(projet.audit_uuid),
                    details={'ancien_statut': 'en_attente', 'nouveau_statut': 'brouillon'},
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f"La soumission du projet '{projet.titre}' a été annulée.")
            
            else:
                messages.error(request, "Action non autorisée.")
                
        except Projet.DoesNotExist:
            messages.error(request, "Projet non trouvé.")
        
        return redirect('mes_projets')
    
    context = {
        'projets': projets,
        'stats': stats,
        'STATUTS': dict(Projet.STATUTS)
    }
    
    return render(request, 'core/projets/mes_projets.html', context)

def projets_utilisateur(request, user_id):
    """Affiche tous les projets d'un utilisateur spécifique"""
    utilisateur = get_object_or_404(User, id=user_id)
    
    # Récupérer tous les projets de l'utilisateur (sauf brouillons et rejetés)
    projets = Projet.objects.filter(
        porteur=utilisateur
    ).exclude(
        Q(statut='brouillon') | Q(statut='rejete')
    ).order_by('-date_creation')
    
    # Statistiques de l'utilisateur
    stats = {
        'total_projets': projets.count(),
        'projets_actifs': projets.filter(statut='actif').count(),
        'projets_termines': projets.filter(statut='termine').count(),
        'total_collecte': projets.aggregate(total=Sum('montant_collecte'))['total'] or 0,
        'taux_reussite': calculer_taux_reussite(projets)
    }
    def get_statut_color(statut):
        color_map = {
            'brouillon': 'secondary',
            'en_cours': 'primary', 
            'en_attente': 'warning',
            'termine': 'success',
            'annule': 'danger',
            'suspendu': 'info'
        }
        return color_map.get(statut, 'secondary')
    
    context = {
        'utilisateur': utilisateur,
        'projets': projets,
        'stats': stats,
        'get_statut_color': get_statut_color,
        'intcomma': intcomma,
        'active_tab': 'all' 
    }
    
    return render(request, 'core/projets/projets_utilisateur.html', context)

@login_required
def soumettre_preuves_palier(request, palier_id):
    """Interface pour le porteur pour soumettre les preuves d'un palier"""
    palier = get_object_or_404(Palier, id=palier_id, projet__porteur=request.user)
    projet = palier.projet
    
    if palier.transfere:
        messages.info(request, "Ce palier a déjà été traité")
        return redirect('mes_projets')
    
    try:
        preuve_existante = PreuvePalier.objects.get(palier=palier)
    except PreuvePalier.DoesNotExist:
        preuve_existante = None
    
    if request.method == 'POST':
        # NE PAS utiliser le formulaire pour la validation des fichiers
        # Récupérer directement les fichiers depuis request.FILES
        fichiers = request.FILES.getlist('fichiers')
        description = request.POST.get('description', '')
        
        # Validation manuelle des fichiers
        errors = []
        
        # Vérifier qu'au moins un fichier est sélectionné
        if not fichiers or len(fichiers) == 0:
            errors.append("Veuillez sélectionner au moins un fichier.")
        
        # Vérifier le nombre de fichiers
        elif len(fichiers) > 10:
            errors.append("Maximum 10 fichiers autorisés.")
        
        # Vérifier la taille totale et les types
        else:
            taille_totale = 0
            types_autorises = [
                'image/jpeg', 'image/png', 'image/gif', 'image/webp',
                'application/pdf', 
                'video/mp4', 'video/avi', 'video/quicktime', 'video/x-msvideo',
                'application/msword', 
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain'
            ]
            
            for fichier in fichiers:
                taille_totale += fichier.size
                
                # Vérifier le type MIME
                if hasattr(fichier, 'content_type') and fichier.content_type:
                    if fichier.content_type not in types_autorises:
                        errors.append(f"Type de fichier non autorisé : {fichier.name}")
                
                # Vérifier la taille individuelle
                if fichier.size > 10 * 1024 * 1024:  # 10 MB
                    errors.append(f"Le fichier {fichier.name} est trop volumineux (max 10 MB)")
            
            # Vérifier la taille totale
            if taille_totale > 50 * 1024 * 1024:  # 50 MB
                errors.append("La taille totale des fichiers ne doit pas dépasser 50 MB")
        
        if errors:
            # Afficher les erreurs
            for error in errors:
                messages.error(request, error)
            form = PreuveForm(initial={'description': description})
        else:
            # Traitement des fichiers valides
            with transaction.atomic():
                if preuve_existante:
                    # Supprimer les anciens fichiers physiquement
                    for ancien_fichier in preuve_existante.fichiers.all():
                        ancien_fichier.fichier.delete(save=False)
                    preuve_existante.delete()
                
                # Créer la nouvelle preuve
                preuve = PreuvePalier.objects.create(
                    palier=palier,
                    statut='en_attente'
                )
                
                # Sauvegarder les fichiers
                fichiers_uploades = []
                for fichier in fichiers:
                    type_fichier = determiner_type_fichier(fichier.name)
                    fichier_preuve = FichierPreuve.objects.create(
                        preuve=preuve,
                        fichier=fichier,
                        type_fichier=type_fichier
                    )
                    fichiers_uploades.append(fichier_preuve)
                
                # Journaliser
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='submit_proof',
                    modele='Palier',
                    objet_id=str(palier.id),
                    details={
                        'projet': projet.titre,
                        'palier': f"{palier.pourcentage}%",
                        'fichiers': len(fichiers_uploades),
                        'types_fichiers': [f.type_fichier for f in fichiers_uploades],
                        'statut': 'en_attente'
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )
                
                # Notification HCS
                notifier_soumission_preuve_hcs(projet, palier, len(fichiers_uploades))
            
            messages.success(request, 
                f"✅ {len(fichiers_uploades)} preuve(s) soumise(s) avec succès. "
                f"En attente de vérification par l'administrateur."
            )
            return redirect('mes_projets')
    
    else:
        form = PreuveForm()
    
    context = {
        'palier': palier,
        'projet': projet,
        'form': form,
        'preuve_existante': preuve_existante
    }
    return render(request, 'core/projets/soumettre_preuves.html', context)

#===================
# END PROJETS
#===================
#===================
# ADMIN
#===================

def admin_required(view_func):
    """Décorateur pour vérifier si l'utilisateur est admin"""
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'admin') or not request.user.admin.est_actif:
            from django.contrib import messages
            from django.shortcuts import redirect
            messages.error(request, "Accès réservé aux administrateurs.")
            return redirect('accueil')
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required
@permission_required('core.manage_users', raise_exception=True)
def detail_membre(request, user_id):
    """Détail d'un membre avec statistiques"""
    membre = get_object_or_404(User, id=user_id)
    
    # Statistiques selon le type d'utilisateur
    stats = {}
    
    if membre.user_type == 'porteur':
        stats['projets_crees'] = Projet.objects.filter(porteur=membre).count()
        stats['projets_actifs'] = Projet.objects.filter(porteur=membre, statut='actif').count()
        stats['montant_collecte'] = Projet.objects.filter(
            porteur=membre
        ).aggregate(total=Sum('montant_collecte'))['total'] or 0
    
    if membre.user_type == 'donateur':
        stats['dons_total'] = Transaction.objects.filter(
            contributeur=membre, statut='confirme'
        ).count()
        stats['montant_donne'] = Transaction.objects.filter(
            contributeur=membre, statut='confirme'
        ).aggregate(total=Sum('montant'))['total'] or 0
    
    context = {
        'membre': membre,
        'stats': stats,
        'title': f'Profil de {membre.get_full_name() or membre.username}'
    }
    
    return render(request, 'core/admin/detail_membre.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def gerer_distributions(request):
    """Interface admin pour libérer les fonds selon les paliers avec vérification des preuves"""
    
    # Récupérer les projets éligibles
    projets = Projet.objects.filter(
        Q(montant_engage__gt=0) | 
        Q(statut__in=['actif', 'termine'])
    ).prefetch_related('paliers', 'transaction_set')
    
    distributions = []
    
    for projet in projets:
        # Calcul manuel du total des dons
        total_dons = sum(
            float(t.montant) for t in projet.transaction_set.all() 
            if t.statut == 'confirme' and t.destination == 'operator'
        )
        
        # Calcul des métriques
        montant_engage = float(projet.montant_engage or 0)
        montant_distribue = float(projet.montant_distribue or 0)
        montant_demande = float(projet.montant_demande or 0)
        
        montant_disponible = montant_engage - montant_distribue
        pourcentage_engage = (montant_engage / montant_demande * 100) if montant_demande > 0 else 0
        pourcentage_distribue = (montant_distribue / montant_demande * 100) if montant_demande > 0 else 0
        
        # Analyser chaque palier avec son statut de preuve
        paliers_avec_statut = []
        
        for palier in projet.paliers.order_by('montant_minimum'):
            palier_montant = float(palier.montant or 0)
            
            # Vérifier le statut des preuves
            try:
                preuve = PreuvePalier.objects.get(palier=palier)
                statut_preuve = preuve.statut
                date_soumission = preuve.date_soumission
                preuve_id = preuve.id
            except PreuvePalier.DoesNotExist:
                statut_preuve = 'non_soumis'
                date_soumission = None
                preuve_id = None
            
            # Déterminer si le palier est distributable
            distributable = (
                montant_disponible >= palier_montant and 
                not palier.transfere and
                statut_preuve == 'approuve'
            )
            
            palier_data = {
                'id': palier.id,
                'pourcentage': float(palier.pourcentage),
                'montant': palier_montant,
                'transfere': palier.transfere,
                'date_transfert': palier.date_transfert,
                'statut_preuve': statut_preuve,
                'date_soumission': date_soumission,
                'preuve_id': preuve_id,
                'distributable': distributable,
                'montant_suffisant': montant_disponible >= palier_montant,
                'preuve_requise': not palier.transfere and statut_preuve != 'approuve'
            }
            
            paliers_avec_statut.append(palier_data)
        
        # Séparer les paliers par statut
        paliers_distribuables = [p for p in paliers_avec_statut if p['distributable']]
        paliers_en_attente = [p for p in paliers_avec_statut if not p['transfere'] and not p['distributable']]
        paliers_deja_distribues = [p for p in paliers_avec_statut if p['transfere']]
        
        distributions.append({
            'projet': projet,
            'montant_demande': montant_demande,
            'montant_engage': montant_engage,
            'montant_distribue': montant_distribue,
            'montant_disponible': montant_disponible,
            'pourcentage_engage': round(pourcentage_engage, 1),
            'pourcentage_distribue': round(pourcentage_distribue, 1),
            'paliers_distribuables': paliers_distribuables,
            'paliers_en_attente': paliers_en_attente,
            'paliers_deja_distribues': paliers_deja_distribues,
            'total_dons': total_dons,
        })
    
    # Gestion des requêtes POST
    if request.method == 'POST':
        projet_id = request.POST.get('projet_id')
        palier_id = request.POST.get('palier_id')
        action = request.POST.get('action')
        
        try:
            projet = Projet.objects.get(id=projet_id)
            palier = Palier.objects.get(id=palier_id, projet=projet)
            
            if action == 'distribuer':
                # Vérifications préalables
                try:
                    preuve = PreuvePalier.objects.get(palier=palier)
                    if preuve.statut != 'approuve':
                        messages.error(request, "Les preuves doivent être approuvées avant distribution")
                        return redirect('gerer_distributions')
                except PreuvePalier.DoesNotExist:
                    messages.error(request, "Aucune preuve soumise pour ce palier")
                    return redirect('gerer_distributions')
                
                montant_disponible = projet.montant_engage - projet.montant_distribue
                if montant_disponible < float(palier.montant):
                    messages.error(request, "Fonds insuffisants pour ce palier")
                    return redirect('gerer_distributions')
                
                # Journaliser le début
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='validate',
                    modele='Distribution',
                    objet_id=f"projet_{projet.id}_palier_{palier.id}",
                    details={'action': 'debut_distribution', 'projet': projet.titre},
                    adresse_ip=request.META.get('REMOTE_ADDR'),
                    statut='IN_PROGRESS'
                )
                
                # ⚡ EFFECTUER LE TRANSFERT
                resultat = transfer_from_admin_to_doer(
                        projet=projet,
                        porteur=projet.porteur,
                        montant_brut=palier.montant,
                        palier=palier,
                        initiateur=request.user 
                    )
                if resultat['success']:
                    transaction_hash = resultat['transactionId']
                    
                    # ✅ Mettre à jour le palier avec le hash de transaction
                    palier.transfere = True
                    palier.date_transfert = timezone.now()
                    palier.transaction_hash = resultat['transactionId']
                    palier.save()
                    
                    # Mettre à jour les montants du projet
                    projet.montant_distribue += palier.montant
                    projet.save(update_fields=['montant_distribue'])
                    
                    # 📧 ENVOYER LA NOTIFICATION AU PORTEUR
                    envoyer_notification_porteur(projet.porteur, palier, 'distribution')
                    
                    # 🌐 Notification HCS
                    envoyer_don_hcs(
                        topic_id=projet.topic_id,
                        utilisateur_email=projet.porteur.email,
                        montant=palier.montant,
                        transaction_hash=transaction_hash
                    )
                    
                    # 📝 Journaliser le succès
                    AuditLog.objects.create(
                        utilisateur=request.user,
                        action='validate',
                        modele='Distribution',
                        objet_id=f"projet_{projet.id}_palier_{palier.id}",
                        details={
                            'action': 'distribution_success',
                            'transaction_hash': transaction_hash,
                            'montant': float(palier.montant)
                        },
                        adresse_ip=request.META.get('REMOTE_ADDR'),
                        statut='SUCCESS'
                    )
                    
                    messages.success(request, 
                        f"✅ Distribution de {palier.montant} HBAR effectuée\n"
                        f"📧 Notification envoyée au porteur\n"
                        f"🔗 Transaction: {transaction_hash}"
                    )
                    
                else:
                    # Journaliser l'échec
                    AuditLog.objects.create(
                        utilisateur=request.user,
                        action='validate',
                        modele='Distribution',
                        objet_id=f"projet_{projet.id}_palier_{palier.id}",
                        details={
                            'action': 'distribution_failed',
                            'error': resultat.get('error', 'Erreur inconnue')
                        },
                        adresse_ip=request.META.get('REMOTE_ADDR'),
                        statut='FAILURE'
                    )
                    
                    messages.error(request, f"❌ Erreur: {resultat.get('error', 'Erreur inconnue')}")
            
            elif action == 'verifier_preuves':
                return redirect('verifier_preuves_palier', palier_id=palier.id)
                
        except Exception as e:
            AuditLog.objects.create(
                utilisateur=request.user,
                action='validate',
                modele='Distribution',
                objet_id=f"projet_{projet_id}_palier_{palier_id}",
                details={'action': 'distribution_exception', 'error': str(e)},
                adresse_ip=request.META.get('REMOTE_ADDR'),
                statut='FAILURE'
            )
            
            logger.error(f"Erreur distribution: {str(e)}")
            messages.error(request, f"❌ Erreur: {str(e)}")
        
        return redirect('gerer_distributions')
    
    # Calcul des totaux
    total_engage = sum(dist['montant_engage'] for dist in distributions)
    total_distribue = sum(dist['montant_distribue'] for dist in distributions)
    total_disponible = sum(dist['montant_disponible'] for dist in distributions)
    total_paliers_attente = sum(len(dist['paliers_en_attente']) for dist in distributions)
    total_paliers_distribuables = sum(len(dist['paliers_distribuables']) for dist in distributions)
    
    context = {
        'distributions': distributions,
        'total_engage': total_engage,
        'total_distribue': total_distribue,
        'total_disponible': total_disponible,
        'total_paliers_attente': total_paliers_attente,
        'total_paliers_distribuables': total_paliers_distribuables,
    }
    
    return render(request, 'core/admin/gerer_distributions.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def liste_associations_admin(request):
    """Liste complète des associations pour administration"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    associations = Association.objects.all().select_related('user').order_by('-date_creation_association')
    
    # Filtres
    statut = request.GET.get('statut')
    domaine = request.GET.get('domaine')
    recherche = request.GET.get('recherche')
    
    if statut == 'validees':
        associations = associations.filter(valide=True)
    elif statut == 'attente':
        associations = associations.filter(valide=False)
    
    if domaine:
        associations = associations.filter(domaine_principal=domaine)
    
    if recherche:
        associations = associations.filter(
            Q(nom__icontains=recherche) |
            Q(ville__icontains=recherche) |
            Q(user__email__icontains=recherche)
        )
    
    paginator = Paginator(associations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'associations': page_obj,
        'domaines': Association.DOMAINES_ACTION,
    }
    return render(request, 'core/admin/liste_associations.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def liste_membres(request):
    """Liste des membres avec filtres"""
    membres = User.objects.all().order_by('-date_joined')
    
    form = FiltreMembresForm(request.GET or None)
    
    if form.is_valid():
        if form.cleaned_data['user_type']:
            membres = membres.filter(user_type=form.cleaned_data['user_type'])
        if form.cleaned_data['date_debut']:
            membres = membres.filter(date_joined__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            membres = membres.filter(date_joined__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['recherche']:
            membres = membres.filter(
                Q(username__icontains=form.cleaned_data['recherche']) |
                Q(first_name__icontains=form.cleaned_data['recherche']) |
                Q(last_name__icontains=form.cleaned_data['recherche']) |
                Q(email__icontains=form.cleaned_data['recherche']) |
                Q(organisation__icontains=form.cleaned_data['recherche'])
            )
        if form.cleaned_data['actif']:
            # Convertir la chaîne en booléen
            is_active = form.cleaned_data['actif'] == 'true'
            membres = membres.filter(is_active=is_active)
    
    # Statistiques par type
    stats = {
        'total': membres.count(),
        'porteurs': membres.filter(user_type='porteur').count(),
        'donateurs': membres.filter(user_type='donateur').count(),
        'investisseur': membres.filter(user_type='investisseur').count(),
        'association': membres.filter(user_type='association').count(),
        'admins': membres.filter(user_type='admin').count(),
        'actifs': membres.filter(is_active=True).count(),
    }
    
    # Pagination
    paginator = Paginator(membres, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'membres': page_obj,
        'form': form,
        'stats': stats,
        'title': 'Gestion des membres'
    }
    
    return render(request, 'core/admin/liste_membres.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def logs_distributions(request):
    """Affiche les logs spécifiques aux distributions"""
    logs = AuditLog.objects.filter(
        modele__in=['Distribution', 'DistributionAuto', 'Palier']
    ).order_by('-date_action')
    
    return render(request, 'core/admin/logs_distributions.html', {
        'logs': logs
    })


@login_required
@permission_required('core.manage_users', raise_exception=True)
def liste_projets_attente(request):
    """Liste complète des associations pour administration"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    projets = Projet.objects.filter(statut='en_attente').select_related('porteur')
    
    context = {
        'liste_projet_admin': projets,
        'title': 'Projets en attente de validation'
    }
    
    return render(request, 'core/admin/projets_en_attente.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def rejeter_association(request, association_id):
    """Rejeter une association avec motif"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    association = get_object_or_404(Association, id=association_id)
    
    if request.method == 'POST':
        motif = request.POST.get('motif', '')
        
        # Créer un log d'audit
        AuditLog.objects.create(
            utilisateur=request.user,
            action='reject',  # Utilisez 'action' au lieu de 'action_type'
            modele='Association',  # Utilisez 'modele' au lieu de 'modele_concerne'
            objet_id=str(association.id),  # Utilisez 'objet_id' au lieu de 'id_modele'
            details=f"Rejet de l'association {association.nom}. Motif: {motif}",
            adresse_ip=get_client_ip(request)  # Utilisez 'adresse_ip' au lieu de 'ip_address'
        )
        
        # Envoyer un email de notification (optionnel)
        try:
            send_mail(
                subject=f"Votre association {association.nom} n'a pas été validée",
                message=f"""Votre association "{association.nom}" n'a pas été validée pour la raison suivante:

{motif}

Vous pouvez modifier votre profil et soumettre à nouveau votre demande.

Cordialement,
L'équipe Solidavenir""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[association.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Erreur envoi email: {e}")
        
        # Supprimer l'association ou la marquer comme rejetée
        association.delete()  # ou association.valide = False + sauvegarde
        
        messages.warning(request, f"L'association {association.nom} a été rejetée.")
        return redirect('tableau_de_bord')
    
    context = {'association': association}
    return render(request, 'core/admin/rejeter_association.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def tableau_de_bord(request):
    """Tableau de bord administrateur complet avec éléments prioritaires"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    # Date pour les filtres
    aujourdhui = timezone.now().date()
    debut_semaine = aujourdhui - timedelta(days=aujourdhui.weekday())
    debut_mois = aujourdhui.replace(day=1)
    
    # ÉLÉMENTS PRIORITAIRES - À VALIDER/VÉRIFIER
    
    # 1. Projets en attente de validation
    projets_attention = Projet.objects.filter(
        statut='en_attente'
    ).select_related('porteur').order_by('date_creation')[:10]
    
    # 2. Associations en attente de validation
    associations_attente = Association.objects.filter(
        valide=False
    ).select_related('user').order_by('date_creation_association')[:10]
    
    # 3. Paliers atteints nécessitant une action
    paliers_atteints = Palier.objects.filter(
        transfere=False,
        projet__statut='actif'
    ).select_related('projet').order_by('projet__date_creation')
    
    # Filtrer uniquement les paliers dont le montant minimum est atteint
    paliers_action = []
    for palier in paliers_atteints:
        montant_collecte = Transaction.objects.filter(
            projet=palier.projet,
            statut='confirme'
        ).aggregate(Sum('montant'))['montant__sum'] or 0
        
        if montant_collecte >= palier.montant_minimum:
            paliers_action.append({
                'palier': palier,
                'montant_collecte': montant_collecte,
                'pourcentage_atteint': (montant_collecte / palier.projet.montant_demande * 100) if palier.projet.montant_demande > 0 else 0
            })
    
    # 4. Preuves de palier à vérifier
    preuves_a_verifier = PreuvePalier.objects.filter(
        statut__in=['en_attente', 'modification']
    ).select_related('palier', 'palier__projet').order_by('-date_soumission')[:10]
    
    # 5. Transactions à vérifier (pour la modération)
    transactions_verification = Transaction.objects.filter(
        statut='en_attente'
    ).select_related('projet', 'contributeur').order_by('-date_transaction')[:5]
    
    # STATISTIQUES PRINCIPALES (simplifiées pour focus sur l'action)
    stats = {
        # Actions prioritaires
        'projets_attente': projets_attention.count(),
        'associations_attente': associations_attente.count(),
        'paliers_action': len(paliers_action),
        'preuves_verification': preuves_a_verifier.count(),
        'transactions_verification': transactions_verification.count(),
        
        # Projets
        'projets_total': Projet.objects.count(),
        'projets_actifs': Projet.objects.filter(statut='actif').count(),
        'projets_termines': Projet.objects.filter(statut='termine').count(),
        
        # Utilisateurs
        'utilisateurs_total': User.objects.count(),
        'association_total': User.objects.filter(user_type='association').count(),
        'porteurs_total': User.objects.filter(user_type='porteur').count(),
        'donateurs_total': User.objects.filter(user_type='donateur').count(),
        
        # Transactions
        'transactions_confirmees': Transaction.objects.filter(statut='confirme').count(),
        
        # Montants
        'montant_total': Transaction.objects.filter(statut='confirme').aggregate(
            Sum('montant'))['montant__sum'] or 0,
        'montant_jour': Transaction.objects.filter(
            date_transaction__date=aujourdhui,
            statut='confirme'
        ).aggregate(Sum('montant'))['montant__sum'] or 0,
        
        # Dons
        'dons_jour': Transaction.objects.filter(
            date_transaction__date=aujourdhui,
            statut='confirme'
        ).count(),
    }
    
    # Données pour les graphiques (conservées mais optionnelles)
    projets_par_statut = Projet.objects.values('statut').annotate(
        count=Count('id')
    ).order_by('statut')
    
    # Évolution des dons sur les 15 derniers jours (réduit pour plus de rapidité)
    derniers_15_jours = [aujourdhui - timedelta(days=i) for i in range(14, -1, -1)]
    dons_par_jour = Transaction.objects.filter(
        date_transaction__date__gte=aujourdhui - timedelta(days=14),
        statut='confirme'
    ).values('date_transaction__date').annotate(
        total=Sum('montant'),
        count=Count('id')
    ).order_by('date_transaction__date')
    
    donnees_graphique = {
        'labels': [date.strftime('%d/%m') for date in derniers_15_jours],
        'montants': [0] * 15,
        'nombre_dons': [0] * 15
    }
    
    for don in dons_par_jour:
        date_str = don['date_transaction__date'].strftime('%d/%m')
        if date_str in donnees_graphique['labels']:
            index = donnees_graphique['labels'].index(date_str)
            donnees_graphique['montants'][index] = float(don['total'])
            donnees_graphique['nombre_dons'][index] = don['count']
    
    # Dernières transactions confirmées (pour monitoring)
    recent_transactions = Transaction.objects.filter(
        statut='confirme'
    ).select_related('projet', 'contributeur').order_by('-date_transaction')[:5]
    
    # Derniers logs d'audit
    recent_audits = AuditLog.objects.select_related('utilisateur').order_by('-date_action')[:5]
    
    # Top donateurs
    top_donateurs = User.objects.filter(
        user_type='donateur',
        transaction__statut='confirme'
    ).annotate(
        total_dons=Sum('transaction__montant'),
        nombre_dons=Count('transaction')
    ).order_by('-total_dons')[:5]
    
    # Projets les plus financés
    projets_populaires = Projet.objects.filter(
        statut='actif'
    ).annotate(
        montant_collectes=Sum('transaction__montant', filter=Q(transaction__statut='confirme'))
    ).order_by('-montant_collectes')[:5]
    
    # Statistiques associations
    stats_associations = {
        'associations_total': Association.objects.count(),
        'associations_validees': Association.objects.filter(valide=True).count(),
        'associations_attente': Association.objects.filter(valide=False).count(),
    }
    
    context = {
        # ÉLÉMENTS PRIORITAIRES
        'projets_attention': projets_attention,
        'associations_attente': associations_attente,
        'paliers_action': paliers_action,
        'preuves_a_verifier': preuves_a_verifier,
        'transactions_verification': transactions_verification,
        
        # STATISTIQUES
        'stats': stats,
        'stats_associations': stats_associations,
        
        # DONNÉES SECOND AIRES
        'projets_par_statut': list(projets_par_statut),
        'donnees_graphique': donnees_graphique,
        'recent_transactions': recent_transactions,
        'recent_audits': recent_audits,
        'top_donateurs': top_donateurs,
        'projets_populaires': projets_populaires,
        'aujourdhui': aujourdhui,
    }
    
    return render(request, 'core/admin/tableau_de_bord.html', context)

@login_required
@permission_required('core.view_dashboard', raise_exception=True)
def liste_transactions_validation(request):
    """Liste des transactions à vérifier avec filtres"""
    transactions = Transaction.objects.all().order_by('-date_transaction')
    form = FiltreTransactionsForm(request.GET or None)
    
    if form.is_valid():
        if form.cleaned_data['date_debut']:
            transactions = transactions.filter(date_transaction__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            transactions = transactions.filter(date_transaction__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['montant_min']:
            transactions = transactions.filter(montant__gte=form.cleaned_data['montant_min'])
        if form.cleaned_data['montant_max']:
            transactions = transactions.filter(montant__lte=form.cleaned_data['montant_max'])
        if form.cleaned_data['projet']:
            transactions = transactions.filter(projet__titre__icontains=form.cleaned_data['projet'])
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'transactions': page_obj,
        'form': form,
        'title': 'Transactions à vérifier',
        'total_transactions': transactions.count(),
        'montant_total': transactions.aggregate(total=Sum('montant'))['total'] or 0
    }
    
    return render(request, 'core/admin/transactions_validation.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def valider_association(request, association_id):
    """Valider une association"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    association = get_object_or_404(Association, id=association_id)
    
    if request.method == 'POST':
        association.valide = True
        association.save()
        
        # Créer un log d'audit
        AuditLog.objects.create(
            utilisateur=request.user,
            action='validate',  # Utilisez 'action' au lieu de 'action_type'
            modele='Association',  # Utilisez 'modele' au lieu de 'modele_concerne'
            objet_id=str(association.id),  # Utilisez 'objet_id' au lieu de 'id_modele'
            details=f"Validation de l'association {association.nom}",
            adresse_ip=get_client_ip(request)  # Utilisez 'adresse_ip' au lieu de 'ip_address'
        )
        
        # Envoyer un email de confirmation (optionnel)
        try:
            send_mail(
                subject=f"Votre association {association.nom} a été validée !",
                message=f"""Félicitations ! Votre association "{association.nom}" a été validée par notre équipe.

Elle est maintenant visible sur la plateforme Solidavenir et peut recevoir des dons.

Cordialement,
L'équipe Solidavenir""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[association.user.email],
                fail_silently=True,
            )
        except Exception as e:
            print(f"Erreur envoi email: {e}")
        
        messages.success(request, f"L'association {association.nom} a été validée avec succès.")
        return redirect('tableau_de_bord')
    
    context = {'association': association}
    return render(request, 'core/admin/valider_association.html', context)


@login_required
@permission_required('core.validate_project', raise_exception=True)
def valider_projet(request, audit_uuid):
    """Validation d'un projet par un administrateur avec gestion complète"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    # Vérifier que le projet est en attente de validation
    if projet.statut not in ['en_attente', 'brouillon']:
        messages.warning(request, f"Ce projet est déjà {projet.get_statut_display().lower()}.")
        return redirect('tableau_de_bord')
    
    # Statistiques pour le dashboard admin
    stats = {
        'montant_demande': projet.montant_demande,
        'duree_existence': (timezone.now() - projet.date_creation).days,
        'projets_utilisateur': Projet.objects.filter(porteur=projet.porteur).count(),
    }
    
    if request.method == 'POST':
        form = ValidationProjetForm(request.POST, instance=projet)
        if form.is_valid():
            projet = form.save(commit=False)
            ancien_statut = projet.statut
            nouveau_statut = form.cleaned_data['statut']
            
            # Gestion de la validation
            if nouveau_statut == 'actif':
                projet.valide_par = request.user
                projet.date_validation = timezone.now()
                
                # Génération d'un identifiant unique simple (remplacement Hedera)
                if not projet.identifiant_unique:
                    identifiant = f"SOLID{projet.id:06d}{timezone.now().strftime('%Y%m%d')}"
                    projet.identifiant_unique = identifiant
                    
                    # Journalisation création identifiant
                    AuditLog.objects.create(
                        utilisateur=request.user,
                        action='create',
                        modele='ProjectID',
                        objet_id=identifiant,
                        details={'projet': projet.titre},
                        adresse_ip=request.META.get('REMOTE_ADDR')
                    )
                    
                    messages.info(request, f"Identifiant unique généré: {identifiant}")
                
                # ✅ CRÉATION DU TOPIC HCS SUR HEDERA
                if not projet.topic_id:
                    try:
                        topic_response = creer_topic_pour_projet(projet, request.user)
                        if topic_response and topic_response.get('success'):
                            # Les champs sont déjà sauvegardés par creer_topic_pour_projet
                            # On peut simplement mettre à jour le statut
                            projet.hedera_topic_created = True
                            
                            # Journalisation création topic
                            AuditLog.objects.create(
                                utilisateur=request.user,
                                action='create',
                                modele='HederaTopic',
                                objet_id=topic_response['topicId'],
                                details={
                                    'projet': projet.titre,
                                    'transaction_id': topic_response.get('transactionId', ''),
                                    'hashscan_url': topic_response.get('hashscanUrl', '')
                                },
                                adresse_ip=request.META.get('REMOTE_ADDR')
                            )
                            
                            messages.success(request, f"Topic HCS créé: {projet.topic_id}")
                        else:
                            error_msg = topic_response.get('error', 'Erreur inconnue') if topic_response else 'Erreur inconnue'
                            messages.warning(request, f"Projet validé mais erreur création topic HCS: {error_msg}")
                    except Exception as e:
                        logger.error(f"Erreur création topic HCS: {str(e)}")
                        messages.warning(request, f"Projet validé mais erreur création topic HCS: {str(e)}")
                
            elif nouveau_statut == 'rejete':
                projet.valide_par = request.user
                projet.date_validation = None
                
                # Envoyer un email au porteur en cas de rejet
                try:
                    sujet_email = f'Votre projet  a été examiné - Solid\'Avenir'
                    message_email = f"""Bonjour {projet.porteur.get_full_name() or projet.porteur.username},

Votre projet "{projet.titre}" a été examiné par notre équipe.
Statut: Rejeté
Raison: {form.cleaned_data.get('commentaire_validation', 'Non spécifiée')}

Vous pouvez modifier votre projet et le soumettre à nouveau.

Cordialement,
L'équipe Solid'Avenir"""
                    
                    send_mail(
                        sujet_email,
                        message_email,
                        settings.DEFAULT_FROM_EMAIL,
                        [projet.porteur.email],
                        fail_silently=True,
                    )
                    messages.info(request, "Email de rejet envoyé au porteur du projet.")
                    
                except Exception as e:
                    logger.error(f"Erreur envoi email rejet: {str(e)}")
                    messages.warning(request, "Erreur lors de l'envoi d'email, mais le projet a été rejeté.")
            
            projet.save()
            
            # Journalisation audit détaillée
            action = 'validate' if nouveau_statut == 'actif' else 'reject'
            AuditLog.objects.create(
                utilisateur=request.user,
                action=action,
                modele='Projet',
                objet_id=str(projet.audit_uuid),
                details={
                    'ancien_statut': ancien_statut,
                    'nouveau_statut': nouveau_statut,
                    'montant': float(projet.montant_demande),
                    'commentaire': form.cleaned_data.get('commentaire_validation', ''),
                    'topic_id': projet.topic_id if nouveau_statut == 'actif' else None,
                    'hedera_topic_created': projet.hedera_topic_created if nouveau_statut == 'actif' else False
                },
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            # Envoyer une notification au porteur pour validation
            if nouveau_statut == 'actif':
                try:
                    # Formatage correct du sujet d'email
                    sujet_email = f'Félicitations ! Votre projet  est actif - Solid\'Avenir'
                    
                    # Formatage correct du message (éviter les caractères bizarres)
                    message_email = f"""Bonjour {projet.porteur.get_full_name() or projet.porteur.username},

Votre projet "{projet.titre}" a été validé et est maintenant actif sur notre plateforme.
Montant demandé: {projet.montant_demande:,} FCFA

Lien de votre projet: {request.build_absolute_uri(projet.get_absolute_url())}

Informations blockchain:
- Topic HCS: {projet.topic_id}
- Voir sur HashScan: {projet.hedera_topic_hashscan_url or 'Non disponible'}

Vous pouvez maintenant partager votre projet et commencer à collecter des fonds.

Cordialement,
L'équipe Solid'Avenir"""
                    
                    send_mail(
                        sujet_email,
                        message_email,
                        settings.DEFAULT_FROM_EMAIL,
                        [projet.porteur.email],
                        fail_silently=True,
                    )
                    messages.info(request, "Email de validation envoyé au porteur du projet.")
                    
                except Exception as e:
                    logger.error(f"Erreur envoi email validation: {str(e)}")
                    messages.warning(request, "Erreur lors de l'envoi d'email, mais le projet a été validé.")
            
            action_msg = "validé et activé" if nouveau_statut == 'actif' else "rejeté"
            messages.success(request, f"Le projet a été {action_msg} avec succès.")
            
            return redirect('tableau_de_bord')
    else:
        form = ValidationProjetForm(instance=projet)
    
    # Documents du projet
    documents = []
    if projet.document_justificatif:
        documents.append({
            'nom': 'Document justificatif',
            'fichier': projet.document_justificatif,
            'type': 'justificatif'
        })
    if projet.plan_financement:
        documents.append({
            'nom': 'Plan de financement',
            'fichier': projet.plan_financement,
            'type': 'financement'
        })
    
    context = {
        'form': form,
        'projet': projet,
        'documents': documents,
        'stats': stats,
        'porteur': projet.porteur,
        'STATUTS': dict(Projet.STATUTS)
    }
    
    return render(request, 'core/admin/valider_projet.html', context)


@login_required
@permission_required('core.manage_users', raise_exception=True)
def verifier_preuves_palier(request, palier_id):
    """Interface pour vérifier les preuves soumises par le porteur"""
    palier = get_object_or_404(Palier, id=palier_id)
    projet = palier.projet
    
    try:
        preuve = PreuvePalier.objects.get(palier=palier)
        fichiers = preuve.fichiers.all()
    except PreuvePalier.DoesNotExist:
        preuve = None
        fichiers = []
    
    if request.method == 'POST':
        form = VerificationPreuveForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            commentaires = form.cleaned_data['commentaires']
            
            if not preuve:
                messages.error(request, "Aucune preuve trouvée pour ce palier")
                return redirect('gerer_distributions')
            
            if action == 'approuver':
                preuve.statut = 'approuve'
                preuve.commentaires = commentaires
                preuve.save()
                
                # Journaliser
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='approve_proof',
                    modele='PreuvePalier',
                    objet_id=str(preuve.id),
                    details={
                        'projet': projet.titre,
                        'palier': f"{palier.pourcentage}%",
                        'montant': float(palier.montant),
                        'fichiers': len(fichiers),
                        'statut': 'approuve'
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR'),
                    statut='SUCCESS'
                )
                
                # Notifier le porteur
                envoyer_notification_porteur(projet.porteur, palier, 'approuve', commentaires)
                
                messages.success(request, "Preuves approuvées avec succès")
                
            elif action == 'rejeter':
                preuve.statut = 'rejete'
                preuve.commentaires = commentaires
                preuve.save()
                
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='reject_proof',
                    modele='PreuvePalier',
                    objet_id=str(preuve.id),
                    details={
                        'projet': projet.titre,
                        'palier': f"{palier.pourcentage}%",
                        'commentaires': commentaires,
                        'statut': 'rejete'
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR'),
                    statut='SUCCESS'
                )
                
                envoyer_notification_porteur(projet.porteur, palier, 'rejete', commentaires)
                messages.warning(request, "Preuves rejetées")
                
            elif action == 'modification':
                preuve.statut = 'modification'
                preuve.commentaires = commentaires
                preuve.save()
                
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='request_proof_modification',
                    modele='PreuvePalier',
                    objet_id=str(preuve.id),
                    details={
                        'projet': projet.titre,
                        'palier': f"{palier.pourcentage}%",
                        'commentaires': commentaires,
                        'statut': 'modification'
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR'),
                    statut='SUCCESS'
                )
                
                envoyer_notification_porteur(projet.porteur, palier, 'modification', commentaires)
                messages.info(request, "Modifications demandées au porteur")
            
            return redirect('gerer_distributions')
    else:
        form = VerificationPreuveForm()
    
    context = {
        'palier': palier,
        'projet': projet,
        'preuve': preuve,
        'fichiers': fichiers,
        'form': form
    }
    return render(request, 'core/admin/verifier_preuves.html', context)


@login_required
@permission_required('core.can_audit', raise_exception=True)
def logs_audit(request):
    """Logs d'audit avec filtres"""
    logs = AuditLog.objects.all().select_related('utilisateur').order_by('-date_action')
    
    form = FiltreAuditForm(request.GET or None)
    
    if form.is_valid():
        if form.cleaned_data['utilisateur']:
            logs = logs.filter(utilisateur=form.cleaned_data['utilisateur'])
        if form.cleaned_data['action']:
            logs = logs.filter(action=form.cleaned_data['action'])
        if form.cleaned_data['modele']:
            logs = logs.filter(modele__icontains=form.cleaned_data['modele'])
        if form.cleaned_data['date_debut']:
            logs = logs.filter(date_action__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            logs = logs.filter(date_action__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['recherche']:
            logs = logs.filter(
                Q(modele__icontains=form.cleaned_data['recherche']) |
                Q(objet_id__icontains=form.cleaned_data['recherche']) |
                Q(details__icontains=form.cleaned_data['recherche'])
            )
    
    # Statistiques
    stats = {
        'total': logs.count(),
        'aujourdhui': logs.filter(date_action__date=timezone.now().date()).count(),
        '7_jours': logs.filter(date_action__gte=timezone.now() - timedelta(days=7)).count(),
    }
    
    # Pagination
    paginator = Paginator(logs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'logs': page_obj,
        'form': form,
        'stats': stats,
        'title': 'Logs d\'audit'
    }
    
    return render(request, 'core/admin/logs_audit.html', context)


@login_required
def preview_association_admin(request, association_id):
    """Prévisualisation d'une association pour les administrateurs (même non validée)"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    association = get_object_or_404(Association, id=association_id)
    
    context = {
        'association': association,
        'projets_actifs': association.get_projets_actifs(),
        'is_preview': True  # Pour indiquer au template que c'est une prévisualisation admin
    }
    return render(request, 'core/associations/detail_association.html', context)

#===================
# END ADMIN
#===================




logger = logging.getLogger(__name__)
def handle_contribution(request, projet, user_has_wallet):
    """Gère la soumission d'une contribution"""
    # 🔒 Vérifications de sécurité
    if not request.user.is_authenticated:
        messages.info(request, "Connectez-vous pour contribuer.")
        return redirect(f"{reverse('connexion')}?{urlencode({'next': request.path})}")

    if request.user.user_type == 'admin':
        messages.error(request, "Les administrateurs ne peuvent pas effectuer de contributions.")
        return redirect('detail_projet', audit_uuid=projet.audit_uuid)

    if projet.statut != 'actif':
        messages.error(request, "Les contributions ne sont pas autorisées pour ce projet actuellement.")
        return redirect('detail_projet', audit_uuid=projet.audit_uuid)

    if not user_has_wallet:
        messages.error(request, "Veuillez configurer votre wallet pour effectuer une contribution.")
        return redirect('configurer_wallet')

    # 📝 Validation du formulaire
    form = Transfer_fond(request.POST, projet=projet, contributeur=request.user)
    
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Erreur {field}: {error}")
        return redirect('detail_projet', audit_uuid=projet.audit_uuid)

    try:
        with transaction.atomic():
            # 💾 Sauvegarde de la transaction
            transaction_obj = form.save(commit=False)
            transaction_obj.projet = projet
            transaction_obj.contributeur = request.user
            transaction_obj.statut = "en_attente"
            transaction_obj.destination = "operator"
            transaction_obj.save()

            # 📊 Mise à jour des statistiques du projet
            projet.refresh_from_db()

            # 📖 AUDIT LOG - Journalisation détaillée
            AuditLog.objects.create(
                utilisateur=request.user,
                action="contribution_initiee",
                modele="Transaction",
                objet_id=str(transaction_obj.id),
                details={
                    'montant': float(transaction_obj.montant),
                    'projet_id': projet.id,
                    'projet_titre': projet.titre,
                    'projet_audit_uuid': str(projet.audit_uuid),
                    'contributeur_email': request.user.email,
                    'transaction_type': 'don',
                    'destination': 'operator',
                    'statut': 'en_attente',
                    'commission_projet': float(projet.commission),
                    'montant_engage_avant': float(projet.montant_engage),
                    'montant_collecte_avant': float(projet.montant_collecte or 0)
                },
                adresse_ip=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                statut='SUCCESS'
            )

            # 🔔 Notification (optionnelle)
            try:
                # Envoyer une notification HCS
                from .utils import envoyer_notification_contribution
                envoyer_notification_contribution(projet, request.user, transaction_obj.montant)
            except Exception as e:
                logger.error(f"Erreur notification contribution: {e}")

            messages.success(request, 
                f"✅ Votre contribution de {transaction_obj.montant} HBAR a été enregistrée ! "
                f"Elle est en attente de confirmation sur la blockchain."
            )

    except Exception as e:
        logger.error(f"Erreur lors de la contribution: {e}")
        
        # 📖 AUDIT LOG - Journalisation de l'erreur
        AuditLog.objects.create(
            utilisateur=request.user,
            action="contribution_erreur",
            modele="Transaction",
            objet_id="N/A",
            details={
                'erreur': str(e),
                'projet_id': projet.id,
                'projet_titre': projet.titre,
                'contributeur_email': request.user.email,
                'montant_tente': request.POST.get('montant', 'N/A')
            },
            adresse_ip=request.META.get('REMOTE_ADDR'),
            statut='FAILURE'
        )
        
        messages.error(request, "Une erreur est survenue lors de l'enregistrement de votre contribution.")

    return redirect('detail_projet', audit_uuid=projet.audit_uuid)

def configurer_wallet(request):
    """Vue temporaire pour la configuration du wallet"""
    messages.info(request, "La fonctionnalité de configuration du wallet sera bientôt disponible.")
    return redirect('profil')

def calculer_taux_reussite(projets_queryset):
    """Calcule le taux de réussite des projets terminés"""
    projets_termines = projets_queryset.filter(statut__in=['termine', 'echec'])
    if not projets_termines.exists():
        return 0
    
    reussis = projets_termines.filter(statut='termine').count()
    return round((reussis / projets_termines.count()) * 100, 1)

# Fonction utilitaire pour récupérer l'IP
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
   

@login_required
def envoyer_email_view(request):
    """Vue simpliste pour envoyer un email"""
    if request.method == 'POST':
        form = EmailFormSimple(request.POST)
        if form.is_valid():
            # Récupérer les données du formulaire
            destinataire = form.cleaned_data['destinataire']
            sujet = form.cleaned_data['sujet']
            message = form.cleaned_data['message']
            type_email = form.cleaned_data['type_email']
            
            try:
                # Créer le log d'email
                email_log = EmailLog.objects.create(
                    destinataire=destinataire,
                    sujet=sujet,
                    corps=message,
                    type_email=type_email,
                    statut='pending',
                    utilisateur=request.user
                )
                
                # Envoyer l'email réel
                send_mail(
                    sujet,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [destinataire],
                    fail_silently=False,
                )
                
                # Marquer comme envoyé
                email_log.marquer_comme_envoye()
                
                messages.success(request, f"Email envoyé avec succès à {destinataire}")
                return redirect('envoyer_email')
                
            except Exception as e:
                # En cas d'erreur
                if 'email_log' in locals():
                    email_log.marquer_comme_erreur(str(e))
                
                messages.error(request, f"Erreur lors de l'envoi: {str(e)}")
    else:
        form = EmailFormSimple()
    
    return render(request, 'core/emails/envoyer_email.html', {'form': form})


@login_required
def liste_emails_view(request):
    """Vue pour afficher la liste des emails envoyés"""
    emails = EmailLog.objects.all().order_by('-date_creation')
    return render(request, 'core/emails/liste_email.html', {'emails': emails})


def voir_wallet(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # S'assurer que l'utilisateur a un wallet
    request.user.ensure_wallet()
    
    # Obtenir le solde actuel
    solde = None
    try:
        response = requests.get(
            f'http://hedera_service:3001/balance/{request.user.hedera_account_id}',
            timeout=5
        )
        if response.status_code == 200:
            solde = response.json().get('balance')
    except Exception as e:
        print(f"Erreur récupération solde: {e}")
    
    return render(request, 'core/hedera/wallet_detail.html', {
        'solde': solde,
        'user': request.user
    })


def creer_topic_pour_projet(projet, utilisateur):
    """
    Crée un topic HCS pour un projet via le microservice Node.js
    et journalise l'action avec l'utilisateur à l'origine.
    """
    url = "http://hedera_service:3001/create-topic"
    try:
        response = requests.post(url, json={
            "memo": f"Projet {projet.titre} - {projet.audit_uuid}"
        }, timeout=30)  
        response.raise_for_status() 
        data = response.json()
        
        if data.get("success"):
            # Sauvegarder l'ID du topic dans le projet
            projet.topic_id = data["topicId"]
            projet.hedera_topic_created = True
            projet.hedera_topic_transaction_id = data.get("transactionId")
            projet.hedera_topic_hashscan_url = data.get("hashscanUrl")
            projet.save(update_fields=[
                "topic_id", 
                "hedera_topic_created", 
                "hedera_topic_transaction_id", 
                "hedera_topic_hashscan_url"
            ])
            
            # Journaliser la création du topic avec l'utilisateur
            AuditLog.objects.create(
                utilisateur=utilisateur,  
                action='create',
                modele='HCS_Topic',
                objet_id=data["topicId"],
                details={
                    'projet': projet.titre,
                    'projet_uuid': str(projet.audit_uuid),
                    'transaction_hash': data.get("transactionId", ""),
                    'hashscan_url': data.get("hashscanUrl", "")
                },
                adresse_ip=getattr(utilisateur, "last_login_ip", "127.0.0.1")
            )
            
            return data  
        
        else:
            error_msg = data.get("error", "Erreur inconnue")
            logger.error(f"Erreur création topic HCS: {error_msg}")
            raise Exception(error_msg)
            
    except requests.exceptions.ConnectionError:
        logger.error("Microservice HCS non disponible")
        raise Exception("Service de blockchain temporairement indisponible")
    except requests.exceptions.Timeout:
        logger.error("Timeout création topic HCS")
        raise Exception("Timeout du service blockchain")
    except Exception as e:
        logger.error(f"Erreur création topic pour projet {projet.id}: {e}")
        raise e


def envoyer_don_hcs(topic_id, utilisateur_email, montant, transaction_hash, type_message="distribution_palier"):
    """Envoie un message HCS pour enregistrer un don"""
    url = "http://hedera_service:3001/send-message"
    
    # Message structuré pour HCS
    message_data = {
        "type": type_message,
        "utilisateur": utilisateur_email,
        "montant": float(montant),
        "date": timezone.now().isoformat(),
        "transaction_hash": transaction_hash,
        "timestamp": int(timezone.now().timestamp())
    }
    
    payload = {
        "topicId": topic_id,
        "message": message_data
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        data = response.json()
        from core.models import Projet, TopicMessage
        projet = Projet.objects.filter(topic_id=topic_id).first()
        if projet:
            TopicMessage.objects.create(
                projet=projet,
                type_message=type_message,
                utilisateur_email=utilisateur_email,
                montant=montant,
                transaction_hash=transaction_hash,
                contenu=message_data
            )

        logger.info(f"Message HCS envoyé avec succès: {data}")
        return data
        
    except requests.exceptions.ConnectionError:
        logger.error("Microservice HCS non disponible")
        return {"success": False, "error": "Service HCS indisponible"}
    
    except requests.exceptions.Timeout:
        logger.error("Timeout lors de l'envoi du message HCS")
        return {"success": False, "error": "Timeout service HCS"}
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"Erreur HTTP HCS: {e}")
        return {"success": False, "error": f"Erreur HTTP: {e}"}
    
    except Exception as e:
        logger.error(f"Erreur inattendue HCS: {e}")
        return {"success": False, "error": str(e)}

@csrf_exempt
def process_donation(request, project_id):
    if request.method == 'POST':
        try:
            project = Projet.objects.get(id=project_id)

            if not request.user.is_authenticated:
                messages.error(request, "Vous devez être connecté pour effectuer un don")
                return redirect('login')
            
            if not request.user.hedera_account_id or not request.user.hedera_private_key:
                messages.error(request, "Votre wallet n'est pas configuré")
                return redirect('detail_projet', audit_uuid=project.audit_uuid)
            
            amount = Decimal(request.POST.get('amount', 0))
            if amount <= 0:
                messages.error(request, "Montant invalide")
                return redirect('detail_projet', audit_uuid=project.audit_uuid)

            user = request.user

            # --- Transfert HBAR ---
            transfer_data = {
                'fromAccountId': user.hedera_account_id,
                'fromPrivateKey': user.hedera_private_key,
                'toAccountId': settings.HEDERA_OPERATOR_ID,
                'amount': float(amount)
            }
            response = requests.post('http://hedera_service:3001/transfer', json=transfer_data, timeout=30)

            if response.status_code != 200:
                messages.error(request, "Erreur lors du transfert HBAR ❌")
                return redirect('detail_projet', audit_uuid=project.audit_uuid)

            result = response.json()

            transaction = Transaction.objects.create(
                user=user,
                montant=amount,
                hedera_transaction_hash=result.get('transactionId'),
                contributeur=user,
                projet=project,
                statut='confirme' if result.get('success') else 'erreur',
                destination='operator'
            )

            # Mise à jour du montant engagé
            if transaction.statut == 'confirme':
                project.montant_engage = (
                    project.transaction_set.filter(statut='confirme', destination='operator')
                    .aggregate(total=Sum('montant'))['total'] or 0
                )
                project.save(update_fields=['montant_engage'])

                # --- Envoyer message HCS ---
                if project.topic_id:
                    hcs_response = envoyer_don_hcs(
                        topic_id=project.topic_id,
                        utilisateur_email=user.email,
                        montant=amount,
                        transaction_hash=result.get('transactionId')
                    )

                    if hcs_response and hcs_response.get('success'):
                        transaction.hedera_message_id = hcs_response.get('messageId')
                        transaction.hedera_message_hashscan_url = f"https://hashscan.io/testnet/topic/{project.topic_id}?message={hcs_response.get('messageId')}"
                        transaction.save(update_fields=['hedera_message_id', 'hedera_message_hashscan_url'])

                        messages.success(request, f"Votre don de {amount} HBAR a été effectué ✅ et tracé sur HCS")
                        
                        # 🔹 Optionnel : envoyer email au contributeur
                        # send_email_hedera_confirmation(user.email, transaction)
                    else:
                        error_msg = hcs_response.get('error', 'Erreur HCS') if hcs_response else 'Service HCS indisponible'
                        messages.warning(request, f"Don effectué mais erreur HCS: {error_msg} ⚠️")
                else:
                    messages.warning(request, "Don effectué mais aucun Topic HCS associé au projet ⚠️")

            else:
                messages.error(request, "Erreur lors de l'enregistrement de la transaction ❌")

            return redirect('detail_projet', audit_uuid=project.audit_uuid)

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('detail_projet', audit_uuid=project.audit_uuid)

    messages.warning(request, "Méthode non autorisée")
    return redirect('detail_projet', audit_uuid=project.audit_uuid)

def transfer_from_admin_to_doer(projet, porteur, montant_brut, palier=None, initiateur=None):
    """
    Transfert avec commission, journalisation et notification HCS complète
    """
    montant_brut = Decimal(montant_brut)

    # Commission
    commission_pct = projet.commission or Decimal("1.0")
    commission_amount = (montant_brut * commission_pct) / Decimal("100")
    montant_net = montant_brut - commission_amount

    # Transfert HBAR
    transfer_data = {
        "fromAccountId": settings.HEDERA_OPERATOR_ID,
        "fromPrivateKey": settings.HEDERA_OPERATOR_KEY,
        "toAccountId": porteur.hedera_account_id,
        "amount": float(montant_net)
    }

    try:
        response = requests.post("http://hedera_service:3001/transfer", json=transfer_data, timeout=30)
        
        if response.status_code != 200:
            logger.error(f"Erreur transfert HBAR: {response.status_code} - {response.text}")
            return {"success": False, "error": f"Erreur API HBAR: {response.status_code}"}

        data = response.json()
        transaction_hash = data.get("transactionId")

        # Journalisation en base
        transaction_admin = TransactionAdmin.objects.create(
            projet=projet,
            palier=palier, 
            montant_brut=montant_brut,
            montant_net=montant_net,
            commission=commission_amount,
            commission_pourcentage=commission_pct,
            transaction_hash=transaction_hash,
            beneficiaire=porteur,
            type_transaction="distribution",
            initiateur=initiateur 
        )

        # ✅ ENVOI HCS AVEC DÉTAILS COMPLETS
        if projet.topic_id:
            resultat_hcs = envoyer_don_hcs(
                topic_id=projet.topic_id,
                utilisateur_email=porteur.email,
                montant=montant_brut,  # Montant brut avant commission
                transaction_hash=transaction_hash,
                type_message="distribution_admin_porteur"
            )

            if resultat_hcs.get('success'):
                # Stockage HCS dans TransactionAdmin
                transaction_admin.hedera_message_id = resultat_hcs.get('messageId')
                transaction_admin.hedera_message_hashscan_url = (
                    f"https://hashscan.io/testnet/topic/{projet.topic_id}?message={resultat_hcs.get('messageId')}"
                )
                transaction_admin.save(update_fields=['hedera_message_id', 'hedera_message_hashscan_url'])
                logger.info(f"✅ Distribution {transaction_hash} tracée sur HCS")
            else:
                logger.warning(f"⚠️ HCS échoué pour {transaction_hash}")

        return {"success": True, "transactionId": transaction_hash}

    except requests.exceptions.Timeout:
        error_msg = "Timeout lors du transfert HBAR"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    except requests.exceptions.ConnectionError:
        error_msg = "Service HBAR indisponible"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    except Exception as e:
        error_msg = f"Erreur inattendue: {str(e)}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}



def envoyer_distribution_hcs(topic_id, distribution_data):
    """Envoie un message HCS spécifique pour les distributions"""
    url = "http://hedera_service:3001/send-message"
    
    message_data = {
        "type": "distribution",
        "version": "1.0",
        "timestamp": int(timezone.now().timestamp()),
        "date": timezone.now().isoformat(),
        "data": distribution_data  # Tous les détails de la distribution
    }
    
    payload = {
        "topicId": topic_id,
        "message": message_data
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        logger.info(f"Message distribution HCS envoyé: {distribution_data.get('transaction_hash')}")
        return {"success": True, "data": data, "message_id": data.get("message_id")}
        
    except requests.exceptions.ConnectionError:
        logger.error("Microservice HCS non disponible")
        return {"success": False, "error": "Service HCS indisponible"}
    
    except requests.exceptions.Timeout:
        logger.error("Timeout HCS")
        return {"success": False, "error": "Timeout service HCS"}
    
    except Exception as e:
        logger.error(f"Erreur HCS: {e}")
        return {"success": False, "error": str(e)}


def creer_paliers(projet):
    # Supprimer les paliers existants
    projet.paliers.all().delete()
    
    pourcentages = [40, 30, 30]
    for pct in pourcentages:
        montant_palier = (projet.montant_demande * Decimal(pct)) / 100
        Palier.objects.create(
            projet=projet, 
            pourcentage=Decimal(pct), 
            montant=montant_palier
        )

def verifier_paliers(projet):
    """Vérifier si les paliers peuvent être distribués"""
    montant_disponible = projet.montant_engage - projet.montant_distribue
    
    for palier in projet.paliers.order_by('montant_minimum'):
        if (montant_disponible >= palier.montant and 
            not palier.transfere and 
            palier.montant <= montant_disponible):
            
            return True  # Palier prêt à être distribué
    
    return False


def envoyer_notification_hcs(topic_id, type_notification, details):
    """Système de notification HCS complet"""
    message_data = {
        "type": type_notification,
        "timestamp": int(timezone.now().timestamp()),
        "details": details
    }
    
    payload = {
        "topicId": topic_id,
        "message": message_data
    }
    
    try:
        response = requests.post("http://hedera_service:3001/send-message", json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Erreur HCS: {e}")
        return {"success": False}


def notifier_soumission_preuve_hcs(projet, palier, nb_fichiers):
    """Notifier dans HCS la soumission de preuves d'un palier"""
    details = {
        "projet": projet.titre,
        "palier": f"{palier.pourcentage}%",
        "fichiers": nb_fichiers,
        "statut": "en_attente"
    }
    
    return envoyer_notification_hcs(
        topic_id=projet.topic_id, 
        type_notification="soumission_preuve",
        details=details
    )


def envoyer_notification_porteur(porteur, palier, action, commentaires=""):
    """Envoie une notification au porteur concernant son palier"""
    
    projet = palier.projet
    sujet = ""
    message = ""
    
    if action == 'approuve':
        sujet = f"✅ Palier {palier.pourcentage}% approuvé - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},
        
        Félicitations ! Les preuves que vous avez soumises pour le palier {palier.pourcentage}% 
        de votre projet "{projet.titre}" ont été approuvées.
        
        Montant du palier : {palier.montant} HBAR
        Prochaines étapes : Le transfert des fonds sera effectué sous peu.
        
        Cordialement,
        L'équipe SolidChain
        """
    
    elif action == 'rejete':
        sujet = f"❌ Palier {palier.pourcentage}% nécessite des modifications - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},
        
        Les preuves soumises pour le palier {palier.pourcentage}% de votre projet 
        "{projet.titre}" nécessitent des modifications.
        
        Commentaires de l'administrateur :
        {commentaires}
        
        Veuillez soumettre de nouvelles preuves en vous connectant à votre espace.
        
        Cordialement,
        L'équipe SolidChain
        """
    
    elif action == 'modification':
        sujet = f"📝 Modifications requises - Palier {palier.pourcentage}% - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},
        
        Des modifications sont requises pour les preuves du palier {palier.pourcentage}% 
        de votre projet "{projet.titre}".
        
        Retour de l'administrateur :
        {commentaires}
        
        Veuillez apporter les modifications demandées et resoumettre vos preuves.
        
        Cordialement,
        L'équipe SolidChain
        """
    
    elif action == 'distribution':
        # Récupérer l'URL d'exploration de la transaction
        transaction_url = f"https://hashscan.io/testnet/transaction/{palier.transaction_hash}"
        
        sujet = f"💰 Transfert effectué - Palier {palier.pourcentage}% - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},
        
        Le transfert du palier {palier.pourcentage}% de votre projet "{projet.titre}" 
        a été effectué avec succès.
        
        📊 DÉTAILS DU TRANSFERT :
        • Montant transféré : {palier.montant} HBAR
        • Date du transfert : {timezone.now().strftime('%d/%m/%Y à %H:%M')}
        • Hash de transaction : {palier.transaction_hash}
        • Lien de vérification : {transaction_url}
        
        🔍 Vous pouvez vérifier la transaction sur HashScan :
        {transaction_url}
        
        Le montant a été crédité sur votre compte Hedera associé au projet.
        
        
        
        Cordialement,
        L'équipe SolidChain
        """
    
    # Envoi par email
    try:
        porteur.email_user(sujet, message)
        logger.info(f"Notification envoyée à {porteur.email} pour le palier {palier.id}")
    except Exception as e:
        logger.error(f"Erreur envoi email à {porteur.email}: {str(e)}")
    
    # Notification HCS
    try:
        envoyer_don_hcs(
            topic_id=projet.topic_id,
            utilisateur_email=porteur.email,
            montant=palier.montant if action == 'distribution' else 0,
            transaction_hash=palier.transaction_hash if action == 'distribution' else "",
            type_message=f"notification_{action}"
        )
    except Exception as e:
        logger.error(f"Erreur notification HCS: {str(e)}")


def determiner_type_fichier(nom_fichier):
    """Détermine le type de fichier basé sur l'extension"""
    extension = os.path.splitext(nom_fichier)[1].lower()
    
    # Images
    images = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg']
    if extension in images:
        return 'photo'
    
    # Vidéos
    videos = ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm', '.mkv']
    if extension in videos:
        return 'video'
    
    # Documents
    documents = [
        '.pdf', '.doc', '.docx', '.txt', '.rtf', 
        '.xls', '.xlsx', '.ppt', '.pptx', '.odt'
    ]
    if extension in documents:
        return 'document'
    
    return 'autre'

# Version alternative avec vérification MIME type
def determiner_type_fichier_avance(fichier):
    """Détermine le type de fichier avec vérification MIME"""
    nom_fichier = fichier.name
    
    # Vérification par extension (méthode simple)
    type_simple = determiner_type_fichier(nom_fichier)
    
    # Vérification MIME type (plus fiable)
    mime = MimeTypes()
    mime_type, _ = mime.guess_type(nom_fichier)
    
    if mime_type:
        if mime_type.startswith('image/'):
            return 'photo'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('application/'):
            return 'document'
    
    return type_simple

@login_required
def liste_topics(request):
    projets = Projet.objects.exclude(topic_id__isnull=True).exclude(topic_id__exact="")

    context = {
        "projets": projets,
    }
    return render(request, "core/site/liste_topics.html", context)


@login_required
def topic_detail(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)

    if not projet.topic_id:
        messages.warning(request, "Ce projet n’a pas encore de topic Hedera.")
        return redirect("liste_topics")

    messages_topic = projet.messages.all()
    context = {
        "projet": projet,
        "messages_topic": messages_topic,
    }
    return render(request, "core/site/topic_detail.html", context)
