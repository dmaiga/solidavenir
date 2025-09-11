from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponseForbidden
from django.db import transaction as db_transaction
from django.utils import timezone
from django.core.paginator import Paginator
from .models import Projet, Transaction, User, AuditLog
from .forms import InscriptionForm, CreationProjetForm, DonForm, ValidationProjetForm, ProfilUtilisateurForm, ContactForm
from .services.hedera_service import HederaService
import logging
from django.db.models import Sum,Q,Max,Min
from django.core.mail import send_mail, EmailMessage
from django.conf import settings
from datetime import timedelta
logger = logging.getLogger(__name__)

# Dans views.py
from django.shortcuts import render
from django.db.models import Sum, Q, Count
from .models import Projet, Transaction, User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect

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
    
    return render(request, 'core/connexion.html')

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
    
    return render(request, 'core/accueil.html', context)
#
#
def liste_projets(request):
    """Liste de tous les projets actifs avec pagination"""
    projets_list = Projet.objects.filter(statut='actif').annotate(
        montant_collectes=Sum('transaction__montant', filter=Q(transaction__statut='confirme')),
        nombre_donateurs=Count('transaction__donateur', filter=Q(transaction__statut='confirme'), distinct=True)
    ).order_by('-date_creation')
    
    # Calculer le pourcentage de financement et durée restante
   
    
    # Pagination - 9 projets par page
    paginator = Paginator(projets_list, 9)
    page_number = request.GET.get('page')
    projets = paginator.get_page(page_number)
    
    return render(request, 'core/liste_projets.html', {'projets': projets})

def detail_projet(request, audit_uuid):
    """Détail d'un projet spécifique avec possibilité de don"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    # Seuls les projets actifs ou terminés sont visibles par le public
    if projet.statut not in ['actif', 'termine'] and not request.user.is_staff:
        messages.error(request, "Ce projet n'est pas accessible.")
        return redirect('liste_projets')
    
    # Récupérer des projets similaires
    projets_similaires = Projet.objects.filter(
        statut='actif'
    ).exclude(
        audit_uuid=audit_uuid
    )[:3]
    
    transactions = Transaction.objects.filter(projet=projet, statut='confirme').order_by('-date_transaction')[:10]
    
    if request.method == 'POST':
        if not request.user.is_authenticated:
            messages.info(request, "Connectez-vous pour faire un don.")
            return redirect('connexion')
        
        if request.user.user_type != 'donateur':
            messages.error(request, "Seuls les donateurs peuvent effectuer des dons.")
            return redirect('detail_projet', audit_uuid=audit_uuid)
        
        form = DonForm(request.POST, projet=projet, donateur=request.user)
        if form.is_valid():
            return _process_don(request, form, projet)
    else:
        form = DonForm(projet=projet, donateur=request.user if request.user.is_authenticated else None)
    
    return render(request, 'core/detail_projet.html', {
        'projet': projet,
        'transactions': transactions,
        'form': form,
        'projets_similaires': projets_similaires,
        'pourcentage': projet.pourcentage_financement  
    })

@db_transaction.atomic
def _process_don(request, form, projet):
    """Traitement d'un don avec intégration Hedera - Version corrigée"""
    try:
        montant = form.cleaned_data['montant']
        
        # Vérifications de sécurité
        if not request.user.hedera_account_id:
            messages.error(request, "Veuillez configurer votre compte Hedera dans votre profil.")
            return redirect('detail_projet', audit_uuid=projet.audit_uuid)
        
        # Récupérer la clé privée déchiffrée
        private_key = request.user.get_hedera_private_key()
        if not private_key:
            messages.error(request, "Problème de sécurité avec votre compte. Contactez l'administrateur.")
            return redirect('detail_projet', audit_uuid=projet.audit_uuid)
        
        # Vérifier le solde
        hedera_service = HederaService()
        solde = hedera_service.get_account_balance(request.user.hedera_account_id)
        if solde < float(montant):
            messages.error(request, f"Solde insuffisant. Votre solde: {solde:.2f} HBAR")
            return redirect('detail_projet', audit_uuid=projet.audit_uuid)
        
        # Effectuer la transaction
        transaction_hash = hedera_service.effectuer_transaction(
            request.user.hedera_account_id,
            private_key,  # Clé déjà déchiffrée
            projet.porteur.hedera_account_id,
            float(montant)
        )
        
        # Création de l'enregistrement de transaction
        transaction = Transaction.objects.create(
            montant=montant,
            hedera_transaction_hash=transaction_hash,
            donateur=request.user,
            projet=projet,
            statut='confirme'
        )
        
        # Journalisation de l'audit
        AuditLog.objects.create(
            utilisateur=request.user,
            action='create',
            modele='Transaction',
            objet_id=str(transaction.audit_uuid),
            details={
                'montant': float(montant),
                'projet': projet.titre,
                'transaction_hash': transaction_hash
            },
            adresse_ip=request.META.get('REMOTE_ADDR')
        )
        
        # Mise à jour du montant collecté
        projet.montant_collecte += montant
        if projet.montant_collecte >= projet.montant_demande:
            projet.statut = 'termine'
            messages.success(request, "Félicitations! Ce projet est maintenant entièrement financé!")
        
        projet.save()
        
        messages.success(request, f"Don de {montant:.0f} FCFA effectué avec succès!")
        return redirect('confirmation_don', transaction_audit_uuid=transaction.audit_uuid)
        
    except Exception as e:
        logger.error(f"Erreur lors du don: {str(e)}")
        
        # Journalisation de l'erreur
        AuditLog.objects.create(
            utilisateur=request.user,
            action='error',
            modele='Transaction',
            details={
                'erreur': str(e),
                'projet': projet.titre,
                'montant_tente': float(montant) if 'montant' in locals() else 'inconnu'
            },
            adresse_ip=request.META.get('REMOTE_ADDR')
        )
        
        messages.error(request, "Une erreur s'est produite lors du traitement de votre don. Veuillez réessayer.")
        return redirect('detail_projet', audit_uuid=projet.audit_uuid)


def confirmation_don(request, transaction_audit_uuid):
    """Page de confirmation après un don"""
    transaction = get_object_or_404(Transaction, audit_uuid=transaction_audit_uuid)
    
    # Vérifier que l'utilisateur a le droit de voir cette transaction
    if request.user != transaction.donateur and not request.user.is_staff:
        return HttpResponseForbidden("Accès non autorisé.")
    
    return render(request, 'core/confirmation_don.html', {'transaction': transaction})

def inscription(request):
    """Inscription d'un nouvel utilisateur"""
    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            # Journalisation audit
            AuditLog.objects.create(
                utilisateur=user,
                action='create',
                modele='User',
                objet_id=str(user.audit_uuid),
                details={'user_type': user.user_type},
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            # Connexion automatique
            login(request, user)
            messages.success(request, f"Bienvenue {user.username}! Votre compte a été créé avec succès.")
            
            # Redirection selon le type d'utilisateur
            if user.user_type == 'porteur':
                return redirect('creer_projet')
            else:
                return redirect('accueil')
    else:
        form = InscriptionForm()
    
    return render(request, 'core/inscription.html', {'form': form})

@login_required
def creer_projet(request):
    """Création d'un nouveau projet avec gestion des fichiers"""
    if request.user.user_type != 'porteur':
        messages.error(request, "Seuls les porteurs de projet peuvent créer des projets.")
        return redirect('accueil')
    
    # Vérifier le nombre de projets en cours
    projets_en_cours = Projet.objects.filter(
        porteur=request.user, 
        statut__in=['actif', 'en_attente', 'brouillon']
    ).count()
    
    if projets_en_cours >= 5:
        messages.error(request, "Vous avez déjà 5 projets en cours. Veuillez en terminer un avant d'en créer un nouveau.")
        return redirect('mes_projets')
    
    if request.method == 'POST':
        form = CreationProjetForm(request.POST, request.FILES, porteur=request.user)
        if form.is_valid():
            try:
                projet = form.save()
                
                # Journalisation audit
                AuditLog.objects.create(
                    utilisateur=request.user,
                    action='create',
                    modele='Projet',
                    objet_id=str(projet.audit_uuid),
                    details={
                        'titre': projet.titre, 
                        'montant': float(projet.montant_demande),
                        'statut': projet.statut
                    },
                    adresse_ip=request.META.get('REMOTE_ADDR')
                )
                
                # Envoyer un email de confirmation
                try:
                    send_mail(
                        'Votre projet a été créé - Solid\'Avenir',
                        f'Bonjour {request.user.get_full_name() or request.user.username},\n\n'
                        f'Votre projet "{projet.titre}" a été créé avec succès.\n'
                        f'Montant demandé: {projet.montant_demande:,} FCFA\n'
                        f'Statut: {projet.get_statut_display()}\n\n'
                        f'Il sera examiné par notre équipe dans les plus brefs délais.\n\n'
                        f'Cordialement,\nL\'équipe Solid\'Avenir',
                        settings.DEFAULT_FROM_EMAIL,
                        [request.user.email],
                        fail_silently=True,
                    )
                except Exception as e:
                    logger.error(f"Erreur envoi email création projet: {str(e)}")
                
                messages.success(request, 
                    "Votre projet a été créé avec succès! "
                    "Il sera examiné par notre équipe dans les 48h."
                )
                return redirect('mes_projets')
                
            except Exception as e:
                logger.error(f"Erreur création projet: {str(e)}")
                messages.error(request, 
                    "Une erreur est survenue lors de la création du projet. "
                    "Veuillez réessayer."
                )
    else:
        form = CreationProjetForm(porteur=request.user)
    
    context = {
        'form': form,
        'projets_en_cours': projets_en_cours,
        'limite_projets': 5
    }
    
    return render(request, 'core/creer_projet.html', context)

@login_required
def mes_projets(request):
    """Liste des projets de l'utilisateur connecté avec statistiques"""
    if request.user.user_type != 'porteur':
        messages.error(request, "Accès réservé aux porteurs de projet.")
        return redirect('accueil')
    
    # Récupérer tous les projets du porteur avec annotations
    projets = Projet.objects.filter(porteur=request.user).annotate(
        nombre_donateurs=Count('transaction__donateur', filter=Q(transaction__statut='confirme'), distinct=True),
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
    
    return render(request, 'core/mes_projets.html', context)


@login_required
def mes_dons(request):
    """Historique des dons de l'utilisateur connecté"""
    if request.user.user_type != 'donateur':
        messages.error(request, "Accès réservé aux donateurs.")
        return redirect('accueil')
    
    dons = Transaction.objects.filter(donateur=request.user).select_related('projet').order_by('-date_transaction')
    total_dons = sum(don.montant for don in dons)
    
    return render(request, 'core/mes_dons.html', {
        'dons': dons,
        'total_dons': total_dons
    })

@login_required
def modifier_profil(request):
    """Modification du profil utilisateur"""
    if request.method == 'POST':
        form = ProfilUtilisateurForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            
            # Journalisation audit
            AuditLog.objects.create(
                utilisateur=request.user,
                action='update',
                modele='User',
                objet_id=str(request.user.audit_uuid),
                details={'champs_modifies': list(form.changed_data)},
                adresse_ip=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('modifier_profil')
    else:
        form = ProfilUtilisateurForm(instance=request.user)
    
    return render(request, 'core/modifier_profil.html', {'form': form})

def transparence(request):
    """Page de transparence avec toutes les transactions vérifiables"""
    transactions = Transaction.objects.filter(statut='confirme').select_related('projet').order_by('-date_transaction')
    
    # Statistiques de transparence
    stats = {
        'total_dons': sum(t.montant for t in transactions),
        'total_transactions': transactions.count(),
        'projets_finances': len(set(t.projet_id for t in transactions)),
    }
    
    # Pagination
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'core/transparence.html', {
        'transactions': page_obj,
        'stats': stats
    })


from .models import Projet, AuditLog
from .forms import ValidationProjetForm
from .services.hedera_service import HederaService

logger = logging.getLogger(__name__)

@login_required
@permission_required('core.validate_project', raise_exception=True)
def valider_projet(request, audit_uuid):
    """Validation d'un projet par un administrateur avec gestion complète"""
    projet = get_object_or_404(Projet, audit_uuid=audit_uuid)
    
    # Vérifier que le projet est en attente de validation
    if projet.statut not in ['en_attente', 'brouillon']:
        messages.warning(request, f"Ce projet est déjà {projet.get_statut_display().lower()}.")
        return redirect('valider_projet')  # Redirection vers une vue existante
    
    # Initialiser le service Hedera
    hedera_service = HederaService()
    
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
            
           
            return redirect('valider_projet')
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
    
    return render(request, 'core/valider_projet.html', context)

def contact(request):
    """Page de contact"""
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            # Ici vous pourriez envoyer un email ou enregistrer le message
            messages.success(request, "Votre message a été envoyé avec succès!")
            return redirect('contact')
    else:
        form = ContactForm()
    
    return render(request, 'core/contact.html', {'form': form})


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
        'porteurs_total': User.objects.filter(user_type='porteur').count(),
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
        'projet', 'donateur'
    ).order_by('-date_transaction')[:10]
    
    # Derniers logs d'audit
    recent_audits = AuditLog.objects.select_related(
        'utilisateur'
    ).order_by('-date_action')[:10]
    
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
    }
    
    return render(request, 'core/tableau_de_bord.html', context)