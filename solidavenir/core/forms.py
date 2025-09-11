from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import User, Projet, Transaction
from django_summernote.widgets import SummernoteWidget

class InscriptionForm(UserCreationForm):
    user_type = forms.ChoiceField(choices=User.USER_TYPES, label="Type d'utilisateur")
    
    # Champs supplémentaires selon le type d'utilisateur
    telephone = forms.CharField(max_length=20, required=False, label="Téléphone")
    adresse = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label="Adresse")
    
    # Champs conditionnels pour les porteurs de projet
    organisation = forms.CharField(max_length=100, required=False, label="Organisation")
    site_web = forms.URLField(required=False, label="Site web")
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type', 
                 'telephone', 'adresse', 'organisation', 'site_web']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Réorganiser l'ordre des champs si nécessaire
        self.fields['password2'].label = "Confirmation du mot de passe"
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user_type = self.cleaned_data.get('user_type')
        
        # Assigner les champs supplémentaires
        user.telephone = self.cleaned_data.get('telephone', '')
        user.adresse = self.cleaned_data.get('adresse', '')
        
        if user_type == 'porteur':
            user.organisation = self.cleaned_data.get('organisation', '')
            user.site_web = self.cleaned_data.get('site_web', '')
        
        if user_type != 'porteur':
            user.organisation = None
            user.site_web = None

        if commit:
            user.save()
        return user

class CreationProjetForm(forms.ModelForm):
    # Utiliser Summernote pour la description
    description = forms.CharField(widget=SummernoteWidget(attrs={'summernote': {'width': '100%', 'height': '300px'}}))
    
    # Montant en FCFA avec placeholder
    montant_demande = forms.DecimalField(
        max_digits=15, 
        decimal_places=0,
        label="Montant demandé (FCFA)",
        help_text="Indiquez le montant nécessaire en FCFA",
        widget=forms.NumberInput(attrs={'placeholder': '500000'})
    )
    
    # Image de couverture
    cover_image = forms.ImageField(
        required=False,
        label="Image de couverture",
        help_text="Image représentative de votre projet (format recommandé: 1200x600px)"
    )
    
    # Date de fin
    date_fin = forms.DateField(
        required=False,
        label="Date de fin de campagne",
        help_text="Date limite pour atteindre l'objectif de financement (optionnel)",
        widget=forms.DateInput(attrs={'type': 'date'}),
    )
    
    class Meta:
        model = Projet
        fields = ['titre', 'description', 'montant_demande', 'cover_image', 'date_fin']
    
    def __init__(self, *args, **kwargs):
        self.porteur = kwargs.pop('porteur', None)
        super().__init__(*args, **kwargs)
        
        # Personnalisation des labels et help texts
        self.fields['titre'].label = "Titre du projet"
        self.fields['titre'].help_text = "Un titre clair et concis pour votre projet"
        self.fields['description'].label = "Description détaillée"
        self.fields['description'].help_text = "Décrivez en détail votre projet, ses objectifs et son impact"
    
    def clean_date_fin(self):
        date_fin = self.cleaned_data.get('date_fin')
        if date_fin:
            if date_fin < timezone.now().date():
                raise ValidationError("La date de fin ne peut pas être dans le passé.")
            if date_fin > timezone.now().date() + timedelta(days=365):  # 1 an max
                raise ValidationError("La campagne ne peut pas durer plus d'un an.")
        return date_fin
    
    def clean(self):
        cleaned_data = super().clean()
        if self.porteur and Projet.objects.filter(porteur=self.porteur, statut__in=['actif','en_attente']).count() >= 5:
            raise ValidationError("Vous avez déjà 5 projets en cours. Veuillez en terminer un avant d'en créer un autre.")
        return cleaned_data

    def clean_montant_demande(self):
        montant = self.cleaned_data.get('montant_demande')
        if montant <= 0:
            raise ValidationError("Le montant doit être positif.")
        
        # Validation spécifique FCFA (pas de centimes)
        if montant % 1 != 0:
            raise ValidationError("Le montant doit être un nombre entier pour le FCFA.")
        
        # Montant minimum (par exemple 10 000 FCFA)
        if montant < 10000:
            raise ValidationError("Le montant minimum est de 10 000 FCFA.")
        
        return montant
    
    def save(self, commit=True):
        projet = super().save(commit=False)
        if self.porteur:
            projet.porteur = self.porteur
        
        # Par défaut, le statut est brouillon pour les nouveaux projets
        if not projet.pk:
            projet.statut = 'brouillon'
        
        if commit:
            projet.save()
        return projet
    
    
class DonForm(forms.ModelForm):
    # Montant en FCFA
    montant = forms.DecimalField(
        max_digits=10, 
        decimal_places=0,
        label="Montant du don (FCFA)",
        help_text="Montant en FCFA que vous souhaitez donner",
        widget=forms.NumberInput(attrs={'placeholder': '10000', 'min': '100'})
    )
    
    # Option de don anonyme
    don_anonyme = forms.BooleanField(
        required=False, 
        label="Faire un don anonyme",
        help_text="Votre nom n'apparaîtra pas publiquement"
    )
    
    class Meta:
        model = Transaction
        fields = ['montant', 'don_anonyme']
    
    def __init__(self, *args, **kwargs):
        self.projet = kwargs.pop('projet', None)
        self.donateur = kwargs.pop('donateur', None)
        super().__init__(*args, **kwargs)
        
        # Ajuster le montant minimum en fonction du projet
        if self.projet:
            montant_restant = self.projet.montant_demande - self.projet.montant_collecte
            if montant_restant > 0:
                self.fields['montant'].help_text += f". Il reste {montant_restant:.0f} FCFA à collecter."
    
    def clean_montant(self):
        montant =  self.cleaned_data.get('montant')
        
        if montant <= 0:
            raise ValidationError("Le montant doit être positif.")
        
        # Validation FCFA (nombre entier)
        if montant % 1 != 0:
            raise ValidationError("Le montant doit être un nombre entier pour le FCFA.")
        
        # Montant minimum de don (1000 FCFA)
        if montant < 1000:
            raise ValidationError("Le montant minimum de don est de 1 000 FCFA.")
        
        # Vérifier que le projet est encore actif
        if self.projet and self.projet.statut != 'actif':
            raise ValidationError("Ce projet n'accepte plus de dons.")
        
        # Vérifier que le montant ne dépasse pas le besoin restant
        if self.projet:
            montant_restant = self.projet.montant_demande - self.projet.montant_collecte
            if montant > montant_restant:
                raise ValidationError(f"Le montant ne peut pas dépasser les {montant_restant:.0f} FCFA restants.")
        
        return montant

class ValidationProjetForm(forms.ModelForm):
    # Formulaire pour la validation des projets par les administrateurs
    commentaire_validation = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Commentaire de validation",
        help_text="Commentaire optionnel sur la validation du projet"
    )
    
    class Meta:
        model = Projet
        fields = ['statut']  # On ne montre que le statut pour la validation
    
    def clean(self):
        cleaned_data = super().clean()
        statut = cleaned_data.get("statut")
        commentaire = cleaned_data.get("commentaire_validation")
        if statut == 'rejete' and not commentaire:
            raise ValidationError("Un commentaire est obligatoire en cas de rejet.")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limiter les choix de statut pour la validation
        self.fields['statut'].choices = [
            ('actif', 'Actif'),
            ('rejete', 'Rejeté')
        ]

class ProfilUtilisateurForm(forms.ModelForm):
    # Formulaire de mise à jour du profil utilisateur
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'telephone', 'adresse']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personnalisation des labels
        self.fields['first_name'].label = "Prénom"
        self.fields['last_name'].label = "Nom"
        self.fields['telephone'].label = "Téléphone"
        self.fields['adresse'].label = "Adresse"

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé par un autre utilisateur.")
        return email


class ContactForm(forms.Form):
    # Formulaire de contact générique
    sujet = forms.CharField(max_length=100, label="Sujet")
    email = forms.EmailField(label="Votre email")
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 5}), label="Message")
    
    def clean_sujet(self):
        sujet = self.cleaned_data.get('sujet')
        if len(sujet) < 5:
            raise ValidationError("Le sujet doit contenir au moins 5 caractères.")
        return sujet
    
    captcha = forms.CharField(label="Combien font 2 + 3 ?", help_text="Question anti-spam")

    def clean_captcha(self):
        value = self.cleaned_data.get('captcha')
        if value.strip() != "5":
            raise ValidationError("Captcha incorrect.")
        return value
