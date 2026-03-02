"""
Trinity Search Skill — Real Web Search

Uses DuckDuckGo HTML interface (no API key needed).
Scrapes live headlines from cybersecurity news sources.
No fake/hardcoded "topics" presented as current news.
Competitor baseline facts are labeled as such — not live data.
"""
import re
import requests
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False

_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
        '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

_CYBERSEC_SOURCES = [
    {
        'name': 'The Hacker News',
        'url': 'https://thehackernews.com',
        'selector': 'h2.home-title',
    },
    {
        'name': 'Bleeping Computer',
        'url': 'https://www.bleepingcomputer.com/news/security/',
        'selector': 'h4',
    },
    {
        'name': 'CISA Advisories',
        'url': 'https://www.cisa.gov/news-events/cybersecurity-advisories',
        'selector': 'h3',
    },
    {
        'name': 'Krebs on Security',
        'url': 'https://krebsonsecurity.com',
        'selector': 'h2.entry-title',
    },
]

# Stable public knowledge — clearly labeled, not presented as live data
_COMPETITOR_BASELINE = {
    'nessus': {
        'name': 'Nessus by Tenable',
        'price': '$3,000+/year',
        'target': 'Enterprise',
        'weakness': 'Too expensive for SMBs, complex UI',
    },
    'qualys': {
        'name': 'Qualys VMDR',
        'price': '$10,000+/year',
        'target': 'Enterprise',
        'weakness': 'Enterprise-only pricing, requires cloud',
    },
    'openscap': {
        'name': 'OpenSCAP',
        'price': 'Free',
        'target': 'Technical users only',
        'weakness': 'No AI, ugly reports, steep learning curve',
    },
    'rapid7': {
        'name': 'Rapid7 InsightVM',
        'price': '$5,000+/year',
        'target': 'Mid to large enterprise',
        'weakness': 'Expensive, complex setup',
    },
}


class SearchSkill:
    """
    Trinity Search Skill
    Real web search via DuckDuckGo — no API key needed.
    Live headline scraping from cybersecurity news sources.
    Honest about what is live vs cached baseline knowledge.
    """

    name = "search"
    description = "Real web search for cybersecurity news, competitors, clients, market intel"

    def get_tools(self):
        return [
            {
                "name": "search_web",
                "description": "Search the web for any query (real DuckDuckGo results)",
                "params": ["query", "max_results"],
                "needs_approval": False,
            },
            {
                "name": "search_cybersecurity_news",
                "description": "Get real current cybersecurity headlines from live sources",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "search_cis_updates",
                "description": "Check CIS website + search for latest benchmark versions",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "find_potential_clients",
                "description": "Generate targeted prospect search with real web results",
                "params": ["location", "industry"],
                "needs_approval": False,
            },
            {
                "name": "research_competitor",
                "description": "Research competitor using live search + known baseline facts",
                "params": ["competitor_name"],
                "needs_approval": False,
            },
            {
                "name": "search_linkedin_prospects",
                "description": "LinkedIn prospect search strategy for a role/location",
                "params": ["role", "location", "industry"],
                "needs_approval": False,
            },
            {
                "name": "get_market_intelligence",
                "description": "Live market intel via real search + known industry figures",
                "params": [],
                "needs_approval": False,
            },
            {
                "name": "check_source",
                "description": "Check if URL is accessible and return its page title",
                "params": ["url"],
                "needs_approval": False,
            },
        ]

    def execute(self, tool_name, params):
        tool_map = {
            "search_web": self.search_web,
            "search_cybersecurity_news": self.search_cybersecurity_news,
            "search_cis_updates": self.search_cis_updates,
            "find_potential_clients": self.find_potential_clients,
            "research_competitor": self.research_competitor,
            "search_linkedin_prospects": self.search_linkedin_prospects,
            "get_market_intelligence": self.get_market_intelligence,
            "check_source": self.check_source,
        }
        tool = tool_map.get(tool_name)
        if not tool:
            return {"error": f"Unknown tool: {tool_name}", "success": False}
        try:
            return tool(**params)
        except TypeError as e:
            return {"error": f"Wrong params for {tool_name}: {e}", "success": False}
        except Exception as e:
            return {"error": str(e), "success": False}

    # ==========================================
    # CORE SEARCH ENGINE
    # ==========================================

    def _ddg_search(self, query, max_results=5):
        """
        Real DuckDuckGo search via the HTML interface.
        No API key. Returns list of {title, url, snippet}.
        Returns empty list if search fails — never fake results.
        """
        try:
            resp = requests.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query, "b": "", "kl": ""},
                headers=_HEADERS,
                timeout=12,
            )
            resp.raise_for_status()
            results = []

            if HAS_BS4:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for item in soup.select('.result')[:max_results]:
                    title_el = item.select_one('.result__title a')
                    snippet_el = item.select_one('.result__snippet')
                    url_el = item.select_one('.result__url')
                    title = title_el.get_text(strip=True) if title_el else ""
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""
                    url = url_el.get_text(strip=True) if url_el else ""
                    if title:
                        results.append({"title": title, "url": url, "snippet": snippet})
            else:
                # Regex fallback when bs4 not installed
                raw = resp.text
                titles = re.findall(
                    r'class="result__a"[^>]*>(.*?)</a>', raw, re.DOTALL
                )
                snippets = re.findall(
                    r'class="result__snippet"[^>]*>(.*?)</span>', raw, re.DOTALL
                )
                urls = re.findall(
                    r'class="result__url"[^>]*>(.*?)</a>', raw, re.DOTALL
                )
                for i in range(min(max_results, len(titles))):
                    title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                    snippet = (
                        re.sub(r'<[^>]+>', '', snippets[i]).strip()
                        if i < len(snippets) else ""
                    )
                    url = (
                        re.sub(r'<[^>]+>', '', urls[i]).strip()
                        if i < len(urls) else ""
                    )
                    if title:
                        results.append({"title": title, "url": url, "snippet": snippet})

            return results

        except requests.Timeout:
            return []
        except requests.RequestException:
            return []

    def _scrape_headlines(self, url, selector):
        """Scrape headlines from a news page using CSS selector."""
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            if resp.status_code != 200:
                return [], resp.status_code

            if HAS_BS4:
                soup = BeautifulSoup(resp.text, 'html.parser')
                elements = soup.select(selector)[:8]
                headlines = [el.get_text(strip=True) for el in elements]
            else:
                # Regex: extract h2/h3/h4 tags as fallback
                tags = re.findall(r'<h[234][^>]*>(.*?)</h[234]>', resp.text, re.DOTALL)
                headlines = [
                    re.sub(r'<[^>]+>', '', t).strip()
                    for t in tags[:8]
                    if len(re.sub(r'<[^>]+>', '', t).strip()) > 10
                ]

            return [h for h in headlines if len(h) > 10][:5], 200

        except requests.Timeout:
            return [], 0
        except Exception:
            return [], 0

    # ==========================================
    # SEARCH TOOLS — ALL RETURN REAL DATA
    # ==========================================

    def search_web(self, query, max_results=5):
        """Real DuckDuckGo web search."""
        max_results = int(max_results) if max_results else 5
        results = self._ddg_search(query, max_results)
        return {
            "success": True,
            "query": query,
            "results": results,
            "count": len(results),
            "source": "DuckDuckGo HTML",
            "searched_at": datetime.now().isoformat(),
            "note": (
                "Real search results."
                if results
                else "No results returned. DuckDuckGo may have blocked the request — try a shorter query."
            ),
        }

    def search_cybersecurity_news(self):
        """
        Fetch real cybersecurity headlines from live sources.
        Also runs a DuckDuckGo search for today's news.
        Does NOT return hardcoded topic lists.
        """
        all_headlines = []
        source_status = []

        for src in _CYBERSEC_SOURCES:
            headlines, status_code = self._scrape_headlines(src['url'], src['selector'])
            source_status.append({
                "name": src['name'],
                "url": src['url'],
                "accessible": status_code == 200,
                "headlines_found": len(headlines),
            })
            for h in headlines:
                all_headlines.append({"source": src['name'], "headline": h})

        # Supplement with real DuckDuckGo search
        ddg = self._ddg_search("cybersecurity news today", 5)
        for r in ddg:
            all_headlines.append({
                "source": "DuckDuckGo",
                "headline": r["title"],
                "url": r.get("url", ""),
                "snippet": r.get("snippet", ""),
            })

        return {
            "success": True,
            "fetched_at": datetime.now().isoformat(),
            "total_headlines": len(all_headlines),
            "headlines": all_headlines[:20],
            "sources_checked": source_status,
            "data_freshness": "live — fetched right now",
        }

    def check_source(self, url):
        """Check accessibility + extract page title from a URL."""
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            title = ""
            if resp.status_code == 200:
                if HAS_BS4:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    title_el = soup.find('title')
                    title = title_el.get_text(strip=True) if title_el else ""
                else:
                    m = re.search(
                        r'<title[^>]*>(.*?)</title>', resp.text,
                        re.IGNORECASE | re.DOTALL
                    )
                    title = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else ""

            return {
                "success": True,
                "url": url,
                "accessible": resp.status_code == 200,
                "status_code": resp.status_code,
                "page_title": title,
                "response_time_ms": int(resp.elapsed.total_seconds() * 1000),
            }
        except requests.Timeout:
            return {"success": False, "url": url, "accessible": False, "error": "Timeout (10s)"}
        except requests.RequestException as e:
            return {"success": False, "url": url, "accessible": False, "error": str(e)}

    def search_cis_updates(self):
        """Check CIS site + search for latest benchmark versions."""
        site_check = self.check_source("https://www.cisecurity.org/cis-benchmarks")
        search_results = self._ddg_search(
            "CIS benchmark latest version 2025 2026 update release", 5
        )
        return {
            "success": True,
            "checked_at": datetime.now().isoformat(),
            "cis_site_accessible": site_check.get("accessible", False),
            "cis_site_title": site_check.get("page_title", ""),
            "trinity6_implements": [
                "CIS Linux Sections 1-6",
                "CIS Network Controls",
                "CIS Access Controls",
                "CIS Logging Controls",
            ],
            "next_to_implement": [
                "CIS Windows Server",
                "CIS Docker",
                "CIS Kubernetes",
                "CIS AWS Foundations",
            ],
            "live_search_results": search_results,
            "note": (
                "live_search_results are real DuckDuckGo results for latest CIS versions. "
                "trinity6_implements is what the codebase currently covers."
            ),
        }

    def find_potential_clients(self, location="Chennai", industry="any"):
        """
        Generate prospect strategy + real web search for local companies.
        LinkedIn queries are templates (LinkedIn blocks scraping).
        """
        linkedin_searches = [
            f"IT Manager {location}",
            f"CISO {location}",
            f"Compliance Officer {location}",
            f"Information Security {location}",
            f"CTO startup {location}",
        ]

        # Real search for local IT/compliance companies
        query = f"IT companies {location} cybersecurity compliance SMB"
        if industry and industry != "any":
            query = f"{industry} companies {location} cybersecurity compliance"
        real_results = self._ddg_search(query, 5)

        outreach = (
            f"Hi [Name],\n\n"
            f"I noticed you manage IT security at [Company].\n\n"
            f"I built Trinity6, an AI-powered compliance scanner that checks your Linux "
            f"servers against CIS benchmarks and generates professional audit reports in minutes.\n\n"
            f"Most SMBs in {location} spend weeks on manual compliance audits. "
            f"Would you be open to a free audit? No cost, no obligation.\n\n"
            f"David\nTrinity6 — Intelligent Security\ntrinity6.com"
        )

        return {
            "success": True,
            "location": location,
            "industry": industry,
            "linkedin_search_templates": linkedin_searches,
            "web_search_results": real_results,
            "outreach_message": outreach,
            "platforms": [
                "LinkedIn — best for B2B",
                "IndiaMART — SMB contacts",
                f"{location} startup communities",
                "Local IT professional groups",
            ],
            "goal": "5 prospects this week. 1 free audit. 1 paying client.",
            "note": (
                "web_search_results are real companies found via DuckDuckGo. "
                "linkedin_search_templates are manual search queries (LinkedIn blocks bots)."
            ),
        }

    def research_competitor(self, competitor_name):
        """
        Competitor research: baseline facts (clearly labeled) + real live search.
        Never presents stale hardcoded data as current intelligence.
        """
        key = competitor_name.lower().replace(' ', '').replace('-', '')
        baseline = None
        for k, v in _COMPETITOR_BASELINE.items():
            if k in key or key in k:
                baseline = v
                break

        # Always do a real search for current pricing/news
        live = self._ddg_search(
            f"{competitor_name} cybersecurity scanner pricing review 2025", 5
        )

        return {
            "success": True,
            "competitor": competitor_name,
            "baseline_facts": baseline or {"note": "No stored baseline — check live results"},
            "baseline_disclaimer": (
                "Baseline facts are known public data from product pages — "
                "verify pricing as it changes frequently."
            ),
            "live_search_results": live,
            "trinity6_advantages": [
                "Affordable SMB pricing",
                "AI-powered plain-English reports",
                "Local AI — no cloud dependency",
                "Multi-framework single scan",
            ],
            "searched_at": datetime.now().isoformat(),
        }

    def search_linkedin_prospects(self, role="IT Manager", location="Chennai", industry=""):
        """Generate LinkedIn prospect search strategy."""
        queries = [
            f'"{role}" "{location}"',
            f'"{role}" "{location}" compliance',
            f'"CISO" "{location}"',
            f'"Information Security" "{location}"',
        ]
        if industry:
            queries.append(f'"{role}" "{location}" "{industry}"')

        return {
            "success": True,
            "role": role,
            "location": location,
            "industry": industry,
            "linkedin_search_queries": queries,
            "connection_message": (
                f"Hi [Name], I see you manage IT at [Company] in {location}. "
                "I built Trinity6, an AI-powered compliance scanner for SMBs. "
                "Would love to connect."
            ),
            "follow_up_message": (
                "Thanks for connecting! I'd love to offer you a free compliance audit. "
                "Trinity6 generates a full CIS benchmark report in minutes. Interested?"
            ),
            "weekly_target": "20 connection requests, 5 follow-ups, 1 free audit",
            "note": "LinkedIn blocks automated scraping. These are manual search queries.",
        }

    def get_market_intelligence(self):
        """
        Market intel: stable industry figures + real live search.
        Live search results are clearly labeled.
        """
        global_search = self._ddg_search(
            "cybersecurity SMB market size 2025 2026 compliance tools growth", 5
        )
        india_search = self._ddg_search(
            "India cybersecurity market SMB GRC compliance 2025", 3
        )

        return {
            "success": True,
            "searched_at": datetime.now().isoformat(),
            "known_market_figures": {
                "global_cybersecurity": "~$200B by 2028 (Statista/MarketsandMarkets)",
                "grc_market": "~$64B by 2028",
                "smb_security": "Fastest-growing segment",
                "disclaimer": "These are published industry estimates — verify with latest reports.",
            },
            "known_opportunities": [
                "SMBs needing affordable compliance tools",
                "Companies preparing for SOC 2 certification",
                "Healthcare firms needing HIPAA compliance",
                "Finance companies needing PCI DSS help",
                "IT MSPs needing scanner for client audits",
            ],
            "live_global_search": global_search,
            "live_india_search": india_search,
        }
