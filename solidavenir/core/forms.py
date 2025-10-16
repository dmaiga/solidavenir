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

from .models import Projet,ImageProjet
from django import forms
from django.core.exceptions import ValidationError
from django_summernote.widgets import SummernoteWidget
from decimal import Decimal
from .models import Projet

from django import forms
from .models import User,Palier
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




from django import forms
from .models import EmailLog

from django import forms
from .models import ContactSubmission
import random
from django import forms
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from django import forms
from django.utils.html import format_html



class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # Si data est None, retourner une liste vide
        if not data:
            return []

        # Si c'est déjà une liste (cas de MultipleFileInput), traiter chaque fichier
        cleaned_files = []
        if isinstance(data, (list, tuple)):
            for d in data:
                cleaned_files.append(super().clean(d, initial))
            return cleaned_files
        
        # Sinon, retourner une liste avec un seul élément
        return [super().clean(data, initial)]


class MultiFileInput(forms.ClearableFileInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = attrs or {}
        attrs['multiple'] = 'multiple'
        return super().render(name, value, attrs, renderer)
    
    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return None

class InscriptionFormSimplifiee(UserCreationForm):
    """
    Simplified registration form for creating users without admin access.

    Supports the following user types:
    - Project Owner ('porteur')
    - Donor/Philanthropist ('donateur')
    - Investor ('investisseur')
    - Association/NGO ('association')

    Handles optional association name field and GDPR consent.
    Automatically generates a unique username based on first name, last name, or email.
    """
    # Types d'utilisateurs sans admin
    USER_TYPES_WITHOUT_ADMIN = [
        ('porteur', 'Project Owner'),
        ('donateur', 'Donor/Philanthropist'),
        ('investisseur', 'Investor'),
        ('association', 'Association/NGO'),
    ]
    
    user_type = forms.ChoiceField(
        choices=USER_TYPES_WITHOUT_ADMIN, 
        label="I am",
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
            'placeholder': 'your.email@example.com'
        })
    )
    
    first_name = forms.CharField(
        max_length=30, 
        required=False, 
        label="First Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Your first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=30, 
        required=False, 
        label="Last Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Your last name'
        })
    )
    
    # Champ optionnel pour le nom de l'association (si type association)
    nom_association = forms.CharField(
        max_length=200, 
        required=False, 
        label="Your association name",
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Ex: Association for Sustainable Development',
            
        })
    )
    
    consentement_rgpd = forms.BooleanField(
        required=True, 
        label="I accept the terms of use and privacy policy",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2', 'user_type', 'first_name', 'last_name', 'nom_association', 'consentement_rgpd']
        widgets = {
            'username': forms.HiddenInput(),
            'password1': forms.PasswordInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Create a secure password'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Confirm your password'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personnalisation des labels
        self.fields['password1'].label = "Password"
        self.fields['password2'].label = "Password Confirmation"
        
        # Génération automatique du username
        self.fields['username'].required = False
        
        # Aide contextuelle
        self.fields['password1'].help_text = "Use at least 8 characters with letters, numbers and symbols"
        
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
            self.add_error('nom_association', "Association name is required for this account type.")
        
        return cleaned_data
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("An account already exists with this email address.")
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
                        
                        email_contact=user.email,
                        date_creation=timezone.now().date()
                    )

        return user
    


#
#   ASSOCIATION
#
from .models import Association,AssociationImage
class AssociationForm(forms.ModelForm):
    """
    Form for editing an Association profile.

    Allows updating key information such as:
    - Basic information (name, slogan, short/long description)
    - Visuals (logo, cover image)
    - Main and secondary domains, causes supported
    - Legal status, registration number, creation date, approval date
    - Contact information and social media links
    - Key figures (members, beneficiaries)
    - Projects, ongoing actions, partnerships
    - Transparency indicators for finances and actions

    All fields are optional, with placeholders and help texts to guide users.
    """
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
                'placeholder': 'Brief description of your association (max 200 characters)'
            }),
            'description_longue': forms.Textarea(attrs={
                'rows': 5, 
                'class': 'form-control',
                'placeholder': 'Detailed description of your association'
             }),
            'causes_defendues': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Causes you support'

            }),
            'adresse_siege': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'form-control',
                'placeholder':'Full address of the head office'
            }),
            'projets_phares': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Your main projects'
            }),
            'actions_en_cours': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control',
                'placeholder': 'Current actions'
            }),
            'partenariats': forms.Textarea(attrs={
                'rows': 2, 
                'class': 'form-control',
                'placeholder': 'Your main partners'
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
        """
        Initialize the form.

        - Makes all fields optional.
        - Adds Bootstrap classes for styling.
        - Sets placeholders for numeric and URL fields.
        - Adds help texts for transparency fields.
        - Reorders fields for logical grouping.
        """
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
        self.fields['transparent_finances'].help_text =   "Sharing financial information helps gain donor trust."
        self.fields['transparent_actions'].help_text =   "Showing concrete actions helps increase visibility."
        # Placeholders pour les champs numériques
        self.fields['nombre_adherents'].widget.attrs['placeholder'] = 'Approximate number'
        self.fields['nombre_beneficiaires'].widget.attrs['placeholder'] = 'Approximate number'
        
        # Placeholders pour les URLs
        self.fields['site_web'].widget.attrs['placeholder'] = 'https://your-site.org'
        self.fields['facebook'].widget.attrs['placeholder'] = 'https://facebook.com/your-page'
        self.fields['twitter'].widget.attrs['placeholder'] = 'https://twitter.com/your-account'
        self.fields['instagram'].widget.attrs['placeholder'] = 'https://instagram.com/your-account'
        self.fields['linkedin'].widget.attrs['placeholder'] = 'https://linkedin.com/company/your-company'
        self.fields['youtube'].widget.attrs['placeholder'] = 'https://youtube.com/c/your-channel'
        
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


class AssociationImageForm(forms.ModelForm):
    """
       
    Simplified form for uploading an image associated with an Association.

    This form only includes the 'image' field, allowing users to upload
    a single image without additional metadata or fields.
 
    Formulaire ultra-simplifié pour l'upload d'images
    """
    class Meta:
        model = AssociationImage
        fields = ['image']


class ProfilUtilisateurForm(forms.ModelForm):
    """
    User profile update form including profile picture.

    Allows users to update personal information such as name, email,
    contact details, biography, social media links, and newsletter preference.
    Also supports uploading a profile picture with size and format validation.
    
    Formulaire de modification du profil utilisateur avec photo"""
    
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
            'bio': forms.Textarea(attrs={'rows': 4, 'class': 'form-control', 'placeholder': 'Tell us a bit about yourself...' }),
            'photo_profil': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
        labels = {
            'photo_profil': 'Profile Picture',
            'site_web_perso': 'Personal Website',
            'newsletter': 'Subscribe to newsletter',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Personnaliser les help texts
        self.fields['photo_profil'].help_text = "Recommended square image (JPG, PNG, max 5 MB)"
        self.fields['bio'].help_text = "A brief description about yourself (optional)"
        self.fields['date_naissance'].help_text = "Format: DD/MM/YYYY" 
        
        # Ajouter des classes Bootstrap à tous les champs
        
        for field_name, field in self.fields.items():
            if field_name != 'photo_profil':  # Le champ fichier a déjà une classe
                field.widget.attrs['class'] = field.widget.attrs.get('class', '') + ' form-control'
    
    def clean_photo_profil(self):
        """
        Validates the uploaded profile picture.

        Checks that the file size does not exceed 5 MB and that the file format
        is among the allowed image types (JPG, PNG, GIF).
        """
        photo = self.cleaned_data.get('photo_profil')
        if photo:
            # Vérifier la taille (5 Mo max)
            if photo.size > 5 * 1024 * 1024:
                raise forms.ValidationError("L'image ne doit pas dépasser 5 Mo.")
            
            # Vérifier l'extension
            valid_extensions = ['jpg', 'jpeg', 'png', 'gif']
            extension = photo.name.split('.')[-1].lower()
            if extension not in valid_extensions:
                raise forms.ValidationError("Unsupported image format. Use JPG, PNG, or GIF.")
        
        return photo
    
    def clean_date_naissance(self):
        """
        Validates the user's date of birth.

        Ensures that the user is at least 13 years old to use the platform.
        """
        date_naissance = self.cleaned_data.get('date_naissance')
        if date_naissance:
            from datetime import date
            # Vérifier que l'utilisateur a au moins 13 ans
            age_minimum = date.today().year - date_naissance.year
            if age_minimum < 13:
                raise forms.ValidationError("You must be at least 13 years old to use this platform.")
        return date_naissance
    

class ValidationProjetForm(forms.ModelForm):
    """
    Form for project validation by administrators.

    Allows admins to set the project status to either 'Active' or 'Rejected'.
    Includes an optional validation comment, which becomes mandatory if the project is rejected.
    """
    # Formulaire pour la validation des projets par les administrateurs
    commentaire_validation = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        required=False,
        label="Validation Comment",
        help_text="Optional comment regarding the project validation"
    )
    
    class Meta:
        model = Projet
        fields = ['statut']  # On ne montre que le statut pour la validation
    
    def clean(self):
        """
        Ensures that a comment is provided when the project is rejected.
        """
        cleaned_data = super().clean()
        statut = cleaned_data.get("statut")
        commentaire = cleaned_data.get("commentaire_validation")
        if statut == 'rejete' and not commentaire:
            raise ValidationError("A comment is required when rejecting a project.")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        """
        Initializes the form and restricts the status choices for validation purposes.
        """
        super().__init__(*args, **kwargs)
        # Limiter les choix de statut pour la validation
        self.fields['statut'].choices = [
            ('actif', 'Actif'),
            ('rejete', 'Rejeté')
        ]



class AdminCreationForm(UserCreationForm):
    """
    Form for creating administrator accounts.

    This form is intended for use in the admin panel or backoffice.
    Includes fields for department and administrator role, in addition to basic user info.
    """
    """Formulaire pour créer des administrateurs (à utiliser dans l'admin ou backoffice)"""
    
    departement = forms.CharField(
        max_length=100, 
        required=True, 
        label="Department",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    role_admin = forms.CharField(
        max_length=100, 
        required=True, 
        label="Administrator Role",
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
        """
        Saves the user instance as an administrator.

        Sets the user_type to 'admin' and assigns department and admin role.
        """
        user = super().save(commit=False)
        user.user_type = 'admin'
        user.departement = self.cleaned_data.get('departement')
        user.role_admin = self.cleaned_data.get('role_admin')
        
        if commit:
            user.save()
        return user
    

class FiltreMembresForm(forms.Form):
    """
    Form for filtering users/members in the admin panel or dashboard.

    Allows filtering by user type, account status, registration date range, 
    and a search field for name, email, or organization.
    """
    
    TYPE_CHOICES = [
        ('', 'All types'),
        ('porteur', 'Project Owner'),
        ('donateur', 'Donor'),
        ('investisseur', 'Investor'),
        ('association', 'Association/NGO'),
        ('admin', 'Administrator'),
    ]
    
    STATUT_CHOICES = [
        ('', 'All statuses'),
        ('true', 'Active'),
        ('false', 'Inactive'),
    ]
    
    user_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        label="User Type"
    )
    
    actif = forms.ChoiceField(
        choices=STATUT_CHOICES,
        required=False,
        label="Account Status"
    )
    
    date_debut = forms.DateField(
        required=False,
        label="Registration Date (start)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    date_fin = forms.DateField(
        required=False,
        label="Registration Date (end)",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    recherche = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={
            'placeholder': 'Name, email, organization...',
            'class': 'form-control'
        })
    )


class FiltreTransactionsForm(forms.Form):
    """
    Form for filtering financial transactions.

    Allows filtering by date range, minimum and maximum amount, 
    and associated project name.
    """
    
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Start Date'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='End Date'
    )
    montant_min = forms.DecimalField(
        required=False,
        min_value=0,
        label='Minimum Amount (FCFA)'
    )
    montant_max = forms.DecimalField(
        required=False,
        min_value=0,
        label='Maximum Amount (FCFA)'
    )
    projet = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Project name...'}),
        label='Project'
    )

class FiltreAuditForm(forms.Form):
    """
    Form for filtering audit logs.

    Allows filtering by user, action type, model name, 
    date range, and a general search term.
    """
    
    ACTION_CHOICES = [
        ('', 'All actions'),
        ('create', 'Creation'),
        ('update', 'Update'),
        ('delete', 'Deletion'),
        ('validate', 'Validation'),
        ('reject', 'Rejection'),
    ]
    
    utilisateur = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label='User'
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        label='Action'
    )
    modele = forms.CharField(
        required=False,
        label='Model'
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Start Date'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='End Date'
    )
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Model, Object ID, Details...'}),
        label='Search'
    )


class Transfer_fond(forms.ModelForm):
    """
    Form for contributing funds to a project.

    Fields:
        montant (DecimalField): Amount to contribute in FCFA.
            Must be a positive integer, minimum 1,000 FCFA, and not exceed the remaining amount required by the project.
            Displays the current HBAR conversion rate in the help text.
        
        contribution_anonyme (BooleanField): Option to contribute anonymously.
            If checked, the contributor's name will not appear publicly.

    Attributes:
        projet (Projet, optional): The project to which the contribution is made.
        contributeur (User, optional): The user making the contribution.

    Methods:
        get_taux_conversion_actuel(): Retrieves the current FCFA to HBAR conversion rate from an external API.
        clean_montant(): Validates the 'montant' field according to the rules described above.
    """
    
    montant = forms.DecimalField(
        max_digits=10, 
        decimal_places=0,
        label="Contribution amount (FCFA)",
        help_text="Amount in FCFA you wish to contribute",
        widget=forms.NumberInput(attrs={'placeholder': '10000', 'min': '1'})
    )
    
    contribution_anonyme = forms.BooleanField(
        required=False, 
        label="Contribute anonymously",
        help_text="Your name will not appear publicly"
    )
    
    class Meta:
        model = Transaction
        fields = ['montant', 'contribution_anonyme']
    
    def __init__(self, *args, **kwargs):
        self.projet = kwargs.pop('projet', None)
        self.contributeur = kwargs.pop('contributeur', None)
        super().__init__(*args, **kwargs)
        
        if self.projet:
            montant_restant = self.projet.montant_demande - self.projet.montant_collecte
            if montant_restant > 0:
                self.fields['montant'].help_text += f". Remaining amount to collect: {montant_restant:.0f} FCFA."
        
        taux_conversion = self.get_taux_conversion_actuel()
        self.fields['montant'].help_text += f" (≈ 1 HBAR = {taux_conversion} FCFA)"
    
    def get_taux_conversion_actuel(self):
        """Fetches the current conversion rate from FCFA to HBAR."""
        try:
            response = requests.get('https://api.taux-conversion.com/fcfa/hbar')
            data = response.json()
            return Decimal(data['taux'])
        except:
            return Decimal('0.8')
    
    def clean_montant(self):
        """
        Validates the contribution amount.

        Checks:
            - Positive number
            - Integer value
            - Minimum 1,000 FCFA
            - Does not exceed remaining amount required
            - Project is still active
        """
        montant = self.cleaned_data.get('montant')
        
        if montant <= 0:
            raise ValidationError("Amount must be positive.")
        
        if montant % 1 != 0:
            raise ValidationError("Amount must be an integer in FCFA.")
        
        if montant < 1000:
            raise ValidationError("Minimum contribution is 1,000 FCFA.")
        
        if self.projet and self.projet.statut != 'actif':
            raise ValidationError("This project no longer accepts contributions.")
        
        if self.projet:
            montant_restant = self.projet.montant_demande - self.projet.montant_collecte
            if montant > montant_restant:
                raise ValidationError(f"Amount cannot exceed the remaining {montant_restant:.0f} FCFA.")
        
        return montant


class EmailForm(forms.ModelForm):
    """
    Form for composing and sending emails.

    Fields:
        destinataire (EmailField): Recipient's email address.
            Must be a valid email format.
        
        sujet (CharField): Subject of the email.
        
        corps (TextField): Body/content of the email.
        
        type_email (ChoiceField): Type of email.
            Allows selection from predefined email types.

    Widgets:
        - 'destinataire': Email input with placeholder.
        - 'sujet': Text input with placeholder.
        - 'corps': Textarea with placeholder and 5 rows.
        - 'type_email': Select dropdown.

    Labels:
        - destinataire: "Recipient"
        - sujet: "Subject"
        - corps: "Message"
        - type_email: "Email Type"
    """
    
    class Meta:
        model = EmailLog
        fields = ['destinataire', 'sujet', 'corps', 'type_email']
        widgets = {
            'destinataire': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'email@example.com'
            }),
            'sujet': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Subject of your email'
            }),
            'corps': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Write your message here...'
            }),
            'type_email': forms.Select(attrs={
                'class': 'form-select'
            })
        }
        labels = {
            'destinataire': 'Recipient',
            'sujet': 'Subject',
            'corps': 'Message',
            'type_email': 'Email Type'
        }



class EmailFormSimple(forms.Form):
    """
    Simple form for composing an email.

    Fields:
        destinataire (EmailField): Recipient's email address. Must be a valid email.
        sujet (CharField): Subject of the email, maximum 200 characters.
        message (CharField): Body/content of the email.
        type_email (ChoiceField): Type of email, selected from predefined choices (EmailLog.TYPES).

    Widgets:
        - destinataire: Email input with Bootstrap styling and placeholder.
        - sujet: Text input with Bootstrap styling and placeholder.
        - message: Textarea with 5 rows, Bootstrap styling, and placeholder.
        - type_email: Select dropdown with Bootstrap styling.
    """
    
    destinataire = forms.EmailField(
        label="Recipient",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'email@example.com'
        })
    )
    sujet = forms.CharField(
        label="Subject",
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Subject of your email'
        })
    )
    message = forms.CharField(
        label="Message",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Write your message here...'
        })
    )
    type_email = forms.ChoiceField(
        label="Email Type",
        choices=EmailLog.TYPES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        })
    )


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
    """
    Simplified project creation form with reward-based business/social distinction
    """
    
    # Description field with rich editor
    description = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 8,
            'class': 'form-control',
            'placeholder': 'Describe your project in detail...'
        }),
        label="Complete Description"
    )
    
    # Short description
    description_courte = forms.CharField(
        max_length=300,
        required=True,
        widget=forms.Textarea(attrs={
            'rows': 3, 
            'maxlength': '300',
            'class': 'form-control',
            'placeholder': 'Summarize your project in 300 characters maximum...'
        }),
        label="Project Summary",
        help_text="300 characters maximum - This summary will appear in project lists"
    )
    
    # Amounts
    montant_demande = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        label="Requested Amount (FCFA)",
        help_text="Total amount needed to realize your project",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '500000'
        })
    )
    
    # Rewards section - Natural business/social distinction
    offre_recompenses = forms.BooleanField(
        required=False,
        label="Offer rewards to contributors?",
        help_text="Check this box if you wish to offer rewards in exchange for contributions",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    description_recompenses = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 4,
            'class': 'form-control',
            'placeholder': 'Describe the rewards you offer (examples below)...\n\n💼 BUSINESS: Equity, profit-sharing, product pre-orders, VIP services\n🚀 SOCIAL: Donor wall recognition, naming opportunities, community events, impact reports\n🌱 ECOLOGICAL: Eco-friendly products, planting certificates, sustainability workshops'
        }),
        label="Rewards Description",
        help_text="The type of rewards naturally indicates your project nature (business, social, ecological)"
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
                'placeholder': 'Catchy title for your project...'
            }),
            'categorie': forms.Select(attrs={'class': 'form-control'}),
            'autre_categorie': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Specify your category...',
                'style': 'display: none;'
            }),
            'type_financement': forms.Select(attrs={'class': 'form-control'}),
            'video_presentation': forms.URLInput(attrs={
                'class': 'form-control',
                'placeholder': 'https://youtube.com/... (optional)'
            }),
            'duree_campagne': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 15,
                'max': 90,
                'value': 30
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'innovation, ecology, education... (comma separated)'
            }),
            'cover_image': forms.FileInput(attrs={'class': 'form-control'}),
            'association': forms.HiddenInput(),  # Hidden field for association
        }
    
    def __init__(self, *args, **kwargs):
        self.porteur = kwargs.pop('porteur', None)
        super().__init__(*args, **kwargs)
        
        # Initial configuration
        self.fields['duree_campagne'].initial = 30
        self.fields['type_financement'].initial = 'don'
        self.fields['cover_image'].help_text = "Presentation image (recommended format: 1200x600px)"
        
        # Manage association field
        if self.porteur and hasattr(self.porteur, 'association_profile'):
            # If user is an association, pre-fill and hide the field
            self.fields['association'].initial = self.porteur.association_profile
            self.fields['association'].widget = forms.HiddenInput()
        else:
            # If user is not an association, hide the field
            self.fields['association'].widget = forms.HiddenInput()
            self.fields['association'].required = False
        
        # If modification and rewards exist
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
        
        # Rewards validation
        if offre_recompenses and not description_recompenses:
            self.add_error('description_recompenses', "Please describe the rewards you are offering.")
        
        # Category validation
        if categorie == 'autre' and not autre_categorie:
            self.add_error('autre_categorie', "Please specify your project category.")
        
        if categorie != 'autre' and autre_categorie:
            self.add_error('autre_categorie', "This field should only be filled if you select 'Other domain'.")
        
        # Funding type vs rewards validation
        if offre_recompenses and type_financement not in ['don', 'recompense', 'mixte']:
            self.add_error('offre_recompenses', "Rewards are only available for donations, rewards, or mixed funding.")
        
        # Association validation
        if association and self.porteur:
            # Verify user has the right to associate this project with this association
            if hasattr(self.porteur, 'association_profile') and self.porteur.association_profile != association:
                self.add_error('association', "You cannot associate this project with this association.")
        
        return cleaned_data
    
    def clean_description_courte(self):
        """Validation for short description"""
        description_courte = self.cleaned_data.get('description_courte', '')
        description_courte = description_courte.strip()
        
        if len(description_courte) < 10:
            raise ValidationError("The summary must contain at least 10 characters.")
        
        if len(description_courte) > 300:
            raise ValidationError("The summary cannot exceed 300 characters.")
        
        return description_courte
    
    def clean_montant_demande(self):
        """Validation for requested amount"""
        montant = self.cleaned_data.get('montant_demande')
        if montant and montant < 5:
            raise ValidationError("The requested amount must be at least 10 FCFA.")
        return montant
    
    def save(self, commit=True):
        projet = super().save(commit=False)

        if self.porteur:
            projet.porteur = self.porteur

        # Rewards management
        offre_recompenses = self.cleaned_data.get('offre_recompenses', False)
        description_recompenses = self.cleaned_data.get('description_recompenses', '')

        projet.has_recompenses = offre_recompenses
        projet.recompenses_description = description_recompenses if offre_recompenses else None

        # Default minimum amount at 50%
        if not projet.montant_minimal and projet.montant_demande:
            projet.montant_minimal = Decimal(projet.montant_demande) * Decimal('0.5')

        if commit:
            projet.save()
            self.save_m2m()     
        return projet


class PalierForm(forms.ModelForm):
    class Meta:
        model = Palier
        fields = ['titre', 'description', 'montant']
        widgets = {
            'titre': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'montant': forms.NumberInput(attrs={'class': 'form-control'}),
        }

from django.forms import modelformset_factory

PalierFormSet = modelformset_factory(
    Palier,
    form=PalierForm,
    extra=3,
    can_delete=True,
    min_num=1,  # Au moins 1 palier
    validate_min=True
)

class AjoutImagesProjetForm(forms.Form):
    """Formulaire dédié à l'ajout d'images secondaires"""
    
    images = MultipleFileField(
        required=True,
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/jpeg,image/png,image/webp',
            'multiple': 'multiple'
        }),
        label="Images supplémentaires",
        help_text="Sélectionnez une ou plusieurs images (max 10, 5MB par image)"
    )
    
    def __init__(self, *args, **kwargs):
        self.projet = kwargs.pop('projet', None)
        super().__init__(*args, **kwargs)
    
    def clean_images(self):
        """Validation pour les images"""
        images = self.cleaned_data.get('images', [])
        
        # Si images est None, retourner une liste vide
        if images is None:
            return []
        
        # Vérifier que c'est une liste
        if not isinstance(images, list):
            images = [images] if images else []

        # Limite à 10 images
        if len(images) > 10:
            raise ValidationError("Vous ne pouvez pas uploader plus de 10 images.")
        
        # Vérifier le nombre total d'images (existant + nouvelles)
        if self.projet:
            images_existantes = self.projet.images.count()
            if images_existantes + len(images) > 10:
                raise ValidationError(
                    f"Vous avez déjà {images_existantes} images. "
                    f"Vous ne pouvez ajouter que {10 - images_existantes} image(s) supplémentaire(s)."
                )

        for image in images:
            if image:  # Vérifier que l'image n'est pas None
                # Vérifier le type MIME
                if image.content_type not in ['image/jpeg', 'image/png', 'image/webp']:
                    raise ValidationError(f"Format non supporté: {image.name}. Utilisez JPEG, PNG ou WebP.")

                # Vérifier la taille (5MB max par image)
                if image.size > 5 * 1024 * 1024:
                    raise ValidationError(f"L'image {image.name} est trop lourde (max 5MB).")

        return images
    
    def save(self):
        """Sauvegarde les images dans le projet"""
        if not self.projet:
            raise ValueError("Un projet doit être spécifié")
        
        images = self.cleaned_data.get('images', [])
        ordre_depart = self.projet.images.count() + 1
        
        images_crees = []
        for i, image_file in enumerate(images):
            if image_file:
                image_projet = ImageProjet.objects.create(
                    projet=self.projet,
                    image=image_file,
                    ordre=ordre_depart + i
                )
                images_crees.append(image_projet)
        
        return images_crees




class PreuveForm(forms.Form):
    """
    Form for submitting proof files for a project milestone.

    Fields:
        fichiers (FileField): One or more proof files to be uploaded. Acceptable file types include images, PDFs, videos, and documents.
            - Widget: MultiFileInput
            - Help text: "Select one or more files (max 10 files, 50 MB in total)"
            - Required: Yes
        description (CharField): Optional text field to describe the submitted proofs.
            - Widget: Textarea with 3 rows
            - Help text: "Optional: explain how these proofs demonstrate milestone completion"
            - Required: No

    Validation:
        - clean_fichiers(): Returns the uploaded files; additional validation (like size/count limits) can be added here if needed.
    """
    """Formulaire pour soumettre des preuves pour un palier"""

    fichiers = forms.FileField(
        label="Proof Files",
        widget=MultiFileInput(attrs={
            'accept': '.jpg,.jpeg,.png,.pdf,.mp4,.avi,.mov,.doc,.docx,.xls,.xlsx,.txt',
            'class': 'form-control'
        }),
        help_text="Select one or more files (max 10 files, 50 MB total)",
        required=True
    )

    description = forms.CharField(
        label="Proof Description",
        widget=forms.Textarea(attrs={
            'rows': 3,
            'placeholder': 'Briefly describe the submitted proofs...',
            'class': 'form-control'
        }),
        required=False,
        help_text="Optional: explain how these proofs demonstrate milestone completion"
    )

    def clean_fichiers(self):
        return self.cleaned_data.get('fichiers')
    



class VerificationPreuveForm(forms.Form):
    """
    Form for verifying submitted proof files (admin use only).

    Fields:
        action (ChoiceField): Action to take on the submitted proofs. Choices include:
            - 'approuver': Approve the proofs
            - 'rejeter': Reject the proofs
            - 'modification': Request modifications
            - Widget: RadioSelect
        commentaires (CharField): Optional comments explaining the decision.
            - Widget: Textarea with 4 rows
            - Help text: "Comments will be visible to the project owner"
            - Required if action is 'rejeter' or 'modification'

    Validation:
        - clean(): Ensures that comments are provided when rejecting or requesting modifications.
    """
    """Formulaire pour vérifier les preuves (admin)"""
    
    ACTION_CHOICES = [
        ('approuver', 'Approve proofs'),
        ('rejeter', 'Reject proofs'),
        ('modification', 'Request modifications'),
    ]
    
    action = forms.ChoiceField(
        label="Action",
        choices=ACTION_CHOICES,
        widget=forms.RadioSelect
    )
    
    commentaires = forms.CharField(
        label="Commentaires",
        widget=forms.Textarea(attrs={
            'rows': 4,
            'placeholder': 'Explain your decision...'
        }),
        required=False,
        help_text="Comments will be visible to the project owner"
    )
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        commentaires = cleaned_data.get('commentaires', '')
        
        if action in ['rejeter', 'modification'] and not commentaires.strip():
            raise forms.ValidationError(
                "Comments are required when rejecting or requesting modifications."
            )
        
        return cleaned_data