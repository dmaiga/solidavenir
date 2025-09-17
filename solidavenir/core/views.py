# Standard library
import logging
from datetime import timedelta
from urllib.parse import urlencode

# Django imports
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.forms import PasswordChangeForm
from django.http import JsonResponse, HttpResponseForbidden, HttpResponseRedirect
from django.db import transaction as db_transaction
from django.db.models import Sum, Count, Q, Avg, Max, Min, DecimalField
from django.db.models.functions import Coalesce, TruncMonth
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from django.contrib.humanize.templatetags.humanize import intcomma

# Local apps imports
from .models import Projet, Transaction, User, AuditLog, Association
from .forms import (
    InscriptionFormSimplifiee, CreationProjetForm, ValidationProjetForm,
    ProfilUtilisateurForm, ContactForm, Transfer_fond, AssociationForm
)



def about(request):
    return render(request, 'core/site/about.html')

def savoir_plus(request):
    return render(request, 'core/site/savoir_plus.html')
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

@csrf_protect
def connexion(request):
    """Page de connexion"""
    if request.user.is_authenticated:
        messages.info(request, "Vous êtes déjà connecté.")
        return redirect('accueil')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        remember_me = request.POST.get('remember_me')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Journalisation audit
            AuditLog.objects.create(
                utilisateur=user,
                action='login',
                modele='User',
                objet_id=str(user.audit_uuid),
                details={'method': 'form', 'remember_me': bool(remember_me)},
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            # Gestion de "Remember me"
            if not remember_me:
                # Session expire à la fermeture du navigateur
                request.session.set_expiry(0)
            else:
                # Session expire après 30 jours
                request.session.set_expiry(60 * 60 * 24 * 30)
            
            messages.success(request, f"Bienvenue {user.username} !")
            
            # Redirection après connexion
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


def accueil(request):
    """Page d'accueil avec projets populaires et statistiques"""
    # Récupérer les projets actifs les plus populaires
    projets_populaires = Projet.objects.filter(
        statut='actif'
    ).annotate(
        total_collecte=Sum('transaction__montant', filter=Q(transaction__statut='confirme'))
    ).order_by('-total_collecte')[:3]
    
    # Statistiques globales
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
from django.db import transaction 



@login_required
def mes_projets(request):
    """Liste des projets de l'utilisateur connecté avec statistiques"""
    
    
    # Récupérer tous les projets du porteur avec annotations
    projets = Projet.objects.filter(porteur=request.user).annotate(
        nombre_donateurs=Count('transaction__contributeur', filter=Q(transaction__statut='confirme'), distinct=True),
        derniere_transaction=Max('transaction__date_transaction', filter=Q(transaction__statut='confirme'))
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


def transparence(request):
    """Page de transparence avec toutes les transactions vérifiables et statistiques détaillées"""
    # Filtres possibles
    projet_filter = request.GET.get('projet')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    # Transactions confirmées avec relations
    transactions = Transaction.objects.filter(statut='confirme').select_related(
        'projet', 'contributeur', 'verifie_par'
    ).order_by('-date_transaction')
    
    # Appliquer les filtres
    if projet_filter:
        transactions = transactions.filter(projet__audit_uuid=projet_filter)
    
    if date_debut:
        try:
            date_debut = timezone.datetime.strptime(date_debut, '%Y-%m-%d').date()
            transactions = transactions.filter(date_transaction__date__gte=date_debut)
        except ValueError:
            pass
    
    if date_fin:
        try:
            date_fin = timezone.datetime.strptime(date_fin, '%Y-%m-%d').date()
            transactions = transactions.filter(date_transaction__date__lte=date_fin)
        except ValueError:
            pass
    
    # Statistiques détaillées
    stats = {
        'total_dons': transactions.aggregate(total=Sum('montant'))['total'] or 0,
        'total_transactions': transactions.count(),
        'projets_finances': transactions.values('projet').distinct().count(),
        'donateurs_uniques': transactions.values('contributeur').distinct().count(),
        'moyenne_don': transactions.aggregate(moyenne=Avg('montant'))['moyenne'] or 0,
    }
    
    # Top projets par montant collecté
    top_projets = Projet.objects.filter(
        transaction__statut='confirme'
    ).annotate(
        total_collecte=Sum('transaction__montant'),
        nombre_dons=Count('transaction')
    ).order_by('-total_collecte')[:5]
    
    # Top donateurs
    top_donateurs = User.objects.filter(
        transaction__statut='confirme'
    ).annotate(
        total_dons=Sum('transaction__montant'),
        nombre_dons=Count('transaction')
    ).order_by('-total_dons')[:5]
    
    # Évolution mensuelle des dons - Méthode compatible avec tous les SGBD
    donations_mensuelles = Transaction.objects.filter(
        statut='confirme',
        date_transaction__gte=timezone.now() - timedelta(days=365)
    ).annotate(
        mois=TruncMonth('date_transaction')
    ).values('mois').annotate(
        total=Sum('montant'),
        count=Count('id')
    ).order_by('mois')
    
    # Projets disponibles pour le filtre
    projets_actifs = Projet.objects.filter(statut='actif').values('audit_uuid', 'titre')
    
    # Pagination
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



from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactForm
from .models import ContactSubmission

def contact(request):
    """Page de contact"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Créer l'instance du modèle mais ne pas sauvegarder tout de suite
            submission = form.save(commit=False)
            # Vous pouvez ajouter des informations supplémentaires ici si nécessaire
            submission.save()  # Sauvegarder dans la base de données
            
            # Ici vous pourriez également envoyer un email
            messages.success(request, "Votre message a été envoyé avec succès!")
            return redirect('contact')
    else:
        form = ContactForm()
    
    return render(request, 'core/site/contact.html', {'form': form})

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

def detail_projet(request, audit_uuid):
    """Détail d'un projet spécifique avec possibilité de contribution"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    # Compter les contributeurs distincts
    contributeurs_count = Transaction.objects.filter(
        projet=projet, 
        statut='confirme'
    ).values('contributeur').distinct().count()
    
    # Récupérer les niveaux de financement si le projet en a
    recompenses = None
    if projet.has_recompenses and projet.recompenses_description:
        recompenses = projet.recompenses_description
    
    # Vérifier si l'utilisateur peut voir le projet (créateur ou staff)
    user_can_preview = (
        request.user == projet.porteur or  # Créateur du projet
        request.user.is_staff or           # Staff/admin
        hasattr(request.user, 'association_profile') and request.user.association_profile == projet.association  # Association propriétaire
    )
    
    # Seuls les projets actifs ou terminés sont visibles par le public
    # Mais permettre le preview au créateur et au staff même si le projet n'est pas actif
    if projet.statut not in ['actif', 'termine'] and not user_can_preview:
        messages.error(request, "Ce projet n'est pas accessible.")
        return redirect('liste_projets')
    
    # Récupérer des projets similaires (seulement pour les projets actifs)
    projets_similaires = Projet.objects.filter(statut='actif').exclude(audit_uuid=audit_uuid)[:3]
    
    transactions = Transaction.objects.filter(projet=projet, statut='confirme').order_by('-date_transaction')[:5]
    
    # Vérifier si l'utilisateur a un wallet configuré
    user_has_wallet = False
    if request.user.is_authenticated:
        # Vérifier si l'utilisateur a un wallet configuré dans son profil
        user_has_wallet = hasattr(request.user, 'hedera_account_id') and request.user.hedera_account_id
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, "Connectez-vous pour contribuer.")
            return redirect(f"{reverse('connexion')}?{urlencode({'next': request.path})}")
        
        # Les administrateurs ne peuvent pas effectuer de contributions
        if request.user.user_type == 'admin':
            messages.error(request, "Les administrateurs ne peuvent pas effectuer de contributions.")
            return redirect('detail_projet', audit_uuid=audit_uuid)
        
        # Empêcher les contributions si le projet n'est pas actif
        if projet.statut != 'actif':
            messages.error(request, "Les contributions ne sont pas autorisées pour ce projet actuellement.")
            return redirect('detail_projet', audit_uuid=audit_uuid)
        
        # Vérifier si l'utilisateur a un wallet configuré
        if not user_has_wallet:
            messages.info(request, "Veuillez configurer votre wallet pour effectuer une contribution.")
            # Rediriger vers la page de configuration du wallet (à développer)
            return redirect('configurer_wallet')
        
    else:
        form = Transfer_fond(projet=projet, contributeur=request.user if request.user.is_authenticated else None)
    
    can_edit = projet.peut_etre_modifie_par(request.user)
    
    # Déterminer si c'est un preview (projet non actif mais visible par le créateur/staff)
    is_preview = projet.statut not in ['actif', 'termine'] and user_can_preview
    return render(request, 'core/projets/detail_projet.html', {
        'projet': projet,
        
        'transactions': transactions,
        'contributeurs_count': contributeurs_count,
        'form': form,
        'projets_similaires': projets_similaires,
        'pourcentage': projet.pourcentage_financement,
        'user_has_wallet': user_has_wallet, 
        'recompenses': recompenses,
        'can_edit': can_edit,
        'is_preview': is_preview,
    })

def configurer_wallet(request):
    """Vue temporaire pour la configuration du wallet"""
    messages.info(request, "La fonctionnalité de configuration du wallet sera bientôt disponible.")
    return redirect('profil')

import requests

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
                        
                        response = requests.post("http://localhost:3001/create-wallet", timeout=10)
                        if response.status_code == 200:
                            data = response.json()
                            projet.hedera_account_id = data.get("accountId")
                            projet.hedera_private_key = data.get("privateKey")
                        else:
                            raise Exception("Échec de création wallet Hedera")
                    except Exception as e:
                        logger.error(f"Erreur wallet Hedera: {str(e)}")
                        messages.error(request, "Le projet a été créé mais sans compte Hedera.")
                    
                    projet.save()

                    # Journalisation
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
                            'association': str(projet.association.id) if projet.association else None
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


@login_required
def profil(request):
    """Page de profil utilisateur"""
    
    # Récupérer le solde Hedera si le wallet est configuré
    solde = None
    if request.user.hedera_account_id:
        try:
            response = requests.get(
                f'http://localhost:3001/balance/{request.user.hedera_account_id}',
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
from .forms import FiltreMembresForm, FiltreTransactionsForm, FiltreAuditForm


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
@permission_required('core.view_dashboard', raise_exception=True)
def liste_transactions_validation(request):
    """Liste des transactions à vérifier avec filtres"""
    transactions = Transaction.objects.filter(
        statut='en_attente'
    ).select_related('contributeur', 'projet').order_by('-date_transaction')
    
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


logger = logging.getLogger(__name__)

@login_required
@permission_required('core.validate_project', raise_exception=True)
def valider_projet(request, audit_uuid):
    """Validation d'un projet par un administrateur avec gestion complète"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    # Vérifier que le projet est en attente de validation
    if projet.statut not in ['en_attente', 'brouillon']:
        messages.warning(request, f"Ce projet est déjà {projet.get_statut_display().lower()}.")
        return redirect('tableau_de_bord')  # Redirection vers une vue existante
    
    
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
                
                # Créer un topic Hedera pour la traçabilité
                try:
                        if not projet.hedera_topic_id:
                            hedera_service = HederaService()
                            topic_id = hedera_service.creer_topic(projet.titre)
                            projet.hedera_topic_id = topic_id

                            # Journalisation création topic
                            AuditLog.objects.create(
                                utilisateur=request.user,
                                action='create',
                                modele='HederaTopic',
                                objet_id=topic_id,
                                details={'projet': projet.titre},
                                adresse_ip=request.META.get('REMOTE_ADDR')
                            )

                            messages.info(request, f"Topic Hedera créé: {topic_id}")
                except Exception as e:
                        logger.error(f"Erreur création topic Hedera: {str(e)}")
                        messages.warning(request, "Erreur lors de la création du topic Hedera, mais le projet a été validé.")
            elif nouveau_statut == 'rejete':
                projet.valide_par = request.user
                projet.date_validation = None
                
                # Envoyer un email au porteur en cas de rejet
                try:
                    send_mail(
                        f'Votre projet "{projet.titre}" a été examiné - Solid\'Avenir',
                        f'Bonjour {projet.porteur.get_full_name() or projet.porteur.username},\n\n'
                        f'Votre projet "{projet.titre}" a été examiné par notre équipe.\n'
                        f'Statut: Rejeté\n'
                        f'Raison: {form.cleaned_data.get("commentaire_validation", "Non spécifiée")}\n\n'
                        f'Vous pouvez modifier votre projet et le soumettre à nouveau.\n\n'
                        f'Cordialement,\nL\'équipe Solid\'Avenir',
                        settings.DEFAULT_FROM_EMAIL,
                        [projet.porteur.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(f"Erreur envoi email rejet: {str(e)}")
            
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
                    'commentaire': form.cleaned_data.get('commentaire_validation', '')
                },
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            # Envoyer une notification au porteur pour validation
            if nouveau_statut == 'actif':
                try:
                    send_mail(
                        f'Félicitations ! Votre projet "{projet.titre}" est actif - Solid\'Avenir',
                        f'Bonjour {projet.porteur.get_full_name() or projet.porteur.username},\n\n'
                        f'Votre projet "{projet.titre}" a été validé et est maintenant actif sur notre plateforme.\n'
                        f'Montant demandé: {projet.montant_demande:,} FCFA\n\n'
                        f'Vous pouvez maintenant partager votre projet et commencer à collecter des fonds.\n\n'
                        f'Cordialement,\nL\'équipe Solid\'Avenir',
                        settings.DEFAULT_FROM_EMAIL,
                        [projet.porteur.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(f"Erreur envoi email validation: {str(e)}")
            
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
def tableau_de_bord(request):
    """Tableau de bord administrateur complet avec statistiques détaillées"""
    if not request.user.is_administrator():
        messages.error(request, "Accès réservé aux administrateurs.")
        return redirect('accueil')
    
    # Date pour les filtres
    aujourdhui = timezone.now().date()
    debut_semaine = aujourdhui - timedelta(days=aujourdhui.weekday())
    debut_mois = aujourdhui.replace(day=1)
    
    # Statistiques principales
    stats = {
        # Projets
        'projets_total': Projet.objects.count(),
        'projets_actifs': Projet.objects.filter(statut='actif').count(),
        'projets_attente': Projet.objects.filter(statut='en_attente').count(),
        'projets_brouillon': Projet.objects.filter(statut='brouillon').count(),
        'projets_termines': Projet.objects.filter(statut='termine').count(),
        
        # Utilisateurs
        'utilisateurs_total': User.objects.count(),
        'association_total': User.objects.filter(user_type='association').count(),
        'porteurs_total': User.objects.filter(user_type='porteur').count(),
        'investisseur_total': User.objects.filter(user_type='investisseur').count(),
        'donateurs_total': User.objects.filter(user_type='donateur').count(),
        'admins_total': User.objects.filter(user_type='admin').count(),
        
        # Transactions
        'transactions_total': Transaction.objects.count(),
        'transactions_confirmees': Transaction.objects.filter(statut='confirme').count(),
        'transactions_attente': Transaction.objects.filter(statut='en_attente').count(),
        
        # Montants
        'montant_total': Transaction.objects.filter(statut='confirme').aggregate(
            Sum('montant'))['montant__sum'] or 0,
        'montant_jour': Transaction.objects.filter(
            date_transaction__date=aujourdhui,
            statut='confirme'
        ).aggregate(Sum('montant'))['montant__sum'] or 0,
        'montant_semaine': Transaction.objects.filter(
            date_transaction__date__gte=debut_semaine,
            statut='confirme'
        ).aggregate(Sum('montant'))['montant__sum'] or 0,
        'montant_mois': Transaction.objects.filter(
            date_transaction__date__gte=debut_mois,
            statut='confirme'
        ).aggregate(Sum('montant'))['montant__sum'] or 0,
        
        # Dons
        'dons_jour': Transaction.objects.filter(
            date_transaction__date=aujourdhui,
            statut='confirme'
        ).count(),
        'dons_semaine': Transaction.objects.filter(
            date_transaction__date__gte=debut_semaine,
            statut='confirme'
        ).count(),
        'dons_mois': Transaction.objects.filter(
            date_transaction__date__gte=debut_mois,
            statut='confirme'
        ).count(),
    }
    
    # Données pour les graphiques
    # Répartition des projets par statut
    projets_par_statut = Projet.objects.values('statut').annotate(
        count=Count('id')
    ).order_by('statut')
    
    # Évolution des dons sur les 30 derniers jours
    derniers_30_jours = [aujourdhui - timedelta(days=i) for i in range(29, -1, -1)]
    dons_par_jour = Transaction.objects.filter(
        date_transaction__date__gte=aujourdhui - timedelta(days=29),
        statut='confirme'
    ).values('date_transaction__date').annotate(
        total=Sum('montant'),
        count=Count('id')
    ).order_by('date_transaction__date')
    
    # Préparer les données pour le graphique
    donnees_graphique = {
        'labels': [date.strftime('%d/%m') for date in derniers_30_jours],
        'montants': [0] * 30,
        'nombre_dons': [0] * 30
    }
    
    for don in dons_par_jour:
        date_str = don['date_transaction__date'].strftime('%d/%m')
        if date_str in donnees_graphique['labels']:
            index = donnees_graphique['labels'].index(date_str)
            donnees_graphique['montants'][index] = float(don['total'])
            donnees_graphique['nombre_dons'][index] = don['count']
    
    # Projets nécessitant une attention
    projets_attention = Projet.objects.filter(
        statut='en_attente'
    ).select_related('porteur').order_by('date_creation')[:5]
    
    # Dernières transactions pour audit
    recent_transactions = Transaction.objects.select_related(
        'projet', 'contributeur'
    ).order_by('-date_transaction')[:5]
    
    # Derniers logs d'audit
    recent_audits = AuditLog.objects.select_related(
        'utilisateur'
    ).order_by('-date_action')[:5]
    
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
    ).order_by('-montant_collecte')[:5]
    
 # ASSOCIATIONS EN ATTENTE DE VALIDATION (NOUVEAU)
    associations_attente = Association.objects.filter(
        valide=False
    ).select_related('user').order_by('date_creation_association')[:5]
    
    # Statistiques associations (NOUVEAU)
    stats_associations = {
        'associations_total': Association.objects.count(),
        'associations_validees': Association.objects.filter(valide=True).count(),
        'associations_attente': Association.objects.filter(valide=False).count(),
        'associations_vedette': Association.objects.filter(featured=True, valide=True).count(),
    }
    
    context = {
        'stats': stats,
        'projets_par_statut': list(projets_par_statut),
        'donnees_graphique': donnees_graphique,
        'projets_attention': projets_attention,
        'recent_transactions': recent_transactions,
        'recent_audits': recent_audits,
        'top_donateurs': top_donateurs,
        'projets_populaires': projets_populaires,
        'aujourdhui': aujourdhui,
        
        # NOUVEAUX: Données associations
        'associations_attente': associations_attente,
        'stats_associations': stats_associations,
    }
    
    return render(request, 'core/admin/tableau_de_bord.html', context)



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

def calculer_taux_reussite(projets_queryset):
    """Calcule le taux de réussite des projets terminés"""
    projets_termines = projets_queryset.filter(statut__in=['termine', 'echec'])
    if not projets_termines.exists():
        return 0
    
    reussis = projets_termines.filter(statut='termine').count()
    return round((reussis / projets_termines.count()) * 100, 1)



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

# Fonction utilitaire pour récupérer l'IP
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


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


logger = logging.getLogger(__name__)

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
                    
            elif nouveau_statut == 'rejete':
                projet.valide_par = request.user
                projet.date_validation = None
                
                # Envoyer un email au porteur en cas de rejet
                try:
                    # Envoi d'email via le backend Django configuré
                    send_mail(
                        f'Votre projet "{projet.titre}" a été examiné - Solid\'Avenir',
                        f'Bonjour {projet.porteur.get_full_name() or projet.porteur.username},\n\n'
                        f'Votre projet "{projet.titre}" a été examiné par notre équipe.\n'
                        f'Statut: Rejeté\n'
                        f'Raison: {form.cleaned_data.get("commentaire_validation", "Non spécifiée")}\n\n'
                        f'Vous pouvez modifier votre projet et le soumettre à nouveau.\n\n'
                        f'Cordialement,\nL\'équipe Solid\'Avenir',
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
                    'commentaire': form.cleaned_data.get('commentaire_validation', '')
                },
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            # Envoyer une notification au porteur pour validation
            if nouveau_statut == 'actif':
                try:
                    # Envoi d'email via le backend Django configuré
                    send_mail(
                        f'Félicitations ! Votre projet "{projet.titre}" est actif - Solid\'Avenir',
                        f'Bonjour {projet.porteur.get_full_name() or projet.porteur.username},\n\n'
                        f'Votre projet "{projet.titre}" a été validé et est maintenant actif sur notre plateforme.\n'
                        f'Montant demandé: {projet.montant_demande:,} FCFA\n\n'
                        f'Vous pouvez maintenant partager votre projet et commencer à collecter des fonds.\n\n'
                        f'Cordialement,\nL\'équipe Solid\'Avenir',
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



from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import EmailFormSimple
from .models import EmailLog
from django.core.mail import send_mail
from django.conf import settings

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


import requests
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings

from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.shortcuts import redirect
import requests

def get_hbar_to_fcfa():
    """Retourne le prix actuel de 1 HBAR en USD (USD)"""
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "hedera-hashgraph", "vs_currencies": "usd"},
            timeout=10
        )
        data = response.json()
        return data["hedera-hashgraph"]["usd"]
    except Exception as e:
        print(f"Erreur conversion HBAR-FCFA: {e}")
        return None


def convert_fcfa_to_hbar(fcfa_amount):
    """Convertit un montant FCFA en HBAR"""
    rate = get_hbar_to_fcfa()
    if not rate:
        raise ValueError("Impossible de récupérer le taux de conversion")
    return fcfa_amount / rate



@csrf_exempt
def process_donation(request, project_id):
    if request.method == 'POST':
        try:
            amount = request.POST.get('amount')
            user = request.user
            project = Projet.objects.get(id=project_id)

            transfer_data = {
                'fromAccountId': user.hedera_account_id,
                'fromPrivateKey': user.hedera_private_key,
                'toAccountId': project.hedera_account_id,
                'amount': float(amount)
            }

            response = requests.post('http://localhost:3001/transfer', json=transfer_data, timeout=30)

            if response.status_code == 200:
                result = response.json()

                transaction = Transaction.objects.create(
                    user=user,
                    montant=amount,
                    hedera_transaction_hash=result['transactionId'],
                    contributeur=user,
                    projet=project,
                    statut='confirme' if result['success'] else 'erreur'
                )

                # Mettre à jour le montant collecté du projet
                if transaction.statut == 'confirme':
                    project.montant_collecte = (
                        project.transaction_set.filter(statut='confirme')
                        .aggregate(total=Sum('montant'))['total'] or 0
                    )
                    project.save(update_fields=['montant_collecte'])

                messages.success(request, f"Votre don de {amount} HBAR a bien été effectué ✅")
                return redirect('detail_projet', audit_uuid=project.audit_uuid)

            else:
                messages.error(request, "Erreur lors du transfert ❌")
                return redirect('detail_projet', audit_uuid=project.audit_uuid)

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('detail_projet', audit_uuid=project.audit_uuid)

    messages.warning(request, "Méthode non autorisée")
    return redirect('detail_projet', audit_uuid=project.audit_uuid)


def voir_wallet(request):
    if not request.user.is_authenticated:
        return redirect('login')
    
    # S'assurer que l'utilisateur a un wallet
    request.user.ensure_wallet()
    
    # Obtenir le solde actuel
    solde = None
    try:
        response = requests.get(
            f'http://localhost:3001/balance/{request.user.hedera_account_id}',
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