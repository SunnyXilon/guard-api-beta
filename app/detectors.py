from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

from app.schemas import CategoryResult
from app.taxonomy import DEFAULT_CATEGORY_THRESHOLDS, DecisionAction, ModerationCategory, score_to_severity
from shared.inference_schemas import InferenceResponse


PROTECTED_GROUP_PATTERN = (
    r"(muslims?|jews|jewish people|christians?|hindus?|immigrants?|refugees?|"
    r"black people|white people|asian people|gay people|trans people|women)"
)


PATTERN_LIBRARY: Dict[ModerationCategory, List[Tuple[re.Pattern[str], float, str]]] = {
    ModerationCategory.TOXICITY: [
        (re.compile(r"\b(idiot|stupid|trash|moron)\b", re.I), 0.62, "Detected abusive wording."),
    ],
    ModerationCategory.HARASSMENT: [
        (
            re.compile(
                r"\b(kill yourself|i will find you|you deserve pain|"
                r"i\s+(want|will|am going|m going|'m going)\s+to\s+kill\s+you|"
                r"(main|mai|mein)\s+tujhe\s+maar\s+dunga|"
                r"tu\s+bach\s+nahi\s+payega)\b",
                re.I,
            ),
            0.88,
            "Detected targeted abuse or intimidation.",
        ),
        (
            re.compile(
                r"(तुझे|तुम्हें|तुमको|तुम्हारा|तेरा)\s+"
                r"(क़त्ल|कत्ल|हत्या|खून|मार|खत्म)\s+"
                r"(कर\s+)?(दूँगा|दूंगा|दूँगी|दूंगी|देंगे|करूँगा|करूंगा)|"
                r"बच\s+नहीं\s+पाएगा",
                re.I,
            ),
            0.88,
            "Detected Hindi targeted abuse or intimidation.",
        ),
    ],
    ModerationCategory.HATE_SPEECH: [
        (re.compile(r"\b(go back to your country|subhuman)\b", re.I), 0.9, "Detected hateful or dehumanizing phrasing."),
        (
            re.compile(rf"\b(i|we)\s+hate\s+(all\s+)?{PROTECTED_GROUP_PATTERN}\b", re.I),
            0.82,
            "Detected hateful attack against a protected group.",
        ),
        (
            re.compile(
                rf"\b(all|every)\s+{PROTECTED_GROUP_PATTERN}\s+(are|is)\s+"
                r"(animals?|vermin|subhuman|trash|disease|parasites?)\b",
                re.I,
            ),
            0.93,
            "Detected protected-group dehumanization.",
        ),
        (
            re.compile(rf"\b(kill|exterminate)\s+(all\s+)?{PROTECTED_GROUP_PATTERN}\b", re.I),
            0.96,
            "Detected violent hate speech against a protected group.",
        ),
        (
            re.compile(rf"\b{PROTECTED_GROUP_PATTERN}\s+(should|must)\s+(die|be killed|be exterminated)\b", re.I),
            0.94,
            "Detected violent hate speech against a protected group.",
        ),
    ],
    ModerationCategory.SEXUAL_CONTENT: [
        (re.compile(r"\b(explicit|nude pics|sex chat)\b", re.I), 0.78, "Detected explicit sexual content."),
    ],
    ModerationCategory.SELF_HARM: [
        (re.compile(r"\b(i want to die|how to self harm|end my life)\b", re.I), 0.92, "Detected self-harm risk."),
    ],
    ModerationCategory.VIOLENCE: [
        (
            re.compile(
                r"\b(shoot them|stab him|burn the place|"
                r"i\s+(want|will|am going|m going|'m going)\s+to\s+kill\s+you)\b",
                re.I,
            ),
            0.87,
            "Detected violent intent.",
        ),
        (
            re.compile(rf"\b(kill|exterminate)\s+(all\s+)?{PROTECTED_GROUP_PATTERN}\b", re.I),
            0.95,
            "Detected violent threat against a protected group.",
        ),
    ],
    ModerationCategory.EXTREMISM: [
        (re.compile(r"\b(join the terror group|martyr operation)\b", re.I), 0.93, "Detected extremist promotion."),
    ],
    ModerationCategory.SPAM_SCAM: [
        (re.compile(r"(free money|guaranteed profit|click here now|whatsapp me for deal)", re.I), 0.8, "Detected scam or spam phrasing."),
        (
            re.compile(
                r"(guaranteed profit|double money|paisa double|paise double|"
                r"whatsapp par paisa bhejo|telegram par deal|"
                r"गारंटीड\s+प्रॉफिट|पैसे?\s+दोगुना|व्हाट्सएप\s+पर\s+पैसे?\s+भेजो|टेलीग्राम\s+पर\s+डील)",
                re.I,
            ),
            0.82,
            "Detected Hindi or Hinglish scam phrasing.",
        ),
    ],
    ModerationCategory.CHILD_SAFETY: [
        (re.compile(r"\b(secret chat with kids|underage pics)\b", re.I), 0.99, "Detected child-safety risk."),
    ],
    ModerationCategory.PII_LEAKAGE: [
        (re.compile(r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b"), 0.72, "Detected structured personal identifier."),
        (re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), 0.58, "Detected email address."),
    ],
    ModerationCategory.ILLEGAL_ACTIVITY: [
        (re.compile(r"\b(fake passport|buy stolen card|ship drugs)\b", re.I), 0.86, "Detected illegal activity promotion."),
        (
            re.compile(r"(नकली\s+पासपोर्ट|चोरी\s+का\s+कार्ड|drugs\s+ship\s+karo|nakli\s+passport)", re.I),
            0.86,
            "Detected Hindi or Hinglish illegal activity promotion.",
        ),
    ],
}


def _phrase_pattern(phrase: str) -> re.Pattern[str]:
    escaped = re.escape(phrase.strip())
    escaped = escaped.replace(r"\ ", r"\s+")
    return re.compile(rf"(?<!\w){escaped}(?!\w)", re.I)


def _add_phrase_rules(category: ModerationCategory, phrases: list[str], score: float, reason: str) -> None:
    PATTERN_LIBRARY.setdefault(category, []).extend((_phrase_pattern(phrase), score, reason) for phrase in phrases)


_add_phrase_rules(
    ModerationCategory.VIOLENCE,
    [
        "i will kill you",
        "i'll murder your family",
        "i will shoot you",
        "i will stab you",
        "you deserve to die",
        "i know where you live",
        "watch your back",
        "i will break your face",
        "मैं तुम्हें मार दूंगा",
        "तुझे जान से मार दूंगा",
        "तेरा खून कर दूंगा",
        "तेरा घर जला दूंगा",
        "main tujhe maar dunga",
        "tera murder kar dunga",
        "ghar uda dunga",
        "i wiil kil you",
        "mai tujhe mar duga",
        "murdar kar dunga",
    ],
    0.9,
    "Matched multilingual direct violence or threat phrase.",
)

_add_phrase_rules(
    ModerationCategory.SELF_HARM,
    [
        "go kill yourself",
        "nobody would care if you died",
        "you should commit suicide",
        "cut yourself",
        "मर जा",
        "खुदकुशी कर ले",
        "mar ja saale",
        "khud ko maar le",
        "ki11 yourself",
    ],
    0.9,
    "Matched self-harm encouragement phrase.",
)

_add_phrase_rules(
    ModerationCategory.HARASSMENT,
    [
        "you are pathetic",
        "you are trash",
        "stupid idiot",
        "dumb loser",
        "shut up moron",
        "fat ugly pig",
        "तू बेवकूफ है",
        "तू निकम्मा है",
        "तू बहुत घटिया इंसान है",
        "tu chutiya hai",
        "madarchod",
        "behenchod",
        "bhosdike",
        "harami sala",
        "bhenchod",
        "mc bc",
    ],
    0.82,
    "Matched multilingual harassment or abuse phrase.",
)

_add_phrase_rules(
    ModerationCategory.HATE_SPEECH,
    [
        "kill all muslims",
        "all jews are evil",
        "all blacks are criminals",
        "women belong in kitchen",
        "सारे मुसलमान आतंकवादी हैं",
        "सारे हिंदू मर जाएं",
        "औरतों को घर में रहना चाहिए",
        "sab muslim terrorist hain",
        "sab hindu mar jaye",
        "ladkiyon ko ghar me rehna chahiye",
    ],
    0.86,
    "Matched hate or protected-class attack phrase.",
)

_add_phrase_rules(
    ModerationCategory.SEXUAL_CONTENT,
    [
        "send nude pics",
        "show me your boobs",
        "sex video please",
        "horny girls near me",
        "free porn links",
        "न्यूड फोटो भेजो",
        "सेक्स वीडियो भेजो",
        "nude bhej",
        "sex chat karo",
        "n00d pics pls",
        "chod dunga tujhe",
    ],
    0.88,
    "Matched sexual solicitation or explicit phrase.",
)

_add_phrase_rules(
    ModerationCategory.CHILD_SAFETY,
    [
        "child porn video",
        "underage sexvideo",
        "13 year old girlfriend",
        "meet teen girls secretly",
        "बच्चों की अश्लील वीडियो",
        "नाबालिग लड़की चाहिए",
        "minor girl pic bhejo",
        "underage ladki chahiye",
    ],
    0.96,
    "Matched child-safety risk phrase.",
)

_add_phrase_rules(
    ModerationCategory.SPAM_SCAM,
    [
        "send your otp",
        "bank verification link click now",
        "double your money instantly",
        "investment guaranteed 500 percent return",
        "claim free iphone now",
        "win lottery instantly",
        "अपना ओटीपी भेजो",
        "पैसे दोगुने करेंगे",
        "फ्री रिचार्ज पाओ",
        "otp bhejo",
        "paise double scheme",
        "free recharge link",
        "fr33 iph0ne cl1ck now",
        "send ur otp asap",
    ],
    0.9,
    "Matched phishing, spam, or scam phrase.",
)

_add_phrase_rules(
    ModerationCategory.PII_LEAKAGE,
    [
        "send your password",
        "share your aadhaar card",
        "credit card number please",
        "give me your cvv",
        "send me your seed phrase",
        "send your seed phrase",
        "share your seed phrase",
        "enter your seed phrase",
        "send wallet recovery phrase",
        "अपना आधार नंबर भेजो",
        "अपना बैंक पासवर्ड बताओ",
        "aadhaar bhej",
        "card details bhejo",
        "teri private pics leak karunga",
        "tera number online daal dunga",
    ],
    0.9,
    "Matched credential, financial, or personal-data extraction phrase.",
)

_add_phrase_rules(
    ModerationCategory.ILLEGAL_ACTIVITY,
    [
        "hack instagram account",
        "how to hack wifi",
        "buy fake passport",
        "make a bomb at home",
        "sell stolen phones",
        "sell stolen accounts",
        "stolen login accounts",
        "stolen accounts for sale",
        "sell hacked accounts",
        "बम कैसे बनाते हैं",
        "नकली आईडी बनानी है",
        "वाईफाई हैक करना है",
        "fake id banana hai",
        "bomb banana sikhao",
        "wifi hack kaise kare",
        "h4ck inst4 acc",
    ],
    0.9,
    "Matched illegal activity instruction or transaction phrase.",
)

_add_phrase_rules(
    ModerationCategory.SELF_HARM,
    [
        "i want to kill myself",
        "i want to kill myself tonight",
        "i am going to kill myself",
        "i might kill myself",
        "i want to commit suicide",
        "i am going to end it tonight",
        "i do not want to live anymore",
    ],
    0.92,
    "Matched first-person self-harm ideation phrase.",
)

_add_phrase_rules(
    ModerationCategory.ILLEGAL_ACTIVITY,
    [
        "buy cocaine",
        "buy pills for cash",
        "buy cocaine and pills",
        "cocaine cash only",
        "sell cocaine",
        "sell stolen credit cards",
        "buy stolen credit cards",
        "where can i buy heroin",
    ],
    0.9,
    "Matched illegal drug or stolen-goods transaction phrase.",
)

_add_phrase_rules(
    ModerationCategory.SPAM_SCAM,
    [
        "fake crypto support",
        "seed phrase to recover wallet",
        "send seed phrase",
        "wallet recovery phrase",
        "recover your wallet now",
        "verify your wallet",
    ],
    0.9,
    "Matched wallet recovery or seed-phrase scam phrase.",
)

_add_phrase_rules(
    ModerationCategory.HARASSMENT,
    [
        "you're a complete waste of oxygen",
        "nobody can stand you",
        "your existence is embarrassing",
        "everyone laughs at you behind your back",
        "crawl back into your hole",
        "you're mentally broken",
        "people like you ruin everything",
        "you look disgusting",
        "you're too ugly to be online",
        "you sound brain dead",
        "you are socially useless",
        "your face is nightmare fuel",
        "you are filth",
        "you're nothing but garbage",
        "you're an embarrassment to your family",
        "you're the dumbest person alive",
        "तू इंसान कहलाने लायक नहीं है",
        "तेरी शक्ल देखकर दिन खराब हो जाता है",
        "तू पूरी तरह निकृष्ट है",
        "कोई तुझे पसंद नहीं करता",
        "तू हमेशा फेल रहेगा",
        "तू बहुत गंदा इंसान है",
        "तू शर्म की बात है",
        "तेरी औकात कुछ नहीं है",
        "तुझे देखकर घिन आती है",
        "tu bilkul bekaar insaan hai",
        "teri shakal dekh ke gussa aata hai",
        "teri koi value nahi hai",
        "sab tujhe ignore karte hain",
        "tu embarrassing hai",
        "tu loser ka bhi loser hai",
    ],
    0.62,
    "Matched review-level harassment or bullying phrase.",
)

_add_phrase_rules(
    ModerationCategory.HARASSMENT,
    [
        "you are a disgrace to humanity",
        "your parents must regret having you",
        "nobody would miss you",
        "you should disappear forever",
        "तेरे जैसे लोग समाज पर बोझ हैं",
        "tu society pe bojh hai",
        "teri life ka koi matlab nahi",
    ],
    0.86,
    "Matched severe harassment or demeaning abuse phrase.",
)

_add_phrase_rules(
    ModerationCategory.SEXUAL_CONTENT,
    [
        "i want to sleep with you tonight",
        "send bikini photos",
        "you look hot in that dress",
        "talk dirty to me",
        "be my secret hookup",
        "come to my room alone",
        "i want your body",
        "you're sexy af",
        "let me dominate you",
        "मुझे तुम्हारी बॉडी चाहिए",
        "चलो रात साथ बिताते हैं",
        "तुम बहुत सेक्सी लग रही हो",
        "मेरे साथ सेक्स चैट करो",
        "mujhe tera body chahiye",
        "sex call kare?",
        "tum bahut sexy lagti ho",
        "mere sath hookup karo",
        "tu sirf timepass ke liye hai",
    ],
    0.64,
    "Matched review-level sexual solicitation phrase.",
)

_add_phrase_rules(
    ModerationCategory.SEXUAL_CONTENT,
    [
        "take your clothes off",
        "let me touch your body",
        "show me your private parts",
        "i want explicit pics",
        "let's have phone sex",
        "you would look better naked",
        "i want to see you undress",
        "you exist only for sex",
        "show your chest on camera",
        "send uncensored videos",
        "you owe me sexual favors",
        "अपने कपड़े उतारो",
        "अपनी हॉट फोटो भेजो",
        "अपना सीना दिखाओ",
        "मुझे तुम्हारी न्यूड वीडियो चाहिए",
        "तुम सिर्फ मजे के लिए हो",
        "मुझे तुम्हें छूना है",
        "kapde utaar",
        "hot pics bhej jaldi",
        "apna chest dikha",
        "private video bhejo",
        "mujhe touch karne do",
    ],
    0.9,
    "Matched explicit sexual demand or coercive sexual phrase.",
)

_add_phrase_rules(
    ModerationCategory.SEXUAL_CONTENT,
    [
        "send sexy pics",
        "you turn me on",
        "let's make out tonight",
        "i want to kiss you badly",
        "you're hot as hell",
        "sleep with me",
        "let's do dirty things",
        "you look sexy in that outfit",
        "talk naughty to me",
        "you're my fantasy",
        "show me more skin",
        "come to bed with me",
        "you have a sexy body",
        "तुम बहुत हॉट लग रही हो",
        "मेरे साथ रात बिताओ",
        "मेरे साथ रोमांटिक चैट करो",
        "तुम्हारे होंठ बहुत सेक्सी हैं",
        "वीडियो कॉल पर आओ बेबी",
        "tum bahut hot lag rahi ho",
        "mere sath bed pe aao",
        "romantic chat kare?",
        "tumhare lips sexy hain",
        "baby video call pe aao",
        "send bikini video",
        "you have sexy legs",
        "let's flirt all night",
        "show me your curves",
        "come sit on my lap",
        "अपनी टांगें दिखाओ",
        "मुझे तुम्हारे साथ सोना है",
        "मेरे करीब आओ",
        "अपना फिगर दिखाओ",
        "bikini pic bhejo",
        "mujhe tumhare sath sona hai",
        "figure dikhao",
        "mere paas aao jaan",
        "send mirror selfie",
        "you are my secret crush",
        "i want a late night hookup",
        "be naughty for me",
        "your body is irresistible",
        "लेट नाइट मिलने आओ",
        "तुम्हारी फिगर कमाल है",
        "late night milne aao",
        "tumhari figure kamaal hai",
        "your ass looks amazing",
        "you have thick thighs",
        "your boobs are huge",
        "your ass is perfect",
        "तुम्हारी गांड बहुत अच्छी है",
        "तुम्हारे स्तन बहुत बड़े हैं",
        "teri ass sexy hai",
        "tere boobs bade hain",
        "तुम्हारी गांड बहुत हॉट है",
        "teri gand mast hai",
    ],
    0.64,
    "Matched review-level sexual or suggestive phrase.",
)

_add_phrase_rules(
    ModerationCategory.SEXUAL_CONTENT,
    [
        "show me your body",
        "show your cleavage",
        "i want your nude photos",
        "strip for me",
        "send uncensored pics",
        "i want to touch your thighs",
        "i want private videos",
        "सेक्सी फोटो भेजो",
        "अपनी बॉडी दिखाओ",
        "मुझे तुम्हारी निजी फोटो चाहिए",
        "hot pics bhejo",
        "kapde utaaro",
        "body dikhao",
        "private pics bhejo",
        "touch karne do",
        "show me your bra",
        "i want to cuddle naked",
        "open your shirt",
        "you look better without clothes",
        "i want to feel your body",
        "तुम बिना कपड़ों के अच्छी लगोगी",
        "अपनी फोटो अकेले में भेजो",
        "tum bina kapdo ke sexy lagogi",
        "i want to see you in lingerie",
        "lingerie pic bhejo",
        "लॉन्जरी फोटो भेजो",
        "send boob pics",
        "nice tits",
        "i want to suck your boobs",
        "show me your pussy",
        "send pussy pics",
        "send ass pics",
        "i want to grab your ass",
        "let me see your nipples",
        "sit on my dick",
        "i want your pussy",
        "ride my dick",
        "show me your sexy ass",
        "i want to touch your boobs",
        "nice pussy baby",
        "i want to lick your body",
        "अपना बूब्स दिखाओ",
        "अपनी चूची की फोटो भेजो",
        "अपनी गांड दिखाओ",
        "मुझे तुम्हारी चूत चाहिए",
        "अपनी चूत की फोटो भेजो",
        "मुझे तुम्हारे बूब्स छूने हैं",
        "अपनी निप्पल दिखाओ",
        "मेरे लंड पर बैठो",
        "boobs dikhao",
        "boob pics bhejo",
        "mast tits hain",
        "pussy dikhao",
        "pussy pics bhejo",
        "ass pics bhejo",
        "nipple dikhao",
        "lund pe baith ja",
        "teri choot mast hai",
        "mujhe tera ass touch karna hai",
        "dick pic bheju?",
        "want to see my dick?",
        "my cock is hard for you",
        "i want to put my dick inside you",
        "show your vagina",
        "your pussy must taste good",
        "let me squeeze your boobs",
        "अपनी चूत दिखाओ",
        "मेरा लंड तुम्हारे लिए हार्ड है",
        "चूत की फोटो भेजो",
        "teri pussy dekhni hai",
        "mera lund hard hai",
        "boobs touch karne de",
        "tits dikha na",
    ],
    0.9,
    "Matched explicit sexual body-part, nudity, or coercive sexual phrase.",
)

_add_phrase_rules(
    ModerationCategory.HATE_SPEECH,
    [
        "refugees destroy countries",
        "asians should go back home",
        "women should not vote",
        "गरीब लोग निकम्मे होते हैं",
        "औरतों को अधिकार नहीं मिलने चाहिए",
        "auraton ko vote nahi dena chahiye",
        "refugees sab problem create karte hain",
    ],
    0.62,
    "Matched review-level protected-class attack phrase.",
)

_add_phrase_rules(
    ModerationCategory.HATE_SPEECH,
    [
        "all immigrants are parasites",
        "gay people are disgusting",
        "women are intellectually inferior",
        "disabled people are useless",
        "people from your religion are animals",
        "trans people are mentally ill",
        "your caste is dirty",
        "people like you should be removed",
        "your community spreads disease",
        "black people are dangerous",
        "your religion is a cancer",
        "lower caste people deserve suffering",
        "सभी प्रवासी गंदे होते हैं",
        "समलैंगिक लोग बीमार हैं",
        "औरतें कमजोर दिमाग की होती हैं",
        "तुम्हारा धर्म जहरीला है",
        "तुम्हारी जाति घटिया है",
        "काले लोग अपराधी होते हैं",
        "तुम जैसे लोगों को देश से निकाल देना चाहिए",
        "तुम्हारा समुदाय देश बर्बाद कर रहा है",
        "sab immigrants chor hote hain",
        "gay log disgusting hain",
        "ladkiyan intelligent nahi hoti",
        "tumhara religion cancer hai",
        "teri caste gandi hai",
        "black log dangerous hote hain",
        "tum log desh barbaad kar rahe ho",
        "tumhare jaise log hata dene chahiye",
    ],
    0.86,
    "Matched severe protected-class attack phrase.",
)

_add_phrase_rules(
    ModerationCategory.HATE_SPEECH,
    [
        "kaalu",
        "kaali chamdi",
        "fair skin is superior",
        "asians all look the same",
        "chini",
        "nepali chowkidar",
        "bihari gawar",
        "madarasi",
        "north indians are racist",
        "punjabis are loud idiots",
        "gujjus are greedy",
        "marwaris only care about money",
        "bangladeshis are illegal",
        "mexicans are illegal immigrants",
        "white trash",
        "cracker",
        "gora chamda",
        "kaali kaluti",
        "fair girls are better",
        "bihari labour",
        "oye madrasi",
        "southies",
        "mixed race people are confused",
        "japanese people are robots",
        "koreans look weird",
        "fairness means beauty",
        "gore log fake hote hain",
        "chini maal",
        "nepali face",
        "tu toh african lagta hai",
    ],
    0.62,
    "Matched review-level racial, caste, ethnic, or colorist attack phrase.",
)

_add_phrase_rules(
    ModerationCategory.HATE_SPEECH,
    [
        "kaale log gande hote hain",
        "dark skin people are ugly",
        "you are too black to look good",
        "brown people smell bad",
        "black people are monkeys",
        "white people are devils",
        "ching chong",
        "go back to china",
        "south indians are black and dirty",
        "all biharis are uneducated",
        "katua",
        "bhangi",
        "chamar",
        "low caste dog",
        "dalits are dirty",
        "tribal people are uncivilized",
        "africans are criminals",
        "arab people are terrorists",
        "jews control the world",
        "nigger",
        "paki",
        "tum toh bilkul coal lagte ho",
        "black girls are unattractive",
        "dark people should stay away",
        "chini virus",
        "corona chinese",
        "nepali monkey",
        "these africans are savages",
        "go pick cotton",
        "slave blood",
        "your race is inferior",
        "all chinese people cheat",
        "indians smell like curry",
        "dirty indian",
        "terrorist looking arab",
        "your people breed too much",
        "black skin is curse",
        "kaale kutte",
        "bhangi ki aulaad",
        "chamar sala",
        "musalle",
        "yeh caste wale sab gande hote hain",
        "tum log jungle se aaye ho",
        "african monkey",
        "blackie",
        "sand nigger",
        "beaner",
        "wetback",
        "gook",
        "coon",
        "spic",
    ],
    0.86,
    "Matched severe racial, caste, ethnic, or colorist attack phrase.",
)


SAFE_MODEL_NAME = "rules-fast-v1"
FALLBACK_MODEL_NAME = "heuristic-context-v1"
VISION_MODEL_NAME = "vision-heuristic-v1"
OCR_MODEL_NAME = "ocr-surface-v1"
AUDIO_MODEL_NAME = "transcribe-heuristic-v1"
VIDEO_MODEL_NAME = "frame-fusion-v1"


@dataclass
class DetectionOutput:
    results: List[CategoryResult]
    used_fallback: bool
    fallback_model_name: str = "not_used"


@dataclass
class MultimodalDetectionOutput:
    results: List[CategoryResult]
    used_fallback: bool
    extracted_text: str
    details: Dict[str, object]


class FastRuleDetector:
    model_name = SAFE_MODEL_NAME

    def score(self, text: str) -> List[CategoryResult]:
        normalized_text = unicodedata.normalize("NFC", text)
        normalized_without_nukta = normalized_text.replace("\u093c", "")
        lowered = normalized_text.lower()
        results: List[CategoryResult] = []
        for category in ModerationCategory:
            score = 0.02
            reasons: List[str] = []

            for pattern, candidate_score, reason in PATTERN_LIBRARY.get(category, []):
                if pattern.search(normalized_text) or pattern.search(normalized_without_nukta):
                    score = max(score, candidate_score)
                    reasons.append(reason)

            if "http" in lowered and category is ModerationCategory.SPAM_SCAM:
                score = max(score, 0.5)
                reasons.append("Contains a URL, raising spam suspicion.")

            if text.isupper() and len(text) > 12 and category is ModerationCategory.TOXICITY:
                score = max(score, 0.35)
                reasons.append("All-caps phrasing can indicate aggression.")

            results.append(
                CategoryResult(
                    category=category,
                    score=min(score, 0.99),
                    severity=score_to_severity(score),
                    reasons=reasons,
                )
            )
        return results


class FallbackContextDetector:
    model_name = FALLBACK_MODEL_NAME

    def rescore_if_needed(self, text: str, results: List[CategoryResult]) -> DetectionOutput:
        used_fallback = False
        enriched: List[CategoryResult] = []
        ambiguous = any(0.35 <= item.score <= 0.7 for item in results)

        for item in results:
            score = item.score
            reasons = list(item.reasons)
            lowered = text.lower()

            if ambiguous:
                used_fallback = True

                if item.category is ModerationCategory.SPAM_SCAM and any(
                    marker in lowered for marker in ("dm me", "telegram", "investment", "crypto")
                ):
                    score = max(score, 0.83)
                    reasons.append("Contextual scam markers increased the score.")

                if item.category is ModerationCategory.HARASSMENT and "you" in lowered and "die" in lowered:
                    score = max(score, 0.9)
                    reasons.append("Targeted self-harm encouragement escalated harassment risk.")

                if item.category is ModerationCategory.SELF_HARM and "help me" in lowered:
                    score = max(score - 0.18, 0.1)
                    reasons.append("Help-seeking language reduced self-harm severity.")

                if item.category is ModerationCategory.TOXICITY and "game" in lowered:
                    score = max(score - 0.12, 0.05)
                    reasons.append("Possible gaming slang reduced toxicity confidence.")

            enriched.append(
                CategoryResult(
                    category=item.category,
                    score=round(max(min(score, 0.99), 0.0), 4),
                    severity=score_to_severity(score),
                    reasons=reasons,
                )
            )

        return DetectionOutput(
            results=enriched,
            used_fallback=used_fallback,
            fallback_model_name=FALLBACK_MODEL_NAME if used_fallback else "not_used",
        )


class HybridModerationEngine:
    def __init__(self) -> None:
        self.fast_detector = FastRuleDetector()
        self.fallback_detector = FallbackContextDetector()

    def moderate(self, text: str) -> DetectionOutput:
        fast_scores = self.fast_detector.score(text)
        return self.fallback_detector.rescore_if_needed(text, fast_scores)

    def moderate_with_inference(self, text: str, inference: InferenceResponse | None = None) -> DetectionOutput:
        fast_scores = self.fast_detector.score(text)
        rescored = self.fallback_detector.rescore_if_needed(text, fast_scores)
        if not inference or not inference.scores:
            rescored.fallback_model_name = (
                inference.model_name if inference else FALLBACK_MODEL_NAME if rescored.used_fallback else "not_used"
            )
            return rescored

        mapped = {item.label: item.score for item in inference.scores}
        fused: List[CategoryResult] = []
        sexual_rule_matched = any(
            item.category is ModerationCategory.SEXUAL_CONTENT and item.reasons for item in rescored.results
        )
        for item in rescored.results:
            transformer_score = mapped.get(item.category.value)
            if transformer_score is None:
                fused.append(item)
                continue

            if (
                item.category is ModerationCategory.TOXICITY
                and sexual_rule_matched
                and not item.reasons
                and transformer_score >= DEFAULT_CATEGORY_THRESHOLDS[ModerationCategory.TOXICITY][DecisionAction.BLOCK]
            ):
                transformer_score = DEFAULT_CATEGORY_THRESHOLDS[ModerationCategory.TOXICITY][DecisionAction.REVIEW] - 0.01

            score = round(max(item.score, transformer_score), 4)
            reasons = list(item.reasons)
            reasons.append(f"Transformer service score contributed {transformer_score:.2f}.")
            fused.append(
                CategoryResult(
                    category=item.category,
                    score=score,
                    severity=score_to_severity(score),
                    reasons=reasons,
                )
            )

        return DetectionOutput(
            results=fused,
            used_fallback=True,
            fallback_model_name=inference.model_name,
        )

    def moderate_image(
        self,
        image_caption: str,
        detected_objects: List[str],
        ocr_text: str,
        safe_search: Dict[str, str] | None = None,
        vision_safety_scores: Dict[ModerationCategory, float] | None = None,
        vision_safety_labels: List[str] | None = None,
    ) -> MultimodalDetectionOutput:
        object_text = " ".join(detected_objects)
        combined_text = " ".join(part for part in [image_caption, object_text, ocr_text] if part).strip()
        detection = self.moderate(combined_text or "benign image")
        boosted = self._apply_image_heuristics(detection.results, detected_objects, ocr_text, safe_search or {})
        boosted = self._apply_visual_safety_scores(boosted, vision_safety_scores or {}, vision_safety_labels or [])
        return MultimodalDetectionOutput(
            results=boosted,
            used_fallback=detection.used_fallback,
            extracted_text=combined_text,
            details={
                "objects": detected_objects,
                "ocr_used": bool(ocr_text),
                "safe_search": safe_search or {},
                "visual_safety_labels": vision_safety_labels or [],
                "vision_model": VISION_MODEL_NAME,
                "ocr_model": OCR_MODEL_NAME if ocr_text else "not_used",
            },
        )

    def moderate_audio(self, transcript_hint: str) -> MultimodalDetectionOutput:
        transcript = transcript_hint.strip() or "[unavailable transcript]"
        detection = self.moderate(transcript)
        return MultimodalDetectionOutput(
            results=detection.results,
            used_fallback=detection.used_fallback,
            extracted_text=transcript,
            details={
                "transcription_model": AUDIO_MODEL_NAME,
                "segments_processed": 1,
            },
        )

    def moderate_video(
        self,
        transcript_hint: str,
        frames: List[Dict[str, object]],
        vision_safety_scores: Dict[ModerationCategory, float] | None = None,
        vision_safety_labels: List[str] | None = None,
    ) -> MultimodalDetectionOutput:
        frame_texts: List[str] = []
        detected_objects: List[str] = []
        for frame in frames:
            frame_texts.append(str(frame.get("description", "")))
            frame_texts.append(str(frame.get("ocr_text", "")))
            detected_objects.extend([str(item) for item in frame.get("detected_objects", [])])

        combined_text = " ".join(
            part for part in [transcript_hint, " ".join(frame_texts), " ".join(detected_objects)] if part
        ).strip()
        detection = self.moderate(combined_text or "benign video")
        boosted = self._apply_image_heuristics(detection.results, detected_objects, combined_text)
        boosted = self._apply_visual_safety_scores(boosted, vision_safety_scores or {}, vision_safety_labels or [])

        # Video fusion keeps the max risk seen across transcript/frame cues.
        return MultimodalDetectionOutput(
            results=boosted,
            used_fallback=detection.used_fallback,
            extracted_text=combined_text,
            details={
                "frame_count": len(frames),
                "visual_safety_labels": vision_safety_labels or [],
                "fusion_model": VIDEO_MODEL_NAME,
                "transcription_model": AUDIO_MODEL_NAME if transcript_hint else "not_used",
            },
        )

    def _apply_visual_safety_scores(
        self,
        results: List[CategoryResult],
        visual_scores: Dict[ModerationCategory, float],
        labels: List[str],
    ) -> List[CategoryResult]:
        if not visual_scores:
            return results

        enriched: List[CategoryResult] = []
        for item in results:
            score = item.score
            reasons = list(item.reasons)
            visual_score = visual_scores.get(item.category)
            if visual_score is not None and visual_score > score:
                score = visual_score
                reasons.append(f"Local visual safety scan raised {item.category.value} risk.")
            enriched.append(
                CategoryResult(
                    category=item.category,
                    score=round(max(min(score, 0.99), 0.0), 4),
                    severity=score_to_severity(score),
                    reasons=reasons,
                )
            )
        return enriched

    def _apply_image_heuristics(
        self,
        results: List[CategoryResult],
        detected_objects: List[str],
        ocr_text: str,
        safe_search: Dict[str, str] | None = None,
    ) -> List[CategoryResult]:
        joined_objects = " ".join(detected_objects).lower()
        joined_text = ocr_text.lower()
        safe_search = safe_search or {}
        enriched: List[CategoryResult] = []

        for item in results:
            score = item.score
            reasons = list(item.reasons)

            if item.category is ModerationCategory.VIOLENCE and any(
                marker in joined_objects for marker in ("gun", "knife", "blood", "weapon")
            ):
                score = max(score, 0.82)
                reasons.append("Visual objects suggest violent imagery.")

            if item.category is ModerationCategory.SEXUAL_CONTENT and any(
                marker in joined_objects for marker in ("nudity", "lingerie", "bedroom")
            ):
                score = max(score, 0.8)
                reasons.append("Visual objects suggest sexual content.")

            if item.category is ModerationCategory.CHILD_SAFETY and (
                "underage" in joined_text or "child" in joined_objects
            ):
                score = max(score, 0.94)
                reasons.append("Combined OCR/object cues suggest child-safety risk.")

            if item.category is ModerationCategory.ILLEGAL_ACTIVITY and any(
                marker in joined_objects for marker in ("drugs", "pills", "counterfeit", "weapon")
            ):
                score = max(score, 0.8)
                reasons.append("Visual evidence suggests illegal activity.")

            if item.category is ModerationCategory.SEXUAL_CONTENT:
                adult = safe_search.get("adult", "UNKNOWN")
                racy = safe_search.get("racy", "UNKNOWN")
                if adult in {"LIKELY", "VERY_LIKELY"} or racy in {"LIKELY", "VERY_LIKELY"}:
                    score = max(score, 0.86)
                    reasons.append("Google Vision SafeSearch flagged adult or racy imagery.")
                elif adult == "POSSIBLE" or racy == "POSSIBLE":
                    score = max(score, 0.48)
                    reasons.append("Google Vision SafeSearch found possible adult or racy imagery.")

            if item.category is ModerationCategory.VIOLENCE:
                violence = safe_search.get("violence", "UNKNOWN")
                if violence in {"LIKELY", "VERY_LIKELY"}:
                    score = max(score, 0.86)
                    reasons.append("Google Vision SafeSearch flagged violent imagery.")
                elif violence == "POSSIBLE":
                    score = max(score, 0.5)
                    reasons.append("Google Vision SafeSearch found possible violent imagery.")

            enriched.append(
                CategoryResult(
                    category=item.category,
                    score=round(max(min(score, 0.99), 0.0), 4),
                    severity=score_to_severity(score),
                    reasons=reasons,
                )
            )

        return enriched
