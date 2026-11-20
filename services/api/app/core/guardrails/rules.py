"""Deterministic multi-category rule engine for financial advisory guardrails."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.guardrails.normalizer import NormalizedText, normalize_text

# Markers indicating a sentence explicitly audits, critiques, or warns about
# a third-party claim rather than endorsing it.
_AUDIT_FRAME_RE = re.compile(
    r"\b(?:"
    r"red[- ]?flags?|scams?|frauds?|misleading|unverified|unregulated|"
    r"violates?|violation|warnings?\s+(?:signs?|about|against)|"
    r"warns?\s+against|cautions?\s+(?:against|retail|investors?)|cautionary|beware|"
    r"never\s+trust|avoid\s+(?:posts?|messages?|claims?|tips?|calls?)|"
    r"flags?(?:\s+(?:this|such))?|flagged(?:\s+as)?|marks?\s+such|marked\s+as|extract(?:ed)?\s+claim|"
    r"claim\s+extracted|historical\s+resolution|failed\s+to\s+reach|"
    r"did\s+not\s+reach|brier\s+score|accuracy\s+score|audit(?:ing|ed)?|"
    r"example\s+of\s+(?:a|an)\s+(?:urgency|red[- ]?flag|misleading|pump|tip|spam|prohibited)|"
    r"sebi\s+(?:warns?|cautions?|prohibits?|bans?|regulates?)|"
    r"hallmark\s+of"
    r")\b",
    re.IGNORECASE,
)

# Endorsement / action cues that disqualify a sentence from quote-audit masking.
_ENDORSEMENT_OUTSIDE_QUOTE_RE = re.compile(
    r"\b(?:"
    r"you\s+should|i\s+agree|solid\s+call|good\s+call|follow\s+(?:this|his|her|their)|"
    r"do\s+this|try\s+this|worth\s+buying|smart\s+move|go\s+ahead"
    r")\b",
    re.IGNORECASE,
)

# Trojan-horse disclaimers that must NEVER grant educational exemption.
_TROJAN_DISCLAIMER_RE = re.compile(
    r"\b(?:"
    r"for\s+educational\s+purposes?\s+only|purely\s+educational|education\s+only|"
    r"not\s+(?:a\s+)?(?:financial|investment|trading|sebi)\s+advice|"
    r"not\s+(?:a\s+)?recommendation|no\s+advice\s+intended|"
    r"purely\s+hypothetical|disclaimer\s*:|\bnfa\b|\bdyor\b"
    r")\b",
    re.IGNORECASE,
)

# Platform/policy statements describing what PaisaProof does NOT do.
_POLICY_NEGATION_RE = re.compile(
    r"\b(?:paisaproof|this\s+platform|the\s+platform|our\s+platform|the\s+app|we)\s+"
    r"(?:is\s+an\s+educational\b[^.;\n]{0,80}\band\s+)?"
    r"(?:does\s+not|do\s+not|never|will\s+not|cannot)\s+"
    r"(?:provide|give|offer|issue|make|publish|recommend)\b"
    r"(?:(?!(?:\bbut\b|\bhowever\b|\byet\b|\bexcept\b|[.;\n])).){0,160}",
    re.IGNORECASE,
)

# Quoted substrings ('...' or "...") used inside audited third-party references.
# Negative lookaround on single quotes prevents matching apostrophes in contractions.
_QUOTED_SPAN_RE = re.compile(
    r"(?<![a-zA-Z0-9])'(?:[^'\\]|\\.){3,280}'(?![a-zA-Z0-9])|"
    r'"(?:[^"\\]|\\.){3,280}"'
)

# Conceptual definitions that mention financial terms without prescribing trades.
_BENIGN_CONCEPT_PHRASES_RE = re.compile(
    r"\b(?:"
    r"(?:a|an|the|in\s+a)?\s*buy[- ]and[- ]hold\s+"
    r"(?:strategy|approach|investing|investment|method|philosophy|style|principle|"
    r"is\b|means\b|refers\s+to)|"
    r"stop[- ]?loss\s+(?:order|orders|level|levels|mechanism|rule|is\b|helps?\b|limits?\b)|"
    r"(?:target\s+prices?|price\s+targets?)\s+"
    r"(?:are|is|represent|refer\s+to|estimates?|not\s+guarantees)|"
    r"multibagger\s+(?:is\s+a\s+term|refers\s+to|means|coined\s+by)|"
    r"upper\s+circuit\s+(?:limit|limits|band|mechanism|is\b|halts?\b)"
    r")\b",
    re.IGNORECASE,
)

# Cautionary/negated warnings about prohibited claims (no ticker action allowed).
_CAUTIONARY_CLAUSE_RE = re.compile(
    r"\b(?:"
    r"never\s+(?:trust|follow|believe|rely\s+on|fall\s+for)|"
    r"do\s+not\s+(?:trust|follow|believe|rely\s+on)|"
    r"avoid\s+(?:tips?|calls?|claims?|promises?|messages?)|"
    r"beware\s+of|cautions?\s+(?:investors?|retail|against)|"
    r"warns?\s+against|no\s+(?:legitimate|stock|investment|strategy)\s+"
    r"(?:can\s+)?(?:offer|offers|guarantee|guarantees|promise|promises)|"
    r"not\s+(?:risk[- ]?free|guaranteed)|"
    r"red\s+flags?\s+(?:include|like|such\s+as)|"
    r"hallmark\s+of\s+(?:unregulated|fraudulent|scam)"
    r")\b"
    r"(?:(?!(?:\bbut\b|\bhowever\b|[.;\n])).){0,160}",
    re.IGNORECASE,
)

# Historical past-tense price movement reporting (not a forward target).
_HISTORICAL_FACT_RE = re.compile(
    r"\b(?:rose|gained|fell|dropped|declined|rallied|surged|slumped|doubled|tripled|"
    r"delivered|returned|touched|reached|hit)\s+"
    r"(?:by\s+|nearly\s+|around\s+|over\s+)?"
    r"(?:₹|rs\.?|inr)?\s*\d[\d,]*(?:\.\d+)?%?"
    r"[^.\n]{0,80}\b"
    r"(?:in\s+(?:q[1-4]|fy\d{2,4}|20\d{2}|19\d{2}|january|february|march|april|"
    r"may|june|july|september|october|november|december|july|august)|"
    r"between\s+(?:19|20)\d{2}\s+and\s+(?:19|20)\d{2}|"
    r"last\s+(?:year|quarter|month|week|decade)|historically|previously|earlier)\b",
    re.IGNORECASE,
)

# Tokens that should NEVER appear solely via obfuscation/homoglyphs/leetspeak.
_OBFUSCATED_TRIGGER_TOKENS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("directive_en", re.compile(r"\b(?:buy|sell|hold|buynow|sellnow|holdnow)\b")),
    ("directive_hinglish", re.compile(r"\b(?:kharido|kharid|khareedo|becho|bech)\b")),
    ("price_target", re.compile(r"\b(?:target|stoploss)\b")),
    ("guaranteed_return", re.compile(r"\b(?:pakka|guaranteed)\b")),
)


@dataclass(frozen=True, slots=True)
class RuleSpec:
    """Single compiled rule mapped to a canonical guardrail reason code."""

    reason: str
    pattern: re.Pattern[str]
    use_original_case: bool = False
    check_shadows: bool = True


def _compile(
    reason: str,
    pattern: str,
    *,
    ignore_case: bool = True,
    use_original_case: bool = False,
    check_shadows: bool = True,
) -> RuleSpec:
    flags = re.IGNORECASE if ignore_case else 0
    return RuleSpec(
        reason=reason,
        pattern=re.compile(pattern, flags),
        use_original_case=use_original_case,
        check_shadows=check_shadows,
    )


_RULES: tuple[RuleSpec, ...] = (
    # ------------------------------------------------------------------
    # 1. English directives (directive_en)
    # ------------------------------------------------------------------
    _compile(
        "directive_en",
        r"\b(?:"
        r"strong\s*buy|strong\s*sell|buy\s*now|sell\s*now|hold\s*now|"
        r"buy\s*call|sell\s*call|hold\s*call|intraday\s*(?:buy|sell|call)|"
        r"swing\s*(?:trade\s*)?(?:buy|sell|call)|positional\s*(?:buy|sell)|"
        r"delivery\s*(?:buy|call)|breakout\s*buy|momentum\s*buy|"
        r"btst|stbt|enter\s+at\s+cmp|buy\s+at\s+cmp|sell\s+at\s+cmp|"
        r"book\s+profits?|profit\s+booking|exit\s+immediately|exit\s+now|"
        r"dump\s+(?:this|the)\s+stock|load\s*up\s*on|average\s+down(?:\s+on)?|"
        r"add\s+(?:\S+\s+){1,4}to\s+(?:your\s+)?portfolio|"
        r"go(?:ing)?\s+(?:long|short)\s+on|initiate\s+(?:a\s+)?(?:long|short|buy|sell)|"
        r"buy\s+(?:on\s+)?(?:every\s+)?dips?|buy\s+the\s+dip|accumulate\s+on\s+dips?|"
        r"keep\s+holding|continue\s+holding|stay\s+invested\s+in|"
        r"hold\s+(?:\S+\s+){1,4}for\s+\d+\s*(?:days?|weeks?|months?|years?)|"
        r"pick\s+up\s+shares\s+of|grab\s+shares\s+of|"
        r"worth\s+(?:buying|selling|holding|accumulating|picking\s+up|grabbing|adding)|"
        r"buy\s+\d+\s+shares|sell\s+(?:all\s+)?your\s+(?:\S+\s+)?shares"
        r")\b",
    ),
    _compile(
        "directive_en",
        r"(?:^|[.!?;:\n]\s*)(?i:please\s+|just\s+|now\s+|definitely\s+|immediately\s+)?"
        r"(?i:buy|sell|hold|accumulate|exit|dump|liquidate|trim|short)\s+"
        r"(?:(?i:shares\s+of|into)\s+)?"
        r"(?!Side\b|Orders?\b|Limits?\b|Zones?\b|Signals?\b|Alerts?\b|Volumes?\b|Pressures?\b)"
        r"[A-Z][A-Za-z0-9&.-]{1,}",
        ignore_case=False,
        use_original_case=True,
        check_shadows=False,
    ),
    _compile(
        "directive_en",
        r"\b(?:you\s+(?:should|must|can|could|need\s+to|ought\s+to|better)|"
        r"(?:traders?|investors?|everyone|readers?)\s+(?:should|must|can)|"
        r"(?:i|we)\s+(?:advise|urge|suggest|tell)\s+(?:you\s+)?to|"
        r"(?:(?:good|great|right|best|ideal)\s+)?time\s+to|"
        r"advisable\s+to|smart\s+(?:move\s+)?to|wise\s+to)\s+"
        r"(?:definitely\s+|immediately\s+|quickly\s+|now\s+|consider\s+)?"
        r"(?:buy|buying|sell|selling|hold|holding|accumulate|accumulating|"
        r"exit|exiting|dump|dumping|short|shorting|load\s+up|book\s+profits?|"
        r"average\s+down|enter\s+into|pick\s+up|grab)\b",
    ),
    _compile(
        "directive_en",
        r"\b(?:buy|sell|hold|accumulate|exit|dump|enter)\s+"
        r"(?:\S+\s+){1,4}"
        r"(?:right\s+now|today|tomorrow|immediately|at\s+cmp|around\s+(?:₹|rs\.?)?\s*\d|"
        r"near\s+(?:₹|rs\.?)?\s*\d|below\s+(?:₹|rs\.?)?\s*\d|above\s+(?:₹|rs\.?)?\s*\d|"
        r"before\s+(?:earnings|results|budget|expiry|friday|monday|tuesday|wednesday|"
        r"thursday|open|close)|"
        r"for\s+(?:long\s+term|short\s+term|multibagger|quick\s+gains?))\b",
    ),
    _compile(
        "directive_en",
        r"\b(?:buynow|sellnow|holdnow|strongbuy|strongsell|bookprofits?|exitnow)\b",
    ),
    # ------------------------------------------------------------------
    # 2. Hinglish & Devanagari directives (directive_hinglish)
    # ------------------------------------------------------------------
    _compile(
        "directive_hinglish",
        r"\b(?:"
        r"khar(?:i|ee?)d(?:o|na\s*chahiye|\s*lo|\s*le(?:na)?|\s*sakte)?|"
        r"le\s*lo|lelo|le\s+lena|le\s+sakte|"
        r"utha\s*lo|uthao|utha\s*le(?:na)?|"
        r"bech\s*do|becho|bech\s*de(?:na)?|bechna\s*chahiye|bech\s*ke\s*nikal|"
        r"hold\s*(?:kar(?:o|\s*lo|\s*le|\s*rakh(?:o)?)|rakh(?:o|na)?)|"
        r"rakh\s*lo|ko\s+rakh(?:o|\s*lo)|"
        r"rakh(?:o|lo)\s+(?:bhai\s+|yaar\s+)?(?:apne\s+)?portfolio\s+mein|"
        r"pais[ae]\s*(?:laga(?:o|\s*do)?|daal\s*do|dal\s*do)|"
        r"daal\s*do|dal\s*do|invest\s*kar(?:\s*do|o)|"
        r"nikal\s*ja(?:o)?|niklo|book\s*kar\s*lo|profit\s*book\s*kar(?:o|lo)|"
        r"entry\s*(?:le\s*lo|kar\s*lo|maaro)|average\s*kar\s*lo|"
        r"chup\s*chap\s+(?:\S+\s+){0,3}(?:le|utha|kharid|khareed|daal|laga|hold|bech)|"
        r"(?:jaldi|abhi|turant)\s+(?:se\s+)?(?:\S+\s+){0,2}"
        r"(?:le\s*lo|utha\s*lo|kharido|khareedo|becho|bech\s*do|nikal\s*jao|book\s*karo)|"
        r"bhaag(?:ega|ne\s*wala)|udega|fatega|rocketing\s+soon"
        r")\b",
    ),
    _compile(
        "directive_hinglish",
        r"(?:"
        r"ख[़]?रीद(?:ो|ना\s*चाहिए|\s*लो|\s*लें|\s*सकते)|"
        r"ले\s*लो|ले\s*लें|उठा\s*लो|उठाओ|उठा\s*लें|"
        r"बेच\s*दो|बेचो|बेच\s*दें|बेचना\s*चाहिए|"
        r"होल्ड\s*कर(?:ो|ें|\s*लो|\s*रखो)|रख\s*लो|"
        r"(?:पैस[ाे]|रुपय[ेा]|फंड)\s*(?:लगाओ|लगा\s*दें|डाल\s*दो|डालें)|"
        r"(?:में|मे)\s+\d+(?:\s+\S+){0,2}\s*(?:डाल\s*दो|लगा\s*दो)|"
        r"निवेश\s*कर(?:ो|ें)|निकल\s*जा(?:ओ|एं)|"
        r"बुक\s*कर\s*(?:लो|लें)|प्रॉफिट\s*बुक|"
        r"स्टॉप\s*लॉस|टारगेट|पक्का\s*(?:प्रॉफिट|रिटर्न|मुनाफा)|"
        r"अपर\s*सर्किट|मल्टीबैगर|डबल\s*हो\s*जाएगा|दोगुना|"
        r"रॉकेट\s*बनेगा|जैकपॉट|पार\s*करेगा|क्रॉस\s*करेगा|तक\s*जाएगा|छू\s*लेगा"
        r")",
        ignore_case=False,
        check_shadows=False,
    ),
    # ------------------------------------------------------------------
    # 3. Price targets & stop-loss prescriptions (price_target)
    # ------------------------------------------------------------------
    _compile(
        "price_target",
        r"\b(?:target\s*price|price\s*target|next\s*target|first\s*target|"
        r"second\s*target|final\s*target|upside\s*target|downside\s*target|"
        r"short[- ]term\s*target|long[- ]term\s*target)\s*"
        r"(?:(?:for|on|in|of)\s+(?:\S+\s+){1,4})?"
        r"(?:is|of|at|near|around|:|=|-)?\s*(?:₹|rs\.?|inr)?\s*\d+",
    ),
    _compile(
        "price_target",
        r"\b(?:tp|tgt|t1|t2|sl|stoploss|stop[- ]?loss)\s*"
        r"(?:is|of|at|below|above|near|around|:|=|-|@)?\s*"
        r"(?:₹|rs\.?|inr)?\s*\d+",
    ),
    _compile(
        "price_target",
        r"\btargets?\s*(?::|=|@|of|is|at|near|around)?\s*(?:₹|rs\.?|inr)\s*\d+|"
        r"\btargets?\s*(?::|=|@|of|at)\s*\d+(?:,\d+)*(?:\.\d+)?\b|"
        r"\btargets?\s+\d{2,}(?:,\d+)*(?:\.\d+)?\b",
    ),
    _compile(
        "price_target",
        r"\b(?:will|can|could|may|might|likely\s+to|expected\s+to|set\s+to|"
        r"poised\s+to|going\s+to|ready\s+to|bound\s+to|about\s+to)\s+"
        r"(?:hit|reach|touch|cross|break|test|reclaim|surge\s+to|rally\s+to|"
        r"jump\s+to|climb\s+to|shoot\s+to|fall\s+to|drop\s+to|slip\s+to)\s+"
        r"(?:levels?\s+of\s+)?(?:₹|rs\.?|inr)?\s*\d+",
    ),
    _compile(
        "price_target",
        r"\b(?:upside|downside|potential\s+gain|expected\s+return|price\s+move)\s+"
        r"(?:of|up\s+to|around|at\s+least)?\s*\d+(?:\.\d+)?\s*%|\b\d+(?:\.\d+)?\s*%\s+"
        r"(?:upside|downside|upside\s+potential|expected\s+gain|rally\s+ahead)\b|"
        r"\b(?:upside|downside)\s+(?:to|towards)\s+(?:₹|rs\.?|inr)?\s*\d+",
    ),
    _compile(
        "price_target",
        r"(?:₹|rs\.?|inr)?\s*\d+(?:,\d+)*\s*"
        r"(?:tak\s*(?:jayega|ja\s*sakta|pahunch(?:ega)?)|"
        r"cross\s*karega|paar\s*karega|touch\s*karega|hit\s*karega|todega)\b",
    ),
    _compile(
        "price_target",
        r"\b(?:multibagger|double\s+ho\s+jayega|triple\s+ho\s+jayega|"
        r"double\s+your\s+money|triple\s+your\s+money|"
        r"(?:2x|3x|4x|5x|10x|20x|50x|100x)"
        r"(?!\s*(?:p/?e|p/?b|ev/?ebitda|earnings|sales|revenue|book|multiple|valuation|leverage)\b)"
        r"(?:\s+(?:returns?|gains?|upside|potential|stock|pick|wealth|money|in\s+\d+|within\s+\d+)|(?=[.!?,;\s]|$))|"
        r"(?:become|turn|deliver|give|make)\s+(?:\S+\s+){0,2}(?:2x|3x|5x|10x|double|triple))\b",
    ),
    # ------------------------------------------------------------------
    # 4. Stock recommendations & rankings (stock_recommendation)
    # ------------------------------------------------------------------
    _compile(
        "stock_recommendation",
        r"\b(?:"
        r"(?:best|top|finest|no\.?\s*1|number\s+1|number\s+one)\s+"
        r"(?:\d+\s+)?(?:stocks?|shares?|picks?|bets?|buys?)\s+"
        r"(?:to\s+(?:buy|invest|hold|own|accumulate|pick)|"
        r"for\s+(?:202\d|long\s+term|short\s+term|next\s+year|diwali|muhurat|tomorrow|today|gains?)|"
        r"right\s+now)|"
        r"top\s+\d+\s+(?:stocks?|shares?|picks?|buys?|investments?)|"
        r"must[- ]?(?:buy|have|own)\s+(?:stocks?|shares?|picks?)|"
        r"(?:stock|pick|share)\s+of\s+the\s+(?:day|week|month|year)|"
        r"hidden\s+gem\s+(?:stock|pick|share)|"
        r"(?:no\.?\s*1|number\s+1|number\s+one)\s+(?:bet|pick|stock|share)\b|"
        r"(?:i|we)\s+(?:strongly\s+|highly\s+|personally\s+)?"
        r"(?:recommend|endorse|suggest|advise)\s+"
        r"(?:buying|selling|holding|accumulating|investing\s+in|picking|adding|"
        r"this\s+stock|the\s+stock|these\s+shares|entering)|"
        r"(?:my|our|meri|hamari)\s+(?:top\s+|best\s+|personal\s+)?"
        r"(?:recommendation|stock\s+pick|top\s+pick|best\s+pick|call|bet|conviction)|"
        r"sabse\s+(?:ach?ha|badiya|badhiya|best)\s+(?:stock|share|pick)|"
        r"(?:rating|verdict|stance|call)\s*[:=-]\s*(?:strong\s+)?(?:buy|sell|hold|accumulate)"
        r")\b",
    ),
    _compile(
        "stock_recommendation",
        r"\b(?i:(?:i|we)\s+(?:strongly\s+|highly\s+|personally\s+)?(?:recommend|endorse)\s+)"
        r"[A-Z][A-Za-z0-9&.-]{1,}",
        ignore_case=False,
        use_original_case=True,
        check_shadows=False,
    ),
    _compile(
        "stock_recommendation",
        r"\b(?:allocate|invest|put|shift|move|park|deploy)\s+"
        r"(?:\d+(?:\.\d+)?%|₹\s*\d[\d,]*|rs\.?\s*\d[\d,]*|half|all|most|part|some)\s+"
        r"(?:of\s+(?:your|my)\s+(?:\S+\s+)?(?:capital|funds|money|portfolio|savings)\s+)?"
        r"(?:in|into|to|towards)\s+(?!index\s+funds?\s+in\s+general)\S+",
    ),
    _compile(
        "stock_recommendation",
        r"\b(?:better\s+(?:buy|pick|bet|stock|investment|choice)\s+than|"
        r"(?:prefer|pick|choose)\s+\S+(?:\s+\S+){0,2}\s+over|"
        r"switch\s+from\s+\S+(?:\s+\S+){0,2}\s+to|"
        r"rotate\s+(?:out\s+of|from)\s+\S+(?:\s+\S+){0,2}\s+(?:into|to)|"
        r"better\s+than\s+\S+(?:\s+\S+)?\s+right\s+now)\b",
    ),
    # ------------------------------------------------------------------
    # 5. Guaranteed returns & pump urgency (guaranteed_return)
    # ------------------------------------------------------------------
    _compile(
        "guaranteed_return",
        r"\b(?:"
        r"(?:guaranteed|assured|confirmed|certain|fixed)\s+"
        r"(?:returns?|profits?|gains?|income|upside|doubling|multibagger)|"
        r"(?:risk[- ]?free|zero[- ]?risk|no[- ]?risk|no[- ]?loss)\s+"
        r"(?:profits?|returns?|gains?|trade|call|investment|stock|strategy)|"
        r"100%\s*(?:profit|return|returns|safe|sure|certain|accuracy|accurate|winning|pakka)|"
        r"sure[- ]?shot|sureshot|foolproof\s+(?:call|tip|pick|profit|trade)|"
        r"can['’]?t\s+lose|cannot\s+lose|"
        r"pakka\s*(?:profit|return|paisa|munafa|faayda|fayda|jackpot|upper\s+circuit|circuit)|"
        r"bina\s+risk\s+(?:profit|return|paisa)|"
        r"rocket\s+(?:banega|hone\s+wala)|to\s+the\s+moon|jackpot\s+(?:call|tip|stock)|"
        r"bumper\s+profit|dhamaka\s+(?:call|stock)|aag\s+laga\s+dega|"
        r"kal\s+(?:upper\s+)?circuit|upper\s+circuit\s+lagega|circuit\s+to\s+circuit|"
        r"miss(?:ed)?\s+(?:the\s+)?bus|last\s+chance\s+to\s+(?:buy|enter|get\s+in)|"
        r"before\s+it['’]?s\s+too\s+late|inside(?:r)?\s+(?:news|tip|info|leak)|"
        r"operator\s+(?:game|tip|call|news)"
        r")\b",
    ),
)


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences without splitting on obfuscations like 'b.u.y'."""
    parts = re.split(r"(?<=[.!?\n])\s+|\n+", text)
    return [p for p in parts if p]


def _sanitize_sentence(sentence: str) -> str:
    """Neutralize clearly benign educational, policy, and audited-quote spans."""
    if _TROJAN_DISCLAIMER_RE.search(sentence):
        return sentence

    sanitized = _POLICY_NEGATION_RE.sub(" <POLICY> ", sentence)
    sanitized = _HISTORICAL_FACT_RE.sub(" <HISTORICAL_FACT> ", sanitized)
    sanitized = _BENIGN_CONCEPT_PHRASES_RE.sub(" <CONCEPT> ", sanitized)
    sanitized = _CAUTIONARY_CLAUSE_RE.sub(" <CAUTION> ", sanitized)

    if _AUDIT_FRAME_RE.search(sanitized):
        outside = _QUOTED_SPAN_RE.sub(" ", sanitized)
        if not _ENDORSEMENT_OUTSIDE_QUOTE_RE.search(outside):
            sanitized = _QUOTED_SPAN_RE.sub(' "<AUDITED_QUOTE>" ', sanitized)

    return sanitized


def sanitize_educational_context(text: str) -> str:
    """Apply clause-level educational/audit sanitization across sentences."""
    if not text:
        return text
    return " ".join(_sanitize_sentence(s) for s in _split_sentences(text))


def evaluate_rules(norm: NormalizedText) -> list[str]:
    """Run all deterministic guardrail rules and return triggered reason codes."""
    if not norm.cleaned:
        return []

    sanitized_cleaned = sanitize_educational_context(norm.raw_cleaned)
    sanitized_norm = normalize_text(sanitized_cleaned)

    reasons: list[str] = []
    seen: set[str] = set()

    for rule in _RULES:
        if rule.reason in seen:
            continue

        candidates: list[str]
        if rule.use_original_case:
            candidates = [sanitized_norm.cleaned]
        elif rule.check_shadows:
            candidates = [
                sanitized_norm.lower,
                sanitized_norm.deobfuscated,
                *sanitized_norm.shadow_variants,
            ]
        else:
            candidates = [sanitized_norm.cleaned, sanitized_norm.lower]

        for candidate in candidates:
            if rule.pattern.search(candidate):
                reasons.append(rule.reason)
                seen.add(rule.reason)
                break

    # Defense-in-depth: detect directive/target words revealed ONLY after
    # deobfuscation, zero-width stripping, homoglyph mapping, or leet decoding.
    for reason, token_re in _OBFUSCATED_TRIGGER_TOKENS:
        if reason in seen:
            continue
        in_shadow = any(token_re.search(s) for s in sanitized_norm.shadow_variants)
        if in_shadow and not token_re.search(norm.raw_lower):
            reasons.append(reason)
            seen.add(reason)

    return reasons
