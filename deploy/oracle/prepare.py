"""Generate server-only configuration without printing or overwriting secrets."""
import os
from pathlib import Path
import secrets


def prepare(directory):
    destination = Path(directory) / '.env'
    template = (Path(__file__).parent / '.env.example').read_text(encoding='utf-8')
    values = {key: secrets.token_urlsafe(36) for key in (
        'POSTGRES_ADMIN_PASSWORD', 'POSTGRES_APP_PASSWORD', 'API_PROXY_SECRET')}
    lines = []
    for line in template.splitlines():
        key = line.partition('=')[0]
        lines.append(f'{key}={values[key]}' if key in values else line)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8', newline='\n') as output:
        output.write('\n'.join(lines) + '\n')
    return destination


if __name__ == '__main__':
    try:
        print(f'Created server configuration: {prepare(Path(__file__).parent)}')
    except FileExistsError:
        raise SystemExit('Configuration already exists and was preserved. Edit deploy/oracle/.env on the server.') from None
