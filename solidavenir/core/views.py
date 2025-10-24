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
from django.db.models.functions import Coalesce, TruncMonth,TruncDate
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
    InscriptionFormSimplifiee, CreationProjetForm,AjoutImagesProjetForm, ValidationProjetForm,
    ProfilUtilisateurForm, ContactForm, Transfer_fond, AssociationForm,
    FiltreMembresForm, FiltreTransactionsForm, FiltreAuditForm,
    EmailFormSimple, PreuveForm, VerificationPreuveForm,PalierForm,TransferDirectForm
)
from .utils import safe_float, safe_int, safe_decimal

# associations/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Association, AssociationImage
from .forms import AssociationImageForm

logger = logging.getLogger(__name__)

# views.py
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse

@csrf_exempt
def clear_session_messages(request):
    """Nettoyer les messages de session après affichage"""
    if 'swal' in request.session:
        del request.session['swal']
    if 'form_errors' in request.session:
        del request.session['form_errors']
    request.session.modified = True
    return JsonResponse({'status': 'cleared'})
#
#   SITE
#
def accueil(request):
    
    """Homepage with popular projects and statistics"""
    """Page d'accueil avec projets populaires et statistiques"""
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
    """About page"""
    """Page À propos"""
    
    return render(request, 'core/site/about.html')

def savoir_plus(request):
    """Learn more page"""
    """Page En savoir plus"""
    return render(request, 'core/site/savoir_plus.html')

def policy_view(request):
    context = {
        'title': 'Project Policy - Solid\'Avenir',
        'description': 'Discover our governance model based on four fundamental pillars: verification, transparency, fund distribution, and data protection.'
    }
    return render(request, 'core/site/policy.html', context)

def contact(request):
    """Contact page"""
    """Page de contact"""
    
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            submission = form.save(commit=False)
            submission.save()  
            messages.success(request, "Your message has been sent successfully!")

            return redirect('contact')
    else:
        form = ContactForm()
    
    return render(request, 'core/site/contact.html', {'form': form})

def transparence(request):
    """
    Render the transparency dashboard for donations and administrative transactions.
    """
    projet_filter = request.GET.get('projet')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    # Transactions (dons) ordered by date only, newest date first
    transactions = (
        Transaction.objects.filter(statut='confirme')
        .select_related('projet', 'contributeur', 'verifie_par')
        .order_by('-date_transaction')
    )

    # Transactions admin – most recent first
    transactions_admin = (
        TransactionAdmin.objects
        .select_related('projet', 'beneficiaire', 'initiateur')
        .order_by('-date_creation')
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
    total_dons = transactions.aggregate(total=Sum('montant'))['total'] or 0
    total_distributions = transactions_admin.aggregate(total=Sum('montant_net'))['total'] or 0
    total_commissions = transactions_admin.filter(type_transaction__in=['distribution', 'commission']).aggregate(total=Sum('commission'))['total'] or 0
    moyenne_don = transactions.aggregate(moyenne=Avg('montant'))['moyenne'] or 0

    stats = {
        'total_dons': f"{total_dons:.2f}",
        'total_transactions': transactions.count(),
        'total_distributions': f"{total_distributions:.2f}",
        'total_commissions': f"{total_commissions:.2f}",
        'projets_finances': transactions.values('projet').distinct().count(),
        'donateurs_uniques': transactions.values('contributeur').distinct().count(),
        'moyenne_don': f"{moyenne_don:.2f}",
    }

    # --- CORRECTION: Top projets et donateurs ---
    # Utilisez 'transaction' (au singulier) comme indiqué dans l'erreur
    top_projets = Projet.objects.filter(transaction__statut='confirme').annotate(
        total_collecte=Sum('transaction__montant'),
        nombre_dons=Count('transaction')
    ).order_by('-total_collecte')[:5]

    # Utilisez 'contributions' (le related_name que vous avez défini)
    top_donateurs = User.objects.filter(contributions__statut='confirme').annotate(
        total_dons=Sum('contributions__montant'),
        nombre_dons=Count('contributions')
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
        'transactions_admin': transactions_admin,  
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
    """
    Historique des contributions et transferts de l'utilisateur connecté
    """
    # Récupère toutes les transactions où l'utilisateur est contributeur
    contributions = Transaction.objects.filter(
        contributeur=request.user
    ).select_related('projet', 'association').order_by('-date_transaction')
    
    total_contributions = sum(contrib.montant for contrib in contributions)
    
    # Statistiques par projet (uniquement les dons aux projets)
    projets_stats = Transaction.objects.filter(
        contributeur=request.user, 
        statut='confirme',
        projet__isnull=False
    ).values(
        'projet__titre'
    ).annotate(
        total=Sum('montant')
    ).order_by('-total')
    
    # Statistiques par association (transferts directs)
    associations_stats = Transaction.objects.filter(
        contributeur=request.user,
        statut='confirme', 
        association__isnull=False
    ).values(
        'association__nom'
    ).annotate(
        total=Sum('montant')
    ).order_by('-total')
    
    # Contributions mensuelles (6 derniers mois)
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
        'associations_count': associations_stats.count(),
        'associations_stats': associations_stats,
        'contributions_mensuelles': contributions_mensuelles,
    }
    
    return render(request, 'core/site/mes_dons.html', context)
#===========
# END SITE
#===========
#-----------------------------------
#users
#===================================

def inscription(request):
    """
    Handle simplified user registration with smooth error display
    """
    # Rediriger les utilisateurs déjà connectés
    if request.user.is_authenticated:
        request.session['swal'] = {
            'icon': 'info',
            'title': 'Déjà connecté',
            'text': 'Vous êtes déjà connecté à votre compte.',
            'timer': 3000
        }
        return redirect('accueil')
    
    if request.method == 'POST':
        form = InscriptionFormSimplifiee(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                
                # Connexion automatique
                login(request, user)
                
                # Message de bienvenue smooth
                user_type_display = dict(User.USER_TYPES).get(user.user_type, 'utilisateur')
                request.session['swal'] = {
                    'icon': 'success',
                    'title': f'Bienvenue {user.first_name or user.username}!',
                    'text': f'Votre compte {user_type_display} a été créé avec succès.',
                    'timer': 4000,
                    'showConfirmButton': False
                }
                
                # Redirection selon le type d'utilisateur
                if user.user_type == 'association':
                    return redirect('espace_association')
                else:
                    return redirect('accueil')
                
            except Exception as e:
                # Erreur smooth pour les problèmes techniques
                request.session['swal'] = {
                    'icon': 'error',
                    'title': 'Erreur technique',
                    'text': 'Une erreur est survenue lors de la création du compte. Veuillez réessayer.',
                    'timer': 5000
                }
                logger.error(f"Erreur inscription: {str(e)}")
                logger.exception("Détails de l'erreur d'inscription:")
        else:
            # Stocker les erreurs pour l'affichage smooth
            errors_list = []
            for field, errors in form.errors.items():
                field_label = form.fields[field].label if field in form.fields else field.replace('_', ' ').title()
                for error in errors:
                    errors_list.append(f"{field_label}: {error}")
            
            # Message d'erreur consolidé
            if errors_list:
                request.session['form_errors'] = errors_list
    
    else:
        form = InscriptionFormSimplifiee()
    
    user_types_without_admin = [choice for choice in User.USER_TYPES if choice[0] != 'admin']
    
    context = {
        'form': form,
        'user_types': user_types_without_admin,
        'title': 'Rejoignez notre communauté solidaire',
        'description': 'Une plateforme transparente pour financer des projets qui changent le monde'
    }
    
    return render(request, 'core/users/inscription.html', context)

from django.contrib.auth import get_user_model

@csrf_exempt
def connexion(request):
    """
    Handle user login page and authentication.

    Functionality:
        - Redirects already authenticated users to the dashboard (admin) or homepage (regular users).
        - Accepts login via username or email.
        - Authenticates the user and logs them in if credentials are valid.
        - Creates an audit log for successful logins, including IP address and login method.
        - Supports "remember me" functionality: sets session expiry accordingly.
        - Redirects users based on type (admin → dashboard, others → homepage) or `next` URL parameter.
        - Displays error message if authentication fails.

    Template used:
        'core/users/connexion.html'

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Rendered login page or redirect to appropriate URL.
    """
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
            # Message d'erreur amélioré
            messages.error(request, "Invalid username/email or password. Please check your credentials and try again.")
    
    return render(request, 'core/users/connexion.html')

@login_required
def deconnexion(request):
    """
    Log out the currently authenticated user.

    Functionality:
        - Records a logout event in the AuditLog, including the user's audit UUID and IP address.
        - Logs the user out of the session.
        - Displays a success message confirming the logout.
        - Redirects the user to the homepage.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Redirects to the homepage after logout.
    """
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
    
    return redirect('accueil')

@login_required
def changer_mot_de_passe(request):
    """
    Allow the currently authenticated user to change their password.

    Functionality:
        - Displays a password change form.
        - Validates and saves the new password if the form is valid.
        - Updates the session to keep the user logged in after password change.
        - Logs the password change action in the AuditLog, including the user's audit UUID and IP address.
        - Displays a success message upon successful password change.
        - Redirects the user to the homepage after the password is changed.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the password change page or redirects after a successful update.
    """

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
            
            messages.success(request, "Your password has been changed successfully.")

            return redirect('accueil')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'core/users/changer_mot_de_passe.html', {'form': form})


@login_required
def modifier_profil(request):
    """
    Allow the currently authenticated user to update their profile information, including profile photo.

    Functionality:
        - Displays a profile edit form pre-filled with the user's current data.
        - Supports updating profile fields and uploading a new profile picture.
        - Validates and saves the form data if valid.
        - Logs all modified fields in the AuditLog along with the user's audit UUID, user type, and IP address.
        - Displays a success message upon successful update.
        - Redirects back to the profile edit page after saving.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the profile edit page with the form and profile completion status.
    """

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
            
            messages.success(request, "Your profile has been updated successfully.")

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
    """
    Display the profile page of the currently authenticated user with personalized information.

    Functionality:
        - Retrieves the user's Hedera wallet balance if the account ID is configured.
        - Displays user-specific statistics:
            - For contributors: number of confirmed donations and number of supported projects.
            - For project owners: number of projects and total amount collected.
        - Shows the user's recent activity (last 30 days) from the AuditLog.
        - Handles any errors in retrieving Hedera balance gracefully.
        - Renders the profile template with all relevant context data.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders 'core/users/profil.html' with user info, wallet balance, statistics, and recent activities.
    """

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


#===================
# END SITE
#===================

#===================
# ASSOCIATION
#===================


def liste_associations(request):
    """
    Display a list of all validated associations with optional filtering and statistics.

    Functionality:
        - Retrieves associations that are validated (valide=True).
        - Applies optional filters based on:
            - Main domain of activity (`domaine`)
            - City (`ville`)
            - Search query matching name, short description, or supported causes (`recherche`)
        - Computes general statistics:
            - Total number of members across filtered associations.
            - Total number of active projects across filtered associations.
            - Number of distinct cities represented.
        - Separates associations into featured and non-featured for display.
        - Passes all relevant data to the template context.

    Args:
        request (HttpRequest): The HTTP request object, which may contain GET parameters for filtering.

    Returns:
        HttpResponse: Renders 'core/associations/liste_associations.html' with filtered associations, statistics, and featured highlights.
    """

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
    """
    Display the details of a single validated association.

    Functionality:
        - Retrieves the association identified by the given slug, ensuring it is validated.
        - Fetches the association's active projects for display.
        - Passes the association and its active projects to the template context.

    Args:
        request (HttpRequest): The HTTP request object.
        slug (str): The unique slug identifying the association.

    Returns:
        HttpResponse: Renders 'core/associations/detail_association.html' with the association's details and active projects.
    """

    """Détail d'une association"""
    association = get_object_or_404(Association, slug=slug, valide=True)
    est_membre = False
    if request.user.is_authenticated:
        est_membre = association.est_membre(request.user)
    context = {
        'association': association,
        'est_membre': est_membre,
        'projets_actifs': association.get_projets_actifs(),
        'quatre_images': association.quatre_dernieres_images,
    }
    return render(request, 'core/associations/detail_association.html', context)


@login_required
def modifier_profil_association(request):
    """
    Allows an authenticated association user to update their association profile.

    Functionality:
        - Checks that the logged-in user is an association; redirects non-association users.
        - Retrieves the association linked to the current user.
        - Handles profile update form submission with support for file uploads (e.g., logo, images).
        - Saves changes if the form is valid and displays a success message.
        - Renders the profile modification template with the form and current association data.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders 'core/associations/modifier_profil.html' with the form and association details.
    """

    """Modifier le profil de l'association"""
    if not request.user.is_association():
        messages.error(request, "Accès réservé aux associations.")
        return redirect('accueil')
    
    association = get_object_or_404(Association, user=request.user)
    
    if request.method == 'POST':
        form = AssociationForm(request.POST, request.FILES, instance=association)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")

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
    """
    Personal dashboard for association users.

    Functionality:
        - Ensures the logged-in user is an association; redirects non-association users.
        - Retrieves or creates the association profile linked to the user.
        - Fetches all projects belonging to the association.
        - Computes association statistics including active projects, total projects,
          total amount collected, and total number of contributors.
        - Retrieves the 5 most recent projects.
        - Renders the association dashboard template with profile, statistics, and recent projects.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders 'core/associations/espace_association.html' with context data.
    """

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
    est_membre = False
    if request.user.is_authenticated:
        est_membre = association.est_membre(request.user)
    context = {
        'association': association,
        'est_membre': est_membre,
        'stats': stats,
        'projets_recents': projets_recents,
    }
    return render(request, 'core/associations/espace_association.html', context)

@login_required
def dons_recus(request):
    """
    Affiche les dons reçus pour l'association connectée.
    Accessible uniquement si l'utilisateur connecté est une association.
    """
    if not request.user.is_association():
        messages.error(request, "Accès réservé aux associations.")
        return redirect('accueil')

    try:
        association = request.user.association_profile
    except Association.DoesNotExist:
        messages.warning(request, "Profil d'association introuvable.")
        return redirect('accueil')

    # On récupère uniquement les transactions confirmées destinées à cette association
    transactions = Transaction.objects.filter(
        association=association,
        statut='confirme'
    ).order_by('-date_transaction')

    context = {
        'association': association,
        'transactions': transactions,
    }

    return render(request, 'core/associations/dons_recus.html', context)

@login_required
def upload_association_image(request, slug):
    """
    Vue simple pour uploader une image pour une association
    """
    association = get_object_or_404(Association, slug=slug)
    
    # Vérification que l'utilisateur est membre de l'association
    if not association.est_membre(request.user):
        messages.error(request, "Vous n'êtes pas autorisé à ajouter des photos à cette association.")
        return redirect('detail_association', slug=slug)
    
    if request.method == 'POST':
        form = AssociationImageForm(request.POST, request.FILES)
        if form.is_valid():
            # Crée l'image sans la sauvegarder
            image = form.save(commit=False)
            # Assign l'association automatiquement
            image.association = association
            # Sauvegarde finale
            image.save()
            
            messages.success(request, "Photo added !")
            return redirect('detail_association', slug=slug)
    else:
        form = AssociationImageForm()
    
    return render(request, 'core/associations/upload_image.html', {
        'form': form,
        'association': association
    })

def association_images_list(request, slug):
    """
    Vue pour afficher toutes les images d'une association
    """
    association = get_object_or_404(Association, slug=slug)
    images = association.images.all().order_by('-date_ajout')
    
    return render(request, 'core/associations/images_list.html', {
        'association': association,
        'images': images
    })

from django.core.mail import send_mail
from django.conf import settings
from django.utils.html import strip_tags

@login_required
@csrf_exempt
def transfer_direct_association(request):
    """
    Traite le transfert direct d'HBAR vers une association (MVP)
    Envoie aussi un e-mail de notification à l'association.
    """
    association_id = request.GET.get('association')  # pour préremplir le form

    if request.method == 'POST':
        form = TransferDirectForm(request.POST, user=request.user)

        if form.is_valid():
            try:
                association = form.cleaned_data['association']
                montant = form.cleaned_data['montant']
                message_perso = form.cleaned_data['message']
                user = request.user

                # Vérification des wallets
                if not user.has_active_wallet or not association.user.has_active_wallet:
                    messages.error(request, "Wallet non disponible pour le transfert")
                    return render(request, 'core/associations/transfer_direct.html', {'form': form})

                # Transfert HBAR via API locale
                transfer_data = {
                    'fromAccountId': user.hedera_account_id,
                    'fromPrivateKey': user.hedera_private_key,
                    'toAccountId': association.user.hedera_account_id,  # ✅ Compte réel de l’association
                    'amount': float(montant)
                }

                response = requests.post('http://localhost:3001/transfer', json=transfer_data, timeout=30)

                if response.status_code != 200:
                    messages.error(request, "Erreur de connexion avec le service de transfert")
                    return render(request, 'core/associations/transfer_direct.html', {'form': form})

                result = response.json()
                if not result.get('success'):
                    messages.error(request, f"Échec du transfert: {result.get('error', 'Erreur inconnue')}")
                    return render(request, 'core/associations/transfer_direct.html', {'form': form})

                # Enregistrement en base
                transaction = None
                with db_transaction.atomic():
                    transaction = Transaction.objects.create(
                        user=user,
                        montant=montant,
                        hedera_transaction_hash=result.get('transactionId'),
                        hedera_status=result.get('status'),
                        hedera_hashscan_url=result.get('hashscanUrl'),
                        contributeur=user,
                        association=association,
                        destination='association',
                        statut='confirme',
                        notes_verification=f"Transfert direct - {message_perso}" if message_perso else "Transfert direct vers association"
                    )

                # ✅ Envoi d’e-mail à l’association
                recipient_email = association.email_contact or association.user.email
                if recipient_email:
                    subject = f"🎉 Nouveau don reçu sur SolidAvenir - {association.nom}"
                    html_message = f"""
                    <p>Bonjour <b>{association.nom}</b>,</p>
                    <p>Vous avez reçu un nouveau don de la part de <b>{user.get_full_name_or_username()}</b>.</p>
                    <ul>
                        <li><b>Montant :</b> {montant} HBAR</li>
                        <li><b>Message :</b> {message_perso or 'Aucun message personnel'}</li>
                        <li><b>Transaction :</b> <a href="{result.get('hashscanUrl')}" target="_blank">Voir sur Hashscan</a></li>
                    </ul>
                    <p>Merci de continuer à œuvrer pour vos causes sur <a href="{request.build_absolute_uri('/')}">SolidAvenir</a>.</p>
                    <hr>
                    <small>Cet e-mail vous est envoyé automatiquement par la plateforme SolidAvenir.</small>
                    """
                    plain_message = strip_tags(html_message)

                    send_mail(
                        subject,
                        plain_message,
                        settings.DEFAULT_FROM_EMAIL,
                        [recipient_email],
                        html_message=html_message,
                        fail_silently=True,
                    )

                # ✅ (Optionnel) Création d'une notification interne
                if hasattr(association.user, 'notifications'):
                    association.user.notifications.create(
                        titre="🎁 Nouveau don reçu",
                        message=f"{user.get_full_name_or_username()} a envoyé {montant} HBAR.",
                        lien=result.get('hashscanUrl'),
                    )

                messages.success(request, f"✅ Transfert de {montant} HBAR vers {association.nom} effectué avec succès !")
                return redirect('mes_dons')

            except Exception as e:
                messages.error(request, f"Erreur lors du transfert: {str(e)}")

    else:
        # Cas GET : préremplir si ?association=id est passé
        initial_data = {}
        if association_id:
            try:
                association = Association.objects.get(id=association_id, valide=True)
                initial_data['association'] = association
            except Association.DoesNotExist:
                messages.warning(request, "Association invalide ou introuvable.")

        form = TransferDirectForm(user=request.user, initial=initial_data)

    return render(request, 'core/associations/transfer_direct.html', {'form': form})


#===================
# END ASSOCIATION
#===================

#===================
# PROJETS
#===================

@login_required
def creer_projet(request):
    """
    Create a new project with reward description.

    Functionality:
        - Ensures the logged-in user can create a project (individual or association).
        - If the user has an associated association profile, links the project to it.
        - Handles project creation form submission, including file uploads.
        - Generates a unique project identifier.
        - Creates Hedera wallet for the project via external API call.
            - Stores account ID and private key in the project.
            - If wallet creation fails, logs the error and continues project creation.
        - Automatically creates default reward tiers (Palier) for the project.
        - Logs the creation in the AuditLog with project and user details.
        - Displays success or error messages and redirects accordingly.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders 'core/projets/creer_projet.html' with form and association context.
    """

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

                    #  Création du wallet Hedera pour ce projet
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
                    # 🔑 Génération de l'identifiant unique incluant le porteur
                    projet.save()
                    projet.identifiant_unique = f"SOLID{projet.id:06d}-{request.user.id}-{timezone.now().strftime('%Y%m%d')}"
                    projet.save(update_fields=['identifiant_unique'])
                    
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
                    "Your project has been successfully created with a dedicated Hedera account!"
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
    try:
        projet = Projet.objects.get(audit_uuid=uuid, porteur=request.user)
        
        if not projet.peut_etre_modifie_par(request.user):
            messages.error(request, "Ce projet ne peut plus être modifié.")
            # CORRECTION : utiliser audit_uuid au lieu de uuid
            return redirect('detail_projet', audit_uuid=uuid)
        
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

                    messages.success(request, "Your project has been successfully updated.")
                    # CORRECTION : utiliser audit_uuid au lieu de uuid
                    return redirect('detail_projet', audit_uuid=uuid)

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
def ajouter_images_projet(request, uuid):
    try:
        projet = Projet.objects.get(audit_uuid=uuid, porteur=request.user)
        
        if not projet.peut_etre_modifie_par(request.user):
            messages.error(request, "Vous n'avez pas la permission de modifier ce projet.")
            # CORRECTION : utiliser audit_uuid au lieu de uuid
            return redirect('detail_projet', audit_uuid=uuid)
        
        images_existantes = projet.images.all()
        images_restantes = 10 - images_existantes.count()
        
        if request.method == 'POST':
            form = AjoutImagesProjetForm(request.POST, request.FILES, projet=projet)
            
            if form.is_valid():
                try:
                    images_crees = form.save()
                    
                    # Journalisation
                    AuditLog.objects.create(
                        utilisateur=request.user,
                        action='add_images',
                        modele='Projet',
                        objet_id=str(projet.audit_uuid),
                        details={
                            'images_ajoutees': len(images_crees),
                            'total_images': projet.images.count()
                        },
                        adresse_ip=request.META.get('REMOTE_ADDR')
                    )
                    
                    # CORRECTION : utiliser audit_uuid au lieu de uuid
                    return redirect('detail_projet', audit_uuid=uuid)
                    
                except Exception as e:
                    logger.error(f"Erreur ajout images: {str(e)}", exc_info=True)
                    messages.error(request, "Une erreur est survenue lors de l'ajout des images.")
        else:
            form = AjoutImagesProjetForm(projet=projet)
        
        context = {
            'form': form,
            'projet': projet,
            'images_existantes': images_existantes,
            'max_images': 10,
            'images_restantes': images_restantes  
        }
        
        return render(request, 'core/projets/ajouter_images.html', context)
        
    except Projet.DoesNotExist:
        messages.error(request, "Projet non trouvé.")
        return redirect('mes_projets')


@login_required
def supprimer_projet(request, uuid):
    """
    Delete a project owned by the logged-in user.

    Functionality:
        - Retrieves the project by its audit UUID and ensures the logged-in user is the owner.
        - Only allows deletion if the project status is 'draft' or 'rejected'.
            - If the status is not allowed, displays an error and redirects to the project detail page.
        - Handles POST requests to delete the project.
            - Logs the deletion in AuditLog including project title, status, and requested amount.
            - Deletes the project and displays a success message, then redirects to the user's project list.
        - For GET requests, renders a confirmation page before deletion.

    Args:
        request (HttpRequest): The HTTP request object.
        uuid (UUID): The unique audit UUID of the project to delete.

    Returns:
        HttpResponse: 
            - Renders 'core/projets/supprimer_projet.html' for GET requests.
            - Redirects to project detail or project list on success, error, or project not found.
    """

    """Suppression d'un projet"""
    try:
        projet = Projet.objects.get(audit_uuid=uuid, porteur=request.user)
        
        # Vérifier que le projet peut être supprimé (seulement brouillon ou rejeté)
        if projet.statut not in ['brouillon', 'rejete']:
            messages.error(
                request, 
                "Seuls les projets en brouillon ou rejetés peuvent être supprimés."
            )
            # CORRECTION : utiliser audit_uuid au lieu de uuid
            return redirect('detail_projet', audit_uuid=uuid)
        
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
                messages.success(request, "Your project has been successfully deleted")
                return redirect('mes_projets')
                
            except Exception as e:
                logger.error(f"Erreur suppression projet: {str(e)}", exc_info=True)
                messages.error(request, "Une erreur est survenue lors de la suppression.")
                # CORRECTION : utiliser audit_uuid au lieu de uuid
                return redirect('detail_projet', audit_uuid=uuid)
        
        # GET request - afficher la confirmation
        return render(request, 'core/projets/supprimer_projet.html', {'projet': projet})
        
    except Projet.DoesNotExist:
        messages.error(request, "Projet non trouvé.")
        return redirect('mes_projets')
    

def detail_projet(request, audit_uuid):
    """
    Display detailed information for a specific project with contribution capability.

    Functionality:
        - Retrieves the project by its audit UUID. Returns 404 if not found.
        - Increments the project's view counter.
        - Aggregates advanced statistics on confirmed transactions:
            - Total number of unique contributors
            - Total amount collected
            - Average and maximum donation amounts
            - Date of the most recent donation
        - Prepares reward tiers (paliers) with their submission status, distribution status, and FCFA amounts.
        - Handles currency conversion for project amounts.
        - Checks if the logged-in user has permission to preview the project if it's not active or completed.
        - Shows similar active projects in the same category.
        - Retrieves recent confirmed transactions related to the project.
        - Determines if the logged-in user has a Hedera wallet configured.
        - Handles POST requests for contributions via `handle_contribution`.
        - Prepares a contribution form for authenticated users.
    
    Args:
        request (HttpRequest): The HTTP request object.
        audit_uuid (UUID): The unique audit UUID of the project.

    Returns:
        HttpResponse: 
            - Renders 'core/projets/detail_projet.html' with context including:
                - project details
                - recent transactions
                - contributors count
                - total collected amount
                - contribution form
                - similar projects
                - reward tiers and their status
                - currency conversions
                - user permissions and wallet status
                - various statistics
            - Redirects to project list with error if access is denied.
    """

    """Détail d'un projet spécifique avec possibilité de contribution"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    #  Incrémenter le compteur de vues
    projet.incrementer_vues()
    
    #  Statistiques avancées
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
    
    #  Paliers avec statut
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
    
    #  Conversions de devise
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
    
    #  Vérification des permissions de visualisation
    user_can_preview = (
        request.user == projet.porteur or
        request.user.is_staff or
        (hasattr(request.user, 'association_profile') and 
         request.user.association_profile == projet.association)
    )
    
    if projet.statut not in ['actif', 'termine'] and not user_can_preview:
        messages.error(request, "Ce projet n'est pas accessible.")
        return redirect('liste_projets')
    
    #  Projets similaires
    projets_similaires = Projet.objects.filter(
        statut='actif',
        categorie=projet.categorie
    ).exclude(audit_uuid=audit_uuid).order_by('?')[:3]  # Random order for variety
    
    #  Transactions récentes
    transactions_recentes = Transaction.objects.filter(
        projet=projet, 
        statut='confirme',
        destination='operator'
    ).select_related('contributeur').order_by('-date_transaction')[:10]
    
    # Vérification wallet utilisateur
    user_has_wallet = False
    if request.user.is_authenticated:
        user_has_wallet = (
            hasattr(request.user, 'hedera_account_id') and 
            request.user.hedera_account_id and
            hasattr(request.user, 'hedera_private_key') and 
            request.user.hedera_private_key
        )
    
    #  Gestion des contributions (POST)
    if request.method == 'POST':
        return handle_contribution(request, projet, user_has_wallet)
    
    # Formulaire de contribution
    form = Transfer_fond(projet=projet, contributeur=request.user if request.user.is_authenticated else None)
    
    # Context pour le template
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
    """
    Display a paginated list of all active projects with filtering options.

    Functionality:
        - Retrieves all projects with status 'active'.
        - Annotates each project with:
            - Total confirmed contributions (montant_collectes)
            - Number of unique contributors (nombre_donateurs)
        - Supports filters based on:
            - Search query across title, short description, full description, and tags
            - Project category
            - Financing type
        - Provides filter options for categories and financing types.
        - Paginates the results (9 projects per page).

    Args:
        request (HttpRequest): The HTTP request object containing GET parameters for filtering and pagination.

    Returns:
        HttpResponse:
            - Renders 'core/projets/liste_projets.html' with context including:
                - Filtered and paginated project list
                - Available categories and financing types
                - Current filter values for search, category, and financing type
    """

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
    """
    Display a list of projects owned by the currently logged-in user, 
    including detailed statistics and milestone (palier) information.

    Functionality:
        - Retrieves all projects where the logged-in user is the project owner (porteur).
        - Annotates each project with:
            - Number of unique confirmed contributors.
            - Date of the latest confirmed transaction.
        - Prefetches related milestones (paliers) and their proofs, ordered appropriately.
        - Calculates global statistics for the user's projects:
            - Total projects
            - Projects by status (active, pending, completed)
            - Total collected vs. total requested amounts
            - Overall funding percentage
        - Handles POST requests to change project status:
            - 'soumettre' (submit) from 'draft' to 'pending'
            - 'annuler' (cancel) from 'pending' to 'draft'
            - Logs each action in the AuditLog.

    Args:
        request (HttpRequest): The HTTP request object; may include POST data for status changes.

    Returns:
        HttpResponse:
            - Renders 'core/projets/mes_projets.html' with context containing:
                - 'projets': list of user's projects with annotations and prefetched relations
                - 'stats': dictionary with global statistics
                - 'STATUTS': mapping of project status codes to human-readable labels
    """

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
                
                messages.success(request, f"The project '{projet.titre}' has been submitted for approval.")

            
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
                
                messages.success(request, f"The submission of the project '{projet.titre}' has been canceled.")
            
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
    """
    Display all non-draft and non-rejected projects for a specific user.

    Functionality:
        - Retrieves the user by ID.
        - Fetches all projects owned by the user, excluding drafts ('brouillon') and rejected ('rejete').
        - Orders projects by creation date in descending order.
        - Calculates statistics for the user's projects, including:
            - Total projects
            - Active projects
            - Completed projects
            - Total amount collected
            - Success rate (via `calculer_taux_reussite`)
        - Provides a utility function to get the color associated with a project's status.
        - Supplies Django's `intcomma` for numeric formatting.

    Args:
        request (HttpRequest): The HTTP request object.
        user_id (int): ID of the user whose projects are to be displayed.

    Returns:
        HttpResponse:
            - Renders 'core/projets/projets_utilisateur.html' with context containing:
                - 'utilisateur': the target User object
                - 'projets': queryset of the user's projects
                - 'stats': dictionary of project statistics
                - 'get_statut_color': function to map project status to color
                - 'intcomma': template filter for formatting numbers
                - 'active_tab': UI indicator for the active tab in the template
    """

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
    """
    Interface for project owners to submit proof documents for a milestone (palier).

    Functionality:
        - Fetches the milestone (Palier) by ID and ensures the current user is the project owner.
        - Prevents submission if the milestone has already been transferred.
        - Handles existing proof objects (PreuvePalier) and allows replacing files.
        - Validates uploaded files:
            - At least one file required.
            - Maximum 10 files.
            - Individual file size ≤ 10 MB.
            - Total size ≤ 50 MB.
            - Allowed MIME types: images, videos, PDFs, Word/Excel documents, plain text.
        - Saves validated files as FichierPreuve linked to PreuvePalier.
        - Records an AuditLog entry for submission.
        - Triggers HCS (Hedera Consensus Service) notification.
        - Displays success or error messages to the user.

    Args:
        request (HttpRequest): The HTTP request object.
        palier_id (int): ID of the milestone for which proofs are submitted.

    Returns:
        HttpResponse:
            - Renders 'core/projets/soumettre_preuves.html' with context:
                - 'palier': the milestone object
                - 'projet': the associated project
                - 'form': PreuveForm instance
                - 'preuve_existante': existing PreuvePalier object (if any)
            - On successful POST, redirects to 'mes_projets' with a success message.
    """

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
                        'palier': f"{palier.titre}%",
                        'fichiers': len(fichiers_uploades),
                        'types_fichiers': [f.type_fichier for f in fichiers_uploades],
                        'statut': 'en_attente'
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )
                
                # Notification HCS
                notifier_soumission_preuve_hcs(projet, palier, len(fichiers_uploades))
            
                messages.success(
                    request, 
                    f"✅ {len(fichiers_uploades)} proof(s) submitted successfully. "
                    "Waiting for verification by the administrator."
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

# views.py


#===================
# END PROJETS
#===================
#===================
# ADMIN
#===================

def admin_required(view_func):
    """
    Decorator to ensure that the current user is an active administrator.

    If the user is not an admin, they are redirected to the homepage
    with an error message.
    """
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
    """Display member details with associated statistics."""
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
    """
    Admin interface to manage milestone-based fund distributions for projects.
    """
    
    # Récupérer les projets éligibles
    projets = Projet.objects.filter(
        Q(montant_engage__gt=0) | 
        Q(statut__in=['actif', 'termine'])
    ).prefetch_related('paliers', 'transaction_set')
    
    distributions = []
    
    for projet in projets:
        # Calcul manuel du total des dons avec gestion des valeurs None
        total_dons = sum(
            float(t.montant or 0) for t in projet.transaction_set.all() 
            if t.statut == 'confirme' and t.destination == 'operator'
        )
        
        # Calcul des métriques avec gestion des valeurs None
        montant_engage = float(projet.montant_engage or 0)
        montant_distribue = float(projet.montant_distribue or 0)
        montant_demande = float(projet.montant_demande or 1)  # Éviter division par zéro
        
        montant_disponible = montant_engage - montant_distribue
        pourcentage_engage = (montant_engage / montant_demande * 100) if montant_demande > 0 else 0
        pourcentage_distribue = (montant_distribue / montant_demande * 100) if montant_demande > 0 else 0
        
        # Analyser chaque palier avec son statut de preuve
        paliers_avec_statut = []
        
        for palier in projet.paliers.order_by('montant_minimum'):
            # Gestion des valeurs None pour les montants des paliers
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
                'titre': palier.titre,  # Utiliser le titre au lieu du pourcentage
                'montant': palier_montant,
                'transfere': palier.transfere,
                'date_transfert': palier.date_transfert,
                'statut_preuve': statut_preuve,
                'date_soumission': date_soumission,
                'preuve_id': preuve_id,
                'distributable': distributable,
                'montant_suffisant': montant_disponible >= palier_montant,
                'preuve_requise': not palier.transfere and statut_preuve != 'approuve',
                'description': palier.description  # Ajouter la description pour l'affichage
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
                
                # Gestion des valeurs None pour les montants
                montant_engage = float(projet.montant_engage or 0)
                montant_distribue = float(projet.montant_distribue or 0)
                palier_montant = float(palier.montant or 0)
                
                montant_disponible = montant_engage - montant_distribue
                if montant_disponible < palier_montant:
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
                    montant_brut=palier_montant,
                    palier=palier,
                    initiateur=request.user 
                )
                
                if resultat['success']:
                    transaction_hash = resultat['transactionId']
                    
                    # Mettre à jour le palier avec le hash de transaction
                    palier.transfere = True
                    palier.date_transfert = timezone.now()
                    palier.transaction_hash = resultat['transactionId']
                    palier.save()
                    
                    # Mettre à jour les montants du projet
                    nouveau_montant_distribue = montant_distribue + palier_montant
                    projet.montant_distribue = nouveau_montant_distribue
                    projet.save(update_fields=['montant_distribue'])
                    
                    # 📧 ENVOYER LA NOTIFICATION AU PORTEUR
                    envoyer_notification_porteur(projet.porteur, palier, 'distribution')
                    
                    # Notification HCS
                    if projet.topic_id:
                        envoyer_don_hcs(
                            topic_id=projet.topic_id,
                            utilisateur_email=projet.porteur.email,
                            montant=palier_montant,
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
                            'montant': palier_montant
                        },
                        adresse_ip=request.META.get('REMOTE_ADDR'),
                        statut='SUCCESS'
                    )
                    
                    messages.success(
                       request, 
                       f"✅ {palier_montant} HBAR distributed successfully\n"
                       f"📧 Notification sent to the project owner\n"
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
    
    # Calcul des totaux avec gestion des valeurs manquantes
    total_engage = sum(dist.get('montant_engage', 0) for dist in distributions)
    total_distribue = sum(dist.get('montant_distribue', 0) for dist in distributions)
    total_disponible = sum(dist.get('montant_disponible', 0) for dist in distributions)
    total_paliers_attente = sum(len(dist.get('paliers_en_attente', [])) for dist in distributions)
    total_paliers_distribuables = sum(len(dist.get('paliers_distribuables', [])) for dist in distributions)
    
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
    """
    Admin view to list and filter platform members.

    Features:
    - Supports filtering by user type, date joined range, active status, and text search 
      (username, first name, last name, email, organization).
    - Provides statistics by user type and active status.
    - Results are paginated (25 members per page).

    Context variables for template rendering:
    - membres: Paginated queryset of members according to applied filters.
    - form: Filter form instance for rendering in the template.
    - stats: Dictionary with counts by user type and active status.
    - title: Page title for the admin interface.
    """

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
    """
    Admin view to display audit logs related to fund distributions.

    Filters logs to include only actions associated with:
    - 'Distribution'
    - 'DistributionAuto'
    - 'Palier'

    Logs are ordered by action date in descending order.

    Context variables for template rendering:
    - logs: Queryset of relevant AuditLog entries.
    """

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
    """
    Admin view to list all projects pending approval.

    Retrieves projects with status 'en_attente' and includes related
    porteur information for efficient display.

    Access restricted to administrators; non-admin users are redirected
    with an error message.

    Context variables for template rendering:
    - liste_projet_admin: Queryset of projects awaiting validation
    - title: Page title for display purposes
    """

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
    """
    Admin view to reject an association with a provided reason.

    Steps performed:
    1. Checks that the user has administrator privileges.
       Non-admin users are redirected with an error message.
    2. Retrieves the targeted association by ID.
    3. On POST request:
       - Retrieves the rejection reason from the form.
       - Logs the rejection in the AuditLog model including
         the user, action type, object ID, details, and client IP.
       - Optionally sends a notification email to the association's owner.
       - Deletes the association (or can alternatively mark it as rejected).
       - Displays a warning message to the admin and redirects to dashboard.

    Template context:
    - association: the Association object being rejected
    """

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
    """
    Admin dashboard view providing a comprehensive overview of platform activities 
    and highlighting high-priority items requiring immediate attention.

    Features:

    1. Priority Items:
       - Projects pending approval (top 5 oldest)
       - Associations pending approval (top 5 oldest)
       - Funding milestones (Palier) reached but not yet distributed
       - Proofs requiring review
       - Transactions awaiting moderation

    2. Key Statistics:
       - Counts of projects (total, active, completed)
       - Counts of users by type (porteurs, donateurs, associations, etc.)
       - Transactions confirmed and daily totals
       - Donations received today and total amounts

    3. Historical Data for Visualizations:
       - Projects grouped by status
       - Donations over the last 15 days (amount and count per day)

    4. Recent Activities:
       - Latest confirmed transactions
       - Recent audit logs
       - Top donors
       - Most funded active projects

    5. Association Metrics:
       - Total associations
       - Validated associations
       - Associations pending approval

    Access Control:
    - Only users with administrator privileges can access this view.
    - Non-admin users are redirected to the home page with an error message.

    Template Context:
    - projets_attention: queryset of projects pending validation
    - associations_attente: queryset of associations pending validation
    - paliers_action: list of milestones ready for distribution
    - preuves_a_verifier: queryset of proofs requiring review
    - transactions_verification: queryset of transactions awaiting moderation
    - stats: dictionary of main platform statistics
    - stats_associations: dictionary of association-specific statistics
    - projets_par_statut: list of projects grouped by status
    - donnees_graphique: donations data structured for charting
    - recent_transactions: latest confirmed transactions
    - recent_audits: latest audit logs
    - top_donateurs: top donors by total contribution
    - projets_populaires: most funded active projects
    - aujourdhui: current date for filtering and display
    """

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
    ).select_related('porteur').order_by('date_creation')[:5]
    
    # 2. Associations en attente de validation
    associations_attente = Association.objects.filter(
        valide=False
    ).select_related('user').order_by('date_creation_association')[:5]
    
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
    ).select_related('palier', 'palier__projet').order_by('-date_soumission')[:5]
    
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
        transactions__statut='confirme'
    ).annotate(
        total_dons=Sum('transactions__montant'),  
        nombre_dons=Count('transactions')  
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
    """
    Admin view to list and filter transactions that require verification.

    Features:
    - Display all transactions in descending order by transaction date.
    - Apply filters based on:
        * Start and end dates
        * Minimum and maximum amounts
        * Associated project title
    - Pagination with 20 transactions per page.
    - Calculate total number of transactions and total amount for the filtered set.

    Access Control:
    - Requires the 'core.view_dashboard' permission.
    - User must be logged in.

    Template Context:
    - transactions: paginated queryset of filtered transactions
    - form: FiltreTransactionsForm instance with current filters
    - title: page title for rendering
    - total_transactions: total count of transactions after filtering
    - montant_total: sum of transaction amounts after filtering
    """

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
    """
    Admin view to validate a user-submitted association.

    This view allows an administrator to approve an association, mark it as valid,
    log the action for audit purposes, and optionally notify the association owner
    via email.

    Features:
    - Retrieve an association by its ID.
    - Ensure only administrators can access this action.
    - Update the association's 'valide' status to True upon validation.
    - Record the validation action in the AuditLog with user, IP, and details.
    - Send a confirmation email to the association owner notifying them of the approval.
    - Provide success messages and redirect back to the admin dashboard.

    Access Control:
    - Requires the user to be logged in.
    - Requires the 'core.manage_users' permission.
    - Additional check: user must be an administrator.

    Template Context:
    - association: Association instance to be validated.
    """

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
            action='validate',  
            modele='Association',  
            objet_id=str(association.id),
            details=f"Validation de l'association {association.nom}",
            adresse_ip=get_client_ip(request)  
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
        
        return redirect('tableau_de_bord')
    
    context = {'association': association}
    return render(request, 'core/admin/valider_association.html', context)


@permission_required('core.manage_users', raise_exception=True)
@login_required
def liste_projets_admin(request):
    """
    Vue fonctionnelle pour afficher la liste des projets avec filtres et statistiques.
    """
    queryset = Projet.objects.select_related(
        'porteur', 
        'association', 
        'valide_par'
    ).prefetch_related('paliers', 'images')

    # --- Récupération des filtres GET ---
    statut = request.GET.get('statut')
    categorie = request.GET.get('categorie')
    type_financement = request.GET.get('type_financement')
    recherche = request.GET.get('recherche')
    tri = request.GET.get('tri', '-date_creation')

    # --- Application des filtres ---
    if statut and statut != 'tous':
        queryset = queryset.filter(statut=statut)

    if categorie and categorie != 'toutes':
        if categorie == 'autre':
            queryset = queryset.filter(categorie='autre')
        else:
            queryset = queryset.filter(categorie=categorie)

    if type_financement and type_financement != 'tous':
        queryset = queryset.filter(type_financement=type_financement)

    if recherche:
        queryset = queryset.filter(
            Q(titre__icontains=recherche) |
            Q(description__icontains=recherche) |
            Q(description_courte__icontains=recherche) |
            Q(tags__icontains=recherche) |
            Q(porteur__username__icontains=recherche) |
            Q(porteur__email__icontains=recherche)
        )

    # --- Tri ---
    if tri in [
        'date_creation', '-date_creation', 
        'titre', '-titre', 
        'montant_demande', '-montant_demande', 
        'montant_collecte', '-montant_collecte'
    ]:
        queryset = queryset.order_by(tri)

    # --- Pagination ---
    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    projets_page = paginator.get_page(page_number)

    # --- Statistiques globales ---
    total_projets = Projet.objects.count()
    projets_actifs = Projet.objects.filter(statut='actif').count()
    projets_termines = Projet.objects.filter(statut='termine').count()
    projets_en_attente = Projet.objects.filter(statut='en_attente').count()
    projets_brouillon = Projet.objects.filter(statut='brouillon').count()

    montant_total_demande = Projet.objects.aggregate(total=Sum('montant_demande'))['total'] or 0
    montant_total_collecte = Projet.objects.aggregate(total=Sum('montant_collecte'))['total'] or 0
    taux_collecte_global = (
        (montant_total_collecte / montant_total_demande * 100)
        if montant_total_demande > 0 else 0
    )

    # --- Projets expirant bientôt ---
    projets_expirant = Projet.objects.filter(
        statut='actif',
        date_fin__lte=timezone.now() + timezone.timedelta(days=7),
        date_fin__gt=timezone.now()
    ).count()

    # --- Contexte ---
    context = {
        'projets': projets_page,
        'total_projets': total_projets,
        'projets_actifs': projets_actifs,
        'projets_termines': projets_termines,
        'projets_en_attente': projets_en_attente,
        'projets_brouillon': projets_brouillon,
        'projets_expirant': projets_expirant,
        'montant_total_demande': montant_total_demande,
        'montant_total_collecte': montant_total_collecte,
        'taux_collecte_global': taux_collecte_global,

        # Filtres et valeurs actuelles
        'statuts_choices': Projet.STATUTS,
        'categories_choices': Projet.CATEGORIES,
        'types_financement_choices': Projet.TYPES_FINANCEMENT,
        'filtre_statut': statut or '',
        'filtre_categorie': categorie or '',
        'filtre_type_financement': type_financement or '',
        'filtre_recherche': recherche or '',
        'tri_actuel': tri,
    }

    return render(request, 'core/admin/liste_projets.html', context)

@login_required
@permission_required('core.validate_project', raise_exception=True)
def valider_projet(request, audit_uuid):
    """
    Admin view to validate or reject a project submitted by a user.

    This view allows administrators to review a project that is pending validation
    or in draft status, and either approve (activate) or reject it. The process
    includes document review, status updates, email notifications, blockchain topic
    creation (Hedera HCS), and detailed audit logging.

    Features:
    - Retrieve a project by its audit UUID, ensuring it is pending validation or draft.
    - Display key statistics for the project and the project owner:
        * Requested amount
        * Duration since creation
        * Number of projects submitted by the user
    - Form-based validation or rejection with optional comments.
    - When approving a project:
        * Generate a unique project identifier if not already present.
        * Create a Hedera HCS topic for blockchain tracking.
        * Log all actions in the AuditLog.
        * Send a notification email to the project owner.
    - When rejecting a project:
        * Record the rejection and optional comment.
        * Send a notification email to the project owner.
        * Update the audit log.

    Access Control:
    - Requires the user to be logged in.
    - Requires the 'core.validate_project' permission.

    Template Context:
    - form: ValidationProjetForm instance for approval/rejection.
    - projet: Project instance being reviewed.
    - documents: List of project-related documents for review.
    - stats: Dictionary of project and user statistics.
    - porteur: User instance of the project owner.
    - STATUTS: Dictionary of available project statuses.
    """

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
                
                #  CRÉATION DU TOPIC HCS SUR HEDERA
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
                            
                            messages.success(request, f"HCS topic created: {projet.topic_id}")

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
                    sujet_email = f'Votre projet  a été examiné par SolidAvenir'
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
    """
    Admin interface to review and manage proof submissions for a project milestone (palier).

    This view allows an administrator to:
    - Approve, reject, or request modifications for a proof submitted by the project owner.
    - Log every action in the AuditLog with relevant details (user, IP, project, milestone, status, files count).
    - Notify the project owner of the action taken via notifications.

    Workflow:
    1. Retrieve the milestone (Palier) and associated project.
    2. Attempt to fetch the submitted proof (PreuvePalier) and associated files.
    3. If the request method is POST:
       - Process the VerificationPreuveForm.
       - Apply the chosen action ('approuver', 'rejeter', 'modification').
       - Update the proof status, save comments, and log the action.
       - Notify the project owner.
       - Provide feedback messages for the admin.
    4. If GET, display the proof details and verification form.

    Access Control:
    - User must be logged in.
    - User must have the 'core.manage_users' permission.

    Template Context:
    - palier: The milestone object being verified.
    - projet: The project associated with the milestone.
    - preuve: The proof object, if exists.
    - fichiers: List of files attached to the proof.
    - form: VerificationPreuveForm instance for admin actions.

    Messages:
    - Success, warning, or info messages based on admin actions.
    """

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
                        'palier': f"{palier.titre}%",
                        'montant': float(palier.montant),
                        'fichiers': len(fichiers),
                        'statut': 'approuve'
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR'),
                    statut='SUCCESS'
                )
                
                # Notifier le porteur
                envoyer_notification_porteur(projet.porteur, palier, 'approuve', commentaires)
                
                
                
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
                        'palier': f"{palier.titre}%",
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
                        'palier': f"{palier.titre}%",
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
    """
    Admin view to display and filter audit logs.

    Features:
    - Display all audit logs in descending order of action date.
    - Apply filters based on:
        * User
        * Action type
        * Model name
        * Date range (start and end)
        * Free text search in model, object ID, or details
    - Pagination with 50 logs per page.
    - Calculate statistics:
        * Total logs
        * Logs created today
        * Logs created in the last 7 days

    Access Control:
    - Requires the 'core.can_audit' permission.
    - User must be logged in.

    Template Context:
    - logs: Paginated queryset of filtered audit logs
    - form: FiltreAuditForm instance with current filters
    - stats: Dictionary with log statistics
    - title: Page title for rendering

    Messages:
    - Feedback messages can be added for filtering or errors (currently not used).
    """

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
@permission_required('core.can_audit', raise_exception=True)
def preview_association_admin(request, association_id):
    """
    Admin view to preview an association, including those not yet validated.

    Features:
    - Fetch an association by its ID.
    - Display all relevant details to administrators.
    - Include active projects linked to the association.
    - Flag `is_preview` in context to indicate this is an admin preview.

    Access Control:
    - User must be logged in.
    - Requires 'core.can_audit' permission.
    - Only administrators can access; others are redirected with an error message.

    Template Context:
    - association: The Association object being previewed
    - projets_actifs: Queryset of the association's active projects
    - is_preview: Boolean flag indicating this is an admin preview
    """

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
#===========
# PALLIER
#===========
@login_required
def gerer_paliers(request, projet_id):
    """
    Vue principale pour gérer tous les paliers d'un projet
    """
    projet = get_object_or_404(Projet, id=projet_id, porteur=request.user)
    paliers = projet.paliers.all().order_by('montant_minimum')
    
    # Calcul du total des paliers pour validation
    total_paliers = sum(palier.montant for palier in paliers)
    
    context = {
        'projet': projet,
        'paliers': paliers,
        'total_paliers': total_paliers,
        'reste_a_assigner': projet.montant_demande - total_paliers,
        'projet_audit_uuid': projet.audit_uuid,  
    }
    return render(request, 'core/projets/gerer_paliers.html', context)


@login_required
def ajouter_palier(request, projet_id):
    """
    Vue pour ajouter un nouveau palier à un projet
    """
    projet = get_object_or_404(Projet, id=projet_id, porteur=request.user)
    
    # Calcul du montant déjà assigné aux paliers existants
    montant_assigné = sum(palier.montant for palier in projet.paliers.all())
    montant_restant = projet.montant_demande - montant_assigné
    
    if request.method == 'POST':
        form = PalierForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    palier = form.save(commit=False)
                    palier.projet = projet
                    
                    # Validation : ne pas dépasser le montant demandé
                    nouveau_total = montant_assigné + palier.montant
                    if nouveau_total > projet.montant_demande:
                        messages.error(
                            request, 
                            f"Le montant total des paliers ({nouveau_total:,} FCFA) dépasse le montant demandé ({projet.montant_demande:,} FCFA). "
                            f"Montant restant à assigner : {montant_restant:,} FCFA."
                        )
                    else:
                        palier.save()
                        messages.success(request, f"Palier '{palier.titre}' ajouté avec succès !")
                        return redirect('gerer_paliers', projet_id=projet.id)
                        
            except Exception as e:
                messages.error(request, f"Erreur lors de l'ajout du palier : {str(e)}")
    else:
        form = PalierForm()
    
    context = {
        'projet': projet,
        'form': form,
        'montant_restant': montant_restant,
        'montant_assigné': montant_assigné,
    }
    return render(request, 'core/projets/ajouter_palier.html', context)

@login_required
def modifier_palier(request, palier_id):
    """
    Vue pour modifier un palier existant
    """
    palier = get_object_or_404(Palier, id=palier_id, projet__porteur=request.user)
    projet = palier.projet
    
    # Calcul des montants pour validation
    montant_autres_paliers = sum(p.montant for p in projet.paliers.exclude(id=palier_id))
    montant_restant = projet.montant_demande - montant_autres_paliers
    
    if request.method == 'POST':
        form = PalierForm(request.POST, instance=palier)
        if form.is_valid():
            try:
                with transaction.atomic():
                    palier_modifie = form.save(commit=False)
                    
                    # Validation du montant
                    nouveau_total = montant_autres_paliers + palier_modifie.montant
                    if nouveau_total > projet.montant_demande:
                        messages.error(
                            request,
                            f"Le nouveau montant total ({nouveau_total:,} FCFA) dépasse le montant demandé. "
                            f"Montant maximum possible : {montant_restant:,} FCFA."
                        )
                    else:
                        palier_modifie.save()
                        messages.success(request, f"Palier '{palier_modifie.titre}' modifié avec succès !")
                        return redirect('gerer_paliers', projet_id=projet.id)
                        
            except Exception as e:
                messages.error(request, f"Erreur lors de la modification : {str(e)}")
    else:
        form = PalierForm(instance=palier)
    
    context = {
        'form': form,
        'palier': palier,
        'projet': projet,
        'montant_restant': montant_restant,
    }
    return render(request, 'core/projets/modifier_palier.html', context)

@login_required
def supprimer_palier(request, palier_id):
    """
    Vue pour supprimer un palier
    """
    palier = get_object_or_404(Palier, id=palier_id, projet__porteur=request.user)
    projet = palier.projet
    
    if request.method == 'POST':
        try:
            titre_palier = palier.titre
            palier.delete()
            messages.success(request, f"Palier '{titre_palier}' supprimé avec succès !")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression : {str(e)}")
        
        return redirect('gerer_paliers', projet_id=projet.id)
    
    context = {
        'palier': palier,
        'projet': projet,
    }
    return render(request, 'core/projets/supprimer_palier.html', context)
#-----------------------------------
#END PALIER
#===================================

def voir_wallet(request):
    """
    Display the authenticated user's Hedera wallet balance.

    Ensures the user has a wallet, fetches the current balance from
    the local Hedera microservice, and renders the wallet details page.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponse: Renders the 'wallet_detail' template with the user's wallet balance.
                      Redirects to login if the user is not authenticated.
    """
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


def creer_topic_pour_projet(projet, utilisateur):
    """
    Create a Hedera Consensus Service (HCS) topic for a project via the Node.js microservice.
    Logs the action with the initiating user.

    Args:
        projet (Projet): The project instance for which to create the topic.
        utilisateur (User): The user performing the action.

    Returns:
        dict: Response data from the microservice on success.

    Raises:
        Exception: If the microservice is unavailable, times out, or returns an error.
    """
    url = "http://localhost:3001/create-topic"
    
    # Créer un mémo tronqué à 100 caractères maximum
    memo_base = f"Project {projet.titre}"
    memo = memo_base[:100]  # Tronquer à 100 caractères
    
    try:
        response = requests.post(url, json={
            "memo": memo
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
                    'hashscan_url': data.get("hashscanUrl", ""),
                    'memo_utilise': memo  # Ajouter le mémo utilisé pour traçabilité
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
    """
    Sends a message to a Hedera Consensus Service (HCS) topic to record a donation.

    The message includes the user's email, donation amount, transaction hash, 
    timestamp, and the type of message. It also logs the message in the local database 
    for traceability.

    Args:
        topic_id (str): The HCS topic ID where the message will be sent.
        utilisateur_email (str): Email of the contributor.
        montant (Decimal or float): Amount of the donation.
        transaction_hash (str): Hash identifying the blockchain transaction.
        type_message (str, optional): Type of message being sent. Defaults to "distribution_palier".

    Returns:
        dict: Response from the HCS microservice, including success status and error details if any.

    Raises:
        ConnectionError: If the HCS microservice is not reachable.
        TimeoutError: If the request to the HCS microservice times out.
        HTTPError: If the HCS microservice returns an HTTP error.
        Exception: For any other unexpected error during message sending.
    """
    """Envoie un message HCS pour enregistrer un don"""
    url = "http://localhost:3001/send-message"
    
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
    """
    Handles a HBAR donation from an authenticated user to a specified project.

    This view performs several operations:
    1. Validates that the user is authenticated and has a configured Hedera wallet.
    2. Validates the donation amount.
    3. Executes a HBAR transfer from the user's account to the operator account via a microservice.
    4. Creates a local Transaction record with the transaction status.
    5. Updates the project's engaged amount if the transaction is confirmed.
    6. Sends a message to the Hedera Consensus Service (HCS) topic associated with the project.
    7. Logs success or error messages for user feedback.

    Args:
        request (HttpRequest): The incoming HTTP request object.
        project_id (int): ID of the project receiving the donation.

    Returns:
        HttpResponseRedirect: Redirects back to the project detail page with success or error messages.

    Raises:
        Exception: Captures any unexpected error during the donation process.
    """

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
            response = requests.post('http://localhost:3001/transfer', json=transfer_data, timeout=30)

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

                # 🔹 Vérifier si c’est la première contribution de cet utilisateur
                deja_contributeur = project.transaction_set.filter(
                    contributeur=user,
                    statut='confirme',
                    destination='operator'
                ).exclude(id=transaction.id).exists()

                if not deja_contributeur:
                    project.contributeurs_count = F('contributeurs_count') + 1

                project.save(update_fields=['montant_engage', 'contributeurs_count'])


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

                        messages.success(request, f"Your donation of {amount} HBAR has been successfully made ✅ and recorded on HCS")

                        
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
    Executes a transfer from the platform operator to the project doer, applying commission,
    recording the transaction in the database, and optionally sending a message to the Hedera Consensus Service (HCS).

    The function performs the following steps:
    1. Calculates commission and net amount.
    2. Transfers HBAR from the operator account to the doer's account via a microservice.
    3. Creates a TransactionAdmin record to log the transfer details.
    4. Sends a structured HCS message to the project's topic with the transfer information.
    5. Updates the TransactionAdmin record with HCS message identifiers if successful.
    6. Handles errors including API timeout, connection issues, and unexpected exceptions.

    Args:
        projet (Projet): The project object associated with the transfer.
        porteur (User): The recipient user of the transfer.
        montant_brut (Decimal | float | str): The gross HBAR amount before commission.
        palier (Palier, optional): Associated milestone if applicable.
        initiateur (User, optional): User initiating the transfer, for auditing.

    Returns:
        dict: A dictionary with 'success' (bool), 'transactionId' (str, if successful), and 'error' (str, if any).
    """

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
        response = requests.post("http://localhost:3001/transfer", json=transfer_data, timeout=30)
        
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

        #  ENVOI HCS AVEC DÉTAILS COMPLETS
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
    """
    Sends a Hedera Consensus Service (HCS) message for a distribution event.

    This function constructs a structured message containing all distribution details
    and posts it to the specified HCS topic via the microservice. It handles connection
    errors, timeouts, and unexpected exceptions, logging each appropriately.

    Args:
        topic_id (str): The HCS topic identifier where the message should be sent.
        distribution_data (dict): Detailed information about the distribution event.

    Returns:
        dict: Contains 'success' (bool), 'data' (response JSON if successful), 
              'message_id' (str from HCS if available), and 'error' (str if failed).
    """

    """Envoie un message HCS spécifique pour les distributions"""
    url = "http://localhost:3001/send-message"
    
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
    """
    Generates funding milestones (paliers) for a given project.

    This function deletes any existing milestones associated with the project
    and creates new ones based on predefined percentage allocations of the
    project's requested amount. Each milestone tracks its percentage and
    corresponding monetary value.

    Args:
        projet (Projet): The project instance for which milestones are created.

    Side Effects:
        - Deletes existing Palier objects linked to the project.
        - Creates new Palier objects with calculated amounts.
    """

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
    """
    Checks if any funding milestones (paliers) of a project are eligible for distribution.

    A milestone is considered ready for distribution if:
    - It has not been transferred yet.
    - The available funds (engaged amount minus already distributed) are sufficient
      to cover the milestone amount.

    Args:
        projet (Projet): The project instance to check.

    Returns:
        bool: True if at least one milestone can be distributed, False otherwise.
    """

    """Vérifier si les paliers peuvent être distribués"""
    montant_disponible = projet.montant_engage - projet.montant_distribue
    
    for palier in projet.paliers.order_by('montant_minimum'):
        if (montant_disponible >= palier.montant and 
            not palier.transfere and 
            palier.montant <= montant_disponible):
            
            return True  # Palier prêt à être distribué
    
    return False


def envoyer_notification_hcs(topic_id, type_notification, details):
    """
    Sends a structured notification message to a Hedera Consensus Service (HCS) topic.

    The message includes the type of notification, a timestamp, and detailed payload.

    Args:
        topic_id (str): The HCS topic ID to send the notification to.
        type_notification (str): The type/category of the notification.
        details (dict): Additional details to include in the message payload.

    Returns:
        dict: Response from the HCS microservice. Returns {"success": False} on failure.
    """

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
        response = requests.post("http://localhost:3001/send-message", json=payload, timeout=10)
        return response.json()
    except Exception as e:
        logger.error(f"Erreur HCS: {e}")
        return {"success": False}



def determiner_type_fichier(nom_fichier):

    """
    Determines the general file type based on the file extension.

    Args:
        nom_fichier (str): The name of the file including its extension.

    Returns:
        str: The type category of the file: 'photo', 'video', 'document', or 'autre' for others.
    """

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


def determiner_type_fichier_avance(fichier):
    """
    Determines the file type using both extension and MIME type verification.

    Args:
        fichier (File): A Django UploadedFile object.

    Returns:
        str: The general file type: 'photo', 'video', 'document', or fallback to simple detection 'autre'.
    """

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


#
# NOTIFICATION  
#


def notifier_soumission_preuve_hcs(projet, palier, nb_fichiers):
    """
    Sends a notification to the HCS (Hedera Consensus Service) about the submission 
    of proof files for a project milestone (palier).

    Args:
        projet (Projet): The project object associated with the milestone.
        palier (Palier): The milestone for which proofs are submitted.
        nb_fichiers (int): Number of files submitted.

    Returns:
        dict: Response from the HCS notification service, indicating success or failure.
    """

    """Notifier dans HCS la soumission de preuves d'un palier"""
    details = {
        "projet": projet.titre,
        "palier": f"{palier.titre}%",
        "fichiers": nb_fichiers,
        "statut": "en_attente"
    }
    
    return envoyer_notification_hcs(
        topic_id=projet.topic_id, 
        type_notification="soumission_preuve",
        details=details
    )


def envoyer_notification_porteur(porteur, palier, action, commentaires=""):
    """
    Sends a notification to the project owner regarding the status of a milestone (palier).

    Args:
        porteur (User): The project owner to notify.
        palier (Palier): The milestone associated with the notification.
        action (str): The type of notification. Options:
                      - 'approuve': milestone approved
                      - 'rejete': milestone rejected
                      - 'modification': changes required
                      - 'distribution': funds distributed
        commentaires (str, optional): Optional comments from the administrator.

    Behavior:
        - Sends an email to the project owner with a formatted message.
        - Optionally sends a message to the HCS (Hedera Consensus Service) topic.
    """

    """Envoie une notification au porteur concernant son palier"""

    projet = palier.projet
    sujet = ""
    message = ""

    if action == 'approuve':
        sujet = f"✅ Palier {palier.titre} approuvé - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},

        Félicitations ! Les preuves que vous avez soumises pour le palier "{palier.titre}" 
        de votre projet "{projet.titre}" ont été approuvées.

        📊 DÉTAILS DU PALIER :
        • Titre : {palier.titre}
        • Montant du palier : {palier.montant} HBAR
        • Description : {palier.description}

        🎯 Prochaines étapes : Le transfert des fonds sera effectué sous peu.

        Cordialement,
        L'équipe SolidAvenir
        """
        type_email = "project_approved"

    elif action == 'rejete':
        sujet = f"❌ Palier {palier.titre} nécessite des modifications - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},

        Les preuves soumises pour le palier "{palier.titre}" de votre projet 
        "{projet.titre}" nécessitent des modifications.

        📋 DÉTAILS DU PALIER :
        • Titre : {palier.titre}
        • Montant : {palier.montant} HBAR

        💬 Commentaires de l'administrateur :
        {commentaires}

        Veuillez soumettre de nouvelles preuves en vous connectant à votre espace.

        Cordialement,
        L'équipe SolidAvenir
        """
        type_email = "project_rejected"

    elif action == 'modification':
        sujet = f"📝 Modifications requises - Palier {palier.titre} - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},

        Des modifications sont requises pour les preuves du palier "{palier.titre}" 
        de votre projet "{projet.titre}".

        📋 DÉTAILS DU PALIER :
        • Titre : {palier.titre}
        • Montant : {palier.montant} HBAR

        🔍 Retour de l'administrateur :
        {commentaires}

        Veuillez apporter les modifications demandées et resoumettre vos preuves.

        Cordialement,
        L'équipe SolidAvenir
        """
        type_email = "notification"

    elif action == 'distribution':
        transaction_url = f"https://hashscan.io/testnet/transaction/{palier.transaction_hash}"
        sujet = f"💰 Transfert effectué - Palier {palier.titre} - {projet.titre}"
        message = f"""
        Bonjour {porteur.get_full_name()},

        Le transfert du palier "{palier.titre}" de votre projet "{projet.titre}" 
        a été effectué avec succès.

        📊 DÉTAILS DU TRANSFERT :
        • Titre du palier : {palier.titre}
        • Montant transféré : {palier.montant} HBAR
        • Date du transfert : {timezone.now().strftime('%d/%m/%Y à %H:%M')}
        • Hash de transaction : {palier.transaction_hash}
        • Lien de vérification : {transaction_url}

        🔍 Vous pouvez vérifier la transaction sur HashScan :
        {transaction_url}

        📝 Description de l'utilisation prévue :
        {palier.description}

        Le montant a été crédité sur votre compte Hedera associé au projet.

        Cordialement,
        L'équipe SolidAvenir
        """
        type_email = "don_received"

    # Création du log d'email avant envoi
    email_log = EmailLog.objects.create(
        destinataire=porteur.email,
        sujet=sujet,
        corps=message,
        type_email=type_email,
        utilisateur=porteur
    )

    # Envoi par email
    try:
        porteur.email_user(sujet, message)
        email_log.marquer_comme_envoye()
        logger.info(f"Notification envoyée à {porteur.email} pour le palier {palier.id}")
    except Exception as e:
        email_log.marquer_comme_erreur(str(e))
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

logger = logging.getLogger(__name__)
def handle_contribution(request, projet, user_has_wallet):
    """
    Handles the submission of a contribution (donation) to a project.

    Security & Validation:
        - Ensures the user is authenticated.
        - Prevents admins from contributing.
        - Only allows contributions to projects with status 'actif'.
        - Requires the user to have a configured wallet.
        - Validates the Transfer_fond form.

    Processing:
        - Creates a Transaction object with status 'en_attente' and destination 'operator'.
        - Updates the project's statistics after saving.
        - Logs a detailed AuditLog entry for the contribution initiation.
        - Optionally sends a notification via HCS (Hedera Consensus Service).

    Error Handling:
        - Catches any exceptions during transaction creation.
        - Logs a failure AuditLog entry.
        - Displays an error message to the user.

    Args:
        request (HttpRequest): The HTTP request object.
        projet (Projet): The project instance to which the contribution is made.
        user_has_wallet (bool): Indicates whether the user has a configured Hedera wallet.

    Returns:
        HttpResponseRedirect: Redirects to 'detail_projet' view with success or error messages.
    """

    """Gère la soumission d'une contribution"""
    #  Vérifications de sécurité
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

    #  Validation du formulaire
    form = Transfer_fond(request.POST, projet=projet, contributeur=request.user)
    
    if not form.is_valid():
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"Erreur {field}: {error}")
        return redirect('detail_projet', audit_uuid=projet.audit_uuid)

    try:
        with transaction.atomic():
            #  Sauvegarde de la transaction
            transaction_obj = form.save(commit=False)
            transaction_obj.projet = projet
            transaction_obj.contributeur = request.user
            transaction_obj.statut = "en_attente"
            transaction_obj.destination = "operator"
            transaction_obj.save()

            #  Mise à jour des statistiques du projet
            projet.refresh_from_db()

            #  AUDIT LOG - Journalisation détaillée
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

            # Notification (optionnelle)
            try:
                # Envoyer une notification HCS
                from .utils import envoyer_notification_contribution
                envoyer_notification_contribution(projet, request.user, transaction_obj.montant)
            except Exception as e:
                logger.error(f"Erreur notification contribution: {e}")

            messages.success(
                request, 
                f"✅ Your contribution of {transaction_obj.montant} HBAR has been recorded! "
                f"It is pending confirmation on the blockchain."
            )
            

    except Exception as e:
        logger.error(f"Erreur lors de la contribution: {e}")
        
        #  AUDIT LOG - Journalisation de l'erreur
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
    """
    Temporary view for wallet configuration.

    Currently, this feature is not implemented and simply informs the user
    that wallet setup will be available soon.

    Args:
        request (HttpRequest): The HTTP request object.

    Returns:
        HttpResponseRedirect: Redirects the user to their profile page with an informational message.
    """

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
    """simple views to send an email"""
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
                
                messages.success(request, f"Email has been successfully sent to {destinataire}")
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
    """views to display all email sent"""
    """Vue pour afficher la liste des emails envoyés"""
    emails = EmailLog.objects.all().order_by('-date_creation')
    return render(request, 'core/emails/liste_email.html', {'emails': emails})
