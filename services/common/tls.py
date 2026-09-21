"""Add an explicitly trusted local CA without disabling certificate validation."""
import ssl


def vendor_tls(verify=True, ca_bundle=""):
    if ca_bundle:
        if not verify:
            raise ValueError("A CA bundle requires certificate verification")
        context = ssl.create_default_context()
        context.load_verify_locations(cafile=ca_bundle)
        return context
    return verify
