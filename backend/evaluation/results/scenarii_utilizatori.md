# Scenarii de utilizare – Secțiunea 6.4

Toate datele provin din rularea efectivă a sistemului TripCraft pe baza de date reală.
Scorurile de potrivire reprezintă similaritatea cosinus IDF-ponderată calculată de `compute_country_scores()` (v4.3).

---

## 1. Aventurier și viață de noapte
**Tip utilizator:** Tânăr solist pasionat de adrenalină și ieșiri nocturne
**Budget:** mid | **Sezon:** summer | **Stil:** solo | **Ritm:** packed

### Profil de taguri (top taguri, scor > 0.5)
| Tag | Scor Bayesian |
|-----|---------------|
| `hiking` | 0.6667 |
| `rock-climbing` | 0.6667 |
| `via-ferrata` | 0.6667 |
| `white-water-rafting` | 0.6667 |
| `paragliding` | 0.6667 |
| `techno-clubs` | 0.6667 |
| `pub-crawls` | 0.6667 |
| `underground-clubs` | 0.6667 |

**Carduri chestionar:** 26  |  **Entropie finală:** 3.7004

### Clasificare țări
| Rang | Țara | Scor potrivire |
|------|------|----------------|
| 1 | France | 0.8040 |
| 2 | Croatia | 0.7952 |
| 3 | Slovakia | 0.7702 |
| 4 | Germany | 0.7932 |

### Țara recomandată: **France** (scor = 0.8040)

### Taguri relevante ale țării (explică potrivirea)
| Tag | Scor user | Scor țară | IDF | Contribuție |
|-----|-----------|-----------|-----|-------------|
| `paragliding` | 0.6667 | 0.6800 | 1.2350 | 0.7361 |
| `hiking` | 0.6667 | 0.7800 | 1.0000 | 0.7280 |
| `techno-clubs` | 0.6667 | 0.7200 | 1.0390 | 0.6909 |

**Orașe vizitate:** Paris, Lyon

### Atracții reprezentative pe zile
**Ziua 1 – Paris**
- Catedrala Notre-Dame (1.0h, scor=0.1870)
- Sainte-Chapelle (1.0h, scor=0.1795)
- Grădinile Tuileries (1.5h, scor=0.1795)
- Turnul Eiffel (1.5h, scor=0.1870)
- Arc de Triomphe (1.0h, scor=0.2000)
**Ziua 2 – Lyon**
- Vieux Lyon & Traboules (1.5h, scor=0.1870)
- Basilique Notre-Dame de Fourvière (1.0h, scor=0.1870)
- Place Bellecour (0.5h, scor=0.1938)
- Les Halles de Lyon Paul Bocuse (1.5h, scor=0.2237)
- Parc de la Tête d'Or (2.0h, scor=0.2000)

---

## 2. Istorie și gastronomie
**Tip utilizator:** Cuplu interesat de patrimoniu cultural și experiențe culinare
**Budget:** mid | **Sezon:** autumn | **Stil:** couple | **Ritm:** balanced

### Profil de taguri (top taguri, scor > 0.5)
| Tag | Scor Bayesian |
|-----|---------------|
| `ancient-ruins` | 0.6667 |
| `history-museums` | 0.6667 |
| `castles-palaces` | 0.6667 |
| `roman-history` | 0.6667 |
| `gothic-architecture` | 0.6667 |
| `wine-vineyards` | 0.6667 |
| `michelin-restaurants` | 0.6667 |
| `cooking-classes` | 0.6667 |

**Carduri chestionar:** 26  |  **Entropie finală:** 3.5850

### Clasificare țări
| Rang | Țara | Scor potrivire |
|------|------|----------------|
| 1 | France | 0.8779 |
| 2 | Cyprus | 0.8000 |
| 3 | Spain | 0.8552 |
| 4 | Italy | 0.8553 |

### Țara recomandată: **France** (scor = 0.8779)

### Taguri relevante ale țării (explică potrivirea)
| Tag | Scor user | Scor țară | IDF | Contribuție |
|-----|-----------|-----------|-----|-------------|
| `michelin-restaurants` | 0.6667 | 0.9900 | 1.2350 | 1.1391 |
| `wine-vineyards` | 0.6667 | 0.9900 | 1.1783 | 1.0871 |
| `gothic-architecture` | 0.6667 | 0.9400 | 1.1608 | 1.0100 |

**Orașe vizitate:** Paris, Lyon

### Atracții reprezentative pe zile
**Ziua 1 – Paris**
- Catedrala Notre-Dame (1.0h, scor=0.3906)
- Sainte-Chapelle (1.0h, scor=0.3430)
- Grădinile Tuileries (1.5h, scor=0.1795)
- Turnul Eiffel (1.5h, scor=0.2863)
- Arc de Triomphe (1.0h, scor=0.4434)
**Ziua 2 – Lyon**
- Vieux Lyon & Traboules (1.5h, scor=0.4374)
- Basilique Notre-Dame de Fourvière (1.0h, scor=0.3331)
- Place Bellecour (0.5h, scor=0.1938)
- Les Halles de Lyon Paul Bocuse (1.5h, scor=0.4096)
- Parc de la Tête d'Or (2.0h, scor=0.2000)

---

## 3. Natură și relaxare
**Tip utilizator:** Persoană care caută liniște în natură și wellness profund
**Budget:** budget | **Sezon:** spring | **Stil:** couple | **Ritm:** relaxed

### Profil de taguri (top taguri, scor > 0.5)
| Tag | Scor Bayesian |
|-----|---------------|
| `national-parks` | 0.6667 |
| `forest-bathing` | 0.6667 |
| `lake-swimming` | 0.6667 |
| `stargazing` | 0.6667 |
| `birdwatching` | 0.6667 |
| `yoga-retreats` | 0.6667 |
| `digital-detox` | 0.6667 |
| `silence-retreats` | 0.6667 |

**Carduri chestionar:** 26  |  **Entropie finală:** 3.5850

### Clasificare țări
| Rang | Țara | Scor potrivire |
|------|------|----------------|
| 1 | Hungary | 0.7556 |
| 2 | Bosnia and Herzegovina | 0.7187 |
| 3 | Serbia | 0.7349 |
| 4 | Slovakia | 0.7164 |

### Țara recomandată: **Hungary** (scor = 0.7556)

### Taguri relevante ale țării (explică potrivirea)
| Tag | Scor user | Scor țară | IDF | Contribuție |
|-----|-----------|-----------|-----|-------------|
| `thermal-baths` | 0.6667 | 0.9900 | 1.1965 | 1.1038 |
| `lake-swimming` | 0.6667 | 0.6200 | 1.1116 | 0.6187 |
| `national-parks` | 0.6667 | 0.5800 | 1.0000 | 0.5414 |

**Orașe vizitate:** Budapesta, Debrecen

### Atracții reprezentative pe zile
**Ziua 1 – Budapesta**
- Nagyvásárcsarnok (Piața Mare) (1.5h, scor=0.2197)
- Széchenyi gyógyfürdő (2.5h, scor=0.3621)
**Ziua 2 – Debrecen**
- Nagyerdei Park (2.0h, scor=0.3337)
- Aquaticum Debrecen (3.5h, scor=0.3555)

---

## 4. Familie și confort
**Tip utilizator:** Familie cu copii care prioritizează siguranța și activitățile distractive
**Budget:** mid | **Sezon:** summer | **Stil:** family | **Ritm:** relaxed

### Profil de taguri (top taguri, scor > 0.5)
| Tag | Scor Bayesian |
|-----|---------------|
| `theme-parks` | 0.6667 |
| `petting-zoos` | 0.6667 |
| `zoos-aquariums` | 0.6667 |
| `playgrounds-parks` | 0.6667 |
| `science-interactive-museums` | 0.6667 |
| `kids-workshops` | 0.6667 |
| `accessible-attractions` | 0.6667 |
| `child-beaches` | 0.6667 |

**Carduri chestionar:** 26  |  **Entropie finală:** 3.5850

### Clasificare țări
| Rang | Țara | Scor potrivire |
|------|------|----------------|
| 1 | France | 0.7895 |
| 2 | Netherlands | 0.7681 |
| 3 | Cyprus | 0.7204 |
| 4 | Germany | 0.7788 |

### Țara recomandată: **France** (scor = 0.7895)

### Taguri relevante ale țării (explică potrivirea)
| Tag | Scor user | Scor țară | IDF | Contribuție |
|-----|-----------|-----------|-----|-------------|
| `theme-parks` | 0.6667 | 0.7200 | 1.6020 | 0.9633 |
| `hop-on-hop-off` | 0.6667 | 0.8000 | 1.0000 | 0.7467 |
| `child-beaches` | 0.6667 | 0.6200 | 1.3722 | 0.7123 |

**Orașe vizitate:** Paris, Lyon

### Atracții reprezentative pe zile
**Ziua 1 – Paris**
- Grădinile Tuileries (1.5h, scor=0.3210)
- Disneyland Paris (5.0h, scor=0.5327)
**Ziua 2 – Lyon**
- Place Bellecour (0.5h, scor=0.3184)
- Parc de la Tête d'Or (2.0h, scor=0.3842)

---

## 5. Urban, modern și social
**Tip utilizator:** Millennial urban conectat, pasionat de design, cafenele și events
**Budget:** mid | **Sezon:** any | **Stil:** group | **Ritm:** balanced

### Profil de taguri (top taguri, scor > 0.5)
| Tag | Scor Bayesian |
|-----|---------------|
| `contemporary-architecture` | 0.6667 |
| `designer-districts` | 0.6667 |
| `specialty-coffee` | 0.6667 |
| `rooftop-bars` | 0.6667 |
| `meetup-events` | 0.6667 |
| `pop-up-events` | 0.6667 |
| `street-art` | 0.6667 |
| `craft-beer` | 0.6667 |

**Carduri chestionar:** 26  |  **Entropie finală:** 3.7004

### Clasificare țări
| Rang | Țara | Scor potrivire |
|------|------|----------------|
| 1 | Germany | 0.7910 |
| 2 | Spain | 0.7630 |
| 3 | United Kingdom | 0.7892 |
| 4 | Belgium | 0.7829 |

### Țara recomandată: **Germany** (scor = 0.7910)

### Taguri relevante ale țării (explică potrivirea)
| Tag | Scor user | Scor țară | IDF | Contribuție |
|-----|-----------|-----------|-----|-------------|
| `craft-beer` | 0.6667 | 0.9500 | 1.0390 | 0.9196 |
| `designer-districts` | 0.6667 | 0.7200 | 1.2767 | 0.8059 |
| `tech-hubs` | 0.6667 | 0.7400 | 1.1965 | 0.7911 |

**Orașe vizitate:** Berlin, Munich

### Atracții reprezentative pe zile
**Ziua 1 – Berlin**
- Berliner Fernsehturm (1.0h, scor=0.3005)
- Brandenburger Tor (0.5h, scor=0.2966)
- Reichstagsgebäude (1.5h, scor=0.2745)
- Kurfürstendamm (1.5h, scor=0.4327)
- East Side Gallery (1.5h, scor=0.3401)
**Ziua 2 – Munich**
- Hofbräuhaus am Platzl (1.5h, scor=0.3181)
- Marienplatz (1.0h, scor=0.3187)
- Frauenkirche (1.0h, scor=0.2564)
- BMW Welt & Museum (3.0h, scor=0.3312)

---
