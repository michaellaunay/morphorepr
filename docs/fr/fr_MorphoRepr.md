# MorphoRepr : un langage contrôlé à structure morphologique pour la description des features SAE des LLMs
## Un article de positionnement et protocole d'évaluation

**Title (English):** MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol

**Michaël Launay**
Logikascium (EURL), Fretin, France
Enseignant vacataire, Université de Lille / ENSAM Lille / Polytech Lille
michaellaunay@logikascium.com

---

*Preprint — article de positionnement et protocole d'évaluation — soumis à arXiv cs.CL / HAL*
*Version 0.25 — Juin 2026*
*Remplace la version 0.24. Aucun résultat expérimental n'est revendiqué dans cette version ; les résultats seront rapportés à l'issue de l'exécution du pipeline.*

---

## Résumé

Les descriptions en langue naturelle des features des autoencodeurs sparses (SAEs) dans les grands modèles de langage (LLMs) sont précises mais insuffisamment structurées pour l'évaluation systématique, la comparaison inter-features, l'agrégation statistique et la prédiction causale. Elles sont vagues, inconsistantes entre runs d'annotation, et résistent à la manipulation formelle. Nous proposons **MorphoRepr**, un langage contrôlé à structure morphologique inspiré de la grammaire agglutinante de l'espéranto, conçu comme couche d'annotation lisible par l'humain pour les features sparses produits par des SAEs entraînés sur les activations de LLMs. Chaque expression MorphoRepr encode des hypothèses humaines sur la sémantique d'un ou plusieurs latents SAE sous forme d'une chaîne compositionnelle de morphèmes à sémantique formellement définie, pondérés par des coefficients d'activation normalisés. MorphoRepr ne prétend pas décoder les représentations internes des LLMs ; il encode des hypothèses humaines structurées sur la sémantique des latents SAE, hypothèses qui doivent être validées par des expériences de prédiction d'activation et d'intervention causale.

Nous présentons le cadre formel, un pipeline d'évaluation agentique en cinq phases, et un protocole d'évaluation complet spécifiant des métriques de couverture, fidélité, validité causale, productivité morphologique et cohérence d'annotation — incluant des comparaisons directes aux étiquettes en langue naturelle, aux Semantic Regexes (Boggust et al., 2025), aux tags-mots-clés contrôlés et à un contrôle par annotations mélangées. La question ouverte centrale est de savoir si la composition morphologique agglutinante apporte un avantage mesurable sur ces alternatives en cohérence d'annotation, compacité et pouvoir prédictif causal. Les résultats expérimentaux seront rapportés dans une version ultérieure à l'issue de l'exécution du pipeline.

**Mots-clés :** interprétabilité mécaniste, autoencodeurs sparses, morphologie agglutinante, espéranto, annotation de features SAE, langage contrôlé, validité causale, productivité morphologique

---

## Abstract (English)

Natural language descriptions of SAE features in LLMs are accurate but insufficiently structured for systematic evaluation, cross-feature comparison, and causal prediction. We propose MorphoRepr, a morphologically structured controlled language for SAE feature annotation, and present a five-phase agentic evaluation pipeline with a complete evaluation protocol including fidelity as a discrimination task, causal validity via output property classifiers with confidence intervals, morphological productivity metrics, and a planned user study. This is a position paper; no experimental claims are made.

**Keywords:** mechanistic interpretability, sparse autoencoders, agglutinative morphology, Esperanto, SAE feature annotation, controlled language, causal validity, morphological productivity

---

## 1. Introduction

Les représentations internes des grands modèles de langage (LLMs) demeurent largement opaques à l'inspection humaine. Les autoencodeurs sparses (SAEs) ont émergé comme un outil scalable pour décomposer ces représentations en directions de features plus sparses et plus monosémantiques (Bricken et al., 2023 ; Cunningham et al., 2023 ; Anthropic, 2024). Les latents résultants sont plus interprétables que les neurones individuels, mais le problème de leur *labélisation* à grande échelle — leur assigner des descriptions précises, cohérentes et formellement manipulables — demeure un goulot d'étranglement significatif.

Les approches actuelles s'appuient sur des étiquettes en langue naturelle générées par des LLMs, utiles pour l'interprétation humaine mais présentant des limitations bien connues comme système de notation formelle : imprécision, inconsistance entre runs, et inadaptation au raisonnement compositionnel ou à la comparaison statistique sur de grands inventaires de features (Boggust et al., 2025 ; Paulo et al., 2024). Le défi n'est pas que la langue naturelle soit inexpressive en principe — elle peut décrire presque tout, au prix de la verbosité. Le défi est que les descriptions en langue naturelle sont **insuffisamment structurées** pour les tâches systématiques que requiert l'interprétabilité à grande échelle : comparaison inter-features, statistiques au niveau des morphèmes, prédiction causale à partir de l'étiquette seule, et recherche programmatique dans les espaces de features.

Ce papier propose **MorphoRepr**, un langage contrôlé pour l'annotation des features SAE qui répond à ces limitations en empruntant la logique structurelle de l'espéranto — composition agglutinante, inventaire fini de morphèmes, règles dérivationnelles transparentes — et en l'étendant avec un vocabulaire contrôlé de primitives sémantiques dérivées empiriquement de l'espace de features SAE d'un LLM de production. L'affirmation centrale n'est pas que MorphoRepr capture la géométrie interne des représentations LLM — il ne le fait explicitement pas — mais qu'il peut fournir un système d'annotation plus cohérent, plus compact et plus prédictif causalement que les alternatives existantes pour le sous-ensemble de latents SAE dont le contenu est stable et morpho-sémantiquement exprimable.

**Note sur la portée.** MorphoRepr encode des hypothèses humaines sur la sémantique des latents SAE. Un latent SAE n'est pas équivalent à un concept humain : les latents sont des directions apprises dans l'espace d'activation, dépendantes des objectifs de reconstruction, des contraintes de sparsité, des statistiques du corpus et de l'architecture du modèle. Leur interprétabilité est prometteuse mais partielle. Les descriptions MorphoRepr sont des hypothèses sur le contenu des latents, non des vérités sur les représentations internes du modèle.

### 1.1 Contributions

Ce papier apporte les contributions suivantes :

1. **Conceptuelle** : nous proposons MorphoRepr comme langage contrôlé pour l'annotation des features SAE et établissons son ancrage théorique dans l'hypothèse de représentation linéaire et l'hypothèse de superposition.

2. **Méthodologique** : nous décrivons un pipeline agentique en cinq phases pour induire empiriquement un lexique MorphoRepr à partir de features SAE, et spécifions un protocole d'évaluation complet incluant la couverture, la fidélité (comme tâche de discrimination), la validité causale (avec classifieurs automatiques de propriétés de sortie et intervalles de confiance), des métriques de productivité morphologique, des métriques de cohérence d'annotation au niveau morphémique, et une étude utilisateur planifiée.

3. **Prospective** : nous identifions les questions de recherche ouvertes que les versions expérimentales ultérieures devront traiter, discutons les menaces à la validité, et esquissons un agenda de recherche à plus long terme.

### 1.2 Statut du papier

Ce papier est un **article de positionnement et protocole d'évaluation**. Il présente un cadre formel et un protocole expérimental complet ; il ne rapporte pas de résultats expérimentaux. Les résultats seront rapportés dans une version ultérieure (v1.0) à l'issue de l'exécution du pipeline agentique décrit en Section 4.

---

## 2. Contexte et travaux connexes

### 2.1 Autoencodeurs sparses et interprétabilité mécaniste

L'hypothèse de représentation linéaire (LRH) postule que les réseaux de neurones encodent des concepts interprétables comme des directions linéaires dans leurs espaces d'activation (Mikolov et al., 2013 ; Park et al., 2023). L'hypothèse de superposition (Elhage et al., 2022) propose que les modèles compriment un grand nombre de tels features dans un nombre plus restreint de neurones en exploitant l'orthogonalité approximative, créant des neurones polysémantiques qui répondent à plusieurs concepts non liés.

Les autoencodeurs sparses répondent à la superposition en projetant les activations dans un espace de plus haute dimension tout en imposant la sparsité. Bricken et al. (2023) démontrent que les features SAE sont plus monosémantiques et plus interprétables que les neurones individuels. Anthropic (2024) fait passer cette approche à l'échelle des modèles de production (Claude 3 Sonnet). Gao et al. (2024) fournissent une analyse complémentaire de la dynamique d'entraînement des SAEs, de la qualité de reconstruction et des compromis de sparsité.

**Mise en garde importante** : les latents SAE sont des décompositions apprises, non des détecteurs de features vérifiés. Ils dépendent des objectifs de reconstruction, des pénalités de sparsité, de la taille du dictionnaire, du corpus d'entraînement et de l'architecture du modèle. Un latent avec une description en langue naturelle plausible n'est pas nécessairement un concept humain propre ; il peut être un artefact statistique, une régularité spécifique au corpus, ou une superposition de plusieurs patterns plus faibles. Tout système d'annotation — y compris MorphoRepr — encode des hypothèses sur le contenu des latents, non des faits sur les représentations internes du modèle.

Le goulot d'étranglement actuel est la *labélisation* : assigner des descriptions humainement lisibles aux dizaines de milliers de features découverts par les grands SAEs (Bills et al., 2023 ; Paulo et al., 2024). Ces descriptions sont précises mais insuffisamment structurées pour l'évaluation systématique et le raisonnement formel.

### 2.2 Langages structurés pour l'annotation de features

Boggust et al. (2025) introduisent les *Semantic Regexes*, un langage structuré pour décrire automatiquement les features LLM en combinant des primitives pour les motifs de tokens exacts, les formes syntaxiques et les catégories sémantiques. Ce travail est l'antécédent le plus proche de MorphoRepr et constitue la baseline principale contre laquelle MorphoRepr doit être évalué.

La différence structurelle clé est le mécanisme de composition. Les Semantic Regexes combinent des primitives par des opérateurs logiques (ET, OU, NON, contexte). MorphoRepr est un langage contrôlé *agglutinant*, où les primitives sont combinées par concaténation selon des règles morphologiques, produisant un token unique prononçable plutôt qu'une formule. Si cette distinction produit un avantage mesurable est la question empirique centrale que ce papier prépare à répondre.

L'affirmation de meilleure lisibilité humaine — que `0.87·mal-far-int-e` est plus lisible que `¬(ag:past & subject:human)` — est une hypothèse ergonomique, non un résultat établi. Certains lecteurs trouveront les opérateurs logiques explicites plus clairs. Cela sera testé dans l'étude utilisateur planifiée (Section 4.5).

### 2.3 Édition de modèles

ROME (Meng et al., 2022) et MEMIT (Meng et al., 2023) démontrent que les connaissances factuelles dans les transformers peuvent être localisées dans des matrices de poids MLP spécifiques et modifiées chirurgicalement. Ces techniques sont pertinentes comme cible applicative à plus long terme pour MorphoRepr, discutée brièvement en Section 5.

### 2.4 Systèmes d'apprentissage complémentaires

La théorie des systèmes d'apprentissage complémentaires (CLS) (McClelland et al., 1995 ; Kumaran et al., 2016) propose que la mémoire biologique est organisée en systèmes hippocampique (rapide, épisodique) et néocortical (lent, sémantique). L'analogie avec les architectures mémorielles des LLMs motive l'agenda de recherche à plus long terme esquissé en Section 5.

---

## 3. Le système MorphoRepr

### 3.1 Principes de conception

MorphoRepr est conçu selon quatre principes :

**Compositionnalité morphologique.** Toute expression MorphoRepr est une concaténation finie de morphèmes tirés d'un inventaire fixe. Le sens d'une expression est entièrement déterminé par les sens de ses morphèmes constitutifs et leur ordre de composition.

**Encodage d'activation pondéré.** Chaque terme d'une expression est précédé d'un coefficient réel dans [0,01 ; 1,00] représentant la force d'activation normalisée du latent SAE correspondant. Une expression complète prend la forme :

```
α₁·m₁[-m₂[-m₃]] [+ α₂·m₄[-m₅] [+ ...]]
```

où les `mᵢ` sont des morphèmes, `-` dénote la concaténation agglutinante, `+` dénote la combinaison additive de features, et `αᵢ ∈ [0,01 ; 1,00]` sont les coefficients d'activation ordonnés par valeur décroissante. Par exemple :

```
0.87·mal-far-int-e  +  0.41·pens-ad-is
```

se lit : *« n'ayant pas (vraiment) agi (force 0,87) plus ayant continué à penser (force 0,41) »*.

**Sémantique formelle des morphèmes.** Chaque morphème de l'inventaire dispose d'une définition formellement spécifiée comprenant : (a) une dénotation en termes de primitive sémantique, (b) un énoncé de portée précisant ce que le morphème couvre et exclut, et (c) un ensemble de features SAE attestés que le morphème encode de façon fiable.

**Expressivité bornée.** MorphoRepr est explicitement conçu comme une *projection avec perte*. Il capture le contenu morpho-syntaxique et largement sémantique des features SAE. Le contenu pragmatique, culturel, spécifique aux entités nommées et profondément contextuel se situe hors de sa portée par conception. Le résidu — les features que le système ne peut pas encoder avec confiance ≥ 0,50 — est une sortie de première classe (UNCOVERED), non un mode d'échec.

### 3.2 Normalisation des coefficients

Le coefficient d'activation `αᵢ` d'un terme représente la force d'activation du latent SAE correspondant, normalisée dans [0,01 ; 1,00] selon la convention suivante :

Pour chaque latent SAE `f`, soit `a(f, x)` l'activation de `f` sur l'entrée `x`. La référence de normalisation est le 99e percentile des activations observées pour `f` sur un corpus de référence (le même corpus utilisé pour l'évaluation de l'entraînement SAE). Formellement :

```
α(f, x) = clip( a(f, x) / p99(f), 0,01, 1,00 )
```

où `p99(f)` est le 99e percentile d'activation du feature `f` sur le corpus de référence, et `clip` tronque les valeurs dans [0,01 ; 1,00]. Cette convention garantit que : (a) le coefficient reflète la force relative du feature dans le contexte courant par rapport à son activation maximale typique ; (b) les valeurs restent bornées et comparables entre features et couches ; (c) la combinaison additive `α₁·m₁ + α₂·m₂` exprime la contribution relative de deux features dans le même contexte, non leurs amplitudes d'activation absolues.

Lorsqu'une expression MorphoRepr est utilisée comme annotation statique (non liée à une instance d'activation spécifique), les coefficients représentent la confiance de l'encodeur dans chaque assignation de morphème plutôt qu'une valeur d'activation mesurée. Dans ce contexte d'annotation, les coefficients sont élicités directement depuis l'agent encodeur et restent dans [0,01 ; 1,00].

### 3.3 L'inventaire des morphèmes

L'inventaire MorphoRepr est organisé en cinq catégories. Conformément à la grammaire formalisée en Annexe A, **les morphèmes de domaine servent de racines** (noyau sémantique d'un mot), tandis que les morphèmes de polarité servent de préfixes. Les racines libres — induites par le pipeline agentique pour les concepts non couverts par le vocabulaire prédéfini — sont autorisées, dénotées par des séquences de lettres minuscules de 2 à 5 caractères ; voir note 1.

**Suffixes temporels** (encodent le temps et l'aspect verbal ; production `suffixe-temporel`) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-as` | présent, en cours | temps présent `-as` |
| `-is` | passé, accompli | temps passé `-is` |
| `-os` | futur, anticipé | temps futur `-os` |
| `-us` | conditionnel, hypothétique | conditionnel `-us` |

**Infixes participiaux** (insérés entre la racine et le suffixe) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-ad-` | itératif, habituel | suffixe itératif `-ad-` |
| `-int-` | participe actif passé | `-int-` |
| `-at-` | participe passif présent | `-at-` |
| `-ist-` | agent habituel, professionnel | `-ist-` |
| `-ant-` | agent actuel, acteur | participe actif présent |
| `-ig-` | causatif, faire faire | `-ig-` |
| `-iĝ-` | inchoatif, devenir | `-iĝ-` |

**Préfixes de polarité et de degré** (modifient la racine qu'ils précèdent) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `mal-` | négation, contraire | `mal-` |
| `ne-` | absence, manque | `ne` (adverbe) |
| `pli-` | augmentation comparative | `pli` |
| `plej-` | superlatif | `plej` |
| `duon-` | partiel, approximatif | `duon-` |

**Racines de domaine** (racines sémantiques prédéfinies ; production `racine-prédéfinie` dans la grammaire) :

| Racine | Sens | Notes |
|--------|------|-------|
| `sci` | connaissance, fait, croyance | couvre les features épistémiques |
| `emo` | affect, émotion, valence | couvre les features de sentiment |
| `ag` | action physique, mouvement | couvre les features d'action |
| `dir` | direction, relation spatiale | couvre les features spatiaux |
| `soc` | relation sociale, rôle | couvre les features interpersonnels |
| `dat` | numérique, code, données | couvre les features techniques/computationnels |
| `tem` | temps, séquence, ordre | couvre les features d'ordonnancement temporel |
| `lok` | lieu, emplacement | couvre les features d'ancrage spatial |

**Suffixes de rôle syntaxique** (élément final d'un mot lorsque celui-ci est nominal, adjectival, adverbial ou infinitival) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-o` | nom (entité, concept) | suffixe nominal `-o` |
| `-a` | adjectif (propriété, attribut) | suffixe adjectival `-a` |
| `-e` | adverbe (manière, degré) | suffixe adverbial `-e` |
| `-i` | infinitif (action abstraite) | suffixe infinitif `-i` |

**Note sur les types de suffixes.** MorphoRepr utilise deux familles de suffixes distinctes : les *suffixes de rôle syntaxique* (`-o`, `-a`, `-e`, `-i`) et les *suffixes temporels* (`-as`, `-is`, `-os`, `-us`). Un mot se termine par exactement un suffixe. Un mot avec suffixe temporel est verbal ; un mot avec suffixe syntaxique est nominal, adjectival, adverbial ou infinitival. Cette distinction est explicite dans la grammaire (Annexe A). MorphoRepr n'est pas de la morphologie espéranto stricte ; il emprunte la logique structurelle de l'espéranto tout en adaptant le système de suffixes aux besoins de l'annotation.

---

*Note 1 : Les racines libres telles que `far` (faire/agir) et `pens` (penser) sont des racines MorphoRepr valides sous la production `racine-libre ::= [a-z]{2,5}` de la grammaire. Elles sont induites par le pipeline agentique (Phase 2) lorsqu'aucune racine de domaine prédéfinie ne couvre un cluster de features. Les racines libres doivent être enregistrées dans le lexique versionné avant utilisation. Une racine libre ne peut pas être identique à un token de préfixe (`mal`, `ne`, `pli`, `plej`, `duon`), d'infixe (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) ou de suffixe (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`) déjà défini dans l'inventaire. Les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.*

---

### 3.4 Exemples d'encodage

Les exemples suivants illustrent des encodages MorphoRepr pour des features SAE. **Ces exemples sont des illustrations pédagogiques**, non des encodages validés expérimentalement. Chaque encodage est parsé contre la grammaire de l'Annexe A pour vérifier la validité structurelle ; les choix d'encodage reflètent un jugement humain éclairé et sont explicitement interprétatifs — ils peuvent varier entre annotateurs, ce que le protocole d'évaluation est précisément conçu pour mesurer. Les indices de features et descriptions sont tirés de l'interface publique Neuronpedia pour Claude 3 Sonnet (couche et version SAE à préciser dans la version expérimentale).

**Feature #892** (description en langue naturelle : *« tokens dans des contextes au passé, en particulier des actions accomplies »*) :
```
0.91·ag-is
```
Parse : `ag` (racine de domaine) + `-is` (suffixe temporel, passé). Lecture : *« action physique accomplie (passé) »*, force 0,91. Le suffixe temporel `-is` est utilisé ici car le feature encode une propriété verbale et temporelle ; `-o` encoderait l'action-comme-entité.

**Feature #1204** (description : *« marqueurs de négation et éléments à polarité négative »*) :
```
0.88·mal-o  +  0.34·ne-a
```
Parse, terme 1 : `mal` (racine-prédéfinie) + `-o` (suffixe syntaxique). Parse, terme 2 : `ne` (racine-prédéfinie) + `-a`. Lecture : *« la négation comme entité (0,88) plus l'absence comme propriété (0,34) »*. Note : `mal` et `ne` fonctionnent ici comme racines (espéranto : `malo` = « le contraire »), non comme préfixes ; la grammaire le permet sous `racine-prédéfinie`. Les encodeurs doivent déclarer explicitement ce choix de parse.

**Feature #3871** (description : *« agents humains accomplissant des actions intentionnelles, en particulier dans des contextes narratifs »*) :
```
0.79·soc-ant-o  +  0.45·ag-int-a
```
Parse, terme 1 : `soc` (racine) + `-ant-` (infixe) + `-o` (suffixe). Parse, terme 2 : `ag` (racine) + `-int-` (infixe) + `-a` (suffixe). Lecture : *« acteur social en train d'agir (0,79) plus entité ayant agi physiquement (0,45) »*.

**Feature #4102** (description : *« code Python impliquant des boucles for et des motifs d'itération »*) :
```
0.94·dat-ad-o
```
Parse : `dat` (racine) + `-ad-` (infixe, itératif) + `-o` (suffixe). Lecture : *« processus itératif de données/code »*, force 0,94. **Limitation reconnue** : cet encodage compresse « boucle for Python » en une entité-données-itérative générique. Il ne peut pas distinguer entre itération de code, série numérique, répétition textuelle ou motifs syntaxiques. Cette limitation motive l'induction de racines libres.

**Feature #7823** (description : *« tokens apparaissant dans des contextes émotionnellement négatifs, en particulier le deuil et la perte »*) :
```
0.86·mal-emo-a  +  0.42·ne-soc-a
```
Parse, terme 1 : `mal-` (préfixe) + `emo` (racine) + `-a` (suffixe). Parse, terme 2 : `ne-` (préfixe) + `soc` (racine) + `-a` (suffixe). Lecture : *« propriété affective négative (0,86) plus absence de relation sociale (0,42) »*. **Justification de l'encodage** : le deuil et la perte impliquent à la fois une valence négative (`mal-emo-a`) et une absence relationnelle (`ne-soc-a`). Cet encodage est plus compositionnel que le `0.51·pens-is` de la v0.24 (état cognitif passé), qui dépendait d'un jugement interprétatif sur la rumination. **Cet exemple illustre également une limitation** : l'encodage reste interprétatif et pourrait varier entre annotateurs ; le protocole d'évaluation mesure cette variance directement.

### 3.5 Relation avec la hiérarchie d'abstraction de l'IDM

*(Note : cette section fournit une analogie structurelle optionnelle utile pour les lecteurs familiers de l'ingénierie dirigée par les modèles. Elle ne constitue pas une justification scientifique de MorphoRepr et peut être sautée sans perte de continuité.)*

L'IDM organise les artefacts de modélisation en quatre niveaux d'abstraction (M0 : instances, M1 : modèles, M2 : métamodèles, M3 : le MOF méta-métamodèle). MorphoRepr peut être compris par analogie :

- **M0** : un token spécifique en contexte, avec son vecteur d'activation
- **M1** : un latent SAE — une direction apprise dans l'espace d'activation avec une description en langue naturelle
- **M2** : une expression MorphoRepr — un encodage structuré d'un ou plusieurs latents SAE
- **M3** : l'inventaire de morphèmes MorphoRepr — l'ensemble autodescriptif de primitives

Cette analogie est illustrative. Les latents SAE ne sont pas des « modèles » au sens IDM ; MorphoRepr n'a pas la sémantique formelle du MOF. L'analogie motive la structure autoréférentielle de l'inventaire de morphèmes mais ne constitue pas une preuve formelle d'aucune propriété.

---

## 4. Étude de faisabilité agentique

### 4.1 Motivation pour une approche agentique

L'induction d'un lexique MorphoRepr à partir de features SAE requiert à la fois une application cohérente de règles formelles (accessible à l'automatisation) et un jugement sémantique sur la pertinence des morphèmes (nécessitant un raisonnement au niveau LLM). Cette combinaison motive un pipeline multi-agents.

### 4.2 Architecture du pipeline

Le pipeline se compose de cinq phases plus une étude utilisateur planifiée. Les gabarits de prompts complets pour chaque agent sont fournis en Annexe B.

#### Phase 1 : Extraction des features SAE

**Objectif** : constituer un corpus stratifié de features SAE avec des exemples d'activation.

**Sources de données** : SAEs publics pour Claude 3 Sonnet via l'API Neuronpedia ; SAE-Bench (EleutherAI) ; `sae_lens`.

L'*agent de chargement* récupère pour chaque feature son index, ses 20 exemples à activation maximale avec leurs valeurs d'activation, son score d'interprétabilité existant et sa fréquence d'activation sur le corpus de référence. L'*agent de classement* constitue **trois splits d'évaluation** pour éviter le biais de sélection vers les features faciles à interpréter :

- **Easy set** (n=200) : features avec score d'interprétabilité ≥ 0,7, haute fréquence
- **Random set** (n=200) : features échantillonnés uniformément sans filtrage par score
- **Hard set** (n=100) : features avec score d'interprétabilité < 0,5, ou context-dépendants, ou spécifiques à un domaine (code, mathématiques, entités nommées, multilingue)

Cette stratification garantit que les statistiques de couverture et de validité reflètent la distribution complète des latents SAE. Tous les seuils go/no-go principaux sont évalués sur le **random set**.

#### Phase 2 : Induction du lexique MorphoRepr

**Objectif** : identifier un ensemble minimal de morphèmes couvrant l'espace sémantique du corpus de features.

L'*agent de clustering* plonge les descriptions en langue naturelle à l'aide de nomic-embed-text et applique un clustering k-means (k ≈ 20). L'*agent de labélisation* propose des morphèmes par cluster. L'*agent de cohérence* valide selon trois critères : non-redondance (similarité cosinus < 0,7), couverture et composabilité. Les échecs déclenchent une boucle de feedback (max 5 itérations).

**Gouvernance du lexique** : les racines libres sont enregistrées dans un lexique versionné avec définition formelle, énoncé de portée, cluster de features inducteur et horodatage de version. Une racine libre ne peut pas entrer en collision avec un token existant de préfixe, infixe ou suffixe.

**Métriques de productivité morphologique** (calculées en fin de Phase 2 et mises à jour après la Phase 3) :

| Métrique | Définition |
|----------|-----------|
| Features par racine | Nombre moyen de features couverts par chaque racine |
| Taux de racines libres | Nouvelles racines libres introduites par 100 features encodés |
| Couverture lexique de base | Proportion d'annotations utilisant uniquement les racines de domaine prédéfinies |
| Couverture racines libres | Proportion d'annotations nécessitant au moins une racine libre |
| Entropie des morphèmes | Entropie de Shannon de la distribution d'utilisation des morphèmes |

Ces métriques opérationnalisent la question de gouvernance clé : MorphoRepr est-il réellement compositionnel (peu de primitives, réutilisation élevée) ou converge-t-il vers un dictionnaire ad hoc compressé (nombreuses étiquettes courtes, faible réutilisation) ?

#### Phase 3 : Encodage des features, fidélité et mesure de couverture

**Objectif** : encoder chaque feature et calculer des statistiques stratifiées de couverture, fidélité et cohérence.

L'*agent d'encodage* produit une expression MorphoRepr pondérée ou une réponse UNCOVERED avec justification (voir Annexe B.2). Chaque run d'annotation est exécuté **deux fois indépendamment** pour mesurer la cohérence entre runs.

**Métriques de couverture** (par split) :
- Taux de couverture brut : pourcentage de features avec confiance de l'encodeur ≥ 0,6
- Taux UNCOVERED, catégorisé par type de feature (entité nommée, pragmatique, spécifique à un domaine, context-dépendant)

**Métrique de fidélité — tâche de discrimination** (remplace le « score de fidélité » vague de la v0.24) :

Pour chaque feature encodé `f`, nous constituons :
- Un ensemble de 20 exemples top-activating tirés de Neuronpedia (ensemble positif)
- Un ensemble de 20 exemples contrôles appariés qui n'activent pas `f` (ensemble négatif), sélectionnés par l'agent de chargement pour être contextuellement similaires

Un *agent juge de fidélité* reçoit l'annotation MorphoRepr et doit classer quels exemples sont dans l'ensemble positif. La métrique de fidélité est l'**AUC-ROC** de cette tâche de discrimination. Cette formulation transforme la fidélité en une tâche de prédiction testable plutôt qu'un jugement de plausibilité subjectif.

**Métriques de cohérence d'annotation** (au niveau morphémique, entre deux runs indépendants) :

| Métrique | Définition |
|----------|-----------|
| Taux d'exact match | Proportion de features recevant des expressions identiques dans les deux runs |
| Overlap de racines | Similarité de Jaccard des ensembles de racines entre les deux runs |
| Jaccard de morphèmes | Similarité de Jaccard des ensembles de morphèmes complets (racines + infixes + préfixes) |
| Corrélation des coefficients | Corrélation de Pearson des coefficients des termes correspondants |
| Distance d'édition morphémique | Nombre moyen de substitutions de morphèmes entre les deux annotations |

ROUGE-L est conservé comme métrique secondaire pour la comparaison aux baselines en langue naturelle, mais n'est pas la mesure de cohérence principale pour MorphoRepr.

**Comparaisons aux baselines** (exécutées en parallèle sur le même corpus) :

| Baseline | Description |
|----------|-------------|
| Étiquettes en langue naturelle | Générées par LLM, sans contrainte |
| Semantic Regexes | Protocole Boggust et al. (2025) |
| Tags-mots-clés contrôlés | Syntagme nominal unique, sans composition |
| MorphoRepr mélangé | Annotations MorphoRepr réelles d'autres features, réassignées aléatoirement — contrôle plus fort que des chaînes aléatoires grammaticalement valides, car il teste si la forme morphologique seule porte du pouvoir prédictif |

Métriques de comparaison pour toutes les baselines : longueur des descriptions (tokens), cohérence d'annotation (ROUGE-L pour les NL, Jaccard de morphèmes pour MorphoRepr), AUC-ROC de fidélité, taux UNCOVERED, score de validité causale.

#### Phase 4 : Validation causale par steering d'activation

**Objectif** : vérifier que les expressions MorphoRepr sont prédictives causalement du comportement du modèle sous intervention sur les features.

**Protocole de steering** : pour chaque feature encodé, l'*agent de steering* amplifie le latent SAE cible de +5 unités d'activation (Anthropic, 2024) sur 20 phrases-sondes neutres et enregistre le déplacement de sortie. Un *agent de prédiction causale* génère une prédiction comportementale basée **uniquement sur l'expression MorphoRepr** (non la description en langue naturelle) — voir Annexe B.3. Un *agent juge* évalue si le déplacement observé correspond à la prédiction.

**Garde-fou méthodologique contre la circularité** : l'agent juge reçoit uniquement l'expression MorphoRepr et le déplacement de sortie observé, non la description en langue naturelle. Cela garantit que la validation mesure le pouvoir prédictif de l'encodage MorphoRepr lui-même.

**Classifieurs de propriétés de sortie** (remplace le score binaire correct/incorrect de la v0.24) :

Plutôt qu'un jugement binaire unique, le protocole mesure un ensemble de propriétés de sortie classifiables automatiquement. Pour chaque phrase-sonde, les propriétés suivantes sont mesurées avant et après le steering :

| Propriété | Méthode de mesure |
|-----------|------------------|
| Présence de négation | Parseur syntaxique |
| Temps (passé/présent/futur) | Tagger |
| Valence émotionnelle | Classifieur de sentiment |
| Présence de code | Classifieur au niveau des tokens |
| Présence d'agent | NER + analyse des dépendances |
| Référence spatiale | NER + parse syntaxique |
| Référence sociale | NER + coréférence |
| Modalité conditionnelle | Correspondance de motifs syntaxiques |

L'agent de prédiction causale prédit quelles propriétés augmenteront sous steering ; le juge mesure si elles le font. Cela produit une **accuracy par propriété** et un **score de validité causale** agrégé (accuracy moyenne sur les propriétés prédites). Le score est calculé par feature, par split, et agrégé avec des **intervalles de confiance bootstrap à 95 %**.

**Catégories de résultat de validité causale** : chaque feature est assigné à l'une des quatre catégories : *confirmé* (majorité des propriétés prédites se déplacent comme attendu), *partiel* (certaines propriétés se déplacent), *nul* (aucun déplacement mesurable), *mixte/ambigu* (les propriétés se déplacent dans des directions inattendues). Cela remplace le jugement binaire correct/incorrect et permet une analyse plus fine.

**Contrôles de validité supplémentaires** :
- Annotations MorphoRepr mélangées comme contrôle négatif (doit produire une validité causale proche du hasard)
- Validation causale exécutée séparément pour les splits easy / random / hard
- Deux runs de prédiction indépendants ; κ de Cohen sur les résultats catégoriels

**Reformulation du critère go/no-go** : le critère de publication principal n'est plus un seuil absolu fixe. La décision de publication repose sur l'**amélioration relative par rapport aux baselines** avec intervalles de confiance :

> MorphoRepr est considéré comme démontrant une utilité causale si son score de validité causale sur le random set dépasse à la fois les étiquettes en langue naturelle et les Semantic Regexes avec des intervalles de confiance bootstrap à 95 % non chevauchants.

La valeur de référence opérationnelle de 0,65 sur le random set est conservée comme plancher absolu minimal (en dessous duquel le système n'a aucune utilité pratique indépendamment de la comparaison aux baselines), mais la conclusion principale repose sur le gain relatif.

#### Phase 5 : Synthèse et publication

L'*agent de rapport* génère des statistiques stratifiées de couverture, fidélité, cohérence, validité causale et productivité sur tous les splits et baselines. L'*agent d'analyse des lacunes* classe les features UNCOVERED. L'*agent de rédaction* produit un résumé structuré des résultats.

### 4.3 Stack technique

```
Orchestration :        Claude Code (boucle agentique) ou LangGraph
Agents LLM :           Claude Sonnet (tâches de jugement sémantique)
                       Claude Haiku (tâches répétitives de scoring et mise en forme)
Accès SAE :            sae_lens + API Neuronpedia (neuronpedia.org)
Embeddings :           nomic-embed-text (clustering des descriptions de features)
Clustering :           scikit-learn k-means + UMAP (visualisation)
Stockage :             SQLite (corpus de features) + JSON (lexique versionné)
Classifieurs de sortie : spaCy (syntaxe/NER), VADER/transformer (valence),
                       classifieurs personnalisés pour code/modalité
Évaluation :           SAE-Bench (EleutherAI) comme benchmark externe
Baselines :            étiquettes NL, Semantic Regexes, tags-mots-clés,
                       MorphoRepr mélangé
Points de sauvegarde : snapshot complet de l'état du pipeline après chaque phase
```

### 4.4 Critères de succès

| Métrique | Plancher minimal | Critère de publication |
|----------|-----------------|----------------------|
| Couverture brute — easy set (conf ≥ 0,6) | 65 % | 80 % |
| Couverture brute — random set (conf ≥ 0,6) | 45 % | 60 % |
| Couverture brute — hard set (conf ≥ 0,6) | 20 % | 35 % |
| AUC-ROC de fidélité — random set | 0,60 | 0,72 |
| Validité causale — random set (plancher absolu) | 0,50 | 0,65 |
| Validité causale vs étiquettes NL (random set) | — | Gain positif, IC non chevauchants |
| Validité causale vs Semantic Regexes (random set) | — | Gain non négatif |
| Cohérence d'annotation — overlap de racines (random set) | 0,60 | 0,75 |
| Cohérence d'annotation — exact match (random set) | 0,30 | 0,50 |
| Taille finale du lexique | < 250 morphèmes | < 150 morphèmes |
| Taux de racines libres | — | < 5 par 100 features |
| Features UNCOVERED catégorisés | — | ≥ 80 % |

Une couverture brute inférieure à 40 % sur le random set n'invalide pas la contribution ; elle constituerait un résultat négatif précisément caractérisé quantifiant quelles propriétés des latents SAE résistent à l'encodage morphologique — contribution en soi à la théorie de la structure des features dans les LLMs.

### 4.5 Étude utilisateur planifiée

L'affirmation que les annotations MorphoRepr sont plus lisibles par l'humain et moins cognitivement exigeantes que les alternatives nécessite une évaluation humaine. Nous planifions l'étude suivante, à rapporter conjointement aux résultats expérimentaux dans la v1.0 :

**Participants** : 20 chercheurs NLP/ML sans exposition préalable à MorphoRepr.

**Design** : intra-sujet, contrebalancé. Chaque participant annote 30 features SAE avec trois systèmes (MorphoRepr, Semantic Regexes, étiquettes en langue naturelle) dans un ordre aléatoire, après une courte session de formation.

**Mesures** :
- Temps d'apprentissage de la notation (durée de complétion de la session de formation)
- Temps d'interprétation d'une annotation (moyenne par feature)
- Précision d'interprétation (correspondance avec des annotations gold d'experts)
- Cohérence d'annotation (accord entre deux participants par feature)
- Charge cognitive subjective (NASA-TLX)
- Classement de préférence (MorphoRepr vs Semantic Regex vs NL)

**Hypothèse** : les annotations MorphoRepr seront interprétées plus rapidement et avec une cohérence plus élevée que les Semantic Regexes, au prix d'une apprenabilité initiale plus faible. Cette hypothèse est empirique, non supposée.

---

## 5. Agenda de recherche

*Cette section esquisse des directions de recherche à plus long terme, conditionnelles aux résultats expérimentaux de la Section 4. Elle ne constitue pas une contribution du présent papier.*

Si MorphoRepr s'avère causalement valide comme système d'annotation, deux extensions naturelles se dessinent.

**MorphoRepr-Edit.** Si les expressions MorphoRepr peuvent être validées comme prédictives causalement au niveau des features, elles pourraient éventuellement servir d'espace d'adressage structuré pour l'édition de modèles (de style ROME/MEMIT), transformant la procédure de localisation coûteuse au cas par cas en une consultation structurée dans un espace sémantiquement typé. C'est hautement spéculatif : MorphoRepr adresse des latents SAE, non des matrices de poids directement, et le mapping des latents vers des directions de poids éditables nécessite des travaux substantiels supplémentaires.

**MorphoRepr-Memory.** Une architecture mémorielle hybride inspirée de la théorie CLS pourrait combiner un magasin vectoriel externe (tampon épisodique, indexé par des embeddings MorphoRepr) avec une consolidation paramétrique sélective via LoRA, produisant une interface de récupération auditable par l'humain. Le problème ouvert clé est qu'écrire dans un système dynamique non linéaire de façon compositionnelle et sans interférence n'est garanti par aucune théorie actuelle.

Ces directions sont proposées comme programme de recherche en trois papiers : le présent papier (cadre et protocole), un second papier (résultats expérimentaux) et un troisième papier (application édition ou mémoire).

---

## 6. Positionnement dans la littérature actuelle

| Approche | Compositionnalité | Lisibilité humaine | Cohérence | Validité causale |
|----------|------------------|-------------------|-----------|-----------------|
| Étiquettes en langue naturelle (Bills et al., 2023) | Aucune | Élevée | Faible | Non évaluée |
| Semantic Regexes (Boggust et al., 2025) | Logique | Modérée | Élevée | Non évaluée |
| SAELing (Huang et al., 2025) | Aucune | Élevée | Modérée | Partielle |
| TCAV (Kim et al., 2018) | Aucune | Modérée | Modérée | Partielle |
| **MorphoRepr (proposé)** | **Agglutinante** | **Élevée (hypothèse)** | **À mesurer** | **Critère central** |
| Logique du premier ordre | Complète | Faible | Élevée | Élevée |

La question ouverte centrale distinguant MorphoRepr des Semantic Regexes est de savoir si la composition morphologique agglutinante produit un avantage mesurable en cohérence d'annotation et pouvoir prédictif causal. Le protocole d'évaluation de la Section 4 est conçu pour mesurer cela empiriquement.

---

## 7. Discussion

### 7.1 Ce que MorphoRepr peut et ne peut pas exprimer

MorphoRepr capture : les propriétés morpho-syntaxiques (temps, aspect, négation, agentivité, rôle syntaxique), le domaine sémantique large (connaissance, affect, action, espace, relation sociale, données), et la force d'activation (via les coefficients). Il ne capture pas : les features d'entités nommées très spécifiques, les features profondément pragmatiques (ironie, registre, connotation culturelle), les features définis par un contexte textuel spécifique, ou les relations inter-features.

La couverture estimée de 45 à 65 % sur le random set (en attente de validation empirique) signifie qu'une fraction substantielle des latents SAE se situe par conception hors de la portée expressive de MorphoRepr. Ce n'est pas un échec — c'est une quantification de la frontière entre contenu morpho-sémantique et contextuel-pragmatique dans l'espace de features LLM.

### 7.2 Pourquoi l'espéranto et non une autre langue agglutinante

Le choix de l'espéranto comme modèle structurel repose sur quatre propriétés : morphologie entièrement régulière (sans exceptions), inventaire fini d'affixes (~40 affixes à sens formellement définis), notation en alphabet latin, et apprenabilité humaine. Nous ne prétendons pas que la morphologie espéranto est intrinsèquement optimale. Si le protocole d'évaluation ne montre aucun avantage mesurable sur les alternatives, un autre système de notation devrait être utilisé.

### 7.3 Gouvernance et versionnage du lexique

L'extensibilité de MorphoRepr via les racines libres crée une tension : un petit lexique fermé limite la couverture ; un lexique extensible sans contraintes risque de devenir un vocabulaire ad hoc compressé. La résolution est un **lexique gouverné et versionné** avec définitions enregistrées, énoncés de portée et horodatages de version. Les métriques de productivité morphologique (Section 4.2) opérationnalisent cette tension : un taux élevé de racines libres ou une faible entropie des morphèmes indiquerait que MorphoRepr converge vers un dictionnaire plutôt qu'un système compositionnel.

### 7.4 Menaces à la validité

Nous identifions les menaces suivantes à la validité des résultats expérimentaux planifiés :

**Menaces à la validité interne :**
- *Circularité résiduelle de l'annotation* : l'encodeur et le juge de fidélité sont tous deux des LLMs. Même avec la description en langue naturelle retenue du juge causal, l'étape d'encodage a été informée par cette description. La baseline MorphoRepr mélangé est conçue pour quantifier la part du pouvoir prédictif attribuable à la forme morphologique seule.
- *Dépendance aux descriptions NL initiales* : si les descriptions NL utilisées pour le clustering sont de mauvaise qualité, le lexique induit le sera aussi. Cela est atténué par l'utilisation de plusieurs sources de descriptions et la boucle de validation de cohérence.
- *Subjectivité des classifieurs de propriétés de sortie* : les classifieurs automatiques pour la valence, la modalité et les références sociales ont des taux d'erreur non nuls. Toutes les sorties des classifieurs seront vérifiées sur un échantillon aléatoire.
- *+5 unités d'activation peuvent ne pas être comparables entre features et couches* : la magnitude de steering est tirée d'Anthropic (2024) mais peut nécessiter une calibration par feature ou par couche. Nous rapporterons la distribution des magnitudes d'activation obtenues.

**Menaces à la validité externe :**
- *Dépendance à Claude 3 Sonnet et Neuronpedia* : les résultats peuvent ne pas se généraliser à d'autres modèles, architectures SAE ou dictionnaires de features. Le split random est conçu pour échantillonner largement, mais la généralisation entre modèles nécessite des études de réplication séparées.
- *Biais de la langue anglaise* : le protocole actuel annote des features de langue anglaise. Le système morphologique de MorphoRepr est agnostique à la langue en principe, mais son utilité pour des espaces de features multilingues ou à forte densité de code n'est pas testée.
- *Coût cognitif d'apprentissage de MorphoRepr* : si la notation nécessite un temps de formation significatif pour être interprétée de façon fiable, son avantage pratique sur les étiquettes NL est réduit. L'étude utilisateur (Section 4.5) est conçue pour mesurer cela directement.
- *Risque de croissance ad hoc du lexique* : si l'induction de racines libres est trop permissive, MorphoRepr perd sa propriété compositionnelle. Les métriques de productivité et les règles de gouvernance sont conçues pour détecter et contraindre cela, mais ne peuvent pas entièrement l'empêcher.
- *Variance de qualité des latents SAE* : le hard set contient par construction des latents moins interprétables. Si ces latents manquent de contenu humainement interprétable stable, aucun système d'annotation — y compris MorphoRepr — ne peut les annoter de façon fiable. Les résultats UNCOVERED dans le hard set peuvent refléter la qualité des latents plutôt que les limitations du système.

---

## 8. Conclusion

Nous avons proposé MorphoRepr, un langage contrôlé à structure morphologique pour l'annotation des features SAE dans les LLMs, et décrit un pipeline agentique en cinq phases et un protocole d'évaluation complet pour évaluer sa couverture, sa fidélité, sa validité causale, sa productivité et sa cohérence d'annotation par rapport à plusieurs baselines.

Ce papier est un article de positionnement et protocole d'évaluation ; il ne revendique pas de résultats expérimentaux. Le cas théorique en faveur de MorphoRepr repose sur trois observations convergentes : la compositionnalité documentée des espaces d'activation LLM (hypothèse de représentation linéaire), l'analogie structurelle entre la morphologie agglutinante et la composition additive des latents SAE, et l'insuffisance démontrée des étiquettes en langue naturelle pour les tâches d'interprétabilité systématique. Si ce cas théorique se traduit en un système pratiquement utile est une question empirique que le pipeline décrit en Section 4 est conçu pour répondre.

La question ouverte centrale n'est pas si MorphoRepr est meilleur que la langue naturelle — il est presque certainement meilleur en cohérence et moins bon en couverture. La question centrale est de savoir s'il est meilleur que les Semantic Regexes, et spécifiquement si la composition agglutinante apporte un avantage mesurable en pouvoir prédictif causal et cohérence d'annotation qui justifie le coût cognitif supplémentaire d'apprendre une nouvelle notation.

Le code du pipeline agentique, la spécification du lexique MorphoRepr, et tous les résultats expérimentaux seront mis à disposition à : `https://github.com/michaellaunay/morphorepr`.

---

## Références

Bills, S., Cammarata, N., Mossing, D., Tillman, H., Gao, L., Goh, G., Sutskever, I., Leike, J., Wu, J., & Saunders, W. (2023). *Language models can explain neurons in language models*. OpenAI Blog.

Boggust, A., Ren, D., Assogba, Y., Moritz, D., Satyanarayan, A., & Hohman, F. (2025). *Semantic Regexes: Auto-Interpreting LLM Features with a Structured Language*. arXiv:2510.06378.

Bricken, T., Templeton, A., Batson, J., Chen, B., Jermyn, A., Conerly, T., Turner, N., Anil, C., Denison, C., Askell, A., Lasenby, R., Wu, Y., Kravec, S., Schiefer, N., Maxwell, T., Joseph, N., Hatfield-Dodds, Z., Tamkin, A., Nguyen, K., … Henighan, T. (2023). *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning*. Transformer Circuits Thread.

Cunningham, H., Ewart, A., Sherburn, L., Tuck, R., & Sharkey, L. (2023). *Sparse Autoencoders Find Highly Interpretable Features in Language Models*. arXiv:2309.08600.

Elhage, N., Hume, T., Olsson, C., Schiefer, N., Henighan, T., Kravec, S., Hatfield-Dodds, Z., Lasenby, R., Drain, D., Chen, C., Grosse, R., McCandlish, S., Kaplan, J., Amodei, D., Wattenberg, M., & Olah, C. (2022). *Toy Models of Superposition*. Transformer Circuits Thread.

Anthropic. (2024). *Extracting Interpretable Features from Claude 3 Sonnet*. Transformer Circuits Thread. https://transformer-circuits.pub/2024/scaling-monosemanticity/

Gao, L., la Tour, T. D., Tillman, H., Goh, G., Troll, R., Radford, A., Sutskever, I., Leike, J., & Wu, J. (2024). *Scaling and evaluating sparse autoencoders*. arXiv:2406.04093.

Huang, J., et al. (2025). *Sparse Auto-Encoder Interprets Linguistic Features in Large Language Models*. arXiv:2502.20344.

Kim, B., Wattenberg, M., Gilmer, J., Cai, C., Wexler, J., Viegas, F., & Sayres, R. (2018). *Interpretability Beyond Classification Accuracy: Quantifying Interpretability of Machine Learning Models via Concept Activation Vectors (TCAV)*. ICML 2018.

Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). *What learning systems do intelligent agents need? Complementary learning systems theory updated*. Trends in Cognitive Sciences, 20(7), 512–534.

McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex: Insights from the successes and failures of connectionist models of learning and memory*. Psychological Review, 102(3), 419–457.

Meng, K., Bau, D., Andonian, A., & Belinkov, Y. (2022). *Locating and Editing Factual Associations in GPT*. NeurIPS 2022.

Meng, K., Sharma, A. S., Andonian, A., Belinkov, Y., & Bau, D. (2023). *Mass-Editing Memory in a Transformer*. ICLR 2023.

Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). *Efficient Estimation of Word Representations in Vector Space*. arXiv:1301.3781.

Object Management Group. (2016). *Meta Object Facility (MOF) Core Specification, Version 2.5.1*. Document OMG formal/2016-11-01.

Park, K., Hernandez-Garcia, A., Sharma, S., Gontier, N., & Schölkopf, B. (2023). *The Linear Representation Hypothesis and the Geometry of Large Language Models*. arXiv:2311.03658.

Paulo, G., Mallen, A., Juang, C., & Belrose, N. (2024). *Automatically Interpreting Millions of Features in Large Language Models*. arXiv:2410.13928.

Zamenhof, L. L. (1887). *Unua Libro* [Langue internationale]. Varsovie.

---

## Annexe A : Spécification formelle de la grammaire MorphoRepr

### A.1 Grammaire formelle (BNF)

```
expression          ::= terme ('+' terme)*
terme               ::= coefficient '·' mot
coefficient         ::= '0.' chiffre-nonzero chiffre
                      | '0.' chiffre chiffre-nonzero
                      | '1.00'
(* coefficient ∈ [0,01 ; 1,00] ; voir Section 3.2 pour la convention de normalisation *)
(* chiffre          ::= '0'|'1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'           *)
(* chiffre-nonzero  ::= '1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9'               *)

mot                 ::= (préfixe)* racine (infixe)* suffixe
préfixe             ::= 'mal-' | 'ne-' | 'pli-' | 'plej-' | 'duon-'
racine              ::= racine-prédéfinie | racine-libre
racine-prédéfinie   ::= 'sci' | 'emo' | 'ag' | 'dir' | 'soc'
                      | 'dat' | 'tem' | 'lok' | 'mal' | 'ne'
racine-libre        ::= [a-z]{2,5}
                      (* racines induites par le pipeline, enregistrées dans le lexique ;
                         ne doit pas entrer en collision avec un token de préfixe,
                         infixe ou suffixe *)
infixe              ::= '-ad-' | '-int-' | '-it-' | '-ist-' | '-ant-'
                      | '-at-' | '-ig-' | '-iĝ-'
suffixe             ::= suffixe-syntaxique | suffixe-temporel
suffixe-syntaxique  ::= '-o' | '-a' | '-e' | '-i'
suffixe-temporel    ::= '-as' | '-is' | '-os' | '-us' | '-u'
```

### A.2 Règles de composition

1. Un mot doit contenir exactement une racine.
2. Les préfixes précèdent la racine ; les infixes suivent la racine et précèdent le suffixe ; le suffixe est final.
3. Les préfixes multiples sont autorisés et se composent de gauche à droite : `mal-ne-X` = « non-absent-X » ≠ `ne-mal-X` = « non-contraire-X ».
4. Les coefficients doivent être dans [0,01 ; 1,00], normalisés selon la Section 3.2. Un coefficient de 0,00 indique un feature absent et ne doit pas apparaître dans les expressions.
5. Les termes d'une expression sont ordonnés par coefficient décroissant.
6. Les racines libres doivent être enregistrées dans le lexique versionné avant utilisation ; les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.
7. Une racine libre ne peut pas être identique à un token de préfixe (`mal`, `ne`, `pli`, `plej`, `duon`), d'infixe (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) ou de suffixe (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`).
8. Un mot se terminant par un suffixe temporel (`-as`, `-is`, `-os`, `-us`, `-u`) est verbal. Un mot se terminant par un suffixe syntaxique (`-o`, `-a`, `-e`, `-i`) est nominal, adjectival, adverbial ou infinitival respectivement. Ces deux familles de suffixes sont mutuellement exclusives au sein d'un même mot.

---

## Annexe B : Gabarits de prompts du pipeline agentique

### B.1 Prompt système de l'agent de labélisation

```
You are a formal linguist designing MorphoRepr, an agglutinative
meta-language for annotating internal features of large language models.

MorphoRepr morphemes must satisfy four constraints:
1. FORMAL: The meaning is precisely bounded — you must specify
   both what the morpheme covers and what it excludes.
2. COMPOSITIONAL: The morpheme must compose unambiguously with
   other morphemes following Esperanto agglutinative rules.
3. MINIMAL: The morpheme should be as short as possible (2-5 chars)
   while remaining phonetically distinct from other morphemes.
4. EMPIRICAL: The morpheme must be grounded in observed SAE feature
   behavior, not theoretical linguistic categories.

You will receive a cluster of semantically related SAE features.
If the cluster is covered by a predefined domain root (sci, emo, ag,
dir, soc, dat, tem, lok), propose that root. Otherwise, propose a
new free root of 2-5 lowercase characters that does not conflict
with the existing lexicon (reserved tokens: mal, ne, pli, plej, duon,
ad, int, it, ist, ant, at, ig, o, a, e, i, as, is, os, us, u).
In both cases, provide: (1) a formal definition, (2) a scope statement
specifying what the morpheme covers AND excludes, (3) coverage examples,
(4) an estimate of how many features in the cluster the morpheme covers.
```

### B.2 Prompt système de l'agent d'encodage

```
You are encoding SAE features into MorphoRepr expressions.

MorphoRepr is an agglutinative formal language where:
- Each term has the form: coefficient · morpheme-chain
- Coefficients are in [0.01, 1.00] (two decimal places), representing
  your confidence in the morpheme assignment (annotation context)
- Morpheme chains follow the grammar: (prefix)* root (infix)* suffix
- Suffix is either a syntactic suffix (-o, -a, -e, -i) or a tense
  suffix (-as, -is, -os, -us, -u), not both in the same word
- Domain roots (sci, emo, ag, dir, soc, dat, tem, lok) and
  registered free roots are the only valid roots
- An expression contains 1-4 terms, ordered by descending coefficient

For each term, state:
  - The morpheme chain and its parse
  - Your encoding rationale (why this morpheme captures this feature)
  - Your confidence [0.01, 1.00]
  - What the morpheme does NOT cover for this feature

If you cannot encode a feature with confidence >= 0.50 using the
available lexicon, respond UNCOVERED and specify:
  - What semantic content cannot be expressed
  - Which morpheme category is missing
  - Whether a free root could address the gap

Be precise about confidence. Overconfident encodings that fail
causal validation are more harmful than honest UNCOVERED responses.
```

### B.3 Prompt système de l'agent de prédiction causale

```
You are predicting the effect of amplifying a SAE feature on LLM output.

Given a MorphoRepr expression for a feature, you must predict which
of the following output properties will measurably increase when this
feature is amplified by +5 activation units on neutral probe sentences:

OUTPUT PROPERTIES TO PREDICT:
- negation_presence: increase in negation markers
- past_tense: increase in past-tense verb forms
- future_tense: increase in future-tense verb forms
- conditional_modality: increase in conditional constructions
- negative_valence: increase in negative sentiment words
- positive_valence: increase in positive sentiment words
- code_presence: increase in code tokens or technical symbols
- agent_reference: increase in explicit agent noun phrases
- social_reference: increase in interpersonal or role references
- spatial_reference: increase in spatial or directional terms
- iterative_structure: increase in repetitive or list-like patterns

For each property, state:
  1. Predicted direction: INCREASE / DECREASE / NO_CHANGE
  2. Confidence: [0.0, 1.0]

Base your prediction ONLY on the MorphoRepr expression provided.
Do not use the natural language description of the feature.
This constraint is intentional: we are testing whether MorphoRepr
expressions alone are sufficient for causal prediction.

Format your response as a JSON object with property names as keys
and objects {"direction": "INCREASE"|"DECREASE"|"NO_CHANGE",
"confidence": float} as values.
```

---

## Annexe C : Modifications par rapport à la version 0.24

**Normalisation des coefficients (Section 3.2, nouvelle).** Une sous-section dédiée définit la convention de normalisation : les coefficients sont normalisés par le 99e percentile d'activation de chaque feature sur le corpus de référence et tronqués dans [0,01 ; 1,00]. L'interprétation en contexte d'annotation (coefficient comme confiance de l'encodeur) est distinguée de l'interprétation en contexte d'instance d'activation.

**Métrique de fidélité redéfinie comme tâche de discrimination (Section 4.2).** Le « score de fidélité » vague de la v0.24 a été remplacé par une tâche de discrimination concrète : pour chaque feature, le juge de fidélité prédit quels exemples parmi 20 candidats appartiennent à l'ensemble positif (top-activating) vs. un ensemble contrôle apparié. La métrique est l'AUC-ROC. Cela transforme la fidélité en une tâche de prédiction testable.

**Validité causale — classifieurs de propriétés de sortie (Section 4.3).** Le jugement binaire correct/incorrect de la v0.24 a été remplacé par un ensemble de propriétés de sortie classifiables automatiquement (présence de négation, temps, valence, présence de code, référence d'agent, etc.), chacune mesurée par un classifieur dédié. L'agent prédit quelles propriétés augmenteront ; le juge mesure si elles le font. Les résultats sont rapportés comme accuracy par propriété, score de validité causale agrégé avec intervalles de confiance bootstrap à 95 %, et quatre catégories de résultat (confirmé / partiel / nul / mixte).

**Critère go/no-go reformulé (Section 4.4).** Le critère de publication principal est maintenant l'amélioration relative par rapport aux baselines avec des intervalles de confiance non chevauchants, plutôt qu'un seuil absolu fixe. La valeur 0,65 est conservée comme plancher absolu minimal uniquement.

**Baseline MorphoRepr mélangé (Section 4.2).** Les « expressions MorphoRepr valides aléatoires » de la v0.24 ont été remplacées par un contrôle plus fort : des annotations MorphoRepr réelles d'autres features, réassignées aléatoirement. Cela teste si la forme morphologique seule porte du pouvoir prédictif.

**Métriques de cohérence d'annotation au niveau morphémique (Section 4.2).** ROUGE-L est rétrogradé en métrique secondaire. Les métriques principales sont : taux d'exact match, Jaccard de racines, Jaccard de morphèmes, corrélation des coefficients, et distance d'édition morphémique.

**Métriques de productivité morphologique (Section 4.2, nouvelles).** Cinq métriques opérationnalisent la tension compositionnel vs. ad hoc : features par racine, taux de racines libres, couverture lexique de base, couverture racines libres, entropie des morphèmes.

**Étude utilisateur planifiée (Section 4.5, nouvelle).** Une étude intra-sujet contrebalancée avec 20 participants est spécifiée, mesurant le temps d'apprentissage, le temps d'interprétation, la précision d'interprétation, la cohérence d'annotation, la charge cognitive NASA-TLX et le classement de préférence (MorphoRepr vs. Semantic Regexes vs. étiquettes NL).

**Menaces à la validité (Section 7.4, nouvelle).** Une sous-section dédiée identifie les menaces à la validité interne et externe : circularité résiduelle de l'annotation, dépendance aux descriptions NL initiales, taux d'erreur des classifieurs, calibration de la magnitude de steering, spécificité au modèle/SAE, biais de la langue anglaise, coût cognitif d'apprentissage, et risque de croissance ad hoc du lexique.

**Exemple Feature #7823 mis à jour.** L'encodage `0.51·pens-is` de la v0.24 (état cognitif passé, justifié par la rumination) a été remplacé par `0.42·ne-soc-a` (absence de relation sociale), qui est plus compositionnel et moins dépendant d'un jugement interprétatif unique.

**Prompt de l'agent encodeur mis à jour (Annexe B.2).** Le prompt requiert maintenant que l'encodeur indique le parse, la justification de l'encodage, la confiance, et ce que le morphème ne couvre PAS pour chaque terme.

**Prompt de l'agent de prédiction causale mis à jour (Annexe B.3).** Le prompt spécifie désormais la liste complète des propriétés de sortie à prédire et requiert une sortie au format JSON pour le traitement automatisé.

---

*Version 0.25 — Juin 2026*
*Michaël Launay — michaellaunay@logikascium.com*
*Logikascium EURL — https://www.logikascium.com*
*GitHub : https://github.com/michaellaunay/morphorepr*
