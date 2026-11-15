"""What the prompts say per language of the conversation (`spoken`) and of the person's texts (`reader`).

A new language is one more entry of each table.
"""

NAMES = {"es": "Spanish", "en": "English"}

# The sources that the figure search prefers, by the language of the conversation.
SOURCES = {
    "es": "INE, Eurostat, BOE, Banco de España, ministries, OECD, EFE, Reuters, Maldita, Newtral, EFE Verifica",
    "en": "the national statistics office, the central bank, the official gazette and the ministries of the country "
          "the conversation is about, Eurostat, OECD, IMF, Reuters, AP, AFP Fact Check, PolitiFact, FactCheck.org, "
          "Full Fact",
}
EARLIER = {"es": "interviews, speeches, Maldita, Newtral",
           "en": "interviews, speeches, transcripts, PolitiFact, FactCheck.org, Full Fact"}

# The producer tiers of a figure, by the language of the conversation.
TIERS = {
    "es": """1. Independent statistics with international methods: INE, Eurostat, Banco de España, OECD.
2. Administrative records of a ministry: SEPE, Interior, Seguridad Social.
3. Government communication: La Moncloa, ministry press releases.
4. Producers under political control: CIS.
5. Think tanks and media of any side.
A measure built only from official records (for example SEPE registered unemployment plus SEPE's
"demandantes con relación laboral") takes the tier of those records, even when a think tank adds them up.""",
    "en": """1. Independent statistics with international methods: the national statistics office, the central bank,
   Eurostat, OECD.
2. Administrative records of a ministry or a public agency.
3. Government communication: the government's and the ministries' press releases.
4. Producers under political control.
5. Think tanks and media of any side.
A measure built only from official records takes the tier of those records, even when a think tank adds them up.""",
}

# The judge's example of a nitpick reason, in the reader's language.
NITPICK = {"es": "49,8 M frente a 49,4 M, el fondo se sostiene", "en": "49.8 M against 49.4 M, the substance holds"}

# How a voice is named, in the reader's language.
ROLES = {"es": ('"Ana Ruiz (invitada)"', '"Presentador"'), "en": ('"Jane Smith (guest)"', '"Host"')}

# A neutral context sentence, in the reader's language.
CONTEXT = {"es": "Ministro de Transportes del Gobierno de España desde noviembre de 2023.",
           "en": "Secretary of Transportation of the United States since 2021."}
