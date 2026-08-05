"""Generate the offline-verification signing key pair.

Keep private_key.pem only on the license server. Bundle public_key.pem with the app.
"""

from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


root = Path(__file__).resolve().parent
private_path = root / "private_key.pem"
public_path = root / "public_key.pem"
if private_path.exists() or public_path.exists():
    raise SystemExit("Refusing to overwrite an existing signing key.")

private_key = Ed25519PrivateKey.generate()
private_path.write_bytes(
    private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
)
public_path.write_bytes(
    private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
)
print(f"Private key: {private_path} (server only; never commit or distribute it)")
print(f"Public key:  {public_path} (copy to backend/license_public_key.pem)")
