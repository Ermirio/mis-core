from urllib.parse import urlsplit


def normalize_opc_tcp_url(value):
    """Normalize common OPC URL typos and require an explicit host and port."""
    raw = str(value or '').strip()
    if not raw:
        raise ValueError('URL OPC vazia')

    lowered = raw.lower()
    if lowered.startswith('opc.tcp//'):
        raw = f"opc.tcp://{raw[len('opc.tcp//'):].lstrip('/')}"
    elif lowered.startswith('opc.tcp:/') and not lowered.startswith('opc.tcp://'):
        raw = f"opc.tcp://{raw[len('opc.tcp:/'):].lstrip('/')}"
    elif lowered.startswith('opc.tcp:') and not lowered.startswith('opc.tcp://'):
        raw = f"opc.tcp://{raw[len('opc.tcp:'):].lstrip('/')}"

    parsed = urlsplit(raw)
    if parsed.scheme.lower() != 'opc.tcp':
        raise ValueError('a URL deve comecar com opc.tcp://')
    if not parsed.hostname:
        raise ValueError('host/IP ausente')

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError('porta invalida') from exc

    if port is None:
        raise ValueError('porta ausente')

    return raw
