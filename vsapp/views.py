from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password, check_password
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import transaction
from django.db.models import Q, Count, Prefetch
from django.http import JsonResponse
from .models import *
from functools import wraps
import hashlib
import secrets
import string

# Create your views here.

def index(request):
    """Landing page"""
    active_elections = Election.objects.filter(status='active')
    total_voters = User.objects.filter(user_type='voter', is_active=True).count()
    total_votes = Vote.objects.count()
    active_elections_count = active_elections.count()
    
    return render(request, 'index.html', {
        'active_elections': active_elections,
        'total_voters': total_voters,
        'total_votes': total_votes,
        'active_elections_count': active_elections_count
    })

def about(request):
    """About page"""
    return render(request, 'about.html')

def register_voter(request):
    """Voter registration"""
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        matric_number = request.POST.get('matric_number')
        department = request.POST.get('department')
        level = request.POST.get('level')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('register_voter')
        
        if User.objects.filter(matric_number=matric_number).exists():
            messages.error(request, 'Matric number already registered.')
            return redirect('register_voter')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('register_voter')
        
        try:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                matric_number=matric_number,
                department=department,
                level=level,
                phone=phone,
                user_type='voter'
            )
            messages.success(request, 'Registration successful! Please login to vote.')
            AuditLog.objects.create(
                user=user,
                action_type='create',
                description='Voter account created',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return redirect('login')
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
    
    return render(request, 'auth/register_voter.html')

@login_required
def register_admin(request):
    """Admin registration (only for admins)"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match.')
            return redirect('register_admin')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already taken.')
            return redirect('register_admin')
        
        try:
            user = User.objects.create_user(
                username=username,
                first_name=first_name,
                last_name=last_name,
                email=email,
                password=password,
                user_type='admin'
            )
            messages.success(request, 'Admin account created successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='create',
                description=f'Admin account created for {username}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return redirect('admin_dashboard')
        except Exception as e:
            messages.error(request, f'Registration failed: {str(e)}')
    
    return render(request, 'admin/register_admin.html')

def login_view(request):
    """Voter login"""
    if request.method == 'POST':
        matric_number = request.POST.get('matric_number')
        password = request.POST.get('password')
        
        try:
            user = User.objects.get(matric_number=matric_number)
            user = authenticate(request, username=user.username, password=password)
            if user:
                if user.user_type == 'voter':
                    # Generate OTP
                    otp = ''.join(secrets.choice(string.digits) for _ in range(6))
                    user.otp_code = make_password(otp)
                    user.otp_created_at = timezone.now()
                    user.save()
                    request.session['pending_otp_user_id'] = str(user.id)
                    request.session.pop('otp_verified', None)
                    messages.success(request, f'OTP sent to your registered email/phone: {otp}')
                    return redirect('otp_verify')
                else:
                    messages.error(request, 'Invalid credentials for voter login.')
            else:
                messages.error(request, 'Invalid credentials.')
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
    
    return render(request, 'auth/login.html')

def otp_verify(request):
    """OTP verification"""
    pending_user_id = request.session.get('pending_otp_user_id')
    if not pending_user_id:
        messages.error(request, 'Session expired. Please login again.')
        return redirect('login')

    try:
        pending_user = User.objects.get(id=pending_user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found. Please login again.')
        request.session.pop('pending_otp_user_id', None)
        return redirect('login')

    if request.method == 'POST':
        otp = request.POST.get('otp')
        if pending_user.otp_code and check_password(otp, pending_user.otp_code):
            # Check if OTP is not expired (5 minutes)
            if pending_user.otp_created_at and timezone.now() - pending_user.otp_created_at < timezone.timedelta(minutes=5):
                pending_user.otp_code = ''
                pending_user.save()
                login(request, pending_user)
                request.session.pop('pending_otp_user_id', None)
                request.session['otp_verified'] = True
                return redirect('vote')
            else:
                messages.error(request, 'OTP expired. Please login again.')
                request.session.pop('pending_otp_user_id', None)
                return redirect('login')
        else:
            messages.error(request, 'Invalid OTP.')
    
    return render(request, 'auth/otp_verify.html')


def otp_required(view_func):
    """Ensure OTP was verified in this session."""
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.session.get('otp_verified'):
            messages.error(request, 'Please verify OTP to continue.')
            return redirect('otp_verify')
        return view_func(request, *args, **kwargs)
    return _wrapped

@login_required
@otp_required
def vote_with_election(request, election_id):
    """Voting dashboard for specific election"""
    if request.user.user_type != 'voter':
        messages.error(request, 'Access denied.')
        return redirect('index')

    # Get the specific election
    try:
        election = Election.objects.get(id=election_id, status='active')
    except Election.DoesNotExist:
        messages.error(request, 'Election not found or not active.')
        return redirect('vote')

    # Check if user has already voted in this election
    existing_record = VoterRecord.objects.filter(voter=request.user, election=election).first()
    if existing_record:
        return redirect('already_voted', election_id=election.id)

    positions = election.positions.all().prefetch_related('candidates')

    # Prepare positions data for JSON serialization
    positions_data = []
    for position in positions:
        position_dict = {
            'id': position.id,
            'title': position.title,
            'description': position.description,
            'candidates': []
        }
        for candidate in position.candidates.all():
            candidate_dict = {
                'id': candidate.id,
                'full_name': candidate.full_name,
                'department': candidate.department,
                'level': candidate.level,
                'manifesto': candidate.manifesto,
                'photo_url': candidate.photo.url if candidate.photo else None
            }
            position_dict['candidates'].append(candidate_dict)
        positions_data.append(position_dict)

    if request.method == 'POST':
        now = timezone.now()
        if not (election.start_date <= now <= election.end_date and election.status == 'active'):
            messages.error(request, 'Voting is closed for this election.')
            return redirect('vote_with_election', election_id=election.id)

        # Process vote
        with transaction.atomic():
            selections_made = 0
            for position in positions:
                selected_ids = request.POST.getlist(f'position_{position.id}')
                if not selected_ids:
                    continue
                if position.max_votes and len(selected_ids) > position.max_votes:
                    messages.error(request, f"You can select up to {position.max_votes} candidate(s) for {position.title}.")
                    return redirect('vote_with_election', election_id=election.id)

                for candidate_id in selected_ids:
                    candidate = get_object_or_404(Candidate, id=candidate_id, position=position)
                    # Create vote hash (non-reversible, anonymized)
                    vote_data = f"{request.user.id}-{candidate.id}-{timezone.now()}"
                    vote_hash = hashlib.sha256(vote_data.encode()).hexdigest()
                    Vote.objects.create(
                        candidate=candidate,
                        vote_hash=vote_hash,
                        ip_address=request.META.get('REMOTE_ADDR')
                    )
                    selections_made += 1

            if selections_made == 0:
                messages.error(request, 'Please select at least one candidate before submitting.')
                return redirect('vote_with_election', election_id=election.id)

            # Record voter participation
            verification_code = secrets.token_urlsafe(16)
            VoterRecord.objects.create(
                voter=request.user,
                election=election,
                verification_code=verification_code
            )

            # Log the vote
            AuditLog.objects.create(
                user=request.user,
                action_type='vote',
                description=f'Voted in election: {election.title}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )

            messages.success(request, f'Vote submitted successfully!')
            return redirect('vote_success', election_id=election.id)

    return render(request, 'voting/vote.html', {
        'election': election,
        'positions': positions,
        'positions_data': positions_data,
        'is_active': election.status == 'active' and election.start_date <= timezone.now() <= election.end_date,
        'now': timezone.now(),
        'end_timestamp': int(election.end_date.timestamp() * 1000),
    })

@login_required
@otp_required
def vote(request):
    """Voting dashboard"""
    if request.user.user_type != 'voter':
        messages.error(request, 'Access denied.')
        return redirect('index')

    # Get active elections
    active_elections = Election.objects.filter(status='active')

    if not active_elections.exists():
        messages.info(request, 'No active elections available at the moment. Check back later or view past results.')
        return redirect('live_results')

    # Show election selection page for all active elections
    now = timezone.now()
    elections_with_status = []
    for election in active_elections:
        # Check if user has voted in this election
        has_voted = VoterRecord.objects.filter(voter=request.user, election=election).exists()
        elections_with_status.append({
            'election': election,
            'is_active': election.status == 'active' and election.start_date <= now <= election.end_date,
            'has_voted': has_voted
        })
    return render(request, 'voting/election_select.html', {
        'elections': elections_with_status
    })

@login_required
@otp_required
def vote_success(request, election_id):
    """Vote confirmation page"""
    election = get_object_or_404(Election, id=election_id)
    record = VoterRecord.objects.filter(voter=request.user, election=election).first()
    return render(request, 'voting/success.html', {
        'election': election,
        'record': record,
    })

@login_required
@otp_required
def already_voted(request, election_id):
    election = get_object_or_404(Election, id=election_id)
    record = VoterRecord.objects.filter(voter=request.user, election=election).first()
    return render(request, 'voting/already_voted.html', {
        'election': election,
        'record': record,
    })

def live_results(request):
    """Live results dashboard"""
    # Get all active elections
    active_elections = Election.objects.filter(status='active').prefetch_related('positions__candidates__votes')
        
    # If no active elections, show the most recent closed election
    if not active_elections.exists():
        recent_election = Election.objects.filter(status='closed').order_by('-end_date').first()
        if recent_election:
            active_elections = [recent_election]
        else:
            messages.info(request, 'No election results available.')
            return redirect('index')
        
    # Get the selected election (from URL parameter or default to first active)
    selected_election_id = request.GET.get('election')
    if selected_election_id:
        try:
            selected_election = Election.objects.get(id=selected_election_id, status__in=['active', 'closed'])
        except Election.DoesNotExist:
            selected_election = active_elections.first()
    else:
        selected_election = active_elections.first()
        
    # Get positions and results for selected election (order candidates by votes desc)
    candidates_qs = Candidate.objects.annotate(
        vote_count_agg=Count('votes')
    ).order_by('-vote_count_agg', 'full_name')
    positions = selected_election.positions.all().prefetch_related(
        Prefetch('candidates', queryset=candidates_qs, to_attr='candidates_ordered'),
        'candidates__votes'
    )
        
    # Calculate totals
    total_voters = User.objects.filter(user_type='voter', is_active=True).count()
    total_votes = selected_election.total_votes

    # Prepare positions data for charts
    positions_data = []
    for position in positions:
        position_dict = {
            'id': position.id,
            'title': position.title,
            'description': position.description,
            'candidates': []
        }
        for candidate in position.candidates.all():
            candidate_dict = {
                'id': candidate.id,
                'full_name': candidate.full_name,
                'department': candidate.department,
                'level': candidate.level,
                'manifesto': candidate.manifesto,
                'photo_url': candidate.photo.url if candidate.photo else None,
                'vote_count': candidate.vote_count,
                'vote_percentage': candidate.vote_percentage
            }
            position_dict['candidates'].append(candidate_dict)
        positions_data.append(position_dict)

    template_name = 'results/live_results.html'
    if request.headers.get('HX-Request'):
        template_name = 'results/partials/live_results_content.html'

    return render(request, template_name, {
        'active_elections': active_elections,
        'selected_election': selected_election,
        'positions': positions,
        'positions_data': positions_data,
        'total_voters': total_voters,
        'total_votes': total_votes,
        'now': timezone.now(),
        'end_timestamp': int(selected_election.end_date.timestamp() * 1000),
    })

def admin_login(request):
    """Admin login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)
        if user and user.user_type == 'admin':
            login(request, user)
            AuditLog.objects.create(
                user=user,
                action_type='login',
                description='Admin login',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            return redirect('admin_dashboard')
        else:
            messages.error(request, 'Invalid admin credentials.')

    return render(request, 'admin/admin_login.html')

@login_required
def admin_dashboard(request):
    """Admin dashboard"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    elections = Election.objects.all()
    total_voters = User.objects.filter(user_type='voter').count()
    total_votes = Vote.objects.count()
    active_elections = elections.filter(status='active').count()
    
    # Calculate system health based on various metrics
    total_users = User.objects.count()
    active_users = User.objects.filter(last_login__gte=timezone.now() - timezone.timedelta(days=7)).count()
    recent_votes = Vote.objects.filter(timestamp__gte=timezone.now() - timezone.timedelta(hours=24)).count()
    total_candidates = Candidate.objects.count()
    
    # System health calculation (simplified)
    # Base health: 80%
    # Bonus for active users: up to +10%
    # Bonus for recent activity: up to +10%
    # Penalty for no active elections: -5%
    health_score = 80.0
    health_score += min(10, (active_users / max(1, total_users)) * 100 * 0.1)
    health_score += min(10, recent_votes * 0.5)  # 2 points per recent vote, max 10
    if active_elections == 0:
        health_score -= 5
    
    system_health = min(100.0, max(0.0, health_score))
    
    recent_audits = AuditLog.objects.select_related('user').all()[:6]
    return render(request, 'admin/dashboard.html', {
        'elections': elections,
        'total_voters': total_voters,
        'total_votes': total_votes,
        'active_elections': active_elections,
        'system_health': system_health,
        'total_users': total_users,
        'active_users': active_users,
        'recent_votes': recent_votes,
        'recent_audits': recent_audits,
    })

@login_required
def admin_elections(request):
    """Election management"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('index')

    elections = Election.objects.all()

    def _parse_dt(value):
        dt = parse_datetime(value) if value else None
        if dt and timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    if request.method == 'POST':
        if 'create' in request.POST:
            title = request.POST.get('title')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            status = request.POST.get('status', 'draft')
            start_dt = _parse_dt(start_date)
            end_dt = _parse_dt(end_date)
            if not start_dt or not end_dt:
                messages.error(request, 'Invalid start or end date.')
                return redirect('admin_elections')
            if end_dt <= start_dt:
                messages.error(request, 'End date must be after start date.')
                return redirect('admin_elections')
            if status == 'active' and start_dt > timezone.now():
                start_dt = timezone.now()

            Election.objects.create(
                title=title,
                description=description,
                start_date=start_dt,
                end_date=end_dt,
                status=status,
                created_by=request.user
            )
            messages.success(request, 'Election created successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='create',
                description=f'Created election: {title}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        elif 'update' in request.POST:
            election_id = request.POST.get('election_id')
            title = request.POST.get('title')
            description = request.POST.get('description')
            start_date = request.POST.get('start_date')
            end_date = request.POST.get('end_date')
            status = request.POST.get('status')
            
            election = get_object_or_404(Election, id=election_id)
            start_dt = _parse_dt(start_date)
            end_dt = _parse_dt(end_date)
            if not start_dt or not end_dt:
                messages.error(request, 'Invalid start or end date.')
                return redirect('admin_elections')
            if end_dt <= start_dt:
                messages.error(request, 'End date must be after start date.')
                return redirect('admin_elections')
            if status == 'active' and start_dt > timezone.now():
                start_dt = timezone.now()

            election.title = title
            election.description = description
            election.start_date = start_dt
            election.end_date = end_dt
            election.status = status
            election.save()
            messages.success(request, 'Election updated successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='update',
                description=f'Updated election: {title}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        elif 'delete' in request.POST:
            election_id = request.POST.get('election_id')
            election = get_object_or_404(Election, id=election_id)
            title = election.title
            election.delete()
            messages.success(request, 'Election deleted successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='delete',
                description=f'Deleted election: {title}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        elif 'update_status' in request.POST:
            election_id = request.POST.get('election_id')
            status = request.POST.get('status')
            election = get_object_or_404(Election, id=election_id)
            election.status = status
            election.save()
            messages.success(request, f'Election status updated to {status}.')
    
    return render(request, 'admin/elections.html', {'elections': elections, 'total_voters': User.objects.filter(user_type='voter', is_active=True).count()})

@login_required
def admin_candidates(request):
    """Candidate management"""
    if request.user.user_type != 'admin':
        messages.error(request, 'Access denied.')
        return redirect('index')
    
    # Get base queryset
    candidates = Candidate.objects.all().select_related('position__election', 'user')
    
    # Handle filtering
    election_filter = request.GET.get('election')
    position_filter = request.GET.get('position')
    search_query = request.GET.get('search')
    
    if election_filter:
        candidates = candidates.filter(position__election_id=election_filter)
    
    if position_filter:
        candidates = candidates.filter(position__title__icontains=position_filter)
    
    if search_query:
        candidates = candidates.filter(
            Q(full_name__icontains=search_query) |
            Q(department__icontains=search_query) |
            Q(user__matric_number__icontains=search_query)
        )
    
    if request.method == 'POST':
        if 'create' in request.POST:
            election_id = request.POST.get('election')
            matric_number = request.POST.get('matric_number')
            full_name = request.POST.get('full_name')
            department = request.POST.get('department')
            level = request.POST.get('level')
            position_title = request.POST.get('position_title')
            manifesto = request.POST.get('manifesto')
            photo = request.FILES.get('photo')
            
            election = get_object_or_404(Election, id=election_id)
            user = get_object_or_404(User, matric_number=matric_number)
            
            position, created = Position.objects.get_or_create(
                election=election,
                title=position_title
            )
            
            Candidate.objects.create(
                position=position,
                user=user,
                full_name=full_name,
                department=department,
                level=level,
                manifesto=manifesto,
                photo=photo
            )
            messages.success(request, 'Candidate added successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='create',
                description=f'Added candidate: {full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
            AuditLog.objects.create(
                user=request.user,
                action_type='create',
                description=f'Added candidate: {full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        elif 'update' in request.POST:
            candidate_id = request.POST.get('candidate_id')
            election_id = request.POST.get('election')
            matric_number = request.POST.get('matric_number')
            full_name = request.POST.get('full_name')
            department = request.POST.get('department')
            level = request.POST.get('level')
            position_title = request.POST.get('position_title')
            manifesto = request.POST.get('manifesto')
            photo = request.FILES.get('photo')
            
            candidate = get_object_or_404(Candidate, id=candidate_id)
            election = get_object_or_404(Election, id=election_id)
            user = get_object_or_404(User, matric_number=matric_number)
            
            position, created = Position.objects.get_or_create(
                election=election,
                title=position_title
            )
            
            candidate.position = position
            candidate.user = user
            candidate.full_name = full_name
            candidate.department = department
            candidate.level = level
            candidate.manifesto = manifesto
            if photo:
                candidate.photo = photo
            candidate.save()
            messages.success(request, 'Candidate updated successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='update',
                description=f'Updated candidate: {full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
        elif 'delete' in request.POST:
            candidate_id = request.POST.get('candidate_id')
            candidate = get_object_or_404(Candidate, id=candidate_id)
            full_name = candidate.full_name
            candidate.delete()
            messages.success(request, 'Candidate deleted successfully.')
            AuditLog.objects.create(
                user=request.user,
                action_type='delete',
                description=f'Deleted candidate: {full_name}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
    
    elections = Election.objects.all()
    users = User.objects.filter(user_type='voter')
    
    return render(request, 'admin/candidates.html', {
        'candidates': candidates,
        'elections': elections,
        'users': users
    })

def logout_view(request):
    """Logout"""
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action_type='logout',
            description='User logout',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
    logout(request)
    request.session.pop('otp_verified', None)
    request.session.pop('pending_otp_user_id', None)
    return redirect('index')

