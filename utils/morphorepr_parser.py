# utils/morphorepr_parser.py
"""
Parseur MorphoRepr.
Source unique de vérité pour TOUTES les métriques morphémiques.

Algorithme par SEGMENTATION sur '-' (corrige les bugs de la v4 : non-détection
des infixes, et échec sur mal-o / ne-a). Pour chaque mot :
  1. Retirer le coefficient (avant '·'), fait dans parse_expression().
  2. Découper le mot sur '-' en segments.
  3. Le dernier segment est le suffixe (doit être un token de suffixe connu).
  4. Lire les préfixes en tête, SANS jamais consommer le dernier segment
     disponible (qui devient la racine). => mal-o donne racine 'mal' ;
     mal-emo-a donne préfixe 'mal' + racine 'emo'.
  5. Le premier segment non-préfixe est la racine ; les segments restants
     sont les infixes.

Note : un parseur strictement positionnel par sous-chaînes (v4) échouait car,
après retrait du suffixe '-o', le corps 'soc-ant' ne contient plus le motif
'-ant-' (le tiret final est parti avec le suffixe). La segmentation évite cela.
"""
from dataclasses import dataclass, field
from typing import Optional
import re

PREFIXES  = ("mal-", "ne-", "pli-", "plej-", "duon-")
INFIXES   = ("-ad-", "-int-", "-it-", "-ist-", "-ant-", "-at-", "-ig-", "-iĝ-")
TENSE_SUFFIXES     = ("-as", "-is", "-os", "-us", "-u")
SYNTACTIC_SUFFIXES = ("-o", "-a", "-e", "-i")
ALL_SUFFIXES = TENSE_SUFFIXES + SYNTACTIC_SUFFIXES

PREDEFINED_ROOTS = frozenset(
    {"sci", "emo", "ag", "dir", "soc", "dat", "tem", "lok", "mal", "ne"}
)

# RESERVED_TOKENS : ne peuvent PAS être utilisés comme nouvelles racines libres induites.
# Note : "mal" et "ne" apparaissent dans PREDEFINED_ROOTS ET RESERVED_TOKENS.
# C'est intentionnel :
#   - "mal" et "ne" sont valides comme racines PRÉDÉFINIES (ex. "mal-o", "ne-a")
#   - Ils ne peuvent PAS être ré-enregistrés comme nouvelles racines LIBRES par le pipeline
RESERVED_TOKENS = frozenset({
    "mal", "ne", "pli", "plej", "duon",                 # tokens de préfixe
    "ad", "int", "it", "ist", "ant", "at", "ig", "iĝ",  # tokens d'infixe (iĝ inclus)
    "o", "a", "e", "i", "as", "is", "os", "us", "u"      # tokens de suffixe
})

# Jeux de tokens SANS tiret, utilisés par la segmentation (parse_word).
PREFIX_TOKENS      = frozenset(p.strip("-") for p in PREFIXES)
INFIX_TOKENS       = frozenset(ix.strip("-") for ix in INFIXES)
TENSE_SUFFIX_TOK   = frozenset(s.strip("-") for s in TENSE_SUFFIXES)
SYNT_SUFFIX_TOK    = frozenset(s.strip("-") for s in SYNTACTIC_SUFFIXES)
SUFFIX_TOKENS      = TENSE_SUFFIX_TOK | SYNT_SUFFIX_TOK


@dataclass
class ParsedTerm:
    coefficient: float
    coefficient_type: str = "confidence"   # "confidence" | "activation"
    prefixes: list[str] = field(default_factory=list)
    root: str = ""
    infixes: list[str] = field(default_factory=list)
    suffix: str = ""
    suffix_type: str = ""   # "tense" | "syntactic"
    raw_word: str = ""
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.parse_error is None and bool(self.root) and bool(self.suffix)

    @property
    def all_morphemes(self) -> set[str]:
        m = set(self.prefixes) | {self.root} | set(self.infixes)
        if self.suffix:
            m.add(self.suffix)
        return m


@dataclass
class ParsedExpression:
    terms: list[ParsedTerm] = field(default_factory=list)
    raw: str = ""
    parse_error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return (self.parse_error is None
                and bool(self.terms)
                and all(t.is_valid for t in self.terms))

    @property
    def roots(self) -> set[str]:
        return {t.root for t in self.terms if t.root}

    @property
    def all_morphemes(self) -> set[str]:
        result = set()
        for t in self.terms:
            result |= t.all_morphemes
        return result

    @property
    def coefficients(self) -> list[float]:
        return [t.coefficient for t in self.terms]


def parse_word(word: str, known_free_roots: Optional[set] = None) -> ParsedTerm:
    """Parse un seul mot MorphoRepr par SEGMENTATION sur '-'.

    `known_free_roots` (optionnel) : racines libres enregistrées. Une racine non
    prédéfinie et non enregistrée reste SYNTAXIQUEMENT valide (règle 6) ; parse_word
    ne l'invalide pas (l'éligibilité à l'enregistrement est vérifiée séparément par
    can_register_new_free_root)."""
    known_free_roots = known_free_roots or set()
    term = ParsedTerm(coefficient=0.0, coefficient_type="confidence", raw_word=word)

    segs = [s for s in word.strip().split("-") if s]
    if not segs:
        term.parse_error = f"Mot vide : {word}"
        return term

    # Étape 3 : suffixe = dernier segment
    if segs[-1] not in SUFFIX_TOKENS:
        term.parse_error = f"Aucun suffixe reconnu : {word}"
        return term
    term.suffix = "-" + segs[-1]
    term.suffix_type = "tense" if segs[-1] in TENSE_SUFFIX_TOK else "syntactic"

    body = segs[:-1]
    if not body:
        term.parse_error = f"Aucune racine extraite : {word}"
        return term

    # Étape 4 : préfixes en tête, SANS jamais consommer le dernier segment (la racine).
    # => mal-o : racine 'mal' ; mal-emo-a : préfixe 'mal' + racine 'emo' ; mal-ne-o :
    #    préfixe 'mal' + racine 'ne'.
    i = 0
    while i < len(body) - 1 and body[i] in PREFIX_TOKENS:
        term.prefixes.append(body[i])
        i += 1

    # Étape 5a : racine = premier segment non-préfixe restant
    root = body[i]
    i += 1
    if root in PREDEFINED_ROOTS:
        pass                                   # racine prédéfinie (inclut mal, ne)
    elif root in RESERVED_TOKENS:
        term.parse_error = f"Token réservé '{root}' utilisé comme racine : {word}"
        return term
    elif root in known_free_roots:
        pass                                   # racine libre enregistrée
    elif re.match(r'^[a-z]{2,5}$', root):
        pass                                   # racine libre bien formée (enreg. vérifié ailleurs)
    else:
        term.parse_error = f"Racine mal formée '{root}' : {word}"
        return term
    term.root = root

    # Étape 5b : segments restants = infixes
    for seg in body[i:]:
        if seg not in INFIX_TOKENS:
            term.parse_error = f"Segment inattendu '{seg}' (infixe inconnu/mal placé) : {word}"
            return term
        term.infixes.append(seg)

    return term


def parse_expression(expr: str,
                     coefficient_type: str = "confidence") -> ParsedExpression:
    """Parse une expression MorphoRepr complète."""
    result = ParsedExpression(raw=expr)
    if not expr or not expr.strip():
        result.parse_error = "Expression vide"
        return result

    term_strings = [t.strip() for t in expr.split("+") if t.strip()]
    if not term_strings:
        result.parse_error = "Aucun terme trouvé"
        return result

    for ts in term_strings:
        if "·" not in ts:
            result.parse_error = f"Terme sans séparateur '·' : {ts}"
            return result
        coeff_str, word = ts.split("·", 1)
        try:
            coeff = float(coeff_str.strip())
        except ValueError:
            result.parse_error = f"Coefficient invalide : {coeff_str}"
            return result
        if not (0.01 <= coeff <= 1.00):
            result.parse_error = f"Coefficient hors plage [0.01,1.00] : {coeff}"
            return result
        parsed_term = parse_word(word.strip())
        parsed_term.coefficient = coeff
        parsed_term.coefficient_type = coefficient_type
        result.terms.append(parsed_term)

    # Vérifier l'ordre décroissant des coefficients
    coeffs = [t.coefficient for t in result.terms]
    if coeffs != sorted(coeffs, reverse=True):
        result.parse_error = "Termes non ordonnés par coefficient décroissant"
        return result

    return result


def is_valid_root(root: str, known_free_roots: Optional[set] = None) -> bool:
    """Vrai si `root` est une racine VALIDE en l'état : racine prédéfinie, ou racine
    libre bien formée ([a-z]{2,5}) non réservée (enregistrée ou non). Sert au parsing."""
    known_free_roots = known_free_roots or set()
    if root in PREDEFINED_ROOTS:
        return True
    if root in RESERVED_TOKENS:
        return False
    if root in known_free_roots:
        return True
    return bool(re.match(r'^[a-z]{2,5}$', root))


def can_register_new_free_root(root: str,
                               known_free_roots: Optional[set] = None) -> Optional[str]:
    """Valide l'éligibilité d'une racine candidate à être ENREGISTRÉE comme NOUVELLE
    racine libre. Retourne None si éligible, un message d'erreur sinon.

    Distinct de is_valid_root : 'mal' et 'ne' sont des racines VALIDES (prédéfinies)
    mais ne peuvent PAS être ré-enregistrées comme nouvelles racines libres ; de même
    une racine déjà enregistrée ne peut pas l'être deux fois."""
    known_free_roots = known_free_roots or set()
    if root in PREDEFINED_ROOTS:
        return f"'{root}' est déjà une racine prédéfinie (pas de ré-enregistrement)"
    if root in RESERVED_TOKENS:
        return f"'{root}' est un token réservé (préfixe/infixe/suffixe)"
    if root in known_free_roots:
        return f"'{root}' est déjà enregistrée comme racine libre"
    if not re.match(r'^[a-z]{2,5}$', root):
        return f"'{root}' ne correspond pas à [a-z]{{2,5}}"
    return None
