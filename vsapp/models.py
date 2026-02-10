from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import uuid

# ==================== USER MODELS ====================

class User(AbstractUser):
    """Extended user model for both voters and admins"""
    USER_TYPES = (
        ('voter', 'Voter'),
        ('admin', 'Administrator'),
    )
    
    user_type = models.CharField(max_length=10, choices=USER_TYPES, default='voter')
    matric_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=15, blank=True)
    has_voted = models.BooleanField(default=False)
    otp_code = models.CharField(max_length=6, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.matric_number})"


# ==================== ELECTION MODELS ====================

class Election(models.Model):
    """Main election model"""
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('active', 'Active'),
        ('closed', 'Closed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='draft')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='elections_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['end_date']),
        ]
    
    def __str__(self):
        return self.title
    
    @property
    def is_active(self):
        now = timezone.now()
        return self.status == 'active' and self.start_date <= now <= self.end_date
    
    @property
    def total_votes(self):
        return Vote.objects.filter(candidate__position__election=self).count()
    
    @property
    def voter_turnout(self):
        total_voters = User.objects.filter(user_type='voter', is_active=True).count()
        if total_voters == 0:
            return 0
        return (self.total_votes / total_voters) * 100


class Position(models.Model):
    """Positions available in an election (President, VP, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='positions')
    title = models.CharField(max_length=100)  # e.g., "President", "Vice President"
    description = models.TextField(blank=True)
    order = models.IntegerField(default=0)  # Display order
    max_votes = models.IntegerField(default=1)  # Usually 1 vote per position
    
    class Meta:
        ordering = ['order', 'title']
        unique_together = ['election', 'title']
    
    def __str__(self):
        return f"{self.title} - {self.election.title}"


class Candidate(models.Model):
    """Candidates running for positions"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='candidates')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidacies')
    full_name = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    level = models.CharField(max_length=20)
    manifesto = models.TextField()
    photo = models.ImageField(upload_to='candidates/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['full_name']
        unique_together = ['position', 'user']
    
    def __str__(self):
        return f"{self.full_name} - {self.position.title}"
    
    @property
    def vote_count(self):
        return self.votes.count()
    
    @property
    def vote_percentage(self):
        total_votes = self.position.candidates.aggregate(
            total=models.Count('votes')
        )['total'] or 0

        if total_votes == 0:
            return 0
        return (self.vote_count / total_votes) * 100




# ==================== VOTING MODELS ====================

class Vote(models.Model):
    """Individual vote records (encrypted/anonymized)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='votes')
    vote_hash = models.CharField(max_length=256, unique=True)  # Blockchain hash
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    
    # NOTE: Do NOT store voter identity with vote for anonymity
    # Use separate VoterRecord model to track who has voted
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['candidate', 'timestamp']),
            models.Index(fields=['vote_hash']),
        ]
    
    def __str__(self):
        return f"Vote for {self.candidate.full_name} at {self.timestamp}"


class VoterRecord(models.Model):
    """Tracks which voters have participated (separate from actual votes)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voter_records')
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='voter_records')
    voted_at = models.DateTimeField(auto_now_add=True)
    verification_code = models.CharField(max_length=20, unique=True)  # For voter to verify their vote was counted
    
    class Meta:
        unique_together = ['voter', 'election']
        ordering = ['-voted_at']
    
    def __str__(self):
        return f"{self.voter.matric_number} voted in {self.election.title}"


# ==================== AUDIT & SECURITY ====================

class AuditLog(models.Model):
    """System audit trail for all administrative actions"""
    ACTION_TYPES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('vote', 'Vote Cast'),
        ('election_start', 'Election Started'),
        ('election_close', 'Election Closed'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Optional: Store affected object details
    content_type = models.CharField(max_length=50, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action_type} by {self.user} at {self.timestamp}"


class SystemSetting(models.Model):
    """System configuration and settings"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    def __str__(self):
        return self.key
