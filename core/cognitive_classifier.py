"""
Cognitive Classifier for Consilium AI
Adaptive Council Intelligence (ACI) - Core Component
"""

import re
import hashlib
import time
from typing import Set, Dict, List, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict


class CognitiveDimension(Enum):
    PAST = auto()
    PRESENT = auto()
    FUTURE = auto()
    FACTUAL = auto()
    PROCEDURAL = auto()
    CREATIVE = auto()
    ETHICAL = auto()
    COMPLICATED = auto()
    COMPLEX = auto()
    CHAOTIC = auto()


@dataclass
class TaskProfile:
    dimensions: Set[CognitiveDimension] = field(default_factory=set)
    required_depth: int = 5
    emotional_load: float = 0.0
    urgency: float = 0.3
    ambiguity_score: float = 0.0
    domain_hints: Dict[str, float] = field(default_factory=dict)
    suggested_language: str = "pl"
    processing_time_ms: float = 0.0
    confidence_score: float = 0.0


class CognitiveClassifier:
    URGENCY_UK_HIGH = ["терміново","допоможіть","сьогодні","завтра","зараз","негайно","швидко","дедлайн","строк","горить","критично","штраф","прострочено","відключать","заблокують","виселять","паніка","біда","термін","терміновий"]
    URGENCY_UK_MEDIUM = ["тиждень","скоро","планую","найближчим часом","неділька"]
    EMOTIONAL_UK_ANXIETY = ["боюся","страшно","переживаю","тривожно","хвилююся","паніка","жах","не сплю","кошмар","стрес","тиск","занепокоєння","неспокій","страх","боязнь"]
    EMOTIONAL_UK_FRUSTRATION = ["заплутався","не розумію","складно","важко","не можу розібратися","безпорадність","нікак не виходить","в глухому куті","застряг","тупик","розгубленість","збентеження"]
    EMOTIONAL_UK_EXCITEMENT = ["хочу","мрія","ідея","можливість","шанс","цікаво","захопливо","натхнення","хобі","пристрасть","ентузіазм","захоплення","прагнення","бажання"]
    PROCEDURAL_UK = ["як","який порядок","покроково","покрокова інструкція","процес","процедура","алгоритм","спосіб","метод","чекліст","план дій","де отримати","куди звернутися","порядок дій","інструкція","кроки","етапи"]
    FACTUAL_UK = ["скільки","що таке","коли","де","хто","який","котрий","розмір","ставка","норма","правило","закон","вартість","ціна","термін","дата","кількість"]
    CREATIVE_UK = ["придумати","назва","ідея для","дизайн","логотип","назвати","бренд","концепція","креатив","створити","вигадати","розробити","згенерувати","помислити"]
    ETHICAL_UK = ["правильно","етично","морально","чи повинен я","совість","провина","відповідальність","зрада","чесність","справедливість","добре чи погано","чесно","порядно"]
    CHAOS_UK = ["кризис","катастрофа","аварія","злам","загроза","терміново і незрозуміло","паніка","не знаю що робити","все руйнується","допоможіть терміново","вибухова ситуація","колапс"]
    COMPLEX_UK = ["залежить від","неоднозначно","багато факторів","складна система","взаємопов'язано","непередбачувано","парадокс","дилема","протиріччя","компроміс","баланс","система"]
    COMPLICATED_UK = ["багато документів","декілька етапів","багато частин","складна процедура","багато кроків","бюрократія","паперова тяганина","інстанції","погодження"]
    PAST_UK = ["чому сталося","що було","аналіз","причина","корінь","історія","раніше","перед тим","звідки взялося","минуле","попередній досвід","уроки","чому так"]
    FUTURE_UK = ["буде","план","хочу","ціль","стратегія","роадмап","через рік","в майбутньому","до чого призведе","прогноз","перспектива","наміри","бажаний результат","куди рухатися"]
    DOMAIN_UK_PATTERNS = {
        "immigration": ["внж","карта побиту","побит","віза","резиденція","імміграція","міграція","постійне місце проживання","громадянство","паспорт","карта поляка","тимчасовий дозвіл"],
        "tax": ["податок","оптимізація","податкова","податкова знижка","пільга","відрахування","cost","koszt","księgowy","księgowość","podatki","ulga","pit","cit","vat","ryczałt","jdг","działalność gospodarcza","podatek dochodowy"],
        "business": ["бізнес","фірма","компанія","стартап","підприємець","działalność gospodarcza","spółka","self-employed","b2b","ceo","founder","venture","investment","фоп","тов","пп"],
        "employment": ["робота","praca","job","cv","резюме","hire","umowa","o pracę","zlecenie","dzieło","wakat","rekrutacja","etat","employment","contract","hiring","recruitment","position","вакансія","пошук роботи","зарплата","zarobki","wynagrodzenie"],
        "housing": ["квартира","mieszkanie","rent","житло","нерухомість","wynajem","kupno","sprzedaż","lokal","zakwaterowanie","apartment","flat","house","rental","lease","mortgage","оренда","купівля","продаж","іпотека","кредит на житло"],
        "legal": ["суд","sąd","court","legal","право","law","contract","umowa","prawnik","adwokat","radca","spór","pozew","lawsuit","attorney","lawyer","dispute","sue","claim","адвокат","юрист","консультація","справа","позов","судовий"],
        "health": ["лікар","lekarz","health","медичний","zdrowie","szpital","klinika","badanie","recepta","choroba","leczenie","doctor","hospital","clinic","prescription","treatment","лікарня","клініка","рецепт","хвороба","лікування","симптом"],
        "education": ["навчання","studia","education","університет","szkoła","kurs","dyplom","stopień","nauka","edukacja","uczelnia","study","degree","diploma","course","learning","academy","освіта","школа","курси","диплом","ступінь","навчальний заклад"]
    }

    URGENCY_HIGH = ["срочно","помогите","помоги","сегодня","завтра","сейчас","немедленно","быстро","дедлайн","срок","горит","критично","штраф","просроч","отключат","заблокируют","выселят","термин","срочняк","паника","беда","pilne","szybko","termin","dzisiaj","jutro","teraz","natychmiast","kary","opóźnienie","wyłączą","blokada","wyeksmitują","alarm","kryzys","urgent","asap","emergency","deadline","today","tomorrow","now","immediately","quickly","penalty","overdue","cut off","blocked","evicted","crisis","panic","help"]
    URGENCY_MEDIUM = ["неделя","скоро","планирую","в ближайшее время","tydzień","wkrótce","planuję","week","soon","planning"]
    EMOTIONAL_ANXIETY = ["боюсь","страшно","переживаю","тревожно","беспокоюсь","паника","ужас","не сплю","кошмар","стресс","давление","boję się","strach","stres","niepokój","panika","koszmar","scared","afraid","worried","anxious","stressed","panic","nightmare","can't sleep","pressure"]
    EMOTIONAL_FRUSTRATION = ["запутался","не понимаю","сложно","трудно","не могу разобраться","беспомощность","никак не получается","в тупике","застрял","zgubiłem się","nie rozumiem","trudno","bezradność","confused","lost","stuck","can't figure out","helpless","no idea","complicated","frustrated"]
    EMOTIONAL_EXCITEMENT = ["хочу","мечта","идея","возможность","шанс","интересно","увлекательно","вдохновение","хобби","страсть","chcę","marzenie","pomysł","szansa","pasja","inspiracja","want","dream","idea","opportunity","excited","passion","inspiration","interesting","chance"]
    PROCEDURAL_MARKERS = ["как","какой порядок","пошагово","пошаговая инструкция","процесс","процедура","алгоритм","способ","метод","чеклист","план действий","roadmap","где получить","jak","proces","procedura","krok po kroku","instrukcja","how to","steps","process","procedure","checklist","guide","tutorial","walkthrough","where to get"]
    FACTUAL_MARKERS = ["сколько","что такое","когда","где","кто","какой","который","размер","ставка","норма","правило","закон","ile","co to","kiedy","gdzie","kto","jaki","rozmiar","stawka","norma","prawo","reguła","how much","what is","when","where","who","which","size","rate","rule","law","norm","what are"]
    CREATIVE_MARKERS = ["придумать","название","идея для","дизайн","логотип","назвать","бренд","концепция","креатив","создать","wymyślić","nazwa","pomysł na","projekt","logo","marka","koncepcja","kreatywne","stworzyć","create","name for","design","logo","brand","concept","creative","idea for","brainstorm","invent"]
    ETHICAL_MARKERS = ["правильно","этично","морально","должен ли я","совесть","вина","ответственность","предательство","честность","słusznie","etycznie","moralnie","powinienem","sumienie","wina","odpowiedzialność","uczciwość","right thing","ethical","moral","should I","conscience","guilt","responsibility","honesty","betrayal","fair"]
    CHAOS_MARKERS = ["кризис","катастрофа","авария","взлом","угроза","срочно и непонятно","паника","не знаю что делать","всё рушится","помогите срочно","kryzys","katastrofa","wypadek","włamanie","zagrożenie","crisis","disaster","emergency","hacked","threat","everything collapsing","don't know what to do","urgent help"]
    COMPLEX_MARKERS = ["зависит от","неоднозначно","много факторов","сложная система","взаимосвязано","непредсказуемо","парадокс","дилемма","zależy od","niejednoznaczne","wiele czynników","system","wzajemnie połączone","nieprzewidywalne","paradoks","dylemat","depends on","uncertain","many factors","complex system","interconnected","unpredictable","paradox","dilemma","trade-off"]
    COMPLICATED_MARKERS = ["много документов","несколько этапов","много частей","сложная процедура","много шагов","бюрократия","wiele dokumentów","etapy","części","skomplikowana procedura","biurokracja","kroki","many documents","multiple stages","many parts","complicated procedure","many steps","bureaucracy"]
    PAST_MARKERS = ["почему случилось","что было","анализ","причина","корень","история","раньше","прежде","откуда взялось","dlaczego się stało","co było","analiza","przyczyna","korzeń","historia","wcześniej","why happened","what was","analysis","root cause","history","before","where it came from","retrospective"]
    FUTURE_MARKERS = ["будет","план","хочу","цель","стратегия"," roadmap","через год","в будущем","к чему приведёт","прогноз","będzie","plan","chcę","cel","strategia","przyszłość","za rok","prognoza","will be","plan","want","goal","strategy","future","in a year","forecast","where this leads","vision"]

    DOMAIN_PATTERNS = {
        "immigration": ["внж","карта побыта","побыт","karta pobytu","pobyt","виза","visa","residence","immigration","urząd","migracja","stały pobyt","obywatelstwo","paszport","pasport"],
        "tax": ["налог","podatek","tax","zus","optymalizacja","jdг","ryczałt","pit","cit","vat","księgowy","księgowość","podatki","ulga","deduction","expense","cost","accountant"],
        "business": ["бизнес","firma","company","startup","business","entrepreneur","działalność gospodarcza","spółka","self-employed","b2b","ceo","founder","venture","investment"],
        "employment": ["работа","praca","job","cv","resume","hire","umowa","o pracę","zlecenie","dzieło","wakat","rekrutacja","etat","employment","contract","hiring","recruitment","position"],
        "housing": ["квартира","mieszkanie","rent","housing","nieruchomość","wynajem","kupno","sprzedaż","lokal","zakwaterowanie","apartment","flat","house","rental","lease","mortgage"],
        "legal": ["суд","sąd","court","legal","prawo","law","contract","umowa","prawnik","adwokat","radca","spór","pozew","lawsuit","attorney","lawyer","dispute","sue","claim"],
        "health": ["врач","lekarz","health","medical","zdrowie","szpital","klinika","badanie","recepta","choroba","leczenie","doctor","hospital","clinic","prescription","treatment","diagnosis","symptom"],
        "education": ["учёба","studia","education","university","szkoła","kurs","dyplom","stopień","nauka","edukacja","uczelnia","study","degree","diploma","course","learning","academy"]
    }

    CYRILLIC_PATTERN = re.compile(r'[\u0400-\u04FF]+')
    POLISH_CHARS = set('ąćęłńóśźżĄĆĘŁŃÓŚŹŻ')

    def __init__(self, cache_size: int = 1000):
        self._cache = {}
        self._cache_order = []
        self._cache_size = cache_size
        self._stats = {"total_calls": 0, "cache_hits": 0, "avg_latency_ms": 0.0}
        self._compile_all_patterns()

    def _compile_all_patterns(self):
        self.ALL_URGENCY_HIGH = self.URGENCY_HIGH + self.URGENCY_UK_HIGH
        self.ALL_URGENCY_MEDIUM = self.URGENCY_MEDIUM + self.URGENCY_UK_MEDIUM
        self.ALL_EMOTIONAL_ANXIETY = self.EMOTIONAL_ANXIETY + self.EMOTIONAL_UK_ANXIETY
        self.ALL_EMOTIONAL_FRUSTRATION = self.EMOTIONAL_FRUSTRATION + self.EMOTIONAL_UK_FRUSTRATION
        self.ALL_EMOTIONAL_EXCITEMENT = self.EMOTIONAL_EXCITEMENT + self.EMOTIONAL_UK_EXCITEMENT
        self.ALL_PROCEDURAL = self.PROCEDURAL_MARKERS + self.PROCEDURAL_UK
        self.ALL_FACTUAL = self.FACTUAL_MARKERS + self.FACTUAL_UK
        self.ALL_CREATIVE = self.CREATIVE_MARKERS + self.CREATIVE_UK
        self.ALL_ETHICAL = self.ETHICAL_MARKERS + self.ETHICAL_UK
        self.ALL_CHAOS = self.CHAOS_MARKERS + self.CHAOS_UK
        self.ALL_COMPLEX = self.COMPLEX_MARKERS + self.COMPLEX_UK
        self.ALL_COMPLICATED = self.COMPLICATED_MARKERS + self.COMPLICATED_UK
        self.ALL_PAST = self.PAST_MARKERS + self.PAST_UK
        self.ALL_FUTURE = self.FUTURE_MARKERS + self.FUTURE_UK
        self.ALL_DOMAINS = {}
        for domain in self.DOMAIN_PATTERNS.keys():
            base = self.DOMAIN_PATTERNS.get(domain, [])
            uk = self.DOMAIN_UK_PATTERNS.get(domain, [])
            self.ALL_DOMAINS[domain] = base + uk

    async def analyze(self, query: str, user_context: Optional[Dict] = None) -> TaskProfile:
        start_time = time.perf_counter()
        user_context = user_context or {}
        cache_key = self._get_cache_key(query, user_context)
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            cached = self._cache[cache_key]
            cached.processing_time_ms = 0.0
            return cached
        query_lower = query.lower().strip()
        words = set(query_lower.split())
        time_dim = self._detect_temporal_orientation(query_lower, words)
        knowledge_dims = self._detect_knowledge_domain(query_lower, words)
        complexity = self._detect_complexity(query_lower, words)
        emotional = self._calculate_emotional_load(query_lower, words, user_context)
        urgency = self._calculate_urgency(query_lower, words)
        ambiguity = self._calculate_ambiguity(query, knowledge_dims, words)
        depth = self._calculate_depth(emotional, complexity, urgency, knowledge_dims)
        domains = self._extract_domains(query_lower)
        language = self._detect_language(query, words)
        dimensions = {time_dim} | knowledge_dims | {complexity}
        confidence = self._calculate_confidence(dimensions, ambiguity, query)
        profile = TaskProfile(
            dimensions=dimensions, required_depth=depth, emotional_load=emotional,
            urgency=urgency, ambiguity_score=ambiguity, domain_hints=domains,
            suggested_language=language,
            processing_time_ms=(time.perf_counter() - start_time) * 1000,
            confidence_score=confidence)
        self._update_cache(cache_key, profile)
        self._stats["total_calls"] += 1
        total = self._stats["total_calls"]
        current_avg = self._stats["avg_latency_ms"]
        self._stats["avg_latency_ms"] = (current_avg * (total - 1) + profile.processing_time_ms) / total
        return profile

    def _detect_language(self, query: str, words: Set[str]) -> str:
        query_lower = query.lower()
        uk_specific_chars = set('іїєґ')
        ru_specific_chars = set('ыэъё')
        has_uk_chars = any(c in query_lower for c in uk_specific_chars)
        has_ru_chars = any(c in query_lower for c in ru_specific_chars)
        uk_markers = ['як','що','чи','для','це','але','вже','також','тому','отримати','роботи','бізнес','гроші','люди','країна','побит','карта побиту','побиту','внж','польщі','варшаві']
        uk_word_count = sum(1 for word in uk_markers if word in query_lower)
        if has_uk_chars or uk_word_count >= 2:
            return "uk"
        if has_ru_chars:
            return "ru"
        if self.CYRILLIC_PATTERN.search(query):
            pl_translit = ['jak','karta','pobytu','praca','polsce','warszawie']
            if any(w in query_lower for w in pl_translit):
                return "pl"
            return "uk"
        if any(c in self.POLISH_CHARS for c in query):
            return "pl"
        english_common = {"the","and","for","are","but","not","you","all","can","how","what"}
        if words & english_common:
            return "en"
        return "pl"

    def _detect_temporal_orientation(self, query: str, words: Set[str]) -> CognitiveDimension:
        past_score = sum(1 for m in self.ALL_PAST if m in query)
        future_score = sum(1 for m in self.ALL_FUTURE if m in query)
        if past_score > future_score:
            return CognitiveDimension.PAST
        if future_score > past_score:
            return CognitiveDimension.FUTURE
        if any(w in query for w in ["як","jak","how to","co zrobić","як зробити"]):
            return CognitiveDimension.FUTURE
        if any(w in query for w in ["що таке","co to","what is","що означає"]):
            return CognitiveDimension.PRESENT
        return CognitiveDimension.FUTURE

    def _detect_knowledge_domain(self, query: str, words: Set[str]) -> Set[CognitiveDimension]:
        dims = set()
        if any(m in query for m in self.ALL_PROCEDURAL): dims.add(CognitiveDimension.PROCEDURAL)
        if any(m in query for m in self.ALL_FACTUAL):    dims.add(CognitiveDimension.FACTUAL)
        if any(m in query for m in self.ALL_CREATIVE):   dims.add(CognitiveDimension.CREATIVE)
        if any(m in query for m in self.ALL_ETHICAL):    dims.add(CognitiveDimension.ETHICAL)
        if not dims: dims.add(CognitiveDimension.PROCEDURAL)
        return dims

    def _detect_complexity(self, query: str, words: Set[str]) -> CognitiveDimension:
        if any(m in query for m in self.ALL_CHAOS):        return CognitiveDimension.CHAOTIC
        if any(m in query for m in self.ALL_COMPLEX):      return CognitiveDimension.COMPLEX
        if any(m in query for m in self.ALL_COMPLICATED):  return CognitiveDimension.COMPLICATED
        return CognitiveDimension.COMPLICATED

    def _calculate_emotional_load(self, query: str, words: Set[str], context: Dict) -> float:
        score = 0.0
        score += sum(1 for m in self.ALL_EMOTIONAL_ANXIETY if m in query) * 0.25
        score += sum(1 for m in self.ALL_EMOTIONAL_FRUSTRATION if m in query) * 0.2
        score += sum(1 for m in self.ALL_EMOTIONAL_EXCITEMENT if m in query) * 0.1
        if "!" in query: score += 0.05 * query.count("!")
        score += len([w for w in words if w.isupper() and len(w) > 2]) * 0.1
        if context.get("previous_stressful_sessions"): score += 0.15
        return min(score, 1.0)

    def _calculate_urgency(self, query: str, words: Set[str]) -> float:
        high = sum(1 for m in self.ALL_URGENCY_HIGH if m in query)
        if high > 0: return min(0.3 + high * 0.2, 1.0)
        medium = sum(1 for m in self.ALL_URGENCY_MEDIUM if m in query)
        if medium > 0: return 0.6
        urgent_time = ["сьогодні","dzisiaj","today","завтра вранці","jutro rano","tomorrow morning"]
        if any(t in query for t in urgent_time): return 0.8
        return 0.3

    def _calculate_ambiguity(self, query: str, knowledge_dims: Set[CognitiveDimension], words: Set[str]) -> float:
        score = len(knowledge_dims) * 0.15
        word_count = len(words)
        if word_count < 5: score += 0.3
        elif word_count < 10: score += 0.15
        vague = ["щось","якось","something","somehow","і т.д.","itp","таке"]
        score += sum(0.1 for t in vague if t in query)
        if not re.search(r'\d{1,4}', query): score += 0.1
        return min(score, 1.0)

    def _calculate_depth(self, emotional: float, complexity: CognitiveDimension, urgency: float, knowledge_dims: Set[CognitiveDimension]) -> int:
        base = 5
        if emotional > 0.6: base += 2
        elif emotional > 0.3: base += 1
        if complexity == CognitiveDimension.COMPLEX: base += 2
        elif complexity == CognitiveDimension.CHAOTIC: base += 1
        if CognitiveDimension.CREATIVE in knowledge_dims: base += 1
        if CognitiveDimension.ETHICAL in knowledge_dims: base += 1
        if urgency > 0.8: base = max(base - 2, 3)
        elif urgency > 0.5: base = max(base - 1, 4)
        return min(base, 10)

    def _extract_domains(self, query: str) -> Dict[str, float]:
        domains = {}
        for domain, patterns in self.ALL_DOMAINS.items():
            matches = sum(1 for p in patterns if p in query)
            if matches > 0:
                domains[domain] = round(min(0.3 + (matches - 1) * 0.2, 0.9), 2)
        return domains

    def _calculate_confidence(self, dimensions: Set[CognitiveDimension], ambiguity: float, query: str) -> float:
        base = 0.8 - ambiguity * 0.3
        if len(dimensions) > 3: base -= 0.1
        if len(query.split()) < 5: base -= 0.1
        return max(base, 0.3)

    def _get_cache_key(self, query: str, context: Dict) -> str:
        context_str = str(sorted(context.items())) if context else ""
        return hashlib.md5(f"{query.lower().strip()}:{context_str}".encode()).hexdigest()[:16]

    def _update_cache(self, key: str, profile: TaskProfile):
        if key in self._cache:
            self._cache_order.remove(key)
        elif len(self._cache) >= self._cache_size:
            oldest = self._cache_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = profile
        self._cache_order.append(key)

    def get_stats(self) -> Dict:
        total = self._stats["total_calls"]
        hits = self._stats["cache_hits"]
        return {**self._stats, "cache_hit_rate": hits / total if total > 0 else 0.0,
                "cache_size": len(self._cache)}
