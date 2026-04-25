# agent.py
"""
Market Research Agent with structured report template.
Generates professional newsletter-style HTML reports.
"""

import re
import time
from urllib.parse import parse_qs, unquote, urlparse
from typing import List, Dict, Any, Callable, Optional
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

# ============================================================================
# Configuration
# ============================================================================
import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash-exp"
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# Default settings (can be overridden)
DEFAULT_SETTINGS = {
    'max_search_results': 5,
    'scrape_timeout': 10,
    'search_timeout': 15,
    'polite_delay': 1.5,
    'temperature': 0.3,
}

client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================================
# Web Search Tool
# ============================================================================
class WebSearchTool:
    def __init__(self, timeout=15, status_callback: Optional[Callable] = None):
        self.timeout = timeout
        self.status_callback = status_callback
        
    def _log(self, message: str):
        if self.status_callback:
            self.status_callback(message)
    
    def _sanitize_query(self, query: str) -> str:
        return re.sub(r'[<>"\']', "", query.strip())
    
    def _validate_url(self, string: str) -> bool:
        url_regex = re.compile(
            r"^(https?:\/\/)?(www\.)?([a-zA-Z0-9.-]+)(\.[a-zA-Z]{2,})?(:\d+)?(\/[^\s]*)?$",
            re.IGNORECASE,
        )
        return bool(url_regex.match(string))
    
    def _ensure_url(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        if not self._validate_url(url):
            raise ValueError(f"Invalid URL: {url}")
        return url
    
    def search(self, query: str, max_results: int) -> List[Dict[str, str]]:
        self._log(f"🔍 Searching DuckDuckGo for: '{query}'")
        
        query = self._sanitize_query(query)
        if not query:
            self._log("❌ Empty search query")
            return []
        
        headers = {"User-Agent": USER_AGENT}
        params = {"q": query, "kl": "us-en"}
        url = "https://html.duckduckgo.com/html/"
        
        try:
            self._log("📡 Sending search request...")
            response = requests.post(url, data=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            self._log("✅ Search request successful")
        except requests.RequestException as e:
            self._log(f"❌ Search request failed: {e}")
            return []
        
        if not response.text or "text/html" not in response.headers.get("content-type", "").lower():
            self._log("❌ No valid search results found")
            return []
        
        soup = BeautifulSoup(response.text, "html.parser")
        results = []
        
        self._log(f"🔎 Parsing search results (max {max_results})...")
        
        for idx, result in enumerate(soup.select("div.result")[:max_results], 1):
            title_tag = result.select_one("a.result__a")
            snippet_tag = result.select_one("a.result__snippet")
            
            if title_tag:
                raw_link = title_tag.get("href", "")
                parsed = urlparse(raw_link)
                uddg = parse_qs(parsed.query).get("uddg", [""])[0]
                decoded_link = unquote(uddg) if uddg else raw_link
                
                try:
                    final_url = self._ensure_url(decoded_link)
                except ValueError:
                    continue
                
                title = title_tag.get_text(strip=True)[:80]
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "url": final_url,
                    "snippet": snippet_tag.get_text(strip=True) if snippet_tag else ""
                })
                self._log(f"  ✓ Result {idx}: {title}")
        
        self._log(f"✅ Found {len(results)} search results")
        return results


# ============================================================================
# URL Scraper Tool
# ============================================================================
class URLScraperTool:
    def __init__(self, timeout=10, status_callback: Optional[Callable] = None):
        self.timeout = timeout
        self.status_callback = status_callback
    
    def _log(self, message: str):
        if self.status_callback:
            self.status_callback(message)
    
    def _validate_url(self, url: str) -> bool:
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    def scrape(self, url: str) -> Dict[str, Any]:
        domain = urlparse(url).netloc
        self._log(f"📄 Scraping: {domain}")
        
        if not self._validate_url(url):
            self._log(f"  ❌ Invalid URL: {domain}")
            return {"url": url, "content": "", "status": "error", "error": "Invalid URL"}
        
        headers = {
            'User-Agent': USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'noscript', 'meta']):
                element.decompose()
            
            content_parts = []
            title = soup.find('title')
            if title:
                content_parts.append(f"TITLE: {title.get_text().strip()}")
            
            main_content = (soup.find('main') or soup.find('article') or 
                          soup.find('div', class_=re.compile('content|main|body', re.I)) or
                          soup.find('body') or soup)
            
            for element in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
                text = element.get_text(separator=' ', strip=True)
                if text and len(text) > 10:
                    content_parts.append(text)
            
            full_content = '\n\n'.join(content_parts)
            full_content = re.sub(r'\n\s*\n\s*\n', '\n\n', full_content)
            full_content = re.sub(r'[ \t]+', ' ', full_content)
            
           #char_count = len(full_content.strip()[:5000])
            char_count = len(full_content.strip())
            self._log(f"  ✅ Scraped {char_count} characters from {domain}")
            
            return {
                "url": url,
                #"content": full_content.strip()[:5000],
                "content": full_content.strip(),
                "status": "success",
                "title": title.get_text().strip() if title else ""
            }
            
        except Exception as e:
            self._log(f"  ❌ Error scraping {domain}: {str(e)[:50]}")
            return {"url": url, "content": "", "status": "error", "error": str(e)}


# ============================================================================
# Report Template Generator
# ============================================================================
def generate_market_report(query: str, collected_data: List[Dict[str, str]], 
                          status_callback: Optional[Callable] = None,
                          temperature: float = 0.3) -> str:
    """Generate structured HTML report following exact template."""
    
    def _log(msg):
        if status_callback:
            status_callback(msg)
    
    _log(f"🤖 Preparing data for AI analysis...")
    _log(f"📊 Analyzing {len(collected_data)} sources...")
    
    sources_text = ""
    for idx, item in enumerate(collected_data, 1):
        sources_text += f"\n\n--- Source {idx} ---\n"
        sources_text += f"Title: {item.get('title', 'N/A')}\n"
        sources_text += f"URL: {item.get('url', 'N/A')}\n"
        sources_text += f"Content: {item.get('content', 'N/A')[:2000]}\n"
    
    current_date = datetime.now().strftime("%B %d, %Y")
    
    prompt = f"""You are a professional market research analyst. Generate a comprehensive HTML market research report for: "{query}"

CRITICAL: Follow this EXACT structure and format. Output ONLY valid HTML with inline CSS.

Structure Requirements:

1. EXECUTIVE SUMMARY
   - Brief overview (150-250 words)
   - Key findings paragraph
   - Total market size, growth rate, main drivers

2. MARKET OVERVIEW
   2.1 Global Market Breakdown (HTML TABLE):
   | Category/Type | Market Share (%) | Key Features | CAGR (%) |
   
   2.2 Sector-Wise Distribution (HTML TABLE):
   | Sector | Total Market Share (%) | Category/Type Share (%) | Key Applications |
   
   2.3 Adoption & Usage Trends (HTML TABLE):
   | Sector | Traditional/Legacy Share (%) | Modern/New Tech Share (%) | Key Drivers |

3. REGIONAL INSIGHTS
   - Bullet points highlighting emerging vs developed regions

4. KEY PLAYERS (HTML TABLE):
   | Segment | Key Players | Strengths |

5. CHALLENGES / RISKS
   - Bullet points on challenges, risks, limitations

6. FUTURE OUTLOOK / PROJECTIONS
   6.1 Comparative Projections (HTML TABLE):
   | Region | Market Size (USD Bn) | CAGR (%) | Year Range |
   
   6.2 Market Share Contribution (HTML TABLE):
   | Year | Region/Country Share (%) |
   
   6.3 Sector-Wise Growth (HTML TABLE):
   | Sector | Projected Market Share (%) | Key Applications |

7. CONCLUSION
   - Summarize opportunities and risks
   - Emerging trends and stakeholder implications

8. REFERENCES
   - List all source URLs as hyperlinks

CSS STYLING REQUIREMENTS:
- Professional newsletter design with colors, padding, borders
- Tables: borders, zebra stripes, header styling
- Headings: hierarchical sizing, colors
- Clean spacing and typography
- Responsive layout

If data is missing: Use "NA" and note "Insufficient public data"

Date: {current_date}
Prepared by: AI Market Research Agent

Sources:
{sources_text}

Generate ONLY the complete HTML (no markdown, no commentary):"""

    try:
        _log("🧠 Generating structured report with Gemini AI...")
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                temperature=temperature,
            )
        )
        _log("✅ Report generation complete!")
        return response.text
    except Exception as e:
        _log(f"❌ Error generating report: {str(e)}")
        return f"<html><body><h1>Error Generating Report</h1><p>{str(e)}</p></body></html>"


# ============================================================================
# Main Agent Function
# ============================================================================
def run_agent(query: str, settings: Dict[str, Any] = None, 
              priority_websites: List[str] = None,
              status_callback: Optional[Callable] = None) -> str:
    """
    Main agent pipeline with configurable settings and priority websites.
    
    Args:
        query: Search query string
        settings: Dictionary with configuration (max_search_results, timeouts, etc.)
        priority_websites: List of websites to search first (e.g., ['timesofindia.com', 'bbc.com'])
        status_callback: Function to call with status updates
        
    Returns:
        HTML string containing the formatted market research report
    """
    # Merge default settings with user settings
    config = {**DEFAULT_SETTINGS, **(settings or {})}
    priority_sites = priority_websites or []
    
    def _log(msg):
        if status_callback:
            status_callback(msg)
    
    _log("🚀 Starting market research agent...")
    _log(f"📝 Query: '{query}'")
    _log(f"⚙️ Settings: Max results={config['max_search_results']}, Timeout={config['search_timeout']}s")
    
    if priority_sites:
        _log(f"🎯 Priority websites enabled: {', '.join(priority_sites)}")
    
    _log("=" * 50)
    
    # Step 1: Web Search (with priority websites first)
    _log("\n🔍 STEP 1: Web Search")
    search_tool = WebSearchTool(timeout=config['search_timeout'], status_callback=status_callback)
    
    all_results = []
    
    # Search priority websites first if enabled
    if priority_sites:
        for priority_site in priority_sites:
            priority_query = f"site:{priority_site} {query}"
            _log(f"🎯 Searching priority site: {priority_site}")
            try:
                priority_results = search_tool.search(priority_query, max_results=2)
                if priority_results:
                    all_results.extend(priority_results)
                    _log(f"  ✅ Found {len(priority_results)} results from {priority_site}")
                else:
                    _log(f"  ⚠️ No results from {priority_site}")
            except Exception as e:
                _log(f"  ❌ Error searching {priority_site}: {str(e)[:50]}")
    
    # Then do general search to fill remaining slots
    remaining_slots = config['max_search_results'] - len(all_results)
    if remaining_slots > 0:
        _log(f"🔍 Performing general search for {remaining_slots} more results...")
        try:
            general_results = search_tool.search(query, max_results=remaining_slots)
            all_results.extend(general_results)
        except Exception as e:
            _log(f"❌ General search error: {str(e)}")
    
    # Limit to max configured results and deduplicate
    seen_urls = set()
    search_results = []
    for result in all_results:
        if result['url'] not in seen_urls:
            search_results.append(result)
            seen_urls.add(result['url'])
        if len(search_results) >= config['max_search_results']:
            break
    
    if not search_results:
        _log("❌ Pipeline stopped: No search results")
        return "<html><body><h1>No Search Results</h1><p>Could not find relevant information.</p></body></html>"
    
    _log(f"✅ Total unique search results: {len(search_results)}")
    
    # Step 2: Scrape URLs
    _log(f"\n📄 STEP 2: Scraping {len(search_results)} URLs")
    scraper_tool = URLScraperTool(timeout=config['scrape_timeout'], status_callback=status_callback)
    collected_data = []
    
    for idx, result in enumerate(search_results, 1):
        scraped = scraper_tool.scrape(result['url'])
        
        if scraped['status'] == 'success' and scraped['content']:
            collected_data.append({
                'title': result.get('title', scraped.get('title', 'Untitled')),
                'url': result['url'],
                'snippet': result.get('snippet', ''),
                'content': scraped['content']
            })
        
        # Polite delay between requests
        if idx < len(search_results):
            _log(f"⏳ Waiting {config['polite_delay']}s before next request...")
            time.sleep(config['polite_delay'])
    
    if not collected_data:
        _log("❌ Pipeline stopped: No content retrieved")
        return "<html><body><h1>Scraping Failed</h1><p>Could not retrieve content from search results.</p></body></html>"
    
    _log(f"✅ Successfully scraped {len(collected_data)} sources")
    
    # Step 3: Generate Report
    _log("\n🤖 STEP 3: AI Report Generation")
    try:
        report_html = generate_market_report(
            query, 
            collected_data, 
            status_callback=status_callback,
            temperature=config['temperature']
        )
    except Exception as e:
        _log(f"❌ Report generation failed: {str(e)}")
        return f"<html><body><h1>Report Generation Error</h1><p>{str(e)}</p></body></html>"
    
    _log("\n" + "=" * 50)
    _log("🎉 Market research report complete!")
    
    return report_html
