from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


def normalize_opc_tcp_url(value):
    """Normalize common OPC URL typos and require an explicit host and port."""
    raw = str(value or '').strip()
    if not raw:
        raise ValidationError('Informe a URL do servidor OPC UA.')

    lowered = raw.lower()
    if lowered.startswith('opc.tcp//'):
        raw = f"opc.tcp://{raw[len('opc.tcp//'):].lstrip('/')}"
    elif lowered.startswith('opc.tcp:/') and not lowered.startswith('opc.tcp://'):
        raw = f"opc.tcp://{raw[len('opc.tcp:/'):].lstrip('/')}"
    elif lowered.startswith('opc.tcp:') and not lowered.startswith('opc.tcp://'):
        raw = f"opc.tcp://{raw[len('opc.tcp:'):].lstrip('/')}"

    parsed = urlsplit(raw)
    if parsed.scheme.lower() != 'opc.tcp':
        raise ValidationError('A URL deve comecar com opc.tcp://.')
    if not parsed.hostname:
        raise ValidationError('A URL OPC deve informar o host ou IP do servidor.')

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValidationError('A porta da URL OPC e invalida.') from exc

    if port is None:
        raise ValidationError('A URL OPC deve informar a porta do servidor.')

    return raw
