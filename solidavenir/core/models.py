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

def validate_profile_image_size(value):
    """Valide que l'image de profil ne dépasse pas 5 Mo"""
    limit = 5 * 1024 * 1024  # 5 Mo
    if value.size > limit:
        raise ValidationError("La taille maximale de l'image de profil est de 5 Mo.")

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
    
    user_type = models.CharField(max_length=15, choices=USER_TYPES, default='donateur')
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
    hedera_private_key = models.BinaryField(blank=True, null=True)
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    hedera_public_key = models.TextField(blank=True, null=True)
    hedera_account_created = models.BooleanField(default=False)
    # Champs pour porteurs de projet - Tous optionnels
    organisation = models.CharField(max_length=100, blank=True, null=True, 
                                  help_text="Nom de votre entreprise, startup, ou structure")
    site_web = models.URLField(blank=True, null=True, help_text="Site web de votre projet")
    description_projet = models.TextField(blank=True, null=True, help_text="Décrivez brièvement votre projet")
    montant_recherche = models.DecimalField(max_digits=15, decimal_places=2, blank=True, null=True,
                                          help_text="Montant approximatif recherché")
    
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
    
    def get_hedera_private_key(self):
        """Récupère la clé privée (déchiffrée en production)"""
        # En production, implémentez un système de chiffrement
        return self.hedera_private_key
    
    def has_hedera_wallet(self):
        return bool(self.hedera_account_id and self.hedera_private_key)
    

# apps/projets/models.py

# --- VALIDATEURS PERSONNALISÉS ---
from django.core.exceptions import ValidationError

def validate_file_size(value):
    """Vérifie que le fichier ne dépasse pas 10 Mo"""
    limit = 10 * 1024 * 1024  # 10 Mo
    if value.size > limit:
        raise ValidationError("La taille maximale autorisée est de 10 Mo.")

# --- MODELE PRINCIPAL PROJET ---
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, FileExtensionValidator
from django.utils import timezone
from django.utils.text import slugify
from django.db.models import Sum, Q
import uuid
from datetime import timedelta

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
    titre = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField()
    description_courte = models.CharField(max_length=300, help_text="Description résumée pour les listes")

    # Informations financières
    montant_demande = models.DecimalField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    montant_minimal = models.DecimalField(
        max_digits=15,
        decimal_places=0,
        default=0,
        help_text="Montant minimum à atteindre pour que le projet soit financé"
    )
    montant_collecte = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    type_financement = models.CharField(max_length=10, choices=TYPES_FINANCEMENT, default='don')

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
    hedera_topic_id = models.CharField(max_length=150, blank=True, null=True)
    transactions_hash = models.TextField(blank=True, null=True)

    # Récompenses (intégrées directement dans le modèle)
    has_recompenses = models.BooleanField(default=False)
    niveaux_financement_json = models.JSONField(
        blank=True, 
        null=True,
        help_text="Structure JSON pour stocker les niveaux de financement et récompenses"
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
        if self.montant_demande == 0:
            return 0
        montant_actuel = self.montant_actuel()
        return round((montant_actuel / self.montant_demande) * 100, 1)

    @property
    def objectif_atteint(self):
        return self.montant_collecte >= self.montant_demande

    @property
    def objectif_minimal_atteint(self):
        return self.montant_collecte >= self.montant_minimal

    def montant_actuel(self):
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

    def incrementer_vues(self):
        self.vues += 1
        self.save(update_fields=['vues'])

    def incrementer_partages(self):
        self.partages += 1
        self.save(update_fields=['partages'])

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

    # --- METHODES POUR LES RECOMPENSES ---
    def ajouter_niveau_financement(self, montant, titre, description, livraison_estimee=None, quantite_limitee=None):
        """Ajoute un niveau de financement au projet"""
        if not self.niveaux_financement_json:
            self.niveaux_financement_json = []
        
        niveau = {
            'id': len(self.niveaux_financement_json) + 1,
            'montant': float(montant),
            'titre': titre,
            'description': description,
            'livraison_estimee': livraison_estimee.isoformat() if livraison_estimee else None,
            'quantite_limitee': quantite_limitee,
            'quantite_vendue': 0,
            'actif': True
        }
        
        self.niveaux_financement_json.append(niveau)
        self.save()
        return niveau

    def get_niveaux_financement(self):
        """Retourne la liste des niveaux de financement"""
        return self.niveaux_financement_json or []

    def get_niveau_par_montant(self, montant):
        """Trouve un niveau de financement correspondant au montant"""
        if not self.niveaux_financement_json:
            return None
            
        for niveau in self.niveaux_financement_json:
            if niveau['montant'] == float(montant) and niveau.get('actif', True):
                return niveau
        return None



from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
import uuid

class Association(models.Model):
    DOMAINES_ACTION = (
        ('environnement', 'Environnement & Écologie'),
        ('education', 'Éducation & Formation'),
        ('sante', 'Santé & Bien-être'),
        ('social', 'Action Sociale & Solidarité'),
        ('culture', 'Culture & Arts'),
        ('droits_humains', 'Droits Humains'),
        ('developpement', 'Développement International'),
        ('animaux', 'Protection Animale'),
        ('jeunesse', 'Jeunesse & Sports'),
        ('autre', 'Autre domaine'),
    )
    
    STATUTS_JURIDIQUES = (
        ('agreement', 'Accord de Siège (Organisations Internationales)'),
        ('ong', 'ONG Internationale'),
        ('association', 'Association Malienne'),
        ('fondation', 'Fondation'),
        ('giec', 'GIEC (Groupement d\'Intérêt Économique et Culturel)'),
        ('cooperative', 'Coopérative'),
        ('autre', 'Autre statut'),
    )
    
    # Référence à l'utilisateur
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE,
        related_name='association_profile',
        limit_choices_to={'user_type': 'association'}
    )
    
    # Identité
    nom = models.CharField(max_length=200, unique=True)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    slogan = models.CharField(max_length=300, blank=True, null=True)
    description_courte = models.TextField(max_length=500, help_text="Description concise pour les listes")
    description_longue = models.TextField(help_text="Description détaillée de l'association")
    
    # Informations juridiques - SPÉCIFIQUES AU MALI
    statut_juridique = models.CharField(max_length=20, choices=STATUTS_JURIDIQUES, default='association')
    numero_agrement = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Numéro d'agrément",
        help_text="Numéro d'agrément délivré par le gouvernement malien"
    )
    date_agrement = models.DateField(
        blank=True, 
        null=True,
        verbose_name="Date d'agrément",
        help_text="Date d'obtention de l'agrément"
    )
    date_creation = models.DateField(verbose_name="Date de création")
    numero_rc = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Numéro au Registre du Commerce",
        help_text="Numéro d'immatriculation au RCCM"
    )
    numero_ifu = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name="Numéro IFU/Numéro contribuable",
        help_text="Identifiant Fiscal Unique"
    )
    
    # Logo et visuels
    logo = models.ImageField(
        upload_to='associations/logos/',
        blank=True,
        null=True,
        help_text="Logo de l'association (format carré recommandé)"
    )
    cover_image = models.ImageField(
        upload_to='associations/covers/',
        blank=True,
        null=True,
        help_text="Image de couverture (format 1200x400px recommandé)"
    )
    images_galerie = models.ManyToManyField(
        'AssociationImage',
        blank=True,
        related_name='associations'
    )
    
    # Domaines d'action
    domaine_principal = models.CharField(max_length=50, choices=DOMAINES_ACTION)
    domaines_secondaires = models.CharField(
        max_length=200, 
        blank=True, 
        null=True,
        help_text="Domaines secondaires (séparés par des virgules)"
    )
    causes_defendues = models.TextField(help_text="Causes principales défendues par l'association")
    
    # Contact et localisation
    adresse_siege = models.TextField(verbose_name="Adresse du siège social")
    ville = models.CharField(max_length=100, default="Bamako")
    commune = models.CharField(max_length=100, blank=True, null=True, help_text="Commune d'implantation")
    code_postal = models.CharField(max_length=10, blank=True, null=True)
    pays = models.CharField(max_length=100, default='Mali')
    telephone = models.CharField(max_length=20)
    email_contact = models.EmailField()
    site_web = models.URLField(blank=True, null=True)
    
    # Réseaux sociaux
    facebook = models.URLField(blank=True, null=True)
    twitter = models.URLField(blank=True, null=True)
    linkedin = models.URLField(blank=True, null=True)
    instagram = models.URLField(blank=True, null=True)
    youtube = models.URLField(blank=True, null=True)
    
    # Chiffres clés
    nombre_adherents = models.PositiveIntegerField(default=0, verbose_name="Nombre d'adhérents")
    nombre_beneficiaires = models.PositiveIntegerField(default=0, verbose_name="Nombre de bénéficiaires")
    budget_annuel = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        blank=True, 
        null=True,
        verbose_name="Budget annuel (FCFA)"
    )
    pourcentage_frais_gestion = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        verbose_name="Frais de gestion (%)",
        help_text="""Pourcentage des ressources consacré aux frais de fonctionnement (hors missions).
        <br>• < 15% : Excellent
        <br>• 15-25% : Bon
        <br>• 25-35% : Acceptable
        <br>• > 35% : Élevé"""
    )
    
    # Documents justificatifs pour le Mali
    agrement_file = models.FileField(
        upload_to='associations/agrements/',
        blank=True,
        null=True,
        verbose_name="Copie de l'agrément",
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    statuts_file = models.FileField(
        upload_to='associations/statuts/',
        blank=True,
        null=True,
        verbose_name="Copie des statuts",
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    rapport_annuel = models.FileField(
        upload_to='associations/rapports/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    comptes_annuels = models.FileField(
        upload_to='associations/comptes/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )
    
    # Projets et actions
    projets_phares = models.TextField(blank=True, null=True, help_text="Projets principaux réalisés")
    actions_en_cours = models.TextField(blank=True, null=True)
    partenariats = models.TextField(blank=True, null=True)
    
    # Transparence
    transparent_finances = models.BooleanField(default=False, verbose_name="Transparence financière")
    transparent_actions = models.BooleanField(default=False, verbose_name="Transparence des actions")
    
    # Métadonnées
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    date_creation_profile = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    valide = models.BooleanField(default=False, help_text="Profil validé par l'administration")
    featured = models.BooleanField(default=False, help_text="Mise en avant sur la plateforme")
    
    class Meta:
        ordering = ['-featured', 'nom']
        verbose_name = "Association"
        verbose_name_plural = "Associations"
    
    def __str__(self):
        return self.nom
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.nom)
            original_slug = self.slug
            counter = 1
            while Association.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('detail_association', kwargs={'slug': self.slug})
    
    def get_logo_url(self):
        if self.logo:
            return self.logo.url
        return '/static/images/default-association-logo.png'
    
    def get_cover_url(self):
        if self.cover_image:
            return self.cover_image.url
        return '/static/images/default-association-cover.jpg'
    
    def get_domaines_list(self):
        """Retourne la liste des domaines d'action"""
        domaines = [self.get_domaine_principal_display()]
        if self.domaines_secondaires:
            domaines.extend([d.strip() for d in self.domaines_secondaires.split(',')])
        return domaines
    
    def get_projets_actifs(self):
        """Retourne les projets actifs de l'association"""
        return self.user.projet_set.filter(statut='actif')
    
    def get_total_collecte(self):
        """Montant total collecté pour tous les projets"""
        return self.user.projet_set.aggregate(
            total=Sum('montant_collecte')
        )['total'] or 0
    
    def get_nombre_donateurs(self):
        """Nombre de donateurs uniques pour tous les projets"""
        from django.db.models import Count
        return self.user.projet_set.annotate(
            donateurs_count=Count('transaction__donateur', distinct=True)
        ).aggregate(total=Sum('donateurs_count'))['total'] or 0
    
    def get_completion_percentage(self):
        """Calcule le pourcentage de complétion du profil"""
        fields_to_check = [
            'nom', 'description_courte', 'description_longue',
            'logo', 'domaine_principal', 'causes_defendues',
            'statut_juridique', 'adresse_siege', 'ville',
            'telephone', 'email_contact'
        ]
        
        completed = 0
        for field in fields_to_check:
            value = getattr(self, field)
            if value and str(value).strip():
                completed += 1
        
        total_score = len(fields_to_check)
        percentage = (completed / total_score) * 100
        return min(round(percentage), 100)
    
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








from decimal import Decimal
import math
class Transaction(models.Model):
    STATUTS = (
        ('en_attente', 'En attente'),
        ('confirme', 'Confirmé'),
        ('erreur', 'Erreur'),
        ('rembourse', 'Remboursé'),
    )
    
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    montant = models.DecimalField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    montant_hbar = models.DecimalField(max_digits=15, decimal_places=8, null=True, blank=True)
    taux_conversion = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    
    date_transaction = models.DateTimeField(auto_now_add=True)
    hedera_transaction_hash = models.CharField(max_length=150, unique=True)
    contributeur = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        limit_choices_to={'user_type__in': ['porteur', 'donateur', 'investisseur', 'association']}
    ) 
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)
    
    statut = models.CharField(max_length=10, choices=STATUTS, default='en_attente')
    contributeur_anonymise = models.CharField(max_length=100, editable=False)  # CORRIGÉ: donateur → contributeur
    
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
        ]
        permissions = [
            ("verify_transaction", "Peut vérifier une transaction"),
            ("refund_transaction", "Peut rembourser une transaction"),
        ]
    
    def save(self, *args, **kwargs):
        # CORRIGÉ: Utiliser contributeur au lieu de donateur
        if self.contributeur and not self.contributeur_anonymise:
            salt = getattr(settings, 'ANONYMIZATION_SALT', '')
            self.contributeur_anonymise = self.anonymiser_contributeur(salt)
        
        # Conversion automatique FCFA vers HBAR si nécessaire
        if self.montant and not self.montant_hbar:
            self.convertir_fcfa_vers_hbar()
            
        super().save(*args, **kwargs)
    
    def convertir_fcfa_vers_hbar(self):
        """Convertit le montant FCFA en HBAR"""
        try:
            taux = self.get_taux_conversion()
            self.taux_conversion = taux
            montant_hbar = Decimal(self.montant) / Decimal(taux)
            self.montant_hbar = montant_hbar.quantize(Decimal('0.00000001'))
        except Exception as e:
            self.taux_conversion = Decimal('0.8')
            montant_hbar = Decimal(self.montant) / self.taux_conversion
            self.montant_hbar = montant_hbar.quantize(Decimal('0.00000001'))
    
    def get_taux_conversion(self):
        """Récupère le taux de conversion FCFA/HBAR"""
        try:
            response = requests.get('https://api.taux-conversion.com/fcfa/hbar')
            data = response.json()
            return Decimal(data['taux'])
        except:
            return Decimal('0.8')
    
    def anonymiser_contributeur(self, salt):
        """Anonymisation du contributeur"""
        unique_id = f"{self.contributeur.audit_uuid}{salt}"
        return f"Contributeur_{hashlib.sha256(unique_id.encode()).hexdigest()[:20]}"
    
    def clean(self):
        """Validation: Empêcher les admins de contribuer"""
        if self.contributeur and self.contributeur.user_type == 'admin':
            raise ValidationError("Les administrateurs ne peuvent pas effectuer de contributions.")















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
    
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=10, choices=ACTION_TYPES)
    modele = models.CharField(max_length=50)  # Nom du modèle affecté
    objet_id = models.CharField(max_length=100)  # ID de l'objet affecté
    details = models.JSONField()  #Détails de l'action en JSON
    date_action = models.DateTimeField(auto_now_add=True)
    adresse_ip = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['date_action']),
            models.Index(fields=['utilisateur']),
            models.Index(fields=['modele', 'objet_id']),
        ]
        ordering = ['-date_action']
