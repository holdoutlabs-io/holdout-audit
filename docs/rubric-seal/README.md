# Seal of the Holdout Labs Fragility Rubric v1.0

`../RUBRIC-v1.0.md` (SHA-256 `0c0420617f2f460d452d862b5e522171bef5e91a259a845d77449bfa115a7292`) was timestamped under RFC 3161 by two independent authorities before any sample audit was run under it:

| Authority | Signed time (UTC) | Token |
|---|---|---|
| DigiCert | 2026-09-25T14:02:23Z | `0c0420617f2f460d.digicert.tsr` |
| FreeTSA | 2026-09-25T14:02:23Z | `0c0420617f2f460d.freetsa.tsr` |

The seal record `seal.json` has SHA-256 `efad782bc139e091f5eb6573e2aa6764f2bcfa5340c455593298152fbd5009ac`. Every sample report prints this hash. `registry.jsonl` is the hash-chained registry entry. The `.tsq` files are the original requests, which bind the nonce.

## Verify it yourself

With plain OpenSSL, from the repository root. Each command should print `Verification: OK`.

```bash
C=src/holdout_audit/certs
openssl ts -verify -data docs/RUBRIC-v1.0.md -in docs/rubric-seal/0c0420617f2f460d.digicert.tsr -CAfile $C/digicert-trusted-root-g4.pem
openssl ts -verify -data docs/RUBRIC-v1.0.md -in docs/rubric-seal/0c0420617f2f460d.freetsa.tsr -CAfile $C/freetsa-cacert.pem -untrusted $C/freetsa-tsa.crt
openssl ts -reply -in docs/rubric-seal/0c0420617f2f460d.digicert.tsr -text | grep "Time stamp"
```

With the package:

```bash
uv run holdout-audit verify-seal docs/rubric-seal
```

A timestamp proves that this exact text existed no later than the signed time. It does not prove the rubric was designed without seeing any data. See the METHODS change log for what was seen before v1.0 was written.
