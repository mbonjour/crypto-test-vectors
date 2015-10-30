from __future__ import print_function
import binascii
from ecc import *

radix_256 = 2 ** 256
radix_8 = 2 ** 8

genP256 = ECPoint(secp256r1.gx, secp256r1.gy, secp256r1)


class ImplicitCertUtil:
    """Implicit Certificate Helper"""

    @staticmethod
    def gen_cert(tbsCert, RU, dCA, k=None):
        """
        Implicit Certificate Generation as per SEC4 Sec 3.4

        Inputs:
        - tbsCert: {octet string} To-be-signed user's certificate data
        - RU:      {ec256 point}  User's certificate request public key
        - dCA:     {octet string} CA's private key

        Outputs:
        - PU:      {ec256 point} public key reconstruction point
        - CertU:   {octet string} tbsCert || PU
                   In this script, to illustrate the concept, PU is concatenated with tbsCert;
                   it is somewhat similar to CertificateBase in 1609.2 (see 1609dot2-schema.asn)
                   as the verifyKeyIndicator (which is PU) is the last value in the CertificateBase construct,
                   but this should be checked as it depends on the ASN.1 encoding employed.
                   Important Note:
                   - In 1609.2 v3 d9 Sec.6.4.3,
                     H(CertU) = H (H (ToBeSignedCertificate) || H (Entirety of issuer cert) )
                     This was confirmed by William by email on Oct 29, 2015
                   Therefore here H(CertU) = H(tbsCert || PU) is just for illustration purposes
        - r:       {octet string} private key reconstruction value
        """
        r_len = 256 / 8
        assert len(dCA) == r_len * 2, "input dCA must be of octet length: " + str(r_len)
        assert RU.is_on_curve(), "User's request public key must be a point on the curve P-256"

        # Generate CA's ephemeral key pair

        if k is None:
            k_long = randint(1, genP256.ecc.n - 1)
            # unused k
            k = "{0:0>{width}X}".format(k_long, width=bitLen(genP256.ecc.n) * 2 // 8)
        else:
            k_long = int(k, 16)
        kG = k_long * genP256

        # Compute User's public key reconstruction point, PU
        PU = RU + kG

        # Convert PU to an octet string (compressed point)
        PU_os = PU.output(compress=True)

        # CertU = tbsCert || PU (see note above)
        CertU = tbsCert + PU_os

        # e = leftmost floor(log_2 n) bits of SHA-256(CertU), i.e.
        # e = Shiftright(SHA-256(CertU)) by 1 bit
        e = sha256(binascii.unhexlify(CertU)).hexdigest()
        e_long = int(e, 16) // 2

        r_long = (e_long * k_long + int(dCA, 16)) % genP256.ecc.n
        r = "{0:0>{width}X}".format(r_long, width=bitLen(genP256.ecc.n) * 2 // 8)
        return PU, CertU, r

    @staticmethod
    def reconstruct_private(kU, CertU, r):
        """
        Implicit Certificate Private Key Reconstruction as per SEC4 Sec. 3.6

        Inputs:
        - kU:    {octet string} User's certificate request private key, corresponding to RU
        - CertU: {octet string} tbsCert || PU (see note above)
        - r:     {octet string} private key reconstruction value

        Output:
        - dU: {octet string} User's (reconstructed) private key

        Note:
        In SEC 4 Sec. 3.6, QU, the User's private key is calculated as
        QU' = dU*G
        and is verified to be equal to QU calculated by reconstruction (see function below)
        This check is performed in the tests, outside this function.
        """

        # e = leftmost floor(log_2 n) bits of SHA-256(CertU)
        e = sha256(binascii.unhexlify(CertU)).hexdigest()
        e_long = int(e, 16) // 2

        # Compute U's private key
        # dU = (e * kU + r) mod n
        dU_long = (e_long * int(kU, 16) + int(r, 16)) % genP256.ecc.n
        dU = "{0:0>{width}X}".format(dU_long, width=bitLen(genP256.ecc.n) * 2 // 8)

        return dU

    @staticmethod
    def reconstruct_public(CertU, QCA):
        """
        Implicit Certificate Public Key Reconstruction as per SEC4 Sec. 3.5
        Can be performed by any party.

        Inputs:
        - CertU: {octet string} tbsCert || PU (see note above)
        - QCA:   {ec256 point}  CA's public key

        Output:
        - QU: {ec256_point} User's (reconstructed) public key
        """

        # extract PU,
        # in this script it's the last 33 bytes of CertU, an octet string of a compressed point
        PU_os = CertU[-33 * 2:]

        # convert PU_os to an ec256_point
        PU = ECPoint(secp256r1, PU_os)

        # e = leftmost floor(log_2 n) bits of SHA-256(CertU)
        # Read note above about what is actually the input to SHA-256
        e = sha256(binascii.unhexlify(CertU)).hexdigest()
        e_long = int(e, 16) // 2

        # Compute U's public key
        QU = e_long * PU + QCA

        return QU
