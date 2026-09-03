# NeuroData researcher beta site

This Worker serves the reviewed `v0.3.0b1` researcher kit and records only
random, unlinked download sessions and optional installation confirmations.
Dataset files, local paths, scan reports, names, email addresses and participant
IDs are not sent to the Worker or stored in D1.

## Local verification

Place the exact published wheel in `.artifacts/`, then run:

```bash
npm ci
npm run build:kit
npm test
npx wrangler d1 migrations apply neurodata-researcher-beta-installs --local
npm run dev
npm run check:deploy
```

The kit builder rejects a wheel whose filename, version or SHA-256 differs from
`src/release.js`. It builds the ZIP twice and fails if the output is not
deterministic. The site reads version and package information from
`/api/info`; do not duplicate release values in the HTML or frontend script.

For a production update, apply pending D1 migrations remotely before deploying
the Worker. Both operations are external changes and require explicit approval.
After deployment, test download, refresh recovery and installation confirmation
in desktop Chrome, Firefox and Safari before sharing the link.

## EEG-list invitation draft

Replace `<BETA_URL>` with the verified live URL before sending.

**Subject:** Beta testers wanted: local neurodata release audit

I am looking for researchers to test an open-source Python tool with a local
browser interface. It checks a neurodata release for privacy-relevant metadata,
broken file references and coverage gaps before sharing. The scan runs locally
and does not upload or modify the dataset.

Installation and the synthetic demo take about 20 minutes on macOS, Windows or
Linux. The beta supports Python 3.10–3.13 and is tested in CI on Python 3.10,
3.12 and 3.13. An optional authorised dataset scan may take longer depending on
its size and formats. Relevant formats include BIDS metadata, EEGLAB `.set`,
BrainVision, EDF/BDF and FIF. Send feedback, not the dataset or unreviewed
reports.

Beta: <BETA_URL>

Thank you,
Daria Agafonova
