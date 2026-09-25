# Seal of the Holdout Labs Fragility Rubric v1.1

`../RUBRIC-v1.1.md` (SHA-256 `2311b126336bab9f426a84f9c9cd9cb937e346b403a62f60e3c96ed8b5868e46`, committed in `f43316e`) was timestamped under RFC 3161 by two independent authorities before any audit was run under it:

| Authority | Signed time (UTC) | Token |
|---|---|---|
| DigiCert | 2026-09-25T14:20:10Z | `2311b126336bab9f.digicert.tsr` |
| FreeTSA | 2026-09-25T14:20:11Z | `2311b126336bab9f.freetsa.tsr` |

The seal record `seal.json` has SHA-256 `ac882c422df5154ec7e6e928904c9099d6b286dc9e5369fece4b85df57044138`, and every v1.1 report prints it.

## Verify it yourself

Each command should print `Verification: OK`.

```bash
C=src/holdout_audit/certs
openssl ts -verify -data docs/RUBRIC-v1.1.md -in docs/rubric-seal-v1.1/2311b126336bab9f.digicert.tsr -CAfile $C/digicert-trusted-root-g4.pem
openssl ts -verify -data docs/RUBRIC-v1.1.md -in docs/rubric-seal-v1.1/2311b126336bab9f.freetsa.tsr -CAfile $C/freetsa-cacert.pem -untrusted $C/freetsa-tsa.crt
uv run holdout-audit verify-seal docs/rubric-seal-v1.1
```
