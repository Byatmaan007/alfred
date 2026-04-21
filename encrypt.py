"""Encrypt main.py into main.enc using a password."""
import os
import sys
import getpass
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet
import base64

TARGET = os.path.join(os.path.dirname(__file__), "main.py")
OUTPUT = os.path.join(os.path.dirname(__file__), "main.enc")

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def main():
    if not os.path.exists(TARGET):
        print("main.py not found.")
        sys.exit(1)

    password = getpass.getpass("Set encryption password: ")
    confirm  = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        sys.exit(1)

    salt      = os.urandom(16)
    key       = derive_key(password, salt)
    token     = Fernet(key).encrypt(open(TARGET, "rb").read())

    with open(OUTPUT, "wb") as f:
        f.write(salt + token)

    os.remove(TARGET)
    print(f"Encrypted → main.enc  (main.py deleted)")

if __name__ == "__main__":
    main()
