# SaunaImport.com

A static research site for U.S. sauna trade, tariff and customs intelligence. It uses primary CBP rulings to identify sauna-relevant HTS categories and a scheduled GitHub Action to fetch U.S. Census International Trade data.

## What the site now does

- Publishes crawlable static HTML for live Census metrics instead of relying on JavaScript placeholders
- Retains the current trade dataset as JSON plus category and country CSV files
- Configures the updater to pull full monthly history from January 2010 forward, including an explicit 2017 code crosswalk for prefabricated buildings of wood
- Writes immutable monthly snapshots under `data/archive/YYYY-MM/`
- Generates a dated monthly research release under `reports/YYYY-MM/`
- Maintains classification research for complete wooden saunas, electric sauna heaters and portable infrared saunas
- Includes contrasting CBP rulings for built-in sauna kits and multi-country barrel saunas
- Publishes tariff research, methodology, data dictionary, source hierarchy and citation guidance
- Includes `Dataset` structured data, sitemap, explicit crawler access and `llms.txt`
- Provides one consumer pathway under `/where-to-buy/`

## Census API key

Create a repository secret:

`Repository → Settings → Secrets and variables → Actions → New repository secret`

Name it:

`CENSUS_API_KEY`

Then run **Actions → Update trade data and deploy → Run workflow** once.

The scheduled workflow runs weekly. Census trade data are monthly, so most weekly runs will simply confirm the newest released month until a new release appears.

## Deployment

In GitHub Pages set:

`Settings → Pages → Build and deployment → Source: GitHub Actions`

Both workflows render the committed trade snapshot into static HTML before staging the public site. The data-refresh workflow also commits the regenerated data, archive and report pages when they change.

## Custom domain

The repository includes `CNAME` for `saunaimport.com`. Configure the apex and `www` DNS records according to current GitHub Pages documentation and enable **Enforce HTTPS** after DNS resolves.

## Important methodological constraint

Do **not** add the totals for `9406.10 + 8516.29 + 8516.79` and label the sum “U.S. sauna imports.” Each category contains substantial non-sauna merchandise. The site deliberately publishes them separately as sauna-relevant proxy categories.

## Local preview

No framework is required:

```bash
python3 scripts/render_site.py
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## Legal / customs disclaimer

This repository is an informational research project and is not legal, customs, tariff, tax or brokerage advice. CBP classifications are fact-specific and tariff treatment can change.
