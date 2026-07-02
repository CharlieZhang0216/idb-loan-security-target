"""Generate proper password hashes for seed users to enable login.
For the demo, we use a known password for each role:
- borrower: password123
- officer:  officer123
- risk:     risk123
- admin:    admin123
"""
import hashlib
import sys
sys.path.insert(0, '/app')
from app import create_app, db
from models import User

app = create_app('development')

DEMO_PASSWORDS = {
    'borrower': 'password123',
    'officer': 'officer123',
    'risk': 'risk123',
    'admin': 'admin123',
}

def hash_password(password, role=None):
    """Generate a fake hash for demo purposes."""
    return f'scrypt:32768:8:1$demo${hashlib.sha256(password.encode()).hexdigest()[:40]}'

def verify_password(stored, password):
    """Simple verification for demo - compares SHA256."""
    expected = hashlib.sha256(password.encode()).hexdigest()[:40]
    return expected in stored

with app.app_context():
    users = User.query.all()
    for user in users:
        demo_pw = DEMO_PASSWORDS.get(user.role, 'password123')
        user.password_hash = hash_password(demo_pw, user.role)
        print(f"Set password for {user.username} ({user.role}): {demo_pw}")

    db.session.commit()
    print(f"\nUpdated {len(users)} users with demo passwords")

    # Print demo credentials
    print("\n=== DEMO CREDENTIALS ===")
    print("Borrower:  br_cn_liwei / password123")
    print("Officer:   of_anderson / officer123")
    print("Risk:      ri_mueller / risk123")
    print("Admin:     ad_martinez / admin123")
    print("========================\n")
