# Sitemap single-source change

The project now has one authoritative sitemap:

`sitemap.xml`

Removed duplicate copies:
- `static/sitemap.xml`
- `deploy/sitemap.xml`

Public sitemap URL:
- https://homeworkmagic.co.uk/sitemap.xml

The deployment process should copy/serve the root `sitemap.xml` rather than maintaining separate sitemap copies.
