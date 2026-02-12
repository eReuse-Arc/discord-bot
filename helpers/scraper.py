import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import urljoin
import aiohttp
from bs4 import BeautifulSoup
from constants import SYDNEY_TZ, ARC_BASE, ARC_EVENT_URL_RE


@dataclass
class ArcEventData:
    title: str
    date_str: str
    start_dt: datetime
    end_dt: datetime
    location: str
    location_url: str | None
    week_label: str | None 
    description: str
    register_url: str | None
    hero_image_url: str | None
    page_url: str



def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _parse_mon_16_feb_to_date(day_month: str, now_sydney: datetime) -> datetime.date:
    parts = day_month.strip().split()
    if len(parts) >= 3 and len(parts[0]) == 3:
        day = int(parts[1])
        mon = parts[2]
    elif len(parts) == 2:
        day = int(parts[0])
        mon = parts[1]
    else:
        raise ValueError(f"Unrecognized date format: {day_month!r}")

    month_map = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    month = month_map.get(mon.lower()[:3])
    if not month:
        raise ValueError(f"Unrecognized month: {mon!r}")

    year = now_sydney.year
    candidate = datetime(year, month, day, tzinfo=SYDNEY_TZ).date()

    if candidate < (now_sydney.date() - timedelta(days=30)):
        candidate = datetime(year + 1, month, day, tzinfo=SYDNEY_TZ).date()

    return candidate


def _parse_time_range(time_line: str) -> tuple[tuple[int, int], tuple[int, int]]:
    if "Time:" in time_line:
        time_line = time_line.split("Time:", 1)[1].strip()

    if "|" in time_line:
        _, rhs = time_line.split("|", 1)
    else:
        rhs = time_line

    rhs = rhs.strip()
    m = re.search(r"(\d{1,2}:\d{2}\s*[ap]m)\s*-\s*(\d{1,2}:\d{2}\s*[ap]m)", rhs, re.I)
    if not m:
        raise ValueError(f"Could not parse time range from: {time_line!r}")

    def to_24h(t: str) -> tuple[int, int]:
        t = t.strip().upper().replace("  ", " ")
        dt = datetime.strptime(t, "%I:%M %p")
        return dt.hour, dt.minute

    return to_24h(m.group(1)), to_24h(m.group(2))


def _absolutize(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith("http") else urljoin(ARC_BASE, url)


def scrape_arc_event_html(html: str, page_url: str, now_sydney: datetime) -> ArcEventData:
    soup = BeautifulSoup(html, "lxml")

    title_el = soup.select_one("h1.event-title")
    title = _clean_text(title_el.get_text()) if title_el else "Arc Event"

    subtitle = soup.select_one("p.event-subtitle")
    day_month = None
    if subtitle:
        span = subtitle.find("span")
        if span:
            day_month = _clean_text(span.get_text())
    if not day_month:
        raise ValueError("Could not find event date (event-subtitle span).")

    event_date = _parse_mon_16_feb_to_date(day_month, now_sydney)
    date_str = event_date.strftime("%d/%m/%Y")

    content_div = soup.select_one("div.content.text-left")
    if not content_div:
        raise ValueError("Could not find event content (div.content.text-left).")

    paragraphs = [p.get_text("\n", strip=True) for p in content_div.find_all("p")]
    paragraphs = [_clean_text(p) for p in paragraphs if _clean_text(p)]

    location = ""
    location_url = None

    for ptag in content_div.find_all("p"):
        txt = _clean_text(ptag.get_text(" ", strip=True))
        if "Location:" in txt:
            location = _clean_text(txt.split("Location:", 1)[1])

            a = ptag.find("a")
            if a and a.get("href"):
                location_url = a.get("href").strip()
            break

    if not location:
        raise ValueError("Could not find location.")


    week_label = None
    for p in paragraphs:
        if "When:" in p:
            week_label = _clean_text(p.split("When:", 1)[1])
            break

    if not week_label and subtitle:
        strong = subtitle.find("strong")
        if strong:
            wk = _clean_text(strong.get_text())
            m = re.search(r"WK\s*(\d+)", wk, re.I)
            if m:
                week_label = f"Week {m.group(1)}"


    time_line = ""
    for p in paragraphs:
        if "Time:" in p or p.startswith("🕒"):
            time_line = p
            break
    if not time_line:
        raise ValueError("Could not find time line.")

    (sh, sm), (eh, em) = _parse_time_range(time_line)
    start_dt = datetime(event_date.year, event_date.month, event_date.day, sh, sm, tzinfo=SYDNEY_TZ)
    end_dt = datetime(event_date.year, event_date.month, event_date.day, eh, em, tzinfo=SYDNEY_TZ)

    meta_prefixes = ("📍", "🕒", "📅", "📢")
    desc_lines = [p for p in paragraphs if not p.startswith(meta_prefixes)]
    description = "\n\n".join(desc_lines).strip()

    reg_a = soup.select_one("a.button.feature-button.button-primary")
    register_url = _absolutize(reg_a.get("href")) if reg_a else None

    hero_url = None
    picture = soup.select_one("picture.picture-hero")
    if picture:
        sources = picture.find_all("source")
        for s in sources:
            srcset = s.get("srcset")
            if srcset and "hero-xlarge" in srcset:
                hero_url = _absolutize(srcset.split()[0])
                break
        if not hero_url:
            img = picture.find("img")
            if img and img.get("src"):
                hero_url = _absolutize(img.get("src"))

    return ArcEventData(
        title=title,
        date_str=date_str,
        start_dt=start_dt,
        end_dt=end_dt,
        location=location,
        location_url=location_url,
        week_label=week_label,
        description=description,
        register_url=register_url,
        hero_image_url=hero_url,
        page_url=page_url,
    )



async def fetch_arc_event_data(url: str) -> ArcEventData:
    if not ARC_EVENT_URL_RE.search(url):
        raise ValueError("Please provide a valid Arc event URL (https://www.arc.unsw.edu.au/events/...).")

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
            r.raise_for_status()
            html = await r.text()

    now_sydney = datetime.now(tz=SYDNEY_TZ)
    return scrape_arc_event_html(html, url, now_sydney)


async def fetch_image_bytes(url: str) -> bytes | None:
    if not url:
        return None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as r:
                r.raise_for_status()
                return await r.read()
    except Exception:
        return None
