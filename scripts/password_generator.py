import secrets, urllib.parse

password = secrets.token_urlsafe(24) + '@#!'  # Strong random pass with forced special chars
encoded = urllib.parse.quote_plus(password)

print(f'POSTGRES_PASSWORD={password}')
print(f'POSTGRES_PASSWORD_URLENCODED={encoded}')