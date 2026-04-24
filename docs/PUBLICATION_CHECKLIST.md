# Publication Checklist — SoftwareX

This is the step-by-step procedure for the day you submit the SoftwareX
article.  Do **not** run any of the public/Zenodo steps until you are ready:
flipping a repository to public and cutting a Zenodo-archived release mints
permanent identifiers.

The deployment-twin repository (`*-app-link`) remains **PRIVATE** forever.
Only this open-access repository is made public and archived.

---

## A. Activate Zenodo on your GitHub account (one-time)

1. Visit <https://zenodo.org> and **Log in with GitHub** (authorise).
2. Open <https://zenodo.org/account/settings/github/>.
3. You will see all your GitHub repositories.  Leave every toggle **OFF**
   until you reach step B.3 — Zenodo only archives a repository after you
   flip its toggle on **and** create a GitHub Release.

## B. Submission-day procedure

Run from inside this repository.

### B.1 Pre-flight

```powershell
gh repo view El-Naggar8876/sprinkler-design-softwarex --json visibility,licenseInfo,description
git status              # working tree must be clean
git log --oneline -3    # confirm latest commit
```

Open the live Streamlit Cloud URL once and confirm it works end-to-end.

### B.2 Make the repository public

```powershell
gh repo edit El-Naggar8876/sprinkler-design-softwarex --visibility public --accept-visibility-change-consequences
```

### B.3 Enable Zenodo for this repository

1. Refresh <https://zenodo.org/account/settings/github/>.
2. Locate `El-Naggar8876/sprinkler-design-softwarex` and switch the
   toggle to **ON**.
3. *(Optional)* Click the repository name and **Reserve DOI**.  You can then
   cite the DOI in the article before the first release exists.

### B.4 Cut the v1.0.0 release

```powershell
gh release create v1.0.0 \
    --title "v1.0.0 — SoftwareX submission" \
    --notes "First archived release accompanying the SoftwareX article submission."
```

Within roughly one minute Zenodo will:

- Download the source archive automatically.
- Mint a permanent DOI (e.g. `10.5281/zenodo.XXXXXXX`).
- Create a versioned record and a concept DOI (the latter always points to
  the most recent version).

### B.5 Add the DOI badge

Copy the Markdown badge from the Zenodo record and add it at the top of
`README.md`:

```markdown
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.XXXXXXX.svg)](https://doi.org/10.5281/zenodo.XXXXXXX)
```

Update the DOI placeholder in `CITATION.cff`, commit and push:

```powershell
git add README.md CITATION.cff
git commit -m "docs: add Zenodo DOI badge"
git push
```

## C. SoftwareX "Code metadata" table

| Field | Value |
|-------|-------|
| Current code version | `v1.0.0` |
| Permanent link to code/repository | `https://github.com/El-Naggar8876/sprinkler-design-softwarex` |
| Permanent link to executables | Streamlit Cloud URL (see Step 2) |
| Legal Code License | MIT |
| Code versioning system used | git |
| Languages, tools, services | Python 3.11, Streamlit, NumPy, SciPy, Plotly, Folium, ezdxf, Earth Engine API |
| Compilation requirements | `pip install -r requirements.txt` |
| Link to developer documentation | `README.md` and `docs/` |
| Support email | _to be added_ |
| DOI | _from Zenodo (Step B.4)_ |

## D. Reverting

- **Made repo public too early:**
  ```powershell
  gh repo edit El-Naggar8876/sprinkler-design-softwarex --visibility private --accept-visibility-change-consequences
  ```
- **Cut a release by mistake:** delete the GitHub Release.  Zenodo cannot
  withdraw a minted DOI but you can email <support@zenodo.org> to mark the
  record as removed.  Better to not release until you are certain.
- **Wrong files committed after release:** push a follow-up commit and tag
  `v1.0.1`.

## E. Rotate the GCP service-account key

Once the live apps are deployed and stable, before stepping away from the
project, rotate the Google Cloud service-account key that is currently in:

1. The original `Drip-Irrigation-Design` repository (in git history).
2. The local `.streamlit/secrets.toml` of the two `*-app-link` twins.
3. The Streamlit Community Cloud "Secrets" panel for each deployed app.

Procedure: Google Cloud Console → *IAM & Admin* → *Service Accounts* →
`earth-engine-access-982@steel-sonar-428908-v8.iam.gserviceaccount.com` →
*Keys* tab → **Add key** (JSON) → update the three locations above → delete
the old key.
