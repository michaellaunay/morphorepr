# MorphoRepr : un méta-langage à structure morphologique pour la projection lisible par l'humain des représentations internes des LLMs

**Title (English):** MorphoRepr: A Morphologically-Structured Meta-Language for Human-Readable Projection of LLM Internal Representations

**Michaël Launay**
Logikascium (EURL), Fretin, France
Enseignant vacataire, Université de Lille / ENSAM Lille / Polytech Lille
michaellaunay@logikascium.com

---

*Preprint — soumis à arXiv cs.CL / HAL*
*Version 0.23 — Juin 2026*

---

## Résumé

Aucune langue naturelle ne dispose d'un pouvoir expressif suffisant pour décrire fidèlement les représentations internes des grands modèles de langage (LLMs). Si les langues agglutinantes et logiquement régulières comme l'espéranto offrent des propriétés structurelles — compositionnalité, transparence morphologique, sémantique des suffixes non ambiguë — théoriquement mieux adaptées à cette tâche que les langues analytiques, même ces langues ne peuvent capturer qu'une infime fraction de l'information encodée dans les espaces d'activation de haute dimension. Cette limitation tient au fait que chaque vecteur d'activation ne représente pas un mot de manière isolée, mais encode ses interactions contextuelles avec les tokens environnants et le contexte discursif global — un type d'information relationnel, gradué et continu qu'aucune langue naturelle, et qu'aucun langage formel conçu pour éliminer l'ambiguïté, ne peut exprimer sans devenir soit trop approximatif, soit illisible par sa verbosité.

Nous proposons **MorphoRepr**, un méta-langage à structure morphologique inspiré de la grammaire agglutinante de l'espéranto, conçu comme une couche de projection lisible par l'humain au-dessus des features sparses et disentanglés produits par les autoencodeurs sparses (SAEs) entraînés sur les activations de LLMs. Chaque expression MorphoRepr associe un ou plusieurs features SAE à une chaîne compositionnelle de morphèmes dont la sémantique est formellement définie, pondérés par leurs coefficients d'activation. Cette approche établit une analogie structurelle avec la hiérarchie d'abstraction de l'ingénierie dirigée par les modèles (IDM) : tout comme le méta-métamodèle MOF définit une tour d'abstraction autodescriptive (M0–M3) où chaque niveau décrit le niveau inférieur, MorphoRepr opère comme une couche d'interprétabilité qui décrit les représentations au niveau des activations en termes de primitives compositionnelles lisibles par l'humain — sans prétendre à l'exhaustivité au niveau de la géométrie brute des vecteurs.

L'objectif n'est pas de décoder intégralement l'état interne d'un LLM, mais de fournir une approximation humainement lisible, suffisamment précise et cohérente pour permettre l'audit, le pilotage (*steering*) et l'analyse causale du comportement du modèle au niveau des features.

Dans ce papier, nous proposons un cadre formel pour cette approche et décrivons un pipeline d'IA agentique en cinq phases conçu pour en évaluer la faisabilité. Nous présentons un protocole d'évaluation pour mesurer les taux de couverture, les statistiques d'utilisation des morphèmes et les scores d'alignement causal, et discutons des catégories de features attendues à résister à l'encodage morphologique et des raisons de cette résistance. Les résultats expérimentaux seront rapportés dans une version ultérieure à l'issue de l'exécution du pipeline.

**Au-delà de l'interprétation : vers une consolidation mémorielle guidée par MorphoRepr dans les LLMs.** Si MorphoRepr s'avère viable en tant que couche de projection structurée au-dessus des features SAE, une extension naturelle se dessine : inverser le pipeline pour écrire de nouvelles connaissances directement dans les poids du modèle, plutôt que de se limiter à lire les espaces d'activation. Nous esquissons une trajectoire de recherche dans laquelle le contenu encodé en MorphoRepr — exprimé en espéranto et parsé en chaînes de morphèmes compositionnels — sert d'interface d'écriture sémantiquement adressée pour l'édition ciblée des poids du modèle. Cette direction s'appuierait sur les techniques d'édition de modèles existantes telles que ROME et MEMIT, qui démontrent que des associations factuelles peuvent être localisées dans des matrices de poids MLP spécifiques des couches du transformer et modifiées chirurgicalement sans dégradation globale. Nous proposons en outre une architecture mémorielle hybride inspirée de la théorie des systèmes d'apprentissage complémentaires (CLS) de la consolidation mémorielle biologique, dans laquelle un magasin vectoriel externe joue le rôle de tampon épisodique rapide et un mécanisme de consolidation transfère sélectivement les connaissances validées dans les poids du modèle via adaptation de rang faible (LoRA), reproduisant le rejeu hippocampo-néocortical observé durant le sommeil dans les systèmes biologiques.

**Mots-clés :** interprétabilité mécaniste, autoencodeurs sparses, morphologie agglutinante, espéranto, projection de features, édition de modèles, consolidation mémorielle, IA agentique

---

## Abstract (English)

No natural language provides sufficient expressive power to faithfully describe the internal representations of large language models (LLMs). We propose MorphoRepr, a morphologically-structured meta-language inspired by Esperanto's agglutinative grammar, designed as a human-readable projection layer over the sparse, disentangled features produced by Sparse Autoencoders (SAEs) trained on LLM activations. We present a five-phase agentic AI feasibility pipeline and sketch a future research trajectory toward MorphoRepr-guided model editing and biologically-inspired memory consolidation.

**Keywords:** mechanistic interpretability, sparse autoencoders, agglutinative morphology, Esperanto, feature projection, model editing, memory consolidation, agentic AI

---

## 1. Introduction

Les représentations internes des grands modèles de langage (LLMs) demeurent largement opaques à l'inspection humaine. Un transformer traitant la phrase *« Elle n'avait pas terminé la tâche »* n'encode pas ce sens comme un objet linguistique structuré, mais comme un vecteur d'activation de haute dimension — plus précisément, comme une superposition de milliers de directions faiblement actives dans un espace de 768 à 4096 dimensions, où chaque direction correspond à un feature latent sans corrélat humainement interprétable garanti.

Le domaine de l'interprétabilité mécaniste a accompli des progrès significatifs dans la décomposition de ces représentations. Les autoencodeurs sparses (SAEs) ont en particulier émergé comme un outil scalable pour démêler la superposition polysémantique des neurones de modèles en directions de features plus sparses et plus monosémantiques (Bricken et al., 2023 ; Cunningham et al., 2023 ; Templeton et al., 2024). Le problème de la *labélisation* de ces features — de leur assigner des descriptions humainement lisibles qui soient précises, cohérentes et compositionnellement structurées — reste cependant ouvert. Les approches actuelles s'appuient sur des étiquettes en langue naturelle générées par des LLMs, qui sont précises mais vagues, inconsistantes d'une exécution à l'autre, et peu adaptées au raisonnement formel sur les relations entre features (Boggust et al., 2025).

Ce papier propose une approche différente, motivée par une observation linguistique : les propriétés structurelles qui font de l'espéranto une langue naturelle exceptionnellement apprenante — sa morphologie agglutinante, son mapping bijectif suffixe-à-sens, sa formation des mots compositionnelle — sont précisément les propriétés que l'on souhaiterait dans un système de notation pour les features SAE. Un feature encodant « la négation d'une action passée par un agent humain » pourrait s'écrire `mal-far-int-a` plutôt qu'une phrase anglaise en forme libre, chaque morphème portant un sens formellement défini et borné.

Nous ne proposons pas d'utiliser l'espéranto lui-même comme langage de représentation — son lexique est trop petit, sa couverture des concepts computationnels abstraits trop limitée, et ses ambiguïtés de langue naturelle trop nombreuses. Nous proposons à la place **MorphoRepr**, un méta-langage formel qui emprunte à l'espéranto sa *logique structurelle* — ses règles de composition agglutinante, son inventaire fini de morphèmes, son système dérivationnel transparent — et l'étend avec un vocabulaire contrôlé de primitives dérivées empiriquement de l'espace de features SAE d'un LLM de production.

L'analogie structurelle que nous établissons avec l'ingénierie dirigée par les modèles (IDM) n'est pas purement décorative. En IDM, le Meta-Object Facility (MOF) définit une tour de niveaux d'abstraction (M0 : instances, M1 : modèles, M2 : métamodèles, M3 : le MOF lui-même) où chaque niveau décrit le niveau inférieur, et M3 est autodescriptif. MorphoRepr occupe une position analogue : c'est un langage qui décrit le langage des features LLM, lui-même défini en termes d'un ensemble fini de primitives formellement spécifiées. Cette structure autoréférentielle est précisément ce qui lui confère le potentiel de passer à l'échelle — le même inventaire de morphèmes qui décrit un feature aujourd'hui peut décrire un nouveau feature demain, sans nécessiter d'extension manuelle d'un vocabulaire en langue naturelle.

### 1.1 Contributions

Ce papier apporte les contributions suivantes :

1. **Conceptuelle** : nous formalisons la notion de méta-langage à structure morphologique pour l'annotation des features SAE, et établissons son ancrage théorique dans l'hypothèse de représentation linéaire et l'hypothèse de superposition.

2. **Méthodologique** : nous décrivons un pipeline d'IA agentique en cinq phases pour induire empiriquement un lexique MorphoRepr à partir de features SAE et spécifions un protocole d'évaluation pour la couverture et la validité causale.

3. **Prospective** : nous esquissons une trajectoire de recherche étendant MorphoRepr d'un outil d'interprétabilité en lecture seule à une interface d'édition de modèles en écriture, et, à terme, à une architecture de consolidation mémorielle d'inspiration biologique.

---

## 2. Contexte et travaux connexes

### 2.1 Autoencodeurs sparses et interprétabilité mécaniste

L'hypothèse de représentation linéaire (LRH) postule que les réseaux de neurones encodent des concepts interprétables comme des directions linéaires dans leurs espaces d'activation (Mikolov et al., 2013 ; Park et al., 2023). L'hypothèse de superposition (Elhage et al., 2022) propose en outre que les modèles compriment un grand nombre de tels features dans un nombre plus restreint de neurones en exploitant l'orthogonalité approximative, créant des neurones polysémantiques qui répondent à plusieurs concepts non liés.

Les autoencodeurs sparses répondent au problème de superposition en projetant les activations dans un espace de plus haute dimension tout en imposant la sparsité, ce qui fait que chaque entrée n'active qu'un petit nombre de features appris. Bricken et al. (2023) démontrent que les features SAE sont plus monosémantiques et plus interprétables que les neurones individuels, tel que mesuré par des scores d'interprétabilité automatisée. Templeton et al. (2024) font passer cette approche à l'échelle des modèles de production, trouvant des features correspondant à des entités nommées spécifiques, des constructions syntaxiques et des concepts sémantiques abstraits.

Le goulot d'étranglement actuel de l'interprétabilité basée sur les SAEs est la *labélisation* : l'assignation de descriptions humainement lisibles aux dizaines de milliers de features découverts par les grands SAEs. Les approches existantes utilisent des LLMs pour générer des descriptions en langue naturelle en inspectant des exemples à forte activation (Bills et al., 2023 ; Paulo et al., 2024). Ces descriptions sont précises mais exhibent les limitations bien connues de la langue naturelle comme notation formelle : imprécision, inconsistance entre exécutions, et impossibilité de raisonnement compositionnel.

### 2.2 Langages structurés pour l'annotation de features

Boggust et al. (2025) introduisent les *Semantic Regexes* (expressions régulières sémantiques), un langage structuré pour décrire automatiquement les features LLM en combinant des primitives pour les motifs de tokens exacts, les formes syntaxiques et les catégories sémantiques, avec des modificateurs pour la contextualisation, la composition et la quantification. Les Semantic Regexes correspondent à la précision des descriptions en langue naturelle tout en produisant des sorties plus concises et cohérentes. Ce travail constitue l'antécédent le plus proche de MorphoRepr dans la littérature actuelle.

La différence clé est structurelle : les Semantic Regexes sont un langage de correspondance de motifs dans la tradition des expressions régulières, où les primitives sont combinées par des opérateurs logiques (ET, OU, NON, contexte). MorphoRepr est un langage *agglutinant*, où les primitives sont combinées par concaténation selon des règles morphologiques, et l'expression résultante est un token lisible unique plutôt qu'une formule. Cette distinction importe pour l'utilisabilité humaine : `0.87·mal-far-int-e` est lisible et mémorisable d'une façon que `¬(ag:past & subject:human)` n'est pas.

### 2.3 Édition de modèles

ROME (Meng et al., 2022) et MEMIT (Meng et al., 2023) démontrent que les connaissances factuelles dans les LLMs transformers peuvent être localisées dans des matrices de poids MLP spécifiques et modifiées chirurgicalement. L'insight clé est que les couches MLP des transformers fonctionnent comme des mémoires associatives, avec des paires clé-valeur correspondant à des associations factuelles. ROME calcule une mise à jour de rang un d'une matrice de poids cible qui insère une nouvelle paire clé-valeur tout en perturbant minimalement les associations existantes.

La limitation persistante des approches actuelles d'édition de modèles est la *localisation* : déterminer quelles matrices de poids modifier pour une connaissance donnée requiert une procédure de traçage causal empirique coûteuse et imparfaite. MorphoRepr répond à ce problème en fournissant une carte sémantique rigoureuse des expressions morphologiques vers les indices de features SAE puis vers les directions de poids spécifiques à chaque couche, transformant potentiellement la localisation d'une recherche empirique en une consultation structurée.

### 2.4 Systèmes d'apprentissage complémentaires

La théorie des systèmes d'apprentissage complémentaires (CLS) (McClelland et al., 1995 ; Kumaran et al., 2016) propose que la mémoire biologique est organisée en deux systèmes complémentaires : l'hippocampe, qui encode les mémoires épisodiques rapidement et spécifiquement, et le néocortex, qui encode les connaissances sémantiques lentement et de façon distribuée. La consolidation mémorielle se produit lorsque l'hippocampe rejoue les épisodes récents vers le néocortex durant le sommeil, intégrant progressivement de nouvelles informations dans la mémoire sémantique à long terme.

L'analogie avec les architectures mémorielles des LLMs est directe : les systèmes RAG et les magasins vectoriels externes fonctionnent comme des tampons hippocampiques (rapides, spécifiques, épisodiques), tandis que les poids du modèle fonctionnent comme la mémoire à long terme néocorticale (lente, distribuée, sémantique). L'édition de modèles guidée par MorphoRepr fournirait le mécanisme de consolidation — le rejeu — qui relie ces deux systèmes.

---

## 3. Le système MorphoRepr

### 3.1 Principes de conception

MorphoRepr est conçu selon quatre principes qui le distinguent à la fois de l'annotation en langue naturelle et des systèmes de notation formels existants :

**Compositionnalité morphologique.** Toute expression MorphoRepr est une concaténation finie de morphèmes tirés d'un inventaire fixe. Le sens d'une expression est entièrement déterminé par les sens de ses morphèmes constitutifs et leur ordre de composition. Aucune expression ne requiert de référence externe pour être interprétée.

**Encodage d'activation pondéré.** Chaque morphème dans une expression est précédé d'un coefficient réel dans [0,0 ; 1,0] représentant la force d'activation normalisée du feature SAE correspondant. Une expression complète prend la forme :

```
α₁·m₁[-m₂[-m₃]] [+ α₂·m₄[-m₅] [+ ...]]
```

où les `mᵢ` sont des morphèmes, `-` dénote la concaténation agglutinante, `+` dénote la combinaison additive de features, et les `αᵢ` sont les coefficients d'activation. Par exemple :

```
0.87·mal-far-int-e  +  0.41·pens-ad-is
```

se lit : *« n'ayant pas (vraiment) agi (force 0,87) plus ayant continué à penser (force 0,41) »*.

**Sémantique formelle des morphèmes.** Chaque morphème de l'inventaire dispose d'une définition formellement spécifiée comprenant : (a) une dénotation en termes de primitive sémantique, (b) un énoncé de portée précisant ce que le morphème couvre et ce qu'il exclut, et (c) un ensemble de features SAE attestés que le morphème encode de façon fiable.

**Expressivité bornée.** MorphoRepr ne tente pas d'encoder toute l'information d'un vecteur d'activation. Il est explicitement conçu comme une *projection avec perte* qui capture le contenu morpho-syntaxique et largement sémantique des features SAE tout en reconnaissant que le contenu pragmatique, culturel et profondément contextuel se situe hors de sa portée. Le résidu — l'information non capturée par aucune expression MorphoRepr — est une sortie de première classe du système, non un mode d'échec.

### 3.2 L'inventaire des morphèmes

L'inventaire MorphoRepr est organisé en cinq catégories, chacune inspirée du système grammatical de l'espéranto mais étendue pour couvrir le terrain sémantique des features d'activation LLM. Conformément à la grammaire formalisée en Annexe A, **les morphèmes de domaine servent de racines** (le noyau sémantique d'un mot), tandis que les morphèmes de polarité servent de préfixes qui modifient ces racines. Les racines libres — induites par le pipeline agentique pour les concepts non couverts par le vocabulaire prédéfini — sont également autorisées et dénotées par des séquences de lettres minuscules de 2 à 5 caractères (ex. : `far`, `pens`, `ver`) ; voir note 1.

**Morphèmes temporels** (suffixes encodant le temps et l'aspect verbal) :

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

**Racines de domaine** (racines sémantiques prédéfinies ; ce sont les racines de la production `root` dans la grammaire) :

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

**Suffixes de rôle syntaxique** (l'élément final de chaque mot) :

| Morphème | Sens | Analogue espéranto |
|----------|------|-------------------|
| `-o` | nom (entité, concept) | suffixe nominal `-o` |
| `-a` | adjectif (propriété, attribut) | suffixe adjectival `-a` |
| `-e` | adverbe (manière, degré) | suffixe adverbial `-e` |
| `-i` | infinitif (action abstraite) | suffixe infinitif `-i` |

---

*Note 1 : Les racines libres telles que `far` (faire/agir) et `pens` (penser) ne font pas partie du vocabulaire prédéfini mais sont des racines MorphoRepr valides car elles satisfont la production `root ::= [a-z]{2,5}` de la grammaire. Elles sont induites par le pipeline agentique (Phase 2) lorsqu'aucune racine de domaine prédéfinie ne couvre un cluster de features. Les racines libres héritent de toutes les règles de composition et doivent être enregistrées dans le lexique versionné.*

---

### 3.3 Exemples d'encodage

Les exemples suivants illustrent des encodages MorphoRepr pour des features SAE tirés de l'interface publique Neuronpedia pour Claude 3 Sonnet. Chaque encodage est parsé contre la grammaire de l'Annexe A pour vérifier la validité structurelle.

**Feature #892** (description en langue naturelle : *« tokens dans des contextes au passé, en particulier des actions accomplies »*) :
```
0.91·ag-is
```
Parse : `ag` (racine de domaine) + `-is` (suffixe). Lecture : *« action physique accomplie (passé) »*, force 0,91.

**Feature #1204** (description : *« marqueurs de négation et éléments à polarité négative »*) :
```
0.88·mal-o  +  0.34·ne-a
```
Parse, terme 1 : `mal-` (préfixe de polarité) + racine implicite `∅` → ici `mal` fonctionne comme racine¹ + `-o` (suffixe). Parse, terme 2 : `ne-` + `-a`. Lecture : *« la négation comme entité (0,88) plus l'absence comme propriété (0,34) »*.

> ¹ *Note sur `mal-o` et `ne-a`* : dans ces deux cas, les morphèmes de polarité `mal` et `ne` fonctionnent directement comme racines (construction permise en espéranto : `malo` = « le contraire », `neo` = « le non »). C'est le seul cas où un morphème de polarité double en tant que racine ; la grammaire le permet sous la production `root ::= [a-z]{2,5}` lorsqu'aucune racine de domaine n'est applicable.

**Feature #3871** (description : *« agents humains accomplissant des actions intentionnelles, en particulier dans des contextes narratifs »*) :
```
0.79·soc-ant-o  +  0.45·ag-int-a
```
Parse, terme 1 : `soc` (racine de domaine) + `-ant-` (infixe participial) + `-o` (suffixe). Parse, terme 2 : `ag` (racine de domaine) + `-int-` (infixe participial) + `-a` (suffixe). Lecture : *« acteur social en train d'agir (0,79) plus entité ayant agi physiquement (0,45) »*.

**Feature #4102** (description : *« code Python impliquant des boucles for et des motifs d'itération »*) :
```
0.94·dat-ad-o
```
Parse : `dat` (racine de domaine) + `-ad-` (infixe participial, itératif) + `-o` (suffixe). Lecture : *« processus itératif de données/code »*, force 0,94.

**Feature #7823** (description : *« tokens apparaissant dans des contextes émotionnellement négatifs, en particulier le deuil et la perte »*) :
```
0.86·mal-emo-a  +  0.51·pens-is
```
Parse, terme 1 : `mal-` (préfixe de polarité) + `emo` (racine de domaine) + `-a` (suffixe). Parse, terme 2 : `pens` (racine libre, induite) + `-is` (suffixe). Lecture : *« propriété affective négative (0,86) plus état cognitif passé (0,51) »*.

### 3.4 Relation avec la hiérarchie d'abstraction de l'IDM

L'ingénierie dirigée par les modèles organise les artefacts de modélisation en quatre niveaux d'abstraction :

- **M0** : Instances du monde réel (un processus en cours d'exécution spécifique)
- **M1** : Modèles décrivant les instances (un diagramme d'objets UML)
- **M2** : Métamodèles décrivant la structure des modèles (le métamodèle UML)
- **M3** : Le MOF, le méta-métamodèle autodescriptif

MorphoRepr occupe une position analogue à M2 dans cette hiérarchie, appliquée au domaine des représentations LLM :

- **M0** : Un token spécifique dans un contexte spécifique, avec son vecteur d'activation
- **M1** : Un feature SAE — une direction dans l'espace d'activation avec une description en langue naturelle
- **M2** : Une expression MorphoRepr — un encodage compositionnel formel d'un ou plusieurs features SAE
- **M3** : L'inventaire de morphèmes MorphoRepr — l'ensemble autodescriptif de primitives qui définit toutes les expressions valides

La propriété cruciale de M3 en IDM est l'autoréférence : le MOF peut se décrire lui-même en utilisant ses propres construits. MorphoRepr approche cette propriété : ses morphèmes peuvent, en principe, décrire d'autres morphèmes. `sci-o` (entité-connaissance) peut décrire le morphème `sci` lui-même ; `ag-i` (agir en tant qu'agent) peut décrire le rôle des morphèmes agentifs. Cette capacité autoréférentielle n'est pas une simple curiosité formelle — c'est ce qui permet à MorphoRepr de passer à l'échelle vers de nouveaux types de features sans nécessiter de mécanismes d'extension externes.

---

## 4. Étude de faisabilité agentique

### 4.1 Motivation pour une approche agentique

L'induction d'un lexique MorphoRepr à partir de features SAE est une tâche simultanément trop répétitive pour une exécution manuelle et trop sémantiquement nuancée pour un algorithme déterministe. Encoder 500 features requiert une application cohérente de règles formelles (accessible à l'automatisation) combinée à un jugement sémantique sur quels morphèmes capturent le mieux le sens de chaque feature (nécessitant un raisonnement au niveau LLM). Cette combinaison est précisément la niche opérationnelle des systèmes d'IA agentique.

Trois propriétés structurelles rendent cette tâche particulièrement adaptée à un pipeline agentique :

**Critères de convergence mesurables.** Le taux de couverture — la fraction de features recevant un encodage MorphoRepr avec confiance ≥ 0,6 — est un nombre réel que le pipeline peut calculer de façon autonome et utiliser pour décider d'itérer, d'étendre le lexique, ou de terminer.

**Structure de raffinement itératif.** Le processus d'induction du lexique est naturellement itératif : les morphèmes initiaux échoueront à couvrir certains features, ce qui révèle des lacunes motivant de nouveaux morphèmes, qui à leur tour permettent de nouveaux encodages. Cette boucle de feedback est facilement automatisable.

**Séparation des préoccupations entre agents.** Les différentes phases du pipeline requièrent des capacités qualitativement différentes : récupération et classement (Phase 1), clustering et abstraction (Phase 2), encodage formel (Phase 3), raisonnement causal (Phase 4), et synthèse (Phase 5). Assigner ces tâches à des agents spécialisés permet d'optimiser chacun indépendamment.

### 4.2 Architecture du pipeline

Le pipeline se compose de cinq phases, chacune implémentée comme un ensemble d'agents LLM spécialisés orchestrés par un contrôleur à état. Les gabarits de prompts complets pour chaque agent sont fournis en Annexe B.

#### Phase 1 : Extraction des features SAE

**Objectif** : Constituer un corpus de 500 features SAE annotés avec des exemples d'activation.

**Sources de données** :
- SAEs publics pour Claude 3 Sonnet, accessibles via l'API Neuronpedia (neuronpedia.org), avec 16k à 1M features selon la couche cible
- SAE-Bench (EleutherAI), un benchmark standardisé avec des features étiquetés
- `sae_lens`, une bibliothèque Python open source fournissant un accès unifié aux SAEs de plusieurs modèles

L'*agent de chargement* interroge l'API Neuronpedia pour chaque couche cible, récupérant pour chaque feature son index, ses 20 exemples à activation maximale (avec leurs scores d'activation), son score d'interprétabilité existant issu du pipeline d'autointerpétabilité d'Anthropic, et sa fréquence d'activation sur un corpus de référence. L'*agent de classement* filtre les 500 features les mieux classés selon un score composite pondérant la fréquence (50 %) et le score d'interprétabilité existant (50 %). Les features avec un score d'interprétabilité inférieur à 0,7 sont exclus. Les résultats sont stockés dans un *magasin de features* (base de données SQLite) supportant les phases d'encodage et d'évaluation.

#### Phase 2 : Induction du lexique MorphoRepr

**Objectif** : Identifier, par analyse empirique du corpus de features, un ensemble minimal de morphèmes couvrant l'espace sémantique des 500 features les mieux classés.

L'*agent de clustering* plonge les descriptions en langue naturelle des 500 features à l'aide de nomic-embed-text et applique un clustering k-means avec k ≈ 20, chaque cluster représentant une famille de morphèmes candidate. L'*agent de labélisation* reçoit chaque cluster et propose un morphème — soit de la liste des racines de domaine prédéfinies, soit comme nouvelle racine libre — accompagné d'une définition formelle, d'un énoncé de portée et d'exemples de couverture (voir Annexe B.1 pour le prompt complet). L'*agent de cohérence* valide le lexique proposé selon trois critères : non-redondance (similarité cosinus entre représentations de morphèmes < 0,7), couverture (chaque feature peut recevoir au moins un morphème), et composabilité (les morphèmes se concaténent sans ambiguïté selon la grammaire de l'Annexe A). Les échecs déclenchent une boucle de feedback vers l'agent de labélisation, pour un maximum de 5 itérations.

#### Phase 3 : Encodage des features et mesure de couverture

**Objectif** : Encoder chacun des 500 features comme une expression MorphoRepr et calculer les statistiques de couverture.

L'*agent d'encodage* traite chaque feature individuellement, produisant une expression MorphoRepr pondérée ou une réponse `UNCOVERED` avec justification (voir Annexe B.2 pour le prompt complet). L'*agent d'évaluation* calcule trois métriques agrégées : (a) **taux de couverture brut** — pourcentage de features avec confiance de l'encodeur ≥ 0,6 ; (b) **score de fidélité** — un second LLM juge évalue si l'expression MorphoRepr prédit correctement les exemples à forte activation, selon le scoring par simulation de Paulo et al. (2024) ; (c) **taux UNCOVERED** — pourcentage de features que l'encodeur ne peut pas exprimer avec une confiance ≥ 0,5, analysé par type de feature. L'*agent de repli* regroupe les features UNCOVERED, propose de nouveaux morphèmes candidats et les resoumet à la boucle de validation de la Phase 2.

#### Phase 4 : Validation causale par steering d'activation

**Objectif** : Vérifier que les morphèmes MorphoRepr sont des prédicteurs causalement valides du comportement du modèle sous intervention sur les features, et non de simples étiquettes descriptives.

Pour chaque feature encodé, l'*agent de steering* amplifie le feature SAE cible de +5 unités d'activation (magnitude de steering standard d'après Templeton et al., 2024) sur 20 phrases-sondes neutres, enregistre le déplacement de sortie, et génère une prédiction causale basée uniquement sur l'expression MorphoRepr (voir Annexe B.3). Un *LLM juge* évalue si le déplacement observé correspond à la prédiction. L'*agent causal* calcule un score d'alignement causal par morphème et un score de validité causale agrégé sur tous les morphèmes.

**Seuil de décision go/no-go** : un score de validité causale agrégé dépassant 0,65 (65 %) constitue la validation de MorphoRepr comme système à pouvoir prédictif causal.

#### Phase 5 : Synthèse et publication

L'*agent de rapport* génère des statistiques de couverture structurées, des distributions de scores de fidélité, et des scores de validité causale par morphème. L'*agent d'analyse des lacunes* classe les features UNCOVERED en catégories (features d'entités nommées très spécifiques, features pragmatiques contextuels, features de domaines techniques spécifiques) et quantifie la fraction de l'espace de features se situant par conception hors de la portée expressive de MorphoRepr. L'*agent de rédaction* produit un résumé structuré des résultats approprié pour inclusion dans la section résultats d'une soumission à une conférence.

### 4.3 Stack technique

```
Orchestration :  Claude Code (boucle agentique) ou LangGraph
Agents LLM :     Claude Sonnet (tâches de jugement sémantique)
                 Claude Haiku (tâches répétitives de scoring et mise en forme)
Accès SAE :      sae_lens + API Neuronpedia (neuronpedia.org)
Embeddings :     nomic-embed-text (clustering des descriptions de features)
Clustering :     scikit-learn k-means + UMAP (visualisation)
Stockage :       SQLite (corpus de features) + JSON (lexique versionné)
Évaluation :     SAE-Bench (EleutherAI) comme benchmark externe
Points de sauvegarde : snapshot complet de l'état du pipeline après chaque phase
```

### 4.4 Critères de succès

| Métrique | Seuil minimal | Seuil de publication |
|----------|--------------|---------------------|
| Couverture brute (confiance ≥ 0,6) | 55 % | 70 % |
| Validité causale | 50 % | 65 % |
| Taille finale du lexique | < 250 morphèmes | < 150 morphèmes |
| Features UNCOVERED analysés | — | ≥ 80 % catégorisés |

Une couverture brute inférieure à 40 % n'invalide pas la contribution. Elle constituerait au contraire un résultat négatif à valeur analytique : elle quantifierait précisément quelles propriétés des features SAE résistent à l'encodage morphologique, et pourquoi — une contribution à la théorie de la structure des features dans les LLMs.

---

## 5. Vers une consolidation mémorielle guidée par MorphoRepr

### 5.1 Inverser le pipeline : de la lecture à l'écriture

L'étude de faisabilité décrite en Section 4 traite MorphoRepr comme un système en *lecture seule* : il projette les états d'activation en expressions humainement lisibles sans modifier le modèle. Si cette projection s'avère valide, une prochaine étape naturelle consiste à inverser le pipeline — à utiliser les expressions MorphoRepr comme interface structurée pour *écrire* de nouvelles connaissances dans les poids du modèle.

Cette inversion se déroulerait comme suit :

1. Une connaissance est exprimée en espéranto, exploitant la structure agglutinante de l'espéranto pour produire une entrée morphologiquement parsée.
2. Le texte espéranto est automatiquement converti en expression MorphoRepr via le parseur morphologique développé dans l'étude de faisabilité.
3. L'expression MorphoRepr est mappée à un ensemble de features SAE cibles via le lexique.
4. Les features cibles sont localisés dans des matrices de poids spécifiques en utilisant les cartes causales établies en Phase 4.
5. Une mise à jour ciblée des poids (de style ROME/MEMIT) est appliquée pour encoder la nouvelle connaissance.

La contribution propre de MorphoRepr à ce pipeline serait à l'étape 4 : transformer la procédure de localisation coûteuse, empirique et au cas par cas de ROME en une consultation structurée dans un espace d'adressage sémantiquement typé.

### 5.2 L'architecture mémorielle hybride

Nous proposons une architecture mémorielle en deux étapes inspirée de la théorie des systèmes d'apprentissage complémentaires :

**Étape 1 : Tampon épisodique (analogue hippocampique).** Un magasin vectoriel externe — dans la tradition des systèmes de connaissances en graphe de Karpathy utilisant des outils tels qu'Obsidian — contient du contenu encodé en espéranto indexé par des embeddings MorphoRepr. Ce magasin fonctionne comme une mémoire épisodique rapide et à haute capacité : de nouvelles informations peuvent y être ajoutées instantanément, récupérées par similarité sémantique, et mises à jour sans risque d'interférence avec d'autres mémoires stockées. L'utilisation d'embeddings MorphoRepr plutôt que d'embeddings LLM bruts comme mécanisme d'indexation fournit une récupération auditable par l'humain : une requête en syntaxe MorphoRepr peut être interprétée par un opérateur humain.

**Étape 2 : Consolidation paramétrique (analogue néocorticale).** Un mécanisme de consolidation transfère sélectivement les connaissances fréquemment accédées ou causalement importantes du tampon épisodique vers les poids du modèle via adaptation de rang faible (LoRA). Le critère de consolidation est double : fréquence (connaissance accédée plus d'un nombre seuil de fois) et validation causale (connaissance dont l'encodage MorphoRepr a été confirmé comme prédictivement causal en Phase 4). Cela reflète la sélectivité de la consolidation hippocampo-néocorticale durant le sommeil, qui privilégie les mémoires émotionnellement saillantes et répétitivement activées.

La conception en deux étapes répond à la tension centrale de l'édition de modèles actuelle : la vitesse d'acquisition épisodique (accommodée par l'Étape 1) et les exigences de stabilité de la mémoire paramétrique (gérées par la consolidation sélective de l'Étape 2).

### 5.3 Problèmes ouverts et limitations

**Inscriptibilité compositionnelle.** La lecture depuis les espaces d'activation se réduit à une projection linéaire, bien comprise. Écrire de façon compositionnelle et sans interférence dans un système dynamique non linéaire n'est garanti par aucune théorie actuelle. Les matrices de poids d'un transformer ne sont pas une mémoire adressable ; une modification locale a des effets globaux difficiles à prédire. MorphoRepr ne résout pas ce problème ; il le recadre comme un problème de recherche structurée dans un espace d'adressage sémantiquement typé, ce qui constitue une condition nécessaire à toute solution rigoureuse.

**Oubli catastrophique.** Les approches actuelles d'édition séquentielle de modèles dégradent les performances du modèle après quelques milliers d'éditions. Ce n'est pas une limitation spécifique à MorphoRepr ; c'est une propriété fondamentale de l'architecture transformer actuelle. La contribution de MorphoRepr est de rendre le processus d'édition plus rigoureux, non de résoudre la limitation architecturale.

**Spécificité épisodique.** MorphoRepr opère au niveau des features sémantiques et morpho-syntaxiques. Les mémoires épisodiques — « j'ai parlé avec la personne X le jour Y du sujet Z » — requièrent un niveau de spécificité contextuelle que la morphologie espéranto ne peut pas capturer directement. L'Étape 1 (le tampon épisodique) peut stocker de telles mémoires comme des enregistrements structurés ; l'Étape 2 (la consolidation paramétrique) ne peut encoder que leur contenu sémantique, non leur spécificité épisodique.

Cette direction vers la consolidation mémorielle est proposée ici comme programme de recherche futur, conditionné par les résultats de faisabilité de la Section 4. Elle est incluse dans ce papier pour situer MorphoRepr dans le défi plus large de la construction de LLMs dotés d'une mémoire à long terme persistante, auditable par l'humain et structurée morphologiquement.

---

## 6. Positionnement dans la littérature actuelle

MorphoRepr occupe une position distinctive dans le paysage de l'interprétabilité, se différenciant des travaux connexes les plus proches comme suit :

| Approche | Compositionnalité | Lisibilité humaine | Couverture | Validité causale |
|----------|------------------|-------------------|------------|-----------------|
| Étiquettes en langue naturelle (Bills et al., 2023) | Aucune | Élevée | Élevée | Non évaluée |
| Semantic Regexes (Boggust et al., 2025) | Logique | Modérée | Élevée | Non évaluée |
| SAELing (Huang et al., 2025) | Aucune | Élevée | Modérée | Partielle |
| TCAV (Kim et al., 2018) | Aucune | Modérée | Faible | Partielle |
| **MorphoRepr (proposé)** | **Agglutinante** | **Élevée** | **À mesurer** | **Critère central** |
| Logique du premier ordre | Complète | Faible | Élevée | Élevée |

La contribution distinctive de MorphoRepr par rapport aux Semantic Regexes — le concurrent le plus direct — est le mécanisme de composition agglutinante. Là où les Semantic Regexes expriment le `feature #1204` comme `¬token("not") | field("negation")`, MorphoRepr l'exprime comme `0,88·mal-o + 0,34·ne-a`. La seconde forme est compacte, phonétiquement prononçable, et compositionnellement transparente de la même façon que le mot espéranto `malfeliĉa` (*malheureux*) est transparentement composé de `mal-` (contraire) + `feliĉ-` (heureux) + `-a` (suffixe adjectival). Cette transparence n'est pas simplement esthétique : elle permet aux opérateurs humains de *construire* de nouvelles descriptions de features de toutes pièces en composant des morphèmes, plutôt que de simplement *lire* des descriptions générées par un LLM.

---

## 7. Discussion

### 7.1 Ce que MorphoRepr peut et ne peut pas exprimer

MorphoRepr est explicitement conçu comme une projection avec perte. Il capture :
- Les propriétés morpho-syntaxiques (temps, aspect, négation, agentivité, rôle syntaxique)
- Le domaine sémantique large (connaissance, affect, action, espace, relation sociale, données)
- La force d'activation (via les coefficients)

Il ne capture pas :
- Les features d'entités nommées très spécifiques (« features à propos de la Tour Eiffel »)
- Les features profondément pragmatiques (ironie, registre, connotation culturelle)
- Les features dont le sens est défini par un contexte textuel spécifique plutôt que par une propriété sémantique
- Les relations inter-features (comment deux features interagissent causalement)

La couverture estimée de 55 à 70 % (en attente de validation empirique) signifie qu'environ 30 à 45 % des 500 features SAE les mieux classés se situent par conception hors de la portée expressive de MorphoRepr. Ce n'est pas un échec — c'est une quantification de la frontière entre le morpho-sémantique et le contextuel-pragmatique dans l'espace de features LLM, qui est en soi un résultat scientifiquement intéressant.

### 7.2 Pourquoi l'espéranto et non une autre langue agglutinante

Le turc, le finnois, le hongrois, le swahili et le japonais sont tous des langues agglutinantes ou polysynthétiques avec des systèmes morphologiques bien étudiés. L'espéranto est choisi pour quatre raisons spécifiques à cette application :

1. **Régularité conçue** : la morphologie de l'espéranto est entièrement régulière par construction, sans exception. Les langues agglutinantes naturelles ont des formes irrégulières, des morphèmes supplétifs et des alternances phonologiques qui compliqueraient la spécification formelle.

2. **Inventaire fini d'affixes** : l'espéranto possède environ 40 affixes aux sens formellement définis. Cet inventaire fini est précisément le type de vocabulaire contrôlé nécessaire pour l'ensemble de morphèmes de MorphoRepr.

3. **Notation en alphabet latin** : l'espéranto utilise un alphabet dérivé du latin, rendant les expressions MorphoRepr directement intégrables dans des formats de texte standard, du code et des schémas de données sans problèmes d'encodage.

4. **Apprenabilité humaine** : le système morphologique de l'espéranto peut être appris en quelques heures. Cela signifie que les expressions MorphoRepr seront interprétables, sans formation préalable, par tout chercheur familier d'une petite table de référence des morphèmes.

---

## 8. Conclusion

Nous avons proposé MorphoRepr, un méta-langage à structure morphologique pour l'annotation des features SAE dans les LLMs, et décrit un pipeline agentique en cinq phases pour conduire une étude de faisabilité de sa couverture et de sa validité causale. Ce papier présente le cadre formel et le protocole d'évaluation ; les résultats expérimentaux seront rapportés dans une version ultérieure à l'issue de l'exécution du pipeline.

Le cas théorique en faveur de MorphoRepr repose sur trois observations convergentes : la compositionnalité documentée des espaces d'activation LLM (l'hypothèse de représentation linéaire), l'analogie structurelle entre la morphologie agglutinante et la composition additive des features SAE, et l'insuffisance démontrée des étiquettes en langue naturelle pour les tâches d'interprétabilité formelle. Si ce cas théorique se traduit en un système pratiquement utile est une question empirique que le pipeline décrit en Section 4 est conçu pour répondre.

Au-delà de l'interprétabilité, l'architecture prospective de consolidation mémorielle esquissée en Section 5 suggère que MorphoRepr, si validé, pourrait servir d'interface rigoureuse entre la mémoire épisodique rapide des magasins vectoriels externes et la mémoire paramétrique lente des poids du transformer — une implémentation computationnelle de la théorie des systèmes d'apprentissage complémentaires à l'échelle des LLMs de production.

Le code du pipeline agentique, la spécification du lexique MorphoRepr, et tous les résultats expérimentaux seront mis à disposition à : `https://github.com/michaellaunay/morphorepr`.

---

## Références

Bills, S., Cammarata, N., Mossing, D., Tillman, H., Gao, L., Goh, G., Sutskever, I., Leike, J., Wu, J., & Saunders, W. (2023). *Language models can explain neurons in language models*. OpenAI Blog.

Boggust, A., Ren, D., Assogba, Y., Moritz, D., Satyanarayan, A., & Hohman, F. (2025). *Semantic Regexes: Auto-Interpreting LLM Features with a Structured Language*. arXiv:2510.06378.

Bricken, T., Templeton, A., Batson, J., Chen, B., Jermyn, A., Conerly, T., Turner, N., Anil, C., Denison, C., Askell, A., Lasenby, R., Wu, Y., Kravec, S., Schiefer, N., Maxwell, T., Joseph, N., Hatfield-Dodds, Z., Tamkin, A., Nguyen, K., … Henighan, T. (2023). *Towards Monosemanticity: Decomposing Language Models With Dictionary Learning*. Transformer Circuits Thread.

Cunningham, H., Ewart, A., Sherburn, L., Tuck, R., & Sharkey, L. (2023). *Sparse Autoencoders Find Highly Interpretable Features in Language Models*. arXiv:2309.08600.

Elhage, N., Hume, T., Olsson, C., Schiefer, N., Henighan, T., Kravec, S., Hatfield-Dodds, Z., Lasenby, R., Drain, D., Chen, C., Grosse, R., McCandlish, S., Kaplan, J., Amodei, D., Wattenberg, M., & Olah, C. (2022). *Toy Models of Superposition*. Transformer Circuits Thread.

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

Templeton, A., Conerly, T., Marcus, J., Lindsey, J., Bricken, T., Chen, B., Pearce, A., Citro, C., Ameisen, E., Jones, A., Cunningham, H., Turner, N., McDougall, C., MacDiarmid, M., Freeman, C. D., Sumers, T. R., Rees, E., Batson, J., Jermyn, A., … Henighan, T. (2024). *Scaling and evaluating sparse autoencoders*. Anthropic Research.

Zamenhof, L. L. (1887). *Unua Libro* [Langue internationale]. Varsovie.

---

## Annexe A : Spécification formelle de la grammaire MorphoRepr

### A.1 Grammaire formelle (BNF)

```
expression    ::= terme ('+' terme)*
terme         ::= coefficient '·' mot
coefficient   ::= [0-9]'.'[0-9][0-9]
mot           ::= (préfixe)* racine (infixe)* suffixe
préfixe       ::= 'mal-' | 'ne-' | 'pli-' | 'plej-' | 'duon-'
racine        ::= racine-prédéfinie | racine-libre
racine-prédéfinie ::= 'sci' | 'emo' | 'ag' | 'dir' | 'soc'
                    | 'dat' | 'tem' | 'lok' | 'mal' | 'ne'
racine-libre  ::= [a-z]{2,5}
                  (* racines induites par le pipeline, enregistrées dans le lexique *)
infixe        ::= '-ad-' | '-int-' | '-it-' | '-ist-' | '-ant-'
                | '-at-' | '-ig-' | '-iĝ-'
suffixe       ::= '-o' | '-a' | '-e' | '-i' | '-as' | '-is'
                | '-os' | '-us' | '-u'
```

### A.2 Règles de composition

1. Un mot doit contenir exactement une racine.
2. Les préfixes précèdent la racine ; les infixes suivent la racine ; le suffixe est final.
3. Les préfixes multiples sont autorisés et se composent de gauche à droite : `mal-ne-X` = « non-absent-X » ≠ `ne-mal-X` = « non-contraire-X ».
4. Les coefficients doivent être dans [0,01 ; 1,00] ; un coefficient de 0,00 indique un feature absent et ne doit pas apparaître dans les expressions.
5. Les termes d'une expression sont ordonnés par coefficient décroissant.
6. Les racines libres (`racine-libre`) doivent être enregistrées dans le lexique versionné avant utilisation ; les racines libres non enregistrées sont syntaxiquement valides mais sémantiquement indéfinies.

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
with the existing lexicon. In both cases, provide a formal definition,
scope statement, and coverage examples.
```

### B.2 Prompt système de l'agent d'encodage

```
You are encoding SAE features into MorphoRepr expressions.

MorphoRepr is an agglutinative formal language where:
- Each term has the form: coefficient · morpheme-chain
- Coefficients are in [0.01, 1.00] (two decimal places)
- Morpheme chains follow the grammar: (prefix)* root (infix)* suffix
- Domain roots (sci, emo, ag, dir, soc, dat, tem, lok) and
  registered free roots are the only valid roots
- An expression contains 1-4 terms, ordered by descending coefficient
- If you cannot encode a feature with confidence ≥ 0.50 using the
  available lexicon, respond UNCOVERED and explain what semantic
  content the lexicon cannot express.

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

*Version 0.23 — Juin 2026*
*Michaël Launay — michaellaunay@logikascium.com*
*Logikascium EURL — https://www.logikascium.com*
*GitHub : https://github.com/michaellaunay/morphorepr*
