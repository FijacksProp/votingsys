#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'VotingSystem.settings')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from vsapp.models import *

print("=== DATABASE STATUS ===")
print("\nElections:")
for e in Election.objects.all():
    print(f"  {e.id}: {e.title} - Status: {e.status}")
    positions = e.positions.all()
    print(f"    Positions: {[p.title for p in positions]}")

print("\nUsers:")
for u in User.objects.all():
    print(f"  {u.username}: {u.user_type} - Matric: {u.matric_number}")

print("\nAll Positions:")
for p in Position.objects.all():
    print(f"  {p.title} - Election: {p.election.title}")

print("\nCandidates:")
for c in Candidate.objects.all():
    print(f"  {c.full_name} - Position: {c.position.title} - Election: {c.position.election.title}")

print("\nVotes:")
for v in Vote.objects.all():
    print(f"  {v.voter.username} voted for {v.candidate.full_name} in {v.position.title}")

print("\nVoter Records:")
for vr in VoterRecord.objects.all():
    print(f"  {vr.voter.username} in {vr.election.title}")