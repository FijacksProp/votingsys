from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('register/voter/', views.register_voter, name='register_voter'),
    path('register/adm/', views.register_admin, name='register_admin'),
    path('login/', views.login_view, name='login'),
    path('otp-verify/', views.otp_verify, name='otp_verify'),
    path('vote/', views.vote, name='vote'),
    path('vote/<uuid:election_id>/', views.vote_with_election, name='vote_with_election'),
    path('vote/success/', views.vote_success, name='vote_success'),
    path('live_results/', views.live_results, name='live_results'),
    path('adm/login/', views.admin_login, name='admin_login'),
    path('adm/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('adm/elections/', views.admin_elections, name='admin_elections'),
    path('adm/candidates/', views.admin_candidates, name='admin_candidates'),
    path('logout/', views.logout_view, name='logout'),
]

if settings.DEBUG:
   urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)