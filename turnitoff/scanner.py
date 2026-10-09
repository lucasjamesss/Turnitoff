"""Heuristic scanner for AI-writing tells. A checker, not a detector.

Thresholds are uncalibrated guesses. Tune them on your own writing.
"""
import re
import statistics as st

HARD = (r"delv(?:e|es|ed|ing)|tapestry|testament|multifaceted|holistic|seamless(?:ly)?|"
        r"camaraderie|palpable|ever-evolving|game-changer|plethora|myriad|embark(?:s|ed|ing)?|"
        r"underscor(?:e|es|ed|ing)|showcas(?:e|es|ed|ing)|foster(?:s|ed|ing)?|pivotal|"
        r"intricate|intricacies|realm|vibrant|unlock(?:s|ed|ing)?|elevat(?:e|es|ed|ing)|"
        r"leverag(?:e|es|ed|ing)|utiliz(?:e|es|ed|ing)")
SOFT = (r"crucial|robust|landscape|journey|navigat(?:e|es|ed|ing)|nuanced|streamlin(?:e|es|ed|ing)|"
        r"enhanc(?:e|es|ed|ing)|comprehensive|innovative|transformative|groundbreaking")

PHRASES = [
    (r"it(?:'|’)?s worth noting|it is (?:important|worth) (?:to note|noting)|it should be noted", "hedge opener", 2),
    (r"\bin today(?:'|’)?s\b", "'in today's ...'", 2),
    (r"\bwhen it comes to\b|\bdive (?:in|into)\b|\bat the end of the day\b|\bin the (?:realm|world) of\b", "stock phrase", 1),
    (r"plays? an? (?:crucial|pivotal|vital|key|important) role|\ba testament to\b", "significance filler", 2),
    (r"\b(?:serves|stands) as\b|\bboasts\b", "copula dodge", 1),
    (r"\b(?:rich|diverse|vibrant) (?:tapestry|array|heritage)\b", "stock noun phrase", 2),
    (r"great question|i hope this helps|let me know if you", "chat residue", 2),
    (r"(?:^|[.!?]\s+)(?:Moreover|Furthermore|Additionally|Notably|Importantly|Consequently),", "connective filler", 1),
]
NEGPAR = [
    r"\b(?:it|this|that)(?:'s|’s| is| was)\s+not\s+(?:just\s+|only\s+|merely\s+|simply\s+)?[^.?!;]{1,80}?[,;:—–-]+\s*(?:it|this|that)(?:'s|’s| is| was)\b",
    r"\bnot (?:just|only|merely|simply) [^.?!]{1,80}?,? but (?:also )?",
    r"\bno [^.?!,]{1,30}, no [^.?!,]{1,30}, (?:just|only)\b",
    r"\bmore than just\b",
]
PARTICIPLE = (r",\s+(?:highlighting|underscoring|reflecting|showcasing|ensuring|fostering|enabling|"
              r"allowing|demonstrating|emphasizing|illustrating|contributing|providing|offering|"
              r"reinforcing|signaling|marking)\b")
TRIPLE = r"\b[\w'-]+(?: [\w'-]+)?, [\w'-]+(?: [\w'-]+)?,? and [\w'-]+\b"
CLOSER = r"^(?:In conclusion|In summary|To sum up|To summarize|In essence|In short|Overall|Ultimately)\b"
EMOJI = "[\U0001F300-\U0001FAFF☀-➿]"


def clean(t):
    t = re.sub(r"```.*?```", " ", t, flags=re.S)
    t = re.sub(r"`[^`]*`", " ", t)
    t = re.sub(r"https?://\S+", " ", t)
    return re.sub(r"<!--.*?-->", " ", t, flags=re.S)


def words(s):
    return re.findall(r"[A-Za-z0-9'’-]+", s)


def paragraphs(t):
    out = []
    for block in re.split(r"\n\s*\n", t):
        lines = [l for l in block.splitlines() if l.strip()]
        if not lines or all(re.match(r"\s*(#|[-*•]\s|\d+[.)]\s|\||>)", l) for l in lines):
            continue
        out.append(" ".join(l.strip() for l in lines if not re.match(r"\s*#", l)))
    return out


def sentence_lengths(paras):
    n = []
    for p in paras:
        for s in re.split(r"(?<=[.!?])\s+(?=[A-Z\"'“(\[])", p):
            c = len(words(s))
            if c:
                n.append(c)
    return n


def cv(xs):
    m = st.mean(xs)
    return st.pstdev(xs) / m if m else 0


def analyze(raw, formal=False):
    """Return (score, findings, word_count). Higher score = more AI-like."""
    t = clean(raw)
    nw = len(words(t))
    per300 = lambda c: c * 300 / max(nw, 1)
    f = []  # (weight, message)

    hard = re.findall(r"\b(?:%s)\b" % HARD, t, flags=re.I)
    if hard:
        f.append((min(4, 2 * len(hard)), "AI vocabulary x%d: %s" % (len(hard), ", ".join(sorted(set(h.lower() for h in hard))))))
    soft = re.findall(r"\b(?:%s)\b" % SOFT, t, flags=re.I)
    if len(soft) >= 2:
        f.append((min(2, 0.5 * len(soft)), "soft AI vocabulary x%d: %s" % (len(soft), ", ".join(sorted(set(s.lower() for s in soft))))))
    for rx, label, w in PHRASES:
        m = re.findall(rx, t, flags=re.I | re.M)
        if m:
            f.append((min(4, w * len(m)), "%s x%d" % (label, len(m))))

    neg = sum(len(re.findall(rx, t, flags=re.I)) for rx in NEGPAR)
    if neg:
        f.append((min(4, 2 * neg), "negative parallelism ('not X, it's Y') x%d" % neg))

    dashes = len(re.findall("[—–]|\\s--\\s", t))
    if dashes and (formal or per300(dashes) > 1):
        f.append((min(3, dashes), "em/en dashes x%d (%.1f per 300 words)" % (dashes, per300(dashes))))

    part = len(re.findall(PARTICIPLE, t, flags=re.I))
    if per300(part) > 1:
        f.append((min(3, part), "trailing participle clauses x%d" % part))

    trip = len(re.findall(TRIPLE, t))
    if nw >= 120 and per300(trip) > 2.5:
        f.append((1, "rule-of-three lists x%d" % trip))

    bold = len(re.findall(r"^\s*(?:[-*•]|\d+[.)])\s+\*\*[^*]+\*\*", raw, flags=re.M))
    if bold >= 3:
        f.append((2, "bold-lead bullets x%d" % bold))
    if len(re.findall(EMOJI, t)):
        f.append((1, "emoji in prose"))

    paras = paragraphs(t)
    if paras and re.match(CLOSER, paras[-1]):
        f.append((2, "announced conclusion in last paragraph"))
    elif sum(1 for p in paras if re.match(CLOSER, p)) >= 1:
        f.append((1, "recap paragraph opener"))

    lens = sentence_lengths(paras)
    if len(lens) >= 8:
        c = cv(lens)
        if c < 0.40:
            f.append((2, "uniform sentence length (CV %.2f, mean %.1f words)" % (c, st.mean(lens))))
        elif c < 0.50:
            f.append((1, "low sentence-length variation (CV %.2f)" % c))
        if min(lens) >= 6 and max(lens) <= 30:
            f.append((1, "no short (<6) or long (>30) sentences"))
        run = best = 1
        for i in range(1, len(lens)):
            run = run + 1 if abs(lens[i] - lens[i - 1]) <= 3 else 1
            best = max(best, run)
        if best >= 5:
            f.append((1, "%d consecutive sentences of near-equal length" % best))
    if len(paras) >= 5:
        pl = [len(words(p)) for p in paras]
        if cv(pl) < 0.35:
            f.append((1, "uniform paragraph length (CV %.2f)" % cv(pl)))

    return sum(w for w, _ in f), [m for _, m in f], nw


def verdict(score):
    return "clean" if score < 3 else ("minor-tells" if score < 6 else "reads-AI")


def report(score, findings, nw):
    lines = ["turnitoff: %s (score %.1f, %d words)" % (verdict(score), score, nw)]
    lines += ["  - " + m for m in findings]
    return "\n".join(lines)
