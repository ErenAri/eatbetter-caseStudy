# P0 and P3 QA closeout — 2026-08-19

## Outcome

No open P0 application defect remains within the local case-study runtime. The audit found and fixed
two P0 hardening issues: vulnerable backend HTTP/upload dependency pins and a nonlocal environment
that could compose development authentication with in-memory persistence. Staging and production now
fail closed until verified authentication, persistent repository, and private object-storage adapters
exist.

The recorded P3 finding `EB-QA-014` remains fixed. This closeout also resolves three additional P3
polish findings: destructive actions lacked confirmation, assistive technology heard only calories
instead of complete daily nutrition, and project-status copy still reported the already-fixed P1
no-go state.

This is not a production security certification. The app remains an undeployed case study with the
production adapters, operational controls, physical-device testing, and product-specific measured
accuracy evidence explicitly deferred.

## P0 audit

| Area | Evidence and result |
|---|---|
| Runtime composition | `APP_ENV=staging` and `APP_ENV=production` are rejected before the local development repository, storage, or bearer-token seam can start. Regression tests cover both environments. |
| Authentication and ownership | Every meal route depends on the authentication seam; repository and service reads, writes, summaries, and deletion include the derived owner ID. This remains development authentication, not production JWT verification. |
| Image handling | Upload reads are bounded, allowed MIME types are explicit, JPEG/PNG/WebP signatures are checked, storage keys are generated, and original filenames are not trusted. |
| Nutrition safety | Confirmation still requires a retrieved canonical identity, nutrition snapshot, portion provenance, deterministic final nutrition, and no unresolved blocking clarification for every active food. |
| AI authority | Vision cannot provide nutrition; canonicalization can select only a persisted candidate rank or abstain; final arithmetic remains Decimal-based application code. |
| Secrets and private evidence | `.env`, raw benchmark runs, private photos, and generated Android output remain ignored. The tracked-file secret scan found no credential pattern. |
| Backend dependencies | `fastapi 0.141.1`, `starlette 1.6.0`, and `python-multipart 0.0.32` replace vulnerable pins. `pip-audit -r requirements.txt` reports no known vulnerabilities. |
| Irreversible UI actions | Removing a food and permanently discarding an incomplete meal now require explicit destructive confirmation. |

## P3 closeout

- `EB-QA-014`: Today does not render a stale Log meal action while loading or showing an error.
- `EB-QA-015`: Remove food explains that the item will be excluded from the saved meal and totals;
  the mutation runs only after the destructive confirmation.
- `EB-QA-016`: Discard and start over explains that the incomplete record and uploaded image are
  permanently deleted; cancel is the safe default.
- `EB-QA-017`: daily nutrition exposes calories, protein, carbohydrates, and fat as one assistive
  label. Busy food actions and candidate choices expose their disabled state and reject taps.
- `EB-QA-018`: project status now reflects the completed P1/P2/P3 remediation and standalone Android
  debug build instead of the superseded no-go recommendation.

## Dependency-audit boundary

`npm audit --omit=dev` reports zero critical, 11 high, and seven moderate advisories in the Expo 57 /
React Native 0.86 dependency graph. The reported paths are Metro, Expo CLI/config plugins, Xcode, and
their transitive parsers—local build tooling that is not shipped as the meal-analysis server. The
audit's proposed automatic remediation is an incompatible downgrade to Expo 53 and React Native
0.72; the currently published `image-size 2.0.2` is itself still inside the reported affected range.
No forced override or unsupported SDK downgrade was applied.

This remains a real development-machine supply-chain boundary: use trusted project assets, do not
expose Metro to untrusted networks, and update the Expo SDK when a compatible patched dependency set
is available. The backend separately accepts only bounded JPEG, PNG, and WebP uploads and does not use
the affected Metro image parser.

## Verification

- Backend: `130 passed`
- Evaluation harness: `40 passed`
- Mobile: `28 passed`
- TypeScript: clean
- Expo Doctor: `21/21`
- Python dependency audit: no known vulnerabilities
- Standalone Android evidence from the prior pass: debug APK built, installed, and cold-launched on
  `boyama_test`

## Remaining owner/device work

1. Test camera cancel, background/foreground, and process-death restoration on a physical Android
   phone.
2. Run iOS and screen-reader passes.
3. Collect owned or consented phone meals with weighed portions and measured oil/sauce for genuine
   end-to-end product accuracy evidence.
4. Implement production JWT, persistence, storage, deployment, monitoring, backup, and incident
   response before allowing staging or production startup.
