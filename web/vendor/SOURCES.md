# Vendor Asset Sources

This directory pins third-party browser assets required by `web/ui/index.html`.

## Pinned Assets

- `react/react.development.js`
  - Source: `https://unpkg.com/react@18.2.0/umd/react.development.js`
  - Version: `react@18.2.0`
  - SHA256: `857364e2b982318417025fb9b4b8355c09f75fa46ba0be93f520f769f6757a78`

- `react/react-dom.development.js`
  - Source: `https://unpkg.com/react-dom@18.2.0/umd/react-dom.development.js`
  - Version: `react-dom@18.2.0`
  - SHA256: `6d11da926dde155c0d8773ae0e05bb64683f1f40d4e1eb628717dd8499172282`

- `babel/babel.min.js`
  - Source: `https://unpkg.com/@babel/standalone@7.24.6/babel.min.js`
  - Version: `@babel/standalone@7.24.6`
  - SHA256: `c5543421a97f01005685e77b03f5d34259a56ba75232cde6ed5219662911775f`

## Rationale

These assets are intentionally vendored so the UI shell does not depend on
live external network/CDN availability.

