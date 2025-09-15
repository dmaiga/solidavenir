from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .models import User, Projet, Transaction
from django_summernote.widgets import SummernoteWidget
from django.utils import timezone
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from decimal import Decimal
from django import forms
from django.contrib.auth.forms import UserChangeForm
from .models import User

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Projet
from django import forms
from django.core.exceptions import ValidationError
from django_summernote.widgets import SummernoteWidget
from decimal import Decimal
from .models import Projet


class InscriptionFormSimplifiee(UserCreationForm):
    # Types d'utilisateurs sans admin
    USER_TYPES_WITHOUT_ADMIN = [
        ('porteur', 'Porteur de Projet'),
        ('donateur', 'Donateur/Philanthrope'),
        ('investisseur', 'Investisseur'),
        ('association', 'Association/ONG'),
    ]
    
    user_type = forms.ChoiceField(
        choices=USER_TYPES_WITHOUT_ADMIN, 
        label="Je suis",
        widget=forms.Select(attrs={
            'class': 'form-control', 
            'onchange': "showRelevantFields()",
            'id': 'user_type_select'
        })
    )
    
    # Champs essentiels seulement
    email = forms.EmailField(
        required=True, 
        label="Email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'votre.email@exemple.com'
        })
    )
    
    first_name = forms.CharField(
        max_length=30, 
        required=False, 
        label="Prénom",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Votre prénom'
        })
    )
    
    last_name = forms.CharField(
        max_length=30, 
        required=False, 
        label="Nom",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Votre nom'
        })
    )
    
    # Champ optionnel pour le nom de l'association (si type association)
    nom_association = forms.CharField(
        max_length=200, 
        required=False, 
        label="Nom de votre association",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ex: Association pour le développement durable',
            
        })
    )
    
    consentement_rgpd = forms.BooleanField(
        required=True, 
        label="J'accepte les conditions d'utilisation et la politique de confidentialité",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type', 'first_name', 'last_name', 'nom_association', 'consentement_rgpd']
        widgets = {
            'username': forms.HiddenInput(),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Créez un mot de passe sécurisé'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Confirmez votre mot de passe'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personnalisation des labels
        self.fields['password1'].label = "Mot de passe"
        self.fields['password2'].label = "Confirmation du mot de passe"
        
        # Génération automatique du username
        self.fields['username'].required = False
        
        # Aide contextuelle
        self.fields['password1'].help_text = "Utilisez au moins 8 caractères avec des lettres, chiffres et symboles"
        
        # Afficher le champ nom_association seulement si le type est association
        if 'user_type' in self.data:
            user_type = self.data.get('user_type')
            if user_type == 'association':
                self.fields['nom_association'].widget.attrs['style'] = 'display: block;'
                self.fields['nom_association'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        user_type = cleaned_data.get('user_type')
        nom_association = cleaned_data.get('nom_association')
        
        # Validation spécifique pour les associations
        if user_type == 'association' and not nom_association:
            self.add_error('nom_association', "Le nom de l'association est requis pour ce type de compte.")
        
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Un compte existe déjà avec cette adresse email.")
        return email
     
    def generate_username(self, first_name, last_name, email):
        """Génère un username unique basé sur le nom et prénom ou email"""
        base_username = ""
        if first_name and last_name:
            base_username = f"{first_name.lower()}.{last_name.lower()}"
        else:
            # Utiliser la partie avant @ de l'email
            base_username = email.split('@')[0]
        
        # Vérifier l'unicité et ajouter un numéro si nécessaire
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        # Génération automatique du username
        first_name = self.cleaned_data.get('first_name', '')
        last_name = self.cleaned_data.get('last_name', '')
        email = self.cleaned_data.get('email', '')
        user_type = self.cleaned_data.get('user_type')
        nom_association = self.cleaned_data.get('nom_association', '')
        
        user.username = self.generate_username(first_name, last_name, email)
        
        # Assigner les champs de base
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.consentement_rgpd = self.cleaned_data.get('consentement_rgpd', False)
        
        # Stocker le nom d'association pour la création du profil
        user.nom_association = nom_association
        
        if user.consentement_rgpd:
            user.date_consentement = timezone.now()
        
        if commit:
            user.save()

            # CRÉATION AUTOMATIQUE DU PROFIL ASSOCIATION SI BESOIN
            if user_type == 'association':
                from .models import Association
                # Éviter les doublons
                if not hasattr(user, 'association_profile'):
                    Association.objects.create(
                        user=user,
                        nom=nom_association or f"Association {user.username}",
                        domaine_principal='autre',
                        causes_defendues="Causes à définir",
                        statut_juridique='association', 
                        adresse_siege="Adresse à compléter",
                        ville="Bamako", 
                        code_postal="00000",
                        telephone="0000000000",
                        email_contact=user.email,
                        date_creation=timezone.now().date()
                    )

        return user


#
#   ASSOCIATION
#
from .models import Association
class AssociationForm(forms.ModelForm):
    """Formulaire pour la modification du profil association"""
    
    class Meta:
        model = Association
        fields = [
            'nom', 'slogan', 'description_courte', 'description_longue',
            'logo', 'cover_image', 'domaine_principal','domaines_secondaires', 'causes_defendues',
            'statut_juridique', 'numero_agrement', 'date_creation_association',
            'date_agrement', 'adresse_siege', 'ville', 'code_postal', 'pays',
            'telephone', 'email_contact', 'site_web', 'facebook', 'twitter',
            'instagram', 'linkedin', 'youtube', 'nombre_adherents',
            'nombre_beneficiaires', 'projets_phares', 'actions_en_cours',
            'partenariats', 'transparent_finances', 'transparent_actions'
        ]
        widgets = {
            'description_courte': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Description brève de votre association (200 caractères max)'
            }),
            'description_longue': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'placeholder': 'Description détaillée de votre association'
            }),
            'causes_defendues': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Les causes que vous défendez'
            }),
            'adresse_siege': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'form-control',
                'placeholder': 'Adresse complète du siège social'
            }),
            'projets_phares': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Vos projets les plus importants'
            }),
            'actions_en_cours': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Vos actions actuelles'
            }),
            'partenariats': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'form-control',
                'placeholder': 'Vos principaux partenaires'
            }),
            'date_creation_association': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'date_agrement': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Rendre tous les champs optionnels
        for field_name, field in self.fields.items():
            field.required = False
            if 'class' not in field.widget.attrs and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'
        
        # Personnalisation spécifique des champs
        self.fields['logo'].widget.attrs['class'] = 'form-control'
        self.fields['cover_image'].widget.attrs['class'] = 'form-control'
        
        # Textes d'aide conviviaux
        self.fields['transparent_finances'].help_text = "Partager nos informations financières nous aide à gagner la confiance des donateurs"
        self.fields['transparent_actions'].help_text = "Montrer nos actions concrètes permet de mieux nous faire connaître"
        
        # Placeholders pour les champs numériques
        self.fields['nombre_adherents'].widget.attrs['placeholder'] = 'Nombre approximatif'
        self.fields['nombre_beneficiaires'].widget.attrs['placeholder'] = 'Nombre approximatif'
        
        # Placeholders pour les URLs
        self.fields['site_web'].widget.attrs['placeholder'] = 'https://votre-site.org'
        self.fields['facebook'].widget.attrs['placeholder'] = 'https://facebook.com/votre-page'
        self.fields['twitter'].widget.attrs['placeholder'] = 'https://twitter.com/votre-compte'
        self.fields['instagram'].widget.attrs['placeholder'] = 'https://instagram.com/votre-compte'
        self.fields['linkedin'].widget.attrs['placeholder'] = 'https://linkedin.com/company/votre-entreprise'
        self.fields['youtube'].widget.attrs['placeholder'] = 'https://youtube.com/c/votre-chaine'
        
        # Réorganiser l'ordre des champs de manière logique
        self.order_fields([
            # Informations de base
            'nom', 'slogan', 'description_courte', 'description_longue',
            'logo', 'cover_image',
            
            # Domaine et statut
            'domaine_principal','domaines_secondaires' 'causes_defendues', 'statut_juridique',
            
            # Agréments et dates
            'numero_agrement', 'date_creation_association', 'date_agrement',
            
            # Contact et localisation
            'adresse_siege', 'ville', 'code_postal', 'pays',
            'telephone', 'email_contact', 'site_web',
            
            # Réseaux sociaux
            'facebook', 'twitter', 'instagram', 'linkedin', 'youtube',
            
            # Chiffres et informations
            'nombre_adherents', 'nombre_beneficiaires',
            'projets_phares', 'actions_en_cours', 'partenariats',
            
            # Transparence
            'transparent_finances', 'transparent_actions'
        ])


class ProfilUtilisateurForm(forms.ModelForm):
    """Formulaire de modification du profil utilisateur avec photo"""
    
    class Meta:
        model = User
        fields = [
            'photo_profil', 'first_name', 'last_name', 'email', 'telephone',
            'date_naissance', 'genre', 'bio', 'ville', 'pays', 'code_postal',
            'site_web_perso', 'linkedin', 'twitter', 'facebook',
            'newsletter'  # Ajout de la newsletter
        ]
        widgets = {
            'date_naissance': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Parlez-nous un peu de vous...'}),
            'photo_profil': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'photo_profil': 'Photo de profil',
            'site_web_perso': 'Site web personnel',
            'newsletter': 'Recevoir la newsletter',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personnaliser les help texts
        self.fields['photo_profil'].help_text = "Image carrée recommandée (JPG, PNG, max 5 Mo)"
        self.fields['bio'].help_text = "Une brève description de vous-même (optionnel)"
        self.fields['date_naissance'].help_text = "Format: JJ/MM/AAAA"
        
        # Ajouter des classes Bootstrap à tous les champs
        for field_name, field in self.fields.items():
            if field_name != 'photo_profil':  # Le champ fichier a déjà une classe
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'
    
    def clean_photo_profil(self):
        photo = self.cleaned_data.get('photo_profil')
        if photo:
            # Vérifier la taille (5 Mo max)
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("L'image ne doit pas dépasser 5 Mo.")
            
            # Vérifier l'extension
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
            extension = photo.name.split('.')[-1].lower()
            if extension not in valid_extensions:
                raise forms.ValidationError("Format d'image non supporté. Utilisez JPG, PNG ou GIF.")
        
        return photo
    
    def clean_date_naissance(self):
        date_naissance = self.cleaned_data.get('date_naissance')
        if date_naissance:
            from datetime import date
            # Vérifier que l'utilisateur a au moins 13 ans
            age_minimum = date.today().year - date_naissance.year
            if age_minimum < 13:
                raise forms.ValidationError("Vous devez avoir au moins 13 ans pour utiliser cette plateforme.")
        return date_naissance

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



class AdminCreationForm(UserCreationForm):
    """Formulaire pour créer des administrateurs (à utiliser dans l'admin ou backoffice)"""
    
    departement = forms.CharField(
        max_length=100, 
        required=True, 
        label="Département",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role_admin = forms.CharField(
        max_length=100, 
        required=True, 
        label="Rôle administrateur",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'first_name', 'last_name', 'departement', 'role_admin']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.user_type = 'admin'
        user.departement = self.cleaned_data.get('departement')
        user.role_admin = self.cleaned_data.get('role_admin')
        
        if commit:
            user.save()
        return user
    

from django import forms
from .models import User
from django.core.validators import FileExtensionValidator


# forms.py
import random
from django import forms
from django.core.exceptions import ValidationError
import random
from django import forms
from django.core.exceptions import ValidationError

    

from django import forms
from .models import User

class FiltreMembresForm(forms.Form):
    TYPE_CHOICES = [
        ('', 'Tous les types'),
        ('porteur', 'Porteur de projet'),
        ('donateur', 'Donateur'),
        ('investisseur', 'Investisseur'),
        ('association', 'Association'),
        ('admin', 'Administrateur'),
    ]
    
    STATUT_CHOICES = [
        ('', 'Tous les statuts'),
        ('true', 'Actif'),
        ('false', 'Inactif'),
    ]
    
    user_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        label="Type d'utilisateur"
    )
    
    actif = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        label="Statut du compte"
    )
    
    date_debut = forms.DateField(
        required=False,
        label="Date d'inscription (début)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    date_fin = forms.DateField(
        required=False,
        label="Date d'inscription (fin)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    recherche = forms.CharField(
        required=False,
        label="Recherche",
        widget=forms.TextInput(attrs={
            'placeholder': 'Nom, email, organisation...',
            'class': 'form-control'
        })
    )


class FiltreTransactionsForm(forms.Form):
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date (début)'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date (fin)'
    )
    montant_min = forms.DecimalField(
        required=False,
        min_value=0,
        label='Montant min (FCFA)'
    )
    montant_max = forms.DecimalField(
        required=False,
        min_value=0,
        label='Montant max (FCFA)'
    )
    projet = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nom du projet...'}),
        label='Projet'
    )

class FiltreAuditForm(forms.Form):
    ACTION_CHOICES = [
        ('', 'Toutes les actions'),
        ('create', 'Création'),
        ('update', 'Modification'),
        ('delete', 'Suppression'),
        ('validate', 'Validation'),
        ('reject', 'Rejet'),
    ]
    
    utilisateur = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label='Utilisateur'
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        label='Action'
    )
    modele = forms.CharField(
        required=False,
        label='Modèle'
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date (début)'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date (fin)'
    )
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Modèle, ID objet, détails...'}),
        label='Recherche'
    )
#
class Transfer_fond(forms.ModelForm):
    # Montant en FCFA
    montant = forms.DecimalField(
        max_digits=10, 
        decimal_places=0,
        label="Montant de la contribution (FCFA)",  # Texte changé
        help_text="Montant en FCFA que vous souhaitez contribuer",  # Texte changé
        widget=forms.NumberInput(attrs={'placeholder': '10000', 'min': '100'})
    )
    
    # Option de contribution anonyme
    contribution_anonyme = forms.BooleanField(  # Nom changé
        required=False, 
        label="Contribuer anonymement",  # Texte changé
        help_text="Votre nom n'apparaîtra pas publiquement"
    )
    
    class Meta:
        model = Transaction
        fields = ['montant', 'contribution_anonyme']  # Nom changé
    
    def __init__(self, *args, **kwargs):
        self.projet = kwargs.pop('projet', None)
        self.contributeur = kwargs.pop('contributeur', None)  # Nom changé
        super().__init__(*args, **kwargs)
        
        if self.projet:
            montant_restant = self.projet.montant_demande - self.projet.montant_collecte
            if montant_restant > 0:
                self.fields['montant'].help_text += f". Il reste {montant_restant:.0f} FCFA à collecter."
        
        taux_conversion = self.get_taux_conversion_actuel()
        self.fields['montant'].help_text += f" (≈ 1 HBAR = {taux_conversion} FCFA)"
    
    def get_taux_conversion_actuel(self):
        try:
            response = requests.get('https://api.taux-conversion.com/fcfa/hbar')
            data = response.json()
            return Decimal(data['taux'])
        except:
            return Decimal('0.8')
    
    def clean_montant(self):
        montant = self.cleaned_data.get('montant')
        
        if montant <= 0:
            raise ValidationError("Le montant doit être positif.")
        
        if montant % 1 != 0:
            raise ValidationError("Le montant doit être un nombre entier pour le FCFA.")
        
        if montant < 1000:
            raise ValidationError("Le montant minimum de contribution est de 1 000 FCFA.")  # Texte changé
        
        if self.projet and self.projet.statut != 'actif':
            raise ValidationError("Ce projet n'accepte plus de contributions.")  # Texte changé
        
        if self.projet:
            montant_restant = self.projet.montant_demande - self.projet.montant_collecte
            if montant > montant_restant:
                raise ValidationError(f"Le montant ne peut pas dépasser les {montant_restant:.0f} FCFA restants.")
        
        return montant



from django import forms
from .models import EmailLog

class EmailForm(forms.ModelForm):
    class Meta:
        model = EmailLog
        fields = ['destinataire', 'sujet', 'corps', 'type_email']
        widgets = {
            'destinataire': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@exemple.com'
            }),
            'sujet': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Sujet de votre email'
            }),
            'corps': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Contenu de votre message...'
            }),
            'type_email': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        labels = {
            'destinataire': 'Destinataire',
            'sujet': 'Sujet',
            'corps': 'Message',
            'type_email': 'Type d\'email'
        }

class EmailFormSimple(forms.Form):
    destinataire = forms.EmailField(
        label="Destinataire",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@exemple.com'
        })
    )
    sujet = forms.CharField(
        label="Sujet",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sujet de votre email'
        })
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Contenu de votre message...'
        })
    )
    type_email = forms.ChoiceField(
        label="Type d'email",
        choices=EmailLog.TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )


from django import forms
from .models import ContactSubmission
import random

class ContactForm(forms.ModelForm):
    # CAPTCHA plus sécurisé avec opération aléatoire
    captcha_question = forms.CharField(widget=forms.HiddenInput())
    captcha_answer = forms.CharField(
        label="Question de sécurité",
        help_text="Répondez à la question ci-dessous pour prouver que vous n'êtes pas un robot",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Votre réponse'
        })
    )
    
    class Meta:
        model = ContactSubmission
        fields = ['sujet', 'email', 'message']
        widgets = {
            'sujet': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Problème avec un don'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'votre@email.com'
            }),
            'message': forms.Textarea(attrs={
                'rows': 5,
                'class': 'form-control',
                'placeholder': 'Décrivez votre demande en détail...'
            }),
        }
        labels = {
            'sujet': 'Sujet',
            'email': 'Votre email',
            'message': 'Message',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Générer une question CAPTCHA aléatoire
        if not self.is_bound:
            a = random.randint(1, 10)
            b = random.randint(1, 10)
            operation = random.choice(['+', '-'])
            
            if operation == '+':
                result = a + b
                question = f"{a} + {b}"
            else:
                result = max(a, b) - min(a, b)
                question = f"{max(a, b)} - {min(a, b)}"
            
            self.fields['captcha_question'].initial = f"{question}|{result}"
            self.initial['captcha_question'] = f"{question}|{result}"
            # Stocker la question pour l'affichage dans le template
            self.captcha_display_question = question
    
    def clean_sujet(self):
        sujet = self.cleaned_data.get('sujet')
        if len(sujet) < 5:
            raise forms.ValidationError("Le sujet doit contenir au moins 5 caractères.")
        return sujet
    
    def clean_captcha_answer(self):
        answer = self.cleaned_data.get('captcha_answer')
        question_data = self.cleaned_data.get('captcha_question', '')
        
        if not question_data:
            raise forms.ValidationError("Erreur de validation du CAPTCHA.")
        
        question, expected_answer = question_data.split('|')
        
        try:
            user_answer = int(answer.strip())
        except (ValueError, TypeError):
            raise forms.ValidationError("Veuillez entrer un nombre valide.")
        
        if user_answer != int(expected_answer):
            raise forms.ValidationError(f"Réponse incorrecte. La réponse attendue était {expected_answer}.")
        
        return answer
    



class CreationProjetForm(forms.ModelForm):
    """Formulaire simplifié de création de projet"""
    
    # Champ description avec éditeur riche
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 8,
            'class': 'form-control',
            'placeholder': 'Décrivez votre projet en détail...'
        }),
        label="Description complète"
    )
    
    # Description courte
    description_courte = forms.CharField(
        max_length=300,
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'maxlength': '300',
            'class': 'form-control',
            'placeholder': 'Résumez votre projet en 300 caractères maximum...'
        }),
        label="Résumé du projet",
        help_text="300 caractères maximum - Ce résumé apparaîtra dans les listes de projets"
    )
    
    # Montants
    montant_demande = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        label="Montant demandé (FCFA)",
        help_text="Montant total nécessaire pour réaliser votre projet",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '500000'
        })
    )
    
    # Récompenses simplifiées
    offre_recompenses = forms.BooleanField(
        required=False,
        label="Proposer des contreparties aux contributeurs ?",
        help_text="Cochez cette case si vous souhaitez offrir des récompenses en échange des contributions",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    description_recompenses = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Décrivez les contreparties que vous offrez (ex: Nom sur le mur des donateurs, produit personnalisé, invitation à l\'inauguration, etc.)...'
        }),
        label="Description des contreparties",
        help_text="Décrivez brièvement ce que vous proposez en échange des contributions"
    )
    
    class Meta:
        model = Projet
        fields = [
            'titre', 'description_courte', 'description', 'categorie', 'autre_categorie',
            'type_financement', 'montant_demande', 'offre_recompenses', 'description_recompenses',
            'cover_image', 'video_presentation', 'duree_campagne', 'tags', 'association'
        ]
        widgets = {
            'titre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre accrocheur de votre projet...'
            }),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'autre_categorie': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Précisez votre catégorie...',
                'style': 'display: none;'
            }),
            'type_financement': forms.Select(attrs={'class': 'form-control'}),
            'video_presentation': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://youtube.com/... (optionnel)'
            }),
            'duree_campagne': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 15,
                'max': 90,
                'value': 30
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'innovation, écologie, éducation... (séparés par des virgules)'
            }),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'association': forms.HiddenInput(),  # Champ caché pour l'association
        }
    
    def __init__(self, *args, **kwargs):
        self.porteur = kwargs.pop('porteur', None)
        super().__init__(*args, **kwargs)
        
        # Configuration initiale
        self.fields['duree_campagne'].initial = 30
        self.fields['type_financement'].initial = 'don'
        self.fields['cover_image'].help_text = "Image de présentation (format recommandé: 1200x600px)"
        
        # Gérer le champ association
        if self.porteur and hasattr(self.porteur, 'association_profile'):
            # Si l'utilisateur est une association, pré-remplir et cacher le champ
            self.fields['association'].initial = self.porteur.association_profile
            self.fields['association'].widget = forms.HiddenInput()
        else:
            # Si l'utilisateur n'est pas une association, cacher le champ
            self.fields['association'].widget = forms.HiddenInput()
            self.fields['association'].required = False
        
        # Si modification et récompenses existent
        if self.instance and self.instance.has_recompenses:
            self.fields['offre_recompenses'].initial = True
            self.fields['description_recompenses'].initial = self.instance.recompenses_description
    
    def clean(self):
        cleaned_data = super().clean()
        offre_recompenses = cleaned_data.get('offre_recompenses')
        description_recompenses = cleaned_data.get('description_recompenses')
        categorie = cleaned_data.get('categorie')
        autre_categorie = cleaned_data.get('autre_categorie')
        type_financement = cleaned_data.get('type_financement')
        association = cleaned_data.get('association')
        
        # Validation récompenses
        if offre_recompenses and not description_recompenses:
            self.add_error('description_recompenses', "Veuillez décrire les contreparties que vous proposez.")
        
        # Validation catégorie
        if categorie == 'autre' and not autre_categorie:
            self.add_error('autre_categorie', "Veuillez préciser la catégorie de votre projet.")
        
        if categorie != 'autre' and autre_categorie:
            self.add_error('autre_categorie', "Ce champ ne doit être rempli que si vous sélectionnez 'Autre domaine'.")
        
        # Validation type financement vs récompenses
        if offre_recompenses and type_financement not in ['don', 'recompense', 'mixte']:
            self.add_error('offre_recompenses', "Les contreparties ne sont disponibles que pour les dons, récompenses ou financements mixtes.")
        
        # Validation association
        if association and self.porteur:
            # Vérifier que l'utilisateur a le droit d'associer ce projet à cette association
            if hasattr(self.porteur, 'association_profile') and self.porteur.association_profile != association:
                self.add_error('association', "Vous ne pouvez pas associer ce projet à cette association.")
        
        return cleaned_data
    
    def clean_description_courte(self):
        """Validation pour la description courte"""
        description_courte = self.cleaned_data.get('description_courte', '')
        description_courte = description_courte.strip()
        
        if len(description_courte) < 20:
            raise ValidationError("Le résumé doit contenir au moins 20 caractères.")
        
        if len(description_courte) > 300:
            raise ValidationError("Le résumé ne peut pas dépasser 300 caractères.")
        
        return description_courte
    
    def clean_montant_demande(self):
        """Validation du montant demandé"""
        montant = self.cleaned_data.get('montant_demande')
        if montant and montant < 10000:
            raise ValidationError("Le montant demandé doit être d'au moins 10 000 FCFA.")
        return montant
    
    def save(self, commit=True):
        projet = super().save(commit=False)
        
        if self.porteur:
            projet.porteur = self.porteur
        
        # Gestion des récompenses
        offre_recompenses = self.cleaned_data.get('offre_recompenses', False)
        description_recompenses = self.cleaned_data.get('description_recompenses', '')
        
        projet.has_recompenses = offre_recompenses
        projet.recompenses_description = description_recompenses if offre_recompenses else None
        
        # Montant minimal par défaut à 50%
        if not projet.montant_minimal and projet.montant_demande:
            projet.montant_minimal = Decimal(projet.montant_demande) * Decimal('0.5')
        
        if commit:
            projet.save()
            self.save_m2m() 
        
        return projet    
