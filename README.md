# SaunaImport.com

A zero-hosting-cost static research site for U.S. sauna trade and tariff intelligence. It uses primary CBP rulings to identify sauna-relevant HTS categories and a scheduled GitHub Action to fetch monthly data from the U.S. Census International Trade API.

## What is already built

- Responsive static site, no framework and no runtime dependency
- Trade dashboard with vanilla-JS charting
- Classification pages for prefabricated wooden saunas, electric sauna heaters and portable infrared saunas
- Curated CBP ruling library
- Methodology page designed to prevent false “sauna market size” claims from broad tariff categories
- JSON/CSV endpoints
- SEO metadata, canonical URLs, Dataset structured data, sitemap, robots.txt and llms.txt
- Scheduled Census data refresh
- GitHub Pages deployment workflow
- Custom domain set to `saunaimport.com`

## 1. Create the GitHub repository

Create a repository (for example `saunaimport`) and upload the contents of this folder to the repository root. The default branch should be `main`.

## 2. Get a Census API key

The Census Bureau currently requires an API key for all Data API queries. Request one from the Census developers site.

In GitHub, go to:

`Repository → Settings → Secrets and variables → Actions → New repository secret`

Create:

`CENSUS_API_KEY = your key`

Then run **Actions → Update trade data → Run workflow** once. The workflow will generate `data/trade.json` and `data/trade.csv`. It is also scheduled weekly; the Census underlying trade data are monthly.

## 3. Enable GitHub Pages

Go to:

`Repository → Settings → Pages → Build and deployment → Source: GitHub Actions`

The included `pages.yml` stages only the public website files and deploys them using the current GitHub Pages Actions flow. The scheduled data workflow also deploys immediately after refreshing Census data, so it does not rely on a bot commit triggering another workflow.

## 4. Add the custom domain

In `Settings → Pages → Custom domain`, enter:

`saunaimport.com`

For the apex domain at GoDaddy, GitHub currently documents these A records:

- `185.199.108.153`
- `185.199.109.153`
- `185.199.110.153`
- `185.199.111.153`

For `www`, add a CNAME to your GitHub Pages default host, e.g. `YOUR-GITHUB-USERNAME.github.io` (not to the repository path). GitHub recommends configuring both apex and `www` and can redirect between them.

After DNS resolves, enable **Enforce HTTPS** in GitHub Pages.

## 5. Important methodological constraint

Do **not** change the site to add `9406.10 + 8516.29 + 8516.79` and label the result “U.S. sauna imports.” Those categories are broader than saunas. The site is deliberately designed to show each proxy separately until a defensible shipment-description data source is added.

## Local preview

No build is required:

```bash
python3 -m http.server 8080
```

Open `http://localhost:8080`.

## Data source

U.S. Census Bureau International Trade API, `imports/hsimport` endpoint. The updater uses the world geography for the 36-month time series and USITC standard countries/areas for the latest origin-country breakdown.

## Legal / customs disclaimer

This repository is an informational research project and is not legal, customs, tariff, tax or brokerage advice. CBP classifications are fact-specific and tariff treatment can change.
