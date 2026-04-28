"""
ExperienceRanker — вычисляет итоговый score для контекста.
Формула: semantic * sw + experience * ew
Режимы и веса задокументированы в архитектурных принципах v3.0.
"""


class ExperienceRanker:
    """Взвешивает семантическую релевантность и опытную полезность."""

    WEIGHTS = {
        "standard":     (0.6, 0.4),
        "deep_analysis":(0.7, 0.3),
        "crisis":       (0.85, 0.15),
        "reflection":   (0.45, 0.55),
        "planning":     (0.5, 0.5),
    }

    def score(
        self,
        semantic: float,
        experience: float,
        mode: str = "standard",
    ) -> float:
        """
        Возвращает взвешенный score [0.0 … 1.0].

        Args:
            semantic:   оценка семантической похожести (0–1)
            experience: оценка опытной полезности (0–1)
            mode:       режим работы совета

        Returns:
            float: итоговый score
        """
        sw, ew = self.WEIGHTS.get(mode, self.WEIGHTS["standard"])
        return round(semantic * sw + experience * ew, 4)
