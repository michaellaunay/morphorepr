# MorphoRepr : un langage contrôlé à structure morphologique pour la description des features SAE des LLMs
## Un article de positionnement et protocole d'évaluation

**Title (English):** MorphoRepr: A Morphologically Structured Controlled Language for SAE Feature Description in LLMs — A Position Paper and Evaluation Protocol

**Michaël Launay**
Logikascium (EURL), Fretin, France
Enseignant vacataire, Université de Lille / ENSAM Lille / Polytech Lille
michaellaunay@logikascium.com

---

*Preprint — article de positionnement et protocole d'évaluation — soumis à arXiv cs.CL / HAL*
*Version 0.27 — Juin 2026*
*Remplace la version 0.26. Aucun résultat expérimental n'est revendiqué dans cette version ; les résultats seront rapportés à l'issue de l'exécution du pipeline.*

**Note sur les versions** : ceci est la version longue HAL/arXiv. Une version courte workshop (cœur conceptuel, métriques principales, annexes résumées) est disponible sur demande et sera soumise séparément aux venues consacrées à l'interprétabilité et à l'IA centrée sur l'humain. La liste détaillée des modifications par rapport à la version 0.26 figure en Annexe C.

---

## Résumé

Les descriptions en langue naturelle des features des autoencodeurs sparses (SAEs) dans les grands modèles de langage (LLMs) peuvent être utiles et souvent précises, mais elles sont insuffisamment structurées pour l'évaluation systématique, la comparaison inter-features, l'agrégation statistique et la prédiction causale. Elles sont vagues, inconsistantes entre runs d'annotation, et résistent à la manipulation formelle. Nous proposons **MorphoRepr**, un langage contrôlé à structure morphologique inspiré d'une morphologie agglutinante régulière de type espéranto, conçu comme couche d'annotation lisible par l'humain pour les features sparses produits par des SAEs entraînés sur les activations de LLMs. Chaque expression MorphoRepr encode des hypothèses humaines sur la sémantique d'un ou plusieurs latents SAE sous forme d'une chaîne compositionnelle de morphèmes à sémantique formellement définie, pondérés par des coefficients normalisés. MorphoRepr ne prétend pas décoder les représentations internes des LLMs ; il encode des hypothèses humaines structurées sur la sémantique des latents SAE, hypothèses qui doivent être validées par des expériences de prédiction d'activation et d'intervention causale. Soulignons d'emblée que MorphoRepr évalue la *prédictivité d'une annotation*, et non la puissance brute d'une méthode de steering.

Nous présentons le cadre formel, un pipeline d'évaluation agentique en cinq phases, et un protocole d'évaluation complet spécifiant des métriques de couverture, fidélité (comme tâche de discrimination avec AUC-ROC), validité causale (via des classifieurs de propriétés de sortie stratifiés, avec un score primaire en macro-F1 et des intervalles de confiance bootstrap sur la **différence appariée** entre méthodes), productivité morphologique, et cohérence d'annotation au niveau morphémique — incluant des comparaisons directes, **sur un ensemble de features partagé**, aux étiquettes en langue naturelle, aux Semantic Regexes (Boggust et al., 2025), aux tags-mots-clés contrôlés et à un contrôle par annotations mélangées intra-split. La question ouverte centrale est de savoir si la composition morphologique agglutinante apporte un avantage mesurable sur ces alternatives en cohérence d'annotation, compacité et pouvoir prédictif causal. Les résultats expérimentaux seront rapportés dans une version ultérieure à l'issue de l'exécution du pipeline.

**Mots-clés :** interprétabilité mécaniste, autoencodeurs sparses, morphologie agglutinante, espéranto, annotation de features SAE, langage contrôlé, validité causale, productivité morphologique

---

## Abstract (English)

Natural language descriptions of SAE features in LLMs can be useful and often accurate, but they are insufficiently structured for systematic evaluation, cross-feature comparison, and causal prediction. We propose MorphoRepr, a morphologically structured controlled language for SAE feature annotation, inspired by Esperanto-like regular agglutination without any claim of linguistic optimality. We present a five-phase agentic evaluation pipeline with a complete evaluation protocol including fidelity as an AUC-ROC discrimination task, causal validity via stratified output property classifiers (with a macro-F1 primary score and bootstrap confidence intervals on the *paired* per-feature difference between methods, computed on a shared feature set), morphological productivity metrics, a within-split shuffled control, and a planned human audit and user study. MorphoRepr evaluates the predictivity of an annotation, not the raw power of a steering method. This is a position paper; no experimental claims are made.

**Keywords:** mechanistic interpretability, sparse autoencoders, agglutinative morphology, Esperanto, SAE feature annotation, controlled language, causal validity, morphological productivity

---

## 1. Introduction

Les représentations internes des grands modèles de langage (LLMs) demeurent largement opaques à l'inspection humaine. Les autoencodeurs sparses (SAEs) ont émergé comme un outil scalable pour décomposer ces représentations en directions de features plus sparses et plus monosémantiques (Bricken et al., 2023 ; Cunningham et al., 2023 ; Anthropic, 2024). Les latents résultants sont plus interprétables que les neurones individuels, mais le problème de leur *labélisation* à grande échelle — leur assigner des descriptions précises, cohérentes et formellement manipulables — demeure un goulot d'étranglement significatif.

Les approches actuelles s'appuient sur des étiquettes en langue naturelle générées par des LLMs, qui peuvent être utiles et souvent précises mais présentent des limitations bien connues comme système de notation formelle : imprécision, inconsistance entre runs, et inadaptation au raisonnement compositionnel ou à la comparaison statistique sur de grands inventaires de features (Boggust et al., 2025 ; Paulo et al., 2024). Le défi n'est pas que la langue naturelle soit inexpressive en principe — elle peut décrire presque tout, au prix de la verbosité. Le défi est que les descriptions en langue naturelle sont **insuffisamment structurées** pour les tâches systématiques que requiert l'interprétabilité à grande échelle : comparaison inter-features, statistiques au niveau des morphèmes, prédiction causale à partir de l'étiquette seule, et recherche programmatique dans les espaces de features.

MorphoRepr s'inscrit dans la tradition des *langages contrôlés* (controlled natural languages, CNL ; Kuhn, 2014) : une notation à syntaxe et vocabulaire restreints, conçue pour la précision et la manipulabilité. Son antécédent le plus proche en interprétabilité est le langage structuré des Semantic Regexes (Boggust et al., 2025), une baseline forte — code et package publics, et déjà validée par une étude utilisateur — par rapport à laquelle MorphoRepr doit être évalué. La différence est le mécanisme de composition : opérateurs logiques pour les Semantic Regexes, concaténation morphologique agglutinante pour MorphoRepr.

Ce papier propose **MorphoRepr**, un langage contrôlé pour l'annotation des features SAE qui répond à ces limitations en empruntant la logique structurelle d'une morphologie agglutinante régulière de type espéranto — composition agglutinante, inventaire fini de morphèmes, règles dérivationnelles transparentes — et en l'étendant avec un vocabulaire contrôlé de primitives sémantiques dérivées empiriquement de l'espace de features SAE d'un LLM de production. L'affirmation centrale n'est pas que MorphoRepr capture la géométrie interne des représentations LLM — il ne le fait explicitement pas — mais qu'il peut fournir un système d'annotation plus cohérent, plus compact et plus prédictif causalement que les alternatives existantes pour le sous-ensemble de latents SAE dont le contenu est stable et morpho-sémantiquement exprimable.

**Note sur la portée.** MorphoRepr encode des hypothèses humaines sur la sémantique des latents SAE. Un latent SAE n'est pas équivalent à un concept humain : les latents sont des directions apprises dans l'espace d'activation, dépendantes des objectifs de reconstruction, des contraintes de sparsité, des statistiques du corpus et de l'architecture du modèle. Leur interprétabilité est prometteuse mais partielle. Les descriptions MorphoRepr sont des hypothèses sur le contenu des latents, non des vérités sur les représentations internes du modèle.

### 1.1 Contributions

Ce papier apporte les contributions suivantes :

1. **Conceptuelle** : nous proposons MorphoRepr comme langage contrôlé pour l'annotation des features SAE et établissons son ancrage théorique dans l'hypothèse de représentation linéaire et l'hypothèse de superposition, tout en distinguant explicitement ses deux mécanismes de composition (additif et agglutinant), de statut épistémique différent (Section 3.1).

2. **Méthodologique** : nous décrivons un pipeline agentique en cinq phases pour induire empiriquement un lexique MorphoRepr à partir de features SAE, et spécifions un protocole d'évaluation complet incluant : la couverture sur des splits stratifiés ; la fidélité comme tâche de discrimination AUC-ROC ; la validité causale via des classifieurs de propriétés de sortie stratifiés (robustes, semi-robustes et fragiles), avec un **score primaire en macro-F1** et des **intervalles de confiance bootstrap sur la différence appariée entre méthodes**, calculés **sur un ensemble de features partagé** ; des métriques de productivité morphologique ; des métriques de cohérence d'annotation au niveau morphémique ; un contrôle mélangé intra-split ; et un audit humain et une étude utilisateur planifiés. La validation causale principale est conçue pour s'exécuter sur un modèle proxy open-weight (Section 4.2).

3. **Prospective** : nous identifions les questions de recherche ouvertes que les versions expérimentales ultérieures devront traiter, discutons les menaces à la validité, et esquissons un agenda de recherche à plus long terme.

### 1.2 Statut du papier

Ce papier est un **article de positionnement et protocole d'évaluation**. Il présente un cadre formel et un protocole expérimental complet ; il ne rapporte pas de résultats expérimentaux. Les résultats seront rapportés dans une version ultérieure (v1.0) à l'issue de l'exécution du pipeline agentique décrit en Section 4.

Pour clarifier ce qui est et n'est pas revendiqué, le tableau suivant met en regard chaque affirmation, son statut dans la présente version et l'évidence prévue pour la tester :

| Affirmation | Statut (v0.27) | Évidence prévue |
|-------------|----------------|-----------------|
| MorphoRepr est plus compact que les étiquettes NL | Hypothèse | longueur / entropie / étude utilisateur |
| MorphoRepr est plus cohérent que les étiquettes NL | Hypothèse | Jaccard sur deux runs |
| MorphoRepr est plus prédictif causalement que les Semantic Regexes | **Hypothèse principale** | steering + classifieurs (Section 4) |
| MorphoRepr est plus lisible que les Semantic Regexes | Hypothèse | étude utilisateur (Section 4.6) |
| MorphoRepr couvre tous les latents SAE | **Non revendiqué** | taux UNCOVERED catégorisé |
| L'agglutination apporte un gain au-delà des primitives partagées | **Question ouverte** | étude d'ablation (Section 4.7) |

---

## 2. Contexte et travaux connexes

### 2.1 Autoencodeurs sparses et interprétabilité mécaniste

L'hypothèse de représentation linéaire (LRH) postule que les réseaux de neurones encodent des concepts interprétables comme des directions linéaires dans leurs espaces d'activation (Mikolov et al., 2013 ; Park et al., 2023). L'hypothèse de superposition (Elhage et al., 2022) propose que les modèles compriment un grand nombre de tels features dans un nombre plus restreint de neurones en exploitant l'orthogonalité approximative, créant des neurones polysémantiques qui répondent à plusieurs concepts non liés. La LRH n'est toutefois pas universelle : Engels et al. (2024) montrent l'existence de features irréductiblement multidimensionnels (par exemple des structures circulaires pour les jours de la semaine ou les mois), ce qui borne la validité de toute composition strictement additive de latents 1-D.

Les autoencodeurs sparses répondent à la superposition en projetant les activations dans un espace de plus haute dimension tout en imposant la sparsité. Bricken et al. (2023) démontrent que les features SAE sont plus monosémantiques et plus interprétables que les neurones individuels. Anthropic (2024) fait passer cette approche à l'échelle des modèles de production (Claude 3 Sonnet). Gao et al. (2024) fournissent une analyse complémentaire de la dynamique d'entraînement des SAEs, de la qualité de reconstruction et des compromis de sparsité.

**Mise en garde importante** : les latents SAE sont des décompositions apprises, non des détecteurs de features vérifiés. Ils dépendent des objectifs de reconstruction, des pénalités de sparsité, de la taille du dictionnaire, du corpus d'entraînement et de l'architecture du modèle. Un latent avec une description en langue naturelle plausible n'est pas nécessairement un concept humain propre ; il peut être un artefact statistique, une régularité spécifique au corpus, ou une superposition de plusieurs patterns plus faibles. Des limitations structurelles documentées aggravent ce risque : Chanin et al. (2025) montrent que des SAEs trop étroits, en présence de features corrélées, **fusionnent** des composantes de features distinctes (*feature hedging*), détruisant la monosémanticité attendue — un phénomène suspecté de contribuer à la sous-performance des SAEs face aux baselines supervisées. Tout système d'annotation — y compris MorphoRepr — encode des hypothèses sur le contenu des latents, non des faits sur les représentations internes du modèle, et ne doit pas présupposer que tous les latents sont propres.

Le goulot d'étranglement actuel est la *labélisation* : assigner des descriptions humainement lisibles aux dizaines de milliers de features découverts par les grands SAEs. Les approches existantes utilisent des LLMs pour générer des descriptions en langue naturelle en inspectant des exemples à forte activation (Bills et al., 2023 ; Paulo et al., 2024). Ces descriptions peuvent être utiles et souvent précises, mais elles sont insuffisamment structurées pour l'évaluation systématique et le raisonnement formel.

### 2.2 Langages structurés pour l'annotation de features

Boggust et al. (2025) introduisent les *Semantic Regexes*, un langage structuré pour décrire automatiquement les features LLM en combinant des primitives pour les motifs de tokens exacts, les formes syntaxiques et les catégories sémantiques avec des modificateurs pour la contextualisation, la composition et la quantification. Leur travail rapporte que les Semantic Regexes égalent la précision des étiquettes en langue naturelle tout en produisant des descriptions plus concises et plus cohérentes, et qu'une étude utilisateur montre qu'ils aident à construire des modèles mentaux précis des features. Leur code et un package Python sont publics. C'est l'antécédent le plus proche de MorphoRepr et la baseline principale contre laquelle MorphoRepr doit être évalué : nous utilisons leur implémentation officielle dans le protocole (Section 4).

La différence structurelle clé est le mécanisme de composition. Les Semantic Regexes combinent des primitives par des opérateurs logiques (ET, OU, NON, contexte). MorphoRepr est un langage contrôlé *agglutinant*, où les primitives sont combinées par concaténation selon des règles morphologiques, produisant un token unique prononçable plutôt qu'une formule. Si cette distinction produit un avantage mesurable en cohérence d'annotation, charge cognitive ou pouvoir prédictif causal est la question empirique centrale que ce papier prépare à répondre. Comme les Semantic Regexes ont déjà démontré concision et cohérence par rapport au NL, l'enjeu spécifique de MorphoRepr se situe *vis-à-vis des Semantic Regexes*, et non du NL.

L'affirmation de meilleure lisibilité humaine — que `0.87·mal-far-int-e` est plus lisible que `¬(ag:past & subject:human)` — est une hypothèse ergonomique, non un résultat établi. Cela sera testé dans l'étude utilisateur planifiée (Section 4.6).

**Fidélité comme tâche de détection.** La métrique de fidélité que nous adoptons (Section 4) — discriminer les exemples à forte activation des contrôles à partir de l'annotation seule — relève de la tradition du *detection scoring* de l'auto-interprétation (Bills et al., 2023 ; Paulo et al., 2024), reformulée ici en AUC-ROC. Nous ne la présentons pas comme nouvelle, mais comme un endpoint testable réutilisé.

### 2.3 Édition de modèles

ROME (Meng et al., 2022) et MEMIT (Meng et al., 2023) démontrent que les connaissances factuelles dans les transformers peuvent être localisées dans des matrices de poids MLP spécifiques et modifiées chirurgicalement. Ces techniques sont pertinentes comme cible applicative à plus long terme pour MorphoRepr, discutée brièvement en Section 5.

### 2.4 Systèmes d'apprentissage complémentaires

La théorie des systèmes d'apprentissage complémentaires (CLS) (McClelland et al., 1995 ; Kumaran et al., 2016) — mémoire hippocampique rapide et néocorticale lente — motive uniquement l'agenda de recherche à plus long terme esquissé en Section 5 (MorphoRepr-Memory) et n'est pas une justification de la contribution présente.

### 2.5 Explication agentique, autoencodeurs en langage naturel et benchmarks de steering

Plusieurs travaux récents délimitent la place de MorphoRepr.

**Explication agentique.** SAGE (Han et al., 2025) est un framework agentique qui, pour chaque feature, formule plusieurs explications, conçoit des expériences d'activation pour les tester, et raffine les explications à partir du retour empirique. MorphoRepr partage l'esprit agentique (Section 4) mais vise une *notation contrôlée* plutôt qu'une explication en langue libre.

**Autoencodeurs en langage naturel (NLA).** Anthropic (2026) entraîne un modèle à traduire ses activations en texte (verbaliseur d'activation) puis à reconstruire l'activation à partir de ce texte seul (reconstructeur d'activation). MorphoRepr est lui aussi une couche textuelle entre activation et interprétation, mais avec une visée différente : les NLAs optimisent un texte naturel pour la *reconstruction* de l'activation, tandis que MorphoRepr optimise une notation contrôlée pour la *cohérence, la recherche, la comparaison et la prédiction causale*. Les deux paradigmes de validation diffèrent (reconstruction d'activation vs intervention causale).

**Benchmarks de steering et baselines représentationnelles.** AxBench (Wu et al., 2025) compare directement prompting, finetuning, SAEs, difference-in-means (DiffMean), probes linéaires et representation finetuning (ReFT). Sur le steering, le prompting surpasse toutes les méthodes, suivi du finetuning ; pour la détection de concepts, DiffMean est la meilleure ; les SAEs n'y sont pas compétitifs. Une réponse récente (Jørgensen & Hansen, 2026) nuance ce constat : les SAEs redeviennent quasi à parité avec une baseline LoRA sur AxBench lorsque les features sont sélectionnés et étiquetés par un pipeline supervisé. Ce débat est directement pertinent : MorphoRepr n'évalue pas la puissance d'une méthode de steering mais la **prédictivité causale d'une annotation**, et nous incluons DiffMean / ReFT comme points de comparaison d'intervention (Section 4.2).

---

## 3. Le système MorphoRepr

### 3.1 Principes de conception

MorphoRepr est conçu selon quatre principes :

**Compositionnalité morphologique.** Toute expression MorphoRepr est une concaténation finie de morphèmes tirés d'un inventaire fixe. Le sens d'une expression est entièrement déterminé par les sens de ses morphèmes constitutifs et leur ordre de composition.

**Encodage pondéré.** Chaque terme d'une expression est précédé d'un coefficient réel dans [0,01 ; 1,00] (voir Section 3.2 pour son interprétation). Une expression complète prend la forme :

```
c₁·m₁[-m₂[-m₃]] [+ c₂·m₄[-m₅] [+ ...]]
```

où les `mᵢ` sont des morphèmes, `-` dénote la concaténation agglutinante, `+` dénote la combinaison additive de termes, et `cᵢ ∈ [0,01 ; 1,00]` sont les coefficients ordonnés par valeur décroissante. Par exemple :

```
0.87·mal-far-int-e  +  0.41·pens-ad-is
```

se lit : *« n'ayant pas (vraiment) agi (coefficient 0,87) plus ayant continué à penser (0,41) »*.

**Deux mécanismes de composition, de statut épistémique différent.** MorphoRepr combine les morphèmes de deux manières qu'il importe de ne pas confondre. La combinaison *additive* entre termes (`c₁·m₁ + c₂·m₂`) est l'analogue naturel de la superposition linéaire : sous la LRH, des directions de features s'additionnent dans l'espace d'activation. La concaténation *agglutinante* à l'intérieur d'un mot (`mal-far-int-e`), en revanche, est ordonnée et non commutative et **ne correspond à aucune opération de l'algèbre des activations SAE** (ni somme, ni projection). Elle est, à ce stade, un pari ergonomique : produire un token unique, prononçable et compositionnel, plus lisible qu'une formule. C'est précisément ce mécanisme qui distingue MorphoRepr des Semantic Regexes, et c'est aussi celui dont l'apport doit être démontré plutôt que supposé. L'étude d'ablation (Section 4.7) est conçue pour isoler empiriquement la contribution de l'agglutination et de l'ordre.

**Sémantique formelle des morphèmes.** Chaque morphème de l'inventaire dispose d'une définition formellement spécifiée comprenant : (a) une dénotation en termes de primitive sémantique, (b) un énoncé de portée précisant ce que le morphème couvre et exclut, et (c) un ensemble de features SAE attestés que le morphème encode de façon fiable.

**Expressivité bornée.** MorphoRepr est explicitement conçu comme une *projection avec perte*. Il capture le contenu morpho-syntaxique et largement sémantique des features SAE. Le contenu pragmatique, culturel, spécifique aux entités nommées et profondément contextuel se situe hors de sa portée par conception. Le résidu — les features que le système ne peut pas encoder avec confiance ≥ 0,50 — est une sortie de première classe (UNCOVERED), non un mode d'échec.

### 3.2 Interprétation et normalisation des coefficients

MorphoRepr utilise deux types de coefficients, distingués par le contexte d'usage, et le pipeline les trace explicitement (champ `coefficient_type`) :

- **Coefficient de confiance `γ`** (mode *annotation statique*) : lorsqu'une expression annote une feature `f` indépendamment d'une instance, `γᵢ ∈ [0,01 ; 1,00]` représente la confiance de l'encodeur dans l'assignation du morphème `mᵢ`. **C'est le mode utilisé par le protocole d'évaluation de la Section 4**, et les coefficients des exemples de la Section 3.4 sont des `γ` (confiance d'annotation pédagogique), non des activations mesurées.

- **Coefficient d'activation `α`** (mode *instance contextualisée*) : lorsqu'une expression annote une instance d'activation spécifique `x`, `αᵢ(x)` représente la force d'activation normalisée du latent correspondant. La référence de normalisation est le 99e percentile des activations observées pour le latent `f` sur un corpus de référence :

```
α(f, x) = clip( a(f, x) / p99(f), 0,01, 1,00 )
```

Cette convention garantit que (a) le coefficient reflète la force relative du feature dans le contexte courant ; (b) les valeurs restent bornées et comparables entre features et couches ; (c) la combinaison additive exprime la contribution relative de deux features dans le même contexte, non leurs amplitudes absolues.

Les deux familles s'écrivent de façon identique en surface (un réel dans [0,01 ; 1,00]) ; seule la sémantique diffère, et le pipeline conserve le type. Une expression statique prend la forme `γ₁·m₁ + γ₂·m₂` ; une expression contextualisée, `α₁(x)·m₁ + α₂(x)·m₂`. *Extension prévue* : la Phase 4 mesurant de vraies activations avant/après, elle permettra de comparer empiriquement annotations en mode `γ` et en mode `α` sur le sous-ensemble steeré.

### 3.3 L'inventaire des morphèmes

L'inventaire MorphoRepr est organisé en cinq catégories. Conformément à la grammaire formalisée en Annexe A, **les morphèmes de domaine servent de racines** (noyau sémantique d'un mot), tandis que les morphèmes de polarité servent de préfixes. Les racines libres — induites par le pipeline agentique pour les concepts non couverts par le vocabulaire prédéfini — sont autorisées, dénotées par des séquences de lettres minuscules de 2 à 5 caractères ; voir note 1.

**Suffixes temporels** (encodent le temps et l'aspect verbal ; production `suffixe-temporel`) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-as` | présent, en cours | temps présent `-as` |
| `-is` | passé, accompli | temps passé `-is` |
| `-os` | futur, anticipé | temps futur `-os` |
| `-us` | conditionnel, hypothétique | conditionnel `-us` |
| `-u` | volitif, impératif | volitif `-u` |

**Infixes participiaux** (insérés entre la racine et le suffixe) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-ad-` | itératif, habituel | suffixe itératif `-ad-` |
| `-int-` | participe actif passé | `-int-` |
| `-it-` | participe passif passé | `-it-` |
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

**Racines de domaine** (racines sémantiques prédéfinies ; production `racine-prédéfinie`) :

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
| `mal` | contraire, négation (comme entité) | **double rôle** : aussi préfixe `mal-` ; voir ci-dessous |
| `ne` | absence, manque (comme entité) | **double rôle** : aussi préfixe `ne-` ; voir ci-dessous |

**Note sur le double rôle de `mal` et `ne`.** Ces deux tokens sont à la fois des *préfixes* (`mal-emo-a` = « propriété affective négative ») et des *racines prédéfinies* (`mal-o` = « le contraire, comme entité » ; espéranto `malo`). La désambiguïsation est positionnelle : `mal`/`ne` sont racines lorsqu'aucune autre racine ne les suit avant le suffixe, et préfixes sinon. Les encodeurs doivent déclarer explicitement le parse choisi (Section 3.4).

**Suffixes de rôle syntaxique** (élément final d'un mot lorsque celui-ci est nominal, adjectival, adverbial ou infinitival) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-o` | nom (entité, concept) | suffixe nominal `-o` |
| `-a` | adjectif (propriété, attribut) | suffixe adjectival `-a` |
| `-e` | adverbe (manière, degré) | suffixe adverbial `-e` |
| `-i` | infinitif (action abstraite) | suffixe infinitif `-i` |

**Note sur les types de suffixes.** MorphoRepr utilise deux familles de suffixes distinctes : les *suffixes de rôle syntaxique* (`-o`, `-a`, `-e`, `-i`) et les *suffixes temporels* (`-as`, `-is`, `-os`, `-us`, `-u`). Un mot se termine par exactement un suffixe. Un mot avec suffixe temporel est verbal ; un mot avec suffixe syntaxique est nominal, adjectival, adverbial ou infinitival. Cette distinction est explicite dans la grammaire (Annexe A) et l'inventaire ci-dessus est exhaustivement aligné sur celle-ci et sur le parseur de référence.

---

*Note 1 : Les racines libres telles que `far` (faire/agir) et `pens` (penser) sont des racines MorphoRepr valides sous la production `racine-libre ::= [a-z]{2,5}` de la grammaire. Elles sont induites par le pipeline agentique (Phase 2) lorsqu'aucune racine de domaine prédéfinie ne couvre un cluster de features. Les racines libres doivent être enregistrées dans le lexique versionné avant utilisation. Une racine libre ne peut pas être identique à un token de préfixe (`mal`, `ne`, `pli`, `plej`, `duon`), d'infixe (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) ou de suffixe (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`) déjà défini dans l'inventaire. Les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.*

---

### 3.4 Exemples d'encodage

Les exemples suivants illustrent des encodages MorphoRepr pour des features SAE. **Ces exemples sont des illustrations pédagogiques**, non des encodages validés expérimentalement, et leurs coefficients sont des confiances d'annotation (`γ`, Section 3.2). Les choix d'encodage reflètent un jugement humain éclairé et sont explicitement interprétatifs — ils peuvent varier entre annotateurs, ce que le protocole d'évaluation est précisément conçu pour mesurer. Les indices de features et descriptions sont tirés de l'interface publique Neuronpedia pour Claude 3 Sonnet (couche et version SAE à préciser dans la version expérimentale ; en mode proxy, voir Section 4.2, les features et SAE sont ceux du modèle proxy et ces exemples restent purement illustratifs).

**Feature #892** (description en langue naturelle : *« tokens dans des contextes au passé, en particulier des actions accomplies »*) :
```
0.91·ag-is
```
Parse : `ag` (racine de domaine) + `-is` (suffixe temporel, passé). Lecture : *« action physique accomplie (passé) »*, confiance 0,91. Le suffixe temporel `-is` est utilisé ici car le feature encode une propriété verbale et temporelle ; `-o` encoderait l'action-comme-entité.

**Feature #1204** (description : *« marqueurs de négation et éléments à polarité négative »*) :
```
0.88·mal-o  +  0.34·ne-a
```
Parse, terme 1 : `mal` (racine prédéfinie) + `-o` (suffixe syntaxique). Parse, terme 2 : `ne` (racine prédéfinie) + `-a`. Lecture : *« la négation comme entité (0,88) plus l'absence comme propriété (0,34) »*. Note : `mal` et `ne` fonctionnent ici comme racines (espéranto : `malo` = « le contraire »), non comme préfixes — désambiguïsation positionnelle (aucune racine ne les suit avant le suffixe) ; les encodeurs doivent déclarer explicitement ce choix de parse.

**Feature #3871** (description : *« agents humains accomplissant des actions intentionnelles, en particulier dans des contextes narratifs »*) :
```
0.79·soc-ant-o  +  0.45·ag-int-a
```
Parse, terme 1 : `soc` (racine) + `-ant-` (infixe) + `-o` (suffixe). Parse, terme 2 : `ag` (racine) + `-int-` (infixe) + `-a` (suffixe). Lecture : *« acteur social en train d'agir (0,79) plus entité ayant agi physiquement (0,45) »*.

**Feature #4102** (description : *« code Python impliquant des boucles for et des motifs d'itération »*) :
```
0.94·dat-ad-o
```
Parse : `dat` (racine) + `-ad-` (infixe, itératif) + `-o` (suffixe). Lecture : *« processus itératif de données/code »*, confiance 0,94. **Limitation reconnue** : cet encodage ne peut pas distinguer entre itération de code, série numérique, répétition textuelle ou motifs syntaxiques — limitation connue du vocabulaire de racines de domaine prédéfinies qui motive l'induction de racines libres.

**Feature #7823** (description : *« tokens apparaissant dans des contextes émotionnellement négatifs, en particulier le deuil et la perte »*) :
```
0.86·mal-emo-a  +  0.42·ne-soc-a
```
Parse, terme 1 : `mal-` (préfixe) + `emo` (racine) + `-a` (suffixe). Parse, terme 2 : `ne-` (préfixe) + `soc` (racine) + `-a` (suffixe). Lecture : *« propriété affective négative (0,86) plus absence de relation sociale (0,42) »*. **Justification de l'encodage** : le deuil et la perte impliquent à la fois une valence négative (`mal-emo-a`) et une absence relationnelle (`ne-soc-a`). **Limitation reconnue** : l'encodage reste interprétatif et pourrait varier entre annotateurs ; le protocole d'évaluation mesure cette variance directement.

**Note de portée d'une expression.** Une expression peut annoter soit *un* latent SAE (les termes en sont alors des facettes co-présentes, comme pour le feature #7823), soit *un petit cluster* de latents co-activés. Le contrat est fixé par le contexte d'usage : en Phase 4 (validation causale), une expression annote le **latent unique** qui est steeré, et ses coefficients sont des confiances `γ` sur les facettes de ce latent. Cette précision lève l'ambiguïté entre coefficient unique par latent et coefficients multiples par expression.

### 3.5 Note : analogie optionnelle avec la hiérarchie d'abstraction de l'IDM

Pour les lecteurs venant de l'ingénierie dirigée par les modèles, MorphoRepr admet une lecture par niveaux d'abstraction (instance/token → latent décrit → expression → inventaire de morphèmes), analogue aux niveaux M0–M3 de l'IDM. Cette analogie est purement illustrative, ne constitue pas une justification scientifique, et peut être ignorée sans perte de continuité ; un développement est disponible sur demande.

---

## 4. Étude de faisabilité agentique

### 4.1 Motivation pour une approche agentique

L'induction d'un lexique MorphoRepr à partir de features SAE requiert à la fois une application cohérente de règles formelles (accessible à l'automatisation) et un jugement sémantique sur la pertinence des morphèmes (nécessitant un raisonnement au niveau LLM). Cette combinaison motive un pipeline multi-agents. Nous reconnaissons d'emblée que le pipeline utilise des LLMs pour l'annotation, le jugement, la prédiction et le rapport. Les garde-fous décrits dans cette section, conjointement avec l'audit humain décrit en Section 4.3, sont conçus pour borner la circularité résultante.

### 4.2 Architecture du pipeline

Le pipeline se compose de cinq phases plus un audit humain, une étude utilisateur et une étude d'ablation planifiés. Les gabarits de prompts complets sont fournis en Annexe B.

#### Phase 1 : Extraction des features SAE

**Objectif** : constituer un corpus stratifié de features SAE avec des exemples d'activation.

**Sources de données** : SAEs publics via l'API Neuronpedia ; SAE-Bench (EleutherAI) ; `sae_lens`. **Cohérence modèle/couche** : tous les features d'un run proviennent d'un même modèle et, sauf indication contraire, d'une même couche ; en mode proxy (voir ci-dessous), la source de features est celle du modèle proxy, et les exemples Claude 3 Sonnet de la Section 3.4 restent purement illustratifs.

L'*agent de chargement* récupère pour chaque feature son index, ses 20 exemples à activation maximale avec leurs valeurs d'activation, son score d'interprétabilité existant, sa fréquence d'activation, sa couche et ses statistiques d'activation (dont le 99e percentile, pour la normalisation et la détection OOD). L'*agent de classement* constitue **trois splits d'évaluation disjoints** pour éviter le biais de sélection :

- **Easy set** (n=200) : features avec score d'interprétabilité ≥ 0,7, haute fréquence
- **Random set** (n=200) : features échantillonnés uniformément **dans le complément de easy ∪ hard** (disjonction garantie)
- **Hard set** (n=100) : features avec score d'interprétabilité < 0,5, ou context-dépendants, ou spécifiques à un domaine (code, mathématiques, entités nommées, multilingue)

Tous les seuils go/no-go principaux sont évalués sur le **random set**.

#### Phase 2 : Induction du lexique MorphoRepr

**Objectif** : identifier un ensemble minimal de morphèmes couvrant l'espace sémantique du corpus de features.

L'*agent de clustering* plonge les descriptions en langue naturelle à l'aide de nomic-embed-text et applique un clustering k-means (k ≈ 20) **à graine fixée** (de même que la réduction UMAP de visualisation), garantissant la reproductibilité de l'induction. L'*agent de labélisation* propose des morphèmes par cluster (voir Annexe B.1). L'*agent de cohérence* valide selon trois critères : non-redondance (similarité cosinus < 0,7), couverture et composabilité. Les échecs déclenchent une boucle de feedback (max 5 itérations).

**Gouvernance du lexique** : les racines libres sont enregistrées dans un lexique versionné avec définition formelle, énoncé de portée, cluster de features inducteur et horodatage de version. Une racine libre ne peut pas entrer en collision avec un token existant de préfixe, infixe ou suffixe.

**Métriques de productivité morphologique** (calculées en fin de Phase 2, mises à jour après la Phase 3) :

| Métrique | Définition |
|----------|-----------|
| Features par racine | Nombre moyen de features couverts par chaque racine |
| Taux de racines libres | Nouvelles racines libres introduites par 100 features encodés |
| Couverture lexique de base | Proportion d'annotations utilisant uniquement les racines de domaine prédéfinies |
| Couverture racines libres | Proportion d'annotations nécessitant au moins une racine libre |
| Entropie des morphèmes | Entropie de Shannon de la distribution d'utilisation des morphèmes |

Un taux élevé de racines libres ou une faible entropie des morphèmes indiquerait que MorphoRepr converge vers un dictionnaire compressé plutôt qu'un système réellement compositionnel. *Ces métriques reposent sur une décomposition morphémique correcte : le parseur de référence est testé sur l'intégralité des exemples du présent papier, y compris les cas à infixe et les racines `mal`/`ne`.*

#### Phase 3 : Encodage des features, fidélité et mesure de couverture

**Objectif** : encoder chaque feature et calculer des statistiques stratifiées de couverture, fidélité et cohérence sur deux runs d'annotation indépendants.

**Métriques de couverture** (par split) : taux de couverture brut (confiance de l'encodeur ≥ 0,6) ; taux UNCOVERED catégorisé par type de feature.

**Métrique de fidélité — tâche de discrimination** : pour chaque feature encodé `f`, nous constituons 20 exemples top-activating (ensemble positif) et 20 exemples contrôles appariés (ensemble négatif). Un *agent juge de fidélité* reçoit l'annotation MorphoRepr et classe quels exemples sont dans l'ensemble positif. La métrique de fidélité est l'**AUC-ROC** de cette tâche de discrimination (relevant du *detection scoring*, Section 2.2), qui transforme la fidélité en une tâche de prédiction testable plutôt qu'un jugement de plausibilité subjectif.

**Métriques de cohérence d'annotation** (au niveau morphémique, entre deux runs indépendants) :

| Métrique | Définition |
|----------|-----------|
| Taux d'exact match | Proportion de features recevant des expressions identiques dans les deux runs |
| Jaccard de racines | Similarité de Jaccard des ensembles de racines entre les deux runs |
| Jaccard de morphèmes | Similarité de Jaccard des ensembles de morphèmes complets |
| Corrélation des coefficients | Corrélation de Pearson des coefficients des termes correspondants |
| Distance d'édition morphémique | Nombre moyen de substitutions de morphèmes entre les deux annotations |

ROUGE-L est conservé comme métrique secondaire pour la comparaison aux baselines en langue naturelle uniquement.

**Comparaisons aux baselines** (exécutées en parallèle sur le même corpus) :

| Baseline | Description |
|----------|-------------|
| Étiquettes en langue naturelle | Générées par LLM, sans contrainte |
| Semantic Regexes | Implémentation officielle de Boggust et al. (2025) |
| Tags-mots-clés contrôlés | Syntagme nominal unique, sans composition |
| MorphoRepr mélangé | Voir ci-dessous |

**Baseline MorphoRepr mélangé** : des annotations MorphoRepr réelles d'autres features sont réassignées aléatoirement *à l'intérieur du même split* et à longueur d'expression comparable (±1 terme). Le mélange intra-split évite la contamination croisée entre les features easy et hard ; l'appariement de longueur évite une divergence triviale détectable. Cela teste si la forme morphologique seule porte du pouvoir prédictif, indépendamment du sens.

#### Phase 4 : Validation causale par steering d'activation

**Objectif** : vérifier que les expressions MorphoRepr sont prédictives causalement du comportement du modèle sous intervention sur les features.

**Modèle de validation (proxy par défaut).** L'accès expérimental complet aux activations de Claude 3 Sonnet (steering contrôlé avec génération avant/après) n'est pas garanti par les interfaces publiques. La validation causale principale s'exécute donc sur un **modèle proxy open-weight disposant de SAEs publics** (p. ex. GPT-2, Pythia ou Mistral via `sae_lens`). Dans ce cas : (a) toutes les conclusions causales sont limitées au modèle proxy ; (b) le pipeline entier (Phases 1–5) opère sur les SAEs du proxy ; (c) cela est déclaré explicitement en section Méthodes du papier expérimental. Si un accès direct aux activations d'un modèle de production est obtenu, le même protocole s'y applique.

**Protocole de steering** : pour chaque feature encodé, l'*agent de steering* amplifie le latent SAE cible **à sa propre couche** (colonne `layer` du feature) sur 20 phrases-sondes neutres et enregistre le déplacement de sortie. La **magnitude primaire est normalisée par feature** (un multiple du 99e percentile d'activation du feature), ce qui rend les interventions comparables entre features et couches ; la magnitude historique fixe de +5 unités (Anthropic, 2024) est conservée comme condition secondaire. Une courbe dose-réponse (plusieurs multiples de `p99`) est exécutée sur un sous-échantillon ; sa monotonie sert de preuve d'effet causal réel. Un *agent de prédiction causale* génère une prédiction comportementale basée **uniquement sur l'expression MorphoRepr** — voir Annexe B.3. Un *agent juge* évalue si le déplacement observé correspond à la prédiction.

**Exclusion des sorties hors-distribution (OOD)** : une instance dont l'activation obtenue dépasse `p99 × seuil_OOD` est marquée OOD et **exclue de la métrique primaire** (rapportée séparément) : un steering qui pousse le modèle hors-distribution mesure du bruit, non le rôle causal du feature.

**Garde-fou méthodologique contre la circularité** : l'agent juge reçoit uniquement l'expression MorphoRepr et le déplacement de sortie observé, non la description en langue naturelle. La baseline MorphoRepr mélangé quantifie de plus la part du pouvoir prédictif attribuable à la forme morphologique seule, indépendamment de l'étape d'encodage.

**Comparaison équitable entre méthodes.** Le tête-à-tête de validité causale (MorphoRepr vs étiquettes NL vs Semantic Regexes) est calculé **sur le même ensemble de features** — l'intersection des features couverts par MorphoRepr (confiance ≥ 0,5) — afin d'éviter que MorphoRepr ne soit avantagé en n'étant évalué que sur ses features les plus clairs. Les baselines sont en outre rapportées sur le set complet pour transparence. **Symétrie des prédicteurs** : chaque baseline dispose d'un prompt de prédiction parallèle (prenant son annotation et prédisant les mêmes propriétés), ingénieré avec un soin égal et gelé avant le run, afin que la comparaison ne se joue pas sur la qualité différentielle des prompts.

**Classifieurs de propriétés de sortie — stratifiés par niveau de robustesse** :

Plutôt qu'un jugement binaire unique, le protocole mesure un ensemble de propriétés de sortie, stratifiées par fiabilité du classifieur :

*Propriétés robustes* (fiabilité élevée des classifieurs ; métriques primaires) :

| Propriété | Méthode de mesure |
|-----------|------------------|
| Présence de négation | Parseur syntaxique (lexique de négation soigneusement élagué ; sans préfixes ambigus) |
| Temps (passé/présent/futur) | Tagger POS |
| Présence de code | Classifieur au niveau des tokens |
| Modalité conditionnelle | Correspondance de motifs syntaxiques |

*Propriétés semi-robustes* (fiabilité modérée ; métriques secondaires) :

| Propriété | Méthode de mesure |
|-----------|------------------|
| Valence émotionnelle | Classifieur de sentiment à base de transformer (distribution complète des labels) |

*Propriétés fragiles* (fiabilité plus faible ; rapportées séparément avec mises en garde) :

| Propriété | Méthode de mesure | Limitations connues |
|-----------|------------------|---------------------|
| Présence d'agent | NER + analyse des dépendances | Erreurs de parseur sur les phrases complexes |
| Référence sociale | NER + coréférence | Bruit de résolution de coréférence |
| Référence spatiale | NER + parse syntaxique | Syntagmes prépositionnels ambigus |
| Structure itérative | Correspondance de motifs | Taux élevé de faux positifs |

Les résultats des propriétés fragiles sont rapportés séparément et interprétés avec des mises en garde explicites. Les conclusions de validité causale sont tirées principalement des propriétés robustes et semi-robustes. Toutes les sorties des classifieurs sont vérifiées sur un échantillon aléatoire de 50 features avant le run complet, avec rapport des matrices de confusion.

**Score de validité causale.** L'agent de prédiction causale prédit la direction de changement de chaque propriété ({increase, decrease, no_change}) ; le juge mesure la direction observée. Le **score primaire est le macro-F1 sur ces trois directions**, restreint aux propriétés robustes, **calculé par feature puis moyenné** sur le random set (l'accuracy par propriété est conservée comme métrique secondaire). Le macro-F1 traite explicitement la classe `no_change` et n'est pas biaisé par le déséquilibre des directions. Les cas où l'agent ne prédit aucune propriété, ou où le steering échoue, sont comptabilisés selon une règle pré-enregistrée (échec de prédiction = score nul pour la propriété concernée) ; les instances OOD sont exclues comme indiqué ci-dessus.

**Catégories de résultat de validité causale** : chaque feature est assigné à l'une des quatre catégories : *confirmé* (majorité des propriétés robustes prédites se déplacent comme attendu), *partiel* (certaines propriétés se déplacent), *nul* (aucun déplacement mesurable), *mixte/ambigu* (déplacements dans des directions inattendues).

**Contrôles supplémentaires d'intervention** (au-delà du contrôle d'annotation mélangé) :
- feature SAE aléatoire de **même couche** ;
- direction aléatoire de **même norme** ;
- feature à **fréquence d'activation comparable** ;
- **steering négatif** (−magnitude) lorsque c'est sémantiquement pertinent ;
- **prompt-only** : fournir l'étiquette dans le prompt sans steering ;
- baseline supervisée **DiffMean / ReFT** (cf. Section 2.5).

**Contrôles de validité supplémentaires** :
- Annotations MorphoRepr mélangées comme contrôle négatif (attendu : validité causale proche du hasard). *Pour rester comparable au traitement, un sous-ensemble des annotations mélangées est scoré via le même chemin predictor + juge que le traitement ; le reste via classifieurs pour borner le coût.*
- Validation causale exécutée séparément pour les splits easy / random / hard
- Deux runs de prédiction indépendants ; κ de Cohen sur les résultats catégoriels

**Critère go/no-go** : le critère de publication principal est l'**amélioration relative par rapport aux baselines**, évaluée par une comparaison **appariée** (les méthodes annotant les mêmes features) :

> MorphoRepr est considéré comme démontrant une utilité causale si, sur le random set et l'ensemble de features partagé, l'**intervalle de confiance bootstrap à 95 % de la différence appariée** de score de validité causale (MorphoRepr − baseline, par feature) **exclut 0** dans le sens positif, à la fois face aux étiquettes en langue naturelle et face aux Semantic Regexes.

Cette formulation appariée remplace le critère antérieur de « non-chevauchement des intervalles de confiance marginaux », qui était inutilement conservateur. Le plancher opérationnel de 0,50 (macro-F1) sur le random set est conservé comme seuil absolu minimal en dessous duquel le système n'a aucune utilité pratique indépendamment de la comparaison aux baselines.

**Méthodologie statistique.** Tous les intervalles de confiance sont bootstrap (10 000 rééchantillonnages, **stratifiés par split**, graine fixée). Les comparaisons principales (pré-déclarées : validité causale sur random set, propriétés robustes, vs NL et vs Semantic Regexes) sont corrigées par **Holm-Bonferroni** ; les analyses exploratoires (autres splits, propriétés fragiles, métriques secondaires) sont signalées comme telles et corrigées par **Benjamini-Hochberg**. Une analyse de puissance indicative est rapportée (avec ≈100 features appariés entrant en validation causale et un effet attendu de l'ordre de 0,05–0,10, la puissance de détection d'une différence MorphoRepr vs Semantic Regexes est limitée et explicitement quantifiée).

#### Phase 5 : Synthèse et publication

L'*agent de rapport* génère des statistiques stratifiées de couverture, fidélité, cohérence, validité causale (par niveau de robustesse des propriétés) et productivité sur tous les splits et baselines. L'*agent d'analyse des lacunes* classe les features UNCOVERED par type. L'*agent de rédaction* produit un résumé structuré des résultats pour inclusion dans le papier expérimental v1.0.

### 4.3 Audit humain

Pour borner la circularité introduite par l'utilisation de LLMs tout au long du pipeline, le papier expérimental v1.0 inclura un **audit humain** sur un sous-ensemble de 50 features tirés aléatoirement du random split. Pour chaque feature de ce sous-ensemble :

- Deux annotateurs humains indépendants (chercheurs NLP/ML) produisent des annotations MorphoRepr après une session de formation standardisée
- Les annotations humaines sont comparées aux annotations du pipeline sur le Jaccard de morphèmes, l'overlap de racines et la corrélation des coefficients
- Les désaccords sont arbitrés par un troisième annotateur
- Le taux d'accord entre annotations humaines et pipeline est rapporté comme métrique de calibration de la fiabilité du pipeline (et non comme un seuil dur, vu la taille limitée de l'échantillon)

L'audit humain ne remplace pas le pipeline automatisé pour le corpus complet, mais fournit un point de calibration de vérité terrain qui borne l'interprétation des résultats du pipeline.

### 4.4 Stack technique

```
Orchestration :          orchestrateur déterministe (état gelé/auditable) ;
                         Claude Code utilisé pour le développement/supervision uniquement
Agents LLM :             modèle de jugement sémantique ; modèle léger de scoring/mise en forme
Accès SAE :              sae_lens + API Neuronpedia (neuronpedia.org)
Modèle de validation :   modèle proxy open-weight par défaut (Section 4.2)
Embeddings :             nomic-embed-text (clustering des descriptions de features, graine fixée)
Clustering :             scikit-learn k-means + UMAP (visualisation), graines fixées
Stockage :               SQLite (corpus de features) + JSON (lexique versionné)
Classifieurs de sortie : spaCy (syntaxe/NER/dépendances),
                         classifieur de sentiment à base de transformer (valence),
                         classifieurs personnalisés pour code/modalité ; matrices de confusion rapportées
Évaluation :             SAE-Bench (EleutherAI) comme benchmark externe
Baselines :              étiquettes NL, Semantic Regexes (code officiel), tags-mots-clés,
                         MorphoRepr mélangé intra-split ; DiffMean/ReFT comme contrôles d'intervention
Points de sauvegarde :   snapshot complet de l'état du pipeline après chaque phase
Audit humain :           50 features, 2 annotateurs + arbitre
```

*Note de reproductibilité.* Le run est **gelé et auditable** plutôt que strictement déterministe : code, configuration, prompts, corpus et lexique sont figés et vérifiés par empreinte ; en revanche les sorties des appels LLM sont stochastiques (et le sont nécessairement pour les deux runs de cohérence). Toutes les sorties brutes des agents sont archivées, de sorte que le run est ré-analysable même s'il n'est pas régénérable à l'identique.

### 4.5 Critères de succès

| Métrique | Plancher minimal | Critère de publication |
|----------|-----------------|----------------------|
| Couverture brute — easy set (conf ≥ 0,6) | 65 % | 80 % |
| Couverture brute — random set (conf ≥ 0,6) | 45 % | 60 % |
| Couverture brute — hard set (conf ≥ 0,6) | 20 % | 35 % |
| AUC-ROC de fidélité — random set | 0,60 | 0,72 |
| Validité causale (macro-F1) — random set, props robustes (plancher) | 0,50 | 0,65 |
| Validité causale vs étiquettes NL, random set (ens. partagé) | — | Différence appariée > 0, IC à 95 % excluant 0 |
| Validité causale vs Semantic Regexes, random set (ens. partagé) | — | Différence appariée ≥ 0, IC à 95 % |
| Cohérence d'annotation — Jaccard de racines, random set | 0,60 | 0,75 |
| Cohérence d'annotation — exact match, random set | 0,30 | 0,50 |
| Audit humain — Jaccard de morphèmes pipeline vs humain | — | ≥ 0,60 |
| Taille finale du lexique | < 250 morphèmes | < 150 morphèmes |
| Taux de racines libres | — | < 5 par 100 features |
| Features UNCOVERED catégorisés | — | ≥ 80 % |

### 4.6 Étude utilisateur planifiée

L'affirmation que les annotations MorphoRepr sont plus lisibles par l'humain et moins cognitivement exigeantes que les alternatives nécessite une évaluation humaine. Nous planifions l'étude suivante, à rapporter conjointement aux résultats expérimentaux dans la v1.0 :

**Participants** : 20 chercheurs NLP/ML sans exposition préalable à MorphoRepr.

**Design** : intra-sujet, contrebalancé. Chaque participant annote 30 features SAE avec trois systèmes (MorphoRepr, Semantic Regexes, étiquettes en langue naturelle) dans un ordre aléatoire, après une courte session de formation.

**Mesures** : temps d'apprentissage (durée de complétion de la session de formation) ; temps d'interprétation (moyenne par feature) ; précision d'interprétation (correspondance avec des annotations gold d'experts **indépendants des concepteurs de MorphoRepr**) ; cohérence d'annotation (accord entre deux participants par feature) ; charge cognitive subjective (NASA-TLX) ; classement de préférence.

**Hypothèse** : les annotations MorphoRepr seront interprétées plus rapidement et avec une cohérence plus élevée que les Semantic Regexes, au prix d'une apprenabilité initiale plus faible. Cette hypothèse est empirique, non supposée.

### 4.7 Étude d'ablation planifiée

Pour isoler l'apport des composants distinctifs de MorphoRepr — en particulier l'agglutination et l'ordre, dont l'ancrage théorique est faible (Section 3.1) — nous planifions une ablation comparant, sur les métriques de cohérence et de validité causale : (a) MorphoRepr complet ; (b) sans coefficients ; (c) racines seules ; (d) morphèmes **sans ordre** (sac de morphèmes) ; (e) suffixes/infixes seuls ; (f) coefficients randomisés. La condition « sans ordre » est décisive : si elle n'entraîne pas de perte mesurable, l'agglutination ordonnée n'apporte rien au-delà d'un ensemble de primitives, et la valeur de MorphoRepr serait alors purement ergonomique (à trancher par l'étude utilisateur).

---

## 5. Agenda de recherche

*Cette section esquisse des directions de recherche à plus long terme, conditionnelles aux résultats expérimentaux de la Section 4. Elle ne constitue pas une contribution du présent papier.*

Si MorphoRepr s'avère causalement valide comme système d'annotation, deux extensions naturelles se dessinent.

**MorphoRepr-Edit.** Si les expressions MorphoRepr peuvent être validées comme prédictives causalement au niveau des features, elles pourraient éventuellement servir d'espace d'adressage structuré pour l'édition de modèles (de style ROME/MEMIT). C'est hautement spéculatif : MorphoRepr adresse des latents SAE, non des matrices de poids directement, et le mapping des latents vers des directions de poids éditables nécessite des travaux substantiels supplémentaires.

**MorphoRepr-Memory.** Une architecture mémorielle hybride inspirée de la théorie CLS pourrait combiner un magasin vectoriel externe (tampon épisodique, indexé par des embeddings MorphoRepr) avec une consolidation paramétrique sélective via LoRA, produisant une interface de récupération auditable par l'humain.

Ces directions sont proposées comme programme de recherche en trois papiers : le présent papier (cadre et protocole), un second papier (résultats expérimentaux) et un troisième papier (application édition ou mémoire).

---

## 6. Positionnement dans la littérature actuelle

| Approche | Compositionnalité | Lisibilité humaine | Cohérence | Validité causale |
|----------|------------------|-------------------|-----------|-----------------|
| Étiquettes en langue naturelle (Bills et al., 2023) | Aucune | Élevée | Faible | Non évaluée |
| Semantic Regexes (Boggust et al., 2025) | Logique | Modérée | Élevée | Non évaluée |
| LinguaLens (2025 ; cf. réf., auteurs à confirmer) | Aucune | Élevée | Modérée | Partielle |
| Explication agentique — SAGE (Han et al., 2025) | Aucune (langue libre) | Élevée | Modérée | Partielle |
| Autoencodeurs en langage naturel (Anthropic, 2026) | Aucune | Élevée | Modérée | Reconstruction |
| TCAV (Kim et al., 2018) | Aucune | Modérée | Modérée | Partielle |
| **MorphoRepr (proposé)** | **Agglutinante** | **Élevée (hypothèse)** | **À mesurer** | **Critère central** |
| Logique du premier ordre | Complète | Faible | Élevée | Élevée |

La question ouverte centrale distinguant MorphoRepr des Semantic Regexes est de savoir si la composition morphologique agglutinante produit un avantage mesurable en cohérence d'annotation et pouvoir prédictif causal. Le protocole d'évaluation de la Section 4 est conçu pour mesurer cela empiriquement.

---

## 7. Discussion

### 7.1 Ce que MorphoRepr peut et ne peut pas exprimer

MorphoRepr capture : les propriétés morpho-syntaxiques (temps, aspect, négation, agentivité, rôle syntaxique), le domaine sémantique large (connaissance, affect, action, espace, relation sociale, données) et la force d'activation (via les coefficients). Il ne capture pas : les features d'entités nommées très spécifiques, les features profondément pragmatiques (ironie, registre, connotation culturelle), les features définis par un contexte textuel spécifique, ou les relations inter-features.

La couverture estimée de 45 à 65 % sur le random set (en attente de validation empirique) signifie qu'une fraction substantielle des latents SAE se situe par conception hors de la portée expressive de MorphoRepr. Ce n'est pas un échec — cela quantifie la frontière entre contenu morpho-sémantique et contextuel-pragmatique dans l'espace de features LLM.

### 7.2 Pourquoi l'espéranto et non une autre langue agglutinante

Le choix d'une morphologie de type espéranto comme modèle structurel repose sur quatre propriétés : morphologie entièrement régulière (sans exceptions), inventaire fini d'affixes (~40 affixes à sens formellement définis), notation en alphabet latin, et apprenabilité humaine. Nous ne prétendons pas que la morphologie espéranto est intrinsèquement optimale ; l'affirmation scientifique porte sur la *composition agglutinante régulière* en général, dont l'espéranto n'est qu'une instanciation commode. Si le protocole d'évaluation ne montre aucun avantage mesurable sur les alternatives, un autre système de notation devrait être utilisé.

### 7.3 Gouvernance et versionnage du lexique

L'extensibilité de MorphoRepr via les racines libres crée une tension : un petit lexique fermé limite la couverture ; un lexique extensible sans contraintes risque de devenir un vocabulaire ad hoc compressé. La résolution est un **lexique gouverné et versionné** avec définitions enregistrées, énoncés de portée et horodatages de version. Les métriques de productivité morphologique (Section 4.2) opérationnalisent cette tension : un taux élevé de racines libres ou une faible entropie des morphèmes indiquerait une dérive de la compositionnalité vers un dictionnaire.

### 7.4 Menaces à la validité

**Menaces à la validité interne :**

- *Le protocole pourrait ne pas détecter l'apport distinctif de MorphoRepr.* Les propriétés robustes (négation, temps, code, modalité), sur lesquelles reposent les conclusions principales, sont morpho-syntaxiques ; les Semantic Regexes les encodent aussi, de sorte que les deux systèmes risquent d'y converger. Le contenu réellement distinctif de MorphoRepr (racines sémantiques de domaine, agglutination) se manifeste davantage sur les propriétés fragiles, dépondérées. Conséquence possible : conclure à l'absence d'avantage faute de mesurer là où il se situerait. L'étude d'ablation (Section 4.7) et l'effort de faire passer au moins une propriété sémantique en semi-robuste atténuent ce risque.
- *Circularité résiduelle de l'annotation* : l'encodeur et le juge de fidélité sont tous deux des LLMs. Même avec la description en langue naturelle retenue du juge causal, l'étape d'encodage a été informée par cette description. La baseline MorphoRepr mélangé quantifie la part du pouvoir prédictif attribuable à la forme morphologique seule ; l'audit humain (Section 4.3) fournit un point de calibration de vérité terrain.
- *Dépendance aux descriptions NL initiales* : si les descriptions NL utilisées pour le clustering sont de mauvaise qualité, le lexique induit le sera aussi. Atténué par l'utilisation de plusieurs sources de descriptions et la boucle de validation de cohérence.
- *Erreurs des classifieurs de propriétés de sortie* : les classifieurs automatiques ont des taux d'erreur non nuls, particulièrement pour les propriétés fragiles. Toutes les sorties sont vérifiées sur 50 features avant le run complet, avec matrices de confusion ; les lexiques de détection (négation) sont élagués des préfixes ambigus.
- *Calibration de la magnitude de steering* : une magnitude fixe peut ne pas être comparable entre features et couches. La magnitude primaire est normalisée par feature (multiple de `p99`) ; la distribution des magnitudes obtenues est rapportée et les instances OOD sont exclues de la métrique primaire.
- *Comparabilité du contrôle mélangé* : le contrôle négatif n'est strictement comparable au traitement que s'il est scoré par le même chemin ; un sous-ensemble des mélanges passe donc par le predictor + juge LLM pour calibrer la comparaison.

**Menaces à la validité externe :**

- *Dépendance au modèle de validation* : la validation causale principale s'exécute sur un modèle proxy open-weight ; ses conclusions ne se généralisent pas automatiquement à d'autres modèles, architectures SAE ou dictionnaires de features. La généralisation nécessite des études de réplication séparées. Les exemples Claude 3 Sonnet du papier sont illustratifs et ne constituent aucun résultat validé.
- *Variance et qualité des latents SAE* : les latents peuvent souffrir de fusion (feature hedging), d'absorption ou de splitting (Chanin et al., 2025), et certains features sont irréductiblement multidimensionnels (Engels et al., 2024), ce qui borne une notation fondée sur la composition additive de directions. Les résultats UNCOVERED dans le hard set peuvent refléter la qualité des latents plutôt que les limitations du système ; ils sont analysés séparément.
- *Une baseline forte et déjà validée* : les Semantic Regexes ont déjà démontré concision, cohérence et bénéfice en étude utilisateur par rapport au NL ; surpasser cette baseline, en particulier en validité causale (qu'elle n'a pas évaluée), est un objectif exigeant et c'est le bon cadre de comparaison.
- *Biais de la langue anglaise* : le protocole actuel annote des features de langue anglaise. Le système morphologique de MorphoRepr est agnostique à la langue en principe, mais son utilité pour des espaces de features multilingues ou à forte densité de code n'est pas testée.
- *Coût cognitif d'apprentissage de MorphoRepr* : si la notation nécessite un temps de formation significatif, son avantage pratique sur les étiquettes NL est réduit. L'étude utilisateur (Section 4.6) mesure cela directement.
- *Risque de croissance ad hoc du lexique* : si l'induction de racines libres est trop permissive, MorphoRepr perd sa propriété compositionnelle. Les métriques de productivité et les règles de gouvernance sont conçues pour détecter et contraindre cela.

---

## 8. Conclusion

Nous avons proposé MorphoRepr, un langage contrôlé à structure morphologique pour l'annotation des features SAE dans les LLMs, et décrit un pipeline agentique en cinq phases et un protocole d'évaluation complet pour évaluer sa couverture, sa fidélité, sa validité causale, sa productivité et sa cohérence d'annotation par rapport à plusieurs baselines — incluant un contrôle mélangé intra-split, des contrôles d'intervention, un audit humain et une étude d'ablation.

Ce papier est un article de positionnement et protocole d'évaluation ; il ne revendique pas de résultats expérimentaux. Le cas théorique en faveur de MorphoRepr repose sur trois observations convergentes : la compositionnalité documentée des espaces d'activation LLM (hypothèse de représentation linéaire), l'analogie structurelle entre la composition additive des termes et la composition additive des latents SAE, et l'insuffisance démontrée des étiquettes en langue naturelle pour les tâches d'interprétabilité systématique. Nous distinguons explicitement ce socle (qui concerne la combinaison additive) du mécanisme agglutinant intra-mot, distinctif mais sans contrepartie dans l'algèbre des activations, dont l'apport doit être démontré par ablation.

La question ouverte centrale n'est pas si MorphoRepr est meilleur que la langue naturelle — il est presque certainement meilleur en cohérence et moins bon en couverture. La question centrale est de savoir s'il est meilleur que les Semantic Regexes, et spécifiquement si la composition agglutinante apporte un avantage mesurable en pouvoir prédictif causal et cohérence d'annotation qui justifie le coût cognitif supplémentaire d'apprendre une nouvelle notation.

MorphoRepr n'est pas une solution pour lire les représentations internes des LLMs ; c'est une hypothèse testable pour l'annotation structurée des latents SAE, évaluée contre des baselines structurées déjà publiées et validées.

Le code du pipeline agentique, la spécification du lexique MorphoRepr, et tous les résultats expérimentaux seront mis à disposition à : `https://github.com/michaellaunay/morphorepr`.

---

## Références

Anthropic. (2024). *Extracting Interpretable Features from Claude 3 Sonnet*. Transformer Circuits Thread. https://transformer-circuits.pub/2024/scaling-monosemanticity/

Anthropic. (2026). *Natural Language Autoencoders*. https://www.anthropic.com/research/natural-language-autoencoders

Bills, S., Cammarata, N., Mossing, D., Tillman, H., Gao, L., Goh, G., Sutskever, I., Leike, J., Wu, J., & Saunders, W. (2023). *Language models can explain neurons in language models*. OpenAI Blog.

Boggust, A., Ren, D., Assogba, Y., Moritz, D., Satyanarayan, A., & Hohman, F. (2025). *Semantic Regexes: Auto-Interpreting LLM Features with a Structured Language*. arXiv:2510.06378. (Code : https://github.com/apple/ml-semantic-regex)

Bricken, T., Templeton, A., Batson, J., Chen, B., Jermyn, A., Conerly, T., Turner, N., Anil, C., Denison, C., Askell, A., Lasenby, R., Wu, Y., Kravec, S., Schiefer, N., Maxwell, T., Joseph, N., Hatfield-Dodds, Z., Tamkin, A., Nguyen, K., … Henighan, T. (2023). *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning*. Transformer Circuits Thread.

Chanin, D., Dulka, T., & Garriga-Alonso, A. (2025). *Feature Hedging: Correlated Features Break Narrow Sparse Autoencoders*. arXiv:2505.11756.

Cunningham, H., Ewart, A., Sherburn, L., Tuck, R., & Sharkey, L. (2023). *Sparse Autoencoders Find Highly Interpretable Features in Language Models*. arXiv:2309.08600.

Elhage, N., Hume, T., Olsson, C., Schiefer, N., Henighan, T., Kravec, S., Hatfield-Dodds, Z., Lasenby, R., Drain, D., Chen, C., Grosse, R., McCandlish, S., Kaplan, J., Amodei, D., Wattenberg, M., & Olah, C. (2022). *Toy Models of Superposition*. Transformer Circuits Thread.

Engels, J., Riggs, L., & Tegmark, M. (2024). *Not All Language Model Features Are Linear*. arXiv:2405.14860.

Gao, L., la Tour, T. D., Tillman, H., Goh, G., Troll, R., Radford, A., Sutskever, I., Leike, J., & Wu, J. (2024). *Scaling and evaluating sparse autoencoders*. arXiv:2406.04093.

Han, J., Xu, W., Jin, M., & Du, M. (2025). *SAGE: An Agentic Explainer Framework for Interpreting SAE Features in Language Models*. arXiv:2511.20820.

Jørgensen, M. G., & Hansen, L. K. (2026). *Steering LLMs? Actually, Sparse Autoencoders can outperform simple baselines*. arXiv:2605.31183.

Kim, B., Wattenberg, M., Gilmer, J., Cai, C., Wexler, J., Viegas, F., & Sayres, R. (2018). *Interpretability Beyond Classification Accuracy: Quantifying Interpretability of Machine Learning Models via Concept Activation Vectors (TCAV)*. ICML 2018.

Kuhn, T. (2014). *A Survey and Classification of Controlled Natural Languages*. Computational Linguistics, 40(1), 121–170.

Kumaran, D., Hassabis, D., & McClelland, J. L. (2016). *What learning systems do intelligent agents need? Complementary learning systems theory updated*. Trends in Cognitive Sciences, 20(7), 512–534.

[À confirmer — auteurs à vérifier] *LinguaLens: Towards Interpreting Linguistic Mechanisms of Large Language Models via Sparse Auto-Encoder* (2025). arXiv:2502.20344. *(Cette entrée remplace la référence « Huang et al., SAELing » de la v0.26 : le titre vérifié de arXiv:2502.20344 est « LinguaLens » ; la liste d'auteurs doit être confirmée auprès de la source avant soumission.)*

McClelland, J. L., McNaughton, B. L., & O'Reilly, R. C. (1995). *Why there are complementary learning systems in the hippocampus and neocortex: Insights from the successes and failures of connectionist models of learning and memory*. Psychological Review, 102(3), 419–457.

Meng, K., Bau, D., Andonian, A., & Belinkov, Y. (2022). *Locating and Editing Factual Associations in GPT*. NeurIPS 2022.

Meng, K., Sharma, A. S., Andonian, A., Belinkov, Y., & Bau, D. (2023). *Mass-Editing Memory in a Transformer*. ICLR 2023.

Mikolov, T., Chen, K., Corrado, G., & Dean, J. (2013). *Efficient Estimation of Word Representations in Vector Space*. arXiv:1301.3781.

Object Management Group. (2016). *Meta Object Facility (MOF) Core Specification, Version 2.5.1*. Document OMG formal/2016-11-01.

Park, K., Choe, Y. J., & Veitch, V. (2023). *The Linear Representation Hypothesis and the Geometry of Large Language Models*. arXiv:2311.03658.

Paulo, G., Mallen, A., Juang, C., & Belrose, N. (2024). *Automatically Interpreting Millions of Features in Large Language Models*. arXiv:2410.13928.

Turner, A., Thiergart, L., Udell, D., Leech, G., Mini, U., & MacDiarmid, M. (2023). *Activation Addition: Steering Language Models Without Optimization*. arXiv:2308.10248.

Wu, Z., Arora, A., Geiger, A., Wang, Z., Huang, J., Jurafsky, D., Manning, C. D., & Potts, C. (2025). *AxBench: Steering LLMs? Even Simple Baselines Outperform Sparse Autoencoders*. arXiv:2501.17148.

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
(* Forme canonique : deux décimales, coefficient ∈ [0,01 ; 1,00].             *)
(* Le parseur de référence normalise vers cette forme et accepte en entrée    *)
(* toute valeur réelle de [0,01 ; 1,00] ; voir Section 3.2 pour la sémantique *)
(* (confiance γ ou activation α) selon le contexte d'usage.                   *)
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

L'inventaire de la Section 3.3, cette grammaire et le parseur de référence listent un inventaire de morphèmes identique (préfixes, infixes incluant `-it-`, suffixes temporels incluant `-u`, racines prédéfinies incluant `mal`/`ne`).

### A.2 Règles de composition

1. Un mot doit contenir exactement une racine.
2. Les préfixes précèdent la racine ; les infixes suivent la racine et précèdent le suffixe ; le suffixe est final.
3. Les préfixes multiples sont autorisés et se composent de gauche à droite : `mal-ne-X` = « non-absent-X » ≠ `ne-mal-X` = « non-contraire-X ».
4. Les coefficients doivent être dans [0,01 ; 1,00] (forme canonique à deux décimales). Un coefficient de 0,00 indique un feature absent et ne doit pas apparaître dans les expressions.
5. Les termes d'une expression sont ordonnés par coefficient décroissant.
6. Les racines libres doivent être enregistrées dans le lexique versionné avant utilisation ; les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.
7. Une racine libre ne peut pas être identique à un token de préfixe (`mal`, `ne`, `pli`, `plej`, `duon`), d'infixe (`ad`, `int`, `it`, `ist`, `ant`, `at`, `ig`, `iĝ`) ou de suffixe (`o`, `a`, `e`, `i`, `as`, `is`, `os`, `us`, `u`).
8. **Désambiguïsation `mal`/`ne` (préfixe vs racine)** : `mal` et `ne` sont analysés comme *racines* lorsqu'aucune autre racine ne les suit avant le suffixe (`mal-o`, `ne-a`), et comme *préfixes* sinon (`mal-emo-a`, `ne-soc-a`, `mal-ne-o` = préfixe `mal` + racine `ne` + suffixe `-o`). Le parse retenu doit être explicitement déclaré par l'encodeur. (Note d'implémentation : un parseur strictement positionnel sans retour arrière ne suffit pas ; la segmentation doit se faire sur les tirets puis classer les segments — les préfixes en tête sans jamais consommer le dernier segment disponible, qui est la racine.)
9. Un mot se terminant par un suffixe temporel (`-as`, `-is`, `-os`, `-us`, `-u`) est verbal. Un mot se terminant par un suffixe syntaxique (`-o`, `-a`, `-e`, `-i`) est nominal, adjectival, adverbial ou infinitival respectivement. Ces deux familles de suffixes sont mutuellement exclusives au sein d'un même mot.

---

## Annexe B : Gabarits de prompts du pipeline agentique

*Tous les agents produisent une sortie JSON dont le schéma exact est spécifié dans le prompt correspondant, afin que le parseur et les requêtes en aval puissent l'exploiter sans ambiguïté.*

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
ad, int, it, ist, ant, at, ig, iĝ, o, a, e, i, as, is, os, us, u).

Respond ONLY with a JSON object, no prose, with this exact schema:
{
  "root": "<proposed root>",
  "root_type": "predefined" | "free",
  "definition": "<formal definition>",
  "scope": {"covers": "<...>", "excludes": "<...>"},
  "coverage_examples": ["<feature description>", ...],
  "estimated_features_covered": <integer>
}
```

### B.2 Prompt système de l'agent d'encodage

```
You are encoding SAE features into MorphoRepr expressions.

MorphoRepr is an agglutinative formal language where:
- Each term has the form: coefficient · morpheme-chain
- Coefficients are in [0.01, 1.00] (two decimal places), representing
  your CONFIDENCE in the morpheme assignment (annotation context, γ)
- Morpheme chains follow the grammar: (prefix)* root (infix)* suffix
- Suffix is either a syntactic suffix (-o, -a, -e, -i) or a tense
  suffix (-as, -is, -os, -us, -u), not both in the same word
- 'mal' and 'ne' are ROOTS when no other root follows before the
  suffix (mal-o, ne-a), and PREFIXES otherwise (mal-emo-a)
- Domain roots (sci, emo, ag, dir, soc, dat, tem, lok) and
  registered free roots are the only valid roots
- An expression contains 1-4 terms, ordered by descending coefficient

Respond ONLY with a JSON object, no prose, using EXACTLY this schema.

If you can encode the feature with confidence >= 0.50:
{
  "status": "encoded",
  "expression": "<full MorphoRepr expression string, e.g. 0.88·mal-o + 0.34·ne-a>",
  "terms": [
    {
      "coefficient": <float in [0.01,1.00]>,
      "morpheme_chain": "<e.g. mal-o>",
      "parse": {"prefixes": [...], "root": "<...>", "infixes": [...], "suffix": "<...>"},
      "rationale": "<why this morpheme captures this feature>",
      "not_covered": "<what this term does NOT cover for this feature>"
    }
  ]
}

If you CANNOT encode it with confidence >= 0.50:
{
  "status": "uncovered",
  "uncovered_reason": "<what semantic content cannot be expressed>",
  "missing_morpheme_category": "<which morpheme category is missing>",
  "could_a_free_root_help": true | false
}

Be precise about confidence. Overconfident encodings that fail
causal validation are more harmful than honest "uncovered" responses.
```

### B.3 Prompt système de l'agent de prédiction causale

```
You are predicting the effect of amplifying a SAE feature on LLM output.

Given a MorphoRepr expression for a feature, you must predict which
of the following output properties will measurably change when this
feature is amplified on neutral probe sentences.

ROBUST PROPERTIES (primary; report these first):
- negation_presence: change in negation markers
- past_tense: change in past-tense verb forms
- future_tense: change in future-tense verb forms
- conditional_modality: change in conditional constructions
- code_presence: change in code tokens or technical symbols

SEMI-ROBUST PROPERTIES (secondary):
- negative_valence: change in negative sentiment words
- positive_valence: change in positive sentiment words

FRAGILE PROPERTIES (report but flag as lower-confidence):
- agent_reference: change in explicit agent noun phrases
- social_reference: change in interpersonal or role references
- spatial_reference: change in spatial or directional terms
- iterative_structure: change in repetitive or list-like patterns

For each property, state:
  1. Predicted direction: INCREASE / DECREASE / NO_CHANGE
  2. Confidence: [0.0, 1.0]
  3. For fragile properties, add: FRAGILE

Base your prediction ONLY on the MorphoRepr expression provided.
Do not use the natural language description of the feature.

Format your response as a JSON object with property names as keys
and objects {"direction": "INCREASE"|"DECREASE"|"NO_CHANGE",
"confidence": float, "tier": "robust"|"semi-robust"|"fragile"}
as values.
```

*Note : pour chaque baseline (étiquette NL, Semantic Regex, tag-mot-clé), un prompt de prédiction parallèle reprend exactement le même format de sortie et le même ensemble de propriétés, en substituant l'expression MorphoRepr par l'annotation de la baseline. Ces prompts sont ingénierés avec un soin égal et gelés avant le run (Section 4.2).*

---

## Annexe C : Modifications par rapport à la version 0.26

Cette version intègre une relecture critique consolidée. Les changements principaux :

**Conceptuel — deux mécanismes de composition (Section 3.1, nouveau).** Un principe explicite distingue désormais la composition *additive* entre termes (analogue de la superposition linéaire, théoriquement ancrée) de la concaténation *agglutinante* intra-mot (distinctive mais sans contrepartie dans l'algèbre des activations SAE, présentée comme un pari ergonomique à valider par ablation).

**Coefficients — distinction confiance/activation explicite (Section 3.2, renommée).** Les coefficients sont désormais notés `γ` (confiance d'annotation, mode utilisé par le protocole) et `α` (activation normalisée, mode instance). La section précise que les exemples de la Section 3.4 sont des `γ`, et que la Phase 4 permettra de comparer les deux modes.

**Inventaire morphémique complété (Section 3.3).** Ajout de l'infixe `-it-` (participe passif passé) et du suffixe temporel `-u` (volitif), absents des tableaux de la v0.26 mais présents dans la grammaire. Ajout de `mal`/`ne` au tableau des racines de domaine avec une note sur leur double rôle préfixe/racine et la règle de désambiguïsation positionnelle.

**Portée d'une expression clarifiée (Section 3.4, nouvelle note).** Une expression annote soit un latent unique (termes = facettes), soit un petit cluster de latents ; en Phase 4 le contrat est « un latent steeré, coefficients de confiance sur ses facettes ».

**Section 3.5 (analogie IDM/MOF) réduite.** Ramenée à une note de deux phrases, explicitement optionnelle.

**Validité causale durcie (Section 4.2).** (a) validation principale sur **modèle proxy open-weight** par défaut, remontée depuis le protocole ; (b) comparaison tête-à-tête **sur un ensemble de features partagé** ; (c) **magnitude de steering normalisée par feature** (multiple de `p99`) en primaire ; (d) **exclusion des instances OOD** de la métrique primaire ; (e) **prédicteurs de baseline symétriques** et gelés ; (f) **contrôles d'intervention** ajoutés (feature aléatoire même couche, direction aléatoire même norme, fréquence comparable, steering négatif, prompt-only, DiffMean/ReFT) ; (g) steering ciblant la **couche propre** du feature ; (h) splits **disjoints** et clustering **à graine fixée**.

**Score causal et statistiques (Section 4.2, 4.5).** Score primaire = **macro-F1** sur {increase, decrease, no_change} (propriétés robustes), par feature puis moyenné, avec règle explicite pour les échecs de prédiction et le `no_change`. Critère go/no-go reformulé en **différence appariée** dont l'IC à 95 % exclut 0 (remplace le non-chevauchement d'IC marginaux). Bootstrap stratifié (10 000, graine fixée) ; correction des comparaisons multiples (Holm-Bonferroni primaire, Benjamini-Hochberg exploratoire) ; analyse de puissance indicative.

**Étude d'ablation (Section 4.7, nouvelle).** Ablation isolant l'apport de l'agglutination/ordre (condition « sac de morphèmes » décisive), répondant à la tension conceptuelle de la Section 3.1.

**Classifieurs (Section 4.2).** Lexique de négation élagué des préfixes ambigus ; classifieur de valence utilisant la distribution complète des labels ; matrices de confusion rapportées.

**Table claims-vs-evidence (Section 1.2, nouvelle).** Met en regard chaque affirmation, son statut et l'évidence prévue.

**Reproductibilité — terminologie (Section 4.4).** Le run est qualifié de **« gelé et auditable »** plutôt que « déterministe » : code/config/prompts/corpus/lexique figés et vérifiés par empreinte, mais sorties LLM stochastiques (nécessaire pour les deux runs de cohérence) et archivées.

**Littérature et baselines (Sections 1, 2.1, 2.2, 2.5, 6).** Ajout de la tradition des langages contrôlés (Kuhn, 2014) ; situation de la fidélité dans le *detection scoring* ; mise en avant des Semantic Regexes comme baseline forte au code public et déjà validée ; nuance sur les limitations des SAEs (feature hedging — Chanin et al., 2025 ; features multidimensionnels — Engels et al., 2024) ; nouvelle Section 2.5 (SAGE — Han et al., 2025 ; NLA — Anthropic, 2026 ; AxBench — Wu et al., 2025 ; réponse de Jørgensen & Hansen, 2026) ; Activation Addition (Turner et al., 2023) ; réduction de la mention CLS à son rôle prospectif.

**Citations (Références).** Correction de la référence à la LRH-géométrie : auteurs réels **Park, K., Choe, Y. J., & Veitch, V. (2023)** (la v0.26 indiquait une liste d'auteurs erronée). Réconciliation de l'entrée arXiv:2502.20344 sous son titre vérifié **« LinguaLens »**, avec liste d'auteurs signalée comme à confirmer. Ajout des références vérifiées listées ci-dessus.

**Annexes A et B.** Annexe A : note alignant la forme canonique des coefficients et le comportement du parseur, et règle 8 de désambiguïsation `mal`/`ne` avec note d'implémentation (segmentation sur tirets). Annexe B : schémas de sortie JSON explicites pour les prompts de labélisation et d'encodage (B.1, B.2), et note sur les prompts de prédiction symétriques des baselines.

**Phrase de conclusion.** Reformulée : MorphoRepr est évalué « contre des baselines structurées déjà publiées et validées ».

---

*Version 0.27 — Juin 2026*
*Michaël Launay — michaellaunay@logikascium.com*
*Logikascium EURL — https://www.logikascium.com*
*GitHub : https://github.com/michaellaunay/morphorepr*
