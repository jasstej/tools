"""HTTPS/TLS support for file sharing server."""

import ssl
import os
from pathlib import Path
from http.server import HTTPServer


class HTTPSServer(HTTPServer):
    """HTTPS server wrapper using SSL/TLS."""

    def __init__(self, server_address, RequestHandlerClass, certfile, keyfile):
        """
        Initialize HTTPS server.

        Args:
            server_address: (host, port) tuple
            RequestHandlerClass: Handler class
            certfile: Path to SSL certificate file
            keyfile: Path to SSL key file
        """
        super().__init__(server_address, RequestHandlerClass)
        self.certfile = certfile
        self.keyfile = keyfile
        self._setup_ssl()

    def _setup_ssl(self):
        """Configure SSL/TLS for the server."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.certfile, self.keyfile)
        # Disable hostname checking for self-signed certificates
        context.check_hostname = False
        self.socket = context.wrap_socket(self.socket, server_side=True)

    def server_bind(self):
        """Bind socket before wrapping."""
        # We wrap socket in _setup_ssl, so just call parent
        if not hasattr(self.socket, '_wrapped'):
            self.socket._wrapped = True
            super().server_bind()
        else:
            super().server_bind()


def generate_self_signed_cert(certfile: Path, keyfile: Path, days: int = 365):
    """
    Generate a self-signed SSL certificate for testing/LAN use.

    Requires: openssl command-line tool

    Args:
        certfile: Path to save certificate
        keyfile: Path to save private key
        days: Certificate validity period
    """
    import subprocess

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-keyout",
                str(keyfile),
                "-out",
                str(certfile),
                "-days",
                str(days),
                "-nodes",
                "-subj",
                "/CN=localhost",
            ],
            check=True,
            capture_output=True,
        )
        # Restrict permissions on key file
        os.chmod(keyfile, 0o600)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def ensure_certificates(data_dir: Path) -> tuple:
    """
    Ensure SSL certificates exist, generate if needed.

    Args:
        data_dir: Data directory for storing certificates

    Returns:
        (certfile, keyfile) tuple or None if generation fails
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    certfile = data_dir / "server.crt"
    keyfile = data_dir / "server.key"

    # Check if certificates exist
    if certfile.exists() and keyfile.exists():
        return certfile, keyfile

    # Try to generate using openssl
    if generate_self_signed_cert(certfile, keyfile):
        return certfile, keyfile

    # If openssl fails, try using Python's ssl module
    try:
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime

        # Generate private key
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend(),
        )

        # Generate certificate
        subject = issuer = x509.Name(
            [
                x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
            ]
        )
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow())
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
            .add_extension(
                x509.SubjectAlternativeName(
                    [x509.DNSName("localhost"), x509.DNSName("127.0.0.1")]
                ),
                critical=False,
            )
            .sign(key, hashes.SHA256(), default_backend())
        )

        # Save certificate
        with open(certfile, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

        # Save private key
        with open(keyfile, "wb") as f:
            f.write(
                key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.TraditionalOpenSSL,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )

        os.chmod(keyfile, 0o600)
        return certfile, keyfile

    except ImportError:
        return None


