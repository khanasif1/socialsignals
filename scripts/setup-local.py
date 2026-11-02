"""Initialize private local configuration without printing or overwriting secrets."""
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
backend = root / "backend" / ".env"
frontend = root / "frontend" / ".env"
if not backend.exists():
    template = (root / ".env.example").read_text(encoding="utf-8").split("# Copy ONLY")[0]
    template = template.replace("replace-with-a-private-random-login-passphrase", secrets.token_urlsafe(36))
    template = template.replace("replace-with-an-independent-random-signing-secret", secrets.token_urlsafe(36))
    with backend.open("x", encoding="utf-8") as file:
        file.write(template)
    backend.chmod(0o600)
    print("Created backend/.env with independent private secrets. Read its login passphrase locally; never commit it.")
else:
    print("Kept existing backend/.env.")
if not frontend.exists():
    with frontend.open("x", encoding="utf-8") as file:
        file.write("EXPO_PUBLIC_API_URL=http://localhost:8000\nEXPO_PUBLIC_DEMO=true\n")
    print("Created frontend/.env in demo mode.")
else:
    print("Kept existing frontend/.env.")
