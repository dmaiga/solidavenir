from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Projet, Transaction, AuditLog,Association
from django.utils import timezone

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'user_type', 'date_joined', 'is_active')
    list_filter = ('user_type', 'is_active', 'is_staff')
    fieldsets = UserAdmin.fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('user_type', 'hedera_account_id', 'telephone', 'adresse', 
                      'date_naissance', 'organisation', 'site_web', 
                      'departement', 'role_admin')
        }),
    )
    actions = ['make_administrator', 'make_porteur', 'make_donateur']
    
    def make_administrator(self, request, queryset):
        queryset.update(user_type='admin')
    make_administrator.short_description = "Définir comme administrateur"
    
    def make_porteur(self, request, queryset):
        queryset.update(user_type='porteur')
    make_porteur.short_description = "Définir comme porteur de projet"
    
    def make_donateur(self, request, queryset):
        queryset.update(user_type='donateur')
    make_donateur.short_description = "Définir comme donateur"

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('utilisateur', 'action', 'modele', 'date_action')
    list_filter = ('action', 'modele', 'date_action')
    search_fields = ('utilisateur__username', 'objet_id')
    readonly_fields = ('audit_uuid', 'utilisateur', 'action', 'modele', 'objet_id', 'details', 'date_action', 'adresse_ip')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
from django.contrib import admin
from .models import Association, AssociationImage
@admin.register(Association)
class AssociationAdmin(admin.ModelAdmin):
    list_display = ['nom', 'user', 'domaine_principal', 'ville']
    list_filter = ['domaine_principal', 'ville', 'statut_juridique']
    search_fields = ['nom', 'user__username', 'user__email', 'ville']

    fieldsets = (
        ('Informations générales', {
            'fields': ('user', 'nom', 'slug', 'slogan', 'description_courte', 'description_longue')
        }),
        ('Logo et images', {
            'fields': ('logo', 'cover_image')
        }),
        ('Domaines d\'action', {
            'fields': ('domaine_principal', 'domaines_secondaires', 'causes_defendues')
        }),
        ('Informations juridiques', {
            'fields': ('statut_juridique', 'date_creation_association')
        }),
        ('Contact et localisation', {
            'fields': ('adresse_siege', 'ville', 'code_postal', 'pays', 'telephone', 'email_contact', 'site_web')
        }),
        ('Réseaux sociaux', {
            'fields': ('facebook', 'twitter', 'linkedin', 'instagram', 'youtube')
        }),
        ('Chiffres clés', {
            'fields': ('nombre_adherents', 'nombre_beneficiaires')
        }),
        ('Transparence', {
            'fields': (  'transparent_finances', 'transparent_actions')
        }),
        ('Projets et actions', {
            'fields': ('projets_phares', 'actions_en_cours', 'partenariats')
        }),
    )


@admin.register(AssociationImage)
class AssociationImageAdmin(admin.ModelAdmin):
    list_display = ['association', 'legende', 'date_ajout', 'ordre']
    list_filter = ['association']
    search_fields = ['association__nom', 'legende']
    ordering = ['association', 'ordre']

from django.contrib import admin
from .models import ContactSubmission

@admin.register(ContactSubmission)
class ContactSubmissionAdmin(admin.ModelAdmin):

    list_display = ('sujet', 'email', 'date_soumission', 'traite')
    list_filter = ('traite', 'date_soumission')
    search_fields = ('sujet', 'email', 'message')
    readonly_fields = ('sujet', 'email', 'message', 'date_soumission')
    
    def has_add_permission(self, request):
        return False  # Empêcher l'ajout manuel depuis l'admin
    

from django.contrib import admin
from django.utils.html import format_html
from .models import Projet, Palier

# Créer un inline pour les paliers
class PalierInline(admin.TabularInline):
    model = Palier
    extra = 0
    readonly_fields = ('montant_minimum', 'transfere', 'date_transfert', 'transaction_hash')
    fields = ('pourcentage', 'montant', 'montant_minimum', 'transfere', 'date_transfert', 'transaction_hash')
    
    def has_add_permission(self, request, obj=None):
        # Permettre d'ajouter des paliers seulement à la création
        return obj is None

@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ('titre', 'porteur','montant_collecte', 'montant_demande', 'montant_engage', 'montant_distribue', 'statut', 'date_creation', 'paliers_status')
    list_filter = ('statut', 'date_creation', 'categorie')
    search_fields = ('titre', 'porteur__username', 'description')
    readonly_fields = ('audit_uuid', 'topic_id', 'date_creation', 'date_mise_a_jour', 'montant_engage', 'montant_distribue', 'paliers_summary')
    inlines = [PalierInline]  # ← Ajouter les paliers en inline
    actions = ['validate_projects', 'reject_projects', 'creer_paliers_auto']
    
    # Champs à afficher dans le détail
    fieldsets = (
        ('Informations générales', {
            'fields': ('titre', 'description', 'porteur', 'association', 'statut')
        }),
        ('Financement', {
            'fields': ('montant_demande', 'montant_minimal','montant_collecte', 'montant_engage', 'montant_distribue', 'commission')
        }),
        ('Détails techniques', {
            'fields': ('audit_uuid', 'topic_id', 'hedera_account_id', 'paliers_summary'),
            'classes': ('collapse',)
        }),
        ('Dates', {
            'fields': ('date_creation', 'date_mise_a_jour', 'date_debut', 'date_fin'),
            'classes': ('collapse',)
        }),
    )
    
    def paliers_status(self, obj):
        """Affiche le statut des paliers dans la liste"""
        total = obj.paliers.count()
        transferes = obj.paliers.filter(transfere=True).count()
        
        if total == 0:
            return format_html('<span class="badge bg-secondary">Aucun palier</span>')
        elif transferes == total:
            return format_html('<span class="badge bg-success">✓ Tous distribués</span>')
        elif transferes > 0:
            return format_html('<span class="badge bg-warning">{}/{} distribués</span>', transferes, total)
        else:
            return format_html('<span class="badge bg-info">{} paliers</span>', total)
    paliers_status.short_description = "Paliers"
    
    def paliers_summary(self, obj):
        """Résumé des paliers dans le détail"""
        paliers = obj.paliers.all()
        if not paliers.exists():
            return "Aucun palier configuré"
        
        html = '<div class="paliers-summary">'
        for palier in paliers:
            status = "✓ Distribué" if palier.transfere else "⏳ En attente"
            css_class = "text-success" if palier.transfere else "text-warning"
            html += f'''
            <div class="border p-2 mb-2">
                <strong>Palier {palier.pourcentage}%</strong> - {palier.montant} HBAR
                <br><span class="{css_class}">{status}</span>
                {f"<br>Distribué le: {palier.date_transfert}" if palier.transfere else ""}
            </div>
            '''
        html += '</div>'
        return format_html(html)
    paliers_summary.short_description = "Résumé des paliers"
    
    def creer_paliers_auto(self, request, queryset):
        """Action pour créer automatiquement les paliers"""
        from .utils import creer_paliers  # Import local pour éviter circularité
        
        for projet in queryset:
            creer_paliers(projet)
            self.message_user(request, f"Paliers créés pour {projet.titre}")
    creer_paliers_auto.short_description = "Créer les paliers automatiquement"
    
    def validate_projects(self, request, queryset):
        for projet in queryset:
            projet.statut = 'actif'
            projet.valide_par = request.user
            projet.date_validation = timezone.now()
            
            # Créer automatiquement les paliers si nécessaire
            if not projet.paliers.exists():
                from .utils import creer_paliers
                creer_paliers(projet)
            
            projet.save()
        self.message_user(request, "Projets validés avec succès")
    validate_projects.short_description = "Valider les projets sélectionnés"
    
    def reject_projects(self, request, queryset):
        queryset.update(statut='rejete')
        self.message_user(request, "Projets rejetés avec succès")
    reject_projects.short_description = "Rejeter les projets sélectionnés"
    
    # Ajouter du CSS pour l'admin
    class Media:
        css = {
            'all': ('css/admin_paliers.css',)
        }


@admin.register(Palier)
class PalierAdmin(admin.ModelAdmin):
    list_display = ('projet', 'pourcentage', 'montant', 'montant_minimum', 'transfere', 'date_transfert')
    list_filter = ('transfere', 'projet__statut')
    search_fields = ('projet__titre',)
    readonly_fields = ('montant_minimum', 'date_transfert', 'transaction_hash')
    
    def has_add_permission(self, request):
        # Les paliers sont créés automatiquement, pas manuellement
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Empêcher la suppression des paliers
        return False
from django.contrib import admin
from .models import Transaction, TransactionAdmin

# Admin pour Transaction « classique »
@admin.register(Transaction)
class TransactionAdminModel(admin.ModelAdmin):
    list_display = ('montant', 'contributeur_anonymise', 'projet', 'statut', 'date_transaction')
    list_filter = ('statut', 'date_transaction')
    search_fields = ('hedera_transaction_hash', 'projet__titre')
    readonly_fields = ('audit_uuid', 'date_transaction', 'hedera_transaction_hash')
    actions = ['verify_transactions', 'mark_as_refunded']
    
    def verify_transactions(self, request, queryset):
        for transaction in queryset:
            transaction.statut = 'confirme'
            transaction.verifie_par = request.user
            transaction.date_verification = timezone.now()
            transaction.save()
    verify_transactions.short_description = "Marquer comme vérifiées"
    
    def mark_as_refunded(self, request, queryset):
        queryset.update(statut='rembourse')
    mark_as_refunded.short_description = "Marquer comme remboursées"

# Admin pour TransactionAdmin (suivi financier admin)
@admin.register(TransactionAdmin)
class TransactionAdminFinancial(admin.ModelAdmin):
    list_display = (
        'id', 'projet', 'palier', 'beneficiaire', 'initiateur',
        'montant_brut', 'montant_net', 'commission', 'commission_pourcentage',
        'transaction_hash', 'type_transaction', 'date_creation'
    )
    list_filter = ('type_transaction', 'date_creation', 'projet')
    search_fields = ('transaction_hash', 'beneficiaire__username', 'projet__titre')
    readonly_fields = ('transaction_hash', 'date_creation')
