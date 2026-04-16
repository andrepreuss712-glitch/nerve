#!/usr/bin/env python3
"""
Aktualisiert das NERVE-Verkaufsprofil mit vollständigen Daten.
Ausführen: python scripts/update_nerve_profile.py

Erstellt von Claudian am 14.04.2026
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from database.db import db_session, get_session
from database.models import Profile

NERVE_PROFILE = {
    "basis": {
        "unternehmen": "NERVE — KI-Echtzeit-Vertriebsassistent. Wir coachen Vertriebler WÄHREND des Telefonats, nicht danach. Live-Coaching im Ohr, Training-Simulator zum Üben, PreCall-Recherche vor jedem Anruf. Deutsche Server, DSGVO als Architektur. Gegründet 2026, Sitz in Iserlohn.",
        "produktbeschreibung": "NERVE ist ein KI-gestützter Sales-Assistent der Vertrieblern in Echtzeit hilft — direkt während sie telefonieren. Die KI hört mit (nur den Berater im Cold Call, beide Seiten nur mit Consent im Meeting), erkennt Einwände, zeigt Gegenargumente, trackt die Kaufbereitschaft und gibt Hinweise zur richtigen Gesprächsphase. Dazu: Training-Simulator mit 6 Persönlichkeitstypen und Sekretärin-Modus zum Üben, automatische Firmen-Recherche vor dem Call, Lernkarten-System das aus echten Calls lernt, und ein Coach der wöchentlich Stärken und Schwächen analysiert. Alles im Browser, kein Download nötig. Picture-in-Picture Fenster schwebt über dem CRM.",
        "preismodell": "SaaS-Abo, monatlich kündbar. Starter, Pro und Business Stufen. Flat-Rate mit Fair-Use. Early Access: 50% Gründerrabatt auf alle Pläne, limitiert auf 50 Plätze. Keine Setup-Gebühr, keine Vertragslaufzeit.",
        "usps": [
            "Echtzeit-Coaching WÄHREND des Calls — nicht danach wie Gong oder Fireflies",
            "DSGVO-konform als Architektur — kein Audio wird gespeichert, deutsche Server",
            "Training-Simulator mit KI-Kunden die realistisch reagieren und auflegen können",
            "Kein Download nötig — läuft im Browser, PiP-Fenster über dem CRM",
            "Lernt aus deinen Calls — Lernkarten, Schwächen-Erkennung, Wochenreport",
            "PreCall-Recherche — KI recherchiert die Firma vor dem Anruf automatisch",
            "Cold Call Modus — KI hört NUR dich, nicht den Kunden. Null DSGVO-Risiko"
        ],
        "konsequenz": "Ohne NERVE telefoniert dein Team blind. Keine Echtzeit-Hilfe bei Einwänden, kein systematisches Training, kein Überblick über Schwächen. Jeder verlorene Deal kostet echtes Geld. Bei einem Dealwert von 5.000€ und einer Closing-Rate von 20% bringt jedes Prozent mehr Rate 50.000€ pro Jahr pro Vertriebler. NERVE amortisiert sich nach dem ersten gewonnenen Deal."
    },

    "opener": "Hallo [Name], André Preuß hier von NERVE. Kurze Frage — wenn Ihre Vertriebler gerade im Cold Call sind und ein Einwand kommt, woher wissen die in dem Moment was sie sagen sollen?",

    "erlaubnis": "Ich zeig Ihnen in 30 Sekunden warum ich anrufe — wenn's nicht passt, sagen Sie's direkt und ich bin weg. Fair?",

    "pitch": "Wir haben eine KI gebaut die Ihren Vertrieblern live im Gespräch coacht. Die hört mit, erkennt Einwände in Echtzeit und zeigt sofort das beste Gegenargument an — als kleines Fenster das über dem CRM schwebt. Dazu ein Training-Simulator wo Ihre Leute gegen KI-Kunden üben können die realistisch reagieren, und eine automatische Firmen-Recherche vor jedem Anruf. Das Ganze DSGVO-konform, deutsche Server, kein Audio wird gespeichert. Ihre Leute werden messbar besser, Call für Call.",

    "zielgruppe": {
        "alter": "30-55",
        "berufsstatus": "Vertriebsleiter, Head of Sales, VP Sales, Geschäftsführer mit Vertriebsverantwortung, Sales Team Leads",
        "einkommensniveau": "60.000-150.000€ Jahresgehalt",
        "lebenssituation": "Verantwortlich für Umsatzziele, steht unter Druck die Zahlen zu liefern. Hat ein Team von 3-50 Vertrieblern. Sucht nach Wegen die Abschlussquote zu steigern ohne mehr Leute einzustellen.",
        "beruflicher_hintergrund": [
            "B2B-Vertrieb",
            "Outbound Sales",
            "Telefonakquise",
            "SaaS-Vertrieb",
            "Versicherungsvertrieb",
            "Finanzdienstleistungen",
            "Personalvermittlung",
            "IT-Dienstleistungen"
        ],
        "vorwissen": "mittel",
        "entscheidungsverhalten": [
            "ROI-getrieben — will wissen was es bringt in Euro",
            "Braucht Proof — Demo oder Testphase",
            "Entscheidet oft nicht allein — muss Geschäftsführung überzeugen",
            "Misstrauisch bei KI-Versprechen — hat schon Tools gesehen die nichts gebracht haben",
            "Zeitdruck — will schnelle Ergebnisse, nicht monatelanges Onboarding"
        ]
    },

    "schmerzen": {
        "schmerzpunkte": [
            {
                "situation": "Neue Vertriebler brauchen 3-6 Monate bis sie produktiv sind",
                "kern": "Onboarding-Kosten sind enorm — Gehalt läuft, Umsatz kommt nicht",
                "verstaerken": "Was kostet Sie jeder Monat in dem ein neuer Mitarbeiter unter Ziel bleibt? Bei 5.000€ Gehalt und 3 Monaten Ramp-Up sind das 15.000€ bevor der erste Euro reinkommt."
            },
            {
                "situation": "Vertriebler verlieren Deals an immer den gleichen Einwänden",
                "kern": "Kein systematisches Einwand-Training, jeder wurschtelt sich durch",
                "verstaerken": "Wenn 3 von 10 Deals am Preiseinwand scheitern und Ihr Dealwert bei 10.000€ liegt — das sind 30.000€ die jeden Monat liegen bleiben. Nicht weil das Produkt zu teuer ist, sondern weil die Antwort nicht saß."
            },
            {
                "situation": "Coaching passiert nur im Nachhinein oder gar nicht",
                "kern": "Vertriebsleiter kann nicht in jedem Call dabei sitzen",
                "verstaerken": "Wie viele Calls pro Woche können Sie persönlich mithören? 5? 10? Ihre Leute machen 200. Die anderen 190 sind ungecoacht."
            },
            {
                "situation": "CRM-Daten sind dünn — niemand pflegt nach dem Call ordentlich ein",
                "kern": "Keine Datengrundlage für Coaching-Gespräche oder Pipeline-Reviews",
                "verstaerken": "Sie sitzen im Weekly und fragen 'Wie lief der Call mit Firma X?' und die Antwort ist 'Ganz gut, ich ruf nochmal an'. Kein Score, kein Einwand-Log, kein Lerneffekt."
            },
            {
                "situation": "Hohe Fluktuation im Vertrieb — gute Leute gehen, neue kommen",
                "kern": "Wissen geht verloren, Aufbau fängt von vorne an",
                "verstaerken": "Jeder Vertriebler der geht nimmt seine Erfahrung mit. Jeder neue fängt bei Null an. NERVE speichert was funktioniert — die Lernkarten, die Phrasen, die Techniken bleiben."
            }
        ],
        "trigger": {
            "verlust": 9,
            "familie": 2,
            "status": 7,
            "zahlen": 10,
            "dringlichkeit": 7,
            "micro": 5
        }
    },

    "phasen": [
        {
            "name": "Opener",
            "ziel": "Aufmerksamkeit gewinnen, Gesprächsbereitschaft herstellen. Nicht pitchen!",
            "skript": [
                "Hallo [Name], André Preuß hier von NERVE.",
                "Kurze Frage — wenn Ihre Vertriebler gerade im Cold Call sind und ein Einwand kommt, woher wissen die in dem Moment was sie sagen sollen?",
                "NICHT: 'Ich rufe an weil wir ein tolles Produkt haben...'",
                "Ziel: Der Prospect soll nachdenken, nicht abwehren."
            ]
        },
        {
            "name": "Erlaubnis",
            "ziel": "Berechtigung zum Weiterreden holen. Respekt zeigen, Kontrolle geben.",
            "skript": [
                "Ich zeig Ihnen in 30 Sekunden warum ich anrufe — wenn's nicht passt, sagen Sie's direkt.",
                "Alternativ: 'Haben Sie kurz 2 Minuten? Ich komm direkt zum Punkt.'",
                "WICHTIG: Wenn er Nein sagt → akzeptieren, Follow-Up vorschlagen."
            ]
        },
        {
            "name": "Bedarfsanalyse",
            "ziel": "Pain herausfinden. Fragen statt pitchen. Verstehen wie der Vertrieb aktuell läuft.",
            "skript": [
                "Wie viele Leute telefonieren bei Ihnen aktiv raus?",
                "Wie läuft das Onboarding wenn ein Neuer anfängt?",
                "Wie coachen Sie aktuell — hören Sie mit rein, oder eher im Nachgang?",
                "Was passiert wenn ein Einwand kommt den der Vertriebler nicht drauf hat?",
                "ZUHÖREN — nicht sofort NERVE als Lösung präsentieren."
            ]
        },
        {
            "name": "Pitch",
            "ziel": "NERVE vorstellen, aber NUR auf die Pains eingehen die er genannt hat.",
            "skript": [
                "Genau da setzt NERVE an — [konkreten Pain aufgreifen].",
                "Die KI coacht Ihre Leute live im Gespräch. Kleines Fenster über dem CRM.",
                "Erkennt Einwände in Echtzeit, zeigt sofort das beste Gegenargument.",
                "Dazu Training-Simulator zum Üben und automatische Firmen-Recherche.",
                "DSGVO-konform, deutsche Server, kein Audio wird gespeichert.",
                "NICHT alles aufzählen — nur was zu seinem Problem passt."
            ]
        },
        {
            "name": "Einwandbehandlung",
            "ziel": "Einwände ernst nehmen, nicht wegargumentieren. Verstehen ob Vorwand oder echt.",
            "skript": [
                "Verstehe ich — [Einwand wiederholen]. Darf ich fragen was genau Sie meinen?",
                "IMMER: Erst verstehen, dann antworten.",
                "Bei 'zu teuer': Was kostet Sie ein verlorener Deal? NERVE muss sich nur mit einem einzigen gewonnenen Deal amortisieren.",
                "Bei 'haben wir schon': Was genau nutzen Sie? Die meisten Tools analysieren nachher — wir coachen live."
            ]
        },
        {
            "name": "Abschluss",
            "ziel": "Konkreten nächsten Schritt vereinbaren. Demo, Trial, oder Termin.",
            "skript": [
                "Ich schlage vor: Ich zeig Ihnen das in 15 Minuten live. Sie sehen wie das aussieht, und dann entscheiden Sie ob es passt.",
                "Wir haben gerade 50 Early Access Plätze mit 50% Gründerrabatt — die gehen erfahrungsgemäß schnell weg.",
                "Wann passt Ihnen diese Woche besser — Mittwoch oder Donnerstag?",
                "IMMER einen konkreten Termin vorschlagen, nicht 'melden Sie sich wenn Sie Interesse haben'."
            ]
        }
    ],

    "einwaende": [
        {
            "kategorie": "Preis",
            "intensitaet": "hoch",
            "einwand": "Das ist uns zu teuer",
            "varianten": [
                "Dafür haben wir kein Budget",
                "Das können wir uns gerade nicht leisten",
                "Was kostet das nochmal genau?",
                "Das ist zu viel für ein KI-Tool"
            ],
            "gegenargument": "Verstehe ich. Lassen Sie mich kurz gegenrechnen: Wenn einer Ihrer Vertriebler durch NERVE auch nur einen Deal mehr pro Monat macht — bei Ihrem Dealwert rechnet sich das ab Tag 1. Was kostet Sie aktuell ein verlorener Deal?",
            "technik": "Kosten-Nutzen-Umkehr: Nicht was NERVE kostet fragen, sondern was es kostet NERVE NICHT zu haben."
        },
        {
            "kategorie": "Zeit",
            "intensitaet": "mittel",
            "einwand": "Ich habe gerade keine Zeit dafür",
            "varianten": [
                "Rufen Sie nächstes Quartal nochmal an",
                "Wir sind gerade mitten in einem Projekt",
                "Das Timing passt nicht"
            ],
            "gegenargument": "Verstehe ich, gerade ist viel los. Deswegen ganz kurz: NERVE braucht kein IT-Projekt und kein Onboarding das Wochen dauert. Ihre Leute loggen sich ein und telefonieren — die KI läuft ab dem ersten Call. Wenn Ihnen 15 Minuten für eine Demo zu viel sind, dann ist das wahrscheinlich wirklich nicht das Richtige. Aber wenn doch — wann passt es diese Woche kurz?",
            "technik": "Zeitdruck relativieren + minimalen Aufwand betonen. NERVE ist keine Einführung, es ist ein Login."
        },
        {
            "kategorie": "Bedarf",
            "intensitaet": "hoch",
            "einwand": "Wir brauchen sowas nicht",
            "varianten": [
                "Unsere Leute können das schon",
                "Wir haben genug Erfahrung im Team",
                "KI im Vertrieb brauchen wir nicht"
            ],
            "gegenargument": "Ihre besten Leute brauchen das wahrscheinlich nicht — die sind Profis. Aber was ist mit den anderen 80%? Die Neuen, die Mittelmäßigen, die die bei Preiseinwänden immer noch ins Schwimmen kommen? NERVE hebt nicht die Besten an — es zieht den Durchschnitt hoch. Und das ist wo der Umsatz liegt.",
            "technik": "Nicht den Besten verkaufen, sondern den Hebel beim Durchschnitt zeigen."
        },
        {
            "kategorie": "Vertrauen",
            "intensitaet": "hoch",
            "einwand": "KI im Verkaufsgespräch? Das klingt nach Manipulation",
            "varianten": [
                "Ich will nicht dass eine KI meine Leute steuert",
                "Das klingt creepy",
                "Unsere Kunden würden das nicht wollen"
            ],
            "gegenargument": "Gute Frage — und deswegen haben wir NERVE so gebaut: Im Cold Call hört die KI NUR Ihren Vertriebler, nicht den Kunden. Kein Audio wird gespeichert. Deutsche Server, alles DSGVO-konform. NERVE manipuliert nicht — es ist wie ein erfahrener Kollege der daneben sitzt und einen Zettel rüberschiebt wenn es eng wird. Würden Sie Ihrem besten Vertriebler verbieten einem Neuen Tipps zu geben?",
            "technik": "Reframing: NERVE ist kein Big Brother sondern ein Mentor. DSGVO als Vertrauensbeweis."
        },
        {
            "kategorie": "Wettbewerb",
            "intensitaet": "mittel",
            "einwand": "Wir nutzen schon Gong / Fireflies / ein anderes Tool",
            "varianten": [
                "Wir haben schon was dafür",
                "Unser CRM kann das auch",
                "Wir nutzen CloseAI"
            ],
            "gegenargument": "Welches Tool nutzen Sie? [Zuhören] — Die meisten dieser Tools analysieren NACH dem Call. Das ist super für Reviews, aber im Moment wo der Einwand kommt hilft das nicht. NERVE coacht LIVE — in dem Moment wo es drauf ankommt. Das ist der Unterschied zwischen einem Videocoach der das Spiel danach analysiert und einem Trainer der an der Seitenlinie steht.",
            "technik": "Differenzierung: Post-Call vs. Live. Nicht schlecht über Konkurrenz reden, sondern den Unterschied klar machen."
        },
        {
            "kategorie": "Entscheider",
            "intensitaet": "mittel",
            "einwand": "Das muss ich mit meinem Chef / der GF besprechen",
            "varianten": [
                "Die Entscheidung liegt nicht bei mir",
                "Da muss ich erstmal intern abstimmen",
                "Schicken Sie mir Unterlagen, ich leite das weiter"
            ],
            "gegenargument": "Verstehe — wer entscheidet denn bei Ihnen über neue Vertriebstools? [Name erfragen] Wie wäre es wenn wir zu dritt 15 Minuten machen? Dann sieht er direkt was es kann und Sie müssen nichts weiterleiten. Ist oft einfacher als eine interne Präsentation vorzubereiten.",
            "technik": "Entscheider mit ins Gespräch holen statt Material schicken. Material wird ignoriert."
        },
        {
            "kategorie": "Datenschutz",
            "intensitaet": "hoch",
            "einwand": "Was ist mit Datenschutz? Wir telefonieren mit Kunden.",
            "varianten": [
                "Hört die KI die Kundengespräche mit?",
                "Wird das aufgezeichnet?",
                "Unser Datenschutzbeauftragter würde das nie erlauben"
            ],
            "gegenargument": "Die Frage kommt immer — und sie ist berechtigt. Kurze Antwort: NERVE speichert KEIN Audio. Null. Im Cold Call hört die KI NUR Ihren Vertriebler, nicht den Kunden. Für Meetings gibt es einen Consent-Flow wo der Kunde explizit zustimmt. Alles auf deutschen Servern in Nürnberg. Das ist keine Nachbesserung, das ist unsere Architektur von Tag 1. Geben Sie das gerne an Ihren DSB weiter — wir haben das für genau diese Frage gebaut.",
            "technik": "DSGVO als Feature verkaufen, nicht als Pflicht. 'Wir haben das FÜR diese Frage gebaut.'"
        },
        {
            "kategorie": "Skepsis",
            "intensitaet": "mittel",
            "einwand": "KI-Tools versprechen viel und halten wenig",
            "varianten": [
                "Wir haben schon andere KI-Sachen probiert, bringt nichts",
                "Das klingt zu gut um wahr zu sein",
                "Wie soll eine KI wissen was im Verkauf funktioniert?"
            ],
            "gegenargument": "Verstehe die Skepsis — es gibt viel Hype und wenig Substanz im KI-Bereich. Deswegen sage ich nicht 'glauben Sie mir', sondern 'testen Sie es'. 14 Tage, Ihr Team telefoniert wie immer, NERVE läuft mit. Entweder die Zahlen werden besser oder Sie kündigen. Kein Risiko, keine Verpflichtung. Wenn es nicht funktioniert haben Sie 15 Minuten für die Demo investiert.",
            "technik": "Nicht argumentieren sondern einladen zum Testen. Risiko auf Null senken."
        }
    ],

    "fragen": [
        {
            "frage": "Wie funktioniert das technisch? Muss ich was installieren?",
            "antwort": "Nein, NERVE läuft komplett im Browser. Ihre Vertriebler loggen sich ein, klicken auf 'Call starten', und ein kleines Fenster schwebt über dem CRM. Kein Download, kein Plugin, keine IT-Abteilung nötig. Einzige Voraussetzung: Chrome oder Edge und ein Mikrofon."
        },
        {
            "frage": "Funktioniert das auch bei uns in der Branche?",
            "antwort": "NERVE ist branchenunabhängig — die Verkaufsprofile sind individuell. Ihre Leute tragen ihr Produkt, ihre Zielgruppe und ihre typischen Einwände ein. Die KI coacht dann auf Basis DIESER Daten. Ob Sie Software, Versicherungen oder Maschinen verkaufen spielt keine Rolle."
        },
        {
            "frage": "Wie lange dauert das Onboarding?",
            "antwort": "Am ersten Tag. Profil anlegen dauert 15-20 Minuten — Produkt beschreiben, typische Einwände eintragen, fertig. Danach ist NERVE sofort einsatzbereit. Kein wochenlanges Training, kein Consulting."
        },
        {
            "frage": "Was kostet das pro User?",
            "antwort": "Aktuell sind wir in der Early Access Phase mit 50% Gründerrabatt. Die regulären Preise liegen zwischen Starter und Business je nach Teamgröße. Am besten zeige ich Ihnen das in der Demo — dann sehen Sie auch direkt welcher Plan zu Ihrem Team passt."
        },
        {
            "frage": "Können wir das erstmal mit einem Vertriebler testen?",
            "antwort": "Absolut — genau so machen es die meisten. Einer testet, die anderen schauen sich die Ergebnisse an. Wenn der nach 2 Wochen bessere Zahlen hat, ist die Entscheidung für den Rest des Teams einfach."
        },
        {
            "frage": "Was unterscheidet euch von Gong?",
            "antwort": "Gong ist Post-Call Analytics — hervorragend für Reviews und Coaching nach dem Gespräch. NERVE coacht LIVE, in dem Moment wo der Einwand kommt. Das sind zwei verschiedene Sachen. Gong sagt Ihnen was schiefgelaufen ist. NERVE verhindert dass es schiefläuft."
        }
    ],

    "kaufsignale": [
        {
            "signal": "Fragt nach Preisen oder Konditionen",
            "beschreibung": "Will wissen was es kostet = denkt ernsthaft drüber nach. Jetzt nicht ausweichen sondern transparent antworten und auf Demo/Trial überleiten."
        },
        {
            "signal": "Fragt wie das Onboarding läuft",
            "beschreibung": "Denkt schon an die Umsetzung. Betonen: 15 Minuten Profil anlegen, sofort einsatzbereit. Kein IT-Projekt."
        },
        {
            "signal": "Erwähnt spezifische Probleme im Team",
            "beschreibung": "Gibt echten Pain preis. Sofort aufgreifen: 'Genau da hilft NERVE — darf ich Ihnen zeigen wie?'"
        },
        {
            "signal": "Fragt ob das in seiner Branche funktioniert",
            "beschreibung": "Prüft Relevanz = ernstes Interesse. Branchenunabhängigkeit betonen, individuelle Profile."
        },
        {
            "signal": "Fragt nach einer Demo oder Testphase",
            "beschreibung": "Stärkstes Kaufsignal. Sofort Termin machen. Nicht erst Unterlagen schicken."
        },
        {
            "signal": "Vergleicht mit vorhandenem Tool",
            "beschreibung": "Ist im Evaluierungsmodus. Differenzierung Live vs. Post-Call. Nicht schlecht über Konkurrenz reden."
        },
        {
            "signal": "Fragt ob andere in der Branche das nutzen",
            "beschreibung": "Social Proof. Ehrlich sein: 'Wir sind in der Early Access Phase, deswegen gibt es den Gründerrabatt. Die ersten 50 Tester formen das Produkt mit.'"
        }
    ],

    "nogos": [
        {
            "kriterium": "Firma hat keinen aktiven Outbound-Vertrieb",
            "beschreibung": "Wenn niemand telefoniert, braucht niemand NERVE. Höflich raus, nicht überzeugen wollen."
        },
        {
            "kriterium": "Einzelkämpfer ohne Team und ohne Telefon-Sales",
            "beschreibung": "NERVE ist für Teams gebaut. Ein Freelancer der 2 Calls pro Woche macht ist kein guter Fit."
        },
        {
            "kriterium": "Prospect will nur schriftlichen Vertrieb (Email/LinkedIn)",
            "beschreibung": "NERVE ist ein Telefon-Tool. Kein Fit für rein schriftlichen Vertrieb."
        },
        {
            "kriterium": "Budget unter 50€ pro Monat pro User",
            "beschreibung": "Unter dem Starter-Plan gibt es nichts. Nicht runterhandeln, sondern ROI rechnen."
        }
    ],

    "wettbewerber": [
        {
            "name": "CloseAI",
            "schwaeche": "169€ für nur 10 Calls pro Monat — extrem teuer pro Call. Desktop-App nötig (Download + Installation). Kein Training-Simulator. Deutscher Anbieter aber weniger bekannt.",
            "vorteil": "NERVE: Flat-Rate statt Call-Limit, Browser-basiert (kein Download), Training-Simulator inklusive, günstiger bei mehr Calls."
        },
        {
            "name": "Gong",
            "schwaeche": "Nur Post-Call Analyse — hilft im Moment des Einwands nicht. Enterprise-Pricing (5-stellig/Jahr). Komplexes Onboarding. US-Server.",
            "vorteil": "NERVE: Live-Coaching statt Nachbesprechung. Sofort einsatzbereit, kein Enterprise-Vertrag nötig. Deutsche Server."
        },
        {
            "name": "Fireflies.ai",
            "schwaeche": "Meeting-Transkription, kein Live-Coaching. Keine Einwand-Erkennung, keine Gegenargumente. Eher für interne Meetings als für Sales.",
            "vorteil": "NERVE: Gebaut für Vertrieb, nicht für Meetings. Live-Coaching, Einwand-Erkennung, Training."
        },
        {
            "name": "Chorus (ZoomInfo)",
            "schwaeche": "Aufgekauft von ZoomInfo, nur im Bundle erhältlich. Post-Call Analyse. Teuer, Enterprise-only. US-Server.",
            "vorteil": "NERVE: Eigenständig, faire Preise, Live statt Post-Call, DSGVO-konform."
        }
    ],

    "techniken": {
        "aktiv": [
            "Offene Fragen stellen",
            "Pain vertiefen bevor Lösung anbieten",
            "Einwand wiederholen und validieren",
            "Kosten-Nutzen-Umkehr bei Preiseinwänden",
            "Konkreten nächsten Schritt vorschlagen",
            "Alternative-Close (Mittwoch oder Donnerstag?)",
            "Social Proof durch Early Access Exklusivität",
            "ROI vorrechnen mit konkreten Zahlen",
            "Reframing — Problem aus anderer Perspektive zeigen"
        ],
        "verboten": [
            "Konkurrenz schlecht machen",
            "Zu früh pitchen bevor der Pain klar ist",
            "Nachgeben beim Preis ohne Gegenleistung",
            "Druck aufbauen oder manipulieren",
            "Fachbegriffe nutzen die der Prospect nicht kennt",
            "Versprechen machen die NERVE nicht halten kann",
            "Monologe halten statt Fragen stellen"
        ],
        "offene_fragen": "Wie sieht ein typischer Tag bei Ihren Vertrieblern aus? Was passiert wenn ein Neuer anfängt — wie lange dauert es bis der produktiv ist? Wie messen Sie aktuell die Qualität der Telefonate? Was würde sich ändern wenn Ihre Closing-Rate um 10% steigen würde?"
    },

    "uebergaenge": [
        {
            "von": "Opener",
            "nach": "Erlaubnis",
            "bruecke": "Gute Frage oder? Ich zeig Ihnen in 30 Sekunden warum ich frage..."
        },
        {
            "von": "Erlaubnis",
            "nach": "Bedarfsanalyse",
            "bruecke": "Danke. Damit ich Ihnen was Sinnvolles zeigen kann — kurze Frage vorab..."
        },
        {
            "von": "Bedarfsanalyse",
            "nach": "Pitch",
            "bruecke": "Genau das höre ich oft. Und genau da setzt NERVE an..."
        },
        {
            "von": "Pitch",
            "nach": "Einwandbehandlung",
            "bruecke": "Was ist Ihr erster Gedanke dazu?"
        },
        {
            "von": "Einwandbehandlung",
            "nach": "Abschluss",
            "bruecke": "Macht das Sinn für Sie? Dann lassen Sie uns einen konkreten nächsten Schritt machen."
        }
    ],

    "ki": {
        "ton": "Direkt, auf Augenhöhe, kein Berater-Deutsch. Kurze Sätze, klare Aussagen. Wie ein erfahrener Vertriebskollege der einem Tipp gibt — nicht wie ein Coach der doziert.",
        "ansprache": "Sie",
        "antwortlaenge": "1-2 Sätze",
        "sensitivitaet": "hoch",
        "zusatz": "Immer zuerst den Einwand validieren bevor ein Gegenargument kommt. Nie aggressiv. Wenn der Prospect kein Interesse hat, respektieren — nicht überreden. NERVE verkauft sich über Nutzen, nicht über Druck. Wichtig: DSGVO und Datenschutz sind USP, nicht Pflicht. Bei jeder Gelegenheit betonen dass kein Audio gespeichert wird und alles auf deutschen Servern läuft."
    }
}


def main():
    with app.app_context():
        session = get_session()
        try:
            # Profil finden (erstes aktives Profil oder per Name)
            profile = session.query(Profile).filter(
                Profile.name.ilike('%nerve%')
            ).first()

            if not profile:
                # Fallback: erstes Profil
                profile = session.query(Profile).first()

            if not profile:
                print("Kein Profil gefunden. Erstelle neues...")
                profile = Profile(
                    org_id=1,
                    name="NERVE Sales",
                    branche="SaaS / KI / Vertriebstechnologie",
                    daten=json.dumps(NERVE_PROFILE, ensure_ascii=False),
                    erstellt_von=1
                )
                session.add(profile)
            else:
                print(f"Profil gefunden: '{profile.name}' (ID: {profile.id})")
                profile.daten = json.dumps(NERVE_PROFILE, ensure_ascii=False)
                profile.branche = "SaaS / KI / Vertriebstechnologie"
                print("Profil aktualisiert.")

            session.commit()
            print(f"Gespeichert. Profil-ID: {profile.id}")
            print(f"JSON-Größe: {len(profile.daten)} Zeichen")
        finally:
            session.close()


if __name__ == '__main__':
    main()
