# Frontier Desk: AI news pipeline and website

This project runs an AI-news website that mostly runs itself. You stay in charge of what gets published.

## How it works

1. **Collect.** Every 3 hours, it checks the news feeds listed in `config/sources.yaml`: OpenAI, Google, DeepMind, Anthropic, the main search-industry news sites and tech press.
2. **Choose.** It keeps only AI stories. It skips stories it has already covered, groups reports of the same story together, and ranks them. Official company sources count most. Stories covered by several outlets rank higher.
3. **Draft.** Claude writes a short, original summary of each story using **only** what the sources say, with links to them.
4. **Check.** Each draft gets two checks:
   - A second Claude pass checks every claim against the sources.
   - A copy check makes sure no sentences were lifted from another outlet.

   Drafts that fail either check go to `content/flagged/` and are never published automatically.
5. **Approve.** New drafts arrive as one pull request on GitHub. Read them and fix anything you want. Then press **Merge** to publish them all, or delete a draft's file to reject it.
6. **Publish.** Merging rebuilds the website and puts it live. The site includes section pages, article pages, an RSS feed, a sitemap and Google news markup.

Nothing is published without a person approving it. This keeps the site within Google's spam rules. Under those rules, mass-produced AI content can lose its search traffic and its ads.

## One-time setup (about 30 minutes, no coding)

1. **GitHub.** Create a free account at github.com. Create a new **private** repository called `frontier-desk`, then upload all the files from this folder. Use "Add file → Upload files", and include the hidden `.github` folder.
2. **Claude API key.** Sign up at console.anthropic.com, add billing, and create an API key.
   - In your repository, open **Settings → Secrets and variables → Actions → New repository secret**.
   - Name: `ANTHROPIC_API_KEY`. Value: your key.
3. **Allow the bot to open pull requests.** Go to **Settings → Actions → General → Workflow permissions**. Choose "Read and write permissions" and tick "Allow GitHub Actions to create and approve pull requests".
4. **Turn on the website.** Go to **Settings → Pages → Build and deployment → Source: GitHub Actions**. Free GitHub Pages needs a public repository. If you want to keep the code private, connect the repository to Cloudflare Pages or Netlify instead (both free): build command `pip install -r requirements.txt && python -m web.build`, output folder `public`.
5. **Your details.** Edit `config/settings.yaml` on GitHub: site name, your domain, contact email.
6. **First run.** Open the **Actions** tab, then **News drafts → Run workflow**. A few minutes later a pull request called "AI news drafts to approve" appears. Read it, then merge it.
7. **Custom domain** (optional). Buy a domain, then add it under **Settings → Pages → Custom domain**.

## Everyday use

- **Review drafts.** Open the pull request, click **Files changed** and read each draft. Click the pencil icon to edit one, or the bin icon to drop it. When you're happy, click **Merge pull request**. New drafts pile up in the same pull request until you merge, so you can review once or twice a day.
- **Fix a flagged draft.** The pull request lists what is wrong with it. Fix the text, delete the `problems:` lines, and move the file from `content/flagged/` to `content/articles/`.
- **Correct a published article.** Edit its file in `content/articles/` and save. The site updates in a couple of minutes.
- **Change sources.** Edit `config/sources.yaml`. Check each feed address in your browser first.
- **Change how often it runs.** Edit the `cron` line in `.github/workflows/news.yml`.
- **Write your own article,** such as an "AI for business" guide. Copy any file in `content/articles/`, change the text, and set `ai_drafted: false`.

## Making money

All of this is set in `config/settings.yaml`. Until you fill in a setting, the site shows a placeholder box.

| What | What to do | Where it goes |
|---|---|---|
| Display ads | Apply for Google AdSense once you have 20–30 good articles and some traffic. Paste your publisher ID (`ca-pub-…`) into `adsense_client`. `ads.txt` is created for you. | Top banner, sidebar, between stories, inside articles |
| Newsletter | Create a free list on Beehiiv, Buttondown or Mailchimp. Paste its form address into `newsletter_form_action`. Sell sponsorship once you have readers. | Sidebar signup box |
| Membership | Create two Stripe Payment Links (for example £5 and £12 a month) and paste them into `member_link` and `pro_link`. | Membership band and the free-article limit |
| Affiliate links | Join the affiliate programmes of AI tools you have actually used. List them under `affiliate_tools`. | "AI tools we rate" box |
| Sponsored posts and job ads | Sell these directly once traffic grows. Always label them. | Article pages |

**Note:** the free-article limit runs in the reader's browser. It works as a nudge to subscribe, but it is not a hard paywall. A hard paywall with logins is a later upgrade.

### Before you switch on ads in the UK

- **Privacy policy page.** You need one before applying to AdSense.
- **Cookie consent banner.** It must be Google-certified. You can turn on Google's free one in AdSense under **Privacy & messaging**.
- **AI disclosure.** The site already includes a "How we use AI" page and a disclosure line on every article.

## Costs

- **GitHub, GitHub Pages and Cloudflare Pages:** free.
- **Claude API:** you pay per draft. Each story takes two short calls to Claude: one to draft it and one to fact-check it. Check current prices at anthropic.com/pricing. To control spend, lower `max_drafts_per_run` or run less often.
- **Domain:** about £10 a year.

## For developers

```bash
pip install -r requirements.txt
python -m pytest -q tests          # offline tests (sample feeds, fake Claude)
python -m pipeline.run --dry-run   # see which stories would be drafted (needs internet, no API key)
python -m pipeline.run             # draft for real (needs ANTHROPIC_API_KEY)
python -m web.build                # build the site into public/
```

### Code layout

- `pipeline/fetch.py`: collects stories from feeds and pages.
- `pipeline/choose.py`: filters, de-duplicates, groups and ranks stories.
- `pipeline/writer.py`: Claude prompts, drafting and fact-checking.
- `pipeline/store.py`: saves drafts as Markdown and writes the pull request report.
- `web/`: the site generator (Jinja templates in `web/templates`, styles in `web/static/style.css`).
