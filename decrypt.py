"""Decrypt main.enc back into main.py."""
import os
import sys
import getpass
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.fernet import Fernet, InvalidToken
import base64

TARGET = os.path.join(os.path.dirname(__file__), "main.enc")
OUTPUT = os.path.join(os.path.dirname(__file__), "main.py")

def derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

def main():
    if not os.path.exists(TARGET):
        print("main.enc not found.")
        sys.exit(1)

    password = getpass.getpass("Enter password: ")

    data  = open(TARGET, "rb").read()
    salt  = data[:16]
    token = data[16:]

    try:
        key      = derive_key(password, salt)
        plaintext = Fernet(key).decrypt(token)
    except InvalidToken:
        print("Wrong password.")
        sys.exit(1)

    with open(OUTPUT, "wb") as f:
        f.write(plaintext)

    os.remove(TARGET)
    print("Decrypted → main.py  (main.enc deleted)")

if __name__ == "__main__":
    main()
