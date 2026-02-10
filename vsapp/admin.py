from django.contrib import admin
from .models import *

@admin.register(User)
class User(admin.ModelAdmin):
    list_display = ['matric_number', 'user_type', 'department', 'level', 'has_voted']
    list_filter = ['user_type', 'department', 'level', 'has_voted']
    search_fields = ['user_type', 'matric_number', 'first_name', 'last_name', 'username']
    readonly_fields = ['last_login', 'date_joined']

@admin.register(Election)
class ElectionAdmin(admin.ModelAdmin):
    list_display = ['title', 'status', 'start_date', 'end_date', 'voter_turnout']
    list_filter = ['status', 'start_date']
    search_fields = ['title', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'position', 'department', 'vote_count']
    list_filter = ['position__election', 'department']
    search_fields = ['full_name', 'manifesto']

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['id', 'candidate', 'timestamp']
    readonly_fields = ['id', 'vote_hash', 'timestamp']
    
    def has_add_permission(self, request):
        return False  # Votes should only be created through voting interface
    
    def has_change_permission(self, request, obj=None):
        return False  # Votes are immutable

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'user', 'description', 'timestamp']
    list_filter = ['action_type', 'timestamp']
    readonly_fields = ['id', 'user', 'action_type', 'description', 'timestamp']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(Position)
admin.site.register(VoterRecord)
admin.site.register(SystemSetting)
