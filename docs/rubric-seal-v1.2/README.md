# Seal of the Holdout Labs Fragility Rubric v1.2

`../RUBRIC-v1.2.md` (SHA-256 `81bc60b5bf4520fdfb91c43b37883c30a9a2061903442d1e8a8b05f3d37a71fc`) was timestamped under RFC 3161 at 2026-09-25 20:33:45Z (DigiCert) and 20:33:46Z (FreeTSA). That was before any Batch 3 data were fetched and before any positive-control run. The seal record `seal.json` has SHA-256 `142cbfb45314faab8a578b62a17532ac323b0f619f74ab008244163d682db4dd`.

To verify, run each command below; each should print `Verification: OK`.

```bash
C=src/holdout_audit/certs
openssl ts -verify -data docs/RUBRIC-v1.2.md -in docs/rubric-seal-v1.2/81bc60b5bf4520fd.digicert.tsr -CAfile $C/digicert-trusted-root-g4.pem
openssl ts -verify -data docs/RUBRIC-v1.2.md -in docs/rubric-seal-v1.2/81bc60b5bf4520fd.freetsa.tsr -CAfile $C/freetsa-cacert.pem -untrusted $C/freetsa-tsa.crt
```
