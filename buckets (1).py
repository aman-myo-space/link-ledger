"""Topic classification for the MyOperator blog.

Five pillars, each with sub-buckets sharing a hue family so the graph reads
at a glance. Matching runs on title + slug + H2 headings.

Order matters: the first match wins. Case studies and branded posts are
checked first because they can mention any product; AI before WhatsApp
because "AI agent for WhatsApp" is an AI post; WhatsApp before Calling
because WhatsApp posts often mention calls and numbers.

Matching is semantic in the sense that each rule covers the family of terms
the topic is actually written with, not one exact keyword.
"""
import re

CLIENTS = (r"lenskart|darkins|sodexo|berger|itc |e-choupal|maharaja|davaindia|munshi|"
           r"kylas|leadsquared|amazon like|mann ki baat|bajaj|policybazaar|urban ?company|"
           r"nykaa|zomato|swiggy|paytm|razorpay")

RULES = [
    # ---- CASE STUDIES (amber family) ----
    ("Case Studies", "Customer stories", "#f59e0b",
     r"case stud|success stor|customer stor|" + CLIENTS),

    # ---- BRANDED (rose family) ----
    ("Branded", "Awards & recognition", "#e11d48",
     r"award|recognition|badge|top.?rated|listed as|wins? (big|at|best)|best ease of use|capterra|software advice"),
    ("Branded", "Product & company", "#fb7185",
     r"myoperator|heyo ?phone|business ai operator|\bbaio\b|our (product|platform|team)"),

    # ---- AI AGENTS (magenta family) ----
    ("AI Agents", "Voice AI", "#a21caf",
     r"voice ?(ai|bot|agent)|ai voice|ai calling|ai call|callbot|speech (ai|recognition)|"
     r"conversational voice|ivr.{0,15}\bai\b|\bai\b.{0,15}ivr"),
    ("AI Agents", "Chat AI", "#d946ef",
     r"(whatsapp|chat) ?(ai|bot)|chatbot|ai chat|chat agent|messaging ai"),
    ("AI Agents", "AI & automation", "#f0abfc",
     r"\bai\b|a\.i\.|artificial intelligence|machine learning|\bllm\b|\bgpt\b|generative|"
     r"agentic|automat(e|ion|ing).{0,20}(agent|workflow|support|sales)|prompt"),

    # ---- WHATSAPP (green family) ----
    ("WhatsApp", "API & pricing", "#047857",
     r"whatsapp business (api|platform)|wa business api|whatsapp.{0,25}(pricing|price|cost|"
     r"charge|rate|billing|conversation fee)|meta.{0,20}pricing"),
    ("WhatsApp", "Campaigns & broadcast", "#10b981",
     r"bulk whatsapp|whatsapp.{0,20}(broadcast|bulk|campaign|marketing|newsletter|promotion)|"
     r"click to whatsapp|\bctwa\b|whatsapp ads"),
    ("WhatsApp", "Verification & setup", "#34d399",
     r"blue tick|green tick|whatsapp.{0,25}(verif|approval|display name|business profile|"
     r"onboard|setup|set up|link|qr)|whatsapp template"),
    ("WhatsApp", "WhatsApp general", "#6ee7b7",
     r"whatsapp|\bwa\.me\b|messaging app"),

    # ---- CALLING / CUSTOMER COMMUNICATION / LEGACY (blue-slate family) ----
    ("Calling & Comms", "Numbers & telephony", "#1d4ed8",
     r"toll.?free|tollfree|1800|virtual (number|phone|receptionist)|business number|"
     r"second number|\bivr\b|cloud telephony|pbx|epabx|\bdid\b|number series|160 series|"
     r"call (forward|transfer|rout|track|record)"),
    ("Calling & Comms", "Call centre operations", "#3b82f6",
     r"call cent|contact cent|inbound call|outbound call|dialer|agent (script|productivity|"
     r"performance|training)|queue|hold time|first call resolution|\bahts?\b|telecall"),
    ("Calling & Comms", "Customer experience", "#60a5fa",
     r"customer (service|support|experience|satisfaction|retention|loyalty|trust|feedback|"
     r"journey|expectation|care|engagement)|\bcsat\b|\bnps\b|complaint|churn|helpdesk|"
     r"service quality|angry customer"),
    ("Calling & Comms", "Sales & marketing", "#93c5fd",
     r"\bsales\b|lead (gen|manage|nurtur|qualif|captur)|\bcrm\b|marketing|remarketing|"
     r"\bsms\b|missed call|\botp\b|\bdlt\b|campaign|conversion|pitch|prospect|cold call|"
     r"funnel|ecommerce|e-commerce|festival|advertis"),
    ("Calling & Comms", "Business & workplace", "#c7d2fe",
     r"remote|work from home|\bwfh\b|productivity|employee|team|hiring|startup|\bgst\b|"
     r"small business|\bsme\b|entrepreneur|management|tool|app|integration|trend|"
     r"communication|business"),
]
FALLBACK = ("Calling & Comms", "Business & workplace", "#c7d2fe")

PARENT_ORDER = ["AI Agents", "WhatsApp", "Calling & Comms", "Branded", "Case Studies"]
PARENT_COLOUR = {"AI Agents": "#d946ef", "WhatsApp": "#10b981",
                 "Calling & Comms": "#3b82f6", "Branded": "#fb7185", "Case Studies": "#f59e0b"}


def classify(title, slug, h2s):
    """Return (parent, sub, colour). Slug must be the path only, never the full URL:
    the domain contains the brand name and would match every post."""
    # H2 headings are deliberately excluded: CTA headings mention the brand,
    # case studies and chat on nearly every post, which poisons every rule.
    hay = " ".join([title or "", (slug or "").replace("-", " ")]).lower()
    for parent, sub, colour, pat in RULES:
        if re.search(pat, hay):
            return parent, sub, colour
    return FALLBACK
