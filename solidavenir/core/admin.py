from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Projet, Transaction, AuditLog
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

@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ('titre', 'porteur', 'montant_demande', 'montant_collecte', 'statut', 'date_creation')
    list_filter = ('statut', 'date_creation')
    search_fields = ('titre', 'porteur__username', 'description')
    readonly_fields = ('audit_uuid', 'date_creation', 'date_mise_a_jour')
    actions = ['validate_projects', 'reject_projects']
    
    def validate_projects(self, request, queryset):
        for projet in queryset:
            projet.statut = 'actif'
            projet.valide_par = request.user
            projet.date_validation = timezone.now()
            projet.save()
    validate_projects.short_description = "Valider les projets sélectionnés"
    
    def reject_projects(self, request, queryset):
        queryset.update(statut='rejete')
    reject_projects.short_description = "Rejeter les projets sélectionnés"

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('montant', 'donateur_anonymise', 'projet', 'statut', 'date_transaction')
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