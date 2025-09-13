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

class InscriptionForm(UserCreationForm):
    user_type = forms.ChoiceField(
        choices=User.USER_TYPES, 
        label="Type d'utilisateur",
        widget=forms.Select(attrs={
            'class': 'form-control', 
            'onchange': "showRelevantFields()",
            'id': 'user_type_select'
        })
    )
    
    # Informations de base pour tous les utilisateurs
    email = forms.EmailField(required=True, label="Email")
    first_name = forms.CharField(max_length=30, required=False, label="Prénom")
    last_name = forms.CharField(max_length=30, required=False, label="Nom")
    telephone = forms.CharField(max_length=20, required=False, label="Téléphone")
    adresse = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}), 
        required=False, 
        label="Adresse"
    )
    date_naissance = forms.DateField(
        required=False, 
        label="Date de naissance",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    # Champs pour porteurs de projet - Tous optionnels
    organisation = forms.CharField(
        max_length=100, 
        required=False, 
        label="Structure",
        help_text="Entreprise, startup, association, ou nom de votre projet",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Facultatif'})
    )
    site_web = forms.URLField(
        required=False, 
        label="Site web",
        widget=forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://...'})
    )
    description_projet = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=False, 
        label="Description du projet",
        help_text="Quelques mots sur votre projet"
    )
    montant_recherche = forms.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False, 
        label="Budget estimé (€)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Facultatif'})
    )
    type_financement = forms.ChoiceField(
        choices=[('', '---------')] + list(User.FINANCEMENT_CHOICES), 
        required=False, 
        label="Type de financement",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # Champs pour associations - Tous optionnels
    nom_association = forms.CharField(
        max_length=200, 
        required=False, 
        label="Nom de l'association",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Facultatif'})
    )
    causes_defendues = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=False, 
        label="Causes défendues",
        help_text="Les causes que vous soutenez"
    )
    domaine_action = forms.CharField(
        max_length=100, 
        required=False, 
        label="Domaine d'action",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Facultatif'})
    )
    
    # Champs pour investisseurs - Tous optionnels
    type_investisseur = forms.ChoiceField(
        choices=[('', '---------')] + [
            ('particulier', 'Particulier'),
            ('institutionnel', 'Institutionnel'),
            ('business_angel', 'Business Angel'),
            ('fond_investissement', 'Fonds d\'investissement'),
            ('autre', 'Autre')
        ],
        required=False, 
        label="Type d'investisseur",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    secteur_prefere = forms.CharField(
        max_length=100, 
        required=False, 
        label="Secteur d'intérêt",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Facultatif'})
    )
    montant_investissement_min = forms.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False, 
        label="Investissement min (€)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Facultatif'})
    )
    montant_investissement_max = forms.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False, 
        label="Investissement max (€)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Facultatif'})
    )
    
    # Champs pour donateurs - Tous optionnels
    causes_soutenues = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        required=False, 
        label="Causes soutenues",
        help_text="Les causes que vous souhaitez soutenir"
    )
    montant_don_moyen = forms.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        required=False, 
        label="Don moyen (€)",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': 'Facultatif'})
    )
    frequence_dons = forms.ChoiceField(
        choices=[('', '---------')] + [
            ('ponctuel', 'Ponctuel'),
            ('mensuel', 'Mensuel'),
            ('trimestriel', 'Trimestriel'),
            ('annuel', 'Annuel')
        ],
        required=False, 
        label="Fréquence des dons",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    consentement_rgpd = forms.BooleanField(
        required=False, 
        label="J'accepte la politique de confidentialité",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'email', 'password1', 'password2', 'user_type',
            'first_name', 'last_name', 'telephone', 'adresse', 'date_naissance',
            'organisation', 'site_web', 'description_projet', 'montant_recherche', 'type_financement',
            'nom_association', 'causes_defendues', 'domaine_action',
            'type_investisseur', 'secteur_prefere', 'montant_investissement_min', 'montant_investissement_max',
            'causes_soutenues', 'montant_don_moyen', 'frequence_dons',
            'consentement_rgpd'
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Choisissez un nom d\'utilisateur'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'votre@email.com'}),
            'password1': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Mot de passe'}),
            'password2': forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirmation du mot de passe'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Personnalisation des labels
        self.fields['password2'].label = "Confirmation du mot de passe"
        
        # Rendre tous les champs optionnels sauf les essentiels
        for field_name, field in self.fields.items():
            if field_name not in ['username', 'email', 'password1', 'password2', 'user_type', 'consentement_rgpd']:
                field.required = False
            if 'class' not in field.widget.attrs and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("Cet email est déjà utilisé.")
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user_type = self.cleaned_data.get('user_type')
        
        # Assigner les champs de base
        user.email = self.cleaned_data.get('email')
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.telephone = self.cleaned_data.get('telephone', '')
        user.adresse = self.cleaned_data.get('adresse', '')
        user.date_naissance = self.cleaned_data.get('date_naissance')
        user.consentement_rgpd = self.cleaned_data.get('consentement_rgpd', False)
        
        if user.consentement_rgpd:
            user.date_consentement = timezone.now()
        
        # Assigner les champs spécifiques selon le type d'utilisateur
        # Tous les champs sont optionnels maintenant
        user.organisation = self.cleaned_data.get('organisation', '')
        user.site_web = self.cleaned_data.get('site_web', '')
        user.description_projet = self.cleaned_data.get('description_projet', '')
        user.montant_recherche = self.cleaned_data.get('montant_recherche')
        user.type_financement = self.cleaned_data.get('type_financement', '')
        
        user.nom_association = self.cleaned_data.get('nom_association', '')
        user.causes_defendues = self.cleaned_data.get('causes_defendues', '')
        user.domaine_action = self.cleaned_data.get('domaine_action', '')
        
        user.type_investisseur = self.cleaned_data.get('type_investisseur', '')
        user.secteur_prefere = self.cleaned_data.get('secteur_prefere', '')
        user.montant_investissement_min = self.cleaned_data.get('montant_investissement_min')
        user.montant_investissement_max = self.cleaned_data.get('montant_investissement_max')
        
        user.causes_soutenues = self.cleaned_data.get('causes_soutenues', '')
        user.montant_don_moyen = self.cleaned_data.get('montant_don_moyen')
        user.frequence_dons = self.cleaned_data.get('frequence_dons', '')

        
        
        if commit:
            user.save()

            # CRÉATION AUTOMATIQUE DU PROFIL ASSOCIATION SI BESOIN
            if user_type == 'association':
                from .models import Association
                # Éviter les doublons
                if not hasattr(user, 'association_profile'):
                    Association.objects.create(
                        user=user,
                        nom=self.cleaned_data.get('nom_association') or f"Association {user.username}",
                        domaine_principal='autre',
                        causes_defendues=self.cleaned_data.get('causes_defendues') or "Causes à définir",
                        statut_juridique='association', 
                        adresse_siege=self.cleaned_data.get('adresse') or "Adresse à compléter",
                        ville=user.ville or "Bamako", 
                        code_postal=user.code_postal or "00000",
                        telephone=user.telephone or "0000000000",
                        email_contact=user.email,
                        date_creation=timezone.now().date()
                    )

        return user
    



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
from django import forms
from .models import User
from django.core.validators import FileExtensionValidator

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
    

# forms.py
import random
from django import forms
from django.core.exceptions import ValidationError
import random
from django import forms
from django.core.exceptions import ValidationError

class ContactForm(forms.Form):
    # Formulaire de contact générique
    sujet = forms.CharField(
        max_length=100, 
        label="Sujet",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Ex: Problème avec un don'
        })
    )
    
    email = forms.EmailField(
        label="Votre email",
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'votre@email.com'
        })
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control',
            'placeholder': 'Décrivez votre demande en détail...'
        }), 
        label="Message"
    )
    
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
            raise ValidationError("Le sujet doit contenir au moins 5 caractères.")
        return sujet
    
    def clean_captcha_answer(self):
        answer = self.cleaned_data.get('captcha_answer')
        question_data = self.cleaned_data.get('captcha_question', '')
        
        if not question_data:
            raise ValidationError("Erreur de validation du CAPTCHA.")
        
        question, expected_answer = question_data.split('|')
        
        try:
            user_answer = int(answer.strip())
        except (ValueError, TypeError):
            raise ValidationError("Veuillez entrer un nombre valide.")
        
        if user_answer != int(expected_answer):
            raise ValidationError(f"Réponse incorrecte. La réponse attendue était {expected_answer}.")
        
        return answer
    

    

class FiltreMembresForm(forms.Form):
    TYPE_CHOICES = [
        ('', 'Tous les types'),
        ('porteur', 'Porteurs'),
        ('donateur', 'Donateurs'),
        ('admin', 'Administrateurs'),
    ]
    
    type_utilisateur = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        label='Type d\'utilisateur'
    )
    date_debut = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date d\'inscription (début)'
    )
    date_fin = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label='Date d\'inscription (fin)'
    )
    recherche = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nom, email, username...'}),
        label='Recherche'
    )
    actif = forms.ChoiceField(
        choices=[('', 'Tous'), ('1', 'Actifs'), ('0', 'Inactifs')],
        required=False,
        label='Statut'
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

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import Projet
from django import forms
from django.core.exceptions import ValidationError
from django_summernote.widgets import SummernoteWidget
from decimal import Decimal
from .models import Projet
class CreationProjetForm(forms.ModelForm):
    """Formulaire de création de projet avec validation personnalisée."""

    description = forms.CharField(
        widget=SummernoteWidget(attrs={'summernote': {'width': '100%', 'height': '300px'}})
    )

    description_courte = forms.CharField(
        max_length=300,
        required=True,
        widget=forms.Textarea(attrs={'rows': 3, 'maxlength': '300'}),
        label="Description courte",
        help_text="Résumé en 300 caractères maximum."
    )

    budget_detaille = forms.FileField(
        required=False,
        label="Budget détaillé",
        help_text="Document détaillant le budget (PDF, DOC, JPG, PNG)",
        widget=forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.jpg,.png'})
    )

    montant_demande = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        label="Montant demandé (FCFA)",
        help_text="Indiquez le montant total nécessaire en FCFA",
        widget=forms.NumberInput(attrs={'placeholder': '500000'})
    )

    montant_minimal = forms.DecimalField(
        max_digits=15,
        decimal_places=0,
        required=False,
        label="Montant minimal (FCFA)",
        help_text="Montant minimum à atteindre pour valider le projet",
        widget=forms.NumberInput(attrs={'placeholder': '250000'})
    )
    
    class Meta:
        model = Projet
        fields = [
            'titre', 'description_courte', 'description', 'categorie', 'autre_categorie', 'tags',
            'type_financement', 'montant_demande', 'montant_minimal',
            'cover_image', 'video_presentation', 'duree_campagne',
            'document_justificatif', 'plan_financement', 'budget_detaille', 'has_recompenses'
        ]
        widgets = {
            'duree_campagne': forms.NumberInput(attrs={'min': 1, 'max': 90}),
            'tags': forms.TextInput(attrs={'placeholder': 'tag1, tag2, tag3...'}),
            'autre_categorie': forms.TextInput(attrs={
                'placeholder': 'Précisez votre catégorie...',
                'style': 'display: none;'  # Caché par défaut
            }),
        }

    def __init__(self, *args, **kwargs):
        self.porteur = kwargs.pop('porteur', None)
        super().__init__(*args, **kwargs)

        # Valeur par défaut
        self.fields['type_financement'].initial = 'don'
        self.fields['cover_image'].help_text = "Image principale du projet (format recommandé: 1200x600px)"
        self.fields['video_presentation'].help_text = "Lien YouTube ou Vimeo (optionnel)"
        self.fields['has_recompenses'].label = "Proposer des récompenses/niveaux de financement ?"
        
        # Ajuster l'affichage en fonction de la catégorie sélectionnée
        if self.instance and self.instance.categorie == 'autre':
            self.fields['autre_categorie'].widget.attrs['style'] = 'display: block;'
    
    def clean(self):
        cleaned_data = super().clean()
        has_recompenses = cleaned_data.get('has_recompenses')
        type_financement = cleaned_data.get('type_financement')
        categorie = cleaned_data.get('categorie')
        autre_categorie = cleaned_data.get('autre_categorie')
        
        # Validation: récompenses seulement pour certains types de financement
        if has_recompenses and type_financement not in ['don', 'recompense', 'mixte']:
            raise ValidationError("Les récompenses ne sont disponibles que pour les types de financement: Don, Récompense ou Mixte.")
        
        # Validation: si catégorie est "autre", autre_categorie est requis
        if categorie == 'autre' and not autre_categorie:
            raise ValidationError({
                'autre_categorie': "Veuillez préciser la catégorie de votre projet."
            })
        
        # Validation: si catégorie n'est pas "autre", autre_categorie doit être empty
        if categorie != 'autre' and autre_categorie:
            raise ValidationError({
                'autre_categorie': "Ce champ ne doit être rempli que si vous sélectionnez 'Autre domaine'."
            })
        
        return cleaned_data
    
    def clean_montant_minimal(self):
        """Validation : le montant minimal doit être inférieur ou égal au montant demandé."""
        montant_minimal = self.cleaned_data.get('montant_minimal')
        montant_demande = self.cleaned_data.get('montant_demande')

        if montant_minimal and montant_demande:
            if montant_minimal > montant_demande:
                raise ValidationError("Le montant minimal ne peut pas dépasser le montant demandé.")

        return montant_minimal

    def clean_description_courte(self):
        """Validation pour la description courte"""
        description_courte = self.cleaned_data.get('description_courte', '')
        # Nettoyer le texte des balises HTML si jamais il y en a
        from django.utils.html import strip_tags
        cleaned_description = strip_tags(description_courte).strip()
        
        if len(cleaned_description) < 10:
            raise ValidationError("La description courte doit contenir au moins 10 caractères.")
        
        if len(cleaned_description) > 300:
            raise ValidationError("La description courte ne peut pas dépasser 300 caractères.")
        
        return cleaned_description

    def save(self, commit=True):
        projet = super().save(commit=False)

        if self.porteur:
            projet.porteur = self.porteur

        # Auto-définir le montant minimal à 50% si non fourni
        if not projet.montant_minimal and projet.montant_demande:
            projet.montant_minimal = Decimal(projet.montant_demande) * Decimal('0.5')

        if commit:
            projet.save()

        return projet
    
from .models import Association
class AssociationForm(forms.ModelForm):
    """Formulaire pour la modification du profil association"""
    
    class Meta:
        model = Association
        fields = [
            'nom', 'slogan', 'description_courte', 'description_longue',
            'logo', 'cover_image', 'domaine_principal', 'domaines_secondaires',
            'causes_defendues', 'statut_juridique', 'numero_agrement',
            'date_agrement', 'date_creation', 'numero_rc', 'numero_ifu',
            'adresse_siege', 'ville', 'commune', 'code_postal', 'pays',
            'telephone', 'email_contact', 'site_web',
            'facebook', 'twitter', 'linkedin', 'instagram', 'youtube',
            'nombre_adherents', 'nombre_beneficiaires', 'budget_annuel',
            'pourcentage_frais_gestion', 'agrement_file', 'statuts_file',
            'rapport_annuel', 'comptes_annuels', 'transparent_finances', 
            'transparent_actions', 'projets_phares', 'actions_en_cours', 
            'partenariats'
        ]
        widgets = {
            'description_courte': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'description_longue': forms.Textarea(attrs={'rows': 5, 'class': 'form-control'}),
            'causes_defendues': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'domaines_secondaires': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Séparés par des virgules'
            }),
            'date_creation': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'date_agrement': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'adresse_siege': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'projets_phares': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'actions_en_cours': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'partenariats': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre tous les champs optionnels
        for field_name, field in self.fields.items():
            field.required = False
            if 'class' not in field.widget.attrs and not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'
        
        # Personnalisation spécifique
        self.fields['logo'].widget.attrs['class'] = 'form-control'
        self.fields['cover_image'].widget.attrs['class'] = 'form-control'
        self.fields['agrement_file'].widget.attrs['class'] = 'form-control'
        self.fields['statuts_file'].widget.attrs['class'] = 'form-control'
        self.fields['rapport_annuel'].widget.attrs['class'] = 'form-control'
        self.fields['comptes_annuels'].widget.attrs['class'] = 'form-control'
        
        # Aide contextuelle pour le pourcentage de frais
        self.fields['pourcentage_frais_gestion'].help_text = """
        Pourcentage des ressources consacré aux frais de fonctionnement.
        • < 15% : Excellent • 15-25% : Bon • 25-35% : Acceptable • > 35% : Élevé
        """