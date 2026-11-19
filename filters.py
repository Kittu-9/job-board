"""Title, restriction, location and date helpers. Pure functions, no network."""
import html
import re
from datetime import date, datetime, timedelta, timezone

# ---------- software engineering title filter ----------
_EXPLICIT = re.compile(
    r"(?i)\bsoftware\b.*\b(engineer\w*|developer|programmer|architect)\b"
    r"|\b(engineer\w*|developer|programmer|architect)\b.*\bsoftware\b"
    r"|\b(sde|swe|sdet)\b"
)
_ROLE = re.compile(
    r"""(?ix)
      \b(back[\s-]?end|front[\s-]?end|full[\s-]?stack)\b
    | \b(platform|infrastructure|data|ml|mlops|machine\s+learning|ai|cloud|devops|devsecops
        |site\s+reliability|mobile|ios|android|web|ui|firmware|embedded|security|api
        |research|forward\s+deployed|database|big\s+data|compiler|kernel|distributed\s+systems)
      \s+(software\s+)?(engineer|developer)\b
    | \bengineer\s*[,\-–:(]\s*(backend|back[\s-]end|frontend|front[\s-]end|full[\s-]?stack|platform
        |infrastructure|data|machine\s+learning|ml|ai|cloud|mobile|ios|android|web|security)\b
    | \b(sre|developer|programmer)\b
    | \bmember\s+of\s+(the\s+)?technical\s+staff\b
    """
)
# Always excluded, even when the title says "software".
_HARD_EXCLUDE = re.compile(
    r"""(?ix)\b(
      sales | pre[\s-]?sales | recruit\w* | sourcer | marketing | account\s+(executive|manager)
    | business\s+develop\w* | developer\s+(relations|advocate|advocacy|marketing|community)
    | real\s+estate | manager | director | vp | vice\s+president | head\s+of
    )\b"""
)
# Excluded only when the title does not explicitly say software engineer/developer.
_SOFT_EXCLUDE = re.compile(
    r"""(?ix)\b(
      solutions?\s+engineer | support\s+engineer | customer\s+(success|support|engineer|solutions)
    | field\s+(engineer|service|applications?) | mechanical | electrical | civil | hardware
    | manufacturing | chemical | structural | facilities | technician | land\s+developer
    | curriculum | instructional | data\s+cent(er|re)
    )\b"""
)


def is_software_role(title):
    """True when the job title is a hands-on software engineering role."""
    t = " ".join((title or "").split())
    if not t or _HARD_EXCLUDE.search(t):
        return False
    if _EXPLICIT.search(t):
        return True
    return bool(_ROLE.search(t)) and not _SOFT_EXCLUDE.search(t)


# ---------- citizenship / clearance filter ----------
_US = r"(u\.?\s?s\.?(\s?a\.?)?|united\s+states)"
_RESTRICTED = re.compile(
    rf"""(?ix)
      \b(security|secret|top\s+secret|dod|government|federal|public\s+trust|active|current|interim)\s+clearance
    | \bts\s*/\s*sci\b | \bpolygraph\b
    | \bclearance\s+(is\s+)?(required|eligib\w+)
    | \b(obtain|maintain|hold|possess)\s+(and\s+maintain\s+)?[\w\s/.\-]{{0,40}}?\bclearance
    | \b(must|required\s+to|need\s+to)\s+be\s+(a\s+|an\s+)?{_US}\s+citizen
    | \b{_US}\s+citizen(ship)?\s+(is\s+)?(required|only|mandatory)
    | \b(requires?|requirement\s+of)\s+{_US}\s+citizenship
    | \bcitizenship\s+(is\s+)?required
    | \bonly\s+{_US}\s+citizens
    """
)


def strip_html(text):
    text = html.unescape(text or "")
    text = re.sub(r"(?s)<(script|style).*?</\1>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(html.unescape(text).split())


def is_restricted(text):
    """True when the posting text asks for US citizenship or a security clearance."""
    return bool(_RESTRICTED.search(strip_html(text)))


# ---------- location helpers ----------
_STATE_ABBR = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT "
               "NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC").split()
_STATE_NAMES = ("alabama alaska arizona arkansas california colorado connecticut delaware florida "
                "hawaii idaho illinois indiana iowa kansas kentucky louisiana maine maryland "
                "massachusetts michigan minnesota mississippi missouri montana nebraska nevada "
                "new\\s+hampshire new\\s+jersey new\\s+mexico new\\s+york north\\s+carolina "
                "north\\s+dakota ohio oklahoma oregon pennsylvania rhode\\s+island south\\s+carolina "
                "south\\s+dakota tennessee texas utah vermont virginia washington west\\s+virginia "
                "wisconsin wyoming").split()
_US_CITIES = ("san francisco|seattle|austin|boston|chicago|los angeles|palo alto|mountain view|"
              "sunnyvale|san jose|santa clara|menlo park|redmond|bellevue|atlanta|dallas|plano|"
              "denver|nyc|bay area|san diego|houston|charlotte|mclean|irving|bentonville|raleigh|"
              "pittsburgh|phoenix|salt lake city|miami|philadelphia|minneapolis|detroit|nashville|"
              "cupertino|san mateo|foster city|brooklyn|silicon valley")
_US_EXPLICIT = re.compile(r"(?i)\b(united\s+states|usa|u\.s\.a?\.?)(?![a-z])|\bUS\b|^US[\-, ]")
_US_HINT = re.compile(
    r",\s*(" + "|".join(_STATE_ABBR) + r")\b|(?i:\b(" + "|".join(_STATE_NAMES) + r")\b)|(?i:\b("
    + _US_CITIES + r")\b)"
)
_NON_US = re.compile(
    r"""(?ix)\b(
      india|canada|united\s+kingdom|uk|england|scotland|ireland|germany|france|spain|netherlands
    | poland|israel|singapore|japan|china|australia|new\s+zealand|brazil|mexico|costa\s+rica
    | philippines|romania|portugal|sweden|norway|denmark|finland|switzerland|austria|belgium
    | italy|greece|korea|taiwan|vietnam|malaysia|indonesia|thailand|uae|serbia|hungary|czech\w*
    | slovakia|argentina|colombia|chile|emea|apac|latam|europe
    | london|dublin|bangalore|bengaluru|hyderabad|pune|chennai|mumbai|gurgaon|gurugram|noida
    | delhi|toronto|vancouver|montreal|ottawa|waterloo|berlin|munich|paris|amsterdam|tel\s+aviv
    | tokyo|sydney|melbourne|zurich|warsaw|krakow|madrid|barcelona|lisbon|stockholm|shanghai
    | beijing|shenzhen|hong\s+kong|seoul|taipei|sao\s+paulo|são\s+paulo|guadalajara|manila
    | bucharest|belgrade|prague|budapest|dubai|cork|edinburgh|manchester
    )\b"""
)


def is_us_location(loc):
    """True = United States, False = clearly elsewhere, None = cannot tell."""
    loc = loc or ""
    if _US_EXPLICIT.search(loc):
        return True
    if _NON_US.search(loc):
        return False
    if _US_HINT.search(loc):
        return True
    return None


def any_us(locations):
    flags = [is_us_location(l) for l in locations] or [None]
    if any(f is True for f in flags):
        return True
    if all(f is False for f in flags):
        return False
    return None


def is_remote(text):
    return bool(re.search(r"(?i)\bremote\b", text or ""))


# ---------- dates ----------
def parse_date(value, today=None):
    """Return an ISO date string (YYYY-MM-DD) or None from the formats the feeds use."""
    today = today or datetime.now(timezone.utc).date()
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        secs = value / 1000 if value > 1e11 else value
        return datetime.fromtimestamp(secs, timezone.utc).date().isoformat()
    s = str(value).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return m.group(0)
    low = s.lower()
    if "today" in low or "just posted" in low:
        return today.isoformat()
    if "yesterday" in low:
        return (today - timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s+day", low)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            pass
    return None
