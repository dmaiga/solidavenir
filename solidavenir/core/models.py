from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
import uuid
from cryptography.fernet import Fernet
from django.conf import settings
import hashlib
from django.core.validators import FileExtensionValidator
import logging
logger = logging.getLogger('audit')
from django.utils import timezone

from django.db.models import Sum,Q
from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from cryptography.fernet import Fernet
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid
from django.core.validators import FileExtensionValidator
from django.core.exceptions import ValidationError
import requests
from decimal import Decimal
# --- MODELE PRINCIPAL PROJET ---
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Sum, Q
import uuid
from datetime import timedelta

from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
import uuid
# --- VALIDATEURS PERSONNALISÉS ---
from django.core.exceptions import ValidationError

from decimal import Decimal
import math


def validate_profile_image_size(value):
    """Valide que l'image de profil ne dépasse pas 5 Mo"""
    limit = 5 * 1024 * 1024  # 5 Mo
    if value.size > limit:
        raise ValidationError("La taille maximale de l'image de profil est de 5 Mo.")

def validate_file_size(value):
    """Vérifie que le fichier ne dépasse pas 10 Mo"""
    limit = 10 * 1024 * 1024  # 10 Mo
    if value.size > limit:
        raise ValidationError("La taille maximale autorisée est de 10 Mo.")

from decimal import Decimal, ROUND_HALF_UP
from django.core.cache import cache
import requests
import logging

logger = logging.getLogger(__name__)

# =============================================================================
# FONCTIONS DE CONVERSION DE DEVISES
# =============================================================================

def get_hbar_to_usd():
    """Récupère le prix HBAR/USD avec cache"""
    cache_key = 'hbar_usd_rate'
    cached_rate = cache.get(cache_key)
    
    if cached_rate:
        return cached_rate
    
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "hedera-hashgraph", "vs_currencies": "usd"},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        rate = Decimal(str(data["hedera-hashgraph"]["usd"]))
        
        # Cache pour 5 minutes
        cache.set(cache_key, rate, 300)
        return rate
        
    except Exception as e:
        logger.error(f"Erreur récupération taux HBAR/USD: {e}")
        # Retourner un taux par défaut en cas d'erreur
        return Decimal('0.07')

def get_usd_to_fcfa():
    """Taux USD/FCFA (fixe ou API)"""
    # Pour l'Afrique de l'Ouest, taux approximatif
    return Decimal('600')

def convert_hbar_to_fcfa(hbar_amount):
    """Convertit HBAR vers FCFA"""
    if not isinstance(hbar_amount, Decimal):
        hbar_amount = Decimal(str(hbar_amount))
    
    usd_rate = get_hbar_to_usd()
    fcfa_rate = get_usd_to_fcfa()
    return (hbar_amount * usd_rate * fcfa_rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def convert_fcfa_to_hbar(fcfa_amount):
    """Convertit FCFA vers HBAR"""
    if not isinstance(fcfa_amount, Decimal):
        fcfa_amount = Decimal(str(fcfa_amount))
    
    usd_rate = get_hbar_to_usd()
    fcfa_rate = get_usd_to_fcfa()
    if usd_rate == 0:
        raise ValueError("Taux de conversion indisponible")
    return (fcfa_amount / fcfa_rate / usd_rate).quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)

class User(AbstractUser):
    USER_TYPES = (
        ('admin', 'Administrateur'),
        ('porteur', 'Porteur de Projet'),
        ('donateur', 'Donateur/Philanthrope'),
        ('investisseur', 'Investisseur'),
        ('association', 'Association/ONG'),
    )
    
    FINANCEMENT_CHOICES = (
        ('don', 'Don pur'),
        ('pret', 'Prêt'),
        ('equity', 'Investissement en equity'),
        ('mixte', 'Financement mixte'),
        ('autre', 'Autre type de financement'),
    )
    
    GENRE_CHOICES = (
        ('homme', 'Homme'),
        ('femme', 'Femme'),
        ('autre', 'Autre'),
        ('non_specifie', 'Non spécifié'),
    )
    
    user_type = models.CharField(max_length=15, choices=USER_TYPES, default='porteur')
    type_financement = models.CharField(max_length=10, choices=FINANCEMENT_CHOICES, blank=True, null=True)
    
    # Photo de profil
    photo_profil = models.ImageField(
        upload_to='profiles/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'gif']),
            validate_profile_image_size
        ],
        help_text="Photo de profil (format carré recommandé, max 5 Mo)"
    )
    
    # Informations de base pour tous les utilisateurs
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    ville = models.CharField(max_length=100, blank=True, null=True)
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    pays = models.CharField(max_length=100, blank=True, null=True)
    genre = models.CharField(max_length=15, choices=GENRE_CHOICES, default='non_specifie')
    bio = models.TextField(blank=True, null=True, help_text="Une brève description de vous-même")
    
    # Réseaux sociaux et contacts
    site_web_perso = models.URLField(blank=True, null=True, help_text="Votre site web personnel")
    linkedin = models.URLField(blank=True, null=True, help_text="Votre profil LinkedIn")
    twitter = models.URLField(blank=True, null=True, help_text="Votre profil Twitter")
    facebook = models.URLField(blank=True, null=True, help_text="Votre profil Facebook")
    
    # Hedera blockchain (optionnel pour MVP)
    hedera_account_id = models.CharField(max_length=50, blank=True, null=True)
    hedera_private_key = models.TextField(blank=True, null=True) 
    hedera_public_key = models.TextField(blank=True, null=True) 
    
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    wallet_activated = models.BooleanField(default=False)
    # Champs pour porteurs de projet - Tous optionnels
    organisation = models.CharField(max_length=100, blank=True, null=True, 
                                  help_text="Nom de votre entreprise, startup, ou structure")
    site_web = models.URLField(blank=True, null=True, help_text="Site web de votre projet")
    description_projet = models.TextField(blank=True, null=True, help_text="Décrivez brièvement votre projet")
    montant_recherche = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                          help_text="Montant approximatif recherché")
    date_creation_profile = models.DateTimeField(auto_now_add=True)
    # Champs pour associations/ONG - Tous optionnels
    nom_association = models.CharField(max_length=200, blank=True, null=True)
    causes_defendues = models.TextField(blank=True, null=True)
    domaine_action = models.CharField(max_length=100, blank=True, null=True)
    date_creation_association = models.DateField(blank=True, null=True)
    
    # Champs pour investisseurs - Tous optionnels
    type_investisseur = models.CharField(max_length=50, blank=True, null=True, 
                                       choices=[('', 'Non spécifié'),
                                               ('particulier', 'Particulier'),
                                               ('institutionnel', 'Institutionnel'),
                                               ('business_angel', 'Business Angel'),
                                               ('fond_investissement', 'Fonds d\'investissement'),
                                               ('autre', 'Autre')])
    secteur_prefere = models.CharField(max_length=100, blank=True, null=True)
    montant_investissement_min = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    montant_investissement_max = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    expectative_rendement = models.CharField(max_length=100, blank=True, null=True)
    
    # Champs pour donateurs/philanthropes - Tous optionnels
    causes_soutenues = models.TextField(blank=True, null=True)
    montant_don_moyen = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True)
    frequence_dons = models.CharField(max_length=50, blank=True, null=True,
                                    choices=[('', 'Non spécifié'),
                                            ('ponctuel', 'Ponctuel'),
                                            ('mensuel', 'Mensuel'),
                                            ('trimestriel', 'Trimestriel'),
                                            ('annuel', 'Annuel')])
    
    # Champs pour administrateurs - Optionnels
    departement = models.CharField(max_length=100, blank=True, null=True)
    role_admin = models.CharField(max_length=100, blank=True, null=True)
    
    # Préférences et consentements
    newsletter = models.BooleanField(default=True)
    consentement_rgpd = models.BooleanField(default=True)
    date_consentement = models.DateTimeField(blank=True, null=True)
    
    # Métadonnées
    date_inscription = models.DateTimeField(auto_now_add=True)
    date_derniere_connexion = models.DateTimeField(blank=True, null=True)
    email_verifie = models.BooleanField(default=False)
    telephone_verifie = models.BooleanField(default=False)
    
    class Meta:
        permissions = [
            ("can_audit", "Peut effectuer des audits de transparence"),
            ("manage_users", "Peut gérer tous les utilisateurs"),
            ("manage_projects", "Peut gérer tous les projets"),
            ("manage_transactions", "Peut gérer toutes les transactions"),
            ("view_dashboard", "Peut voir le tableau de bord administrateur"),
        ]
        ordering = ['-date_joined']
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"
    
    def get_full_name_or_username(self):
        """Retourne le nom complet ou le username si le nom n'est pas disponible"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username
    
    def get_profile_picture_url(self):
        """Retourne l'URL de la photo de profil ou une image par défaut"""
        if self.photo_profil:
            return self.photo_profil.url
        return '/static/images/default-profile.png'
    
    def get_profile_display_picture(self):
        """Retourne la photo de profil ou les initiales pour l'avatar"""
        if self.photo_profil:
            return f'<img src="{self.photo_profil.url}" class="profile-picture" alt="{self.get_full_name_or_username()}">'
        else:
            initials = ''
            if self.first_name:
                initials += self.first_name[0].upper()
            if self.last_name:
                initials += self.last_name[0].upper()
            if not initials:
                initials = self.username[0:2].upper()
            return f'<div class="avatar-initials">{initials}</div>'
    
    # Méthodes simplifiées pour le MVP
    def is_administrator(self):
        return self.user_type == 'admin'
    
    def is_porteur_projet(self):
        return self.user_type == 'porteur'
    
    def is_investisseur(self):
        return self.user_type == 'investisseur'
    
    def is_association(self):
        return self.user_type == 'association'
    
    def is_donateur(self):
        return self.user_type == 'donateur'
    
    def get_profile_completion(self):
        """Calcule le pourcentage de complétion du profil"""
        fields_to_check = [
            'email', 'first_name', 'last_name', 'telephone', 
            'adresse', 'ville', 'pays', 'bio'
        ]
        
        completed = 0
        for field in fields_to_check:
            value = getattr(self, field)
            if value and str(value).strip():
                completed += 1
        
        # Bonus pour la photo de profil
        if self.photo_profil:
            completed += 2  # La photo compte un peu plus
        
        total_score = len(fields_to_check) + 2  # Total possible avec bonus photo
        percentage = (completed / total_score) * 100
        return min(round(percentage), 100)  # Maximum 100%
    
    def get_projets_actifs(self):
        return self.projet_set.filter(statut='actif')
    
    def get_projets_termines(self):
        return self.projet_set.filter(statut__in=['termine', 'echec'])
    
    def get_total_collecte(self):
        return self.projet_set.aggregate(
            total=Sum('montant_collecte')
        )['total'] or 0
    
    def get_nombre_projets_lances(self):
        return self.projet_set.count()
    
    def get_taux_reussite(self):
        projets_termines = self.projet_set.filter(statut__in=['termine', 'echec'])
        if not projets_termines.exists():
            return 0
        
        reussis = projets_termines.filter(statut='termine').count()
        return round((reussis / projets_termines.count()) * 100, 1)
    
    def get_user_type_icon(self):
        """Retourne une icône selon le type d'utilisateur"""
        icons = {
            'admin': 'bi-shield',
            'porteur': 'bi-lightbulb',
            'donateur': 'bi-heart',
            'investisseur': 'bi-graph-up',
            'association': 'bi-people'
        }
        return icons.get(self.user_type, 'bi-person')
    
    def get_age(self):
        """Calcule l'âge de l'utilisateur si date_naissance est renseignée"""
        if self.date_naissance:
            today = date.today()
            return today.year - self.date_naissance.year - (
                (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
            )
        return None
    
    def update_last_login(self):
        """Met à jour la date de dernière connexion"""
        self.date_derniere_connexion = timezone.now()
        self.save(update_fields=['date_derniere_connexion'])
    def has_active_wallet(self):
        return self.wallet_activated and bool(self.hedera_account_id)
    
    def peut_contribuer(self):
        """Vérifie si l'utilisateur peut faire des contributions"""
        return self.user_type != 'admin' and self.is_authenticated
    
    def ensure_wallet(self):
        """Crée un wallet automatiquement s'il n'existe pas"""
        if not self.hedera_account_id or not self.wallet_activated:
            try:
                # Appeler le service Node.js pour créer un wallet
                response = requests.post(
                    'http://hedera_service:3001/create-wallet',
                    json={'initialBalance': 50},
                    timeout=10
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result['success']:
                        # Stocker les informations du wallet
                        self.hedera_account_id = result['accountId']
                        # ⚠️ IMPORTANT: Stocker la clé privée de manière sécurisée
                        # Dans un environnement de production, utilisez un service de gestion de secrets
                        self.hedera_public_key = result['publicKey']
                        self.hedera_private_key = result['privateKey']
                        self.wallet_activated = True
                        self.save()
                        return True
            except Exception as e:
                print(f"Erreur création wallet: {e}")
                return False
        return True
    
    @property
    def has_active_wallet(self):
        """Vérifie si l'utilisateur a un wallet actif"""
        return self.wallet_activated and bool(self.hedera_account_id)

User = get_user_model()

class Projet(models.Model):
    """
    Représente un projet de financement participatif porté par un utilisateur.
    """

    STATUTS = (
        ('brouillon', 'Brouillon'),
        ('en_attente', 'En attente de validation'),
        ('actif', 'Actif - Campagne en cours'),
        ('suspendu', 'Suspendu temporairement'),
        ('termine', 'Terminé avec succès'),
        ('echec', 'Échec de la campagne'),
        ('annule', 'Annulé'),
        ('rejete', 'Rejeté'),
    )

    TYPES_FINANCEMENT = (
        ('don', 'Dons uniquement'),
        ('pret', 'Prêt avec remboursement'),
        ('equity', 'Investissement en equity'),
        ('recompense', 'Financement avec récompenses'),
        ('mixte', 'Financement mixte'),
    )
    
    
    CATEGORIES = (
        ('agriculture', 'Agriculture et Agroalimentaire'),
        ('artisanat', 'Artisanat et Métiers'),
        ('commerce', 'Commerce et Vente'),
        ('education', 'Éducation et Formation'),
        ('sante', 'Santé et Bien-être'),
        ('technologie', 'Technologie et Innovation'),
        ('energie', 'Énergie et Environnement'),
        ('tourisme', 'Tourisme et Hôtellerie'),
        ('culture', 'Culture et Arts'),
        ('social', 'Social et Communautaire'),
        ('sport', 'Sport et Loisirs'),
        ('immobilier', 'Immobilier et Construction'),
        ('transport', 'Transport et Mobilité'),
        ('finance', 'Finance et Microcrédit'),
        ('autre', 'Autre domaine'),
    )

    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    titre = models.CharField(max_length=250)
    slug = models.SlugField(max_length=300, unique=True, blank=True)
    description = models.TextField()
    description_courte = models.CharField(max_length=300, help_text="Description résumée pour les listes")
    identifiant_unique = models.CharField(
        max_length=240, 
        unique=True,
        blank=True,
        null=True,
        help_text="Identifiant unique du projet, généré automatiquement"
    )
    # Informations financières
    #hedera
    hedera_account_id = models.CharField(max_length=100, blank=True, null=True)
    hedera_private_key = models.CharField(max_length=500, blank=True, null=True)
    montant_engage = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    montant_distribue = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    montant_demande = models.DecimalField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    montant_minimal = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        help_text="Montant minimum à atteindre pour que le projet soit financé"
    )

    montant_collecte = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    type_financement = models.CharField(max_length=10, choices=TYPES_FINANCEMENT, default='don')
    wallet_configure = models.BooleanField(
        default=False,
        help_text="Indique si le wallet est configuré pour les transactions"
    )
    topic_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    hedera_topic_created = models.BooleanField(
        default=False,
        help_text="Indique si le topic HCS a été créé sur Hedera"
    )
    hedera_topic_transaction_id = models.CharField(
        max_length=150, 
        blank=True, 
        null=True,
        help_text="Transaction ID de création du topic HCS"
    )
    hedera_topic_hashscan_url = models.URLField(
        blank=True, 
        null=True,
        help_text="URL HashScan pour le topic HCS"
    )
    # Médias
    cover_image = models.ImageField(
        upload_to='covers/projets/',
        blank=True,
        null=True,
        help_text="Image de couverture du projet (recommandé: 1200x600px)"
    )
    video_presentation = models.URLField(blank=True, null=True, help_text="Lien vers une vidéo de présentation")

    # Dates
    date_debut = models.DateTimeField(null=True, blank=True, help_text="Date de début de la campagne de financement")
    date_fin = models.DateTimeField(null=True, blank=True, help_text="Date de fin de la campagne de financement")
    duree_campagne = models.PositiveIntegerField(default=30, help_text="Durée de la campagne en jours")

    porteur = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'porteur'})
    association = models.ForeignKey(
        'Association',
        on_delete=models.CASCADE,
        related_name='projets',
        null=True, blank=True,
        help_text="Association porteuse du projet"
    )
    # Validation admin
    valide_par = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='projets_valides', limit_choices_to={'user_type': 'admin'}
    )
    date_validation = models.DateTimeField(null=True, blank=True)
    motif_rejet = models.TextField(blank=True, null=True)

    # Métriques
    vues = models.PositiveIntegerField(default=0)
    contributeurs_count = models.PositiveIntegerField(default=0)
    partages = models.PositiveIntegerField(default=0)

    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    statut = models.CharField(max_length=20, choices=STATUTS, default='en_attente')

    # Catégorisation
    categorie = models.CharField(
        max_length=200, 
        choices=CATEGORIES, 
        default='commerce',
        verbose_name="Catégorie du projet"
    )
    autre_categorie = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        verbose_name="Autre catégorie (si autre est sélectionné)"
    )
    tags = models.CharField(max_length=200, null=True, blank=True)

    # Documents justificatifs
    document_justificatif = models.FileField(
        upload_to='documents/projets/',
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'jpg', 'png']),
            validate_file_size
        ]
    )
    plan_financement = models.FileField(upload_to='documents/projets/', blank=True, null=True, validators=[validate_file_size])
    budget_detaille = models.FileField(upload_to='documents/projets/', blank=True, null=True, validators=[validate_file_size])

    # Blockchain
    blockchain_tx_id = models.CharField(max_length=250, blank=True, null=True)
    wallet_url = models.URLField(blank=True, null=True, help_text="URL vers la page de contribution sur le serveur Node.js")
    # Récompenses (intégrées directement dans le modèle)
    has_recompenses = models.BooleanField(default=False)
    recompenses_description = models.TextField(blank=True, null=True, help_text="Description des récompenses pour contributeurs")
    commission = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=2,
        help_text="Pourcentage de commission retenue par la plateforme avant distribution au porteur"
    )
    class Meta:
        indexes = [
            models.Index(fields=['audit_uuid']),
            models.Index(fields=['statut']),
            models.Index(fields=['porteur']),
            models.Index(fields=['date_fin']),
            models.Index(fields=['categorie']),
            models.Index(fields=['montant_demande']),
            models.Index(fields=['type_financement']),
        ]
        ordering = ['-date_creation']
        permissions = [
            ("validate_project", "Peut valider un projet"),
            ("suspend_project", "Peut suspendre un projet"),
            ("view_analytics", "Peut voir les analytics des projets"),
        ]


    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.titre)
            original_slug = self.slug
            counter = 1
            while Projet.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        if self.date_debut and self.duree_campagne and not self.date_fin:
            self.date_fin = self.date_debut + timedelta(days=self.duree_campagne)
        
        if self.montant_collecte > 0:
            # Import local pour éviter circularité
            from .views import verifier_paliers
            verifier_paliers(self)
        
        # Si la catégorie n'est pas "autre", effacer le champ autre_categorie
        if self.categorie != 'autre' and self.autre_categorie:
            self.autre_categorie = None
        
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.titre} - {self.get_statut_display()}"

    @property
    def categorie_display(self):
        """Retourne la catégorie affichable avec gestion de 'autre'"""
        if self.categorie == 'autre' and self.autre_categorie:
            return f"📦 {self.autre_categorie}"
        return self.get_categorie_display()
    # --- PERMISSIONS ---
    def peut_etre_modifie_par(self, user):
        if user.is_administrator():
            return True
        return self.porteur == user and self.statut in ['brouillon', 'en_attente', 'actif']
    @property
    def est_associe_a_une_association(self):
        """Vérifie si le projet est associé à une association"""
        return self.association is not None
    # --- STATUTS UTILES ---
    @property
    def est_actif(self):
        return self.statut == 'actif'

    @property
    def est_termine(self):
        return self.statut in ['termine', 'echec', 'annule']

    # --- FINANCES ---
    @property
    def montant_restant(self):
        return max(0, self.montant_demande - (self.montant_collecte or 0))

    @property
    def pourcentage_financement(self):
        """Pourcentage basé sur le montant engagé (déposé chez l'opérateur)"""
        if self.montant_demande == 0:
            return 0
        
        # Utiliser montant_engage au lieu de montant_collecte
        montant_engage = self.montant_engage or 0
        return round((montant_engage / self.montant_demande) * 100, 1)

    @property
    def objectif_atteint(self):
        """Vérifie si le montant engagé atteint l'objectif"""
        return self.montant_engage >= self.montant_demande
    
    @property
    def objectif_minimal_atteint(self):
        """Vérifie si le montant engagé atteint l'objectif minimal"""
        return self.montant_engage >= self.montant_minimal

    def montant_actuel(self):
        from django.db.models import Sum
        return self.transaction_set.filter(statut='confirme').aggregate(
            total=Sum('montant')
        )['total'] or 0

    # --- TEMPS ---
    @property
    def jours_restants(self):
        if self.date_fin:
            delta = self.date_fin - timezone.now()
            return max(0, delta.days)
        return 0

    @property
    def jours_ecoules(self):
        if self.date_debut:
            delta = timezone.now() - self.date_debut
            return min(delta.days, self.duree_campagne)
        return 0

    # --- METRIQUES ---
    @property
    def taux_conversion(self):
        if self.vues == 0:
            return 0
        return round((self.contributeurs_count / self.vues) * 100, 2)
    @property
    def has_hedera_topic(self):
        return bool(self.topic_id and self.hedera_topic_created)
    
    @property
    def topic_hashscan_link(self):
        if self.topic_id:
            return f"https://hashscan.io/testnet/topic/{self.topic_id}"
        return None
 
    @property
    def stats_contributeurs(self):
        """Statistiques avancées des contributeurs"""
        from django.db.models import Count, Avg
        stats = Transaction.objects.filter(
            projet=self, 
            statut='confirme',
            destination='operator'
        ).aggregate(
            total_contributeurs=Count('contributeur', distinct=True),
            don_moyen=Avg('montant'),
            don_max=Max('montant'),
            don_min=Min('montant')
        )
        return stats


    def incrementer_vues(self):
        self.vues += 1
        self.save(update_fields=['vues'])

    def incrementer_partages(self):
        self.partages += 1
        self.save(update_fields=['partages'])
        
    def generer_identifiant_unique(self):
        if not self.identifiant_unique and self.id:
            self.identifiant_unique = f"SOLID{self.id:06d}{timezone.now().strftime('%Y%m%d')}"
    # --- ACTIONS ---
    def demarrer_campagne(self, admin_user=None):
        """Passe le projet en statut 'actif' si en attente et fixe dates."""
        if self.statut == 'en_attente':
            self.statut = 'actif'
            self.date_debut = timezone.now()
            self.date_fin = self.date_debut + timedelta(days=self.duree_campagne)
            if admin_user and admin_user.is_administrator():
                self.valide_par = admin_user
                self.date_validation = timezone.now()
            self.save(update_fields=['statut', 'date_debut', 'date_fin', 'valide_par', 'date_validation'])
            return True
        return False

    def annuler(self, motif=""):
        """Annule un projet en cours"""
        self.statut = 'annule'
        if motif:
            self.motif_rejet = motif
        self.save(update_fields=['statut', 'motif_rejet'])

    def rejeter(self, motif=""):
        """Rejette un projet en attente"""
        self.statut = 'rejete'
        self.motif_rejet = motif
        self.save(update_fields=['statut', 'motif_rejet'])

    def verifier_statut(self):
        """Met à jour automatiquement le statut si la campagne est terminée"""
        if self.statut == 'actif' and self.date_fin and timezone.now() > self.date_fin:
            if self.objectif_minimal_atteint:
                self.statut = 'termine'
            else:
                self.statut = 'echec'
            self.save(update_fields=['statut'])

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('detail_projet', kwargs={'audit_uuid': str(self.audit_uuid)})
    
    def peut_etre_modifie_par(self, user):
        """Vérifie si l'utilisateur peut modifier ce projet"""
        if not user.is_authenticated:
            return False
        if user.is_staff:
            return True
        if user == self.porteur:
            return True
        if hasattr(user, 'association_profile') and user.association_profile == self.association:
            return True
        return False

    @property
    def montant_demande_fcfa(self):
        """Montant demandé en FCFA"""
        try:
            return convert_hbar_to_fcfa(self.montant_demande)
        except Exception as e:
            logger.error(f"Erreur conversion montant_demande: {e}")
            return Decimal('0')

    @property
    def montant_engage_fcfa(self):
        """Montant engagé en FCFA"""
        try:
            return convert_hbar_to_fcfa(self.montant_engage or 0)
        except Exception as e:
            logger.error(f"Erreur conversion montant_engage: {e}")
            return Decimal('0')
    
    @property
    def montant_restant_fcfa(self):
        """Montant restant en FCFA"""
        try:
            return convert_hbar_to_fcfa(self.montant_restant)
        except Exception as e:
            logger.error(f"Erreur conversion montant_restant: {e}")
            return Decimal('0')
    
    @property
    def montant_distribue_fcfa(self):
        """Montant distribué en FCFA"""
        try:
            return convert_hbar_to_fcfa(self.montant_distribue or 0)
        except Exception as e:
            logger.error(f"Erreur conversion montant_distribue: {e}")
            return Decimal('0')
    
    @property
    def pourcentage_distribue(self):
        """Pourcentage déjà distribué au porteur"""
        if not self.montant_engage or self.montant_engage == 0:
            return 0
        try:
            return round((float(self.montant_distribue or 0) / float(self.montant_engage)) * 100, 1)
        except Exception as e:
            logger.error(f"Erreur calcul pourcentage_distribue: {e}")
            return 
    
    @property
    def taux_commission(self):
        """Taux de commission formaté"""
        return f"{self.commission}%"
    
    @property
    def montant_commission_total(self):
        """Commission totale prélevée"""
        try:
            if not self.montant_distribue:
                return Decimal('0')
            commission = (self.montant_distribue * self.commission / 100)
            return commission.quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        except Exception as e:
            logger.error(f"Erreur calcul commission: {e}")
            return Decimal('0')


class Association(models.Model):
    DOMAINES_ACTION = (
        ('education', 'Éducation'),
        ('sante', 'Santé'),
        ('environnement', 'Environnement'),
        ('droits_humains', 'Droits humains'),
        ('developpement', 'Développement communautaire'),
        ('culture', 'Culture'),
        ('urgence', 'Aide humanitaire'),
        ('autre', 'Autre'),
    )
    
    STATUT_JURIDIQUE_CHOICES = (
        ('association', 'Association'),
        ('ong', 'ONG'),
        ('fondation', 'Fondation'),
        ('autre', 'Autre statut'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='association_profile')
    
    # Informations de base
    nom = models.CharField(max_length=200)
    slogan = models.CharField(max_length=250, blank=True, null=True)
    description_courte = models.TextField(max_length=200, blank=True, null=True)
    description_longue = models.TextField(blank=True, null=True)
    logo = models.ImageField(upload_to='associations/logos/', blank=True, null=True)
    cover_image = models.ImageField(upload_to='associations/covers/', blank=True, null=True)
    
    # Domaines d'action et statut
    domaine_principal = models.CharField(max_length=50, choices=DOMAINES_ACTION, default='developpement')
    domaines_secondaires = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        help_text="Domaines secondaires (séparés par des virgules)"
    )
    causes_defendues = models.TextField(blank=True, null=True)
    statut_juridique = models.CharField(max_length=50, choices=STATUT_JURIDIQUE_CHOICES, default='association')
    # --- Agréments & enregistrement ---
    numero_agrement = models.CharField(max_length=100, blank=True, null=True)
    date_creation_association = models.DateField(blank=True, null=True)  
    date_agrement = models.DateField(blank=True, null=True)

    # Contact et localisation
    adresse_siege = models.TextField(blank=True, null=True)
    ville = models.CharField(max_length=100, blank=True, null=True)
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    pays = models.CharField(max_length=100, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email_contact = models.EmailField(blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    
    # --- Réseaux sociaux ---
    facebook = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    
    # Informations optionnelles (à compléter plus tard)
    nombre_adherents = models.IntegerField(blank=True, null=True, help_text="Nombre approximatif d’adhérents")
    nombre_beneficiaires = models.IntegerField(blank=True, null=True, help_text="Nombre approximatif de personnes aidées")
    projets_phares = models.TextField(blank=True, null=True, help_text="Quelques-uns de vos projets importants")
    actions_en_cours = models.TextField(blank=True, null=True)
    partenariats = models.TextField(blank=True, null=True)
    # Transparence (optionnel)
    transparent_finances = models.BooleanField(default=False, help_text="Nous partageons nos informations financières")
    transparent_actions = models.BooleanField(default=False, help_text="Nous rendons compte de nos actions")
    
    # Métadonnées
    date_creation = models.DateField(auto_now_add=True)
    date_maj = models.DateTimeField(auto_now=True)
    valide = models.BooleanField(default=False, help_text="Profil validé par l'administration")
    featured = models.BooleanField(default=False, help_text="Mise en avant sur la plateforme")
    slug = models.SlugField(max_length=255, unique=True, blank=True, null=True)

    class Meta:
        verbose_name = "Association"
        verbose_name_plural = "Associations"
    
    def __str__(self):
        return self.nom
    
    def get_absolute_url(self):
        return reverse('association_detail', kwargs={'pk': self.pk})
    
    @property
    def est_verifiee(self):
        return self.verifiee
    
    def get_domaine_display(self):
        return self.get_domaine_principal_display()
    

    def get_projets_actifs(self):
        """Retourne les projets actifs liés à cette association"""
        return self.projets.filter(statut="actif")

    def get_total_collecte(self):
        """Somme de tous les montants collectés des projets de cette association"""
        return self.projets.aggregate(total=Sum("montant_collecte"))["total"] or 0

    def get_nombre_contributeurs(self):
        """Nombre de contributeurs uniques (via transactions confirmées)"""
        from django.db.models import Count
        try:
            # Correction de la requête
            return Transaction.objects.filter(
                projet__association=self,
                statut="confirme"
            ).values('user').distinct().count()
        except:
            return 0
    
    def get_logo_url(self):
        """Retourne l'URL du logo ou une image par défaut si aucun logo n'est défini"""
        if self.logo and hasattr(self.logo, 'url'):
            return self.logo.url
        return '/static/images/default-association-logo.png'
    
    def get_cover_url(self):
        """Retourne l'URL de l'image de couverture ou une image par défaut"""
        if self.cover_image and hasattr(self.cover_image, 'url'):
            return self.cover_image.url
        return '/static/images/default-association-cover.jpg'
    
    def get_completion_percentage(self):
        """Calcule le pourcentage de complétion du profil"""
        fields_to_check = [
            'nom', 'description_courte', 'domaine_principal', 
            'statut_juridique', 'adresse_siege', 'ville', 
            'code_postal', 'pays', 'telephone', 'email_contact'
        ]
        
        completed = 0
        for field in fields_to_check:
            value = getattr(self, field)
            if value and str(value).strip():
                completed += 1
        
        # Bonus pour le logo
        if self.logo:
            completed += 2
        
        total_score = len(fields_to_check) + 2  # Total possible avec bonus logo
        percentage = (completed / total_score) * 100
        return min(round(percentage), 100)
    def save(self, *args, **kwargs):
        # Générer automatiquement le slug à partir du nom si pas défini
        if not self.slug and self.nom:
            self.slug = slugify(self.nom)
        super().save(*args, **kwargs)


class AssociationImage(models.Model):
    """Modèle pour les images de galerie des associations"""
    association = models.ForeignKey(
        Association, 
        on_delete=models.CASCADE, 
        related_name='images'
    )
    image = models.ImageField(upload_to='associations/galerie/')
    legende = models.CharField(max_length=200, blank=True, null=True)
    date_ajout = models.DateTimeField(auto_now_add=True)
    ordre = models.PositiveIntegerField(default=0)
    
    class Meta:
        ordering = ['ordre', 'date_ajout']
    
    def __str__(self):
        return f"Image pour {self.association.nom}"


class AuditLog(models.Model):
    ACTION_TYPES = (
        ('create', 'Création'),
        ('update', 'Modification'),
        ('delete', 'Suppression'),
        ('validate', 'Validation'),
        ('reject', 'Rejet'),
        ('verify', 'Vérification'),
        ('refund', 'Remboursement'),
    )
    
    STATUT_CHOICES = (
        ('SUCCESS', 'Succès'),
        ('FAILURE', 'Échec'),
       
    )
    
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    utilisateur = models.ForeignKey(User, 
                                    on_delete=models.CASCADE,
                                   
                                    )
    action = models.CharField(max_length=10, choices=ACTION_TYPES)
    modele = models.CharField(max_length=50)  # Nom du modèle affecté
    objet_id = models.CharField(max_length=100)  # ID de l'objet affecté
    details = models.JSONField()  # Détails de l'action en JSON
    date_action = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='SUCCESS')  # Champ ajouté
    
    class Meta:
        indexes = [
            models.Index(fields=['date_action']),
            models.Index(fields=['utilisateur']),
            models.Index(fields=['modele', 'objet_id']),
        ]
        ordering = ['-date_action']
    def __str__(self):
        return f"{self.utilisateur.username} - {self.action} - {self.modele} - {self.date_action}"
    



class EmailLog(models.Model):
    STATUTS = [
        ('sent', 'Envoyé'),
        ('failed', 'Échec'),
        ('simulated', 'Simulé'),
        ('pending', 'En attente'),
    ]
    
    TYPES = [
        ('project_approved', 'Projet approuvé'),
        ('project_rejected', 'Projet rejeté'),
        ('don_received', 'Don reçu'),
        ('user_welcome', 'Bienvenue utilisateur'),
        ('password_reset', 'Réinitialisation mot de passe'),
        ('notification', 'Notification'),
        ('other', 'Autre'),
    ]
    
    destinataire = models.EmailField(verbose_name="Destinataire")
    sujet = models.CharField(max_length=200, verbose_name="Sujet")
    corps = models.TextField(verbose_name="Corps du message")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")
    date_envoi = models.DateTimeField(null=True, blank=True, verbose_name="Date d'envoi")
    statut = models.CharField(max_length=10, choices=STATUTS, default='pending', verbose_name="Statut")
    type_email = models.CharField(max_length=20, choices=TYPES, default='other', verbose_name="Type d'email")
    erreur = models.TextField(blank=True, verbose_name="Message d'erreur")
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Utilisateur concerné"
    )
    
    class Meta:
        ordering = ['-date_creation']
        verbose_name = "Log d'email"
        verbose_name_plural = "Logs d'emails"
    
    def __str__(self):
        return f"{self.destinataire} - {self.sujet} ({self.statut})"
    
    def marquer_comme_envoye(self):
        self.statut = 'sent'
        self.date_envoi = timezone.now()
        self.save()
    
    def marquer_comme_erreur(self, message_erreur):
        self.statut = 'failed'
        self.erreur = message_erreur
        self.save()

class Palier(models.Model):
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='paliers')
    pourcentage = models.DecimalField(max_digits=5, decimal_places=2)
    montant = models.DecimalField(max_digits=15, decimal_places=0)
    montant_minimum = models.DecimalField(max_digits=15, decimal_places=0, editable=False)
    transfere = models.BooleanField(default=False)
    date_transfert = models.DateTimeField(null=True, blank=True)
    transaction_hash = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['montant_minimum']

        # Dans models.py - Modifiez la méthode save() de Palier
    def save(self, *args, **kwargs):
        if not self.montant and self.projet.montant_demande:
            self.montant = (self.projet.montant_demande * self.pourcentage) / 100

        # Calcul du montant minimum pour déclencher ce palier
        montant_anterieur = Decimal('0')

        # Récupérer tous les paliers existants avec pourcentage inférieur
        paliers_existants = Palier.objects.filter(
            projet=self.projet, 
            pourcentage__lt=self.pourcentage
        )

        for palier in paliers_existants:
            montant_anterieur += palier.montant

        self.montant_minimum = montant_anterieur + Decimal('0.01')

        super().save(*args, **kwargs)

class PreuvePalier(models.Model):
    STATUT_CHOICES = [
        ('non_soumis', 'Non soumis'),
        ('en_attente', 'En attente de vérification'),
        ('approuve', 'Approuvé'),
        ('rejete', 'Rejeté'),
        ('modification', 'Modification requise'),
    ]
    
    palier = models.ForeignKey('Palier', on_delete=models.CASCADE, related_name='preuves')
    date_soumission = models.DateTimeField(auto_now_add=True)
    date_verification = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='non_soumis')
    commentaires = models.TextField(blank=True)
    verificateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='preuves_verifiees'
    )
    
    class Meta:
        verbose_name = "Preuve de palier"
        verbose_name_plural = "Preuves de paliers"
        ordering = ['-date_soumission']
    
    def __str__(self):
        return f"Preuve {self.palier.projet.titre} - Palier {self.palier.pourcentage}%"
    
    def save(self, *args, **kwargs):
        if self.statut in ['approuve', 'rejete', 'modification'] and not self.date_verification:
            self.date_verification = timezone.now()
        super().save(*args, **kwargs)
        
class FichierPreuve(models.Model):
    TYPE_CHOICES = [
        ('photo', 'Photo'),
        ('video', 'Vidéo'),
        ('document', 'Document'),
        ('autre', 'Autre'),
    ]
    
    preuve = models.ForeignKey(PreuvePalier, on_delete=models.CASCADE, related_name='fichiers')
    fichier = models.FileField(upload_to='preuves/%Y/%m/%d/')
    type_fichier = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_upload = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = "Fichier preuve"
        verbose_name_plural = "Fichiers preuves"



class Transaction(models.Model):
    STATUTS = (
        ('en_attente', 'En attente'),
        ('confirme', 'Confirmé'),
        ('erreur', 'Erreur'),
        ('rembourse', 'Remboursé'),
    )
    destination = models.CharField(max_length=20, choices=[
        ('operator', 'Vers opérateur'),
        ('project', 'Vers projet direct'),
        ('beneficiary', 'Vers bénéficiaire')
    ], default='operator')

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions')
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    montant = models.DecimalField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    
    date_transaction = models.DateTimeField(auto_now_add=True)
    hedera_transaction_hash = models.CharField(max_length=150, unique=True)
    hedera_hashscan_url = models.URLField(
        blank=True, 
        null=True,
        help_text="URL HashScan pour visualiser la transaction"
    )
    hedera_status = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        help_text="Statut Hedera de la transaction (SUCCESS, FAILED, etc.)"
    )
    
    hedera_message_hashscan_url = models.URLField(
        blank=True, 
        null=True,
        help_text="URL HashScan pour le message HCS"
    )
    
    topic = models.ForeignKey(
        'Projet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions_by_topic',
        to_field='topic_id',  # Lien sur le champ topic_id
        help_text="Topic HCS du projet associé à cette transaction"
    )
    
    contributeur = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        limit_choices_to={'user_type__in': ['porteur', 'donateur', 'investisseur', 'association']}
    ) 
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)
    
    statut = models.CharField(max_length=10, choices=STATUTS, default='en_attente')
    contributeur_anonymise = models.CharField(max_length=100, editable=False)
    
    # Suivi administratif
    verifie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='transactions_verifiees', limit_choices_to={'user_type': 'admin'})
    date_verification = models.DateTimeField(null=True, blank=True)
    notes_verification = models.TextField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['hedera_transaction_hash']),
            models.Index(fields=['date_transaction']),
            models.Index(fields=['contributeur']),
            models.Index(fields=['projet']),
            models.Index(fields=['topic']),
        ]
        permissions = [
            ("verify_transaction", "Peut vérifier une transaction"),
            ("refund_transaction", "Peut rembourser une transaction"),
        ]
    
    def save(self, *args, **kwargs):
        # ✅ Auto-remplissage du topic à partir du projet
        if self.projet and self.projet.topic_id and not self.topic:
            self.topic = self.projet
        
        if self.contributeur and not self.contributeur_anonymise:
            salt = getattr(settings, 'ANONYMIZATION_SALT', '')
            self.contributeur_anonymise = self.anonymiser_contributeur(salt)
            
        super().save(*args, **kwargs)
    
    @property
    def is_hedera_confirmed(self):
        return self.hedera_status == 'SUCCESS'
    
    @property
    def has_hedera_message(self):
        return bool(self.hedera_message_id)
    
    @property
    def topic_hashscan_link(self):
        """Retourne le lien HashScan du topic"""
        if self.topic and self.topic.topic_id:
            return f"https://hashscan.io/testnet/topic/{self.topic.topic_id}"
        return None
    
    def anonymiser_contributeur(self, salt):
        """Anonymisation du contributeur"""
        unique_id = f"{self.contributeur.audit_uuid}{salt}"
        return f"Contributeur_{hashlib.sha256(unique_id.encode()).hexdigest()[:20]}"
    
    def clean(self):
        """Validation: Empêcher les admins de contribuer"""
        if self.contributeur and self.contributeur.user_type == 'admin':
            raise ValidationError("Les administrateurs ne peuvent pas effectuer de contributions.")




class TransactionAdmin(models.Model):
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)
    palier = models.ForeignKey('Palier', on_delete=models.SET_NULL, null=True, blank=True)  # lien vers le palier si applicable
    montant_brut = models.DecimalField(max_digits=15, decimal_places=2)
    montant_net = models.DecimalField(max_digits=15, decimal_places=2)
    commission = models.DecimalField(max_digits=15, decimal_places=2)
    commission_pourcentage = models.DecimalField(max_digits=5, decimal_places=2)
    transaction_hash = models.CharField(max_length=100)
    beneficiaire = models.ForeignKey(User, on_delete=models.CASCADE, related_name='transactions_reçues')
    initiateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions_initiées')  # admin qui déclenche
    date_creation = models.DateTimeField(auto_now_add=True)
    hedera_message_id = models.CharField(max_length=150, blank=True, null=True)
    hedera_message_hashscan_url = models.URLField(blank=True, null=True)

    type_transaction = models.CharField(max_length=20, choices=[
        ('distribution', 'Distribution'),
        ('commission', 'Commission')
    ])

    def __str__(self):
        return f"{self.type_transaction} {self.montant_net} → {self.beneficiaire}"



class ContactSubmission(models.Model): 

    sujet = models.CharField(max_length=100)
    email = models.EmailField()
    message = models.TextField()
    date_soumission = models.DateTimeField(default=timezone.now)
    traite = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Soumission de contact"
        verbose_name_plural = "Soumissions de contact"
        ordering = ['-date_soumission']
    
    def __str__(self):
        return f"{self.sujet} - {self.email}"
    
class TopicMessage(models.Model):
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name="messages")
    type_message = models.CharField(max_length=100)  # ex: don, distribution_admin_porteur
    utilisateur_email = models.EmailField(blank=True, null=True)
    montant = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    transaction_hash = models.CharField(max_length=200, blank=True, null=True)
    contenu = models.JSONField(default=dict)  # message complet HCS
    date_envoi = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-date_envoi"]

    def __str__(self):
        return f"{self.projet.titre} | {self.type_message} | {self.montant or ''}"
