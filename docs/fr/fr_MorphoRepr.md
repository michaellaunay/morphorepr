# MorphoRepr : un langage contrôlé à structure morphologique pour la description des features SAE des LLMs
## Un article de positionnement et protocole d'évaluation

**Title (English):** MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol

**Michaël Launay**
Logikascium (EURL), Fretin, France
Enseignant vacataire, Université de Lille / ENSAM Lille / Polytech Lille
michaellaunay@logikascium.com

---

*Preprint — article de positionnement et protocole d'évaluation — soumis à arXiv cs.CL / HAL*
*Version 0.24 — Juin 2026*
*Remplace la version 0.23. Aucun résultat expérimental n'est revendiqué dans cette version ; les résultats seront rapportés à l'issue de l'exécution du pipeline.*

---

## Résumé

Les descriptions en langue naturelle des features des autoencodeurs sparses (SAEs) dans les grands modèles de langage (LLMs) sont précises mais insuffisamment structurées pour l'évaluation systématique, la comparaison inter-features, l'agrégation statistique et la prédiction causale. Elles sont vagues, inconsistantes entre runs d'annotation, et résistent à la manipulation formelle. Nous proposons **MorphoRepr**, un langage contrôlé à structure morphologique inspiré de la grammaire agglutinante de l'espéranto, conçu comme couche d'annotation lisible par l'humain pour les features sparses produits par des SAEs entraînés sur les activations de LLMs. Chaque expression MorphoRepr encode des hypothèses humaines sur la sémantique d'un ou plusieurs latents SAE sous forme d'une chaîne compositionnelle de morphèmes à sémantique formellement définie, pondérés par leurs coefficients d'activation. MorphoRepr ne prétend pas décoder les représentations internes des LLMs ; il encode des hypothèses humaines structurées sur la sémantique des latents SAE, hypothèses qui doivent être validées par des expériences de prédiction d'activation et d'intervention causale.

Nous présentons le cadre formel, un pipeline d'évaluation agentique en cinq phases, et un protocole d'évaluation complet spécifiant des métriques de couverture, fidélité et validité causale. Nous identifions la question ouverte centrale : si la composition morphologique agglutinante apporte un avantage mesurable par rapport aux approches d'annotation structurée existantes — en particulier les Semantic Regexes (Boggust et al., 2025) — en termes de cohérence d'annotation, compacité et pouvoir prédictif causal. Les résultats expérimentaux seront rapportés dans une version ultérieure à l'issue de l'exécution du pipeline.

**Mots-clés :** interprétabilité mécaniste, autoencodeurs sparses, morphologie agglutinante, espéranto, annotation de features SAE, langage contrôlé, validité causale

---

## Abstract (English)

Natural language descriptions of SAE features in LLMs are accurate but insufficiently structured for systematic evaluation, cross-feature comparison, and causal prediction. We propose MorphoRepr, a morphologically structured controlled language for SAE feature annotation, and present a five-phase agentic evaluation pipeline with a complete evaluation protocol. This is a position paper; no experimental claims are made.

**Keywords:** mechanistic interpretability, sparse autoencoders, agglutinative morphology, Esperanto, SAE feature annotation, controlled language, causal validity

---

## 1. Introduction

Les représentations internes des grands modèles de langage (LLMs) demeurent largement opaques à l'inspection humaine. Les autoencodeurs sparses (SAEs) ont émergé comme un outil scalable pour décomposer ces représentations en directions de features plus sparses et plus monosémantiques (Bricken et al., 2023 ; Cunningham et al., 2023 ; Anthropic, 2024). Les latents résultants sont plus interprétables que les neurones individuels, mais le problème de leur *labélisation* à grande échelle — leur assigner des descriptions précises, cohérentes et formellement manipulables — demeure un goulot d'étranglement significatif.

Les approches actuelles s'appuient sur des étiquettes en langue naturelle générées par des LLMs, utiles pour l'interprétation humaine mais présentant des limitations bien connues comme système de notation formelle : imprécision, inconsistance entre runs, et inadaptation au raisonnement compositionnel ou à la comparaison statistique sur de grands inventaires de features (Boggust et al., 2025 ; Paulo et al., 2024). Le défi n'est pas que la langue naturelle soit inexpressive en principe — elle peut décrire presque tout, au prix de la verbosité. Le défi est que les descriptions en langue naturelle sont **insuffisamment structurées** pour les tâches systématiques que requiert l'interprétabilité à grande échelle : comparaison inter-features, statistiques au niveau des morphèmes, prédiction causale à partir de l'étiquette seule, et recherche programmatique dans les espaces de features.

Ce papier propose **MorphoRepr**, un langage contrôlé pour l'annotation des features SAE qui répond à ces limitations en empruntant la logique structurelle de l'espéranto — composition agglutinante, inventaire fini de morphèmes, règles dérivationnelles transparentes — et en l'étendant avec un vocabulaire contrôlé de primitives sémantiques dérivées empiriquement de l'espace de features SAE d'un LLM de production. L'affirmation centrale n'est pas que MorphoRepr capture la géométrie interne des représentations LLM — il ne le fait explicitement pas — mais qu'il peut fournir un système d'annotation plus cohérent, plus compact et plus prédictif causalement que les alternatives existantes pour le sous-ensemble de latents SAE dont le contenu est stable et morpho-sémantiquement exprimable.

**Note sur la portée.** MorphoRepr encode des hypothèses humaines sur la sémantique des latents SAE. Un latent SAE n'est pas équivalent à un concept humain : les latents sont des directions apprises dans l'espace d'activation, dépendantes des objectifs de reconstruction, des contraintes de sparsité, des statistiques du corpus et de l'architecture du modèle. Leur interprétabilité est prometteuse mais partielle. Les descriptions MorphoRepr sont des hypothèses sur le contenu des latents, non des vérités sur les représentations internes du modèle.

### 1.1 Contributions

Ce papier apporte les contributions suivantes :

1. **Conceptuelle** : nous proposons MorphoRepr comme langage contrôlé pour l'annotation des features SAE et établissons son ancrage théorique dans l'hypothèse de représentation linéaire et l'hypothèse de superposition.

2. **Méthodologique** : nous décrivons un pipeline agentique en cinq phases pour induire empiriquement un lexique MorphoRepr à partir de features SAE et spécifions un protocole d'évaluation complet pour la couverture, la fidélité et la validité causale, incluant des comparaisons aux baselines.

3. **Prospective** : nous identifions les questions de recherche ouvertes que les versions expérimentales ultérieures de ce travail devront traiter, et esquissons un agenda de recherche à plus long terme.

### 1.2 Statut du papier

Ce papier est un **article de positionnement et protocole d'évaluation**. Il présente un cadre formel et un protocole expérimental complet ; il ne rapporte pas de résultats expérimentaux. Les résultats seront rapportés dans une version ultérieure (v1.0) à l'issue de l'exécution du pipeline agentique décrit en Section 4.

---

## 2. Contexte et travaux connexes

### 2.1 Autoencodeurs sparses et interprétabilité mécaniste

L'hypothèse de représentation linéaire (LRH) postule que les réseaux de neurones encodent des concepts interprétables comme des directions linéaires dans leurs espaces d'activation (Mikolov et al., 2013 ; Park et al., 2023). L'hypothèse de superposition (Elhage et al., 2022) propose que les modèles compriment un grand nombre de tels features dans un nombre plus restreint de neurones en exploitant l'orthogonalité approximative, créant des neurones polysémantiques qui répondent à plusieurs concepts non liés.

Les autoencodeurs sparses répondent à la superposition en projetant les activations dans un espace de plus haute dimension tout en imposant la sparsité, ce qui fait que chaque entrée n'active qu'un petit nombre de features appris. Bricken et al. (2023) démontrent que les features SAE sont plus monosémantiques et plus interprétables que les neurones individuels. Anthropic (2024) fait passer cette approche à l'échelle des modèles de production (Claude 3 Sonnet), trouvant des features correspondant à des entités nommées spécifiques, des constructions syntaxiques et des concepts sémantiques abstraits. Gao et al. (2024) fournissent une analyse complémentaire de la dynamique d'entraînement des SAEs, de la qualité de reconstruction et des compromis de sparsité.

**Mise en garde importante** : les latents SAE sont des décompositions apprises, non des détecteurs de features vérifiés. Ils dépendent des objectifs de reconstruction, des pénalités de sparsité, de la taille du dictionnaire, du corpus d'entraînement et de l'architecture du modèle. Un latent avec une description en langue naturelle plausible n'est pas nécessairement un concept humain propre ; il peut être un artefact statistique, une régularité spécifique au corpus, ou une superposition de plusieurs patterns plus faibles. Tout système d'annotation — y compris MorphoRepr — encode des hypothèses sur le contenu des latents, non des faits sur les représentations internes du modèle.

Le goulot d'étranglement actuel de l'interprétabilité basée sur les SAEs est la *labélisation* : assigner des descriptions humainement lisibles aux dizaines de milliers de features découverts par les grands SAEs. Les approches existantes utilisent des LLMs pour générer des descriptions en langue naturelle en inspectant des exemples à forte activation (Bills et al., 2023 ; Paulo et al., 2024). Ces descriptions sont précises mais insuffisamment structurées pour l'évaluation systématique et le raisonnement formel.

### 2.2 Langages structurés pour l'annotation de features

Boggust et al. (2025) introduisent les *Semantic Regexes*, un langage structuré pour décrire automatiquement les features LLM en combinant des primitives pour les motifs de tokens exacts, les formes syntaxiques et les catégories sémantiques, avec des modificateurs pour la contextualisation, la composition et la quantification. Les Semantic Regexes correspondent à la précision des descriptions en langue naturelle tout en produisant des sorties plus concises et cohérentes. Ce travail est l'antécédent le plus proche de MorphoRepr dans la littérature actuelle et constitue la baseline principale contre laquelle MorphoRepr doit être évalué.

La différence structurelle clé entre MorphoRepr et les Semantic Regexes est le mécanisme de composition. Les Semantic Regexes sont un langage de correspondance de motifs dans la tradition des expressions régulières, où les primitives sont combinées par des opérateurs logiques (ET, OU, NON, contexte). MorphoRepr est un langage contrôlé *agglutinant*, où les primitives sont combinées par concaténation selon des règles morphologiques, produisant un token unique prononçable plutôt qu'une formule. Si cette distinction produit un avantage mesurable en cohérence d'annotation, charge cognitive ou pouvoir prédictif causal est la question empirique centrale que ce papier prépare à répondre.

Nous notons que l'affirmation de meilleure lisibilité humaine — que `0.87·mal-far-int-e` est plus lisible que `¬(ag:past & subject:human)` — est une hypothèse ergonomique, non un résultat établi. Certains lecteurs trouveront au contraire les opérateurs logiques explicites plus clairs. Cela sera testé dans le protocole d'évaluation (Section 4.4).

### 2.3 Édition de modèles

ROME (Meng et al., 2022) et MEMIT (Meng et al., 2023) démontrent que les connaissances factuelles dans les transformers peuvent être localisées dans des matrices de poids MLP spécifiques et modifiées chirurgicalement. Ces techniques sont pertinentes comme cible applicative à plus long terme pour MorphoRepr : si les encodages MorphoRepr peuvent être validés comme prédictifs causalement du comportement du modèle au niveau des features, ils pourraient éventuellement servir d'espace d'adressage structuré pour l'édition de modèles. Cette direction est discutée brièvement en Section 5 mais ne constitue pas une contribution expérimentale du présent papier.

### 2.4 Systèmes d'apprentissage complémentaires

La théorie des systèmes d'apprentissage complémentaires (CLS) (McClelland et al., 1995 ; Kumaran et al., 2016) propose que la mémoire biologique est organisée en systèmes hippocampique (rapide, épisodique) et néocortical (lent, sémantique). L'analogie avec les architectures mémorielles des LLMs — RAG comme tampon hippocampique, poids du modèle comme mémoire à long terme néocorticale — motive l'agenda de recherche à plus long terme esquissé en Section 5.

---

## 3. Le système MorphoRepr

### 3.1 Principes de conception

MorphoRepr est conçu selon quatre principes :

**Compositionnalité morphologique.** Toute expression MorphoRepr est une concaténation finie de morphèmes tirés d'un inventaire fixe. Le sens d'une expression est entièrement déterminé par les sens de ses morphèmes constitutifs et leur ordre de composition.

**Encodage d'activation pondéré.** Chaque terme d'une expression est précédé d'un coefficient réel dans [0,01 ; 1,00] représentant la force d'activation normalisée du latent SAE correspondant. Une expression complète prend la forme :

```
α₁·m₁[-m₂[-m₃]] [+ α₂·m₄[-m₅] [+ ...]]
```

où les `mᵢ` sont des morphèmes, `-` dénote la concaténation agglutinante, `+` dénote la combinaison additive de features, et `αᵢ ∈ [0,01 ; 1,00]` sont les coefficients d'activation. Par exemple :

```
0.87·mal-far-int-e  +  0.41·pens-ad-is
```

se lit : *« n'ayant pas (vraiment) agi (force 0,87) plus ayant continué à penser (force 0,41) »*.

**Sémantique formelle des morphèmes.** Chaque morphème de l'inventaire dispose d'une définition formellement spécifiée comprenant : (a) une dénotation en termes de primitive sémantique, (b) un énoncé de portée précisant ce que le morphème couvre et exclut, et (c) un ensemble de features SAE attestés que le morphème encode de façon fiable.

**Expressivité bornée.** MorphoRepr est explicitement conçu comme une *projection avec perte*. Il capture le contenu morpho-syntaxique et largement sémantique des features SAE. Le contenu pragmatique, culturel, spécifique aux entités nommées et profondément contextuel se situe hors de sa portée par conception. Le résidu — les features que le système ne peut pas encoder avec confiance ≥ 0,50 — est une sortie de première classe (UNCOVERED), non un mode d'échec, et contribue à comprendre la frontière entre contenu morpho-sémantique et contextuel-pragmatique dans l'espace de features LLM.

### 3.2 L'inventaire des morphèmes

L'inventaire MorphoRepr est organisé en cinq catégories. Conformément à la grammaire formalisée en Annexe A, **les morphèmes de domaine servent de racines** (noyau sémantique d'un mot), tandis que les morphèmes de polarité servent de préfixes. Les racines libres — induites par le pipeline agentique pour les concepts non couverts par le vocabulaire prédéfini — sont autorisées, dénotées par des séquences de lettres minuscules de 2 à 5 caractères ; voir note 1.

**Suffixes temporels** (encodent le temps et l'aspect verbal ; constituent la production `suffixe` lorsqu'aucun suffixe de rôle syntaxique n'est utilisé) :

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

**Suffixes de rôle syntaxique** (élément final d'un mot lorsque celui-ci est nominal, adjectival, adverbial ou infinitival plutôt que verbal) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-o` | nom (entité, concept) | suffixe nominal `-o` |
| `-a` | adjectif (propriété, attribut) | suffixe adjectival `-a` |
| `-e` | adverbe (manière, degré) | suffixe adverbial `-e` |
| `-i` | infinitif (action abstraite) | suffixe infinitif `-i` |

**Note sur les types de suffixes.** MorphoRepr utilise deux familles de suffixes distinctes : les *suffixes de rôle syntaxique* (`-o`, `-a`, `-e`, `-i`) et les *suffixes temporels* (`-as`, `-is`, `-os`, `-us`). Un mot se termine par exactement un suffixe. Un mot avec suffixe temporel est verbal ; un mot avec suffixe syntaxique est nominal, adjectival, adverbial ou infinitival. Cette distinction est explicitée dans la grammaire (Annexe A). MorphoRepr n'est pas de la morphologie espéranto stricte ; il emprunte la logique structurelle de l'espéranto tout en adaptant le système de suffixes aux besoins de l'annotation.

---

*Note 1 : Les racines libres telles que `far` (faire/agir) et `pens` (penser) sont des racines MorphoRepr valides sous la production `racine-libre ::= [a-z]{2,5}` de la grammaire. Elles sont induites par le pipeline agentique (Phase 2) lorsqu'aucune racine de domaine prédéfinie ne couvre un cluster de features. Les racines libres doivent être enregistrées dans le lexique versionné avant utilisation. Une racine libre ne peut pas être identique à un token de préfixe (`mal`, `ne`, `pli`, `plej`, `duon`), d'infixe (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) ou de suffixe (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`) déjà défini dans l'inventaire. Les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.*

---

### 3.3 Exemples d'encodage

Les exemples suivants illustrent des encodages MorphoRepr pour des features SAE. **Ces exemples sont des illustrations pédagogiques**, non des encodages validés expérimentalement. Chaque encodage est parsé contre la grammaire de l'Annexe A pour vérifier la validité structurelle ; les choix d'encodage reflètent un jugement humain éclairé et seront soumis au protocole de validation causale de la Section 4.3. Les indices de features et descriptions sont tirés de l'interface publique Neuronpedia pour Claude 3 Sonnet (couche et version SAE à préciser dans la version expérimentale).

**Feature #892** (description en langue naturelle : *« tokens dans des contextes au passé, en particulier des actions accomplies »*) :
```
0.91·ag-is
```
Parse : `ag` (racine de domaine) + `-is` (suffixe temporel, passé). Lecture : *« action physique accomplie (passé) »*, force 0,91. Note : le suffixe temporel `-is` est utilisé ici car le feature encode une propriété verbale et temporelle ; `-o` encoderait l'action-comme-entité.

**Feature #1204** (description : *« marqueurs de négation et éléments à polarité négative »*) :
```
0.88·mal-o  +  0.34·ne-a
```
Parse, terme 1 : `mal` (racine-prédéfinie, permise sous `racine ::= [a-z]{2,5}` lorsqu'utilisée comme racine) + `-o` (suffixe de rôle syntaxique). Parse, terme 2 : `ne` (racine-prédéfinie) + `-a`. Lecture : *« la négation comme entité (0,88) plus l'absence comme propriété (0,34) »*.

> *Note sur `mal-o` et `ne-a`* : dans ces deux cas, `mal` et `ne` fonctionnent directement comme racines — construction permise en espéranto (`malo` = « le contraire ») et autorisée par la production `racine-prédéfinie` qui inclut explicitement `mal` et `ne`. C'est le seul cas où un morphème de polarité sert aussi de racine. La grammaire résout l'ambiguïté en exigeant que lorsque `mal` ou `ne` apparaît sans racine de domaine suivante, il soit parsé comme `racine-prédéfinie`, non comme `préfixe`. Les encodeurs doivent déclarer explicitement ce choix de parse.

**Feature #3871** (description : *« agents humains accomplissant des actions intentionnelles, en particulier dans des contextes narratifs »*) :
```
0.79·soc-ant-o  +  0.45·ag-int-a
```
Parse, terme 1 : `soc` (racine) + `-ant-` (infixe) + `-o` (suffixe). Parse, terme 2 : `ag` (racine) + `-int-` (infixe) + `-a` (suffixe). Lecture : *« acteur social en train d'agir (0,79) plus entité ayant agi physiquement (0,45) »*.

**Feature #4102** (description : *« code Python impliquant des boucles for et des motifs d'itération »*) :
```
0.94·dat-ad-o
```
Parse : `dat` (racine) + `-ad-` (infixe, itératif) + `-o` (suffixe). Lecture : *« processus itératif de données/code »*, force 0,94. **Limitation reconnue** : cet encodage compresse « boucle for Python » en une entité-données-itérative générique. Il ne peut pas distinguer entre itération de code, série numérique, répétition textuelle ou motifs syntaxiques. C'est une limitation connue du vocabulaire de racines de domaine prédéfinies et motive l'induction de racines libres.

**Feature #7823** (description : *« tokens apparaissant dans des contextes émotionnellement négatifs, en particulier le deuil et la perte »*) :
```
0.86·mal-emo-a  +  0.51·pens-is
```
Parse, terme 1 : `mal-` (préfixe) + `emo` (racine) + `-a` (suffixe). Parse, terme 2 : `pens` (racine libre, induite) + `-is` (suffixe temporel). Lecture : *« propriété affective négative (0,86) plus état cognitif passé (0,51) »*. **Justification de l'encodage** : `pens-is` capture le caractère rétrospectif et ruminatif des contextes de deuil ; des encodages alternatifs (ex. `mal-emo-o`) ont été considérés mais jugés moins spécifiques. Cette justification sera systématiquement élicitée et comparée entre runs d'annotation dans le protocole d'évaluation.

### 3.4 Relation avec la hiérarchie d'abstraction de l'IDM

*(Note : cette section fournit une analogie structurelle optionnelle utile pour les lecteurs familiers de l'ingénierie dirigée par les modèles. Elle ne constitue pas une justification scientifique de MorphoRepr et peut être sautée sans perte de continuité.)*

L'IDM organise les artefacts de modélisation en quatre niveaux d'abstraction (M0 : instances, M1 : modèles, M2 : métamodèles, M3 : le MOF méta-métamodèle). MorphoRepr peut être compris par analogie :

- **M0** : un token spécifique en contexte, avec son vecteur d'activation
- **M1** : un latent SAE — une direction apprise dans l'espace d'activation avec une description en langue naturelle
- **M2** : une expression MorphoRepr — un encodage structuré d'un ou plusieurs latents SAE
- **M3** : l'inventaire de morphèmes MorphoRepr — l'ensemble autodescriptif de primitives

Cette analogie est illustrative. Les latents SAE ne sont pas des « modèles » au sens IDM ; MorphoRepr n'a pas la sémantique formelle du MOF. L'analogie motive la structure autoréférentielle de l'inventaire de morphèmes (les morphèmes peuvent, en principe, décrire d'autres morphèmes) mais ne constitue pas une preuve formelle d'aucune propriété.

---

## 4. Étude de faisabilité agentique

### 4.1 Motivation pour une approche agentique

L'induction d'un lexique MorphoRepr à partir de features SAE requiert à la fois une application cohérente de règles formelles (accessible à l'automatisation) et un jugement sémantique sur la pertinence des morphèmes (nécessitant un raisonnement au niveau LLM). Cette combinaison motive un pipeline multi-agents.

### 4.2 Architecture du pipeline

Le pipeline se compose de cinq phases. Les gabarits de prompts complets pour chaque agent sont fournis en Annexe B.

#### Phase 1 : Extraction des features SAE

**Objectif** : constituer un corpus stratifié de features SAE avec des exemples d'activation.

**Sources de données** : SAEs publics pour Claude 3 Sonnet via l'API Neuronpedia ; SAE-Bench (EleutherAI) ; `sae_lens`.

L'*agent de chargement* récupère pour chaque feature son index, ses 20 exemples à activation maximale, son score d'interprétabilité existant et sa fréquence d'activation. L'*agent de classement* constitue **trois splits d'évaluation** pour éviter le biais de sélection vers les features faciles à interpréter :

- **Easy set** (n=200) : features avec score d'interprétabilité ≥ 0,7, haute fréquence
- **Random set** (n=200) : features échantillonnés uniformément sans filtrage par score
- **Hard set** (n=100) : features avec score d'interprétabilité < 0,5, ou context-dépendants, ou spécifiques à un domaine (code, mathématiques, entités nommées, multilingue)

Cette stratification garantit que les statistiques de couverture reflètent la distribution complète des latents SAE, non uniquement le sous-ensemble le plus interprétable.

#### Phase 2 : Induction du lexique MorphoRepr

**Objectif** : identifier un ensemble minimal de morphèmes couvrant l'espace sémantique du corpus de features.

L'*agent de clustering* plonge les descriptions en langue naturelle à l'aide de nomic-embed-text et applique un clustering k-means (k ≈ 20). L'*agent de labélisation* propose des morphèmes par cluster. L'*agent de cohérence* valide selon trois critères : non-redondance (similarité cosinus < 0,7), couverture et composabilité. Les échecs déclenchent une boucle de feedback (max 5 itérations).

**Gouvernance du lexique** : les racines libres doivent être enregistrées dans un lexique versionné. Une racine libre ne peut pas entrer en collision avec un token existant de préfixe, infixe ou suffixe. Le lexique enregistre pour chaque racine libre : sa chaîne, sa définition formelle, son énoncé de portée, son cluster de features inducteur et son horodatage de version.

#### Phase 3 : Encodage des features et mesure de couverture

**Objectif** : encoder chaque feature et calculer des statistiques de couverture stratifiées.

L'*agent d'encodage* produit une expression MorphoRepr pondérée ou une réponse UNCOVERED avec justification. L'*agent d'évaluation* calcule :

(a) **Taux de couverture brut** par split (easy / random / hard) : pourcentage de features avec confiance de l'encodeur ≥ 0,6 ;
(b) **Score de fidélité** : un second LLM juge évalue si l'expression MorphoRepr prédit correctement les exemples à forte activation (protocole de scoring par simulation de Paulo et al., 2024) ;
(c) **Taux UNCOVERED** par split, catégorisé par type de feature (entité nommée, pragmatique, spécifique à un domaine, context-dépendant).

**Comparaisons aux baselines** (exécutées en parallèle sur le même corpus) :
- Étiquettes en langue naturelle (générées par LLM, sans contrainte)
- Semantic Regexes (protocole Boggust et al., 2025)
- Tags-mots-clés contrôlés (syntagme nominal unique, sans composition)
- Expressions MorphoRepr valides aléatoires (grammaticalement correctes, sémantiquement arbitraires) — sert de borne inférieure

Métriques de comparaison : longueur des descriptions (tokens), cohérence entre runs (ROUGE-L entre deux runs d'annotation indépendants), score de fidélité, taux UNCOVERED.

#### Phase 4 : Validation causale par steering d'activation

**Objectif** : vérifier que les expressions MorphoRepr sont prédictives causalement du comportement du modèle sous intervention sur les features, non de simples paraphrases plausibles.

**Protocole** : pour chaque feature encodé, l'*agent de steering* amplifie le latent SAE cible de +5 unités d'activation (Anthropic, 2024) sur 20 phrases-sondes neutres. Un *agent de prédiction causale* génère une prédiction comportementale basée **uniquement sur l'expression MorphoRepr** (non la description en langue naturelle). Un *agent juge* évalue si le déplacement de sortie observé correspond à la prédiction.

**Métrique de validité causale** : pour chaque feature, un score binaire (prédiction correcte / incorrecte). Score de validité causale agrégé = fraction de features avec prédictions correctes. Le même protocole est exécuté pour les étiquettes en langue naturelle et les Semantic Regexes pour permettre la comparaison directe.

**Garde-fou méthodologique contre la circularité** : l'agent juge reçoit uniquement l'expression MorphoRepr et le déplacement de sortie observé. Il ne reçoit pas la description en langue naturelle du feature. Cette contrainte est appliquée par le contrôleur du pipeline. Elle garantit que la validation mesure le pouvoir prédictif de l'encodage MorphoRepr lui-même, non celui de la description en langue naturelle sous-jacente qui l'a généré.

**Contrôles de validité supplémentaires** :
- Ablation : étiquettes MorphoRepr valides aléatoires comme contrôle négatif
- Split de features : validation causale exécutée séparément pour les splits easy / random / hard
- Cohérence entre runs : deux runs d'annotation indépendants, κ de Cohen sur les scores de validité causale binaires

**Seuil de décision go/no-go** : validité causale agrégée ≥ 0,65 sur le random set (non l'easy set) constitue le seuil de publication.

#### Phase 5 : Synthèse et publication

L'*agent de rapport* génère des statistiques de couverture et validité causale stratifiées. L'*agent d'analyse des lacunes* classe les features UNCOVERED. L'*agent de rédaction* produit un résumé structuré des résultats.

### 4.3 Stack technique

```
Orchestration :   Claude Code (boucle agentique) ou LangGraph
Agents LLM :      Claude Sonnet (tâches de jugement sémantique)
                  Claude Haiku (tâches répétitives de scoring et mise en forme)
Accès SAE :       sae_lens + API Neuronpedia (neuronpedia.org)
Embeddings :      nomic-embed-text (clustering des descriptions de features)
Clustering :      scikit-learn k-means + UMAP (visualisation)
Stockage :        SQLite (corpus de features) + JSON (lexique versionné)
Évaluation :      SAE-Bench (EleutherAI) comme benchmark externe
Baselines :       étiquettes en langue naturelle, Semantic Regexes,
                  tags-mots-clés contrôlés, étiquettes MorphoRepr aléatoires
Points de sauvegarde : snapshot complet de l'état du pipeline après chaque phase
```

### 4.4 Critères de succès

| Métrique | Seuil minimal | Seuil de publication | Cible baseline |
|----------|--------------|---------------------|----------------|
| Couverture brute — easy set (conf ≥ 0,6) | 65 % | 80 % | — |
| Couverture brute — random set (conf ≥ 0,6) | 45 % | 60 % | — |
| Couverture brute — hard set (conf ≥ 0,6) | 20 % | 35 % | — |
| Validité causale — random set | 50 % | 65 % | > étiquettes NL |
| Score de fidélité | 0,55 | 0,70 | > étiquettes NL |
| Cohérence entre runs (ROUGE-L) | 0,60 | 0,75 | > étiquettes NL |
| Taille finale du lexique | < 250 morphèmes | < 150 morphèmes | — |
| Features UNCOVERED catégorisés | — | ≥ 80 % | — |

Une couverture brute inférieure à 40 % sur le random set n'invalide pas la contribution ; elle constituerait un résultat négatif précisément caractérisé quantifiant quelles propriétés des latents SAE résistent à l'encodage morphologique — contribution en soi à la théorie de la structure des features dans les LLMs.

---

## 5. Agenda de recherche

*Cette section esquisse des directions de recherche à plus long terme, conditionnelles aux résultats expérimentaux de la Section 4. Elle ne constitue pas une contribution du présent papier.*

Si MorphoRepr s'avère causalement valide comme système d'annotation, deux extensions naturelles se dessinent.

**MorphoRepr-Edit.** Les expressions MorphoRepr pourraient servir d'espace d'adressage structuré pour l'édition de modèles (de style ROME/MEMIT), transformant la procédure de localisation coûteuse au cas par cas en une consultation structurée dans un espace sémantiquement typé. C'est hautement spéculatif : MorphoRepr adresse des latents SAE, non des matrices de poids directement, et le mapping des latents vers des directions de poids éditables nécessiterait des travaux substantiels supplémentaires. ROME et MEMIT opèrent sur des associations factuelles dans les couches MLP ; une généralisation à du contenu morpho-sémantique arbitraire reste un problème ouvert.

**MorphoRepr-Memory.** Une architecture mémorielle hybride inspirée de la théorie CLS pourrait combiner un magasin vectoriel externe (tampon épisodique, indexé par des embeddings MorphoRepr) avec une consolidation paramétrique sélective via LoRA. L'attrait est une interface de récupération auditable par l'humain : les requêtes en syntaxe MorphoRepr sont interprétables par des opérateurs humains. Le problème ouvert clé est que lire depuis les espaces d'activation se réduit à une projection linéaire (bien comprise), tandis qu'écrire dans un système dynamique non linéaire de façon compositionnelle et sans interférence n'est garanti par aucune théorie actuelle.

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

La question ouverte clé distinguant MorphoRepr des Semantic Regexes est de savoir si la composition morphologique agglutinante produit un avantage mesurable en cohérence d'annotation et pouvoir prédictif causal. Les expressions MorphoRepr sont compactes et prononçables (`0,88·mal-o + 0,34·ne-a`) ; les expressions Semantic Regex sont logiquement explicites (`¬token("not") | field("negation")`). Les deux propriétés ont des avantages potentiels ; le protocole d'évaluation de la Section 4 est conçu pour les mesurer empiriquement plutôt que de les supposer.

---

## 7. Discussion

### 7.1 Ce que MorphoRepr peut et ne peut pas exprimer

MorphoRepr capture :
- Les propriétés morpho-syntaxiques (temps, aspect, négation, agentivité, rôle syntaxique)
- Le domaine sémantique large (connaissance, affect, action, espace, relation sociale, données)
- La force d'activation (via les coefficients)

Il ne capture pas :
- Les features d'entités nommées très spécifiques (« features à propos de la Tour Eiffel »)
- Les features profondément pragmatiques (ironie, registre, connotation culturelle)
- Les features définis par un contexte textuel spécifique plutôt que par une propriété sémantique
- Les relations inter-features (comment deux features interagissent causalement)

La couverture estimée de 45 à 65 % sur le random set (en attente de validation empirique) signifie qu'une fraction substantielle des latents SAE se situe par conception hors de la portée expressive de MorphoRepr. Ce n'est pas un échec — c'est une quantification de la frontière entre contenu morpho-sémantique et contextuel-pragmatique dans l'espace de features LLM.

### 7.2 Pourquoi l'espéranto et non une autre langue agglutinante

Le choix de l'espéranto comme modèle structurel (non comme langue elle-même) repose sur quatre propriétés pertinentes pour un langage contrôlé d'annotation : morphologie entièrement régulière (sans exceptions), inventaire fini d'affixes (~40 affixes à sens formellement définis), notation en alphabet latin (intégrable dans des formats de texte standard), et apprenabilité humaine (le système morphologique peut être appris à partir d'une petite table de référence en quelques heures). Le turc, le finnois, le hongrois et le japonais sont également agglutinants, mais leurs irrégularités de langue naturelle compliqueraient la spécification formelle.

Nous ne prétendons pas que la morphologie espéranto est intrinsèquement optimale pour cette application. Le protocole d'évaluation testera si une notation d'inspiration morphologique réduit la variance d'annotation et améliore le pouvoir prédictif causal par rapport aux alternatives. Si ce n'est pas le cas, un autre système de notation devrait être utilisé.

### 7.3 Gouvernance et versionnage du lexique

L'extensibilité de MorphoRepr via les racines libres crée une tension : un petit lexique fermé limite la couverture ; un lexique extensible sans contraintes risque de devenir un vocabulaire contrôlé ad hoc sans propriétés formelles stables. La résolution adoptée ici est un **lexique gouverné et versionné** : les racines libres sont enregistrées avec définitions formelles, énoncés de portée et horodatages de version. Chaque run expérimental enregistre quelle version du lexique a été utilisée. Les conflits sémantiques, la synonymie et les dépréciations sont tracés explicitement. Cette structure de gouvernance est nécessaire pour la reproductibilité et la comparaison de résultats entre runs.

---

## 8. Conclusion

Nous avons proposé MorphoRepr, un langage contrôlé à structure morphologique pour l'annotation des features SAE dans les LLMs, et décrit un pipeline agentique en cinq phases et un protocole d'évaluation complet pour évaluer sa couverture, sa cohérence, sa fidélité et sa validité causale par rapport aux étiquettes en langue naturelle et aux Semantic Regexes.

Ce papier est un article de positionnement et protocole d'évaluation ; il ne revendique pas de résultats expérimentaux. Le cas théorique en faveur de MorphoRepr repose sur trois observations convergentes : la compositionnalité documentée des espaces d'activation LLM (hypothèse de représentation linéaire), l'analogie structurelle entre la morphologie agglutinante et la composition additive des latents SAE, et l'insuffisance démontrée des étiquettes en langue naturelle pour les tâches d'interprétabilité systématique. Si ce cas théorique se traduit en un système pratiquement utile est une question empirique que le pipeline décrit en Section 4 est conçu pour répondre.

La question ouverte centrale n'est pas si MorphoRepr est meilleur que la langue naturelle — il est presque certainement meilleur en cohérence et moins bon en couverture. La question centrale est de savoir s'il est meilleur que les Semantic Regexes, et spécifiquement si la composition agglutinante apporte un avantage mesurable en pouvoir prédictif causal qui justifie le coût cognitif supplémentaire d'apprendre une nouvelle notation.

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
expression        ::= terme ('+' terme)*
terme             ::= coefficient '·' mot
coefficient       ::= '0.' chiffre-nonzero chiffre
                    | '0.' chiffre chiffre-nonzero
                    | '1.00'
(* coefficient ∈ [0,01 ; 1,00] ; la contrainte est sémantique, pas purement syntaxique *)
(* chiffre ::= '0'|'1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9' *)
(* chiffre-nonzero ::= '1'|'2'|'3'|'4'|'5'|'6'|'7'|'8'|'9' *)

mot               ::= (préfixe)* racine (infixe)* suffixe
préfixe           ::= 'mal-' | 'ne-' | 'pli-' | 'plej-' | 'duon-'
racine            ::= racine-prédéfinie | racine-libre
racine-prédéfinie ::= 'sci' | 'emo' | 'ag' | 'dir' | 'soc'
                    | 'dat' | 'tem' | 'lok' | 'mal' | 'ne'
racine-libre      ::= [a-z]{2,5}
                    (* racines induites par le pipeline, enregistrées dans le lexique ;
                       ne doit pas entrer en collision avec un token de préfixe,
                       infixe ou suffixe *)
infixe            ::= '-ad-' | '-int-' | '-it-' | '-ist-' | '-ant-'
                    | '-at-' | '-ig-' | '-iĝ-'
suffixe           ::= suffixe-syntaxique | suffixe-temporel
suffixe-syntaxique ::= '-o' | '-a' | '-e' | '-i'
suffixe-temporel  ::= '-as' | '-is' | '-os' | '-us' | '-u'
```

### A.2 Règles de composition

1. Un mot doit contenir exactement une racine.
2. Les préfixes précèdent la racine ; les infixes suivent la racine et précèdent le suffixe ; le suffixe est final.
3. Les préfixes multiples sont autorisés et se composent de gauche à droite : `mal-ne-X` = « non-absent-X » ≠ `ne-mal-X` = « non-contraire-X ».
4. Les coefficients doivent être dans [0,01 ; 1,00]. Un coefficient de 0,00 indique un feature absent et ne doit pas apparaître dans les expressions.
5. Les termes d'une expression sont ordonnés par coefficient décroissant.
6. Les racines libres doivent être enregistrées dans le lexique versionné avant utilisation ; les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.
7. Une racine libre ne peut pas être identique à un token de préfixe (`mal`, `ne`, `pli`, `plej`, `duon`), d'infixe (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) ou de suffixe (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`).
8. Un mot se terminant par un suffixe temporel (`-as`, `-is`, `-os`, `-us`, `-u`) est interprété comme verbal. Un mot se terminant par un suffixe syntaxique (`-o`, `-a`, `-e`, `-i`) est interprété comme nominal, adjectival, adverbial ou infinitival respectivement. Ces deux familles de suffixes sont mutuellement exclusives au sein d'un même mot.

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
In both cases, provide a formal definition, scope statement,
and coverage examples.
```

### B.2 Prompt système de l'agent d'encodage

```
You are encoding SAE features into MorphoRepr expressions.

MorphoRepr is an agglutinative formal language where:
- Each term has the form: coefficient · morpheme-chain
- Coefficients are in [0.01, 1.00] (two decimal places)
- Morpheme chains follow the grammar: (prefix)* root (infix)* suffix
- Suffix is either a syntactic suffix (-o, -a, -e, -i) or a tense
  suffix (-as, -is, -os, -us, -u), not both
- Domain roots (sci, emo, ag, dir, soc, dat, tem, lok) and
  registered free roots are the only valid roots
- An expression contains 1-4 terms, ordered by descending coefficient
- State your encoding rationale for each term
- If you cannot encode a feature with confidence ≥ 0.50 using the
  available lexicon, respond UNCOVERED and explain what semantic
  content the lexicon cannot express

Be precise about confidence. Overconfident encodings that fail
causal validation are more harmful than honest UNCOVERED responses.
```

### B.3 Prompt système de l'agent de prédiction causale

```
You are predicting the effect of amplifying a SAE feature on LLM output.

Given a MorphoRepr expression for a feature, predict:
1. In which semantic direction will outputs shift when this feature
   is amplified by +5 activation units?
2. Which of the following output properties would you expect to increase?
   [list of measurable output properties]
3. What is your confidence in this prediction? [0.0 - 1.0]

Base your prediction ONLY on the MorphoRepr expression provided.
Do not use the natural language description of the feature.
This constraint is intentional: we are testing whether MorphoRepr
expressions alone are sufficient for causal prediction.
```

---

## Annexe C : Modifications par rapport à la version 0.23

Les modifications suivantes ont été apportées en réponse aux commentaires de reviewers sur le preprint v0.23.

**Titre et cadrage.** Le titre passe de « un méta-langage à structure morphologique pour la projection lisible par l'humain des représentations internes des LLMs » à « un langage contrôlé à structure morphologique pour la description des features SAE des LLMs — un article de positionnement et protocole d'évaluation ». Le sous-titre rend le statut du papier explicite. Le cadrage a été déplacé de « projection des représentations internes » vers « annotation des latents SAE », ce qui décrit plus précisément la contribution.

**Résumé et Introduction.** L'affirmation « aucune langue naturelle ne dispose d'un pouvoir expressif suffisant » a été remplacée par une affirmation plus précise : les descriptions en langue naturelle sont insuffisamment structurées pour l'évaluation systématique, la comparaison inter-features et la prédiction causale. Une note de statut du papier a été ajoutée en Section 1.2.

**Disclaimer de portée.** Un paragraphe a été ajouté en Section 2.1 et une phrase en Section 1 précisant explicitement que MorphoRepr encode des hypothèses humaines sur la sémantique des latents SAE, non des représentations vérifiées des représentations internes du modèle, et qu'un latent SAE n'est pas équivalent à un concept humain.

**Correction de la BNF — coefficient.** La règle de production du coefficient a été corrigée. L'ancienne règle `[0-9]'.'[0-9][0-9]` admettait des valeurs hors de [0,01 ; 1,00] (ex. 9,99). La nouvelle règle contraint explicitement les coefficients à [0,01 ; 1,00].

**Disambiguation des suffixes.** La BNF distingue maintenant `suffixe-syntaxique` (`-o`, `-a`, `-e`, `-i`) et `suffixe-temporel` (`-as`, `-is`, `-os`, `-us`). La règle de composition 8 explicite qu'un mot se termine par l'un ou l'autre, jamais les deux. `ag-is` est clairement verbal ; `ag-int-a` est adjectival.

**Règle de collision des racines libres.** La règle 7 interdit qu'une racine libre soit identique à un token réservé de préfixe, infixe ou suffixe. Le prompt de l'agent de labélisation a été mis à jour en conséquence.

**Splits d'évaluation stratifiés.** Le corpus d'évaluation a été restructuré en trois splits (easy / random / hard) pour éviter le biais de sélection vers les features très interprétables. Les critères de succès sont maintenant différenciés par split. Le seuil de publication porte sur le random set, non l'easy set.

**Comparaisons aux baselines.** Le protocole d'évaluation Phase 3 spécifie désormais quatre baselines à exécuter en parallèle : étiquettes en langue naturelle, Semantic Regexes, tags-mots-clés contrôlés et expressions MorphoRepr valides aléatoires. Le tableau de positionnement a été mis à jour.

**Garde-fou anti-circularité.** Un garde-fou méthodologique a été ajouté à la Phase 4 : l'agent juge reçoit uniquement l'expression MorphoRepr et le déplacement observé — non la description en langue naturelle. Cette contrainte est rendue explicite et justifiée.

**Correction des références.** La référence à « Templeton et al. (2024), Scaling and evaluating sparse autoencoders » a été corrigée. Le papier sur le scaling de l'entraînement des SAEs est Gao et al. (2024), arXiv:2406.04093. Le papier Anthropic sur les features de Claude 3 Sonnet est désormais cité comme Anthropic (2024), *Extracting Interpretable Features from Claude 3 Sonnet*, Transformer Circuits Thread.

**Section 3.4 (analogie IDM/MOF).** Une note éditoriale a été ajoutée rendant explicite que cette section est optionnelle et ne constitue pas une justification scientifique.

**Section 5 (anciennement consolidation mémorielle).** Réduite à une page d'agenda de recherche, explicitement spéculative et conditionnelle aux résultats expérimentaux. L'architecture mémorielle complète a été retirée des contributions principales.

**Exemples d'encodage.** Chaque exemple inclut désormais une note « limitation reconnue » ou « justification de l'encodage » pour rendre explicite le statut pédagogique des exemples.

---

*Version 0.24 — Juin 2026*
*Michaël Launay — michaellaunay@logikascium.com*
*Logikascium EURL — https://www.logikascium.com*
*GitHub : https://github.com/michaellaunay/morphorepr*
