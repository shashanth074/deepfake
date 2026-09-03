# Legal, Ethical and Chain-of-Custody Considerations

## What this platform is — and is not

It produces an **automated technical assessment**. It is not a certified
forensic determination, and it holds no investigative or legal authority.

It also **does not file complaints**. It generates an evidence document that a
complainant submits themselves through their own jurisdiction's process. Keeping
that boundary explicit avoids the platform appearing to act as a legal
authority, and it is stated in the UI footer, the API response, and section 5 of
every generated report.

Real cybercrime cases are typically escalated to a government forensic
laboratory. This tool produces an investigative lead, not proof.

## Chain of custody

| Step | Mechanism |
|---|---|
| Preserve the original | The uploaded bytes are written once and never modified. Analysis works on copies and derived frames. |
| Hash on arrival | SHA-256 computed during the streaming write, before any processing, and stored on the job record. |
| Attest in the report | The file hash is printed in section 1 with instructions for reproducing it. |
| Hash the report | The finished PDF is hashed and the value recorded in the report register. |
| Publish for verification | `GET /api/reports/{ref}/verify` returns that hash, publicly and without authentication, so a reviewer can check a document without access to the submission. |

A document cannot contain its own hash. Rather than printing a self-referential
value that no one could reproduce, the report names the register endpoint. Both
checks then work with ordinary tools (`shasum -a 256`, `certutil -hashfile`).

**Limits of this scheme.** Hashes detect alteration; they do not prove
authorship or origin, and the register is only as trustworthy as the platform
serving it. A production deployment handling real case material should add
signatures from a recognised certifying authority and a tamper-evident audit
log.

## Data protection

Uploaded media is sensitive personal data — often the complainant's own face or
voice, sometimes in intimate content.

- **Minimisation.** Only the file, its hash and its metadata are stored. Guests
  need no account at all.
- **Access control.** A job created by a signed-in user is readable only by
  them. Guest jobs are reachable only via an unguessable identifier. Failures
  return 404 rather than 403, so an identifier is never confirmed to exist.
- **Erasure.** `DELETE /api/history/{id}` removes the record, the stored media,
  the evidence images and the generated reports. This is the right-to-erasure
  path under GDPR Art. 17 and India's DPDP Act.
- **Retention.** Set an explicit retention window before any real deployment and
  publish it. There is deliberately no default: an arbitrary one would be worse
  than a considered one.
- **Encryption.** Use encryption at rest for the storage volume and TLS in
  transit. `docs/deployment.md` covers the Nginx/TLS setup.

## Acceptable use

- Analyse only media you own or are authorised to analyse.
- The platform detects manipulation; it must not be used to create it.
- Do not demonstrate with a real person's face or voice without their consent —
  use consenting volunteers or public research datasets.

## Honest reporting

Deliberate design choices that keep the output truthful:

- Scores near the threshold return **inconclusive**, never a forced binary.
- Confidence is reported separately from probability, and reads zero at 0.5.
- A deployment with no trained checkpoint is flagged in the API response, in the
  UI, and in a red block in the PDF stating the result has no evidentiary value.
- The known-limitations disclaimer appears in the report itself, not only in the
  documentation, because the report is what travels to a police station.
- The false-positive rate is tracked alongside accuracy. Real uploads are
  overwhelmingly authentic, so a model with 95% accuracy and a 10% false-positive
  rate would wrongly accuse a great many innocent people.
