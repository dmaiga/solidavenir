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

class User(AbstractUser):
    USER_TYPES = (
        ('admin', 'Administrateur'),
        ('porteur', 'Porteur de Projet'),
        ('donateur', 'Donateur'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='donateur')
    hedera_account_id = models.CharField(max_length=50, blank=True, null=True)
    hedera_private_key =  models.BinaryField(blank=True, null=True)
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Informations supplémentaires pour tous les utilisateurs
    telephone = models.CharField(max_length=20, blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    date_naissance = models.DateField(blank=True, null=True)
    
    # Champs spécifiques aux porteurs de projet
    organisation = models.CharField(max_length=100, blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    
    # Champs spécifiques aux administrateurs
    departement = models.CharField(max_length=100, blank=True, null=True)
    role_admin = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        permissions = [
            ("can_audit", "Peut effectuer des audits de transparence"),
            ("manage_users", "Peut gérer tous les utilisateurs"),
            ("manage_projects", "Peut gérer tous les projets"),
            ("manage_transactions", "Peut gérer toutes les transactions"),
            ("view_dashboard", "Peut voir le tableau de bord administrateur"),
        ]
    
    def is_administrator(self):
        return self.user_type == 'admin' or self.is_superuser
    
    def can_manage_users(self):
        return self.is_administrator() or self.has_perm('core.manage_users')
    
    def can_manage_projects(self):
        return self.is_administrator() or self.has_perm('core.manage_projects')
    
    def can_manage_transactions(self):
        return self.is_administrator() or self.has_perm('core.manage_transactions')
    
    def can_view_dashboard(self):
        return self.is_administrator() or self.has_perm('core.view_dashboard')
    
    def set_hedera_private_key(self, private_key):
        """Chiffre et stocke la clé privée"""
        try:
            if hasattr(settings, 'ENCRYPTION_KEY'):
                fernet = Fernet(settings.ENCRYPTION_KEY)
                self.hedera_private_key = fernet.encrypt(private_key.encode())
                logger.info(f"Clé privée chiffrée pour l'utilisateur {self.username}")
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement de la clé: {str(e)}")
            raise

    def get_hedera_private_key(self):
        """Déchiffre la clé privée"""
        if self.hedera_private_key and hasattr(settings, 'ENCRYPTION_KEY'):
            fernet = Fernet(settings.ENCRYPTION_KEY)
            return fernet.decrypt(self.hedera_private_key).decode()
        return None
    

class Projet(models.Model):
    STATUTS = (
        ('brouillon', 'Brouillon'),
        ('en_attente', 'En attente de validation'),
        ('actif', 'Actif'),
        ('termine', 'Terminé'),
        ('annule', 'Annulé'),
        ('rejete', 'Rejeté'),
    )
    
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    titre = models.CharField(max_length=200)
    description = models.TextField()
    montant_demande = models.DecimalField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    montant_collecte = models.DecimalField(max_digits=15, decimal_places=0, default=0)
    cover_image = models.ImageField(
        upload_to='covers/projets/',
        blank=True,
        null=True,
        help_text="Image de couverture du projet (recommandé: 1200x600px)"
    )
    
    date_fin = models.DateField(
        null=True,
        blank=True,
        help_text="Date de fin de la campagne de financement"
    )
    porteur = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'porteur'})
    
    # Validation par les administrateurs
    valide_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='projets_valides', limit_choices_to={'user_type': 'admin'})
    date_validation = models.DateTimeField(null=True, blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)
    statut = models.CharField(max_length=10, choices=STATUTS, default='brouillon')
    
    # Documents justificatifs (chemins vers les fichiers)
    document_justificatif = models.FileField(
    upload_to='documents/projets/', 
    blank=True, 
    null=True,
    validators=[FileExtensionValidator(allowed_extensions=['pdf', 'doc', 'docx', 'jpg', 'png'])]
)
    plan_financement = models.FileField(upload_to='documents/projets/', blank=True, null=True)
    
    hedera_topic_id = models.CharField(max_length=150, blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['audit_uuid']),
            models.Index(fields=['statut']),
            models.Index(fields=['porteur']),
            models.Index(fields=['date_fin']),
        ]
        permissions = [
            ("validate_project", "Peut valider un projet"),
        ]
    
    
    
    def peut_etre_modifie_par(self, user):
        if user.is_administrator():
            return True
        return self.porteur == user and self.statut in ['brouillon', 'en_attente']
    
    @property
    def montant_restant(self):
        return max(0, self.montant_demande - (self.montant_collecte or 0))
    
    @property
    def pourcentage_financement(self):
        if self.montant_demande == 0:
            return 0
        montant_actuel = self.montant_actuel()
        return round((montant_actuel / self.montant_demande) * 100, 1)
    
    def montant_actuel(self):
        return self.transaction_set.filter(statut='confirme').aggregate(
            total=Sum('montant')
        )['total'] or 0
    
    @property
    def jours_restants(self):
        if self.date_fin:
            jours = (self.date_fin - timezone.now().date()).days
            return max(0, jours)
        return 0
    

class Transaction(models.Model):
    STATUTS = (
        ('en_attente', 'En attente'),
        ('confirme', 'Confirmé'),
        ('erreur', 'Erreur'),
        ('rembourse', 'Remboursé'),
    )
    
    audit_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    montant = models.DecimalField(max_digits=15, decimal_places=0, validators=[MinValueValidator(0)])
    date_transaction = models.DateTimeField(auto_now_add=True)
    
    hedera_transaction_hash = models.CharField(max_length=150, unique=True)
    
    donateur = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'user_type': 'donateur'})
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE)
    
    statut = models.CharField(max_length=10, choices=STATUTS, default='en_attente')
    donateur_anonymise = models.CharField(max_length=100, editable=False)
    
    # Suivi administratif
    verifie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                   related_name='transactions_verifiees', limit_choices_to={'user_type': 'admin'})
    date_verification = models.DateTimeField(null=True, blank=True)
    notes_verification = models.TextField(blank=True, null=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['hedera_transaction_hash']),
            models.Index(fields=['date_transaction']),
            models.Index(fields=['donateur']),
            models.Index(fields=['projet']),
        ]
        permissions = [
            ("verify_transaction", "Peut vérifier une transaction"),
            ("refund_transaction", "Peut rembourser une transaction"),
        ]
    

    def save(self, *args, **kwargs):
        if self.donateur and not self.donateur_anonymise:
            salt = getattr(settings, 'ANONYMIZATION_SALT', '')
            self.donateur_anonymise = self.anonymiser_donateur(salt)
        super().save(*args, **kwargs)
    
    def anonymiser_donateur(self, salt):
        """Anonymisation plus sécurisée"""
        unique_id = f"{self.donateur.audit_uuid}{salt}"
        return f"Donateur_{hashlib.sha256(unique_id.encode()).hexdigest()[:20]}"

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