"""Throwaway certificates for the local HTTPS test server.

urllib3 2 verifies with VERIFY_X509_STRICT, so these carry the extensions a
real CA and server certificate have: CA basic constraints and key usage,
key identifiers, and a server-auth leaf whose subjectAltName lists its hosts.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

_PEM = serialization.Encoding.PEM


@dataclass(frozen=True)
class Authority:
    key: ec.EllipticCurvePrivateKey
    cert: x509.Certificate

    def write(self, path: Path) -> Path:
        path.write_bytes(self.cert.public_bytes(_PEM))
        return path


@dataclass(frozen=True)
class ServerCert:
    chain: Path  # leaf then CA, as a server sends it
    key: Path


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _usage(*, sign_certs: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True,
        content_commitment=False,
        key_encipherment=False,
        data_encipherment=False,
        key_agreement=False,
        key_cert_sign=sign_certs,
        crl_sign=sign_certs,
        encipher_only=False,
        decipher_only=False,
    )


def authority(common_name: str) -> Authority:
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(common_name))
        .issuer_name(_name(common_name))
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=30))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(_usage(sign_certs=True), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return Authority(key, cert)


def server_cert(
    ca: Authority,
    directory: Path,
    name: str,
    *,
    hosts: tuple[str, ...] = ("127.0.0.1",),
    expired: bool = False,
) -> ServerCert:
    """Issue a server certificate for ``hosts`` and write its chain and key."""
    key = ec.generate_private_key(ec.SECP256R1())
    now = datetime.now(UTC)
    if expired:
        valid_from, valid_to = now - timedelta(days=30), now - timedelta(days=1)
    else:
        valid_from, valid_to = now - timedelta(days=1), now + timedelta(days=30)
    alt_names: list[x509.GeneralName] = []
    for host in hosts:
        try:
            alt_names.append(x509.IPAddress(ip_address(host)))
        except ValueError:
            alt_names.append(x509.DNSName(host))
    cert = (
        x509.CertificateBuilder()
        .subject_name(_name(hosts[0]))
        .issuer_name(ca.cert.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(valid_from)
        .not_valid_after(valid_to)
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_usage(sign_certs=False), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(ca.key.public_key()),
            critical=False,
        )
        .sign(ca.key, hashes.SHA256())
    )
    chain = directory / f"{name}.pem"
    chain.write_bytes(cert.public_bytes(_PEM) + ca.cert.public_bytes(_PEM))
    key_path = directory / f"{name}.key"
    key_path.write_bytes(
        key.private_bytes(
            _PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    return ServerCert(chain, key_path)
